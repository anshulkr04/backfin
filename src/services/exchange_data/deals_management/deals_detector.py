#!/usr/bin/env python3
"""
Deals Detector - Main orchestrator for bulk and block deals detection.

This script:
1. Downloads bulk and block deals from NSE and BSE
2. Normalizes all data to standard format
3. Deduplicates across exchanges (keeps BSE when duplicate)
4. Submits to verification queue
5. Auto-populates securityid for NSE deals via database trigger

Usage:
    python deals_detector.py [--date DD-MM-YYYY] [--stats-only] [--keep-source-data]
"""

import os
import sys
import logging
import argparse
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
from dotenv import load_dotenv
from supabase import create_client

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_fetchers.nse_fetcher import NSEDataFetcher
from data_fetchers.bse_fetcher import BSEDataFetcher
from processors.normalizer import DataNormalizer
from processors.deduplicator import DealsDeduplicator

# Load environment
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_supabase_client():
    """Get Supabase client instance."""
    SUPABASE_URL = os.environ.get("SUPABASE_URL2") or os.environ.get("SUPABASE_URL")
    SUPABASE_KEY = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_KEY2")
        or os.environ.get("SUPABASE_ANON_KEY")
    )
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Missing Supabase credentials")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def get_deals_stats(supabase):
    """
    Get current deals table statistics.
    
    Args:
        supabase: Supabase client
    """
    try:
        # Count total deals
        resp = supabase.table("deals").select("*", count='exact').execute()
        total_count = resp.count if resp.count else 0
        
        # Get breakdown
        bulk_resp = supabase.table("deals").select("*", count='exact').eq("deal", "BULK").execute()
        block_resp = supabase.table("deals").select("*", count='exact').eq("deal", "BLOCK").execute()
        nse_resp = supabase.table("deals").select("*", count='exact').eq("exchange", "NSE").execute()
        bse_resp = supabase.table("deals").select("*", count='exact').eq("exchange", "BSE").execute()
        
        logger.info("=" * 80)
        logger.info("DEALS TABLE STATISTICS")
        logger.info("=" * 80)
        logger.info(f"Total deals in database:    {total_count}")
        logger.info("")
        logger.info("Breakdown by type:")
        logger.info(f"  Bulk deals:               {bulk_resp.count if bulk_resp.count else 0}")
        logger.info(f"  Block deals:              {block_resp.count if block_resp.count else 0}")
        logger.info("")
        logger.info("Breakdown by exchange:")
        logger.info(f"  NSE:                      {nse_resp.count if nse_resp.count else 0}")
        logger.info(f"  BSE:                      {bse_resp.count if bse_resp.count else 0}")
            
    except Exception as e:
        logger.error(f"Error fetching deals stats: {e}")


def check_duplicate_deal(
    supabase,
    symbol: str,
    client_name: str,
    deal_type: str,
    quantity: int,
    price: str,
    date: str,
    exchange: str,
    deal: str
) -> bool:
    """
    Check if an identical deal already exists in deals table.
    
    Args:
        supabase: Supabase client
        symbol: Symbol/security name
        client_name: Client name
        deal_type: BUY or SELL
        quantity: Quantity
        price: Price (4dp)
        date: Date (ISO format)
        exchange: NSE or BSE
        deal: BULK or BLOCK
        
    Returns:
        True if duplicate exists, False otherwise
    """
    try:
        # Check in deals table only (no verification queue)
        resp = supabase.table("deals")\
            .select("id")\
            .eq("symbol", symbol)\
            .eq("client_name", client_name)\
            .eq("deal_type", deal_type)\
            .eq("quantity", quantity)\
            .eq("price", price)\
            .eq("date", date)\
            .eq("exchange", exchange)\
            .eq("deal", deal)\
            .limit(1)\
            .execute()
        
        if resp.data and len(resp.data) > 0:
            return True
        
        return False
        
    except Exception as e:
        logger.warning(f"Error checking duplicate: {e}")
        return False


