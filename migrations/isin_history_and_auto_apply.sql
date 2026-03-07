-- Migration: ISIN History and Company Management Improvements
-- Date: 2026-03-07
-- Purpose: Track ISIN changes over time, enable cascading updates

-- 1. ISIN History table - tracks all ISIN changes for a company
CREATE TABLE IF NOT EXISTS public.isin_history (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL,
    old_isin text NOT NULL,
    new_isin text NOT NULL,
    changed_at timestamp with time zone DEFAULT now(),
    source text DEFAULT 'detect_changes',
    CONSTRAINT isin_history_pkey PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_isin_history_old_isin ON public.isin_history(old_isin);
CREATE INDEX IF NOT EXISTS idx_isin_history_new_isin ON public.isin_history(new_isin);
CREATE INDEX IF NOT EXISTS idx_isin_history_company_id ON public.isin_history(company_id);

-- 2. Add company_id index on corporatefilings for fast lookups
CREATE INDEX IF NOT EXISTS idx_corporatefilings_company_id ON public.corporatefilings(company_id);
CREATE INDEX IF NOT EXISTS idx_corporatefilings_isin ON public.corporatefilings(isin);

-- 3. Function to resolve company_id from ISIN (handles historical ISINs)
CREATE OR REPLACE FUNCTION public.resolve_company_id(p_isin text)
RETURNS uuid AS $$
DECLARE
    v_company_id uuid;
BEGIN
    -- First try current ISIN
    SELECT company_id INTO v_company_id
    FROM public.stocklistdata
    WHERE isin = p_isin
    LIMIT 1;
    
    IF v_company_id IS NOT NULL THEN
        RETURN v_company_id;
    END IF;
    
    -- Try historical ISIN
    SELECT s.company_id INTO v_company_id
    FROM public.isin_history h
    JOIN public.stocklistdata s ON s.isin = h.new_isin
    WHERE h.old_isin = p_isin
    ORDER BY h.changed_at DESC
    LIMIT 1;
    
    RETURN v_company_id;
END;
$$ LANGUAGE plpgsql;

-- 4. Function to auto-apply a company change (no verification needed)
CREATE OR REPLACE FUNCTION public.auto_apply_company_change(
    p_change_id uuid,
    p_applied_by text DEFAULT 'auto_apply_cron'
)
RETURNS json AS $$
DECLARE
    v_change record;
    v_company_id uuid;
    v_result json;
BEGIN
    -- Get the change
    SELECT * INTO v_change
    FROM public.company_changes_pending
    WHERE id = p_change_id AND applied = false;
    
    IF v_change IS NULL THEN
        RETURN json_build_object('success', false, 'error', 'Change not found or already applied');
    END IF;
    
    -- Handle based on change type
    IF v_change.change_type = 'new' THEN
        -- New company: insert into stocklistdata
        INSERT INTO public.stocklistdata (isin, securityid, newbsecode, newnsecode, newname, symbol, sector)
        VALUES (
            v_change.new_isin,
            v_change.new_securityid,
            v_change.new_bsecode,
            v_change.new_nsecode,
            v_change.new_name,
            v_change.new_symbol,
            v_change.new_sector
        )
        ON CONFLICT (isin) DO NOTHING;
        
    ELSIF v_change.change_type = 'isin' OR v_change.change_type LIKE '%isin%' THEN
        -- ISIN change: get company_id, record in history, update stocklistdata
        SELECT company_id INTO v_company_id
        FROM public.stocklistdata
        WHERE isin = v_change.old_isin OR isin = v_change.isin
        LIMIT 1;
        
        IF v_company_id IS NOT NULL THEN
            -- Record ISIN change in history
            INSERT INTO public.isin_history (company_id, old_isin, new_isin, source)
            VALUES (v_company_id, COALESCE(v_change.old_isin, v_change.isin), v_change.new_isin, 'detect_changes');
            
            -- Update stocklistdata
            UPDATE public.stocklistdata
            SET isin = v_change.new_isin,
                securityid = COALESCE(v_change.new_securityid, securityid),
                newbsecode = COALESCE(v_change.new_bsecode, newbsecode),
                newnsecode = COALESCE(v_change.new_nsecode, newnsecode),
                newname = COALESCE(v_change.new_name, newname),
                symbol = COALESCE(v_change.new_symbol, symbol),
                sector = COALESCE(v_change.new_sector, sector)
            WHERE company_id = v_company_id;
            
            -- Update corporatefilings with new ISIN (only recent ones since Nov 2025)
            UPDATE public.corporatefilings
            SET isin = v_change.new_isin,
                company_id = v_company_id
            WHERE isin = COALESCE(v_change.old_isin, v_change.isin)
              AND date >= '2025-11-01';
              
            -- Also set company_id on recent filings that match old ISIN but don't have company_id
            UPDATE public.corporatefilings
            SET company_id = v_company_id
            WHERE isin = v_change.new_isin
              AND company_id IS NULL
              AND date >= '2025-11-01';
        END IF;
        
    ELSE
        -- Other changes (name, bsecode, nsecode, etc): just update stocklistdata
        UPDATE public.stocklistdata
        SET securityid = COALESCE(v_change.new_securityid, securityid),
            newbsecode = COALESCE(v_change.new_bsecode, newbsecode),
            newnsecode = COALESCE(v_change.new_nsecode, newnsecode),
            newname = COALESCE(v_change.new_name, newname),
            symbol = COALESCE(v_change.new_symbol, symbol),
            sector = COALESCE(v_change.new_sector, sector)
        WHERE isin = v_change.isin;
    END IF;
    
    -- Mark change as applied
    UPDATE public.company_changes_pending
    SET applied = true,
        applied_at = now(),
        verified = true,
        review_status = 'approved'
    WHERE id = p_change_id;
    
    -- Audit log
    INSERT INTO public.company_changes_audit_log (pending_change_id, isin, action, notes, created_at)
    VALUES (p_change_id, v_change.isin, 'applied', 'Auto-applied by cron', now());
    
    RETURN json_build_object('success', true, 'change_type', v_change.change_type, 'isin', v_change.isin);
END;
$$ LANGUAGE plpgsql;

COMMENT ON TABLE public.isin_history IS 'Tracks historical ISIN changes for companies. Enables resolution of old ISINs to current company_id.';
COMMENT ON FUNCTION public.resolve_company_id IS 'Resolves a company_id from an ISIN, including historical ISINs.';
COMMENT ON FUNCTION public.auto_apply_company_change IS 'Auto-applies a detected company change without manual verification.';
