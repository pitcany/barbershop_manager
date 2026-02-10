# Database Reference

## Contents
- Connection Setup
- Query Patterns
- Aggregation Pipelines
- Insert and Update Patterns
- N+1 Enrichment
- Anti-Patterns

## Connection Setup

Global Motor client in `backend/server.py`:

```python
from motor.motor_asyncio import AsyncIOMotorClient

mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'barbershop_autopilot')]
```

The `db` object is imported/passed directly — no connection pooling wrapper. Motor handles connection pooling internally. Shutdown hook closes the client:

```python
@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
```

See the **mongodb** skill for comprehensive query patterns.

## Query Patterns

### Always Exclude `_id`

Every query uses `{"_id": 0}` projection. The codebase uses UUID string `id` fields, never MongoDB ObjectIds:

```python
# GOOD — every find includes projection
appointment = await db.appointments.find_one(
    {"id": appointment_id, "shop_id": shop.id},
    {"_id": 0}
)

# BAD — ObjectId leaks into response, breaks Pydantic serialization
appointment = await db.appointments.find_one(
    {"id": appointment_id, "shop_id": shop.id}
)
```

### Always Scope to `shop_id`

```python
# GOOD
query = {"shop_id": shop.id}
if status:
    query["status"] = status

# BAD — multi-tenant data leak
query = {}
if status:
    query["status"] = status
```

### Sorted + Paginated List

```python
items = await db.collection.find(
    query, {"_id": 0}
).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

total = await db.collection.count_documents(query)
return {"items": items, "total": total}
```

### Partial Projection for Enrichment

When enriching results, fetch only needed fields:

```python
client = await db.clients.find_one(
    {"id": apt["client_id"]},
    {"_id": 0, "name": 1, "phone": 1}  # Only what's needed
)
```

## Aggregation Pipelines

### Revenue Aggregation

```python
pipeline = [
    {"$match": {
        "shop_id": shop.id,
        "created_at": {"$gte": month_start.isoformat()},
        "revenue_impact": {"$gt": 0}
    }},
    {"$group": {"_id": None, "total": {"$sum": "$revenue_impact"}}}
]
result = await db.events.aggregate(pipeline).to_list(1)
total = result[0]["total"] if result else 0
```

### Conversation Threading (Group + Sort)

```python
pipeline = [
    {"$match": {"shop_id": shop.id}},
    {"$sort": {"created_at": -1}},
    {"$group": {
        "_id": "$client_id",
        "last_message": {"$first": "$content"},
        "last_message_at": {"$first": "$created_at"},
        "message_count": {"$sum": 1}
    }},
    {"$sort": {"last_message_at": -1}},
    {"$limit": limit}
]
threads = await db.messages.aggregate(pipeline).to_list(limit)
```

### Revenue Chart (Date Bucketing)

```python
pipeline = [
    {"$match": {"shop_id": shop.id, "created_at": {"$gte": start_date.isoformat()}}},
    {"$addFields": {"date": {"$substr": ["$created_at", 0, 10]}}},
    {"$group": {
        "_id": "$date",
        "recovered": {"$sum": {"$cond": [{"$gt": ["$revenue_impact", 0]}, "$revenue_impact", 0]}},
        "lost": {"$sum": {"$cond": [{"$lt": ["$revenue_impact", 0]}, {"$abs": "$revenue_impact"}, 0]}}
    }},
    {"$sort": {"_id": 1}}
]
```

## Insert and Update Patterns

### Insert with UUID

```python
import uuid

await db.messages.insert_one({
    "id": str(uuid.uuid4()),
    "shop_id": shop.id,
    "client_id": client.id,
    "created_at": datetime.now(timezone.utc).isoformat()
    # ... other fields
})
```

### Partial Update

```python
result = await db.appointments.update_one(
    {"id": appointment_id, "shop_id": shop.id},  # Always scope
    {"$set": {
        "status": new_status,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }}
)

if result.modified_count == 0:
    raise HTTPException(status_code=404, detail="Not found")
```

### Atomic Increment

```python
await db.clients.update_one(
    {"id": client_id},
    {
        "$inc": {"no_shows": 1},
        "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
    }
)
```

## N+1 Enrichment

This codebase intentionally uses N+1 queries for enrichment (acceptable at current scale):

```python
for apt in appointments:
    client = await db.clients.find_one({"id": apt["client_id"]}, {"_id": 0, "name": 1})
    service = await db.services.find_one({"id": apt["service_id"]}, {"_id": 0, "name": 1})
    apt["client"] = client
    apt["service"] = service
```

For high-volume endpoints, replace with `$lookup` aggregation or batch queries.

## Anti-Patterns

### WARNING: Storing Dates as datetime Objects

**The Problem:** This codebase stores dates as ISO strings, not native datetime. Mixing types breaks comparisons.

**The Fix:** Always use `.isoformat()`:

```python
# GOOD
"created_at": datetime.now(timezone.utc).isoformat()

# BAD — inconsistent with existing data
"created_at": datetime.now(timezone.utc)
```

### WARNING: Missing `to_list()` on Motor Cursors

Motor `find()` returns a cursor, not a list. Always call `.to_list(limit)`:

```python
# GOOD
items = await db.collection.find(query, {"_id": 0}).to_list(50)

# BAD — cursor object, not data
items = await db.collection.find(query, {"_id": 0})
```