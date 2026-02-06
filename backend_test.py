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
    def __init__(self, base_url="https://autopilot-barber.preview.emergentagent.com"):
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
        # Get clients to find our test client
        success, data, status = self.make_request('GET', '/clients?search=+15559999999')
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
            else:
                self.log_result("Client has proper consent tracking fields", False, "Test client not found")
        else:
            self.log_result("Client has proper consent tracking fields", False, "Could not retrieve clients")
    
    def test_stop_opt_out_simulation(self):
        """Test STOP keyword opt-out processing (simulated)"""
        print("\n🔍 Testing STOP Opt-Out Processing...")
        
        # First, create a client with consent via the consent form
        consent_data = {
            "phone": "+15551111111",
            "name": "STOP Test User", 
            "consent": True
        }
        
        # Remove token for public endpoint
        temp_token = self.token
        self.token = None
        
        success, data, status = self.make_request('POST', '/public/sms-consent', 200, consent_data)
        self.log_result("Created test client with consent", success)
        
        # Restore token
        self.token = temp_token
        
        # Verify client was created with consent
        success, data, status = self.make_request('GET', '/clients?search=+15551111111')
        test_client = None
        if success and data.get('clients'):
            for client in data['clients']:
                if client.get('phone') == '+15551111111':
                    test_client = client
                    break
        
        if test_client and test_client.get('sms_consent') == True:
            self.log_result("Test client has initial consent", True)
            
            # Note: We cannot directly test the Twilio webhook without form data
            # But we can verify the opt-out logic exists by checking the endpoint
            # The actual STOP processing would happen via Twilio webhook with form data
            
            # Test that webhook endpoint exists and can handle requests
            success, data, status = self.make_request('POST', '/webhooks/twilio/inbound', 422, {})
            webhook_exists = status in [200, 422, 400]
            self.log_result("STOP processing webhook endpoint exists", webhook_exists)
            
            print("   ℹ️  Note: STOP keyword processing tested via webhook endpoint existence")
            print("   ℹ️  Actual opt-out would be triggered by Twilio webhook with form data")
            
        else:
            self.log_result("Test client has initial consent", False, "Could not create test client")
    
    def test_email_outbox_endpoint(self):
        """Test email outbox endpoint for mock mode"""
        print("\n🔍 Testing Email Outbox Endpoint...")
        
        success, data, status = self.make_request('GET', '/email-outbox')
        has_email_outbox = success and 'emails' in data
        self.log_result("Email outbox endpoint", has_email_outbox)
    
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
        self.test_email_outbox_endpoint()
        
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