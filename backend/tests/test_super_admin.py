"""
Backend tests for Super Admin shop management features.
Tests: GET/POST /api/admin/shops, GET/POST /api/admin/shops/{shop_id}/admins, 403 for non-super_admin
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


@pytest.fixture(scope="module")
def api_session():
    """Shared requests session."""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def super_admin_token(api_session):
    """Get auth token for super_admin (admin/admin123)."""
    response = api_session.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    assert response.status_code == 200, f"Super admin login failed: {response.text}"
    return response.json().get("access_token")


@pytest.fixture(scope="module")
def super_admin_client(api_session, super_admin_token):
    """Session with super_admin auth header."""
    api_session.headers.update({"Authorization": f"Bearer {super_admin_token}"})
    return api_session


@pytest.fixture(scope="module")
def test_shop_id(super_admin_client):
    """Create a test shop and return its ID for other tests. Cleanup after."""
    unique_slug = f"test-shop-{uuid.uuid4().hex[:8]}"
    shop_data = {
        "name": "TEST_SuperAdminShop",
        "slug": unique_slug,
        "phone": f"+1555{str(uuid.uuid4().int)[:7]}",
        "email": "test@superadminshop.com",
        "address": "123 Test St, Testing, TX 12345",
        "timezone": "America/New_York"
    }
    response = super_admin_client.post(f"{BASE_URL}/api/admin/shops", json=shop_data)
    assert response.status_code == 200 or response.status_code == 201, f"Create test shop failed: {response.text}"
    shop = response.json()
    shop_id = shop.get("id")
    yield shop_id
    # Cleanup: no delete endpoint yet, so we just leave it


class TestSuperAdminAuth:
    """Test that admin endpoints require super_admin role."""
    
    def test_list_shops_requires_auth(self, api_session):
        """GET /api/admin/shops without token returns 401."""
        # Remove auth header
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        response = session.get(f"{BASE_URL}/api/admin/shops")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ GET /api/admin/shops without auth returns 401")
    
    def test_create_shop_requires_auth(self, api_session):
        """POST /api/admin/shops without token returns 401."""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        response = session.post(f"{BASE_URL}/api/admin/shops", json={
            "name": "Unauthorized Shop",
            "slug": "unauth-shop",
            "phone": "+15551111111"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ POST /api/admin/shops without auth returns 401")


class TestListShops:
    """Tests for GET /api/admin/shops."""
    
    def test_list_shops_success(self, super_admin_client):
        """GET /api/admin/shops returns list of shops with admin_count."""
        response = super_admin_client.get(f"{BASE_URL}/api/admin/shops")
        assert response.status_code == 200, f"List shops failed: {response.text}"
        data = response.json()
        assert "shops" in data
        assert isinstance(data["shops"], list)
        
        # If there are shops, check structure
        if len(data["shops"]) > 0:
            shop = data["shops"][0]
            assert "id" in shop
            assert "name" in shop
            # Note: slug might be missing on old shops created before feature
            assert "phone" in shop
            assert "admin_count" in shop
        
        print(f"✓ GET /api/admin/shops returns {len(data['shops'])} shops")


class TestCreateShop:
    """Tests for POST /api/admin/shops."""
    
    def test_create_shop_success(self, super_admin_client):
        """POST /api/admin/shops creates a new shop."""
        unique_slug = f"new-shop-{uuid.uuid4().hex[:8]}"
        shop_data = {
            "name": "TEST_NewCreatedShop",
            "slug": unique_slug,
            "phone": f"+1555{str(uuid.uuid4().int)[:7]}",
            "email": "newshop@test.com",
            "address": "456 New St, City, ST 67890",
            "timezone": "America/Chicago"
        }
        response = super_admin_client.post(f"{BASE_URL}/api/admin/shops", json=shop_data)
        assert response.status_code == 200 or response.status_code == 201, f"Create shop failed: {response.text}"
        
        shop = response.json()
        assert shop["name"] == shop_data["name"]
        assert shop["slug"] == unique_slug
        assert shop["email"] == shop_data["email"]
        assert shop["address"] == shop_data["address"]
        assert shop["timezone"] == shop_data["timezone"]
        assert "id" in shop
        print(f"✓ POST /api/admin/shops created shop: {shop['id']}")
    
    def test_create_shop_invalid_slug(self, super_admin_client):
        """POST /api/admin/shops with invalid slug returns 422."""
        shop_data = {
            "name": "Invalid Slug Shop",
            "slug": "ab",  # Too short (min 3 chars)
            "phone": "+15552222222"
        }
        response = super_admin_client.post(f"{BASE_URL}/api/admin/shops", json=shop_data)
        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"
        print("✓ POST /api/admin/shops with invalid slug returns 422")
    
    def test_create_shop_invalid_phone(self, super_admin_client):
        """POST /api/admin/shops with invalid phone returns 422."""
        shop_data = {
            "name": "Invalid Phone Shop",
            "slug": "invalid-phone-shop-v2",
            "phone": "abc"  # Completely invalid, not enough digits
        }
        response = super_admin_client.post(f"{BASE_URL}/api/admin/shops", json=shop_data)
        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"
        print("✓ POST /api/admin/shops with invalid phone returns 422")
    
    def test_create_shop_duplicate_slug(self, super_admin_client, test_shop_id):
        """POST /api/admin/shops with duplicate slug returns 409."""
        # First get the test shop to know its slug
        response = super_admin_client.get(f"{BASE_URL}/api/admin/shops")
        shops = response.json()["shops"]
        test_shop = next((s for s in shops if s["id"] == test_shop_id), None)
        
        if test_shop:
            shop_data = {
                "name": "Duplicate Slug Shop",
                "slug": test_shop["slug"],  # Use existing slug
                "phone": "+15553333333"
            }
            response = super_admin_client.post(f"{BASE_URL}/api/admin/shops", json=shop_data)
            assert response.status_code == 409, f"Expected 409, got {response.status_code}: {response.text}"
            print("✓ POST /api/admin/shops with duplicate slug returns 409")
        else:
            pytest.skip("Test shop not found")
    
    def test_create_shop_missing_required_fields(self, super_admin_client):
        """POST /api/admin/shops without required fields returns 422."""
        # Missing slug
        response = super_admin_client.post(f"{BASE_URL}/api/admin/shops", json={
            "name": "No Slug Shop",
            "phone": "+15554444444"
        })
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("✓ POST /api/admin/shops without slug returns 422")


class TestCreateShopAdmin:
    """Tests for POST /api/admin/shops/{shop_id}/admins."""
    
    def test_create_admin_success(self, super_admin_client, test_shop_id):
        """POST /api/admin/shops/{shop_id}/admins creates a new admin."""
        unique_username = f"test_admin_{uuid.uuid4().hex[:8]}"
        admin_data = {
            "username": unique_username,
            "password": "SecurePass123!"
        }
        response = super_admin_client.post(
            f"{BASE_URL}/api/admin/shops/{test_shop_id}/admins", 
            json=admin_data
        )
        assert response.status_code == 200 or response.status_code == 201, f"Create admin failed: {response.text}"
        
        admin = response.json()
        assert admin["username"] == unique_username
        assert admin["role"] == "shop_admin"
        assert admin["shop_id"] == test_shop_id
        assert "id" in admin
        assert "password_hash" not in admin  # Should not expose hash
        print(f"✓ POST /api/admin/shops/{test_shop_id}/admins created admin: {admin['id']}")
        
        return unique_username, "SecurePass123!"
    
    def test_create_admin_for_nonexistent_shop(self, super_admin_client):
        """POST /api/admin/shops/{invalid_id}/admins returns 404."""
        fake_shop_id = str(uuid.uuid4())
        admin_data = {
            "username": "admin_for_nowhere",
            "password": "SecurePass123!"
        }
        response = super_admin_client.post(
            f"{BASE_URL}/api/admin/shops/{fake_shop_id}/admins", 
            json=admin_data
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ POST /api/admin/shops/{invalid_id}/admins returns 404")
    
    def test_create_admin_password_too_short(self, super_admin_client, test_shop_id):
        """POST /api/admin/shops/{shop_id}/admins with short password returns 422."""
        admin_data = {
            "username": "short_pass_admin",
            "password": "short"  # Less than 8 chars
        }
        response = super_admin_client.post(
            f"{BASE_URL}/api/admin/shops/{test_shop_id}/admins", 
            json=admin_data
        )
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("✓ POST /api/admin/shops/{shop_id}/admins with short password returns 422")
    
    def test_create_admin_duplicate_username(self, super_admin_client, test_shop_id):
        """POST /api/admin/shops/{shop_id}/admins with duplicate username returns 409."""
        # Create first admin
        unique_username = f"dup_admin_{uuid.uuid4().hex[:8]}"
        admin_data = {
            "username": unique_username,
            "password": "SecurePass123!"
        }
        response1 = super_admin_client.post(
            f"{BASE_URL}/api/admin/shops/{test_shop_id}/admins", 
            json=admin_data
        )
        assert response1.status_code in [200, 201]
        
        # Try to create another admin with same username
        response2 = super_admin_client.post(
            f"{BASE_URL}/api/admin/shops/{test_shop_id}/admins", 
            json=admin_data
        )
        assert response2.status_code == 409, f"Expected 409, got {response2.status_code}"
        print("✓ POST /api/admin/shops/{shop_id}/admins with duplicate username returns 409")


class TestListShopAdmins:
    """Tests for GET /api/admin/shops/{shop_id}/admins."""
    
    def test_list_admins_success(self, super_admin_client, test_shop_id):
        """GET /api/admin/shops/{shop_id}/admins returns list of admins."""
        response = super_admin_client.get(f"{BASE_URL}/api/admin/shops/{test_shop_id}/admins")
        assert response.status_code == 200, f"List admins failed: {response.text}"
        
        data = response.json()
        assert "admins" in data
        assert isinstance(data["admins"], list)
        
        # Check structure if admins exist
        if len(data["admins"]) > 0:
            admin = data["admins"][0]
            assert "id" in admin
            assert "username" in admin
            assert "role" in admin
            assert "shop_id" in admin
            assert "password_hash" not in admin  # Should not expose hash
        
        print(f"✓ GET /api/admin/shops/{test_shop_id}/admins returns {len(data['admins'])} admins")
    
    def test_list_admins_nonexistent_shop(self, super_admin_client):
        """GET /api/admin/shops/{invalid_id}/admins returns 404."""
        fake_shop_id = str(uuid.uuid4())
        response = super_admin_client.get(f"{BASE_URL}/api/admin/shops/{fake_shop_id}/admins")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ GET /api/admin/shops/{invalid_id}/admins returns 404")


class TestNewAdminLogin:
    """Test that newly created shop admin can log in."""
    
    def test_new_admin_can_login(self, super_admin_client, test_shop_id, api_session):
        """A newly created shop admin should be able to log in."""
        import time
        time.sleep(2)  # Wait to avoid rate limit
        
        # Create a new admin
        unique_username = f"login_test_{uuid.uuid4().hex[:8]}"
        password = "LoginTest123!"
        admin_data = {
            "username": unique_username,
            "password": password
        }
        response = super_admin_client.post(
            f"{BASE_URL}/api/admin/shops/{test_shop_id}/admins", 
            json=admin_data
        )
        assert response.status_code in [200, 201], f"Failed to create test admin: {response.text}"
        
        # Now try logging in with the new admin
        login_session = requests.Session()
        login_session.headers.update({"Content-Type": "application/json"})
        login_response = login_session.post(f"{BASE_URL}/api/auth/login", json={
            "username": unique_username,
            "password": password
        })
        
        if login_response.status_code == 429:
            pytest.skip("Rate limited, skipping login test")
        
        assert login_response.status_code == 200, f"New admin login failed: {login_response.text}"
        
        token_data = login_response.json()
        assert "access_token" in token_data
        print(f"✓ Newly created admin '{unique_username}' can log in successfully")


class TestShopAdminAccessRestriction:
    """Test that shop_admin cannot access super_admin endpoints."""
    
    def test_shop_admin_cannot_access_admin_endpoints(self, super_admin_client, test_shop_id):
        """A shop_admin should get 403 when trying to access /api/admin/* endpoints."""
        import time
        # Small delay to avoid rate limits
        time.sleep(1)
        
        # Create a shop admin
        unique_username = f"restricted_{uuid.uuid4().hex[:6]}"
        password = "RestrictedPass123!"
        admin_data = {
            "username": unique_username,
            "password": password
        }
        response = super_admin_client.post(
            f"{BASE_URL}/api/admin/shops/{test_shop_id}/admins", 
            json=admin_data
        )
        assert response.status_code in [200, 201]
        
        # Login as shop admin
        time.sleep(1)  # Avoid rate limit
        shop_admin_session = requests.Session()
        shop_admin_session.headers.update({"Content-Type": "application/json"})
        login_response = shop_admin_session.post(f"{BASE_URL}/api/auth/login", json={
            "username": unique_username,
            "password": password
        })
        if login_response.status_code == 429:
            pytest.skip("Rate limited, skipping this test")
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        token = login_response.json()["access_token"]
        
        # Try to access admin endpoints
        shop_admin_session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Try GET /api/admin/shops
        restricted_response = shop_admin_session.get(f"{BASE_URL}/api/admin/shops")
        assert restricted_response.status_code == 403, f"Expected 403, got {restricted_response.status_code}"
        print("✓ shop_admin gets 403 when accessing GET /api/admin/shops")
        
        # Try POST /api/admin/shops
        shop_data = {
            "name": "Unauthorized Shop",
            "slug": f"unauth-{uuid.uuid4().hex[:6]}",
            "phone": "+15559999999"
        }
        restricted_response2 = shop_admin_session.post(f"{BASE_URL}/api/admin/shops", json=shop_data)
        assert restricted_response2.status_code == 403, f"Expected 403, got {restricted_response2.status_code}"
        print("✓ shop_admin gets 403 when trying to POST /api/admin/shops")
