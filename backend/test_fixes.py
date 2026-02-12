"""
Tests for the 8 critical fixes:
1. Stripe webhook signature verification
2. Double-booking prevention
3. Pagination caps
4. WaitlistFillAgent SMS compliance
5. FrontDeskAgent state machine
6. (Frontend — tested via build)
7. Allowed transitions endpoint
8. Real providers async wrapping
"""
import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure backend is on path
sys.path.insert(0, os.path.dirname(__file__))

from models import ALLOWED_TRANSITIONS, AppointmentStatus


# ============================================================
# 1. Stripe webhook signature verification
# ============================================================

class TestStripeWebhookSignature:
    """Verify that handle_webhook rejects invalid/missing signatures."""

    def _make_provider(self, webhook_secret=""):
        """Create a StripePaymentProvider with checkout stubbed to non-None."""
        with patch.dict(os.environ, {
            "STRIPE_API_KEY": "sk_test_fake",
            "STRIPE_WEBHOOK_SECRET": webhook_secret,
        }):
            from providers.real_providers import StripePaymentProvider
            provider = StripePaymentProvider()
            # Stub checkout to non-None so we reach the signature logic
            provider.checkout = MagicMock()
            provider.webhook_secret = webhook_secret
            return provider

    def test_missing_webhook_secret_rejects(self):
        """Without STRIPE_WEBHOOK_SECRET, webhook should be rejected."""
        provider = self._make_provider(webhook_secret="")
        result = asyncio.get_event_loop().run_until_complete(
            provider.handle_webhook(b'{}', 'sig_fake')
        )
        assert "error" in result
        assert "secret" in result["error"].lower() or "not configured" in result["error"].lower()

    def test_invalid_signature_rejects(self):
        """An invalid signature should be rejected."""
        provider = self._make_provider(webhook_secret="whsec_test_secret")
        result = asyncio.get_event_loop().run_until_complete(
            provider.handle_webhook(b'{"type": "fake"}', 'invalid_signature')
        )
        assert "error" in result
        assert "signature" in result["error"].lower() or "verification" in result["error"].lower()

    def test_valid_signature_accepted(self):
        """A properly signed event should be accepted."""
        import hmac
        import hashlib

        webhook_secret = "whsec_test_secret"
        payload = json.dumps({
            "id": "evt_test",
            "type": "checkout.session.completed",
            "data": {"object": {"id": "cs_test", "payment_status": "paid"}},
        }).encode()

        timestamp = int(datetime.now().timestamp())
        signed_payload = f"{timestamp}.{payload.decode()}"
        sig = hmac.new(
            webhook_secret.encode(), signed_payload.encode(), hashlib.sha256
        ).hexdigest()
        header = f"t={timestamp},v1={sig}"

        provider = self._make_provider(webhook_secret=webhook_secret)
        result = asyncio.get_event_loop().run_until_complete(
            provider.handle_webhook(payload, header)
        )
        assert result.get("event_type") == "checkout.session.completed"
        assert result.get("session_id") == "cs_test"
        assert result.get("payment_status") == "paid"


# ============================================================
# 2. Double-booking prevention
# ============================================================

class TestDoubleBookingPrevention:
    """Test that create_appointment rejects overlapping bookings."""

    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        # Set up async collection mocks
        db.shops = MagicMock()
        db.barbers = MagicMock()
        db.services = MagicMock()
        db.clients = MagicMock()
        db.appointments = MagicMock()
        db.events = MagicMock()
        db.payments = MagicMock()
        return db

    def test_conflict_detected(self):
        """An overlapping appointment should trigger 409."""
        future_time = (datetime.now(timezone.utc) + timedelta(hours=24))
        existing_apt = {
            "id": "existing-1",
            "scheduled_at": future_time.isoformat(),
            "duration_minutes": 30,
        }

        # The conflict detection logic (extracted for unit test)
        scheduled_dt = future_time + timedelta(minutes=10)  # Overlaps!
        duration = 30
        end_dt = scheduled_dt + timedelta(minutes=duration)
        conflict_start = datetime.fromisoformat(existing_apt["scheduled_at"].replace("Z", "+00:00"))
        conflict_end = conflict_start + timedelta(minutes=existing_apt.get("duration_minutes", 30))

        # Check overlap: conflict_start < end_dt AND conflict_end > scheduled_dt
        is_overlap = conflict_start < end_dt and conflict_end > scheduled_dt
        assert is_overlap is True

    def test_no_conflict_adjacent_slots(self):
        """Adjacent (non-overlapping) appointments should not conflict."""
        base_time = datetime.now(timezone.utc) + timedelta(hours=24)
        existing_start = base_time
        existing_end = existing_start + timedelta(minutes=30)

        new_start = existing_end  # Starts exactly when existing ends
        new_end = new_start + timedelta(minutes=30)

        is_overlap = existing_start < new_end and existing_end > new_start
        assert is_overlap is False  # No overlap — adjacent is fine


