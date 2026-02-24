"""
Backend tests for Platform Overview Dashboard - GET /api/admin/platform-stats
Tests: Aggregate stats, per-shop breakdown, role-based access (super_admin only)
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
def test_shop_data(super_admin_client):
    """Create a test shop and return its data for verification. Used to test stats update."""
    unique_slug = f"stats-test-{uuid.uuid4().hex[:8]}"
    shop_data = {
        "name": "TEST_PlatformStatsShop",
        "slug": unique_slug,
        "phone": f"+1555{str(uuid.uuid4().int)[:7]}",
        "email": "stats-test@example.com",
        "address": "123 Stats Ave, Testing, TX 12345",
        "timezone": "America/New_York"
    }
    response = super_admin_client.post(f"{BASE_URL}/api/admin/shops", json=shop_data)
    assert response.status_code in [200, 201], f"Create test shop failed: {response.text}"
    shop = response.json()
    return shop


class TestPlatformStatsAuth:
    """Test that platform-stats endpoint requires super_admin role."""
    
    def test_platform_stats_requires_auth(self, api_session):
        """GET /api/admin/platform-stats without token returns 401."""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        response = session.get(f"{BASE_URL}/api/admin/platform-stats")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ GET /api/admin/platform-stats without auth returns 401")
    
    def test_platform_stats_shop_admin_forbidden(self, super_admin_client):
        """GET /api/admin/platform-stats with shop_admin token returns 403."""
        import time
        
        # Create a shop first
        unique_slug = f"access-test-{uuid.uuid4().hex[:8]}"
        shop_data = {
            "name": "TEST_AccessTestShop",
            "slug": unique_slug,
            "phone": f"+1555{str(uuid.uuid4().int)[:7]}",
            "email": "access-test@example.com",
            "timezone": "America/New_York"
        }
        shop_response = super_admin_client.post(f"{BASE_URL}/api/admin/shops", json=shop_data)
        assert shop_response.status_code in [200, 201]
        shop_id = shop_response.json()["id"]
        
        # Create a shop admin
        unique_username = f"stats_test_{uuid.uuid4().hex[:6]}"
        password = "StatsTest123!"
        admin_data = {
            "username": unique_username,
            "password": password
        }
        admin_response = super_admin_client.post(
            f"{BASE_URL}/api/admin/shops/{shop_id}/admins", 
            json=admin_data
        )
        assert admin_response.status_code in [200, 201]
        
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
        
        # Try to access platform-stats endpoint with shop_admin token
        shop_admin_session.headers.update({"Authorization": f"Bearer {token}"})
        stats_response = shop_admin_session.get(f"{BASE_URL}/api/admin/platform-stats")
        assert stats_response.status_code == 403, f"Expected 403 for shop_admin, got {stats_response.status_code}"
        print("✓ GET /api/admin/platform-stats with shop_admin returns 403")


class TestPlatformStatsResponse:
    """Tests for GET /api/admin/platform-stats response structure."""
    
    def test_platform_stats_returns_aggregate_stats(self, super_admin_client):
        """GET /api/admin/platform-stats returns all required aggregate fields."""
        response = super_admin_client.get(f"{BASE_URL}/api/admin/platform-stats")
        assert response.status_code == 200, f"Platform stats failed: {response.text}"
        
        data = response.json()
        
        # Verify all required aggregate fields exist
        required_fields = [
            "total_shops",
            "total_clients",
            "today_appointments",
            "month_appointments",
            "month_no_shows",
            "no_show_rate",
            "month_revenue",
            "shop_breakdown"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Verify data types
        assert isinstance(data["total_shops"], int)
        assert isinstance(data["total_clients"], int)
        assert isinstance(data["today_appointments"], int)
        assert isinstance(data["month_appointments"], int)
        assert isinstance(data["month_no_shows"], int)
        assert isinstance(data["no_show_rate"], (int, float))
        assert isinstance(data["month_revenue"], (int, float))
        assert isinstance(data["shop_breakdown"], list)
        
        # Verify values are non-negative
        assert data["total_shops"] >= 0
        assert data["total_clients"] >= 0
        assert data["no_show_rate"] >= 0
        assert data["no_show_rate"] <= 100  # Percentage should be 0-100
        assert data["month_revenue"] >= 0
        
        print(f"✓ GET /api/admin/platform-stats returns all aggregate fields")
        print(f"  - total_shops: {data['total_shops']}")
        print(f"  - total_clients: {data['total_clients']}")
        print(f"  - month_appointments: {data['month_appointments']}")
        print(f"  - no_show_rate: {data['no_show_rate']}%")
        print(f"  - month_revenue: ${data['month_revenue']}")
    
    def test_platform_stats_shop_breakdown_structure(self, super_admin_client):
        """GET /api/admin/platform-stats shop_breakdown has correct structure per shop."""
        response = super_admin_client.get(f"{BASE_URL}/api/admin/platform-stats")
        assert response.status_code == 200
        
        data = response.json()
        shop_breakdown = data["shop_breakdown"]
        
        # Should have at least one shop (Urban Cuts Barbershop or test shop)
        assert len(shop_breakdown) >= 1, "Expected at least one shop in breakdown"
        
        # Check structure of each shop entry
        for shop in shop_breakdown:
            required_shop_fields = [
                "id",
                "name",
                "slug",
                "month_appointments",
                "month_no_shows",
                "no_show_rate",
                "total_clients",
                "month_revenue"
            ]
            
            for field in required_shop_fields:
                assert field in shop, f"Shop missing field: {field}"
            
            # Verify data types
            assert isinstance(shop["id"], str)
            assert isinstance(shop["name"], str)
            assert isinstance(shop["slug"], str)
            assert isinstance(shop["month_appointments"], int)
            assert isinstance(shop["month_no_shows"], int)
            assert isinstance(shop["no_show_rate"], (int, float))
            assert isinstance(shop["total_clients"], int)
            assert isinstance(shop["month_revenue"], (int, float))
            
            # Verify values are non-negative
            assert shop["month_appointments"] >= 0
            assert shop["month_no_shows"] >= 0
            assert shop["no_show_rate"] >= 0
            assert shop["total_clients"] >= 0
            assert shop["month_revenue"] >= 0
        
        print(f"✓ shop_breakdown contains {len(shop_breakdown)} shops with correct structure")
        for s in shop_breakdown:
            print(f"  - {s['name']} (/{s['slug']}): {s['month_appointments']} apts, ${s['month_revenue']} revenue")
    
    def test_platform_stats_shop_count_matches_list(self, super_admin_client):
        """total_shops in platform-stats should match GET /api/admin/shops count."""
        stats_response = super_admin_client.get(f"{BASE_URL}/api/admin/platform-stats")
        assert stats_response.status_code == 200
        
        shops_response = super_admin_client.get(f"{BASE_URL}/api/admin/shops")
        assert shops_response.status_code == 200
        
        stats_total = stats_response.json()["total_shops"]
        shops_list_count = len(shops_response.json()["shops"])
        
        assert stats_total == shops_list_count, f"total_shops ({stats_total}) != shops list count ({shops_list_count})"
        print(f"✓ total_shops ({stats_total}) matches /api/admin/shops count ({shops_list_count})")


class TestPlatformStatsAfterShopCreation:
    """Test that stats update after creating a new shop."""
    
    def test_stats_update_after_new_shop(self, super_admin_client):
        """Platform stats should reflect a newly created shop."""
        # Get stats before
        before_response = super_admin_client.get(f"{BASE_URL}/api/admin/platform-stats")
        assert before_response.status_code == 200
        before_count = before_response.json()["total_shops"]
        before_breakdown_count = len(before_response.json()["shop_breakdown"])
        
        # Create a new shop
        unique_slug = f"stats-update-{uuid.uuid4().hex[:8]}"
        shop_data = {
            "name": "TEST_StatsUpdateShop",
            "slug": unique_slug,
            "phone": f"+1555{str(uuid.uuid4().int)[:7]}",
            "email": "stats-update@example.com",
            "timezone": "America/New_York"
        }
        create_response = super_admin_client.post(f"{BASE_URL}/api/admin/shops", json=shop_data)
        assert create_response.status_code in [200, 201], f"Create shop failed: {create_response.text}"
        new_shop_id = create_response.json()["id"]
        
        # Get stats after
        after_response = super_admin_client.get(f"{BASE_URL}/api/admin/platform-stats")
        assert after_response.status_code == 200
        after_count = after_response.json()["total_shops"]
        after_breakdown_count = len(after_response.json()["shop_breakdown"])
        
        # Verify count increased
        assert after_count == before_count + 1, f"total_shops should increase by 1 (was {before_count}, now {after_count})"
        assert after_breakdown_count == before_breakdown_count + 1, f"shop_breakdown should have 1 more entry"
        
        # Verify new shop is in breakdown
        after_breakdown = after_response.json()["shop_breakdown"]
        new_shop_in_breakdown = any(s["id"] == new_shop_id for s in after_breakdown)
        assert new_shop_in_breakdown, f"New shop {new_shop_id} should be in shop_breakdown"
        
        print(f"✓ Stats updated after new shop creation: {before_count} → {after_count} shops")
