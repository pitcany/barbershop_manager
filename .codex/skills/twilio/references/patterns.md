# Twilio Patterns Reference

## Contents
- Provider Abstraction Pattern
- Compliance Service Pattern
- Message Storage Pattern
- Inbound Webhook Pattern
- Anti-Patterns

## Provider Abstraction Pattern

All SMS flows use the `SMSProvider` interface. The factory selects mock or real based on environment:

```python
# backend/providers/__init__.py
def get_sms_provider() -> SMSProvider:
    twilio_enabled = _is_true(os.environ.get("TWILIO_ENABLED"))
    if twilio_enabled:
        account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
        if account_sid and auth_token:
            return TwilioSMSProvider()
        else:
            logger.warning("TWILIO_ENABLED=true but credentials missing, falling back to mock")
    return MockSMSProvider()
```

The singleton `get_sms()` caches the provider instance. Use `reset_providers()` in tests.

```python
# In tests, reset to get fresh mock
from providers import reset_providers
reset_providers()
```

## Compliance Service Pattern

`SMSComplianceService` wraps the raw provider with three enforcement layers:

```python
# 1. Consent check — blocks if client.sms_consent is False
has_consent, reason = await self.check_consent(client_id)

# 2. Twilio enabled check — returns mock success if TWILIO_ENABLED=false
if not is_twilio_enabled():
    return SMSResponse(success=True, message_id=f"mock_disabled_{...}")

# 3. Actual send with audit logging on success AND failure
response = await self.sms_provider.send_sms(SMSMessage(to=to_phone, body=message))
await self.audit.log_sms_sent(client_id, to_phone, message, response.success, ...)
```

### WARNING: Bypassing SMSComplianceService

**The Problem:**

```python
# BAD — skips consent check, skips audit logging
sms = get_sms()
await sms.send_sms(SMSMessage(to=phone, body="Hello"))
```

**Why This Breaks:**
1. Sends to clients who opted out (TCPA violation risk)
2. No audit trail for compliance reviews
3. No rate limiting enforcement

**The Fix:**

```python
# GOOD — always route through compliance service
sms_service = create_sms_service(db, shop.id, audit_logger)
await sms_service.send_sms(client_id=cid, to_phone=phone, message="Hello")
```

**When You Might Be Tempted:** System notifications, test messages, admin alerts. Even these should go through the compliance service — use `bypass_consent=True` only for opt-out confirmations.

## Message Storage Pattern

Both inbound and outbound messages are stored in the `messages` collection:

```python
await db.messages.insert_one({
    "id": str(uuid.uuid4()),
    "shop_id": shop.id,
    "client_id": client.id,
    "direction": MessageDirection.OUTBOUND.value,  # or INBOUND
    "message_type": "sms",
    "content": response_text,
    "twilio_sid": sms_response.message_id,  # mock_sms_* or real Twilio SID
    "created_at": datetime.now(timezone.utc).isoformat()
})
```

Messages use `{"_id": 0}` projection in queries. The `twilio_sid` field stores either a real Twilio SID (`SM...`) or a mock ID (`mock_sms_...`).

## Inbound Webhook Pattern

The `POST /api/webhooks/twilio/inbound` endpoint follows this flow:

1. Parse Twilio form data (`From`, `To`, `Body`, `MessageSid`)
2. Look up shop by `To` phone number
3. Find or create client (inbound SMS grants implied consent)
4. Store inbound message
5. Check for STOP/opt-out keywords
6. Process through `FrontDeskAgent`
7. Check daily rate limit (`shop.max_messages_per_day`)
8. Send response via `SMSComplianceService`
9. Store outbound message

### WARNING: Missing Rate Limit on New Flows

**The Problem:**

```python
# BAD — sends response without checking rate limit
response_text = await process_something(client)
await sms_service.send_sms(client_id=client.id, to_phone=phone, message=response_text)
```

**Why This Breaks:**
1. Clients could trigger unlimited outbound messages
2. Twilio costs spiral on abuse or loops

**The Fix:**

```python
# GOOD — check outbound count before sending
today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
outbound_count = await db.messages.count_documents({
    "shop_id": shop.id,
    "client_id": client.id,
    "direction": MessageDirection.OUTBOUND.value,
    "created_at": {"$gte": today_start.isoformat()}
})
if outbound_count >= shop.max_messages_per_day:
    return  # Rate limited
```

## Anti-Patterns

### WARNING: Synchronous Twilio Client in Async Context

**The Problem:**

```python
# The TwilioSMSProvider uses synchronous twilio-python client
# inside an async method — this blocks the event loop
msg = self.client.messages.create(body=..., from_=..., to=...)
```

**Why This Breaks:**
1. `twilio.rest.Client.messages.create()` is synchronous HTTP
2. Blocks the FastAPI event loop during the HTTP call
3. All other requests stall until Twilio responds

**The Fix:**

```python
# Use asyncio.to_thread for sync Twilio calls
import asyncio

async def send_sms(self, message: SMSMessage) -> SMSResponse:
    msg = await asyncio.to_thread(
        self.client.messages.create,
        body=message.body,
        from_=message.from_ or self.from_number,
        to=message.to
    )
    return SMSResponse(success=True, message_id=msg.sid)
```

**When You Might Be Tempted:** The current codebase does this. If Twilio is enabled in production, wrap all `self.client.*` calls with `asyncio.to_thread()`.