"""Public endpoints (no auth required)."""
from fastapi import APIRouter, HTTPException, Request
from datetime import datetime, timezone, timedelta
from typing import Optional
import uuid
import logging

from deps import db, check_rate_limit
from models import Shop, SMSConsentRequest
from scheduling import create_scheduling_engine
from providers import get_payment, get_calendar
from providers.interfaces import CalendarEvent

logger = logging.getLogger(__name__)

router = APIRouter()


async def _get_shop():
    """Get shop (for public endpoints where no auth is needed)"""
    shop_data = await db.shops.find_one({}, {"_id": 0})
    if not shop_data:
        raise HTTPException(status_code=500, detail="Shop not configured")
    return Shop(**shop_data)


@router.get("/public/shop-info")
async def get_public_shop_info():
    shop_data = await db.shops.find_one({}, {"_id": 0, "name": 1, "phone": 1, "address": 1, "business_hours": 1})
    if not shop_data:
        raise HTTPException(status_code=404, detail="Shop not found")
    return shop_data


@router.get("/public/barbers")
async def get_public_barbers():
    shop = await _get_shop()
    barbers = await db.barbers.find({"shop_id": shop.id, "active": True}, {"_id": 0, "id": 1, "name": 1}).to_list(50)
    return {"barbers": barbers}


@router.get("/public/services")
async def get_public_services():
    shop = await _get_shop()
    services = await db.services.find(
        {"shop_id": shop.id, "active": True},
        {"_id": 0, "id": 1, "name": 1, "description": 1, "duration_minutes": 1, "price": 1}
    ).to_list(50)
    return {"services": services}


@router.get("/public/availability")
async def get_public_availability(
    date: str,
    barber_id: Optional[str] = None,
    service_id: Optional[str] = None,
    raw_request: Request = None,
):
    """Get available slots for a given date (public, no auth)"""
    shop = await _get_shop()
    scheduler = create_scheduling_engine(db, shop.model_dump())

    # Determine duration from service
    duration = 30
    if service_id:
        service = await db.services.find_one({"id": service_id, "shop_id": shop.id}, {"_id": 0})
        if service:
            duration = service.get("duration_minutes", 30)

    try:
        target = datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid date format. Use ISO 8601.")

    slots = await scheduler.get_available_slots(date=target, barber_id=barber_id, duration_minutes=duration)
    return {"slots": [s.to_dict() for s in slots], "date": date}


