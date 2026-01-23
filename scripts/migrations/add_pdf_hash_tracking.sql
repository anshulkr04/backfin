-- =====================================================
-- PDF HASH-BASED DUPLICATE DETECTION SYSTEM
-- Migration Script for Supabase
-- =====================================================
-- Purpose: Track PDF file hashes to detect duplicate announcements
--          from the same company. Duplicates are saved but hidden
--          from users by default.
-- =====================================================

-- 1. Create announcement_pdf_hashes table
-- This table stores unique PDF hashes per company
CREATE TABLE IF NOT EXISTS public.announcement_pdf_hashes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- PDF identification
    pdf_hash TEXT NOT NULL,  -- SHA-256 hash of PDF content
    pdf_size_bytes BIGINT,   -- File size for quick comparison
    
    -- Company relationship
    isin TEXT,                -- ISIN of the company
    symbol TEXT,              -- Stock symbol
    company_name TEXT,        -- Company name for reference
    
    -- Original announcement that introduced this PDF
    original_corp_id UUID NOT NULL,  -- Reference to first announcement with this PDF
    original_newsid TEXT,            -- BSE/NSE news ID of original
    original_date TEXT,              -- Store as TEXT to match corporatefilings.date type
    
    -- Metadata
    first_seen_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    duplicate_count INTEGER DEFAULT 0,  -- How many duplicates found
    
    -- Performance indexes
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT announcement_pdf_hashes_isin_hash_unique UNIQUE (isin, pdf_hash),
    CONSTRAINT announcement_pdf_hashes_corp_id_fkey FOREIGN KEY (original_corp_id) 
        REFERENCES public.corporatefilings(corp_id) ON DELETE CASCADE
);

-- Create indexes for efficient lookup
CREATE INDEX IF NOT EXISTS idx_pdf_hashes_hash ON announcement_pdf_hashes(pdf_hash);
CREATE INDEX IF NOT EXISTS idx_pdf_hashes_isin ON announcement_pdf_hashes(isin);
CREATE INDEX IF NOT EXISTS idx_pdf_hashes_symbol ON announcement_pdf_hashes(symbol);
CREATE INDEX IF NOT EXISTS idx_pdf_hashes_isin_hash ON announcement_pdf_hashes(isin, pdf_hash);
CREATE INDEX IF NOT EXISTS idx_pdf_hashes_original_corp_id ON announcement_pdf_hashes(original_corp_id);
CREATE INDEX IF NOT EXISTS idx_pdf_hashes_created_at ON announcement_pdf_hashes(created_at DESC);

-- Add comments for documentation
COMMENT ON TABLE announcement_pdf_hashes IS 'Stores PDF file hashes to detect duplicate announcements from the same company';
COMMENT ON COLUMN announcement_pdf_hashes.pdf_hash IS 'SHA-256 hash of PDF file content';
COMMENT ON COLUMN announcement_pdf_hashes.pdf_size_bytes IS 'Size of PDF file in bytes for quick pre-filtering';
COMMENT ON COLUMN announcement_pdf_hashes.original_corp_id IS 'Corp ID of the first announcement that had this PDF';
COMMENT ON COLUMN announcement_pdf_hashes.duplicate_count IS 'Number of duplicate announcements found with this PDF hash';


-- =====================================================
-- 2. Add duplicate tracking columns to corporatefilings
-- =====================================================

-- Add columns to track duplicate status
ALTER TABLE public.corporatefilings 
ADD COLUMN IF NOT EXISTS pdf_hash TEXT,
ADD COLUMN IF NOT EXISTS pdf_size_bytes BIGINT,
ADD COLUMN IF NOT EXISTS is_duplicate BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS original_announcement_id UUID,  -- Links to the original if this is a duplicate
ADD COLUMN IF NOT EXISTS duplicate_of_newsid TEXT;       -- BSE/NSE newsid of original

-- Create indexes for duplicate filtering
CREATE INDEX IF NOT EXISTS idx_corporatefilings_pdf_hash ON corporatefilings(pdf_hash);
CREATE INDEX IF NOT EXISTS idx_corporatefilings_is_duplicate ON corporatefilings(is_duplicate);
CREATE INDEX IF NOT EXISTS idx_corporatefilings_original_announcement_id ON corporatefilings(original_announcement_id);
CREATE INDEX IF NOT EXISTS idx_corporatefilings_isin_pdf_hash ON corporatefilings(isin, pdf_hash) WHERE pdf_hash IS NOT NULL;

-- Add foreign key constraint for original announcement reference (if not exists)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'corporatefilings_original_announcement_fkey'
    ) THEN
        ALTER TABLE public.corporatefilings
        ADD CONSTRAINT corporatefilings_original_announcement_fkey 
            FOREIGN KEY (original_announcement_id) 
            REFERENCES public.corporatefilings(corp_id) ON DELETE SET NULL;
    END IF;
