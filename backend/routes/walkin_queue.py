"""Walk-in queue endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Optional

from deps import db, get_shop, batch_fetch_map
from models import Shop, JoinQueueRequest, WalkInQueueStatus
from walkin_queue_agent import WalkInQueueAgent

router = APIRouter()


@router.get("/walkin-queue")
async def list_queue(
    shop: Shop = Depends(get_shop),
    include_completed: bool = False,
):
    """List active walk-in queue entries with client/service/barber enrichment."""
    agent = WalkInQueueAgent(db, shop)

    if include_completed:
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        entries = await db.walkin_queue.find(
            {
                "shop_id": shop.id,
                "$or": [
                    {"status": {"$in": ["waiting", "notified", "serving"]}},
                    {"status": "completed", "completed_at": {"$gte": today_start}},
                ],
            },
            {"_id": 0},
        ).sort("joined_at", 1).to_list(200)
    else:
        entries = await agent.get_active_queue(include_serving=True)

    # Enrich with related data
    client_ids = [e.get("client_id") for e in entries if e.get("client_id")]
    service_ids = [e.get("service_id") for e in entries if e.get("service_id")]
    barber_ids = [e.get("barber_id") for e in entries if e.get("barber_id")]
    barber_ids += [e.get("assigned_barber_id") for e in entries if e.get("assigned_barber_id")]

    clients_map = await batch_fetch_map(db.clients, client_ids, {"id": 1, "name": 1, "phone": 1})
    services_map = await batch_fetch_map(db.services, service_ids, {"id": 1, "name": 1, "duration_minutes": 1, "price": 1})
    barbers_map = await batch_fetch_map(db.barbers, barber_ids, {"id": 1, "name": 1})

    for e in entries:
        e["client"] = clients_map.get(e.get("client_id"), {"name": "Unknown", "phone": ""})
        e["service"] = services_map.get(e.get("service_id")) if e.get("service_id") else None
        e["barber"] = barbers_map.get(e.get("barber_id")) if e.get("barber_id") else None
        e["assigned_barber"] = barbers_map.get(e.get("assigned_barber_id")) if e.get("assigned_barber_id") else None

    return {"queue": entries}


@router.post("/walkin-queue")
async def add_to_queue(body: JoinQueueRequest, shop: Shop = Depends(get_shop)):
    """Admin adds a walk-in to the queue."""
    client = await db.clients.find_one(
        {"id": body.client_id, "shop_id": shop.id}, {"_id": 0}
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    agent = WalkInQueueAgent(db, shop)
    result = await agent.join_queue(
        client=client,
        service_id=body.service_id,
        barber_id=body.barber_id,
        source="admin_dashboard",
    )

    if result.get("error") == "queue_full":
        raise HTTPException(status_code=409, detail=f"Queue is full (max {result['max_size']})")

    return result


@router.patch("/walkin-queue/{entry_id}/status")
async def update_queue_status(
    entry_id: str,
    status: str,
    assigned_barber_id: Optional[str] = None,
    shop: Shop = Depends(get_shop),
):
    """Change a queue entry's status (serving, completed, left)."""
    valid = {s.value for s in WalkInQueueStatus}
    if status not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid}")

    agent = WalkInQueueAgent(db, shop)
    result = await agent.advance_queue(entry_id, status, assigned_barber_id)
    if not result:
        raise HTTPException(status_code=404, detail="Queue entry not found")
    return result


@router.delete("/walkin-queue/{entry_id}")
async def remove_from_queue(entry_id: str, shop: Shop = Depends(get_shop)):
    """Remove an entry from the queue (marks as LEFT)."""
    agent = WalkInQueueAgent(db, shop)
    success = await agent.remove_from_queue(entry_id)
    if not success:
        raise HTTPException(status_code=404, detail="Queue entry not found")
    return {"message": "Removed from queue"}


@router.get("/walkin-queue/stats")
async def get_queue_stats(shop: Shop = Depends(get_shop)):
    """Queue summary stats."""
    agent = WalkInQueueAgent(db, shop)
    return await agent.get_queue_stats()
