-- =====================================================
-- DISABLE ALL RLS POLICIES FOR PDF HASH SYSTEM
-- =====================================================
-- Purpose: Remove Row Level Security restrictions that are
--          preventing scrapers from writing PDF hashes
-- Date: 2026-01-14
-- =====================================================

-- Disable RLS on announcement_pdf_hashes table
ALTER TABLE IF EXISTS announcement_pdf_hashes DISABLE ROW LEVEL SECURITY;

-- Disable RLS on duplicate_detection_stats table
ALTER TABLE IF EXISTS duplicate_detection_stats DISABLE ROW LEVEL SECURITY;

-- Drop all existing policies on announcement_pdf_hashes
DROP POLICY IF EXISTS "Service role has full access to pdf_hashes" ON announcement_pdf_hashes;
DROP POLICY IF EXISTS "Authenticated users can read pdf_hashes" ON announcement_pdf_hashes;
DROP POLICY IF EXISTS "Enable read access for all users" ON announcement_pdf_hashes;
DROP POLICY IF EXISTS "Enable insert for service role" ON announcement_pdf_hashes;
DROP POLICY IF EXISTS "Enable update for service role" ON announcement_pdf_hashes;

-- Drop all existing policies on duplicate_detection_stats
DROP POLICY IF EXISTS "Service role has full access to duplicate_stats" ON duplicate_detection_stats;
DROP POLICY IF EXISTS "Authenticated users can read duplicate_stats" ON duplicate_detection_stats;
DROP POLICY IF EXISTS "Enable read access for all users" ON duplicate_detection_stats;
DROP POLICY IF EXISTS "Enable insert for service role" ON duplicate_detection_stats;
DROP POLICY IF EXISTS "Enable update for service role" ON duplicate_detection_stats;

-- Check if corporatefilings has RLS enabled and disable it if needed
-- (This allows scrapers to update pdf_hash, is_duplicate columns)
ALTER TABLE IF EXISTS corporatefilings DISABLE ROW LEVEL SECURITY;

-- Drop any RLS policies that might restrict corporatefilings updates
DROP POLICY IF EXISTS "Enable read access for all users" ON corporatefilings;
DROP POLICY IF EXISTS "Enable insert for service role" ON corporatefilings;
DROP POLICY IF EXISTS "Enable update for service role" ON corporatefilings;
DROP POLICY IF EXISTS "Service role has full access" ON corporatefilings;

-- =====================================================
-- VERIFICATION QUERIES
-- =====================================================

-- After running this script, verify RLS is disabled:
/*
-- Check RLS status for all tables
SELECT 
    schemaname,
    tablename,
    rowsecurity as rls_enabled
FROM pg_tables
WHERE schemaname = 'public'
    AND tablename IN ('announcement_pdf_hashes', 'duplicate_detection_stats', 'corporatefilings')
ORDER BY tablename;

-- Should show: rls_enabled = false for all three tables

-- Check that no policies exist
SELECT 
    schemaname,
    tablename,
    policyname
FROM pg_policies
WHERE schemaname = 'public'
    AND tablename IN ('announcement_pdf_hashes', 'duplicate_detection_stats', 'corporatefilings');

-- Should return no rows (all policies dropped)
*/
