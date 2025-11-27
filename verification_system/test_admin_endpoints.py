"""
Test script for Admin API endpoints
Tests: Corporate Actions, Stock Price Refresh endpoints

Usage:
    python test_admin_endpoints.py

Expected Endpoints:
    - POST /api/admin/auth/register
    - POST /api/admin/auth/login
    - GET  /api/admin/corporate-actions
    - POST /api/admin/refresh-stock-price
"""

import requests
import json
from datetime import datetime, timedelta
import time
import random
import string

# Configuration
BASE_URL = "https://admin.anshulkr.com"  # Change to your API URL
API_PREFIX = "/api/admin"

# Generate random credentials for new test user
timestamp = int(time.time())
random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
TEST_USER = {
    "email": f"test_{timestamp}_{random_suffix}@backfin.com",
    "password": f"TestPass{timestamp}@{random_suffix}",
    "name": "Test API User"
}

# Global token storage
auth_token = None


def print_section(title):
    """Print a formatted section header"""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def print_response(response, description="Response"):
    """Pretty print response"""
    print(f"\n{description}:")
    print(f"Status Code: {response.status_code}")
    try:
        data = response.json()
        print(json.dumps(data, indent=2))
    except:
        print(response.text)
    print("-" * 80)


def register_user():
    """Register a test user"""
    print_section("1. REGISTER TEST USER")
    
    url = f"{BASE_URL}{API_PREFIX}/auth/register"
    headers = {"Content-Type": "application/json"}
    
    response = requests.post(url, json=TEST_USER, headers=headers)
    
    if response.status_code in [200, 201]:
        print(f"✅ User registered successfully: {TEST_USER['email']}")
        data = response.json()
        return data.get('access_token')
    elif response.status_code == 400 and "already exists" in response.text.lower():
        print(f"ℹ️  User already exists: {TEST_USER['email']}")
        return None
    else:
        print_response(response, "❌ Registration failed")
        return None


def login_user():
    """Login and get access token"""
    print_section("2. LOGIN")
    
    url = f"{BASE_URL}{API_PREFIX}/auth/login"
    headers = {"Content-Type": "application/json"}
    
    login_data = {
        "email": TEST_USER["email"],
        "password": TEST_USER["password"]
    }
    
    response = requests.post(url, json=login_data, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        token = data.get('access_token')
        print(f"✅ Login successful")
        print(f"Token: {token[:50]}...")
        return token
    else:
        print_response(response, "❌ Login failed")
        return None


def get_auth_headers():
    """Get authorization headers"""
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    }


def test_corporate_actions_basic():
    """Test basic corporate actions endpoint"""
    print_section("3. GET CORPORATE ACTIONS (Basic)")
    
    url = f"{BASE_URL}{API_PREFIX}/corporate-actions"
    params = {
        "page": 1,
        "page_size": 5
    }
    
    response = requests.get(url, params=params, headers=get_auth_headers())
    print_response(response, "Corporate Actions - Page 1 (5 records)")
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n📊 Summary:")
        print(f"   Total Count: {data.get('total_count', 0)}")
        print(f"   Current Page: {data.get('current_page', 0)}")
        print(f"   Total Pages: {data.get('total_pages', 0)}")
        print(f"   Records Returned: {data.get('count', 0)}")
        return True
    return False


