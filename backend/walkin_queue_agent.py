"""
Walk-in Queue Agent — business logic for live walk-in queue management.
Handles joining, position tracking, notifications, and queue advancement.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List

from models import (
    WalkInQueueStatus, EventType, Shop, MessageDirection,
    generate_id,
)
from providers import get_sms
from audit import create_audit_logger
from sms_compliance import create_sms_service

logger = logging.getLogger(__name__)

# Active statuses (client still in the queue or being served)
ACTIVE_STATUSES = [
    WalkInQueueStatus.WAITING.value,
    WalkInQueueStatus.NOTIFIED.value,
]

SERVING_STATUSES = [
    WalkInQueueStatus.SERVING.value,
]

ALL_ACTIVE = ACTIVE_STATUSES + SERVING_STATUSES


class WalkInQueueAgent:
    """Manages the live walk-in queue for a shop."""

    def __init__(self, db, shop: Shop):
        self.db = db
        self.shop = shop
        audit_logger = create_audit_logger(db, shop.id)
        self.sms_service = create_sms_service(db, shop.id, audit_logger)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def join_queue(
        self,
        client: dict,
        service_id: Optional[str] = None,
        barber_id: Optional[str] = None,
        source: str = "sms",
    ) -> dict:
        """Add a client to the walk-in queue. Returns the new entry dict."""
        max_size = self.shop.walkin_max_queue_size

        # Check if client already waiting
        existing = await self.db.walkin_queue.find_one({
            "shop_id": self.shop.id,
            "client_id": client["id"],
            "status": {"$in": ACTIVE_STATUSES},
        }, {"_id": 0})
        if existing:
            pos = await self._calc_position(existing)
            wait = self._estimate_wait(pos, service_id)
            existing["position"] = pos
            existing["estimated_wait_minutes"] = wait
            return existing

        # Check queue capacity
        queue_size = await self.db.walkin_queue.count_documents({
            "shop_id": self.shop.id,
            "status": {"$in": ACTIVE_STATUSES},
        })
        if queue_size >= max_size:
            return {"error": "queue_full", "max_size": max_size}

        now = datetime.now(timezone.utc)
        position = queue_size + 1
        wait = self._estimate_wait(position, service_id)

        entry = {
            "id": generate_id(),
            "shop_id": self.shop.id,
            "client_id": client["id"],
            "barber_id": barber_id,
            "service_id": service_id,
            "position": position,
            "joined_at": now.isoformat(),
            "estimated_wait_minutes": wait,
            "status": WalkInQueueStatus.WAITING.value,
            "notified_at": None,
            "serving_at": None,
            "completed_at": None,
            "assigned_barber_id": None,
            "source": source,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        await self.db.walkin_queue.insert_one(entry)
        entry.pop("_id", None)

        # Log event
        await self._log_event(
            EventType.WALKIN_JOINED,
            client_id=client["id"],
            data={"position": position, "wait_minutes": wait, "source": source},
        )

        return entry

    async def get_client_position(self, client_id: str) -> Optional[dict]:
        """Return the client's current queue entry with recalculated position."""
        entry = await self.db.walkin_queue.find_one({
            "shop_id": self.shop.id,
            "client_id": client_id,
            "status": {"$in": ACTIVE_STATUSES},
        }, {"_id": 0})
        if not entry:
            return None
        pos = await self._calc_position(entry)
        entry["position"] = pos
        entry["estimated_wait_minutes"] = self._estimate_wait(pos, entry.get("service_id"))
        return entry

    async def get_active_queue(self, include_serving: bool = True) -> List[dict]:
        """Return all active queue entries sorted by joined_at."""
        statuses = ALL_ACTIVE if include_serving else ACTIVE_STATUSES
        entries = await self.db.walkin_queue.find(
            {"shop_id": self.shop.id, "status": {"$in": statuses}},
            {"_id": 0},
        ).sort("joined_at", 1).to_list(100)

        # Recalculate positions
        waiting_pos = 0
        for e in entries:
            if e["status"] in ACTIVE_STATUSES:
                waiting_pos += 1
                e["position"] = waiting_pos
                e["estimated_wait_minutes"] = self._estimate_wait(waiting_pos, e.get("service_id"))
            else:
                e["position"] = 0  # serving — no wait
        return entries

    async def advance_queue(
        self,
        entry_id: str,
        new_status: str,
        assigned_barber_id: Optional[str] = None,
    ) -> Optional[dict]:
        """Transition a queue entry's status."""
        entry = await self.db.walkin_queue.find_one(
            {"id": entry_id, "shop_id": self.shop.id}, {"_id": 0}
        )
        if not entry:
            return None

        now = datetime.now(timezone.utc).isoformat()
        update: Dict = {"status": new_status, "updated_at": now}

        if new_status == WalkInQueueStatus.SERVING.value:
            update["serving_at"] = now
            if assigned_barber_id:
                update["assigned_barber_id"] = assigned_barber_id
        elif new_status == WalkInQueueStatus.COMPLETED.value:
            update["completed_at"] = now
        elif new_status == WalkInQueueStatus.LEFT.value:
            update["completed_at"] = now

        await self.db.walkin_queue.update_one(
            {"id": entry_id}, {"$set": update}
        )

        event_map = {
            WalkInQueueStatus.SERVING.value: EventType.WALKIN_SERVING,
            WalkInQueueStatus.COMPLETED.value: EventType.WALKIN_COMPLETED,
            WalkInQueueStatus.LEFT.value: EventType.WALKIN_LEFT,
        }
        if new_status in event_map:
            await self._log_event(
                event_map[new_status],
                client_id=entry["client_id"],
                data={"entry_id": entry_id},
            )

        # Check if we should notify the next person
        if new_status in (WalkInQueueStatus.SERVING.value, WalkInQueueStatus.COMPLETED.value, WalkInQueueStatus.LEFT.value):
            await self._check_and_notify_next()

        entry.update(update)
        return entry

    async def remove_from_queue(self, entry_id: str) -> bool:
        """Mark an entry as LEFT."""
        result = await self.advance_queue(entry_id, WalkInQueueStatus.LEFT.value)
        return result is not None

    async def get_queue_stats(self) -> dict:
        """Return summary stats for the queue."""
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

        waiting = await self.db.walkin_queue.count_documents({
            "shop_id": self.shop.id,
            "status": {"$in": ACTIVE_STATUSES},
        })
        serving = await self.db.walkin_queue.count_documents({
            "shop_id": self.shop.id,
            "status": WalkInQueueStatus.SERVING.value,
        })
        served_today = await self.db.walkin_queue.count_documents({
            "shop_id": self.shop.id,
            "status": WalkInQueueStatus.COMPLETED.value,
            "completed_at": {"$gte": today_start},
        })

        # Average wait today (completed entries)
        completed_today = await self.db.walkin_queue.find(
            {
                "shop_id": self.shop.id,
                "status": WalkInQueueStatus.COMPLETED.value,
                "completed_at": {"$gte": today_start},
                "serving_at": {"$ne": None},
            },
            {"_id": 0, "joined_at": 1, "serving_at": 1},
        ).to_list(200)

        avg_wait = 0
        if completed_today:
            waits = []
            for e in completed_today:
                try:
                    j = datetime.fromisoformat(str(e["joined_at"]).replace("Z", "+00:00"))
                    s = datetime.fromisoformat(str(e["serving_at"]).replace("Z", "+00:00"))
                    waits.append((s - j).total_seconds() / 60)
                except Exception:
                    pass
            if waits:
                avg_wait = round(sum(waits) / len(waits))

        avg_service = self.shop.walkin_avg_service_minutes

        return {
            "current_queue_size": waiting,
            "currently_serving": serving,
            "served_today": served_today,
            "avg_wait_today": avg_wait,
            "next_estimated_wait_minutes": waiting * avg_service,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _calc_position(self, entry: dict) -> int:
        """Calculate an entry's current position among waiting entries."""
        ahead = await self.db.walkin_queue.count_documents({
            "shop_id": self.shop.id,
            "status": {"$in": ACTIVE_STATUSES},
            "joined_at": {"$lt": entry["joined_at"]},
        })
        return ahead + 1

    def _estimate_wait(self, position: int, service_id: Optional[str] = None) -> int:
        """Estimate wait in minutes based on position."""
        avg = self.shop.walkin_avg_service_minutes
        return max(0, (position - 1) * avg)

    async def _check_and_notify_next(self):
        """Send 'you're next' SMS to the client at the notify position."""
        notify_pos = self.shop.walkin_notify_position

        # Get waiting entries sorted by joined_at
        waiting = await self.db.walkin_queue.find(
            {"shop_id": self.shop.id, "status": WalkInQueueStatus.WAITING.value},
            {"_id": 0},
        ).sort("joined_at", 1).to_list(notify_pos + 1)

        if len(waiting) < notify_pos:
            return

        target = waiting[notify_pos - 1]

        # Already notified?
        if target["status"] == WalkInQueueStatus.NOTIFIED.value:
            return

        # Fetch client
        client = await self.db.clients.find_one(
            {"id": target["client_id"]}, {"_id": 0, "phone": 1, "name": 1}
        )
        if not client:
            return

        # Update status to notified
        now = datetime.now(timezone.utc).isoformat()
        await self.db.walkin_queue.update_one(
            {"id": target["id"]},
            {"$set": {"status": WalkInQueueStatus.NOTIFIED.value, "notified_at": now, "updated_at": now}},
        )

        # Send SMS
        message = (
            f"Heads up! You're next in line at {self.shop.name}. "
            f"Please be ready — your barber will be with you shortly!"
        )
        try:
            await self.sms_service.send_sms(
                client_id=target["client_id"],
                to_phone=client["phone"],
                message=message,
            )

            # Log outbound message
            await self.db.messages.insert_one({
                "id": generate_id(),
                "shop_id": self.shop.id,
                "client_id": target["client_id"],
                "direction": MessageDirection.OUTBOUND.value,
                "message_type": "sms",
                "content": message,
                "created_at": now,
            })
        except Exception as exc:
            logger.error(f"Failed to send queue notification: {exc}")

        await self._log_event(
            EventType.WALKIN_NOTIFIED,
            client_id=target["client_id"],
            data={"entry_id": target["id"], "position": notify_pos},
        )

    async def _log_event(
        self,
        event_type: EventType,
        client_id: Optional[str] = None,
        data: Optional[dict] = None,
    ):
        """Non-blocking event log."""
        try:
            await self.db.events.insert_one({
                "id": generate_id(),
                "shop_id": self.shop.id,
                "event_type": event_type.value,
                "client_id": client_id,
                "data": data or {},
                "revenue_impact": 0.0,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as exc:
            logger.error(f"Failed to log event {event_type}: {exc}")
