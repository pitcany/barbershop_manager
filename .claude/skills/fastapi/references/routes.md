# Routes Reference

## Contents
- Route Organization
- Naming Conventions
- Parameter Patterns
- Pagination and Filtering
- Webhook Endpoints
- Anti-Patterns

## Route Organization

All routes live in `backend/server.py` on a single `APIRouter`:

```python
api_router = APIRouter(prefix="/api")
# ... all routes defined on api_router ...
app.include_router(api_router)
```

Route groups are separated by comment headers:

| Group | Auth | Prefix |
|-------|------|--------|
| Auth | None | `/api/auth/` |
| Dashboard | JWT | `/api/dashboard/` |
| Resources | JWT | `/api/appointments`, `/api/clients`, etc. |
| Webhooks | Signature | `/api/webhooks/` |
| Public | None | `/api/public/` |
| Internal/Debug | JWT | `/api/internal/`, `/api/mock-payment` |

## Naming Conventions

Routes use **kebab-case** for multi-word paths:

```python
# GOOD
@api_router.get("/audit-log")
@api_router.post("/sms-consent")
@api_router.get("/email-outbox")
@api_router.get("/revenue-chart")

# BAD — never use snake_case or camelCase in URLs
@api_router.get("/audit_log")      # Wrong
@api_router.get("/auditLog")       # Wrong
```

## Parameter Patterns

### Path Parameters — Resource Identification

```python
@api_router.get("/appointments/{appointment_id}")
async def get_appointment(appointment_id: str, shop: Shop = Depends(get_shop)):
    appointment = await db.appointments.find_one(
        {"id": appointment_id, "shop_id": shop.id},  # Always scope to shop
        {"_id": 0}
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return appointment
```

### Query Parameters — Filtering and Pagination

```python
@api_router.get("/appointments")
async def list_appointments(
    shop: Shop = Depends(get_shop),
    status: Optional[str] = None,
    date: Optional[str] = None,
    limit: int = 50,
    skip: int = 0
):
    query = {"shop_id": shop.id}
    if status:
        query["status"] = status
    if date:
        query["scheduled_at"] = {"$gte": date, "$lt": f"{date}T23:59:59"}

    appointments = await db.appointments.find(
        query, {"_id": 0}
    ).sort("scheduled_at", -1).skip(skip).limit(limit).to_list(limit)

    total = await db.appointments.count_documents(query)
    return {"appointments": appointments, "total": total}
```

### Request Body — Pydantic Models

```python
@api_router.patch("/shop/policy")
async def update_shop_policy(update: PolicyUpdate, shop: Shop = Depends(get_shop)):
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.shops.update_one({"id": shop.id}, {"$set": update_data})
    return {"message": "Policy updated successfully"}
```

See the **pydantic** skill for model definitions.

## Webhook Endpoints

Webhooks use `Request` directly — no Pydantic body, no auth dependency:

```python
@api_router.post("/webhooks/twilio/inbound")
async def twilio_inbound_webhook(request: Request):
    form_data = await request.form()  # Twilio sends form data, not JSON
    from_number = form_data.get("From", "")
    body = form_data.get("Body", "")
    # ... process and return JSONResponse
    return JSONResponse(content={"status": "processed"})
```

Stripe sends raw bytes for signature verification:

```python
@api_router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    body = await request.body()  # Raw bytes for signature
    signature = request.headers.get("Stripe-Signature", "")
```

## Anti-Patterns

### WARNING: Forgetting Shop Scoping

**The Problem:**

```python
# BAD — returns data from ALL shops
@api_router.get("/clients")
async def list_clients(shop: Shop = Depends(get_shop)):
    clients = await db.clients.find({}, {"_id": 0}).to_list(50)
    return {"clients": clients}
```

**Why This Breaks:** Multi-tenant data leak. Every query MUST include `shop_id`.

**The Fix:**

```python
# GOOD — scoped to authenticated shop
clients = await db.clients.find(
    {"shop_id": shop.id}, {"_id": 0}
).to_list(50)
```

### WARNING: Using Depends(get_shop) on Webhook Routes

Webhook endpoints authenticate via provider signatures (Twilio, Stripe), not JWT. Adding `Depends(get_shop)` would reject all webhook calls since they carry no Bearer token.

### WARNING: Returning `_id` from MongoDB

Every query must include `{"_id": 0}` in the projection. The frontend expects clean JSON without ObjectId fields.