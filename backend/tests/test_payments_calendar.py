"""
Tests for Stripe Payments and Google Calendar integration endpoints
Iteration 8 - Testing payment and calendar features
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://salon-flow-manager.preview.emergentagent.com").rstrip("/")


class TestAuth:
    """Get authentication token for subsequent tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Login and get auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["access_token"]

    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        """Headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }


class TestPaymentCreateDeposit(TestAuth):
    """Test POST /api/payments/create-deposit/{appointment_id}"""
    
    def test_create_deposit_returns_checkout_url(self, headers):
        """Creating deposit should return Stripe checkout URL"""
        # Get a deposit_pending appointment
        response = requests.get(
            f"{BASE_URL}/api/appointments?status=deposit_pending",
            headers=headers
        )
        assert response.status_code == 200
        appointments = response.json().get("appointments", [])
        
        if not appointments:
            pytest.skip("No deposit_pending appointments available")
        
        apt_id = appointments[0]["id"]
        
        # Create deposit
        response = requests.post(
            f"{BASE_URL}/api/payments/create-deposit/{apt_id}",
            headers={**headers, "x-origin": BASE_URL}
        )
        
        assert response.status_code == 200, f"Create deposit failed: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "checkout_url" in data, "Missing checkout_url in response"
        assert "session_id" in data, "Missing session_id in response"
        
        # Validate Stripe checkout URL format
        assert data["checkout_url"].startswith("https://checkout.stripe.com"), \
            f"Invalid checkout URL: {data['checkout_url']}"
        assert data["session_id"].startswith("cs_test_"), \
            f"Invalid session_id format: {data['session_id']}"
        
        print(f"✓ Created deposit with session: {data['session_id'][:40]}...")
        return data["session_id"]
    
    def test_create_deposit_for_invalid_appointment(self, headers):
        """Creating deposit for non-existent appointment should return 404"""
        response = requests.post(
            f"{BASE_URL}/api/payments/create-deposit/invalid_appointment_id",
            headers={**headers, "x-origin": BASE_URL}
        )
        assert response.status_code == 404
    
    def test_create_deposit_updates_payment_transactions(self, headers):
        """After creating deposit, payment_transactions should have the record"""
        # Get transactions
        response = requests.get(
            f"{BASE_URL}/api/payments/transactions",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "transactions" in data
        assert "total" in data
        assert data["total"] > 0, "No transactions found"
        
        # Verify transaction fields
        txn = data["transactions"][0]
        required_fields = ["id", "shop_id", "client_id", "appointment_id", 
                          "amount", "session_id", "payment_status", "status"]
        for field in required_fields:
            assert field in txn, f"Missing field: {field}"
        
        print(f"✓ Found {data['total']} payment transaction(s)")


class TestPaymentStatus(TestAuth):
    """Test GET /api/payments/status/{session_id}"""
    
    def test_get_payment_status_valid_session(self, headers):
        """Getting payment status should return Stripe status"""
        # First get a valid session_id
        response = requests.get(
            f"{BASE_URL}/api/payments/transactions",
            headers=headers
        )
        assert response.status_code == 200
        txns = response.json().get("transactions", [])
        
        if not txns:
            pytest.skip("No payment transactions available")
        
        session_id = txns[0]["session_id"]
        
        # Get status
        response = requests.get(
            f"{BASE_URL}/api/payments/status/{session_id}",
            headers=headers
        )
        assert response.status_code == 200, f"Get status failed: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "status" in data, "Missing status field"
        assert "payment_status" in data, "Missing payment_status field"
        assert "amount" in data, "Missing amount field"
        
        print(f"✓ Payment status: {data['payment_status']}, amount: ${data['amount']}")
    
    def test_get_payment_status_invalid_session(self, headers):
        """Getting status for invalid session should return 404"""
        response = requests.get(
            f"{BASE_URL}/api/payments/status/invalid_session_id",
            headers=headers
        )
        assert response.status_code == 404


class TestPaymentTransactions(TestAuth):
    """Test GET /api/payments/transactions"""
    
    def test_list_transactions(self, headers):
        """Listing transactions should return paginated results"""
        response = requests.get(
            f"{BASE_URL}/api/payments/transactions",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "transactions" in data
        assert "total" in data
        assert isinstance(data["transactions"], list)
        
        print(f"✓ Listed {len(data['transactions'])} transactions (total: {data['total']})")
    
    def test_list_transactions_pagination(self, headers):
        """Transactions endpoint should support limit and skip params"""
        response = requests.get(
            f"{BASE_URL}/api/payments/transactions?limit=5&skip=0",
            headers=headers
        )
        assert response.status_code == 200


class TestStripeWebhook:
    """Test POST /api/webhooks/stripe"""
    
    def test_webhook_endpoint_accessible(self):
        """Stripe webhook endpoint should be accessible"""
        # Webhook doesn't require auth but needs proper signature
        response = requests.post(
            f"{BASE_URL}/api/webhooks/stripe",
            headers={"Content-Type": "application/json"},
            json={}
        )
        # Should return 400 (invalid signature) not 404/500
        assert response.status_code in [400, 401, 403], \
            f"Unexpected status: {response.status_code}"
        print("✓ Webhook endpoint accessible (rejects invalid requests)")


class TestGoogleCalendarOAuth(TestAuth):
    """Test GET /api/oauth/calendar/login"""
    
    def test_oauth_login_returns_authorization_url(self, headers):
        """OAuth login should return Google authorization URL"""
        response = requests.get(
            f"{BASE_URL}/api/oauth/calendar/login",
            headers={**headers, "x-origin": BASE_URL}
        )
        assert response.status_code == 200, f"OAuth login failed: {response.text}"
        data = response.json()
        
        # Validate response
        assert "authorization_url" in data, "Missing authorization_url"
        
        # Validate Google OAuth URL format
        auth_url = data["authorization_url"]
        assert "accounts.google.com/o/oauth2/auth" in auth_url, \
            f"Invalid auth URL: {auth_url}"
        assert "client_id=" in auth_url, "Missing client_id in auth URL"
        assert "redirect_uri=" in auth_url, "Missing redirect_uri in auth URL"
        assert "scope=" in auth_url, "Missing scope in auth URL"
        
        print(f"✓ OAuth authorization URL generated")


class TestCalendarStatus(TestAuth):
    """Test GET /api/calendar/status"""
    
    def test_calendar_status_structure(self, headers):
        """Calendar status should return connection info"""
        response = requests.get(
            f"{BASE_URL}/api/calendar/status",
            headers=headers
        )
        assert response.status_code == 200, f"Get status failed: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "connected" in data, "Missing connected field"
        assert isinstance(data["connected"], bool), "connected should be boolean"
        
        if data["connected"]:
            assert "email" in data, "Missing email when connected"
            assert "connected_at" in data, "Missing connected_at when connected"
            print(f"✓ Calendar connected as: {data['email']}")
        else:
            print("✓ Calendar not connected (expected until OAuth flow completed)")


class TestCalendarDisconnect(TestAuth):
    """Test POST /api/calendar/disconnect"""
    
    def test_disconnect_calendar(self, headers):
        """Disconnecting calendar should return success"""
        response = requests.post(
            f"{BASE_URL}/api/calendar/disconnect",
            headers=headers
        )
        assert response.status_code == 200, f"Disconnect failed: {response.text}"
        data = response.json()
        
        assert "message" in data
        assert "disconnected" in data["message"].lower()
        
        print("✓ Calendar disconnect endpoint working")


class TestCalendarEvents(TestAuth):
    """Test GET /api/calendar/events"""
    
    def test_list_calendar_events(self, headers):
        """Listing calendar events should return events or not_connected"""
        response = requests.get(
            f"{BASE_URL}/api/calendar/events",
            headers=headers
        )
        assert response.status_code == 200, f"Get events failed: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "events" in data, "Missing events field"
        assert "source" in data, "Missing source field"
        assert isinstance(data["events"], list), "events should be list"
        
        # Source should indicate status
        assert data["source"] in ["google", "mock", "not_connected", "error"], \
            f"Unexpected source: {data['source']}"
        
        print(f"✓ Calendar events source: {data['source']}, count: {len(data['events'])}")


class TestSettingsIntegrationInfo(TestAuth):
    """Test that shop settings include integration info"""
    
    def test_shop_has_deposit_settings(self, headers):
        """Shop should have deposit configuration"""
        response = requests.get(
            f"{BASE_URL}/api/shop",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check deposit settings exist
        assert "deposit_amount" in data, "Missing deposit_amount setting"
        assert "deposit_required_hours" in data, "Missing deposit_required_hours setting"
        
        print(f"✓ Deposit settings: ${data['deposit_amount']} required {data['deposit_required_hours']}h before appointment")


class TestHealthCheckProviders:
    """Test health endpoint shows provider status"""
    
    def test_health_shows_provider_status(self):
        """Health endpoint should show Stripe and Calendar enabled"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        
        assert "providers" in data, "Missing providers in health"
        providers = data["providers"]
        
        assert "stripe_enabled" in providers, "Missing stripe_enabled"
        assert "calendar_enabled" in providers, "Missing calendar_enabled"
        
        print(f"✓ Providers - Stripe: {providers['stripe_enabled']}, Calendar: {providers['calendar_enabled']}")


