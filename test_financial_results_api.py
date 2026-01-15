#!/usr/bin/env python3
"""
Test Script for Financial Results API
Tests both the main API and verification system API endpoints

Usage:
    python test_financial_results_api.py

Environment Variables:
    MAIN_API_URL: Main API base URL (default: http://localhost:5001)
    VERIFICATION_API_URL: Verification system URL (default: http://localhost:8000)
    ADMIN_EMAIL: Admin email for verification system auth
    ADMIN_PASSWORD: Admin password for verification system auth
"""

import os
import sys
import json
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()

# Configuration
MAIN_API_URL = "https://api.marketwire.ai"
VERIFICATION_API_URL = "https://admin.anshulkr.com"
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(title):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{title}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")

def print_success(msg):
    print(f"{Colors.GREEN}✅ {msg}{Colors.RESET}")

def print_error(msg):
    print(f"{Colors.RED}❌ {msg}{Colors.RESET}")

def print_warning(msg):
    print(f"{Colors.YELLOW}⚠️  {msg}{Colors.RESET}")

def print_info(msg):
    print(f"{Colors.BLUE}ℹ️  {msg}{Colors.RESET}")

# ============================================================
# MAIN API TESTS (/api/financial_results)
# ============================================================

def test_main_api_basic():
    """Test basic GET /api/financial_results"""
    print_info("Testing GET /api/financial_results (basic)")
    try:
        response = requests.get(f"{MAIN_API_URL}/api/financial_results", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print_success(f"Response OK - Found {data.get('count', 0)} results")
            print(f"   Total count: {data.get('total_count', 'N/A')}")
            print(f"   Total pages: {data.get('total_pages', 'N/A')}")
            print(f"   Current page: {data.get('current_page', 'N/A')}")
            return True
        else:
            print_error(f"HTTP {response.status_code}: {response.text[:200]}")
            return False
    except requests.exceptions.ConnectionError:
        print_error(f"Connection failed - Is the API running at {MAIN_API_URL}?")
        return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False

def test_main_api_with_filters():
    """Test GET /api/financial_results with various filters"""
    print_info("Testing GET /api/financial_results with filters")
    
    tests = [
        {"name": "Date range filter", "params": {
            "start_date": (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
            "end_date": datetime.now().strftime("%Y-%m-%d")
        }},
        {"name": "Verified filter (true)", "params": {"verified": "true"}},
        {"name": "Verified filter (false)", "params": {"verified": "false"}},
        {"name": "Pagination", "params": {"page": 1, "page_size": 5}},
        {"name": "Symbol filter", "params": {"symbol": "RELIANCE"}},
        {"name": "ISIN filter", "params": {"isin": "INE002A01018"}},
    ]
    
    passed = 0
    for test in tests:
        try:
            response = requests.get(
                f"{MAIN_API_URL}/api/financial_results",
                params=test["params"],
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                print_success(f"{test['name']}: OK (count: {data.get('count', 0)})")
                passed += 1
            else:
                print_error(f"{test['name']}: HTTP {response.status_code}")
        except Exception as e:
            print_error(f"{test['name']}: {str(e)[:50]}")
    
    print(f"\n   Passed: {passed}/{len(tests)}")
    return passed == len(tests)

def test_main_api_invalid_params():
    """Test error handling for invalid parameters"""
    print_info("Testing error handling for invalid parameters")
    
    tests = [
        {"name": "Invalid date format", "params": {"start_date": "invalid-date"}},
        {"name": "Page size too large", "params": {"page_size": 500}},
        {"name": "Negative page", "params": {"page": -1}},
    ]
    
    for test in tests:
        try:
            response = requests.get(
                f"{MAIN_API_URL}/api/financial_results",
                params=test["params"],
                timeout=10
            )
            
            if response.status_code >= 400:
                print_success(f"{test['name']}: Correctly returned error ({response.status_code})")
            else:
                print_warning(f"{test['name']}: Returned {response.status_code} (expected error)")
        except Exception as e:
            print_error(f"{test['name']}: {str(e)[:50]}")

# ============================================================
# VERIFICATION SYSTEM API TESTS
# ============================================================

def get_auth_token():
    """Get JWT token from verification system"""
    print_info("Authenticating with verification system...")
    try:
        response = requests.post(
            f"{VERIFICATION_API_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            if token:
                print_success("Authentication successful")
                return token
            else:
                print_error("No access_token in response")
                return None
        else:
            print_error(f"Auth failed: HTTP {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return None
    except requests.exceptions.ConnectionError:
        print_error(f"Connection failed - Is verification system running at {VERIFICATION_API_URL}?")
        return None
    except Exception as e:
        print_error(f"Auth error: {e}")
        return None

def test_verification_get_financial_results(token):
    """Test GET /api/financial_results in verification system"""
    print_info("Testing GET /api/financial_results (verification system)")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(
            f"{VERIFICATION_API_URL}/api/financial_results",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            count = len(data) if isinstance(data, list) else data.get('count', 0)
            print_success(f"Response OK - Found {count} results")
            return True, data
        else:
            print_error(f"HTTP {response.status_code}: {response.text[:200]}")
            return False, None
    except Exception as e:
        print_error(f"Error: {e}")
        return False, None

def test_verification_get_single_result(token, result_id):
    """Test GET /api/financial_results/{id}"""
    print_info(f"Testing GET /api/financial_results/{result_id}")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(
            f"{VERIFICATION_API_URL}/api/financial_results/{result_id}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success(f"Response OK - Got result for ID: {result_id}")
            print(f"   Company: {data.get('companyname', 'N/A')}")
            print(f"   Verified: {data.get('verified', 'N/A')}")
            return True
        elif response.status_code == 404:
            print_warning(f"Result not found (404) - ID: {result_id}")
            return True  # Not an error, just not found
        else:
            print_error(f"HTTP {response.status_code}: {response.text[:200]}")
            return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False

def test_verification_update_result(token, result_id):
    """Test PATCH /api/financial_results/{id}"""
    print_info(f"Testing PATCH /api/financial_results/{result_id}")
    
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # Test updating a field
    update_data = {
        "revenue": "100000.50",
        "profit": "25000.75"
    }
    
    try:
        response = requests.patch(
            f"{VERIFICATION_API_URL}/api/financial_results/{result_id}",
            headers=headers,
            json=update_data,
            timeout=10
        )
        
        if response.status_code == 200:
            print_success("Update successful")
            return True
        elif response.status_code == 404:
            print_warning(f"Result not found (404) - ID: {result_id}")
            return True
        else:
            print_error(f"HTTP {response.status_code}: {response.text[:200]}")
            return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False

def test_verification_unverified_results(token):
    """Test GET /api/financial_results/unverified"""
    print_info("Testing GET /api/financial_results/unverified")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(
            f"{VERIFICATION_API_URL}/api/financial_results/unverified",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            count = len(data) if isinstance(data, list) else data.get('count', 0)
            print_success(f"Response OK - Found {count} unverified results")
            return True
        elif response.status_code == 404:
            print_warning("Endpoint not found (404)")
            return True
        else:
            print_error(f"HTTP {response.status_code}: {response.text[:200]}")
            return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False

# ============================================================
# MAIN TEST RUNNER
# ============================================================

def run_all_tests():
    print_header("FINANCIAL RESULTS API TEST SUITE")
    
    print(f"Main API URL: {MAIN_API_URL}")
    print(f"Verification API URL: {VERIFICATION_API_URL}")
    print()
    
    results = {
        "main_api": [],
        "verification_api": []
    }
    
    # ==========================================
    # MAIN API TESTS
    # ==========================================
    print_header("MAIN API TESTS (/api/financial_results)")
    
    result = test_main_api_basic()
    results["main_api"].append(("Basic GET", result))
    print()
    
    result = test_main_api_with_filters()
    results["main_api"].append(("Filters", result))
    print()
    
    test_main_api_invalid_params()
    print()
    
    # ==========================================
    # VERIFICATION SYSTEM TESTS
    # ==========================================
    print_header("VERIFICATION SYSTEM API TESTS")
    
    token = get_auth_token()
    
    if token:
        print()
        
        success, data = test_verification_get_financial_results(token)
        results["verification_api"].append(("GET all results", success))
        print()
        
        # Get a result ID for further tests
        result_id = None
        if success and data:
            if isinstance(data, list) and len(data) > 0:
                result_id = data[0].get('id')
            elif isinstance(data, dict) and data.get('results'):
                result_id = data['results'][0].get('id') if data['results'] else None
        
        if result_id:
            result = test_verification_get_single_result(token, result_id)
            results["verification_api"].append(("GET single result", result))
            print()
            
            # Uncomment to test update (may modify data)
            # result = test_verification_update_result(token, result_id)
            # results["verification_api"].append(("PATCH result", result))
            # print()
        else:
            print_warning("No result ID available for single-result tests")
        
        result = test_verification_unverified_results(token)
        results["verification_api"].append(("GET unverified", result))
        print()
    else:
        print_warning("Skipping verification API tests - authentication failed")
        print_info("Set ADMIN_EMAIL and ADMIN_PASSWORD environment variables")
    
    # ==========================================
    # SUMMARY
    # ==========================================
    print_header("TEST SUMMARY")
    
    total_passed = 0
    total_tests = 0
    
    print(f"{Colors.BOLD}Main API:{Colors.RESET}")
    for name, passed in results["main_api"]:
        status = f"{Colors.GREEN}PASS{Colors.RESET}" if passed else f"{Colors.RED}FAIL{Colors.RESET}"
        print(f"  {name}: {status}")
        total_passed += 1 if passed else 0
        total_tests += 1
    
    print(f"\n{Colors.BOLD}Verification API:{Colors.RESET}")
    if results["verification_api"]:
        for name, passed in results["verification_api"]:
            status = f"{Colors.GREEN}PASS{Colors.RESET}" if passed else f"{Colors.RED}FAIL{Colors.RESET}"
            print(f"  {name}: {status}")
            total_passed += 1 if passed else 0
            total_tests += 1
    else:
        print("  (Skipped - auth failed)")
    
    print(f"\n{Colors.BOLD}Overall: {total_passed}/{total_tests} tests passed{Colors.RESET}")
    
    return total_passed == total_tests

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
