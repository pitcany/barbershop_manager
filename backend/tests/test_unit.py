"""
Unit tests for Barbershop Autopilot core business logic.

Covers:
1. Appointment state machine transitions
2. Deposit requirement logic
3. Waitlist time-matching with flexibility boundaries
4. Rate limiter behavior
5. JWT token creation and expiration
6. SMS consent revocation and STOP/opt-out
7. Revenue logger same-day boundary conditions
8. Provider switching with env variables
9. Scheduled job idempotency
"""
import os
import sys
import time
import asyncio
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure backend directory is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================
# Fixtures & helpers
# ============================================================

class MockCollection:
    """In-memory mock for a MongoDB collection."""

    def __init__(self, docs=None):
        self._docs = list(docs or [])
        self._inserted = []

    async def find_one(self, query=None, projection=None):
        for doc in self._docs:
            if self._matches(doc, query or {}):
                return dict(doc)
        return None

    def find(self, query=None, projection=None):
        results = [dict(d) for d in self._docs if self._matches(d, query or {})]
        return _MockCursor(results)

    async def insert_one(self, doc):
        self._docs.append(dict(doc))
        self._inserted.append(dict(doc))
        return MagicMock(inserted_id="mock_id")

    async def update_one(self, query, update, upsert=False):
        for doc in self._docs:
            if self._matches(doc, query):
                if "$set" in update:
                    doc.update(update["$set"])
                if "$inc" in update:
                    for k, v in update["$inc"].items():
                        doc[k] = doc.get(k, 0) + v
                return MagicMock(modified_count=1, matched_count=1)
        return MagicMock(modified_count=0, matched_count=0)

    def _matches(self, doc, query):
        for key, val in query.items():
            if key == "$or":
                if not any(self._matches(doc, sub) for sub in val):
                    return False
                continue
            doc_val = doc.get(key)
            if isinstance(val, dict):
                if "$in" in val:
                    if doc_val not in val["$in"]:
                        return False
                elif "$gte" in val or "$lte" in val:
                    if "$gte" in val and doc_val < val["$gte"]:
                        return False
                    if "$lte" in val and doc_val > val["$lte"]:
                        return False
                elif "$regex" in val:
                    import re
                    if not re.search(val["$regex"], str(doc_val or "")):
                        return False
                else:
                    if doc_val != val:
                        return False
            else:
                if doc_val != val:
                    return False
        return True


class _MockCursor:
    def __init__(self, results):
        self._results = results

    async def to_list(self, length=100):
        return self._results[:length]


class MockDB:
    """In-memory mock for the whole database."""

    def __init__(self):
        self.appointments = MockCollection()
        self.clients = MockCollection()
        self.messages = MockCollection()
        self.barbers = MockCollection()
        self.services = MockCollection()
        self.waitlist = MockCollection()
        self.events = MockCollection()
        self.payments = MockCollection()
        self.shops = MockCollection()
        self.recovered_revenue_events = MockCollection()
        self.google_calendar_tokens = MockCollection()


def make_shop(**overrides):
    from models import Shop
    defaults = {
        "id": "shop-1",
        "name": "Test Barbershop",
        "phone": "+15551234567",
        "address": "123 Main St",
        "timezone": "America/New_York",
        "deposit_amount": 20.0,
        "deposit_required_hours": 48,
        "confirmation_window_hours": 24,
        "cancellation_window_hours": 4,
        "max_messages_per_day": 4,
    }
    defaults.update(overrides)
    return Shop(**defaults)


def make_client(**overrides):
    defaults = {
        "id": "client-1",
        "shop_id": "shop-1",
        "name": "John Doe",
        "phone": "+15559876543",
        "sms_consent": True,
        "no_shows": 0,
        "total_appointments": 3,
    }
    defaults.update(overrides)
    return defaults


