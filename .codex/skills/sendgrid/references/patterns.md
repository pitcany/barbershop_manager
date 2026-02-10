# SendGrid Patterns Reference

## Contents
- Provider Abstraction
- Mock vs Real Switching
- EmailMessage Construction
- Success Detection
- Audit Integration
- Anti-Patterns

## Provider Abstraction

All email goes through `EmailProvider`, never directly through the SendGrid client. This is the same pattern used for Twilio, Stripe, and Google Calendar.

```python
# backend/providers/interfaces.py — the contract
class EmailProvider(ABC):
    @abstractmethod
    async def send_email(self, message: EmailMessage) -> EmailResponse:
        pass
```

```python
# GOOD — use the provider factory
from providers import get_email
email_provider = get_email(db)
response = await email_provider.send_email(message)
```

```python
# BAD — importing SendGrid directly bypasses mock mode and audit logging
from sendgrid import SendGridAPIClient
client = SendGridAPIClient(os.environ.get("SENDGRID_API_KEY"))
```

## Mock vs Real Switching

The factory in `backend/providers/__init__.py:56` controls which implementation runs:

```python
def get_email_provider(db=None) -> EmailProvider:
    send_emails = _is_true(os.environ.get("SEND_EMAILS"))
    if send_emails:
        api_key = os.environ.get("SENDGRID_API_KEY")
        if api_key:
            return SendGridEmailProvider()
        else:
            logger.warning("SEND_EMAILS=true but SENDGRID_API_KEY missing, falling back to mock")
    return MockEmailProvider(db)
```

Key behaviors:
- `SEND_EMAILS` unset or `false` → `MockEmailProvider` (stores to `email_outbox` collection)
- `SEND_EMAILS=true` + no API key → logs warning, falls back to mock
- `SEND_EMAILS=true` + `SENDGRID_API_KEY` set → `SendGridEmailProvider`

The mock provider accepts an optional `db` parameter to persist emails to MongoDB. The real provider does not — it sends via the SendGrid API.

### WARNING: Singleton Initialization Order

The `get_email(db)` singleton caches the first provider created. If called before the database is available, `MockEmailProvider` gets `db=None` and silently skips outbox storage.

```python
# BAD — called before db is initialized
email_provider = get_email()  # db=None, outbox storage silently disabled

# GOOD — pass db when first initializing
email_provider = get_email(db)
```

## EmailMessage Construction

Always provide both `html_content` and `plain_content`. SendGrid delivers the HTML version to capable clients and falls back to plain text.

```python
from providers.interfaces import EmailMessage

message = EmailMessage(
    to="client@example.com",
    subject="Your Appointment",
    html_content="<h1>Confirmed</h1>",
    plain_content="Confirmed",          # ALWAYS include
    from_email="shop@domain.com"        # Optional — defaults to SENDER_EMAIL
)
```

### WARNING: Missing plain_content

**The Problem:**
```python
# BAD — no plain_content
EmailMessage(
    to="client@example.com",
    subject="Test",
    html_content="<h1>Hello</h1>"
)
```

**Why This Breaks:**
1. Some email clients (especially enterprise) render plain-text only
2. Spam filters penalize emails without a plain-text alternative
3. Accessibility screen readers prefer plain text

**The Fix:**
```python
# GOOD — always include plain text
EmailMessage(
    to="client@example.com",
    subject="Test",
    html_content="<h1>Hello</h1>",
    plain_content="Hello"
)
```

## Success Detection

SendGrid returns HTTP 202 (Accepted) for successful sends — not 200. The provider handles this:

```python
# backend/providers/real_providers.py:202-204
response = self.client.send(mail)
success = response.status_code == 202
```

The `EmailResponse` returned always has:
- `success: bool` — whether the send was accepted
- `message_id: Optional[str]` — from `X-Message-Id` header
- `error: Optional[str]` — error message on failure

```python
response = await email_provider.send_email(message)
if response.success:
    logger.info(f"Sent: {response.message_id}")
else:
    logger.error(f"Failed: {response.error}")
```

## Audit Integration

Every email send should be audit-logged. The audit logger uses `AuditProvider.SENDGRID` regardless of whether mock or real is active.

```python
from audit import create_audit_logger
from models import AuditProvider, AuditAction

audit = create_audit_logger(db, shop.id)

# Convenience method
await audit.log_email_sent(
    to_email="client@example.com",
    subject="Reminder",
    success=True,
    entity_type="appointment",
    entity_id="apt_123"
)

# Or use the generic method for custom actions
await audit.log(
    provider=AuditProvider.SENDGRID,
    action=AuditAction.SEND_EMAIL,
    entity_type="client",
    entity_id="client_456",
    success=False,
    error_message="Rate limit exceeded"
)
```

### WARNING: Audit Failures Must Never Block

Audit logging is non-blocking by design. The `AuditLogger.log()` method catches all exceptions internally. NEVER wrap email sending in a try/except that depends on audit success.

```python
# BAD — audit failure blocks email flow
try:
    await email_provider.send_email(message)
    await audit.log_email_sent(...)  # if this fails, the whole operation appears to fail
except Exception:
    raise HTTPException(500, "Failed")

# GOOD — send email, then audit independently
response = await email_provider.send_email(message)
await audit.log_email_sent(to_email=..., success=response.success, error=response.error)
# audit.log() handles its own exceptions internally
```

## Anti-Patterns

### WARNING: Synchronous SendGrid Client in Async Context

**The Problem:**
```python
# The SendGrid Python SDK's send() is synchronous
response = self.client.send(mail)  # blocks the event loop
```

**Why This Breaks:**
The current `SendGridEmailProvider.send_email()` is declared `async` but calls `self.client.send()` synchronously. At low volume this is acceptable, but under load it blocks the FastAPI event loop.

**The Fix (if email volume increases):**
```python
import asyncio

async def send_email(self, message: EmailMessage) -> EmailResponse:
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, self.client.send, mail)
```

**When You Might Be Tempted:**
When email volume is low (< 10/minute), the blocking call won't cause noticeable issues. If the system scales to bulk notifications, this becomes a bottleneck.