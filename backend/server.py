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
load_dotenv(ROOT_DIR / ".env")

# Import shared dependencies from deps module
from deps import db, pwd_context

# Import models (used by seed_demo_data)
from models import AppointmentStatus, MessageDirection, EventType

# Import scheduler (used by startup/shutdown — APScheduler path only)
from scheduler import start_scheduler, stop_scheduler

# Feature flag: set USE_CELERY_SCHEDULER=true to use Celery+Redis instead of APScheduler
USE_CELERY_SCHEDULER = os.environ.get("USE_CELERY_SCHEDULER", "false").lower() == "true"

# Import route modules
from routes import all_routers

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
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


# All route handlers live in routes/*.py modules
# (auth, appointments, clients, payments, calendar, jobs, public, webhooks)


# Include all route modules
for r in all_routers:
    api_router.include_router(r)

app.include_router(api_router)

# CORS middleware
cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",")]
allow_creds = cors_origins != ["*"]
if not allow_creds:
    logger.warning(
        "CORS_ORIGINS not set — credentials disabled. Set explicit origins for production."
    )
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

    # Ensure TTL index for rate-limit entries (auto-cleanup)
    await db.rate_limit_entries.create_index("expires_at", expireAfterSeconds=0)

    # Performance indexes for high-traffic queries
    await db.appointments.create_index([("shop_id", 1), ("scheduled_at", -1)])
    await db.appointments.create_index(
        [("shop_id", 1), ("status", 1), ("scheduled_at", -1)]
    )
    await db.appointments.create_index(
        [("client_id", 1), ("shop_id", 1), ("scheduled_at", -1)]
    )
    await db.clients.create_index([("shop_id", 1), ("created_at", -1)])
    await db.clients.create_index([("shop_id", 1), ("phone", 1)])
    await db.messages.create_index(
        [("shop_id", 1), ("client_id", 1), ("created_at", -1)]
    )
    await db.messages.create_index([("shop_id", 1), ("created_at", -1)])
    await db.waitlist.create_index([("shop_id", 1), ("active", 1)])
    await db.events.create_index([("shop_id", 1), ("created_at", -1)])
    await db.payments.create_index([("shop_id", 1), ("status", 1), ("payment_type", 1)])
    await db.payment_transactions.create_index([("shop_id", 1), ("session_id", 1)])
    await db.stripe_webhook_events.create_index("stripe_event_id", unique=True)
    await db.stripe_webhook_events.create_index([("created_at", -1)])

    # job_runs: unique per (job_name, window_key) for idempotency; indexed for history queries
    await db.job_runs.create_index([("job_name", 1), ("window_key", 1)], unique=True)
    await db.job_runs.create_index([("started_at", -1)])
    await db.job_runs.create_index([("status", 1)])

    # Unique index on shop slug for multi-tenancy
    # Use partial filter to skip docs with empty/missing slug (legacy shops)
    await db.shops.create_index(
        "slug",
        unique=True,
        partialFilterExpression={"slug": {"$exists": True, "$gt": ""}},
    )
    # Index for Twilio webhook phone-based routing
    # sparse=True so docs missing phone are excluded from uniqueness check
    await db.shops.create_index("phone", unique=True, sparse=True)

    # Enforce global username uniqueness at DB level (login has no shop context)
    await db.admin_users.create_index("username", unique=True)

    # Check if shop exists
    shop_count = await db.shops.count_documents({})
    if shop_count == 0:
        logger.info("Seeding demo data...")
        await seed_demo_data()

    if not USE_CELERY_SCHEDULER:
        start_scheduler(db)
    else:
        logger.info(
            "[SCHEDULER] Celery mode — APScheduler not started. Run worker + beat separately."
        )
    logger.info("Barbershop Autopilot ready!")


@app.on_event("shutdown")
async def shutdown_event():
    if not USE_CELERY_SCHEDULER:
        stop_scheduler()
    logger.info("Barbershop Autopilot stopped.")


@app.on_event("shutdown")
async def shutdown_db_client():
    from deps import _client

    _client.close()


# ==================== SEED DATA ====================


