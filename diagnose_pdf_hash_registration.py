#!/usr/bin/env python3
"""
Diagnose and fix PDF hash registration issues

This script:
1. Checks why hashes aren't being registered in announcement_pdf_hashes table
2. Tests the registration function directly
3. Backfills missing hashes from corporatefilings that have pdf_hash but aren't in announcement_pdf_hashes
"""
import os
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
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


def check_table_exists(supabase, table_name):
    """Check if a table exists and is accessible"""
    try:
        result = supabase.table(table_name).select("*").limit(1).execute()
        return True, result.data
    except Exception as e:
        return False, str(e)


def test_insert_to_hash_table(supabase):
    """Test if we can insert into announcement_pdf_hashes"""
    logger.info("\n" + "="*60)
    logger.info("TEST 1: Direct insert to announcement_pdf_hashes")
    logger.info("="*60)
    
    # First get a valid corp_id from corporatefilings
    cf_result = supabase.table("corporatefilings").select("corp_id, isin, symbol, companyname, date, newsid").limit(1).execute()
    
    if not cf_result.data:
        logger.error("❌ No records in corporatefilings table")
        return False
    
    cf = cf_result.data[0]
    test_hash = f"test_hash_{datetime.now().timestamp()}"
    
    test_data = {
        'pdf_hash': test_hash,
        'pdf_size_bytes': 12345,
        'isin': cf.get('isin'),
        'symbol': cf.get('symbol'),
        'company_name': cf.get('companyname'),
        'original_corp_id': cf['corp_id'],
        'original_newsid': cf.get('newsid'),
        'original_date': cf.get('date'),
        'duplicate_count': 0
    }
    
    logger.info(f"Attempting to insert test hash: {test_hash[:20]}...")
    logger.info(f"Data: {test_data}")
    
    try:
        response = supabase.table('announcement_pdf_hashes').insert(test_data).execute()
        
        if response.data:
            logger.info(f"✅ INSERT SUCCESSFUL!")
            logger.info(f"   Inserted ID: {response.data[0].get('id')}")
            
            # Clean up test data
            supabase.table('announcement_pdf_hashes').delete().eq('pdf_hash', test_hash).execute()
            logger.info("   (Test record cleaned up)")
            return True
        else:
            logger.error(f"❌ Insert returned no data")
            return False
            
    except Exception as e:
        logger.error(f"❌ INSERT FAILED: {e}")
        
        # Check if it's an RLS issue
        if "row-level security" in str(e).lower() or "rls" in str(e).lower():
            logger.error("\n⚠️  ROW LEVEL SECURITY (RLS) IS BLOCKING INSERTS!")
            logger.error("   Run: ALTER TABLE announcement_pdf_hashes DISABLE ROW LEVEL SECURITY;")
        
        # Check if it's a foreign key issue
        if "foreign key" in str(e).lower() or "violates" in str(e).lower():
            logger.error("\n⚠️  FOREIGN KEY CONSTRAINT VIOLATION!")
            logger.error("   The original_corp_id may reference a deleted record")
        
        return False


def find_missing_registrations(supabase):
    """Find records in corporatefilings with pdf_hash but not in announcement_pdf_hashes"""
    logger.info("\n" + "="*60)
    logger.info("TEST 2: Finding missing hash registrations")
    logger.info("="*60)
    
    # Get records from corporatefilings that have pdf_hash
    cf_query = supabase.table("corporatefilings")\
        .select("corp_id, isin, symbol, companyname, date, newsid, pdf_hash, pdf_size_bytes, is_duplicate")\
        .not_.is_("pdf_hash", "null")\
        .eq("is_duplicate", False)\
        .limit(100)\
        .execute()
    
    if not cf_query.data:
        logger.info("No records with pdf_hash in corporatefilings")
        return []
    
    logger.info(f"Found {len(cf_query.data)} non-duplicate records with pdf_hash in corporatefilings")
    
    # Check which ones are NOT in announcement_pdf_hashes
    missing = []
    for cf in cf_query.data:
        pdf_hash = cf.get('pdf_hash')
        isin = cf.get('isin')
        
        if not pdf_hash or not isin:
            continue
        
        # Check if hash exists in announcement_pdf_hashes
        hash_check = supabase.table('announcement_pdf_hashes')\
            .select('id')\
            .eq('isin', isin)\
            .eq('pdf_hash', pdf_hash)\
            .limit(1)\
            .execute()
        
        if not hash_check.data:
            missing.append(cf)
            logger.info(f"   ⚠️  Missing: {cf.get('symbol')} - {pdf_hash[:16]}...")
    
    logger.info(f"\n📊 Summary: {len(missing)} out of {len(cf_query.data)} records are missing from announcement_pdf_hashes")
    
    return missing