def make_appointment(**overrides):
    from models import AppointmentStatus
    defaults = {
        "id": "apt-1",
        "shop_id": "shop-1",
        "client_id": "client-1",
        "barber_id": "barber-1",
        "service_id": "service-1",
        "status": AppointmentStatus.PENDING.value,
        "scheduled_at": (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat(),
        "duration_minutes": 30,
    }
    defaults.update(overrides)
    return defaults


# ============================================================
# 1. Appointment State Machine Transitions
# ============================================================


class TestAppointmentStateMachine:
    """Tests valid and invalid appointment state transitions."""

    @pytest.mark.asyncio
    async def test_confirm_from_pending(self):
        """PENDING -> CONFIRMED via confirmation handler."""
        from models import Client, AppointmentStatus
        from agents import FrontDeskAgent

        db = MockDB()
        shop = make_shop()
        apt = make_appointment(status=AppointmentStatus.PENDING.value)
        db.appointments = MockCollection([apt])

        agent = FrontDeskAgent(db, shop)
        client = Client(**make_client())
        msg, meta = await agent.process_inbound_message(client, "CONFIRM")

        assert meta["action"] == "confirmed"
        updated = await db.appointments.find_one({"id": "apt-1"})
        assert updated["status"] == AppointmentStatus.CONFIRMED.value

    @pytest.mark.asyncio
    async def test_confirm_from_deposit_paid(self):
        """DEPOSIT_PAID -> CONFIRMED via confirmation handler."""
        from models import Client, AppointmentStatus
        from agents import FrontDeskAgent

        db = MockDB()
        shop = make_shop()
        apt = make_appointment(status=AppointmentStatus.DEPOSIT_PAID.value)
        db.appointments = MockCollection([apt])

        agent = FrontDeskAgent(db, shop)
        client = Client(**make_client())
        msg, meta = await agent.process_inbound_message(client, "YES")

        assert meta["action"] == "confirmed"
        updated = await db.appointments.find_one({"id": "apt-1"})
        assert updated["status"] == AppointmentStatus.CONFIRMED.value

    @pytest.mark.asyncio
    async def test_confirm_no_pending_appointment(self):
        """Confirming when no pending appointment returns informative message."""
        from models import Client
        from agents import FrontDeskAgent

        db = MockDB()
        shop = make_shop()
        agent = FrontDeskAgent(db, shop)
        client = Client(**make_client())
        msg, meta = await agent.process_inbound_message(client, "CONFIRM")

        assert meta["action"] == "no_appointment"
        assert "don't have any" in msg.lower()

    @pytest.mark.asyncio
    async def test_cancel_from_confirmed(self):
        """CONFIRMED -> CANCELLED via cancellation handler."""
        from models import Client, AppointmentStatus
        from agents import FrontDeskAgent

        db = MockDB()
        shop = make_shop()
        apt = make_appointment(status=AppointmentStatus.CONFIRMED.value)
        db.appointments = MockCollection([apt])

        agent = FrontDeskAgent(db, shop)
        client = Client(**make_client())
        msg, meta = await agent.process_inbound_message(client, "CANCEL")

        assert meta["action"] == "cancelled"
        updated = await db.appointments.find_one({"id": "apt-1"})
        assert updated["status"] == AppointmentStatus.CANCELLED.value

    @pytest.mark.asyncio
    async def test_cancel_from_pending(self):
        """PENDING -> CANCELLED via cancellation handler."""
        from models import Client, AppointmentStatus
        from agents import FrontDeskAgent

        db = MockDB()
        shop = make_shop()
        apt = make_appointment(status=AppointmentStatus.PENDING.value)
        db.appointments = MockCollection([apt])

        agent = FrontDeskAgent(db, shop)
        client = Client(**make_client())
        msg, meta = await agent.process_inbound_message(client, "NO")

        assert meta["action"] == "cancelled"

    @pytest.mark.asyncio
    async def test_cannot_cancel_completed(self):
        """COMPLETED appointment should not be cancellable."""
        from models import Client, AppointmentStatus
        from agents import FrontDeskAgent

        db = MockDB()
        shop = make_shop()
        apt = make_appointment(status=AppointmentStatus.COMPLETED.value)
        db.appointments = MockCollection([apt])

        agent = FrontDeskAgent(db, shop)
        client = Client(**make_client())
        msg, meta = await agent.process_inbound_message(client, "CANCEL")

        assert meta["action"] == "no_appointment"

    @pytest.mark.asyncio
    async def test_no_show_increments_client_counter(self):
        """process_no_show updates appointment status and increments client no_shows."""
        from models import AppointmentStatus
        from agents import NoShowEnforcementAgent

        db = MockDB()
        shop = make_shop()
        client = make_client(no_shows=0)
        apt = make_appointment(status=AppointmentStatus.CONFIRMED.value)
        service = {"id": "service-1", "name": "Haircut", "price": 35.0}
        db.appointments = MockCollection([apt])
        db.clients = MockCollection([client])
        db.services = MockCollection([service])

        agent = NoShowEnforcementAgent(db, shop)
        await agent.process_no_show("apt-1")

        updated_apt = await db.appointments.find_one({"id": "apt-1"})
        assert updated_apt["status"] == AppointmentStatus.NO_SHOW.value

        updated_client = await db.clients.find_one({"id": "client-1"})
        assert updated_client["no_shows"] == 1

    @pytest.mark.asyncio
    async def test_status_check_command(self):
        """STATUS command returns current appointment info."""
        from models import Client, AppointmentStatus
        from agents import FrontDeskAgent

        db = MockDB()
        shop = make_shop()
        apt = make_appointment(status=AppointmentStatus.CONFIRMED.value)
        barber = {"id": "barber-1", "shop_id": "shop-1", "name": "Mike", "active": True}
        service = {"id": "service-1", "shop_id": "shop-1", "name": "Haircut", "price": 35}
        db.appointments = MockCollection([apt])
        db.barbers = MockCollection([barber])
        db.services = MockCollection([service])

        agent = FrontDeskAgent(db, shop)
        client = Client(**make_client())
        msg, meta = await agent.process_inbound_message(client, "STATUS")

        assert meta["action"] == "status_checked"

    @pytest.mark.asyncio
    async def test_help_command(self):
        """HELP command returns help response."""
        from models import Client
        from agents import FrontDeskAgent

        db = MockDB()
        shop = make_shop()
        agent = FrontDeskAgent(db, shop)
        client = Client(**make_client())
        msg, meta = await agent.process_inbound_message(client, "HELP")

        assert meta["action"] == "help"

    @pytest.mark.asyncio
    async def test_unrecognized_message_returns_greeting(self):
        """Unknown message returns greeting."""
        from models import Client
        from agents import FrontDeskAgent

        db = MockDB()
        shop = make_shop()
        agent = FrontDeskAgent(db, shop)
        client = Client(**make_client())
        msg, meta = await agent.process_inbound_message(client, "hello there")

        assert meta["action"] == "greeting"


# ============================================================
# 2. Deposit Requirement Logic
# ============================================================


class TestDepositRequirement:

    @pytest.mark.asyncio
    async def test_no_deposit_far_ahead_no_prior_no_shows(self):
        """49 hours away, 0 no-shows -> deposit NOT required."""
        from agents import NoShowEnforcementAgent

        db = MockDB()
        shop = make_shop(deposit_required_hours=48)
        agent = NoShowEnforcementAgent(db, shop)

        apt = make_appointment(
            scheduled_at=(datetime.now(timezone.utc) + timedelta(hours=49)).isoformat()
        )
        client = make_client(no_shows=0)

        assert await agent.check_deposit_requirement(apt, client) is False

    @pytest.mark.asyncio
    async def test_deposit_required_close_to_appointment(self):
        """47 hours away, 0 no-shows -> deposit required (within 48h threshold)."""
        from agents import NoShowEnforcementAgent

        db = MockDB()
        shop = make_shop(deposit_required_hours=48)
        agent = NoShowEnforcementAgent(db, shop)

        apt = make_appointment(
            scheduled_at=(datetime.now(timezone.utc) + timedelta(hours=47)).isoformat()
        )
        client = make_client(no_shows=0)

        assert await agent.check_deposit_requirement(apt, client) is True

    @pytest.mark.asyncio
    async def test_deposit_required_with_prior_no_shows(self):
        """Far ahead but 1+ no-shows -> deposit required."""
        from agents import NoShowEnforcementAgent

        db = MockDB()
        shop = make_shop(deposit_required_hours=48)
        agent = NoShowEnforcementAgent(db, shop)

        apt = make_appointment(
            scheduled_at=(datetime.now(timezone.utc) + timedelta(hours=100)).isoformat()
        )
        client = make_client(no_shows=2)

        assert await agent.check_deposit_requirement(apt, client) is True

    @pytest.mark.asyncio
    async def test_deposit_boundary_exactly_at_threshold(self):
        """Exactly 48 hours away -> NOT required (uses < operator)."""
        from agents import NoShowEnforcementAgent

        db = MockDB()
        shop = make_shop(deposit_required_hours=48)
        agent = NoShowEnforcementAgent(db, shop)

        apt = make_appointment(
            scheduled_at=(datetime.now(timezone.utc) + timedelta(hours=48, seconds=1)).isoformat()
        )
        client = make_client(no_shows=0)

        assert await agent.check_deposit_requirement(apt, client) is False


# ============================================================
# 3. Waitlist Time-Matching
# ============================================================


class TestWaitlistMatching:

    @pytest.mark.asyncio
    async def test_match_within_flexibility(self):
        """Waitlist entry within flexibility window matches."""
        from agents import WaitlistFillAgent

        db = MockDB()
        shop = make_shop()
        cancelled_time = datetime(2025, 6, 15, 10, 0, tzinfo=timezone.utc)
        preferred_time = datetime(2025, 6, 15, 11, 0, tzinfo=timezone.utc)

        cancelled_apt = make_appointment(
            scheduled_at=cancelled_time.isoformat(),
            service_id="svc-1", barber_id="barber-1"
        )
        waitlist_entry = {
            "id": "wl-1", "shop_id": "shop-1", "client_id": "client-2",
            "service_id": "svc-1", "barber_id": "barber-1",
            "preferred_date": preferred_time.isoformat(),
            "flexible_hours": 2, "active": True, "contact_attempts": 0,
        }
        db.waitlist = MockCollection([waitlist_entry])

        agent = WaitlistFillAgent(db, shop)
        matches = await agent.find_waitlist_matches(cancelled_apt)

        assert len(matches) == 1
        assert matches[0]["id"] == "wl-1"

    @pytest.mark.asyncio
    async def test_no_match_outside_flexibility(self):
        """Waitlist entry outside flexibility window is excluded."""
        from agents import WaitlistFillAgent

        db = MockDB()
        shop = make_shop()
        cancelled_time = datetime(2025, 6, 15, 10, 0, tzinfo=timezone.utc)
        preferred_time = datetime(2025, 6, 15, 14, 0, tzinfo=timezone.utc)  # 4 hours diff

        cancelled_apt = make_appointment(
            scheduled_at=cancelled_time.isoformat(),
            service_id="svc-1", barber_id="barber-1"
        )
        waitlist_entry = {
            "id": "wl-1", "shop_id": "shop-1", "client_id": "client-2",
            "service_id": "svc-1", "barber_id": "barber-1",
            "preferred_date": preferred_time.isoformat(),
            "flexible_hours": 2, "active": True, "contact_attempts": 0,
        }
        db.waitlist = MockCollection([waitlist_entry])

        agent = WaitlistFillAgent(db, shop)
        matches = await agent.find_waitlist_matches(cancelled_apt)

        assert len(matches) == 0

    @pytest.mark.asyncio
    async def test_no_barber_preference_matches_any(self):
        """Waitlist entry with barber_id=None matches any barber."""
        from agents import WaitlistFillAgent

        db = MockDB()
        shop = make_shop()
        cancelled_time = datetime(2025, 6, 15, 10, 0, tzinfo=timezone.utc)

        cancelled_apt = make_appointment(
            scheduled_at=cancelled_time.isoformat(),
            service_id="svc-1", barber_id="barber-99"
        )
        waitlist_entry = {
            "id": "wl-1", "shop_id": "shop-1", "client_id": "client-2",
            "service_id": "svc-1", "barber_id": None,
            "preferred_date": cancelled_time.isoformat(),
            "flexible_hours": 2, "active": True, "contact_attempts": 0,
        }
        db.waitlist = MockCollection([waitlist_entry])

        agent = WaitlistFillAgent(db, shop)
        matches = await agent.find_waitlist_matches(cancelled_apt)

        assert len(matches) == 1

    @pytest.mark.asyncio
    async def test_matches_sorted_by_contact_attempts(self):
        """Multiple matches should be sorted by contact_attempts ascending."""
        from agents import WaitlistFillAgent

        db = MockDB()
        shop = make_shop()
        cancelled_time = datetime(2025, 6, 15, 10, 0, tzinfo=timezone.utc)

        cancelled_apt = make_appointment(
            scheduled_at=cancelled_time.isoformat(),
            service_id="svc-1", barber_id="barber-1"
        )
        entries = [
            {"id": "wl-a", "shop_id": "shop-1", "client_id": "c1",
             "service_id": "svc-1", "barber_id": "barber-1",
             "preferred_date": cancelled_time.isoformat(),
             "flexible_hours": 2, "active": True, "contact_attempts": 3},
            {"id": "wl-b", "shop_id": "shop-1", "client_id": "c2",
             "service_id": "svc-1", "barber_id": "barber-1",
             "preferred_date": cancelled_time.isoformat(),
             "flexible_hours": 2, "active": True, "contact_attempts": 0},
        ]
        db.waitlist = MockCollection(entries)

        agent = WaitlistFillAgent(db, shop)
        matches = await agent.find_waitlist_matches(cancelled_apt)

        assert len(matches) == 2
        assert matches[0]["id"] == "wl-b"  # fewer attempts first


# ============================================================
# 4. Rate Limiter
# ============================================================


class TestRateLimiter:

    def setup_method(self):
        """Clear rate limit state before each test."""
        from deps import _rate_limit_store, _rate_limit_windows
        _rate_limit_store.clear()
        _rate_limit_windows.clear()

    def test_first_request_allowed(self):
        from deps import check_rate_limit
        assert check_rate_limit("test-key", max_requests=5, window_seconds=60) is True

    def test_under_limit_allowed(self):
        from deps import check_rate_limit
        for _ in range(4):
            assert check_rate_limit("test-key", max_requests=5, window_seconds=60) is True

    def test_at_limit_blocked(self):
        from deps import check_rate_limit
        for _ in range(5):
            check_rate_limit("test-key", max_requests=5, window_seconds=60)
        # 6th request should be blocked
        assert check_rate_limit("test-key", max_requests=5, window_seconds=60) is False

    def test_different_keys_independent(self):
        from deps import check_rate_limit
        for _ in range(5):
            check_rate_limit("key-a", max_requests=5, window_seconds=60)
        # key-a exhausted, but key-b should still work
        assert check_rate_limit("key-b", max_requests=5, window_seconds=60) is True

    def test_expired_entries_removed(self):
        from deps import check_rate_limit, _rate_limit_store
        # Fill up the limit with a tiny window
        for _ in range(5):
            check_rate_limit("expire-key", max_requests=5, window_seconds=0.1)
        # Wait for window to expire
        time.sleep(0.15)
        # Should be allowed again
        assert check_rate_limit("expire-key", max_requests=5, window_seconds=0.1) is True


# ============================================================
# 5. JWT Token Creation & Expiration
# ============================================================


class TestJWT:

    def test_create_and_verify_token(self):
        from deps import create_access_token, verify_token
        token = create_access_token({"sub": "admin", "shop_id": "shop-1"})
        payload = verify_token(token)
        assert payload is not None
        assert payload["sub"] == "admin"
        assert payload["shop_id"] == "shop-1"
        assert "exp" in payload

    def test_expired_token_rejected(self):
        import jwt as pyjwt
        from deps import SECRET_KEY, ALGORITHM, verify_token
        expired_payload = {
            "sub": "admin",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1)
        }
        token = pyjwt.encode(expired_payload, SECRET_KEY, algorithm=ALGORITHM)
        assert verify_token(token) is None

    def test_invalid_signature_rejected(self):
        import jwt as pyjwt
        from deps import ALGORITHM, verify_token
        token = pyjwt.encode(
            {"sub": "admin", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
            "wrong-secret-key",
            algorithm=ALGORITHM
        )
        assert verify_token(token) is None

    @pytest.mark.asyncio
    async def test_get_current_user_no_header(self):
        from deps import get_current_user
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(authorization=None)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_bad_header(self):
        from deps import get_current_user
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(authorization="Token abc123")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_expired_token(self):
        import jwt as pyjwt
        from deps import get_current_user, SECRET_KEY, ALGORITHM
        from fastapi import HTTPException
        token = pyjwt.encode(
            {"sub": "admin", "exp": datetime.now(timezone.utc) - timedelta(hours=1)},
            SECRET_KEY, algorithm=ALGORITHM
        )
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(authorization=f"Bearer {token}")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_valid_token(self):
        from deps import get_current_user, create_access_token
        token = create_access_token({"sub": "admin", "shop_id": "shop-1"})
        payload = await get_current_user(authorization=f"Bearer {token}")
        assert payload["sub"] == "admin"


# ============================================================
# 6. SMS Consent & STOP/Opt-Out
# ============================================================


class TestSMSCompliance:

    def test_is_opt_out_stop(self):
        from sms_compliance import is_opt_out_message
        assert is_opt_out_message("STOP") is True

    def test_is_opt_out_unsubscribe(self):
        from sms_compliance import is_opt_out_message
        assert is_opt_out_message("UNSUBSCRIBE") is True

    def test_is_opt_out_case_insensitive(self):
        from sms_compliance import is_opt_out_message
        assert is_opt_out_message("stop") is True
        assert is_opt_out_message("Stop") is True

    def test_is_opt_out_with_whitespace(self):
        from sms_compliance import is_opt_out_message
        assert is_opt_out_message("  STOP  ") is True

    def test_is_not_opt_out(self):
        from sms_compliance import is_opt_out_message
        assert is_opt_out_message("CONFIRM") is False
        assert is_opt_out_message("HELP") is False
        assert is_opt_out_message("hello") is False

    @pytest.mark.asyncio
    async def test_check_consent_granted(self):
        from sms_compliance import SMSComplianceService
        db = MockDB()
        db.clients = MockCollection([make_client(sms_consent=True)])
        audit = AsyncMock()
        svc = SMSComplianceService(db, "shop-1", audit)
        has_consent, reason = await svc.check_consent("client-1")
        assert has_consent is True
        assert reason is None

    @pytest.mark.asyncio
    async def test_check_consent_not_granted(self):
        from sms_compliance import SMSComplianceService
        db = MockDB()
        db.clients = MockCollection([make_client(sms_consent=False)])
        audit = AsyncMock()
        svc = SMSComplianceService(db, "shop-1", audit)
        has_consent, reason = await svc.check_consent("client-1")
        assert has_consent is False
        assert "not granted" in reason

    @pytest.mark.asyncio
    async def test_check_consent_client_not_found(self):
        from sms_compliance import SMSComplianceService
        db = MockDB()
        audit = AsyncMock()
        svc = SMSComplianceService(db, "shop-1", audit)
        has_consent, reason = await svc.check_consent("nonexistent")
        assert has_consent is False
        assert "not found" in reason.lower()

    @pytest.mark.asyncio
    async def test_send_blocked_without_consent(self):
        from sms_compliance import SMSComplianceService
        db = MockDB()
        db.clients = MockCollection([make_client(sms_consent=False)])
        audit = AsyncMock()
        svc = SMSComplianceService(db, "shop-1", audit)
        resp = await svc.send_sms("client-1", "+15551234567", "Hello")
        assert resp.success is False
        assert "blocked" in resp.error.lower()

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"TWILIO_ENABLED": "false"}, clear=False)
    async def test_send_succeeds_with_consent_mock_mode(self):
        from sms_compliance import SMSComplianceService
        db = MockDB()
        db.clients = MockCollection([make_client(sms_consent=True)])
        audit = AsyncMock()
        svc = SMSComplianceService(db, "shop-1", audit)
        resp = await svc.send_sms("client-1", "+15551234567", "Hello")
        assert resp.success is True

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"TWILIO_ENABLED": "false"}, clear=False)
    async def test_send_with_bypass_consent(self):
        """bypass_consent=True should send even without consent."""
        from sms_compliance import SMSComplianceService
        db = MockDB()
        db.clients = MockCollection([make_client(sms_consent=False)])
        audit = AsyncMock()
        svc = SMSComplianceService(db, "shop-1", audit)
        resp = await svc.send_sms("client-1", "+15551234567", "Opt-out confirmed", bypass_consent=True)
        assert resp.success is True

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"TWILIO_ENABLED": "false"}, clear=False)
    async def test_opt_out_revokes_consent(self):
        """process_opt_out sets sms_consent=false."""
        from sms_compliance import SMSComplianceService
        db = MockDB()
        client = make_client(sms_consent=True)
        db.clients = MockCollection([client])
        audit = AsyncMock()
        svc = SMSComplianceService(db, "shop-1", audit)

        result = await svc.process_opt_out("client-1", "+15559876543")
        assert result is True

        updated = await db.clients.find_one({"id": "client-1"})
        assert updated["sms_consent"] is False

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"TWILIO_ENABLED": "false"}, clear=False)
    async def test_opt_out_sends_confirmation(self):
        """process_opt_out sends a confirmation message with bypass_consent."""
        from sms_compliance import SMSComplianceService, OPT_OUT_CONFIRMATION
        db = MockDB()
        client = make_client(sms_consent=True)
        db.clients = MockCollection([client])
        audit = AsyncMock()
        svc = SMSComplianceService(db, "shop-1", audit)

        await svc.process_opt_out("client-1", "+15559876543")
        # Audit should have been called for the confirmation send
        assert audit.log_sms_sent.called

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"TWILIO_ENABLED": "false"}, clear=False)
    async def test_full_consent_lifecycle(self):
        """Grant consent -> send message -> STOP -> verify blocked."""
        from sms_compliance import SMSComplianceService
        db = MockDB()
        client = make_client(sms_consent=True)
        db.clients = MockCollection([client])
        audit = AsyncMock()
        svc = SMSComplianceService(db, "shop-1", audit)

        # 1. Send with consent - should succeed
        resp = await svc.send_sms("client-1", "+15559876543", "Reminder")
        assert resp.success is True

        # 2. Process STOP opt-out
        await svc.process_opt_out("client-1", "+15559876543")

        # 3. Verify consent revoked
        has_consent, _ = await svc.check_consent("client-1")
        assert has_consent is False

        # 4. Send after opt-out - should be blocked
        resp = await svc.send_sms("client-1", "+15559876543", "Another message")
        assert resp.success is False