async def seed_demo_data():
    """Seed the database with rich demo barbershop data (30 days of history)."""
    import random
    import uuid

    shop_id = "demo_shop"
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    # ── Helpers ──────────────────────────────────────────────
    def uid():
        return str(uuid.uuid4())

    def ago(days=0, hours=0, minutes=0):
        """Return ISO string for a time in the past."""
        return (now - timedelta(days=days, hours=hours, minutes=minutes)).isoformat()

    def future(days=0, hours=0):
        return (now + timedelta(days=days, hours=hours)).isoformat()

    # ── Shop ────────────────────────────────────────────────
    shop = {
        "id": shop_id,
        "slug": "classic-cuts",
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
        "stripe_connect_account_id": None,
        "stripe_charges_enabled": False,
        "stripe_payouts_enabled": False,
        "platform_fee_bps": 0,
        "retention_enabled": True,
        "retention_lapse_weeks": 4,
        "retention_cooldown_days": 7,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    await db.shops.insert_one(shop)

    # ── Barbers ─────────────────────────────────────────────
    barber_ids = ["barber_1", "barber_2", "barber_3"]
    barbers = [
        {
            "id": "barber_1",
            "shop_id": shop_id,
            "name": "Marcus Johnson",
            "email": "marcus@classiccuts.local",
            "active": True,
            "created_at": now_iso,
        },
        {
            "id": "barber_2",
            "shop_id": shop_id,
            "name": "David Lee",
            "email": "david@classiccuts.local",
            "active": True,
            "created_at": now_iso,
        },
        {
            "id": "barber_3",
            "shop_id": shop_id,
            "name": "Anthony Davis",
            "email": "anthony@classiccuts.local",
            "active": True,
            "created_at": now_iso,
        },
    ]
    await db.barbers.insert_many(barbers)

    # ── Services ────────────────────────────────────────────
    service_defs = [
        {
            "id": "service_1",
            "name": "Classic Haircut",
            "description": "Traditional haircut with clippers and scissors",
            "duration_minutes": 30,
            "price": 25.0,
        },
        {
            "id": "service_2",
            "name": "Haircut + Beard Trim",
            "description": "Full haircut with beard shaping",
            "duration_minutes": 45,
            "price": 35.0,
        },
        {
            "id": "service_3",
            "name": "Premium Cut + Hot Towel",
            "description": "Deluxe haircut with hot towel treatment",
            "duration_minutes": 60,
            "price": 50.0,
        },
        {
            "id": "service_4",
            "name": "Kids Cut",
            "description": "Haircut for children under 12",
            "duration_minutes": 20,
            "price": 15.0,
        },
    ]
    services = [
        {**s, "shop_id": shop_id, "active": True, "created_at": now_iso}
        for s in service_defs
    ]
    await db.services.insert_many(services)
    svc_by_id = {s["id"]: s for s in service_defs}

    # ── Clients (10) ────────────────────────────────────────
    consent_ts = now_iso
    client_defs = [
        {
            "id": "client_1",
            "name": "John Smith",
            "phone": "+15559876543",
            "email": "john@example.com",
            "no_shows": 0,
        },
        {
            "id": "client_2",
            "name": "Mike Wilson",
            "phone": "+15551112222",
            "email": "mike@example.com",
            "no_shows": 2,
        },
        {
            "id": "client_3",
            "name": "James Brown",
            "phone": "+15553334444",
            "email": "james@example.com",
            "no_shows": 0,
        },
        {
            "id": "client_4",
            "name": "Robert Taylor",
            "phone": "+15554445555",
            "email": "robert@example.com",
            "no_shows": 0,
        },
        {
            "id": "client_5",
            "name": "Carlos Rivera",
            "phone": "+15555556666",
            "email": "carlos@example.com",
            "no_shows": 1,
        },
        {
            "id": "client_6",
            "name": "Daniel Kim",
            "phone": "+15556667777",
            "email": "daniel@example.com",
            "no_shows": 0,
        },
        {
            "id": "client_7",
            "name": "Marcus Thompson",
            "phone": "+15557778888",
            "email": "marcus@example.com",
            "no_shows": 0,
        },
        {
            "id": "client_8",
            "name": "Andre Williams",
            "phone": "+15558889999",
            "email": "andre@example.com",
            "no_shows": 2,
        },
        {
            "id": "client_9",
            "name": "Kevin Patel",
            "phone": "+15559990000",
            "email": "kevin@example.com",
            "no_shows": 0,
        },
        {
            "id": "client_10",
            "name": "Tyler Jackson",
            "phone": "+15550001111",
            "email": "tyler@example.com",
            "no_shows": 0,
        },
    ]
    clients = []
    for c in client_defs:
        clients.append(
            {
                **c,
                "shop_id": shop_id,
                "sms_consent": True,
                "sms_consent_timestamp": consent_ts,
                "sms_consent_source": "web_form",
                "total_appointments": 0,  # updated below
                "created_at": ago(days=random.randint(30, 90)),
                "updated_at": now_iso,
            }
        )
    await db.clients.insert_many(clients)

    # ── Historical appointments (past 30 days) ──────────────
    random.seed(42)  # deterministic for reproducible demo
    appointments = []
    apt_counter = 0
    client_apt_counts = {c["id"]: 0 for c in client_defs}

    # Build ~4 appointments per day for 30 days
    for day_offset in range(30, 0, -1):
        daily_count = random.randint(3, 6)
        for slot in range(daily_count):
            apt_counter += 1
            client = random.choice(client_defs)
            service = random.choice(service_defs)
            barber = random.choice(barber_ids)
            hour = 9 + slot * 2  # spread across business hours

            # Most are completed, a few are no-show or cancelled
            if client["id"] in ("client_2", "client_8") and random.random() < 0.3:
                status = AppointmentStatus.NO_SHOW.value
            elif random.random() < 0.03:
                status = AppointmentStatus.CANCELLED.value
            else:
                status = AppointmentStatus.COMPLETED.value

            scheduled = ago(days=day_offset, hours=-hour)
            apt_id = f"apt_hist_{apt_counter}"
            apt = {
                "id": apt_id,
                "shop_id": shop_id,
                "client_id": client["id"],
                "barber_id": barber,
                "service_id": service["id"],
                "scheduled_at": scheduled,
                "duration_minutes": service["duration_minutes"],
                "status": status,
                "price": service["price"]
                if status == AppointmentStatus.COMPLETED.value
                else 0,
                "deposit_required": random.random() < 0.3,
                "deposit_amount": 20.0 if random.random() < 0.3 else 0,
                "deposit_paid": status == AppointmentStatus.COMPLETED.value
                and random.random() < 0.3,
                "created_at": ago(days=day_offset + 1),
                "updated_at": scheduled,
            }
            appointments.append(apt)
            client_apt_counts[client["id"]] += 1

    # Upcoming appointments (today + tomorrow)
    upcoming_apts = [
        {
            "id": "apt_today_1",
            "shop_id": shop_id,
            "client_id": "client_1",
            "barber_id": "barber_1",
            "service_id": "service_1",
            "scheduled_at": future(hours=2),
            "duration_minutes": 30,
            "status": AppointmentStatus.CONFIRMED.value,
            "price": 0,
            "deposit_required": False,
            "deposit_amount": 0,
            "deposit_paid": False,
            "created_at": ago(days=1),
            "updated_at": now_iso,
        },
        {
            "id": "apt_today_2",
            "shop_id": shop_id,
            "client_id": "client_4",
            "barber_id": "barber_2",
            "service_id": "service_2",
            "scheduled_at": future(hours=4),
            "duration_minutes": 45,
            "status": AppointmentStatus.DEPOSIT_PAID.value,
            "price": 0,
            "deposit_required": True,
            "deposit_amount": 20.0,
            "deposit_paid": True,
            "created_at": ago(days=2),
            "updated_at": now_iso,
        },
        {
            "id": "apt_tomorrow_1",
            "shop_id": shop_id,
            "client_id": "client_3",
            "barber_id": "barber_1",
            "service_id": "service_3",
            "scheduled_at": future(days=1, hours=3),
            "duration_minutes": 60,
            "status": AppointmentStatus.PENDING.value,
            "price": 0,
            "deposit_required": False,
            "deposit_amount": 0,
            "deposit_paid": False,
            "created_at": ago(hours=5),
            "updated_at": now_iso,
        },
    ]
    appointments.extend(upcoming_apts)
    client_apt_counts["client_1"] += 1
    client_apt_counts["client_4"] += 1
    client_apt_counts["client_3"] += 1

    await db.appointments.insert_many(appointments)

    # Update client total_appointments counts
    for cid, count in client_apt_counts.items():
        if count > 0:
            await db.clients.update_one(
                {"id": cid}, {"$set": {"total_appointments": count}}
            )

    # ── Payments (deposits) ─────────────────────────────────
    payments = []
    for i in range(15):
        day_offset = random.randint(1, 28)
        client = random.choice(client_defs)
        payments.append(
            {
                "id": f"pay_{i + 1}",
                "shop_id": shop_id,
                "client_id": client["id"],
                "amount": 20.0,
                "payment_type": "deposit",
                "status": "completed",
                "stripe_payment_id": f"pi_mock_{uid()[:8]}",
                "created_at": ago(days=day_offset),
            }
        )
    await db.payments.insert_many(payments)

    # ── Events (30 days of revenue activity) ────────────────
    events = []
    evt_counter = 0

    # Waitlist fills — spread across 14 days for chart visibility
    for day_offset in [2, 4, 5, 7, 8, 10, 12, 13]:
        evt_counter += 1
        service = random.choice(service_defs)
        client = random.choice(client_defs)
        events.append(
            {
                "id": f"evt_{evt_counter}",
                "shop_id": shop_id,
                "event_type": EventType.WAITLIST_FILLED.value,
                "client_id": client["id"],
                "data": {
                    "service": service["name"],
                    "original_client": "cancelled_client",
                },
                "revenue_impact": service["price"],
                "created_at": ago(days=day_offset, hours=random.randint(9, 16)),
            }
        )

    # Deposit paid events
    for day_offset in [1, 3, 6, 9, 11]:
        evt_counter += 1
        client = random.choice(client_defs)
        events.append(
            {
                "id": f"evt_{evt_counter}",
                "shop_id": shop_id,
                "event_type": EventType.DEPOSIT_PAID.value,
                "client_id": client["id"],
                "data": {"amount": 20.0},
                "revenue_impact": 20.0,
                "created_at": ago(days=day_offset, hours=random.randint(9, 16)),
            }
        )

    # No-show detected events (negative revenue)
    for day_offset in [3, 6, 9, 11, 14]:
        evt_counter += 1
        service = random.choice(service_defs)
        events.append(
            {
                "id": f"evt_{evt_counter}",
                "shop_id": shop_id,
                "event_type": EventType.NO_SHOW_DETECTED.value,
                "client_id": random.choice(["client_2", "client_5", "client_8"]),
                "data": {"service": service["name"]},
                "revenue_impact": -service["price"],
                "created_at": ago(days=day_offset, hours=random.randint(9, 16)),
            }
        )

    # Revenue recovered events (no-show fees collected)
    for day_offset in [2, 5, 8, 13]:
        evt_counter += 1
        events.append(
            {
                "id": f"evt_{evt_counter}",
                "shop_id": shop_id,
                "event_type": EventType.REVENUE_RECOVERED.value,
                "client_id": random.choice(["client_2", "client_8"]),
                "data": {"type": "no_show_fee", "amount": 20.0},
                "revenue_impact": 20.0,
                "created_at": ago(days=day_offset, hours=random.randint(9, 16)),
            }
        )

    # Some general events for variety
    for day_offset in range(1, 8):
        evt_counter += 1
        events.append(
            {
                "id": f"evt_{evt_counter}",
                "shop_id": shop_id,
                "event_type": EventType.APPOINTMENT_CREATED.value,
                "client_id": random.choice(client_defs)["id"],
                "data": {},
                "revenue_impact": 0,
                "created_at": ago(days=day_offset, hours=random.randint(9, 16)),
            }
        )

    await db.events.insert_many(events)

    # ── Recovered revenue events ────────────────────────────
    recovered_revenue = []
    for evt in events:
        if evt["event_type"] in (
            EventType.WAITLIST_FILLED.value,
            EventType.REVENUE_RECOVERED.value,
        ):
            recovered_revenue.append(
                {
                    "id": uid(),
                    "shop_id": shop_id,
                    "event_id": evt["id"],
                    "event_type": evt["event_type"],
                    "client_id": evt["client_id"],
                    "amount": evt["revenue_impact"],
                    "created_at": evt["created_at"],
                }
            )
    if recovered_revenue:
        await db.recovered_revenue_events.insert_many(recovered_revenue)

    # ── Messages (conversations across clients) ─────────────
    messages = []
    msg_counter = 0

    # Conversation 1: John Smith booking (today)
    for offset_min, direction, content in [
        (90, "inbound", "Hi, I'd like to book a haircut"),
        (
            85,
            "outbound",
            "Hi John! Thanks for reaching out to Classic Cuts. We have availability today at 2pm or 4pm. Which works for you?",
        ),
        (80, "inbound", "2pm works great"),
        (
            75,
            "outbound",
            "Your appointment is confirmed! Today at 2:00 PM - Classic Haircut with Marcus Johnson. Reply YES to confirm or NO to cancel.",
        ),
    ]:
        msg_counter += 1
        messages.append(
            {
                "id": f"msg_{msg_counter}",
                "shop_id": shop_id,
                "client_id": "client_1",
                "direction": direction,
                "message_type": "sms",
                "content": content,
                "created_at": ago(minutes=offset_min),
            }
        )

    # Conversation 2: Robert Taylor (today)
    for offset_min, direction, content in [
        (120, "inbound", "BOOK tomorrow 3pm beard trim"),
        (
            115,
            "outbound",
            "Got it, Robert! You're booked for tomorrow at 3:00 PM - Haircut + Beard Trim with David Lee. We'll send a reminder!",
        ),
    ]:
        msg_counter += 1
        messages.append(
            {
                "id": f"msg_{msg_counter}",
                "shop_id": shop_id,
                "client_id": "client_4",
                "direction": direction,
                "message_type": "sms",
                "content": content,
                "created_at": ago(minutes=offset_min),
            }
        )

    # Conversation 3: Carlos Rivera confirmation (yesterday)
    for offset_hours, direction, content in [
        (
            26,
            "outbound",
            "Reminder: You have an appointment tomorrow at 11:00 AM - Classic Haircut. Reply YES to confirm or CANCEL to cancel.",
        ),
        (25, "inbound", "YES"),
        (25, "outbound", "Great! Your appointment is confirmed. See you tomorrow!"),
    ]:
        msg_counter += 1
        messages.append(
            {
                "id": f"msg_{msg_counter}",
                "shop_id": shop_id,
                "client_id": "client_5",
                "direction": direction,
                "message_type": "sms",
                "content": content,
                "created_at": ago(hours=offset_hours),
            }
        )

    # Conversation 4: Mike Wilson no-show follow-up (3 days ago)
    for offset_hours, direction, content in [
        (
            72,
            "outbound",
            "Hi Mike, you missed your appointment today. Per our policy, a $20 no-show fee has been applied. Reply HELP for options.",
        ),
        (71, "inbound", "Sorry I forgot! Can I rebook?"),
        (
            70,
            "outbound",
            "No problem! A deposit of $20 will be required for your next booking. Reply BOOK to schedule.",
        ),
    ]:
        msg_counter += 1
        messages.append(
            {
                "id": f"msg_{msg_counter}",
                "shop_id": shop_id,
                "client_id": "client_2",
                "direction": direction,
                "message_type": "sms",
                "content": content,
                "created_at": ago(hours=offset_hours),
            }
        )

    # A few older messages for history
    for day_offset in [5, 7, 10, 14]:
        client = random.choice(client_defs)
        msg_counter += 1
        messages.append(
            {
                "id": f"msg_{msg_counter}",
                "shop_id": shop_id,
                "client_id": client["id"],
                "direction": "outbound",
                "message_type": "sms",
                "content": f"Reminder: You have an appointment tomorrow. Reply YES to confirm.",
                "created_at": ago(days=day_offset, hours=10),
            }
        )
        msg_counter += 1
        messages.append(
            {
                "id": f"msg_{msg_counter}",
                "shop_id": shop_id,
                "client_id": client["id"],
                "direction": "inbound",
                "message_type": "sms",
                "content": "YES",
                "created_at": ago(days=day_offset, hours=9),
            }
        )

    await db.messages.insert_many(messages)

    # ── Waitlist ────────────────────────────────────────────
    waitlist = [
        {
            "id": "wait_1",
            "shop_id": shop_id,
            "client_id": "client_3",
            "service_id": "service_2",
            "preferred_date": future(days=2),
            "flexible_hours": 3,
            "active": True,
            "contact_attempts": 0,
            "created_at": ago(days=1),
        },
        {
            "id": "wait_2",
            "shop_id": shop_id,
            "client_id": "client_6",
            "service_id": "service_3",
            "preferred_date": future(days=3),
            "flexible_hours": 2,
            "active": True,
            "contact_attempts": 0,
            "created_at": ago(hours=12),
        },
        {
            "id": "wait_3",
            "shop_id": shop_id,
            "client_id": "client_9",
            "service_id": "service_1",
            "preferred_date": future(days=1),
            "flexible_hours": 4,
            "active": True,
            "contact_attempts": 1,
            "created_at": ago(hours=6),
        },
    ]
    await db.waitlist.insert_many(waitlist)

    # ── Admin user ──────────────────────────────────────────
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    admin = {
        "id": "admin_1",
        "shop_id": shop_id,
        "username": "admin",
        "password_hash": pwd_context.hash(admin_password),
        "role": "super_admin",
        "created_at": now_iso,
    }
    await db.admin_users.insert_one(admin)

    logger.info("Demo data seeded successfully!")
    logger.info(
        "Admin login: username='admin' (password set via ADMIN_PASSWORD env var)"
    )
