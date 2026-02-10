# Errors Reference

## Contents
- HTTPException Patterns
- Status Code Convention
- Non-Blocking Error Handling
- Webhook Error Responses
- Logging Patterns
- Anti-Patterns

## HTTPException Patterns

This codebase uses FastAPI's `HTTPException` directly — no custom exception classes:

### 401 Unauthorized — Auth Failures

```python
# In get_current_user (server.py:98-108)
if not authorization or not authorization.startswith("Bearer "):
    raise HTTPException(status_code=401, detail="Not authenticated")

payload = verify_token(token)
if not payload:
    raise HTTPException(status_code=401, detail="Invalid or expired token")

# In login
if not admin or not pwd_context.verify(request.password, admin["password_hash"]):
    raise HTTPException(status_code=401, detail="Invalid credentials")
```

### 404 Not Found — Missing Resources

```python
appointment = await db.appointments.find_one(
    {"id": appointment_id, "shop_id": shop.id}, {"_id": 0}
)
if not appointment:
    raise HTTPException(status_code=404, detail="Appointment not found")
```

Pattern: always check after query, always include the resource type in the detail message.

### 400 Bad Request — Invalid Input

```python
valid_statuses = [s.value for s in AppointmentStatus]
if status not in valid_statuses:
    raise HTTPException(
        status_code=400,
        detail=f"Invalid status. Must be one of: {valid_statuses}"
    )
```

### 400 for Disabled Features

```python
if not twilio_enabled:
    raise HTTPException(
        status_code=400,
        detail="SMS sending is disabled. Set TWILIO_ENABLED=true and configure credentials."
    )
```

### 500 for Provider Failures

```python
response = await sms.send_sms(SMSMessage(to=request.to_phone, body=request.message))
if not response.success:
    raise HTTPException(status_code=500, detail=response.error or "Failed to send SMS")
```

## Status Code Convention

| Code | When Used | Example |
|------|-----------|---------|
| 200 | Successful GET, PATCH, DELETE | Default for all success responses |
| 400 | Bad input, disabled feature | Invalid status, SMS disabled |
| 401 | Missing/invalid JWT | No Bearer header, expired token |
| 404 | Resource not found | Appointment, client, shop not found |
| 500 | External provider failure | Twilio/Stripe call failed |

## Non-Blocking Error Handling

Audit and revenue logging use try/except to NEVER block main operations:

```python
# audit.py — failures are swallowed
try:
    await self.db.integration_audit_log.insert_one(log_entry)
except Exception as e:
    logger.error(f"Failed to write audit log: {e}")
    # No re-raise — business logic continues

# revenue_logger.py — same pattern
try:
    await self.db.recovered_revenue_events.insert_one(event)
    return True
except Exception as e:
    logger.error(f"[REVENUE] Failed to log {source.value} event: {e}")
    return False  # Caller checks return value but doesn't fail
```

This is intentional. Side-effect logging should never degrade the user experience.

## Webhook Error Responses

Webhooks return `JSONResponse` with status info instead of raising HTTPException:

```python
# Stripe webhook — don't raise, return error status
if result.get("error"):
    logger.error(f"Stripe webhook error: {result['error']}")
    return JSONResponse(content={"status": "error"}, status_code=400)

# Twilio webhook — soft failures
if not shop_data:
    logger.warning(f"No shop found for number {to_number}")
    return JSONResponse(content={"status": "no_shop"})
```

Webhook providers retry on 5xx. Return 400 for permanent failures, 200 for "received but couldn't process" scenarios.

## Logging Patterns

```python
import logging
logger = logging.getLogger(__name__)

# Info for normal operations
logger.info(f"Inbound SMS from {from_number}: {body[:50]}...")

# Warning for non-critical issues
logger.warning(f"Rate limit reached for client {client.id}")
logger.warning(f"No shop found for number {to_number}")

# Error for failures
logger.error(f"Stripe webhook error: {result['error']}")
logger.error(f"Failed to write audit log: {e}")
```

## Anti-Patterns

### WARNING: Raising HTTPException in Non-Blocking Contexts

```python
# BAD — audit failure blocks the request
async def log_event(self, ...):
    await self.db.audit_log.insert_one(entry)  # Unhandled exception kills request

# GOOD — catch and log
async def log_event(self, ...):
    try:
        await self.db.audit_log.insert_one(entry)
    except Exception as e:
        logger.error(f"Audit log failed: {e}")
```

### WARNING: Generic Error Messages

```python
# BAD — useless to the caller
raise HTTPException(status_code=400, detail="Bad request")

# GOOD — tells caller what's wrong
raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
```

### WARNING: Leaking Internal Errors to Clients

```python
# BAD — exposes stack trace or internal details
except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))

# GOOD — generic message, log the details
except Exception as e:
    logger.error(f"Payment failed: {e}")
    raise HTTPException(status_code=500, detail="Payment processing failed")
```

### WARNING: Forgetting `modified_count` Check on Updates

```python
# BAD — silent failure if ID doesn't exist
await db.appointments.update_one({"id": apt_id}, {"$set": {"status": "cancelled"}})
return {"message": "Done"}

# GOOD — explicit 404 on miss
result = await db.appointments.update_one(
    {"id": apt_id, "shop_id": shop.id},
    {"$set": {"status": "cancelled", "updated_at": datetime.now(timezone.utc).isoformat()}}
)
if result.modified_count == 0:
    raise HTTPException(status_code=404, detail="Appointment not found")
```

## New Endpoint Checklist

Copy this checklist when adding a new endpoint:

- [ ] Route uses kebab-case path naming
- [ ] Auth: uses `Depends(get_shop)` for protected routes, none for public/webhooks
- [ ] All queries scoped with `shop_id` and `{"_id": 0}` projection
- [ ] HTTPException for all error paths with descriptive detail messages
- [ ] `modified_count` checked after updates
- [ ] Timestamps use `datetime.now(timezone.utc).isoformat()`
- [ ] IDs use `str(uuid.uuid4())`
- [ ] Side-effect logging (audit/revenue) wrapped in try/except