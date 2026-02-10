# Twilio Workflows Reference

## Contents
- Adding a New Outbound SMS Flow
- Handling New Inbound Commands
- Consent Management
- Reminder Job
- Testing SMS Without Twilio
- Enabling Real Twilio

## Adding a New Outbound SMS Flow

Copy this checklist and track progress:
- [ ] Step 1: Import `create_sms_service` and `create_audit_logger`
- [ ] Step 2: Create service instances with `db` and `shop_id`
- [ ] Step 3: Call `sms_service.send_sms(client_id, to_phone, message)`
- [ ] Step 4: Store outbound message in `messages` collection
- [ ] Step 5: Check rate limit before sending
- [ ] Step 6: Test with `simulate_sms.py --mode interactive`

```python
# Example: sending a waitlist offer
from sms_compliance import create_sms_service
from audit import create_audit_logger

audit = create_audit_logger(db, shop.id)
sms_service = create_sms_service(db, shop.id, audit)

# Check rate limit first
today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
count = await db.messages.count_documents({
    "shop_id": shop.id, "client_id": client_id,
    "direction": "outbound",
    "created_at": {"$gte": today_start.isoformat()}
})
if count < shop.max_messages_per_day:
    response = await sms_service.send_sms(
        client_id=client_id,
        to_phone=phone,
        message=MessageTemplates.WAITLIST_OFFER.format(...)
    )
    # Store the message — see the **mongodb** skill for insert patterns
    await db.messages.insert_one({
        "id": str(uuid.uuid4()),
        "shop_id": shop.id,
        "client_id": client_id,
        "direction": MessageDirection.OUTBOUND.value,
        "message_type": "sms",
        "content": message,
        "twilio_sid": response.message_id,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
```

## Handling New Inbound Commands

To add a new SMS command (e.g., "WAITLIST"):

1. Add keyword matching in `FrontDeskAgent.process_inbound_message()`:

```python
# backend/agents.py — inside process_inbound_message()
if content in ("WAITLIST", "WAIT"):
    return await self._handle_waitlist_request(client)
```

2. Implement the handler method:

```python
async def _handle_waitlist_request(self, client: Client) -> Tuple[str, Dict]:
    return (
        "You've been added to our waitlist. We'll text you when a slot opens!",
        {"action": "waitlist_added"}
    ), 
```

3. Add a message template in `MessageTemplates` if reusable.

Validation loop:
1. Add the command handler
2. Run: `python scripts/simulate_sms.py --mode interactive`
3. Send the new command keyword
4. If response is wrong, fix handler and repeat step 2
5. Only proceed when correct response is returned

## Consent Management

Three consent sources tracked in `client.sms_consent_source`:

| Source | When | Auto-grants |
|--------|------|-------------|
| `inbound_sms` | Client texts the shop first | Yes |
| `web_form` | Client submits `POST /api/public/sms-consent` | Depends on `consent` field |
| `opt_out_stop` | Client sends STOP/UNSUBSCRIBE/CANCEL | Revokes consent |

### Granting consent programmatically:

```python
# Via SMSComplianceService
await sms_service.grant_consent(client_id=cid, source="web_form")
```

### Processing opt-out:

```python
# Handled automatically in webhook when is_opt_out_message() returns True
if is_opt_out_message(body):
    await sms_service.process_opt_out(client.id, from_number)
    # Sets sms_consent=False, sends one final confirmation, logs to audit
```

### WARNING: Sending After Opt-Out

**The Problem:** The compliance service blocks sends to opted-out clients, but if you query `sms_consent` separately and cache the result, it may be stale.

**The Fix:** NEVER cache consent status. Always let `SMSComplianceService.check_consent()` query the database on each send.

## Reminder Job

The `AppointmentReminderJob` in `backend/scheduled_jobs.py` sends reminders for appointments within the `confirmation_window_hours` window:

```python
# Run for all shops
from scheduled_jobs import run_reminder_job_for_all_shops
results = await run_reminder_job_for_all_shops(db)

# Or standalone via cron
python backend/scheduled_jobs.py
```

The job:
1. Finds CONFIRMED/DEPOSIT_PAID appointments within the reminder window
2. Filters out appointments that already have a reminder message (checks `messages` collection)
3. Sends via `SMSComplianceService` (consent enforced automatically)
4. Stores outbound message record

## Testing SMS Without Twilio

The simulation script sends HTTP POST to the webhook endpoint with Twilio-format form data:

```python
# scripts/simulate_sms.py — what happens under the hood
form_data = {
    "From": "+15559999999",
    "To": "+15551234567",    # Must match a shop's phone number in DB
    "Body": "BOOK",
    "MessageSid": f"SM{datetime.now().strftime('%Y%m%d%H%M%S')}",
    "AccountSid": "SIMULATION",
    "NumMedia": "0"
}
requests.post(f"{BASE_URL}/api/webhooks/twilio/inbound", data=form_data)
```

The backend doesn't validate the webhook signature in mock mode, so this works without credentials.

## Enabling Real Twilio

Copy this checklist and track progress:
- [ ] Step 1: Set `TWILIO_ENABLED=true`
- [ ] Step 2: Set `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN`
- [ ] Step 3: Set `TWILIO_PHONE_NUMBER` (E.164 format: `+1XXXXXXXXXX`)
- [ ] Step 4: Configure Twilio webhook URL to `https://yourdomain.com/api/webhooks/twilio/inbound`
- [ ] Step 5: Send a test SMS via `POST /api/sms/send-test` (requires auth)
- [ ] Step 6: Verify message appears in Twilio console
- [ ] Step 7: Check `integration_audit_log` collection for audit trail

```bash
# Environment variables needed
export TWILIO_ENABLED=true
export TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
export TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
export TWILIO_PHONE_NUMBER=+15551234567
```

### WARNING: Webhook Signature Validation Is Incomplete

The current `TwilioSMSProvider.validate_webhook()` always returns `True`. In production, validate signatures using Twilio's `RequestValidator`:

```python
# Proper validation requires the full URL and form params
from twilio.request_validator import RequestValidator

validator = RequestValidator(auth_token)
is_valid = validator.validate(
    uri=request.url,          # Full URL including https
    params=dict(form_data),   # All form parameters
    signature=request.headers.get("X-Twilio-Signature", "")
)
```

This is a known gap. See the **fastapi** skill for adding middleware-level validation.