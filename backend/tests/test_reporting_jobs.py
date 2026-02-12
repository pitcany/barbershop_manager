"""
Test Reporting Dashboard and Jobs Dashboard Features
Tests new API endpoints for iteration 6:
- GET /api/reporting/overview
- GET /api/reporting/jobs-history
- GET /api/jobs/status
- POST /api/jobs/reminders/run
- GET /api/jobs/reminders/preview
- POST /api/jobs/daily-summary/run
- GET /api/jobs/daily-summary/preview
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://booking-recovery.preview.emergentagent.com').rstrip('/')

@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for tests"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Authentication failed - skipping tests")


@pytest.fixture
def api_client(auth_token):
    """Authenticated requests session"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


class TestAuthEndpoint:
    """Auth endpoint tests"""
    
    def test_login_success(self):
        """Test successful login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        print("Auth: Login successful")


class TestReportingOverview:
    """Test /api/reporting/overview endpoint"""
    
    def test_reporting_overview_default(self, api_client):
        """Test reporting overview with default 30 days"""
        response = api_client.get(f"{BASE_URL}/api/reporting/overview")
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields
        assert "period_days" in data
        assert "appointments" in data
        assert "revenue" in data
        assert "daily_trend" in data
        assert "recovered_events" in data
        assert "barber_performance" in data
        assert "messages" in data
        
        # Verify data structure
        assert "total" in data["appointments"]
        assert "by_status" in data["appointments"]
        assert "no_show_rate" in data["appointments"]
        assert "total_earned" in data["revenue"]
        assert "total_recovered" in data["revenue"]
        
        print(f"Reporting overview - period: {data['period_days']} days, total appts: {data['appointments']['total']}")
    
    def test_reporting_overview_7_days(self, api_client):
        """Test reporting overview with 7 days period"""
        response = api_client.get(f"{BASE_URL}/api/reporting/overview?days=7")
        assert response.status_code == 200
        data = response.json()
        assert data["period_days"] == 7
        print(f"7-day reporting: {data['appointments']['total']} appointments")
    
    def test_reporting_overview_14_days(self, api_client):
        """Test reporting overview with 14 days period"""
        response = api_client.get(f"{BASE_URL}/api/reporting/overview?days=14")
        assert response.status_code == 200
        data = response.json()
        assert data["period_days"] == 14
        print(f"14-day reporting: {data['appointments']['total']} appointments")
    
    def test_reporting_overview_90_days(self, api_client):
        """Test reporting overview with 90 days period"""
        response = api_client.get(f"{BASE_URL}/api/reporting/overview?days=90")
        assert response.status_code == 200
        data = response.json()
        assert data["period_days"] == 90
        print(f"90-day reporting: {data['appointments']['total']} appointments")
    
    def test_reporting_overview_daily_trend(self, api_client):
        """Verify daily_trend data structure"""
        response = api_client.get(f"{BASE_URL}/api/reporting/overview?days=30")
        assert response.status_code == 200
        data = response.json()
        
        if len(data["daily_trend"]) > 0:
            trend_entry = data["daily_trend"][0]
            assert "date" in trend_entry
            assert "total" in trend_entry
            assert "completed" in trend_entry
            assert "no_shows" in trend_entry
            assert "cancelled" in trend_entry
            assert "revenue" in trend_entry
        print(f"Daily trend entries: {len(data['daily_trend'])}")
    
    def test_reporting_overview_barber_performance(self, api_client):
        """Verify barber_performance data structure"""
        response = api_client.get(f"{BASE_URL}/api/reporting/overview?days=30")
        assert response.status_code == 200
        data = response.json()
        
        if len(data["barber_performance"]) > 0:
            barber = data["barber_performance"][0]
            assert "name" in barber
            assert "total" in barber
            assert "completed" in barber
            assert "no_shows" in barber
            assert "revenue" in barber
        print(f"Barber performance entries: {len(data['barber_performance'])}")
    
    def test_reporting_overview_messages(self, api_client):
        """Verify messages data structure"""
        response = api_client.get(f"{BASE_URL}/api/reporting/overview?days=30")
        assert response.status_code == 200
        data = response.json()
        
        assert "inbound" in data["messages"]
        assert "outbound" in data["messages"]
        print(f"Messages - inbound: {data['messages']['inbound']}, outbound: {data['messages']['outbound']}")


class TestJobsHistory:
    """Test /api/reporting/jobs-history endpoint"""
    
    def test_jobs_history_default(self, api_client):
        """Test jobs history with default limit"""
        response = api_client.get(f"{BASE_URL}/api/reporting/jobs-history")
        assert response.status_code == 200
        data = response.json()
        
        assert "entries" in data
        assert "count" in data
        assert isinstance(data["entries"], list)
        print(f"Jobs history - count: {data['count']}")
    
    def test_jobs_history_with_limit(self, api_client):
        """Test jobs history with custom limit"""
        response = api_client.get(f"{BASE_URL}/api/reporting/jobs-history?limit=5")
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["entries"]) <= 5
        print(f"Jobs history with limit 5 - returned: {len(data['entries'])}")
    
    def test_jobs_history_entry_structure(self, api_client):
        """Verify job history entry structure"""
        response = api_client.get(f"{BASE_URL}/api/reporting/jobs-history?limit=5")
        assert response.status_code == 200
        data = response.json()
        
        if len(data["entries"]) > 0:
            entry = data["entries"][0]
            assert "action" in entry
            assert "provider" in entry
            assert "success" in entry
            assert "created_at" in entry
        print("Jobs history entry structure verified")


class TestJobsStatus:
    """Test /api/jobs/status endpoint"""
    
    def test_jobs_status(self, api_client):
        """Test scheduler status endpoint"""
        response = api_client.get(f"{BASE_URL}/api/jobs/status")
        assert response.status_code == 200
        data = response.json()
        
        assert data["scheduler"] == "running"
        assert "jobs" in data
        assert isinstance(data["jobs"], list)
        print(f"Scheduler running with {len(data['jobs'])} jobs")
    
    def test_jobs_status_has_both_jobs(self, api_client):
        """Verify both expected jobs exist"""
        response = api_client.get(f"{BASE_URL}/api/jobs/status")
        assert response.status_code == 200
        data = response.json()
        
        job_ids = [job["id"] for job in data["jobs"]]
        assert "appointment_reminders" in job_ids
        assert "daily_summary" in job_ids
        print("Both expected jobs found: appointment_reminders, daily_summary")
    
    def test_jobs_status_job_structure(self, api_client):
        """Verify job status structure"""
        response = api_client.get(f"{BASE_URL}/api/jobs/status")
        assert response.status_code == 200
        data = response.json()
        
        for job in data["jobs"]:
            assert "id" in job
            assert "name" in job
            assert "next_run" in job
            assert "trigger" in job
        print("Job structure verified")


class TestRemindersEndpoints:
    """Test /api/jobs/reminders/* endpoints"""
    
    def test_reminders_preview(self, api_client):
        """Test reminders preview endpoint"""
        response = api_client.get(f"{BASE_URL}/api/jobs/reminders/preview")
        assert response.status_code == 200
        data = response.json()
        
        assert "reminder_window_hours" in data
        assert "appointments_needing_reminder" in data
        assert "preview" in data
        assert isinstance(data["preview"], list)
        print(f"Reminders preview - {data['appointments_needing_reminder']} appointments needing reminder")
    
    def test_reminders_run(self, api_client):
        """Test running reminders job"""
        response = api_client.post(f"{BASE_URL}/api/jobs/reminders/run")
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "completed"
        assert "results" in data
        assert "total_found" in data["results"]
        assert "sent" in data["results"]
        assert "failed" in data["results"]
        assert "blocked" in data["results"]
        print(f"Reminders run - found: {data['results']['total_found']}, sent: {data['results']['sent']}")


class TestDailySummaryEndpoints:
    """Test /api/jobs/daily-summary/* endpoints"""
    
    def test_daily_summary_preview(self, api_client):
        """Test daily summary preview endpoint"""
        response = api_client.get(f"{BASE_URL}/api/jobs/daily-summary/preview")
        assert response.status_code == 200
        data = response.json()
        
        assert "stats" in data
        assert "shop_email" in data
        
        stats = data["stats"]
        assert "date" in stats
        assert "total_appointments" in stats
        assert "completed" in stats
        assert "no_shows" in stats
        assert "cancelled" in stats
        assert "total_revenue" in stats
        assert "total_recovered" in stats
        assert "messages_sent" in stats
        assert "messages_received" in stats
        assert "waitlist_active" in stats
        assert "new_clients" in stats
        assert "no_show_rate" in stats
        print(f"Daily summary preview - date: {stats['date']}")
    
    def test_daily_summary_run(self, api_client):
        """Test running daily summary job (may fail due to SendGrid 401 - expected)"""
        response = api_client.post(f"{BASE_URL}/api/jobs/daily-summary/run")
        assert response.status_code == 200
        data = response.json()
        
        # Status can be "success" or "failed" (SendGrid 401 is expected)
        assert "status" in data
        assert "stats" in data
        assert "to" in data
        print(f"Daily summary run - status: {data['status']}, to: {data['to']}")


class TestRegressionEndpoints:
    """Regression tests for existing endpoints"""
    
    def test_dashboard_stats(self, api_client):
        """Test dashboard stats still works"""
        response = api_client.get(f"{BASE_URL}/api/dashboard/stats")
        assert response.status_code == 200
        data = response.json()
        assert "appointments_today" in data
        print("Dashboard stats - SUCCESS")
    
    def test_clients_list(self, api_client):
        """Test clients list still works"""
        response = api_client.get(f"{BASE_URL}/api/clients")
        assert response.status_code == 200
        data = response.json()
        assert "clients" in data
        print(f"Clients list - {len(data['clients'])} clients")
    
    def test_appointments_list(self, api_client):
        """Test appointments list still works"""
        response = api_client.get(f"{BASE_URL}/api/appointments")
        assert response.status_code == 200
        data = response.json()
        assert "appointments" in data
        print(f"Appointments list - {len(data['appointments'])} appointments")
    
    def test_conversations_list(self, api_client):
        """Test conversations list still works"""
        response = api_client.get(f"{BASE_URL}/api/conversations")
        assert response.status_code == 200
        data = response.json()
        assert "conversations" in data
        print("Conversations list - SUCCESS")
    
    def test_waitlist_list(self, api_client):
        """Test waitlist list still works"""
        response = api_client.get(f"{BASE_URL}/api/waitlist")
        assert response.status_code == 200
        data = response.json()
        assert "waitlist" in data
        print(f"Waitlist list - {len(data['waitlist'])} entries")
    
    def test_barbers_list(self, api_client):
        """Test barbers list still works"""
        response = api_client.get(f"{BASE_URL}/api/barbers")
        assert response.status_code == 200
        data = response.json()
        assert "barbers" in data
        print(f"Barbers list - {len(data['barbers'])} barbers")
    
    def test_services_list(self, api_client):
        """Test services list still works"""
        response = api_client.get(f"{BASE_URL}/api/services")
        assert response.status_code == 200
        data = response.json()
        assert "services" in data
        print(f"Services list - {len(data['services'])} services")
    
    def test_health_endpoint(self, api_client):
        """Test health check endpoint"""
        response = api_client.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("Health check - healthy")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
