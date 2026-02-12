"""Stripe payment endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
from typing import Optional
import uuid
import logging

from deps import db, get_shop
from models import Shop, AppointmentStatus
from providers import get_payment
from revenue_logger import log_no_show_fee_on_payment_success

logger = logging.getLogger(__name__)

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
        amount=amount, currency="usd", success_url=success_url, cancel_url=cancel_url, metadata=metadata
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

    now_iso = datetime.now(timezone.utc).isoformat()

    if stripe_status.payment_status == "paid":
        result = await db.payment_transactions.update_one(
            {"session_id": session_id, "payment_status": {"$ne": "paid"}},
            {"$set": {"payment_status": "paid", "status": "completed", "updated_at": now_iso}},
        )
        if result.modified_count > 0:
            await db.payments.update_one(
                {"stripe_session_id": session_id},
                {"$set": {"status": "completed", "updated_at": now_iso}},
            )
            appointment_id = txn.get("appointment_id")
            if appointment_id:
                await db.appointments.update_one(
                    {"id": appointment_id},
                    {"$set": {"deposit_paid": True, "status": AppointmentStatus.DEPOSIT_PAID.value, "updated_at": now_iso}},
                )
                payment_record = await db.payments.find_one({"stripe_session_id": session_id}, {"_id": 0})
                appointment = await db.appointments.find_one({"id": appointment_id}, {"_id": 0})
                if payment_record and appointment:
                    await log_no_show_fee_on_payment_success(db, payment_record, appointment)

    elif stripe_status.status == "expired":
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {"payment_status": "expired", "status": "expired", "updated_at": now_iso}},
        )
        await db.payments.update_one(
            {"stripe_session_id": session_id},
            {"$set": {"status": "failed", "updated_at": now_iso}},
        )

    return {
        "status": stripe_status.status,
        "payment_status": stripe_status.payment_status,
        "amount": stripe_status.amount,
        "appointment_id": txn.get("appointment_id"),
    }


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
