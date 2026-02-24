"""Shared payment transition logic for status polling and webhook processing."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from models import AppointmentStatus
from revenue_logger import log_no_show_fee_on_payment_success


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def apply_checkout_payment_update(
    db,
    *,
    session_id: str,
    payment_status: Optional[str],
    checkout_status: Optional[str] = None,
    stripe_event_id: Optional[str] = None,
    payment_intent_id: Optional[str] = None,
    destination_account_id: Optional[str] = None,
    application_fee_amount: Optional[int] = None,
) -> Dict[str, Any]:
    """Apply idempotent payment state transitions from Stripe session events."""
    txn = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not txn:
        return {"found": False, "updated": False}

    now_iso = _now_iso()
    normalized = (payment_status or "").lower()
    txn_update: Dict[str, Any] = {"updated_at": now_iso}
    payment_update: Dict[str, Any] = {"updated_at": now_iso}

    if stripe_event_id:
        txn_update["stripe_event_id"] = stripe_event_id
        payment_update["stripe_event_id"] = stripe_event_id
    if payment_intent_id:
        txn_update["stripe_payment_intent_id"] = payment_intent_id
        payment_update["stripe_payment_intent_id"] = payment_intent_id
    if destination_account_id:
        txn_update["destination_account_id"] = destination_account_id
        payment_update["destination_account_id"] = destination_account_id
    if application_fee_amount is not None:
        txn_update["application_fee_amount"] = application_fee_amount
        payment_update["application_fee_amount"] = application_fee_amount

    changed = False

    if normalized == "paid":
        txn_update.update({"payment_status": "paid", "status": "completed"})
        payment_update.update({"status": "completed"})

        txn_result = await db.payment_transactions.update_one(
            {"session_id": session_id, "payment_status": {"$ne": "paid"}},
            {"$set": txn_update},
        )
        if txn_result.modified_count > 0:
            changed = True
            await db.payments.update_one(
                {"stripe_session_id": session_id},
                {"$set": payment_update},
            )

            appointment_id = txn.get("appointment_id")
            if appointment_id:
                await db.appointments.update_one(
                    {"id": appointment_id},
                    {
                        "$set": {
                            "deposit_paid": True,
                            "status": AppointmentStatus.DEPOSIT_PAID.value,
                            "updated_at": now_iso,
                        }
                    },
                )

                payment_record = await db.payments.find_one(
                    {"stripe_session_id": session_id}, {"_id": 0}
                )
                appointment = await db.appointments.find_one(
                    {"id": appointment_id}, {"_id": 0}
                )
                if payment_record and appointment:
                    await log_no_show_fee_on_payment_success(db, payment_record, appointment)

    elif normalized in ("unpaid", "no_payment_required") or checkout_status == "expired":
        failed_status = "expired" if checkout_status == "expired" else "failed"
        txn_update.update({"payment_status": normalized or "unpaid", "status": failed_status})
        payment_update.update({"status": "failed"})

        txn_result = await db.payment_transactions.update_one(
            {
                "session_id": session_id,
                "payment_status": {"$ne": "paid"},
                "status": {"$ne": "completed"},
            },
            {"$set": txn_update},
        )
        if txn_result.modified_count > 0:
            changed = True
            await db.payments.update_one(
                {"stripe_session_id": session_id, "status": {"$ne": "completed"}},
                {"$set": payment_update},
            )

    return {"found": True, "updated": changed}
