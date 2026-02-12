"""
Backend API Tests for Barbershop Autopilot MVP - New Features
Tests: Client Management, Scheduling/Conflict Prevention, Real-Time Conversations
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://salon-flow-manager.preview.emergentagent.com').rstrip('/')

class TestAuth:
    """Authentication endpoint tests"""
    
    @pytest.fixture(scope="class")
    def token(self):
        """Get auth token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["access_token"]
    
    def test_login_success(self):
        """Test successful login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert len(data["access_token"]) > 0
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "wrong",
            "password": "wrong"
        })
        assert response.status_code == 401


class TestDashboard:
    """Dashboard statistics tests"""
    
    @pytest.fixture(scope="class")
    def auth_header(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin", "password": "admin123"
        })
        return {"Authorization": f"Bearer {response.json()['access_token']}"}
    
    def test_dashboard_stats(self, auth_header):
        """Test dashboard stats endpoint returns all expected fields"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        
        # Verify all expected fields are present
        expected_fields = [
            "appointments_today", "appointments_month", "no_shows_month",
            "revenue_recovered", "waitlist_count", "messages_today",
            "deposits_collected", "no_show_rate"
        ]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
        
        # Verify data types
        assert isinstance(data["appointments_today"], int)
        assert isinstance(data["no_show_rate"], (int, float))


