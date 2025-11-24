#!/usr/bin/env python3
"""
Test script for Insider Trading API endpoint
Tests user registration, login, and fetching insider trading data
"""

import requests
import json
from datetime import datetime
import random
import string

# API Configuration
BASE_URL = "https://fin.anshulkr.com/api"
HEADERS = {"Content-Type": "application/json"}

def generate_random_email():
    """Generate a random email for testing"""
    random_string = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"test_{random_string}@example.com"

def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def print_response(response, show_data=True):
    """Pretty print API response"""
    print(f"\nStatus Code: {response.status_code}")
    try:
        data = response.json()
        if show_data:
            print(f"Response: {json.dumps(data, indent=2)}")
        else:
            # For large responses, just show summary
            if isinstance(data, dict):
                if 'data' in data and isinstance(data['data'], list):
                    print(f"Records returned: {len(data['data'])}")
                    if data['data']:
                        print(f"First record: {json.dumps(data['data'][0], indent=2)}")
                if 'pagination' in data:
                    print(f"Pagination: {json.dumps(data['pagination'], indent=2)}")
                if 'filters' in data:
                    print(f"Filters: {json.dumps(data['filters'], indent=2)}")
            else:
                print(f"Response: {json.dumps(data, indent=2)}")
    except:
        print(f"Response Text: {response.text}")

def test_register():
    """Test user registration"""
    print_section("TEST 1: User Registration")
    
    email = generate_random_email()
    password = "TestPassword123!"
    
    payload = {
        "email": email,
        "password": password,
        "phone": "+1234567890",
        "account_type": "free"
    }
    
    print(f"Registering user with email: {email}")
    response = requests.post(f"{BASE_URL}/register", headers=HEADERS, json=payload)
    print_response(response)
    
    if response.status_code == 201:
        data = response.json()
        token = data.get('token')
        print(f"\n✅ Registration successful!")
        print(f"Token: {token[:50]}...")
        return email, password, token
    else:
        print("\n❌ Registration failed!")
        return None, None, None

def test_login(email, password):
    """Test user login"""
    print_section("TEST 2: User Login")
    
    payload = {
        "email": email,
        "password": password
    }
    
    print(f"Logging in with email: {email}")
    response = requests.post(f"{BASE_URL}/login", headers=HEADERS, json=payload)
    print_response(response)
    
    if response.status_code == 200:
        data = response.json()
        token = data.get('token')
        print(f"\n✅ Login successful!")
        print(f"Token: {token[:50]}...")
        return token
    else:
        print("\n❌ Login failed!")
        return None

def test_insider_trading_today(token):
    """Test fetching insider trading data for today"""
    print_section("TEST 3: Get Insider Trading - Today's Data (All Exchanges)")
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    headers = {
        **HEADERS,
        "Authorization": f"Bearer {token}"
    }
    
    params = {
        "start_date": today,
        "end_date": today,
        "page": 1,
        "page_size": 50
    }
    
    print(f"Fetching insider trading data for date: {today}")
    response = requests.get(f"{BASE_URL}/insider_trading", headers=headers, params=params)
    print_response(response, show_data=False)
    
    if response.status_code == 200:
        print("\n✅ Successfully fetched insider trading data!")
        return True
    else:
        print("\n❌ Failed to fetch insider trading data!")
        return False

def test_insider_trading_bse(token):
    """Test fetching BSE insider trading data"""
    print_section("TEST 4: Get Insider Trading - BSE Only")
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    headers = {
        **HEADERS,
        "Authorization": f"Bearer {token}"
    }
    
    params = {
        "exchange": "BSE",
        "start_date": today,
        "end_date": today,
        "page": 1,
        "page_size": 50
    }
    
    print(f"Fetching BSE insider trading data for date: {today}")
    response = requests.get(f"{BASE_URL}/insider_trading", headers=headers, params=params)
    print_response(response, show_data=False)
    
    if response.status_code == 200:
        print("\n✅ Successfully fetched BSE insider trading data!")
        return True
    else:
        print("\n❌ Failed to fetch BSE insider trading data!")
        return False

def test_insider_trading_nse(token):
    """Test fetching NSE insider trading data"""
    print_section("TEST 5: Get Insider Trading - NSE Only")
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    headers = {
        **HEADERS,
        "Authorization": f"Bearer {token}"
    }
    
    params = {
        "exchange": "NSE",
        "start_date": today,
        "end_date": today,
        "page": 1,
        "page_size": 50
    }
    
    print(f"Fetching NSE insider trading data for date: {today}")
    response = requests.get(f"{BASE_URL}/insider_trading", headers=headers, params=params)
    print_response(response, show_data=False)
    
    if response.status_code == 200:
        print("\n✅ Successfully fetched NSE insider trading data!")
        return True
    else:
        print("\n❌ Failed to fetch NSE insider trading data!")
        return False

