"""Auth, shop, dashboard, and health endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime, timezone, timedelta
from typing import Optional
import os

from deps import db, pwd_context, create_access_token, get_current_user, get_shop, check_rate_limit
from models import (
    Shop, LoginRequest, TokenResponse, PolicyUpdate,
    CreateBarberRequest, UpdateBarberRequest,
    CreateServiceRequest, UpdateServiceRequest,
    UpdateShopDetailsRequest,
)
import uuid

router = APIRouter()


# ==================== AUTH ====================

@router.post("/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest, raw_request: Request):
    client_ip = raw_request.client.host if raw_request.client else "unknown"
    if not check_rate_limit(f"login:{client_ip}", max_requests=10, window_seconds=300):
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")

    admin = await db.admin_users.find_one({"username": request.username}, {"_id": 0})
    if not admin or not pwd_context.verify(request.password, admin["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": admin["id"], "username": admin["username"], "shop_id": admin["shop_id"]})
    return TokenResponse(access_token=token, token_type="bearer")


@router.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    admin = await db.admin_users.find_one({"id": user["sub"]}, {"_id": 0, "password_hash": 0})
    if not admin:
        raise HTTPException(status_code=404, detail="User not found")
    return admin


# ==================== SHOP ====================

@router.get("/shop")
async def get_shop_info(shop: Shop = Depends(get_shop)):
    return shop.model_dump()


@router.patch("/shop/policy")
async def update_shop_policy(update: PolicyUpdate, shop: Shop = Depends(get_shop)):
    update_data = {k: v for k, v in update.model_dump(exclude_unset=True).items() if v is not None}
    if update_data:
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.shops.update_one({"id": shop.id}, {"$set": update_data})
    return {"message": "Policy updated"}


# ==================== DASHBOARD ====================

@router.get("/dashboard/stats")
async def get_dashboard_stats(shop: Shop = Depends(get_shop)):
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    week_start = (now - timedelta(days=7)).isoformat()
    month_start = (now - timedelta(days=30)).isoformat()

    # Today's appointments
    today_count = await db.appointments.count_documents({"shop_id": shop.id, "scheduled_at": {"$gte": today_start}})
    upcoming = await db.appointments.find(
        {"shop_id": shop.id, "scheduled_at": {"$gte": now.isoformat()}, "status": {"$in": ["pending", "confirmed", "deposit_paid"]}},
        {"_id": 0}
    ).sort("scheduled_at", 1).limit(5).to_list(5)

    for apt in upcoming:
        client = await db.clients.find_one({"id": apt.get("client_id")}, {"_id": 0, "name": 1, "phone": 1})
        apt["client"] = client or {"name": "Unknown", "phone": ""}

    # No-show rate (30 days)
    month_total = await db.appointments.count_documents({"shop_id": shop.id, "scheduled_at": {"$gte": month_start}})
    month_noshows = await db.appointments.count_documents({"shop_id": shop.id, "scheduled_at": {"$gte": month_start}, "status": "no_show"})
    no_show_rate = round((month_noshows / month_total * 100) if month_total > 0 else 0, 1)

    # Revenue this month
    revenue_pipeline = [
        {"$match": {"shop_id": shop.id, "status": "completed", "scheduled_at": {"$gte": month_start}}},
        {"$group": {"_id": None, "total": {"$sum": "$price"}}}
    ]
    revenue_result = await db.appointments.aggregate(revenue_pipeline).to_list(1)
    revenue = revenue_result[0]["total"] if revenue_result else 0

    # Deposits collected
    deposits_pipeline = [
        {"$match": {"shop_id": shop.id, "status": "completed", "payment_type": "deposit", "created_at": {"$gte": month_start}}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]
    deposits_result = await db.payments.aggregate(deposits_pipeline).to_list(1)
    deposits_collected = deposits_result[0]["total"] if deposits_result else 0

    # Waitlist fills
    waitlist_count = await db.waitlist.count_documents({"shop_id": shop.id, "active": True})

    # Recent events
    recent_events = await db.events.find(
        {"shop_id": shop.id}, {"_id": 0}
    ).sort("created_at", -1).limit(10).to_list(10)

    return {
        "today_appointments": today_count,
        "upcoming_appointments": upcoming,
        "no_show_rate": no_show_rate,
        "month_revenue": revenue,
        "deposits_collected": deposits_collected,
        "active_waitlist": waitlist_count,
        "recent_events": recent_events,
        "total_clients": await db.clients.count_documents({"shop_id": shop.id}),
        "month_total_appointments": month_total,
        "month_no_shows": month_noshows,
    }


@router.get("/dashboard/revenue-chart")
async def get_revenue_chart(shop: Shop = Depends(get_shop), days: int = 30):
    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=days)).isoformat()

    pipeline = [
        {"$match": {"shop_id": shop.id, "scheduled_at": {"$gte": start_date}, "status": "completed"}},
        {"$addFields": {"day": {"$substr": ["$scheduled_at", 0, 10]}}},
        {"$group": {"_id": "$day", "revenue": {"$sum": "$price"}, "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}
    ]
    data = await db.appointments.aggregate(pipeline).to_list(60)
    return {"chart_data": [{"date": d["_id"], "revenue": d["revenue"], "appointments": d["count"]} for d in data]}


# ==================== BARBERS & SERVICES ====================

@router.get("/barbers")
async def list_barbers(shop: Shop = Depends(get_shop)):
    barbers = await db.barbers.find({"shop_id": shop.id, "active": True}, {"_id": 0}).to_list(50)
    return {"barbers": barbers}


@router.get("/services")
async def list_services(shop: Shop = Depends(get_shop)):
    services = await db.services.find({"shop_id": shop.id, "active": True}, {"_id": 0}).to_list(50)
    return {"services": services}


# ==================== SMS / EMAIL TEST ====================

@router.post("/sms/send-test")
async def send_test_sms(request_body: "SendTestSMSRequest", shop: Shop = Depends(get_shop)):
    from models import SendTestSMSRequest
    from providers import get_sms
    from providers.interfaces import SMSMessage

    twilio_enabled = os.environ.get("TWILIO_ENABLED", "").lower() in ("true", "1", "yes")
    if not twilio_enabled:
        raise HTTPException(status_code=400, detail="SMS sending is disabled. Set TWILIO_ENABLED=true and configure credentials.")

    sms = get_sms()
    response = await sms.send_sms(SMSMessage(to=request_body.to_phone, body=request_body.message))
    if not response.success:
        raise HTTPException(status_code=500, detail=response.error or "Failed to send SMS")
    return {"message": "Test SMS sent", "message_id": response.message_id}


@router.post("/email/send-test")
async def send_test_email(request_body: "SendTestEmailRequest", shop: Shop = Depends(get_shop)):
    from models import SendTestEmailRequest
    from providers import get_email
    from providers.interfaces import EmailMessage

    send_emails = os.environ.get("SEND_EMAILS", "").lower() in ("true", "1", "yes")
    if not send_emails:
        raise HTTPException(status_code=400, detail="Email sending is disabled. Set SEND_EMAILS=true and configure SENDGRID_API_KEY.")

    email_provider = get_email(db)
    response = await email_provider.send_email(EmailMessage(
        to=request_body.to_email,
        subject=request_body.subject,
        html_content=f"""
        <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #D4AF37; padding: 20px; text-align: center;">
                <h1 style="color: #000; margin: 0;">Barbershop Autopilot</h1>
            </div>
            <div style="padding: 30px; background-color: #18181b; color: #fafafa;">
                <h2 style="color: #D4AF37;">Test Email</h2>
                <p>{request_body.message}</p>
                <hr style="border-color: #27272a; margin: 20px 0;">
                <p style="color: #a1a1aa; font-size: 12px;">
                    This email was sent from {shop.name} to verify SendGrid integration.
                </p>
            </div>
        </body></html>""",
        plain_content=request_body.message
    ))
    if not response.success:
        raise HTTPException(status_code=500, detail=response.error or "Failed to send email")
    return {"message": "Test email sent", "message_id": response.message_id}


# ==================== EMAIL OUTBOX ====================

@router.get("/email-outbox")
async def list_email_outbox(shop: Shop = Depends(get_shop)):
    emails = await db.email_outbox.find({"shop_id": shop.id}, {"_id": 0}).sort("created_at", -1).limit(50).to_list(50)
    return {"emails": emails}


# ==================== HEALTH CHECK ====================

@router.get("/")
async def root():
    return {"message": "Barbershop Autopilot API", "version": "1.0.0"}


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "providers": {
            "twilio_enabled": os.environ.get("TWILIO_ENABLED", "false").lower() in ("true", "1", "yes"),
            "stripe_enabled": os.environ.get("STRIPE_ENABLED", "false").lower() in ("true", "1", "yes"),
            "sendgrid_enabled": os.environ.get("SEND_EMAILS", "false").lower() in ("true", "1", "yes"),
            "calendar_enabled": os.environ.get("CALENDAR_ENABLED", "false").lower() in ("true", "1", "yes"),
        },
        "compliance": {
            "sms_consent_enforced": True,
            "stop_handling_enabled": True,
            "audit_logging_enabled": True,
        },
    }
