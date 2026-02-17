"""Super-admin shop management endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
import uuid

from deps import db, pwd_context, get_super_admin
from models import Shop, CreateShopRequest, CreateShopAdminRequest, UpdateShopDetailsRequest

router = APIRouter()


@router.get("/admin/shops")
async def list_shops(user: dict = Depends(get_super_admin)):
    """List all shops (super-admin only)."""
    shops = await db.shops.find(
        {}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    # Attach admin count per shop
    for shop in shops:
        shop["admin_count"] = await db.admin_users.count_documents({"shop_id": shop["id"]})
    return {"shops": shops}


@router.post("/admin/shops")
async def create_shop(body: CreateShopRequest, user: dict = Depends(get_super_admin)):
    """Create a new shop (super-admin only)."""
    # Check slug uniqueness
    existing = await db.shops.find_one({"slug": body.slug}, {"_id": 0, "id": 1})
    if existing:
        raise HTTPException(status_code=409, detail="A shop with this slug already exists")

    # Check phone uniqueness (important for Twilio webhook routing)
    existing_phone = await db.shops.find_one({"phone": body.phone}, {"_id": 0, "id": 1})
    if existing_phone:
        raise HTTPException(status_code=409, detail="A shop with this phone number already exists")

    now_iso = datetime.now(timezone.utc).isoformat()
    shop_id = str(uuid.uuid4())
    shop = {
        "id": shop_id,
        "slug": body.slug,
        "name": body.name,
        "phone": body.phone,
        "email": body.email or "",
        "address": body.address or "",
        "timezone": body.timezone,
        "business_hours": {
            "monday": {"open": "09:00", "close": "18:00"},
            "tuesday": {"open": "09:00", "close": "18:00"},
            "wednesday": {"open": "09:00", "close": "18:00"},
            "thursday": {"open": "09:00", "close": "18:00"},
            "friday": {"open": "09:00", "close": "18:00"},
            "saturday": {"open": "09:00", "close": "17:00"},
            "sunday": None,
        },
        "deposit_amount": 20.0,
        "deposit_required_hours": 48,
        "confirmation_window_hours": 24,
        "cancellation_window_hours": 4,
        "max_messages_per_day": 4,
        "retention_enabled": True,
        "retention_lapse_weeks": 4,
        "retention_cooldown_days": 7,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    await db.shops.insert_one(shop)
    shop.pop("_id", None)
    return shop


@router.patch("/admin/shops/{shop_id}")
async def update_shop(shop_id: str, body: UpdateShopDetailsRequest, user: dict = Depends(get_super_admin)):
    """Update a shop's details (super-admin only).

    Uses UpdateShopDetailsRequest which validates slug format and phone format.
    """
    shop = await db.shops.find_one({"id": shop_id}, {"_id": 0})
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    update_data = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}

    if "slug" in update_data and update_data["slug"] != shop.get("slug"):
        existing = await db.shops.find_one({"slug": update_data["slug"], "id": {"$ne": shop_id}}, {"_id": 0, "id": 1})
        if existing:
            raise HTTPException(status_code=409, detail="A shop with this slug already exists")

    if "phone" in update_data and update_data["phone"] != shop.get("phone"):
        existing = await db.shops.find_one({"phone": update_data["phone"], "id": {"$ne": shop_id}}, {"_id": 0, "id": 1})
        if existing:
            raise HTTPException(status_code=409, detail="A shop with this phone number already exists")

    if update_data:
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.shops.update_one({"id": shop_id}, {"$set": update_data})

    updated = await db.shops.find_one({"id": shop_id}, {"_id": 0})
    return updated


@router.post("/admin/shops/{shop_id}/admins")
async def create_shop_admin(shop_id: str, body: CreateShopAdminRequest, user: dict = Depends(get_super_admin)):
    """Create an admin user for a shop (super-admin only)."""
    shop = await db.shops.find_one({"id": shop_id}, {"_id": 0, "id": 1})
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    existing = await db.admin_users.find_one({"username": body.username}, {"_id": 0, "id": 1})
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken")

    now_iso = datetime.now(timezone.utc).isoformat()
    admin = {
        "id": str(uuid.uuid4()),
        "shop_id": shop_id,
        "username": body.username,
        "password_hash": pwd_context.hash(body.password),
        "role": "shop_admin",
        "created_at": now_iso,
    }
    await db.admin_users.insert_one(admin)
    admin.pop("_id", None)
    admin.pop("password_hash", None)
    return admin


@router.get("/admin/shops/{shop_id}/admins")
async def list_shop_admins(shop_id: str, user: dict = Depends(get_super_admin)):
    """List admins for a shop (super-admin only)."""
    shop = await db.shops.find_one({"id": shop_id}, {"_id": 0, "id": 1})
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    admins = await db.admin_users.find(
        {"shop_id": shop_id},
        {"_id": 0, "password_hash": 0}
    ).to_list(50)
    return {"admins": admins}