def insert_deals_to_table(df: pd.DataFrame, supabase, keep_source_data: bool = False):
    """
    Insert deals directly into deals table with duplicate prevention.
    No manual verification needed for bulk/block deals.
    
    Args:
        df: DataFrame with deduplicated deals
        supabase: Supabase client
        keep_source_data: Whether to keep source_data column
    """
    if df.empty:
        logger.info("No deals to insert")
        return
    
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
            logger.debug(
                f"Skipped duplicate: {row['exchange']} {row['deal']} | "
                f"{row['symbol']} | {row['client_name']} | {row['date']}"
            )
            continue
        
        # Prepare record for deals table (no verification fields needed)
        record = {
            'symbol': row['symbol'],
            'securityid': row.get('securityid'),  # Will be auto-populated by trigger for NSE
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
        return
    
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
    
    # Show breakdown
    df_inserted = df.iloc[[i for i, r in enumerate(df.to_dict('records')) if r in records]]
    if not df_inserted.empty:
        logger.info("\nInsertion breakdown:")
        for exchange in ['NSE', 'BSE']:
            for deal in ['BULK', 'BLOCK']:
                count = len(df_inserted[
                    (df_inserted['exchange'] == exchange) & 
                    (df_inserted['deal'] == deal)
                ])
                if count > 0:
                    logger.info(f"  {exchange} {deal}: {count}")


def download_all_deals(date_str: Optional[str] = None):
    """
    Download all bulk and block deals from NSE and BSE.
    
    Args:
        date_str: Date string in DD-MM-YYYY format (defaults to today)
        
    Returns:
        Tuple of (nse_bulk, nse_block, bse_bulk, bse_block) DataFrames
    """
    logger.info("=" * 80)
    logger.info("STEP 1: DOWNLOADING DEALS DATA")
    logger.info("=" * 80)
    
    # Initialize fetchers
    nse = NSEDataFetcher()
    bse = BSEDataFetcher(headless=True)
    
    try:
        # Fetch NSE data
        nse_bulk_raw = nse.fetch_bulk_deals(date_str)
        nse_block_raw = nse.fetch_block_deals(date_str)
        
        # Fetch BSE data
        bse_bulk_raw = bse.fetch_bulk_deals()
        bse_block_raw = bse.fetch_block_deals()
        
        # Normalize data
        logger.info("\n" + "=" * 80)
        logger.info("STEP 2: NORMALIZING DATA")
        logger.info("=" * 80)
        
        nse_bulk_df = DataNormalizer.normalize_nse_bulk(nse_bulk_raw or [])
        nse_block_df = DataNormalizer.normalize_nse_block(nse_block_raw or [])
        bse_bulk_df = DataNormalizer.normalize_bse_bulk(bse_bulk_raw or [])
        bse_block_df = DataNormalizer.normalize_bse_block(bse_block_raw or [])
        
        return nse_bulk_df, nse_block_df, bse_bulk_df, bse_block_df
        
    finally:
        # Always close connections
        nse.close()
        bse.close()


def deduplicate_deals(nse_bulk, nse_block, bse_bulk, bse_block):
    """
    Deduplicate deals across exchanges.
    
    Args:
        nse_bulk: NSE bulk deals DataFrame
        nse_block: NSE block deals DataFrame
        bse_bulk: BSE bulk deals DataFrame
        bse_block: BSE block deals DataFrame
        
    Returns:
        Tuple of (deduplicated_bulk, deduplicated_block)
    """
    logger.info("\n" + "=" * 80)
    logger.info("STEP 3: DEDUPLICATING DEALS")
    logger.info("=" * 80)
    
    # Combine bulk deals
    bulk_combined = pd.concat([nse_bulk, bse_bulk], ignore_index=True)
    logger.info(f"\nBulk deals - Total before dedup: {len(bulk_combined)}")
    
    # Combine block deals
    block_combined = pd.concat([nse_block, bse_block], ignore_index=True)
    logger.info(f"Block deals - Total before dedup: {len(block_combined)}")
    
    # Deduplicate
    bulk_dedup, bulk_removed = DealsDeduplicator.deduplicate(bulk_combined)
    block_dedup, block_removed = DealsDeduplicator.deduplicate(block_combined)
    
    logger.info(f"\nBulk deals after dedup: {len(bulk_dedup)} (removed {len(bulk_removed)})")
    logger.info(f"Block deals after dedup: {len(block_dedup)} (removed {len(block_removed)})")
    
    # Check for internal duplicates (data quality issue)
    bulk_internal = DealsDeduplicator.find_internal_duplicates(bulk_dedup)
    block_internal = DealsDeduplicator.find_internal_duplicates(block_dedup)
    
    return bulk_dedup, block_dedup


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="Detect and submit bulk/block deals for verification")
    parser.add_argument(
        '--date',
        type=str,
        help='Date to fetch deals for (DD-MM-YYYY format, defaults to today)'
    )
    parser.add_argument(
        '--stats-only',
        action='store_true',
        help='Only show verification queue statistics'
    )
    parser.add_argument(
        '--keep-source-data',
        action='store_true',
        help='Keep original source data in verification queue (for debugging)'
    )
    
    args = parser.parse_args()
    
    try:
        # Get Supabase client
        supabase = get_supabase_client()
        
        # Stats only mode
        if args.stats_only:
            get_deals_stats(supabase)
            return
        
        # Full detection workflow
        logger.info("Starting deals detection workflow")
        logger.info(f"Date: {args.date or 'Today'}")
        
        # Download and normalize
        nse_bulk, nse_block, bse_bulk, bse_block = download_all_deals(args.date)
        
        # Deduplicate
        bulk_final, block_final = deduplicate_deals(nse_bulk, nse_block, bse_bulk, bse_block)
        
        # Combine all final deals
        all_deals = pd.concat([bulk_final, block_final], ignore_index=True)
        
        logger.info("\n" + "=" * 80)
        logger.info("STEP 4: INSERTING INTO DEALS TABLE")
        logger.info("=" * 80)
        
        # Insert directly into deals table (no verification needed)
        insert_deals_to_table(all_deals, supabase, args.keep_source_data)
        
        logger.info("\n✅ Deals detection workflow completed successfully")
        
    except KeyboardInterrupt:
        logger.info("\n⚠️ Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"❌ Error in deals detection workflow: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
