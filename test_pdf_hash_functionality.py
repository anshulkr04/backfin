#!/usr/bin/env python3
"""
Test script to verify PDF hash functionality is working correctly
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL2")
SUPABASE_KEY = os.getenv("SUPABASE_KEY2")

def test_pdf_hash_tables():
    """Test if PDF hash tables exist and have correct schema"""
    print("=" * 80)
    print("TESTING PDF HASH FUNCTIONALITY")
    print("=" * 80)
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ Missing Supabase credentials")
        return False
    
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Connected to Supabase")
    except Exception as e:
        print(f"❌ Failed to connect to Supabase: {e}")
        return False
    
    # Test 1: Check if announcement_pdf_hashes table exists
    print("\n1. Checking announcement_pdf_hashes table...")
    try:
        result = supabase.table('announcement_pdf_hashes').select('*').limit(1).execute()
        print(f"✅ announcement_pdf_hashes table exists")
        print(f"   Total records: {len(result.data)}")
        if result.data:
            print(f"   Sample record: {result.data[0]}")
    except Exception as e:
        print(f"❌ Error accessing announcement_pdf_hashes: {e}")
        return False
    
    # Test 2: Check if corporatefilings has PDF hash columns
    print("\n2. Checking corporatefilings table for PDF hash columns...")
    try:
        result = supabase.table('corporatefilings')\
            .select('corp_id, pdf_hash, pdf_size_bytes, is_duplicate, original_announcement_id')\
            .not_.is_('pdf_hash', 'null')\
            .limit(5)\
            .execute()
        
        print(f"✅ corporatefilings has PDF hash columns")
        print(f"   Records with PDF hash: {len(result.data)}")
        
        if result.data:
            print(f"   Sample records:")
            for record in result.data[:3]:
                print(f"     - corp_id: {record.get('corp_id')}")
                print(f"       pdf_hash: {record.get('pdf_hash')[:16] if record.get('pdf_hash') else None}...")
                print(f"       size: {record.get('pdf_size_bytes')} bytes")
                print(f"       is_duplicate: {record.get('is_duplicate')}")
        else:
            print("   ⚠️  No records with PDF hash found")
    except Exception as e:
        print(f"❌ Error checking corporatefilings: {e}")
        return False
    
    # Test 3: Check recent announcements for PDF hashes
    print("\n3. Checking recent announcements (last 24 hours)...")
    try:
        from datetime import datetime, timedelta
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        
        result = supabase.table('corporatefilings')\
            .select('corp_id, symbol, date, pdf_hash, is_duplicate')\
            .gte('date', yesterday)\
            .order('date', desc=True)\
            .limit(10)\
            .execute()
        
        print(f"✅ Found {len(result.data)} recent announcements")
        
        with_hash = [r for r in result.data if r.get('pdf_hash')]
        without_hash = [r for r in result.data if not r.get('pdf_hash')]
        
        print(f"   With PDF hash: {len(with_hash)}")
        print(f"   Without PDF hash: {len(without_hash)}")
        
        if with_hash:
            print(f"\n   Recent announcements WITH hash:")
            for record in with_hash[:3]:
                print(f"     - {record.get('symbol')} at {record.get('date')}")
                print(f"       Hash: {record.get('pdf_hash')[:16]}...")
                print(f"       Duplicate: {record.get('is_duplicate')}")
        
        if without_hash:
            print(f"\n   ⚠️  Recent announcements WITHOUT hash:")
            for record in without_hash[:3]:
                print(f"     - {record.get('symbol')} at {record.get('date')}")
                print(f"       corp_id: {record.get('corp_id')}")
    
    except Exception as e:
        print(f"❌ Error checking recent announcements: {e}")
    
    # Test 4: Check hash registration statistics
    print("\n4. Checking hash registration statistics...")
    try:
        result = supabase.table('announcement_pdf_hashes')\
            .select('*', count='exact')\
            .execute()
        
        print(f"✅ Total unique PDF hashes registered: {result.count}")
        
        # Get duplicate statistics
        if result.data:
            duplicates = [r for r in result.data if r.get('duplicate_count', 0) > 0]
            print(f"   Hashes with duplicates: {len(duplicates)}")
            if duplicates:
                total_duplicates = sum(r.get('duplicate_count', 0) for r in duplicates)
                print(f"   Total duplicate detections: {total_duplicates}")
    
    except Exception as e:
        print(f"❌ Error checking statistics: {e}")
    
    # Test 5: Check duplicate_detection_stats table
    print("\n5. Checking duplicate_detection_stats table...")
    try:
        result = supabase.table('duplicate_detection_stats')\
            .select('*')\
            .order('stats_date', desc=True)\
            .limit(7)\
            .execute()
        
        print(f"✅ Found {len(result.data)} days of statistics")
        
        if result.data:
            print(f"\n   Recent statistics:")
            for stat in result.data:
                print(f"     {stat.get('stats_date')}: "
                      f"{stat.get('total_processed')} processed, "
                      f"{stat.get('duplicates_detected')} duplicates, "
                      f"{stat.get('unique_pdfs')} unique")
    
    except Exception as e:
        print(f"⚠️  Error checking duplicate stats (may not exist): {e}")
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    
    return True


if __name__ == "__main__":
    success = test_pdf_hash_tables()
    sys.exit(0 if success else 1)