# ============================================================
# 7. Revenue Logger Boundary Conditions
# ============================================================


class TestRevenueLogger:

    def test_same_calendar_day_same_day(self):
        from revenue_logger import is_same_calendar_day
        dt1 = datetime(2025, 1, 15, 10, 0, tzinfo=timezone.utc)
        dt2 = datetime(2025, 1, 15, 20, 0, tzinfo=timezone.utc)
        assert is_same_calendar_day(dt1, dt2) is True

    def test_same_calendar_day_different_day(self):
        from revenue_logger import is_same_calendar_day
        dt1 = datetime(2025, 1, 15, 23, 0, tzinfo=timezone.utc)
        dt2 = datetime(2025, 1, 16, 1, 0, tzinfo=timezone.utc)
        assert is_same_calendar_day(dt1, dt2) is False

    def test_same_calendar_day_naive_datetimes(self):
        from revenue_logger import is_same_calendar_day
        dt1 = datetime(2025, 1, 15, 10, 0)
        dt2 = datetime(2025, 1, 15, 20, 0)
        assert is_same_calendar_day(dt1, dt2) is True

    def test_same_calendar_day_midnight_boundary(self):
        from revenue_logger import is_same_calendar_day
        dt1 = datetime(2025, 1, 15, 23, 59, 59, tzinfo=timezone.utc)
        dt2 = datetime(2025, 1, 16, 0, 0, 0, tzinfo=timezone.utc)
        assert is_same_calendar_day(dt1, dt2) is False

    @pytest.mark.asyncio
    async def test_log_waitlist_fill_same_day(self):
        from revenue_logger import RecoveredRevenueLogger
        db = MockDB()
        rl = RecoveredRevenueLogger(db, "shop-1")
        result = await rl.log_waitlist_fill("apt-1", "client-1", amount=35.0, is_same_day=True)
        assert result is True
        assert len(db.recovered_revenue_events._inserted) == 1

    @pytest.mark.asyncio
    async def test_log_waitlist_fill_not_same_day_skipped(self):
        from revenue_logger import RecoveredRevenueLogger
        db = MockDB()
        rl = RecoveredRevenueLogger(db, "shop-1")
        result = await rl.log_waitlist_fill("apt-1", "client-1", amount=35.0, is_same_day=False)
        assert result is False
        assert len(db.recovered_revenue_events._inserted) == 0

    @pytest.mark.asyncio
    async def test_log_waitlist_fill_zero_amount_skipped(self):
        from revenue_logger import RecoveredRevenueLogger
        db = MockDB()
        rl = RecoveredRevenueLogger(db, "shop-1")
        result = await rl.log_waitlist_fill("apt-1", "client-1", amount=0, is_same_day=True)
        assert result is False

    @pytest.mark.asyncio
    async def test_log_no_show_fee_positive_amount(self):
        from revenue_logger import RecoveredRevenueLogger
        db = MockDB()
        rl = RecoveredRevenueLogger(db, "shop-1")
        result = await rl.log_no_show_fee("apt-1", "client-1", amount=20.0)
        assert result is True

    @pytest.mark.asyncio
    async def test_log_no_show_fee_zero_amount_skipped(self):
        from revenue_logger import RecoveredRevenueLogger
        db = MockDB()
        rl = RecoveredRevenueLogger(db, "shop-1")
        result = await rl.log_no_show_fee("apt-1", "client-1", amount=0)
        assert result is False

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"TWILIO_ENABLED": "false", "CALENDAR_ENABLED": "false"}, clear=False)
    async def test_mocked_provider_notes(self):
        """When providers are mocked, notes should include mocked_execution."""
        from revenue_logger import RecoveredRevenueLogger
        db = MockDB()
        rl = RecoveredRevenueLogger(db, "shop-1")
        await rl.log_waitlist_fill("apt-1", "client-1", amount=35.0, is_same_day=True)
        event = db.recovered_revenue_events._inserted[0]
        assert "mocked_execution=true" in (event.get("notes") or "")

    @pytest.mark.asyncio
    async def test_log_failure_never_raises(self):
        """Revenue logging failures should return False, not raise."""
        from revenue_logger import RecoveredRevenueLogger
        db = MockDB()
        # Make insert_one raise
        db.recovered_revenue_events.insert_one = AsyncMock(side_effect=Exception("DB down"))
        rl = RecoveredRevenueLogger(db, "shop-1")
        result = await rl.log_no_show_fee("apt-1", "client-1", amount=20.0)
        assert result is False


