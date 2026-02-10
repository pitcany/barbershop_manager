# Services Reference

## Contents
- Provider Abstraction
- Agent Architecture
- SMS Compliance Service
- Audit Logger
- Revenue Logger
- Factory Functions

## Provider Abstraction

All external services use an interface + mock/real pattern in `backend/providers/`:

```
providers/
├── __init__.py        # Factory + singleton getters
├── interfaces.py      # Abstract base classes
├── mock_providers.py  # In-memory mocks (default)
└── real_providers.py  # Twilio, Stripe, SendGrid, Google Calendar
```

### Getting a Provider

```python
from providers import get_sms, get_email, get_payment, get_calendar

sms = get_sms()          # MockSMSProvider unless TWILIO_ENABLED=true
payment = get_payment()   # MockPaymentProvider unless STRIPE_API_KEY set
email = get_email(db)     # MockEmailProvider unless SEND_EMAILS=true
calendar = get_calendar() # MockCalendarProvider unless GOOGLE_SERVICE_ACCOUNT_JSON set
```

Providers are **lazy singletons** — created on first call, cached in module globals. Use `reset_providers()` in tests.

### Provider Interface Example

```python
# providers/interfaces.py
class SMSProvider(ABC):
    @abstractmethod
    async def send_sms(self, message: SMSMessage) -> SMSResponse:
        pass

    @abstractmethod
    async def validate_webhook(self, request_body: bytes, signature: str) -> bool:
        pass
```

All provider methods are `async`. See the **stripe** skill for payment provider details, the **twilio** skill for SMS.

## Agent Architecture

Three deterministic agents in `backend/agents.py` — no LLM calls:

| Agent | Responsibility | Key Method |
|-------|---------------|------------|
| `FrontDeskAgent` | Inbound SMS command routing | `process_inbound_message(client, body)` |
| `NoShowEnforcementAgent` | Deposit logic, no-show tracking | `check_deposit_requirement()`, `process_no_show()` |
| `WaitlistFillAgent` | Match cancelled slots to waitlist | `find_waitlist_matches()`, `offer_slot_to_waitlist()` |

### Agent Instantiation Pattern

Agents receive `db` and `shop` — they fetch their own providers internally:

```python
agent = FrontDeskAgent(db, shop)
response_text, metadata = await agent.process_inbound_message(client, body)
```

### WARNING: Adding Provider State to Agents

**The Problem:** Agents call `get_sms()` etc. in `__init__`. If providers change at runtime (e.g., tests calling `reset_providers()`), stale references cause bugs.

**The Fix:** This is the existing design. If you need dynamic providers, call getter functions in methods, not `__init__`.

## SMS Compliance Service

`backend/sms_compliance.py` wraps SMS sending with consent enforcement:

```python
audit_logger = create_audit_logger(db, shop.id)
sms_service = create_sms_service(db, shop.id, audit_logger)

# Consent is checked automatically
response = await sms_service.send_sms(
    client_id=client.id,
    to_phone=from_number,
    message=response_text
)
```

NEVER send SMS directly via `get_sms().send_sms()` in route handlers. Always use `SMSComplianceService` which:
1. Checks client consent before sending
2. Audits every attempt (sent, blocked, failed)
3. Handles opt-out processing (STOP keyword)

## Audit Logger

`backend/audit.py` logs all external API calls. Failures never block operations:

```python
audit_logger = create_audit_logger(db, shop.id)
await audit_logger.log_sms_sent(
    client_id=client_id,
    to_phone=phone,
    message_preview=message,
    success=True,
    message_id=response.message_id
)
```

### WARNING: Blocking on Audit Failures

The audit logger wraps all DB writes in try/except. If you add new audit methods, maintain this pattern:

```python
try:
    await self.db.integration_audit_log.insert_one(log_entry)
except Exception as e:
    logger.error(f"Failed to write audit log: {e}")
    # NEVER re-raise — audit failures must not break business logic
```

## Revenue Logger

`backend/revenue_logger.py` — internal attribution tracking for recovered revenue. Same non-blocking pattern as audit:

```python
# Called from payment success handlers in server.py
await log_no_show_fee_on_payment_success(db, payment_record, appointment)
await log_waitlist_fill_on_booking_success(db, shop_id, new_apt, cancelled_apt, price)
```

These are hook functions called from `server.py` webhook/payment handlers — they don't modify agent logic.

## Factory Functions

This codebase uses factory functions rather than dependency injection containers:

```python
# Pattern used throughout
def create_audit_logger(db, shop_id: str) -> AuditLogger:
    return AuditLogger(db, shop_id)

def create_sms_service(db, shop_id: str, audit_logger: AuditLogger) -> SMSComplianceService:
    return SMSComplianceService(db, shop_id, audit_logger)
```

Factories are simple constructors. No DI framework.