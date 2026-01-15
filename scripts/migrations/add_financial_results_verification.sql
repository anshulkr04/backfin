-- Migration: Add verification tracking to financial_results table
-- Date: 2026-01-14
-- Purpose: Enable verification workflow for financial results data

-- Note: verified column already exists as TEXT type, so we skip adding it
-- Add verification timestamp and user columns if they don't exist
ALTER TABLE financial_results 
ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS verified_by UUID;

-- Ensure verified column has default value (it's already TEXT type)
ALTER TABLE financial_results 
ALTER COLUMN verified SET DEFAULT 'false';

-- Add foreign key constraint to corporatefilings (REQUIRED for PostgREST JOINs)
DO $$
BEGIN
    -- Add FK from financial_results.corp_id -> corporatefilings.corp_id
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'fk_financial_results_corp_id' 
        AND table_name = 'financial_results'
    ) THEN
        ALTER TABLE financial_results
        ADD CONSTRAINT fk_financial_results_corp_id 
        FOREIGN KEY (corp_id) REFERENCES corporatefilings(corp_id) ON DELETE CASCADE;
    END IF;
END $$;

-- Add foreign key constraint to admin_users if the table exists
DO $$
BEGIN
    -- Check if admin_users table exists before adding foreign key
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'admin_users') THEN
        -- Add foreign key constraint if it doesn't exist
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.table_constraints 
            WHERE constraint_name = 'fk_financial_results_verified_by' 
            AND table_name = 'financial_results'
        ) THEN
            ALTER TABLE financial_results
            ADD CONSTRAINT fk_financial_results_verified_by 
            FOREIGN KEY (verified_by) REFERENCES admin_users(id);
        END IF;
    END IF;
END $$;

-- Create index for faster queries on verified status
CREATE INDEX IF NOT EXISTS idx_financial_results_verified ON financial_results(verified);
CREATE INDEX IF NOT EXISTS idx_financial_results_verified_at ON financial_results(verified_at);
CREATE INDEX IF NOT EXISTS idx_financial_results_verified_by ON financial_results(verified_by);

-- Create composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_financial_results_verified_corp_id ON financial_results(verified, corp_id);
CREATE INDEX IF NOT EXISTS idx_financial_results_company_id ON financial_results(company_id);
CREATE INDEX IF NOT EXISTS idx_financial_results_isin ON financial_results(isin);

-- Create view for unverified financial results
CREATE OR REPLACE VIEW financial_results_unverified AS
SELECT 
    fr.*,
    cf.date as announcement_date,
    cf.companyname,
    cf.category as announcement_category,
    cf.verified as announcement_verified
FROM financial_results fr
LEFT JOIN corporatefilings cf ON fr.corp_id = cf.corp_id
WHERE fr.verified = 'false' OR fr.verified IS NULL;

-- Create view for verified financial results
CREATE OR REPLACE VIEW financial_results_verified AS
SELECT 
    fr.*,
    cf.date as announcement_date,
    cf.companyname,
    cf.category as announcement_category,
    au.email as verified_by_email,
    au.name as verified_by_name
FROM financial_results fr
LEFT JOIN corporatefilings cf ON fr.corp_id = cf.corp_id
LEFT JOIN admin_users au ON fr.verified_by = au.id
WHERE fr.verified = 'true';

-- Create function to auto-verify financial results when announcement is verified
CREATE OR REPLACE FUNCTION auto_verify_financial_results()
RETURNS TRIGGER AS $$
BEGIN
    -- When an announcement is verified, verify associated financial results
    IF NEW.verified = true AND (OLD.verified IS NULL OR OLD.verified = false) THEN
        UPDATE financial_results
        SET 
            verified = 'true',
            verified_at = NEW.verified_at,
            verified_by = NEW.verified_by
        WHERE corp_id = NEW.corp_id AND (verified = 'false' OR verified IS NULL);
    END IF;
    
    -- When an announcement is unverified, unverify associated financial results
    IF NEW.verified = false AND OLD.verified = true THEN
        UPDATE financial_results
        SET 
            verified = 'false',
            verified_at = NULL,
            verified_by = NULL
        WHERE corp_id = NEW.corp_id AND verified = 'true';
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for auto-verification
DROP TRIGGER IF EXISTS trigger_auto_verify_financial_results ON corporatefilings;
CREATE TRIGGER trigger_auto_verify_financial_results
    AFTER UPDATE OF verified ON corporatefilings
    FOR EACH ROW
    WHEN (OLD.verified IS DISTINCT FROM NEW.verified)
    EXECUTE FUNCTION auto_verify_financial_results();

-- Add comment to explain the verification workflow
COMMENT ON COLUMN financial_results.verified IS 'Indicates if the financial result has been verified by an admin/verifier';
COMMENT ON COLUMN financial_results.verified_at IS 'Timestamp when the financial result was verified';
COMMENT ON COLUMN financial_results.verified_by IS 'UUID of the admin/verifier who verified this financial result';
COMMENT ON TRIGGER trigger_auto_verify_financial_results ON corporatefilings IS 'Automatically verifies/unverifies financial results when parent announcement verification status changes';

-- Grant necessary permissions (adjust as needed for your setup)
-- GRANT SELECT ON financial_results_unverified TO authenticated;
-- GRANT SELECT ON financial_results_verified TO authenticated;
