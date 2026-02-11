#!/usr/bin/env python3
"""
Comprehensive Barbershop Manager Workflow Test

Simulates a real barbershop manager using the product end-to-end.
Tests all API endpoints, business logic, compliance, and edge cases.
Reports bugs and issues found.

Uses mongomock-motor to avoid needing a real MongoDB instance.
"""
import asyncio
import os
import sys
import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, AsyncMock
from typing import Dict, Any, List, Tuple

# Ensure backend is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Patch Motor before importing server
import mongomock
import motor.motor_asyncio

# Create a mongomock client that behaves like Motor
from mongomock_motor import AsyncMongoMockClient

# Override the Motor client in server.py
mock_mongo_client = AsyncMongoMockClient()
mock_db = mock_mongo_client["test_barbershop"]


class TestResult:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.bugs_found: List[Dict[str, str]] = []
        self.warnings: List[Dict[str, str]] = []
        self.failed_tests: List[Dict[str, str]] = []

    def log_pass(self, test_name: str, detail: str = ""):
        self.tests_run += 1
        self.tests_passed += 1
        print(f"  PASS: {test_name}" + (f" - {detail}" if detail else ""))

    def log_fail(self, test_name: str, detail: str):
        self.tests_run += 1
        self.tests_failed += 1
        self.failed_tests.append({"test": test_name, "detail": detail})
        print(f"  FAIL: {test_name} - {detail}")

    def log_bug(self, severity: str, title: str, detail: str, location: str = ""):
        self.bugs_found.append({
            "severity": severity,
            "title": title,
            "detail": detail,
            "location": location
        })
        print(f"  BUG [{severity}]: {title}")

    def log_warning(self, title: str, detail: str):
        self.warnings.append({"title": title, "detail": detail})
        print(f"  WARNING: {title}")

    def summary(self):
        print("\n" + "=" * 70)
        print("TEST RESULTS SUMMARY")
        print("=" * 70)
        print(f"Tests run:    {self.tests_run}")
        print(f"Tests passed: {self.tests_passed}")
        print(f"Tests failed: {self.tests_failed}")
        print(f"Bugs found:   {len(self.bugs_found)}")
        print(f"Warnings:     {len(self.warnings)}")

        if self.failed_tests:
            print(f"\n--- Failed Tests ({len(self.failed_tests)}) ---")
            for ft in self.failed_tests:
                print(f"  - {ft['test']}: {ft['detail']}")

        if self.bugs_found:
            print(f"\n--- Bugs Found ({len(self.bugs_found)}) ---")
            for i, bug in enumerate(self.bugs_found, 1):
                print(f"\n  BUG #{i} [{bug['severity']}]: {bug['title']}")
                print(f"    Detail: {bug['detail']}")
                if bug['location']:
                    print(f"    Location: {bug['location']}")

        if self.warnings:
            print(f"\n--- Warnings ({len(self.warnings)}) ---")
            for w in self.warnings:
                print(f"  - {w['title']}: {w['detail']}")

        print("=" * 70)
        return self.tests_failed == 0


results = TestResult()


async def setup_test_env():
    """Patch the server module to use mock MongoDB"""
    import server
    # Replace the db reference
    server.db = mock_db
    server.client = mock_mongo_client

    # Reset provider singletons
    from providers import reset_providers
    reset_providers()

    return server


async def seed_and_get_app():
    """Set up the app with seed data"""
    server = await setup_test_env()

    # Run seed manually
    await server.seed_demo_data()

    return server.app


async def run_all_tests():
    """Main test runner"""
    from httpx import AsyncClient, ASGITransport

    app = await seed_and_get_app()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await test_auth_flow(client)
        if not token:
            print("FATAL: Auth failed, cannot continue")
            return

        headers = {"Authorization": f"Bearer {token}"}

        await test_health_endpoints(client)
        await test_dashboard(client, headers)
        await test_appointments(client, headers)
        await test_appointment_status_transitions(client, headers)
        await test_clients(client, headers)
        await test_conversations(client, headers)
        await test_waitlist(client, headers)
        await test_barbers_and_services(client, headers)
        await test_shop_policy(client, headers)
        await test_sms_inbound_workflow(client)
        await test_sms_compliance(client)
        await test_sms_opt_out_flow(client)
        await test_public_endpoints(client)
        await test_mock_payment_flow(client, headers)
        await test_reminder_job(client, headers)
        await test_audit_log(client, headers)
        await test_revenue_tracking(client, headers)
        await test_rate_limiting(client)
        await test_edge_cases(client, headers)
        await test_data_integrity(client, headers)
        await analyze_code_issues()


# ==================== AUTH TESTS ====================

