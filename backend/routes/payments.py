"""Stripe payment endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime, timezone
import uuid

from deps import db, get_shop
from models import Shop, AppointmentStatus
from providers import get_payment
from services.payment_service import apply_checkout_payment_update
from services.stripe_connect import build_connect_context

router = APIRouter()


@router.post("/payments/create-deposit/{appointment_id}")
async def create_deposit_payment(
    appointment_id: str,
    request: Request,
    shop: Shop = Depends(get_shop),
):
    appointment = await db.appointments.find_one({"id": appointment_id, "shop_id": shop.id}, {"_id": 0})
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if appointment.get("status") not in ("deposit_pending", "pending"):
        raise HTTPException(status_code=400, detail=f"Appointment status '{appointment.get('status')}' does not require a deposit")

    existing = await db.payment_transactions.find_one(
        {"appointment_id": appointment_id, "payment_status": "paid"}, {"_id": 0}
    )
    if existing:
        raise HTTPException(status_code=400, detail="Deposit already paid for this appointment")

    amount = float(shop.deposit_amount)
    connect_context = build_connect_context(shop, amount)

    client_data = await db.clients.find_one({"id": appointment["client_id"], "shop_id": shop.id}, {"_id": 0})

    origin = request.headers.get("x-origin", str(request.base_url).rstrip("/"))
    success_url = f"{origin}/payment/success?session_id={{CHECKOUT_SESSION_ID}}&appointment_id={appointment_id}"
    cancel_url = f"{origin}/payment/cancel?appointment_id={appointment_id}"

    metadata = {
        "appointment_id": appointment_id,
        "client_id": appointment["client_id"],
        "shop_id": shop.id,
        "type": "deposit",
    }

    payment = get_payment()
    payment_link = await payment.create_payment_link(
        amount=amount,
        currency="usd",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
        connect_account_id=connect_context["connect_account_id"],
        application_fee_amount=connect_context["application_fee_amount"],
    )

    await db.appointments.update_one(
        {"id": appointment_id},
        {"$set": {
            "deposit_required": True,
            "deposit_amount": amount,
            "status": AppointmentStatus.DEPOSIT_PENDING.value,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    await db.payment_transactions.insert_one({
        "id": str(uuid.uuid4()),
        "shop_id": shop.id,
        "client_id": appointment["client_id"],
        "client_name": client_data.get("name", "") if client_data else "",
        "appointment_id": appointment_id,
        "amount": amount,
        "currency": "usd",
        "session_id": payment_link.session_id,
        "payment_status": "initiated",
        "status": "pending",
        "payment_type": "deposit",
        "metadata": metadata,
        "connect_destination_account_id": connect_context["connect_account_id"],
        "platform_fee_bps": connect_context["platform_fee_bps"],
        "application_fee_amount": connect_context["application_fee_amount"],
        "created_at": now_iso,
        "updated_at": now_iso,
    })

    await db.payments.insert_one({
        "id": str(uuid.uuid4()),
        "shop_id": shop.id,
        "client_id": appointment["client_id"],
        "appointment_id": appointment_id,
        "amount": amount,
        "currency": "usd",
        "stripe_session_id": payment_link.session_id,
        "status": "pending",
        "payment_type": "deposit",
        "destination_account_id": connect_context["connect_account_id"],
        "platform_fee_bps": connect_context["platform_fee_bps"],
        "application_fee_amount": connect_context["application_fee_amount"],
        "created_at": now_iso,
        "updated_at": now_iso,
    })

    return {"checkout_url": payment_link.url, "session_id": payment_link.session_id}


@router.get("/payments/status/{session_id}")
async def get_payment_status(session_id: str, shop: Shop = Depends(get_shop)):
    txn = await db.payment_transactions.find_one({"session_id": session_id, "shop_id": shop.id}, {"_id": 0})
    if not txn:
        raise HTTPException(status_code=404, detail="Payment transaction not found")

    if txn.get("payment_status") == "paid":
        return {
            "status": txn["status"],
            "payment_status": "paid",
            "amount": txn["amount"],
            "appointment_id": txn.get("appointment_id"),
        }

    payment = get_payment()
    stripe_status = await payment.get_payment_status(session_id)

    if stripe_status.payment_status == "paid":
        await apply_checkout_payment_update(
            db,
            session_id=session_id,
            payment_status=stripe_status.payment_status,
            stripe_event_id=None,
            payment_intent_id=stripe_status.metadata.get("payment_intent_id"),
            destination_account_id=stripe_status.metadata.get("destination_account_id"),
            application_fee_amount=stripe_status.metadata.get("application_fee_amount"),
        )

    elif stripe_status.status == "expired":
        await apply_checkout_payment_update(
            db,
            session_id=session_id,
            payment_status=stripe_status.payment_status,
            checkout_status=stripe_status.status,
        )

    return {
        "status": stripe_status.status,
        "payment_status": stripe_status.payment_status,
        "amount": stripe_status.amount,
        "appointment_id": txn.get("appointment_id"),
    }


@router.post("/payments/charge-no-show-fee/{appointment_id}")
async def charge_no_show_fee(
    appointment_id: str,
    request: Request,
    shop: Shop = Depends(get_shop),
):
    """Create a no-show fee payment link and optionally SMS it to the client."""
    appointment = await db.appointments.find_one({"id": appointment_id, "shop_id": shop.id}, {"_id": 0})
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if appointment.get("status") != "no_show":
        raise HTTPException(status_code=400, detail="Can only charge no-show fee for appointments with status 'no_show'")

    # Check no duplicate fee
    existing = await db.payment_transactions.find_one(
        {"appointment_id": appointment_id, "payment_type": "no_show_fee", "payment_status": {"$in": ["initiated", "paid"]}},
        {"_id": 0}
    )
    if existing:
        raise HTTPException(status_code=400, detail="No-show fee already created for this appointment")

    amount = float(shop.deposit_amount)
    connect_context = build_connect_context(shop, amount)

    origin = request.headers.get("x-origin", str(request.base_url).rstrip("/"))
    success_url = f"{origin}/payment/success?session_id={{CHECKOUT_SESSION_ID}}&appointment_id={appointment_id}"
    cancel_url = f"{origin}/payment/cancel?appointment_id={appointment_id}"

    metadata = {
        "appointment_id": appointment_id,
        "client_id": appointment["client_id"],
        "shop_id": shop.id,
        "type": "no_show_fee",
    }

    payment = get_payment()
    payment_link = await payment.create_payment_link(
        amount=amount,
        currency="usd",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
        connect_account_id=connect_context["connect_account_id"],
        application_fee_amount=connect_context["application_fee_amount"],
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    await db.payment_transactions.insert_one({
        "id": str(uuid.uuid4()),
        "shop_id": shop.id,
        "client_id": appointment["client_id"],
        "appointment_id": appointment_id,
        "amount": amount,
        "currency": "usd",
        "session_id": payment_link.session_id,
        "payment_status": "initiated",
        "status": "pending",
        "payment_type": "no_show_fee",
        "metadata": metadata,
        "connect_destination_account_id": connect_context["connect_account_id"],
        "platform_fee_bps": connect_context["platform_fee_bps"],
        "application_fee_amount": connect_context["application_fee_amount"],
        "created_at": now_iso,
        "updated_at": now_iso,
    })

    await db.payments.insert_one({
        "id": str(uuid.uuid4()),
        "shop_id": shop.id,
        "client_id": appointment["client_id"],
        "appointment_id": appointment_id,
        "amount": amount,
        "currency": "usd",
        "stripe_session_id": payment_link.session_id,
        "status": "pending",
        "payment_type": "no_show_fee",
        "created_at": now_iso,
        "updated_at": now_iso,
    })

    return {"checkout_url": payment_link.url, "session_id": payment_link.session_id, "amount": amount}


@router.get("/payments/transactions")
async def list_payment_transactions(shop: Shop = Depends(get_shop), limit: int = 50, skip: int = 0):
    txns = await db.payment_transactions.find({"shop_id": shop.id}, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    total = await db.payment_transactions.count_documents({"shop_id": shop.id})
    return {"transactions": txns, "total": total}


@router.get("/mock-payment")
async def mock_payment_page(session_id: str):
    from providers.mock_providers import MockPaymentProvider

    payment = get_payment()
    if isinstance(payment, MockPaymentProvider):
        await payment.complete_payment(session_id)
        status = await payment.get_payment_status(session_id)
        appointment_id = status.metadata.get("appointment_id")
        if appointment_id:
            await db.appointments.update_one(
                {"id": appointment_id},
                {"$set": {"deposit_paid": True, "status": AppointmentStatus.DEPOSIT_PAID.value, "updated_at": datetime.now(timezone.utc).isoformat()}},
            )
            await db.payments.update_one(
                {"stripe_session_id": session_id},
                {"$set": {"status": "completed", "updated_at": datetime.now(timezone.utc).isoformat()}},
            )
        return {"status": "success", "message": "Mock payment completed", "session_id": session_id, "amount": status.amount}

    raise HTTPException(status_code=400, detail="Not in mock mode")
