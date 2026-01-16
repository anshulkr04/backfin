#!/usr/bin/env python3
"""
Quick test to verify PDF hashing is working after container rebuild
"""
import os
from supabase import create_client
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()

def test_pdf_hashing():
    print("🔍 Testing PDF Hashing Functionality")
    print("=" * 60)
    
    # Connect to Supabase
    supabase_url = os.getenv('SUPABASE_URL2')
    supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    if not supabase_url or not supabase_key:
        print("❌ Missing Supabase credentials in environment")
        return
    
    supabase = create_client(supabase_url, supabase_key)
    
    # Test 1: Check announcement_pdf_hashes table
    print("\n1️⃣ Checking announcement_pdf_hashes table...")
    try:
        hashes = supabase.table("announcement_pdf_hashes").select("*").limit(5).execute()
        if hashes.data:
            print(f"   ✅ Found {len(hashes.data)} PDF hash records")
            for h in hashes.data[:3]:
                print(f"      - ISIN: {h.get('isin')}, Hash: {h.get('pdf_hash')[:16]}..., Size: {h.get('pdf_size_bytes')} bytes")
        else:
            print("   ⚠️  No PDF hash records found yet")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 2: Check corporatefilings for pdf_hash
    print("\n2️⃣ Checking corporatefilings with pdf_hash...")
    try:
        # Look for recent filings with PDF hash
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        filings = (
            supabase.table("corporatefilings")
            .select("corp_id, companyname, pdf_hash, pdf_size_bytes, is_duplicate, date")
            .gte("date", yesterday)
            .not_.is_("pdf_hash", "null")
            .limit(10)
            .execute()
        )
        
        if filings.data:
            print(f"   ✅ Found {len(filings.data)} announcements with PDF hashes")
            for f in filings.data[:5]:
                dup_status = "🔄 DUPLICATE" if f.get('is_duplicate') else "✨ NEW"
                print(f"      {dup_status} - {f.get('companyname', 'N/A')[:30]}")
                print(f"         Hash: {f.get('pdf_hash', 'N/A')[:16]}..., Size: {f.get('pdf_size_bytes', 'N/A')} bytes")
        else:
            print("   ⚠️  No announcements with PDF hash found yet")
            print("      This is expected if containers haven't processed new announcements since rebuild")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 3: Statistics
    print("\n3️⃣ PDF Hashing Statistics...")
    try:
        total_announcements = supabase.table("corporatefilings").select("corp_id", count="exact").execute()
        with_hash = (
            supabase.table("corporatefilings")
            .select("corp_id", count="exact")
            .not_.is_("pdf_hash", "null")
            .execute()
        )
        
        total = total_announcements.count
        hashed = with_hash.count
        percentage = (hashed / total * 100) if total > 0 else 0
        
        print(f"   Total announcements: {total}")
        print(f"   With PDF hash: {hashed}")
        print(f"   Coverage: {percentage:.1f}%")
        
        if percentage > 0:
            print(f"   ✅ PDF hashing is working!")
        else:
            print(f"   ⚠️  No PDF hashes yet - containers need to process new announcements")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 4: Duplicate detection stats
    print("\n4️⃣ Duplicate Detection...")
    try:
        duplicates = (
            supabase.table("corporatefilings")
            .select("corp_id", count="exact")
            .eq("is_duplicate", True)
            .execute()
        )
        
        if duplicates.count > 0:
            print(f"   ✅ Detected {duplicates.count} duplicate announcements")
        else:
            print(f"   ℹ️  No duplicates detected yet")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n" + "=" * 60)
    print("✅ Test complete!")
    print("\n💡 Next steps:")
    print("   1. Rebuild containers: docker-compose -f docker-compose.redis.yml up -d --build")
    print("   2. Wait for new announcements to be processed")
    print("   3. Run this test again to verify PDF hashing is working")

if __name__ == "__main__":
    test_pdf_hashing()
