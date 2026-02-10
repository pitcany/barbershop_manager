# MongoDB Errors Reference

## Contents
- Common Runtime Errors
- Silent Failures
- Missing Indexes (Production Risk)
- Error Handling Patterns
- Troubleshooting Checklist

---

## Common Runtime Errors

### ServerSelectionTimeoutError

```
pymongo.errors.ServerSelectionTimeoutError: localhost:27017: [Errno 61] Connection refused
```

**Cause:** MongoDB is not running locally.
**Fix:** Start MongoDB (`mongod` or `brew services start mongodb-community`) before launching the backend.

### DocumentTooLarge

```
pymongo.errors.DocumentTooLarge: BSON document too large (16793600 bytes)
```

**Cause:** Single document exceeds 16MB BSON limit. Can happen if appending to arrays indefinitely.
**Fix:** Store large data in separate collection with foreign key references. This project avoids embedded arrays, so this is unlikely unless seed data gets extreme.

### DuplicateKeyError on _id

```
pymongo.errors.DuplicateKeyError: E11000 duplicate key error collection
```

**Cause:** Inserting a document with a duplicate `_id`. Since this project uses string `id` fields (not `_id`), this only occurs if the same MongoDB `_id` is inserted twice — usually a re-seeding issue.
**Fix:** The startup seed checks `count_documents({})` before seeding. If re-seeding is needed, drop the collection first.

---

## Silent Failures

### WARNING: Enum Without .value in Queries

**The Problem:**

```python
# BAD — matches nothing, returns empty results, no error
await db.appointments.find({"status": AppointmentStatus.CONFIRMED})
```

**Why This Breaks:** Motor serializes the enum object. MongoDB stores plain strings. Type mismatch means zero matches with no error.

**The Fix:**

```python
# GOOD
await db.appointments.find({"status": AppointmentStatus.CONFIRMED.value})
```

### WARNING: Missing shop_id in Query

**The Problem:**

```python
# BAD — returns ALL appointments across all shops
appointments = await db.appointments.find({"status": "confirmed"}, {"_id": 0}).to_list(100)
```

**Why This Breaks:** Data leaks across tenants. No error raised — just wrong data returned.

**The Fix:**

```python
# GOOD — always scope by shop_id
appointments = await db.appointments.find(
    {"shop_id": shop.id, "status": "confirmed"}, {"_id": 0}
).to_list(100)
```

### WARNING: update_one Matching Nothing

**The Problem:**

```python
# Silently does nothing if filter matches no documents
await db.appointments.update_one(
    {"id": wrong_id},
    {"$set": {"status": "confirmed"}}
)
```

**Why This Breaks:** `modified_count` is 0, but if you don't check it, the operation appears to succeed.

**The Fix:**

```python
result = await db.appointments.update_one(
    {"id": appointment_id},
    {"$set": {"status": "confirmed"}}
)
if result.modified_count == 0:
    raise HTTPException(status_code=404, detail="Appointment not found")
```

### WARNING: to_list() Without Limit

**The Problem:**

```python
# BAD — loads entire collection into memory
all_docs = await db.appointments.find({}, {"_id": 0}).to_list(None)
```

**Why This Breaks:** `to_list(None)` means unlimited. On a growing collection, this exhausts memory.

**The Fix:**

```python
# GOOD — always set a reasonable limit
docs = await db.appointments.find({}, {"_id": 0}).to_list(100)
```

---

## Missing Indexes (Production Risk)

### WARNING: No Explicit Indexes Defined

This codebase creates **zero indexes** beyond MongoDB's automatic `_id` index. For production workloads, this causes full collection scans on every query.

**Critical indexes to add:**

```python
# Add to startup or a migration script
async def create_indexes():
    await db.appointments.create_index([("shop_id", 1), ("status", 1)])
    await db.appointments.create_index([("shop_id", 1), ("scheduled_at", -1)])
    await db.appointments.create_index([("shop_id", 1), ("client_id", 1)])
    await db.clients.create_index([("shop_id", 1), ("phone", 1)], unique=True)
    await db.messages.create_index([("shop_id", 1), ("client_id", 1), ("created_at", -1)])
    await db.events.create_index([("shop_id", 1), ("created_at", -1)])
    await db.payments.create_index("stripe_session_id")
    await db.waitlist.create_index([("shop_id", 1), ("active", 1), ("service_id", 1)])
```

**When You'll Notice:** Dashboard stats endpoint runs multiple `count_documents()` and `aggregate()` calls. Without indexes on `shop_id` + `status` + `scheduled_at`, response time grows linearly with data volume.

**Validation:**

```python
# Check if query uses index
await db.command("explain", {
    "find": "appointments",
    "filter": {"shop_id": "x", "status": "confirmed"}
})
# Look for "COLLSCAN" (bad) vs "IXSCAN" (good) in winningPlan
```

---

## Error Handling Patterns

### Critical Path — Propagate Exceptions

```python
# Appointment updates, payment creation — errors MUST surface
result = await db.appointments.update_one({"id": apt_id}, {"$set": update})
if result.modified_count == 0:
    raise HTTPException(status_code=404, detail="Not found")
```

### Non-Critical Path — Catch and Log

```python
# Audit logging, revenue tracking — errors must NOT block operations
try:
    await self.db.integration_audit_log.insert_one(log_entry)
except Exception as e:
    logger.error(f"Failed to write audit log: {e}")
```

See `backend/audit.py` and `backend/revenue_logger.py` for this pattern.

### Graceful Fallbacks on Optional Lookups

```python
# Enrichment lookups — missing data shouldn't crash
barber = await db.barbers.find_one({"id": apt["barber_id"]}, {"_id": 0, "name": 1})
barber_name = barber["name"] if barber else "your barber"
```

---

## Troubleshooting Checklist

Copy this checklist when debugging MongoDB issues:

- [ ] Is MongoDB running? (`mongod` or check service status)
- [ ] Is `MONGO_URL` correct in environment?
- [ ] Does the query include `shop_id`?
- [ ] Are enum values using `.value`?
- [ ] Are timestamps ISO strings (not datetime objects)?
- [ ] Does `find_one()` result get checked for `None`?
- [ ] Does `update_one()` result get checked for `modified_count == 0`?
- [ ] Is `to_list()` called with a reasonable limit?
- [ ] Is `{"_id": 0}` in the projection?
- [ ] For aggregations: does `$sort` come before `$group` when using `$first`?

### Validate Query Performance

```bash
# Connect to MongoDB shell
mongosh barbershop_autopilot

# Check collection stats
db.appointments.stats()

# Explain a slow query
db.appointments.find({"shop_id": "x", "status": "confirmed"}).explain("executionStats")
```

1. Run query with `explain("executionStats")`
2. Check `winningPlan.stage` — should be `IXSCAN`, not `COLLSCAN`
3. If `COLLSCAN`, add the appropriate compound index
4. Re-run explain to confirm `IXSCAN`
