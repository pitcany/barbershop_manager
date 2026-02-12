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
from zoneinfo import ZoneInfo
import re
import time
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
    SendTestEmailRequest, AdminUser, EmailOutbox, AuditProvider, AuditAction,
    RevenueSource, CreateAppointmentRequest, CreateClientRequest, UpdateClientRequest,
    CreateWaitlistRequest
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
from scheduling import create_scheduling_engine, SchedulingEngine
from scheduler import start_scheduler, stop_scheduler, get_job_status
from owner_ops_agent import OwnerOpsAgent
from retention_rebook_agent import RetentionRebookAgent

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


# ==================== RATE LIMITING ====================

_rate_limit_store: Dict[str, List[float]] = {}
_rate_limit_windows: Dict[str, int] = {}

def check_rate_limit(key: str, max_requests: int, window_seconds: int) -> bool:
    """Returns True if request is allowed, False if rate limited."""
    now = time.time()
    if key not in _rate_limit_store:
        _rate_limit_store[key] = []
        _rate_limit_windows[key] = window_seconds
    elif key not in _rate_limit_windows:
        _rate_limit_windows[key] = window_seconds
    # Remove expired entries
    _rate_limit_store[key] = [t for t in _rate_limit_store[key] if now - t < window_seconds]
    if not _rate_limit_store[key]:
        del _rate_limit_store[key]
        _rate_limit_windows.pop(key, None)
    if key not in _rate_limit_store:
        _rate_limit_store[key] = [now]
        _rate_limit_windows[key] = window_seconds
        return True
    if len(_rate_limit_store[key]) >= max_requests:
        return False
    _rate_limit_store[key].append(now)

    # Periodic cleanup: prune stale keys when store grows large
    if len(_rate_limit_store) > 10000:
        stale_keys = [
            k for k, timestamps in _rate_limit_store.items()
            if all(now - t > _rate_limit_windows.get(k, window_seconds) for t in timestamps)
        ]
        for k in stale_keys:
            del _rate_limit_store[k]
            _rate_limit_windows.pop(k, None)

    return True


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
async def login(request: LoginRequest, raw_request: Request):
    """Admin login"""
    client_ip = raw_request.client.host if raw_request.client else "unknown"
    if not check_rate_limit(f"login:{client_ip}", max_requests=5, window_seconds=900):
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")

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

    # Use shop timezone for "today" boundary
    shop_tz_name = getattr(shop, "timezone", None) or "UTC"
    try:
        shop_tz = ZoneInfo(shop_tz_name)
    except (KeyError, Exception):
        shop_tz = timezone.utc

    local_now = now.astimezone(shop_tz)
    today_start_local = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_start = today_start_local.astimezone(timezone.utc)

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

    # Build lookup from aggregation results
    data_by_date = {
        r["_id"]: {"date": r["_id"], "recovered": r["recovered"], "lost": r["lost"]}
        for r in results
    }

    # Fill gaps: ensure every date in the range has an entry
    filled_data = []
    current_day = start_date.date()
    end_day = now.date()
    while current_day <= end_day:
        date_str = current_day.isoformat()
        if date_str in data_by_date:
            filled_data.append(data_by_date[date_str])
        else:
            filled_data.append({"date": date_str, "recovered": 0, "lost": 0})
        current_day += timedelta(days=1)

    return {"data": filled_data}


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
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
            raise HTTPException(status_code=400, detail="Date must be in YYYY-MM-DD format")
        query["scheduled_at"] = {"$gte": date, "$lt": f"{date}T23:59:59"}
    
    appointments = await db.appointments.find(
        query, {"_id": 0}
    ).sort("scheduled_at", -1).skip(skip).limit(limit).to_list(limit)
    
    # Batch fetch related entities to avoid N+1 queries
    client_ids = list({apt["client_id"] for apt in appointments if apt.get("client_id")})
    service_ids = list({apt["service_id"] for apt in appointments if apt.get("service_id")})
    barber_ids = list({apt["barber_id"] for apt in appointments if apt.get("barber_id")})

    clients_list = await db.clients.find({"id": {"$in": client_ids}}, {"_id": 0, "id": 1, "name": 1, "phone": 1}).to_list(len(client_ids)) if client_ids else []
    services_list = await db.services.find({"id": {"$in": service_ids}}, {"_id": 0, "id": 1, "name": 1}).to_list(len(service_ids)) if service_ids else []
    barbers_list = await db.barbers.find({"id": {"$in": barber_ids}}, {"_id": 0, "id": 1, "name": 1}).to_list(len(barber_ids)) if barber_ids else []

    clients_map = {c["id"]: {"name": c.get("name"), "phone": c.get("phone")} for c in clients_list}
    services_map = {s["id"]: {"name": s.get("name")} for s in services_list}
    barbers_map = {b["id"]: {"name": b.get("name")} for b in barbers_list}

    for apt in appointments:
        apt["client"] = clients_map.get(apt.get("client_id"))
        apt["service"] = services_map.get(apt.get("service_id"))
        apt["barber"] = barbers_map.get(apt.get("barber_id"))
    
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


ALLOWED_TRANSITIONS = {
    "pending": {"confirmed", "cancelled", "deposit_pending"},
    "confirmed": {"completed", "cancelled", "no_show", "rescheduled"},
    "deposit_pending": {"deposit_paid", "cancelled"},
    "deposit_paid": {"confirmed", "completed", "cancelled", "no_show"},
    "rescheduled": {"pending", "confirmed", "cancelled"},
    # Terminal states — no outgoing transitions
    "completed": set(),
    "no_show": set(),
    "cancelled": set(),
}