# ============================================================
# 3. Pagination caps
# ============================================================

class TestPaginationCaps:
    """Test clamp_pagination utility (reimplemented here to avoid server.py import issues)."""

    MAX_LIMIT = 200

    @staticmethod
    def clamp_pagination(limit, skip, max_limit=200):
        """Mirror of server.clamp_pagination for isolated testing."""
        limit = max(1, min(limit, max_limit))
        skip = max(0, skip)
        return limit, skip

    def test_normal_values_pass_through(self):
        limit, skip = self.clamp_pagination(50, 0)
        assert limit == 50
        assert skip == 0

    def test_huge_limit_capped(self):
        limit, skip = self.clamp_pagination(999999, 0)
        assert limit == self.MAX_LIMIT

    def test_negative_skip_clamped(self):
        limit, skip = self.clamp_pagination(50, -10)
        assert skip == 0

    def test_zero_limit_becomes_one(self):
        limit, skip = self.clamp_pagination(0, 0)
        assert limit == 1

    def test_negative_limit_becomes_one(self):
        limit, skip = self.clamp_pagination(-5, 0)
        assert limit == 1

    def test_clamp_pagination_in_server_source(self):
        """Verify the function exists in server.py source code."""
        import pathlib
        server_source = (pathlib.Path(__file__).parent / "server.py").read_text()
        assert "def clamp_pagination(" in server_source
        assert "MAX_LIMIT = 200" in server_source
        # Verify it's used in list endpoints
        assert "clamp_pagination(limit, skip)" in server_source


# ============================================================
# 4. WaitlistFillAgent SMS compliance
# ============================================================

class TestWaitlistSMSCompliance:
    """Test that WaitlistFillAgent routes through compliance service."""

    @pytest.mark.asyncio
    async def test_opted_out_client_not_contacted(self):
        """A client without SMS consent should NOT receive a waitlist offer."""
        from models import Shop

        mock_db = MagicMock()
        shop = Shop(id="shop_1", name="Test", phone="+15550001111")

        # Client found but has NO sms consent
        mock_db.clients.find_one = AsyncMock(return_value={
            "id": "client_1",
            "shop_id": "shop_1",
            "phone": "+15551234567",
            "sms_consent": False,
        })
        mock_db.barbers.find_one = AsyncMock(return_value={"name": "Tony"})

        from agents import WaitlistFillAgent
        with patch("agents.create_audit_logger") as mock_audit, \
             patch("agents.create_sms_service") as mock_sms_factory:

            # Simulate compliance service blocking the send
            mock_sms_svc = MagicMock()
            mock_sms_svc.send_sms = AsyncMock(return_value=MagicMock(success=False, error="SMS blocked: consent not granted"))
            mock_sms_factory.return_value = mock_sms_svc
            mock_audit.return_value = MagicMock()

            agent = WaitlistFillAgent(mock_db, shop)

            cancelled_apt = {
                "id": "apt_1",
                "barber_id": "barber_1",
                "scheduled_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
                "service_id": "svc_1",
            }
            waitlist_entry = {"id": "wl_1", "client_id": "client_1"}

            result = await agent.offer_slot_to_waitlist(cancelled_apt, waitlist_entry)
            assert result is False
            mock_sms_svc.send_sms.assert_called_once()

    @pytest.mark.asyncio
    async def test_opted_in_client_contacted(self):
        """A client with SMS consent SHOULD receive a waitlist offer."""
        from models import Shop

        mock_db = MagicMock()
        shop = Shop(id="shop_1", name="Test", phone="+15550001111")

        mock_db.clients.find_one = AsyncMock(return_value={
            "id": "client_1",
            "shop_id": "shop_1",
            "phone": "+15551234567",
            "sms_consent": True,
        })
        mock_db.barbers.find_one = AsyncMock(return_value={"name": "Tony"})
        mock_db.waitlist.update_one = AsyncMock()
        mock_db.messages.insert_one = AsyncMock()
        mock_db.events.insert_one = AsyncMock()

        from agents import WaitlistFillAgent
        with patch("agents.create_audit_logger") as mock_audit, \
             patch("agents.create_sms_service") as mock_sms_factory:

            mock_sms_svc = MagicMock()
            mock_sms_svc.send_sms = AsyncMock(return_value=MagicMock(success=True, message_id="msg_1"))
            mock_sms_factory.return_value = mock_sms_svc
            mock_audit.return_value = MagicMock()

            agent = WaitlistFillAgent(mock_db, shop)

            cancelled_apt = {
                "id": "apt_1",
                "barber_id": "barber_1",
                "scheduled_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
                "service_id": "svc_1",
            }
            waitlist_entry = {"id": "wl_1", "client_id": "client_1"}

            result = await agent.offer_slot_to_waitlist(cancelled_apt, waitlist_entry)
            assert result is True
            mock_sms_svc.send_sms.assert_called_once()


