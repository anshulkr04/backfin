#!/usr/bin/env python3
"""
Historical Deals Data Collection Script
Collects bulk and block deals data from Nov 25, 2025 to Jan 16, 2026

This script uses the same logic as deals_detector.py but iterates
through the historical date range day by day to ensure complete
data coverage from both NSE and BSE exchanges.

Usage:
    python collect_historical_deals.py
"""

import os
import sys
from datetime import datetime, timedelta
import logging
import pandas as pd
from dotenv import load_dotenv

# Add the deals_management directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src/services/exchange_data/deals_management'))

from data_fetchers.nse_fetcher import NSEDataFetcher
from data_fetchers.bse_fetcher import BSEDataFetcher
from processors.normalizer import DataNormalizer
from processors.deduplicator import DealsDeduplicator
from deals_detector import get_supabase_client, check_duplicate_deal

# Load environment
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('HistoricalDeals')


def insert_deals_to_table(df: pd.DataFrame, supabase):
    """
    Insert deals directly into deals table with duplicate prevention.
    
    Args:
        df: DataFrame with deduplicated deals
        supabase: Supabase client
    """
    if df.empty:
        logger.info("No deals to insert")
        return 0
    
    logger.info(f"Preparing {len(df)} deals for insertion into deals table")
    
    # Prepare records for insertion
    records = []
    duplicates_skipped = 0
    
    for idx, row in df.iterrows():
        # Check for duplicates
        is_duplicate = check_duplicate_deal(
            supabase,
            symbol=row['symbol'],
            client_name=row['client_name'],
            deal_type=row['deal_type'],
            quantity=int(row['quantity']),
            price=str(row['price']),
            date=str(row['date']),
            exchange=row['exchange'],
            deal=row['deal']
        )
        
        if is_duplicate:
            duplicates_skipped += 1
            continue
        
        # Prepare record for deals table
        record = {
            'symbol': row['symbol'],
            'securityid': row.get('securityid'),
            'date': str(row['date']),
            'client_name': row['client_name'],
            'deal_type': row['deal_type'],
            'quantity': int(row['quantity']),
            'price': str(row['price']),
            'exchange': row['exchange'],
            'deal': row['deal']
        }
        
        records.append(record)
    
    logger.info(f"Inserting {len(records)} new deals (skipped {duplicates_skipped} duplicates)")
    
    if not records:
        logger.info("No new deals to insert (all were duplicates)")
        return 0
    
    # Insert in batches directly into deals table
    batch_size = 100
    total_inserted = 0
    
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        try:
            resp = supabase.table("deals").insert(batch).execute()
            batch_inserted = len(resp.data) if resp.data else 0
            total_inserted += batch_inserted
            logger.info(f"Inserted batch {i // batch_size + 1}: {batch_inserted} records")
        except Exception as e:
            logger.error(f"Error inserting batch {i // batch_size + 1}: {e}")
    
    logger.info(f"✅ Successfully inserted {total_inserted} deals into deals table")
    
    return total_inserted


