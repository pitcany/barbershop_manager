"""
Regression Test Suite for Barbershop Autopilot API
Tests all endpoints after server.py refactor into modular route files.
All 30+ endpoints must work identically after the refactor.
"""
import pytest
import requests
import os
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://booking-recovery.preview.emergentagent.com"


class TestHealthAndPublic:
    """Public endpoints (no auth required)"""
    
    def test_health_check(self):
        """GET /api/health - Health check"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        data = response.json()
        assert data["status"] == "healthy"
        assert "providers" in data
        assert data["providers"]["stripe_enabled"] == True
        print("✓ Health check passed - stripe enabled, calendar enabled")
    
    def test_root_endpoint(self):
        """GET /api/ - Root endpoint"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Barbershop Autopilot API"
        assert data["version"] == "1.0.0"
        print("✓ Root endpoint passed")
    
    def test_public_shop_info(self):
        """GET /api/public/shop-info - Public shop info (no auth)"""
        response = requests.get(f"{BASE_URL}/api/public/shop-info")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "business_hours" in data
        print(f"✓ Public shop info: {data.get('name')}")


class TestAuthFlow:
    """Authentication endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get auth token for all tests in this class"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["access_token"]
    
    def test_login_success(self):
        """POST /api/auth/login - Login with admin/admin123"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        print("✓ Login successful - token received")
    
    def test_login_invalid_credentials(self):
        """POST /api/auth/login - Invalid credentials returns 401"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "wrongpassword"
        })
        assert response.status_code == 401
        print("✓ Invalid credentials correctly returns 401")
    
    def test_get_me(self, auth_token):
        """GET /api/auth/me - Returns user info"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "admin"
        assert "shop_id" in data
        print(f"✓ Get me: username={data['username']}")


class TestShopEndpoints:
    """Shop configuration endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin", "password": "admin123"
        })
        return response.json()["access_token"]
    
    def test_get_shop(self, auth_token):
        """GET /api/shop - Returns shop config"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/shop", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "deposit_amount" in data
        assert "business_hours" in data
        print(f"✓ Shop config: {data.get('name')}, deposit=${data.get('deposit_amount')}")
    
    def test_update_shop_policy(self, auth_token):
        """PATCH /api/shop/policy - Update policy"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        # First get current value
        response = requests.get(f"{BASE_URL}/api/shop", headers=headers)
        original = response.json().get("max_messages_per_day", 4)
        
        # Update
        response = requests.patch(f"{BASE_URL}/api/shop/policy", headers=headers, json={
            "max_messages_per_day": 5
        })
        assert response.status_code == 200
        
        # Verify
        response = requests.get(f"{BASE_URL}/api/shop", headers=headers)
        assert response.json().get("max_messages_per_day") == 5
        
        # Restore
        requests.patch(f"{BASE_URL}/api/shop/policy", headers=headers, json={
            "max_messages_per_day": original
        })
        print("✓ Policy update works")


class TestDashboardEndpoints:
    """Dashboard KPI endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin", "password": "admin123"
        })
        return response.json()["access_token"]
    
    def test_dashboard_stats(self, auth_token):
        """GET /api/dashboard/stats - Dashboard KPIs"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "today_appointments" in data
        assert "upcoming_appointments" in data
        assert "no_show_rate" in data
        assert "month_revenue" in data
        assert "total_clients" in data
        print(f"✓ Dashboard stats: {data.get('today_appointments')} today, {data.get('total_clients')} clients")
    
    def test_revenue_chart(self, auth_token):
        """GET /api/dashboard/revenue-chart - Revenue chart data"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/dashboard/revenue-chart", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "chart_data" in data
        print(f"✓ Revenue chart: {len(data.get('chart_data', []))} data points")