@router.post("/public/book")
async def public_book_appointment(request: Request):
    """Public booking endpoint — creates appointment + returns deposit checkout if needed"""
    raw_request = request
    client_ip = raw_request.client.host if raw_request.client else "unknown"
    if not check_rate_limit(f"public-book:{client_ip}", max_requests=10, window_seconds=3600):
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")

    body = await request.json()
    name = body.get("name", "").strip()
    phone = body.get("phone", "").strip()
    email = body.get("email", "").strip()
    barber_id = body.get("barber_id", "")
    service_id = body.get("service_id", "")
    scheduled_at = body.get("scheduled_at", "")
    notes = body.get("notes", "")
    sms_consent = body.get("sms_consent", False)

    if not name or not phone or not barber_id or not service_id or not scheduled_at:
        raise HTTPException(status_code=400, detail="Missing required fields: name, phone, barber_id, service_id, scheduled_at")

    shop = await _get_shop()

    # Validate barber and service
    barber = await db.barbers.find_one({"id": barber_id, "shop_id": shop.id, "active": True}, {"_id": 0})
    if not barber:
        raise HTTPException(status_code=404, detail="Barber not found")

    service = await db.services.find_one({"id": service_id, "shop_id": shop.id, "active": True}, {"_id": 0})
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    # Parse and validate time slot
    try:
        scheduled_dt = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
        if scheduled_dt.tzinfo is None:
            scheduled_dt = scheduled_dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid scheduled_at format")

    duration = service.get("duration_minutes", 30)
    scheduler = create_scheduling_engine(db, shop.model_dump())
    is_valid, error_msg = await scheduler.validate_appointment_slot(
        barber_id=barber_id, scheduled_at=scheduled_dt, duration_minutes=duration
    )
    if not is_valid:
        raise HTTPException(status_code=409, detail=error_msg)

    # Find or create client
    client = await db.clients.find_one({"shop_id": shop.id, "phone": phone}, {"_id": 0})
    now_iso = datetime.now(timezone.utc).isoformat()

    if client:
        update_fields = {"name": name, "updated_at": now_iso}
        if email:
            update_fields["email"] = email
        if sms_consent and not client.get("sms_consent"):
            update_fields["sms_consent"] = True
            update_fields["sms_consent_timestamp"] = now_iso
            update_fields["sms_consent_source"] = "booking_portal"
        await db.clients.update_one({"id": client["id"]}, {"$set": update_fields})
        client_id = client["id"]
    else:
        client_id = str(uuid.uuid4())
        client = {
            "id": client_id,
            "shop_id": shop.id,
            "name": name,
            "phone": phone,
            "email": email,
            "sms_consent": sms_consent,
            "sms_consent_timestamp": now_iso if sms_consent else None,
            "sms_consent_source": "booking_portal" if sms_consent else None,
            "total_appointments": 0,
            "no_shows": 0,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        await db.clients.insert_one(client)
        client.pop("_id", None)

    # Determine if deposit is required (smart enforcement)
    deposit_required = False
    hours_until = (scheduled_dt - datetime.now(timezone.utc)).total_seconds() / 3600
    if hours_until <= shop.deposit_required_hours:
        deposit_required = True
    # Also check no-show history
    if client:
        no_shows = client.get("no_shows", 0) if isinstance(client, dict) else 0
        if no_shows > 0:
            deposit_required = True

    initial_status = "deposit_pending" if deposit_required else "confirmed"

    appointment_id = str(uuid.uuid4())
    appointment = {
        "id": appointment_id,
        "shop_id": shop.id,
        "client_id": client_id,
        "barber_id": barber_id,
        "service_id": service_id,
        "scheduled_at": scheduled_dt.isoformat(),
        "duration_minutes": duration,
        "status": initial_status,
        "notes": notes,
        "price": service.get("price", 0),
        "deposit_required": deposit_required,
        "deposit_amount": float(shop.deposit_amount) if deposit_required else 0,
        "deposit_paid": False,
        "source": "booking_portal",
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    await db.appointments.insert_one(appointment)
    appointment.pop("_id", None)

    # Sync to Google Calendar
    try:
        calendar = get_calendar(db)
        end_dt = scheduled_dt + timedelta(minutes=duration)
        cal_event = CalendarEvent(
            summary=f"{service.get('name', 'Appointment')} - {name}",
            description=f"Barber: {barber.get('name', '')}\nClient: {name}\nPhone: {phone}\nService: {service.get('name', '')}\nNotes: {notes}\nSource: Online Booking",
            start_time=scheduled_dt,
            end_time=end_dt,
        )
        gcal_event_id = await calendar.create_event("primary", cal_event)
        if gcal_event_id:
            await db.appointments.update_one({"id": appointment_id}, {"$set": {"gcal_event_id": gcal_event_id}})
            appointment["gcal_event_id"] = gcal_event_id
    except Exception as e:
        logger.error(f"Calendar sync failed for public booking: {e}")

    result = {
        "appointment_id": appointment_id,
        "status": initial_status,
        "deposit_required": deposit_required,
        "service_name": service.get("name", ""),
        "barber_name": barber.get("name", ""),
        "scheduled_at": scheduled_dt.isoformat(),
        "price": service.get("price", 0),
    }

    # If deposit required, create Stripe checkout
    if deposit_required:
        try:
            origin = request.headers.get("x-origin", str(request.base_url).rstrip("/"))
            success_url = f"{origin}/book/confirmation?appointment_id={appointment_id}&session_id={{CHECKOUT_SESSION_ID}}"
            cancel_url = f"{origin}/book?payment_cancelled=true&appointment_id={appointment_id}"

            metadata = {
                "appointment_id": appointment_id,
                "client_id": client_id,
                "shop_id": shop.id,
                "type": "deposit",
                "source": "booking_portal",
            }

            payment = get_payment()
            payment_link = await payment.create_payment_link(
                amount=float(shop.deposit_amount),
                currency="usd",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata=metadata,
            )

            # Store transaction records
            await db.payment_transactions.insert_one({
                "id": str(uuid.uuid4()),
                "shop_id": shop.id,
                "client_id": client_id,
                "client_name": name,
                "appointment_id": appointment_id,
                "amount": float(shop.deposit_amount),
                "currency": "usd",
                "session_id": payment_link.session_id,
                "payment_status": "initiated",
                "status": "pending",
                "payment_type": "deposit",
                "metadata": metadata,
                "created_at": now_iso,
                "updated_at": now_iso,
            })

            await db.payments.insert_one({
                "id": str(uuid.uuid4()),
                "shop_id": shop.id,
                "client_id": client_id,
                "appointment_id": appointment_id,
                "amount": float(shop.deposit_amount),
                "currency": "usd",
                "stripe_session_id": payment_link.session_id,
                "status": "pending",
                "payment_type": "deposit",
                "created_at": now_iso,
                "updated_at": now_iso,
            })

            result["checkout_url"] = payment_link.url
            result["session_id"] = payment_link.session_id
            result["deposit_amount"] = float(shop.deposit_amount)
        except Exception as e:
            logger.error(f"Stripe checkout creation failed for public booking: {e}")
            result["deposit_error"] = "Payment processing unavailable. Please contact the shop."

    return result


@router.get("/public/appointment/{appointment_id}")
async def get_public_appointment(appointment_id: str):
    """Get appointment status (public, for confirmation page)"""
    apt = await db.appointments.find_one(
        {"id": appointment_id},
        {"_id": 0, "id": 1, "status": 1, "scheduled_at": 1, "duration_minutes": 1,
         "barber_id": 1, "service_id": 1, "deposit_required": 1, "deposit_paid": 1,
         "deposit_amount": 1, "price": 1}
    )
    if not apt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    barber = await db.barbers.find_one({"id": apt.get("barber_id")}, {"_id": 0, "name": 1})
    service = await db.services.find_one({"id": apt.get("service_id")}, {"_id": 0, "name": 1, "price": 1})

    apt["barber_name"] = barber["name"] if barber else "Unknown"
    apt["service_name"] = service["name"] if service else "Unknown"
    return apt


@router.post("/public/sms-consent")
async def submit_sms_consent(request: SMSConsentRequest, raw_request: Request):
    client_ip = raw_request.client.host if raw_request.client else "unknown"
    if not check_rate_limit(f"sms-consent:{client_ip}", max_requests=10, window_seconds=3600):
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")

    shop_data = await db.shops.find_one({}, {"_id": 0})
    if not shop_data:
        raise HTTPException(status_code=500, detail="Shop not configured")

    shop = Shop(**shop_data)

    client_data = await db.clients.find_one({"shop_id": shop.id, "phone": request.phone}, {"_id": 0})
    consent_timestamp = datetime.now(timezone.utc).isoformat() if request.consent else None

    if client_data:
        await db.clients.update_one(
            {"id": client_data["id"]},
            {"$set": {
                "name": request.name,
                "sms_consent": request.consent,
                "sms_consent_timestamp": consent_timestamp,
                "sms_consent_source": "web_form",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
    else:
        client_data = {
            "id": str(uuid.uuid4()),
            "shop_id": shop.id,
            "name": request.name,
            "phone": request.phone,
            "sms_consent": request.consent,
            "sms_consent_timestamp": consent_timestamp,
            "sms_consent_source": "web_form",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.clients.insert_one(client_data)

    return {"message": "Consent recorded", "consent": request.consent}