# ============================================================
# 8. Provider Switching with Environment Variables
# ============================================================


class TestProviderSwitching:

    def setup_method(self):
        from providers import reset_providers
        reset_providers()

    @patch.dict(os.environ, {"TWILIO_ENABLED": "false"}, clear=False)
    def test_sms_defaults_to_mock(self):
        from providers import get_sms_provider
        from providers.mock_providers import MockSMSProvider
        provider = get_sms_provider()
        assert isinstance(provider, MockSMSProvider)

    @patch.dict(os.environ, {
        "TWILIO_ENABLED": "true",
        "TWILIO_ACCOUNT_SID": "ACtest123",
        "TWILIO_AUTH_TOKEN": "token123"
    }, clear=False)
    def test_sms_real_with_credentials(self):
        from providers import get_sms_provider
        from providers.real_providers import TwilioSMSProvider
        provider = get_sms_provider()
        assert isinstance(provider, TwilioSMSProvider)

    @patch.dict(os.environ, {
        "TWILIO_ENABLED": "true",
        "TWILIO_ACCOUNT_SID": "",
        "TWILIO_AUTH_TOKEN": ""
    }, clear=False)
    def test_sms_fallback_when_creds_missing(self):
        from providers import get_sms_provider
        from providers.mock_providers import MockSMSProvider
        provider = get_sms_provider()
        assert isinstance(provider, MockSMSProvider)

    @patch.dict(os.environ, {"SEND_EMAILS": "false"}, clear=False)
    def test_email_defaults_to_mock(self):
        from providers import get_email_provider
        from providers.mock_providers import MockEmailProvider
        provider = get_email_provider()
        assert isinstance(provider, MockEmailProvider)

    @patch.dict(os.environ, {"STRIPE_ENABLED": "false"}, clear=False)
    def test_payment_defaults_to_mock(self):
        from providers import get_payment_provider
        from providers.mock_providers import MockPaymentProvider
        provider = get_payment_provider()
        assert isinstance(provider, MockPaymentProvider)

    @patch.dict(os.environ, {"CALENDAR_ENABLED": "false"}, clear=False)
    def test_calendar_defaults_to_mock(self):
        from providers import get_calendar_provider
        from providers.mock_providers import MockCalendarProvider
        provider = get_calendar_provider()
        assert isinstance(provider, MockCalendarProvider)

    def test_reset_providers_clears_singletons(self):
        from providers import get_sms, reset_providers
        p1 = get_sms()
        reset_providers()
        p2 = get_sms()
        # After reset, a new instance should be created
        assert p1 is not p2

    def test_singleton_returns_same_instance(self):
        from providers import get_sms
        p1 = get_sms()
        p2 = get_sms()
        assert p1 is p2

    @patch.dict(os.environ, {
        "STRIPE_ENABLED": "true",
        "STRIPE_API_KEY": "sk_test_123"
    }, clear=False)
    def test_payment_real_with_key(self):
        from providers import get_payment_provider
        from providers.real_providers import StripePaymentProvider
        provider = get_payment_provider()
        assert isinstance(provider, StripePaymentProvider)

    def test_is_true_variations(self):
        from providers import _is_true
        assert _is_true("true") is True
        assert _is_true("True") is True
        assert _is_true("1") is True
        assert _is_true("yes") is True
        assert _is_true("on") is True
        assert _is_true("false") is False
        assert _is_true("0") is False
        assert _is_true("") is False
        assert _is_true(None) is False


