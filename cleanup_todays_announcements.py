#!/usr/bin/env python3
"""
Cleanup script to reprocess today's announcements
- Deletes today's announcements from corporatefilings table
- Removes latest announcement JSON files
- Forces scrapers to reprocess all announcements for today
"""

import sqlite3
import os
import json
from pathlib import Path
from datetime import datetime

def delete_todays_announcements():
    """Delete today's announcements from the corporatefilings table"""
    db_path = "data/bse_raw.db"
    
    if not os.path.exists(db_path):
        print("❌ Database file not found")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # First, check how many announcements will be deleted
        cursor.execute("""
            SELECT COUNT(*) FROM corporatefilings
            WHERE date(date) = '2025-10-13'
        """)
        count_before = cursor.fetchone()[0]
        print(f"📊 Found {count_before} announcements for 2025-10-13")
        
        if count_before == 0:
            print("✅ No announcements to delete for today")
            conn.close()
            return True
        
        # Delete today's announcements
        cursor.execute("""
            DELETE FROM corporatefilings
            WHERE date(date) = '2025-10-13'
        """)
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        print(f"🗑️ Deleted {deleted_count} announcements from corporatefilings table")
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def delete_todays_local_announcements():
    """Delete today's announcements from the local announcements table"""
    db_path = "data/bse_raw.db"
    
    if not os.path.exists(db_path):
        print("❌ Database file not found")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if announcements table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='announcements'
        """)
        
        if not cursor.fetchone():
            print("ℹ️ Local announcements table doesn't exist, skipping")
            conn.close()
            return True
        
        # Check how many local announcements will be deleted
        cursor.execute("""
            SELECT COUNT(*) FROM announcements
            WHERE date(fetched_at) = '2025-10-13'
        """)
        count_before = cursor.fetchone()[0]
        print(f"📊 Found {count_before} local announcements for 2025-10-13")
        
        if count_before == 0:
            print("✅ No local announcements to delete for today")
            conn.close()
            return True
        
        # Delete today's local announcements
        cursor.execute("""
            DELETE FROM announcements
            WHERE date(fetched_at) = '2025-10-13'
        """)
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        print(f"🗑️ Deleted {deleted_count} announcements from local announcements table")
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def remove_latest_announcement_files():
    """Remove the latest announcement JSON files"""
    data_dir = Path("data")
    files_to_remove = [
        "latest_announcement_bse_scraper.json",
        "latest_announcement_nse_scraper.json",
        "latest_announcement_new_scraper.json"  # Legacy file name
    ]
    
    removed_count = 0
    for filename in files_to_remove:
        file_path = data_dir / filename
        if file_path.exists():
            try:
                os.remove(file_path)
                print(f"🗑️ Removed {filename}")
                removed_count += 1
            except Exception as e:
                print(f"❌ Failed to remove {filename}: {e}")
        else:
            print(f"ℹ️ {filename} doesn't exist, skipping")
    
    return removed_count > 0

def verify_cleanup():
    """Verify that cleanup was successful"""
    db_path = "data/bse_raw.db"
    
    if not os.path.exists(db_path):
        print("❌ Cannot verify - database file not found")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check corporatefilings
        cursor.execute("""
            SELECT COUNT(*) FROM corporatefilings
            WHERE date(date) = '2025-10-13'
        """)
        corp_count = cursor.fetchone()[0]
        
        # Check local announcements if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='announcements'
        """)
        
        local_count = 0
        if cursor.fetchone():
            cursor.execute("""
                SELECT COUNT(*) FROM announcements
                WHERE date(fetched_at) = '2025-10-13'
            """)
            local_count = cursor.fetchone()[0]
        
        conn.close()
        
        print(f"\n✅ VERIFICATION RESULTS:")
        print(f"   Corporatefilings for 2025-10-13: {corp_count} entries")
        print(f"   Local announcements for 2025-10-13: {local_count} entries")
        
        # Check JSON files
        data_dir = Path("data")
        json_files = [
            "latest_announcement_bse_scraper.json",
            "latest_announcement_nse_scraper.json"
        ]
        
        for filename in json_files:
            file_path = data_dir / filename
            exists = "EXISTS" if file_path.exists() else "REMOVED"
            print(f"   {filename}: {exists}")
        
    except Exception as e:
        print(f"❌ Verification error: {e}")

def main():
    print("🧹 Backfin Announcement Cleanup Script")
    print("=" * 50)
    print("This script will:")
    print("1. Delete today's (2025-10-13) announcements from database")
    print("2. Remove latest announcement JSON files")
    print("3. Force scrapers to reprocess all announcements")
    print()
    
    confirmation = input("Do you want to proceed? (yes/no): ").lower().strip()
    if confirmation not in ['yes', 'y']:
        print("❌ Cleanup cancelled")
        return
    
    print("\n🚀 Starting cleanup...")
    
    # Step 1: Delete from corporatefilings
    print("\n📋 Step 1: Cleaning corporatefilings table...")
    if delete_todays_announcements():
        print("✅ Corporatefilings cleanup completed")
    else:
        print("❌ Corporatefilings cleanup failed")
    
    # Step 2: Delete from local announcements
    print("\n📋 Step 2: Cleaning local announcements table...")
    if delete_todays_local_announcements():
        print("✅ Local announcements cleanup completed")
    else:
        print("❌ Local announcements cleanup failed")
    
    # Step 3: Remove JSON files
    print("\n📋 Step 3: Removing latest announcement files...")
    if remove_latest_announcement_files():
        print("✅ JSON files cleanup completed")
    else:
        print("ℹ️ No JSON files to remove")
    
    # Step 4: Verification
    print("\n📋 Step 4: Verification...")
    verify_cleanup()
    
    print("\n🎉 CLEANUP COMPLETED!")
    print("\n📝 Next steps:")
    print("1. Restart scraper containers: docker-compose -f docker-compose.redis.yml restart bse-scraper nse-scraper")
    print("2. Monitor scraping: docker logs -f backfin-bse-scraper")
    print("3. Scrapers will now process ALL announcements for today")

if __name__ == "__main__":
    main()