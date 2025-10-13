#!/usr/bin/env python3
"""
Debug script to check scraping status for today
"""

import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

def check_latest_announcements():
    """Check the latest announcement JSON files"""
    data_dir = Path("data")
    
    print("🔍 Checking latest announcement files...")
    
    # Check BSE
    bse_file = data_dir / "latest_announcement_bse_scraper.json"
    if bse_file.exists():
        with open(bse_file, 'r') as f:
            bse_data = json.load(f)
        print(f"📅 BSE Last Announcement: {bse_data.get('DT', 'Unknown date')}")
        print(f"📰 BSE Last NEWSID: {bse_data.get('NEWSID', 'Unknown')}")
    else:
        print("❌ BSE latest announcement file not found")
    
    # Check NSE
    nse_file = data_dir / "latest_announcement_nse_scraper.json"
    if nse_file.exists():
        with open(nse_file, 'r') as f:
            nse_data = json.load(f)
        print(f"📅 NSE Last Announcement: {nse_data.get('AN_DT', 'Unknown date')}")
        print(f"📰 NSE Last ID: {nse_data.get('SM_NAME', 'Unknown')}")
    else:
        print("❌ NSE latest announcement file not found")

def check_database_status():
    """Check database for today's entries"""
    db_path = "data/bse_raw.db"
    
    if not os.path.exists(db_path):
        print("❌ Database file not found")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check recent entries
        today = datetime.now().strftime('%Y-%m-%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        cursor.execute("""
            SELECT COUNT(*) FROM announcements 
            WHERE date(fetched_at) = ?
        """, (today,))
        today_count = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM announcements 
            WHERE date(fetched_at) = ?
        """, (yesterday,))
        yesterday_count = cursor.fetchone()[0]
        
        print(f"📊 Database Status:")
        print(f"   Today ({today}): {today_count} announcements")
        print(f"   Yesterday ({yesterday}): {yesterday_count} announcements")
        
        # Check latest entries
        cursor.execute("""
            SELECT newsid, headline, fetched_at, ai_processed, sent_to_supabase
            FROM announcements 
            ORDER BY fetched_at DESC 
            LIMIT 5
        """)
        recent = cursor.fetchall()
        
        print(f"📋 Latest 5 entries:")
        for row in recent:
            newsid, headline, fetched_at, ai_processed, sent_to_supabase = row
            print(f"   {newsid}: {headline[:50]}... (AI: {ai_processed}, Sent: {sent_to_supabase})")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Database error: {e}")

def check_container_logs():
    """Provide commands to check container logs"""
    print("\n🔧 To check container logs, run:")
    print("docker logs backfin-bse-scraper --tail 20")
    print("docker logs backfin-nse-scraper --tail 20")
    print("docker logs backfin-worker-spawner --tail 20")

def main():
    print("🚀 Backfin Scraping Debug Tool")
    print("=" * 50)
    
    check_latest_announcements()
    print()
    check_database_status()
    print()
    check_container_logs()

if __name__ == "__main__":
    main()