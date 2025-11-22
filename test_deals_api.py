#!/usr/bin/env python3
"""
Comprehensive test script for Deals API endpoint
Tests registration, login, authentication, and all filter combinations
"""

import requests
import json
import time
from datetime import datetime, timedelta

# Configuration
BASE_URL = "http://localhost:5001/api"
TEST_EMAIL = f"test_deals_{int(time.time())}@example.com"
TEST_PASSWORD = "SecureTestPass123!"
TEST_PHONE = "+1234567890"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_test(message):
    print(f"{Colors.BLUE}{Colors.BOLD}🧪 TEST:{Colors.END} {message}")

def print_success(message):
    print(f"{Colors.GREEN}✅ PASS:{Colors.END} {message}")

def print_error(message):
    print(f"{Colors.RED}❌ FAIL:{Colors.END} {message}")

def print_info(message):
    print(f"{Colors.YELLOW}ℹ️  INFO:{Colors.END} {message}")

def print_section(message):
    print(f"\n{Colors.BOLD}{'=' * 80}{Colors.END}")
    print(f"{Colors.BOLD}{message}{Colors.END}")
    print(f"{Colors.BOLD}{'=' * 80}{Colors.END}\n")

# Test results tracking
tests_passed = 0
tests_failed = 0

def run_test(test_name, test_func):
    """Run a test and track results"""
    global tests_passed, tests_failed
    print_test(test_name)
    try:
        test_func()
        tests_passed += 1
        print_success(f"{test_name}")
        return True
    except AssertionError as e:
        tests_failed += 1
        print_error(f"{test_name}: {str(e)}")
        return False
    except Exception as e:
        tests_failed += 1
        print_error(f"{test_name}: Unexpected error - {str(e)}")
        return False

# Test variables
access_token = None
user_data = None

def test_1_register():
    """Test user registration"""
    response = requests.post(f"{BASE_URL}/register", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "phone": TEST_PHONE,
        "account_type": "premium"
    })
    
    assert response.status_code == 201, f"Expected 201, got {response.status_code}"
    data = response.json()
    assert "access_token" in data, "No access token in response"
    assert data.get("message") == "User registered successfully!", "Unexpected message"
    print_info(f"Registered user: {TEST_EMAIL}")

def test_2_login():
    """Test user login and get access token"""
    global access_token, user_data
    
    response = requests.post(f"{BASE_URL}/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert "access_token" in data, "No access token in response"
    access_token = data["access_token"]
    user_data = data.get("user", {})
    print_info(f"Logged in successfully. Token: {access_token[:20]}...")

def test_3_deals_no_auth():
    """Test that deals endpoint requires authentication"""
    response = requests.get(f"{BASE_URL}/deals")
    assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"

def test_4_deals_basic():
    """Test basic deals endpoint with authentication"""
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"{BASE_URL}/deals", headers=headers)
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert data.get("success") == True, "Response success should be True"
    assert "deals" in data, "No deals in response"
    assert "pagination" in data, "No pagination in response"
    assert "filters" in data, "No filters in response"
    
    print_info(f"Total deals: {data['pagination']['total_count']}")
    print_info(f"Page size: {len(data['deals'])}")

def test_5_deals_pagination():
    """Test pagination parameters"""
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"{BASE_URL}/deals?page=1&page_size=10", headers=headers)
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert len(data["deals"]) <= 10, "Page size not respected"
    
    pagination = data["pagination"]
    assert pagination["page"] == 1, "Wrong page number"
    assert pagination["page_size"] == 10, "Wrong page size"
    print_info(f"Pagination working: page {pagination['page']}/{pagination['total_pages']}")

def test_6_deals_filter_exchange_nse():
    """Test filtering by NSE exchange"""
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"{BASE_URL}/deals?exchange=NSE", headers=headers)
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    
    # All deals should be from NSE
    for deal in data["deals"]:
        assert deal["exchange"] == "NSE", f"Expected NSE, got {deal['exchange']}"
    
    print_info(f"NSE deals: {len(data['deals'])}")

