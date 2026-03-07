#!/usr/bin/env python3
"""
Backfill Sector and Market Cap Data

Reads sector and market cap data from tet.json (sourced externally),
matches by symbol against stocklistdata, and updates the database.

Steps:
1. Read tet.json for sector/marketcap data
2. Fetch all symbols from stocklistdata
3. Match by symbol (case-insensitive) and update sector + market_cap
4. Report match statistics

Usage:
    python3 backfill_sector_marketcap.py
    python3 backfill_sector_marketcap.py --dry-run    # Preview only, no writes
"""

import json
import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL2")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


def load_tet_data(filepath: str = "tet.json") -> dict:
    """Load tet.json and index by symbol (uppercase)"""
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    # Index by symbol for fast lookup
    symbol_map = {}
    skipped = 0
    for record in data:
        symbol = record.get('symbol')
        if not symbol:
            skipped += 1
            continue
        symbol_upper = symbol.strip().upper()
        # If duplicate symbol, keep the one with higher market cap
        if symbol_upper in symbol_map:
            if (record.get('marketCap') or 0) > (symbol_map[symbol_upper].get('marketCap') or 0):
                symbol_map[symbol_upper] = record
        else:
            symbol_map[symbol_upper] = record
    
    logger.info(f"Loaded {len(symbol_map)} unique symbols from tet.json (skipped {skipped} with null symbol)")
    return symbol_map


def fetch_stocklistdata(supabase) -> list:
    """Fetch all records from stocklistdata"""
    all_rows = []
    batch_size = 1000
    start = 0
    
    while True:
        end = start + batch_size - 1
        resp = supabase.table('stocklistdata').select('isin, symbol, newbsecode, newnsecode, sector, newname').range(start, end).execute()
        rows = resp.data if hasattr(resp, 'data') else []
        
        if not rows:
            break
        
        all_rows.extend(rows)
        start += batch_size
        
        if len(rows) < batch_size:
            break
    
    logger.info(f"Fetched {len(all_rows)} records from stocklistdata")
    return all_rows


def match_and_update(supabase, stocklist: list, tet_map: dict, dry_run: bool = False):
    """Match stocklistdata symbols against tet.json and update sector + market_cap"""
    
    matched = 0
    not_matched = 0
    updated = 0
    errors = 0
    skipped_no_change = 0
    
    # For each stock in our database, try to find it in tet.json
    for i, stock in enumerate(stocklist):
        isin = stock.get('isin')
        if not isin:
            continue
        
        # Try multiple fields to find a match
        symbol = (stock.get('symbol') or '').strip().upper().replace('$', '')
        newbsecode = (stock.get('newbsecode') or '').strip().upper().replace('$', '')
        newnsecode = (stock.get('newnsecode') or '').strip().upper().replace('$', '')
        
        # Try matching in order of preference: symbol, newnsecode, newbsecode
        tet_record = None
        for try_symbol in [symbol, newnsecode, newbsecode]:
            if try_symbol and try_symbol in tet_map:
                tet_record = tet_map[try_symbol]
                break
        
        if not tet_record:
            not_matched += 1
            continue
        
        matched += 1
        
        new_sector = tet_record.get('sectorName')
        new_market_cap = tet_record.get('marketCap')  # Already in crores
        
        # Check if we actually need to update
        current_sector = stock.get('sector')
        if current_sector == new_sector:
            # sector hasn't changed, but we still want to set market_cap
            # For now, always update to ensure market_cap is set
            pass
        
        if dry_run:
            if matched <= 10:
                logger.info(f"  [DRY RUN] Would update {isin} ({symbol}): sector='{new_sector}', market_cap={new_market_cap}")
            continue
        
        # Update the record
        try:
            update_data = {}
            if new_sector:
                update_data['sector'] = new_sector
            if new_market_cap is not None:
                update_data['market_cap'] = float(new_market_cap)
            
            if not update_data:
                skipped_no_change += 1
                continue
            
            supabase.table('stocklistdata').update(update_data).eq('isin', isin).execute()
            updated += 1
            
            if updated <= 20 or updated % 500 == 0:
                logger.info(f"  Updated {isin} ({symbol}): sector='{new_sector}', market_cap={new_market_cap}")
        
        except Exception as e:
            errors += 1
            if errors <= 10:
                logger.error(f"  Error updating {isin} ({symbol}): {e}")
        
        if (i + 1) % 1000 == 0:
            logger.info(f"  Progress: {i + 1}/{len(stocklist)} processed, {matched} matched, {updated} updated")
    
    return {
        'total': len(stocklist),
        'matched': matched,
        'not_matched': not_matched,
        'updated': updated,
        'skipped_no_change': skipped_no_change,
        'errors': errors
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Backfill sector and market cap data')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without writing')
    args = parser.parse_args()
    
    logger.info("=" * 80)
    logger.info("BACKFILL SECTOR AND MARKET CAP DATA")
    logger.info(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    logger.info("=" * 80)
    
    # Initialize
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Step 1: Load tet.json
    logger.info("\nStep 1: Loading tet.json...")
    tet_map = load_tet_data()
    
    # Step 2: Fetch stocklistdata
    logger.info("\nStep 2: Fetching stocklistdata...")
    stocklist = fetch_stocklistdata(supabase)
    
    # Step 3: Match and update
    logger.info(f"\nStep 3: {'Previewing' if args.dry_run else 'Updating'} sector & market_cap...")
    stats = match_and_update(supabase, stocklist, tet_map, dry_run=args.dry_run)
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("BACKFILL SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total stocklistdata records: {stats['total']}")
    logger.info(f"Matched with tet.json:       {stats['matched']} ({stats['matched']*100//max(stats['total'],1)}%)")
    logger.info(f"Not matched:                 {stats['not_matched']}")
    logger.info(f"Updated:                     {stats['updated']}")
    logger.info(f"Skipped (no change):         {stats['skipped_no_change']}")
    logger.info(f"Errors:                      {stats['errors']}")
    logger.info("=" * 80)
    
    if args.dry_run:
        logger.info("\n⚠️  DRY RUN — no changes were made. Run without --dry-run to apply.")


if __name__ == '__main__':
    main()
