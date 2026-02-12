"""
Barbershop Autopilot MVP - Main FastAPI Server
Slim entry point: app creation, middleware, startup/shutdown, seed data.
All route logic lives in /routes/*.py
"""
from fastapi import FastAPI, APIRouter
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Load environment
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from deps import db, pwd_context
from models import AppointmentStatus, MessageDirection, EventType
from scheduler import start_scheduler, stop_scheduler
from routes import all_routers

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
    version="1.0.0",
)

# Create API router and include all sub-routers
api_router = APIRouter(prefix="/api")
for r in all_routers:
    api_router.include_router(r)
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


# ==================== STARTUP / SHUTDOWN ====================

@app.on_event("startup")
async def startup_event():
    """Initialize database with seed data if empty, then start scheduler"""
    logger.info("Starting Barbershop Autopilot...")

    shop_count = await db.shops.count_documents({})
    if shop_count == 0:
        logger.info("Seeding demo data...")
        await seed_demo_data()

    start_scheduler(db)
    logger.info("Barbershop Autopilot ready!")


@app.on_event("shutdown")
async def shutdown_event():
    stop_scheduler()
    logger.info("Barbershop Autopilot stopped.")


@app.on_event("shutdown")
async def shutdown_db_client():
    from deps import _client
    _client.close()


# ==================== SEED DATA ====================

