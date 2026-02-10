# SendGrid Workflows Reference

## Contents
- Enabling SendGrid for Production
- Testing Email in Mock Mode
- Adding a New Email Type
- Debugging Failed Sends
- Email Outbox Inspection

## Enabling SendGrid for Production

Copy this checklist and track progress:
- [ ] Step 1: Create a SendGrid account and generate an API key
- [ ] Step 2: Verify a sender identity (domain or single sender)
- [ ] Step 3: Set environment variables
- [ ] Step 4: Test with the built-in endpoint
- [ ] Step 5: Verify audit log entry

```bash
# Step 3: Set environment variables
export SEND_EMAILS=true
export SENDGRID_API_KEY=SG.your_api_key_here
export SENDER_EMAIL=noreply@yourdomain.com
```

```bash
# Step 4: Test with built-in endpoint
curl -X POST http://localhost:8001/api/email/send-test \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"to_email": "test@example.com", "subject": "Test", "message": "Hello"}'
```

```bash
# Step 5: Check audit log
curl http://localhost:8001/api/audit-log?provider=sendgrid \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

1. Set environment variables
2. Validate: `curl -X POST .../api/email/send-test` returns `{"message": "Test email sent"}`
3. If it returns `400` with "Email sending is disabled", check `SEND_EMAILS` is set
4. If it returns `500`, check `SENDGRID_API_KEY` and sender verification
5. Only proceed when test email arrives in inbox

## Testing Email in Mock Mode

When `SEND_EMAILS` is not set (default), the `MockEmailProvider` stores emails in the `email_outbox` MongoDB collection.

```bash
# List stored mock emails
curl http://localhost:8001/api/email-outbox \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

Response:
```json
{
  "emails": [
    {
      "id": "mock_email_abc123",
      "shop_id": "demo_shop",
      "to_email": "client@example.com",
      "from_email": "noreply@barbershop.local",
      "subject": "Appointment Confirmation",
      "html_content": "<h1>Confirmed</h1>",
      "sent": false,
      "created_at": "2026-02-10T12:00:00+00:00"
    }
  ]
}
```

The `sent` field is always `false` in mock mode — emails are stored but never delivered.

### WARNING: Mock Provider Without DB

```python
# BAD — MockEmailProvider without db silently drops outbox storage
email_provider = MockEmailProvider()  # no db argument

# GOOD — always pass db for outbox persistence
email_provider = MockEmailProvider(db)
```

The factory `get_email_provider(db)` handles this correctly. Only a problem if instantiating manually.

## Adding a New Email Type

Follow this pattern to add a new transactional email (e.g., appointment reminder):

```python
# 1. Create the email content builder (in server.py or a new module)
def build_reminder_email(shop: Shop, client_name: str, appointment_time: str) -> EmailMessage:
    return EmailMessage(
        to=client.email,
        subject=f"Reminder: Appointment at {shop.name}",
        html_content=f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background-color: #D4AF37; padding: 20px; text-align: center;">
                <h1 style="color: #000; margin: 0;">{shop.name}</h1>
            </div>
            <div style="padding: 30px; background-color: #18181b; color: #fafafa;">
                <p>Hi {client_name},</p>
                <p>This is a reminder for your appointment at
                   <strong style="color: #D4AF37;">{appointment_time}</strong>.</p>
            </div>
        </body>
        </html>
        """,
        plain_content=f"Hi {client_name}, reminder: appointment at {appointment_time}."
    )
```

```python
# 2. Send through the provider and audit
email_provider = get_email(db)
message = build_reminder_email(shop, client.name, "2pm Tomorrow")
response = await email_provider.send_email(message)

audit = create_audit_logger(db, shop.id)
await audit.log_email_sent(
    to_email=client.email,
    subject=message.subject,
    success=response.success,
    entity_type="appointment",
    entity_id=appointment.id,
    error=response.error
)
```

Copy this checklist and track progress:
- [ ] Step 1: Build the `EmailMessage` with both HTML and plain text
- [ ] Step 2: Use brand colors (`#D4AF37` gold, `#18181b` dark bg, `#fafafa` text)
- [ ] Step 3: Send via `get_email(db).send_email()`
- [ ] Step 4: Audit log with `audit.log_email_sent()`
- [ ] Step 5: Test in mock mode via `/api/email-outbox`
- [ ] Step 6: Test with real SendGrid via `/api/email/send-test`

## Debugging Failed Sends

Common failure scenarios and their solutions:

| Symptom | Cause | Fix |
|---------|-------|-----|
| `400: Email sending is disabled` | `SEND_EMAILS` not set | Set `SEND_EMAILS=true` |
| `500: SendGrid not configured` | API key missing or library not installed | Set `SENDGRID_API_KEY`, run `pip install sendgrid` |
| `403 Forbidden` from SendGrid | Sender identity not verified | Verify sender in SendGrid dashboard |
| `401 Unauthorized` from SendGrid | Invalid API key | Regenerate key in SendGrid dashboard |
| Emails in outbox but `sent: false` | Mock mode active (expected behavior) | Set `SEND_EMAILS=true` for real delivery |

Check the audit log for SendGrid-specific errors:

```bash
curl "http://localhost:8001/api/audit-log?provider=sendgrid" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

Look for entries where `success: false` — the `error_message` field contains the SendGrid error.

## Email Outbox Inspection

The `email_outbox` collection stores all emails when in mock mode. Useful for:
- Verifying email content during development
- Integration testing without SendGrid credentials
- Debugging template rendering

```python
# Direct MongoDB query (e.g., in a test or script)
emails = await db.email_outbox.find(
    {"shop_id": shop.id},
    {"_id": 0}
).sort("created_at", -1).limit(50).to_list(50)
```

The `EmailOutbox` Pydantic model at `backend/models.py:275` defines the schema. See the **pydantic** skill for model conventions.

The outbox endpoint at `GET /api/email-outbox` is auth-protected and returns the 50 most recent emails. See the **fastapi** skill for endpoint patterns.