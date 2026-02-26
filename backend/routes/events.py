"""SSE (Server-Sent Events) endpoint for real-time dashboard notifications."""
import json
import asyncio
import logging

from fastapi import APIRouter, Query, HTTPException
from starlette.responses import StreamingResponse

from deps import verify_token
from event_bus import subscribe, subscriber_count

logger = logging.getLogger(__name__)

router = APIRouter(tags=["events"])


@router.get("/events/stream")
async def event_stream(token: str = Query(..., description="JWT auth token")):
    """
    SSE endpoint.  Streams real-time events to the dashboard.

    Authentication is via query param because the browser EventSource API
    does not support custom headers.

    Events are JSON objects with fields: type, data, shop_id, timestamp.
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    async def generate():
        try:
            async for event in subscribe():
                # Filter by shop_id if the token contains one
                token_shop = payload.get("shop_id")
                if token_shop and event.get("shop_id") and event["shop_id"] != token_shop:
                    continue
                yield f"data: {json.dumps(event)}\n\n"
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.get("/events/health")
async def event_health():
    """Return the number of active SSE subscribers."""
    return {"subscribers": subscriber_count()}