END $$;

-- Add comments
COMMENT ON COLUMN corporatefilings.pdf_hash IS 'SHA-256 hash of the PDF file for duplicate detection';
COMMENT ON COLUMN corporatefilings.pdf_size_bytes IS 'Size of PDF file in bytes';
COMMENT ON COLUMN corporatefilings.is_duplicate IS 'TRUE if this announcement is a duplicate (same PDF from same company)';
COMMENT ON COLUMN corporatefilings.original_announcement_id IS 'Corp ID of the original announcement if this is a duplicate';
COMMENT ON COLUMN corporatefilings.duplicate_of_newsid IS 'NewsID of the original announcement if this is a duplicate';


-- =====================================================
-- 3. Create function to update duplicate count
-- =====================================================

CREATE OR REPLACE FUNCTION update_pdf_hash_duplicate_count()
RETURNS TRIGGER AS $$
BEGIN
    -- When a new duplicate is marked, increment the count
    IF NEW.is_duplicate = TRUE AND (OLD.is_duplicate IS NULL OR OLD.is_duplicate = FALSE) THEN
        UPDATE announcement_pdf_hashes
        SET 
            duplicate_count = duplicate_count + 1,
            updated_at = NOW()
        WHERE 
            pdf_hash = NEW.pdf_hash 
            AND isin = NEW.isin;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to automatically update duplicate count
DROP TRIGGER IF EXISTS trigger_update_pdf_hash_count ON corporatefilings;
CREATE TRIGGER trigger_update_pdf_hash_count
    AFTER UPDATE ON corporatefilings
    FOR EACH ROW
    WHEN (NEW.is_duplicate = TRUE)
    EXECUTE FUNCTION update_pdf_hash_duplicate_count();


-- =====================================================
-- 4. Create helper function to check for duplicate PDFs
-- =====================================================

