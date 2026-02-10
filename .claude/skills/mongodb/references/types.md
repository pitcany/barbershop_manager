# MongoDB Types Reference

## Contents
- Document Schema Conventions
- Pydantic Model Integration
- Enum Storage
- Timestamp Format
- ID Strategy
- Collection Schemas

---

## Document Schema Conventions

Every document in this project follows these rules:

1. **`id` field** — `str(uuid.uuid4())`, NOT MongoDB's `_id`
2. **`shop_id` field** — Present on every tenant-scoped document
3. **Timestamps** — ISO 8601 strings via `datetime.now(timezone.utc).isoformat()`
4. **Enums** — Stored as plain strings (`.value` property)
5. **No nested documents** — Flat structure with foreign key references (`client_id`, `barber_id`)

---

## Pydantic Model Integration

### Model Configuration

```python
from pydantic import BaseModel, Field, ConfigDict

class Shop(BaseModel):
    model_config = ConfigDict(extra="ignore")  # Tolerates _id and unknown fields from MongoDB

    id: str = Field(default_factory=generate_id)
    name: str
    phone: str
    created_at: str = Field(default_factory=utc_now)
```

`extra="ignore"` is critical. MongoDB returns `_id` on every document. Without this, Pydantic raises `ValidationError` on extra fields. See the **pydantic** skill.

### WARNING: Forgetting extra="ignore"

**The Problem:**

```python
# BAD — will crash on MongoDB documents containing _id
class Client(BaseModel):
    id: str
    name: str
```

**Why This Breaks:** MongoDB always returns `_id`. Pydantic V2 defaults to `extra="forbid"` behavior unless configured.

**The Fix:**

```python
# GOOD — ignores _id and any other MongoDB-added fields
class Client(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
```

### Dict-to-Model Conversion

```python
# From MongoDB dict to Pydantic model
shop_data = await db.shops.find_one({"id": shop_id}, {"_id": 0})
shop = Shop(**shop_data)  # Spread dict into model constructor

# From Pydantic model to MongoDB dict
await db.shops.insert_one(shop.model_dump())
```

The projection `{"_id": 0}` removes `_id` before conversion, but `extra="ignore"` is the safety net.

---

## Enum Storage

### Enum Definition Pattern

```python
class AppointmentStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    DEPOSIT_PENDING = "deposit_pending"
    DEPOSIT_PAID = "deposit_paid"
    COMPLETED = "completed"
    NO_SHOW = "no_show"
    CANCELLED = "cancelled"
    RESCHEDULED = "rescheduled"
```

Inheriting from `str` makes the enum JSON-serializable. The `.value` is the stored string.

### WARNING: Enum Objects in Queries

**The Problem:**

```python
# BAD — passes enum object, not string
await db.appointments.find({"status": AppointmentStatus.CONFIRMED})
```

**Why This Breaks:** Motor serializes the enum as an object, not a string. Query matches nothing. No error raised — just empty results.

**The Fix:**

```python
# GOOD — explicit .value extracts the string
await db.appointments.find({"status": AppointmentStatus.CONFIRMED.value})

# GOOD — $in with values
await db.appointments.find({"status": {"$in": [s.value for s in [AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]]}})
```

---

## Timestamp Format

### Storage

```python
"created_at": datetime.now(timezone.utc).isoformat()
# Produces: "2024-02-10T14:30:00.123456+00:00"
```

### Range Queries

```python
# ISO strings sort lexicographically — this works correctly
{"scheduled_at": {"$gte": start.isoformat(), "$lt": end.isoformat()}}
```

### WARNING: Mixing datetime and String Types

**The Problem:**

```python
# BAD — comparing datetime object against ISO string field
{"scheduled_at": {"$gte": datetime.now(timezone.utc)}}
```

**Why This Breaks:** MongoDB stores these as strings. A datetime object comparison against a string field returns no matches.

**The Fix:**

```python
# GOOD — compare strings to strings
{"scheduled_at": {"$gte": datetime.now(timezone.utc).isoformat()}}
```

---

## ID Strategy

```python
import uuid

def generate_id() -> str:
    return str(uuid.uuid4())

# Usage in document creation
{"id": str(uuid.uuid4()), "shop_id": shop.id, ...}
```

### Why Not ObjectId?

- ObjectIds require special JSON serialization
- String UUIDs work natively with Pydantic, JSON responses, and frontend
- No dependency on `bson` for ID generation

### Lookup Pattern

```python
# Always filter by "id", not "_id"
await db.clients.find_one({"id": client_id}, {"_id": 0})
```

---

## Collection Schemas

| Collection | Key Fields | Foreign Keys |
|-----------|-----------|-------------|
| `shops` | id, name, phone, address, deposit_amount, confirmation_window_hours | — |
| `admin_users` | id, shop_id, username, password_hash, role, last_login | shop_id -> shops |
| `barbers` | id, shop_id, name, active | shop_id -> shops |
| `services` | id, shop_id, name, price, duration_minutes | shop_id -> shops |
| `clients` | id, shop_id, name, phone, email, sms_consent, no_shows | shop_id -> shops |
| `appointments` | id, shop_id, client_id, barber_id, service_id, status, scheduled_at | shop_id, client_id, barber_id, service_id |
| `messages` | id, shop_id, client_id, appointment_id, direction, content | shop_id, client_id |
| `waitlist` | id, shop_id, client_id, service_id, barber_id, active | shop_id, client_id, service_id |
| `payments` | id, shop_id, client_id, appointment_id, amount, stripe_session_id, status | shop_id, client_id |
| `events` | id, shop_id, event_type, client_id, appointment_id, revenue_impact | shop_id, client_id |
| `email_outbox` | id, shop_id, to_email, subject, html_content | shop_id |
| `integration_audit_log` | id, shop_id, provider, action, success, error_message | shop_id |
| `recovered_revenue_events` | id, shop_id, source, amount, attributed_at | shop_id |

All collections use `shop_id` for tenant isolation. No embedded documents — references only.
