#!/usr/bin/env python3
"""
Historical Insider Trading Data Collection Script
Collects insider trading data from Nov 25, 2025 to Jan 16, 2026

This script uses the same logic as insider_trading_detector.py but iterates
through the historical date range day by day to ensure complete data coverage
from both NSE and BSE exchanges.

Usage:
    python collect_historical_insider_trading.py
"""

import os
import sys
from datetime import datetime, timedelta
import logging
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

# Add the insider_trading directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src/services/exchange_data/insider_trading'))

from insider_trading_detector import NSEInsiderScraper, BSEInsiderScraper, InsiderTradingManager

# Load environment
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('HistoricalInsiderTrading')


def collect_historical_data(start_date: datetime, end_date: datetime):
    """
    Collect insider trading data for a historical date range.
    
    Args:
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
    """
    logger.info("=" * 100)
    logger.info("HISTORICAL INSIDER TRADING DATA COLLECTION")
    logger.info("=" * 100)
    logger.info(f"Date Range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    logger.info(f"Total Days: {(end_date - start_date).days + 1}")
    logger.info("=" * 100)
    
    # Initialize manager
    manager = InsiderTradingManager()
    
    # Track statistics
    total_days = 0
    successful_days = 0
    failed_days = 0
    total_records_uploaded = 0
    
    # Iterate through each day in the range
    current_date = start_date
    
    while current_date <= end_date:
        total_days += 1
        
        # Format date for APIs (DD-MM-YYYY)
        from_date = current_date.strftime("%d-%m-%Y")
        to_date = current_date.strftime("%d-%m-%Y")
        
        # Format for display
        date_str = current_date.strftime('%Y-%m-%d')
        
        logger.info("\n" + "=" * 100)
        logger.info(f"Processing Date: {date_str} (Day {total_days}/{(end_date - start_date).days + 1})")
        logger.info("=" * 100)
        
        try:
            all_data = []
            
            # Collect NSE data
            logger.info("\nCollecting NSE Data...")
            logger.info("=" * 50)
            
            try:
                nse_data = manager.nse_scraper.scrape_data(from_date, to_date)
                if nse_data:
                    nse_df = manager.nse_scraper.process_nse_data(nse_data)
                    if not nse_df.empty:
                        all_data.append(nse_df)
                        logger.info(f"NSE: Collected {len(nse_df)} records")
                    else:
                        logger.info("NSE: No records found")
                else:
                    logger.info("NSE: No data retrieved")
            except Exception as e:
                logger.error(f"NSE: Collection failed: {e}")
            finally:
                manager.nse_scraper.close()
                # Reinitialize for next iteration
                manager.nse_scraper = NSEInsiderScraper()
            
            # Collect BSE data
            logger.info("\nCollecting BSE Data...")
            logger.info("=" * 50)
            
            try:
                bse_csv_path = manager.bse_scraper.scrape_data()
                if bse_csv_path and os.path.exists(bse_csv_path):
                    bse_df = manager.bse_scraper.process_bse_csv(bse_csv_path)
                    if not bse_df.empty:
                        all_data.append(bse_df)
                        logger.info(f"BSE: Collected {len(bse_df)} records")
                    else:
                        logger.info("BSE: No records found")
                else:
                    logger.info("BSE: No data retrieved")
            except Exception as e:
                logger.error(f"BSE: Collection failed: {e}")
            
            # Check if we have any data
            if not all_data:
                logger.info(f"✓ No data found for {date_str}")
                successful_days += 1
                current_date += timedelta(days=1)
                continue
            
            # Combine and deduplicate
            logger.info("\nDeduplication...")
            logger.info("=" * 50)
            
            combined_df = pd.concat(all_data, ignore_index=True)
            logger.info(f"Combined total: {len(combined_df)} records")
            
            # Get existing records from database to avoid duplicates
            # Convert date format for database query (YYYY-MM-DD)
            db_date = current_date.strftime("%Y-%m-%d")
            existing_keys = manager.get_existing_records_from_db(db_date, db_date)
            
            # Deduplicate against new data and existing database records
            deduped_df = manager.deduplicate_data(combined_df, existing_keys)
            
            if deduped_df.empty:
                logger.info(f"✓ No new records to upload for {date_str} (all duplicates)")
                successful_days += 1
                current_date += timedelta(days=1)
                continue
            
            # Upload to database
            logger.info("\nUploading to Database...")
            logger.info("=" * 50)
            
            records = manager.prepare_for_upload(deduped_df)
            
            if records:
                success = manager.upload_to_database(records)
                if success:
                    logger.info(f"✅ Successfully processed {date_str}: {len(records)} records uploaded")
                    successful_days += 1
                    total_records_uploaded += len(records)
                else:
                    logger.error(f"❌ Failed to upload records for {date_str}")
                    failed_days += 1
            else:
                logger.info(f"✓ No records to upload for {date_str}")
                successful_days += 1
            
            # Cleanup temp files
            manager.cleanup_temp_files()
            
        except Exception as e:
            logger.error(f"❌ Error processing {date_str}: {e}", exc_info=True)
            failed_days += 1
        
        # Move to next day
        current_date += timedelta(days=1)
    
    # Print summary
    logger.info("\n" + "=" * 100)
    logger.info("HISTORICAL DATA COLLECTION SUMMARY")
    logger.info("=" * 100)
    logger.info(f"Date Range:          {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    logger.info(f"Total Days:          {total_days}")
    logger.info(f"Successful Days:     {successful_days}")
    logger.info(f"Failed Days:         {failed_days}")
    logger.info(f"Total Records:       {total_records_uploaded}")
    logger.info("=" * 100)
    
    if failed_days == 0:
        logger.info("✅ All days processed successfully!")
    else:
        logger.warning(f"⚠️  {failed_days} days failed - check logs above for details")


def main():
    """Main entry point"""
    # Define date range
    # From: November 25, 2025
    # To: January 16, 2026 (today)
    start_date = datetime(2026, 1, 17)
    end_date = datetime(2026, 1, 20)
    
    try:
        collect_historical_data(start_date, end_date)
    except KeyboardInterrupt:
        logger.info("\n⏹️  Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"\n💥 Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
