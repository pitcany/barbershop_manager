"""Twilio inbound and Stripe payment webhooks."""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
import os
import logging

from deps import db
from models import Shop, AppointmentStatus
from providers import get_sms, get_payment, get_email
from providers.interfaces import SMSMessage, EmailMessage
from agents import FrontDeskAgent
from audit import create_audit_logger
from sms_compliance import is_opt_out_message, is_twilio_enabled
from revenue_logger import log_no_show_fee_on_payment_success

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/webhooks/twilio/inbound")
async def twilio_inbound_webhook(request: Request):
    form_data = await request.form()

    if is_twilio_enabled():
        sms = get_sms()
        signature = request.headers.get("X-Twilio-Signature", "")
        url = str(request.url)
        params = dict(form_data)
        is_valid = await sms.validate_webhook(url, params, signature)
        if not is_valid:
            logger.warning("Invalid Twilio webhook signature")
            raise HTTPException(status_code=403, detail="Invalid signature")

    from_number = form_data.get("From", "")
    to_number = form_data.get("To", "")
    body = form_data.get("Body", "").strip()

    if not from_number or not body:
        return JSONResponse(content={"status": "ignored", "reason": "missing data"})

    # Route to the correct shop by matching the Twilio "To" number
    shop_data = None
    if to_number:
        shop_data = await db.shops.find_one({"phone": to_number}, {"_id": 0})
    # Fallback: single-shop mode (one atomic query to avoid TOCTOU race)
    if not shop_data:
        fallback = await db.shops.find({}, {"_id": 0}).to_list(2)
        if len(fallback) == 1:
            shop_data = fallback[0]
    if not shop_data:
        logger.warning("No shop matched for inbound SMS to=%s", to_number)
        return JSONResponse(content={"status": "ignored", "reason": "no shop found"})

    shop = Shop(**shop_data)

    client = await db.clients.find_one({"shop_id": shop.id, "phone": from_number}, {"_id": 0})
    if not client:
        import uuid
        client = {
            "id": str(uuid.uuid4()),
            "shop_id": shop.id,
            "name": "Unknown",
            "phone": from_number,
            "sms_consent": True,
            "sms_consent_timestamp": datetime.now(timezone.utc).isoformat(),
            "sms_consent_source": "inbound_sms",
            "total_appointments": 0,
            "no_shows": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.clients.insert_one(client)
        client.pop("_id", None)

    import uuid as _uuid
    await db.messages.insert_one({
        "id": str(_uuid.uuid4()),
        "shop_id": shop.id,
        "client_id": client["id"],
        "direction": "inbound",
        "message_type": "sms",
        "content": body,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    if is_opt_out_message(body):
        await db.clients.update_one({"id": client["id"]}, {"$set": {"sms_consent": False, "sms_consent_timestamp": datetime.now(timezone.utc).isoformat()}})
        return JSONResponse(content={"status": "opt_out_processed"})

    from models import Client
    client_obj = Client(**{k: v for k, v in client.items() if k != "_id"})
    agent = FrontDeskAgent(db, shop)
    response_msg, metadata = await agent.process_inbound_message(client_obj, body)

    if response_msg:
        sms = get_sms()
        await sms.send_sms(SMSMessage(to=from_number, body=response_msg))
        await db.messages.insert_one({
            "id": str(_uuid.uuid4()),
            "shop_id": shop.id,
            "client_id": client["id"],
            "direction": "outbound",
            "message_type": "sms",
            "content": response_msg,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    audit = create_audit_logger(db, shop.id)
    await audit.log_event({
        "provider": "twilio",
        "action": "inbound_sms",
        "success": True,
        "details": {"from": from_number, "body_length": len(body), "response_sent": bool(response_msg)},
    })

    return JSONResponse(content={"status": "processed", "action": metadata.get("action") if metadata else None})


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("Stripe-Signature", "")

    payment = get_payment()
    result = await payment.handle_webhook(body, signature)

    if result.get("error"):
        logger.error(f"Stripe webhook error: {result['error']}")
        return JSONResponse(content={"status": "error"}, status_code=400)

    session_id = result.get("session_id")
    payment_status = result.get("payment_status")

    if session_id and payment_status:
        now_iso = datetime.now(timezone.utc).isoformat()

        if payment_status == "paid":
            txn_result = await db.payment_transactions.update_one(
                {"session_id": session_id, "payment_status": {"$ne": "paid"}},
                {"$set": {"payment_status": "paid", "status": "completed", "updated_at": now_iso}},
            )
            if txn_result.modified_count > 0:
                await db.payments.update_one(
                    {"stripe_session_id": session_id},
                    {"$set": {"status": "completed", "updated_at": now_iso}},
                )
                txn = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
                if txn and txn.get("appointment_id"):
                    await db.appointments.update_one(
                        {"id": txn["appointment_id"]},
                        {"$set": {"deposit_paid": True, "status": AppointmentStatus.DEPOSIT_PAID.value, "updated_at": now_iso}},
                    )
                    payment_record = await db.payments.find_one({"stripe_session_id": session_id}, {"_id": 0})
                    appointment = await db.appointments.find_one({"id": txn["appointment_id"]}, {"_id": 0})
                    if payment_record and appointment:
                        await log_no_show_fee_on_payment_success(db, payment_record, appointment)

        elif payment_status in ("unpaid", "no_payment_required"):
            await db.payment_transactions.update_one(
                {"session_id": session_id},
                {"$set": {"payment_status": payment_status, "status": "failed", "updated_at": now_iso}},
            )
            await db.payments.update_one(
                {"stripe_session_id": session_id},
                {"$set": {"status": "failed", "updated_at": now_iso}},
            )

    return JSONResponse(content={"status": "received"})
