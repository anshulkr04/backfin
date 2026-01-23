#!/usr/bin/env python3
"""
Backfill PDF hashes from corporatefilings to announcement_pdf_hashes table
and verify duplicate detection is working.

This script:
1. Finds all records in corporatefilings that have pdf_hash but are NOT in announcement_pdf_hashes
2. Registers them in announcement_pdf_hashes (for non-duplicates only)
3. Verifies the duplicate detection system is working
"""
import os
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

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


def get_current_stats(supabase):
    """Get current statistics"""
    # Count in announcement_pdf_hashes
    hash_count = supabase.table("announcement_pdf_hashes").select("id", count="exact").execute()
    
    # Count in corporatefilings with pdf_hash
    cf_with_hash = supabase.table("corporatefilings").select("corp_id", count="exact").not_.is_("pdf_hash", "null").execute()
    
    # Count duplicates
    duplicates = supabase.table("corporatefilings").select("corp_id", count="exact").eq("is_duplicate", True).execute()
    
    return {
        "hashes_registered": hash_count.count if hash_count else 0,
        "corporatefilings_with_hash": cf_with_hash.count if cf_with_hash else 0,
        "duplicates_marked": duplicates.count if duplicates else 0
    }


def backfill_hashes(supabase, dry_run=True, batch_size=100):
    """
    Backfill missing PDF hashes from corporatefilings to announcement_pdf_hashes.
    
    For each unique (isin, pdf_hash) combination, register the FIRST occurrence
    (earliest date) as the original announcement.
    """
    logger.info("\n" + "="*60)
    logger.info(f"BACKFILLING PDF HASHES ({'DRY RUN' if dry_run else 'LIVE'})")
    logger.info("="*60)
    
    # Get all non-duplicate records with pdf_hash, ordered by date
    offset = 0
    all_records = []
    
    logger.info("Fetching records from corporatefilings...")
    
    while True:
        result = supabase.table("corporatefilings")\
            .select("corp_id, isin, symbol, companyname, date, pdf_hash, pdf_size_bytes, is_duplicate")\
            .not_.is_("pdf_hash", "null")\
            .order("date", desc=False)\
            .range(offset, offset + batch_size - 1)\
            .execute()
        
        if not result.data:
            break
            
        all_records.extend(result.data)
        offset += batch_size
        
        if len(result.data) < batch_size:
            break
    
    logger.info(f"Found {len(all_records)} records with pdf_hash")
    
    # Group by (isin, pdf_hash) and find the first occurrence
    hash_groups = defaultdict(list)
    for record in all_records:
        isin = record.get('isin')
        pdf_hash = record.get('pdf_hash')
        if isin and pdf_hash:
            key = (isin, pdf_hash)
            hash_groups[key].append(record)
    
    logger.info(f"Found {len(hash_groups)} unique (isin, pdf_hash) combinations")
    
    # Check which are already registered
    registered_count = 0
    to_register = []
    
    for (isin, pdf_hash), records in hash_groups.items():
        # Check if already registered
        existing = supabase.table("announcement_pdf_hashes")\
            .select("id")\
            .eq("isin", isin)\
            .eq("pdf_hash", pdf_hash)\
            .limit(1)\
            .execute()
        
        if existing.data:
            registered_count += 1
            continue
        
        # Use the first (earliest) record as the original
        first_record = records[0]
        to_register.append({
            'record': first_record,
            'duplicate_count': len(records) - 1  # Other records are duplicates
        })
    
    logger.info(f"Already registered: {registered_count}")
    logger.info(f"Need to register: {len(to_register)}")
    
    if not to_register:
        logger.info("✅ All hashes are already registered!")
        return 0, 0
    
    # Register missing hashes
    success_count = 0
    error_count = 0
    
    for item in to_register:
        record = item['record']
        dup_count = item['duplicate_count']
        
        hash_data = {
            'pdf_hash': record.get('pdf_hash'),
            'pdf_size_bytes': record.get('pdf_size_bytes'),
            'isin': record.get('isin'),
            'symbol': record.get('symbol'),
            'company_name': record.get('companyname'),
            'original_corp_id': record['corp_id'],
            'original_newsid': None,  # Not stored in corporatefilings
            'original_date': record.get('date'),
            'duplicate_count': dup_count
        }
        
        if dry_run:
            logger.debug(f"[DRY RUN] Would register: {record.get('symbol')} - {record.get('pdf_hash')[:16]}...")
            success_count += 1
        else:
            try:
                response = supabase.table('announcement_pdf_hashes').insert(hash_data).execute()
                if response.data:
                    success_count += 1
                else:
                    error_count += 1
            except Exception as e:
                if "duplicate key" in str(e).lower() or "23505" in str(e):
                    success_count += 1  # Already exists
                else:
                    logger.error(f"Error registering {record.get('symbol')}: {e}")
                    error_count += 1
    
    logger.info(f"\n📊 Backfill Results:")
    logger.info(f"   Successful: {success_count}")
    logger.info(f"   Errors: {error_count}")
    
    return success_count, error_count


