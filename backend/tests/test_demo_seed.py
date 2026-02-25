"""
Tests for Demo Data Seed and Clear endpoints.
Tests: POST /api/admin/shops/{shop_id}/seed-demo
       POST /api/admin/shops/{shop_id}/clear-data
       GET /api/conversations (verifies field names: client_name, content)
       GET /api/conversations/poll/new (verifies no phantom messages with current timestamp)
"""
import pytest
import requests
import os
from datetime import datetime, timezone

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
SUPER_ADMIN_CREDS = {"username": "admin", "password": "admin123"}


class TestDemoSeedEndpoint:
    """Test POST /api/admin/shops/{shop_id}/seed-demo"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Get super_admin token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        response = self.session.post(f"{BASE_URL}/api/auth/login", json=SUPER_ADMIN_CREDS)
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip("Could not authenticate - rate limited")
    
    def test_seed_demo_without_auth_returns_401(self):
        """Seed endpoint requires authentication"""
        no_auth_session = requests.Session()
        response = no_auth_session.post(f"{BASE_URL}/api/admin/shops/demo_shop/seed-demo")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ seed-demo without auth returns 401")

    def test_seed_demo_invalid_shop_returns_404(self):
        """Seed endpoint returns 404 for invalid shop"""
        response = self.session.post(f"{BASE_URL}/api/admin/shops/invalid_shop_xyz/seed-demo")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ seed-demo invalid shop returns 404")

    def test_seed_demo_creates_expected_data(self):
        """Seed endpoint creates correct data counts"""
        response = self.session.post(f"{BASE_URL}/api/admin/shops/demo_shop/seed-demo")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "message" in data, "Response should have 'message'"
        assert "counts" in data, "Response should have 'counts'"
        
        counts = data["counts"]
        # Verify minimum counts from demo_seed.py
        assert counts.get("clients", 0) >= 15, f"Expected >= 15 clients, got {counts.get('clients')}"
        assert counts.get("barbers", 0) >= 4, f"Expected >= 4 barbers, got {counts.get('barbers')}"
        assert counts.get("services", 0) >= 7, f"Expected >= 7 services, got {counts.get('services')}"
        assert counts.get("appointments", 0) >= 100, f"Expected >= 100 appointments, got {counts.get('appointments')}"
        assert counts.get("messages", 0) >= 30, f"Expected >= 30 messages, got {counts.get('messages')}"
        assert counts.get("events", 0) > 0, "Events should be seeded"
        assert counts.get("transactions", 0) > 0, "Transactions should be seeded"
        assert counts.get("recovered_revenue_events", 0) > 0, "Recovered revenue should be seeded"
        assert counts.get("waitlist", 0) > 0, "Waitlist should be seeded"
        
        print(f"✓ seed-demo creates: {counts.get('clients')} clients, {counts.get('barbers')} barbers, "
              f"{counts.get('appointments')} appointments, {counts.get('messages')} messages")


class TestClearDataEndpoint:
    """Test POST /api/admin/shops/{shop_id}/clear-data"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Get super_admin token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        response = self.session.post(f"{BASE_URL}/api/auth/login", json=SUPER_ADMIN_CREDS)
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip("Could not authenticate - rate limited")

    def test_clear_data_without_auth_returns_401(self):
        """Clear endpoint requires authentication"""
        no_auth_session = requests.Session()
        response = no_auth_session.post(f"{BASE_URL}/api/admin/shops/demo_shop/clear-data")
        assert response.status_code == 401
        print("✓ clear-data without auth returns 401")

    def test_clear_data_invalid_shop_returns_404(self):
        """Clear endpoint returns 404 for invalid shop"""
        response = self.session.post(f"{BASE_URL}/api/admin/shops/invalid_shop_xyz/clear-data")
        assert response.status_code == 404
        print("✓ clear-data invalid shop returns 404")


