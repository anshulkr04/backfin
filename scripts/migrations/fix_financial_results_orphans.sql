-- =====================================================
-- FIX: Clean up orphaned financial_results before adding FK
-- =====================================================
-- Purpose: Remove financial_results rows that reference 
--          non-existent corporatefilings before adding FK constraint
-- Date: 2026-01-14
-- =====================================================

-- Step 1: Check how many orphaned rows exist
SELECT COUNT(*) as orphaned_count
FROM financial_results fr
WHERE NOT EXISTS (
    SELECT 1 FROM corporatefilings cf WHERE cf.corp_id = fr.corp_id
);

-- Step 2: Delete orphaned financial_results (those with invalid corp_id)
DELETE FROM financial_results
WHERE corp_id NOT IN (
    SELECT corp_id FROM corporatefilings
);

-- Step 3: Verify cleanup worked
SELECT COUNT(*) as orphaned_after_cleanup
FROM financial_results fr
WHERE NOT EXISTS (
    SELECT 1 FROM corporatefilings cf WHERE cf.corp_id = fr.corp_id
);

-- Step 4: Now add the FK constraint (should succeed now)
DO $$
BEGIN
    -- Drop existing constraint if it exists
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'fk_financial_results_corp_id' 
        AND table_name = 'financial_results'
    ) THEN
        ALTER TABLE financial_results DROP CONSTRAINT fk_financial_results_corp_id;
    END IF;
    
    -- Add the FK constraint
    ALTER TABLE financial_results
    ADD CONSTRAINT fk_financial_results_corp_id 
    FOREIGN KEY (corp_id) REFERENCES corporatefilings(corp_id) ON DELETE CASCADE;
    
    RAISE NOTICE 'FK constraint added successfully';
END $$;

-- Step 5: Create index for performance
CREATE INDEX IF NOT EXISTS idx_financial_results_corp_id ON financial_results(corp_id);

-- Step 6: Reload PostgREST schema cache
NOTIFY pgrst, 'reload schema';

-- =====================================================
-- VERIFICATION
-- =====================================================
-- Check constraint exists:
/*
SELECT constraint_name, table_name 
FROM information_schema.table_constraints 
WHERE constraint_name = 'fk_financial_results_corp_id';
*/
