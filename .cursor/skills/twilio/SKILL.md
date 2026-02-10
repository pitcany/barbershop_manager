---
name: twilio
description: |
  Implements Twilio SMS sending, inbound webhooks, and compliance handling for the Barbershop Autopilot backend.
  Use when: adding SMS features, modifying inbound webhook processing, updating opt-out/consent logic, configuring Twilio credentials, writing scheduled SMS jobs, or debugging SMS delivery
allowed-tools: Read, Edit, Write, Glob, Grep, Bash, mcp__web-search-prime__webSearchPrime
---

# Twilio Skill

This project uses Twilio behind a **provider abstraction** (`SMSProvider` interface) with mock-by-default behavior. SMS is gated by `TWILIO_ENABLED` env flag and three compliance layers: consent checking, opt-out (STOP) processing, and audit logging. All SMS flows route through `SMSComplianceService` — NEVER call the provider directly from business logic.

## Quick Start

### Sending SMS (Compliant Path)

```python
# ALWAYS use SMSComplianceService, never the raw provider
from sms_compliance import create_sms_service
from audit import create_audit_logger

audit = create_audit_logger(db, shop.id)
sms_service = create_sms_service(db, shop.id, audit)

response = await sms_service.send_sms(
    client_id=client.id,
    to_phone=client.phone,
    message="Your appointment is confirmed!"
)
```

### Processing Inbound SMS

```python
# Inbound webhook parses Twilio form data
form_data = await request.form()
from_number = form_data.get("From", "")
body = form_data.get("Body", "")
message_sid = form_data.get("MessageSid", "")
```

## Key Concepts

| Concept | Location | Detail |
|---------|----------|--------|
| Provider interface | `backend/providers/interfaces.py` | `SMSProvider` ABC with `send_sms()` and `validate_webhook()` |
| Mock provider | `backend/providers/mock_providers.py` | `MockSMSProvider` — logs to console, stores in memory |
| Real provider | `backend/providers/real_providers.py` | `TwilioSMSProvider` — wraps `twilio.rest.Client` |
| Provider factory | `backend/providers/__init__.py` | `get_sms()` singleton, selects based on `TWILIO_ENABLED` |
| Compliance service | `backend/sms_compliance.py` | Consent check, opt-out handling, audit logging |
| Inbound webhook | `backend/server.py:581` | `POST /api/webhooks/twilio/inbound` |
| Consent endpoint | `backend/server.py:737` | `POST /api/public/sms-consent` |
| Agent processing | `backend/agents.py` | `FrontDeskAgent.process_inbound_message()` |
| Audit logger | `backend/audit.py` | `log_sms_sent()`, `log_sms_blocked()`, `log_sms_opt_out()` |

## Common Patterns

### Provider Activation

```python
# Provider resolves based on env flags + credentials
# TWILIO_ENABLED=true + TWILIO_ACCOUNT_SID + TWILIO_AUTH_TOKEN → TwilioSMSProvider
# Otherwise → MockSMSProvider (always succeeds, logs to console)
```

### Consent-Gated Sending

All outbound SMS must pass through `SMSComplianceService.send_sms()` which checks `client.sms_consent` before sending. The only exception: `bypass_consent=True` for the opt-out confirmation message.

### Opt-Out Keywords

```python
OPT_OUT_KEYWORDS = {"STOP", "UNSUBSCRIBE", "CANCEL"}
# Checked case-insensitively against stripped message body
```

## Testing SMS Locally

```bash
# No Twilio credentials needed — mock provider handles everything
python scripts/simulate_sms.py --mode demo        # Scripted conversation
python scripts/simulate_sms.py --mode interactive  # Free-form testing
python scripts/simulate_sms.py --mode test         # All commands
```

## See Also

- [patterns](references/patterns.md) — Provider abstraction, compliance flow, message storage
- [workflows](references/workflows.md) — Webhook handling, reminder jobs, consent management

## Related Skills

- See the **fastapi** skill for endpoint patterns and auth middleware
- See the **mongodb** skill for message/client collection queries
- See the **stripe** skill for the parallel provider abstraction pattern (payments)