def collect_deals_for_date(date_obj: datetime, nse_fetcher, bse_fetcher, supabase):
    """
    Collect deals for a specific date.
    
    Args:
        date_obj: Date to collect data for
        nse_fetcher: NSE data fetcher instance
        bse_fetcher: BSE data fetcher instance
        supabase: Supabase client
        
    Returns:
        Number of records inserted
    """
    date_str_nse = date_obj.strftime("%d-%m-%Y")  # NSE format: DD-MM-YYYY
    date_str_display = date_obj.strftime("%Y-%m-%d")
    
    logger.info(f"\n{'='*100}")
    logger.info(f"Processing Date: {date_str_display}")
    logger.info(f"{'='*100}")
    
    try:
        # Fetch NSE data
        logger.info("Fetching NSE data...")
        nse_bulk_raw = nse_fetcher.fetch_bulk_deals(date_str_nse)
        nse_block_raw = nse_fetcher.fetch_block_deals(date_str_nse)
        
        # Fetch BSE data
        logger.info("Fetching BSE data...")
        bse_bulk_raw = bse_fetcher.fetch_bulk_deals()
        bse_block_raw = bse_fetcher.fetch_block_deals()
        
        # Normalize data
        logger.info("Normalizing data...")
        nse_bulk_df = DataNormalizer.normalize_nse_bulk(nse_bulk_raw or [])
        nse_block_df = DataNormalizer.normalize_nse_block(nse_block_raw or [])
        bse_bulk_df = DataNormalizer.normalize_bse_bulk(bse_bulk_raw or [])
        bse_block_df = DataNormalizer.normalize_bse_block(bse_block_raw or [])
        
        logger.info(f"NSE Bulk: {len(nse_bulk_df)}, NSE Block: {len(nse_block_df)}")
        logger.info(f"BSE Bulk: {len(bse_bulk_df)}, BSE Block: {len(bse_block_df)}")
        
        # Combine and deduplicate
        logger.info("Combining and deduplicating...")
        bulk_combined = pd.concat([nse_bulk_df, bse_bulk_df], ignore_index=True)
        block_combined = pd.concat([nse_block_df, bse_block_df], ignore_index=True)
        
        bulk_dedup, _ = DealsDeduplicator.deduplicate(bulk_combined)
        block_dedup, _ = DealsDeduplicator.deduplicate(block_combined)
        
        # Combine all final deals
        all_deals = pd.concat([bulk_dedup, block_dedup], ignore_index=True)
        
        if all_deals.empty:
            logger.info(f"✓ No deals found for {date_str_display}")
            return 0
        
        logger.info(f"Total deals after deduplication: {len(all_deals)}")
        
        # Insert into database
        records_inserted = insert_deals_to_table(all_deals, supabase)
        
        return records_inserted
        
    except Exception as e:
        logger.error(f"❌ Error processing {date_str_display}: {e}", exc_info=True)
        return 0


def collect_historical_data(start_date: datetime, end_date: datetime):
    """
    Collect deals data for a historical date range.
    
    Args:
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
    """
    logger.info("=" * 100)
    logger.info("HISTORICAL DEALS DATA COLLECTION")
    logger.info("=" * 100)
    logger.info(f"Date Range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    logger.info(f"Total Days: {(end_date - start_date).days + 1}")
    logger.info("=" * 100)
    
    # Get Supabase client
    supabase = get_supabase_client()
    
    # Initialize fetchers once
    logger.info("Initializing data fetchers...")
    nse_fetcher = NSEDataFetcher()
    bse_fetcher = BSEDataFetcher(headless=True)
    
    # Track statistics
    total_days = 0
    successful_days = 0
    failed_days = 0
    total_records_inserted = 0
    
    try:
        # Iterate through each day in the range
        current_date = start_date
        
        while current_date <= end_date:
            total_days += 1
            
            try:
                records_inserted = collect_deals_for_date(
                    current_date, 
                    nse_fetcher, 
                    bse_fetcher, 
                    supabase
                )
                
                if records_inserted >= 0:  # 0 is success (no data), >= 1 is success (data inserted)
                    successful_days += 1
                    total_records_inserted += records_inserted
                    if records_inserted > 0:
                        logger.info(f"✅ {current_date.strftime('%Y-%m-%d')}: {records_inserted} records inserted")
                else:
                    failed_days += 1
                    
            except Exception as e:
                logger.error(f"❌ Failed processing {current_date.strftime('%Y-%m-%d')}: {e}")
                failed_days += 1
            
            # Move to next day
            current_date += timedelta(days=1)
            
    finally:
        # Always close connections
        logger.info("\nClosing connections...")
        nse_fetcher.close()
        bse_fetcher.close()
    
    # Print summary
    logger.info("\n" + "=" * 100)
    logger.info("HISTORICAL DATA COLLECTION SUMMARY")
    logger.info("=" * 100)
    logger.info(f"Date Range:          {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    logger.info(f"Total Days:          {total_days}")
    logger.info(f"Successful Days:     {successful_days}")
    logger.info(f"Failed Days:         {failed_days}")
    logger.info(f"Total Records:       {total_records_inserted}")
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
