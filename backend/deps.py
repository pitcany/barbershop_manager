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
mongo_url = os.environ.get('MONGO_URL')
_client = AsyncIOMotorClient(mongo_url)
db = _client[os.environ.get('DB_NAME')]

# Auth configuration
SECRET_KEY = os.environ.get('JWT_SECRET')
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


# ==================== RATE LIMITING ====================

_rate_limit_store: Dict[str, List[float]] = {}
_rate_limit_windows: Dict[str, int] = {}


def check_rate_limit(key: str, max_requests: int, window_seconds: int) -> bool:
    """Returns True if request is allowed, False if rate limited."""
    now = time.time()
    if key not in _rate_limit_store:
        _rate_limit_store[key] = []
        _rate_limit_windows[key] = window_seconds
    elif key not in _rate_limit_windows:
        _rate_limit_windows[key] = window_seconds
    # Remove expired entries
    _rate_limit_store[key] = [t for t in _rate_limit_store[key] if now - t < window_seconds]
    if not _rate_limit_store[key]:
        del _rate_limit_store[key]
        _rate_limit_windows.pop(key, None)
    if key not in _rate_limit_store:
        _rate_limit_store[key] = [now]
        _rate_limit_windows[key] = window_seconds
        return True
    if len(_rate_limit_store[key]) >= max_requests:
        return False
    _rate_limit_store[key].append(now)

    # Periodic cleanup
    if len(_rate_limit_store) > 10000:
        stale_keys = [
            k for k, timestamps in _rate_limit_store.items()
            if all(now - t > _rate_limit_windows.get(k, window_seconds) for t in timestamps)
        ]
        for k in stale_keys:
            del _rate_limit_store[k]
            _rate_limit_windows.pop(k, None)

    return True
