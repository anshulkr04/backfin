#!/usr/bin/env python3
"""
Manual Database Cleanup Script
Run this to immediately clean up bse_raw.db
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.database_cleaner import DatabaseCleaner
from datetime import datetime
import argparse

def main():
    parser = argparse.ArgumentParser(description='Clean up bse_raw.db database')
    parser.add_argument('--db-path', default='./data/bse_raw.db', help='Path to database file')
    parser.add_argument('--mode', choices=['historical', 'retention'], default='historical', 
                       help='Cleanup mode: historical (delete all before today) or retention (clean old data)')
    parser.add_argument('--retention-days', type=int, default=7, help='Days to retain data (retention mode only)')
    parser.add_argument('--no-backup', action='store_true', help='Skip backup creation')
    parser.add_argument('--force', action='store_true', help='Force cleanup without confirmation')
    
    args = parser.parse_args()
    
    if args.mode == 'historical':
        cleaner = DatabaseCleaner(db_path=args.db_path, cleanup_mode="historical_cleanup")
        today = datetime.now().strftime('%Y-%m-%d')
        mode_desc = f"ALL DATA BEFORE TODAY ({today})"
    else:
        cleaner = DatabaseCleaner(db_path=args.db_path, cleanup_mode="retention_days")
        cleaner.retention_days = args.retention_days
        mode_desc = f"data older than {args.retention_days} days"
    
    # Show current size
    current_size = cleaner.get_db_size()
    print(f"Current database size: {current_size:.2f} MB")
    print(f"Cleanup mode: {args.mode}")
    
    if not args.force:
        print(f"⚠️  WARNING: This will delete {mode_desc}")
        if args.mode == 'historical':
            print(f"   KEEPING: Only today's data ({today}) onwards")
            print(f"   DELETING: Everything before {today}")
        confirm = input(f"Are you sure? (y/N): ")
        if confirm.lower() != 'y':
            print("Cleanup cancelled")
            return
    
    # Perform cleanup
    success = cleaner.perform_cleanup()
    
    if success:
        new_size = cleaner.get_db_size()
        space_saved = current_size - new_size
        print(f"✅ Cleanup completed!")
        print(f"   Space saved: {space_saved:.2f} MB")
        print(f"   New size: {new_size:.2f} MB")
    else:
        print("❌ Cleanup failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()