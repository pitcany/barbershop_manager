"""Twilio inbound and Stripe payment webhooks."""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
import logging
from pymongo.errors import DuplicateKeyError

from deps import db
from models import Shop, AuditProvider, AuditAction
from providers import get_sms, get_payment
from providers.interfaces import SMSMessage
from agents import FrontDeskAgent
from audit import create_audit_logger
from sms_compliance import is_opt_out_message, is_twilio_enabled
from services.payment_service import apply_checkout_payment_update

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
    await audit.log(
        provider=AuditProvider.TWILIO,
        action=AuditAction.RECEIVE_SMS,
        entity_type="client",
        entity_id=client["id"],
        success=True,
        metadata={"from": from_number, "body_length": len(body), "response_sent": bool(response_msg)},
    )

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
    event_id = result.get("event_id")
    event_type = result.get("event_type")

    if event_id:
        try:
            await db.stripe_webhook_events.insert_one(
                {
                    "stripe_event_id": event_id,
                    "event_type": event_type,
                    "session_id": session_id,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        except DuplicateKeyError:
            return JSONResponse(content={"status": "duplicate_ignored", "event_id": event_id})

    if session_id and payment_status:
        await apply_checkout_payment_update(
            db,
            session_id=session_id,
            payment_status=payment_status,
            stripe_event_id=event_id,
            checkout_status=result.get("checkout_status"),
            payment_intent_id=result.get("payment_intent_id"),
            destination_account_id=result.get("destination_account_id"),
            application_fee_amount=result.get("application_fee_amount"),
        )

    return JSONResponse(content={"status": "received", "event_id": event_id})
