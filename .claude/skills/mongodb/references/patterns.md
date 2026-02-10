# MongoDB Patterns Reference

## Contents
- Query Patterns
- Aggregation Pipelines
- Update Operators
- Enrichment and Joins
- Shop Isolation
- Startup Seeding

---

## Query Patterns

### find_one() — Single Document

```python
# Standard: filter + projection excluding _id
client = await db.clients.find_one(
    {"id": client_id, "shop_id": shop.id},
    {"_id": 0}
)

# Partial projection — only fetch needed fields
client = await db.clients.find_one(
    {"id": client_id, "shop_id": shop.id},
    {"_id": 0, "sms_consent": 1, "phone": 1}
)
```

### find() — Multiple Documents with Cursor Chaining

```python
appointments = await db.appointments.find(
    query, {"_id": 0}
).sort("scheduled_at", -1).skip(skip).limit(limit).to_list(limit)
```

Chain order: `find()` -> `.sort()` -> `.skip()` -> `.limit()` -> `.to_list(n)`

NEVER call `.to_list()` without a limit on unbounded collections. Memory will explode.

### Regex Search

```python
# Case-insensitive name search, exact phone search
query["$or"] = [
    {"name": {"$regex": search, "$options": "i"}},
    {"phone": {"$regex": search}}
]
```

### Range Queries on ISO Timestamps

```python
# ISO strings support direct comparison because they sort lexicographically
{"scheduled_at": {"$gte": start.isoformat(), "$lt": end.isoformat()}}
```

This works because ISO 8601 strings sort correctly as strings. NEVER mix datetime objects with ISO string fields.

### $in for Enum Lists

```python
{"status": {"$in": [AppointmentStatus.PENDING.value, AppointmentStatus.DEPOSIT_PAID.value]}}
```

Always use `.value` — passing the enum object directly will match nothing and fail silently.

---

## Aggregation Pipelines

### Revenue Summation

```python
pipeline = [
    {"$match": {"shop_id": shop.id, "created_at": {"$gte": month_start.isoformat()}, "revenue_impact": {"$gt": 0}}},
    {"$group": {"_id": None, "total": {"$sum": "$revenue_impact"}}}
]
result = await db.events.aggregate(pipeline).to_list(1)
total = result[0]["total"] if result else 0
```

### Conversation Grouping with $first

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

`$sort` BEFORE `$group` ensures `$first` picks the most recent document per group.

### Date Extraction with $substr

```python
{"$addFields": {"date": {"$substr": ["$created_at", 0, 10]}}}  # "2024-02-10T14:30:00" -> "2024-02-10"
```

This works because ISO strings have fixed-width format. For native Date types, use `$dateToString` instead.

### Conditional Aggregation with $cond

```python
{"$group": {
    "_id": "$date",
    "recovered": {"$sum": {"$cond": [{"$gt": ["$revenue_impact", 0]}, "$revenue_impact", 0]}},
    "lost": {"$sum": {"$cond": [{"$lt": ["$revenue_impact", 0]}, {"$abs": "$revenue_impact"}, 0]}}
}}
```

---

## Update Operators

### $set — Atomic Field Update

```python
await db.appointments.update_one(
    {"id": appointment_id},
    {"$set": {"status": "confirmed", "confirmed_at": datetime.now(timezone.utc).isoformat()}}
)
```

### $inc + $set — Combined Atomic Update

```python
await db.clients.update_one(
    {"id": client_id},
    {"$inc": {"no_shows": 1}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}}
)
```

Both operators execute atomically in a single write. NEVER do a read-modify-write cycle for counters.

---

## Enrichment and Joins

### WARNING: N+1 Query Pattern

**The Problem:**

```python
# BAD — 1 query per appointment for each related collection
for apt in appointments:
    apt["client"] = await db.clients.find_one({"id": apt["client_id"]}, {"_id": 0, "name": 1})
    apt["service"] = await db.services.find_one({"id": apt["service_id"]}, {"_id": 0, "name": 1})
    apt["barber"] = await db.barbers.find_one({"id": apt["barber_id"]}, {"_id": 0, "name": 1})
```

**Why This Breaks:** 30 appointments = 90 extra queries. Latency grows linearly.

**The Fix (batch fetch):**

```python
client_ids = [apt["client_id"] for apt in appointments]
clients = await db.clients.find({"id": {"$in": client_ids}}, {"_id": 0}).to_list(len(client_ids))
client_map = {c["id"]: c for c in clients}
for apt in appointments:
    apt["client"] = client_map.get(apt["client_id"])
```

**When You Might Be Tempted:** Small result sets (<20) where the N+1 overhead is negligible. This is the current MVP pattern — acceptable for now, not for scale.

---

## Shop Isolation

Every query MUST include `shop_id` for multi-tenant isolation:

```python
# GOOD — scoped to shop
await db.appointments.find({"shop_id": shop.id, "status": "confirmed"}, {"_id": 0})

# BAD — leaks data across shops
await db.appointments.find({"status": "confirmed"}, {"_id": 0})
```

The `shop` object comes from FastAPI's `Depends(get_shop)` dependency. See the **fastapi** skill.

---

## Startup Seeding

```python
# Check-before-seed pattern
shop_count = await db.shops.count_documents({})
if shop_count == 0:
    await seed_demo_data()
```

Seed uses `insert_one()` for shops/admins and `insert_many()` for bulk collections (barbers, services, clients, appointments, messages, events).
