#!/usr/bin/env python3
"""
Backfill company_id in corporatefilings

For filings from November 2025 onwards that don't have company_id set,
this script looks up the ISIN in stocklistdata and sets the company_id.

This enables:
- Stable company identity even when ISIN changes
- Efficient company-level queries across filings
- Foundation for new API filters (market cap via company_id → stocklistdata)

Usage:
    python3 backfill_company_id.py
    python3 backfill_company_id.py --dry-run
    python3 backfill_company_id.py --start-date 2025-11-01
"""

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


def build_isin_to_company_id_map(supabase) -> dict:
    """Build ISIN → company_id lookup from stocklistdata"""
    logger.info("Building ISIN → company_id map...")
    
    all_rows = []
    batch_size = 1000
    start = 0
    
    while True:
        end = start + batch_size - 1
        resp = supabase.table('stocklistdata').select('isin, company_id').range(start, end).execute()
        rows = resp.data or []
        if not rows:
            break
        all_rows.extend(rows)
        start += batch_size
        if len(rows) < batch_size:
            break
    
    isin_map = {}
    for row in all_rows:
        if row.get('isin') and row.get('company_id'):
            isin_map[row['isin']] = row['company_id']
    
    logger.info(f"  Built map with {len(isin_map)} ISIN → company_id entries")
    return isin_map


def fetch_filings_without_company_id(supabase, start_date: str = '2025-11-01', batch_size: int = 1000) -> list:
    """Fetch filings that need company_id backfill"""
    logger.info(f"Fetching filings without company_id (from {start_date})...")
    
    all_filings = []
    offset = 0
    
    while True:
        resp = supabase.table('corporatefilings') \
            .select('corp_id, isin') \
            .is_('company_id', 'null') \
            .gte('date', start_date) \
            .not_.is_('isin', 'null') \
            .range(offset, offset + batch_size - 1) \
            .execute()
        
        rows = resp.data or []
        if not rows:
            break
        
        all_filings.extend(rows)
        offset += batch_size
        
        if len(rows) < batch_size:
            break
        
        if offset % 5000 == 0:
            logger.info(f"  Fetched {offset} filings so far...")
    
    logger.info(f"  Found {len(all_filings)} filings needing company_id")
    return all_filings


def backfill_company_ids(supabase, filings: list, isin_map: dict, dry_run: bool = False) -> dict:
    """Backfill company_id for each filing"""
    stats = {
        'total': len(filings),
        'updated': 0,
        'not_found': 0,
        'errors': 0
    }
    
    # Group by ISIN for batch updates
    isin_groups = {}
    for filing in filings:
        isin = filing.get('isin')
        if isin:
            if isin not in isin_groups:
                isin_groups[isin] = []
            isin_groups[isin].append(filing['corp_id'])
    
    logger.info(f"  Grouped into {len(isin_groups)} unique ISINs")
    
    for isin, corp_ids in isin_groups.items():
        company_id = isin_map.get(isin)
        
        if not company_id:
            stats['not_found'] += len(corp_ids)
            continue
        
        if dry_run:
            stats['updated'] += len(corp_ids)
            if stats['updated'] <= 10:
                logger.info(f"  [DRY RUN] {isin} → {company_id} ({len(corp_ids)} filings)")
            continue
        
        try:
            # Batch update: set company_id for all filings with this ISIN
            supabase.table('corporatefilings') \
                .update({'company_id': company_id}) \
                .eq('isin', isin) \
                .is_('company_id', 'null') \
                .gte('date', '2025-11-01') \
                .execute()
            
            stats['updated'] += len(corp_ids)
            
            if stats['updated'] <= 20 or stats['updated'] % 1000 == 0:
                logger.info(f"  Updated {isin} → {company_id} ({len(corp_ids)} filings)")
        
        except Exception as e:
            stats['errors'] += len(corp_ids)
            logger.error(f"  Error updating {isin}: {e}")
    
    return stats


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Backfill company_id in corporatefilings')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without writing')
    parser.add_argument('--start-date', default='2025-11-01', help='Start date for backfill (default: 2025-11-01)')
    args = parser.parse_args()
    
    logger.info("=" * 70)
    logger.info("BACKFILL company_id IN corporatefilings")
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    logger.info(f"Start date: {args.start_date}")
    logger.info("=" * 70)
    
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    isin_map = build_isin_to_company_id_map(supabase)
    filings = fetch_filings_without_company_id(supabase, args.start_date)
    
    if not filings:
        logger.info("No filings need backfill!")
        return
    
    stats = backfill_company_ids(supabase, filings, isin_map, dry_run=args.dry_run)
    
    logger.info("\n" + "=" * 70)
    logger.info("SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Total filings:    {stats['total']}")
    logger.info(f"Updated:          {stats['updated']}")
    logger.info(f"ISIN not found:   {stats['not_found']}")
    logger.info(f"Errors:           {stats['errors']}")
    logger.info("=" * 70)
    
    if args.dry_run:
        logger.info("\nDRY RUN — no changes made. Run without --dry-run to apply.")


if __name__ == '__main__':
    main()