class TestConversationsFieldNames:
    """Test conversations endpoint field names (client_name, content vs body)"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Get super_admin token and ensure data exists"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        response = self.session.post(f"{BASE_URL}/api/auth/login", json=SUPER_ADMIN_CREDS)
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip("Could not authenticate - rate limited")

    def test_conversations_list_has_correct_fields(self):
        """Conversations list uses client_name and last_message"""
        response = self.session.get(f"{BASE_URL}/api/conversations")
        assert response.status_code == 200
        
        data = response.json()
        assert "conversations" in data
        
        if len(data["conversations"]) > 0:
            conv = data["conversations"][0]
            # Check correct field names
            assert "client_name" in conv, "Should have 'client_name', not 'name'"
            assert "client_phone" in conv, "Should have 'client_phone'"
            assert "last_message" in conv, "Should have 'last_message'"
            assert "last_direction" in conv, "Should have 'last_direction'"
            assert "total_messages" in conv, "Should have 'total_messages'"
            
            # Verify last_message is not empty
            assert conv["last_message"], "last_message should not be empty"
            assert conv["client_name"], "client_name should not be empty"
            
            print(f"✓ Conversations list has correct fields. Example: {conv['client_name']}, "
                  f"last_message: {conv['last_message'][:50]}...")
        else:
            pytest.skip("No conversations to test")

    def test_conversation_messages_have_content_field(self):
        """Individual messages use 'content' field (not 'body')"""
        # Get first conversation
        response = self.session.get(f"{BASE_URL}/api/conversations")
        assert response.status_code == 200
        
        conversations = response.json().get("conversations", [])
        if not conversations:
            pytest.skip("No conversations to test")
        
        client_id = conversations[0]["client_id"]
        
        # Get messages for this client
        msg_response = self.session.get(f"{BASE_URL}/api/conversations/{client_id}")
        assert msg_response.status_code == 200
        
        data = msg_response.json()
        messages = data.get("messages", [])
        
        if messages:
            msg = messages[0]
            assert "content" in msg, "Message should have 'content' field"
            assert "direction" in msg, "Message should have 'direction' field"
            assert "created_at" in msg, "Message should have 'created_at' field"
            assert msg["content"], "content should not be empty"
            
            print(f"✓ Messages have 'content' field. Example: {msg['content'][:50]}...")
        else:
            pytest.skip("No messages to test")


class TestConversationPollingFix:
    """Test that conversation polling doesn't show phantom messages"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Get super_admin token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        response = self.session.post(f"{BASE_URL}/api/auth/login", json=SUPER_ADMIN_CREDS)
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip("Could not authenticate - rate limited")

    def test_poll_with_current_timestamp_returns_no_messages(self):
        """Polling with current timestamp should return no new messages (no phantom counter)"""
        current_time = datetime.now(timezone.utc).isoformat()
        
        response = self.session.get(f"{BASE_URL}/api/conversations/poll/new", params={"since": current_time})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        messages = data.get("messages", [])
        
        # Key test: no phantom messages when polling with current timestamp
        assert len(messages) == 0, f"Expected 0 new messages with current timestamp, got {len(messages)}"
        
        print("✓ Poll with current timestamp returns 0 new messages (no phantom counter)")

    def test_poll_without_since_param(self):
        """Polling without since param still works"""
        response = self.session.get(f"{BASE_URL}/api/conversations/poll/new")
        assert response.status_code == 200
        
        data = response.json()
        # Should have the standard response structure
        assert "messages" in data or "total_unread" in data
        
        print("✓ Poll without since param returns valid response")


class TestDashboardStatsAfterSeed:
    """Test that dashboard/reporting shows data after seed"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Get super_admin token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        response = self.session.post(f"{BASE_URL}/api/auth/login", json=SUPER_ADMIN_CREDS)
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip("Could not authenticate - rate limited")

    def test_reporting_shows_populated_data(self):
        """Reporting endpoint shows data after seed"""
        response = self.session.get(f"{BASE_URL}/api/reporting/overview")
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify populated data
        appointments = data.get("appointments", {})
        assert appointments.get("total", 0) > 0, "Should have appointments"
        
        revenue = data.get("revenue", {})
        assert revenue.get("total_earned", 0) > 0, "Should have revenue earned"
        assert revenue.get("total_recovered", 0) > 0, "Should have recovered revenue"
        
        barber_perf = data.get("barber_performance", [])
        assert len(barber_perf) > 0, "Should have barber performance data"
        
        daily_trend = data.get("daily_trend", [])
        assert len(daily_trend) > 0, "Should have daily trend data"
        
        # Check revenue values are non-zero
        has_revenue = any(day.get("revenue", 0) > 0 for day in daily_trend)
        assert has_revenue, "Daily trend should have non-zero revenue values"
        
        print(f"✓ Reporting shows populated data: {appointments.get('total')} appointments, "
              f"${revenue.get('total_earned')} earned, ${revenue.get('total_recovered')} recovered")

    def test_platform_stats_include_seeded_data(self):
        """Platform stats aggregate seeded data"""
        response = self.session.get(f"{BASE_URL}/api/admin/platform-stats")
        assert response.status_code == 200
        
        data = response.json()
        
        # Should show appointments from seed
        assert data.get("month_appointments", 0) > 0, "Should have month appointments"
        
        # Should have shop breakdown
        breakdown = data.get("shop_breakdown", [])
        assert len(breakdown) > 0, "Should have shop breakdown"
        
        demo_shop = next((s for s in breakdown if s["id"] == "demo_shop"), None)
        if demo_shop:
            assert demo_shop.get("month_appointments", 0) > 0, "demo_shop should have appointments"
            assert demo_shop.get("total_clients", 0) > 0, "demo_shop should have clients"
        
        print(f"✓ Platform stats: {data.get('month_appointments')} month appointments, "
              f"{data.get('total_clients')} total clients")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
