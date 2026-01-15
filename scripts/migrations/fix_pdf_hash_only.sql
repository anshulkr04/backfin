-- =====================================================
-- PDF HASH FIX ONLY - Run this in Supabase SQL Editor
-- =====================================================
-- Date: 2026-01-14
-- Purpose: Fix PDF hash system - disable RLS, clean orphans
-- =====================================================

-- Step 1: Disable RLS on PDF hash tables
ALTER TABLE IF EXISTS announcement_pdf_hashes DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS duplicate_detection_stats DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS corporatefilings DISABLE ROW LEVEL SECURITY;

-- Step 2: Drop all RLS policies on these tables
DROP POLICY IF EXISTS "Service role has full access to pdf_hashes" ON announcement_pdf_hashes;
DROP POLICY IF EXISTS "Authenticated users can read pdf_hashes" ON announcement_pdf_hashes;
DROP POLICY IF EXISTS "Enable read access for all users" ON announcement_pdf_hashes;
DROP POLICY IF EXISTS "Enable insert for service role" ON announcement_pdf_hashes;
DROP POLICY IF EXISTS "Enable update for service role" ON announcement_pdf_hashes;

DROP POLICY IF EXISTS "Service role has full access to duplicate_stats" ON duplicate_detection_stats;
DROP POLICY IF EXISTS "Authenticated users can read duplicate_stats" ON duplicate_detection_stats;

DROP POLICY IF EXISTS "Enable read access for all users" ON corporatefilings;
DROP POLICY IF EXISTS "Enable insert for service role" ON corporatefilings;
DROP POLICY IF EXISTS "Enable update for service role" ON corporatefilings;
DROP POLICY IF EXISTS "Service role has full access" ON corporatefilings;

-- Step 3: Clean up orphaned hashes (if any exist)
DELETE FROM announcement_pdf_hashes
WHERE original_corp_id NOT IN (
    SELECT corp_id FROM corporatefilings WHERE corp_id IS NOT NULL
);

-- Step 4: Verify table exists and has correct columns
-- (This will show an error if table doesn't exist - that means you need to run the full migration first)
SELECT 
    column_name, 
    data_type 
FROM information_schema.columns 
WHERE table_name = 'announcement_pdf_hashes'
ORDER BY ordinal_position;

-- Step 5: Check RLS is now disabled
SELECT 
    tablename, 
    rowsecurity as rls_enabled
FROM pg_tables 
WHERE schemaname = 'public' 
AND tablename IN ('announcement_pdf_hashes', 'duplicate_detection_stats', 'corporatefilings');

-- Step 6: Count current hashes (should show 0 if new, or actual count if some exist)
SELECT COUNT(*) as total_pdf_hashes FROM announcement_pdf_hashes;

-- Step 7: Check corporatefilings has pdf_hash column
SELECT 
    column_name 
FROM information_schema.columns 
WHERE table_name = 'corporatefilings' 
AND column_name IN ('pdf_hash', 'is_duplicate', 'pdf_size_bytes');