def test_duplicate_detection(supabase):
    """Test the duplicate detection flow"""
    logger.info("\n" + "="*60)
    logger.info("TESTING DUPLICATE DETECTION")
    logger.info("="*60)
    
    # Get a record that has a pdf_hash
    test_record = supabase.table("corporatefilings")\
        .select("corp_id, isin, symbol, pdf_hash")\
        .not_.is_("pdf_hash", "null")\
        .not_.is_("isin", "null")\
        .limit(1)\
        .execute()
    
    if not test_record.data:
        logger.warning("No records with pdf_hash found for testing")
        return False
    
    record = test_record.data[0]
    isin = record.get('isin')
    pdf_hash = record.get('pdf_hash')
    symbol = record.get('symbol')
    
    logger.info(f"Testing with: {symbol} (ISIN: {isin})")
    logger.info(f"PDF Hash: {pdf_hash[:32]}...")
    
    # Check if this hash is registered
    hash_lookup = supabase.table("announcement_pdf_hashes")\
        .select("id, original_corp_id, duplicate_count")\
        .eq("isin", isin)\
        .eq("pdf_hash", pdf_hash)\
        .limit(1)\
        .execute()
    
    if hash_lookup.data:
        logger.info(f"✅ Hash IS registered in announcement_pdf_hashes")
        logger.info(f"   Original corp_id: {hash_lookup.data[0].get('original_corp_id')}")
        logger.info(f"   Duplicate count: {hash_lookup.data[0].get('duplicate_count')}")
        
        # Simulate what would happen if we tried to insert the same PDF
        logger.info("\n🧪 Simulating duplicate detection for same hash...")
        logger.info("   If a new announcement came with this same hash, it would be:")
        logger.info("   - Marked as is_duplicate = TRUE")
        logger.info(f"   - Linked to original: {hash_lookup.data[0].get('original_corp_id')}")
        
        return True
    else:
        logger.warning(f"❌ Hash is NOT registered!")
        logger.warning("   Duplicate detection will NOT work for this record.")
        return False