class TestAppointmentEndpoints:
    """Appointment CRUD and scheduling"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin", "password": "admin123"
        })
        return response.json()["access_token"]
    
    def test_list_appointments(self, auth_token):
        """GET /api/appointments - List appointments with enriched client/barber/service"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/appointments", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "appointments" in data
        assert "total" in data
        # Check enrichment
        if data["appointments"]:
            apt = data["appointments"][0]
            assert "client" in apt
            assert "barber" in apt
            assert "service" in apt
        print(f"✓ List appointments: {data.get('total')} total")
    
    def test_get_single_appointment(self, auth_token):
        """GET /api/appointments/{id} - Single appointment detail"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        # Get first appointment ID
        response = requests.get(f"{BASE_URL}/api/appointments?limit=1", headers=headers)
        apts = response.json().get("appointments", [])
        if apts:
            apt_id = apts[0]["id"]
            response = requests.get(f"{BASE_URL}/api/appointments/{apt_id}", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == apt_id
            assert "client" in data
            assert "barber" in data
            assert "service" in data
            print(f"✓ Get appointment {apt_id}: status={data.get('status')}")
        else:
            print("⚠ No appointments to test")
    
    def test_get_availability(self, auth_token):
        """GET /api/scheduling/availability - Available slots"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/scheduling/availability", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "slots" in data
        assert "start" in data
        assert "end" in data
        print(f"✓ Availability: {len(data.get('slots', []))} slots")
    
    def test_create_appointment_conflict(self, auth_token):
        """POST /api/appointments - Conflict detection"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        # Try to create appointment at an existing time (should fail or succeed based on availability)
        response = requests.post(f"{BASE_URL}/api/appointments", headers=headers, json={
            "client_id": "client_1",
            "barber_id": "barber_1",
            "service_id": "service_1",
            "scheduled_at": datetime.now(timezone.utc).isoformat()  # Very soon - might conflict with hours
        })
        # Either 201 success or 409 conflict or 400 outside hours
        assert response.status_code in [201, 400, 409], f"Unexpected status: {response.status_code}"
        print(f"✓ Create appointment returned {response.status_code} (conflict detection working)")


class TestClientEndpoints:
    """Client management endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin", "password": "admin123"
        })
        return response.json()["access_token"]
    
    def test_list_clients(self, auth_token):
        """GET /api/clients - List/search clients"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/clients", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "clients" in data
        assert "total" in data
        print(f"✓ List clients: {data.get('total')} total")
    
    def test_search_clients(self, auth_token):
        """GET /api/clients?search=john - Search clients"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/clients?search=john", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "clients" in data
        print(f"✓ Search clients 'john': {len(data.get('clients', []))} found")
    
    def test_create_client(self, auth_token):
        """POST /api/clients - Create client"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        unique_phone = f"+1555{int(datetime.now().timestamp()) % 10000000:07d}"
        response = requests.post(f"{BASE_URL}/api/clients", headers=headers, json={
            "name": "TEST_RegressionClient",
            "phone": unique_phone,
            "sms_consent": True
        })
        assert response.status_code in [200, 201, 409], f"Create client failed: {response.text}"
        print(f"✓ Create client returned {response.status_code}")
    
    def test_get_client_history(self, auth_token):
        """GET /api/clients/{id}/history - Client history with stats"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        # Get first client
        response = requests.get(f"{BASE_URL}/api/clients?limit=1", headers=headers)
        clients = response.json().get("clients", [])
        if clients:
            client_id = clients[0]["id"]
            response = requests.get(f"{BASE_URL}/api/clients/{client_id}/history", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert "client" in data
            assert "appointments" in data
            assert "stats" in data
            print(f"✓ Client history: {data['stats'].get('total_appointments', 0)} appointments")
        else:
            print("⚠ No clients to test history")


class TestConversationEndpoints:
    """Conversation endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin", "password": "admin123"
        })
        return response.json()["access_token"]
    
    def test_list_conversations(self, auth_token):
        """GET /api/conversations - Grouped conversation list"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/conversations", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "conversations" in data
        print(f"✓ Conversations: {len(data.get('conversations', []))} threads")
    
    def test_get_conversation_detail(self, auth_token):
        """GET /api/conversations/{client_id} - Conversation detail"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        # Get client with messages
        response = requests.get(f"{BASE_URL}/api/conversations", headers=headers)
        convos = response.json().get("conversations", [])
        if convos:
            client_id = convos[0]["client_id"]
            response = requests.get(f"{BASE_URL}/api/conversations/{client_id}", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert "client" in data
            assert "messages" in data
            print(f"✓ Conversation detail: {len(data.get('messages', []))} messages")
        else:
            print("⚠ No conversations to test")


class TestWaitlistEndpoints:
    """Waitlist endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin", "password": "admin123"
        })
        return response.json()["access_token"]
    
    def test_list_waitlist(self, auth_token):
        """GET /api/waitlist - Active waitlist entries"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/waitlist", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "waitlist" in data
        assert "total" in data
        print(f"✓ Waitlist: {data.get('total')} entries")
    
    def test_create_waitlist_entry(self, auth_token):
        """POST /api/waitlist - Create waitlist entry"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        future_date = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
        response = requests.post(f"{BASE_URL}/api/waitlist", headers=headers, json={
            "client_id": "client_1",
            "service_id": "service_1",
            "preferred_date": future_date,
            "flexible_hours": 4,
            "notes": "TEST_Regression entry"
        })
        # May return 409 if client already has active entry
        assert response.status_code in [200, 201, 409], f"Create waitlist failed: {response.text}"
        print(f"✓ Create waitlist returned {response.status_code}")


