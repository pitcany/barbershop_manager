"""
Test suite for APScheduler and OwnerOpsAgent features
Tests the background job system, scheduler status, and daily summary generation.

Features tested:
1. APScheduler started on backend startup
2. Appointment reminders endpoints
3. Daily summary preview/run
4. OwnerOpsAgent stats compilation
5. Scheduler status
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestAuth:
    """Authentication helper tests"""

    @pytest.fixture
    def auth_token(self):
        """Get auth token for testing"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["access_token"]

    def test_login_works(self):
        """Verify login still works with admin/admin123"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["access_token"] is not None


class TestSchedulerStatus:
    """Tests for APScheduler status endpoint"""

    @pytest.fixture
    def auth_token(self):
        """Get auth token for testing"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        return response.json()["access_token"]

    def test_scheduler_status_returns_running(self, auth_token):
        """GET /api/jobs/status returns scheduler mode with jobs list and recent_runs"""
        response = requests.get(
            f"{BASE_URL}/api/jobs/status",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()

        # scheduler_mode is one of the two supported modes
        assert data["scheduler_mode"] in ("apscheduler", "celery")

        # Both modes return jobs list and recent_runs
        assert "jobs" in data
        assert isinstance(data["jobs"], list)
        assert "recent_runs" in data
        assert isinstance(data["recent_runs"], list)

    def test_scheduler_has_both_jobs(self, auth_token):
        """In APScheduler mode, both appointment_reminders and daily_summary jobs exist.
        In Celery mode, jobs list is empty (workers run independently)."""
        response = requests.get(
            f"{BASE_URL}/api/jobs/status",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()

        if data["scheduler_mode"] == "apscheduler":
            job_ids = [job["id"] for job in data["jobs"]]
            assert "appointment_reminders" in job_ids, (
                "appointment_reminders job not found"
            )
            assert "daily_summary" in job_ids, "daily_summary job not found"
        else:
            # Celery mode: beat schedule is defined in celery_app.py, not reflected here
            assert isinstance(data["jobs"], list)

    def test_scheduler_jobs_have_next_run_times(self, auth_token):
        """In APScheduler mode, jobs have id/name/next_run/trigger fields."""
        response = requests.get(
            f"{BASE_URL}/api/jobs/status",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()

        if data["scheduler_mode"] != "apscheduler":
            return  # Celery mode: job list is empty, nothing to assert

        for job in data["jobs"]:
            assert "id" in job
            assert "name" in job
            assert "next_run" in job
            assert "trigger" in job
            assert job["trigger"] is not None


class TestAppointmentReminders:
    """Tests for appointment reminder endpoints"""

    @pytest.fixture
    def auth_token(self):
        """Get auth token for testing"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        return response.json()["access_token"]

    def test_reminders_preview(self, auth_token):
        """GET /api/jobs/reminders/preview returns preview data"""
        response = requests.get(
            f"{BASE_URL}/api/jobs/reminders/preview",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()

        # Verify expected fields
        assert "reminder_window_hours" in data
        assert "appointments_needing_reminder" in data
        assert "preview" in data

        # Verify data types
        assert isinstance(data["reminder_window_hours"], int)
        assert isinstance(data["appointments_needing_reminder"], int)
        assert isinstance(data["preview"], list)

    def test_reminders_run(self, auth_token):
        """POST /api/jobs/reminders/run triggers the reminder job"""
        response = requests.post(
            f"{BASE_URL}/api/jobs/reminders/run",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "status" in data
        assert data["status"] == "completed"
        assert "results" in data

        # Verify results structure
        results = data["results"]
        assert "total_found" in results
        assert "sent" in results
        assert "failed" in results
        assert "blocked" in results

        # Verify data types
        assert isinstance(results["total_found"], int)
        assert isinstance(results["sent"], int)
        assert isinstance(results["failed"], int)
        assert isinstance(results["blocked"], int)


class TestDailySummary:
    """Tests for daily summary endpoints (OwnerOpsAgent)"""

    @pytest.fixture
    def auth_token(self):
        """Get auth token for testing"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        return response.json()["access_token"]

    def test_daily_summary_preview(self, auth_token):
        """GET /api/jobs/daily-summary/preview returns stats without sending email"""
        response = requests.get(
            f"{BASE_URL}/api/jobs/daily-summary/preview",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "stats" in data
        assert "shop_email" in data

    def test_daily_summary_preview_stats_fields(self, auth_token):
        """Verify daily summary stats contain all expected fields"""
        response = requests.get(
            f"{BASE_URL}/api/jobs/daily-summary/preview",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        stats = response.json()["stats"]

        # Verify OwnerOpsAgent stats compilation fields
        expected_fields = [
            "date",
            "date_short",
            "total_appointments",
            "completed",
            "no_shows",
            "cancelled",
            "pending",
            "total_revenue",
            "total_recovered",
            "recovered_by_source",
            "messages_sent",
            "messages_received",
            "waitlist_active",
            "new_clients",
            "no_show_rate",
        ]

        for field in expected_fields:
            assert field in stats, f"Missing expected field: {field}"

    def test_daily_summary_stats_data_types(self, auth_token):
        """Verify stats have correct data types"""
        response = requests.get(
            f"{BASE_URL}/api/jobs/daily-summary/preview",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        stats = response.json()["stats"]

        # Integer fields
        int_fields = [
            "total_appointments",
            "completed",
            "no_shows",
            "cancelled",
            "pending",
            "messages_sent",
            "messages_received",
            "waitlist_active",
            "new_clients",
        ]
        for field in int_fields:
            assert isinstance(stats[field], int), f"{field} should be int"

        # Numeric fields (int or float)
        numeric_fields = ["total_revenue", "total_recovered", "no_show_rate"]
        for field in numeric_fields:
            assert isinstance(stats[field], (int, float)), f"{field} should be numeric"

        # String fields
        assert isinstance(stats["date"], str)
        assert isinstance(stats["date_short"], str)

        # Dict field
        assert isinstance(stats["recovered_by_source"], dict)

    def test_daily_summary_run(self, auth_token):
        """POST /api/jobs/daily-summary/run triggers summary with send attempt"""
        response = requests.post(
            f"{BASE_URL}/api/jobs/daily-summary/run",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "status" in data
        assert "stats" in data

        # SendGrid 401 is expected (API key expired) - status will be "failed"
        # But the endpoint should still return stats correctly
        assert data["status"] in ["sent", "failed", "skipped"]

        # If status is "failed", should have error message
        if data["status"] == "failed":
            assert "error" in data

    def test_daily_summary_run_returns_stats(self, auth_token):
        """Verify daily summary run includes complete stats"""
        response = requests.post(
            f"{BASE_URL}/api/jobs/daily-summary/run",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()

        # Verify stats are included
        assert "stats" in data
        stats = data["stats"]

        # Verify key fields exist
        assert "total_appointments" in stats
        assert "completed" in stats
        assert "no_shows" in stats
        assert "cancelled" in stats
        assert "total_revenue" in stats


class TestRegressionExistingFeatures:
    """Quick regression tests for existing features"""

    @pytest.fixture
    def auth_token(self):
        """Get auth token for testing"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        return response.json()["access_token"]

    def test_dashboard_stats_loads(self, auth_token):
        """Dashboard stats endpoint still works"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/stats",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "appointments_today" in data
        assert "no_show_rate" in data

    def test_clients_list(self, auth_token):
        """Clients list endpoint still works"""
        response = requests.get(
            f"{BASE_URL}/api/clients?limit=5",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "clients" in data
        assert "total" in data

    def test_appointments_list(self, auth_token):
        """Appointments list endpoint still works"""
        response = requests.get(
            f"{BASE_URL}/api/appointments?limit=5",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "appointments" in data
        assert "total" in data

    def test_conversations_list(self, auth_token):
        """Conversations list endpoint still works"""
        response = requests.get(
            f"{BASE_URL}/api/conversations",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "conversations" in data

    def test_waitlist_list(self, auth_token):
        """Waitlist list endpoint still works"""
        response = requests.get(
            f"{BASE_URL}/api/waitlist",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "waitlist" in data

    def test_barbers_list(self, auth_token):
        """Barbers list endpoint still works"""
        response = requests.get(
            f"{BASE_URL}/api/barbers", headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "barbers" in data

    def test_services_list(self, auth_token):
        """Services list endpoint still works"""
        response = requests.get(
            f"{BASE_URL}/api/services",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "services" in data


class TestHealthEndpoint:
    """Test health endpoint without auth"""

    def test_health_check(self):
        """Health endpoint returns correct provider status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert "providers" in data
        assert "sendgrid_enabled" in data["providers"]
        assert "compliance" in data
