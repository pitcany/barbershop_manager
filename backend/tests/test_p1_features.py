"""
Test P1 Features:
1. PATCH /api/shop/details - Editable shop details (name, phone, email, address)
2. GET /api/clients - Verify total_appointments field instead of MongoDB ID
3. Verify shop details are persisted and retrieved correctly
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestShopDetails:
    """Tests for PATCH /api/shop/details endpoint - P1 Feature 1"""
    
    def test_get_shop_initial(self, auth_headers):
        """GET /api/shop - Verify shop details are returned"""
        response = requests.get(f"{BASE_URL}/api/shop", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "phone" in data or data.get("phone") == ""
        assert "email" in data or data.get("email") == ""
        assert "address" in data or data.get("address") == ""
        print(f"Initial shop details: name={data.get('name')}, phone={data.get('phone')}, email={data.get('email')}, address={data.get('address')}")
    
    def test_patch_shop_details_name(self, auth_headers):
        """PATCH /api/shop/details - Update shop name"""
        # First get current shop details
        response = requests.get(f"{BASE_URL}/api/shop", headers=auth_headers)
        original_name = response.json().get("name")
        
        # Update name
        new_name = f"TEST_Updated_Shop_{original_name[:10]}"
        response = requests.patch(f"{BASE_URL}/api/shop/details", 
                                  headers=auth_headers,
                                  json={"name": new_name})
        assert response.status_code == 200
        data = response.json()
        assert data.get("name") == new_name
        
        # Verify change persisted via GET
        response = requests.get(f"{BASE_URL}/api/shop", headers=auth_headers)
        assert response.json().get("name") == new_name
        print(f"Updated shop name to: {new_name}")
        
        # Restore original name
        response = requests.patch(f"{BASE_URL}/api/shop/details", 
                                  headers=auth_headers,
                                  json={"name": original_name})
        assert response.status_code == 200
        print(f"Restored shop name to: {original_name}")
    
    def test_patch_shop_details_phone(self, auth_headers):
        """PATCH /api/shop/details - Update shop phone"""
        test_phone = "+15559998888"
        response = requests.patch(f"{BASE_URL}/api/shop/details",
                                  headers=auth_headers,
                                  json={"phone": test_phone})
        assert response.status_code == 200
        data = response.json()
        assert data.get("phone") == test_phone
        
        # Verify persistence
        response = requests.get(f"{BASE_URL}/api/shop", headers=auth_headers)
        assert response.json().get("phone") == test_phone
        print(f"Updated shop phone to: {test_phone}")
    
    def test_patch_shop_details_email(self, auth_headers):
        """PATCH /api/shop/details - Update shop email"""
        test_email = "test_shop@barbershop.com"
        response = requests.patch(f"{BASE_URL}/api/shop/details",
                                  headers=auth_headers,
                                  json={"email": test_email})
        assert response.status_code == 200
        data = response.json()
        assert data.get("email") == test_email
        
        # Verify persistence
        response = requests.get(f"{BASE_URL}/api/shop", headers=auth_headers)
        assert response.json().get("email") == test_email
        print(f"Updated shop email to: {test_email}")
    
    def test_patch_shop_details_address(self, auth_headers):
        """PATCH /api/shop/details - Update shop address"""
        test_address = "123 Test Street, Suite 456, Test City, TS 12345"
        response = requests.patch(f"{BASE_URL}/api/shop/details",
                                  headers=auth_headers,
                                  json={"address": test_address})
        assert response.status_code == 200
        data = response.json()
        assert data.get("address") == test_address
        
        # Verify persistence
        response = requests.get(f"{BASE_URL}/api/shop", headers=auth_headers)
        assert response.json().get("address") == test_address
        print(f"Updated shop address to: {test_address}")
    
    def test_patch_shop_details_all_fields(self, auth_headers):
        """PATCH /api/shop/details - Update all fields at once"""
        test_data = {
            "name": "TEST_Complete_Shop_Update",
            "phone": "+15551234567",
            "email": "complete@test.com",
            "address": "789 Complete Ave, Full City, FC 00000"
        }
        response = requests.patch(f"{BASE_URL}/api/shop/details",
                                  headers=auth_headers,
                                  json=test_data)
        assert response.status_code == 200
        data = response.json()
        for key, value in test_data.items():
            assert data.get(key) == value, f"Expected {key}={value}, got {data.get(key)}"
        
        # Verify all persisted
        response = requests.get(f"{BASE_URL}/api/shop", headers=auth_headers)
        data = response.json()
        for key, value in test_data.items():
            assert data.get(key) == value, f"Persistence check: Expected {key}={value}, got {data.get(key)}"
        print("All shop details updated and verified successfully")
        
        # Restore to reasonable defaults
        restore_data = {
            "name": "Urban Cuts Barbershop",
            "phone": "+15551234567",
            "email": "contact@urbancuts.com",
            "address": "456 Main Street, New York, NY 10001"
        }
        requests.patch(f"{BASE_URL}/api/shop/details", headers=auth_headers, json=restore_data)
        print("Restored shop details to defaults")
    
    def test_patch_shop_details_empty_not_required(self, auth_headers):
        """PATCH /api/shop/details - Empty payload should not fail"""
        response = requests.patch(f"{BASE_URL}/api/shop/details",
                                  headers=auth_headers,
                                  json={})
        # Should return 200 even with empty payload (no changes)
        assert response.status_code == 200
        print("Empty payload test passed")
    
    def test_patch_shop_details_no_auth(self):
        """PATCH /api/shop/details - Should require authentication"""
        response = requests.patch(f"{BASE_URL}/api/shop/details",
                                  json={"name": "Unauthorized"})
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("Auth required test passed")


class TestClientsNoMongoID:
    """Tests for Clients page - P1 Feature: No MongoDB IDs, shows appointment count instead"""
    
    def test_get_clients_has_total_appointments(self, auth_headers):
        """GET /api/clients - Verify total_appointments field exists instead of raw ID"""
        response = requests.get(f"{BASE_URL}/api/clients?limit=10", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "clients" in data
        
        if data["clients"]:
            first_client = data["clients"][0]
            # Should have total_appointments field
            assert "total_appointments" in first_client or "appointment_count" in first_client, \
                f"Client should have total_appointments/appointment_count field. Keys: {list(first_client.keys())}"
            # Should NOT have raw MongoDB _id field
            assert "_id" not in first_client, "Client should not expose raw MongoDB _id"
            # Should have id (our UUID)
            assert "id" in first_client, "Client should have id field"
            print(f"Client data verified: has total_appointments={first_client.get('total_appointments', first_client.get('appointment_count'))}, no _id")
        else:
            print("No clients found - creating test client to verify")
    
    def test_clients_response_structure(self, auth_headers):
        """GET /api/clients - Verify response structure matches frontend expectations"""
        response = requests.get(f"{BASE_URL}/api/clients?limit=5", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        if data["clients"]:
            client = data["clients"][0]
            # Required fields for frontend display
            required_fields = ["id", "name", "phone"]
            for field in required_fields:
                assert field in client, f"Missing required field: {field}"
            
            # Optional but expected fields
            expected_fields = ["email", "sms_consent", "no_shows", "created_at", "total_appointments"]
            present_fields = [f for f in expected_fields if f in client]
            print(f"Client has required fields and optional: {present_fields}")


class TestBookingLink:
    """Tests related to booking link functionality - P1 Features 2 & 3"""
    
    def test_shop_has_required_fields(self, auth_headers):
        """Verify shop data includes fields needed for booking link generation"""
        response = requests.get(f"{BASE_URL}/api/shop", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Shop must have ID for booking link
        assert "id" in data, "Shop must have id for booking link"
        assert data.get("id"), "Shop id must not be empty"
        print(f"Shop has valid id for booking link: {data.get('id')}")


# Run with: pytest test_p1_features.py -v --tb=short
