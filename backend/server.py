"""
Barbershop Autopilot MVP - Main FastAPI Server
"""
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Header
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import uuid
import jwt
from passlib.context import CryptContext

# Load environment
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Import models
from models import (
    Shop, Barber, Service, Client, Appointment, Message, Waitlist, Payment, Event,
    AppointmentStatus, MessageDirection, EventType, PaymentStatus as PaymentStatusEnum,
    LoginRequest, TokenResponse, SMSConsentRequest, PolicyUpdate, SendTestSMSRequest,
    SendTestEmailRequest, AdminUser, EmailOutbox, AuditProvider, AuditAction
)

# Import providers and agents
from providers import get_sms, get_email, get_payment, get_calendar
from providers.interfaces import SMSMessage, EmailMessage
from agents import FrontDeskAgent, NoShowEnforcementAgent, WaitlistFillAgent

# Import compliance and audit services
from audit import create_audit_logger
from sms_compliance import (
    SMSComplianceService, create_sms_service, 
    is_opt_out_message, is_twilio_enabled
)
from revenue_logger import (
    create_revenue_logger,
    log_no_show_fee_on_payment_success,
    log_waitlist_fill_on_booking_success
)

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'barbershop_autopilot')]

# Auth configuration
SECRET_KEY = os.environ.get('JWT_SECRET', 'barbershop-autopilot-secret-key-change-in-production')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Barbershop Autopilot",
    description="Reduce no-shows and recover lost revenue for barbershops",
    version="1.0.0"
)

# Create API router
api_router = APIRouter(prefix="/api")


# ==================== AUTH UTILITIES ====================

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = authorization.split(" ")[1]
    payload = verify_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return payload


async def get_shop(user: dict = Depends(get_current_user)) -> Shop:
    """Get the shop for the current user"""
    shop_data = await db.shops.find_one({"id": user.get("shop_id")}, {"_id": 0})
    if not shop_data:
        raise HTTPException(status_code=404, detail="Shop not found")
    return Shop(**shop_data)


