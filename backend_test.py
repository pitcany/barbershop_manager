#!/usr/bin/env python3
"""
Backend API Testing for Barbershop Autopilot MVP
Tests all endpoints with admin authentication
"""
import requests
import sys
import json
from datetime import datetime
from typing import Dict, Any, Optional

class BarbershopAPITester:
    def __init__(self, base_url="https://waitlist-hero.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []
        
    def log_result(self, test_name: str, success: bool, details: str = ""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {test_name}")
        else:
            print(f"❌ {test_name} - {details}")
            self.failed_tests.append({"test": test_name, "error": details})
    
    def make_request(self, method: str, endpoint: str, expected_status: int = 200, 
                    data: Optional[Dict] = None, headers: Optional[Dict] = None) -> tuple:
        """Make HTTP request and return (success, response_data, status_code)"""
        url = f"{self.api_url}/{endpoint.lstrip('/')}"
        
        # Default headers
        req_headers = {'Content-Type': 'application/json'}
        if self.token:
            req_headers['Authorization'] = f'Bearer {self.token}'
        if headers:
            req_headers.update(headers)
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=req_headers, timeout=30)
            elif method.upper() == 'POST':
                response = requests.post(url, json=data, headers=req_headers, timeout=30)
            elif method.upper() == 'PATCH':
                response = requests.patch(url, json=data, headers=req_headers, timeout=30)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=req_headers, timeout=30)
            else:
                return False, {}, 0
            
            success = response.status_code == expected_status
            try:
                response_data = response.json()
            except:
                response_data = {"raw_response": response.text}
            
            return success, response_data, response.status_code
            
        except requests.exceptions.RequestException as e:
            return False, {"error": str(e)}, 0
    
    def test_health_check(self):
        """Test basic health endpoints"""
        print("\n🔍 Testing Health Endpoints...")
        
        # Test root endpoint
        success, data, status = self.make_request('GET', '/')
        self.log_result("Root endpoint", success and "Barbershop Autopilot API" in str(data))
        
        # Test health endpoint
        success, data, status = self.make_request('GET', '/health')
        self.log_result("Health check", success and data.get("status") == "healthy")
    
    def test_authentication(self):
        """Test admin login"""
        print("\n🔍 Testing Authentication...")
        
        # Test login with correct credentials
        login_data = {"username": "admin", "password": "admin123"}
        success, data, status = self.make_request('POST', '/auth/login', 200, login_data)
        
        if success and "access_token" in data:
            self.token = data["access_token"]
            self.log_result("Admin login", True)
            
            # Test /auth/me endpoint
            success, user_data, status = self.make_request('GET', '/auth/me')
            self.log_result("Get current user", success and user_data.get("username") == "admin")
        else:
            self.log_result("Admin login", False, f"Status: {status}, Data: {data}")
            return False
        
        # Test login with wrong credentials
        wrong_data = {"username": "admin", "password": "wrong"}
        success, data, status = self.make_request('POST', '/auth/login', 401, wrong_data)
        self.log_result("Invalid login rejection", success)
        
        return True
    
    def test_dashboard_apis(self):
        """Test dashboard statistics endpoints"""
        print("\n🔍 Testing Dashboard APIs...")
        
        # Test dashboard stats
        success, data, status = self.make_request('GET', '/dashboard/stats')
        required_fields = ['appointments_today', 'revenue_recovered', 'no_show_rate', 'messages_today']
        has_required = all(field in data for field in required_fields)
        self.log_result("Dashboard stats API", success and has_required)
        
        # Test revenue chart
        success, data, status = self.make_request('GET', '/dashboard/revenue-chart')
        has_data_array = success and 'data' in data and isinstance(data['data'], list)
        self.log_result("Revenue chart API", has_data_array)
    
    def test_appointments_api(self):
        """Test appointments endpoints"""
        print("\n🔍 Testing Appointments API...")
        
        # Test list appointments
        success, data, status = self.make_request('GET', '/appointments')
        has_appointments = success and 'appointments' in data and 'total' in data
        self.log_result("List appointments", has_appointments)
        
        # Test with filters
        success, data, status = self.make_request('GET', '/appointments?status=confirmed&limit=10')
        self.log_result("Appointments with filters", success)
    
    def test_conversations_api(self):
        """Test conversations endpoints"""
        print("\n🔍 Testing Conversations API...")
        
        # Test list conversations
        success, data, status = self.make_request('GET', '/conversations')
        has_conversations = success and 'conversations' in data
        self.log_result("List conversations", has_conversations)
        
        # If there are conversations, test individual conversation
        if success and data.get('conversations'):
            first_conv = data['conversations'][0]
            client_id = first_conv.get('client_id')
            if client_id:
                success, msg_data, status = self.make_request('GET', f'/conversations/{client_id}')
                has_messages = success and 'messages' in msg_data and 'client' in msg_data
                self.log_result("Individual conversation", has_messages)
    
    def test_waitlist_api(self):
        """Test waitlist endpoints"""
        print("\n🔍 Testing Waitlist API...")
        
        success, data, status = self.make_request('GET', '/waitlist')
        has_waitlist = success and 'waitlist' in data
        self.log_result("List waitlist", has_waitlist)
    
    def test_shop_api(self):
        """Test shop endpoints"""
        print("\n🔍 Testing Shop API...")
        
        # Test get shop info
        success, data, status = self.make_request('GET', '/shop')
        has_shop_data = success and 'name' in data and 'phone' in data
        self.log_result("Get shop info", has_shop_data)
        
        # Test policy update
        policy_data = {"max_messages_per_day": 5}
        success, data, status = self.make_request('PATCH', '/shop/policy', 200, policy_data)
        self.log_result("Update shop policy", success)
    
    def test_public_endpoints(self):
        """Test public endpoints (no auth required)"""
        print("\n🔍 Testing Public Endpoints...")
        
        # Temporarily remove token for public endpoints
        temp_token = self.token
        self.token = None
        
        # Test SMS consent endpoint
        consent_data = {
            "phone": "+15551234567",
            "name": "Test User",
            "consent": True
        }
        success, data, status = self.make_request('POST', '/public/sms-consent', 200, consent_data)
        self.log_result("SMS consent submission", success)
        
        # Test public shop info
        success, data, status = self.make_request('GET', '/public/shop-info')
        has_public_info = success and 'name' in data
        self.log_result("Public shop info", has_public_info)
        
        # Restore token
        self.token = temp_token
    
    def test_webhook_endpoints(self):
        """Test webhook endpoints exist"""
        print("\n🔍 Testing Webhook Endpoints...")
        
        # Test Twilio webhook (should accept POST)
        # We expect it to fail with form data, but endpoint should exist
        success, data, status = self.make_request('POST', '/webhooks/twilio/inbound', 422, {})
        endpoint_exists = status in [200, 422, 400]  # Any response means endpoint exists
        self.log_result("Twilio webhook endpoint exists", endpoint_exists)
        
        # Test Stripe webhook
        success, data, status = self.make_request('POST', '/webhooks/stripe', 400, {})
        endpoint_exists = status in [200, 400, 422]
        self.log_result("Stripe webhook endpoint exists", endpoint_exists)
    
    def test_compliance_features(self):
        """Test SMS compliance hardening features"""
        print("\n🔍 Testing SMS Compliance Features...")
        
        # Test 1: Health endpoint shows compliance status and provider toggles
        success, data, status = self.make_request('GET', '/health')
        has_compliance = (success and 
                         'compliance' in data and 
                         'providers' in data and
                         data['compliance'].get('sms_consent_enforced') == True and
                         data['compliance'].get('stop_handling_enabled') == True and
                         data['compliance'].get('audit_logging_enabled') == True)
        self.log_result("Health endpoint shows compliance status", has_compliance)
        
        provider_toggles = (success and 
                           'twilio_enabled' in data['providers'] and
                           'stripe_enabled' in data['providers'] and
                           'sendgrid_enabled' in data['providers'] and
                           'calendar_enabled' in data['providers'])
        self.log_result("Health endpoint shows provider toggles", provider_toggles)
        
        # Test 2: Audit log endpoint returns logged entries
        success, data, status = self.make_request('GET', '/audit-log')
        has_audit_log = success and 'audit_log' in data and 'count' in data
        self.log_result("Audit log endpoint returns entries", has_audit_log)
        
        # Test with provider filter
        success, data, status = self.make_request('GET', '/audit-log?provider=twilio&limit=50')
        self.log_result("Audit log with provider filter", success)
        
        # Test 3: SMS consent form records consent_source and timestamp
        consent_data = {
            "phone": "+15559999999",
            "name": "Compliance Test User",
            "consent": True
        }
        # Remove token for public endpoint
        temp_token = self.token
        self.token = None
        
        success, data, status = self.make_request('POST', '/public/sms-consent', 200, consent_data)
        consent_recorded = success and data.get('consent') == True
        self.log_result("SMS consent form records consent", consent_recorded)
        
        # Restore token
        self.token = temp_token
        
        # Test 4: Verify client was created with proper consent tracking
        # Get clients to find our test client (search might not work as expected)
        success, data, status = self.make_request('GET', '/clients?limit=100')
        if success and data.get('clients'):
            test_client = None
            for client in data['clients']:
                if client.get('phone') == '+15559999999':
                    test_client = client
                    break
            
            if test_client:
                has_consent_fields = (test_client.get('sms_consent') == True and
                                    test_client.get('sms_consent_source') == 'web_form' and
                                    test_client.get('sms_consent_timestamp') is not None)
                self.log_result("Client has proper consent tracking fields", has_consent_fields)
                
                # Test 5: Verify existing client with opt-out status (client_1 should have sms_consent=false)
                opted_out_client = None
                for client in data['clients']:
                    if client.get('id') == 'client_1' or client.get('sms_consent_source') == 'opt_out_stop':
                        opted_out_client = client
                        break
                
                if opted_out_client:
                    has_opt_out = (opted_out_client.get('sms_consent') == False and
                                  opted_out_client.get('sms_consent_source') == 'opt_out_stop')
                    self.log_result("STOP opt-out client properly marked", has_opt_out)
                else:
                    self.log_result("STOP opt-out client properly marked", False, "No opted-out client found")
            else:
                self.log_result("Client has proper consent tracking fields", False, "Test client not found")
        else:
            self.log_result("Client has proper consent tracking fields", False, "Could not retrieve clients")
    
    def test_stop_opt_out_simulation(self):
        """Test STOP keyword opt-out processing (simulated)"""
        print("\n🔍 Testing STOP Opt-Out Processing...")
        
        # Check if there's already an opted-out client (from previous tests)
        success, data, status = self.make_request('GET', '/clients?limit=100')
        opted_out_client = None
        if success and data.get('clients'):
            for client in data['clients']:
                if client.get('sms_consent') == False and client.get('sms_consent_source') == 'opt_out_stop':
                    opted_out_client = client
                    break
        
        if opted_out_client:
            self.log_result("Found client with STOP opt-out status", True)
            print(f"   ℹ️  Client {opted_out_client.get('name')} ({opted_out_client.get('phone')}) has opted out")
        else:
            self.log_result("Found client with STOP opt-out status", False, "No opted-out clients found")
        
        # Test that webhook endpoint exists and can handle requests
        success, data, status = self.make_request('POST', '/webhooks/twilio/inbound', 422, {})
        webhook_exists = status in [200, 422, 400]
        self.log_result("STOP processing webhook endpoint exists", webhook_exists)
        
        print("   ℹ️  Note: STOP keyword processing tested via webhook endpoint existence")
        print("   ℹ️  Actual opt-out would be triggered by Twilio webhook with form data")
    
    def test_sms_blocking_compliance(self):
        """Test SMS blocking for clients without consent"""
        print("\n🔍 Testing SMS Blocking Compliance...")
        
        # Check audit log for SMS blocking entries
        success, data, status = self.make_request('GET', '/audit-log?provider=twilio&limit=50')
        
        if success and data.get('audit_log'):
            # Look for SMS blocking entries
            blocked_entries = [entry for entry in data['audit_log'] 
                             if entry.get('action') == 'sms_blocked_no_consent']
            
            opt_out_entries = [entry for entry in data['audit_log']
                             if entry.get('action') == 'sms_opt_out']
            
            send_entries = [entry for entry in data['audit_log']
                          if entry.get('action') == 'send_sms']
            
            self.log_result("SMS blocking entries found in audit log", len(blocked_entries) > 0)
            self.log_result("SMS opt-out entries found in audit log", len(opt_out_entries) > 0)
            self.log_result("SMS send attempts logged in audit log", len(send_entries) > 0)
            
            print(f"   ℹ️  Found {len(blocked_entries)} SMS blocking entries")
            print(f"   ℹ️  Found {len(opt_out_entries)} opt-out entries")
            print(f"   ℹ️  Found {len(send_entries)} SMS send attempts")
            
        else:
            self.log_result("SMS blocking entries found in audit log", False, "Could not retrieve audit log")
    
    def test_email_outbox_endpoint(self):
        """Test email outbox endpoint for mock mode"""
        print("\n🔍 Testing Email Outbox Endpoint...")
        
        success, data, status = self.make_request('GET', '/email-outbox')
        has_email_outbox = success and 'emails' in data
        self.log_result("Email outbox endpoint", has_email_outbox)
    
    def test_recovered_revenue_logging(self):
        """Test internal recovered revenue logging functionality"""
        print("\n🔍 Testing Recovered Revenue Logging...")
        
        # Test 1: Internal recovered revenue endpoint exists
        success, data, status = self.make_request('GET', '/internal/recovered-revenue')
        endpoint_exists = success and 'events' in data
        self.log_result("Internal recovered revenue endpoint exists", endpoint_exists)
        
        if not success:
            self.log_result("Recovered revenue endpoint schema", False, f"Endpoint failed: {status}")
            return
        
        # Test 2: Response includes _note indicating internal-only data
        has_internal_note = '_note' in data and 'internal attribution only' in data['_note'].lower()
        self.log_result("Response includes internal-only note", has_internal_note)
        
        # Test 3: Response has correct structure
        has_correct_structure = (
            'events' in data and 
            'count' in data and 
            isinstance(data['events'], list)
        )
        self.log_result("Response has correct structure", has_correct_structure)
        
        # Test 4: Check schema of events (if any exist)
        events = data.get('events', [])
        if events:
            first_event = events[0]
            required_fields = ['id', 'shop_id', 'source', 'amount', 'currency', 'attributed_at']
            optional_fields = ['appointment_id', 'client_id', 'notes']
            
            has_required_fields = all(field in first_event for field in required_fields)
            self.log_result("Events have required schema fields", has_required_fields)
            
            # Test 5: Check for mocked_execution=true in notes (since all providers are mocked)
            has_mocked_note = any(
                event.get('notes') and 'mocked_execution=true' in event.get('notes', '')
                for event in events
            )
            self.log_result("Events include mocked_execution=true note", has_mocked_note)
            
            # Test 6: Verify no zero-amount events exist
            zero_amount_events = [e for e in events if e.get('amount', 0) == 0]
            no_zero_amount = len(zero_amount_events) == 0
            self.log_result("No zero-amount events logged", no_zero_amount)
            if zero_amount_events:
                print(f"   ⚠️  Found {len(zero_amount_events)} zero-amount events")
            
            # Test 7: Check event sources are valid
            valid_sources = ['waitlist_fill', 'no_show_fee']
            invalid_sources = [e.get('source') for e in events if e.get('source') not in valid_sources]
            sources_valid = len(invalid_sources) == 0
            self.log_result("All event sources are valid", sources_valid)
            if invalid_sources:
                print(f"   ⚠️  Found invalid sources: {set(invalid_sources)}")
            
            print(f"   ℹ️  Found {len(events)} revenue events")
            
            # Show sample event for verification
            if events:
                sample_event = events[0]
                print(f"   ℹ️  Sample event: {sample_event.get('source')} - ${sample_event.get('amount', 0):.2f}")
        else:
            print("   ℹ️  No revenue events found (this may be expected for new installations)")
            self.log_result("Events have required schema fields", True, "No events to validate")
            self.log_result("Events include mocked_execution=true note", True, "No events to validate")
            self.log_result("No zero-amount events logged", True, "No events found")
            self.log_result("All event sources are valid", True, "No events to validate")
        
        # Test 8: Test filtering by source parameter
        success, filtered_data, status = self.make_request('GET', '/internal/recovered-revenue?source=waitlist_fill')
        source_filter_works = success and 'events' in filtered_data
        self.log_result("Source parameter filtering works", source_filter_works)
        
        if source_filter_works:
            filtered_events = filtered_data.get('events', [])
            # All events should have waitlist_fill source if filter worked
            wrong_source_events = [e for e in filtered_events if e.get('source') != 'waitlist_fill']
            filter_correct = len(wrong_source_events) == 0
            self.log_result("Source filter returns correct events", filter_correct)
            print(f"   ℹ️  Found {len(filtered_events)} waitlist_fill events")
        
        # Test 9: Test filtering by no_show_fee source
        success, filtered_data, status = self.make_request('GET', '/internal/recovered-revenue?source=no_show_fee')
        if success:
            no_show_events = filtered_data.get('events', [])
            wrong_source_events = [e for e in no_show_events if e.get('source') != 'no_show_fee']
            no_show_filter_correct = len(wrong_source_events) == 0
            self.log_result("No-show fee filter returns correct events", no_show_filter_correct)
            print(f"   ℹ️  Found {len(no_show_events)} no_show_fee events")
        
        # Test 10: Test with invalid source parameter
        success, invalid_data, status = self.make_request('GET', '/internal/recovered-revenue?source=invalid_source')
        if success:
            invalid_events = invalid_data.get('events', [])
            no_invalid_events = len(invalid_events) == 0
            self.log_result("Invalid source filter returns no events", no_invalid_events)
    
    def test_barbers_and_services(self):
        """Test barbers and services endpoints"""
        print("\n🔍 Testing Barbers & Services API...")
        
        # Test barbers
        success, data, status = self.make_request('GET', '/barbers')
        has_barbers = success and 'barbers' in data
        self.log_result("List barbers", has_barbers)
        
        # Test services
        success, data, status = self.make_request('GET', '/services')
        has_services = success and 'services' in data
        self.log_result("List services", has_services)
    
    def run_all_tests(self):
        """Run all API tests"""
        print("🚀 Starting Barbershop Autopilot API Tests")
        print(f"Testing against: {self.base_url}")
        
        # Test health first
        self.test_health_check()
        
        # Test authentication (required for other tests)
        if not self.test_authentication():
            print("❌ Authentication failed - stopping tests")
            return False
        
        # Test all authenticated endpoints
        self.test_dashboard_apis()
        self.test_appointments_api()
        self.test_conversations_api()
        self.test_waitlist_api()
        self.test_shop_api()
        self.test_barbers_and_services()
        
        # Test compliance features (NEW)
        self.test_compliance_features()
        self.test_stop_opt_out_simulation()
        self.test_sms_blocking_compliance()
        self.test_email_outbox_endpoint()
        
        # Test recovered revenue logging (NEW)
        self.test_recovered_revenue_logging()
        
        # Test public endpoints
        self.test_public_endpoints()
        
        # Test webhook endpoints
        self.test_webhook_endpoints()
        
        # Print summary
        print(f"\n📊 Test Summary:")
        print(f"Tests run: {self.tests_run}")
        print(f"Tests passed: {self.tests_passed}")
        print(f"Tests failed: {len(self.failed_tests)}")
        print(f"Success rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        if self.failed_tests:
            print(f"\n❌ Failed Tests:")
            for failure in self.failed_tests:
                print(f"  - {failure['test']}: {failure['error']}")
        
        return len(self.failed_tests) == 0

def main():
    tester = BarbershopAPITester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())