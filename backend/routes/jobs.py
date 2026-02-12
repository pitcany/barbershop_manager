"""Background jobs, reporting, audit, and retention endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Optional
import logging

from deps import db, get_shop, get_current_user, batch_fetch_map
from models import Shop
from scheduler import get_job_status
from owner_ops_agent import OwnerOpsAgent
from retention_rebook_agent import RetentionRebookAgent

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== SCHEDULED JOBS ====================

@router.post("/jobs/reminders/run")
async def run_reminder_job(shop: Shop = Depends(get_shop)):
    from scheduled_jobs import run_appointment_reminders
    results = await run_appointment_reminders(db, shop.id)
    return {"message": "Reminder job executed", "results": results}


@router.get("/jobs/reminders/preview")
async def preview_reminders(shop: Shop = Depends(get_shop)):
    now = datetime.now(timezone.utc)
    window_start = now.isoformat()
    window_end = (now + timedelta(hours=shop.confirmation_window_hours)).isoformat()

    upcoming = await db.appointments.find(
        {"shop_id": shop.id, "scheduled_at": {"$gte": window_start, "$lte": window_end}, "status": {"$in": ["confirmed", "deposit_paid"]}},
        {"_id": 0},
    ).to_list(50)

    client_ids = [apt.get("client_id") for apt in upcoming if apt.get("client_id")]
    barber_ids = [apt.get("barber_id") for apt in upcoming if apt.get("barber_id")]
    clients_map = await batch_fetch_map(db.clients, client_ids, {"id": 1, "name": 1, "phone": 1, "sms_consent": 1})
    barbers_map = await batch_fetch_map(db.barbers, barber_ids, {"id": 1, "name": 1})
    for apt in upcoming:
        apt["client"] = clients_map.get(apt.get("client_id")) or {"name": "Unknown"}
        barber = barbers_map.get(apt.get("barber_id"))
        apt["barber_name"] = barber["name"] if barber else "Unknown"

    return {"preview": upcoming, "window": {"start": window_start, "end": window_end}}


@router.post("/jobs/daily-summary/run")
async def run_daily_summary(shop: Shop = Depends(get_shop)):
    agent = OwnerOpsAgent(db, shop.model_dump())
    result = await agent.send_daily_summary()
    return {"message": "Daily summary executed", "result": result}


@router.get("/jobs/daily-summary/preview")
async def preview_daily_summary(shop: Shop = Depends(get_shop)):
    agent = OwnerOpsAgent(db, shop.model_dump())
    data = await agent.compile_daily_stats()
    return {"preview": data}


@router.get("/jobs/status")
async def scheduler_status(user: dict = Depends(get_current_user)):
    return get_job_status()


@router.post("/jobs/retention/run")
async def run_retention_sweep(shop: Shop = Depends(get_shop)):
    agent = RetentionRebookAgent(db, shop.model_dump())
    result = await agent.run_retention_sweep(shop.id)
    return result


@router.get("/jobs/retention/preview")
async def preview_retention(shop: Shop = Depends(get_shop)):
    agent = RetentionRebookAgent(db, shop.model_dump())
    preview = await agent.preview_targets(shop.id)
    return preview


@router.get("/retention/outreach-history")
async def retention_outreach_history(limit: int = 50, shop: Shop = Depends(get_shop)):
    entries = await db.retention_outreach.find({"shop_id": shop.id}, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return {"entries": entries, "count": len(entries)}


# ==================== AUDIT & REVENUE ====================

@router.get("/audit-log")
async def list_audit_log(shop: Shop = Depends(get_shop), provider: Optional[str] = None, limit: int = 100):
    query = {"shop_id": shop.id}
    if provider:
        query["provider"] = provider
    entries = await db.integration_audit_log.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return {"audit_log": entries, "count": len(entries)}


@router.get("/internal/recovered-revenue")
async def list_recovered_revenue_events(shop: Shop = Depends(get_shop), source: Optional[str] = None, limit: int = 100):
    query = {"shop_id": shop.id}
    if source:
        query["source"] = source
    events = await db.recovered_revenue_events.find(query, {"_id": 0}).sort("attributed_at", -1).limit(limit).to_list(limit)
    total_amount = sum(e.get("amount", 0) for e in events)
    return {
        "events": events,
        "count": len(events),
        "_internal_total": total_amount,
        "_note": "This data is for internal attribution only. NOT for owner-facing display.",
    }


# ==================== REPORTING ====================

@router.get("/reporting/overview")
async def reporting_overview(days: int = 30, shop: Shop = Depends(get_shop)):
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=days)).isoformat()

    apt_pipeline = [
        {"$match": {"shop_id": shop.id, "scheduled_at": {"$gte": start}}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}, "revenue": {"$sum": "$price"}}},
    ]
    apt_stats = await db.appointments.aggregate(apt_pipeline).to_list(20)
    by_status = {r["_id"]: {"count": r["count"], "revenue": r["revenue"]} for r in apt_stats}
    total_apts = sum(r["count"] for r in apt_stats)

    rev_pipeline = [
        {"$match": {"shop_id": shop.id, "attributed_at": {"$gte": start}}},
        {"$group": {"_id": "$source", "total": {"$sum": "$amount"}, "count": {"$sum": 1}}},
    ]
    rev_stats = await db.recovered_revenue_events.aggregate(rev_pipeline).to_list(20)
    recovered_by_source = {r["_id"]: {"amount": r["total"], "count": r["count"]} for r in rev_stats}
    total_recovered = sum(r["total"] for r in rev_stats)

    daily_pipeline = [
        {"$match": {"shop_id": shop.id, "scheduled_at": {"$gte": start}}},
        {"$addFields": {"day": {"$substr": ["$scheduled_at", 0, 10]}}},
        {"$group": {
            "_id": "$day",
            "total": {"$sum": 1},
            "completed": {"$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}},
            "no_shows": {"$sum": {"$cond": [{"$eq": ["$status", "no_show"]}, 1, 0]}},
            "cancelled": {"$sum": {"$cond": [{"$eq": ["$status", "cancelled"]}, 1, 0]}},
            "revenue": {"$sum": "$price"},
        }},
        {"$sort": {"_id": 1}},
    ]
    daily_trend = await db.appointments.aggregate(daily_pipeline).to_list(60)

    recovered_events = await db.recovered_revenue_events.find(
        {"shop_id": shop.id, "attributed_at": {"$gte": start}}, {"_id": 0}
    ).sort("attributed_at", -1).to_list(100)

    barber_pipeline = [
        {"$match": {"shop_id": shop.id, "scheduled_at": {"$gte": start}}},
        {"$group": {
            "_id": "$barber_id",
            "total": {"$sum": 1},
            "completed": {"$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}},
            "no_shows": {"$sum": {"$cond": [{"$eq": ["$status", "no_show"]}, 1, 0]}},
            "revenue": {"$sum": "$price"},
        }},
    ]
    barber_stats = await db.appointments.aggregate(barber_pipeline).to_list(20)
    barber_ids = [bs["_id"] for bs in barber_stats]
    barbers_map = await batch_fetch_map(db.barbers, barber_ids, {"id": 1, "name": 1})
    for bs in barber_stats:
        barber = barbers_map.get(bs["_id"])
        bs["name"] = barber["name"] if barber else bs["_id"]
        del bs["_id"]

    msg_pipeline = [
        {"$match": {"shop_id": shop.id, "created_at": {"$gte": start}}},
        {"$group": {"_id": "$direction", "count": {"$sum": 1}}},
    ]
    msg_stats = await db.messages.aggregate(msg_pipeline).to_list(5)
    messages = {r["_id"]: r["count"] for r in msg_stats}

    audit_pipeline = [
        {"$match": {"shop_id": shop.id, "created_at": {"$gte": start}}},
        {"$group": {"_id": {"provider": "$provider", "success": "$success"}, "count": {"$sum": 1}}},
    ]
    audit_stats = await db.integration_audit_log.aggregate(audit_pipeline).to_list(50)

    no_shows = by_status.get("no_show", {}).get("count", 0)

    return {
        "period_days": days,
        "appointments": {
            "total": total_apts,
            "by_status": by_status,
            "no_show_rate": round((no_shows / total_apts * 100) if total_apts > 0 else 0, 1),
        },
        "revenue": {
            "total_earned": sum(r.get("revenue", 0) for r in apt_stats if r["_id"] == "completed"),
            "total_recovered": total_recovered,
            "recovered_by_source": recovered_by_source,
        },
        "daily_trend": [{"date": d["_id"], **{k: v for k, v in d.items() if k != "_id"}} for d in daily_trend],
        "recovered_events": recovered_events,
        "barber_performance": barber_stats,
        "messages": messages,
        "audit_summary": [{"provider": a["_id"]["provider"], "success": a["_id"]["success"], "count": a["count"]} for a in audit_stats],
    }


@router.get("/reporting/jobs-history")
async def jobs_history(limit: int = 50, user: dict = Depends(get_current_user)):
    entries = await db.integration_audit_log.find(
        {"action": {"$in": ["daily_summary_email", "appointment_reminder", "send_sms", "send_email"]}},
        {"_id": 0},
    ).sort("created_at", -1).limit(limit).to_list(limit)
    return {"entries": entries, "count": len(entries)}
