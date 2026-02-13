"""
P0 New Features Backend Tests - Barbers, Services, Today Schedule, and New Appointments
Tests for iteration_11 covering:
1. Barber CRUD (POST/PATCH/DELETE /api/barbers)
2. Service CRUD (POST/PATCH/DELETE /api/services)
3. Today's Schedule (GET /api/dashboard/today-schedule)
4. Create Appointment (POST /api/appointments)
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_token(api_client):
    """Get authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json().get("access_token")


@pytest.fixture(scope="module")
def authenticated_client(api_client, auth_token):
    """Session with auth header"""
    api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return api_client


class TestHealthAndAuth:
    """Basic health and auth checks"""
    
    def test_health_endpoint(self, api_client):
        """Health endpoint returns healthy status"""
        response = api_client.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
    
    def test_login_success(self, api_client):
        """Login with valid credentials returns token"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"


class TestBarberCRUD:
    """CRUD tests for barbers - /api/barbers endpoints"""
    
    def test_list_barbers(self, authenticated_client):
        """GET /api/barbers returns list of barbers"""
        response = authenticated_client.get(f"{BASE_URL}/api/barbers")
        assert response.status_code == 200
        data = response.json()
        assert "barbers" in data
        assert isinstance(data["barbers"], list)
        # Verify barber structure
        if len(data["barbers"]) > 0:
            barber = data["barbers"][0]
            assert "id" in barber
            assert "name" in barber
    
    def test_create_barber(self, authenticated_client):
        """POST /api/barbers creates a new barber"""
        response = authenticated_client.post(f"{BASE_URL}/api/barbers", json={
            "name": "TEST_Barber_Create",
            "email": "test_barber@shop.com",
            "phone": "+15551112222"
        })
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["name"] == "TEST_Barber_Create"
        assert data["email"] == "test_barber@shop.com"
        assert data["active"] == True
        
        # Cleanup - delete the test barber
        barber_id = data["id"]
        authenticated_client.delete(f"{BASE_URL}/api/barbers/{barber_id}")
    
    def test_create_barber_name_required(self, authenticated_client):
        """POST /api/barbers fails without name"""
        response = authenticated_client.post(f"{BASE_URL}/api/barbers", json={
            "email": "noname@shop.com"
        })
        assert response.status_code == 422  # Validation error
    
    def test_update_barber(self, authenticated_client):
        """PATCH /api/barbers/{id} updates barber details"""
        # First create a barber
        create_response = authenticated_client.post(f"{BASE_URL}/api/barbers", json={
            "name": "TEST_Barber_Update"
        })
        assert create_response.status_code == 200
        barber_id = create_response.json()["id"]
        
        # Update the barber
        update_response = authenticated_client.patch(f"{BASE_URL}/api/barbers/{barber_id}", json={
            "name": "TEST_Barber_Updated",
            "email": "updated@shop.com"
        })
        assert update_response.status_code == 200
        updated = update_response.json()
        assert updated["name"] == "TEST_Barber_Updated"
        assert updated["email"] == "updated@shop.com"
        
        # Cleanup
        authenticated_client.delete(f"{BASE_URL}/api/barbers/{barber_id}")
    
    def test_update_nonexistent_barber(self, authenticated_client):
        """PATCH /api/barbers/{id} returns 404 for invalid id"""
        response = authenticated_client.patch(f"{BASE_URL}/api/barbers/nonexistent-id", json={
            "name": "New Name"
        })
        assert response.status_code == 404
    
    def test_delete_barber(self, authenticated_client):
        """DELETE /api/barbers/{id} deactivates the barber"""
        # First create a barber
        create_response = authenticated_client.post(f"{BASE_URL}/api/barbers", json={
            "name": "TEST_Barber_Delete"
        })
        assert create_response.status_code == 200
        barber_id = create_response.json()["id"]
        
        # Delete the barber
        delete_response = authenticated_client.delete(f"{BASE_URL}/api/barbers/{barber_id}")
        assert delete_response.status_code == 200
        data = delete_response.json()
        assert data["message"] == "Barber deactivated"
        
        # Verify barber is no longer in active list
        list_response = authenticated_client.get(f"{BASE_URL}/api/barbers")
        barbers = list_response.json()["barbers"]
        assert not any(b["id"] == barber_id for b in barbers)


class TestServiceCRUD:
    """CRUD tests for services - /api/services endpoints"""
    
    def test_list_services(self, authenticated_client):
        """GET /api/services returns list of services"""
        response = authenticated_client.get(f"{BASE_URL}/api/services")
        assert response.status_code == 200
        data = response.json()
        assert "services" in data
        assert isinstance(data["services"], list)
        # Verify service structure
        if len(data["services"]) > 0:
            service = data["services"][0]
            assert "id" in service
            assert "name" in service
            assert "price" in service
            assert "duration_minutes" in service
    
    def test_create_service(self, authenticated_client):
        """POST /api/services creates a new service"""
        response = authenticated_client.post(f"{BASE_URL}/api/services", json={
            "name": "TEST_Service_Create",
            "description": "Test service description",
            "duration_minutes": 45,
            "price": 55.00
        })
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["name"] == "TEST_Service_Create"
        assert data["description"] == "Test service description"
        assert data["duration_minutes"] == 45
        assert data["price"] == 55.00
        assert data["active"] == True
        
        # Cleanup
        service_id = data["id"]
        authenticated_client.delete(f"{BASE_URL}/api/services/{service_id}")
    
    def test_create_service_name_required(self, authenticated_client):
        """POST /api/services fails without name"""
        response = authenticated_client.post(f"{BASE_URL}/api/services", json={
            "price": 25.00
        })
        assert response.status_code == 422  # Validation error
    
    def test_create_service_price_required(self, authenticated_client):
        """POST /api/services fails without price"""
        response = authenticated_client.post(f"{BASE_URL}/api/services", json={
            "name": "No Price Service"
        })
        assert response.status_code == 422  # Validation error
    
    def test_update_service(self, authenticated_client):
        """PATCH /api/services/{id} updates service details"""
        # First create a service
        create_response = authenticated_client.post(f"{BASE_URL}/api/services", json={
            "name": "TEST_Service_Update",
            "price": 30.00
        })
        assert create_response.status_code == 200
        service_id = create_response.json()["id"]
        
        # Update the service
        update_response = authenticated_client.patch(f"{BASE_URL}/api/services/{service_id}", json={
            "name": "TEST_Service_Updated",
            "price": 35.00,
            "duration_minutes": 60
        })
        assert update_response.status_code == 200
        updated = update_response.json()
        assert updated["name"] == "TEST_Service_Updated"
        assert updated["price"] == 35.00
        assert updated["duration_minutes"] == 60
        
        # Cleanup
        authenticated_client.delete(f"{BASE_URL}/api/services/{service_id}")
    
    def test_update_nonexistent_service(self, authenticated_client):
        """PATCH /api/services/{id} returns 404 for invalid id"""
        response = authenticated_client.patch(f"{BASE_URL}/api/services/nonexistent-id", json={
            "name": "New Name"
        })
        assert response.status_code == 404
    
    def test_delete_service(self, authenticated_client):
        """DELETE /api/services/{id} deactivates the service"""
        # First create a service
        create_response = authenticated_client.post(f"{BASE_URL}/api/services", json={
            "name": "TEST_Service_Delete",
            "price": 20.00
        })
        assert create_response.status_code == 200
        service_id = create_response.json()["id"]
        
        # Delete the service
        delete_response = authenticated_client.delete(f"{BASE_URL}/api/services/{service_id}")
        assert delete_response.status_code == 200
        data = delete_response.json()
        assert data["message"] == "Service deactivated"
        
        # Verify service is no longer in active list
        list_response = authenticated_client.get(f"{BASE_URL}/api/services")
        services = list_response.json()["services"]
        assert not any(s["id"] == service_id for s in services)


class TestTodaySchedule:
    """Tests for Today's Schedule endpoint"""
    
    def test_today_schedule_returns_appointments(self, authenticated_client):
        """GET /api/dashboard/today-schedule returns today's appointments"""
        response = authenticated_client.get(f"{BASE_URL}/api/dashboard/today-schedule")
        assert response.status_code == 200
        data = response.json()
        assert "appointments" in data
        assert "total" in data
        assert isinstance(data["appointments"], list)
    
    def test_today_schedule_includes_details(self, authenticated_client):
        """Today's schedule includes client, barber, and service details"""
        response = authenticated_client.get(f"{BASE_URL}/api/dashboard/today-schedule")
        assert response.status_code == 200
        data = response.json()
        
        # If there are appointments today, verify structure
        if len(data["appointments"]) > 0:
            apt = data["appointments"][0]
            assert "id" in apt
            assert "scheduled_at" in apt
            assert "status" in apt
            assert "client" in apt
            assert "barber" in apt
            assert "service" in apt
            # Verify nested objects have names
            assert "name" in apt["client"]
            assert "name" in apt["barber"]
            assert "name" in apt["service"]