@api_router.patch("/appointments/{appointment_id}/status")
async def update_appointment_status(
    appointment_id: str,
    status: str,
    shop: Shop = Depends(get_shop)
):
    """Update appointment status with state machine validation."""
    valid_statuses = [s.value for s in AppointmentStatus]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

    # Fetch current appointment to check current status
    appointment = await db.appointments.find_one(
        {"id": appointment_id, "shop_id": shop.id},
        {"_id": 0}
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    current_status = appointment.get("status", "pending")

    # Validate transition
    allowed = ALLOWED_TRANSITIONS.get(current_status, set())
    if status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from '{current_status}' to '{status}'. Allowed: {sorted(allowed) if allowed else 'none (terminal state)'}"
        )

    # For no_show and completed: scheduled_at must be in the past
    if status in ("no_show", "completed"):
        scheduled_at = appointment.get("scheduled_at", "")
        if scheduled_at:
            try:
                scheduled_dt = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
                if scheduled_dt > datetime.now(timezone.utc):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Cannot mark as '{status}' — appointment is still in the future"
                    )
            except (ValueError, TypeError):
                pass  # If date is unparseable, allow the transition

    result = await db.appointments.update_one(
        {"id": appointment_id, "shop_id": shop.id},
        {"$set": {
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Appointment not found or status unchanged")

    # Trigger agents (non-blocking — errors logged, not raised)
    try:
        if status == "cancelled":
            waitlist_agent = WaitlistFillAgent(db, shop)
            await waitlist_agent.process_cancellation(appointment_id)
        elif status == "no_show":
            noshow_agent = NoShowEnforcementAgent(db, shop)
            await noshow_agent.process_no_show(appointment_id)
    except Exception as e:
        logger.error(f"Agent trigger failed for {appointment_id} -> {status}: {e}")

    return {"message": "Status updated"}


# ==================== SCHEDULING / AVAILABILITY ENDPOINTS ====================

@api_router.get("/scheduling/availability")
async def get_availability(
    shop: Shop = Depends(get_shop),
    date: str = None,
    barber_id: Optional[str] = None,
    service_id: Optional[str] = None
):
    """
    Get available time slots for a given date.
    
    Query params:
    - date: ISO date string (YYYY-MM-DD), defaults to today
    - barber_id: Optional specific barber
    - service_id: Optional service (used to determine duration)
    """
    # Parse date
    if date:
        try:
            target_date = datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    else:
        target_date = datetime.now(timezone.utc)
    
    # Get service duration
    duration = 30  # Default
    if service_id:
        service = await db.services.find_one(
            {"id": service_id, "shop_id": shop.id},
            {"_id": 0, "duration_minutes": 1}
        )
        if service:
            duration = service.get("duration_minutes", 30)
    
    scheduler = create_scheduling_engine(db, shop.model_dump())
    slots = await scheduler.get_available_slots(target_date, barber_id, duration)
    
    return {
        "date": target_date.date().isoformat(),
        "duration_minutes": duration,
        "slots": [slot.to_dict() for slot in slots]
    }


@api_router.get("/scheduling/barber/{barber_id}/schedule")
async def get_barber_schedule(
    barber_id: str,
    shop: Shop = Depends(get_shop),
    start_date: str = None,
    end_date: str = None
):
    """
    Get a barber's schedule for a date range.
    
    Defaults to the current day if no dates provided.
    """
    # Parse dates
    now = datetime.now(timezone.utc)
    
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format")
    else:
        start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format")
    else:
        end_dt = start_dt + timedelta(days=1)
    
    # Validate barber exists
    barber = await db.barbers.find_one(
        {"id": barber_id, "shop_id": shop.id},
        {"_id": 0, "id": 1, "name": 1}
    )
    if not barber:
        raise HTTPException(status_code=404, detail="Barber not found")
    
    scheduler = create_scheduling_engine(db, shop.model_dump())
    appointments = await scheduler.get_barber_schedule(barber_id, start_dt, end_dt)
    
    return {
        "barber": barber,
        "start_date": start_dt.isoformat(),
        "end_date": end_dt.isoformat(),
        "appointments": appointments
    }


@api_router.post("/scheduling/validate-slot")
async def validate_slot(
    shop: Shop = Depends(get_shop),
    barber_id: str = None,
    scheduled_at: str = None,
    duration_minutes: int = 30,
    exclude_appointment_id: Optional[str] = None
):
    """
    Validate if a specific time slot is available.
    
    Returns whether the slot can be booked and any conflict details.
    """
    if not barber_id or not scheduled_at:
        raise HTTPException(status_code=400, detail="barber_id and scheduled_at are required")
    
    try:
        scheduled_dt = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
        if scheduled_dt.tzinfo is None:
            scheduled_dt = scheduled_dt.replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid scheduled_at format")
    
    scheduler = create_scheduling_engine(db, shop.model_dump())
    is_valid, error_msg = await scheduler.validate_appointment_slot(
        barber_id=barber_id,
        scheduled_at=scheduled_dt,
        duration_minutes=duration_minutes,
        exclude_appointment_id=exclude_appointment_id
    )
    
    return {
        "valid": is_valid,
        "error": error_msg,
        "barber_id": barber_id,
        "scheduled_at": scheduled_dt.isoformat(),
        "duration_minutes": duration_minutes
    }


@api_router.post("/appointments")
async def create_appointment(
    body: CreateAppointmentRequest,
    shop: Shop = Depends(get_shop)
):
    """Create a new appointment with conflict prevention."""
    # Validate client exists
    client = await db.clients.find_one(
        {"id": body.client_id, "shop_id": shop.id}, {"_id": 0, "id": 1, "no_shows": 1}
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Validate barber exists
    barber = await db.barbers.find_one(
        {"id": body.barber_id, "shop_id": shop.id}, {"_id": 0, "id": 1}
    )
    if not barber:
        raise HTTPException(status_code=404, detail="Barber not found")

    # Validate service exists
    service = await db.services.find_one(
        {"id": body.service_id, "shop_id": shop.id}, {"_id": 0, "id": 1, "duration_minutes": 1, "price": 1}
    )
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    # Parse scheduled_at
    try:
        scheduled_dt = datetime.fromisoformat(body.scheduled_at.replace("Z", "+00:00"))
        if scheduled_dt.tzinfo is None:
            scheduled_dt = scheduled_dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid scheduled_at format — use ISO 8601")

    duration = body.duration_minutes or service.get("duration_minutes", 30)
    
    # === CONFLICT PREVENTION ===
    scheduler = create_scheduling_engine(db, shop.model_dump())
    is_valid, error_msg = await scheduler.validate_appointment_slot(
        barber_id=body.barber_id,
        scheduled_at=scheduled_dt,
        duration_minutes=duration
    )
    
    if not is_valid:
        raise HTTPException(status_code=409, detail=error_msg)
    
    now_iso = datetime.now(timezone.utc).isoformat()

    # Check deposit requirement
    initial_status = "pending"
    try:
        noshow_agent = NoShowEnforcementAgent(db, shop)
        deposit_required = await noshow_agent.check_deposit_requirement(
            {"scheduled_at": scheduled_dt.isoformat()},
            client
        )
        if deposit_required:
            initial_status = "deposit_pending"
    except Exception as e:
        logger.error(f"Deposit check failed: {e}")

    appointment_id = str(uuid.uuid4())
    appointment = {
        "id": appointment_id,
        "shop_id": shop.id,
        "client_id": body.client_id,
        "barber_id": body.barber_id,
        "service_id": body.service_id,
        "scheduled_at": scheduled_dt.isoformat(),
        "duration_minutes": duration,
        "status": initial_status,
        "notes": body.notes or "",
        "price": service.get("price", 0),
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    await db.appointments.insert_one(appointment)
    appointment.pop("_id", None)

    return appointment


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
        escaped_search = re.escape(search)
        query["$or"] = [
            {"name": {"$regex": escaped_search, "$options": "i"}},
            {"phone": {"$regex": escaped_search}}
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


@api_router.post("/clients")
async def create_client(
    body: CreateClientRequest,
    shop: Shop = Depends(get_shop)
):
    """Create a new client."""
    # Check for duplicate phone
    existing = await db.clients.find_one(
        {"phone": body.phone, "shop_id": shop.id}, {"_id": 0, "id": 1}
    )
    if existing:
        raise HTTPException(status_code=409, detail="A client with this phone number already exists")

    now_iso = datetime.now(timezone.utc).isoformat()
    client_id = str(uuid.uuid4())
    client = {
        "id": client_id,
        "shop_id": shop.id,
        "name": body.name,
        "phone": body.phone,
        "email": body.email or "",
        "sms_consent": body.sms_consent,
        "sms_consent_timestamp": now_iso if body.sms_consent else None,
        "sms_consent_source": "admin_created" if body.sms_consent else None,
        "no_shows": 0,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    await db.clients.insert_one(client)
    client.pop("_id", None)

    return client


@api_router.patch("/clients/{client_id}")
async def update_client(
    client_id: str,
    body: UpdateClientRequest,
    shop: Shop = Depends(get_shop)
):
    """Update an existing client."""
    existing = await db.clients.find_one(
        {"id": client_id, "shop_id": shop.id}, {"_id": 0}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Client not found")

    updates = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.phone is not None and body.phone != existing.get("phone"):
        # Check for duplicate phone
        dup = await db.clients.find_one(
            {"phone": body.phone, "shop_id": shop.id, "id": {"$ne": client_id}},
            {"_id": 0, "id": 1}
        )
        if dup:
            raise HTTPException(status_code=409, detail="A client with this phone number already exists")
        updates["phone"] = body.phone
    if body.email is not None:
        updates["email"] = body.email

    if not updates:
        return existing

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.clients.update_one(
        {"id": client_id, "shop_id": shop.id},
        {"$set": updates}
    )

    updated = await db.clients.find_one(
        {"id": client_id, "shop_id": shop.id}, {"_id": 0}
    )
    return updated


@api_router.get("/clients/{client_id}/history")
async def get_client_history(
    client_id: str,
    shop: Shop = Depends(get_shop)
):
    """
    Get comprehensive client history including appointments, messages, and stats.
    """
    # Get client
    client = await db.clients.find_one(
        {"id": client_id, "shop_id": shop.id},
        {"_id": 0}
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Get appointments (last 20)
    appointments = await db.appointments.find(
        {"client_id": client_id, "shop_id": shop.id},
        {"_id": 0}
    ).sort("scheduled_at", -1).limit(20).to_list(20)
    
    # Enrich appointments with service/barber info
    for apt in appointments:
        service = await db.services.find_one({"id": apt.get("service_id")}, {"_id": 0, "name": 1, "price": 1})
        barber = await db.barbers.find_one({"id": apt.get("barber_id")}, {"_id": 0, "name": 1})
        apt["service"] = service
        apt["barber"] = barber
    
    # Get messages (last 50)
    messages = await db.messages.find(
        {"client_id": client_id, "shop_id": shop.id},
        {"_id": 0}
    ).sort("created_at", -1).limit(50).to_list(50)
    
    # Calculate stats
    total_appointments = await db.appointments.count_documents({
        "client_id": client_id, "shop_id": shop.id
    })
    completed_appointments = await db.appointments.count_documents({
        "client_id": client_id, "shop_id": shop.id, "status": "completed"
    })
    no_shows = await db.appointments.count_documents({
        "client_id": client_id, "shop_id": shop.id, "status": "no_show"
    })
    cancelled = await db.appointments.count_documents({
        "client_id": client_id, "shop_id": shop.id, "status": "cancelled"
    })
    
    # Total spent (from completed appointments)
    spent_pipeline = [
        {"$match": {"client_id": client_id, "shop_id": shop.id, "status": "completed"}},
        {"$group": {"_id": None, "total": {"$sum": "$price"}}}
    ]
    spent_result = await db.appointments.aggregate(spent_pipeline).to_list(1)
    total_spent = spent_result[0]["total"] if spent_result else 0
    
    # Check if on waitlist
    waitlist_entry = await db.waitlist.find_one(
        {"client_id": client_id, "shop_id": shop.id, "active": True},
        {"_id": 0}
    )
    
    return {
        "client": client,
        "appointments": appointments,
        "messages": messages,
        "stats": {
            "total_appointments": total_appointments,
            "completed_appointments": completed_appointments,
            "no_shows": no_shows,
            "cancelled": cancelled,
            "no_show_rate": round((no_shows / total_appointments * 100) if total_appointments > 0 else 0, 1),
            "total_spent": total_spent
        },
        "waitlist_entry": waitlist_entry
    }


@api_router.post("/clients/{client_id}/waitlist")
async def add_client_to_waitlist(
    client_id: str,
    service_id: str,
    preferred_date: str,
    barber_id: Optional[str] = None,
    flexible_hours: int = 2,
    shop: Shop = Depends(get_shop)
):
    """Add a client to the waitlist."""
    # Validate client
    client = await db.clients.find_one(
        {"id": client_id, "shop_id": shop.id},
        {"_id": 0, "id": 1}
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Validate service
    service = await db.services.find_one(
        {"id": service_id, "shop_id": shop.id},
        {"_id": 0, "id": 1}
    )
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    # Check if already on waitlist for similar date
    existing = await db.waitlist.find_one({
        "client_id": client_id,
        "shop_id": shop.id,
        "active": True
    })
    if existing:
        raise HTTPException(status_code=409, detail="Client is already on the waitlist")
    
    # Parse date
    try:
        pref_date = datetime.fromisoformat(preferred_date.replace("Z", "+00:00"))
        if pref_date.tzinfo is None:
            pref_date = pref_date.replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid preferred_date format")
    
    now_iso = datetime.now(timezone.utc).isoformat()
    entry_id = str(uuid.uuid4())
    
    entry = {
        "id": entry_id,
        "shop_id": shop.id,
        "client_id": client_id,
        "service_id": service_id,
        "barber_id": barber_id,
        "preferred_date": pref_date.isoformat(),
        "flexible_hours": flexible_hours,
        "active": True,
        "contact_attempts": 0,
        "created_at": now_iso
    }
    
    await db.waitlist.insert_one(entry)
    entry.pop("_id", None)
    
    return entry


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
    
    # Batch fetch client info to avoid N+1 queries
    thread_client_ids = [thread["_id"] for thread in threads]
    clients_list = await db.clients.find({"id": {"$in": thread_client_ids}}, {"_id": 0, "id": 1, "name": 1, "phone": 1}).to_list(len(thread_client_ids)) if thread_client_ids else []
    clients_map = {c["id"]: {"name": c.get("name"), "phone": c.get("phone")} for c in clients_list}

    for thread in threads:
        thread["client"] = clients_map.get(thread["_id"])
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


@api_router.get("/conversations/poll/new")
async def poll_new_messages(
    shop: Shop = Depends(get_shop),
    since: str = None,
    client_id: Optional[str] = None
):
    """
    Poll for new messages since a given timestamp.
    
    Used for real-time updates without WebSockets.
    
    Args:
        since: ISO timestamp - return messages after this time
        client_id: Optional - filter to specific conversation
    
    Returns new messages and the latest timestamp for next poll.
    """
    query = {"shop_id": shop.id}
    
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            query["created_at"] = {"$gt": since_dt.isoformat()}
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid 'since' timestamp format")
    
    if client_id:
        query["client_id"] = client_id
    
    messages = await db.messages.find(
        query, {"_id": 0}
    ).sort("created_at", 1).limit(100).to_list(100)
    
    # Get the latest timestamp for next poll
    latest_timestamp = None
    if messages:
        latest_timestamp = messages[-1].get("created_at")
    
    # Enrich with client info if not filtering by client
    if not client_id and messages:
        client_ids = list({m.get("client_id") for m in messages if m.get("client_id")})
        clients_list = await db.clients.find(
            {"id": {"$in": client_ids}},
            {"_id": 0, "id": 1, "name": 1, "phone": 1}
        ).to_list(len(client_ids)) if client_ids else []
        clients_map = {c["id"]: c for c in clients_list}
        
        for msg in messages:
            msg["client"] = clients_map.get(msg.get("client_id"))
    
    return {
        "messages": messages,
        "count": len(messages),
        "latest_timestamp": latest_timestamp,
        "poll_interval_ms": 3000  # Suggested poll interval
    }


@api_router.get("/conversations/activity/live")
async def get_live_activity(
    shop: Shop = Depends(get_shop),
    minutes: int = 30
):
    """
    Get recent conversation activity for the live dashboard view.
    
    Shows the most recent messages across all conversations,
    useful for seeing the "autopilot in action".
    """
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    
    messages = await db.messages.find({
        "shop_id": shop.id,
        "created_at": {"$gte": since.isoformat()}
    }, {"_id": 0}).sort("created_at", -1).limit(50).to_list(50)
    
    # Enrich with client info
    client_ids = list({m.get("client_id") for m in messages if m.get("client_id")})
    clients_list = await db.clients.find(
        {"id": {"$in": client_ids}},
        {"_id": 0, "id": 1, "name": 1, "phone": 1}
    ).to_list(len(client_ids)) if client_ids else []
    clients_map = {c["id"]: c for c in clients_list}
    
    for msg in messages:
        msg["client"] = clients_map.get(msg.get("client_id"))
    
    # Reverse to show chronological order
    messages.reverse()
    
    return {
        "messages": messages,
        "since": since.isoformat(),
        "count": len(messages)
    }


# ==================== WAITLIST ENDPOINTS ====================

@api_router.get("/waitlist")
async def list_waitlist(shop: Shop = Depends(get_shop)):
    """List active waitlist entries"""
    entries = await db.waitlist.find(
        {"shop_id": shop.id, "active": True},
        {"_id": 0}
    ).sort("created_at", 1).to_list(100)
    
    # Batch fetch related entities to avoid N+1 queries
    client_ids = list({e["client_id"] for e in entries if e.get("client_id")})
    service_ids = list({e["service_id"] for e in entries if e.get("service_id")})

    clients_list = await db.clients.find({"id": {"$in": client_ids}}, {"_id": 0, "id": 1, "name": 1, "phone": 1}).to_list(len(client_ids)) if client_ids else []
    services_list = await db.services.find({"id": {"$in": service_ids}}, {"_id": 0, "id": 1, "name": 1}).to_list(len(service_ids)) if service_ids else []

    clients_map = {c["id"]: {"name": c.get("name"), "phone": c.get("phone")} for c in clients_list}
    services_map = {s["id"]: {"name": s.get("name")} for s in services_list}

    for entry in entries:
        entry["client"] = clients_map.get(entry.get("client_id"))
        entry["service"] = services_map.get(entry.get("service_id"))
    
    return {"waitlist": entries}


@api_router.post("/waitlist")
async def create_waitlist_entry(
    body: CreateWaitlistRequest,
    shop: Shop = Depends(get_shop)
):
    """Add a client to the waitlist."""
    # Validate client
    client = await db.clients.find_one(
        {"id": body.client_id, "shop_id": shop.id}, {"_id": 0, "id": 1}
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Validate service
    service = await db.services.find_one(
        {"id": body.service_id, "shop_id": shop.id}, {"_id": 0, "id": 1}
    )
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    # Validate barber if provided
    if body.barber_id:
        barber = await db.barbers.find_one(
            {"id": body.barber_id, "shop_id": shop.id}, {"_id": 0, "id": 1}
        )
        if not barber:
            raise HTTPException(status_code=404, detail="Barber not found")

    # Parse preferred_date
    try:
        preferred_dt = datetime.fromisoformat(body.preferred_date.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid preferred_date format — use ISO 8601")

    now_iso = datetime.now(timezone.utc).isoformat()
    entry_id = str(uuid.uuid4())
    entry = {
        "id": entry_id,
        "shop_id": shop.id,
        "client_id": body.client_id,
        "service_id": body.service_id,
        "barber_id": body.barber_id,
        "preferred_date": preferred_dt.isoformat(),
        "flexible_hours": body.flexible_hours,
        "active": True,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    await db.waitlist.insert_one(entry)
    entry.pop("_id", None)

    return entry


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

    # Validate Twilio webhook signature when Twilio is enabled
    if is_twilio_enabled():
        signature = request.headers.get("X-Twilio-Signature", "")
        # Use configured base URL if behind a reverse proxy, otherwise use request URL
        base_url = os.environ.get("TWILIO_WEBHOOK_BASE_URL")
        if base_url:
            webhook_url = base_url.rstrip("/") + request.url.path
        else:
            webhook_url = str(request.url)
        form_params = {k: v for k, v in form_data.items()}
        sms_provider = get_sms()
        if not await sms_provider.validate_webhook(webhook_url, form_params, signature):
            logger.warning("Twilio webhook signature validation failed")
            raise HTTPException(status_code=403, detail="Invalid webhook signature")

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
            "sms_consent_source": "implied_inbound",
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
    
    session_id = result.get("session_id")
    payment_status = result.get("payment_status")
    
    if session_id and payment_status:
        now_iso = datetime.now(timezone.utc).isoformat()
        
        if payment_status == "paid":
            # Update payment_transactions (idempotent - only if not already paid)
            txn_result = await db.payment_transactions.update_one(
                {"session_id": session_id, "payment_status": {"$ne": "paid"}},
                {"$set": {"payment_status": "paid", "status": "completed", "updated_at": now_iso}}
            )
            
            if txn_result.modified_count > 0:
                # Update legacy payments
                await db.payments.update_one(
                    {"stripe_session_id": session_id},
                    {"$set": {"status": "completed", "updated_at": now_iso}}
                )
                
                # Find transaction to get appointment_id
                txn = await db.payment_transactions.find_one(
                    {"session_id": session_id}, {"_id": 0}
                )
                if txn and txn.get("appointment_id"):
                    await db.appointments.update_one(
                        {"id": txn["appointment_id"]},
                        {"$set": {
                            "deposit_paid": True,
                            "status": AppointmentStatus.DEPOSIT_PAID.value,
                            "updated_at": now_iso
                        }}
                    )
                    
                    payment_record = await db.payments.find_one(
                        {"stripe_session_id": session_id}, {"_id": 0}
                    )
                    appointment = await db.appointments.find_one(
                        {"id": txn["appointment_id"]}, {"_id": 0}
                    )
                    if payment_record and appointment:
                        await log_no_show_fee_on_payment_success(db, payment_record, appointment)
        
        elif payment_status in ("unpaid", "no_payment_required"):
            await db.payment_transactions.update_one(
                {"session_id": session_id},
                {"$set": {"payment_status": payment_status, "status": "failed", "updated_at": now_iso}}
            )
            await db.payments.update_one(
                {"stripe_session_id": session_id},
                {"$set": {"status": "failed", "updated_at": now_iso}}
            )
    
    return JSONResponse(content={"status": "received"})


# ==================== GOOGLE CALENDAR OAUTH ENDPOINTS ====================

@api_router.get("/oauth/calendar/login")
async def google_calendar_login(request: Request, shop: Shop = Depends(get_shop)):
    """Initiate Google Calendar OAuth flow"""
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    if not client_id:
        raise HTTPException(status_code=500, detail="Google Calendar not configured")
    
    origin = request.headers.get("x-origin", str(request.base_url).rstrip("/"))
    redirect_uri = f"{origin}/api/oauth/calendar/callback"
    
    from google_auth_oauthlib.flow import Flow
    flow = Flow.from_client_config(
        {"web": {
            "client_id": client_id,
            "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"
        }},
        scopes=["https://www.googleapis.com/auth/calendar"],
        redirect_uri=redirect_uri
    )
    
    auth_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent"
    )
    
    # Store state for CSRF protection
    await db.oauth_states.insert_one({
        "state": state,
        "redirect_uri": redirect_uri,
        "shop_id": shop.id,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    return {"authorization_url": auth_url}


@api_router.get("/oauth/calendar/callback")
async def google_calendar_callback(code: str, state: str = ""):
    """Handle Google Calendar OAuth callback"""
    import requests as http_requests
    
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    
    # Find stored state to get redirect_uri
    state_doc = await db.oauth_states.find_one({"state": state}, {"_id": 0})
    redirect_uri = state_doc["redirect_uri"] if state_doc else ""
    
    if not redirect_uri:
        # Fallback - construct from the REACT_APP_BACKEND_URL concept
        redirect_uri = f"{os.environ.get('REACT_APP_BACKEND_URL', '')}/api/oauth/calendar/callback"
    
    # Exchange code for tokens
    token_resp = http_requests.post("https://oauth2.googleapis.com/token", data={
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }).json()
    
    if "error" in token_resp:
        logger.error(f"Google OAuth error: {token_resp}")
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/settings?calendar_error=auth_failed")
    
    # Get user email
    user_info = http_requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {token_resp['access_token']}"}
    ).json()
    
    email = user_info.get("email", "")
    
    # Store tokens
    await db.google_calendar_tokens.update_one(
        {},
        {"$set": {
            "access_token": token_resp["access_token"],
            "refresh_token": token_resp.get("refresh_token"),
            "token_type": token_resp.get("token_type"),
            "expires_in": token_resp.get("expires_in"),
            "email": email,
            "connected_at": datetime.now(timezone.utc).isoformat()
        }},
        upsert=True
    )
    
    # Reset calendar provider singleton so it picks up the new tokens
    from providers import reset_providers
    reset_providers()
    
    # Clean up state
    if state_doc:
        await db.oauth_states.delete_one({"state": state})
    
    logger.info(f"[GCAL] Google Calendar connected for {email}")
    
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/settings?calendar_connected=true")


@api_router.get("/calendar/status")
async def get_calendar_status(shop: Shop = Depends(get_shop)):
    """Check if Google Calendar is connected"""
    tokens = await db.google_calendar_tokens.find_one({}, {"_id": 0})
    
    connected = bool(tokens and tokens.get("access_token"))
    
    return {
        "connected": connected,
        "email": tokens.get("email", "") if connected else "",
        "connected_at": tokens.get("connected_at", "") if connected else ""
    }


@api_router.post("/calendar/disconnect")
async def disconnect_calendar(shop: Shop = Depends(get_shop)):
    """Disconnect Google Calendar"""
    await db.google_calendar_tokens.delete_many({})
    
    from providers import reset_providers
    reset_providers()
    
    return {"message": "Google Calendar disconnected"}


@api_router.get("/calendar/events")
async def list_calendar_events(shop: Shop = Depends(get_shop)):
    """List upcoming calendar events"""
    calendar = get_calendar(db)
    
    from providers.real_providers import GoogleCalendarProvider
    if not isinstance(calendar, GoogleCalendarProvider):
        return {"events": [], "source": "mock"}
    
    service = await calendar._get_service()
    if not service:
        return {"events": [], "source": "not_connected"}
    
    try:
        now = datetime.now(timezone.utc).isoformat()
        result = service.events().list(
            calendarId="primary",
            timeMin=now,
            maxResults=20,
            singleEvents=True,
            orderBy="startTime"
        ).execute()
        
        events = []
        for e in result.get("items", []):
            events.append({
                "id": e["id"],
                "summary": e.get("summary", ""),
                "start": e.get("start", {}).get("dateTime", e.get("start", {}).get("date", "")),
                "end": e.get("end", {}).get("dateTime", e.get("end", {}).get("date", "")),
                "status": e.get("status", ""),
            })
        
        return {"events": events, "source": "google"}
    except Exception as e:
        logger.error(f"Failed to list calendar events: {e}")
        return {"events": [], "source": "error", "error": str(e)}

@api_router.post("/public/sms-consent")
async def submit_sms_consent(request: SMSConsentRequest, raw_request: Request):
    """Public endpoint for SMS consent form (compliance-compliant)"""
    client_ip = raw_request.client.host if raw_request.client else "unknown"
    if not check_rate_limit(f"sms-consent:{client_ip}", max_requests=10, window_seconds=3600):
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")

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


# ==================== PAYMENT ENDPOINTS ====================

@api_router.post("/payments/create-deposit/{appointment_id}")
async def create_deposit_payment(
    appointment_id: str,
    request: Request,
    shop: Shop = Depends(get_shop)
):
    """Create a Stripe checkout session for an appointment deposit"""
    appointment = await db.appointments.find_one(
        {"id": appointment_id, "shop_id": shop.id},
        {"_id": 0}
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    if appointment.get("status") not in ("deposit_pending", "pending"):
        raise HTTPException(status_code=400, detail=f"Appointment status '{appointment.get('status')}' does not require a deposit")
    
    # Check if there's already a completed payment
    existing = await db.payment_transactions.find_one(
        {"appointment_id": appointment_id, "payment_status": "paid"},
        {"_id": 0}
    )
    if existing:
        raise HTTPException(status_code=400, detail="Deposit already paid for this appointment")
    
    # Amount comes from server-side (shop settings), NOT frontend
    amount = float(shop.deposit_amount)
    
    client_data = await db.clients.find_one(
        {"id": appointment["client_id"], "shop_id": shop.id},
        {"_id": 0}
    )
    
    # Build dynamic URLs from the request's origin
    origin = request.headers.get("x-origin", str(request.base_url).rstrip("/"))
    success_url = f"{origin}/payment/success?session_id={{CHECKOUT_SESSION_ID}}&appointment_id={appointment_id}"
    cancel_url = f"{origin}/payment/cancel?appointment_id={appointment_id}"
    
    metadata = {
        "appointment_id": appointment_id,
        "client_id": appointment["client_id"],
        "shop_id": shop.id,
        "type": "deposit"
    }
    
    payment = get_payment()
    payment_link = await payment.create_payment_link(
        amount=amount,
        currency="usd",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata
    )
    
    # Update appointment status
    await db.appointments.update_one(
        {"id": appointment_id},
        {"$set": {
            "deposit_required": True,
            "deposit_amount": amount,
            "status": AppointmentStatus.DEPOSIT_PENDING.value,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # Create payment_transactions record (MANDATORY per playbook)
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.payment_transactions.insert_one({
        "id": str(uuid.uuid4()),
        "shop_id": shop.id,
        "client_id": appointment["client_id"],
        "client_name": client_data.get("name", "") if client_data else "",
        "appointment_id": appointment_id,
        "amount": amount,
        "currency": "usd",
        "session_id": payment_link.session_id,
        "payment_status": "initiated",
        "status": "pending",
        "payment_type": "deposit",
        "metadata": metadata,
        "created_at": now_iso,
        "updated_at": now_iso
    })
    
    # Also create legacy payments record for backwards compat
    await db.payments.insert_one({
        "id": str(uuid.uuid4()),
        "shop_id": shop.id,
        "client_id": appointment["client_id"],
        "appointment_id": appointment_id,
        "amount": amount,
        "currency": "usd",
        "stripe_session_id": payment_link.session_id,
        "status": "pending",
        "payment_type": "deposit",
        "created_at": now_iso,
        "updated_at": now_iso
    })
    
    return {"checkout_url": payment_link.url, "session_id": payment_link.session_id}


@api_router.get("/payments/status/{session_id}")
async def get_payment_status(session_id: str, shop: Shop = Depends(get_shop)):
    """Poll Stripe for checkout session status and update DB"""
    # Check our records first
    txn = await db.payment_transactions.find_one(
        {"session_id": session_id, "shop_id": shop.id},
        {"_id": 0}
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Payment transaction not found")
    
    # If already marked as paid, return immediately (idempotent)
    if txn.get("payment_status") == "paid":
        return {
            "status": txn["status"],
            "payment_status": "paid",
            "amount": txn["amount"],
            "appointment_id": txn.get("appointment_id")
        }
    
    # Poll Stripe for latest status
    payment = get_payment()
    stripe_status = await payment.get_payment_status(session_id)
    
    now_iso = datetime.now(timezone.utc).isoformat()
    
    if stripe_status.payment_status == "paid":
        # Update payment_transactions (only if not already processed)
        result = await db.payment_transactions.update_one(
            {"session_id": session_id, "payment_status": {"$ne": "paid"}},
            {"$set": {
                "payment_status": "paid",
                "status": "completed",
                "updated_at": now_iso
            }}
        )
        
        if result.modified_count > 0:
            # Update legacy payments record
            await db.payments.update_one(
                {"stripe_session_id": session_id},
                {"$set": {"status": "completed", "updated_at": now_iso}}
            )
            
            # Update appointment status
            appointment_id = txn.get("appointment_id")
            if appointment_id:
                await db.appointments.update_one(
                    {"id": appointment_id},
                    {"$set": {
                        "deposit_paid": True,
                        "status": AppointmentStatus.DEPOSIT_PAID.value,
                        "updated_at": now_iso
                    }}
                )
                
                # Log revenue
                payment_record = await db.payments.find_one(
                    {"stripe_session_id": session_id}, {"_id": 0}
                )
                appointment = await db.appointments.find_one(
                    {"id": appointment_id}, {"_id": 0}
                )
                if payment_record and appointment:
                    await log_no_show_fee_on_payment_success(db, payment_record, appointment)
    
    elif stripe_status.status == "expired":
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {"payment_status": "expired", "status": "expired", "updated_at": now_iso}}
        )
        await db.payments.update_one(
            {"stripe_session_id": session_id},
            {"$set": {"status": "failed", "updated_at": now_iso}}
        )
    
    return {
        "status": stripe_status.status,
        "payment_status": stripe_status.payment_status,
        "amount": stripe_status.amount,
        "appointment_id": txn.get("appointment_id")
    }


@api_router.get("/payments/transactions")
async def list_payment_transactions(
    shop: Shop = Depends(get_shop),
    limit: int = 50,
    skip: int = 0
):
    """List payment transactions"""
    txns = await db.payment_transactions.find(
        {"shop_id": shop.id}, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    total = await db.payment_transactions.count_documents({"shop_id": shop.id})
    return {"transactions": txns, "total": total}


@api_router.get("/mock-payment")
async def mock_payment_page(session_id: str):
    """Mock payment endpoint for local testing"""
    from providers.mock_providers import MockPaymentProvider
    
    payment = get_payment()
    if isinstance(payment, MockPaymentProvider):
        await payment.complete_payment(session_id)
        status = await payment.get_payment_status(session_id)
        
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
            await db.payments.update_one(
                {"stripe_session_id": session_id},
                {"$set": {"status": "completed", "updated_at": datetime.now(timezone.utc).isoformat()}}
            )
        
        return {"status": "success", "message": "Mock payment completed", "session_id": session_id, "amount": status.amount}
    
    raise HTTPException(status_code=400, detail="Not in mock mode")


# ==================== SCHEDULED JOBS ENDPOINTS ====================

@api_router.post("/jobs/reminders/run")
async def run_reminder_job(shop: Shop = Depends(get_shop)):
    """
    Manually trigger the appointment reminder job.
    Useful for testing or immediate execution.
    """
    from scheduled_jobs import AppointmentReminderJob
    
    job = AppointmentReminderJob(db, shop)
    results = await job.run()
    
    return {
        "status": "completed",
        "results": results
    }


@api_router.get("/jobs/reminders/preview")
async def preview_reminders(shop: Shop = Depends(get_shop)):
    """
    Preview which appointments would receive reminders.
    Does not actually send any messages.
    """
    from scheduled_jobs import AppointmentReminderJob
    
    job = AppointmentReminderJob(db, shop)
    appointments = await job.get_appointments_needing_reminder()
    
    # Enrich with client info
    preview = []
    for apt in appointments:
        client = await db.clients.find_one(
            {"id": apt["client_id"]},
            {"_id": 0, "name": 1, "phone": 1, "sms_consent": 1}
        )
        preview.append({
            "appointment_id": apt["id"],
            "scheduled_at": apt["scheduled_at"],
            "client_name": client.get("name") if client else "Unknown",
            "client_phone": client.get("phone") if client else "Unknown",
            "has_consent": client.get("sms_consent", False) if client else False
        })
    
    return {
        "reminder_window_hours": shop.confirmation_window_hours,
        "appointments_needing_reminder": len(preview),
        "preview": preview
    }


@api_router.post("/jobs/daily-summary/run")
async def run_daily_summary(shop: Shop = Depends(get_shop)):
    """
    Manually trigger the daily summary email.
    Useful for testing. Sends to the shop owner's configured email.
    """
    agent = OwnerOpsAgent(db, shop.model_dump())
    result = await agent.send_daily_summary()
    return result


@api_router.get("/jobs/daily-summary/preview")
async def preview_daily_summary(shop: Shop = Depends(get_shop)):
    """
    Preview the daily summary stats without sending the email.
    """
    agent = OwnerOpsAgent(db, shop.model_dump())
    stats = await agent.compile_daily_stats()
    return {"stats": stats, "shop_email": shop.email}


@api_router.get("/jobs/status")
async def scheduler_status(user: dict = Depends(get_current_user)):
    """Get status of all scheduled background jobs."""
    jobs = get_job_status()
    return {"scheduler": "running", "jobs": jobs}


@api_router.post("/jobs/retention/run")
async def run_retention_sweep(shop: Shop = Depends(get_shop)):
    """Manually trigger the retention rebook sweep."""
    agent = RetentionRebookAgent(db, shop.model_dump())
    result = await agent.run()
    return result


@api_router.get("/jobs/retention/preview")
async def preview_retention(shop: Shop = Depends(get_shop)):
    """Preview which clients are lapsed without sending any messages."""
    agent = RetentionRebookAgent(db, shop.model_dump())
    lapsed = await agent.find_lapsed_clients()
    return {
        "enabled": agent.enabled,
        "lapse_threshold_weeks": agent.lapse_weeks,
        "cooldown_days": agent.cooldown_days,
        "lapsed_clients": len(lapsed),
        "clients": lapsed,
    }


@api_router.get("/retention/outreach-history")
async def retention_outreach_history(
    limit: int = 50,
    shop: Shop = Depends(get_shop)
):
    """Get history of retention outreach attempts."""
    entries = await db.retention_outreach.find(
        {"shop_id": shop.id}, {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    return {"entries": entries, "count": len(entries)}


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


# ==================== REPORTING ANALYTICS ====================

@api_router.get("/reporting/overview")
async def reporting_overview(
    days: int = 30,
    shop: Shop = Depends(get_shop)
):
    """
    Comprehensive reporting dashboard data.
    Aggregates appointments, revenue, no-shows, and activity over a period.
    """
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=days)).isoformat()

    # Appointment stats by status
    apt_pipeline = [
        {"$match": {"shop_id": shop.id, "scheduled_at": {"$gte": start}}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}, "revenue": {"$sum": "$price"}}}
    ]
    apt_stats = await db.appointments.aggregate(apt_pipeline).to_list(20)
    by_status = {r["_id"]: {"count": r["count"], "revenue": r["revenue"]} for r in apt_stats}
    total_apts = sum(r["count"] for r in apt_stats)

    # Revenue recovered by source
    rev_pipeline = [
        {"$match": {"shop_id": shop.id, "attributed_at": {"$gte": start}}},
        {"$group": {"_id": "$source", "total": {"$sum": "$amount"}, "count": {"$sum": 1}}}
    ]
    rev_stats = await db.recovered_revenue_events.aggregate(rev_pipeline).to_list(20)
    recovered_by_source = {r["_id"]: {"amount": r["total"], "count": r["count"]} for r in rev_stats}
    total_recovered = sum(r["total"] for r in rev_stats)

    # Daily appointment trend
    daily_pipeline = [
        {"$match": {"shop_id": shop.id, "scheduled_at": {"$gte": start}}},
        {"$addFields": {"day": {"$substr": ["$scheduled_at", 0, 10]}}},
        {"$group": {"_id": "$day", "total": {"$sum": 1},
                     "completed": {"$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}},
                     "no_shows": {"$sum": {"$cond": [{"$eq": ["$status", "no_show"]}, 1, 0]}},
                     "cancelled": {"$sum": {"$cond": [{"$eq": ["$status", "cancelled"]}, 1, 0]}},
                     "revenue": {"$sum": "$price"}}},
        {"$sort": {"_id": 1}}
    ]
    daily_trend = await db.appointments.aggregate(daily_pipeline).to_list(60)

    # Recovered revenue events list
    recovered_events = await db.recovered_revenue_events.find(
        {"shop_id": shop.id, "attributed_at": {"$gte": start}}, {"_id": 0}
    ).sort("attributed_at", -1).to_list(100)

    # Barber performance
    barber_pipeline = [
        {"$match": {"shop_id": shop.id, "scheduled_at": {"$gte": start}}},
        {"$group": {"_id": "$barber_id", "total": {"$sum": 1},
                     "completed": {"$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}},
                     "no_shows": {"$sum": {"$cond": [{"$eq": ["$status", "no_show"]}, 1, 0]}},
                     "revenue": {"$sum": "$price"}}}
    ]
    barber_stats = await db.appointments.aggregate(barber_pipeline).to_list(20)
    # Enrich with barber names
    for bs in barber_stats:
        barber = await db.barbers.find_one({"id": bs["_id"]}, {"_id": 0, "name": 1})
        bs["name"] = barber["name"] if barber else bs["_id"]
        del bs["_id"]

    # Message activity
    msg_pipeline = [
        {"$match": {"shop_id": shop.id, "created_at": {"$gte": start}}},
        {"$group": {"_id": "$direction", "count": {"$sum": 1}}}
    ]
    msg_stats = await db.messages.aggregate(msg_pipeline).to_list(5)
    messages = {r["_id"]: r["count"] for r in msg_stats}

    # Audit log stats
    audit_pipeline = [
        {"$match": {"shop_id": shop.id, "created_at": {"$gte": start}}},
        {"$group": {"_id": {"provider": "$provider", "success": "$success"}, "count": {"$sum": 1}}}
    ]
    audit_stats = await db.integration_audit_log.aggregate(audit_pipeline).to_list(50)

    no_shows = by_status.get("no_show", {}).get("count", 0)

    return {
        "period_days": days,
        "appointments": {
            "total": total_apts,
            "by_status": by_status,
            "no_show_rate": round((no_shows / total_apts * 100) if total_apts > 0 else 0, 1),
        },
        "revenue": {
            "total_earned": sum(r.get("revenue", 0) for r in apt_stats if r["_id"] == "completed"),
            "total_recovered": total_recovered,
            "recovered_by_source": recovered_by_source,
        },
        "daily_trend": [{"date": d["_id"], **{k: v for k, v in d.items() if k != "_id"}} for d in daily_trend],
        "recovered_events": recovered_events,
        "barber_performance": barber_stats,
        "messages": messages,
        "audit_summary": [{"provider": a["_id"]["provider"], "success": a["_id"]["success"], "count": a["count"]} for a in audit_stats],
    }


@api_router.get("/reporting/jobs-history")
async def jobs_history(
    limit: int = 50,
    user: dict = Depends(get_current_user)
):
    """Get history of scheduled job executions from audit log."""
    entries = await db.integration_audit_log.find(
        {"action": {"$in": ["daily_summary_email", "appointment_reminder", "send_sms", "send_email"]}},
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    return {"entries": entries, "count": len(entries)}


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
cors_origins = [o.strip() for o in os.environ.get('CORS_ORIGINS', '*').split(',')]
allow_creds = cors_origins != ["*"]
if not allow_creds:
    logger.warning("CORS_ORIGINS not set — credentials disabled. Set explicit origins for production.")
app.add_middleware(
    CORSMiddleware,
    allow_credentials=allow_creds,
    allow_origins=cors_origins,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)


# ==================== STARTUP EVENT ====================

@app.on_event("startup")
async def startup_event():
    """Initialize database with seed data if empty, then start scheduler"""
    logger.info("Starting Barbershop Autopilot...")
    
    # Check if shop exists
    shop_count = await db.shops.count_documents({})
    
    if shop_count == 0:
        logger.info("Seeding demo data...")
        await seed_demo_data()
    
    # Start background scheduler
    start_scheduler(db)
    
    logger.info("Barbershop Autopilot ready!")


@app.on_event("shutdown")
async def shutdown_event():
    """Stop background scheduler on shutdown"""
    stop_scheduler()
    logger.info("Barbershop Autopilot stopped.")


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
        "retention_enabled": True,
        "retention_lapse_weeks": 4,
        "retention_cooldown_days": 7,
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
        {"id": "msg_4", "shop_id": shop_id, "client_id": "client_1", "direction": MessageDirection.OUTBOUND.value, "message_type": "sms", "content": "Your appointment is confirmed! 📅 Today at 2:00 PM ✂️ Classic Haircut with Marcus Johnson. Reply YES to confirm or NO to cancel.", "created_at": (now - timedelta(hours=1, minutes=45)).isoformat()},
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
