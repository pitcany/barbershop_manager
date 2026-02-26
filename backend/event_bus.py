"""
In-process async event bus for real-time dashboard notifications.

Publishes typed events to all connected SSE subscribers.
Fire-and-forget — publish() never raises, never blocks callers.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, Any, Optional, Set

logger = logging.getLogger(__name__)

# Singleton set of subscriber queues
_subscribers: Set[asyncio.Queue] = set()


async def publish(
    event_type: str,
    data: Optional[Dict[str, Any]] = None,
    shop_id: Optional[str] = None,
) -> None:
    """
    Broadcast an event to all connected SSE clients.

    Never raises — failures are logged and swallowed so callers
    are never blocked by notification infrastructure.

    Args:
        event_type: e.g. "new_booking", "no_show", "waitlist_filled", "deposit_paid"
        data: arbitrary payload dict
        shop_id: scope events to a specific shop (future multi-tenant filtering)
    """
    event = {
        "type": event_type,
        "data": data or {},
        "shop_id": shop_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    dead = []
    for q in _subscribers:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            dead.append(q)
        except Exception:
            dead.append(q)
    # Clean up dead/full queues
    for q in dead:
        _subscribers.discard(q)


async def subscribe() -> AsyncGenerator[Dict[str, Any], None]:
    """
    Yields events as they arrive.  Each caller gets its own queue.

    Usage::

        async for event in subscribe():
            yield f"data: {json.dumps(event)}\\n\\n"
    """
    q: asyncio.Queue = asyncio.Queue(maxsize=50)
    _subscribers.add(q)
    try:
        while True:
            event = await q.get()
            yield event
    finally:
        _subscribers.discard(q)


def subscriber_count() -> int:
    """Return the number of active SSE subscribers (for health checks)."""
    return len(_subscribers)
