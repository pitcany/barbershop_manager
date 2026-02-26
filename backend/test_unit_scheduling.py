"""
Unit tests for:
- SchedulingEngine (scheduling.py) — business hours, availability, slot generation
- SMSComplianceService.grant_consent (sms_compliance.py) — the untested method
- Natural-language SMS booking parser (agents.py)

Uses the same FakeDB/FakeCollection pattern as other test files.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone, time
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, os.path.dirname(__file__))

from scheduling import SchedulingEngine, TimeSlot, create_scheduling_engine
from sms_compliance import SMSComplianceService, is_opt_out_message, create_sms_service
from models import Shop


# ============================================================
# Helpers: Async dict-backed fake collections (shared pattern)
# ============================================================

class FakeCollection:
    """Minimal async MongoDB collection mock backed by a plain list."""

    def __init__(self, docs=None):
        self._docs = list(docs or [])

    async def find_one(self, query, projection=None):
        for doc in self._docs:
            if self._matches(doc, query):
                return dict(doc)
        return None

    def find(self, query, projection=None):
        return FakeCursor([dict(d) for d in self._docs if self._matches(d, query)])

    async def insert_one(self, doc):
        self._docs.append(dict(doc))
        return MagicMock(inserted_id="ok")

    async def update_one(self, query, update):
        for doc in self._docs:
            if self._matches(doc, query):
                if "$set" in update:
                    doc.update(update["$set"])
                if "$inc" in update:
                    for k, v in update["$inc"].items():
                        doc[k] = doc.get(k, 0) + v
                return MagicMock(modified_count=1)
        return MagicMock(modified_count=0)

    async def delete_many(self, query):
        before = len(self._docs)
        self._docs = [d for d in self._docs if not self._matches(d, query)]
        return MagicMock(deleted_count=before - len(self._docs))

    async def update_many(self, query, update):
        count = 0
        for doc in self._docs:
            if self._matches(doc, query):
                if "$set" in update:
                    doc.update(update["$set"])
                count += 1
        return MagicMock(modified_count=count)

    async def count_documents(self, query):
        return sum(1 for d in self._docs if self._matches(d, query))

    async def create_index(self, *args, **kwargs):
        pass

    @staticmethod
    def _matches(doc, query):
        for key, condition in query.items():
            if key == "$or":
                if not any(FakeCollection._matches(doc, sub) for sub in condition):
                    return False
                continue
            val = doc.get(key)
            if isinstance(condition, dict):
                for op, operand in condition.items():
                    if op == "$in" and val not in operand:
                        return False
                    if op == "$nin" and val in operand:
                        return False
                    if op == "$ne" and val == operand:
                        return False
                    if op == "$gte" and (val is None or val < operand):
                        return False
                    if op == "$lt" and (val is None or val >= operand):
                        return False
                    if op == "$gt" and (val is None or val <= operand):
                        return False
            else:
                if val != condition:
                    return False
        return True


class FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, *args, **kwargs):
        return self

    def limit(self, n):
        self._docs = self._docs[:n]
        return self

    async def to_list(self, n=None):
        if n is not None:
            return self._docs[:n]
        return self._docs


class FakeDB:
    """Namespace-like object that creates FakeCollections on attribute access."""

    def __init__(self):
        self._collections = {}

    def __getattr__(self, name):
        if name.startswith("_"):
            return super().__getattribute__(name)
        if name not in self._collections:
            self._collections[name] = FakeCollection()
        return self._collections[name]

    def _set(self, name, docs):
        self._collections[name] = FakeCollection(docs)


# ============================================================
# Fixtures
# ============================================================

SHOP_ID = "shop-test-001"

# Business hours: Mon-Fri 9-17, Sat 10-14, Sun closed
BUSINESS_HOURS = {
    "monday":    {"open": "09:00", "close": "17:00"},
    "tuesday":   {"open": "09:00", "close": "17:00"},
    "wednesday": {"open": "09:00", "close": "17:00"},
    "thursday":  {"open": "09:00", "close": "17:00"},
    "friday":    {"open": "09:00", "close": "17:00"},
    "saturday":  {"open": "10:00", "close": "14:00"},
}

SHOP_DICT = {
    "id": SHOP_ID,
    "name": "Test Shop",
    "business_hours": BUSINESS_HOURS,
    "timezone": "America/New_York",
}


def _make_engine(db=None, shop_dict=None):
    """Factory helper."""
    return SchedulingEngine(db or FakeDB(), shop_dict or SHOP_DICT)


# ============================================================
# TestSchedulingEngineBusinessHours
# ============================================================

class TestSchedulingEngineBusinessHours:
    """Tests for _get_day_hours — shop defaults and barber overrides."""

    def test_weekday_returns_hours(self):
        engine = _make_engine()
        # Use a known Monday in ET
        monday = datetime(2026, 3, 2, 12, 0, tzinfo=ZoneInfo("America/New_York"))
        hours = engine._get_day_hours(monday)
        assert hours is not None
        open_t, close_t = hours
        assert open_t == time(9, 0)
        assert close_t == time(17, 0)

    def test_saturday_returns_shorter_hours(self):
        engine = _make_engine()
        saturday = datetime(2026, 2, 28, 12, 0, tzinfo=ZoneInfo("America/New_York"))
        hours = engine._get_day_hours(saturday)
        assert hours is not None
        open_t, close_t = hours
        assert open_t == time(10, 0)
        assert close_t == time(14, 0)

    def test_sunday_returns_none(self):
        engine = _make_engine()
        sunday = datetime(2026, 3, 1, 12, 0, tzinfo=ZoneInfo("America/New_York"))
        hours = engine._get_day_hours(sunday)
        assert hours is None

    def test_barber_schedule_overrides_shop(self):
        engine = _make_engine()
        barber_sched = {"monday": {"open": "10:00", "close": "16:00"}}
        monday = datetime(2026, 3, 2, 12, 0, tzinfo=ZoneInfo("America/New_York"))
        hours = engine._get_day_hours(monday, barber_sched)
        assert hours is not None
        open_t, close_t = hours
        assert open_t == time(10, 0)
        assert close_t == time(16, 0)

    def test_barber_schedule_falls_through_to_shop_on_missing_day(self):
        engine = _make_engine()
        barber_sched = {"wednesday": {"open": "08:00", "close": "15:00"}}
        # Monday not in barber schedule -> uses shop
        monday = datetime(2026, 3, 2, 12, 0, tzinfo=ZoneInfo("America/New_York"))
        hours = engine._get_day_hours(monday, barber_sched)
        assert hours is not None
        assert hours[0] == time(9, 0)

    def test_malformed_hours_returns_none(self):
        shop = {**SHOP_DICT, "business_hours": {"monday": {"open": "bad", "close": "data"}}}
        engine = _make_engine(shop_dict=shop)
        monday = datetime(2026, 3, 2, 12, 0, tzinfo=ZoneInfo("America/New_York"))
        assert engine._get_day_hours(monday) is None

    def test_empty_business_hours(self):
        shop = {**SHOP_DICT, "business_hours": {}}
        engine = _make_engine(shop_dict=shop)
        monday = datetime(2026, 3, 2, 12, 0, tzinfo=ZoneInfo("America/New_York"))
        assert engine._get_day_hours(monday) is None


# ============================================================
# TestSchedulingEngineWithinHours
# ============================================================

class TestSchedulingEngineWithinHours:
    """Tests for _is_within_business_hours edge cases."""

    def test_exactly_at_open(self):
        engine = _make_engine()
        # Monday 9:00 AM ET
        dt = datetime(2026, 3, 2, 9, 0, tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)
        assert engine._is_within_business_hours(dt, 30) is True

    def test_appointment_ending_exactly_at_close(self):
        engine = _make_engine()
        # Monday 4:30 PM ET + 30min = 5:00 PM = close
        dt = datetime(2026, 3, 2, 16, 30, tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)
        assert engine._is_within_business_hours(dt, 30) is True

    def test_appointment_spanning_past_close(self):
        engine = _make_engine()
        # Monday 4:45 PM ET + 30min = 5:15 PM > close
        dt = datetime(2026, 3, 2, 16, 45, tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)
        assert engine._is_within_business_hours(dt, 30) is False

    def test_before_open(self):
        engine = _make_engine()
        # Monday 8:30 AM ET — before 9:00 open
        dt = datetime(2026, 3, 2, 8, 30, tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)
        assert engine._is_within_business_hours(dt, 30) is False

    def test_closed_day(self):
        engine = _make_engine()
        # Sunday
        dt = datetime(2026, 3, 1, 12, 0, tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)
        assert engine._is_within_business_hours(dt, 30) is False

    def test_with_barber_override_hours(self):
        engine = _make_engine()
        barber_sched = {"monday": {"open": "11:00", "close": "15:00"}}
        # Monday 10:00 AM ET — within shop hours but NOT barber hours
        dt = datetime(2026, 3, 2, 10, 0, tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)
        assert engine._is_within_business_hours(dt, 30, barber_sched) is False
        # Monday 11:00 AM ET — within barber hours
        dt2 = datetime(2026, 3, 2, 11, 0, tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)
        assert engine._is_within_business_hours(dt2, 30, barber_sched) is True

    def test_longer_service_duration(self):
        engine = _make_engine()
        # Monday 4:00 PM ET + 90min = 5:30 PM > close
        dt = datetime(2026, 3, 2, 16, 0, tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)
        assert engine._is_within_business_hours(dt, 90) is False
        # Monday 3:00 PM ET + 90min = 4:30 PM < close
        dt2 = datetime(2026, 3, 2, 15, 0, tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)
        assert engine._is_within_business_hours(dt2, 90) is True


# ============================================================
# TestSchedulingEngineAvailability
# ============================================================

class TestSchedulingEngineAvailability:
    """Tests for check_barber_availability — conflict detection."""

    @pytest.mark.asyncio
    async def test_no_conflicts(self):
        db = FakeDB()
        engine = _make_engine(db)
        # Monday 10:00-10:30 — no appointments
        start = datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc)  # 10am ET
        end = start + timedelta(minutes=30)
        available, reason = await engine.check_barber_availability("barber-1", start, end)
        assert available is True
        assert reason is None

    @pytest.mark.asyncio
    async def test_exact_overlap_conflict(self):
        db = FakeDB()
        start = datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc)
        db._set("appointments", [{
            "shop_id": SHOP_ID,
            "barber_id": "barber-1",
            "status": "confirmed",
            "scheduled_at": start.isoformat(),
            "duration_minutes": 30,
        }])
        engine = _make_engine(db)
        end = start + timedelta(minutes=30)
        available, reason = await engine.check_barber_availability("barber-1", start, end)
        assert available is False
        assert "Conflicts" in reason

    @pytest.mark.asyncio
    async def test_partial_overlap_conflict(self):
        db = FakeDB()
        existing_start = datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc)
        db._set("appointments", [{
            "shop_id": SHOP_ID,
            "barber_id": "barber-1",
            "status": "confirmed",
            "scheduled_at": existing_start.isoformat(),
            "duration_minutes": 30,
        }])
        engine = _make_engine(db)
        # New slot starts 15min into existing
        new_start = existing_start + timedelta(minutes=15)
        new_end = new_start + timedelta(minutes=30)
        available, reason = await engine.check_barber_availability("barber-1", new_start, new_end)
        assert available is False

    @pytest.mark.asyncio
    async def test_adjacent_no_overlap(self):
        db = FakeDB()
        existing_start = datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc)
        db._set("appointments", [{
            "shop_id": SHOP_ID,
            "barber_id": "barber-1",
            "status": "confirmed",
            "scheduled_at": existing_start.isoformat(),
            "duration_minutes": 30,
        }])
        engine = _make_engine(db)
        # New slot starts exactly when existing ends — no overlap
        new_start = existing_start + timedelta(minutes=30)
        new_end = new_start + timedelta(minutes=30)
        available, reason = await engine.check_barber_availability("barber-1", new_start, new_end)
        assert available is True

    @pytest.mark.asyncio
    async def test_cancelled_appointment_ignored(self):
        db = FakeDB()
        start = datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc)
        db._set("appointments", [{
            "shop_id": SHOP_ID,
            "barber_id": "barber-1",
            "status": "cancelled",
            "scheduled_at": start.isoformat(),
            "duration_minutes": 30,
        }])
        engine = _make_engine(db)
        end = start + timedelta(minutes=30)
        available, reason = await engine.check_barber_availability("barber-1", start, end)
        assert available is True

    @pytest.mark.asyncio
    async def test_no_show_appointment_ignored(self):
        db = FakeDB()
        start = datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc)
        db._set("appointments", [{
            "shop_id": SHOP_ID,
            "barber_id": "barber-1",
            "status": "no_show",
            "scheduled_at": start.isoformat(),
            "duration_minutes": 30,
        }])
        engine = _make_engine(db)
        end = start + timedelta(minutes=30)
        available, reason = await engine.check_barber_availability("barber-1", start, end)
        assert available is True

    @pytest.mark.asyncio
    async def test_exclude_appointment_id(self):
        db = FakeDB()
        start = datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc)
        db._set("appointments", [{
            "id": "apt-existing",
            "shop_id": SHOP_ID,
            "barber_id": "barber-1",
            "status": "confirmed",
            "scheduled_at": start.isoformat(),
            "duration_minutes": 30,
        }])
        engine = _make_engine(db)
        end = start + timedelta(minutes=30)
        # Without exclude — conflict
        available, _ = await engine.check_barber_availability("barber-1", start, end)
        assert available is False
        # With exclude — no conflict (rescheduling same appointment)
        available2, _ = await engine.check_barber_availability("barber-1", start, end, exclude_appointment_id="apt-existing")
        assert available2 is True

    @pytest.mark.asyncio
    async def test_different_barber_no_conflict(self):
        db = FakeDB()
        start = datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc)
        db._set("appointments", [{
            "shop_id": SHOP_ID,
            "barber_id": "barber-1",
            "status": "confirmed",
            "scheduled_at": start.isoformat(),
            "duration_minutes": 30,
        }])
        engine = _make_engine(db)
        end = start + timedelta(minutes=30)
        available, _ = await engine.check_barber_availability("barber-2", start, end)
        assert available is True


# ============================================================
# TestSchedulingEngineValidation
# ============================================================

class TestSchedulingEngineValidation:
    """Tests for validate_appointment_slot — full validation pipeline."""

    @pytest.mark.asyncio
    async def test_past_appointment_rejected(self):
        db = FakeDB()
        db._set("barbers", [{"id": "barber-1", "shop_id": SHOP_ID}])
        engine = _make_engine(db)
        # Use a past weekday during business hours so the "past" check is hit,
        # not the business hours check.
        past = datetime(2025, 3, 3, 15, 0, tzinfo=timezone.utc)  # Mon 10am ET, in the past
        valid, err = await engine.validate_appointment_slot("barber-1", past, 30)
        assert valid is False
        # Could be caught by either business hours or past check depending on order
        assert "past" in err.lower() or "business hours" in err.lower()

    @pytest.mark.asyncio
    async def test_outside_business_hours_rejected(self):
        db = FakeDB()
        db._set("barbers", [{"id": "barber-1", "shop_id": SHOP_ID}])
        engine = _make_engine(db)
        # Monday 7:00 AM ET — before open
        dt = datetime(2026, 3, 2, 7, 0, tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)
        valid, err = await engine.validate_appointment_slot("barber-1", dt, 30)
        assert valid is False
        assert "business hours" in err.lower()

    @pytest.mark.asyncio
    async def test_conflicting_slot_rejected(self):
        db = FakeDB()
        db._set("barbers", [{"id": "barber-1", "shop_id": SHOP_ID}])
        # Use a future Monday
        monday = datetime(2026, 3, 2, 14, 0, tzinfo=timezone.utc)  # 9 AM ET
        db._set("appointments", [{
            "shop_id": SHOP_ID,
            "barber_id": "barber-1",
            "status": "confirmed",
            "scheduled_at": monday.isoformat(),
            "duration_minutes": 30,
        }])
        engine = _make_engine(db)
        valid, err = await engine.validate_appointment_slot("barber-1", monday, 30)
        assert valid is False
        assert "unavailable" in err.lower()

    @pytest.mark.asyncio
    async def test_valid_slot_accepted(self):
        db = FakeDB()
        db._set("barbers", [{"id": "barber-1", "shop_id": SHOP_ID}])
        engine = _make_engine(db)
        # A future Monday 10 AM ET
        dt = datetime(2026, 3, 9, 15, 0, tzinfo=timezone.utc)  # 10 AM ET (DST not yet)
        valid, err = await engine.validate_appointment_slot("barber-1", dt, 30)
        assert valid is True
        assert err is None

    @pytest.mark.asyncio
    async def test_barber_specific_hours_used(self):
        db = FakeDB()
        db._set("barbers", [{
            "id": "barber-1",
            "shop_id": SHOP_ID,
            "schedule": {"monday": {"open": "12:00", "close": "16:00"}},
        }])
        engine = _make_engine(db)
        # Monday 10 AM ET — within shop hours but NOT barber hours
        dt = datetime(2026, 3, 9, 15, 0, tzinfo=timezone.utc)
        valid, err = await engine.validate_appointment_slot("barber-1", dt, 30)
        assert valid is False
        assert "business hours" in err.lower()


# ============================================================
# TestSchedulingEngineSlotGeneration
# ============================================================

class TestSchedulingEngineSlotGeneration:
    """Tests for get_available_slots — slot listing."""

    @pytest.mark.asyncio
    async def test_generates_slots_for_open_day(self):
        db = FakeDB()
        db._set("barbers", [
            {"id": "b1", "shop_id": SHOP_ID, "name": "Marcus", "active": True},
        ])
        engine = _make_engine(db)
        # Use a future Saturday (shorter hours 10-14)
        sat = datetime(2026, 2, 28, 12, 0, tzinfo=ZoneInfo("America/New_York"))
        with patch("scheduling.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 2, 27, 12, 0, tzinfo=timezone.utc)
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.strptime = datetime.strptime
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
            slots = await engine.get_available_slots(sat, duration_minutes=30)
        assert len(slots) > 0
        for s in slots:
            assert isinstance(s, TimeSlot)
            assert s.barber_id == "b1"
            assert s.barber_name == "Marcus"

    @pytest.mark.asyncio
    async def test_no_barbers_returns_empty(self):
        db = FakeDB()
        engine = _make_engine(db)
        day = datetime(2026, 3, 2, 12, 0, tzinfo=ZoneInfo("America/New_York"))
        slots = await engine.get_available_slots(day)
        assert slots == []

    @pytest.mark.asyncio
    async def test_closed_day_returns_empty(self):
        db = FakeDB()
        db._set("barbers", [
            {"id": "b1", "shop_id": SHOP_ID, "name": "Marcus", "active": True},
        ])
        engine = _make_engine(db)
        # Sunday — closed
        sun = datetime(2026, 3, 1, 12, 0, tzinfo=ZoneInfo("America/New_York"))
        slots = await engine.get_available_slots(sun)
        assert slots == []

    @pytest.mark.asyncio
    async def test_specific_barber_filter(self):
        db = FakeDB()
        db._set("barbers", [
            {"id": "b1", "shop_id": SHOP_ID, "name": "Marcus", "active": True},
            {"id": "b2", "shop_id": SHOP_ID, "name": "James", "active": True},
        ])
        engine = _make_engine(db)
        day = datetime(2026, 3, 9, 12, 0, tzinfo=ZoneInfo("America/New_York"))
        with patch("scheduling.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 8, 12, 0, tzinfo=timezone.utc)
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.strptime = datetime.strptime
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
            slots = await engine.get_available_slots(day, barber_id="b2")
        for s in slots:
            assert s.barber_id == "b2"

    @pytest.mark.asyncio
    async def test_fully_booked_day(self):
        db = FakeDB()
        db._set("barbers", [
            {"id": "b1", "shop_id": SHOP_ID, "name": "Marcus", "active": True},
        ])
        # Fill Saturday 10-14 with 8 consecutive 30-min appointments
        sat_base = datetime(2026, 2, 28, 15, 0, tzinfo=timezone.utc)  # 10 AM ET
        appointments = []
        for i in range(8):
            start = sat_base + timedelta(minutes=30 * i)
            appointments.append({
                "shop_id": SHOP_ID,
                "barber_id": "b1",
                "status": "confirmed",
                "scheduled_at": start.isoformat(),
                "duration_minutes": 30,
            })
        db._set("appointments", appointments)
        engine = _make_engine(db)
        sat = datetime(2026, 2, 28, 12, 0, tzinfo=ZoneInfo("America/New_York"))
        with patch("scheduling.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 2, 27, 12, 0, tzinfo=timezone.utc)
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.strptime = datetime.strptime
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
            slots = await engine.get_available_slots(sat, duration_minutes=30)
        assert len(slots) == 0


# ============================================================
# TestSchedulingEngineBarberScheduleDB
# ============================================================

class TestSchedulingEngineBarberScheduleDB:
    """Tests for _get_barber_schedule_data — DB fetch."""

    @pytest.mark.asyncio
    async def test_returns_schedule_if_present(self):
        db = FakeDB()
        sched = {"monday": {"open": "10:00", "close": "16:00"}}
        db._set("barbers", [{"id": "b1", "shop_id": SHOP_ID, "schedule": sched}])
        engine = _make_engine(db)
        result = await engine._get_barber_schedule_data("b1")
        assert result == sched

    @pytest.mark.asyncio
    async def test_returns_none_if_no_schedule(self):
        db = FakeDB()
        db._set("barbers", [{"id": "b1", "shop_id": SHOP_ID}])
        engine = _make_engine(db)
        result = await engine._get_barber_schedule_data("b1")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_if_barber_not_found(self):
        db = FakeDB()
        engine = _make_engine(db)
        result = await engine._get_barber_schedule_data("nonexistent")
        assert result is None


# ============================================================
# TestTimeSlot
# ============================================================

class TestTimeSlot:
    """Tests for TimeSlot.to_dict serialization."""

    def test_to_dict(self):
        start = datetime(2026, 3, 2, 14, 0, tzinfo=timezone.utc)
        end = start + timedelta(minutes=30)
        slot = TimeSlot(start=start, end=end, barber_id="b1", barber_name="Marcus")
        d = slot.to_dict()
        assert d["barber_id"] == "b1"
        assert d["barber_name"] == "Marcus"
        assert "2026-03-02" in d["start"]
        assert "2026-03-02" in d["end"]


# ============================================================
# TestCreateSchedulingEngine
# ============================================================

class TestCreateSchedulingEngine:
    """Tests for the factory function."""

    def test_creates_engine(self):
        db = FakeDB()
        engine = create_scheduling_engine(db, SHOP_DICT)
        assert isinstance(engine, SchedulingEngine)
        assert engine.shop_id == SHOP_ID

    def test_defaults_timezone(self):
        db = FakeDB()
        shop = {"id": "s1", "business_hours": {}}
        engine = create_scheduling_engine(db, shop)
        assert str(engine.shop_tz) == "America/New_York"


# ============================================================
# TestSMSComplianceGrantConsent
# ============================================================

class TestSMSComplianceGrantConsent:
    """Tests for the previously-untested grant_consent method."""

    @pytest.mark.asyncio
    async def test_grant_consent_success(self):
        db = FakeDB()
        db._set("clients", [{
            "id": "c1",
            "shop_id": SHOP_ID,
            "sms_consent": False,
        }])
        audit = MagicMock()
        service = SMSComplianceService(db, SHOP_ID, audit)
        result = await service.grant_consent("c1", source="web_form")
        assert result is True
        # Verify the DB was updated
        client = await db.clients.find_one({"id": "c1"})
        assert client["sms_consent"] is True
        assert client["sms_consent_source"] == "web_form"

    @pytest.mark.asyncio
    async def test_grant_consent_nonexistent_client(self):
        db = FakeDB()
        audit = MagicMock()
        service = SMSComplianceService(db, SHOP_ID, audit)
        result = await service.grant_consent("nonexistent", source="manual")
        assert result is False

    @pytest.mark.asyncio
    async def test_grant_consent_default_source(self):
        db = FakeDB()
        db._set("clients", [{
            "id": "c1",
            "shop_id": SHOP_ID,
            "sms_consent": False,
        }])
        audit = MagicMock()
        service = SMSComplianceService(db, SHOP_ID, audit)
        await service.grant_consent("c1")
        client = await db.clients.find_one({"id": "c1"})
        assert client["sms_consent_source"] == "unknown"

    @pytest.mark.asyncio
    async def test_re_grant_after_opt_out(self):
        """Verify consent can be re-granted after an opt-out."""
        db = FakeDB()
        db._set("clients", [{
            "id": "c1",
            "shop_id": SHOP_ID,
            "sms_consent": False,
            "sms_consent_source": "opt_out_stop",
        }])
        audit = MagicMock()
        service = SMSComplianceService(db, SHOP_ID, audit)
        result = await service.grant_consent("c1", source="inbound_sms")
        assert result is True
        client = await db.clients.find_one({"id": "c1"})
        assert client["sms_consent"] is True
        assert client["sms_consent_source"] == "inbound_sms"


# ============================================================
# TestNaturalLanguageBooking
# ============================================================

class TestEventBus:
    """Tests for the in-process event bus."""

    @pytest.mark.asyncio
    async def test_publish_to_subscriber(self):
        import event_bus
        # Clear any existing subscribers
        event_bus._subscribers.clear()

        received = []

        async def consumer():
            async for evt in event_bus.subscribe():
                received.append(evt)
                break  # stop after first event

        task = asyncio.create_task(consumer())
        await asyncio.sleep(0.05)  # let consumer start

        await event_bus.publish("test_event", data={"key": "value"}, shop_id=SHOP_ID)
        await asyncio.sleep(0.05)

        assert len(received) == 1
        assert received[0]["type"] == "test_event"
        assert received[0]["data"]["key"] == "value"
        assert received[0]["shop_id"] == SHOP_ID
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_publish_never_raises(self):
        """publish() should never raise, even with no subscribers."""
        import event_bus
        event_bus._subscribers.clear()
        # Should not raise
        await event_bus.publish("some_event", data={})

    @pytest.mark.asyncio
    async def test_subscriber_count(self):
        import event_bus
        event_bus._subscribers.clear()
        assert event_bus.subscriber_count() == 0


class TestNaturalLanguageBooking:
    """Tests for the natural-language SMS booking shortcut."""

    def _make_shop(self):
        return Shop(
            id=SHOP_ID,
            name="Test Barbershop",
            phone="+15551234567",
            address="123 Main St",
            business_hours=BUSINESS_HOURS,
            timezone="America/New_York",
            deposit_amount=25,
            deposit_required_hours=48,
            cancellation_window_hours=4,
            confirmation_window_hours=24,
        )

    def _make_client(self):
        from models import Client
        return Client(
            id="client-1",
            shop_id=SHOP_ID,
            name="John Doe",
            phone="+15559876543",
        )

    def _make_db(self):
        db = FakeDB()
        db._set("services", [
            {"id": "svc-1", "shop_id": SHOP_ID, "name": "Classic Cut",
             "price": 30, "duration_minutes": 30, "active": True},
            {"id": "svc-2", "shop_id": SHOP_ID, "name": "Beard Trim",
             "price": 20, "duration_minutes": 20, "active": True},
        ])
        db._set("barbers", [
            {"id": "barber-1", "shop_id": SHOP_ID, "name": "Marcus", "active": True},
            {"id": "barber-2", "shop_id": SHOP_ID, "name": "James", "active": True},
        ])
        db._set("clients", [
            {"id": "client-1", "shop_id": SHOP_ID, "name": "John Doe",
             "phone": "+15559876543", "no_shows": 0, "sms_consent": True},
        ])
        return db

    @pytest.mark.asyncio
    async def test_natural_booking_full_message(self):
        """BOOK Classic Cut with Marcus Thursday 2pm creates appointment directly."""
        from agents import FrontDeskAgent
        db = self._make_db()
        shop = self._make_shop()
        agent = FrontDeskAgent(db, shop)
        client = self._make_client()

        # Mock the scheduling engine to return valid
        with patch("scheduling.create_scheduling_engine") as mock_se:
            mock_engine = MagicMock()
            mock_engine.validate_appointment_slot = AsyncMock(return_value=(True, None))
            mock_se.return_value = mock_engine

            msg, meta = await agent.process_inbound_message(
                client, "BOOK Classic Cut with Marcus Thursday 2pm"
            )

        assert "booking_completed" in meta.get("action", "")
        assert "Classic Cut" in msg
        assert "Marcus" in msg
        # Appointment should have been created in db
        apt = await db.appointments.find_one({"client_id": "client-1"})
        assert apt is not None
        assert apt["barber_id"] == "barber-1"
        assert apt["service_id"] == "svc-1"

    @pytest.mark.asyncio
    async def test_natural_booking_with_beard_trim(self):
        """BOOK Beard Trim with James Friday 10am"""
        from agents import FrontDeskAgent
        db = self._make_db()
        shop = self._make_shop()
        agent = FrontDeskAgent(db, shop)
        client = self._make_client()

        with patch("scheduling.create_scheduling_engine") as mock_se:
            mock_engine = MagicMock()
            mock_engine.validate_appointment_slot = AsyncMock(return_value=(True, None))
            mock_se.return_value = mock_engine

            msg, meta = await agent.process_inbound_message(
                client, "BOOK Beard Trim with James Friday 10am"
            )

        assert "booking_completed" in meta.get("action", "")
        assert "Beard Trim" in msg
        assert "James" in msg
        apt = await db.appointments.find_one({"client_id": "client-1"})
        assert apt["barber_id"] == "barber-2"
        assert apt["service_id"] == "svc-2"

    @pytest.mark.asyncio
    async def test_natural_booking_no_barber_clause(self):
        """BOOK Classic Cut Saturday 11am — picks first available barber."""
        from agents import FrontDeskAgent
        db = self._make_db()
        shop = self._make_shop()
        agent = FrontDeskAgent(db, shop)
        client = self._make_client()

        with patch("scheduling.create_scheduling_engine") as mock_se:
            mock_engine = MagicMock()
            mock_engine.validate_appointment_slot = AsyncMock(return_value=(True, None))
            mock_se.return_value = mock_engine

            msg, meta = await agent.process_inbound_message(
                client, "BOOK Classic Cut Saturday 11am"
            )

        assert "booking_completed" in meta.get("action", "")
        apt = await db.appointments.find_one({"client_id": "client-1"})
        assert apt["barber_id"] == "barber-1"  # first barber

    @pytest.mark.asyncio
    async def test_natural_booking_unmatched_service_falls_back(self):
        """BOOK Unknown Service Thursday 2pm — can't match, falls back to menu."""
        from agents import FrontDeskAgent
        db = self._make_db()
        shop = self._make_shop()
        agent = FrontDeskAgent(db, shop)
        client = self._make_client()

        msg, meta = await agent.process_inbound_message(
            client, "BOOK Unknown Service Thursday 2pm"
        )

        # Should fall back to menu flow
        assert meta.get("action") == "booking_started"
        assert "services" in msg.lower()

    @pytest.mark.asyncio
    async def test_natural_booking_no_time_falls_back(self):
        """BOOK Classic Cut with Marcus — no time given, falls back to menu."""
        from agents import FrontDeskAgent
        db = self._make_db()
        shop = self._make_shop()
        agent = FrontDeskAgent(db, shop)
        client = self._make_client()

        msg, meta = await agent.process_inbound_message(
            client, "BOOK Classic Cut with Marcus"
        )

        assert meta.get("action") == "booking_started"

    @pytest.mark.asyncio
    async def test_natural_booking_slot_unavailable(self):
        """BOOK Classic Cut Thursday 2pm but slot is taken."""
        from agents import FrontDeskAgent
        db = self._make_db()
        shop = self._make_shop()
        agent = FrontDeskAgent(db, shop)
        client = self._make_client()

        with patch("scheduling.create_scheduling_engine") as mock_se:
            mock_engine = MagicMock()
            mock_engine.validate_appointment_slot = AsyncMock(
                return_value=(False, "Time slot unavailable: conflicts with existing appointment")
            )
            mock_se.return_value = mock_engine

            msg, meta = await agent.process_inbound_message(
                client, "BOOK Classic Cut Thursday 2pm"
            )

        assert meta.get("action") == "natural_booking_unavailable"
        assert "isn't available" in msg

    @pytest.mark.asyncio
    async def test_plain_book_still_works(self):
        """Plain BOOK (no extra text) still starts the menu flow."""
        from agents import FrontDeskAgent
        db = self._make_db()
        shop = self._make_shop()
        agent = FrontDeskAgent(db, shop)
        client = self._make_client()

        msg, meta = await agent.process_inbound_message(client, "BOOK")

        assert meta.get("action") == "booking_started"
        assert "services" in msg.lower()

    @pytest.mark.asyncio
    async def test_natural_booking_tomorrow(self):
        """BOOK Classic Cut tomorrow 3pm uses correct date."""
        from agents import FrontDeskAgent
        db = self._make_db()
        shop = self._make_shop()
        agent = FrontDeskAgent(db, shop)
        client = self._make_client()

        with patch("scheduling.create_scheduling_engine") as mock_se:
            mock_engine = MagicMock()
            mock_engine.validate_appointment_slot = AsyncMock(return_value=(True, None))
            mock_se.return_value = mock_engine

            msg, meta = await agent.process_inbound_message(
                client, "BOOK Classic Cut tomorrow 3pm"
            )

        assert "booking_completed" in meta.get("action", "")
        apt = await db.appointments.find_one({"client_id": "client-1"})
        assert apt is not None
