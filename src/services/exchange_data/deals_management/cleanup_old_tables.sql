-- ================================================================
-- CLEANUP SCRIPT - Remove Verification Tables
-- ================================================================
-- 
-- This script removes the deals_pending_verification table and
-- related objects since deals are now inserted directly into
-- the deals table without manual verification.
--
-- Run this script in your Supabase SQL editor after backing up
-- any data you want to keep.
-- ================================================================

-- Drop the verification statistics view
DROP VIEW IF EXISTS public.deals_verification_stats;

-- Drop triggers from deals_pending_verification table
DROP TRIGGER IF EXISTS trigger_auto_populate_securityid_pending ON public.deals_pending_verification;

-- Drop the deals_pending_verification table
-- WARNING: This will delete all pending verification data
DROP TABLE IF EXISTS public.deals_pending_verification CASCADE;

-- Note: We keep the trigger on the deals table and the function
-- since they're still used for auto-populating securityid
-- when deals are inserted directly.

-- Verify the cleanup
SELECT 
    'Cleanup completed. Remaining tables:' as status,
    tablename 
FROM pg_tables 
WHERE schemaname = 'public' 
    AND tablename LIKE '%deal%'
ORDER BY tablename;
