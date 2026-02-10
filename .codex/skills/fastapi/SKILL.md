---
name: fastapi
description: |
  Builds FastAPI endpoints, async handlers, JWT auth, and middleware for the Barbershop Autopilot backend.
  Use when: adding API routes, modifying auth, updating middleware/CORS, creating webhook handlers, or working with Depends() injection in backend/server.py
allowed-tools: Read, Edit, Write, Glob, Grep, Bash, mcp__plugin_context7-plugin_context7__resolve-library-id, mcp__plugin_context7-plugin_context7__query-docs
---

# FastAPI Skill

This project runs all FastAPI routes in a single file (`backend/server.py`, ~1200 lines) with an `APIRouter` prefixed at `/api`. There is no route module splitting. Auth uses manual JWT via PyJWT + passlib/bcrypt. Database access is direct Motor (async MongoDB) — no ORM. All external services go through a provider abstraction with mock defaults.

## Quick Start

### Adding an Authenticated Endpoint

```python
@api_router.get("/my-resource")
async def list_my_resource(shop: Shop = Depends(get_shop)):
    """get_shop chains: get_current_user -> verify JWT -> load shop"""
    items = await db.my_collection.find(
        {"shop_id": shop.id}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return {"items": items}
```

### Adding a Public Endpoint (No Auth)

```python
@api_router.get("/public/my-info")
async def get_public_info():
    """No Depends(get_shop) = no auth required"""
    data = await db.shops.find_one({}, {"_id": 0, "name": 1, "phone": 1})
    if not data:
        raise HTTPException(status_code=404, detail="Not found")
    return data
```

## Key Concepts

| Concept | Pattern | Location |
|---------|---------|----------|
| Auth dependency chain | `get_current_user` -> `get_shop` | `server.py:98-116` |
| Route prefix | `APIRouter(prefix="/api")` | `server.py:76` |
| ID generation | `str(uuid.uuid4())` — never ObjectId | All insert operations |
| Timestamps | ISO strings via `datetime.now(timezone.utc).isoformat()` | All documents |
| MongoDB projection | Always `{"_id": 0}` | All queries |
| CORS | Wildcard default, env-configurable | `server.py:997-1003` |
| Startup seed | `@app.on_event("startup")` seeds demo data if DB empty | `server.py:1008-1020` |

## Common Patterns

### Enriching Query Results (N+1 Pattern — Intentional in This Codebase)

```python
for apt in appointments:
    client = await db.clients.find_one({"id": apt["client_id"]}, {"_id": 0, "name": 1})
    apt["client"] = client
```

This is an accepted pattern here for simplicity. For high-traffic endpoints, use `$lookup` aggregation instead. See the **mongodb** skill.

### Webhook Handlers (No Auth, Raw Body)

```python
@api_router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("Stripe-Signature", "")
    result = await payment.handle_webhook(body, signature)
```

Webhooks skip `Depends(get_shop)` — they authenticate via signature verification.

## See Also

- [routes](references/routes.md) — Route structure, naming, parameters
- [services](references/services.md) — Provider abstraction, agents, compliance
- [database](references/database.md) — Motor queries, aggregations, projections
- [auth](references/auth.md) — JWT flow, dependency chain, token lifecycle
- [errors](references/errors.md) — HTTPException patterns, error handling

## Related Skills

- See the **pydantic** skill for model definitions and validation
- See the **mongodb** skill for query patterns and aggregation pipelines
- See the **jwt** skill for token creation and verification details
- See the **python** skill for async patterns and general conventions
- See the **stripe** skill for payment webhook handling