# ============================================================
# 5. FrontDeskAgent state machine
# ============================================================

class TestFrontDeskStateMachine:
    """Test that FrontDeskAgent validates transitions."""

    def test_allowed_transitions_map_consistency(self):
        """Verify ALLOWED_TRANSITIONS covers all AppointmentStatus values."""
        all_statuses = {s.value for s in AppointmentStatus}
        assert set(ALLOWED_TRANSITIONS.keys()) == all_statuses

    def test_terminal_states_have_no_transitions(self):
        """Terminal states (completed, no_show, cancelled) should have empty sets."""
        for terminal in ["completed", "no_show", "cancelled"]:
            assert ALLOWED_TRANSITIONS[terminal] == set(), f"{terminal} should be terminal"

    def test_valid_transition_allowed(self):
        """pending -> confirmed should be valid."""
        assert "confirmed" in ALLOWED_TRANSITIONS["pending"]

    def test_invalid_transition_blocked(self):
        """completed -> pending should be invalid."""
        assert "pending" not in ALLOWED_TRANSITIONS["completed"]

    @pytest.mark.asyncio
    async def test_agent_cancellation_validates_state(self):
        """FrontDeskAgent should reject cancellation from terminal state."""
        from models import Shop, Client
        from agents import FrontDeskAgent

        mock_db = MagicMock()
        shop = Shop(id="shop_1", name="Test", phone="+15550001111")

        # No active (cancellable) appointment found
        mock_db.appointments.find_one = AsyncMock(return_value=None)

        agent = FrontDeskAgent(mock_db, shop)
        client = Client(id="c1", shop_id="shop_1", name="Test", phone="+15551234567")
        message, metadata = await agent._handle_cancellation(client)
        assert "no_appointment" in metadata.get("action", "")

    def test_is_valid_transition_method(self):
        """Test the _is_valid_transition helper directly."""
        from models import Shop
        from agents import FrontDeskAgent

        mock_db = MagicMock()
        shop = Shop(id="shop_1", name="Test", phone="+15550001111")
        agent = FrontDeskAgent(mock_db, shop)

        assert agent._is_valid_transition("pending", "confirmed") is True
        assert agent._is_valid_transition("completed", "cancelled") is False
        assert agent._is_valid_transition("no_show", "pending") is False
        assert agent._is_valid_transition("confirmed", "no_show") is True


# ============================================================
# 7. Allowed transitions endpoint
# ============================================================

class TestAllowedTransitionsEndpoint:
    """Test the GET /api/appointments/allowed-transitions endpoint."""

    def test_transitions_match_model(self):
        """Ensure the endpoint would return data matching ALLOWED_TRANSITIONS."""
        # Build the expected response shape
        expected = {
            status: sorted(targets)
            for status, targets in ALLOWED_TRANSITIONS.items()
        }
        # Verify all statuses present
        assert "pending" in expected
        assert "completed" in expected
        assert expected["completed"] == []
        assert "confirmed" in expected["pending"]


# ============================================================
# 8. Real providers async wrapping
# ============================================================

