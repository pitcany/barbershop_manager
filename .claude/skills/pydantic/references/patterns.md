# Pydantic Patterns Reference

## Contents
- ID and Timestamp Factories
- ConfigDict extra="ignore" Pattern
- str Enum Pattern
- Partial Update DTOs
- Provider Interface Models
- Anti-Patterns

## ID and Timestamp Factories

Every domain model uses shared factory functions defined at the top of `backend/models.py`:

```python
import uuid
from datetime import datetime, timezone

def generate_id() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)
```

Use `Field(default_factory=...)` instead of a direct call. Direct calls evaluate at class definition time, producing the same value for every instance.

```python
# GOOD
id: str = Field(default_factory=generate_id)
created_at: datetime = Field(default_factory=utc_now)

# BAD - same ID/timestamp for every instance
id: str = str(uuid.uuid4())
created_at: datetime = datetime.now(timezone.utc)
```

## ConfigDict extra="ignore" Pattern

Every domain model that gets hydrated from MongoDB **must** include `ConfigDict(extra="ignore")`. MongoDB injects `_id` into every document, and without this config, `Model(**doc)` raises a validation error.

```python
# GOOD - safely ignores _id from MongoDB
class Barber(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=generate_id)
    shop_id: str
    name: str

# Hydration from MongoDB works:
doc = await db.barbers.find_one({"id": barber_id}, {"_id": 0})
barber = Barber(**doc)
```

Note: all queries also use `{"_id": 0}` projection as a defense-in-depth measure. Both the projection and `extra="ignore"` are required — the projection is the primary guard, and `extra="ignore"` catches cases where projection is forgotten.

### WARNING: Missing extra="ignore" on Domain Models

**The Problem:**

```python
# BAD - will crash on MongoDB hydration if _id leaks through
class Service(BaseModel):
    id: str = Field(default_factory=generate_id)
    name: str
```

**Why This Breaks:**
1. If any query forgets `{"_id": 0}`, Pydantic raises `ValidationError` for the unexpected `_id` field
2. Pydantic v2 defaults to `extra="forbid"` behavior when extra fields appear without config
3. This silently works in tests but breaks in production when real MongoDB data flows through

**The Fix:**

```python
class Service(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=generate_id)
    name: str
```

**When You Might Be Tempted:** When creating a quick model "just for this endpoint" that you think won't touch MongoDB. If it has an `id` field, it will end up in MongoDB.

## str Enum Pattern

All enums inherit from both `str` and `Enum` so values serialize as plain strings in JSON responses and MongoDB documents:

```python
class PaymentStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
```

Use `.value` when writing to MongoDB or comparing with raw strings from queries:

```python
# Writing to MongoDB
await db.appointments.update_one(
    {"id": apt_id},
    {"$set": {"status": AppointmentStatus.CONFIRMED.value}}
)

# Querying MongoDB with enum values
await db.appointments.find({
    "status": {"$in": [
        AppointmentStatus.PENDING.value,
        AppointmentStatus.CONFIRMED.value
    ]}
})
```

### WARNING: Using Enum Member Instead of .value in MongoDB

**The Problem:**

```python
# BAD - writes the enum object, not the string
await db.appointments.update_one(
    {"id": apt_id},
    {"$set": {"status": AppointmentStatus.CONFIRMED}}
)
```

**Why This Breaks:**
1. Motor/PyMongo may serialize the enum differently than expected
2. Queries using raw string comparison will fail to match
3. Inconsistent data in MongoDB — some records have strings, others have enum representations

**The Fix:** Always use `.value` for MongoDB operations.

## Partial Update DTOs

For PATCH endpoints, use DTOs where every field is `Optional` with `None` default. Filter out `None` values before applying the update:

```python
class PolicyUpdate(BaseModel):
    deposit_amount: Optional[float] = None
    deposit_required_hours: Optional[int] = None
    confirmation_window_hours: Optional[int] = None
    cancellation_window_hours: Optional[int] = None

# In the route handler:
update_data = {k: v for k, v in update.model_dump().items() if v is not None}
update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
await db.shops.update_one({"id": shop.id}, {"$set": update_data})
```

Do NOT use `model_dump(exclude_unset=True)` — it behaves differently when a client explicitly sends `null`. The `v is not None` filter is the project convention.

## Provider Interface Models

Models in `backend/providers/interfaces.py` are lightweight DTOs for provider communication. They do NOT use `ConfigDict(extra="ignore")` because they never touch MongoDB:

```python
class SMSMessage(BaseModel):
    to: str
    body: str
    from_: Optional[str] = None  # trailing underscore avoids 'from' keyword

class SMSResponse(BaseModel):
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
```

Pattern: response models always include `success: bool` and `error: Optional[str]` for uniform error handling.

### WARNING: Mutable Default for dict/list Fields

**The Problem:**

```python
# BAD - shared mutable default
class Event(BaseModel):
    data: dict = {}
    metadata: Dict[str, Any] = {}
```

**Why This Breaks:** Pydantic v2 handles this correctly (creates new instances), but it triggers linter warnings and is inconsistent with the codebase convention.

**The Fix:**

```python
class Event(BaseModel):
    data: dict = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

This project consistently uses `Field(default_factory=...)` for all mutable defaults.
