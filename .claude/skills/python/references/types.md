# Python Types Reference

## Contents
- Pydantic Model Conventions
- Enum Definitions
- Request/Response DTOs
- Provider Interface Types
- Anti-Patterns

## Pydantic Model Conventions

All models use Pydantic v2 with `ConfigDict(extra="ignore")` to safely ignore extra MongoDB fields like `_id`. See the **pydantic** skill for advanced validation.

### Base Entity Pattern

Every entity follows this structure:

```python
from pydantic import BaseModel, Field, ConfigDict
from models import generate_id, utc_now

class Entity(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=generate_id)
    shop_id: str
    # ... domain fields
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
```

Rules:
- `id`: Always `str`, generated via `generate_id()` (UUID4)
- `shop_id`: Required on every entity for multi-tenancy
- `extra="ignore"`: Prevents errors when constructing from MongoDB docs that contain `_id`
- Timestamps: `datetime` type in model, stored as ISO strings in MongoDB

### Existing Models (backend/models.py)

| Model | Key Fields | Purpose |
|-------|-----------|---------|
| `Shop` | `business_hours`, `deposit_amount`, policy fields | Shop configuration |
| `Client` | `phone`, `sms_consent`, `no_shows`, `stripe_customer_id` | Client with SMS/payment state |
| `Appointment` | `status`, `scheduled_at`, `deposit_*` fields | Core booking entity |
| `Message` | `direction`, `message_type`, `content` | SMS/email conversation log |
| `Waitlist` | `preferred_date`, `flexible_hours`, `contact_attempts` | Waitlist queue entry |
| `Payment` | `stripe_session_id`, `status`, `payment_type` | Deposit/fee tracking |
| `Event` | `event_type`, `revenue_impact`, `data` | Business event log |
| `EmailOutbox` | `to_email`, `subject`, `html_content`, `sent` | Email queue |

## Enum Definitions

All enums inherit from `(str, Enum)` so they serialize to strings in JSON and MongoDB:

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

When querying MongoDB, use `.value`:

```python
# GOOD
await db.appointments.find({"status": AppointmentStatus.CONFIRMED.value})

# BAD — passes the enum object, not the string
await db.appointments.find({"status": AppointmentStatus.CONFIRMED})
```

Other enums: `MessageDirection`, `MessageType`, `PaymentStatus`, `EventType`, `AuditProvider`, `AuditAction`, `RevenueSource`.

## Request/Response DTOs

Request models are plain Pydantic — no `ConfigDict`, no `id` field:

```python
class LoginRequest(BaseModel):
    username: str
    password: str

class PolicyUpdate(BaseModel):
    deposit_amount: Optional[float] = None
    deposit_required_hours: Optional[int] = None
    # All Optional — only provided fields get updated
```

For partial updates, filter out `None` values:

```python
update_data = {k: v for k, v in update.model_dump().items() if v is not None}
update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
await db.shops.update_one({"id": shop.id}, {"$set": update_data})
```

## Provider Interface Types

Provider interfaces use Pydantic models for request/response types (in `providers/interfaces.py`):

```python
class SMSMessage(BaseModel):
    to: str
    body: str
    from_: Optional[str] = None

class SMSResponse(BaseModel):
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
```

| Interface | Request Type | Response Type |
|-----------|-------------|---------------|
| `SMSProvider` | `SMSMessage` | `SMSResponse` |
| `EmailProvider` | `EmailMessage` | `EmailResponse` |
| `PaymentProvider` | amount/urls/metadata args | `PaymentLink`, `PaymentStatus` |
| `CalendarProvider` | `CalendarEvent` | `Optional[str]` (event ID) |

## Anti-Patterns

### WARNING: Missing ConfigDict on Entity Models

**The Problem:**

```python
# BAD — no extra="ignore"
class MyEntity(BaseModel):
    id: str
    name: str
```

**Why This Breaks:**
MongoDB returns `_id` in every document. Without `extra="ignore"`, constructing `MyEntity(**mongo_doc)` raises `ValidationError` for the unexpected `_id` field. The `{"_id": 0}` projection helps, but defensive models are safer.

**The Fix:**

```python
class MyEntity(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=generate_id)
    name: str
```

### WARNING: Using datetime Objects in MongoDB Docs

**The Problem:**

```python
# BAD — storing datetime object
await db.collection.insert_one({
    "created_at": datetime.now(timezone.utc)  # datetime object
})
```

**Why This Breaks:**
The codebase stores all dates as ISO strings. Mixing datetime objects and strings causes inconsistent comparison behavior in MongoDB queries (`$gte`, `$lte`) and breaks `datetime.fromisoformat()` parsing.

**The Fix:**

```python
await db.collection.insert_one({
    "created_at": datetime.now(timezone.utc).isoformat()  # ISO string
})
```

### WARNING: Enum Without str Mixin

```python
# BAD — won't serialize to JSON properly
class Status(Enum):
    ACTIVE = "active"

# GOOD — serializes as plain string
class Status(str, Enum):
    ACTIVE = "active"
```

Without the `str` mixin, FastAPI's JSON encoder may serialize it as `{"value": "active"}` instead of just `"active"`.
