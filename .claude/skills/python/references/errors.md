# Python Error Handling Reference

## Contents
- Error Handling Strategy
- Non-Blocking Pattern
- HTTP Exceptions
- Provider Error Handling
- Common Pitfalls
- Anti-Patterns

## Error Handling Strategy

This codebase uses two distinct error handling strategies:

1. **User-facing routes** — raise `HTTPException` for client errors, let FastAPI handle 500s. See the **fastapi** skill for route-level patterns.
2. **Side-effect services** (audit, revenue, compliance) — catch all exceptions, log, return `False`. Never block main operations.

## Non-Blocking Pattern

The most critical pattern in this codebase. Audit logging, revenue tracking, and compliance logging must NEVER prevent the primary business operation from completing.

```python
# From revenue_logger.py — canonical example
async def _log_event(self, source, amount, currency, **kwargs) -> bool:
    try:
        event = {
            "id": str(uuid.uuid4()),
            "shop_id": self.shop_id,
            "source": source.value,
            "amount": amount,
            "attributed_at": datetime.now(timezone.utc).isoformat(),
        }
        await self.db.recovered_revenue_events.insert_one(event)
        logger.info(f"[REVENUE] Logged {source.value}: ${amount:.2f}")
        return True
    except Exception as e:
        logger.error(f"[REVENUE] Failed to log {source.value} event: {e}")
        return False  # Caller continues normally
```

The hook functions in `revenue_logger.py` add a second layer of protection:

```python
async def log_no_show_fee_on_payment_success(db, payment_record, appointment_record) -> bool:
    try:
        # ... validation and logging
        return await revenue_logger.log_no_show_fee(...)
    except Exception as e:
        logger.error(f"[REVENUE] Hook error: {e}")
        return False  # Double-wrapped — main payment flow unaffected
```

### When to Use Non-Blocking

Use this pattern when:
- Logging/auditing external API calls (`audit.py`)
- Tracking revenue attribution (`revenue_logger.py`)
- Sending non-critical notifications
- Any side effect that is "nice to have" but not essential

Do NOT use this pattern when:
- Validating user input (should raise `HTTPException`)
- Core business logic (appointments, payments)
- Authentication/authorization checks

## HTTP Exceptions

Routes use FastAPI's `HTTPException` for client-visible errors:

```python
# Authentication
async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ")[1]
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload

# Resource not found
async def get_shop(user: dict = Depends(get_current_user)) -> Shop:
    shop_data = await db.shops.find_one({"id": user.get("shop_id")}, {"_id": 0})
    if not shop_data:
        raise HTTPException(status_code=404, detail="Shop not found")
    return Shop(**shop_data)
```

Convention: use `detail` strings that are safe to show to end users. Never expose internal error messages, stack traces, or database details.

## Provider Error Handling

Provider calls wrap exceptions and return structured responses:

```python
# From sms_compliance.py
try:
    response = await self.sms_provider.send_sms(SMSMessage(to=to_phone, body=message))
    await self.audit.log_sms_sent(
        client_id=client_id, to_phone=to_phone,
        message_preview=message, success=response.success,
        message_id=response.message_id, error=response.error
    )
    return response
except Exception as e:
    error_msg = str(e)
    await self.audit.log_sms_sent(
        client_id=client_id, to_phone=to_phone,
        message_preview=message, success=False, error=error_msg
    )
    return SMSResponse(success=False, error=error_msg)
```

Pattern: always return a typed response object (`SMSResponse`, `EmailResponse`) even on failure. Callers check `.success` rather than catching exceptions.

## Common Pitfalls

### ISO String Parsing

MongoDB stores dates as ISO strings. When parsing back:

```python
# GOOD — handle both "Z" and "+00:00" suffixes
scheduled = datetime.fromisoformat(
    appointment["scheduled_at"].replace("Z", "+00:00")
)

# BAD — fromisoformat doesn't handle "Z" in Python < 3.11
scheduled = datetime.fromisoformat(appointment["scheduled_at"])  # May fail
```

### Missing Document Checks

Always check for `None` after `find_one`:

```python
# GOOD
appointment = await self.db.appointments.find_one(
    {"id": appointment_id}, {"_id": 0}
)
if not appointment:
    return  # Early return

# BAD — crashes with TypeError on None
appointment = await self.db.appointments.find_one(
    {"id": appointment_id}, {"_id": 0}
)
scheduled = appointment["scheduled_at"]  # KeyError if None
```

### Consent Bypass

The `bypass_consent` parameter in `SMSComplianceService.send_sms()` exists solely for opt-out confirmation messages. Never use it for general sends:

```python
# GOOD — only bypass for opt-out confirmation
await self.send_sms(
    client_id=client_id, to_phone=phone,
    message=OPT_OUT_CONFIRMATION,
    bypass_consent=True  # Legal requirement: confirm opt-out
)

# BAD — bypassing consent for regular messages
await self.send_sms(
    client_id=client_id, to_phone=phone,
    message="Your appointment is tomorrow!",
    bypass_consent=True  # Compliance violation
)
```

## Anti-Patterns

### WARNING: Swallowing Errors Without Logging

**The Problem:**

```python
# BAD — silent failure
try:
    await db.collection.insert_one(doc)
except Exception:
    pass
```

**Why This Breaks:**
You lose all visibility into failures. When MongoDB is down or a document is malformed, you'll have no idea why the system silently stopped working.

**The Fix:**

```python
try:
    await db.collection.insert_one(doc)
except Exception as e:
    logger.error(f"Failed to insert document: {e}")
    return False
```

### WARNING: Raising Exceptions in Audit/Logging Code

**The Problem:**

```python
# BAD — audit failure kills the main operation
async def log_sms_sent(self, **kwargs):
    log_entry = {...}
    await self.db.integration_audit_log.insert_one(log_entry)
    # If this raises, the SMS send appears to fail
```

**Why This Breaks:**
If the audit database write fails (network issue, disk full), the calling code's try/except catches it as a failed SMS send — even though the SMS was actually sent. The user sees an error for a successful operation.

**The Fix:**

```python
async def log_sms_sent(self, **kwargs):
    try:
        log_entry = {...}
        await self.db.integration_audit_log.insert_one(log_entry)
    except Exception as e:
        logger.error(f"Failed to write audit log: {e}")
        # Never raises — main operation continues
```

### WARNING: Catching Too Broadly in Business Logic

**The Problem:**

```python
# BAD — hides bugs in business logic
async def process_inbound_message(self, client, message):
    try:
        # 50 lines of complex logic
        return await self._handle_booking(client)
    except Exception:
        return "Something went wrong", {"action": "error"}
```

**Why This Breaks:**
A typo, wrong variable name, or logic error gets caught and silently converted to a generic "Something went wrong" message. You'll never find the bug.

**The Fix:**

Reserve broad exception handling for side effects only. Let business logic errors propagate so FastAPI returns a 500 with a traceback in dev mode.

```python
async def process_inbound_message(self, client, message):
    # No try/except — let errors surface
    content = message.strip().upper()
    if content in ("HELP", "?"):
        return self._format_template(MessageTemplates.HELP_RESPONSE), {"action": "help"}
    return await self._handle_booking(client)
```
