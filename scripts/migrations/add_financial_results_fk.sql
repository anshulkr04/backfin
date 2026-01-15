-- =====================================================
-- ADD FOREIGN KEY FOR FINANCIAL RESULTS -> CORPORATEFILINGS
-- =====================================================
-- Purpose: Fix PostgREST relationship error by adding explicit FK
-- Date: 2026-01-14
-- Issue: "Could not find a relationship between 'financial_results' 
--         and 'corporatefilings' in the schema cache"
-- =====================================================

-- Add foreign key constraint from financial_results.corp_id to corporatefilings.corp_id
-- This allows PostgREST to understand the relationship for JOIN queries

DO $$
BEGIN
    -- Check if the foreign key constraint already exists
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.table_constraints 
        WHERE constraint_name = 'fk_financial_results_corp_id' 
        AND table_name = 'financial_results'
        AND constraint_type = 'FOREIGN KEY'
    ) THEN
        -- Add the foreign key constraint
        ALTER TABLE financial_results
        ADD CONSTRAINT fk_financial_results_corp_id 
        FOREIGN KEY (corp_id) 
        REFERENCES corporatefilings(corp_id) 
        ON DELETE CASCADE;
        
        RAISE NOTICE 'Added foreign key constraint: fk_financial_results_corp_id';
    ELSE
        RAISE NOTICE 'Foreign key constraint fk_financial_results_corp_id already exists';
    END IF;
END $$;

-- Create index on corp_id if it doesn't exist (for FK performance)
CREATE INDEX IF NOT EXISTS idx_financial_results_corp_id ON financial_results(corp_id);

-- Add comment explaining the relationship
COMMENT ON CONSTRAINT fk_financial_results_corp_id ON financial_results IS 
'Links financial results to their parent corporate filing announcement';

-- =====================================================
-- VERIFICATION QUERY
-- =====================================================

-- Verify the foreign key was created:
/*
SELECT
    tc.constraint_name,
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
    AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
    AND tc.table_name = 'financial_results'
    AND kcu.column_name = 'corp_id';
*/

-- Expected output:
-- constraint_name: fk_financial_results_corp_id
-- table_name: financial_results
-- column_name: corp_id
-- foreign_table_name: corporatefilings
-- foreign_column_name: corp_id

-- =====================================================
-- RELOAD SCHEMA CACHE (IMPORTANT!)
-- =====================================================

-- After running this migration, you MUST reload the PostgREST schema cache
-- Run this command or restart your API:
/*
NOTIFY pgrst, 'reload schema';
*/

-- Alternatively, restart the API server to reload the schema cache automatically