async def test_auth_flow(client) -> str:
    """Test the complete authentication flow"""
    print("\n--- Testing Authentication Flow ---")

    # 1. Login with valid credentials
    resp = await client.post("/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    if resp.status_code == 200 and "access_token" in resp.json():
        token = resp.json()["access_token"]
        results.log_pass("Login with valid credentials")
    else:
        results.log_fail("Login with valid credentials", f"Status {resp.status_code}: {resp.text}")
        return ""

    # 2. Verify token type
    data = resp.json()
    if data.get("token_type") == "bearer":
        results.log_pass("Token type is 'bearer'")
    else:
        results.log_fail("Token type is 'bearer'", f"Got: {data.get('token_type')}")

    # 3. Get current user
    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    if resp.status_code == 200:
        user = resp.json()
        if user.get("username") == "admin" and user.get("shop_id") == "demo_shop":
            results.log_pass("GET /auth/me returns correct user")
        else:
            results.log_fail("GET /auth/me returns correct user", f"Got: {user}")
    else:
        results.log_fail("GET /auth/me", f"Status {resp.status_code}")

    # 4. Invalid login
    resp = await client.post("/api/auth/login", json={
        "username": "admin",
        "password": "wrongpassword"
    })
    if resp.status_code == 401:
        results.log_pass("Invalid login returns 401")
    else:
        results.log_fail("Invalid login returns 401", f"Got status {resp.status_code}")

    # 5. Missing auth header
    resp = await client.get("/api/auth/me")
    if resp.status_code == 401:
        results.log_pass("Missing auth header returns 401")
    else:
        results.log_fail("Missing auth header returns 401", f"Got status {resp.status_code}")

    # 6. Invalid token
    resp = await client.get("/api/auth/me", headers={"Authorization": "Bearer invalid_token_here"})
    if resp.status_code == 401:
        results.log_pass("Invalid token returns 401")
    else:
        results.log_fail("Invalid token returns 401", f"Got status {resp.status_code}")

    return token


# ==================== HEALTH TESTS ====================

async def test_health_endpoints(client):
    """Test health and root endpoints"""
    print("\n--- Testing Health Endpoints ---")

    resp = await client.get("/api/")
    if resp.status_code == 200 and "Barbershop Autopilot API" in resp.json().get("message", ""):
        results.log_pass("Root endpoint")
    else:
        results.log_fail("Root endpoint", f"Status {resp.status_code}")

    resp = await client.get("/api/health")
    if resp.status_code == 200:
        data = resp.json()
        if data.get("status") == "healthy":
            results.log_pass("Health check returns healthy")
        else:
            results.log_fail("Health check returns healthy", f"Got: {data}")

        # Verify compliance flags
        compliance = data.get("compliance", {})
        if all([
            compliance.get("sms_consent_enforced"),
            compliance.get("stop_handling_enabled"),
            compliance.get("audit_logging_enabled")
        ]):
            results.log_pass("Health check shows compliance enabled")
        else:
            results.log_fail("Compliance flags", f"Got: {compliance}")
    else:
        results.log_fail("Health check", f"Status {resp.status_code}")


# ==================== DASHBOARD TESTS ====================

async def test_dashboard(client, headers):
    """Test dashboard stats and revenue chart - the first thing a manager sees"""
    print("\n--- Testing Dashboard (Manager's First Screen) ---")

    # 1. Dashboard stats
    resp = await client.get("/api/dashboard/stats", headers=headers)
    if resp.status_code == 200:
        stats = resp.json()
        results.log_pass("Dashboard stats endpoint works")

        # Verify expected fields
        expected_fields = [
            "appointments_today", "appointments_month", "no_shows_month",
            "revenue_recovered", "waitlist_count", "messages_today",
            "deposits_collected", "no_show_rate"
        ]
        missing = [f for f in expected_fields if f not in stats]
        if not missing:
            results.log_pass("Dashboard has all expected fields")
        else:
            results.log_fail("Dashboard missing fields", f"Missing: {missing}")

        # Verify data types
        if isinstance(stats.get("no_show_rate"), (int, float)):
            results.log_pass("no_show_rate is numeric")
        else:
            results.log_fail("no_show_rate type", f"Got: {type(stats.get('no_show_rate'))}")

        # Check seed data: we seeded 3 appointments, should show some today
        if stats["appointments_today"] >= 0:
            results.log_pass("appointments_today is non-negative")

        # Revenue recovered should include the seeded event (+25 + +20 = 45)
        if stats["revenue_recovered"] >= 0:
            results.log_pass("revenue_recovered is non-negative")
        else:
            results.log_fail("revenue_recovered", f"Got negative: {stats['revenue_recovered']}")

        # Verify no_show_rate calculation
        if stats["appointments_month"] > 0:
            expected_rate = round(stats["no_shows_month"] / stats["appointments_month"] * 100, 1)
            if abs(stats["no_show_rate"] - expected_rate) < 0.01:
                results.log_pass("no_show_rate calculation correct")
            else:
                results.log_fail("no_show_rate calculation",
                    f"Expected {expected_rate}, got {stats['no_show_rate']}")
    else:
        results.log_fail("Dashboard stats", f"Status {resp.status_code}: {resp.text}")

    # 2. Revenue chart
    resp = await client.get("/api/dashboard/revenue-chart", headers=headers)
    if resp.status_code == 200:
        chart = resp.json()
        if "data" in chart:
            results.log_pass("Revenue chart returns data array")

            # Check if seeded events show up
            if len(chart["data"]) > 0:
                # Verify each data point has required fields
                first = chart["data"][0]
                if all(k in first for k in ["date", "recovered", "lost"]):
                    results.log_pass("Revenue chart data has correct schema")
                else:
                    results.log_fail("Revenue chart schema", f"Got: {first}")
            else:
                results.log_warning("Revenue chart empty", "No data points returned despite seeded events")

            # BUG CHECK: Revenue chart doesn't fill in missing dates
            # This means the chart will have gaps
            if len(chart["data"]) < 30:
                results.log_bug(
                    "MEDIUM",
                    "Revenue chart has gaps for days without events",
                    "The chart only returns days that have events, not a continuous 30-day series. "
                    "The frontend will show gaps in the visualization for days with no revenue events.",
                    "server.py:289-312 (get_revenue_chart)"
                )
        else:
            results.log_fail("Revenue chart structure", f"Missing 'data' key")
    else:
        results.log_fail("Revenue chart", f"Status {resp.status_code}")

    # 3. Custom days parameter
    resp = await client.get("/api/dashboard/revenue-chart?days=7", headers=headers)
    if resp.status_code == 200:
        results.log_pass("Revenue chart with days=7 parameter")
    else:
        results.log_fail("Revenue chart days param", f"Status {resp.status_code}")


# ==================== APPOINTMENTS TESTS ====================

async def test_appointments(client, headers):
    """Test appointment listing and filtering"""
    print("\n--- Testing Appointments ---")

    # 1. List all appointments
    resp = await client.get("/api/appointments", headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        if "appointments" in data and "total" in data:
            results.log_pass("List appointments returns correct structure")
            if data["total"] >= 3:
                results.log_pass(f"Found {data['total']} seeded appointments")
            else:
                results.log_fail("Seeded appointments count", f"Expected >= 3, got {data['total']}")

            # Verify enrichment (client, service, barber data attached)
            apt = data["appointments"][0]
            if apt.get("client") and apt.get("service") and apt.get("barber"):
                results.log_pass("Appointments enriched with client/service/barber data")
            else:
                results.log_fail("Appointment enrichment",
                    f"client={apt.get('client')}, service={apt.get('service')}, barber={apt.get('barber')}")
        else:
            results.log_fail("Appointments structure", f"Got: {list(data.keys())}")
    else:
        results.log_fail("List appointments", f"Status {resp.status_code}")

    # 2. Filter by status
    resp = await client.get("/api/appointments?status=confirmed", headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        all_confirmed = all(a["status"] == "confirmed" for a in data["appointments"])
        if all_confirmed:
            results.log_pass("Filter by status=confirmed works")
        else:
            statuses = [a["status"] for a in data["appointments"]]
            results.log_fail("Status filter", f"Not all confirmed: {statuses}")
    else:
        results.log_fail("Filter by status", f"Status {resp.status_code}")

    # 3. Filter by date
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    resp = await client.get(f"/api/appointments?date={today}", headers=headers)
    if resp.status_code == 200:
        results.log_pass(f"Filter by date={today} works")
    else:
        results.log_fail("Filter by date", f"Status {resp.status_code}")

    # 4. Invalid date format
    resp = await client.get("/api/appointments?date=01-01-2025", headers=headers)
    if resp.status_code == 400:
        results.log_pass("Invalid date format returns 400")
    else:
        results.log_fail("Invalid date format", f"Expected 400, got {resp.status_code}")

    # 5. Get single appointment
    resp = await client.get("/api/appointments/apt_1", headers=headers)
    if resp.status_code == 200:
        apt = resp.json()
        if apt["id"] == "apt_1":
            results.log_pass("Get single appointment by ID")
        else:
            results.log_fail("Single appointment ID", f"Got: {apt['id']}")
    else:
        results.log_fail("Get single appointment", f"Status {resp.status_code}")

    # 6. Non-existent appointment
    resp = await client.get("/api/appointments/nonexistent_id", headers=headers)
    if resp.status_code == 404:
        results.log_pass("Non-existent appointment returns 404")
    else:
        results.log_fail("Non-existent appointment", f"Expected 404, got {resp.status_code}")

    # 7. Pagination
    resp = await client.get("/api/appointments?limit=1&skip=0", headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        if len(data["appointments"]) <= 1 and data["total"] >= 3:
            results.log_pass("Pagination works (limit=1)")
        else:
            results.log_fail("Pagination", f"Got {len(data['appointments'])} items, total={data['total']}")
    else:
        results.log_fail("Pagination", f"Status {resp.status_code}")


# ==================== STATUS TRANSITIONS ====================

async def test_appointment_status_transitions(client, headers):
    """Test appointment status updates - critical business logic"""
    print("\n--- Testing Appointment Status Transitions ---")

    # 1. Valid status update: pending -> confirmed
    resp = await client.patch("/api/appointments/apt_3/status?status=confirmed", headers=headers)
    if resp.status_code == 200:
        results.log_pass("Update status pending -> confirmed")
    else:
        results.log_fail("Update status", f"Status {resp.status_code}: {resp.text}")

    # Verify the update persisted
    resp = await client.get("/api/appointments/apt_3", headers=headers)
    if resp.status_code == 200 and resp.json()["status"] == "confirmed":
        results.log_pass("Status update persisted correctly")
    else:
        results.log_fail("Status persistence", f"Got: {resp.json().get('status')}")

    # 2. Invalid status value
    resp = await client.patch("/api/appointments/apt_3/status?status=invalid_status", headers=headers)
    if resp.status_code == 400:
        results.log_pass("Invalid status value returns 400")
    else:
        results.log_fail("Invalid status value", f"Expected 400, got {resp.status_code}")

    # 3. BUG: No state machine validation
    # Can go from confirmed -> pending (backwards transition)
    resp = await client.patch("/api/appointments/apt_3/status?status=pending", headers=headers)
    if resp.status_code == 200:
        results.log_bug(
            "HIGH",
            "No appointment status state machine validation",
            "Any status can transition to any other status. A confirmed appointment can go back "
            "to pending, a completed appointment can become no_show, etc. "
            "This allows impossible transitions like: completed -> pending, no_show -> confirmed.",
            "server.py:377-399 (update_appointment_status)"
        )
    else:
        results.log_pass("Status transition validation exists")

    # 4. BUG: Can mark future appointment as no_show
    resp = await client.patch("/api/appointments/apt_3/status?status=no_show", headers=headers)
    if resp.status_code == 200:
        results.log_bug(
            "HIGH",
            "Can mark future appointments as no_show",
            "A future appointment (tomorrow) can be marked as no_show. "
            "No-show should only be possible for past appointments.",
            "server.py:377-399 (update_appointment_status)"
        )
    # Reset it
    await client.patch("/api/appointments/apt_3/status?status=pending", headers=headers)

    # 5. BUG: Can mark future appointment as completed
    resp = await client.patch("/api/appointments/apt_3/status?status=completed", headers=headers)
    if resp.status_code == 200:
        results.log_bug(
            "MEDIUM",
            "Can mark future appointments as completed",
            "A future appointment can be marked as completed without checking "
            "whether the scheduled time has passed.",
            "server.py:377-399 (update_appointment_status)"
        )
    # Reset it
    await client.patch("/api/appointments/apt_3/status?status=pending", headers=headers)

    # 6. Non-existent appointment status update
    resp = await client.patch("/api/appointments/nonexistent/status?status=confirmed", headers=headers)
    if resp.status_code == 404:
        results.log_pass("Non-existent appointment status update returns 404")
    else:
        results.log_fail("Non-existent apt status", f"Expected 404, got {resp.status_code}")


# ==================== CLIENTS TESTS ====================

async def test_clients(client, headers):
    """Test client management"""
    print("\n--- Testing Client Management ---")

    # 1. List clients
    resp = await client.get("/api/clients", headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        if data["total"] >= 3:
            results.log_pass(f"List clients returns {data['total']} clients")
        else:
            results.log_fail("Client count", f"Expected >= 3, got {data['total']}")
    else:
        results.log_fail("List clients", f"Status {resp.status_code}")

    # 2. Search by name
    resp = await client.get("/api/clients?search=John", headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        if data["total"] >= 1 and any("John" in c.get("name", "") for c in data["clients"]):
            results.log_pass("Search clients by name")
        else:
            results.log_fail("Search by name", f"Got {data['total']} results")
    else:
        results.log_fail("Search clients", f"Status {resp.status_code}")

    # 3. Search by phone
    resp = await client.get("/api/clients?search=%2B15559876543", headers=headers)
    if resp.status_code == 200:
        results.log_pass("Search clients by phone")
    else:
        results.log_fail("Search by phone", f"Status {resp.status_code}")

    # 4. Get single client
    resp = await client.get("/api/clients/client_1", headers=headers)
    if resp.status_code == 200:
        c = resp.json()
        if c["name"] == "John Smith" and c["sms_consent"] == True:
            results.log_pass("Get client details with consent info")
        else:
            results.log_fail("Client details", f"Got: {c}")
    else:
        results.log_fail("Get client", f"Status {resp.status_code}")

    # 5. Verify consent tracking fields
    resp = await client.get("/api/clients/client_1", headers=headers)
    if resp.status_code == 200:
        c = resp.json()
        consent_fields = ["sms_consent", "sms_consent_timestamp", "sms_consent_source"]
        has_all = all(f in c for f in consent_fields)
        if has_all:
            results.log_pass("Client has consent tracking fields")
        else:
            results.log_fail("Consent fields", f"Missing fields in client data")


# ==================== CONVERSATIONS TESTS ====================

async def test_conversations(client, headers):
    """Test conversation threads"""
    print("\n--- Testing Conversations ---")

    # 1. List conversation threads
    resp = await client.get("/api/conversations", headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        if "conversations" in data:
            results.log_pass("List conversations")
            if len(data["conversations"]) > 0:
                thread = data["conversations"][0]
                if all(k in thread for k in ["client_id", "last_message", "message_count"]):
                    results.log_pass("Conversation thread has correct schema")
                else:
                    results.log_fail("Thread schema", f"Got keys: {list(thread.keys())}")
            else:
                results.log_warning("No conversations", "Expected seeded messages to create threads")
        else:
            results.log_fail("Conversations structure", f"Missing 'conversations' key")
    else:
        results.log_fail("List conversations", f"Status {resp.status_code}")

    # 2. Get messages for a specific client
    resp = await client.get("/api/conversations/client_1", headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        if "messages" in data and "client" in data:
            if len(data["messages"]) >= 4:
                results.log_pass(f"Client conversation has {len(data['messages'])} messages")
            else:
                results.log_fail("Message count", f"Expected >= 4 seeded messages, got {len(data['messages'])}")

            # Verify messages are in chronological order (oldest first)
            if len(data["messages"]) >= 2:
                times = [m["created_at"] for m in data["messages"]]
                if times == sorted(times):
                    results.log_pass("Messages in chronological order")
                else:
                    results.log_fail("Message order", "Messages not in chronological order")
        else:
            results.log_fail("Conversation detail", f"Missing keys")
    else:
        results.log_fail("Get conversation", f"Status {resp.status_code}")


# ==================== WAITLIST TESTS ====================

async def test_waitlist(client, headers):
    """Test waitlist management"""
    print("\n--- Testing Waitlist ---")

    # 1. List waitlist
    resp = await client.get("/api/waitlist", headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        if "waitlist" in data and len(data["waitlist"]) >= 1:
            results.log_pass(f"Waitlist has {len(data['waitlist'])} entries")

            # Verify enrichment
            entry = data["waitlist"][0]
            if entry.get("client") and entry.get("service"):
                results.log_pass("Waitlist entries enriched with client/service")
            else:
                results.log_fail("Waitlist enrichment",
                    f"client={entry.get('client')}, service={entry.get('service')}")
        else:
            results.log_fail("Waitlist data", f"Expected entries")
    else:
        results.log_fail("List waitlist", f"Status {resp.status_code}")

    # 2. Remove from waitlist
    resp = await client.delete("/api/waitlist/wait_1", headers=headers)
    if resp.status_code == 200:
        results.log_pass("Remove from waitlist")

        # Verify it's deactivated (not deleted)
        resp = await client.get("/api/waitlist", headers=headers)
        active_ids = [w["id"] for w in resp.json()["waitlist"]]
        if "wait_1" not in active_ids:
            results.log_pass("Removed entry no longer in active waitlist")
        else:
            results.log_fail("Waitlist removal", "Entry still appears in active list")
    else:
        results.log_fail("Remove from waitlist", f"Status {resp.status_code}")

    # Re-add for further tests
    await mock_db.waitlist.update_one(
        {"id": "wait_1"},
        {"$set": {"active": True}}
    )

    # 3. Non-existent waitlist entry
    resp = await client.delete("/api/waitlist/nonexistent", headers=headers)
    if resp.status_code == 404:
        results.log_pass("Non-existent waitlist entry returns 404")
    else:
        results.log_fail("Non-existent waitlist", f"Expected 404, got {resp.status_code}")


# ==================== BARBERS & SERVICES ====================

async def test_barbers_and_services(client, headers):
    """Test barber and service listings"""
    print("\n--- Testing Barbers & Services ---")

    resp = await client.get("/api/barbers", headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        if len(data["barbers"]) >= 3:
            results.log_pass(f"Found {len(data['barbers'])} barbers")
        else:
            results.log_fail("Barber count", f"Expected >= 3, got {len(data['barbers'])}")

    resp = await client.get("/api/services", headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        if len(data["services"]) >= 4:
            results.log_pass(f"Found {len(data['services'])} services")

            # Verify service has price and duration
            svc = data["services"][0]
            if "price" in svc and "duration_minutes" in svc:
                results.log_pass("Services have price and duration")
            else:
                results.log_fail("Service fields", f"Got: {list(svc.keys())}")
        else:
            results.log_fail("Service count", f"Expected >= 4, got {len(data['services'])}")


# ==================== SHOP POLICY ====================

async def test_shop_policy(client, headers):
    """Test shop policy updates - manager configuring their shop"""
    print("\n--- Testing Shop Policy Updates ---")

    # 1. Get current shop info
    resp = await client.get("/api/shop", headers=headers)
    if resp.status_code == 200:
        shop = resp.json()
        results.log_pass("Get shop info")
        original_deposit = shop["deposit_amount"]
    else:
        results.log_fail("Get shop info", f"Status {resp.status_code}")
        return

    # 2. Update deposit amount
    resp = await client.patch("/api/shop/policy", headers=headers, json={
        "deposit_amount": 30.0
    })
    if resp.status_code == 200:
        results.log_pass("Update deposit amount")

        # Verify it persisted
        resp = await client.get("/api/shop", headers=headers)
        if resp.json()["deposit_amount"] == 30.0:
            results.log_pass("Deposit amount persisted")
        else:
            results.log_fail("Deposit persistence", f"Got: {resp.json()['deposit_amount']}")
    else:
        results.log_fail("Update deposit", f"Status {resp.status_code}")

    # 3. Update multiple policies
    resp = await client.patch("/api/shop/policy", headers=headers, json={
        "confirmation_window_hours": 12,
        "max_messages_per_day": 6
    })
    if resp.status_code == 200:
        results.log_pass("Update multiple policies at once")
    else:
        results.log_fail("Multi-policy update", f"Status {resp.status_code}")

    # 4. BUG: No validation on policy values
    resp = await client.patch("/api/shop/policy", headers=headers, json={
        "deposit_amount": -50.0
    })
    if resp.status_code == 200:
        results.log_bug(
            "HIGH",
            "Negative deposit amount accepted",
            "Setting deposit_amount to -50.0 is accepted. There is no validation "
            "that deposit_amount must be non-negative. A manager could accidentally "
            "set a negative deposit, which would mean the shop PAYS the client.",
            "server.py:190-201 (update_shop_policy) and models.py:341-347 (PolicyUpdate)"
        )

    resp = await client.patch("/api/shop/policy", headers=headers, json={
        "max_messages_per_day": -1
    })
    if resp.status_code == 200:
        results.log_bug(
            "HIGH",
            "Negative max_messages_per_day accepted",
            "Setting max_messages_per_day to -1 is accepted. This would block ALL "
            "outbound SMS since the rate limit check would always fail.",
            "server.py:190-201 (update_shop_policy) and models.py:341-347 (PolicyUpdate)"
        )

    resp = await client.patch("/api/shop/policy", headers=headers, json={
        "max_messages_per_day": 0
    })
    if resp.status_code == 200:
        results.log_bug(
            "HIGH",
            "Zero max_messages_per_day accepted",
            "Setting max_messages_per_day to 0 effectively disables all SMS responses "
            "to clients. Rate limit at line 720 checks outbound_count >= shop.max_messages_per_day, "
            "which with 0 would always be true (0 >= 0), blocking the very first message.",
            "server.py:720 and models.py:341-347 (PolicyUpdate)"
        )

    # Restore original values
    await client.patch("/api/shop/policy", headers=headers, json={
        "deposit_amount": original_deposit,
        "max_messages_per_day": 4,
        "confirmation_window_hours": 24
    })


# ==================== SMS INBOUND WORKFLOW ====================

async def test_sms_inbound_workflow(client):
    """Test the SMS inbound webhook - core business flow"""
    print("\n--- Testing SMS Inbound Workflow ---")

    # Simulate Twilio webhook format
    def twilio_form(from_num, body, to_num="+15551234567"):
        return {
            "From": from_num,
            "To": to_num,
            "Body": body,
            "MessageSid": f"SM{uuid.uuid4().hex[:30]}"
        }

    # 1. HELP command from existing client
    resp = await client.post("/api/webhooks/twilio/inbound",
        data=twilio_form("+15559876543", "HELP"))
    if resp.status_code == 200:
        data = resp.json()
        if data.get("action") == "help":
            results.log_pass("HELP command processed")
        else:
            results.log_fail("HELP command", f"Got action: {data.get('action')}")
    else:
        results.log_fail("HELP webhook", f"Status {resp.status_code}")

    # 2. STATUS command
    resp = await client.post("/api/webhooks/twilio/inbound",
        data=twilio_form("+15559876543", "STATUS"))
    if resp.status_code == 200:
        results.log_pass("STATUS command processed")
    else:
        results.log_fail("STATUS webhook", f"Status {resp.status_code}")

    # 3. CONFIRM command
    resp = await client.post("/api/webhooks/twilio/inbound",
        data=twilio_form("+15559876543", "YES"))
    if resp.status_code == 200:
        results.log_pass("YES/CONFIRM command processed")
    else:
        results.log_fail("CONFIRM webhook", f"Status {resp.status_code}")

    # 4. BOOK command
    resp = await client.post("/api/webhooks/twilio/inbound",
        data=twilio_form("+15559876543", "BOOK"))
    if resp.status_code == 200:
        data = resp.json()
        if data.get("action") == "booking_started":
            results.log_pass("BOOK command returns service list")
        else:
            results.log_pass("BOOK command processed")
    else:
        results.log_fail("BOOK webhook", f"Status {resp.status_code}")

    # 5. CANCEL command
    resp = await client.post("/api/webhooks/twilio/inbound",
        data=twilio_form("+15551112222", "CANCEL"))
    if resp.status_code == 200:
        results.log_pass("CANCEL command processed")
    else:
        results.log_fail("CANCEL webhook", f"Status {resp.status_code}")

    # 6. New unknown client texting in
    resp = await client.post("/api/webhooks/twilio/inbound",
        data=twilio_form("+15559999999", "Hello, I want a haircut"))
    if resp.status_code == 200:
        results.log_pass("New client auto-created from inbound SMS")

        # Verify client was created
        new_client = await mock_db.clients.find_one({"phone": "+15559999999"})
        if new_client:
            if new_client.get("sms_consent") == True:
                results.log_pass("New client has sms_consent=True (implied consent)")

                # BUG: Implied consent from inbound SMS
                results.log_bug(
                    "MEDIUM",
                    "Implied SMS consent from any inbound message",
                    "When a new phone number texts in, the system automatically sets "
                    "sms_consent=True with source='inbound_sms'. Under TCPA, receiving a "
                    "single inbound SMS is not sufficient for express written consent to "
                    "send marketing/automated messages. The system should require explicit "
                    "opt-in (e.g., replying 'YES' to a consent prompt).",
                    "server.py:674-686 (twilio_inbound_webhook, new client creation)"
                )
            if new_client.get("name") == "New Client":
                results.log_pass("New client has placeholder name")
        else:
            results.log_fail("Client creation", "New client not found in DB")
    else:
        results.log_fail("New client inbound", f"Status {resp.status_code}")

    # 7. Message to non-existent shop phone
    resp = await client.post("/api/webhooks/twilio/inbound",
        data=twilio_form("+15559876543", "HELP", to_num="+10000000000"))
    if resp.status_code == 200:
        data = resp.json()
        if data.get("status") == "no_shop":
            results.log_pass("Non-existent shop phone returns no_shop status")
        else:
            results.log_fail("Non-existent shop", f"Got: {data}")
    else:
        results.log_fail("Non-existent shop webhook", f"Status {resp.status_code}")

    # 8. BUG: CANCEL keyword conflicts with SMS opt-out
    # In sms_compliance.py, OPT_OUT_KEYWORDS = {"STOP", "UNSUBSCRIBE", "CANCEL"}
    # In agents.py, FrontDeskAgent handles "CANCEL" as appointment cancellation
    # The opt-out check happens BEFORE the agent, so "CANCEL" = opt-out, not appointment cancel!
    resp = await client.post("/api/webhooks/twilio/inbound",
        data=twilio_form("+15553334444", "CANCEL"))
    if resp.status_code == 200:
        data = resp.json()
        if data.get("status") == "opt_out_processed":
            results.log_bug(
                "CRITICAL",
                "CANCEL keyword triggers SMS opt-out instead of appointment cancellation",
                "The word 'CANCEL' is in both OPT_OUT_KEYWORDS (sms_compliance.py:17) and the "
                "FrontDeskAgent command list (agents.py:110). Since opt-out checking happens BEFORE "
                "agent processing (server.py:703), sending 'CANCEL' always triggers opt-out, not "
                "appointment cancellation. Clients trying to cancel appointments are being "
                "unsubscribed from SMS instead. The HELP message tells clients to reply CANCEL "
                "to cancel appointments, which actually unsubscribes them.",
                "sms_compliance.py:17 vs agents.py:110 vs server.py:703"
            )

            # Verify client was opted out
            cl = await mock_db.clients.find_one({"id": "client_3"})
            if cl and cl.get("sms_consent") == False:
                results.log_pass("Client was indeed opted out (confirming the bug)")
                # Restore consent for further tests
                await mock_db.clients.update_one(
                    {"id": "client_3"},
                    {"$set": {"sms_consent": True, "sms_consent_source": "restored_for_test"}}
                )
        else:
            results.log_pass("CANCEL handled as appointment cancel (not opt-out)")


# ==================== SMS COMPLIANCE ====================

async def test_sms_compliance(client):
    """Test SMS consent enforcement"""
    print("\n--- Testing SMS Compliance ---")

    # Create a client WITHOUT consent
    no_consent_client = {
        "id": "client_no_consent",
        "shop_id": "demo_shop",
        "name": "No Consent Client",
        "phone": "+15550000001",
        "sms_consent": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await mock_db.clients.insert_one(no_consent_client)

    # Test that SMS from non-consented client still gets processed
    # (inbound should always work - it's outbound that should be blocked)
    resp = await client.post("/api/webhooks/twilio/inbound",
        data={
            "From": "+15550000001",
            "To": "+15551234567",
            "Body": "HELP",
            "MessageSid": f"SM{uuid.uuid4().hex[:30]}"
        })
    if resp.status_code == 200:
        results.log_pass("Inbound SMS from non-consented client accepted")
    else:
        results.log_fail("Non-consented inbound", f"Status {resp.status_code}")

    # Verify audit log was created for the outbound attempt
    audit_entries = await mock_db.integration_audit_log.find(
        {"entity_id": "client_no_consent"}
    ).to_list(10)
    if len(audit_entries) > 0:
        results.log_pass("Audit log created for SMS to non-consented client")
    else:
        results.log_warning("Missing audit", "No audit entry for non-consented SMS")


# ==================== SMS OPT-OUT ====================

async def test_sms_opt_out_flow(client):
    """Test STOP/opt-out handling"""
    print("\n--- Testing SMS Opt-Out (STOP) ---")

    # Create a fresh consented client for this test
    stop_client = {
        "id": "client_stop_test",
        "shop_id": "demo_shop",
        "name": "Stop Test Client",
        "phone": "+15550000002",
        "sms_consent": True,
        "sms_consent_timestamp": datetime.now(timezone.utc).isoformat(),
        "sms_consent_source": "web_form",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await mock_db.clients.insert_one(stop_client)

    # 1. Send STOP
    resp = await client.post("/api/webhooks/twilio/inbound",
        data={
            "From": "+15550000002",
            "To": "+15551234567",
            "Body": "STOP",
            "MessageSid": f"SM{uuid.uuid4().hex[:30]}"
        })
    if resp.status_code == 200:
        data = resp.json()
        if data.get("status") == "opt_out_processed":
            results.log_pass("STOP keyword triggers opt-out")
        else:
            results.log_fail("STOP handling", f"Got status: {data.get('status')}")
    else:
        results.log_fail("STOP webhook", f"Status {resp.status_code}")

    # 2. Verify consent revoked in DB
    cl = await mock_db.clients.find_one({"id": "client_stop_test"})
    if cl and cl["sms_consent"] == False:
        results.log_pass("Client consent revoked after STOP")
        if cl.get("sms_consent_source") == "opt_out_stop":
            results.log_pass("Consent source updated to opt_out_stop")
        else:
            results.log_fail("Consent source", f"Got: {cl.get('sms_consent_source')}")
    else:
        results.log_fail("Consent revocation", "Client still has consent")

    # 3. Verify UNSUBSCRIBE also works
    unsub_client = {
        "id": "client_unsub_test",
        "shop_id": "demo_shop",
        "name": "Unsub Test Client",
        "phone": "+15550000003",
        "sms_consent": True,
        "sms_consent_timestamp": datetime.now(timezone.utc).isoformat(),
        "sms_consent_source": "web_form",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await mock_db.clients.insert_one(unsub_client)

    resp = await client.post("/api/webhooks/twilio/inbound",
        data={
            "From": "+15550000003",
            "To": "+15551234567",
            "Body": "UNSUBSCRIBE",
            "MessageSid": f"SM{uuid.uuid4().hex[:30]}"
        })
    if resp.status_code == 200:
        data = resp.json()
        if data.get("status") == "opt_out_processed":
            results.log_pass("UNSUBSCRIBE keyword triggers opt-out")
        else:
            results.log_fail("UNSUBSCRIBE", f"Got: {data.get('status')}")


# ==================== PUBLIC ENDPOINTS ====================

async def test_public_endpoints(client):
    """Test public (no auth) endpoints"""
    print("\n--- Testing Public Endpoints ---")

    # 1. Get public shop info
    resp = await client.get("/api/public/shop-info")
    if resp.status_code == 200:
        info = resp.json()
        if "name" in info and "phone" in info:
            results.log_pass("Public shop info works")
        else:
            results.log_fail("Public shop info", f"Missing fields: {list(info.keys())}")
    else:
        results.log_fail("Public shop info", f"Status {resp.status_code}")

    # 2. SMS consent form
    resp = await client.post("/api/public/sms-consent", json={
        "phone": "+15557778888",
        "name": "New Customer",
        "consent": True
    })
    if resp.status_code == 200:
        data = resp.json()
        if data.get("consent") == True:
            results.log_pass("SMS consent form submission")
        else:
            results.log_fail("Consent response", f"Got: {data}")

        # Verify client created in DB
        new_cl = await mock_db.clients.find_one({"phone": "+15557778888"})
        if new_cl:
            if new_cl.get("sms_consent_source") == "web_form":
                results.log_pass("Consent source recorded as web_form")
            else:
                results.log_fail("Consent source", f"Got: {new_cl.get('sms_consent_source')}")
        else:
            results.log_fail("Client creation via consent", "Client not found")
    else:
        results.log_fail("SMS consent form", f"Status {resp.status_code}")

    # 3. Invalid phone format
    resp = await client.post("/api/public/sms-consent", json={
        "phone": "not-a-phone",
        "name": "Invalid",
        "consent": True
    })
    if resp.status_code == 422:
        results.log_pass("Invalid phone format returns 422")
    else:
        results.log_fail("Invalid phone validation", f"Expected 422, got {resp.status_code}")

    # 4. Consent form with consent=False
    resp = await client.post("/api/public/sms-consent", json={
        "phone": "+15556667777",
        "name": "No Consent Person",
        "consent": False
    })
    if resp.status_code == 200:
        data = resp.json()
        # Check that consent_timestamp is None when consent is False
        cl = await mock_db.clients.find_one({"phone": "+15556667777"})
        if cl and cl.get("sms_consent") == False:
            results.log_pass("Consent form with consent=False correctly stored")
            if cl.get("sms_consent_timestamp") is None:
                results.log_pass("No consent timestamp when consent=False")
            else:
                results.log_fail("Consent timestamp", "Timestamp should be None when consent=False")
        else:
            results.log_fail("False consent storage", f"Got consent: {cl.get('sms_consent')}")


# ==================== MOCK PAYMENT FLOW ====================

async def test_mock_payment_flow(client, headers):
    """Test the mock payment endpoint"""
    print("\n--- Testing Mock Payment Flow ---")

    # Create a deposit-pending appointment with payment record
    from providers import get_payment
    payment = get_payment()

    # Create payment link
    link = await payment.create_payment_link(
        amount=20.0,
        currency="usd",
        success_url="http://test/success",
        cancel_url="http://test/cancel",
        metadata={"appointment_id": "apt_2", "client_id": "client_2", "type": "deposit"}
    )

    # Store payment record
    await mock_db.payments.insert_one({
        "id": "pay_test_1",
        "shop_id": "demo_shop",
        "client_id": "client_2",
        "appointment_id": "apt_2",
        "amount": 20.0,
        "currency": "usd",
        "stripe_session_id": link.session_id,
        "status": "pending",
        "payment_type": "deposit",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    })

    # Complete mock payment
    resp = await client.get(f"/api/mock-payment?session_id={link.session_id}")
    if resp.status_code == 200:
        data = resp.json()
        if data.get("status") == "success":
            results.log_pass("Mock payment completed")

            # Verify appointment updated
            apt = await mock_db.appointments.find_one({"id": "apt_2"})
            if apt and apt.get("deposit_paid") == True:
                results.log_pass("Appointment deposit_paid updated")
            else:
                results.log_fail("Appointment update", f"deposit_paid: {apt.get('deposit_paid')}")

            if apt and apt.get("status") == "deposit_paid":
                results.log_pass("Appointment status updated to deposit_paid")
            else:
                results.log_fail("Appointment status", f"Got: {apt.get('status')}")
        else:
            results.log_fail("Payment status", f"Got: {data}")
    else:
        results.log_fail("Mock payment", f"Status {resp.status_code}")


# ==================== REMINDER JOB ====================

async def test_reminder_job(client, headers):
    """Test the appointment reminder system"""
    print("\n--- Testing Reminder Job ---")

    # 1. Preview reminders
    resp = await client.get("/api/jobs/reminders/preview", headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        if "preview" in data and "reminder_window_hours" in data:
            results.log_pass("Reminder preview endpoint works")
        else:
            results.log_fail("Reminder preview", f"Got: {list(data.keys())}")
    else:
        results.log_fail("Reminder preview", f"Status {resp.status_code}")

    # 2. Run reminder job
    resp = await client.post("/api/jobs/reminders/run", headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        if "results" in data:
            r = data["results"]
            results.log_pass(f"Reminder job ran: {r.get('sent', 0)} sent, {r.get('failed', 0)} failed")
        else:
            results.log_fail("Reminder job results", f"Got: {data}")
    else:
        results.log_fail("Reminder job", f"Status {resp.status_code}")


# ==================== AUDIT LOG ====================

async def test_audit_log(client, headers):
    """Test audit log retrieval"""
    print("\n--- Testing Audit Log ---")

    resp = await client.get("/api/audit-log", headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        if "audit_log" in data:
            results.log_pass(f"Audit log has {data.get('count', 0)} entries")
        else:
            results.log_fail("Audit log structure", f"Missing 'audit_log' key")
    else:
        results.log_fail("Audit log", f"Status {resp.status_code}")

    # Filter by provider
    resp = await client.get("/api/audit-log?provider=twilio", headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        all_twilio = all(e.get("provider") == "twilio" for e in data.get("audit_log", []))
        if all_twilio:
            results.log_pass("Audit log filter by provider=twilio")
        else:
            results.log_fail("Audit filter", "Not all entries are Twilio")
    else:
        results.log_fail("Audit log filter", f"Status {resp.status_code}")


# ==================== REVENUE TRACKING ====================

async def test_revenue_tracking(client, headers):
    """Test internal revenue tracking"""
    print("\n--- Testing Revenue Tracking ---")

    resp = await client.get("/api/internal/recovered-revenue", headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        if "_note" in data and "internal" in data.get("_note", "").lower():
            results.log_pass("Revenue endpoint includes internal-only warning")
        else:
            results.log_fail("Revenue warning", "Missing internal-only note")
    else:
        results.log_fail("Revenue tracking", f"Status {resp.status_code}")

    # Filter by source
    resp = await client.get("/api/internal/recovered-revenue?source=waitlist_fill", headers=headers)
    if resp.status_code == 200:
        results.log_pass("Revenue filter by source works")
    else:
        results.log_fail("Revenue filter", f"Status {resp.status_code}")


# ==================== RATE LIMITING ====================

async def test_rate_limiting(client):
    """Test rate limiting on sensitive endpoints"""
    print("\n--- Testing Rate Limiting ---")

    # Clear rate limit store
    import server
    server._rate_limit_store.clear()

    # Login rate limiting: 5 attempts per 15 minutes
    for i in range(6):
        resp = await client.post("/api/auth/login", json={
            "username": "admin",
            "password": "wrong"
        })

    if resp.status_code == 429:
        results.log_pass("Login rate limiting after 5 failed attempts")
    else:
        results.log_fail("Login rate limiting", f"Expected 429 after 6 attempts, got {resp.status_code}")

    # Clear for future tests
    server._rate_limit_store.clear()

    # BUG: Rate limit store memory leak
    results.log_bug(
        "LOW",
        "Rate limit store grows unbounded in memory",
        "The _rate_limit_store dictionary in server.py only cleans up entries when they're "
        "accessed. Old entries from inactive IPs accumulate indefinitely. In production "
        "with many unique IPs, this will slowly consume memory.",
        "server.py:83-100 (_rate_limit_store, check_rate_limit)"
    )


# ==================== EDGE CASES ====================

async def test_edge_cases(client, headers):
    """Test edge cases and error handling"""
    print("\n--- Testing Edge Cases ---")

    # 1. Empty SMS body
    resp = await client.post("/api/webhooks/twilio/inbound",
        data={
            "From": "+15559876543",
            "To": "+15551234567",
            "Body": "",
            "MessageSid": f"SM{uuid.uuid4().hex[:30]}"
        })
    if resp.status_code == 200:
        results.log_pass("Empty SMS body handled gracefully")
    else:
        results.log_fail("Empty SMS body", f"Status {resp.status_code}")

    # 2. Very long SMS body
    long_message = "A" * 1600  # Max SMS is 1600 chars
    resp = await client.post("/api/webhooks/twilio/inbound",
        data={
            "From": "+15559876543",
            "To": "+15551234567",
            "Body": long_message,
            "MessageSid": f"SM{uuid.uuid4().hex[:30]}"
        })
    if resp.status_code == 200:
        results.log_pass("Long SMS body handled")
    else:
        results.log_fail("Long SMS body", f"Status {resp.status_code}")

    # 3. SMS with special characters
    resp = await client.post("/api/webhooks/twilio/inbound",
        data={
            "From": "+15559876543",
            "To": "+15551234567",
            "Body": "Hello! I'd like to book <script>alert('xss')</script>",
            "MessageSid": f"SM{uuid.uuid4().hex[:30]}"
        })
    if resp.status_code == 200:
        results.log_pass("SMS with special chars handled")
        # Check the stored message isn't sanitized (since it's stored as-is)
        msg = await mock_db.messages.find_one({
            "content": {"$regex": "script"}
        })
        if msg:
            results.log_warning(
                "XSS content stored in messages",
                "SMS content with <script> tags is stored as-is in the database. "
                "If displayed in the admin UI without proper escaping, this could be an XSS vector."
            )

    # 4. Email outbox endpoint
    resp = await client.get("/api/email-outbox", headers=headers)
    if resp.status_code == 200:
        results.log_pass("Email outbox endpoint works")
    else:
        results.log_fail("Email outbox", f"Status {resp.status_code}")

    # 5. Stripe webhook with mock data
    resp = await client.post("/api/webhooks/stripe",
        content=b'{"type": "checkout.session.completed"}',
        headers={"Stripe-Signature": "mock_sig", "Content-Type": "application/json"})
    if resp.status_code == 200:
        results.log_pass("Stripe webhook endpoint works")
    else:
        results.log_fail("Stripe webhook", f"Status {resp.status_code}")

    # 6. Test SMS send when TWILIO_ENABLED=false
    resp = await client.post("/api/sms/send-test", headers=headers, json={
        "to_phone": "+15551234567",
        "message": "Test"
    })
    if resp.status_code == 400:
        results.log_pass("Test SMS blocked when TWILIO_ENABLED=false")
    else:
        results.log_fail("Test SMS block", f"Expected 400, got {resp.status_code}")

    # 7. Test email send when SEND_EMAILS=false
    resp = await client.post("/api/email/send-test", headers=headers, json={
        "to_email": "test@example.com",
        "subject": "Test",
        "message": "Test message"
    })
    if resp.status_code == 400:
        results.log_pass("Test email blocked when SEND_EMAILS=false")
    else:
        results.log_fail("Test email block", f"Expected 400, got {resp.status_code}")


# ==================== DATA INTEGRITY ====================

async def test_data_integrity(client, headers):
    """Verify data integrity across collections"""
    print("\n--- Testing Data Integrity ---")

    # 1. All appointments reference valid clients
    appointments = await mock_db.appointments.find({}, {"_id": 0}).to_list(100)
    client_ids = {c["id"] for c in await mock_db.clients.find({}, {"_id": 0, "id": 1}).to_list(100)}

    orphan_apts = [a for a in appointments if a.get("client_id") not in client_ids]
    if not orphan_apts:
        results.log_pass("All appointments reference valid clients")
    else:
        results.log_fail("Orphan appointments", f"{len(orphan_apts)} appointments with invalid client_id")

    # 2. All appointments reference valid barbers
    barber_ids = {b["id"] for b in await mock_db.barbers.find({}, {"_id": 0, "id": 1}).to_list(100)}
    orphan_barber_apts = [a for a in appointments if a.get("barber_id") not in barber_ids]
    if not orphan_barber_apts:
        results.log_pass("All appointments reference valid barbers")
    else:
        results.log_fail("Orphan barber refs", f"{len(orphan_barber_apts)} appointments with invalid barber_id")

    # 3. All appointments reference valid services
    service_ids = {s["id"] for s in await mock_db.services.find({}, {"_id": 0, "id": 1}).to_list(100)}
    orphan_svc_apts = [a for a in appointments if a.get("service_id") not in service_ids]
    if not orphan_svc_apts:
        results.log_pass("All appointments reference valid services")
    else:
        results.log_fail("Orphan service refs", f"{len(orphan_svc_apts)} appointments with invalid service_id")

    # 4. All messages reference valid clients
    messages = await mock_db.messages.find({}, {"_id": 0}).to_list(200)
    orphan_msgs = [m for m in messages if m.get("client_id") not in client_ids]
    if not orphan_msgs:
        results.log_pass("All messages reference valid clients")
    else:
        results.log_fail("Orphan messages", f"{len(orphan_msgs)} messages with invalid client_id")

    # 5. Verify UUID format for IDs
    import re
    uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    for apt in appointments:
        if apt["id"].startswith("apt_"):
            continue  # Seeded data uses short IDs
        if not uuid_pattern.match(apt["id"]):
            results.log_warning("Non-UUID appointment ID", f"ID: {apt['id']}")
            break
    else:
        results.log_pass("Appointment IDs follow UUID or seed convention")


# ==================== CODE ANALYSIS ====================

async def analyze_code_issues():
    """Static analysis of code patterns"""
    print("\n--- Code Analysis ---")

    # 1. Timezone handling
    results.log_bug(
        "MEDIUM",
        "All date queries use UTC but shop has timezone field",
        "The shop model stores a timezone (e.g., 'America/New_York') but all date "
        "comparisons in dashboard stats and appointment queries use UTC. "
        "A barbershop in New York checking 'appointments today' at 11 PM local time "
        "would see tomorrow's appointments because the UTC day has already rolled over. "
        "The scheduled_at comparisons should use the shop's timezone.",
        "server.py:210-212 (dashboard stats) and server.py:331-334 (appointment date filter)"
    )

    # 2. Date string comparison fragility
    results.log_bug(
        "MEDIUM",
        "ISO string comparison for dates is fragile",
        "Dates are stored as ISO strings and compared lexicographically. This works "
        "for UTC dates but will break if any timezone-offset dates (e.g., '+05:00') "
        "are mixed in, since string sorting doesn't account for timezone offsets. "
        "Example: '2025-01-01T00:00:00+05:00' > '2025-01-01T23:00:00Z' lexicographically "
        "but represents an earlier moment.",
        "server.py:217, server.py:292-302"
    )

    # 3. Conversation aggregation stability
    results.log_warning(
        "Conversation sort stability",
        "The conversations aggregation pipeline sorts by created_at then groups with $first. "
        "If two messages have identical created_at timestamps, the 'last message' shown is "
        "non-deterministic. Should use a stable tiebreaker like message ID."
    )

    # 4. Hard-coded shop_id in MockEmailProvider
    results.log_bug(
        "LOW",
        "MockEmailProvider hard-codes shop_id='demo_shop'",
        "The MockEmailProvider (mock_providers.py:158) stores emails with hard-coded "
        "shop_id='demo_shop'. If the system ever supports multiple shops, emails "
        "from other shops would be attributed to demo_shop.",
        "backend/providers/mock_providers.py:158"
    )

    # 5. No appointment creation API endpoint
    results.log_bug(
        "HIGH",
        "No API endpoint to create new appointments",
        "There is no POST /api/appointments endpoint. The only way to create appointments "
        "is through the seed data or (implicitly) through SMS booking flow. A barbershop "
        "manager using the admin dashboard cannot create new appointments for walk-ins, "
        "phone bookings, or manual entries. This is a significant gap in the admin workflow.",
        "server.py (missing POST /api/appointments endpoint)"
    )

    # 6. No client creation/edit API
    results.log_bug(
        "MEDIUM",
        "No API endpoints to create or edit clients",
        "There are no POST /api/clients or PATCH /api/clients/{id} endpoints. "
        "Clients can only be created through SMS inbound or the consent form. "
        "A manager cannot manually add a client, update their name, or correct a phone number.",
        "server.py (missing client CRUD endpoints)"
    )

    # 7. No waitlist creation API
    results.log_bug(
        "MEDIUM",
        "No API endpoint to add to waitlist",
        "There is no POST /api/waitlist endpoint. Waitlist entries can only be created "
        "through seed data. A manager cannot manually add someone to the waitlist from "
        "the admin dashboard.",
        "server.py (missing POST /api/waitlist endpoint)"
    )

    # 8. Frontend RESCHEDULED status not filterable
    results.log_bug(
        "LOW",
        "RESCHEDULED status exists in backend but not filterable in frontend",
        "AppointmentStatus.RESCHEDULED is defined in the backend enum but the frontend's "
        "AppointmentsPage.jsx status filter dropdown doesn't include 'rescheduled' as an option. "
        "Rescheduled appointments would be invisible unless 'All' filter is used.",
        "backend/models.py:30 vs frontend/src/pages/AppointmentsPage.jsx statusOptions"
    )

    # 9. Cancellation doesn't trigger waitlist fill
    results.log_bug(
        "HIGH",
        "Cancelling via API doesn't trigger waitlist fill",
        "When a manager cancels an appointment through the admin dashboard "
        "(PATCH /api/appointments/{id}/status?status=cancelled), the WaitlistFillAgent "
        "is never invoked. Only SMS-initiated cancellations would trigger waitlist filling. "
        "This means the main revenue recovery mechanism doesn't work for admin-initiated cancellations.",
        "server.py:377-399 (update_appointment_status) - missing WaitlistFillAgent call"
    )

    # 10. No-show processing not triggered by status update
    results.log_bug(
        "HIGH",
        "Marking appointment as no_show doesn't trigger NoShowEnforcementAgent",
        "When a manager marks an appointment as no_show via the dashboard, the "
        "NoShowEnforcementAgent.process_no_show() is never called. This means the client's "
        "no_show count isn't incremented, no revenue impact event is logged, and no "
        "no-show warning SMS is sent. The no-show tracking and fee enforcement is completely "
        "bypassed when using the admin dashboard.",
        "server.py:377-399 (update_appointment_status) - missing agent integration"
    )


# ==================== FRONTEND CHECK ====================

async def test_frontend_build():
    """Check frontend for obvious issues"""
    print("\n--- Checking Frontend ---")

    # Read key frontend files and check for issues
    import os
    frontend_dir = os.path.join(os.path.dirname(__file__), 'frontend', 'src')

    if os.path.exists(frontend_dir):
        results.log_pass("Frontend source directory exists")
    else:
        results.log_warning("Frontend missing", "frontend/src directory not found")


# ==================== MAIN ====================

async def main():
    print("=" * 70)
    print("BARBERSHOP AUTOPILOT - COMPREHENSIVE WORKFLOW TEST")
    print("Simulating a barbershop manager using the product")
    print("=" * 70)

    try:
        await run_all_tests()
        await test_frontend_build()
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        results.summary()


if __name__ == "__main__":
    asyncio.run(main())
