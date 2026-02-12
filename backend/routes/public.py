"""Public endpoints (no auth required)."""
from fastapi import APIRouter, HTTPException, Request
from datetime import datetime, timezone

from deps import db, check_rate_limit
from models import Shop, SMSConsentRequest

router = APIRouter()


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
        import uuid
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


@router.get("/public/shop-info")
async def get_public_shop_info():
    shop_data = await db.shops.find_one({}, {"_id": 0, "name": 1, "phone": 1, "address": 1, "business_hours": 1})
    if not shop_data:
        raise HTTPException(status_code=404, detail="Shop not found")
    return shop_data
