-- ============================================================================
-- Migration: Create Classification Comparison Table
-- Purpose: Store and compare Gemini vs Gemma 3 27B classification results
-- ============================================================================

-- Create the classification comparison table
CREATE TABLE IF NOT EXISTS public.classification_comparison (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Reference to the original announcement
    corp_id UUID REFERENCES public.corporatefilings(corp_id),
    
    -- PDF information
    pdf_url TEXT NOT NULL,
    pdf_hash TEXT,
    
    -- Gemini classification results (existing model)
    gemini_category TEXT,
    gemini_confidence TEXT,
    gemini_processed_at TIMESTAMPTZ,
    
    -- Gemma 3 27B classification results (new model)
    gemma_category TEXT,
    gemma_confidence TEXT,
    gemma_processed_at TIMESTAMPTZ,
    
    -- Summary from the AI analysis
    summary TEXT,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Comparison result (populated by trigger or application)
    categories_match BOOLEAN GENERATED ALWAYS AS (
        LOWER(TRIM(gemini_category)) = LOWER(TRIM(gemma_category))
    ) STORED,
    
    -- ISIN and symbol for easier querying
    isin TEXT,
    symbol TEXT,
    company_name TEXT
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_classification_comparison_corp_id 
    ON public.classification_comparison(corp_id);

CREATE INDEX IF NOT EXISTS idx_classification_comparison_created_at 
    ON public.classification_comparison(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_classification_comparison_categories_match 
    ON public.classification_comparison(categories_match);

CREATE INDEX IF NOT EXISTS idx_classification_comparison_gemini_category 
    ON public.classification_comparison(gemini_category);

CREATE INDEX IF NOT EXISTS idx_classification_comparison_gemma_category 
    ON public.classification_comparison(gemma_category);

CREATE INDEX IF NOT EXISTS idx_classification_comparison_isin 
    ON public.classification_comparison(isin);

CREATE INDEX IF NOT EXISTS idx_classification_comparison_pdf_hash 
    ON public.classification_comparison(pdf_hash);

-- Create updated_at trigger function if not exists
CREATE OR REPLACE FUNCTION update_classification_comparison_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to auto-update updated_at
DROP TRIGGER IF EXISTS trigger_update_classification_comparison_updated_at 
    ON public.classification_comparison;
    
CREATE TRIGGER trigger_update_classification_comparison_updated_at
    BEFORE UPDATE ON public.classification_comparison
    FOR EACH ROW
    EXECUTE FUNCTION update_classification_comparison_updated_at();

-- Add comments
COMMENT ON TABLE public.classification_comparison IS 
    'Stores classification results from both Gemini and Gemma 3 27B for comparison';

COMMENT ON COLUMN public.classification_comparison.gemini_category IS 
    'Category assigned by Gemini model (existing classification)';

COMMENT ON COLUMN public.classification_comparison.gemma_category IS 
    'Category assigned by Gemma 3 27B model (new classification)';

COMMENT ON COLUMN public.classification_comparison.categories_match IS 
    'Auto-computed: TRUE if both models assigned the same category';

COMMENT ON COLUMN public.classification_comparison.pdf_url IS 
    'URL of the PDF file that was classified';

COMMENT ON COLUMN public.classification_comparison.summary IS 
    'AI-generated summary of the announcement';

-- Create view for easy analysis of mismatches
CREATE OR REPLACE VIEW public.classification_mismatches AS
SELECT 
    cc.id,
    cc.corp_id,
    cc.isin,
    cc.symbol,
    cc.company_name,
    cc.pdf_url,
    cc.gemini_category,
    cc.gemma_category,
    cc.gemini_confidence,
    cc.gemma_confidence,
    cc.summary,
    cc.created_at
FROM public.classification_comparison cc
WHERE cc.categories_match = FALSE
ORDER BY cc.created_at DESC;

COMMENT ON VIEW public.classification_mismatches IS 
    'View showing only classifications where Gemini and Gemma disagree';

-- Create view for classification statistics
CREATE OR REPLACE VIEW public.classification_stats AS
SELECT 
    COUNT(*) as total_comparisons,
    COUNT(*) FILTER (WHERE categories_match = TRUE) as matching_count,
    COUNT(*) FILTER (WHERE categories_match = FALSE) as mismatch_count,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE categories_match = TRUE) / NULLIF(COUNT(*), 0), 
        2
    ) as match_percentage,
    COUNT(DISTINCT gemini_category) as unique_gemini_categories,
    COUNT(DISTINCT gemma_category) as unique_gemma_categories
FROM public.classification_comparison
WHERE gemini_category IS NOT NULL AND gemma_category IS NOT NULL;

COMMENT ON VIEW public.classification_stats IS 
    'Aggregate statistics on classification comparison results';

-- Create view for category-wise breakdown
CREATE OR REPLACE VIEW public.classification_category_breakdown AS
SELECT 
    COALESCE(gemini_category, 'NULL') as category,
    COUNT(*) as gemini_count,
    COUNT(*) FILTER (WHERE categories_match = TRUE) as gemma_agrees,
    COUNT(*) FILTER (WHERE categories_match = FALSE) as gemma_disagrees,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE categories_match = TRUE) / NULLIF(COUNT(*), 0),
        2
    ) as agreement_rate
FROM public.classification_comparison
WHERE gemini_category IS NOT NULL
GROUP BY gemini_category
ORDER BY gemini_count DESC;

COMMENT ON VIEW public.classification_category_breakdown IS 
    'Category-wise breakdown showing agreement rates between models';

-- Grant permissions (adjust as needed)
-- GRANT SELECT ON public.classification_comparison TO authenticated;
-- GRANT SELECT ON public.classification_mismatches TO authenticated;
-- GRANT SELECT ON public.classification_stats TO authenticated;
-- GRANT SELECT ON public.classification_category_breakdown TO authenticated;

-- ============================================================================
-- How to run this migration:
-- 1. Connect to your Supabase project via SQL Editor
-- 2. Copy and paste this entire script
-- 3. Execute the script
-- ============================================================================