def test_7_deals_filter_exchange_bse():
    """Test filtering by BSE exchange"""
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"{BASE_URL}/deals?exchange=BSE", headers=headers)
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    
    # All deals should be from BSE
    for deal in data["deals"]:
        assert deal["exchange"] == "BSE", f"Expected BSE, got {deal['exchange']}"
    
    print_info(f"BSE deals: {len(data['deals'])}")

def test_8_deals_filter_bulk():
    """Test filtering by BULK deal type"""
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"{BASE_URL}/deals?deal=BULK", headers=headers)
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    
    # All deals should be BULK
    for deal in data["deals"]:
        assert deal["deal"] == "BULK", f"Expected BULK, got {deal['deal']}"
    
    print_info(f"BULK deals: {len(data['deals'])}")

def test_9_deals_filter_block():
    """Test filtering by BLOCK deal type"""
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"{BASE_URL}/deals?deal=BLOCK", headers=headers)
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    
    # All deals should be BLOCK
    for deal in data["deals"]:
        assert deal["deal"] == "BLOCK", f"Expected BLOCK, got {deal['deal']}"
    
    print_info(f"BLOCK deals: {len(data['deals'])}")

def test_10_deals_filter_buy():
    """Test filtering by BUY deal type"""
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"{BASE_URL}/deals?deal_type=BUY", headers=headers)
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    
    # All deals should be BUY
    for deal in data["deals"]:
        assert deal["deal_type"] == "BUY", f"Expected BUY, got {deal['deal_type']}"
    
    print_info(f"BUY deals: {len(data['deals'])}")

def test_11_deals_filter_sell():
    """Test filtering by SELL deal type"""
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"{BASE_URL}/deals?deal_type=SELL", headers=headers)
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    
    # All deals should be SELL
    for deal in data["deals"]:
        assert deal["deal_type"] == "SELL", f"Expected SELL, got {deal['deal_type']}"
    
    print_info(f"SELL deals: {len(data['deals'])}")

def test_12_deals_filter_date_range():
    """Test filtering by date range"""
    headers = {"Authorization": f"Bearer {access_token}"}
    start_date = "2025-11-20"
    end_date = "2025-11-22"
    
    response = requests.get(
        f"{BASE_URL}/deals?start_date={start_date}&end_date={end_date}",
        headers=headers
    )
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    
    # Check date range
    for deal in data["deals"]:
        deal_date = deal["date"]
        assert start_date <= deal_date <= end_date, \
            f"Deal date {deal_date} not in range {start_date} to {end_date}"
    
    print_info(f"Deals in date range: {len(data['deals'])}")

def test_13_deals_filter_symbol():
    """Test filtering by symbol (partial match)"""
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # First get a symbol from the data
    response = requests.get(f"{BASE_URL}/deals?page_size=1", headers=headers)
    data = response.json()
    
    if data["deals"]:
        symbol = data["deals"][0]["symbol"][:4]  # Use first 4 chars for partial match
        
        response = requests.get(f"{BASE_URL}/deals?symbol={symbol}", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # All deals should contain the symbol substring
        for deal in data["deals"]:
            assert symbol.upper() in deal["symbol"].upper(), \
                f"Symbol {deal['symbol']} doesn't contain {symbol}"
        
        print_info(f"Deals matching '{symbol}': {len(data['deals'])}")
    else:
        print_info("No deals to test symbol filter")

def test_14_deals_combined_filters():
    """Test multiple filters combined"""
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(
        f"{BASE_URL}/deals?exchange=BSE&deal=BULK&deal_type=BUY&page_size=5",
        headers=headers
    )
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    
    # Verify all filters are applied
    for deal in data["deals"]:
        assert deal["exchange"] == "BSE", f"Wrong exchange: {deal['exchange']}"
        assert deal["deal"] == "BULK", f"Wrong deal type: {deal['deal']}"
        assert deal["deal_type"] == "BUY", f"Wrong transaction type: {deal['deal_type']}"
    
    print_info(f"BSE BULK BUY deals: {len(data['deals'])}")

def test_15_deals_max_page_size():
    """Test maximum page size limit"""
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"{BASE_URL}/deals?page_size=1000", headers=headers)
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    
    # Should be capped at 500
    assert len(data["deals"]) <= 500, "Page size should be capped at 500"
    print_info(f"Max page size respected: {len(data['deals'])} <= 500")