# ==================== AUTH ENDPOINTS ====================

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Admin login"""
    admin = await db.admin_users.find_one({"username": request.username}, {"_id": 0})
    
    if not admin or not pwd_context.verify(request.password, admin["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Update last login
    await db.admin_users.update_one(
        {"id": admin["id"]},
        {"$set": {"last_login": datetime.now(timezone.utc).isoformat()}}
    )
    
    token = create_access_token({
        "sub": admin["id"],
        "username": admin["username"],
        "shop_id": admin["shop_id"]
    })
    
    return TokenResponse(access_token=token)


@api_router.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    """Get current user info"""
    return {
        "id": user.get("sub"),
        "username": user.get("username"),
        "shop_id": user.get("shop_id")
    }


# ==================== SHOP ENDPOINTS ====================

@api_router.get("/shop")
async def get_shop_info(shop: Shop = Depends(get_shop)):
    """Get shop information"""
    return shop.model_dump()


@api_router.patch("/shop/policy")
async def update_shop_policy(update: PolicyUpdate, shop: Shop = Depends(get_shop)):
    """Update shop policies"""
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.shops.update_one(
        {"id": shop.id},
        {"$set": update_data}
    )
    
    return {"message": "Policy updated successfully"}


# ==================== DASHBOARD ENDPOINTS ====================

@api_router.get("/dashboard/stats")
async def get_dashboard_stats(shop: Shop = Depends(get_shop)):
    """Get dashboard statistics"""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)
    month_start = today_start - timedelta(days=30)
    
    # Appointments today
    appointments_today = await db.appointments.count_documents({
        "shop_id": shop.id,
        "scheduled_at": {"$gte": today_start.isoformat(), "$lt": (today_start + timedelta(days=1)).isoformat()}
    })
    
    # Total appointments this month
    appointments_month = await db.appointments.count_documents({
        "shop_id": shop.id,
        "scheduled_at": {"$gte": month_start.isoformat()}
    })
    
    # No-shows this month
    no_shows_month = await db.appointments.count_documents({
        "shop_id": shop.id,
        "status": AppointmentStatus.NO_SHOW.value,
        "scheduled_at": {"$gte": month_start.isoformat()}
    })
    
    # Revenue recovered (from events)
    revenue_pipeline = [
        {"$match": {
            "shop_id": shop.id,
            "created_at": {"$gte": month_start.isoformat()},
            "revenue_impact": {"$gt": 0}
        }},
        {"$group": {"_id": None, "total": {"$sum": "$revenue_impact"}}}
    ]
    revenue_result = await db.events.aggregate(revenue_pipeline).to_list(1)
    revenue_recovered = revenue_result[0]["total"] if revenue_result else 0
    
    # Waitlist count
    waitlist_count = await db.waitlist.count_documents({
        "shop_id": shop.id,
        "active": True
    })
    
    # Messages today
    messages_today = await db.messages.count_documents({
        "shop_id": shop.id,
        "created_at": {"$gte": today_start.isoformat()}
    })
    
    # Deposits collected this month
    deposits_pipeline = [
        {"$match": {
            "shop_id": shop.id,
            "status": "completed",
            "payment_type": "deposit",
            "created_at": {"$gte": month_start.isoformat()}
        }},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]
    deposits_result = await db.payments.aggregate(deposits_pipeline).to_list(1)
    deposits_collected = deposits_result[0]["total"] if deposits_result else 0
    
    return {
        "appointments_today": appointments_today,
        "appointments_month": appointments_month,
        "no_shows_month": no_shows_month,
        "revenue_recovered": revenue_recovered,
        "waitlist_count": waitlist_count,
        "messages_today": messages_today,
        "deposits_collected": deposits_collected,
        "no_show_rate": round((no_shows_month / appointments_month * 100) if appointments_month > 0 else 0, 1)
    }


@api_router.get("/dashboard/revenue-chart")
async def get_revenue_chart(shop: Shop = Depends(get_shop), days: int = 30):
    """Get revenue data for chart"""
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=days)
    
    # Aggregate revenue by day
    pipeline = [
        {"$match": {
            "shop_id": shop.id,
            "created_at": {"$gte": start_date.isoformat()}
        }},
        {"$addFields": {
            "date": {"$substr": ["$created_at", 0, 10]}
        }},
        {"$group": {
            "_id": "$date",
            "recovered": {"$sum": {"$cond": [{"$gt": ["$revenue_impact", 0]}, "$revenue_impact", 0]}},
            "lost": {"$sum": {"$cond": [{"$lt": ["$revenue_impact", 0]}, {"$abs": "$revenue_impact"}, 0]}}
        }},
        {"$sort": {"_id": 1}}
    ]
    
    results = await db.events.aggregate(pipeline).to_list(100)
    
    return {
        "data": [
            {"date": r["_id"], "recovered": r["recovered"], "lost": r["lost"]}
            for r in results
        ]
    }


# ==================== APPOINTMENT ENDPOINTS ====================

@api_router.get("/appointments")
async def list_appointments(
    shop: Shop = Depends(get_shop),
    status: Optional[str] = None,
    date: Optional[str] = None,
    limit: int = 50,
    skip: int = 0
):
    """List appointments"""
    query = {"shop_id": shop.id}
    
    if status:
        query["status"] = status
    
    if date:
        query["scheduled_at"] = {"$gte": date, "$lt": f"{date}T23:59:59"}
    
    appointments = await db.appointments.find(
        query, {"_id": 0}
    ).sort("scheduled_at", -1).skip(skip).limit(limit).to_list(limit)
    
    # Enrich with client and service info
    for apt in appointments:
        client = await db.clients.find_one({"id": apt["client_id"]}, {"_id": 0, "name": 1, "phone": 1})
        service = await db.services.find_one({"id": apt["service_id"]}, {"_id": 0, "name": 1})
        barber = await db.barbers.find_one({"id": apt["barber_id"]}, {"_id": 0, "name": 1})
        apt["client"] = client
        apt["service"] = service
        apt["barber"] = barber
    
    total = await db.appointments.count_documents(query)
    
    return {"appointments": appointments, "total": total}


@api_router.get("/appointments/{appointment_id}")
async def get_appointment(appointment_id: str, shop: Shop = Depends(get_shop)):
    """Get appointment details"""
    appointment = await db.appointments.find_one(
        {"id": appointment_id, "shop_id": shop.id},
        {"_id": 0}
    )
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    return appointment


@api_router.patch("/appointments/{appointment_id}/status")
async def update_appointment_status(
    appointment_id: str,
    status: str,
    shop: Shop = Depends(get_shop)
):
    """Update appointment status"""
    valid_statuses = [s.value for s in AppointmentStatus]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    
    result = await db.appointments.update_one(
        {"id": appointment_id, "shop_id": shop.id},
        {"$set": {
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    return {"message": "Status updated"}


# ==================== CLIENT ENDPOINTS ====================

@api_router.get("/clients")
async def list_clients(
    shop: Shop = Depends(get_shop),
    search: Optional[str] = None,
    limit: int = 50,
    skip: int = 0
):
    """List clients"""
    query = {"shop_id": shop.id}
    
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"phone": {"$regex": search}}
        ]
    
    clients = await db.clients.find(
        query, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    
    total = await db.clients.count_documents(query)
    
    return {"clients": clients, "total": total}


@api_router.get("/clients/{client_id}")
async def get_client(client_id: str, shop: Shop = Depends(get_shop)):
    """Get client details"""
    client = await db.clients.find_one(
        {"id": client_id, "shop_id": shop.id},
        {"_id": 0}
    )
    
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    return client


# ==================== CONVERSATION ENDPOINTS ====================

@api_router.get("/conversations")
async def list_conversations(shop: Shop = Depends(get_shop), limit: int = 50):
    """List conversation threads (grouped by client)"""
    # Get unique clients with messages, sorted by most recent
    pipeline = [
        {"$match": {"shop_id": shop.id}},
        {"$sort": {"created_at": -1}},
        {"$group": {
            "_id": "$client_id",
            "last_message": {"$first": "$content"},
            "last_message_at": {"$first": "$created_at"},
            "last_direction": {"$first": "$direction"},
            "message_count": {"$sum": 1}
        }},
        {"$sort": {"last_message_at": -1}},
        {"$limit": limit}
    ]
    
    threads = await db.messages.aggregate(pipeline).to_list(limit)
    
    # Enrich with client info
    for thread in threads:
        client = await db.clients.find_one(
            {"id": thread["_id"]},
            {"_id": 0, "name": 1, "phone": 1}
        )
        thread["client"] = client
        thread["client_id"] = thread.pop("_id")
    
    return {"conversations": threads}


@api_router.get("/conversations/{client_id}")
async def get_conversation(client_id: str, shop: Shop = Depends(get_shop), limit: int = 100):
    """Get messages for a specific client"""
    messages = await db.messages.find(
        {"shop_id": shop.id, "client_id": client_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    # Reverse to show oldest first
    messages.reverse()
    
    client = await db.clients.find_one(
        {"id": client_id, "shop_id": shop.id},
        {"_id": 0}
    )
    
    return {"messages": messages, "client": client}


# ==================== WAITLIST ENDPOINTS ====================

@api_router.get("/waitlist")
async def list_waitlist(shop: Shop = Depends(get_shop)):
    """List active waitlist entries"""
    entries = await db.waitlist.find(
        {"shop_id": shop.id, "active": True},
        {"_id": 0}
    ).sort("created_at", 1).to_list(100)
    
    # Enrich with client and service info
    for entry in entries:
        client = await db.clients.find_one({"id": entry["client_id"]}, {"_id": 0, "name": 1, "phone": 1})
        service = await db.services.find_one({"id": entry["service_id"]}, {"_id": 0, "name": 1})
        entry["client"] = client
        entry["service"] = service
    
    return {"waitlist": entries}


@api_router.delete("/waitlist/{entry_id}")
async def remove_from_waitlist(entry_id: str, shop: Shop = Depends(get_shop)):
    """Remove entry from waitlist"""
    result = await db.waitlist.update_one(
        {"id": entry_id, "shop_id": shop.id},
        {"$set": {"active": False}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Waitlist entry not found")
    
    return {"message": "Removed from waitlist"}


# ==================== BARBER & SERVICE ENDPOINTS ====================

@api_router.get("/barbers")
async def list_barbers(shop: Shop = Depends(get_shop)):
    """List barbers"""
    barbers = await db.barbers.find(
        {"shop_id": shop.id, "active": True},
        {"_id": 0}
    ).to_list(50)
    return {"barbers": barbers}


@api_router.get("/services")
async def list_services(shop: Shop = Depends(get_shop)):
    """List services"""
    services = await db.services.find(
        {"shop_id": shop.id, "active": True},
        {"_id": 0}
    ).to_list(50)
    return {"services": services}


# ==================== SMS ENDPOINTS ====================

@api_router.post("/sms/send-test")
async def send_test_sms(request: SendTestSMSRequest, shop: Shop = Depends(get_shop)):
    """Send a test SMS (only works when TWILIO_ENABLED=true)"""
    twilio_enabled = os.environ.get("TWILIO_ENABLED", "").lower() in ("true", "1", "yes")
    
    if not twilio_enabled:
        raise HTTPException(
            status_code=400,
            detail="SMS sending is disabled. Set TWILIO_ENABLED=true and configure credentials."
        )
    
    sms = get_sms()
    response = await sms.send_sms(SMSMessage(
        to=request.to_phone,
        body=request.message
    ))
    
    if not response.success:
        raise HTTPException(status_code=500, detail=response.error or "Failed to send SMS")
    
    return {"message": "Test SMS sent", "message_id": response.message_id}


@api_router.post("/email/send-test")
async def send_test_email(request: SendTestEmailRequest, shop: Shop = Depends(get_shop)):
    """Send a test email (only works when SEND_EMAILS=true)"""
    send_emails = os.environ.get("SEND_EMAILS", "").lower() in ("true", "1", "yes")
    
    if not send_emails:
        raise HTTPException(
            status_code=400,
            detail="Email sending is disabled. Set SEND_EMAILS=true and configure SENDGRID_API_KEY."
        )
    
    email_provider = get_email(db)
    response = await email_provider.send_email(EmailMessage(
        to=request.to_email,
        subject=request.subject,
        html_content=f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #D4AF37; padding: 20px; text-align: center;">
                <h1 style="color: #000; margin: 0;">✂️ Barbershop Autopilot</h1>
            </div>
            <div style="padding: 30px; background-color: #18181b; color: #fafafa;">
                <h2 style="color: #D4AF37;">Test Email</h2>
                <p>{request.message}</p>
                <hr style="border-color: #27272a; margin: 20px 0;">
                <p style="color: #a1a1aa; font-size: 12px;">
                    This email was sent from {shop.name} to verify SendGrid integration.
                </p>
            </div>
        </body>
        </html>
        """,
        plain_content=request.message
    ))
    
    if not response.success:
        raise HTTPException(status_code=500, detail=response.error or "Failed to send email")
    
    return {"message": "Test email sent", "message_id": response.message_id}