async def seed_demo_data():
    """Seed the database with demo barbershop data"""
    shop_id = "demo_shop"

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
            "sunday": None,
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
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.shops.insert_one(shop)

    barbers = [
        {"id": "barber_1", "shop_id": shop_id, "name": "Marcus Johnson", "email": "marcus@classiccuts.local", "active": True, "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": "barber_2", "shop_id": shop_id, "name": "David Lee", "email": "david@classiccuts.local", "active": True, "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": "barber_3", "shop_id": shop_id, "name": "Anthony Davis", "email": "anthony@classiccuts.local", "active": True, "created_at": datetime.now(timezone.utc).isoformat()},
    ]
    await db.barbers.insert_many(barbers)

    services = [
        {"id": "service_1", "shop_id": shop_id, "name": "Classic Haircut", "description": "Traditional haircut with clippers and scissors", "duration_minutes": 30, "price": 25.0, "active": True, "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": "service_2", "shop_id": shop_id, "name": "Haircut + Beard Trim", "description": "Full haircut with beard shaping", "duration_minutes": 45, "price": 35.0, "active": True, "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": "service_3", "shop_id": shop_id, "name": "Premium Cut + Hot Towel", "description": "Deluxe haircut with hot towel treatment", "duration_minutes": 60, "price": 50.0, "active": True, "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": "service_4", "shop_id": shop_id, "name": "Kids Cut", "description": "Haircut for children under 12", "duration_minutes": 20, "price": 15.0, "active": True, "created_at": datetime.now(timezone.utc).isoformat()},
    ]
    await db.services.insert_many(services)

    consent_timestamp = datetime.now(timezone.utc).isoformat()
    clients = [
        {"id": "client_1", "shop_id": shop_id, "name": "John Smith", "phone": "+15559876543", "email": "john@example.com", "sms_consent": True, "sms_consent_timestamp": consent_timestamp, "sms_consent_source": "web_form", "total_appointments": 5, "no_shows": 0, "created_at": datetime.now(timezone.utc).isoformat(), "updated_at": datetime.now(timezone.utc).isoformat()},
        {"id": "client_2", "shop_id": shop_id, "name": "Mike Wilson", "phone": "+15551112222", "email": "mike@example.com", "sms_consent": True, "sms_consent_timestamp": consent_timestamp, "sms_consent_source": "web_form", "total_appointments": 3, "no_shows": 1, "created_at": datetime.now(timezone.utc).isoformat(), "updated_at": datetime.now(timezone.utc).isoformat()},
        {"id": "client_3", "shop_id": shop_id, "name": "James Brown", "phone": "+15553334444", "email": "james@example.com", "sms_consent": True, "sms_consent_timestamp": consent_timestamp, "sms_consent_source": "inbound_sms", "total_appointments": 8, "no_shows": 0, "created_at": datetime.now(timezone.utc).isoformat(), "updated_at": datetime.now(timezone.utc).isoformat()},
    ]
    await db.clients.insert_many(clients)

    now = datetime.now(timezone.utc)
    appointments = [
        {"id": "apt_1", "shop_id": shop_id, "client_id": "client_1", "barber_id": "barber_1", "service_id": "service_1", "scheduled_at": (now + timedelta(hours=2)).isoformat(), "duration_minutes": 30, "status": AppointmentStatus.CONFIRMED.value, "deposit_required": False, "deposit_amount": 0, "deposit_paid": False, "created_at": datetime.now(timezone.utc).isoformat(), "updated_at": datetime.now(timezone.utc).isoformat()},
        {"id": "apt_2", "shop_id": shop_id, "client_id": "client_2", "barber_id": "barber_2", "service_id": "service_2", "scheduled_at": (now + timedelta(hours=4)).isoformat(), "duration_minutes": 45, "status": AppointmentStatus.DEPOSIT_PENDING.value, "deposit_required": True, "deposit_amount": 20.0, "deposit_paid": False, "created_at": datetime.now(timezone.utc).isoformat(), "updated_at": datetime.now(timezone.utc).isoformat()},
        {"id": "apt_3", "shop_id": shop_id, "client_id": "client_3", "barber_id": "barber_1", "service_id": "service_3", "scheduled_at": (now + timedelta(days=1, hours=3)).isoformat(), "duration_minutes": 60, "status": AppointmentStatus.PENDING.value, "deposit_required": False, "deposit_amount": 0, "deposit_paid": False, "created_at": datetime.now(timezone.utc).isoformat(), "updated_at": datetime.now(timezone.utc).isoformat()},
    ]
    await db.appointments.insert_many(appointments)

    messages = [
        {"id": "msg_1", "shop_id": shop_id, "client_id": "client_1", "direction": MessageDirection.INBOUND.value, "message_type": "sms", "content": "Hi, I'd like to book a haircut", "created_at": (now - timedelta(hours=2)).isoformat()},
        {"id": "msg_2", "shop_id": shop_id, "client_id": "client_1", "direction": MessageDirection.OUTBOUND.value, "message_type": "sms", "content": "Hi John! Thanks for reaching out to Classic Cuts Barbershop. We have availability today at 2pm or 4pm. Which works for you?", "created_at": (now - timedelta(hours=1, minutes=55)).isoformat()},
        {"id": "msg_3", "shop_id": shop_id, "client_id": "client_1", "direction": MessageDirection.INBOUND.value, "message_type": "sms", "content": "2pm works great", "created_at": (now - timedelta(hours=1, minutes=50)).isoformat()},
        {"id": "msg_4", "shop_id": shop_id, "client_id": "client_1", "direction": MessageDirection.OUTBOUND.value, "message_type": "sms", "content": "Your appointment is confirmed! Today at 2:00 PM - Classic Haircut with Marcus Johnson. Reply YES to confirm or NO to cancel.", "created_at": (now - timedelta(hours=1, minutes=45)).isoformat()},
    ]
    await db.messages.insert_many(messages)

    waitlist = [
        {"id": "wait_1", "shop_id": shop_id, "client_id": "client_3", "service_id": "service_2", "preferred_date": (now + timedelta(days=2)).isoformat(), "flexible_hours": 3, "active": True, "contact_attempts": 0, "created_at": datetime.now(timezone.utc).isoformat()},
    ]
    await db.waitlist.insert_many(waitlist)

    events = [
        {"id": "event_1", "shop_id": shop_id, "event_type": EventType.WAITLIST_FILLED.value, "client_id": "client_1", "data": {"service": "Classic Haircut"}, "revenue_impact": 25.0, "created_at": (now - timedelta(days=3)).isoformat()},
        {"id": "event_2", "shop_id": shop_id, "event_type": EventType.DEPOSIT_PAID.value, "client_id": "client_2", "data": {"amount": 20.0}, "revenue_impact": 20.0, "created_at": (now - timedelta(days=2)).isoformat()},
        {"id": "event_3", "shop_id": shop_id, "event_type": EventType.NO_SHOW_DETECTED.value, "client_id": "client_2", "data": {"service": "Haircut + Beard Trim"}, "revenue_impact": -35.0, "created_at": (now - timedelta(days=5)).isoformat()},
    ]
    await db.events.insert_many(events)

    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    admin = {
        "id": "admin_1",
        "shop_id": shop_id,
        "username": "admin",
        "password_hash": pwd_context.hash(admin_password),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.admin_users.insert_one(admin)

    logger.info("Demo data seeded successfully!")
    logger.info(f"Admin login: username='admin', password='{admin_password}'")
