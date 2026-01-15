#!/usr/bin/env python3
"""
Quick test to verify PDF hash system can insert data
Run this AFTER running the disable_rls_policies.sql migration
"""

import os
import sys
from datetime import datetime
from supabase import create_client
from dotenv import load_dotenv
load_dotenv()

# Supabase connection
SUPABASE_URL = os.getenv("SUPABASE_URL2")
SUPABASE_KEY = os.getenv("SUPABASE_KEY2")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_KEY environment variables")
    sys.exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

print("=" * 80)
print("PDF HASH SYSTEM - POST-MIGRATION TEST")
print("=" * 80)
print()

# Test 1: Check if tables exist
print("1. Checking if tables exist...")
try:
    # Check announcement_pdf_hashes
    result = supabase.table("announcement_pdf_hashes").select("*").limit(1).execute()
    print(f"   ✅ announcement_pdf_hashes table exists (found {len(result.data)} rows)")
except Exception as e:
    print(f"   ❌ announcement_pdf_hashes table error: {e}")

try:
    # Check if pdf_hash column exists in corporatefilings
    result = supabase.table("corporatefilings").select("pdf_hash, is_duplicate").limit(1).execute()
    print(f"   ✅ corporatefilings has pdf_hash columns")
except Exception as e:
    print(f"   ❌ corporatefilings columns error: {e}")

print()

# Test 2: Try to insert a test hash
print("2. Testing INSERT capability on announcement_pdf_hashes...")
try:
    # Get a real corp_id from corporatefilings for the foreign key
    corp_result = supabase.table("corporatefilings").select("corp_id, isin, symbol, companyname").limit(1).execute()
    
    if corp_result.data:
        corp_data = corp_result.data[0]
        test_hash = {
            "pdf_hash": "test_hash_" + datetime.now().isoformat(),
            "pdf_size_bytes": 12345,
            "isin": corp_data.get("isin") or "TEST_ISIN",
            "symbol": corp_data.get("symbol") or "TEST",
            "company_name": corp_data.get("companyname") or "Test Company",
            "original_corp_id": corp_data["corp_id"],
            "original_newsid": "TEST_NEWS_123",
            "original_date": datetime.now().isoformat(),
            "duplicate_count": 0
        }
        
        insert_result = supabase.table("announcement_pdf_hashes").insert(test_hash).execute()
        print(f"   ✅ Successfully inserted test hash (id: {insert_result.data[0]['id']})")
        
        # Clean up test data
        supabase.table("announcement_pdf_hashes").delete().eq("id", insert_result.data[0]['id']).execute()
        print(f"   ✅ Cleaned up test data")
    else:
        print("   ⚠️  No corporatefilings found to test with")
        
except Exception as e:
    print(f"   ❌ Insert test failed: {e}")

print()

# Test 3: Check RLS status
print("3. Checking RLS status...")
try:
    # This query checks if RLS is enabled
    query = """
    SELECT 
        tablename,
        rowsecurity as rls_enabled
    FROM pg_tables
    WHERE schemaname = 'public'
        AND tablename IN ('announcement_pdf_hashes', 'duplicate_detection_stats', 'corporatefilings')
    ORDER BY tablename;
    """
    
    result = supabase.rpc('exec_sql', {'query': query}).execute()
    print("   RLS Status:")
    for row in result.data:
        status = "DISABLED ✅" if not row.get('rls_enabled') else "ENABLED ❌"
        print(f"   - {row['tablename']}: {status}")
except Exception as e:
    print(f"   ⚠️  Could not check RLS status (this is expected if RPC is not available)")
    print(f"      You can check manually in Supabase SQL editor")

print()

# Test 4: Count existing hashes
print("4. Checking existing hash data...")
try:
    count_result = supabase.table("announcement_pdf_hashes").select("*", count="exact").execute()
    print(f"   ✅ Total hashes in database: {count_result.count}")
    
    # Count announcements with hashes
    hash_count = supabase.table("corporatefilings").select("*", count="exact").not_.is_("pdf_hash", "null").execute()
    print(f"   ✅ Announcements with pdf_hash set: {hash_count.count}")
    
    # Count duplicates
    dup_count = supabase.table("corporatefilings").select("*", count="exact").eq("is_duplicate", True).execute()
    print(f"   ✅ Announcements marked as duplicates: {dup_count.count}")
    
except Exception as e:
    print(f"   ❌ Error checking counts: {e}")

print()
print("=" * 80)
print("NEXT STEPS:")
print("=" * 80)
print("1. If tables don't exist, run: scripts/migrations/add_pdf_hash_tracking.sql")
print("2. If RLS is ENABLED, run: scripts/migrations/disable_rls_policies.sql")
print("3. Restart your scrapers to start tracking PDF hashes")
print("4. Check logs/system/*.log for any hash-related errors")
print("=" * 80)
