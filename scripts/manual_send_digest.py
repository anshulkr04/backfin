#!/usr/bin/env python3
"""
Manual Digest Sender - Quick Testing Tool
Send digest email to any user on-demand

Usage:
    python3 scripts/manual_send_digest.py user@email.com
    python3 scripts/manual_send_digest.py USER_ID --by-id
"""

import os
import sys
import argparse

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from supabase import create_client, Client
from datetime import date

# Load environment
load_dotenv()
SUPABASE_URL = os.getenv('SUPABASE_URL2')
SUPABASE_KEY = os.getenv('SUPABASE_KEY2')

if not all([SUPABASE_URL, SUPABASE_KEY]):
    print("❌ Missing environment variables")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def find_user_by_email(email: str):
    """Find user by email"""
    try:
        response = supabase.table('UserData')\
            .select('UserID, emailID, Phone_Number')\
            .eq('emailID', email)\
            .execute()
        
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"❌ Error finding user: {e}")
        return None

def send_digest_now(user_id: str, target_date=None):
    """Send digest email immediately"""
    if not target_date:
        target_date = date.today()
    
    # Import the digest sender
    sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
    from send_daily_digest import send_digest_to_user
    
    print(f"\n📧 Sending digest for {target_date}...")
    result = send_digest_to_user(user_id, target_date, dry_run=False)
    
    if result:
        print("✅ Digest sent successfully!")
        return True
    else:
        print("❌ Failed to send digest")
        return False

def main():
    parser = argparse.ArgumentParser(description='Send digest email to a user')
    parser.add_argument('identifier', help='Email address or User ID')
    parser.add_argument('--by-id', action='store_true', help='Identifier is User ID instead of email')
    parser.add_argument('--date', type=str, help='Target date (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    # Parse date if provided
    if args.date:
        from datetime import datetime
        try:
            target_date = datetime.strptime(args.date, '%Y-%m-%d').date()
        except ValueError:
            print(f"❌ Invalid date format: {args.date}")
            return 1
    else:
        target_date = date.today()
    
    # Find user
    if args.by_id:
        user_id = args.identifier
        print(f"🔍 Looking up user by ID: {user_id}")
    else:
        email = args.identifier
        print(f"🔍 Looking up user by email: {email}")
        user = find_user_by_email(email)
        
        if not user:
            print(f"❌ User not found with email: {email}")
            return 1
        
        user_id = user['UserID']
        print(f"✅ Found user: {user_id}")
        print(f"   Email: {user.get('emailID', 'N/A')}")
    
    # Check for pending notifications
    response = supabase.table('user_notification_queue')\
        .select('*', count='exact')\
        .eq('user_id', user_id)\
        .eq('notification_date', target_date.isoformat())\
        .eq('is_processed', False)\
        .execute()
    
    count = response.count if hasattr(response, 'count') else len(response.data)
    
    if count == 0:
        print(f"\n⚠️  No pending notifications for this user on {target_date}")
        print("   Either:")
        print("   • User has no companies in watchlist")
        print("   • No announcements today from their companies")
        print("   • Notifications already processed")
        return 0
    
    print(f"\n📊 Found {count} pending notifications")
    
    # Confirm
    response_input = input(f"\nSend digest email now? (y/N): ")
    if response_input.lower() != 'y':
        print("❌ Cancelled")
        return 0
    
    # Send
    success = send_digest_now(user_id, target_date)
    
    return 0 if success else 1

if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
