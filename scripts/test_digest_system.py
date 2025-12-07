#!/usr/bin/env python3
"""
Test Script for Daily Digest System
Tests the notification queue and email digest functionality

Usage:
    python3 scripts/test_digest_system.py
"""

import os
import sys
from datetime import date, datetime
import uuid

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment
load_dotenv()
SUPABASE_URL = os.getenv('SUPABASE_URL2')
SUPABASE_KEY = os.getenv('SUPABASE_KEY2')

if not all([SUPABASE_URL, SUPABASE_KEY]):
    print("❌ Missing environment variables")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def test_queue_notification():
    """Test adding a notification to the queue"""
    print("\n" + "="*60)
    print("TEST 1: Queue Notification")
    print("="*60)
    
    try:
        # Get a test user
        users = supabase.table('UserData').select('UserID, emailID').limit(1).execute()
        if not users.data:
            print("❌ No users found in database")
            return False
        
        test_user = users.data[0]
        user_id = test_user['UserID']
        email = test_user.get('emailID', 'No email')
        
        print(f"📧 Test User: {user_id}")
        print(f"   Email: {email}")
        
        # Get a test announcement
        announcements = supabase.table('corporatefilings').select('*').limit(1).execute()
        if not announcements.data:
            print("❌ No announcements found in database")
            return False
        
        test_announcement = announcements.data[0]
        corp_id = test_announcement['corp_id']
        
        print(f"📊 Test Announcement: {corp_id}")
        print(f"   Company: {test_announcement.get('companyname', 'N/A')}")
        
        # Insert test notification
        notification = {
            'user_id': user_id,
            'corp_id': corp_id,
            'isin': test_announcement.get('isin'),
            'symbol': test_announcement.get('symbol'),
            'company_name': test_announcement.get('companyname'),
            'category': test_announcement.get('category'),
            'matched_by': 'isin',
            'notification_date': date.today().isoformat()
        }
        
        result = supabase.table('user_notification_queue').insert(notification).execute()
        
        if result.data:
            print(f"✅ Notification queued successfully!")
            print(f"   Queue ID: {result.data[0]['id']}")
            return True
        else:
            print(f"❌ Failed to queue notification")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_fetch_pending():
    """Test fetching pending notifications"""
    print("\n" + "="*60)
    print("TEST 2: Fetch Pending Notifications")
    print("="*60)
    
    try:
        target_date = date.today()
        
        # Count total pending
        response = supabase.table('user_notification_queue')\
            .select('*', count='exact')\
            .eq('notification_date', target_date.isoformat())\
            .eq('is_processed', False)\
            .execute()
        
        total = response.count if hasattr(response, 'count') else len(response.data)
        
        print(f"📊 Total pending notifications for {target_date}: {total}")
        
        if response.data:
            # Group by user
            users = {}
            for notif in response.data:
                uid = notif['user_id']
                users[uid] = users.get(uid, 0) + 1
            
            print(f"👥 Users with pending notifications: {len(users)}")
            
            # Show top 5 users
            sorted_users = sorted(users.items(), key=lambda x: x[1], reverse=True)[:5]
            for user_id, count in sorted_users:
                print(f"   • {user_id}: {count} notifications")
            
            return True
        else:
            print("ℹ️  No pending notifications")
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_user_preferences():
    """Test user notification preferences"""
    print("\n" + "="*60)
    print("TEST 3: User Notification Preferences")
    print("="*60)
    
    try:
        # Check if table exists and has data
        response = supabase.table('user_notification_preferences')\
            .select('*', count='exact')\
            .limit(5)\
            .execute()
        
        count = response.count if hasattr(response, 'count') else len(response.data)
        
        print(f"📊 Users with preferences: {count}")
        
        if response.data:
            for pref in response.data:
                print(f"   • User {pref['user_id'][:8]}...")
                print(f"     Email enabled: {pref.get('email_enabled', True)}")
                print(f"     Min announcements: {pref.get('minimum_announcements', 1)}")
        else:
            print("ℹ️  No preferences set (will use defaults)")
        
        return True
        
    except Exception as e:
        print(f"⚠️  Preferences table may not exist: {e}")
        print("ℹ️  This is OK - defaults will be used")
        return True


