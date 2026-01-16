#!/usr/bin/env python3
"""
Historical Corporate Actions Data Collection Script
Collects corporate actions data from Nov 25, 2025 to Jan 16, 2026

This script uses the same logic as corporate_actions_collector.py
but iterates through the historical date range day by day to ensure
complete data coverage.

Usage:
    python collect_historical_corporate_actions.py
"""

import os
import sys
from datetime import datetime, timedelta
import logging

# Add the corporate_actions directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src/services/exchange_data/corporate_actions'))

from corporate_actions_collector import CorporateActionsCollector

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('HistoricalCorporateActions')


def collect_historical_data(start_date: datetime, end_date: datetime):
    """
    Collect corporate actions data for a historical date range.
    
    Args:
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
    """
    logger.info("=" * 100)
    logger.info("HISTORICAL CORPORATE ACTIONS DATA COLLECTION")
    logger.info("=" * 100)
    logger.info(f"Date Range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    logger.info(f"Total Days: {(end_date - start_date).days + 1}")
    logger.info("=" * 100)
    
    # Initialize collector
    collector = CorporateActionsCollector()
    
    # Track statistics
    total_days = 0
    successful_days = 0
    failed_days = 0
    total_records_uploaded = 0
    
    # Iterate through each day in the range
    current_date = start_date
    
    while current_date <= end_date:
        total_days += 1
        date_str = current_date.strftime('%Y-%m-%d')
        
        logger.info("\n" + "=" * 100)
        logger.info(f"Processing Date: {date_str} (Day {total_days}/{(end_date - start_date).days + 1})")
        logger.info("=" * 100)
        
        try:
            # Format dates for each API
            # BSE format: YYYYMMDD
            bse_date = current_date.strftime("%Y%m%d")
            
            # NSE format: DD-MM-YYYY
            nse_date = current_date.strftime("%d-%m-%Y")
            
            # DB query format: YYYY-MM-DD
            db_date = date_str
            
            # Collect NSE data
            nse_df = collector.process_nse_data(nse_date, nse_date)
            
            # Collect BSE data
            bse_df = collector.process_bse_data(bse_date, bse_date)
            
            # Check if we have any data
            if nse_df.empty and bse_df.empty:
                logger.info(f"✓ No data found for {date_str}")
                successful_days += 1
                current_date += timedelta(days=1)
                continue
            
            # Combine data
            import pandas as pd
            combined_df = pd.concat([nse_df, bse_df], ignore_index=True)
            logger.info(f"Combined total: {len(combined_df)} records")
            
            # Get existing records from database
            existing_keys = collector.get_existing_records_from_db(db_date, db_date)
            
            # Deduplicate
            deduped_df = collector.deduplicate_data(combined_df, existing_keys)
            
            if deduped_df.empty:
                logger.info(f"✓ No new records to upload for {date_str} (all duplicates)")
                successful_days += 1
                current_date += timedelta(days=1)
                continue
            
            # Prepare and upload
            records = collector.prepare_for_upload(deduped_df)
            success = collector.upload_to_supabase(records)
            
            if success:
                logger.info(f"✅ Successfully processed {date_str}: {len(records)} records uploaded")
                successful_days += 1
                total_records_uploaded += len(records)
            else:
                logger.error(f"❌ Failed to upload records for {date_str}")
                failed_days += 1
            
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
    start_date = datetime(2025, 11, 25)
    end_date = datetime(2026, 1, 16)
    
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