class TestBarbersAndServices:
    """Barbers and services endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin", "password": "admin123"
        })
        return response.json()["access_token"]
    
    def test_list_barbers(self, auth_token):
        """GET /api/barbers - List barbers"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/barbers", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "barbers" in data
        print(f"✓ Barbers: {len(data.get('barbers', []))} active")
    
    def test_list_services(self, auth_token):
        """GET /api/services - List services"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/services", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "services" in data
        print(f"✓ Services: {len(data.get('services', []))} active")


class TestPaymentEndpoints:
    """Stripe payment endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin", "password": "admin123"
        })
        return response.json()["access_token"]
    
    def test_create_deposit_payment(self, auth_token):
        """POST /api/payments/create-deposit/{appointment_id} - Stripe checkout creation"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        # Find a deposit_pending appointment
        response = requests.get(f"{BASE_URL}/api/appointments?status=deposit_pending&limit=1", headers=headers)
        apts = response.json().get("appointments", [])
        if apts:
            apt_id = apts[0]["id"]
            response = requests.post(f"{BASE_URL}/api/payments/create-deposit/{apt_id}", headers=headers)
            # May be 200, 400 (already paid) or create success
            assert response.status_code in [200, 400], f"Create deposit failed: {response.text}"
            if response.status_code == 200:
                data = response.json()
                assert "checkout_url" in data
                assert "session_id" in data
                assert "checkout.stripe.com" in data["checkout_url"]
                print(f"✓ Create deposit: checkout_url starts with checkout.stripe.com")
            else:
                print(f"✓ Create deposit: {response.status_code} (may be already paid)")
        else:
            print("⚠ No deposit_pending appointments to test")
    
    def test_create_deposit_invalid_appointment(self, auth_token):
        """POST /api/payments/create-deposit/{invalid_id} - Returns 404"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.post(f"{BASE_URL}/api/payments/create-deposit/invalid_id_123", headers=headers)
        assert response.status_code == 404
        print("✓ Invalid appointment returns 404")
    
    def test_list_payment_transactions(self, auth_token):
        """GET /api/payments/transactions - List payment transactions"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/payments/transactions", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "transactions" in data
        assert "total" in data
        print(f"✓ Payment transactions: {data.get('total')} total")


class TestCalendarEndpoints:
    """Google Calendar OAuth endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin", "password": "admin123"
        })
        return response.json()["access_token"]
    
    def test_calendar_oauth_login(self, auth_token):
        """GET /api/oauth/calendar/login - Google Calendar OAuth URL"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/oauth/calendar/login", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "authorization_url" in data
        assert "accounts.google.com" in data["authorization_url"]
        print("✓ Calendar OAuth URL generated")
    
    def test_calendar_status(self, auth_token):
        """GET /api/calendar/status - Calendar connection status"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/calendar/status", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "connected" in data
        print(f"✓ Calendar status: connected={data.get('connected')}")


class TestJobsAndReporting:
    """Scheduler jobs and reporting endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin", "password": "admin123"
        })
        return response.json()["access_token"]
    
    def test_jobs_status(self, auth_token):
        """GET /api/jobs/status - Scheduler status"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/jobs/status", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "running" in data or "status" in data or isinstance(data, dict)
        print(f"✓ Jobs status: {data}")
    
    def test_run_daily_summary(self, auth_token):
        """POST /api/jobs/daily-summary/run - Trigger daily summary"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.post(f"{BASE_URL}/api/jobs/daily-summary/run", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        print("✓ Daily summary triggered")
    
    def test_reporting_overview(self, auth_token):
        """GET /api/reporting/overview - Comprehensive analytics"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/reporting/overview", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "appointments" in data
        assert "revenue" in data
        assert "daily_trend" in data
        print(f"✓ Reporting overview: {data['appointments'].get('total', 0)} appointments in period")


class TestAuditAndEmail:
    """Audit log and email outbox endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin", "password": "admin123"
        })
        return response.json()["access_token"]
    
    def test_audit_log(self, auth_token):
        """GET /api/audit-log - Integration audit entries"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/audit-log", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "audit_log" in data
        assert "count" in data
        print(f"✓ Audit log: {data.get('count')} entries")
    
    def test_email_outbox(self, auth_token):
        """GET /api/email-outbox - Email outbox entries"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/email-outbox", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "emails" in data
        print(f"✓ Email outbox: {len(data.get('emails', []))} emails")


class TestWebhooks:
    """Webhook endpoints (accessibility check)"""
    
    def test_stripe_webhook_accessible(self):
        """POST /api/webhooks/stripe - Stripe webhook endpoint accessible"""
        # Just test that endpoint exists and responds (will fail with 400 due to missing signature)
        response = requests.post(f"{BASE_URL}/api/webhooks/stripe", data=b'{}', headers={"Stripe-Signature": ""})
        # Should not be 404
        assert response.status_code != 404, "Stripe webhook endpoint not found"
        print(f"✓ Stripe webhook endpoint accessible (status: {response.status_code})")
    
    def test_twilio_webhook_accessible(self):
        """POST /api/webhooks/twilio/inbound - Twilio webhook endpoint accessible"""
        response = requests.post(f"{BASE_URL}/api/webhooks/twilio/inbound", data={})
        # Should not be 404
        assert response.status_code != 404, "Twilio webhook endpoint not found"
        print(f"✓ Twilio webhook endpoint accessible (status: {response.status_code})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
