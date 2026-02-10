# Pydantic Workflows Reference

## Contents
- Adding a New Domain Model
- Adding a New Enum
- Adding a Request/Response DTO
- Adding a Provider Interface Model
- Extending an Existing Model
- MongoDB Hydration Workflow

## Adding a New Domain Model

Copy this checklist and track progress:
- [ ] Step 1: Add model class to `backend/models.py` with `ConfigDict(extra="ignore")`
- [ ] Step 2: Include `id`, `shop_id`, `created_at` fields using factory defaults
- [ ] Step 3: Import model in `backend/server.py`
- [ ] Step 4: Add MongoDB collection queries with `{"_id": 0}` projection
- [ ] Step 5: Add seed data in `seed_demo_data()` if needed

```python
# backend/models.py
class NewEntity(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=generate_id)
    shop_id: str
    name: str
    active: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
```

Then import in `backend/server.py`:

```python
from models import (
    # ... existing imports ...
    NewEntity,
)
```

MongoDB operations follow the project pattern — direct Motor queries, no ORM:

```python
# Insert
doc = NewEntity(shop_id=shop.id, name="Test").model_dump()
doc["created_at"] = doc["created_at"].isoformat()
doc["updated_at"] = doc["updated_at"].isoformat()
await db.new_entities.insert_one(doc)

# Query
data = await db.new_entities.find_one({"id": entity_id}, {"_id": 0})
entity = NewEntity(**data)
```

### WARNING: Forgetting ISO String Conversion for Timestamps

**The Problem:**

```python
# BAD - inserts datetime objects into MongoDB
doc = NewEntity(shop_id=shop.id, name="Test").model_dump()
await db.new_entities.insert_one(doc)
```

**Why This Breaks:**
1. This project stores timestamps as ISO strings, not datetime objects
2. All existing queries compare timestamps as strings (`{"$gte": some_iso_string}`)
3. Mixing datetime objects and ISO strings causes comparison failures in MongoDB

**The Fix:** Convert to `.isoformat()` before inserting. The codebase builds dicts manually for inserts rather than using `model_dump()` directly — follow that pattern:

```python
await db.new_entities.insert_one({
    "id": str(uuid.uuid4()),
    "shop_id": shop.id,
    "name": "Test",
    "active": True,
    "created_at": datetime.now(timezone.utc).isoformat(),
    "updated_at": datetime.now(timezone.utc).isoformat(),
})
```

## Adding a New Enum

Enums go in `backend/models.py`, use `(str, Enum)` dual inheritance, and UPPER_SNAKE values:

```python
class NotificationChannel(str, Enum):
    SMS = "sms"
    EMAIL = "email"
    PUSH = "push"
```

Then use `.value` in MongoDB operations. See the **fastapi** skill for using enums in route parameters.

## Adding a Request/Response DTO

DTOs are plain `BaseModel` — no `ConfigDict`, no `id` field, no timestamps:

```python
# Request DTO — fields the client sends
class CreateBarberRequest(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None

# Response DTO — fields the API returns
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
```

For PATCH endpoints, make all fields Optional:

```python
class UpdateBarberRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    active: Optional[bool] = None
```

Filter `None` values in the handler:

```python
update_data = {k: v for k, v in request.model_dump().items() if v is not None}
```

## Adding a Provider Interface Model

Provider models live in `backend/providers/interfaces.py`, not `models.py`. They define the contract between business logic and external services:

```python
# backend/providers/interfaces.py
class CalendarEvent(BaseModel):
    id: Optional[str] = None
    summary: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    location: Optional[str] = None
    attendee_email: Optional[str] = None
```

Pattern: provider response models always include `success` + `error`:

```python
class EmailResponse(BaseModel):
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
```

## Extending an Existing Model

Copy this checklist and track progress:
- [ ] Step 1: Add field to model class in `backend/models.py` with a default value
- [ ] Step 2: Update seed data in `seed_demo_data()` to include the new field
- [ ] Step 3: Update any route handlers that return or modify this model
- [ ] Step 4: Verify `extra="ignore"` handles existing MongoDB documents without the field

Adding a field with a default is backwards-compatible — existing documents missing the field will use the default when hydrated:

```python
class Client(BaseModel):
    model_config = ConfigDict(extra="ignore")
    # ... existing fields ...
    preferred_barber_id: Optional[str] = None  # New field, defaults to None
```

No migration needed. Existing documents in MongoDB will work because:
1. `extra="ignore"` handles any unexpected fields
2. The new field has a default, so missing values are fine
3. MongoDB is schemaless — no ALTER TABLE required

## MongoDB Hydration Workflow

The standard pattern for reading a model from MongoDB:

```python
# 1. Query with _id exclusion
doc = await db.clients.find_one(
    {"id": client_id, "shop_id": shop.id},
    {"_id": 0}
)

# 2. Check for None
if not doc:
    raise HTTPException(status_code=404, detail="Client not found")

# 3. Hydrate to model
client = Client(**doc)

# 4. Use model attributes (type-safe)
if client.sms_consent:
    await send_notification(client.phone)
```

For list queries:

```python
docs = await db.clients.find(
    {"shop_id": shop.id},
    {"_id": 0}
).sort("created_at", -1).limit(50).to_list(50)

# Return raw dicts for API responses (no hydration needed)
return {"clients": docs, "total": total}
```

Note: the codebase returns raw dicts from list endpoints for performance. Hydration to Pydantic models is only done when business logic needs typed access to fields (e.g., in agents, compliance service).

1. Make changes to `backend/models.py`
2. Validate: `cd backend && python -c "from models import *; print('Models OK')"`
3. If validation fails, fix import or syntax errors and repeat step 2
4. Only proceed when validation passes
