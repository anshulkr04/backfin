#!/usr/bin/env python3
"""
Comprehensive Test Script for Backfin Verification System API
Tests all endpoints and features
"""

import requests
import json
import time
from typing import Optional, Dict, Any

# Configuration
BASE_URL = "http://localhost:5002"
API_PREFIX = "/api/admin"

# Test credentials
TEST_USER = {
    "email": "test_admin@backfin.com",
    "password": "TestPassword123!",
    "name": "Test Admin User"
}

# Test PDF URL
TEST_PDF_URL = "https://www.bseindia.com/xml-data/corpfiling/AttachLive/05e93a89-f832-45ff-82b5-5cb78526eda3.pdf"

class Colors:
    """ANSI color codes"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(text: str):
    """Print a formatted header"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text.center(80)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}\n")

def print_test(test_name: str):
    """Print test name"""
    print(f"{Colors.BOLD}{Colors.BLUE}🧪 TEST: {test_name}{Colors.RESET}")

def print_success(message: str):
    """Print success message"""
    print(f"{Colors.GREEN}✅ {message}{Colors.RESET}")

def print_error(message: str):
    """Print error message"""
    print(f"{Colors.RED}❌ {message}{Colors.RESET}")

def print_info(message: str):
    """Print info message"""
    print(f"{Colors.YELLOW}ℹ️  {message}{Colors.RESET}")

def print_response(data: Dict[Any, Any], truncate: int = 200):
    """Print formatted response"""
    response_str = json.dumps(data, indent=2)
    if len(response_str) > truncate:
        response_str = response_str[:truncate] + "..."
    print(f"{Colors.CYAN}{response_str}{Colors.RESET}")

# Global variables
auth_token: Optional[str] = None
test_corp_id: Optional[str] = None

def test_health_check():
    """Test 1: Health Check Endpoint"""
    print_test("Health Check")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print_success(f"Health check passed - Status: {data['status']}")
            print_response(data)
            return True
        else:
            print_error(f"Health check failed - Status: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Health check error: {e}")
        return False

