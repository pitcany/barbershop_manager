"""Super-admin shop management endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
import asyncio
import uuid

from deps import db, pwd_context, get_super_admin
from models import Shop, CreateShopRequest, CreateShopAdminRequest, UpdateShopDetailsRequest

router = APIRouter()


@router.get("/admin/platform-stats")
async def get_platform_stats(user: dict = Depends(get_super_admin)):
    """Aggregate stats across all shops for the platform overview."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    month_start = (now - timedelta(days=30)).isoformat()

    shop_count, total_clients, today_apts, month_apts, month_no_shows, revenue_agg, shops_list = await asyncio.gather(
        db.shops.count_documents({}),
        db.clients.count_documents({}),
        db.appointments.count_documents({"scheduled_at": {"$gte": today_start}}),
        db.appointments.count_documents({"scheduled_at": {"$gte": month_start}}),
        db.appointments.count_documents({"scheduled_at": {"$gte": month_start}, "status": "no_show"}),
        db.payment_transactions.aggregate([
            {"$match": {"status": "completed", "created_at": {"$gte": month_start}}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
        ]).to_list(1),
        db.shops.find({}, {"_id": 0, "id": 1, "name": 1, "slug": 1}).to_list(200),
    )

    revenue = revenue_agg[0]["total"] if revenue_agg else 0
    no_show_rate = round((month_no_shows / month_apts * 100), 1) if month_apts > 0 else 0

    # Per-shop breakdown
    shop_breakdown = []
    for shop in shops_list:
        sid = shop["id"]
        s_apts, s_no_shows, s_clients, s_rev = await asyncio.gather(
            db.appointments.count_documents({"shop_id": sid, "scheduled_at": {"$gte": month_start}}),
            db.appointments.count_documents({"shop_id": sid, "scheduled_at": {"$gte": month_start}, "status": "no_show"}),
            db.clients.count_documents({"shop_id": sid}),
            db.payment_transactions.aggregate([
                {"$match": {"shop_id": sid, "status": "completed", "created_at": {"$gte": month_start}}},
                {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
            ]).to_list(1),
        )
        shop_breakdown.append({
            "id": sid,
            "name": shop["name"],
            "slug": shop.get("slug", ""),
            "month_appointments": s_apts,
            "month_no_shows": s_no_shows,
            "no_show_rate": round((s_no_shows / s_apts * 100), 1) if s_apts > 0 else 0,
            "total_clients": s_clients,
            "month_revenue": s_rev[0]["total"] if s_rev else 0,
        })

    return {
        "total_shops": shop_count,
        "total_clients": total_clients,
        "today_appointments": today_apts,
        "month_appointments": month_apts,
        "month_no_shows": month_no_shows,
        "no_show_rate": no_show_rate,
        "month_revenue": revenue,
        "shop_breakdown": shop_breakdown,
    }

@router.get("/admin/shops")
async def list_shops(user: dict = Depends(get_super_admin)):
    """List all shops (super-admin only)."""
    shops = await db.shops.find(
        {}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)

    # Batch admin counts in one aggregation instead of N+1 queries
    if shops:
        shop_ids = [s["id"] for s in shops]
        counts = await db.admin_users.aggregate([
            {"$match": {"shop_id": {"$in": shop_ids}}},
            {"$group": {"_id": "$shop_id", "count": {"$sum": 1}}}
        ]).to_list(len(shop_ids))
        count_map = {c["_id"]: c["count"] for c in counts}
        for shop in shops:
            shop["admin_count"] = count_map.get(shop["id"], 0)

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
    # Derive defaults from the Shop model to avoid drift with hardcoded values
    shop_obj = Shop(
        id=shop_id,
        slug=body.slug,
        name=body.name,
        phone=body.phone,
        email=body.email or "",
        address=body.address or "",
        timezone=body.timezone,
    )
    shop = shop_obj.model_dump()
    shop["created_at"] = now_iso
    shop["updated_at"] = now_iso
    await db.shops.insert_one(shop)
    return {k: v for k, v in shop.items() if k != "_id"}


@router.patch("/admin/shops/{shop_id}")
async def update_shop(shop_id: str, body: UpdateShopDetailsRequest, user: dict = Depends(get_super_admin)):
    """Update a shop's details (super-admin only).

    Uses UpdateShopDetailsRequest which validates slug format and phone format.
    """
    shop = await db.shops.find_one({"id": shop_id}, {"_id": 0})
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    # exclude_unset=True ensures only caller-provided fields are included;
    # None values are kept so callers can explicitly clear optional fields
    update_data = body.model_dump(exclude_unset=True)

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
    """Create an admin user for a shop (super-admin only).

    Usernames must be globally unique (not per-shop) because the login
    endpoint authenticates by username alone without a shop selector.
    """
    shop = await db.shops.find_one({"id": shop_id}, {"_id": 0, "id": 1})
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    # Global uniqueness — login resolves by username without shop context
    existing = await db.admin_users.find_one({"username": body.username}, {"_id": 0, "id": 1})
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken across all shops. Choose a unique username.")

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
    return {k: v for k, v in admin.items() if k not in ("_id", "password_hash")}


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
