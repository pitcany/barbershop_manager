"""
Tests for features 5, 7, 8:
5. No-show fee collection flow
7. Cancellation window enforcement
8. SMS booking completion (multi-step flow)

Uses pytest + unittest.mock with in-memory async DB stubs.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone, time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure backend is on path
sys.path.insert(0, os.path.dirname(__file__))

from models import (
    AppointmentStatus, Client, Shop, EventType, MessageDirection,
    ALLOWED_TRANSITIONS,
)


# ============================================================
# Helpers: Async dict-backed fake collections
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

    async def update_many(self, query, update):
        count = 0
        for doc in self._docs:
            if self._matches(doc, query):
                if "$set" in update:
                    doc.update(update["$set"])
                count += 1
        return MagicMock(modified_count=count)

    async def delete_many(self, query):
        before = len(self._docs)
        self._docs = [d for d in self._docs if not self._matches(d, query)]
        return MagicMock(deleted_count=before - len(self._docs))

    async def count_documents(self, query):
        return sum(1 for d in self._docs if self._matches(d, query))

    def aggregate(self, pipeline):
        return FakeCursor([])

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
# Shared fixture data
# ============================================================

SHOP_DICT = {
    "id": "shop_1",
    "slug": "classic-cuts",
    "name": "Classic Cuts",
    "phone": "+15551110000",
    "email": "shop@test.com",
    "address": "123 Main St",
    "timezone": "America/New_York",
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
}

SHOP = Shop(**SHOP_DICT)

CLIENT_CONSENT = {
    "id": "client_1",
    "shop_id": "shop_1",
    "name": "Alice Smith",
    "phone": "+15551112222",
    "email": "alice@test.com",
    "sms_consent": True,
    "total_appointments": 3,
    "no_shows": 0,
    "created_at": datetime.now(timezone.utc).isoformat(),
    "updated_at": datetime.now(timezone.utc).isoformat(),
}

CLIENT_NO_CONSENT = {
    "id": "client_2",
    "shop_id": "shop_1",
    "name": "Bob Jones",
    "phone": "+15553334444",
    "email": "bob@test.com",
    "sms_consent": False,
    "total_appointments": 1,
    "no_shows": 0,
    "created_at": datetime.now(timezone.utc).isoformat(),
    "updated_at": datetime.now(timezone.utc).isoformat(),
}

SERVICE = {
    "id": "service_1",
    "shop_id": "shop_1",
    "name": "Fade",
    "price": 30.0,
    "duration_minutes": 30,
    "active": True,
}

SERVICE_2 = {
    "id": "service_2",
    "shop_id": "shop_1",
    "name": "Lineup",
    "price": 20.0,
    "duration_minutes": 15,
    "active": True,
}

BARBER = {
    "id": "barber_1",
    "shop_id": "shop_1",
    "name": "James",
    "active": True,
}

BARBER_2 = {
    "id": "barber_2",
    "shop_id": "shop_1",
    "name": "Marcus",
    "active": True,
}

CLIENT_OBJ = Client(**{k: v for k, v in CLIENT_CONSENT.items() if k != "_id"})
CLIENT_NO_CONSENT_OBJ = Client(**{k: v for k, v in CLIENT_NO_CONSENT.items() if k != "_id"})


def _build_db(**overrides):
    """Build a FakeDB pre-loaded with standard test data."""
    db = FakeDB()
    db._set("shops", [dict(SHOP_DICT)])
    db._set("clients", [dict(CLIENT_CONSENT), dict(CLIENT_NO_CONSENT)])
    db._set("services", [dict(SERVICE), dict(SERVICE_2)])
    db._set("barbers", [dict(BARBER), dict(BARBER_2)])
    for key, docs in overrides.items():
        db._set(key, docs)
    return db


def _make_appointment(status="confirmed", hours_from_now=24, deposit_paid=False, **extra):
    scheduled = (datetime.now(timezone.utc) + timedelta(hours=hours_from_now)).isoformat()
    apt = {
        "id": f"apt_{uuid.uuid4().hex[:8]}",
        "shop_id": "shop_1",
        "client_id": "client_1",
        "barber_id": "barber_1",
        "service_id": "service_1",
        "scheduled_at": scheduled,
        "duration_minutes": 30,
        "status": status,
        "price": 30.0,
        "deposit_required": deposit_paid,
        "deposit_amount": 20.0 if deposit_paid else 0,
        "deposit_paid": deposit_paid,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    apt.update(extra)
    return apt


# ============================================================
# Mock providers
# ============================================================

def _mock_providers():
    """Patch providers to return controllable mocks."""
    sms_mock = MagicMock()
    sms_mock.send_sms = AsyncMock(return_value=MagicMock(success=True, message_id="sms_123"))
    payment_mock = MagicMock()
    payment_mock.create_payment_link = AsyncMock(return_value=MagicMock(
        url="https://pay.test/session_123",
        session_id="sess_123",
    ))
    calendar_mock = MagicMock()
    calendar_mock.create_event = AsyncMock(return_value=None)

    return {
        "agents.get_sms": lambda: sms_mock,
        "agents.get_payment": lambda: payment_mock,
        "agents.get_calendar": lambda db: calendar_mock,
        "agents.create_sms_service": lambda db, shop_id, audit: MagicMock(
            send_sms=AsyncMock(return_value=MagicMock(success=True, message_id="sms_comp_123", error=None)),
        ),
        "agents.create_audit_logger": lambda db, shop_id: MagicMock(
            log=AsyncMock(),
        ),
    }


# ============================================================
# FEATURE 5: No-Show Fee Collection
# ============================================================

class TestNoShowFeeCollection:
    """Test NoShowEnforcementAgent.process_no_show with fee and SMS."""

    @pytest.mark.asyncio
    async def test_no_show_sends_sms_warning(self):
        """SMS warning is sent to client with consent when marked no_show."""
        apt = _make_appointment(status="no_show", hours_from_now=-1)
        db = _build_db(appointments=[apt])

        # Use a shared mock instance so the same object is used inside and outside
        sms_service_mock = MagicMock(
            send_sms=AsyncMock(return_value=MagicMock(success=True, message_id="sms_comp_123", error=None)),
        )
        mocks = _mock_providers()

        with patch("agents.get_sms", mocks["agents.get_sms"]), \
             patch("agents.get_payment", mocks["agents.get_payment"]), \
             patch("agents.create_sms_service", return_value=sms_service_mock), \
             patch("agents.create_audit_logger", return_value=MagicMock(log=AsyncMock())):
            from agents import NoShowEnforcementAgent
            agent = NoShowEnforcementAgent(db, SHOP)
            await agent.process_no_show(apt["id"], host_url="https://shop.test")

        # SMS was sent via compliance service
        assert sms_service_mock.send_sms.called
        call_kwargs = sms_service_mock.send_sms.call_args
        msg = call_kwargs.kwargs.get("message", call_kwargs[1].get("message", ""))
        assert "missed you" in msg.lower()

    @pytest.mark.asyncio
    async def test_no_show_no_sms_without_consent(self):
        """Client without SMS consent should NOT receive SMS."""
        apt = _make_appointment(status="no_show", hours_from_now=-1, client_id="client_2")
        db = _build_db(appointments=[apt])

        sms_service_mock = MagicMock(
            send_sms=AsyncMock(return_value=MagicMock(success=True, message_id="sms_x")),
        )
        mocks = _mock_providers()
        mocks["agents.create_sms_service"] = lambda db, shop_id, audit: sms_service_mock

        with patch("agents.get_sms", mocks["agents.get_sms"]), \
             patch("agents.get_payment", mocks["agents.get_payment"]), \
             patch("agents.create_sms_service", mocks["agents.create_sms_service"]), \
             patch("agents.create_audit_logger", mocks["agents.create_audit_logger"]):
            from agents import NoShowEnforcementAgent
            agent = NoShowEnforcementAgent(db, SHOP)
            await agent.process_no_show(apt["id"], host_url="https://shop.test")

        # SMS should NOT have been sent (client_2 has sms_consent=False)
        assert not sms_service_mock.send_sms.called

    @pytest.mark.asyncio
    async def test_no_show_increments_client_count(self):
        """Client no_shows counter is incremented."""
        apt = _make_appointment(status="no_show", hours_from_now=-1)
        db = _build_db(appointments=[apt])
        initial = (await db.clients.find_one({"id": "client_1"})).get("no_shows", 0)

        mocks = _mock_providers()
        with patch("agents.get_sms", mocks["agents.get_sms"]), \
             patch("agents.get_payment", mocks["agents.get_payment"]), \
             patch("agents.create_sms_service", mocks["agents.create_sms_service"]), \
             patch("agents.create_audit_logger", mocks["agents.create_audit_logger"]):
            from agents import NoShowEnforcementAgent
            agent = NoShowEnforcementAgent(db, SHOP)
            await agent.process_no_show(apt["id"])

        client = await db.clients.find_one({"id": "client_1"})
        assert client["no_shows"] == initial + 1

    @pytest.mark.asyncio
    async def test_no_show_forfeits_deposit(self):
        """If deposit was paid, it should be forfeited and revenue recovery logged."""
        apt = _make_appointment(status="no_show", hours_from_now=-1, deposit_paid=True)
        db = _build_db(appointments=[apt])

        mocks = _mock_providers()
        with patch("agents.get_sms", mocks["agents.get_sms"]), \
             patch("agents.get_payment", mocks["agents.get_payment"]), \
             patch("agents.create_sms_service", mocks["agents.create_sms_service"]), \
             patch("agents.create_audit_logger", mocks["agents.create_audit_logger"]):
            from agents import NoShowEnforcementAgent
            agent = NoShowEnforcementAgent(db, SHOP)
            await agent.process_no_show(apt["id"])

        # Check recovered_revenue_events was created
        events = await db.recovered_revenue_events.find({}).to_list(10)
        assert len(events) == 1
        assert events[0]["source"] == "no_show_fee"
        assert events[0]["amount"] == 20.0

        # Check deposit_forfeited flag
        updated_apt = await db.appointments.find_one({"id": apt["id"]})
        assert updated_apt.get("deposit_forfeited") is True

    @pytest.mark.asyncio
    async def test_no_show_creates_payment_link(self):
        """No-show fee payment link should be created and included in SMS."""
        apt = _make_appointment(status="no_show", hours_from_now=-1)
        db = _build_db(appointments=[apt])

        sms_service_mock = MagicMock(
            send_sms=AsyncMock(return_value=MagicMock(success=True, message_id="sms_x", error=None)),
        )
        mocks = _mock_providers()
        mocks["agents.create_sms_service"] = lambda db, shop_id, audit: sms_service_mock

        with patch("agents.get_sms", mocks["agents.get_sms"]), \
             patch("agents.get_payment", mocks["agents.get_payment"]), \
             patch("agents.create_sms_service", mocks["agents.create_sms_service"]), \
             patch("agents.create_audit_logger", mocks["agents.create_audit_logger"]):
            from agents import NoShowEnforcementAgent
            agent = NoShowEnforcementAgent(db, SHOP)
            await agent.process_no_show(apt["id"], host_url="https://shop.test")

        # Payment link should have been created
        payment_txns = await db.payment_transactions.find({}).to_list(10)
        assert any(t["payment_type"] == "no_show_fee" for t in payment_txns)

        # SMS message should contain the payment URL
        assert sms_service_mock.send_sms.called
        call_kwargs = sms_service_mock.send_sms.call_args
        msg = call_kwargs.kwargs.get("message", call_kwargs[1].get("message", ""))
        assert "pay.test" in msg

    @pytest.mark.asyncio
    async def test_no_show_logs_event(self):
        """NO_SHOW_DETECTED event should be logged with negative revenue impact."""
        apt = _make_appointment(status="no_show", hours_from_now=-1)
        db = _build_db(appointments=[apt])

        mocks = _mock_providers()
        with patch("agents.get_sms", mocks["agents.get_sms"]), \
             patch("agents.get_payment", mocks["agents.get_payment"]), \
             patch("agents.create_sms_service", mocks["agents.create_sms_service"]), \
             patch("agents.create_audit_logger", mocks["agents.create_audit_logger"]):
            from agents import NoShowEnforcementAgent
            agent = NoShowEnforcementAgent(db, SHOP)
            await agent.process_no_show(apt["id"])

        events = await db.events.find({}).to_list(10)
        assert len(events) == 1
        assert events[0]["event_type"] == EventType.NO_SHOW_DETECTED.value
        assert events[0]["revenue_impact"] == -30.0

    @pytest.mark.asyncio
    async def test_no_show_missing_appointment(self):
        """process_no_show with invalid appointment ID should not crash."""
        db = _build_db()

        mocks = _mock_providers()
        with patch("agents.get_sms", mocks["agents.get_sms"]), \
             patch("agents.get_payment", mocks["agents.get_payment"]), \
             patch("agents.create_sms_service", mocks["agents.create_sms_service"]), \
             patch("agents.create_audit_logger", mocks["agents.create_audit_logger"]):
            from agents import NoShowEnforcementAgent
            agent = NoShowEnforcementAgent(db, SHOP)
            await agent.process_no_show("nonexistent_id")  # Should not raise


# ============================================================
# FEATURE 7: Cancellation Window Enforcement
# ============================================================

class TestCancellationWindowSMS:
    """Test FrontDeskAgent cancellation window enforcement via SMS."""

    @pytest.mark.asyncio
    async def test_cancel_within_window_rejected(self):
        """Cancellation within window (e.g. 2h before for 4h window) should be rejected."""
        apt = _make_appointment(status="confirmed", hours_from_now=2)
        db = _build_db(appointments=[apt])

        mocks = _mock_providers()
        with patch("agents.get_sms", mocks["agents.get_sms"]), \
             patch("agents.get_payment", mocks["agents.get_payment"]), \
             patch("agents.get_calendar", mocks["agents.get_calendar"]):
            from agents import FrontDeskAgent
            agent = FrontDeskAgent(db, SHOP)
            msg, meta = await agent.process_inbound_message(CLIENT_OBJ, "CANCEL")

        assert meta["action"] == "cancellation_too_late"
        assert "4 hours" in msg or "notice" in msg.lower()
        # Appointment should still be confirmed
        updated = await db.appointments.find_one({"id": apt["id"]})
        assert updated["status"] == "confirmed"

    @pytest.mark.asyncio
    async def test_cancel_outside_window_allowed(self):
        """Cancellation with enough notice (e.g. 12h before for 4h window) should succeed."""
        apt = _make_appointment(status="confirmed", hours_from_now=12)
        db = _build_db(appointments=[apt])

        mocks = _mock_providers()
        with patch("agents.get_sms", mocks["agents.get_sms"]), \
             patch("agents.get_payment", mocks["agents.get_payment"]), \
             patch("agents.get_calendar", mocks["agents.get_calendar"]):
            from agents import FrontDeskAgent
            agent = FrontDeskAgent(db, SHOP)
            msg, meta = await agent.process_inbound_message(CLIENT_OBJ, "CANCEL")

        assert meta["action"] == "cancelled"
        updated = await db.appointments.find_one({"id": apt["id"]})
        assert updated["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_past_appointment_allowed(self):
        """Cancelling an appointment already in the past (hours_until < 0) should be allowed."""
        # hours_from_now=-1 means the appointment is past, hours_until is negative,
        # so it should NOT be blocked by the window (only positive hours_until is checked)
        apt = _make_appointment(status="confirmed", hours_from_now=-1)
        db = _build_db(appointments=[apt])

        mocks = _mock_providers()
        with patch("agents.get_sms", mocks["agents.get_sms"]), \
             patch("agents.get_payment", mocks["agents.get_payment"]), \
             patch("agents.get_calendar", mocks["agents.get_calendar"]):
            from agents import FrontDeskAgent
            agent = FrontDeskAgent(db, SHOP)
            msg, meta = await agent.process_inbound_message(CLIENT_OBJ, "CANCEL")

        assert meta["action"] == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_just_outside_window_boundary(self):
        """Cancellation just outside the window (4h+1min for 4h window) should succeed."""
        # Use 4.1 hours to ensure we're clearly outside the window
        # (exact boundary is racy due to test execution time)
        apt = _make_appointment(status="confirmed", hours_from_now=4.1)
        db = _build_db(appointments=[apt])

        mocks = _mock_providers()
        with patch("agents.get_sms", mocks["agents.get_sms"]), \
             patch("agents.get_payment", mocks["agents.get_payment"]), \
             patch("agents.get_calendar", mocks["agents.get_calendar"]):
            from agents import FrontDeskAgent
            agent = FrontDeskAgent(db, SHOP)
            msg, meta = await agent.process_inbound_message(CLIENT_OBJ, "CANCEL")

        assert meta["action"] == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_no_appointment(self):
        """CANCEL with no active appointment returns friendly message."""
        db = _build_db()

        mocks = _mock_providers()
        with patch("agents.get_sms", mocks["agents.get_sms"]), \
             patch("agents.get_payment", mocks["agents.get_payment"]), \
             patch("agents.get_calendar", mocks["agents.get_calendar"]):
            from agents import FrontDeskAgent
            agent = FrontDeskAgent(db, SHOP)
            msg, meta = await agent.process_inbound_message(CLIENT_OBJ, "CANCEL")

        assert meta["action"] == "no_appointment"

    @pytest.mark.asyncio
    async def test_cancel_window_zero_allows_all(self):
        """Shop with cancellation_window_hours=0 should allow all cancellations."""
        shop_no_window = Shop(**{**SHOP_DICT, "cancellation_window_hours": 0})
        apt = _make_appointment(status="confirmed", hours_from_now=1)
        db = _build_db(appointments=[apt])

        mocks = _mock_providers()
        with patch("agents.get_sms", mocks["agents.get_sms"]), \
             patch("agents.get_payment", mocks["agents.get_payment"]), \
             patch("agents.get_calendar", mocks["agents.get_calendar"]):
            from agents import FrontDeskAgent
            agent = FrontDeskAgent(db, shop_no_window)
            msg, meta = await agent.process_inbound_message(CLIENT_OBJ, "CANCEL")

        assert meta["action"] == "cancelled"


# ============================================================
# FEATURE 8: SMS Booking Completion
# ============================================================

class TestSMSBookingFlow:
    """Test the multi-step SMS booking conversation."""

    @pytest.mark.asyncio
    async def test_book_command_creates_session(self):
        """BOOK command should create a booking session and list services."""
        db = _build_db()

        mocks = _mock_providers()
        with patch("agents.get_sms", mocks["agents.get_sms"]), \
             patch("agents.get_payment", mocks["agents.get_payment"]), \
             patch("agents.get_calendar", mocks["agents.get_calendar"]):
            from agents import FrontDeskAgent
            agent = FrontDeskAgent(db, SHOP)
            msg, meta = await agent.process_inbound_message(CLIENT_OBJ, "BOOK")

        assert meta["action"] == "booking_started"
        assert "Fade" in msg
        assert "Lineup" in msg

        # Session should exist
        session = await db.sms_booking_sessions.find_one({"client_id": "client_1"})
        assert session is not None
        assert session["step"] == "awaiting_service"
        assert len(session["service_ids"]) == 2

    @pytest.mark.asyncio
    async def test_service_selection(self):
        """Replying with service number should advance to barber selection."""
        db = _build_db()

        mocks = _mock_providers()
        with patch("agents.get_sms", mocks["agents.get_sms"]), \
             patch("agents.get_payment", mocks["agents.get_payment"]), \
             patch("agents.get_calendar", mocks["agents.get_calendar"]):
            from agents import FrontDeskAgent
            agent = FrontDeskAgent(db, SHOP)

            # Step 1: BOOK
            await agent.process_inbound_message(CLIENT_OBJ, "BOOK")

            # Step 2: Select service "1" (Fade)
            msg, meta = await agent.process_inbound_message(CLIENT_OBJ, "1")

        assert meta["action"] == "service_selected"
        assert meta["service_id"] == "service_1"
        assert "James" in msg
        assert "Marcus" in msg

        session = await db.sms_booking_sessions.find_one({"client_id": "client_1"})
        assert session["step"] == "awaiting_barber"
        assert session["service_id"] == "service_1"

    @pytest.mark.asyncio
    async def test_invalid_service_number(self):
        """Invalid service number should return error message."""
        db = _build_db()

        mocks = _mock_providers()
        with patch("agents.get_sms", mocks["agents.get_sms"]), \
             patch("agents.get_payment", mocks["agents.get_payment"]), \
             patch("agents.get_calendar", mocks["agents.get_calendar"]):
            from agents import FrontDeskAgent
            agent = FrontDeskAgent(db, SHOP)

            await agent.process_inbound_message(CLIENT_OBJ, "BOOK")
            msg, meta = await agent.process_inbound_message(CLIENT_OBJ, "99")

        assert meta["action"] == "booking_invalid_input"
        assert "1" in msg and "2" in msg  # Should tell them valid range

    @pytest.mark.asyncio
    async def test_non_numeric_input_during_booking(self):
        """Non-numeric input during service selection should return error."""
        db = _build_db()

        mocks = _mock_providers()
        with patch("agents.get_sms", mocks["agents.get_sms"]), \
             patch("agents.get_payment", mocks["agents.get_payment"]), \
             patch("agents.get_calendar", mocks["agents.get_calendar"]):
            from agents import FrontDeskAgent
            agent = FrontDeskAgent(db, SHOP)

            await agent.process_inbound_message(CLIENT_OBJ, "BOOK")
            msg, meta = await agent.process_inbound_message(CLIENT_OBJ, "hello")

        assert meta["action"] == "booking_invalid_input"

    @pytest.mark.asyncio
    async def test_cancel_during_booking(self):
        """CANCEL during booking flow should clear session."""
        db = _build_db()

        mocks = _mock_providers()
        with patch("agents.get_sms", mocks["agents.get_sms"]), \
             patch("agents.get_payment", mocks["agents.get_payment"]), \
             patch("agents.get_calendar", mocks["agents.get_calendar"]):
            from agents import FrontDeskAgent
            agent = FrontDeskAgent(db, SHOP)

            await agent.process_inbound_message(CLIENT_OBJ, "BOOK")
            msg, meta = await agent.process_inbound_message(CLIENT_OBJ, "CANCEL")

        assert meta["action"] == "booking_cancelled"
        session = await db.sms_booking_sessions.find_one({"client_id": "client_1"})
        assert session is None

    @pytest.mark.asyncio
    async def test_help_during_booking_clears_session(self):
        """HELP during booking flow should clear session and show help."""
        db = _build_db()

        mocks = _mock_providers()
        with patch("agents.get_sms", mocks["agents.get_sms"]), \
             patch("agents.get_payment", mocks["agents.get_payment"]), \
             patch("agents.get_calendar", mocks["agents.get_calendar"]):
            from agents import FrontDeskAgent
            agent = FrontDeskAgent(db, SHOP)

            await agent.process_inbound_message(CLIENT_OBJ, "BOOK")
            msg, meta = await agent.process_inbound_message(CLIENT_OBJ, "HELP")

        assert meta["action"] == "help"
        session = await db.sms_booking_sessions.find_one({"client_id": "client_1"})
        assert session is None

    @pytest.mark.asyncio
    async def test_barber_selection_shows_slots(self):
        """Selecting a barber should show available time slots."""
        db = _build_db()

        mocks = _mock_providers()

        from scheduling import TimeSlot
        tomorrow = datetime.now(timezone.utc).replace(hour=14, minute=0, second=0, microsecond=0) + timedelta(days=1)
        mock_slots = [
            TimeSlot(
                start=tomorrow,
                end=tomorrow + timedelta(minutes=30),
                barber_id="barber_1",
                barber_name="James",
            ),
            TimeSlot(
                start=tomorrow + timedelta(hours=1),
                end=tomorrow + timedelta(hours=1, minutes=30),
                barber_id="barber_1",
                barber_name="James",
            ),
        ]

        with patch("agents.get_sms", mocks["agents.get_sms"]), \
             patch("agents.get_payment", mocks["agents.get_payment"]), \
             patch("agents.get_calendar", mocks["agents.get_calendar"]), \
             patch("scheduling.create_scheduling_engine") as mock_engine:
            mock_engine.return_value.get_available_slots = AsyncMock(return_value=mock_slots)

            from agents import FrontDeskAgent
            agent = FrontDeskAgent(db, SHOP)

            await agent.process_inbound_message(CLIENT_OBJ, "BOOK")
            await agent.process_inbound_message(CLIENT_OBJ, "1")  # Select Fade
            msg, meta = await agent.process_inbound_message(CLIENT_OBJ, "1")  # Select James

        assert meta["action"] == "barber_selected"
        assert "James" in msg
        assert "1." in msg
        assert "2." in msg

        session = await db.sms_booking_sessions.find_one({"client_id": "client_1"})
        assert session["step"] == "awaiting_time"
        # Mock returns 2 slots per day call; the code iterates multiple days and caps at 5
        assert len(session["slot_options"]) >= 2
        assert len(session["slot_options"]) <= 5

    @pytest.mark.asyncio
    async def test_full_booking_flow_creates_appointment(self):
        """Complete flow: BOOK → service → barber → time → appointment created."""
        db = _build_db()

        mocks = _mock_providers()

        from scheduling import TimeSlot
        # Use 3 days ahead (>48h) so deposit is NOT required for a clean client
        future_slot = datetime.now(timezone.utc).replace(hour=14, minute=0, second=0, microsecond=0) + timedelta(days=3)
        mock_slots = [
            TimeSlot(
                start=future_slot,
                end=future_slot + timedelta(minutes=30),
                barber_id="barber_1",
                barber_name="James",
            ),
        ]

        with patch("agents.get_sms", mocks["agents.get_sms"]), \
             patch("agents.get_payment", mocks["agents.get_payment"]), \
             patch("agents.get_calendar", mocks["agents.get_calendar"]), \
             patch("scheduling.create_scheduling_engine") as mock_engine:
            mock_engine.return_value.get_available_slots = AsyncMock(return_value=mock_slots)

            from agents import FrontDeskAgent
            agent = FrontDeskAgent(db, SHOP)

            await agent.process_inbound_message(CLIENT_OBJ, "BOOK")
            await agent.process_inbound_message(CLIENT_OBJ, "1")  # Fade
            await agent.process_inbound_message(CLIENT_OBJ, "1")  # James
            msg, meta = await agent.process_inbound_message(CLIENT_OBJ, "1")  # First slot

        assert meta["action"] == "booking_completed"
        assert "appointment_id" in meta
        assert "all set" in msg.lower() or "booked" in msg.lower()

        # Appointment should exist in DB
        apt = await db.appointments.find_one({"id": meta["appointment_id"]})
        assert apt is not None
        assert apt["service_id"] == "service_1"
        assert apt["barber_id"] == "barber_1"
        assert apt["status"] == "confirmed"
        assert apt["source"] == "sms"

        # Booking session should be cleared
        session = await db.sms_booking_sessions.find_one({"client_id": "client_1"})
        assert session is None

    @pytest.mark.asyncio
    async def test_booking_with_deposit_required(self):
        """Client with no-shows should get deposit_pending status."""
        client_data = dict(CLIENT_CONSENT)
        client_data["no_shows"] = 2
        db = _build_db()
        db._set("clients", [client_data, dict(CLIENT_NO_CONSENT)])

        client_obj = Client(**{k: v for k, v in client_data.items() if k != "_id"})

        mocks = _mock_providers()

        from scheduling import TimeSlot
        tomorrow = datetime.now(timezone.utc).replace(hour=14, minute=0, second=0, microsecond=0) + timedelta(days=1)
        mock_slots = [
            TimeSlot(
                start=tomorrow,
                end=tomorrow + timedelta(minutes=30),
                barber_id="barber_1",
                barber_name="James",
            ),
        ]

        with patch("agents.get_sms", mocks["agents.get_sms"]), \
             patch("agents.get_payment", mocks["agents.get_payment"]), \
             patch("agents.get_calendar", mocks["agents.get_calendar"]), \
             patch("scheduling.create_scheduling_engine") as mock_engine:
            mock_engine.return_value.get_available_slots = AsyncMock(return_value=mock_slots)

            from agents import FrontDeskAgent
            agent = FrontDeskAgent(db, SHOP)

            await agent.process_inbound_message(client_obj, "BOOK")
            await agent.process_inbound_message(client_obj, "1")
            await agent.process_inbound_message(client_obj, "1")
            msg, meta = await agent.process_inbound_message(client_obj, "1")

        assert meta["action"] == "booking_completed_deposit_pending"
        apt = await db.appointments.find_one({"id": meta["appointment_id"]})
        assert apt["status"] == "deposit_pending"
        assert apt["deposit_required"] is True
        assert "deposit" in msg.lower()

    @pytest.mark.asyncio
    async def test_no_available_slots(self):
        """If no slots available, booking should end with friendly message."""
        db = _build_db()

        mocks = _mock_providers()

        with patch("agents.get_sms", mocks["agents.get_sms"]), \
             patch("agents.get_payment", mocks["agents.get_payment"]), \
             patch("agents.get_calendar", mocks["agents.get_calendar"]), \
             patch("scheduling.create_scheduling_engine") as mock_engine:
            mock_engine.return_value.get_available_slots = AsyncMock(return_value=[])

            from agents import FrontDeskAgent
            agent = FrontDeskAgent(db, SHOP)

            await agent.process_inbound_message(CLIENT_OBJ, "BOOK")
            await agent.process_inbound_message(CLIENT_OBJ, "1")
            msg, meta = await agent.process_inbound_message(CLIENT_OBJ, "1")

        assert meta["action"] == "no_slots"
        assert "no available" in msg.lower() or "sorry" in msg.lower()

    @pytest.mark.asyncio
    async def test_expired_session_ignored(self):
        """Expired booking session should be cleared and message treated normally."""
        db = _build_db()

        # Manually insert an expired session
        expired_time = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
        await db.sms_booking_sessions.insert_one({
            "id": "expired_session",
            "shop_id": "shop_1",
            "client_id": "client_1",
            "step": "awaiting_service",
            "service_ids": ["service_1"],
            "expires_at": expired_time,
            "created_at": expired_time,
            "updated_at": expired_time,
        })

        mocks = _mock_providers()
        with patch("agents.get_sms", mocks["agents.get_sms"]), \
             patch("agents.get_payment", mocks["agents.get_payment"]), \
             patch("agents.get_calendar", mocks["agents.get_calendar"]):
            from agents import FrontDeskAgent
            agent = FrontDeskAgent(db, SHOP)

            # "1" would match booking flow if session was active, but should go to greeting
            msg, meta = await agent.process_inbound_message(CLIENT_OBJ, "1")

        # Should NOT be booking_invalid_input (session expired)
        assert meta["action"] == "greeting"

    @pytest.mark.asyncio
    async def test_no_services_available(self):
        """BOOK when no services exist should return friendly message."""
        db = _build_db()
        db._set("services", [])  # No services

        mocks = _mock_providers()
        with patch("agents.get_sms", mocks["agents.get_sms"]), \
             patch("agents.get_payment", mocks["agents.get_payment"]), \
             patch("agents.get_calendar", mocks["agents.get_calendar"]):
            from agents import FrontDeskAgent
            agent = FrontDeskAgent(db, SHOP)
            msg, meta = await agent.process_inbound_message(CLIENT_OBJ, "BOOK")

        assert meta["action"] == "no_services"

    @pytest.mark.asyncio
    async def test_no_barbers_available(self):
        """If no barbers exist, booking should end after service selection."""
        db = _build_db()
        db._set("barbers", [])  # No barbers

        mocks = _mock_providers()
        with patch("agents.get_sms", mocks["agents.get_sms"]), \
             patch("agents.get_payment", mocks["agents.get_payment"]), \
             patch("agents.get_calendar", mocks["agents.get_calendar"]):
            from agents import FrontDeskAgent
            agent = FrontDeskAgent(db, SHOP)

            await agent.process_inbound_message(CLIENT_OBJ, "BOOK")
            msg, meta = await agent.process_inbound_message(CLIENT_OBJ, "1")

        assert meta["action"] == "no_barbers"

    @pytest.mark.asyncio
    async def test_second_service_selection(self):
        """Selecting service 2 should use the second service."""
        db = _build_db()

        mocks = _mock_providers()
        with patch("agents.get_sms", mocks["agents.get_sms"]), \
             patch("agents.get_payment", mocks["agents.get_payment"]), \
             patch("agents.get_calendar", mocks["agents.get_calendar"]):
            from agents import FrontDeskAgent
            agent = FrontDeskAgent(db, SHOP)

            await agent.process_inbound_message(CLIENT_OBJ, "BOOK")
            msg, meta = await agent.process_inbound_message(CLIENT_OBJ, "2")

        assert meta["action"] == "service_selected"
        assert meta["service_id"] == "service_2"
        assert "Lineup" in msg

    @pytest.mark.asyncio
    async def test_appointment_keyword_starts_booking(self):
        """'APPOINTMENT' keyword should also start booking flow."""
        db = _build_db()

        mocks = _mock_providers()
        with patch("agents.get_sms", mocks["agents.get_sms"]), \
             patch("agents.get_payment", mocks["agents.get_payment"]), \
             patch("agents.get_calendar", mocks["agents.get_calendar"]):
            from agents import FrontDeskAgent
            agent = FrontDeskAgent(db, SHOP)
            msg, meta = await agent.process_inbound_message(CLIENT_OBJ, "APPOINTMENT")

        assert meta["action"] == "booking_started"


# ============================================================
# Edge cases across features
# ============================================================

class TestEdgeCases:
    """Cross-feature edge case tests."""

    @pytest.mark.asyncio
    async def test_booking_then_cancel_then_book_again(self):
        """Client should be able to cancel booking flow and start over."""
        db = _build_db()

        mocks = _mock_providers()
        with patch("agents.get_sms", mocks["agents.get_sms"]), \
             patch("agents.get_payment", mocks["agents.get_payment"]), \
             patch("agents.get_calendar", mocks["agents.get_calendar"]):
            from agents import FrontDeskAgent
            agent = FrontDeskAgent(db, SHOP)

            # Start booking
            await agent.process_inbound_message(CLIENT_OBJ, "BOOK")
            # Cancel it
            msg1, meta1 = await agent.process_inbound_message(CLIENT_OBJ, "CANCEL")
            assert meta1["action"] == "booking_cancelled"

            # Start again
            msg2, meta2 = await agent.process_inbound_message(CLIENT_OBJ, "BOOK")
            assert meta2["action"] == "booking_started"
            assert "Fade" in msg2

    @pytest.mark.asyncio
    async def test_confirm_without_booking_session_works_normally(self):
        """YES/CONFIRM should still work for appointment confirmation when no booking session."""
        apt = _make_appointment(status="pending", hours_from_now=24)
        db = _build_db(appointments=[apt])

        mocks = _mock_providers()
        with patch("agents.get_sms", mocks["agents.get_sms"]), \
             patch("agents.get_payment", mocks["agents.get_payment"]), \
             patch("agents.get_calendar", mocks["agents.get_calendar"]):
            from agents import FrontDeskAgent
            agent = FrontDeskAgent(db, SHOP)
            msg, meta = await agent.process_inbound_message(CLIENT_OBJ, "YES")

        assert meta["action"] == "confirmed"

    @pytest.mark.asyncio
    async def test_status_check_during_no_booking_session(self):
        """STATUS command should still work with no booking session."""
        apt = _make_appointment(status="confirmed", hours_from_now=24)
        db = _build_db(appointments=[apt])

        mocks = _mock_providers()
        with patch("agents.get_sms", mocks["agents.get_sms"]), \
             patch("agents.get_payment", mocks["agents.get_payment"]), \
             patch("agents.get_calendar", mocks["agents.get_calendar"]):
            from agents import FrontDeskAgent
            agent = FrontDeskAgent(db, SHOP)
            msg, meta = await agent.process_inbound_message(CLIENT_OBJ, "STATUS")

        assert meta["action"] == "status_checked"