def test_corporate_actions_with_filters():
    """Test corporate actions with filters"""
    print_section("4. GET CORPORATE ACTIONS (With Filters)")
    
    # Test 1: Filter by Exchange (NSE)
    print("\n📍 Test 4.1: Filter by Exchange = NSE")
    url = f"{BASE_URL}{API_PREFIX}/corporate-actions"
    params = {
        "page": 1,
        "page_size": 5,
        "exchange": "NSE"
    }
    
    response = requests.get(url, params=params, headers=get_auth_headers())
    if response.status_code == 200:
        data = response.json()
        print(f"✅ NSE Corporate Actions: {data.get('count', 0)} records")
        print(f"   Total NSE Actions: {data.get('total_count', 0)}")
    else:
        print_response(response, "❌ Failed")
    
    # Test 2: Filter by Exchange (BSE)
    print("\n📍 Test 4.2: Filter by Exchange = BSE")
    params["exchange"] = "BSE"
    
    response = requests.get(url, params=params, headers=get_auth_headers())
    if response.status_code == 200:
        data = response.json()
        print(f"✅ BSE Corporate Actions: {data.get('count', 0)} records")
        print(f"   Total BSE Actions: {data.get('total_count', 0)}")
    else:
        print_response(response, "❌ Failed")
    
    # Test 3: Filter by Date Range
    print("\n📍 Test 4.3: Filter by Date Range (Last 30 days)")
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    params = {
        "page": 1,
        "page_size": 10,
        "start_date": start_date,
        "end_date": end_date
    }
    
    response = requests.get(url, params=params, headers=get_auth_headers())
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Actions in date range: {data.get('count', 0)} records")
        print(f"   Date Range: {start_date} to {end_date}")
        print(f"   Total in range: {data.get('total_count', 0)}")
    else:
        print_response(response, "❌ Failed")
    
    # Test 4: Filter by Symbol
    print("\n📍 Test 4.4: Filter by Symbol (partial match)")
    params = {
        "page": 1,
        "page_size": 5,
        "symbol": "REL"  # Will match RELIANCE, etc.
    }
    
    response = requests.get(url, params=params, headers=get_auth_headers())
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Actions matching 'REL': {data.get('count', 0)} records")
        print(f"   Total matching: {data.get('total_count', 0)}")
    else:
        print_response(response, "❌ Failed")
    
    # Test 5: Combined Filters
    print("\n📍 Test 4.5: Combined Filters (NSE + Date Range)")
    params = {
        "page": 1,
        "page_size": 5,
        "exchange": "NSE",
        "start_date": start_date,
        "end_date": end_date
    }
    
    response = requests.get(url, params=params, headers=get_auth_headers())
    if response.status_code == 200:
        data = response.json()
        print(f"✅ NSE Actions in date range: {data.get('count', 0)} records")
        print(f"   Filters Applied:")
        print(f"      Exchange: {data['filters']['exchange']}")
        print(f"      Date Range: {data['filters']['start_date']} to {data['filters']['end_date']}")
    else:
        print_response(response, "❌ Failed")


def test_corporate_actions_pagination():
    """Test corporate actions pagination"""
    print_section("5. GET CORPORATE ACTIONS (Pagination)")
    
    url = f"{BASE_URL}{API_PREFIX}/corporate-actions"
    
    # Get first page
    print("\n📍 Test 5.1: Page 1")
    params = {"page": 1, "page_size": 3}
    response = requests.get(url, params=params, headers=get_auth_headers())
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Page 1: {data.get('count', 0)} records")
        print(f"   Has Next: {data.get('has_next', False)}")
        print(f"   Has Previous: {data.get('has_previous', False)}")
        
        # Get second page if available
        if data.get('has_next'):
            print("\n📍 Test 5.2: Page 2")
            params["page"] = 2
            response = requests.get(url, params=params, headers=get_auth_headers())
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Page 2: {data.get('count', 0)} records")
                print(f"   Has Next: {data.get('has_next', False)}")
                print(f"   Has Previous: {data.get('has_previous', False)}")
    else:
        print_response(response, "❌ Failed")


def test_corporate_actions_invalid():
    """Test corporate actions with invalid inputs"""
    print_section("6. GET CORPORATE ACTIONS (Error Handling)")
    
    url = f"{BASE_URL}{API_PREFIX}/corporate-actions"
    
    # Test 1: Invalid Exchange
    print("\n📍 Test 6.1: Invalid Exchange")
    params = {"exchange": "INVALID"}
    response = requests.get(url, params=params, headers=get_auth_headers())
    
    if response.status_code == 400:
        print(f"✅ Correctly rejected invalid exchange")
        print(f"   Error: {response.json().get('detail', 'Unknown error')}")
    else:
        print(f"❌ Expected 400, got {response.status_code}")
    
    # Test 2: Invalid Date Format
    print("\n📍 Test 6.2: Invalid Date Format")
    params = {"start_date": "2025-13-45"}  # Invalid date
    response = requests.get(url, params=params, headers=get_auth_headers())
    
    if response.status_code == 400:
        print(f"✅ Correctly rejected invalid date")
        print(f"   Error: {response.json().get('detail', 'Unknown error')}")
    else:
        print(f"❌ Expected 400, got {response.status_code}")