def test_insider_trading_with_symbol(token):
    """Test fetching insider trading data with symbol filter"""
    print_section("TEST 6: Get Insider Trading - With Symbol Filter")
    
    headers = {
        **HEADERS,
        "Authorization": f"Bearer {token}"
    }
    
    params = {
        "symbol": "RELIANCE",
        "page": 1,
        "page_size": 20
    }
    
    print(f"Fetching insider trading data for symbol: RELIANCE")
    response = requests.get(f"{BASE_URL}/insider_trading", headers=headers, params=params)
    print_response(response, show_data=False)
    
    if response.status_code == 200:
        print("\n✅ Successfully fetched insider trading data with symbol filter!")
        return True
    else:
        print("\n❌ Failed to fetch insider trading data with symbol filter!")
        return False

def test_insider_trading_pagination(token):
    """Test pagination for insider trading data"""
    print_section("TEST 7: Get Insider Trading - Pagination Test")
    
    headers = {
        **HEADERS,
        "Authorization": f"Bearer {token}"
    }
    
    # First page
    params = {
        "page": 1,
        "page_size": 10
    }
    
    print("Fetching page 1 with 10 items per page")
    response = requests.get(f"{BASE_URL}/insider_trading", headers=headers, params=params)
    print_response(response, show_data=False)
    
    if response.status_code == 200:
        data = response.json()
        if data.get('pagination', {}).get('has_next'):
            print("\n➡️  Has next page, fetching page 2...")
            params['page'] = 2
            response2 = requests.get(f"{BASE_URL}/insider_trading", headers=headers, params=params)
            print_response(response2, show_data=False)
        
        print("\n✅ Pagination test successful!")
        return True
    else:
        print("\n❌ Pagination test failed!")
        return False

def test_without_auth():
    """Test accessing endpoint without authentication"""
    print_section("TEST 8: Authentication Test - No Token")
    
    params = {
        "page": 1,
        "page_size": 10
    }
    
    print("Attempting to access endpoint without authentication token")
    response = requests.get(f"{BASE_URL}/insider_trading", headers=HEADERS, params=params)
    print_response(response)
    
    if response.status_code == 401:
        print("\n✅ Authentication protection working correctly!")
        return True
    else:
        print("\n❌ Authentication protection failed!")
        return False

def run_all_tests():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("  INSIDER TRADING API TEST SUITE")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 80)
    
    results = {
        'passed': 0,
        'failed': 0,
        'total': 8
    }
    
    # Test 1: Register
    email, password, token = test_register()
    if token:
        results['passed'] += 1
    else:
        results['failed'] += 1
        print("\n❌ Cannot proceed without successful registration!")
        return results
    
    # Test 2: Login
    login_token = test_login(email, password)
    if login_token:
        results['passed'] += 1
        token = login_token  # Use login token
    else:
        results['failed'] += 1
        print("\n❌ Cannot proceed without successful login!")
        return results
    
    # Test 3: Get today's data
    if test_insider_trading_today(token):
        results['passed'] += 1
    else:
        results['failed'] += 1
    
    # Test 4: Get BSE data
    if test_insider_trading_bse(token):
        results['passed'] += 1
    else:
        results['failed'] += 1
    
    # Test 5: Get NSE data
    if test_insider_trading_nse(token):
        results['passed'] += 1
    else:
        results['failed'] += 1
    
    # Test 6: Symbol filter
    if test_insider_trading_with_symbol(token):
        results['passed'] += 1
    else:
        results['failed'] += 1
    
    # Test 7: Pagination
    if test_insider_trading_pagination(token):
        results['passed'] += 1
    else:
        results['failed'] += 1
    
    # Test 8: Authentication
    if test_without_auth():
        results['passed'] += 1
    else:
        results['failed'] += 1
    
    # Print summary
    print_section("TEST SUMMARY")
    print(f"\nTotal Tests: {results['total']}")
    print(f"✅ Passed: {results['passed']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"Success Rate: {(results['passed']/results['total']*100):.1f}%")
    
    if results['failed'] == 0:
        print("\n🎉 ALL TESTS PASSED!")
    else:
        print(f"\n⚠️  {results['failed']} test(s) failed!")
    
    return results

if __name__ == "__main__":
    try:
        results = run_all_tests()
        exit(0 if results['failed'] == 0 else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️  Tests interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n\n❌ Test suite error: {str(e)}")
        import traceback
        traceback.print_exc()
        exit(1)
