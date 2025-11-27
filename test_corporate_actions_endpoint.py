#!/usr/bin/env python3
"""
Test script for the Corporate Actions API endpoint
Tests various filters and pagination scenarios
"""

import requests
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# Configuration
API_BASE_URL = 'https://fin.anshulkr.com'
API_ENDPOINT = f'{API_BASE_URL}/api/corporate_actions'

# Test credentials - replace with your actual token
ACCESS_TOKEN = os.getenv('TEST_ACCESS_TOKEN', '')

if not ACCESS_TOKEN:
    print("❌ ERROR: TEST_ACCESS_TOKEN not set in environment variables")
    print("Set it with: export TEST_ACCESS_TOKEN='your_token_here'")
    exit(1)

# Headers with authentication
headers = {
    'Authorization': f'Bearer {ACCESS_TOKEN}',
    'Content-Type': 'application/json'
}

def print_response(test_name, response):
    """Pretty print the test response"""
    print(f"\n{'='*80}")
    print(f"TEST: {test_name}")
    print(f"{'='*80}")
    print(f"Status Code: {response.status_code}")
    
    try:
        data = response.json()
        print(f"\nResponse:")
        print(json.dumps(data, indent=2, default=str))
        
        if data.get('success') and 'pagination' in data:
            print(f"\n📊 Pagination Info:")
            print(f"  - Total Records: {data['pagination']['total_records']}")
            print(f"  - Current Page: {data['pagination']['current_page']}/{data['pagination']['total_pages']}")
            print(f"  - Page Size: {data['pagination']['page_size']}")
            print(f"  - Records in this page: {len(data.get('data', []))}")
        
        if data.get('success') and 'filters' in data:
            print(f"\n🔍 Applied Filters:")
            for key, value in data['filters'].items():
                print(f"  - {key}: {value}")
    except Exception as e:
        print(f"Response Text: {response.text}")
        print(f"Error parsing JSON: {e}")
    
    print(f"{'='*80}\n")

def test_basic_request():
    """Test basic request without filters"""
    print("\n🧪 Running Test 1: Basic Request (No Filters)")
    response = requests.get(API_ENDPOINT, headers=headers)
    print_response("Basic Request - Get All Corporate Actions", response)
    return response.status_code == 200

def test_filter_by_exchange():
    """Test filtering by exchange"""
    print("\n🧪 Running Test 2: Filter by Exchange")
    
    # Test NSE
    params = {'exchange': 'NSE'}
    response = requests.get(API_ENDPOINT, headers=headers, params=params)
    print_response("Filter by Exchange - NSE", response)
    
    # Test BSE
    params = {'exchange': 'BSE'}
    response = requests.get(API_ENDPOINT, headers=headers, params=params)
    print_response("Filter by Exchange - BSE", response)
    
    return response.status_code == 200

def test_filter_by_date_range():
    """Test filtering by date range"""
    print("\n🧪 Running Test 3: Filter by Date Range")
    
    # Get next 7 days
    start_date = datetime.now().strftime('%Y-%m-%d')
    end_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
    
    params = {
        'start_date': start_date,
        'end_date': end_date
    }
    response = requests.get(API_ENDPOINT, headers=headers, params=params)
    print_response(f"Filter by Date Range - {start_date} to {end_date}", response)
    
    return response.status_code == 200

def test_filter_by_symbol():
    """Test filtering by symbol"""
    print("\n🧪 Running Test 4: Filter by Symbol")
    
    # Test with a common symbol pattern
    params = {'symbol': 'HDFC'}
    response = requests.get(API_ENDPOINT, headers=headers, params=params)
    print_response("Filter by Symbol - HDFC", response)
    
    return response.status_code == 200

def test_filter_by_action_required():
    """Test filtering by action_required"""
    print("\n🧪 Running Test 5: Filter by Action Required")
    
    # Test action_required = true
    params = {'action_required': 'true'}
    response = requests.get(API_ENDPOINT, headers=headers, params=params)
    print_response("Filter by Action Required - True (Bonus/Split/etc)", response)
    
    # Test action_required = false
    params = {'action_required': 'false'}
    response = requests.get(API_ENDPOINT, headers=headers, params=params)
    print_response("Filter by Action Required - False (Dividends/etc)", response)
    
    return response.status_code == 200

def test_pagination():
    """Test pagination"""
    print("\n🧪 Running Test 6: Pagination")
    
    # Page 1, 10 items
    params = {'page': 1, 'page_size': 10}
    response = requests.get(API_ENDPOINT, headers=headers, params=params)
    print_response("Pagination - Page 1, Size 10", response)
    
    # Page 2, 10 items
    params = {'page': 2, 'page_size': 10}
    response = requests.get(API_ENDPOINT, headers=headers, params=params)
    print_response("Pagination - Page 2, Size 10", response)
    
    return response.status_code == 200

def test_combined_filters():
    """Test multiple filters combined"""
    print("\n🧪 Running Test 7: Combined Filters")
    
    start_date = datetime.now().strftime('%Y-%m-%d')
    end_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
    
    params = {
        'exchange': 'NSE',
        'start_date': start_date,
        'end_date': end_date,
        'action_required': 'true',
        'page': 1,
        'page_size': 20
    }
    response = requests.get(API_ENDPOINT, headers=headers, params=params)
    print_response("Combined Filters - NSE + Date Range + Action Required", response)
    
    return response.status_code == 200

def test_invalid_exchange():
    """Test with invalid exchange"""
    print("\n🧪 Running Test 8: Invalid Exchange (Should Fail)")
    
    params = {'exchange': 'INVALID'}
    response = requests.get(API_ENDPOINT, headers=headers, params=params)
    print_response("Invalid Exchange - INVALID", response)
    
    return response.status_code == 400

def test_no_auth():
    """Test without authentication"""
    print("\n🧪 Running Test 9: No Authentication (Should Fail)")
    
    response = requests.get(API_ENDPOINT)
    print_response("No Authentication", response)
    
    return response.status_code == 401

def main():
    """Run all tests"""
    print("="*80)
    print("CORPORATE ACTIONS API ENDPOINT TEST SUITE")
    print("="*80)
    print(f"API Endpoint: {API_ENDPOINT}")
    print(f"Using Token: {ACCESS_TOKEN[:20]}..." if len(ACCESS_TOKEN) > 20 else f"Using Token: {ACCESS_TOKEN}")
    print("="*80)
    
    tests = [
        ("Basic Request", test_basic_request),
        ("Filter by Exchange", test_filter_by_exchange),
        ("Filter by Date Range", test_filter_by_date_range),
        ("Filter by Symbol", test_filter_by_symbol),
        ("Filter by Action Required", test_filter_by_action_required),
        ("Pagination", test_pagination),
        ("Combined Filters", test_combined_filters),
        ("Invalid Exchange", test_invalid_exchange),
        ("No Authentication", test_no_auth),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' failed with exception: {e}")
            results.append((test_name, False))
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print("="*80)
    print(f"Total: {passed}/{total} tests passed ({(passed/total*100):.1f}%)")
    print("="*80)
    
    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
