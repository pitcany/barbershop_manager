# Python Patterns Reference

## Contents
- Async Patterns
- Provider Abstraction
- Agent Pattern
- Factory Functions
- Non-Blocking Side Effects
- Datetime Handling
- Anti-Patterns

## Async Patterns

All I/O in this codebase is async. Every function that touches MongoDB, sends SMS, or calls external APIs must be `async def`.

```python
# GOOD — async throughout
async def process_cancellation(self, appointment_id: str):
    appointment = await self.db.appointments.find_one(
        {"id": appointment_id}, {"_id": 0}
    )
    if not appointment:
        return
    matches = await self.find_waitlist_matches(appointment)
    for match in matches:
        if await self.offer_slot_to_waitlist(appointment, match):
            break
```

```python
# BAD — sync call blocks the event loop
def get_appointment(self, appointment_id: str):
    # pymongo sync call blocks all other requests
    return self.db.appointments.find_one({"id": appointment_id})
```

Motor (async MongoDB driver) is the only database driver used. Never import `pymongo` directly for queries.

### Cursor Iteration

```python
# GOOD — .to_list() with explicit limit
services = await self.db.services.find(
    {"shop_id": self.shop.id, "active": True}, {"_id": 0}
).to_list(10)

# BAD — async for without limit risks loading unbounded data
async for doc in self.db.services.find({"shop_id": self.shop.id}):
    results.append(doc)
```

## Provider Abstraction

External services (Twilio, Stripe, SendGrid, Google Calendar) follow an ABC interface pattern. See the **fastapi** skill for how providers integrate with routes.

```python
# Interface definition (providers/interfaces.py)
class SMSProvider(ABC):
    @abstractmethod
    async def send_sms(self, message: SMSMessage) -> SMSResponse:
        pass

# Mock implementation (providers/mock_providers.py)
class MockSMSProvider(SMSProvider):
    async def send_sms(self, message: SMSMessage) -> SMSResponse:
        message_id = f"mock_sms_{uuid.uuid4().hex[:12]}"
        self.sent_messages.append({...})
        return SMSResponse(success=True, message_id=message_id)

# Singleton access (providers/__init__.py)
_sms_provider: Optional[SMSProvider] = None

def get_sms() -> SMSProvider:
    global _sms_provider
    if _sms_provider is None:
        _sms_provider = get_sms_provider()
    return _sms_provider
```

Adding a new provider:
1. Define interface in `providers/interfaces.py` (Pydantic request/response models + ABC)
2. Add mock in `providers/mock_providers.py`
3. Add real implementation in `providers/real_providers.py`
4. Add factory + singleton in `providers/__init__.py`

## Agent Pattern

Agents are deterministic rule-based classes — no LLM calls. They own business logic and coordinate between database and providers.

```python
class FrontDeskAgent:
    def __init__(self, db, shop: Shop):
        self.db = db
        self.shop = shop
        self.sms = get_sms()       # Provider via singleton
        self.calendar = get_calendar()
        self.payment = get_payment()

    async def process_inbound_message(
        self, client: Client, message_content: str
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        content = message_content.strip().upper()
        if content in ("HELP", "?", "COMMANDS"):
            return self._format_template(MessageTemplates.HELP_RESPONSE), {"action": "help"}
        # ... dispatch to handler methods
```

Key rules for agents:
- Constructor takes `db` and `shop: Shop`
- Providers accessed via `get_sms()`, `get_payment()`, etc.
- Return `Tuple[str, Dict]` — response message + action metadata
- Template-based responses via `MessageTemplates` class constants

## Factory Functions

Every service class has a companion factory function at module bottom:

```python
# audit.py
def create_audit_logger(db, shop_id: str) -> AuditLogger:
    return AuditLogger(db, shop_id)

# sms_compliance.py
def create_sms_service(db, shop_id: str, audit_logger: AuditLogger) -> SMSComplianceService:
    return SMSComplianceService(db, shop_id, audit_logger)
```

This keeps construction logic centralized and makes dependency wiring explicit.

## Non-Blocking Side Effects

Audit logging and revenue tracking must NEVER block main operations. Wrap in try/except and return a boolean:

```python
# GOOD — from revenue_logger.py
async def _log_event(self, source, amount, currency, **kwargs) -> bool:
    try:
        event = {"id": str(uuid.uuid4()), ...}
        await self.db.recovered_revenue_events.insert_one(event)
        return True
    except Exception as e:
        logger.error(f"[REVENUE] Failed to log {source.value} event: {e}")
        return False  # Never raises — caller continues normally
```

```python
# BAD — audit failure crashes the endpoint
async def _log_event(self, source, amount, currency, **kwargs):
    event = {"id": str(uuid.uuid4()), ...}
    await self.db.recovered_revenue_events.insert_one(event)  # Unhandled exception
```

## Datetime Handling

All timestamps are UTC ISO strings stored as strings in MongoDB, not datetime objects:

```python
# GOOD
from datetime import datetime, timezone

now = datetime.now(timezone.utc).isoformat()
await db.collection.update_one(
    {"id": doc_id},
    {"$set": {"updated_at": now}}
)

# Parsing ISO strings back
scheduled = datetime.fromisoformat(
    appointment["scheduled_at"].replace("Z", "+00:00")
)
```

### WARNING: Naive Datetimes

**The Problem:**
```python
# BAD — naive datetime, no timezone info
from datetime import datetime
now = datetime.now()
```

**Why This Breaks:**
1. MongoDB stores it without timezone, causing comparison bugs
2. `timedelta` math between naive and aware datetimes raises `TypeError`
3. Deployed servers in different timezones produce wrong results

**The Fix:**
```python
from datetime import datetime, timezone
now = datetime.now(timezone.utc)
```

Use the `utc_now()` helper from `models.py` for Pydantic defaults.

## Anti-Patterns

### WARNING: Mutable Default Arguments

```python
# BAD
def create_record(metadata: dict = {}):
    metadata["created"] = True  # Shared across all calls!
    return metadata
```

```python
# GOOD — use Field(default_factory=dict) in Pydantic, None in functions
def create_record(metadata: Optional[dict] = None):
    metadata = metadata or {}
    metadata["created"] = True
    return metadata
```

### WARNING: Bare Except Clauses

```python
# BAD — catches KeyboardInterrupt, SystemExit
try:
    await db.collection.insert_one(doc)
except:
    pass
```

```python
# GOOD — catch specific exceptions
try:
    await db.collection.insert_one(doc)
except Exception as e:
    logger.error(f"Insert failed: {e}")
    return False
```

### WARNING: Using `is` for Value Comparison

```python
# BAD — identity check, not equality
if appointment["status"] is "confirmed":
    ...

# GOOD — use == for value comparison, is only for None/singletons
if appointment["status"] == AppointmentStatus.CONFIRMED.value:
    ...
```
