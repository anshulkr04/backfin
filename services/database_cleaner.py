#!/usr/bin/env python3
"""
Database Cleanup Service for Backfin
Cleans up bse_raw.db daily at 12:30 AM to manage storage space
"""

import os
import sqlite3
import logging
import schedule
import time
from datetime import datetime, timedelta
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DatabaseCleaner:
    def __init__(self, db_path="./data/bse_raw.db", cleanup_mode="previous_day"):
        """
        Initialize database cleaner
        
        Args:
            db_path: Path to the SQLite database
            cleanup_mode: 'previous_day' (default) or 'retention_days'
        """
        self.db_path = Path(db_path)
        self.cleanup_mode = cleanup_mode
        self.backup_dir = self.db_path.parent / "backups"
        
        # Create backup directory if it doesn't exist
        self.backup_dir.mkdir(exist_ok=True)
        
        logger.info(f"Database cleaner initialized for {self.db_path}")
        logger.info(f"Cleanup mode: {self.cleanup_mode}")

    def get_db_size(self):
        """Get current database size in MB"""
        if self.db_path.exists():
            size_bytes = self.db_path.stat().st_size
            size_mb = size_bytes / (1024 * 1024)
            return size_mb
        return 0

    def backup_database(self):
        """Create a backup of the database before cleanup"""
        if not self.db_path.exists():
            logger.warning(f"Database {self.db_path} does not exist, skipping backup")
            return None
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"bse_raw_backup_{timestamp}.db"
        backup_path = self.backup_dir / backup_name
        
        try:
            # Use SQLite backup API for consistency
            source_conn = sqlite3.connect(self.db_path)
            backup_conn = sqlite3.connect(backup_path)
            
            source_conn.backup(backup_conn)
            
            source_conn.close()
            backup_conn.close()
            
            logger.info(f"Database backed up to {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"Failed to backup database: {e}")
            return None

    def cleanup_old_data(self):
        """Clean up all data before today from the database"""
        if not self.db_path.exists():
            logger.warning(f"Database {self.db_path} does not exist, skipping cleanup")
            return False
        
        # Calculate date ranges
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        logger.info(f"Cleaning ALL data before today: {today_start.strftime('%Y-%m-%d')}")
        logger.info(f"Keeping only TODAY'S data: {today_start.strftime('%Y-%m-%d')} onwards")
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get list of tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            
            total_deleted = 0
            
            for (table_name,) in tables:
                # Skip system tables
                if table_name.startswith('sqlite_'):
                    continue
                    
                # Check if table has date/timestamp columns
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                
                date_columns = []
                for col in columns:
                    col_name = col[1].lower()
                    if any(keyword in col_name for keyword in ['date', 'time', 'created', 'updated', 'timestamp']):
                        date_columns.append(col[1])
                
                # Delete all records before today
                for date_col in date_columns:
                    try:
                        # Try different date formats to handle various timestamp formats
                        delete_queries = [
                            # ISO format (YYYY-MM-DD HH:MM:SS) - before today
                            f"""
                            DELETE FROM {table_name} 
                            WHERE date({date_col}) < date(?)
                            AND {date_col} IS NOT NULL
                            """,
                            # Unix timestamp format - before today
                            f"""
                            DELETE FROM {table_name} 
                            WHERE date(datetime({date_col}, 'unixepoch')) < date(?)
                            AND {date_col} IS NOT NULL
                            """,
                            # String date format - before today
                            f"""
                            DELETE FROM {table_name} 
                            WHERE {date_col} < ?
                            AND {date_col} IS NOT NULL
                            AND length({date_col}) >= 10
                            """
                        ]
                        
                        today_date_str = today_start.strftime('%Y-%m-%d')
                        
                        for i, delete_query in enumerate(delete_queries):
                            try:
                                if i == 2:  # String format query
                                    cursor.execute(delete_query, (today_date_str,))
                                else:
                                    cursor.execute(delete_query, (today_date_str,))
                                
                                deleted_count = cursor.rowcount
                                
                                if deleted_count > 0:
                                    total_deleted += deleted_count
                                    logger.info(f"Deleted {deleted_count} historical records from {table_name}.{date_col} (method {i+1})")
                                    break  # Successfully deleted, no need to try other formats
                                    
                            except sqlite3.Error as e:
                                if i == len(delete_queries) - 1:  # Last attempt failed
                                    logger.warning(f"Could not clean {table_name}.{date_col}: {e}")
                                continue
                            
                    except Exception as e:
                        logger.warning(f"Error processing {table_name}.{date_col}: {e}")
                        continue
            
            # Vacuum database to reclaim space
            cursor.execute("VACUUM;")
            conn.commit()
            conn.close()
            
            logger.info(f"Historical data cleanup completed. Total records deleted: {total_deleted}")
            logger.info("KEPT: Only today's data onwards")
            return True
            
        except Exception as e:
            logger.error(f"Database cleanup failed: {e}")
            return False

    def cleanup_old_backups(self, backup_retention_days=30):
        """Clean up old backup files"""
        cutoff_date = datetime.now() - timedelta(days=backup_retention_days)
        
        try:
            deleted_backups = 0
            for backup_file in self.backup_dir.glob("bse_raw_backup_*.db"):
                file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
                
                if file_time < cutoff_date:
                    backup_file.unlink()
                    deleted_backups += 1
                    logger.info(f"Deleted old backup: {backup_file.name}")
            
            if deleted_backups > 0:
                logger.info(f"Cleaned up {deleted_backups} old backup files")
                
        except Exception as e:
            logger.error(f"Failed to cleanup old backups: {e}")

    def perform_cleanup(self):
        """Perform complete cleanup process"""
        logger.info("Starting scheduled database cleanup - DELETE ALL HISTORICAL DATA...")
        
        # Get initial size
        initial_size = self.get_db_size()
        logger.info(f"Database size before cleanup: {initial_size:.2f} MB")
        
        # Show what we're keeping
        today = datetime.now().strftime('%Y-%m-%d')
        logger.info(f"DELETING: All data before {today}")
        logger.info(f"KEEPING: Only {today} onwards")
        
        # Create backup
        backup_path = self.backup_database()
        
        # Perform cleanup
        cleanup_success = self.cleanup_old_data()
        
        if cleanup_success:
            # Get final size
            final_size = self.get_db_size()
            space_saved = initial_size - final_size
            
            logger.info(f"Database size after cleanup: {final_size:.2f} MB")
            logger.info(f"Space saved: {space_saved:.2f} MB")
            
            # Cleanup old backups
            self.cleanup_old_backups()
            
            logger.info("Historical data cleanup completed successfully")
        else:
            logger.error("Database cleanup failed")
            
        return cleanup_success

def main():
    """Main function to run the database cleaner"""
    logger.info("Starting Database Cleanup Service - DELETE ALL HISTORICAL DATA MODE")
    
    # Configuration from environment variables
    db_path = os.getenv('DB_PATH', './data/bse_raw.db')
    cleanup_time = os.getenv('CLEANUP_TIME', '00:30')  # 12:30 AM
    
    # Initialize cleaner in historical cleanup mode
    cleaner = DatabaseCleaner(db_path=db_path, cleanup_mode="historical_cleanup")
    
    # Schedule daily cleanup
    schedule.every().day.at(cleanup_time).do(cleaner.perform_cleanup)
    
    logger.info(f"Scheduled daily cleanup at {cleanup_time}")
    logger.info(f"Database: {db_path}")
    logger.info(f"Mode: DELETE ALL DATA BEFORE TODAY")
    
    # Run initial cleanup on startup (clean all historical data)
    logger.info("Running initial cleanup - deleting all historical data...")
    cleaner.perform_cleanup()
    
    # Keep the service running
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
            
    except KeyboardInterrupt:
        logger.info("Database cleanup service stopped")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()