# ==================== WEBHOOK ENDPOINTS ====================

@api_router.post("/webhooks/twilio/inbound")
async def twilio_inbound_webhook(request: Request):
    """Handle inbound SMS from Twilio with compliance enforcement"""
    form_data = await request.form()
    
    from_number = form_data.get("From", "")
    to_number = form_data.get("To", "")
    body = form_data.get("Body", "")
    message_sid = form_data.get("MessageSid", "")
    
    logger.info(f"Inbound SMS from {from_number}: {body[:50]}...")
    
    # Find shop by phone number
    shop_data = await db.shops.find_one({"phone": to_number}, {"_id": 0})
    if not shop_data:
        logger.warning(f"No shop found for number {to_number}")
        return JSONResponse(content={"status": "no_shop"})
    
    shop = Shop(**shop_data)
    
    # Initialize audit logger and SMS compliance service
    audit_logger = create_audit_logger(db, shop.id)
    sms_service = create_sms_service(db, shop.id, audit_logger)
    
    # Find or create client
    client_data = await db.clients.find_one(
        {"shop_id": shop.id, "phone": from_number},
        {"_id": 0}
    )
    
    if not client_data:
        # Create new client with consent (implied from inbound SMS)
        client_data = {
            "id": str(uuid.uuid4()),
            "shop_id": shop.id,
            "name": "New Client",
            "phone": from_number,
            "sms_consent": True,  # Implied consent from inbound message
            "sms_consent_timestamp": datetime.now(timezone.utc).isoformat(),
            "sms_consent_source": "inbound_sms",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        await db.clients.insert_one(client_data)
    
    client = Client(**client_data)
    
    # Store inbound message
    await db.messages.insert_one({
        "id": str(uuid.uuid4()),
        "shop_id": shop.id,
        "client_id": client.id,
        "direction": MessageDirection.INBOUND.value,
        "message_type": "sms",
        "content": body,
        "twilio_sid": message_sid,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    # ===== COMPLIANCE: Handle STOP/Opt-Out =====
    if is_opt_out_message(body):
        await sms_service.process_opt_out(client.id, from_number)
        return JSONResponse(content={"status": "opt_out_processed"})
    
    # Process with FrontDeskAgent (business logic unchanged)
    agent = FrontDeskAgent(db, shop)
    response_text, metadata = await agent.process_inbound_message(client, body)
    
    # Check rate limit
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    outbound_count = await db.messages.count_documents({
        "shop_id": shop.id,
        "client_id": client.id,
        "direction": MessageDirection.OUTBOUND.value,
        "created_at": {"$gte": today_start.isoformat()}
    })
    
    if outbound_count >= shop.max_messages_per_day:
        logger.warning(f"Rate limit reached for client {client.id}")
        return JSONResponse(content={"status": "rate_limited"})
    
    # ===== COMPLIANCE: Send response via SMS service (enforces consent) =====
    sms_response = await sms_service.send_sms(
        client_id=client.id,
        to_phone=from_number,
        message=response_text
    )
    
    # Store outbound message
    await db.messages.insert_one({
        "id": str(uuid.uuid4()),
        "shop_id": shop.id,
        "client_id": client.id,
        "direction": MessageDirection.OUTBOUND.value,
        "message_type": "sms",
        "content": response_text,
        "twilio_sid": sms_response.message_id,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    return JSONResponse(content={"status": "processed", "action": metadata.get("action")})


@api_router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks"""
    body = await request.body()
    signature = request.headers.get("Stripe-Signature", "")
    
    payment = get_payment()
    result = await payment.handle_webhook(body, signature)
    
    if result.get("error"):
        logger.error(f"Stripe webhook error: {result['error']}")
        return JSONResponse(content={"status": "error"}, status_code=400)
    
    # Update payment status if we have a session_id
    if "session_id" in result:
        # Find the payment record
        payment_record = await db.payments.find_one(
            {"stripe_session_id": result["session_id"]},
            {"_id": 0}
        )
        
        if payment_record and result.get("payment_status") == "paid":
            # Update payment status
            await db.payments.update_one(
                {"stripe_session_id": result["session_id"]},
                {"$set": {
                    "status": "completed",
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            
            # Hook: Log no-show fee revenue if applicable
            if payment_record.get("appointment_id"):
                appointment = await db.appointments.find_one(
                    {"id": payment_record["appointment_id"]},
                    {"_id": 0}
                )
                if appointment:
                    await log_no_show_fee_on_payment_success(db, payment_record, appointment)
        elif payment_record:
            await db.payments.update_one(
                {"stripe_session_id": result["session_id"]},
                {"$set": {
                    "status": "failed",
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
    
    return JSONResponse(content={"status": "received"})


# ==================== PUBLIC ENDPOINTS (NO AUTH) ====================

@api_router.post("/public/sms-consent")
async def submit_sms_consent(request: SMSConsentRequest):
    """Public endpoint for SMS consent form (compliance-compliant)"""
    # Find shop (using first shop for MVP)
    shop_data = await db.shops.find_one({}, {"_id": 0})
    if not shop_data:
        raise HTTPException(status_code=500, detail="Shop not configured")
    
    shop = Shop(**shop_data)
    
    # Find or create client
    client_data = await db.clients.find_one(
        {"shop_id": shop.id, "phone": request.phone},
        {"_id": 0}
    )
    
    consent_timestamp = datetime.now(timezone.utc).isoformat() if request.consent else None
    
    if client_data:
        # Update existing client with proper consent tracking
        await db.clients.update_one(
            {"id": client_data["id"]},
            {"$set": {
                "name": request.name,
                "sms_consent": request.consent,
                "sms_consent_timestamp": consent_timestamp,
                "sms_consent_source": "web_form",
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
    else:
        # Create new client with proper consent tracking
        client_data = {
            "id": str(uuid.uuid4()),
            "shop_id": shop.id,
            "name": request.name,
            "phone": request.phone,
            "sms_consent": request.consent,
            "sms_consent_timestamp": consent_timestamp,
            "sms_consent_source": "web_form",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        await db.clients.insert_one(client_data)
    
    return {"message": "Consent recorded", "consent": request.consent}


@api_router.get("/public/shop-info")
async def get_public_shop_info():
    """Get public shop information"""
    shop_data = await db.shops.find_one({}, {"_id": 0, "name": 1, "phone": 1, "address": 1, "business_hours": 1})
    if not shop_data:
        raise HTTPException(status_code=404, detail="Shop not found")
    return shop_data


# ==================== MOCK PAYMENT ENDPOINT ====================

@api_router.get("/mock-payment")
async def mock_payment_page(session_id: str):
    """Mock payment endpoint for local testing"""
    from providers.mock_providers import MockPaymentProvider
    
    payment = get_payment()
    if isinstance(payment, MockPaymentProvider):
        # Auto-complete the payment in mock mode
        await payment.complete_payment(session_id)
        
        # Get session info
        status = await payment.get_payment_status(session_id)
        
        # If there's an appointment_id in metadata, update the appointment
        appointment_id = status.metadata.get("appointment_id")
        if appointment_id:
            await db.appointments.update_one(
                {"id": appointment_id},
                {"$set": {
                    "deposit_paid": True,
                    "status": AppointmentStatus.DEPOSIT_PAID.value,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            
            # Update payment record
            await db.payments.update_one(
                {"stripe_session_id": session_id},
                {"$set": {
                    "status": "completed",
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            
            # Hook: Log no-show fee revenue if applicable
            payment_record = await db.payments.find_one(
                {"stripe_session_id": session_id},
                {"_id": 0}
            )
            appointment = await db.appointments.find_one(
                {"id": appointment_id},
                {"_id": 0}
            )
            if payment_record and appointment:
                await log_no_show_fee_on_payment_success(db, payment_record, appointment)
        
        return {
            "status": "success",
            "message": "Mock payment completed",
            "session_id": session_id,
            "amount": status.amount
        }
    
    raise HTTPException(status_code=400, detail="Not in mock mode")


# ==================== EMAIL OUTBOX ENDPOINT ====================

@api_router.get("/email-outbox")
async def list_email_outbox(shop: Shop = Depends(get_shop)):
    """List emails in outbox (for debugging mock mode)"""
    emails = await db.email_outbox.find(
        {"shop_id": shop.id},
        {"_id": 0}
    ).sort("created_at", -1).limit(50).to_list(50)
    
    return {"emails": emails}


@api_router.get("/audit-log")
async def list_audit_log(
    shop: Shop = Depends(get_shop),
    provider: Optional[str] = None,
    limit: int = 100
):
    """List integration audit log entries"""
    query = {"shop_id": shop.id}
    
    if provider:
        query["provider"] = provider
    
    entries = await db.integration_audit_log.find(
        query, {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    return {"audit_log": entries, "count": len(entries)}


@api_router.get("/internal/recovered-revenue")
async def list_recovered_revenue_events(
    shop: Shop = Depends(get_shop),
    source: Optional[str] = None,
    limit: int = 100
):
    """
    Internal endpoint to query recovered revenue events.
    NOT for UI display - for debugging and verification only.
    """
    query = {"shop_id": shop.id}
    
    if source:
        query["source"] = source
    
    events = await db.recovered_revenue_events.find(
        query, {"_id": 0}
    ).sort("attributed_at", -1).limit(limit).to_list(limit)
    
    # Calculate totals for verification (NOT for display)
    total_amount = sum(e.get("amount", 0) for e in events)
    
    return {
        "events": events,
        "count": len(events),
        "_internal_total": total_amount,
        "_note": "This data is for internal attribution only. NOT for owner-facing display."
    }


# ==================== HEALTH CHECK ====================

@api_router.get("/")
async def root():
    return {"message": "Barbershop Autopilot API", "version": "1.0.0"}


@api_router.get("/health")
async def health_check():
    """Health check with provider status"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "providers": {
            "twilio_enabled": os.environ.get("TWILIO_ENABLED", "false").lower() in ("true", "1", "yes"),
            "stripe_enabled": os.environ.get("STRIPE_ENABLED", "false").lower() in ("true", "1", "yes"),
            "sendgrid_enabled": os.environ.get("SEND_EMAILS", "false").lower() in ("true", "1", "yes"),
            "calendar_enabled": os.environ.get("CALENDAR_ENABLED", "false").lower() in ("true", "1", "yes")
        },
        "compliance": {
            "sms_consent_enforced": True,
            "stop_handling_enabled": True,
            "audit_logging_enabled": True
        }
    }


# Include router
app.include_router(api_router)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== STARTUP EVENT ====================

@app.on_event("startup")
async def startup_event():
    """Initialize database with seed data if empty"""
    logger.info("Starting Barbershop Autopilot...")
    
    # Check if shop exists
    shop_count = await db.shops.count_documents({})
    
    if shop_count == 0:
        logger.info("Seeding demo data...")
        await seed_demo_data()
    
    logger.info("Barbershop Autopilot ready!")


async def seed_demo_data():
    """Seed the database with demo barbershop data"""
    shop_id = "demo_shop"
    
    # Create shop
    shop = {
        "id": shop_id,
        "name": "Classic Cuts Barbershop",
        "phone": "+15551234567",
        "email": "info@classiccuts.local",
        "address": "123 Main Street, Anytown, USA",
        "timezone": "America/New_York",
        "business_hours": {
            "monday": {"open": "09:00", "close": "18:00"},
            "tuesday": {"open": "09:00", "close": "18:00"},
            "wednesday": {"open": "09:00", "close": "18:00"},
            "thursday": {"open": "09:00", "close": "20:00"},
            "friday": {"open": "09:00", "close": "20:00"},
            "saturday": {"open": "08:00", "close": "17:00"},
            "sunday": None
        },
        "deposit_amount": 20.0,
        "deposit_required_hours": 48,
        "confirmation_window_hours": 24,
        "cancellation_window_hours": 4,
        "max_messages_per_day": 4,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await db.shops.insert_one(shop)
    
    # Create barbers
    barbers = [
        {"id": "barber_1", "shop_id": shop_id, "name": "Marcus Johnson", "email": "marcus@classiccuts.local", "active": True, "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": "barber_2", "shop_id": shop_id, "name": "David Lee", "email": "david@classiccuts.local", "active": True, "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": "barber_3", "shop_id": shop_id, "name": "Anthony Davis", "email": "anthony@classiccuts.local", "active": True, "created_at": datetime.now(timezone.utc).isoformat()},
    ]
    await db.barbers.insert_many(barbers)
    
    # Create services
    services = [
        {"id": "service_1", "shop_id": shop_id, "name": "Classic Haircut", "description": "Traditional haircut with clippers and scissors", "duration_minutes": 30, "price": 25.0, "active": True, "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": "service_2", "shop_id": shop_id, "name": "Haircut + Beard Trim", "description": "Full haircut with beard shaping", "duration_minutes": 45, "price": 35.0, "active": True, "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": "service_3", "shop_id": shop_id, "name": "Premium Cut + Hot Towel", "description": "Deluxe haircut with hot towel treatment", "duration_minutes": 60, "price": 50.0, "active": True, "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": "service_4", "shop_id": shop_id, "name": "Kids Cut", "description": "Haircut for children under 12", "duration_minutes": 20, "price": 15.0, "active": True, "created_at": datetime.now(timezone.utc).isoformat()},
    ]
    await db.services.insert_many(services)
    
    # Create demo clients with proper consent tracking
    consent_timestamp = datetime.now(timezone.utc).isoformat()
    clients = [
        {"id": "client_1", "shop_id": shop_id, "name": "John Smith", "phone": "+15559876543", "email": "john@example.com", "sms_consent": True, "sms_consent_timestamp": consent_timestamp, "sms_consent_source": "web_form", "total_appointments": 5, "no_shows": 0, "created_at": datetime.now(timezone.utc).isoformat(), "updated_at": datetime.now(timezone.utc).isoformat()},
        {"id": "client_2", "shop_id": shop_id, "name": "Mike Wilson", "phone": "+15551112222", "email": "mike@example.com", "sms_consent": True, "sms_consent_timestamp": consent_timestamp, "sms_consent_source": "web_form", "total_appointments": 3, "no_shows": 1, "created_at": datetime.now(timezone.utc).isoformat(), "updated_at": datetime.now(timezone.utc).isoformat()},
        {"id": "client_3", "shop_id": shop_id, "name": "James Brown", "phone": "+15553334444", "email": "james@example.com", "sms_consent": True, "sms_consent_timestamp": consent_timestamp, "sms_consent_source": "inbound_sms", "total_appointments": 8, "no_shows": 0, "created_at": datetime.now(timezone.utc).isoformat(), "updated_at": datetime.now(timezone.utc).isoformat()},
    ]
    await db.clients.insert_many(clients)
    
    # Create demo appointments
    now = datetime.now(timezone.utc)
    appointments = [
        {
            "id": "apt_1",
            "shop_id": shop_id,
            "client_id": "client_1",
            "barber_id": "barber_1",
            "service_id": "service_1",
            "scheduled_at": (now + timedelta(hours=2)).isoformat(),
            "duration_minutes": 30,
            "status": AppointmentStatus.CONFIRMED.value,
            "deposit_required": False,
            "deposit_amount": 0,
            "deposit_paid": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        },
        {
            "id": "apt_2",
            "shop_id": shop_id,
            "client_id": "client_2",
            "barber_id": "barber_2",
            "service_id": "service_2",
            "scheduled_at": (now + timedelta(hours=4)).isoformat(),
            "duration_minutes": 45,
            "status": AppointmentStatus.DEPOSIT_PENDING.value,
            "deposit_required": True,
            "deposit_amount": 20.0,
            "deposit_paid": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        },
        {
            "id": "apt_3",
            "shop_id": shop_id,
            "client_id": "client_3",
            "barber_id": "barber_1",
            "service_id": "service_3",
            "scheduled_at": (now + timedelta(days=1, hours=3)).isoformat(),
            "duration_minutes": 60,
            "status": AppointmentStatus.PENDING.value,
            "deposit_required": False,
            "deposit_amount": 0,
            "deposit_paid": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        },
    ]
    await db.appointments.insert_many(appointments)
    
    # Create demo messages
    messages = [
        {"id": "msg_1", "shop_id": shop_id, "client_id": "client_1", "direction": MessageDirection.INBOUND.value, "message_type": "sms", "content": "Hi, I'd like to book a haircut", "created_at": (now - timedelta(hours=2)).isoformat()},
        {"id": "msg_2", "shop_id": shop_id, "client_id": "client_1", "direction": MessageDirection.OUTBOUND.value, "message_type": "sms", "content": "Hi John! Thanks for reaching out to Classic Cuts Barbershop. We have availability today at 2pm or 4pm. Which works for you?", "created_at": (now - timedelta(hours=1, minutes=55)).isoformat()},
        {"id": "msg_3", "shop_id": shop_id, "client_id": "client_1", "direction": MessageDirection.INBOUND.value, "message_type": "sms", "content": "2pm works great", "created_at": (now - timedelta(hours=1, minutes=50)).isoformat()},
        {"id": "msg_4", "shop_id": shop_id, "client_id": "client_1", "direction": MessageDirection.OUTBOUND.value, "message_type": "sms", "content": "Your appointment is confirmed! 📅 Today at 2:00 PM ✂️ Classic Haircut with Marcus Johnson. Reply CONFIRM to confirm or CANCEL to cancel.", "created_at": (now - timedelta(hours=1, minutes=45)).isoformat()},
    ]
    await db.messages.insert_many(messages)
    
    # Create demo waitlist entry
    waitlist = [
        {
            "id": "wait_1",
            "shop_id": shop_id,
            "client_id": "client_3",
            "service_id": "service_2",
            "preferred_date": (now + timedelta(days=2)).isoformat(),
            "flexible_hours": 3,
            "active": True,
            "contact_attempts": 0,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
    ]
    await db.waitlist.insert_many(waitlist)
    
    # Create demo events for revenue tracking
    events = [
        {
            "id": "event_1",
            "shop_id": shop_id,
            "event_type": EventType.WAITLIST_FILLED.value,
            "client_id": "client_1",
            "data": {"service": "Classic Haircut"},
            "revenue_impact": 25.0,
            "created_at": (now - timedelta(days=3)).isoformat()
        },
        {
            "id": "event_2",
            "shop_id": shop_id,
            "event_type": EventType.DEPOSIT_PAID.value,
            "client_id": "client_2",
            "data": {"amount": 20.0},
            "revenue_impact": 20.0,
            "created_at": (now - timedelta(days=2)).isoformat()
        },
        {
            "id": "event_3",
            "shop_id": shop_id,
            "event_type": EventType.NO_SHOW_DETECTED.value,
            "client_id": "client_2",
            "data": {"service": "Haircut + Beard Trim"},
            "revenue_impact": -35.0,
            "created_at": (now - timedelta(days=5)).isoformat()
        },
    ]
    await db.events.insert_many(events)
    
    # Create admin user
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    admin = {
        "id": "admin_1",
        "shop_id": shop_id,
        "username": "admin",
        "password_hash": pwd_context.hash(admin_password),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.admin_users.insert_one(admin)
    
    logger.info("Demo data seeded successfully!")
    logger.info(f"Admin login: username='admin', password='{admin_password}'")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