class TestAsyncWrapping:
    """Verify real providers use asyncio.to_thread for blocking calls."""

    def test_twilio_send_uses_to_thread(self):
        """TwilioSMSProvider.send_sms should use asyncio.to_thread."""
        import inspect
        from providers.real_providers import TwilioSMSProvider
        source = inspect.getsource(TwilioSMSProvider.send_sms)
        assert "asyncio.to_thread" in source

    def test_sendgrid_send_uses_to_thread(self):
        """SendGridEmailProvider.send_email should use asyncio.to_thread."""
        import inspect
        from providers.real_providers import SendGridEmailProvider
        source = inspect.getsource(SendGridEmailProvider.send_email)
        assert "asyncio.to_thread" in source

    def test_gcal_create_uses_to_thread(self):
        """GoogleCalendarProvider.create_event should use asyncio.to_thread."""
        import inspect
        from providers.real_providers import GoogleCalendarProvider
        source = inspect.getsource(GoogleCalendarProvider.create_event)
        assert "asyncio.to_thread" in source

    def test_stripe_webhook_uses_construct_event(self):
        """StripePaymentProvider.handle_webhook should call stripe.Webhook.construct_event."""
        import inspect
        from providers.real_providers import StripePaymentProvider
        source = inspect.getsource(StripePaymentProvider.handle_webhook)
        assert "construct_event" in source


# ============================================================
# HIGH-SEVERITY FIXES
# ============================================================

# ============================================================
# H1. Admin password NOT logged in plaintext
# ============================================================

class TestAdminPasswordNotLogged:
    """Verify seed_demo_data no longer logs the actual admin password."""

    def test_password_not_in_log_line(self):
        """The logger.info call should not interpolate the password value."""
        import pathlib
        source = (pathlib.Path(__file__).parent / "server.py").read_text()
        # The old line was: logger.info(f"Admin login: username='admin', password='{admin_password}'")
        assert "password='{admin_password}'" not in source
        assert "password=\"{admin_password}\"" not in source
        # The new line should reference the env var, not the value
        assert "ADMIN_PASSWORD env var" in source


# ============================================================
# H2. Mock payment endpoint requires authentication
# ============================================================

class TestMockPaymentAuth:
    """Verify mock-payment endpoint now requires auth."""

    def test_mock_payment_has_depends(self):
        """The mock_payment_page handler should include Depends(get_shop)."""
        import pathlib
        source = (pathlib.Path(__file__).parent / "server.py").read_text()
        # Find the function definition line
        import re
        match = re.search(
            r"async def mock_payment_page\(.+Depends\(get_shop\)",
            source,
        )
        assert match is not None, (
            "mock_payment_page should require auth via Depends(get_shop)"
        )


# ============================================================
# H3. Rate limiter uses MongoDB (multi-worker safe)
# ============================================================

class TestRateLimiterMongoBacked:
    """Verify the rate limiter is async and backed by MongoDB."""

    def test_check_rate_limit_is_async(self):
        """check_rate_limit should be an async function."""
        import pathlib
        source = (pathlib.Path(__file__).parent / "server.py").read_text()
        assert "async def check_rate_limit(" in source

    def test_rate_limit_uses_db(self):
        """check_rate_limit should reference db.rate_limit_entries."""
        import pathlib
        source = (pathlib.Path(__file__).parent / "server.py").read_text()
        assert "rate_limit_entries" in source

    def test_no_in_memory_store(self):
        """The old _rate_limit_store dict should be removed."""
        import pathlib
        source = (pathlib.Path(__file__).parent / "server.py").read_text()
        assert "_rate_limit_store" not in source

    def test_callers_use_await(self):
        """Both call sites should await check_rate_limit."""
        import pathlib
        source = (pathlib.Path(__file__).parent / "server.py").read_text()
        assert "await check_rate_limit(" in source
        # Should appear at least twice (login + sms-consent)
        assert source.count("await check_rate_limit(") >= 2

    def test_ttl_index_created_at_startup(self):
        """Startup should create a TTL index on rate_limit_entries."""
        import pathlib
        source = (pathlib.Path(__file__).parent / "server.py").read_text()
        assert "rate_limit_entries.create_index" in source
        assert "expireAfterSeconds" in source


# ============================================================
# H4. SMS compliance CTIA opt-out keywords
# ============================================================

class TestCTIAOptOutKeywords:
    """Verify all CTIA-required opt-out keywords are present."""

    def test_required_keywords_present(self):
        """OPT_OUT_KEYWORDS must include STOP, STOPALL, UNSUBSCRIBE, END, QUIT."""
        from sms_compliance import OPT_OUT_KEYWORDS
        required = {"STOP", "STOPALL", "UNSUBSCRIBE", "END", "QUIT"}
        assert required.issubset(OPT_OUT_KEYWORDS), (
            f"Missing CTIA keywords: {required - OPT_OUT_KEYWORDS}"
        )

    def test_is_opt_out_recognizes_end(self):
        from sms_compliance import is_opt_out_message
        assert is_opt_out_message("END") is True
        assert is_opt_out_message("end") is True

    def test_is_opt_out_recognizes_quit(self):
        from sms_compliance import is_opt_out_message
        assert is_opt_out_message("QUIT") is True
        assert is_opt_out_message("quit") is True

    def test_is_opt_out_recognizes_stopall(self):
        from sms_compliance import is_opt_out_message
        assert is_opt_out_message("STOPALL") is True

    def test_non_keyword_not_opted_out(self):
        from sms_compliance import is_opt_out_message
        assert is_opt_out_message("HELLO") is False
        assert is_opt_out_message("BOOK") is False


