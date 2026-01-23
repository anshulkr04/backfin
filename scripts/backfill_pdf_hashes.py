#!/usr/bin/env python3
"""
Backfill PDF hashes from corporatefilings to announcement_pdf_hashes table

This script:
1. Finds all non-duplicate records in corporatefilings that have pdf_hash but are NOT in announcement_pdf_hashes
2. Registers them in announcement_pdf_hashes table

Run this after the PDF hash columns are added but the registration wasn't happening properly.
"""
import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from supabase import create_client


def get_supabase():
    """Initialize Supabase client"""
    url = os.getenv('SUPABASE_URL2')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    if not url or not key:
        logger.error("❌ Missing SUPABASE_URL2 or SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)
    
    return create_client(url, key)


def get_records_needing_registration(supabase, batch_size=1000):
    """
    Get corporatefilings records that have pdf_hash but aren't registered in announcement_pdf_hashes
    """
    logger.info("Finding records needing registration...")
    
    # Get all non-duplicate records with pdf_hash from corporatefilings
    # Note: corporatefilings doesn't have a newsid column, so we'll leave it null
    all_records = []
    offset = 0
    
    while True:
        result = supabase.table("corporatefilings")\
            .select("corp_id, isin, symbol, companyname, date, pdf_hash, pdf_size_bytes")\
            .not_.is_("pdf_hash", "null")\
            .or_("is_duplicate.is.null,is_duplicate.eq.false")\
            .range(offset, offset + batch_size - 1)\
            .execute()
        
        if not result.data:
            break
            
        all_records.extend(result.data)
        logger.info(f"  Fetched {len(all_records)} records so far...")
        
        if len(result.data) < batch_size:
            break
        offset += batch_size
    
    logger.info(f"Total corporatefilings with pdf_hash: {len(all_records)}")
    
    # Now check which ones are NOT in announcement_pdf_hashes
    missing_records = []
    
    # Get all existing hashes from announcement_pdf_hashes
    existing_hashes = set()
    offset = 0
    
    while True:
        hash_result = supabase.table("announcement_pdf_hashes")\
            .select("isin, pdf_hash")\
            .range(offset, offset + batch_size - 1)\
            .execute()
        
        if not hash_result.data:
            break
            
        for h in hash_result.data:
            # Create a composite key of isin+hash
            existing_hashes.add(f"{h.get('isin')}:{h.get('pdf_hash')}")
        
        if len(hash_result.data) < batch_size:
            break
        offset += batch_size
    
    logger.info(f"Existing hashes in announcement_pdf_hashes: {len(existing_hashes)}")
    
    # Find missing records
    for record in all_records:
        key = f"{record.get('isin')}:{record.get('pdf_hash')}"
        if key not in existing_hashes and record.get('isin') and record.get('pdf_hash'):
            missing_records.append(record)
    
    logger.info(f"Records needing registration: {len(missing_records)}")
    
    return missing_records


def register_hashes(supabase, records, batch_size=50):
    """Register hashes in announcement_pdf_hashes table"""
    
    total = len(records)
    success_count = 0
    error_count = 0
    skip_count = 0
    
    logger.info(f"\nRegistering {total} hashes...")
    
    for i, record in enumerate(records):
        hash_data = {
            'pdf_hash': record.get('pdf_hash'),
            'pdf_size_bytes': record.get('pdf_size_bytes'),
            'isin': record.get('isin'),
            'symbol': record.get('symbol'),
            'company_name': record.get('companyname'),
            'original_corp_id': record['corp_id'],
            'original_newsid': None,  # corporatefilings doesn't have newsid column
            'original_date': record.get('date'),
            'duplicate_count': 0
        }
        
        try:
            response = supabase.table('announcement_pdf_hashes').insert(hash_data).execute()
            if response.data:
                success_count += 1
            else:
                logger.warning(f"  No data returned for: {record.get('symbol')}")
                error_count += 1
        except Exception as e:
            error_str = str(e)
            if "duplicate key" in error_str.lower() or "23505" in error_str:
                # Already exists, that's fine
                skip_count += 1
            else:
                logger.error(f"  Error for {record.get('symbol')}: {e}")
                error_count += 1
        
        # Progress update every 100 records
        if (i + 1) % 100 == 0:
            logger.info(f"  Progress: {i + 1}/{total} ({success_count} success, {skip_count} skipped, {error_count} errors)")
    
    return success_count, skip_count, error_count


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Backfill PDF hashes to announcement_pdf_hashes table")
    parser.add_argument('--dry-run', action='store_true', help="Don't actually insert, just show what would be done")
    parser.add_argument('--limit', type=int, default=None, help="Limit number of records to process")
    args = parser.parse_args()
    
    logger.info("="*60)
    logger.info("PDF HASH BACKFILL SCRIPT")
    logger.info("="*60)
    
    # Initialize Supabase
    supabase = get_supabase()
    logger.info("✅ Connected to Supabase")
    
    # Get current counts
    try:
        hash_count = supabase.table("announcement_pdf_hashes").select("id", count="exact").execute()
        cf_hash_count = supabase.table("corporatefilings").select("corp_id", count="exact").not_.is_("pdf_hash", "null").execute()
        
        logger.info(f"\nCurrent state:")
        logger.info(f"  announcement_pdf_hashes records: {hash_count.count}")
        logger.info(f"  corporatefilings with pdf_hash: {cf_hash_count.count}")
    except Exception as e:
        logger.warning(f"Could not get counts: {e}")
    
    # Find records needing registration
    missing_records = get_records_needing_registration(supabase)
    
    if not missing_records:
        logger.info("\n✅ All hashes are already registered! Nothing to do.")
        return
    
    if args.limit:
        missing_records = missing_records[:args.limit]
        logger.info(f"Limited to {args.limit} records")
    
    if args.dry_run:
        logger.info("\n[DRY RUN] Would register the following:")
        for i, record in enumerate(missing_records[:20]):
            logger.info(f"  {i+1}. {record.get('symbol')} - {record.get('pdf_hash')[:16]}... (ISIN: {record.get('isin')})")
        if len(missing_records) > 20:
            logger.info(f"  ... and {len(missing_records) - 20} more")
        logger.info("\nRun without --dry-run to actually register these hashes.")
        return
    
    # Register hashes
    success, skipped, errors = register_hashes(supabase, missing_records)
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("BACKFILL COMPLETE")
    logger.info("="*60)
    logger.info(f"Total processed: {len(missing_records)}")
    logger.info(f"Successfully registered: {success}")
    logger.info(f"Already existed (skipped): {skipped}")
    logger.info(f"Errors: {errors}")
    
    # Verify final counts
    try:
        final_hash_count = supabase.table("announcement_pdf_hashes").select("id", count="exact").execute()
        logger.info(f"\nFinal announcement_pdf_hashes count: {final_hash_count.count}")
    except Exception as e:
        logger.warning(f"Could not get final count: {e}")


if __name__ == "__main__":
    main()
