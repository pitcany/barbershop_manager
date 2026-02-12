"""Client, conversation, and waitlist endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Optional
import uuid
import re
import logging
import asyncio

from deps import db, get_shop, get_current_user, batch_fetch_map
from models import Shop, CreateClientRequest, UpdateClientRequest, CreateWaitlistRequest

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== CLIENTS ====================

@router.get("/clients")
async def list_clients(
    shop: Shop = Depends(get_shop),
    search: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
):
    query = {"shop_id": shop.id}
    if search:
        escaped = re.escape(search)
        query["$or"] = [
            {"name": {"$regex": escaped, "$options": "i"}},
            {"phone": {"$regex": escaped}},
        ]

    # Use $facet to combine find and count into a single query
    pipeline = [
        {"$match": query},
        {"$sort": {"created_at": -1}},
        {"$facet": {
            "data": [{"$skip": skip}, {"$limit": limit}, {"$project": {"_id": 0}}],
            "total": [{"$count": "count"}],
        }},
    ]
    result = await db.clients.aggregate(pipeline).to_list(1)
    facet = result[0] if result else {"data": [], "total": []}
    clients = facet.get("data", [])
    total = facet["total"][0]["count"] if facet.get("total") else 0

    return {"clients": clients, "total": total}


@router.get("/clients/{client_id}")
async def get_client(client_id: str, shop: Shop = Depends(get_shop)):
    client = await db.clients.find_one({"id": client_id, "shop_id": shop.id}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.post("/clients")
async def create_client(body: CreateClientRequest, shop: Shop = Depends(get_shop)):
    existing = await db.clients.find_one({"shop_id": shop.id, "phone": body.phone}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=409, detail="Client with this phone number already exists")

    now_iso = datetime.now(timezone.utc).isoformat()
    consent_timestamp = now_iso if body.sms_consent else None
    client_data = {
        "id": str(uuid.uuid4()),
        "shop_id": shop.id,
        "name": body.name,
        "phone": body.phone,
        "email": body.email or "",
        "sms_consent": body.sms_consent or False,
        "sms_consent_timestamp": consent_timestamp,
        "sms_consent_source": "admin_dashboard" if body.sms_consent else None,
        "total_appointments": 0,
        "no_shows": 0,
        "notes": body.notes or "",
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    await db.clients.insert_one(client_data)
    client_data.pop("_id", None)
    return client_data


@router.patch("/clients/{client_id}")
async def update_client(client_id: str, body: UpdateClientRequest, shop: Shop = Depends(get_shop)):
    client = await db.clients.find_one({"id": client_id, "shop_id": shop.id}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    update_data = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if "phone" in update_data:
        dup = await db.clients.find_one({"shop_id": shop.id, "phone": update_data["phone"], "id": {"$ne": client_id}}, {"_id": 0})
        if dup:
            raise HTTPException(status_code=409, detail="Another client with this phone number already exists")

    if "sms_consent" in update_data:
        if update_data["sms_consent"] and not client.get("sms_consent"):
            update_data["sms_consent_timestamp"] = datetime.now(timezone.utc).isoformat()
            update_data["sms_consent_source"] = "admin_update"
        elif not update_data["sms_consent"]:
            update_data["sms_consent_timestamp"] = None

    if update_data:
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.clients.update_one({"id": client_id}, {"$set": update_data})

    updated = await db.clients.find_one({"id": client_id}, {"_id": 0})
    return updated


@router.get("/clients/{client_id}/history")
async def get_client_history(client_id: str, shop: Shop = Depends(get_shop)):
    client = await db.clients.find_one({"id": client_id, "shop_id": shop.id}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    appointments = await db.appointments.find(
        {"client_id": client_id, "shop_id": shop.id}, {"_id": 0}
    ).sort("scheduled_at", -1).limit(50).to_list(50)

    # Batch fetch barbers and services to avoid N+1
    barber_ids = [apt.get("barber_id") for apt in appointments if apt.get("barber_id")]
    service_ids = [apt.get("service_id") for apt in appointments if apt.get("service_id")]

    barbers_map = await batch_fetch_map(db.barbers, barber_ids, {"id": 1, "name": 1})
    services_map = await batch_fetch_map(db.services, service_ids, {"id": 1, "name": 1, "price": 1})

    for apt in appointments:
        barber = barbers_map.get(apt.get("barber_id"))
        apt["barber_name"] = barber["name"] if barber else "Unknown"
        service = services_map.get(apt.get("service_id"))
        apt["service_name"] = service["name"] if service else "Unknown"
        apt["service_price"] = service["price"] if service else 0

    messages = await db.messages.find(
        {"client_id": client_id, "shop_id": shop.id}, {"_id": 0}
    ).sort("created_at", -1).limit(50).to_list(50)

    # Parallelize count queries
    total, completed, no_shows, cancelled = await asyncio.gather(
        db.appointments.count_documents({"client_id": client_id, "shop_id": shop.id}),
        db.appointments.count_documents({"client_id": client_id, "shop_id": shop.id, "status": "completed"}),
        db.appointments.count_documents({"client_id": client_id, "shop_id": shop.id, "status": "no_show"}),
        db.appointments.count_documents({"client_id": client_id, "shop_id": shop.id, "status": "cancelled"}),
    )

    revenue_pipeline = [
        {"$match": {"client_id": client_id, "shop_id": shop.id, "status": "completed"}},
        {"$group": {"_id": None, "total": {"$sum": "$price"}}}
    ]
    rev = await db.appointments.aggregate(revenue_pipeline).to_list(1)
    total_revenue = rev[0]["total"] if rev else 0

    return {
        "client": client,
        "appointments": appointments,
        "messages": messages,
        "stats": {
            "total_appointments": total,
            "completed": completed,
            "no_shows": no_shows,
            "cancelled": cancelled,
            "total_revenue": total_revenue,
        },
    }


@router.post("/clients/{client_id}/waitlist")
async def add_client_to_waitlist(client_id: str, body: CreateWaitlistRequest, shop: Shop = Depends(get_shop)):
    client = await db.clients.find_one({"id": client_id, "shop_id": shop.id}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    existing = await db.waitlist.find_one({"shop_id": shop.id, "client_id": client_id, "active": True}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=409, detail="Client already has an active waitlist entry")

    if body.service_id:
        service = await db.services.find_one({"id": body.service_id, "shop_id": shop.id}, {"_id": 0})
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")

    try:
        preferred_dt = datetime.fromisoformat(body.preferred_date.replace("Z", "+00:00"))
        if preferred_dt.tzinfo is None:
            preferred_dt = preferred_dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid preferred_date format — use ISO 8601")

    entry = {
        "id": str(uuid.uuid4()),
        "shop_id": shop.id,
        "client_id": client_id,
        "service_id": body.service_id or "",
        "preferred_barber_id": body.preferred_barber_id or "",
        "preferred_date": preferred_dt.isoformat(),
        "flexible_hours": body.flexible_hours or 3,
        "notes": body.notes or "",
        "active": True,
        "contact_attempts": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.waitlist.insert_one(entry)
    entry.pop("_id", None)
    return entry


# ==================== CONVERSATIONS ====================

@router.get("/conversations")
async def list_conversations(shop: Shop = Depends(get_shop), limit: int = 50):
    pipeline = [
        {"$match": {"shop_id": shop.id}},
        {"$sort": {"created_at": -1}},
        {"$group": {
            "_id": "$client_id",
            "last_message": {"$first": "$content"},
            "last_direction": {"$first": "$direction"},
            "last_at": {"$first": "$created_at"},
            "total_messages": {"$sum": 1},
        }},
        {"$sort": {"last_at": -1}},
        {"$limit": limit},
    ]
    convos = await db.messages.aggregate(pipeline).to_list(limit)

    # Batch fetch clients to avoid N+1
    client_ids = [c["_id"] for c in convos]
    clients_map = await batch_fetch_map(db.clients, client_ids, {"id": 1, "name": 1, "phone": 1})

    # Batch count unread messages
    unread_pipeline = [
        {"$match": {"shop_id": shop.id, "client_id": {"$in": client_ids}, "direction": "inbound", "read": {"$ne": True}}},
        {"$group": {"_id": "$client_id", "count": {"$sum": 1}}},
    ]
    unread_list = await db.messages.aggregate(unread_pipeline).to_list(len(client_ids)) if client_ids else []
    unread_map = {u["_id"]: u["count"] for u in unread_list}

    result = []
    for c in convos:
        client = clients_map.get(c["_id"])
        result.append({
            "client_id": c["_id"],
            "client_name": client["name"] if client else "Unknown",
            "client_phone": client["phone"] if client else "",
            "last_message": c["last_message"],
            "last_direction": c["last_direction"],
            "last_at": c["last_at"],
            "total_messages": c["total_messages"],
            "unread_count": unread_map.get(c["_id"], 0),
        })
    return {"conversations": result}


@router.get("/conversations/{client_id}")
async def get_conversation(client_id: str, shop: Shop = Depends(get_shop), limit: int = 100):
    client = await db.clients.find_one({"id": client_id, "shop_id": shop.id}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    messages = await db.messages.find(
        {"client_id": client_id, "shop_id": shop.id}, {"_id": 0}
    ).sort("created_at", 1).limit(limit).to_list(limit)

    await db.messages.update_many(
        {"client_id": client_id, "shop_id": shop.id, "direction": "inbound", "read": {"$ne": True}},
        {"$set": {"read": True}}
    )

    return {"client": client, "messages": messages}


@router.get("/conversations/poll/new")
async def poll_new_messages(
    shop: Shop = Depends(get_shop),
    since: Optional[str] = None,
    client_id: Optional[str] = None,
):
    query = {"shop_id": shop.id}
    if since:
        query["created_at"] = {"$gt": since}
    if client_id:
        query["client_id"] = client_id

    messages = await db.messages.find(query, {"_id": 0}).sort("created_at", 1).limit(100).to_list(100)

    total_unread = await db.messages.count_documents({"shop_id": shop.id, "direction": "inbound", "read": {"$ne": True}})

    unread_pipeline = [
        {"$match": {"shop_id": shop.id, "direction": "inbound", "read": {"$ne": True}}},
        {"$group": {"_id": "$client_id", "count": {"$sum": 1}}},
    ]
    unread_by_client = {r["_id"]: r["count"] for r in await db.messages.aggregate(unread_pipeline).to_list(100)}

    return {"messages": messages, "total_unread": total_unread, "unread_by_client": unread_by_client}


@router.get("/conversations/activity/live")
async def get_live_activity(
    shop: Shop = Depends(get_shop),
    minutes: int = 60,
):
    cutoff = (datetime.now(timezone.utc) - __import__("datetime").timedelta(minutes=minutes)).isoformat()

    recent_messages = await db.messages.find(
        {"shop_id": shop.id, "created_at": {"$gte": cutoff}}, {"_id": 0}
    ).sort("created_at", -1).limit(20).to_list(20)

    recent_appointments = await db.appointments.find(
        {"shop_id": shop.id, "updated_at": {"$gte": cutoff}}, {"_id": 0, "id": 1, "status": 1, "client_id": 1, "updated_at": 1}
    ).sort("updated_at", -1).limit(10).to_list(10)

    all_client_ids = ([msg.get("client_id") for msg in recent_messages if msg.get("client_id")] +
                      [apt.get("client_id") for apt in recent_appointments if apt.get("client_id")])
    clients_map = await batch_fetch_map(db.clients, all_client_ids, {"id": 1, "name": 1})
    for msg in recent_messages:
        client = clients_map.get(msg.get("client_id"))
        msg["client_name"] = client["name"] if client else "Unknown"
    for apt in recent_appointments:
        client = clients_map.get(apt.get("client_id"))
        apt["client_name"] = client["name"] if client else "Unknown"

    return {"recent_messages": recent_messages, "recent_appointments": recent_appointments}


# ==================== WAITLIST ====================

@router.get("/waitlist")
async def list_waitlist(shop: Shop = Depends(get_shop)):
    entries = await db.waitlist.find({"shop_id": shop.id, "active": True}, {"_id": 0}).sort("created_at", -1).to_list(100)

    # Batch fetch clients and services to avoid N+1
    client_ids = [entry.get("client_id") for entry in entries if entry.get("client_id")]
    service_ids = [entry.get("service_id") for entry in entries if entry.get("service_id")]

    clients_map = await batch_fetch_map(db.clients, client_ids, {"id": 1, "name": 1, "phone": 1})
    services_map = await batch_fetch_map(db.services, service_ids, {"id": 1, "name": 1})

    for entry in entries:
        c = clients_map.get(entry.get("client_id"))
        entry["client"] = {"name": c.get("name", "Unknown"), "phone": c.get("phone", "")} if c else {"name": "Unknown", "phone": ""}
        if entry.get("service_id"):
            s = services_map.get(entry["service_id"])
            entry["service"] = {"name": s.get("name", "Unknown")} if s else {"name": "Unknown"}

    return {"waitlist": entries, "total": len(entries)}


@router.post("/waitlist")
async def create_waitlist_entry(body: CreateWaitlistRequest, shop: Shop = Depends(get_shop)):
    if body.client_id:
        client = await db.clients.find_one({"id": body.client_id, "shop_id": shop.id}, {"_id": 0})
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

    try:
        preferred_dt = datetime.fromisoformat(body.preferred_date.replace("Z", "+00:00"))
        if preferred_dt.tzinfo is None:
            preferred_dt = preferred_dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid preferred_date format")

    entry = {
        "id": str(uuid.uuid4()),
        "shop_id": shop.id,
        "client_id": body.client_id or "",
        "service_id": body.service_id or "",
        "preferred_barber_id": body.preferred_barber_id or "",
        "preferred_date": preferred_dt.isoformat(),
        "flexible_hours": body.flexible_hours or 3,
        "notes": body.notes or "",
        "active": True,
        "contact_attempts": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.waitlist.insert_one(entry)
    entry.pop("_id", None)
    return entry


@router.delete("/waitlist/{entry_id}")
async def remove_from_waitlist(entry_id: str, shop: Shop = Depends(get_shop)):
    result = await db.waitlist.update_one(
        {"id": entry_id, "shop_id": shop.id},
        {"$set": {"active": False, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Waitlist entry not found")
    return {"message": "Removed from waitlist"}