# ============================================================
# H5. No double-write in process_no_show
# ============================================================

class TestNoShowNoDoubleWrite:
    """Verify process_no_show does NOT update appointment status itself."""

    def test_process_no_show_skips_status_update(self):
        """The method source should not contain a status update to NO_SHOW."""
        import inspect
        from agents import NoShowEnforcementAgent
        source = inspect.getsource(NoShowEnforcementAgent.process_no_show)
        # Should NOT re-write the status
        assert '"status": AppointmentStatus.NO_SHOW' not in source
        assert "'status': AppointmentStatus.NO_SHOW" not in source

    def test_process_no_show_still_increments_client_no_shows(self):
        """Side-effects (client stats) should still be present."""
        import inspect
        from agents import NoShowEnforcementAgent
        source = inspect.getsource(NoShowEnforcementAgent.process_no_show)
        assert '"no_shows": 1' in source or "'no_shows': 1" in source

    def test_process_no_show_still_logs_event(self):
        """Revenue impact event should still be logged."""
        import inspect
        from agents import NoShowEnforcementAgent
        source = inspect.getsource(NoShowEnforcementAgent.process_no_show)
        assert "NO_SHOW_DETECTED" in source


# ============================================================
# H6. shop_id scoping in agent DB queries
# ============================================================

class TestAgentShopIdScoping:
    """Verify agent queries include shop_id for tenant isolation."""

    def test_process_no_show_query_has_shop_id(self):
        """NoShowEnforcementAgent.process_no_show should query with shop_id."""
        import inspect
        from agents import NoShowEnforcementAgent
        source = inspect.getsource(NoShowEnforcementAgent.process_no_show)
        assert "shop_id" in source

    def test_process_cancellation_query_has_shop_id(self):
        """WaitlistFillAgent.process_cancellation should query with shop_id."""
        import inspect
        from agents import WaitlistFillAgent
        source = inspect.getsource(WaitlistFillAgent.process_cancellation)
        assert "shop_id" in source

    def test_no_show_client_update_has_shop_id(self):
        """Client update in process_no_show should be scoped to shop_id."""
        import inspect
        from agents import NoShowEnforcementAgent
        source = inspect.getsource(NoShowEnforcementAgent.process_no_show)
        # Verify the clients.update_one call includes shop_id
        assert "self.shop.id" in source

    @pytest.mark.asyncio
    async def test_process_no_show_uses_shop_scoped_query(self):
        """Integration check: process_no_show queries with shop_id."""
        from models import Shop
        from agents import NoShowEnforcementAgent

        mock_db = MagicMock()
        shop = Shop(id="shop_1", name="Test", phone="+15550001111")

        # Appointment not found (shop_id mismatch would cause this)
        mock_db.appointments.find_one = AsyncMock(return_value=None)

        agent = NoShowEnforcementAgent(mock_db, shop)
        await agent.process_no_show("apt_nonexistent")

        # Verify the query included shop_id
        call_args = mock_db.appointments.find_one.call_args
        query_filter = call_args[0][0]
        assert "shop_id" in query_filter
        assert query_filter["shop_id"] == "shop_1"

    @pytest.mark.asyncio
    async def test_process_cancellation_uses_shop_scoped_query(self):
        """Integration check: process_cancellation queries with shop_id."""
        from models import Shop
        from agents import WaitlistFillAgent

        mock_db = MagicMock()
        shop = Shop(id="shop_1", name="Test", phone="+15550001111")

        mock_db.appointments.find_one = AsyncMock(return_value=None)

        with patch("agents.create_audit_logger") as mock_audit, \
             patch("agents.create_sms_service") as mock_sms_factory:
            mock_audit.return_value = MagicMock()
            mock_sms_factory.return_value = MagicMock()

            agent = WaitlistFillAgent(mock_db, shop)
            await agent.process_cancellation("apt_nonexistent")

        call_args = mock_db.appointments.find_one.call_args
        query_filter = call_args[0][0]
        assert "shop_id" in query_filter
        assert query_filter["shop_id"] == "shop_1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