class TestCreateAppointment:
    """Tests for creating appointments via POST /api/appointments"""
    
    def test_get_clients_for_appointment(self, authenticated_client):
        """GET /api/clients returns clients for appointment creation"""
        response = authenticated_client.get(f"{BASE_URL}/api/clients?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert "clients" in data
    
    def test_create_appointment_with_valid_data(self, authenticated_client):
        """POST /api/appointments creates a new appointment"""
        # Get existing barber and service
        barbers_response = authenticated_client.get(f"{BASE_URL}/api/barbers")
        services_response = authenticated_client.get(f"{BASE_URL}/api/services")
        clients_response = authenticated_client.get(f"{BASE_URL}/api/clients?limit=1")
        
        barbers = barbers_response.json()["barbers"]
        services = services_response.json()["services"]
        clients = clients_response.json()["clients"]
        
        if not barbers or not services or not clients:
            pytest.skip("Need existing barbers, services, and clients for this test")
        
        barber_id = barbers[0]["id"]
        service_id = services[0]["id"]
        client_id = clients[0]["id"]
        
        # Schedule for next week within business hours (1pm EST = 18:00 UTC)
        next_monday = datetime.now() + timedelta(days=(7 - datetime.now().weekday()))
        scheduled_at = next_monday.replace(hour=18, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        
        response = authenticated_client.post(f"{BASE_URL}/api/appointments", json={
            "client_id": client_id,
            "barber_id": barber_id,
            "service_id": service_id,
            "scheduled_at": scheduled_at,
            "notes": "TEST_CreateAppointment"
        })
        
        # May fail due to slot conflict, but should not return 500
        assert response.status_code in [200, 409], f"Unexpected error: {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            assert "id" in data
            assert data["client_id"] == client_id
            assert data["barber_id"] == barber_id
            assert data["service_id"] == service_id
    
    def test_create_appointment_missing_client(self, authenticated_client):
        """POST /api/appointments fails without client_id"""
        barbers_response = authenticated_client.get(f"{BASE_URL}/api/barbers")
        services_response = authenticated_client.get(f"{BASE_URL}/api/services")
        
        barbers = barbers_response.json()["barbers"]
        services = services_response.json()["services"]
        
        if not barbers or not services:
            pytest.skip("Need existing barbers and services for this test")
        
        response = authenticated_client.post(f"{BASE_URL}/api/appointments", json={
            "barber_id": barbers[0]["id"],
            "service_id": services[0]["id"],
            "scheduled_at": "2026-02-20T18:00:00+00:00"
        })
        assert response.status_code == 422  # Validation error
    
    def test_create_appointment_invalid_client(self, authenticated_client):
        """POST /api/appointments fails with nonexistent client"""
        barbers_response = authenticated_client.get(f"{BASE_URL}/api/barbers")
        services_response = authenticated_client.get(f"{BASE_URL}/api/services")
        
        barbers = barbers_response.json()["barbers"]
        services = services_response.json()["services"]
        
        if not barbers or not services:
            pytest.skip("Need existing barbers and services for this test")
        
        response = authenticated_client.post(f"{BASE_URL}/api/appointments", json={
            "client_id": "nonexistent-client-id",
            "barber_id": barbers[0]["id"],
            "service_id": services[0]["id"],
            "scheduled_at": "2026-02-20T18:00:00+00:00"
        })
        assert response.status_code == 404
    
    def test_create_appointment_outside_business_hours(self, authenticated_client):
        """POST /api/appointments fails for times outside business hours"""
        barbers_response = authenticated_client.get(f"{BASE_URL}/api/barbers")
        services_response = authenticated_client.get(f"{BASE_URL}/api/services")
        clients_response = authenticated_client.get(f"{BASE_URL}/api/clients?limit=1")
        
        barbers = barbers_response.json()["barbers"]
        services = services_response.json()["services"]
        clients = clients_response.json()["clients"]
        
        if not barbers or not services or not clients:
            pytest.skip("Need existing barbers, services, and clients for this test")
        
        # Try to book at 3 AM UTC (Sunday or late night)
        response = authenticated_client.post(f"{BASE_URL}/api/appointments", json={
            "client_id": clients[0]["id"],
            "barber_id": barbers[0]["id"],
            "service_id": services[0]["id"],
            "scheduled_at": "2026-02-15T03:00:00+00:00",  # Sunday 3 AM UTC
            "notes": "TEST_OutsideHours"
        })
        assert response.status_code == 409  # Conflict - outside hours


class TestAppointmentsListing:
    """Tests for existing appointments listing"""
    
    def test_list_appointments(self, authenticated_client):
        """GET /api/appointments returns appointments list"""
        response = authenticated_client.get(f"{BASE_URL}/api/appointments")
        assert response.status_code == 200
        data = response.json()
        assert "appointments" in data
        assert "total" in data
    
    def test_list_appointments_with_status_filter(self, authenticated_client):
        """GET /api/appointments with status filter works"""
        response = authenticated_client.get(f"{BASE_URL}/api/appointments?status=pending")
        assert response.status_code == 200
        data = response.json()
        assert "appointments" in data
        # All returned appointments should have pending status
        for apt in data["appointments"]:
            assert apt["status"] == "pending"
    
    def test_list_appointments_with_pagination(self, authenticated_client):
        """GET /api/appointments with limit and skip works"""
        response = authenticated_client.get(f"{BASE_URL}/api/appointments?limit=5&skip=0")
        assert response.status_code == 200
        data = response.json()
        assert "appointments" in data
        assert len(data["appointments"]) <= 5


class TestDashboardStats:
    """Tests for dashboard statistics"""
    
    def test_dashboard_stats(self, authenticated_client):
        """GET /api/dashboard/stats returns statistics"""
        response = authenticated_client.get(f"{BASE_URL}/api/dashboard/stats")
        assert response.status_code == 200
        data = response.json()
        assert "today_appointments" in data
        assert "no_show_rate" in data
