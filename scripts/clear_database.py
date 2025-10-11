#!/usr/bin/env python3
"""
Clear Database Script

This script clears all data from the bse_raw.db file while preserving the table structure.
This ensures a clean start for the database without any old cached data.
"""

import sqlite3
import os
import sys
from pathlib import Path
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_database_path():
    """Get the path to the bse_raw.db file"""
    # Check multiple possible locations
    possible_paths = [
        Path("data/bse_raw.db"),
        Path("../data/bse_raw.db"),
        Path("./bse_raw.db"),
        Path("src/scrapers/data/bse_raw.db"),
        Path("../src/scrapers/data/bse_raw.db")
    ]
    
    for path in possible_paths:
        if path.exists():
            return path.resolve()
    
    return None

def backup_database(db_path):
    """Create a backup of the database before clearing"""
    if not db_path.exists():
        logger.warning(f"Database file not found: {db_path}")
        return None
        
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.parent / f"bse_raw_backup_{timestamp}.db"
    
    try:
        import shutil
        shutil.copy2(db_path, backup_path)
        logger.info(f"✅ Database backed up to: {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"❌ Failed to create backup: {e}")
        return None

def get_table_names(cursor):
    """Get all table names in the database"""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    return [table[0] for table in tables]

def get_table_info(cursor, table_name):
    """Get table schema information"""
    cursor.execute(f"PRAGMA table_info({table_name});")
    return cursor.fetchall()

def clear_database(db_path, create_backup=True):
    """Clear all data from the database while preserving structure"""
    
    if not db_path:
        logger.error("❌ Database file not found!")
        return False
        
    if not db_path.exists():
        logger.warning(f"Database file does not exist: {db_path}")
        return True  # Nothing to clear
    
    logger.info(f"🗂️  Found database: {db_path}")
    
    # Create backup if requested
    if create_backup:
        backup_path = backup_database(db_path)
        if not backup_path:
            response = input("⚠️  Backup failed. Continue without backup? (y/N): ")
            if response.lower() != 'y':
                logger.info("Operation cancelled")
                return False
    
    try:
        # Connect to database
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Get all table names
        tables = get_table_names(cursor)
        logger.info(f"📋 Found {len(tables)} tables: {', '.join(tables)}")
        
        if not tables:
            logger.info("✅ Database is empty (no tables found)")
            conn.close()
            return True
        
        # Show current row counts
        logger.info("📊 Current row counts:")
        total_rows = 0
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table};")
                count = cursor.fetchone()[0]
                logger.info(f"   {table}: {count:,} rows")
                total_rows += count
            except Exception as e:
                logger.warning(f"   {table}: Error counting rows - {e}")
        
        logger.info(f"📈 Total rows across all tables: {total_rows:,}")
        
        if total_rows == 0:
            logger.info("✅ Database is already empty")
            conn.close()
            return True
        
        # Confirm deletion
        print(f"\n⚠️  This will DELETE ALL DATA from {total_rows:,} rows in {len(tables)} tables!")
        print(f"Database: {db_path}")
        response = input("Are you sure you want to continue? (type 'YES' to confirm): ")
        
        if response != 'YES':
            logger.info("Operation cancelled")
            conn.close()
            return False
        
        # Clear all tables
        logger.info("🧹 Clearing all tables...")
        cleared_tables = 0
        
        for table in tables:
            try:
                # Delete all rows from table
                cursor.execute(f"DELETE FROM {table};")
                rows_affected = cursor.rowcount
                logger.info(f"   ✅ Cleared {table}: {rows_affected:,} rows deleted")
                cleared_tables += 1
            except Exception as e:
                logger.error(f"   ❌ Failed to clear {table}: {e}")
        
        # Commit changes
        conn.commit()
        
        # Vacuum to reclaim space
        logger.info("🗜️  Vacuuming database to reclaim space...")
        cursor.execute("VACUUM;")
        
        # Verify tables are empty
        logger.info("🔍 Verifying tables are empty:")
        all_empty = True
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table};")
                count = cursor.fetchone()[0]
                if count == 0:
                    logger.info(f"   ✅ {table}: empty")
                else:
                    logger.warning(f"   ⚠️  {table}: still has {count} rows")
                    all_empty = False
            except Exception as e:
                logger.error(f"   ❌ {table}: Error verifying - {e}")
                all_empty = False
        
        conn.close()
        
        if all_empty:
            logger.info("✅ Database successfully cleared!")
            logger.info(f"📁 Table structure preserved ({len(tables)} tables)")
            
            # Show final file size
            file_size = db_path.stat().st_size
            logger.info(f"📏 Final database size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
            
            return True
        else:
            logger.error("❌ Some tables were not fully cleared")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error clearing database: {e}")
        return False

def main():
    """Main function"""
    print("🗄️  BSE Raw Database Cleaner")
    print("=" * 50)
    
    # Find database
    db_path = get_database_path()
    
    if not db_path:
        logger.error("❌ Could not find bse_raw.db file!")
        logger.info("Searched in:")
        logger.info("  - data/bse_raw.db")
        logger.info("  - ../data/bse_raw.db") 
        logger.info("  - ./bse_raw.db")
        logger.info("  - src/scrapers/data/bse_raw.db")
        logger.info("  - ../src/scrapers/data/bse_raw.db")
        return 1
    
    # Clear database
    success = clear_database(db_path, create_backup=True)
    
    if success:
        print("\n🎉 Database cleared successfully!")
        print("The scrapers will now populate fresh data when they run.")
        return 0
    else:
        print("\n💥 Database clearing failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())