"""Google Calendar OAuth and event endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from datetime import datetime, timezone
from typing import Optional
import os
import logging

from deps import db, get_shop
from models import Shop
from providers import get_calendar, reset_providers

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/oauth/calendar/login")
async def google_calendar_login(request: Request, shop: Shop = Depends(get_shop)):
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    if not client_id:
        raise HTTPException(status_code=500, detail="Google Calendar not configured")

    origin = request.headers.get("x-origin", str(request.base_url).rstrip("/"))
    redirect_uri = f"{origin}/api/oauth/calendar/callback"

    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(
        {"web": {
            "client_id": client_id,
            "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }},
        scopes=["https://www.googleapis.com/auth/calendar"],
        redirect_uri=redirect_uri,
    )

    auth_url, state = flow.authorization_url(access_type="offline", prompt="consent")

    await db.oauth_states.insert_one({
        "state": state,
        "redirect_uri": redirect_uri,
        "shop_id": shop.id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    return {"authorization_url": auth_url}


@router.get("/oauth/calendar/callback")
async def google_calendar_callback(code: str, state: str = ""):
    import requests as http_requests

    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")

    state_doc = await db.oauth_states.find_one({"state": state}, {"_id": 0})
    redirect_uri = state_doc["redirect_uri"] if state_doc else ""

    if not redirect_uri:
        redirect_uri = f"{os.environ.get('REACT_APP_BACKEND_URL', '')}/api/oauth/calendar/callback"

    token_resp = http_requests.post("https://oauth2.googleapis.com/token", data={
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }).json()

    if "error" in token_resp:
        logger.error(f"Google OAuth error: {token_resp}")
        return RedirectResponse("/settings?calendar_error=auth_failed")

    user_info = http_requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {token_resp['access_token']}"},
    ).json()

    email = user_info.get("email", "")

    await db.google_calendar_tokens.update_one(
        {},
        {"$set": {
            "access_token": token_resp["access_token"],
            "refresh_token": token_resp.get("refresh_token"),
            "token_type": token_resp.get("token_type"),
            "expires_in": token_resp.get("expires_in"),
            "email": email,
            "connected_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )

    reset_providers()

    if state_doc:
        await db.oauth_states.delete_one({"state": state})

    logger.info(f"[GCAL] Google Calendar connected for {email}")
    return RedirectResponse("/settings?calendar_connected=true")


@router.get("/calendar/status")
async def get_calendar_status(shop: Shop = Depends(get_shop)):
    tokens = await db.google_calendar_tokens.find_one({}, {"_id": 0})
    connected = bool(tokens and tokens.get("access_token"))
    return {
        "connected": connected,
        "email": tokens.get("email", "") if connected else "",
        "connected_at": tokens.get("connected_at", "") if connected else "",
    }


@router.post("/calendar/disconnect")
async def disconnect_calendar(shop: Shop = Depends(get_shop)):
    await db.google_calendar_tokens.delete_many({})
    reset_providers()
    return {"message": "Google Calendar disconnected"}


@router.get("/calendar/events")
async def list_calendar_events(shop: Shop = Depends(get_shop)):
    calendar = get_calendar(db)

    from providers.real_providers import GoogleCalendarProvider

    if not isinstance(calendar, GoogleCalendarProvider):
        return {"events": [], "source": "mock"}

    service = await calendar._get_service()
    if not service:
        return {"events": [], "source": "not_connected"}

    try:
        now = datetime.now(timezone.utc).isoformat()
        result = service.events().list(
            calendarId="primary", timeMin=now, maxResults=20, singleEvents=True, orderBy="startTime"
        ).execute()

        events = []
        for e in result.get("items", []):
            events.append({
                "id": e["id"],
                "summary": e.get("summary", ""),
                "start": e.get("start", {}).get("dateTime", e.get("start", {}).get("date", "")),
                "end": e.get("end", {}).get("dateTime", e.get("end", {}).get("date", "")),
                "status": e.get("status", ""),
            })

        return {"events": events, "source": "google"}
    except Exception as e:
        logger.error(f"Failed to list calendar events: {e}")
        return {"events": [], "source": "error", "error": str(e)}