CREATE OR REPLACE FUNCTION check_duplicate_pdf(
    p_isin TEXT,
    p_pdf_hash TEXT,
    p_symbol TEXT DEFAULT NULL
) RETURNS TABLE (
    is_duplicate BOOLEAN,
    original_corp_id UUID,
    original_newsid TEXT,
    duplicate_count INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        TRUE as is_duplicate,
        aph.original_corp_id,
        aph.original_newsid,
        aph.duplicate_count
    FROM announcement_pdf_hashes aph
    WHERE 
        aph.isin = p_isin 
        AND aph.pdf_hash = p_pdf_hash
    LIMIT 1;
    
    -- If no match found, return non-duplicate
    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, NULL::UUID, NULL::TEXT, 0;
    END IF;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION check_duplicate_pdf IS 'Check if a PDF hash already exists for a company (ISIN)';


-- =====================================================
-- 5. Create view for non-duplicate announcements
-- =====================================================

CREATE OR REPLACE VIEW public.unique_announcements AS
SELECT *
FROM public.corporatefilings
WHERE is_duplicate = FALSE OR is_duplicate IS NULL;

COMMENT ON VIEW unique_announcements IS 'View of announcements excluding duplicates - use this for user-facing queries';


-- =====================================================
-- 6. Create view for duplicate analysis
-- =====================================================

CREATE OR REPLACE VIEW public.duplicate_announcements_report AS
SELECT 
    cf_dup.corp_id as duplicate_corp_id,
    cf_dup.headline as duplicate_headline,
    cf_dup.date as duplicate_date,
    cf_dup.isin,
    cf_dup.symbol,
    cf_dup.companyname,
    cf_dup.pdf_hash,
    cf_orig.corp_id as original_corp_id,
    cf_orig.headline as original_headline,
    cf_orig.date as original_date,
    -- Cast text dates to timestamp for time difference calculation
    CASE 
        WHEN cf_dup.date IS NOT NULL AND cf_orig.date IS NOT NULL 
        THEN cf_dup.date::timestamp with time zone - cf_orig.date::timestamp with time zone
        ELSE NULL
    END as time_difference,
    aph.duplicate_count as total_duplicates_for_hash
FROM corporatefilings cf_dup
LEFT JOIN corporatefilings cf_orig ON cf_dup.original_announcement_id = cf_orig.corp_id
LEFT JOIN announcement_pdf_hashes aph ON cf_dup.pdf_hash = aph.pdf_hash AND cf_dup.isin = aph.isin
WHERE cf_dup.is_duplicate = TRUE
ORDER BY cf_dup.date DESC;

COMMENT ON VIEW duplicate_announcements_report IS 'Analysis view showing all duplicates with their original announcements';


-- =====================================================
-- 7. Create indexes for performance
-- =====================================================

-- Composite index for efficient duplicate checking during insertion
CREATE INDEX IF NOT EXISTS idx_corporatefilings_lookup ON corporatefilings(isin, date DESC, is_duplicate) 
    WHERE pdf_hash IS NOT NULL;

-- Index for API queries that need to exclude duplicates
CREATE INDEX IF NOT EXISTS idx_corporatefilings_user_view ON corporatefilings(date DESC, isin) 
    WHERE (is_duplicate = FALSE OR is_duplicate IS NULL);


-- =====================================================
-- 8. Create statistics tracking table
-- =====================================================

CREATE TABLE IF NOT EXISTS public.duplicate_detection_stats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date DATE NOT NULL UNIQUE DEFAULT CURRENT_DATE,
    
    -- Daily statistics
    total_announcements_processed INTEGER DEFAULT 0,
    duplicates_detected INTEGER DEFAULT 0,
    unique_announcements INTEGER DEFAULT 0,
    duplicate_percentage DECIMAL(5,2),
    
    -- Hash statistics
    unique_pdf_hashes_added INTEGER DEFAULT 0,
    companies_affected INTEGER DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_duplicate_stats_date ON duplicate_detection_stats(date DESC);

COMMENT ON TABLE duplicate_detection_stats IS 'Daily statistics for duplicate detection system';


-- =====================================================
-- 9. Create function to update daily statistics
-- =====================================================

CREATE OR REPLACE FUNCTION update_duplicate_stats()
RETURNS void AS $$
DECLARE
    today_date DATE := CURRENT_DATE;
    v_total_announcements INTEGER;
    v_duplicates INTEGER;
    v_unique_announcements INTEGER;
    v_duplicate_pct DECIMAL(5,2);
    v_unique_hashes INTEGER;
    v_companies_affected INTEGER;
BEGIN
    -- Count announcements from today
    SELECT COUNT(*) INTO v_total_announcements
    FROM corporatefilings
    WHERE DATE(date) = today_date;
    
    SELECT COUNT(*) INTO v_duplicates
    FROM corporatefilings
    WHERE DATE(date) = today_date AND is_duplicate = TRUE;
    
    v_unique_announcements := v_total_announcements - v_duplicates;
    
    v_duplicate_pct := CASE 
        WHEN v_total_announcements > 0 THEN 
            ROUND((v_duplicates::DECIMAL / v_total_announcements::DECIMAL) * 100, 2)
        ELSE 0 
    END;
    
    SELECT COUNT(DISTINCT pdf_hash) INTO v_unique_hashes
    FROM announcement_pdf_hashes
    WHERE DATE(first_seen_at) = today_date;
    
    SELECT COUNT(DISTINCT isin) INTO v_companies_affected
    FROM corporatefilings
    WHERE DATE(date) = today_date AND is_duplicate = TRUE;
    
    -- Insert or update statistics
    INSERT INTO duplicate_detection_stats (
        date, 
        total_announcements_processed, 
        duplicates_detected, 
        unique_announcements,
        duplicate_percentage,
        unique_pdf_hashes_added,
        companies_affected,
        updated_at
    )
    VALUES (
        today_date,
        v_total_announcements,
        v_duplicates,
        v_unique_announcements,
        v_duplicate_pct,
        v_unique_hashes,
        v_companies_affected,
        NOW()
    )
    ON CONFLICT (date) DO UPDATE SET
        total_announcements_processed = EXCLUDED.total_announcements_processed,
        duplicates_detected = EXCLUDED.duplicates_detected,
        unique_announcements = EXCLUDED.unique_announcements,
        duplicate_percentage = EXCLUDED.duplicate_percentage,
        unique_pdf_hashes_added = EXCLUDED.unique_pdf_hashes_added,
        companies_affected = EXCLUDED.companies_affected,
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_duplicate_stats IS 'Update daily duplicate detection statistics. Run this at end of day or via cron job.';


-- =====================================================
-- 10. DISABLE RLS (Row Level Security) - Make Unrestricted
-- =====================================================

-- DISABLE RLS on new tables to allow unrestricted access
ALTER TABLE announcement_pdf_hashes DISABLE ROW LEVEL SECURITY;
ALTER TABLE duplicate_detection_stats DISABLE ROW LEVEL SECURITY;

-- Drop any existing policies (in case they were created before)
DROP POLICY IF EXISTS "Service role has full access to pdf_hashes" ON announcement_pdf_hashes;
DROP POLICY IF EXISTS "Service role has full access to duplicate_stats" ON duplicate_detection_stats;
DROP POLICY IF EXISTS "Authenticated users can read pdf_hashes" ON announcement_pdf_hashes;
DROP POLICY IF EXISTS "Authenticated users can read duplicate_stats" ON duplicate_detection_stats;

-- Note: Tables are now accessible without RLS restrictions
-- All authenticated and anonymous users can read/write to these tables


-- =====================================================
-- 11. Create admin utility functions
-- =====================================================

-- Function to find all duplicates for a specific announcement
CREATE OR REPLACE FUNCTION find_announcement_duplicates(p_corp_id UUID)
RETURNS TABLE (
    corp_id UUID,
    headline TEXT,
    date TIMESTAMP WITH TIME ZONE,
    is_original BOOLEAN,
    pdf_hash TEXT
) AS $$
DECLARE
    v_pdf_hash TEXT;
    v_isin TEXT;
BEGIN
    -- Get the PDF hash and ISIN from the given announcement
    SELECT cf.pdf_hash, cf.isin INTO v_pdf_hash, v_isin
    FROM corporatefilings cf
    WHERE cf.corp_id = p_corp_id;
    
    -- Return all announcements with the same hash and ISIN
    RETURN QUERY
    SELECT 
        cf.corp_id,
        cf.headline,
        cf.date,
        (cf.corp_id = p_corp_id) as is_original,
        cf.pdf_hash
    FROM corporatefilings cf
    WHERE 
        cf.pdf_hash = v_pdf_hash 
        AND cf.isin = v_isin
        AND cf.pdf_hash IS NOT NULL
    ORDER BY cf.date ASC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION find_announcement_duplicates IS 'Find all announcements that share the same PDF hash as the given announcement';


-- Function to rebuild hash tracking from existing data (for migration)
CREATE OR REPLACE FUNCTION rebuild_pdf_hash_tracking()
RETURNS TABLE (
    processed_count INTEGER,
    duplicates_found INTEGER,
    hashes_created INTEGER
) AS $$
DECLARE
    v_processed INTEGER := 0;
    v_duplicates INTEGER := 0;
    v_hashes INTEGER := 0;
BEGIN
    -- This would be run once during migration to populate hashes for existing announcements
    -- For now, return 0s as a placeholder
    RETURN QUERY SELECT 0, 0, 0;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION rebuild_pdf_hash_tracking IS 'Rebuild hash tracking for existing announcements (run once during migration)';


-- =====================================================
-- ROLLBACK SCRIPT (keep for reference, commented out)
-- =====================================================

/*
-- To rollback this migration, run the following:

-- Drop triggers
DROP TRIGGER IF EXISTS trigger_update_pdf_hash_count ON corporatefilings;

-- Drop functions
DROP FUNCTION IF EXISTS update_pdf_hash_duplicate_count();
DROP FUNCTION IF EXISTS check_duplicate_pdf(TEXT, TEXT, TEXT);
DROP FUNCTION IF EXISTS update_duplicate_stats();
DROP FUNCTION IF EXISTS find_announcement_duplicates(UUID);
DROP FUNCTION IF EXISTS rebuild_pdf_hash_tracking();

-- Drop views
DROP VIEW IF EXISTS duplicate_announcements_report;
DROP VIEW IF EXISTS unique_announcements;

-- Drop tables
DROP TABLE IF EXISTS duplicate_detection_stats;
DROP TABLE IF EXISTS announcement_pdf_hashes;

-- Remove columns from corporatefilings
ALTER TABLE corporatefilings DROP COLUMN IF EXISTS pdf_hash;
ALTER TABLE corporatefilings DROP COLUMN IF EXISTS pdf_size_bytes;
ALTER TABLE corporatefilings DROP COLUMN IF EXISTS is_duplicate;
ALTER TABLE corporatefilings DROP COLUMN IF EXISTS original_announcement_id;
ALTER TABLE corporatefilings DROP COLUMN IF EXISTS duplicate_of_newsid;
*/


-- =====================================================
-- VERIFICATION QUERIES
-- =====================================================

-- After running this migration, verify with:
/*
-- 1. Check tables were created
SELECT tablename FROM pg_tables WHERE schemaname = 'public' 
    AND tablename IN ('announcement_pdf_hashes', 'duplicate_detection_stats');

-- 2. Check columns were added to corporatefilings
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'corporatefilings' 
    AND column_name IN ('pdf_hash', 'is_duplicate', 'original_announcement_id');

-- 3. Check indexes were created
SELECT indexname FROM pg_indexes 
WHERE schemaname = 'public' 
    AND indexname LIKE '%pdf_hash%' OR indexname LIKE '%duplicate%';

-- 4. Check functions were created
SELECT routine_name FROM information_schema.routines 
WHERE routine_schema = 'public' 
    AND routine_name LIKE '%duplicate%' OR routine_name LIKE '%pdf_hash%';

-- 5. Check views were created
SELECT table_name FROM information_schema.views 
WHERE table_schema = 'public' 
    AND table_name IN ('unique_announcements', 'duplicate_announcements_report');
*/