class TestClientManagement:
    """Client CRUD and history tests"""
    
    @pytest.fixture(scope="class")
    def auth_header(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin", "password": "admin123"
        })
        return {"Authorization": f"Bearer {response.json()['access_token']}"}
    
    def test_list_clients(self, auth_header):
        """Test listing all clients"""
        response = requests.get(f"{BASE_URL}/api/clients", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        
        assert "clients" in data
        assert "total" in data
        assert isinstance(data["clients"], list)
        assert data["total"] >= 0
    
    def test_client_search_by_name(self, auth_header):
        """Test searching clients by name"""
        response = requests.get(f"{BASE_URL}/api/clients?search=John", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert "clients" in data
    
    def test_client_search_by_phone(self, auth_header):
        """Test searching clients by phone"""
        response = requests.get(f"{BASE_URL}/api/clients?search=5559876543", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert "clients" in data
    
    def test_create_client_success(self, auth_header):
        """Test creating a new client"""
        timestamp = datetime.now().strftime("%H%M%S")
        new_client = {
            "name": f"TEST_Client_{timestamp}",
            "phone": f"+1555{timestamp}",
            "email": f"test{timestamp}@example.com",
            "sms_consent": True
        }
        
        response = requests.post(f"{BASE_URL}/api/clients", json=new_client, headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == new_client["name"]
        assert data["phone"] == new_client["phone"]
        assert "id" in data
        
        # Store for cleanup/verification
        self.__class__.created_client_id = data["id"]
    
    def test_create_client_duplicate_phone(self, auth_header):
        """Test creating client with duplicate phone fails"""
        # Use existing phone
        duplicate = {
            "name": "Duplicate Test",
            "phone": "+15559876543",  # Existing phone
            "sms_consent": True
        }
        
        response = requests.post(f"{BASE_URL}/api/clients", json=duplicate, headers=auth_header)
        assert response.status_code == 409
        assert "already exists" in response.json().get("detail", "").lower()
    
    def test_get_client_by_id(self, auth_header):
        """Test getting client by ID"""
        response = requests.get(f"{BASE_URL}/api/clients/client_1", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        
        assert "id" in data
        assert "name" in data
        assert "phone" in data
    
    def test_get_client_not_found(self, auth_header):
        """Test getting non-existent client returns 404"""
        response = requests.get(f"{BASE_URL}/api/clients/nonexistent_id", headers=auth_header)
        assert response.status_code == 404
    
    def test_get_client_history(self, auth_header):
        """Test getting client history with appointments, messages, and stats"""
        response = requests.get(f"{BASE_URL}/api/clients/client_1/history", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "client" in data
        assert "appointments" in data
        assert "messages" in data
        assert "stats" in data
        
        # Verify stats fields
        stats = data["stats"]
        assert "total_appointments" in stats
        assert "completed_appointments" in stats
        assert "no_shows" in stats
        assert "no_show_rate" in stats
        assert "total_spent" in stats
    
    def test_update_client(self, auth_header):
        """Test updating client details"""
        # First get a client
        response = requests.get(f"{BASE_URL}/api/clients/client_1", headers=auth_header)
        assert response.status_code == 200
        
        # Update the client name
        update_data = {"name": "John Smith Updated"}
        response = requests.patch(
            f"{BASE_URL}/api/clients/client_1",
            json=update_data,
            headers=auth_header
        )
        assert response.status_code == 200
        
        # Verify update
        data = response.json()
        assert data["name"] == "John Smith Updated"
        
        # Revert the name
        requests.patch(
            f"{BASE_URL}/api/clients/client_1",
            json={"name": "John Smith"},
            headers=auth_header
        )


class TestSchedulingAvailability:
    """Scheduling and availability tests"""
    
    @pytest.fixture(scope="class")
    def auth_header(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin", "password": "admin123"
        })
        return {"Authorization": f"Bearer {response.json()['access_token']}"}
    
    def test_get_availability_returns_slots(self, auth_header):
        """Test getting availability returns time slots"""
        # Use tomorrow to ensure business hours are available
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        response = requests.get(
            f"{BASE_URL}/api/scheduling/availability?date={tomorrow}",
            headers=auth_header
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "date" in data
        assert "duration_minutes" in data
        assert "slots" in data
        assert isinstance(data["slots"], list)
    
    def test_availability_with_service_id(self, auth_header):
        """Test availability respects service duration"""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        response = requests.get(
            f"{BASE_URL}/api/scheduling/availability?date={tomorrow}&service_id=service_1",
            headers=auth_header
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["duration_minutes"] == 30  # Classic Haircut is 30 min
    
    def test_availability_with_barber_filter(self, auth_header):
        """Test availability can filter by barber"""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        response = requests.get(
            f"{BASE_URL}/api/scheduling/availability?date={tomorrow}&barber_id=barber_1",
            headers=auth_header
        )
        assert response.status_code == 200
        data = response.json()
        
        # All slots should be for barber_1
        for slot in data["slots"]:
            assert slot["barber_id"] == "barber_1"
    
    def test_validate_slot_endpoint(self, auth_header):
        """Test slot validation endpoint"""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        scheduled_at = f"{tomorrow}T14:00:00Z"  # 10 AM Eastern (14:00 UTC)
        
        response = requests.post(
            f"{BASE_URL}/api/scheduling/validate-slot",
            params={
                "barber_id": "barber_1",
                "scheduled_at": scheduled_at,
                "duration_minutes": 30
            },
            headers=auth_header
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "valid" in data
        assert "barber_id" in data
        assert "scheduled_at" in data
    
    def test_barber_schedule_endpoint(self, auth_header):
        """Test getting barber schedule"""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        response = requests.get(
            f"{BASE_URL}/api/scheduling/barber/barber_1/schedule?start_date={tomorrow}",
            headers=auth_header
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "barber" in data
        assert "start_date" in data
        assert "end_date" in data
        assert "appointments" in data


class TestAppointmentCreation:
    """Appointment creation with conflict prevention tests"""
    
    @pytest.fixture(scope="class")
    def auth_header(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin", "password": "admin123"
        })
        return {"Authorization": f"Bearer {response.json()['access_token']}"}
    
    def test_create_appointment_success(self, auth_header):
        """Test creating a new appointment"""
        # Get available slot first
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        availability_response = requests.get(
            f"{BASE_URL}/api/scheduling/availability?date={tomorrow}&barber_id=barber_1",
            headers=auth_header
        )
        assert availability_response.status_code == 200
        slots = availability_response.json()["slots"]
        
        if not slots:
            pytest.skip("No available slots for testing")
        
        # Use first available slot
        slot = slots[0]
        
        appointment_data = {
            "client_id": "client_1",
            "barber_id": slot["barber_id"],
            "service_id": "service_1",
            "scheduled_at": slot["start"],
            "notes": "TEST appointment"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/appointments",
            json=appointment_data,
            headers=auth_header
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "id" in data
        assert data["client_id"] == "client_1"
        assert data["barber_id"] == slot["barber_id"]
        
        # Store for later tests
        self.__class__.created_appointment_id = data["id"]
        self.__class__.created_slot = slot
    
    def test_create_appointment_conflict_prevention(self, auth_header):
        """Test that double-booking is prevented"""
        # Try to create appointment at same slot
        if not hasattr(self.__class__, 'created_slot'):
            pytest.skip("No appointment created in previous test")
        
        slot = self.__class__.created_slot
        
        appointment_data = {
            "client_id": "client_2",
            "barber_id": slot["barber_id"],
            "service_id": "service_1",
            "scheduled_at": slot["start"],
            "notes": "This should fail - double booking"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/appointments",
            json=appointment_data,
            headers=auth_header
        )
        
        # Should return conflict error
        assert response.status_code == 409
        assert "conflict" in response.json().get("detail", "").lower() or "unavailable" in response.json().get("detail", "").lower()
    
    def test_create_appointment_invalid_client(self, auth_header):
        """Test appointment creation with invalid client"""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        appointment_data = {
            "client_id": "nonexistent_client",
            "barber_id": "barber_1",
            "service_id": "service_1",
            "scheduled_at": f"{tomorrow}T16:00:00Z",
        }
        
        response = requests.post(
            f"{BASE_URL}/api/appointments",
            json=appointment_data,
            headers=auth_header
        )
        assert response.status_code == 404
        assert "client" in response.json().get("detail", "").lower()
    
    def test_create_appointment_invalid_barber(self, auth_header):
        """Test appointment creation with invalid barber"""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        appointment_data = {
            "client_id": "client_1",
            "barber_id": "nonexistent_barber",
            "service_id": "service_1",
            "scheduled_at": f"{tomorrow}T17:00:00Z",
        }
        
        response = requests.post(
            f"{BASE_URL}/api/appointments",
            json=appointment_data,
            headers=auth_header
        )
        assert response.status_code == 404
        assert "barber" in response.json().get("detail", "").lower()


class TestConversations:
    """Conversation and messaging tests"""
    
    @pytest.fixture(scope="class")
    def auth_header(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin", "password": "admin123"
        })
        return {"Authorization": f"Bearer {response.json()['access_token']}"}
    
    def test_list_conversations(self, auth_header):
        """Test listing conversation threads"""
        response = requests.get(f"{BASE_URL}/api/conversations", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        
        assert "conversations" in data
        assert isinstance(data["conversations"], list)
        
        # Verify conversation structure
        if data["conversations"]:
            conv = data["conversations"][0]
            assert "client_id" in conv
            assert "last_message" in conv
            assert "last_message_at" in conv
            assert "message_count" in conv
    
    def test_get_conversation_by_client(self, auth_header):
        """Test getting messages for a specific client"""
        # Get a client with messages
        convs_response = requests.get(f"{BASE_URL}/api/conversations", headers=auth_header)
        conversations = convs_response.json()["conversations"]
        
        if not conversations:
            pytest.skip("No conversations to test")
        
        client_id = conversations[0]["client_id"]
        
        response = requests.get(
            f"{BASE_URL}/api/conversations/{client_id}",
            headers=auth_header
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "messages" in data
        assert "client" in data
        assert isinstance(data["messages"], list)
    
    def test_poll_new_messages(self, auth_header):
        """Test polling endpoint for new messages"""
        response = requests.get(
            f"{BASE_URL}/api/conversations/poll/new",
            headers=auth_header
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "messages" in data
        assert "count" in data
        assert "poll_interval_ms" in data
        assert data["poll_interval_ms"] == 3000
    
    def test_poll_with_since_parameter(self, auth_header):
        """Test polling with since timestamp"""
        # Use a past timestamp
        past = (datetime.now() - timedelta(hours=1)).isoformat()
        
        response = requests.get(
            f"{BASE_URL}/api/conversations/poll/new?since={past}",
            headers=auth_header
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "messages" in data
        assert "latest_timestamp" in data
    
    def test_poll_with_client_filter(self, auth_header):
        """Test polling filtered to specific client"""
        response = requests.get(
            f"{BASE_URL}/api/conversations/poll/new?client_id=client_1",
            headers=auth_header
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "messages" in data
    
    def test_live_activity_endpoint(self, auth_header):
        """Test live activity endpoint for dashboard"""
        response = requests.get(
            f"{BASE_URL}/api/conversations/activity/live",
            headers=auth_header
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "messages" in data
        assert "since" in data
        assert "count" in data


class TestWaitlist:
    """Waitlist management tests"""
    
    @pytest.fixture(scope="class")
    def auth_header(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin", "password": "admin123"
        })
        return {"Authorization": f"Bearer {response.json()['access_token']}"}
    
    def test_list_waitlist(self, auth_header):
        """Test listing active waitlist entries"""
        response = requests.get(f"{BASE_URL}/api/waitlist", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        
        assert "waitlist" in data
        assert isinstance(data["waitlist"], list)
    
    def test_add_to_waitlist(self, auth_header):
        """Test adding client to waitlist"""
        tomorrow = (datetime.now() + timedelta(days=1)).isoformat()
        
        # First check if client_2 is already on waitlist
        waitlist_response = requests.get(f"{BASE_URL}/api/waitlist", headers=auth_header)
        existing = [w for w in waitlist_response.json()["waitlist"] if w["client_id"] == "client_2"]
        
        if existing:
            pytest.skip("Client already on waitlist")
        
        waitlist_data = {
            "client_id": "client_2",
            "service_id": "service_1",
            "preferred_date": tomorrow,
            "flexible_hours": 2
        }
        
        response = requests.post(
            f"{BASE_URL}/api/waitlist",
            json=waitlist_data,
            headers=auth_header
        )
        
        # Either success or already on waitlist
        assert response.status_code in [200, 409]
        
        if response.status_code == 200:
            data = response.json()
            assert "id" in data
            self.__class__.waitlist_entry_id = data["id"]


class TestBarbersAndServices:
    """Barbers and services endpoint tests"""
    
    @pytest.fixture(scope="class")
    def auth_header(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin", "password": "admin123"
        })
        return {"Authorization": f"Bearer {response.json()['access_token']}"}
    
    def test_list_barbers(self, auth_header):
        """Test listing all barbers"""
        response = requests.get(f"{BASE_URL}/api/barbers", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        
        assert "barbers" in data
        assert len(data["barbers"]) >= 3  # We have 3 seed barbers
        
        # Verify barber structure
        barber = data["barbers"][0]
        assert "id" in barber
        assert "name" in barber
    
    def test_list_services(self, auth_header):
        """Test listing all services"""
        response = requests.get(f"{BASE_URL}/api/services", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        
        assert "services" in data
        assert len(data["services"]) >= 4  # We have 4 seed services
        
        # Verify service structure
        service = data["services"][0]
        assert "id" in service
        assert "name" in service
        assert "price" in service
        assert "duration_minutes" in service


class TestAppointments:
    """Appointment listing and status tests"""
    
    @pytest.fixture(scope="class")
    def auth_header(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin", "password": "admin123"
        })
        return {"Authorization": f"Bearer {response.json()['access_token']}"}
    
    def test_list_appointments(self, auth_header):
        """Test listing appointments"""
        response = requests.get(f"{BASE_URL}/api/appointments", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        
        assert "appointments" in data
        assert "total" in data
    
    def test_list_appointments_with_status_filter(self, auth_header):
        """Test filtering appointments by status"""
        response = requests.get(
            f"{BASE_URL}/api/appointments?status=pending",
            headers=auth_header
        )
        assert response.status_code == 200
        data = response.json()
        
        # All returned appointments should have pending status
        for apt in data["appointments"]:
            assert apt["status"] == "pending"
    
    def test_get_appointment_by_id(self, auth_header):
        """Test getting appointment by ID"""
        # First get list to find an ID
        list_response = requests.get(f"{BASE_URL}/api/appointments", headers=auth_header)
        appointments = list_response.json()["appointments"]
        
        if not appointments:
            pytest.skip("No appointments to test")
        
        apt_id = appointments[0]["id"]
        
        response = requests.get(
            f"{BASE_URL}/api/appointments/{apt_id}",
            headers=auth_header
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == apt_id
    
    def test_appointment_not_found(self, auth_header):
        """Test getting non-existent appointment"""
        response = requests.get(
            f"{BASE_URL}/api/appointments/nonexistent_id",
            headers=auth_header
        )
        assert response.status_code == 404


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
