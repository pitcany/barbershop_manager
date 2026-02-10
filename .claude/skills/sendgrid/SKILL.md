---
name: sendgrid
description: |
  Configures SendGrid email delivery and outbox management for the Barbershop Autopilot backend.
  Use when: adding email features, modifying the email provider, working with the email outbox, configuring SEND_EMAILS, debugging email delivery, or writing email templates.
allowed-tools: Read, Edit, Write, Glob, Grep, Bash, mcp__web-search-prime__webSearchPrime
---

# SendGrid Skill

This project uses SendGrid 6.x behind a provider abstraction (`EmailProvider`). Email is **mock by default** — the `MockEmailProvider` stores emails in the `email_outbox` MongoDB collection instead of sending. Real SendGrid activates only when `SEND_EMAILS=true` AND `SENDGRID_API_KEY` is set. All email operations are audit-logged via `AuditProvider.SENDGRID`.

## Quick Start

### Environment Variables

```bash
# Enable real email delivery
SEND_EMAILS=true
SENDGRID_API_KEY=SG.your_key_here
SENDER_EMAIL=noreply@yourdomain.com  # defaults to noreply@barbershop-autopilot.com
```

### Sending an Email via the Provider

```python
from providers import get_email
from providers.interfaces import EmailMessage

email_provider = get_email(db)
response = await email_provider.send_email(EmailMessage(
    to="client@example.com",
    subject="Appointment Confirmation",
    html_content="<h1>Confirmed!</h1><p>See you at 2pm.</p>",
    plain_content="Confirmed! See you at 2pm."
))

if not response.success:
    logger.error(f"Email failed: {response.error}")
```

### Audit Logging Email Sends

```python
from audit import create_audit_logger

audit = create_audit_logger(db, shop.id)
await audit.log_email_sent(
    to_email="client@example.com",
    subject="Appointment Confirmation",
    success=response.success,
    entity_type="appointment",
    entity_id=appointment_id,
    error=response.error
)
```

## Key Concepts

| Concept | Location | Details |
|---------|----------|---------|
| `EmailProvider` interface | `backend/providers/interfaces.py:105` | Abstract `send_email(EmailMessage) -> EmailResponse` |
| `SendGridEmailProvider` | `backend/providers/real_providers.py:169` | Real provider, checks `status_code == 202` for success |
| `MockEmailProvider` | `backend/providers/mock_providers.py:132` | Stores to `email_outbox` collection, accepts optional `db` |
| Provider factory | `backend/providers/__init__.py:56` | `get_email_provider(db)` — switches on `SEND_EMAILS` env var |
| Singleton accessor | `backend/providers/__init__.py:106` | `get_email(db)` — lazy singleton |
| `EmailOutbox` model | `backend/models.py:275` | Pydantic model for outbox records |
| Test endpoint | `backend/server.py:538` | `POST /api/email/send-test` — requires `SEND_EMAILS=true` |
| Outbox endpoint | `backend/server.py:906` | `GET /api/email-outbox` — lists mock-mode emails |
| Audit logging | `backend/audit.py:166` | `log_email_sent()` with `AuditProvider.SENDGRID` |

## Common Patterns

### HTML Email with Brand Styling

```python
html_content = f"""
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <div style="background-color: #D4AF37; padding: 20px; text-align: center;">
        <h1 style="color: #000; margin: 0;">Barbershop Autopilot</h1>
    </div>
    <div style="padding: 30px; background-color: #18181b; color: #fafafa;">
        <h2 style="color: #D4AF37;">{subject}</h2>
        <p>{body_text}</p>
        <hr style="border-color: #27272a; margin: 20px 0;">
        <p style="color: #a1a1aa; font-size: 12px;">
            Sent from {shop.name}
        </p>
    </div>
</body>
</html>
"""
```

### Checking Provider Status at Runtime

```python
# Health endpoint pattern (server.py:982)
"sendgrid_enabled": os.environ.get("SEND_EMAILS", "false").lower() in ("true", "1", "yes")
```

## See Also

- [patterns](references/patterns.md) — provider abstraction, mock/real switching, error handling
- [workflows](references/workflows.md) — enabling SendGrid, testing, adding new email types

## Related Skills

- See the **fastapi** skill for route patterns and the `get_shop` dependency
- See the **python** skill for async patterns and Pydantic models
- See the **pydantic** skill for the `EmailOutbox` and `EmailMessage` models
- See the **stripe** skill for a parallel provider abstraction pattern