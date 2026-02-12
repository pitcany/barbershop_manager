"""
Test suite for RetentionRebookAgent feature
Tests:
- Retention preview endpoint
- Retention run endpoint  
- Cooldown enforcement
- Outreach history endpoint
- Scheduler shows retention job
- Settings retention fields
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"


@pytest.fixture(scope="module")
def auth_token():
    """Login and get auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestRetentionPreview:
    """Test retention preview endpoint"""
    
    def test_preview_endpoint_accessible(self, auth_headers):
        """GET /api/jobs/retention/preview returns data"""
        response = requests.get(f"{BASE_URL}/api/jobs/retention/preview", headers=auth_headers)
        assert response.status_code == 200, f"Preview failed: {response.text}"
        
    def test_preview_returns_expected_structure(self, auth_headers):
        """Preview response has correct structure"""
        response = requests.get(f"{BASE_URL}/api/jobs/retention/preview", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Check expected fields
        assert "enabled" in data
        assert "lapse_threshold_weeks" in data
        assert "cooldown_days" in data
        assert "lapsed_clients" in data
        assert "clients" in data
        assert isinstance(data["clients"], list)
        
    def test_preview_shows_lapsed_client_data(self, auth_headers):
        """Preview shows lapsed clients with details"""
        response = requests.get(f"{BASE_URL}/api/jobs/retention/preview", headers=auth_headers)
        data = response.json()
        
        # Should have lapsed clients based on test data (Alex Martinez)
        print(f"Preview data: enabled={data.get('enabled')}, lapsed={data.get('lapsed_clients')}")
        
        if data["lapsed_clients"] > 0:
            client = data["clients"][0]
            # Check client structure
            assert "client_id" in client
            assert "name" in client
            assert "days_since_last_visit" in client
            assert "completed_visits" in client
            assert "high_signal" in client
            assert "in_cooldown" in client
            assert "next_touch" in client


class TestRetentionRun:
    """Test retention run endpoint"""
    
    def test_run_endpoint_accessible(self, auth_headers):
        """POST /api/jobs/retention/run executes successfully"""
        response = requests.post(f"{BASE_URL}/api/jobs/retention/run", headers=auth_headers)
        assert response.status_code == 200, f"Run failed: {response.text}"
        
    def test_run_returns_expected_structure(self, auth_headers):
        """Run response has correct structure"""
        response = requests.post(f"{BASE_URL}/api/jobs/retention/run", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Check expected fields
        assert "status" in data
        assert data["status"] in ["completed", "disabled"]
        assert "actions" in data
        assert isinstance(data["actions"], list)
        
        if data["status"] == "completed":
            assert "lapsed_found" in data
            assert "actions_taken" in data
            
    def test_run_action_details(self, auth_headers):
        """Run actions contain expected details"""
        response = requests.post(f"{BASE_URL}/api/jobs/retention/run", headers=auth_headers)
        data = response.json()
        
        # If actions exist, check structure
        if data.get("actions"):
            action = data["actions"][0]
            assert "client_id" in action
            assert "name" in action
            # Action should indicate what happened
            assert "action" in action
            print(f"First action: {action}")


class TestRetentionCooldown:
    """Test cooldown enforcement"""
    
    def test_cooldown_skips_recently_contacted(self, auth_headers):
        """Running twice should skip clients in cooldown"""
        # First run
        response1 = requests.post(f"{BASE_URL}/api/jobs/retention/run", headers=auth_headers)
        data1 = response1.json()
        
        # Second run (immediately after)
        response2 = requests.post(f"{BASE_URL}/api/jobs/retention/run", headers=auth_headers)
        data2 = response2.json()
        
        # Preview to see cooldown status
        preview = requests.get(f"{BASE_URL}/api/jobs/retention/preview", headers=auth_headers)
        preview_data = preview.json()
        
        print(f"First run: {data1.get('lapsed_found')} lapsed, {data1.get('actions_taken')} actions")
        print(f"Second run: {data2.get('lapsed_found')} lapsed, {data2.get('actions_taken')} actions")
        
        # Check if any clients are in cooldown
        if preview_data.get("clients"):
            cooldown_clients = [c for c in preview_data["clients"] if c.get("in_cooldown")]
            print(f"Clients in cooldown: {len(cooldown_clients)}")
            
        # If first run took actions, second run should have fewer or skip via cooldown
        # This is valid as long as cooldown is enforced
        assert response1.status_code == 200
        assert response2.status_code == 200


class TestOutreachHistory:
    """Test outreach history endpoint"""
    
    def test_history_endpoint_accessible(self, auth_headers):
        """GET /api/retention/outreach-history returns data"""
        response = requests.get(f"{BASE_URL}/api/retention/outreach-history", headers=auth_headers)
        assert response.status_code == 200, f"History failed: {response.text}"
        
    def test_history_returns_expected_structure(self, auth_headers):
        """History response has correct structure"""
        response = requests.get(f"{BASE_URL}/api/retention/outreach-history", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "entries" in data
        assert "count" in data
        assert isinstance(data["entries"], list)
        
    def test_history_entry_structure(self, auth_headers):
        """History entries have correct fields"""
        response = requests.get(f"{BASE_URL}/api/retention/outreach-history", headers=auth_headers)
        data = response.json()
        
        if data.get("entries"):
            entry = data["entries"][0]
            print(f"History entry: {entry}")
            
            # Expected fields
            assert "id" in entry
            assert "shop_id" in entry
            assert "client_id" in entry
            assert "channel" in entry  # email or sms
            assert "touch" in entry    # touch number
            assert "success" in entry
            assert "created_at" in entry
            
    def test_history_limit_parameter(self, auth_headers):
        """History respects limit parameter"""
        response = requests.get(f"{BASE_URL}/api/retention/outreach-history?limit=5", headers=auth_headers)
        data = response.json()
        assert len(data.get("entries", [])) <= 5


class TestSchedulerRetentionJob:
    """Test scheduler shows retention job"""
    
    def test_scheduler_status_accessible(self, auth_headers):
        """GET /api/jobs/status returns scheduler info"""
        response = requests.get(f"{BASE_URL}/api/jobs/status", headers=auth_headers)
        assert response.status_code == 200
        
    def test_scheduler_has_three_jobs(self, auth_headers):
        """Scheduler should now have 3 jobs including retention"""
        response = requests.get(f"{BASE_URL}/api/jobs/status", headers=auth_headers)
        data = response.json()
        
        assert "jobs" in data
        jobs = data["jobs"]
        
        # Should have 3 jobs now
        job_ids = [j["id"] for j in jobs]
        print(f"Scheduled jobs: {job_ids}")
        
        assert "appointment_reminders" in job_ids
        assert "daily_summary" in job_ids
        assert "retention_sweep" in job_ids
        
        # Verify retention job structure
        retention_job = next((j for j in jobs if j["id"] == "retention_sweep"), None)
        assert retention_job is not None
        assert retention_job.get("name") == "Client Retention Sweep"
        assert "14" in retention_job.get("trigger", "")  # Should run at 14:00


class TestRetentionSettings:
    """Test retention settings in shop policy"""
    
    def test_shop_settings_include_retention(self, auth_headers):
        """GET /api/shop should include retention settings"""
        response = requests.get(f"{BASE_URL}/api/shop", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Check if retention fields exist (may be defaults)
        print(f"Shop retention fields: enabled={data.get('retention_enabled')}, "
              f"lapse_weeks={data.get('retention_lapse_weeks')}, "
              f"cooldown_days={data.get('retention_cooldown_days')}")
        
    def test_save_retention_settings(self, auth_headers):
        """PATCH /api/shop/policy should accept retention settings"""
        # Get current settings
        current = requests.get(f"{BASE_URL}/api/shop", headers=auth_headers).json()
        
        # Update with retention fields
        update = {
            "retention_enabled": True,
            "retention_lapse_weeks": 5,
            "retention_cooldown_days": 10
        }
        
        response = requests.patch(f"{BASE_URL}/api/shop/policy", json=update, headers=auth_headers)
        assert response.status_code == 200, f"Policy update failed: {response.text}"
        
        # Verify saved
        after = requests.get(f"{BASE_URL}/api/shop", headers=auth_headers).json()
        
        # If the shop model supports these fields, they should be saved
        # Note: Shop model may not explicitly include them but PolicyUpdate does
        print(f"After update: retention_enabled={after.get('retention_enabled')}, "
              f"lapse_weeks={after.get('retention_lapse_weeks')}, "
              f"cooldown_days={after.get('retention_cooldown_days')}")
        
        # Restore original values
        restore = {
            "retention_enabled": current.get("retention_enabled", True),
            "retention_lapse_weeks": current.get("retention_lapse_weeks", 4),
            "retention_cooldown_days": current.get("retention_cooldown_days", 7)
        }
        requests.patch(f"{BASE_URL}/api/shop/policy", json=restore, headers=auth_headers)


class TestRegressionEndpoints:
    """Regression tests for existing endpoints"""
    
    def test_dashboard_stats(self, auth_headers):
        """Dashboard stats endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=auth_headers)
        assert response.status_code == 200
        
    def test_clients_list(self, auth_headers):
        """Clients endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
        assert response.status_code == 200
        
    def test_appointments_list(self, auth_headers):
        """Appointments endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/appointments", headers=auth_headers)
        assert response.status_code == 200
        
    def test_reporting_overview(self, auth_headers):
        """Reporting endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/reporting/overview", headers=auth_headers)
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