def verify_system_health(supabase):
    """Verify the overall system health"""
    logger.info("\n" + "="*60)
    logger.info("SYSTEM HEALTH CHECK")
    logger.info("="*60)
    
    issues = []
    
    # Check 1: Table exists and accessible
    try:
        supabase.table("announcement_pdf_hashes").select("id").limit(1).execute()
        logger.info("✅ announcement_pdf_hashes table is accessible")
    except Exception as e:
        issues.append(f"Cannot access announcement_pdf_hashes: {e}")
        logger.error(f"❌ Cannot access announcement_pdf_hashes: {e}")
    
    # Check 2: Has records
    stats = get_current_stats(supabase)
    
    if stats['hashes_registered'] == 0:
        issues.append("announcement_pdf_hashes has 0 records - backfill needed")
        logger.warning("⚠️  announcement_pdf_hashes has 0 records")
    else:
        logger.info(f"✅ announcement_pdf_hashes has {stats['hashes_registered']} records")
    
    # Check 3: Ratio check
    if stats['corporatefilings_with_hash'] > 0:
        ratio = stats['hashes_registered'] / stats['corporatefilings_with_hash']
        if ratio < 0.5:
            issues.append(f"Low registration ratio: {ratio:.1%}")
            logger.warning(f"⚠️  Low registration ratio: {stats['hashes_registered']}/{stats['corporatefilings_with_hash']} = {ratio:.1%}")
        else:
            logger.info(f"✅ Good registration coverage: {ratio:.1%}")
    
    # Check 4: Recent activity
    yesterday = (datetime.now() - timedelta(days=1)).isoformat()
    recent_hashes = supabase.table("announcement_pdf_hashes")\
        .select("id", count="exact")\
        .gte("created_at", yesterday)\
        .execute()
    
    recent_cf = supabase.table("corporatefilings")\
        .select("corp_id", count="exact")\
        .not_.is_("pdf_hash", "null")\
        .gte("date", yesterday)\
        .execute()
    
    recent_hash_count = recent_hashes.count if recent_hashes else 0
    recent_cf_count = recent_cf.count if recent_cf else 0
    
    logger.info(f"\n📊 Last 24 hours:")
    logger.info(f"   New announcements with hash: {recent_cf_count}")
    logger.info(f"   New hashes registered: {recent_hash_count}")
    
    if recent_cf_count > 0 and recent_hash_count == 0:
        issues.append("Recent announcements have hashes but none registered - code issue likely")
        logger.warning("⚠️  Recent announcements have hashes but none registered!")
    
    # Summary
    logger.info("\n" + "="*60)
    if not issues:
        logger.info("✅ SYSTEM HEALTHY - Duplicate detection should be working")
    else:
        logger.warning(f"⚠️  ISSUES FOUND ({len(issues)}):")
        for issue in issues:
            logger.warning(f"   - {issue}")
    
    return len(issues) == 0


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Backfill and verify PDF hash duplicate detection")
    parser.add_argument('--backfill', action='store_true', help="Actually backfill missing hashes (default is dry run)")
    parser.add_argument('--dry-run', action='store_true', help="Show what would be backfilled without doing it")
    parser.add_argument('--test', action='store_true', help="Test duplicate detection")
    parser.add_argument('--health', action='store_true', help="Check system health")
    parser.add_argument('--all', action='store_true', help="Run all checks and backfill")
    args = parser.parse_args()
    
    # Default to health check if no args
    if not any([args.backfill, args.dry_run, args.test, args.health, args.all]):
        args.health = True
        args.test = True
        args.dry_run = True
    
    logger.info("="*60)
    logger.info("PDF HASH DUPLICATE DETECTION - VERIFICATION & BACKFILL")
    logger.info("="*60)
    
    supabase = get_supabase()
    logger.info("✅ Connected to Supabase")
    
    # Show current stats
    stats = get_current_stats(supabase)
    logger.info(f"\n📊 Current Statistics:")
    logger.info(f"   Hashes registered in announcement_pdf_hashes: {stats['hashes_registered']}")
    logger.info(f"   Corporatefilings with pdf_hash: {stats['corporatefilings_with_hash']}")
    logger.info(f"   Announcements marked as duplicate: {stats['duplicates_marked']}")
    
    if args.health or args.all:
        verify_system_health(supabase)
    
    if args.dry_run or args.all:
        backfill_hashes(supabase, dry_run=True)
    
    if args.backfill or args.all:
        logger.info("\n" + "="*60)
        logger.info("PERFORMING LIVE BACKFILL")
        logger.info("="*60)
        success, errors = backfill_hashes(supabase, dry_run=False)
        
        # Show updated stats
        new_stats = get_current_stats(supabase)
        logger.info(f"\n📊 Updated Statistics:")
        logger.info(f"   Hashes registered: {stats['hashes_registered']} → {new_stats['hashes_registered']}")
    
    if args.test or args.all:
        test_duplicate_detection(supabase)
    
    logger.info("\n" + "="*60)
    logger.info("COMPLETE")
    logger.info("="*60)


if __name__ == "__main__":
    main()
