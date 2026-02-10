# MongoDB Modules Reference

## Contents
- Database Connection
- Collection Access Points
- Agent Database Operations
- Audit and Revenue Logging
- SMS Compliance Storage
- Scheduled Jobs Queries

---

## Database Connection

### Singleton Client (backend/server.py)

```python
from motor.motor_asyncio import AsyncIOMotorClient

mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get("DB_NAME", "barbershop_autopilot")]
```

The `db` object is module-level — imported or passed to agents/services as a dependency. Graceful shutdown closes the client:

```python
@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
```

### Shop Context Dependency

Every authenticated endpoint receives a `Shop` model via FastAPI's dependency injection:

```python
async def get_shop(user: dict = Depends(get_current_user)) -> Shop:
    shop_data = await db.shops.find_one({"id": user.get("shop_id")}, {"_id": 0})
    if not shop_data:
        raise HTTPException(status_code=404, detail="Shop not found")
    return Shop(**shop_data)
```

See the **fastapi** skill for `Depends()` patterns.

---

## Collection Access Points

All collections are accessed via `db.<collection_name>`. No abstraction layer, no repository pattern.

### Direct Route Access (server.py)

```python
# Routes access db directly — no service layer
@app.get("/api/appointments")
async def list_appointments(shop: Shop = Depends(get_shop)):
    appointments = await db.appointments.find(
        {"shop_id": shop.id}, {"_id": 0}
    ).sort("scheduled_at", -1).to_list(100)
```

### Agent Access (agents.py)

Agents receive `db` as a constructor parameter:

```python
class FrontDeskAgent:
    def __init__(self, db, shop: Shop, sms_provider, ...):
        self.db = db
        self.shop = shop
```

All agent queries use `self.db.<collection>` and scope by `self.shop.id`.

---

## Agent Database Operations

### FrontDeskAgent — Appointment Lifecycle

```python
# Find pending appointment for client
appointment = await self.db.appointments.find_one({
    "shop_id": self.shop.id,
    "client_id": client.id,
    "status": {"$in": [AppointmentStatus.PENDING.value, AppointmentStatus.DEPOSIT_PAID.value]}
}, {"_id": 0})

# Confirm appointment
await self.db.appointments.update_one(
    {"id": appointment["id"]},
    {"$set": {
        "status": AppointmentStatus.CONFIRMED.value,
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }}
)

# Log business event
await self.db.events.insert_one({
    "id": str(uuid.uuid4()),
    "shop_id": self.shop.id,
    "event_type": event_type.value,
    "client_id": client_id,
    "revenue_impact": revenue_impact,
    "created_at": datetime.now(timezone.utc).isoformat()
})
```

### NoShowEnforcementAgent — Counters and Payments

```python
# Atomic increment of no-show counter
await self.db.clients.update_one(
    {"id": appointment["client_id"]},
    {"$inc": {"no_shows": 1}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}}
)

# Create payment record
await self.db.payments.insert_one({
    "id": str(uuid.uuid4()),
    "shop_id": self.shop.id,
    "client_id": client["id"],
    "amount": amount,
    "stripe_session_id": payment_link.session_id,
    "status": "pending",
    "payment_type": "deposit",
    "created_at": datetime.now(timezone.utc).isoformat()
})
```

### WaitlistFillAgent — Matching and Contact Tracking

```python
# Find matching waitlist entries with $or for barber preference
matches = await self.db.waitlist.find({
    "shop_id": self.shop.id,
    "active": True,
    "service_id": cancelled_appointment["service_id"],
    "$or": [
        {"barber_id": cancelled_appointment["barber_id"]},
        {"barber_id": None}  # No preference
    ]
}, {"_id": 0}).to_list(10)

# Track contact attempt
await self.db.waitlist.update_one(
    {"id": entry["id"]},
    {"$inc": {"contact_attempts": 1}, "$set": {"last_contacted": datetime.now(timezone.utc).isoformat()}}
)
```

---

## Audit and Revenue Logging

### Integration Audit (backend/audit.py)

Logs every external API call. NEVER blocks main operations on failure:

```python
try:
    await self.db.integration_audit_log.insert_one(log_entry)
except Exception as e:
    logger.error(f"Failed to write audit log: {e}")
    # No raise — audit failures must not break business logic
```

### Revenue Logger (backend/revenue_logger.py)

Tracks revenue attribution. Returns `bool` instead of raising:

```python
try:
    await self.db.recovered_revenue_events.insert_one(event)
    return True
except Exception as e:
    logger.error(f"[REVENUE] Failed to log {source.value} event: {e}")
    return False  # Never raise
```

**Pattern:** Non-critical writes use try/except with logging. Critical writes (appointments, payments) propagate exceptions.

---

## SMS Compliance Storage (backend/sms_compliance.py)

### Consent Check — Partial Projection

```python
client = await self.db.clients.find_one(
    {"id": client_id, "shop_id": self.shop_id},
    {"_id": 0, "sms_consent": 1, "phone": 1}
)
```

Only fetches the two fields needed for the consent check — minimizes data transfer.

### Opt-Out Update — Multi-Field Atomic Set

```python
await self.db.clients.update_one(
    {"id": client_id, "shop_id": self.shop_id},
    {"$set": {
        "sms_consent": False,
        "sms_consent_timestamp": datetime.now(timezone.utc).isoformat(),
        "sms_consent_source": "opt_out_stop",
        "updated_at": datetime.now(timezone.utc).isoformat()
    }}
)
```

---

## Scheduled Jobs Queries (backend/scheduled_jobs.py)

### Time Window Query for Reminders

```python
appointments = await self.db.appointments.find({
    "shop_id": self.shop.id,
    "status": {"$in": [AppointmentStatus.CONFIRMED.value, AppointmentStatus.DEPOSIT_PAID.value]},
    "scheduled_at": {"$gte": window_start.isoformat(), "$lte": window_end.isoformat()}
}, {"_id": 0}).to_list(100)
```

### Duplicate Check with Regex

```python
# Check if reminder already sent for this appointment
reminder_exists = await self.db.messages.find_one({
    "shop_id": self.shop.id,
    "client_id": apt["client_id"],
    "appointment_id": apt["id"],
    "direction": MessageDirection.OUTBOUND.value,
    "content": {"$regex": "Reminder:"}
})
```

Uses regex on `content` field to detect previously sent reminders. `find_one` returns `None` if no match — truthy check determines whether to skip.