def test_16_deals_response_structure():
    """Test that response has all required fields"""
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"{BASE_URL}/deals?page_size=1", headers=headers)
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    
    # Check response structure
    assert "success" in data, "Missing 'success' field"
    assert "deals" in data, "Missing 'deals' field"
    assert "pagination" in data, "Missing 'pagination' field"
    assert "filters" in data, "Missing 'filters' field"
    
    # Check pagination structure
    pagination = data["pagination"]
    required_pagination_fields = ["page", "page_size", "total_count", "total_pages", "has_next", "has_prev"]
    for field in required_pagination_fields:
        assert field in pagination, f"Missing pagination field: {field}"
    
    # Check deal structure (if deals exist)
    if data["deals"]:
        deal = data["deals"][0]
        required_deal_fields = ["id", "symbol", "date", "client_name", "deal_type", 
                               "quantity", "price", "exchange", "deal", "created_at"]
        for field in required_deal_fields:
            assert field in deal, f"Missing deal field: {field}"
    
    print_info("Response structure validated")

def main():
    """Run all tests"""
    print_section("🚀 DEALS API COMPREHENSIVE TEST SUITE")
    
    # Test 1-2: Authentication
    print_section("STEP 1: User Registration & Authentication")
    run_test("User Registration", test_1_register)
    run_test("User Login", test_2_login)
    
    # Test 3-4: Basic endpoint access
    print_section("STEP 2: Basic Endpoint Access")
    run_test("Deals endpoint requires authentication", test_3_deals_no_auth)
    run_test("Deals endpoint with valid token", test_4_deals_basic)
    
    # Test 5: Pagination
    print_section("STEP 3: Pagination")
    run_test("Pagination parameters", test_5_deals_pagination)
    
    # Test 6-7: Exchange filters
    print_section("STEP 4: Exchange Filters")
    run_test("Filter by NSE exchange", test_6_deals_filter_exchange_nse)
    run_test("Filter by BSE exchange", test_7_deals_filter_exchange_bse)
    
    # Test 8-9: Deal type filters
    print_section("STEP 5: Deal Type Filters (BULK/BLOCK)")
    run_test("Filter by BULK deals", test_8_deals_filter_bulk)
    run_test("Filter by BLOCK deals", test_9_deals_filter_block)
    
    # Test 10-11: Transaction type filters
    print_section("STEP 6: Transaction Type Filters (BUY/SELL)")
    run_test("Filter by BUY transactions", test_10_deals_filter_buy)
    run_test("Filter by SELL transactions", test_11_deals_filter_sell)
    
    # Test 12-13: Other filters
    print_section("STEP 7: Date & Symbol Filters")
    run_test("Filter by date range", test_12_deals_filter_date_range)
    run_test("Filter by symbol (partial match)", test_13_deals_filter_symbol)
    
    # Test 14: Combined filters
    print_section("STEP 8: Combined Filters")
    run_test("Multiple filters combined", test_14_deals_combined_filters)
    
    # Test 15-16: Edge cases and validation
    print_section("STEP 9: Edge Cases & Validation")
    run_test("Maximum page size limit", test_15_deals_max_page_size)
    run_test("Response structure validation", test_16_deals_response_structure)
    
    # Final summary
    print_section("📊 TEST SUMMARY")
    total_tests = tests_passed + tests_failed
    pass_rate = (tests_passed / total_tests * 100) if total_tests > 0 else 0
    
    print(f"Total Tests: {total_tests}")
    print(f"{Colors.GREEN}Passed: {tests_passed}{Colors.END}")
    print(f"{Colors.RED}Failed: {tests_failed}{Colors.END}")
    print(f"Pass Rate: {pass_rate:.1f}%")
    
    if tests_failed == 0:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 ALL TESTS PASSED! 🎉{Colors.END}")
        return 0
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}❌ SOME TESTS FAILED{Colors.END}")
        return 1

if __name__ == "__main__":
    exit(main())