def test_refresh_stock_price():
    """Test stock price refresh endpoint"""
    print_section("7. REFRESH STOCK PRICE DATA")
    
    url = f"{BASE_URL}{API_PREFIX}/refresh-stock-price"
    
    # Test with security ID 542034
    print("\n📍 Test 7.1: Refresh Stock Price for Security ID: 542034")
    payload = {
        "securityid": 542034
    }
    
    print(f"🔄 Requesting refresh for security ID {payload['securityid']}...")
    print("⏳ This may take a few moments...")
    
    response = requests.post(url, json=payload, headers=get_auth_headers())
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n✅ Stock Price Refresh Successful!")
        print(f"   Security ID: {data.get('securityid')}")
        print(f"   Symbol: {data.get('symbol')}")
        print(f"   ISIN: {data.get('isin')}")
        print(f"   Exchange: {data.get('exchange')}")
        print(f"   Records Fetched: {data.get('records_fetched')}")
        print(f"   Date Range: {data.get('from_date')} to {data.get('to_date')}")
        print(f"   Message: {data.get('message')}")
    else:
        print_response(response, "❌ Stock Price Refresh Failed")


def test_refresh_stock_price_invalid():
    """Test stock price refresh with invalid input"""
    print_section("8. REFRESH STOCK PRICE (Error Handling)")
    
    url = f"{BASE_URL}{API_PREFIX}/refresh-stock-price"
    
    # Test 1: Invalid Security ID (doesn't exist)
    print("\n📍 Test 8.1: Non-existent Security ID")
    payload = {"securityid": 999999999}
    
    response = requests.post(url, json=payload, headers=get_auth_headers())
    
    if response.status_code == 200:
        data = response.json()
        if not data.get('success'):
            print(f"✅ Correctly handled non-existent security ID")
            print(f"   Error: {data.get('error')}")
        else:
            print(f"❌ Expected failure for non-existent security ID")
    else:
        print_response(response, "Response")


def test_no_auth():
    """Test endpoints without authentication"""
    print_section("9. AUTHENTICATION TESTS")
    
    # Test 1: Corporate Actions without token
    print("\n📍 Test 9.1: Corporate Actions - No Auth Token")
    url = f"{BASE_URL}{API_PREFIX}/corporate-actions"
    response = requests.get(url)
    
    if response.status_code in [401, 403]:
        print(f"✅ Correctly rejected request without auth token (status: {response.status_code})")
    else:
        print(f"❌ Expected 401 or 403, got {response.status_code}")
    
    # Test 2: Stock Price Refresh without token
    print("\n📍 Test 9.2: Stock Price Refresh - No Auth Token")
    url = f"{BASE_URL}{API_PREFIX}/refresh-stock-price"
    payload = {"securityid": 542034}
    response = requests.post(url, json=payload)
    
    if response.status_code in [401, 403]:
        print(f"✅ Correctly rejected request without auth token (status: {response.status_code})")
    else:
        print(f"❌ Expected 401 or 403, got {response.status_code}")


def run_all_tests():
    """Run all tests"""
    global auth_token
    
    print(f"\n{'*'*80}")
    print(f"  BACKFIN ADMIN API ENDPOINT TESTS")
    print(f"  Base URL: {BASE_URL}")
    print(f"  Test User: {TEST_USER['email']}")
    print(f"{'*'*80}")
    
    try:
        # Step 1: Register user (or skip if exists)
        token = register_user()
        
        # Step 2: Login
        auth_token = login_user()
        
        if not auth_token:
            print("\n❌ Failed to obtain authentication token. Aborting tests.")
            return
        
        # Step 3: Test Corporate Actions endpoints
        test_corporate_actions_basic()
        test_corporate_actions_with_filters()
        test_corporate_actions_pagination()
        test_corporate_actions_invalid()
        
        # Step 4: Test Stock Price Refresh endpoint
        test_refresh_stock_price()
        test_refresh_stock_price_invalid()
        
        # Step 5: Test authentication
        test_no_auth()
        
        # Summary
        print_section("TEST SUMMARY")
        print("✅ All tests completed!")
        print(f"\nTested Endpoints:")
        print(f"  1. POST {BASE_URL}{API_PREFIX}/auth/register")
        print(f"  2. POST {BASE_URL}{API_PREFIX}/auth/login")
        print(f"  3. GET  {BASE_URL}{API_PREFIX}/corporate-actions")
        print(f"  4. POST {BASE_URL}{API_PREFIX}/refresh-stock-price")
        
    except requests.exceptions.ConnectionError:
        print(f"\n❌ ERROR: Could not connect to {BASE_URL}")
        print(f"   Make sure the API server is running at {BASE_URL}")
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()
