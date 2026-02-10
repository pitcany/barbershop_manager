# Python Modules Reference

## Contents
- Module Map
- Dependency Graph
- Module Details
- Adding New Modules

## Module Map

```
backend/
├── server.py              # FastAPI app, all routes, auth, startup seed
├── models.py              # Pydantic models, enums, DTOs
├── agents.py              # FrontDeskAgent, NoShowEnforcementAgent, WaitlistFillAgent
├── sms_compliance.py      # SMS consent enforcement, opt-out handling
├── audit.py               # Integration audit logger
├── revenue_logger.py      # Revenue attribution tracking
├── scheduled_jobs.py      # Appointment reminder cron job
└── providers/
    ├── __init__.py        # Factory + singleton getters
    ├── interfaces.py      # ABC interfaces + Pydantic I/O types
    ├── mock_providers.py  # In-memory mocks for local dev
    └── real_providers.py  # Twilio, Stripe, SendGrid, Google Calendar
```

## Dependency Graph

```
server.py
├── models.py (all models, enums, DTOs)
├── providers/__init__.py (get_sms, get_email, get_payment, get_calendar)
├── providers/interfaces.py (SMSMessage, EmailMessage)
├── agents.py (FrontDeskAgent, NoShowEnforcementAgent, WaitlistFillAgent)
├── audit.py (create_audit_logger)
├── sms_compliance.py (SMSComplianceService, create_sms_service)
└── revenue_logger.py (create_revenue_logger, hook functions)

agents.py
├── models.py
├── providers/__init__.py
└── providers/interfaces.py

sms_compliance.py
├── providers/__init__.py
├── providers/interfaces.py
└── audit.py

scheduled_jobs.py
├── models.py
├── audit.py
└── sms_compliance.py
```

**Rule:** No circular imports. `models.py` and `providers/interfaces.py` are leaf modules — they import nothing from the project.

## Module Details

### server.py (~1200 lines)

The monolith. Contains all FastAPI routes, auth utilities, CORS, and startup seed logic. See the **fastapi** skill for route patterns.

Key exports used by other modules: none (it's the entry point).

Key imports from other modules:
```python
from models import Shop, Client, Appointment, ...
from providers import get_sms, get_email, get_payment, get_calendar
from agents import FrontDeskAgent, NoShowEnforcementAgent, WaitlistFillAgent
from audit import create_audit_logger
from sms_compliance import SMSComplianceService, create_sms_service
from revenue_logger import create_revenue_logger, log_no_show_fee_on_payment_success
```

### models.py

Pure data definitions. No business logic, no database access.

- `generate_id()` / `utc_now()` — utility functions used across all models
- Entity models: `Shop`, `Barber`, `Service`, `Client`, `Appointment`, `Message`, `Waitlist`, `Payment`, `Event`, `EmailOutbox`, `AdminUser`
- Enums: `AppointmentStatus`, `MessageDirection`, `MessageType`, `PaymentStatus`, `EventType`, `AuditProvider`, `AuditAction`, `RevenueSource`
- Request DTOs: `LoginRequest`, `SMSConsentRequest`, `PolicyUpdate`, `SendTestSMSRequest`, `SendTestEmailRequest`
- Response DTOs: `TokenResponse`

### agents.py

Three deterministic agent classes:

| Agent | Responsibility | Key Method |
|-------|---------------|------------|
| `FrontDeskAgent` | Inbound SMS dispatch | `process_inbound_message()` |
| `NoShowEnforcementAgent` | Deposit logic, no-show tracking | `check_deposit_requirement()`, `process_no_show()` |
| `WaitlistFillAgent` | Match cancellations to waitlist | `find_waitlist_matches()`, `process_cancellation()` |

Also contains `MessageTemplates` — a class of string constants for SMS responses.

### sms_compliance.py

`SMSComplianceService` wraps SMS sending with consent checks. See the **twilio** skill for Twilio-specific details.

Key methods:
- `check_consent(client_id)` — returns `(bool, Optional[str])`
- `send_sms(client_id, to_phone, message, bypass_consent=False)` — consent-checked send
- `process_opt_out(client_id, phone)` — handles STOP keyword
- `grant_consent(client_id, source)` — records consent

### audit.py

`AuditLogger` logs all external integration attempts to `integration_audit_log` collection. Specialized methods for each provider:

```python
audit = create_audit_logger(db, shop_id)
await audit.log_sms_sent(client_id, to_phone, message_preview, success)
await audit.log_sms_blocked(client_id, to_phone, reason)
await audit.log_payment_attempt(client_id, appointment_id, amount, success)
await audit.log_calendar_event(action, appointment_id, calendar_id)
await audit.log_email_sent(to_email, subject, success)
```

### revenue_logger.py

`RecoveredRevenueLogger` tracks revenue attribution events. Two hook functions allow server.py to log revenue without modifying agent code:

```python
# Called from Stripe webhook handler
await log_no_show_fee_on_payment_success(db, payment_record, appointment_record)

# Called when waitlist fill succeeds
await log_waitlist_fill_on_booking_success(db, shop_id, new_apt, cancelled_apt, price)
```

### providers/

**interfaces.py** — ABCs + Pydantic types. Leaf module, no project imports.

**mock_providers.py** — In-memory implementations with `sent_messages`/`sessions` lists for inspection.

**__init__.py** — Factory functions (`get_sms_provider()`) and lazy singletons (`get_sms()`). Environment-based selection: checks `TWILIO_ENABLED`, `STRIPE_API_KEY`, etc.

`reset_providers()` clears all singletons — use in tests.

## Adding New Modules

Copy this checklist:
- [ ] Create `backend/new_module.py`
- [ ] Import models from `models.py` (add new models there if needed)
- [ ] Add factory function at module bottom: `def create_my_service(db, shop_id) -> MyService`
- [ ] Import and wire in `server.py`
- [ ] If it's a new provider: add interface to `interfaces.py`, mock to `mock_providers.py`, real to `real_providers.py`, factory+singleton to `__init__.py`
- [ ] Logging failures must never block main operations

Validation:
1. Run `python -c "from new_module import *"` to check imports
2. Run `python -m pytest` to verify no circular imports
3. If validation fails, check the dependency graph above for cycles