def test_register():
    """Test 2: Register New Admin User"""
    print_test("Register New Admin User")
    try:
        response = requests.post(
            f"{BASE_URL}{API_PREFIX}/auth/register",
            json=TEST_USER,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            global auth_token
            auth_token = data['access_token']
            print_success("Registration successful")
            print_info(f"User ID: {data['user']['id']}")
            print_info(f"Email: {data['user']['email']}")
            print_info(f"Token: {auth_token[:20]}...")
            return True
        elif response.status_code == 400 and "already registered" in response.text:
            print_info("User already exists, will try login")
            return test_login()
        else:
            print_error(f"Registration failed - Status: {response.status_code}")
            print_response(response.json())
            return False
    except Exception as e:
        print_error(f"Registration error: {e}")
        return False

def test_login():
    """Test 3: Login with Credentials"""
    print_test("Login with Existing User")
    try:
        response = requests.post(
            f"{BASE_URL}{API_PREFIX}/auth/login",
            json={
                "email": TEST_USER["email"],
                "password": TEST_USER["password"]
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            global auth_token
            auth_token = data['access_token']
            print_success("Login successful")
            print_info(f"Token: {auth_token[:20]}...")
            return True
        else:
            print_error(f"Login failed - Status: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Login error: {e}")
        return False

def test_get_current_user():
    """Test 4: Get Current User Info"""
    print_test("Get Current User Info")
    try:
        response = requests.get(
            f"{BASE_URL}{API_PREFIX}/auth/me",
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success("Got user info")
            print_response(data)
            return True
        else:
            print_error(f"Get user info failed - Status: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Get user info error: {e}")
        return False

def test_get_announcements():
    """Test 5: Get Unverified Announcements"""
    print_test("Get Unverified Announcements")
    try:
        response = requests.get(
            f"{BASE_URL}{API_PREFIX}/announcements?verified=false&limit=5",
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success(f"Got {data['count']} announcements")
            if data['count'] > 0:
                global test_corp_id
                test_corp_id = data['announcements'][0]['corp_id']
                print_info(f"Test corp_id: {test_corp_id}")
                print_response(data['announcements'][0], truncate=300)
            return True
        else:
            print_error(f"Get announcements failed - Status: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Get announcements error: {e}")
        return False

def test_get_single_announcement():
    """Test 6: Get Single Announcement"""
    print_test("Get Single Announcement")
    if not test_corp_id:
        print_info("Skipping - No test corp_id available")
        return True
    
    try:
        response = requests.get(
            f"{BASE_URL}{API_PREFIX}/announcements/{test_corp_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success("Got announcement details")
            print_response(data, truncate=300)
            return True
        else:
            print_error(f"Get announcement failed - Status: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Get announcement error: {e}")
        return False

def test_update_announcement():
    """Test 7: Update Announcement"""
    print_test("Update Announcement")
    if not test_corp_id:
        print_info("Skipping - No test corp_id available")
        return True
    
    try:
        update_data = {
            "summary": "Updated summary via API test",
            "headline": "Test Headline Update"
        }
        
        response = requests.patch(
            f"{BASE_URL}{API_PREFIX}/announcements/{test_corp_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=update_data,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success("Announcement updated")
            print_response(data)
            return True
        else:
            print_error(f"Update failed - Status: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Update error: {e}")
        return False

def test_generate_content_simple():
    """Test 8: Generate AI Content (Simple)"""
    print_test("Generate AI Content - Simple Request")
    try:
        payload = {
            "fileurl": TEST_PDF_URL,
            "model": "gemini-2.5-flash-lite"
        }
        
        print_info("Generating content (this may take 10-30 seconds)...")
        response = requests.post(
            f"{BASE_URL}{API_PREFIX}/generate-content",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success("Content generated successfully")
            print_info(f"Model: {data['model_used']}")
            print_info(f"Category: {data['category']}")
            print_info(f"Sentiment: {data['sentiment']}")
            print_info(f"Headline: {data['headline'][:80]}...")
            print_info(f"Summary: {data['ai_summary'][:100]}...")
            return True
        else:
            print_error(f"Generation failed - Status: {response.status_code}")
            print_response(response.json() if response.text else {"error": "No response"})
            return False
    except requests.Timeout:
        print_error("Request timed out (>60s)")
        return False
    except Exception as e:
        print_error(f"Generation error: {e}")
        return False

def test_generate_content_with_pages():
    """Test 9: Generate AI Content with Page Selection"""
    print_test("Generate AI Content - With Page Selection")
    try:
        payload = {
            "fileurl": TEST_PDF_URL,
            "model": "gemini-2.5-flash-lite",
            "pages": "1,3-5"
        }
        
        print_info("Generating content from pages 1, 3-5...")
        response = requests.post(
            f"{BASE_URL}{API_PREFIX}/generate-content",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success("Content generated with page selection")
            print_info(f"Category: {data['category']}")
            print_info(f"Sentiment: {data['sentiment']}")
            return True
        else:
            print_error(f"Generation failed - Status: {response.status_code}")
            return False
    except requests.Timeout:
        print_error("Request timed out")
        return False
    except Exception as e:
        print_error(f"Generation error: {e}")
        return False

def test_generate_content_with_context():
    """Test 10: Generate AI Content with Context"""
    print_test("Generate AI Content - With Previous Context")
    try:
        payload = {
            "fileurl": TEST_PDF_URL,
            "model": "gemini-2.5-flash-lite",
            "summary": "Previous summary for context",
            "headline": "Previous headline",
            "ai_summary": "Previous AI generated summary"
        }
        
        print_info("Generating content with context...")
        response = requests.post(
            f"{BASE_URL}{API_PREFIX}/generate-content",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success("Content generated with context")
            print_info(f"Model: {data['model_used']}")
            return True
        else:
            print_error(f"Generation failed - Status: {response.status_code}")
            return False
    except requests.Timeout:
        print_error("Request timed out")
        return False
    except Exception as e:
        print_error(f"Generation error: {e}")
        return False

def test_verify_announcement():
    """Test 11: Verify Announcement"""
    print_test("Verify Announcement")
    if not test_corp_id:
        print_info("Skipping - No test corp_id available")
        return True
    
    try:
        response = requests.post(
            f"{BASE_URL}{API_PREFIX}/announcements/{test_corp_id}/verify",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"notes": "Verified via API test"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success("Announcement verified")
            print_response(data)
            return True
        else:
            print_error(f"Verification failed - Status: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Verification error: {e}")
        return False

def test_get_stats():
    """Test 12: Get Statistics"""
    print_test("Get Verification Statistics")
    try:
        response = requests.get(
            f"{BASE_URL}{API_PREFIX}/stats",
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success("Got statistics")
            print_response(data)
            return True
        else:
            print_error(f"Get stats failed - Status: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Get stats error: {e}")
        return False

def test_unverify_announcement():
    """Test 13: Unverify Announcement"""
    print_test("Unverify Announcement")
    if not test_corp_id:
        print_info("Skipping - No test corp_id available")
        return True
    
    try:
        response = requests.post(
            f"{BASE_URL}{API_PREFIX}/announcements/{test_corp_id}/unverify",
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success("Announcement unverified")
            print_response(data)
            return True
        else:
            print_error(f"Unverify failed - Status: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Unverify error: {e}")
        return False

def test_logout():
    """Test 14: Logout"""
    print_test("Logout")
    try:
        response = requests.post(
            f"{BASE_URL}{API_PREFIX}/auth/logout",
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success("Logged out successfully")
            print_response(data)
            return True
        else:
            print_error(f"Logout failed - Status: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Logout error: {e}")
        return False

def run_all_tests():
    """Run all tests"""
    print_header("BACKFIN VERIFICATION SYSTEM - COMPREHENSIVE API TESTS")
    
    print_info(f"Base URL: {BASE_URL}")
    print_info(f"API Prefix: {API_PREFIX}")
    print_info(f"Test User: {TEST_USER['email']}\n")
    
    tests = [
        ("Health Check", test_health_check),
        ("User Registration", test_register),
        ("Get Current User", test_get_current_user),
        ("Get Announcements", test_get_announcements),
        ("Get Single Announcement", test_get_single_announcement),
        ("Update Announcement", test_update_announcement),
        ("Generate AI Content (Simple)", test_generate_content_simple),
        ("Generate AI Content (With Pages)", test_generate_content_with_pages),
        ("Generate AI Content (With Context)", test_generate_content_with_context),
        ("Verify Announcement", test_verify_announcement),
        ("Get Statistics", test_get_stats),
        ("Unverify Announcement", test_unverify_announcement),
        ("Logout", test_logout),
    ]
    
    results = []
    start_time = time.time()
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
            print()  # Blank line between tests
            time.sleep(0.5)  # Small delay between tests
        except Exception as e:
            print_error(f"Test crashed: {e}")
            results.append((test_name, False))
            print()
    
    # Print summary
    end_time = time.time()
    duration = end_time - start_time
    
    print_header("TEST SUMMARY")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = f"{Colors.GREEN}✅ PASSED{Colors.RESET}" if result else f"{Colors.RED}❌ FAILED{Colors.RESET}"
        print(f"{test_name:.<60} {status}")
    
    print(f"\n{Colors.BOLD}Results: {passed}/{total} tests passed{Colors.RESET}")
    print(f"{Colors.BOLD}Duration: {duration:.2f} seconds{Colors.RESET}\n")
    
    if passed == total:
        print(f"{Colors.GREEN}{Colors.BOLD}🎉 ALL TESTS PASSED! 🎉{Colors.RESET}\n")
    else:
        print(f"{Colors.YELLOW}⚠️  Some tests failed. Please review the output above.{Colors.RESET}\n")

if __name__ == "__main__":
    try:
        run_all_tests()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Tests interrupted by user{Colors.RESET}\n")
    except Exception as e:
        print(f"\n\n{Colors.RED}Fatal error: {e}{Colors.RESET}\n")
