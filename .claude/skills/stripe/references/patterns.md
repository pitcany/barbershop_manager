# Stripe Patterns Reference

## Contents
- Provider Abstraction Pattern
- Payment Record Lifecycle
- Deposit Enforcement Logic
- Audit Logging for Payments
- Revenue Attribution
- Anti-Patterns

---

## Provider Abstraction Pattern

All Stripe access goes through the `PaymentProvider` ABC. NEVER import `stripe` directly in business logic.

```python
# GOOD — Use the provider interface
from providers import get_payment

payment = get_payment()
link = await payment.create_payment_link(
    amount=20.0, currency="usd",
    success_url=success, cancel_url=cancel,
    metadata={"appointment_id": apt_id, "client_id": cid, "type": "deposit"}
)
```

```python
# BAD — Direct Stripe SDK usage bypasses mock/audit
import stripe
stripe.checkout.Session.create(...)  # Breaks local dev, skips audit
```

**Why:** The factory in `backend/providers/__init__.py` returns `MockPaymentProvider` when `STRIPE_API_KEY` is absent. Direct SDK calls bypass this, breaking local dev and skipping audit logging.

### Provider Selection Logic

```python
# backend/providers/__init__.py:73-82
def get_payment_provider(webhook_url: str = "") -> PaymentProvider:
    stripe_key = os.environ.get("STRIPE_API_KEY") or os.environ.get("STRIPE_SECRET_KEY")
    if stripe_key:
        return StripePaymentProvider(webhook_url)
    return MockPaymentProvider()
```

Unlike Twilio (`TWILIO_ENABLED` flag), Stripe activates purely on key presence. No explicit enable flag.

---

## Payment Record Lifecycle

Every payment link creates a `payments` collection document. The record tracks the full lifecycle:

```python
# 1. Created by NoShowEnforcementAgent.create_deposit_request()
{
    "id": "uuid",
    "shop_id": "shop_uuid",
    "client_id": "client_uuid",
    "appointment_id": "apt_uuid",
    "amount": 20.0,
    "currency": "usd",
    "stripe_session_id": "mock_session_xxx",  # or "cs_xxx" in prod
    "status": "pending",
    "payment_type": "deposit",  # or "no_show_fee", "full_payment"
    "created_at": "2025-01-15T10:00:00+00:00",
    "updated_at": "2025-01-15T10:00:00+00:00"
}

# 2. Updated on webhook success (server.py:707-713)
{"status": "completed", "updated_at": "..."}

# 3. Or on webhook failure (server.py:724-730)
{"status": "failed", "updated_at": "..."}
```

### Matching Webhook to Payment

Webhooks match via `stripe_session_id`:

```python
payment_record = await db.payments.find_one(
    {"stripe_session_id": result["session_id"]},
    {"_id": 0}
)
```

### WARNING: Missing Webhook Signature Verification

**The Problem:**

```python
# backend/providers/real_providers.py:152-166
async def handle_webhook(self, request_body: bytes, signature: str) -> Dict[str, Any]:
    # Current implementation just acknowledges — no signature verification
    return {"event_type": "webhook_received", "status": "acknowledged"}
```

**Why This Breaks:** Without `stripe.Webhook.construct_event()`, anyone can forge webhook payloads. This is acceptable for MVP with mock provider but MUST be fixed before production Stripe usage.

**The Fix:**

```python
async def handle_webhook(self, request_body: bytes, signature: str) -> Dict[str, Any]:
    import stripe
    endpoint_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    event = stripe.Webhook.construct_event(request_body, signature, endpoint_secret)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        return {
            "session_id": session["id"],
            "payment_status": session["payment_status"],
            "event_type": event["type"]
        }
    return {"event_type": event["type"], "status": "ignored"}
```

---

## Deposit Enforcement Logic

The `NoShowEnforcementAgent` in `backend/agents.py` decides when deposits are required:

```python
async def check_deposit_requirement(self, appointment: Dict, client: Dict) -> bool:
    scheduled = datetime.fromisoformat(appointment["scheduled_at"].replace("Z", "+00:00"))
    hours_until = (scheduled - datetime.now(timezone.utc)).total_seconds() / 3600

    # Rule 1: Booking close to appointment time
    if hours_until < self.shop.deposit_required_hours:  # Default 48h
        return True

    # Rule 2: Client has previous no-shows
    if client.get("no_shows", 0) > 0:
        return True

    return False
```

Deposit amount comes from `Shop.deposit_amount` (default `$20`), configurable via `PATCH /api/shop/policy`. See the **fastapi** skill for policy update patterns.

### Appointment Status Transitions for Deposits

```
PENDING -> DEPOSIT_PENDING  (deposit required, link sent)
DEPOSIT_PENDING -> DEPOSIT_PAID  (payment completed)
DEPOSIT_PAID -> CONFIRMED  (client confirms via SMS)
```

---

## Audit Logging for Payments

Every payment attempt is logged to `integration_audit_log`. See the **mongodb** skill for collection details.

```python
from audit import create_audit_logger

audit = create_audit_logger(db, shop.id)
await audit.log_payment_attempt(
    client_id=client["id"],
    appointment_id=apt_id,
    amount=20.0,
    success=True,
    session_id=link.session_id
)
```

Audit logging is non-blocking — failures are caught and logged but never raise exceptions or block the payment flow.

---

## Revenue Attribution

Payment success triggers revenue logging via hooks in `backend/revenue_logger.py`:

```python
# Called from both webhook and mock-payment handlers
await log_no_show_fee_on_payment_success(db, payment_record, appointment)
```

This only logs revenue for `payment_type` of `"no_show_fee"` or `"deposit"` (when appointment status is `"no_show"`). The logged events go to `recovered_revenue_events` collection — internal attribution only, never surfaced in UI.

---

## Anti-Patterns

### WARNING: Hardcoding Deposit Amounts

**The Problem:**

```python
# BAD — Amount hardcoded
link = await payment.create_payment_link(amount=20.0, ...)
```

**Why This Breaks:** Deposit amount is configurable per shop via `Shop.deposit_amount`. Hardcoding ignores admin policy changes made through `PATCH /api/shop/policy`.

**The Fix:**

```python
# GOOD — Use shop policy
link = await payment.create_payment_link(amount=shop.deposit_amount, ...)
```

### WARNING: Converting Dollars to Cents Before Provider

**The Problem:**

```python
# BAD — Double conversion
link = await payment.create_payment_link(amount=2000, ...)  # Already cents
```

**Why This Breaks:** The provider interface accepts dollars. The `StripePaymentProvider` converts internally via `emergentintegrations`. Passing cents results in a $2000 charge instead of $20.

**The Fix:**

```python
# GOOD — Always pass dollars
link = await payment.create_payment_link(amount=20.0, ...)
```

### WARNING: Blocking on Audit/Revenue Logging

**The Problem:**

```python
# BAD — Logging failure blocks payment flow
result = await audit.log_payment_attempt(...)
if not result:
    raise HTTPException(status_code=500, detail="Audit failed")
```

**Why This Breaks:** Audit and revenue logging are designed to be non-blocking. A MongoDB hiccup should never prevent a customer from paying.

**When You Might Be Tempted:** When adding compliance requirements. Instead, rely on the existing try/except in `AuditLogger.log()` and `RecoveredRevenueLogger._log_event()` which catch and log errors silently.