class TestRegressionEndpoints(TestAuth):
    """Regression tests for existing endpoints"""
    
    def test_appointments_list(self, headers):
        """Appointments list should work"""
        response = requests.get(f"{BASE_URL}/api/appointments", headers=headers)
        assert response.status_code == 200
        assert "appointments" in response.json()
        print("✓ Regression: Appointments list OK")
    
    def test_clients_list(self, headers):
        """Clients list should work"""
        response = requests.get(f"{BASE_URL}/api/clients", headers=headers)
        assert response.status_code == 200
        assert "clients" in response.json()
        print("✓ Regression: Clients list OK")
    
    def test_dashboard_stats(self, headers):
        """Dashboard stats should work"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=headers)
        assert response.status_code == 200
        print("✓ Regression: Dashboard stats OK")
    
    def test_services_list(self, headers):
        """Services list should work"""
        response = requests.get(f"{BASE_URL}/api/services", headers=headers)
        assert response.status_code == 200
        assert "services" in response.json()
        print("✓ Regression: Services list OK")
    
    def test_barbers_list(self, headers):
        """Barbers list should work"""
        response = requests.get(f"{BASE_URL}/api/barbers", headers=headers)
        assert response.status_code == 200
        assert "barbers" in response.json()
        print("✓ Regression: Barbers list OK")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
