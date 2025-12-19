#!/usr/bin/env python3
"""
Script to create a user account in the Backfin API system
Usage: python create_user_account.py
"""

import os
import sys
import hashlib
import secrets
import uuid
from datetime import datetime
from dotenv import load_dotenv

# Add parent directory to path to import from api
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
load_dotenv()

try:
    from supabase import create_client, Client
except ImportError:
    print("Error: supabase library not found. Install with: pip install supabase")
    sys.exit(1)

def hash_password(password):
    """Hash a password for storing."""
    salt = os.getenv('PASSWORD_SALT', 'default_salt_change_this_in_production')
    return hashlib.sha256((password + salt).encode()).hexdigest()

def generate_access_token():
    """Generate a secure random access token."""
    return secrets.token_hex(32)  # 64 character hex string

def create_user_account(email, password, phone=None, account_type='free'):
    """Create a new user account"""
    
    # Initialize Supabase client
    supabase_url = os.getenv('SUPABASE_URL2')
    supabase_key = os.getenv('SUPABASE_KEY2')
    supabase_service_role_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    if not supabase_url or not supabase_key:
        print("Error: Supabase credentials are missing from .env file!")
        return False
    
    try:
        supabase = create_client(supabase_url, supabase_service_role_key if supabase_service_role_key else supabase_key)
        print(f"✓ Connected to Supabase")
    except Exception as e:
        print(f"Error connecting to Supabase: {e}")
        return False
    
    try:
        # Check if email already exists
        print(f"Checking if user {email} already exists...")
        check_response = supabase.table('UserData').select('emailID').eq('emailID', email).execute()
        
        if check_response.data and len(check_response.data) > 0:
            print(f"✗ Email {email} is already registered!")
            return False
        
        # Generate new UUID for user
        user_id = str(uuid.uuid4())
        
        # Generate access token
        access_token = generate_access_token()
        
        # Hash the password
        hashed_password = hash_password(password)
        
        # Generate a UUID for the watchlist
        watchlist_id = str(uuid.uuid4())
        
        print(f"Creating watchlist...")
        # Create initial watchlist in watchlistnamedata
        supabase.table('watchlistnamedata').insert({
            'watchlistid': watchlist_id,
            'watchlistname': 'Real Time Alerts',
            'userid': user_id
        }).execute()
        
        print(f"Creating user account...")
        # Create user data
        user_data = {
            'UserID': user_id,
            'emailID': email,
            'Password': hashed_password,
            'Phone_Number': phone,
            'Paid': 'false',
            'AccountType': account_type,
            'created_at': datetime.now().isoformat(),
            'AccessToken': access_token,
            'WatchListID': watchlist_id
        }
        
        # Insert user into UserData table
        supabase.table('UserData').insert(user_data).execute()
        
        print(f"\n✓ User account created successfully!")
        print(f"\n{'='*60}")
        print(f"Account Details:")
        print(f"{'='*60}")
        print(f"Email:        {email}")
        print(f"User ID:      {user_id}")
        print(f"Access Token: {access_token}")
        print(f"Watchlist ID: {watchlist_id}")
        print(f"Account Type: {account_type}")
        print(f"Created At:   {datetime.now().isoformat()}")
        print(f"{'='*60}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error creating user account: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Backfin User Account Creation Script")
    print("=" * 60)
    print()
    
    # Account details
    email = "ishmohit@marketwire.ai"
    password = "ishmohit@123"
    
    print(f"Creating account for: {email}")
    print()
    
    success = create_user_account(
        email=email,
        password=password,
        phone=None,
        account_type='free'
    )
    
    if success:
        print("\n✓ Account creation completed successfully!")
        sys.exit(0)
    else:
        print("\n✗ Account creation failed!")
        sys.exit(1)
