#!/usr/bin/env python3
"""
Script to create a test admin user for the verification system
"""

import requests
import json

API_BASE = 'http://localhost:9000'

def create_test_user():
    """Create a test user account"""
    user_data = {
        "email": "admin@test.com",
        "password": "testpassword123",
        "full_name": "Test Admin"
    }
    
    try:
        response = requests.post(f"{API_BASE}/auth/register", json=user_data)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Test user created successfully!")
            print(f"User ID: {result.get('user_id')}")
            print(f"Email: {user_data['email']}")
            print(f"Password: {user_data['password']}")
            return True
        elif response.status_code == 400:
            error = response.json()
            if "already exists" in error.get("detail", ""):
                print("ℹ️  Test user already exists")
                print(f"Email: {user_data['email']}")
                print(f"Password: {user_data['password']}")
                return True
            else:
                print(f"❌ Failed to create user: {error}")
                return False
        else:
            print(f"❌ Failed to create user: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to admin server at http://localhost:9000")
        print("Make sure the admin server is running with: cd admin_server && python main.py")
        return False
    except Exception as e:
        print(f"❌ Error creating user: {e}")
        return False

def test_login():
    """Test logging in with the test user"""
    login_data = {
        "email": "admin@test.com",
        "password": "testpassword123"
    }
    
    try:
        response = requests.post(f"{API_BASE}/auth/login", json=login_data)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Login test successful!")
            print(f"Access token received: {result.get('access_token')[:50]}...")
            return True
        else:
            print(f"❌ Login test failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing login: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Setting up test admin user for verification system...")
    print()
    
    if create_test_user():
        print()
        print("🧪 Testing login...")
        test_login()
        
        print()
        print("📋 Test user credentials:")
        print("Email: admin@test.com")
        print("Password: testpassword123")
        print()
        print("🌐 You can now access the admin interface at:")
        print("http://localhost:9000")
    else:
        print()
        print("❌ Setup failed. Make sure the admin server is running.")