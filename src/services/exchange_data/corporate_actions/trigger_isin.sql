-- ============================================================================
-- Trigger to populate ISIN for BSE records in corporate_actions table
-- ============================================================================
-- This trigger fills the ISIN field for BSE records using sec_code or symbol
-- from the stocklistdata table

CREATE OR REPLACE FUNCTION update_corporate_actions_isin()
RETURNS TRIGGER AS $$
BEGIN
    -- Only update ISIN for BSE records where it's missing
    IF NEW.exchange = 'BSE' AND (NEW.isin IS NULL OR NEW.isin = '') THEN
        -- Try to get ISIN using sec_code first
        IF NEW.sec_code IS NOT NULL AND NEW.sec_code != '' THEN
            SELECT isin INTO NEW.isin
            FROM stocklistdata
            WHERE securityid::text = NEW.sec_code
            LIMIT 1;
        END IF;
        
        -- If still not found, try using symbol (newbsecode)
        IF (NEW.isin IS NULL OR NEW.isin = '') AND NEW.symbol IS NOT NULL AND NEW.symbol != '' THEN
            SELECT isin INTO NEW.isin
            FROM stocklistdata
            WHERE newbsecode = NEW.symbol
            LIMIT 1;
        END IF;
        
        -- Last attempt: try with the generated symbol column
        IF (NEW.isin IS NULL OR NEW.isin = '') AND NEW.symbol IS NOT NULL AND NEW.symbol != '' THEN
            SELECT isin INTO NEW.isin
            FROM stocklistdata
            WHERE symbol = NEW.symbol
            LIMIT 1;
        END IF;
    END IF;
    
    RETURN NEW;
EXCEPTION
    WHEN OTHERS THEN
        -- If any error occurs, just return NEW without modification
        -- This prevents the trigger from blocking inserts due to missing data
        RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop existing trigger if it exists
DROP TRIGGER IF EXISTS trigger_update_corporate_actions_isin ON public.corporate_actions;

-- Create the trigger
CREATE TRIGGER trigger_update_corporate_actions_isin
BEFORE INSERT OR UPDATE ON public.corporate_actions
FOR EACH ROW
EXECUTE FUNCTION update_corporate_actions_isin();

-- ============================================================================
-- Comments
-- ============================================================================
COMMENT ON FUNCTION update_corporate_actions_isin() IS 'Automatically populates ISIN for BSE records in corporate_actions table using stocklistdata';

-- ============================================================================
-- Usage Instructions
-- ============================================================================
-- Run this SQL in your Supabase SQL editor after the main schema.sql
-- This trigger will automatically populate ISIN for BSE records when:
-- 1. A new BSE record is inserted
-- 2. An existing BSE record is updated
-- 3. The ISIN field is NULL or empty
--
-- The trigger tries to match using (in order):
-- 1. sec_code (securityid in stocklistdata)
-- 2. symbol (newbsecode in stocklistdata)
-- 3. symbol (symbol column in stocklistdata)
