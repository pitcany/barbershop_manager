"""
Shared dependencies for route modules.
Provides db access, auth, and rate limiting.
"""
from fastapi import Depends, HTTPException, Header
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime, timezone, timedelta
import os
import time
import jwt
from passlib.context import CryptContext

from models import Shop

# Load environment
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection (singleton)
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
_client = AsyncIOMotorClient(mongo_url)
db = _client[os.environ.get('DB_NAME', 'barbershop_autopilot')]

# Auth configuration
SECRET_KEY = os.environ.get('JWT_SECRET', 'barbershop-autopilot-secret-key-change-in-production')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ==================== AUTH UTILITIES ====================

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ")[1]
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


async def get_shop(user: dict = Depends(get_current_user)) -> Shop:
    """Get the shop for the current user"""
    shop_data = await db.shops.find_one({"id": user.get("shop_id")}, {"_id": 0})
    if not shop_data:
        raise HTTPException(status_code=404, detail="Shop not found")
    return Shop(**shop_data)


async def get_super_admin(user: dict = Depends(get_current_user)) -> dict:
    """Require super-admin role for shop management endpoints."""
    admin = await db.admin_users.find_one({"id": user.get("sub")}, {"_id": 0, "role": 1})
    if not admin or admin.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super-admin access required")
    return user


# ==================== RATE LIMITING ====================

_rate_limit_store: Dict[str, List[float]] = {}
_rate_limit_windows: Dict[str, int] = {}


async def check_rate_limit(key: str, max_requests: int, window_seconds: int) -> bool:
    """Returns True if request is allowed, False if rate limited.
    
    Uses MongoDB so rate limits are shared across multiple workers.
    Expired entries are cleaned up automatically via a TTL index on
    the ``rate_limit_entries`` collection (created at startup).
    """
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(seconds=window_seconds)
    
    count = await db.rate_limit_entries.count_documents({
        "key": key,
        "timestamp": {"$gte": window_start},
    })
    
    if count >= max_requests:
        return False
    
    await db.rate_limit_entries.insert_one({
        "key": key,
        "timestamp": now,
        "expires_at": now + timedelta(seconds=window_seconds),
    })
    return True


# ==================== QUERY UTILITIES ====================

async def batch_fetch_map(
    collection,
    ids: list,
    projection: dict | None = None,
    id_field: str = "id",
) -> dict:
    """Batch-fetch documents by ID list, return {id: doc} map.

    Eliminates N+1 query patterns by replacing N individual find_one()
    calls with a single $in query.

    Args:
        collection: Motor collection to query.
        ids: List of document IDs to fetch.
        projection: Optional field projection (e.g. {"name": 1, "phone": 1}).
                    Always excludes _id automatically.
        id_field: The field name used as the document identifier (default "id").

    Returns:
        Dict mapping id -> document for all found documents.
    """
    if not ids:
        return {}
    unique_ids = list(set(ids))
    proj = {"_id": 0, **(projection or {})}
    docs = await collection.find(
        {id_field: {"$in": unique_ids}}, proj
    ).to_list(len(unique_ids))
    return {doc[id_field]: doc for doc in docs}
