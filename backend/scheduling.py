"""
Scheduling Engine with Conflict Prevention
Handles time-slot availability, double-booking prevention, and business hours validation.
"""
import logging
from datetime import datetime, timedelta, timezone, time
from typing import List, Optional, Dict, Tuple
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


class TimeSlot:
    """Represents an available time slot"""
    def __init__(self, start: datetime, end: datetime, barber_id: str, barber_name: str):
        self.start = start
        self.end = end
        self.barber_id = barber_id
        self.barber_name = barber_name
    
    def to_dict(self) -> dict:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "barber_id": self.barber_id,
            "barber_name": self.barber_name
        }


class SchedulingEngine:
    """
    Handles appointment scheduling with conflict prevention.
    
    Features:
    - Time-slot generation based on business hours
    - Double-booking prevention
    - Barber availability checking
    - Business hours validation
    """
    
    SLOT_DURATION_MINUTES = 30  # Default slot duration
    
    def __init__(self, db, shop: dict):
        self.db = db
        self.shop = shop
        self.shop_id = shop.get("id")
        self.business_hours = shop.get("business_hours", {})
        self.shop_tz = ZoneInfo(shop.get("timezone", "America/New_York"))
    
    def _get_day_hours(self, date: datetime, barber_schedule: Optional[dict] = None) -> Optional[Tuple[time, time]]:
        """Get working hours for a specific day.
        If barber_schedule is provided and has an entry for this day, use it.
        Otherwise fall back to shop business hours."""
        day_name = date.strftime("%A").lower()

        # Check barber-specific schedule first
        hours = None
        if barber_schedule and day_name in barber_schedule:
            hours = barber_schedule.get(day_name)
        else:
            hours = self.business_hours.get(day_name)

        if not hours:
            return None

        try:
            open_time = datetime.strptime(hours["open"], "%H:%M").time()
            close_time = datetime.strptime(hours["close"], "%H:%M").time()
            return (open_time, close_time)
        except (KeyError, ValueError):
            return None

    async def _get_barber_schedule_data(self, barber_id: str) -> Optional[dict]:
        """Fetch barber-specific schedule from DB, or None."""
        barber = await self.db.barbers.find_one(
            {"id": barber_id, "shop_id": self.shop_id},
            {"_id": 0, "schedule": 1}
        )
        if barber and barber.get("schedule"):
            return barber["schedule"]
        return None

    def _is_within_business_hours(self, dt: datetime, duration_minutes: int = 30, barber_schedule: Optional[dict] = None) -> bool:
        """Check if a datetime falls within business hours"""
        # Convert to shop timezone
        local_dt = dt.astimezone(self.shop_tz)
        hours = self._get_day_hours(local_dt, barber_schedule)

        if not hours:
            return False

        open_time, close_time = hours
        slot_time = local_dt.time()
        end_time = (local_dt + timedelta(minutes=duration_minutes)).time()

        return slot_time >= open_time and end_time <= close_time
    
    async def check_barber_availability(
        self,
        barber_id: str,
        start_time: datetime,
        end_time: datetime,
        exclude_appointment_id: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a barber is available for a time slot.
        
        Returns (is_available, conflict_reason)
        """
        # Build query for conflicting appointments
        query = {
            "shop_id": self.shop_id,
            "barber_id": barber_id,
            "status": {"$nin": ["cancelled", "no_show"]},
        }
        
        if exclude_appointment_id:
            query["id"] = {"$ne": exclude_appointment_id}
        
        # Find all appointments for this barber on the same day
        day_start = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        
        query["scheduled_at"] = {
            "$gte": day_start.isoformat(),
            "$lt": day_end.isoformat()
        }
        
        existing_appointments = await self.db.appointments.find(
            query, {"_id": 0, "id": 1, "scheduled_at": 1, "duration_minutes": 1}
        ).to_list(100)
        
        # Check for overlaps
        for apt in existing_appointments:
            apt_start = datetime.fromisoformat(apt["scheduled_at"].replace("Z", "+00:00"))
            apt_duration = apt.get("duration_minutes", 30)
            apt_end = apt_start + timedelta(minutes=apt_duration)
            
            # Check if there's any overlap
            if start_time < apt_end and end_time > apt_start:
                return (False, f"Conflicts with existing appointment from {apt_start.strftime('%I:%M %p')} to {apt_end.strftime('%I:%M %p')}")
        
        return (True, None)
    
    async def validate_appointment_slot(
        self,
        barber_id: str,
        scheduled_at: datetime,
        duration_minutes: int,
        exclude_appointment_id: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate that an appointment slot is available.

        Returns (is_valid, error_message)
        """
        # Fetch barber-specific schedule (if any)
        barber_sched = await self._get_barber_schedule_data(barber_id)

        # Check business hours (barber-specific or shop default)
        if not self._is_within_business_hours(scheduled_at, duration_minutes, barber_sched):
            return (False, "Appointment time is outside business hours")

        # Check if appointment is in the past
        if scheduled_at < datetime.now(timezone.utc):
            return (False, "Cannot schedule appointments in the past")

        # Check barber availability
        end_time = scheduled_at + timedelta(minutes=duration_minutes)
        is_available, conflict = await self.check_barber_availability(
            barber_id, scheduled_at, end_time, exclude_appointment_id
        )

        if not is_available:
            return (False, f"Time slot unavailable: {conflict}")

        return (True, None)
    
    async def get_available_slots(
        self,
        date: datetime,
        barber_id: Optional[str] = None,
        duration_minutes: int = 30
    ) -> List[TimeSlot]:
        """
        Get available time slots for a given date.

        Args:
            date: The date to check
            barber_id: Optional specific barber (if None, checks all barbers)
            duration_minutes: Duration of the service

        Returns list of available TimeSlot objects
        """
        local_date = date.astimezone(self.shop_tz)

        # Get barbers to check (include schedule field)
        barber_query = {"shop_id": self.shop_id, "active": True}
        if barber_id:
            barber_query["id"] = barber_id

        barbers = await self.db.barbers.find(
            barber_query, {"_id": 0, "id": 1, "name": 1, "schedule": 1}
        ).to_list(50)

        if not barbers:
            return []

        now = datetime.now(timezone.utc)
        available_slots = []

        for barber in barbers:
            barber_sched = barber.get("schedule")
            hours = self._get_day_hours(local_date, barber_sched)

            if not hours:
                continue  # This barber is off today

            open_time, close_time = hours

            day_start = local_date.replace(
                hour=open_time.hour,
                minute=open_time.minute,
                second=0,
                microsecond=0
            )
            day_end = local_date.replace(
                hour=close_time.hour,
                minute=close_time.minute,
                second=0,
                microsecond=0
            )

            day_start_utc = day_start.astimezone(timezone.utc)
            day_end_utc = day_end.astimezone(timezone.utc)

            current_slot = day_start_utc

            while current_slot + timedelta(minutes=duration_minutes) <= day_end_utc:
                if current_slot < now:
                    current_slot += timedelta(minutes=self.SLOT_DURATION_MINUTES)
                    continue

                slot_end = current_slot + timedelta(minutes=duration_minutes)

                is_available, _ = await self.check_barber_availability(
                    barber["id"], current_slot, slot_end
                )

                if is_available:
                    available_slots.append(TimeSlot(
                        start=current_slot,
                        end=slot_end,
                        barber_id=barber["id"],
                        barber_name=barber["name"]
                    ))

                current_slot += timedelta(minutes=self.SLOT_DURATION_MINUTES)

        return available_slots
    
    async def get_barber_schedule(
        self,
        barber_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[dict]:
        """
        Get a barber's schedule for a date range.
        
        Returns list of appointments with client info.
        """
        appointments = await self.db.appointments.find({
            "shop_id": self.shop_id,
            "barber_id": barber_id,
            "status": {"$nin": ["cancelled"]},
            "scheduled_at": {
                "$gte": start_date.isoformat(),
                "$lt": end_date.isoformat()
            }
        }, {"_id": 0}).sort("scheduled_at", 1).to_list(100)
        
        # Enrich with client info
        for apt in appointments:
            client = await self.db.clients.find_one(
                {"id": apt["client_id"]},
                {"_id": 0, "name": 1, "phone": 1}
            )
            apt["client"] = client
            
            service = await self.db.services.find_one(
                {"id": apt["service_id"]},
                {"_id": 0, "name": 1}
            )
            apt["service"] = service
        
        return appointments


def create_scheduling_engine(db, shop: dict) -> SchedulingEngine:
    """Factory function to create a scheduling engine."""
    return SchedulingEngine(db, shop)
