"""Appointment CRUD, scheduling, and availability endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime, timezone, timedelta
from typing import Optional
import uuid
import logging

from deps import db, get_shop, get_current_user
from models import Shop, AppointmentStatus, CreateAppointmentRequest
from providers import get_calendar
from providers.interfaces import CalendarEvent
from agents import NoShowEnforcementAgent, WaitlistFillAgent
from scheduling import create_scheduling_engine

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_TRANSITIONS = {
    "pending": {"confirmed", "cancelled", "deposit_pending"},
    "confirmed": {"completed", "cancelled", "no_show", "rescheduled"},
    "deposit_pending": {"deposit_paid", "cancelled"},
    "deposit_paid": {"confirmed", "completed", "cancelled", "no_show"},
    "rescheduled": {"pending", "confirmed", "cancelled"},
    "completed": set(),
    "no_show": set(),
    "cancelled": set(),
}


@router.get("/appointments")
async def list_appointments(
    shop: Shop = Depends(get_shop),
    status: Optional[str] = None,
    date: Optional[str] = None,
    limit: int = 20,
    skip: int = 0,
):
    query = {"shop_id": shop.id}
    if status:
        query["status"] = status
    if date:
        query["scheduled_at"] = {"$gte": f"{date}T00:00:00", "$lt": f"{date}T23:59:59"}

    appointments = await db.appointments.find(query, {"_id": 0}).sort("scheduled_at", -1).skip(skip).limit(limit).to_list(limit)
    total = await db.appointments.count_documents(query)

    for apt in appointments:
        client = await db.clients.find_one({"id": apt.get("client_id")}, {"_id": 0, "name": 1, "phone": 1, "email": 1})
        apt["client"] = client or {"name": "Unknown", "phone": ""}
        barber = await db.barbers.find_one({"id": apt.get("barber_id")}, {"_id": 0, "name": 1})
        apt["barber"] = barber or {"name": "Unknown"}
        service = await db.services.find_one({"id": apt.get("service_id")}, {"_id": 0, "name": 1, "price": 1})
        apt["service"] = service or {"name": "Unknown", "price": 0}

    return {"appointments": appointments, "total": total}


@router.get("/appointments/{appointment_id}")
async def get_appointment(appointment_id: str, shop: Shop = Depends(get_shop)):
    apt = await db.appointments.find_one({"id": appointment_id, "shop_id": shop.id}, {"_id": 0})
    if not apt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    client = await db.clients.find_one({"id": apt.get("client_id")}, {"_id": 0, "name": 1, "phone": 1, "email": 1})
    apt["client"] = client or {"name": "Unknown"}
    barber = await db.barbers.find_one({"id": apt.get("barber_id")}, {"_id": 0, "name": 1})
    apt["barber"] = barber or {"name": "Unknown"}
    service = await db.services.find_one({"id": apt.get("service_id")}, {"_id": 0, "name": 1, "price": 1, "duration_minutes": 1})
    apt["service"] = service or {"name": "Unknown"}
    return apt


@router.patch("/appointments/{appointment_id}/status")
async def update_appointment_status(appointment_id: str, status: str, shop: Shop = Depends(get_shop)):
    valid_statuses = [s.value for s in AppointmentStatus]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

    appointment = await db.appointments.find_one({"id": appointment_id, "shop_id": shop.id}, {"_id": 0})
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    current_status = appointment.get("status", "pending")
    allowed = ALLOWED_TRANSITIONS.get(current_status, set())
    if status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from '{current_status}' to '{status}'. Allowed: {sorted(allowed) if allowed else 'none (terminal state)'}"
        )

    if status in ("no_show", "completed"):
        scheduled_at = appointment.get("scheduled_at", "")
        if scheduled_at:
            try:
                scheduled_dt = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
                if scheduled_dt > datetime.now(timezone.utc):
                    raise HTTPException(status_code=400, detail=f"Cannot mark as '{status}' — appointment is still in the future")
            except (ValueError, TypeError):
                pass

    result = await db.appointments.update_one(
        {"id": appointment_id, "shop_id": shop.id},
        {"$set": {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Appointment not found or status unchanged")

    try:
        if status == "cancelled":
            waitlist_agent = WaitlistFillAgent(db, shop)
            await waitlist_agent.process_cancellation(appointment_id)
            gcal_event_id = appointment.get("gcal_event_id")
            if gcal_event_id:
                calendar = get_calendar(db)
                await calendar.delete_event("primary", gcal_event_id)
        elif status == "no_show":
            noshow_agent = NoShowEnforcementAgent(db, shop)
            await noshow_agent.process_no_show(appointment_id)
    except Exception as e:
        logger.error(f"Agent trigger failed for {appointment_id} -> {status}: {e}")

    return {"message": "Status updated"}


# ==================== SCHEDULING / AVAILABILITY ====================

@router.get("/scheduling/availability")
async def get_availability(
    shop: Shop = Depends(get_shop),
    date: Optional[str] = None,
    barber_id: Optional[str] = None,
    days: int = 7,
):
    scheduler = create_scheduling_engine(db, shop.model_dump())

    if date:
        try:
            start = datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")
    else:
        start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    end = start + timedelta(days=days)
    slots = await scheduler.get_available_slots(start_date=start, end_date=end, barber_id=barber_id)
    return {"slots": slots, "start": start.isoformat(), "end": end.isoformat()}


@router.get("/scheduling/barber/{barber_id}/schedule")
async def get_barber_schedule(
    barber_id: str,
    shop: Shop = Depends(get_shop),
    date: Optional[str] = None,
    days: int = 7,
):
    barber = await db.barbers.find_one({"id": barber_id, "shop_id": shop.id}, {"_id": 0})
    if not barber:
        raise HTTPException(status_code=404, detail="Barber not found")

    scheduler = create_scheduling_engine(db, shop.model_dump())

    if date:
        try:
            start = datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")
    else:
        start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    end = start + timedelta(days=days)
    slots = await scheduler.get_available_slots(start_date=start, end_date=end, barber_id=barber_id)

    appointments = await db.appointments.find(
        {"shop_id": shop.id, "barber_id": barber_id, "scheduled_at": {"$gte": start.isoformat(), "$lte": end.isoformat()}, "status": {"$nin": ["cancelled"]}},
        {"_id": 0}
    ).sort("scheduled_at", 1).to_list(100)

    for apt in appointments:
        client = await db.clients.find_one({"id": apt.get("client_id")}, {"_id": 0, "name": 1})
        apt["client_name"] = client["name"] if client else "Unknown"
        service = await db.services.find_one({"id": apt.get("service_id")}, {"_id": 0, "name": 1})
        apt["service_name"] = service["name"] if service else "Unknown"

    return {"barber": barber, "available_slots": slots, "booked_appointments": appointments}


@router.post("/scheduling/validate-slot")
async def validate_slot(
    shop: Shop = Depends(get_shop),
    barber_id: str = "",
    scheduled_at: str = "",
    duration_minutes: int = 30,
):
    if not barber_id or not scheduled_at:
        raise HTTPException(status_code=400, detail="barber_id and scheduled_at are required")

    try:
        scheduled_dt = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
        if scheduled_dt.tzinfo is None:
            scheduled_dt = scheduled_dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid scheduled_at format")

    scheduler = create_scheduling_engine(db, shop.model_dump())
    is_valid, error_msg = await scheduler.validate_appointment_slot(
        barber_id=barber_id, scheduled_at=scheduled_dt, duration_minutes=duration_minutes
    )
    return {"valid": is_valid, "error": error_msg}


# ==================== CREATE APPOINTMENT ====================

@router.post("/appointments")
async def create_appointment(body: CreateAppointmentRequest, shop: Shop = Depends(get_shop)):
    client = await db.clients.find_one({"id": body.client_id, "shop_id": shop.id}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    barber = await db.barbers.find_one({"id": body.barber_id, "shop_id": shop.id}, {"_id": 0})
    if not barber:
        raise HTTPException(status_code=404, detail="Barber not found")

    service = await db.services.find_one({"id": body.service_id, "shop_id": shop.id}, {"_id": 0})
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    try:
        scheduled_dt = datetime.fromisoformat(body.scheduled_at.replace("Z", "+00:00"))
        if scheduled_dt.tzinfo is None:
            scheduled_dt = scheduled_dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid scheduled_at format — use ISO 8601")

    duration = body.duration_minutes or service.get("duration_minutes", 30)

    scheduler = create_scheduling_engine(db, shop.model_dump())
    is_valid, error_msg = await scheduler.validate_appointment_slot(
        barber_id=body.barber_id, scheduled_at=scheduled_dt, duration_minutes=duration
    )
    if not is_valid:
        raise HTTPException(status_code=409, detail=error_msg)

    now_iso = datetime.now(timezone.utc).isoformat()

    initial_status = "pending"
    try:
        noshow_agent = NoShowEnforcementAgent(db, shop)
        deposit_required = await noshow_agent.check_deposit_requirement(
            {"scheduled_at": scheduled_dt.isoformat()}, client
        )
        if deposit_required:
            initial_status = "deposit_pending"
    except Exception as e:
        logger.error(f"Deposit check failed: {e}")

    appointment_id = str(uuid.uuid4())
    appointment = {
        "id": appointment_id,
        "shop_id": shop.id,
        "client_id": body.client_id,
        "barber_id": body.barber_id,
        "service_id": body.service_id,
        "scheduled_at": scheduled_dt.isoformat(),
        "duration_minutes": duration,
        "status": initial_status,
        "notes": body.notes or "",
        "price": service.get("price", 0),
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    await db.appointments.insert_one(appointment)
    appointment.pop("_id", None)

    # Sync to Google Calendar
    try:
        calendar = get_calendar(db)
        barber_name = barber.get("name", "Unknown")
        client_name = client.get("name", "Unknown")
        end_dt = scheduled_dt + timedelta(minutes=duration)
        cal_event = CalendarEvent(
            summary=f"{service.get('name', 'Appointment')} - {client_name}",
            description=f"Barber: {barber_name}\nClient: {client_name}\nService: {service.get('name', '')}\nNotes: {body.notes or ''}",
            start_time=scheduled_dt,
            end_time=end_dt,
        )
        gcal_event_id = await calendar.create_event("primary", cal_event)
        if gcal_event_id:
            await db.appointments.update_one({"id": appointment_id}, {"$set": {"gcal_event_id": gcal_event_id}})
            appointment["gcal_event_id"] = gcal_event_id
    except Exception as e:
        logger.error(f"Calendar sync failed: {e}")

    return appointment