def test_digest_log():
    """Test digest log table"""
    print("\n" + "="*60)
    print("TEST 4: Email Digest Log")
    print("="*60)
    
    try:
        # Get recent digests
        response = supabase.table('user_email_digest_log')\
            .select('*')\
            .order('created_at', desc=True)\
            .limit(10)\
            .execute()
        
        if response.data:
            print(f"📊 Recent digest emails: {len(response.data)}")
            
            # Group by status
            status_counts = {}
            for log in response.data:
                status = log['status']
                status_counts[status] = status_counts.get(status, 0) + 1
            
            print("\nStatus breakdown:")
            for status, count in status_counts.items():
                emoji = {'sent': '✅', 'failed': '❌', 'skipped': '⏭️', 'pending': '⏳'}.get(status, '•')
                print(f"   {emoji} {status}: {count}")
            
            # Show latest
            latest = response.data[0]
            print(f"\nLatest digest:")
            print(f"   Date: {latest['digest_date']}")
            print(f"   User: {latest['user_id'][:8]}...")
            print(f"   Status: {latest['status']}")
            print(f"   Announcements: {latest['announcement_count']}")
            print(f"   Companies: {latest['company_count']}")
        else:
            print("ℹ️  No digest logs yet (table is empty)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_watchlist_data():
    """Test watchlist data integrity"""
    print("\n" + "="*60)
    print("TEST 5: Watchlist Data")
    print("="*60)
    
    try:
        # Check watchlist entries
        response = supabase.table('watchlistdata')\
            .select('*', count='exact')\
            .limit(5)\
            .execute()
        
        count = response.count if hasattr(response, 'count') else len(response.data)
        
        print(f"📊 Total watchlist entries: {count}")
        
        if response.data:
            print("\nSample entries:")
            for entry in response.data[:3]:
                print(f"   • User: {entry.get('userid', 'N/A')}")
                print(f"     ISIN: {entry.get('isin', 'N/A')}")
                print(f"     Category: {entry.get('category', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def cleanup_test_data():
    """Clean up test notifications (optional)"""
    print("\n" + "="*60)
    print("CLEANUP: Remove Test Notifications")
    print("="*60)
    
    try:
        response = input("Delete today's test notifications? (y/N): ")
        if response.lower() != 'y':
            print("ℹ️  Skipping cleanup")
            return True
        
        target_date = date.today()
        
        # Delete unprocessed notifications from today
        result = supabase.table('user_notification_queue')\
            .delete()\
            .eq('notification_date', target_date.isoformat())\
            .eq('is_processed', False)\
            .execute()
        
        print(f"✅ Cleanup complete")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "🧪 " + "="*58)
    print("   Daily Digest System - Test Suite")
    print("="*60 + "\n")
    
    tests = [
        test_queue_notification,
        test_fetch_pending,
        test_user_preferences,
        test_digest_log,
        test_watchlist_data,
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append((test_func.__name__, result))
        except Exception as e:
            print(f"\n❌ Test crashed: {e}")
            results.append((test_func.__name__, False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        emoji = "✅" if result else "❌"
        print(f"{emoji} {test_name}")
    
    print(f"\n{'✅' if passed == total else '⚠️'} Passed: {passed}/{total}")
    
    # Offer cleanup
    if passed > 0:
        print()
        cleanup_test_data()
    
    print("\n" + "="*60)
    print("📚 Next Steps:")
    print("   1. Review test results above")
    print("   2. Run digest sender in dry-run mode:")
    print("      python3 scripts/send_daily_digest.py --dry-run")
    print("   3. Send test email to specific user:")
    print("      python3 scripts/send_daily_digest.py --test-user USER_ID")
    print("   4. Setup cron job for daily execution")
    print("="*60 + "\n")
    
    return 0 if passed == total else 1


if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