def backfill_missing_hashes(supabase, missing_records, dry_run=True):
    """Backfill missing hashes from corporatefilings to announcement_pdf_hashes"""
    logger.info("\n" + "="*60)
    logger.info(f"TEST 3: Backfilling missing hashes ({'DRY RUN' if dry_run else 'LIVE'})")
    logger.info("="*60)
    
    if not missing_records:
        logger.info("No records to backfill")
        return 0
    
    success_count = 0
    error_count = 0
    
    for record in missing_records:
        hash_data = {
            'pdf_hash': record.get('pdf_hash'),
            'pdf_size_bytes': record.get('pdf_size_bytes'),
            'isin': record.get('isin'),
            'symbol': record.get('symbol'),
            'company_name': record.get('companyname'),
            'original_corp_id': record['corp_id'],
            'original_newsid': record.get('newsid'),
            'original_date': record.get('date'),
            'duplicate_count': 0
        }
        
        if dry_run:
            logger.info(f"   [DRY RUN] Would insert: {record.get('symbol')} - {record.get('pdf_hash')[:16]}...")
            success_count += 1
        else:
            try:
                response = supabase.table('announcement_pdf_hashes').insert(hash_data).execute()
                if response.data:
                    logger.info(f"   ✅ Inserted: {record.get('symbol')} - {record.get('pdf_hash')[:16]}...")
                    success_count += 1
                else:
                    logger.warning(f"   ⚠️  No data returned for: {record.get('symbol')}")
                    error_count += 1
            except Exception as e:
                if "duplicate key" in str(e).lower() or "23505" in str(e):
                    logger.info(f"   ⏭️  Already exists: {record.get('symbol')}")
                    success_count += 1
                else:
                    logger.error(f"   ❌ Error for {record.get('symbol')}: {e}")
                    error_count += 1
    
    logger.info(f"\n📊 Backfill Results: {success_count} success, {error_count} errors")
    return success_count


def check_rls_status(supabase):
    """Check RLS status on the tables"""
    logger.info("\n" + "="*60)
    logger.info("TEST 4: Checking RLS Status")
    logger.info("="*60)
    
    # We can't directly query RLS status, but we can try to infer from errors
    # Just note that we've tested insert above
    logger.info("RLS status check is inferred from insert tests above.")
    logger.info("If insert failed with 'row-level security' error, RLS is enabled and blocking.")


def main():
    """Main diagnostic and fix function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Diagnose and fix PDF hash registration")
    parser.add_argument('--fix', action='store_true', help="Actually backfill missing hashes (default is dry run)")
    args = parser.parse_args()
    
    logger.info("="*60)
    logger.info("PDF HASH REGISTRATION DIAGNOSTIC")
    logger.info("="*60)
    
    # Initialize Supabase
    supabase = get_supabase()
    logger.info("✅ Connected to Supabase")
    
    # Check tables exist
    logger.info("\nChecking table accessibility...")
    
    hash_table_ok, hash_result = check_table_exists(supabase, "announcement_pdf_hashes")
    if hash_table_ok:
        logger.info("✅ announcement_pdf_hashes table is accessible")
    else:
        logger.error(f"❌ announcement_pdf_hashes table issue: {hash_result}")
        return
    
    cf_table_ok, cf_result = check_table_exists(supabase, "corporatefilings")
    if cf_table_ok:
        logger.info("✅ corporatefilings table is accessible")
    else:
        logger.error(f"❌ corporatefilings table issue: {cf_result}")
        return
    
    # Test 1: Try direct insert
    insert_works = test_insert_to_hash_table(supabase)
    
    if not insert_works:
        logger.error("\n" + "="*60)
        logger.error("⛔ DIRECT INSERT FAILED - FIX THIS FIRST!")
        logger.error("="*60)
        logger.error("\nPossible fixes:")
        logger.error("1. Disable RLS: ALTER TABLE announcement_pdf_hashes DISABLE ROW LEVEL SECURITY;")
        logger.error("2. Check foreign key constraints")
        logger.error("3. Check table permissions")
        return
    
    # Test 2: Find missing registrations
    missing = find_missing_registrations(supabase)
    
    # Test 3: Backfill
    if missing:
        backfill_missing_hashes(supabase, missing, dry_run=not args.fix)
        
        if not args.fix:
            logger.info("\n" + "="*60)
            logger.info("To actually backfill, run with --fix flag:")
            logger.info("  python diagnose_pdf_hash_registration.py --fix")
            logger.info("="*60)
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("DIAGNOSTIC COMPLETE")
    logger.info("="*60)
    
    if insert_works and not missing:
        logger.info("✅ Everything looks good! Hash registration should be working.")
        logger.info("   New announcements will have their hashes registered automatically.")
    elif insert_works and missing:
        logger.info("⚠️  Insert works, but there are missing registrations to backfill.")
        if not args.fix:
            logger.info("   Run with --fix to backfill them.")
    else:
        logger.error("❌ There are issues that need to be fixed before hash registration will work.")


if __name__ == "__main__":
    main()
