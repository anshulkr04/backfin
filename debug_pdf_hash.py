#!/usr/bin/env python3
"""
Debug script to check PDF hash functionality
"""
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

# Initialize Supabase
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(url, key)

print("=" * 80)
print("PDF HASH DEBUGGING")
print("=" * 80)

# 1. Check if announcement_pdf_hashes table exists
print("\n1. Checking if 'announcement_pdf_hashes' table exists...")
try:
    response = supabase.table('announcement_pdf_hashes').select('*').limit(1).execute()
    print(f"   ✅ Table exists! Found {len(response.data)} record(s)")
    if response.data:
        print(f"   Sample: {response.data[0]}")
except Exception as e:
    print(f"   ❌ Error: {e}")
    print(f"   Table may not exist or query failed")

# 2. Check recent announcements for pdf_hash
print("\n2. Checking recent announcements for pdf_hash column...")
try:
    response = supabase.table('corporatefilings')\
        .select('corp_id, newsid, symbol, date, pdf_hash, pdf_size_bytes, is_duplicate')\
        .order('date', desc=True)\
        .limit(10)\
        .execute()
    
    print(f"   Found {len(response.data)} recent announcements:")
    for ann in response.data:
        has_hash = "✅" if ann.get('pdf_hash') else "❌"
        print(f"   {has_hash} {ann.get('symbol', 'N/A'):15} {ann.get('newsid', 'N/A'):20} "
              f"Hash: {ann.get('pdf_hash', 'None')[:16] if ann.get('pdf_hash') else 'None':16}... "
              f"Size: {ann.get('pdf_size_bytes', 'N/A')}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# 3. Count announcements with hashes
print("\n3. Counting announcements with/without hashes...")
try:
    # With hash
    response_with = supabase.table('corporatefilings')\
        .select('corp_id', count='exact')\
        .not_.is_('pdf_hash', 'null')\
        .execute()
    
    # Without hash
    response_without = supabase.table('corporatefilings')\
        .select('corp_id', count='exact')\
        .is_('pdf_hash', 'null')\
        .execute()
    
    print(f"   Announcements WITH hash: {response_with.count}")
    print(f"   Announcements WITHOUT hash: {response_without.count}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# 4. Check today's announcements
print("\n4. Checking today's announcements...")
try:
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    
    response = supabase.table('corporatefilings')\
        .select('corp_id, newsid, symbol, date, pdf_hash, pdf_size_bytes')\
        .gte('date', today)\
        .order('date', desc=True)\
        .execute()
    
    print(f"   Found {len(response.data)} announcements from today:")
    for ann in response.data:
        has_hash = "✅" if ann.get('pdf_hash') else "❌"
        print(f"   {has_hash} {ann.get('symbol', 'N/A'):15} {ann.get('newsid', 'N/A'):20} "
              f"Hash: {'Yes' if ann.get('pdf_hash') else 'No'}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# 5. Check announcement_pdf_hashes table stats
print("\n5. Checking announcement_pdf_hashes table statistics...")
try:
    response = supabase.table('announcement_pdf_hashes')\
        .select('*', count='exact')\
        .execute()
    
    print(f"   Total hash records: {response.count}")
    if response.data and len(response.data) > 0:
        print(f"   Recent hashes:")
        for h in response.data[:5]:
            print(f"   - {h.get('symbol', 'N/A'):10} {h.get('original_newsid', 'N/A'):20} "
                  f"Duplicates: {h.get('duplicate_count', 0)}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# 6. Test if we can insert into announcement_pdf_hashes
print("\n6. Testing insert capability...")
try:
    test_data = {
        'pdf_hash': 'test_hash_debug_12345',
        'pdf_size_bytes': 1024,
        'isin': 'TEST000000',
        'symbol': 'TEST',
        'company_name': 'Test Company',
        'original_corp_id': '00000000-0000-0000-0000-000000000000',
        'original_newsid': 'TEST123',
        'original_date': '2026-01-14T00:00:00+00:00',
        'duplicate_count': 0
    }
    
    # Try to insert
    response = supabase.table('announcement_pdf_hashes').insert(test_data).execute()
    
    if response.data:
        print(f"   ✅ Successfully inserted test hash")
        # Clean up
        supabase.table('announcement_pdf_hashes')\
            .delete()\
            .eq('pdf_hash', 'test_hash_debug_12345')\
            .execute()
        print(f"   ✅ Cleaned up test record")
    else:
        print(f"   ⚠️  Insert returned no data")
        
except Exception as e:
    print(f"   ❌ Error: {e}")
    # Try cleanup anyway
    try:
        supabase.table('announcement_pdf_hashes')\
            .delete()\
            .eq('pdf_hash', 'test_hash_debug_12345')\
            .execute()
    except:
        pass

print("\n" + "=" * 80)
print("DIAGNOSIS:")
print("=" * 80)

# Final diagnosis
try:
    # Check if columns exist
    response = supabase.table('corporatefilings')\
        .select('pdf_hash, pdf_size_bytes, is_duplicate')\
        .limit(1)\
        .execute()
    
    has_columns = True
except Exception as e:
    has_columns = False
    
try:
    response = supabase.table('announcement_pdf_hashes').select('*').limit(1).execute()
    has_table = True
except:
    has_table = False

if not has_table:
    print("❌ ISSUE: 'announcement_pdf_hashes' table does NOT exist")
    print("   ACTION: Run migration: scripts/migrations/add_pdf_hash_tracking.sql")
elif not has_columns:
    print("❌ ISSUE: 'corporatefilings' table missing hash columns")
    print("   ACTION: Run migration: scripts/migrations/add_pdf_hash_tracking.sql")
else:
    # Check for recent hashes
    response = supabase.table('corporatefilings')\
        .select('pdf_hash')\
        .not_.is_('pdf_hash', 'null')\
        .gte('date', '2026-01-10')\
        .limit(1)\
        .execute()
    
    if not response.data:
        print("⚠️  ISSUE: No recent announcements have pdf_hash set")
        print("   Possible causes:")
        print("   1. Scrapers are not running")
        print("   2. PDF hash calculation is failing silently")
        print("   3. Hash registration is failing")
        print("   ACTION: Check scraper logs for hash calculation messages")
    else:
        print("✅ System appears to be working correctly!")
        print("   Hash tracking is functional")

print("=" * 80)