# ============================================================
# 9. Scheduled Job Idempotency
# ============================================================


class TestScheduledJobIdempotency:

    @pytest.mark.asyncio
    async def test_appointment_in_window_included(self):
        """Appointment within confirmation_window_hours is included."""
        from scheduled_jobs import AppointmentReminderJob
        from models import AppointmentStatus, MessageDirection

        db = MockDB()
        shop = make_shop(confirmation_window_hours=24)
        scheduled_at = (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()
        apt = make_appointment(
            status=AppointmentStatus.CONFIRMED.value,
            scheduled_at=scheduled_at
        )
        db.appointments = MockCollection([apt])
        # No prior messages
        db.messages = MockCollection([])

        job = AppointmentReminderJob(db, shop)
        result = await job.get_appointments_needing_reminder()
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_appointment_outside_window_excluded(self):
        """Appointment beyond confirmation_window_hours is excluded."""
        from scheduled_jobs import AppointmentReminderJob
        from models import AppointmentStatus

        db = MockDB()
        shop = make_shop(confirmation_window_hours=24)
        scheduled_at = (datetime.now(timezone.utc) + timedelta(hours=30)).isoformat()
        apt = make_appointment(
            status=AppointmentStatus.CONFIRMED.value,
            scheduled_at=scheduled_at
        )
        db.appointments = MockCollection([apt])

        job = AppointmentReminderJob(db, shop)
        result = await job.get_appointments_needing_reminder()
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_already_reminded_excluded_by_message_type(self):
        """Appointment with existing 'appointment_reminder' message is excluded."""
        from scheduled_jobs import AppointmentReminderJob
        from models import AppointmentStatus, MessageDirection

        db = MockDB()
        shop = make_shop(confirmation_window_hours=24)
        scheduled_at = (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()
        apt = make_appointment(
            status=AppointmentStatus.CONFIRMED.value,
            scheduled_at=scheduled_at
        )
        db.appointments = MockCollection([apt])
        # Prior reminder exists via message_type
        db.messages = MockCollection([{
            "shop_id": "shop-1",
            "client_id": "client-1",
            "appointment_id": "apt-1",
            "direction": MessageDirection.OUTBOUND.value,
            "message_type": "appointment_reminder",
            "content": "Reminder: Your appointment...",
        }])

        job = AppointmentReminderJob(db, shop)
        result = await job.get_appointments_needing_reminder()
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_already_reminded_excluded_by_content_regex(self):
        """Appointment with existing 'Reminder:' prefixed message is excluded."""
        from scheduled_jobs import AppointmentReminderJob
        from models import AppointmentStatus, MessageDirection

        db = MockDB()
        shop = make_shop(confirmation_window_hours=24)
        scheduled_at = (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()
        apt = make_appointment(
            status=AppointmentStatus.CONFIRMED.value,
            scheduled_at=scheduled_at
        )
        db.appointments = MockCollection([apt])
        # Prior reminder exists via content prefix (legacy format)
        db.messages = MockCollection([{
            "shop_id": "shop-1",
            "client_id": "client-1",
            "appointment_id": "apt-1",
            "direction": MessageDirection.OUTBOUND.value,
            "message_type": "sms",
            "content": "Reminder: Your appointment is tomorrow at 2:00 PM",
        }])

        job = AppointmentReminderJob(db, shop)
        result = await job.get_appointments_needing_reminder()
        assert len(result) == 0

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"TWILIO_ENABLED": "false"}, clear=False)
    async def test_send_reminder_creates_message_with_correct_type(self):
        """send_reminder stores message with message_type='appointment_reminder'."""
        from scheduled_jobs import AppointmentReminderJob
        from models import AppointmentStatus

        db = MockDB()
        shop = make_shop(confirmation_window_hours=24)
        scheduled_at = (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()
        apt = make_appointment(
            status=AppointmentStatus.CONFIRMED.value,
            scheduled_at=scheduled_at
        )
        client = make_client(sms_consent=True)
        barber = {"id": "barber-1", "name": "Mike"}
        service = {"id": "service-1", "name": "Haircut"}
        db.appointments = MockCollection([apt])
        db.clients = MockCollection([client])
        db.barbers = MockCollection([barber])
        db.services = MockCollection([service])

        job = AppointmentReminderJob(db, shop)
        success = await job.send_reminder(apt)
        assert success is True

        # Verify the stored message
        stored = db.messages._inserted[0]
        assert stored["message_type"] == "appointment_reminder"
        assert stored["content"].startswith("Reminder:")

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"TWILIO_ENABLED": "false"}, clear=False)
    async def test_run_is_idempotent(self):
        """Running the job twice doesn't send duplicate reminders."""
        from scheduled_jobs import AppointmentReminderJob
        from models import AppointmentStatus

        db = MockDB()
        shop = make_shop(confirmation_window_hours=24)
        scheduled_at = (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()
        apt = make_appointment(
            status=AppointmentStatus.CONFIRMED.value,
            scheduled_at=scheduled_at
        )
        client = make_client(sms_consent=True)
        barber = {"id": "barber-1", "name": "Mike"}
        service = {"id": "service-1", "name": "Haircut"}
        db.appointments = MockCollection([apt])
        db.clients = MockCollection([client])
        db.barbers = MockCollection([barber])
        db.services = MockCollection([service])

        job = AppointmentReminderJob(db, shop)

        # First run
        results1 = await job.run()
        assert results1["sent"] == 1

        # Second run - reminder already exists
        results2 = await job.run()
        assert results2["sent"] == 0
        assert results2["total_found"] == 0

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"TWILIO_ENABLED": "false"}, clear=False)
    async def test_error_isolation_between_reminders(self):
        """One failing reminder doesn't prevent others from being sent."""
        from scheduled_jobs import AppointmentReminderJob
        from models import AppointmentStatus

        db = MockDB()
        shop = make_shop(confirmation_window_hours=24)
        scheduled_at = (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()

        # Two appointments: first client missing (will fail), second has data
        apt1 = make_appointment(id="apt-1", client_id="missing-client", status=AppointmentStatus.CONFIRMED.value, scheduled_at=scheduled_at)
        apt2 = make_appointment(id="apt-2", client_id="client-2", status=AppointmentStatus.CONFIRMED.value, scheduled_at=scheduled_at)
        client2 = make_client(id="client-2", sms_consent=True)
        barber = {"id": "barber-1", "name": "Mike"}
        service = {"id": "service-1", "name": "Haircut"}

        db.appointments = MockCollection([apt1, apt2])
        db.clients = MockCollection([client2])
        db.barbers = MockCollection([barber])
        db.services = MockCollection([service])

        job = AppointmentReminderJob(db, shop)
        results = await job.run()

        # apt-1 should fail (client not found), apt-2 should succeed
        assert results["sent"] == 1
        assert results["failed"] == 1


# ============================================================
# 10. Pydantic Model Validation (bonus coverage)
# ============================================================


class TestModelValidation:

    def test_appointment_status_values(self):
        """Verify all 8 AppointmentStatus enum values."""
        from models import AppointmentStatus
        expected = {"pending", "confirmed", "deposit_pending", "deposit_paid",
                    "completed", "no_show", "cancelled", "rescheduled"}
        actual = {s.value for s in AppointmentStatus}
        assert actual == expected

    def test_login_request_empty_rejected(self):
        from models import LoginRequest
        with pytest.raises(Exception):
            LoginRequest(username="", password="test")

    def test_login_request_whitespace_rejected(self):
        from models import LoginRequest
        with pytest.raises(Exception):
            LoginRequest(username="   ", password="test")

    def test_policy_update_invalid_day(self):
        from models import PolicyUpdate
        with pytest.raises(Exception):
            PolicyUpdate(business_hours={"funday": {"open": "09:00", "close": "18:00"}})

    def test_policy_update_valid_hours(self):
        from models import PolicyUpdate
        p = PolicyUpdate(business_hours={"monday": {"open": "09:00", "close": "18:00"}, "sunday": None})
        assert p.business_hours["monday"]["open"] == "09:00"

    def test_send_test_email_invalid_email(self):
        from models import SendTestEmailRequest
        with pytest.raises(Exception):
            SendTestEmailRequest(to_email="not-an-email")

    def test_send_test_email_valid_email(self):
        from models import SendTestEmailRequest
        r = SendTestEmailRequest(to_email="TEST@Example.Com")
        assert r.to_email == "test@example.com"

    def test_sms_consent_phone_validation(self):
        from models import SMSConsentRequest
        with pytest.raises(Exception):
            SMSConsentRequest(phone="abc", name="Test", consent=True)

    def test_sms_consent_valid_phone(self):
        from models import SMSConsentRequest
        r = SMSConsentRequest(phone="+15551234567", name="Test", consent=True)
        assert r.phone == "+15551234567"
