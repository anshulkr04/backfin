-- Migration: V2 Corporate Filings RPC (Fixed)
-- Fixes UUID/TEXT type mismatches, improves reliability
-- Run this in the Supabase SQL Editor
--
-- TYPE MAP (from actual schema):
--   UserData.UserID           = UUID
--   corporatefilings.corp_id  = UUID
--   user_read_filings.user_id = TEXT   ← stores UUID as string
--   user_read_filings.corp_id = TEXT   ← stores UUID as string
--   watchlistdata.userid      = UUID
--   watchlistnamedata.userid  = TEXT
--   stocklistdata.isin        = TEXT
--   corporatefilings.isin     = TEXT
--   investorCorp.corp_id      = UUID
--
-- Key casts needed:
--   JOIN user_read_filings.corp_id (TEXT) = corporatefilings.corp_id (UUID)
--     → use: urf.corp_id = cf.corp_id::text
--   WHERE watchlistdata.userid (UUID) = p_user_id (TEXT)
--     → use: w.userid = p_user_id::uuid

-- ============================================================
-- 1. user_read_filings table (idempotent)
-- ============================================================
CREATE TABLE IF NOT EXISTS user_read_filings (
    user_id TEXT NOT NULL,
    corp_id TEXT NOT NULL,
    read_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, corp_id)
);

CREATE INDEX IF NOT EXISTS idx_urf_user_id ON user_read_filings(user_id);
CREATE INDEX IF NOT EXISTS idx_urf_corp_id ON user_read_filings(corp_id);

-- Enable RLS (service role has full access)
ALTER TABLE user_read_filings ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'user_read_filings'
        AND policyname = 'Service role full access on user_read_filings'
    ) THEN
        CREATE POLICY "Service role full access on user_read_filings"
            ON user_read_filings FOR ALL
            USING (true) WITH CHECK (true);
    END IF;
END $$;

-- ============================================================
-- 2. If user_read_filings.user_id was previously UUID, migrate to TEXT
--    (safe to run even if already TEXT)
-- ============================================================
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'user_read_filings'
        AND column_name = 'user_id'
        AND data_type = 'uuid'
    ) THEN
        ALTER TABLE user_read_filings DROP CONSTRAINT IF EXISTS user_read_filings_pkey;
        ALTER TABLE user_read_filings ALTER COLUMN user_id TYPE TEXT USING user_id::text;
        ALTER TABLE user_read_filings ADD PRIMARY KEY (user_id, corp_id);
        RAISE NOTICE 'Migrated user_read_filings.user_id from UUID to TEXT';
    END IF;
END $$;

-- ============================================================
-- 3. Drop old function if exists, then create fixed version
-- ============================================================
DROP FUNCTION IF EXISTS get_corporate_filings_v2(TEXT, TEXT, TEXT, TEXT[], TEXT[], TEXT[], BOOLEAN, TEXT, TEXT[], BOOLEAN, INTEGER, INTEGER);

CREATE OR REPLACE FUNCTION get_corporate_filings_v2(
    p_user_id TEXT,
    p_start_date TEXT DEFAULT NULL,
    p_end_date TEXT DEFAULT NULL,
    p_categories TEXT[] DEFAULT NULL,
    p_symbols TEXT[] DEFAULT NULL,
    p_isins TEXT[] DEFAULT NULL,
    p_watchlist_only BOOLEAN DEFAULT FALSE,
    p_read_filter TEXT DEFAULT 'all',
    p_marketcap TEXT[] DEFAULT NULL,
    p_include_duplicates BOOLEAN DEFAULT FALSE,
    p_page INTEGER DEFAULT 1,
    p_page_size INTEGER DEFAULT 15
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_offset INTEGER;
    v_total_count BIGINT;
    v_total_pages INTEGER;
    v_filings JSONB;
    v_start_iso TEXT;
    v_end_iso TEXT;
    v_effective_page_size INTEGER;
BEGIN
    v_effective_page_size := LEAST(GREATEST(p_page_size, 1), 100);
    v_offset := (GREATEST(p_page, 1) - 1) * v_effective_page_size;

    -- Build ISO date strings (cf.date is TEXT in ISO 8601 format)
    IF p_start_date IS NOT NULL AND p_start_date != '' THEN
        v_start_iso := p_start_date || 'T00:00:00';
    END IF;
    IF p_end_date IS NOT NULL AND p_end_date != '' THEN
        v_end_iso := p_end_date || 'T23:59:59';
    END IF;

    -- Count matching filings
    -- NOTE: urf.corp_id is TEXT, cf.corp_id is UUID → cast with ::text
    -- NOTE: w.userid is UUID, p_user_id is TEXT → cast with ::uuid
    SELECT COUNT(*)
    INTO v_total_count
    FROM corporatefilings cf
    LEFT JOIN user_read_filings urf
        ON urf.corp_id = cf.corp_id::text AND urf.user_id = p_user_id
    WHERE
        (v_start_iso IS NULL OR cf.date >= v_start_iso)
        AND (v_end_iso IS NULL OR cf.date <= v_end_iso)
        AND (p_categories IS NULL OR cf.category = ANY(p_categories))
        AND (p_categories IS NOT NULL OR cf.category IS DISTINCT FROM 'Procedural/Administrative')
        AND cf.category IS DISTINCT FROM 'Error'
        AND (p_symbols IS NULL OR cf.symbol = ANY(p_symbols))
        AND (p_isins IS NULL OR cf.isin = ANY(p_isins))
        AND (
            NOT p_watchlist_only
            OR cf.isin IN (
                SELECT DISTINCT w.isin
                FROM watchlistdata w
                WHERE w.userid = p_user_id::uuid AND w.isin IS NOT NULL
            )
        )
        AND (
            p_marketcap IS NULL
            OR cf.isin IN (
                SELECT s.isin FROM stocklistdata s
                WHERE
                    ('large' = ANY(p_marketcap) AND s.market_cap > 20000)
                    OR ('mid' = ANY(p_marketcap) AND s.market_cap >= 5000 AND s.market_cap <= 20000)
                    OR ('small' = ANY(p_marketcap) AND s.market_cap >= 500 AND s.market_cap < 5000)
                    OR ('micro' = ANY(p_marketcap) AND s.market_cap >= 100 AND s.market_cap < 500)
                    OR ('nano' = ANY(p_marketcap) AND s.market_cap < 100)
            )
        )
        AND (p_include_duplicates OR cf.is_duplicate IS NOT TRUE)
        AND (
            p_read_filter = 'all'
            OR (p_read_filter = 'read' AND urf.corp_id IS NOT NULL)
            OR (p_read_filter = 'unread' AND urf.corp_id IS NULL)
        );

    v_total_pages := GREATEST(1, CEIL(v_total_count::FLOAT / v_effective_page_size)::INTEGER);

    -- Fetch paginated filings with investorCorp
    SELECT COALESCE(jsonb_agg(filing ORDER BY (filing->>'date') DESC), '[]'::jsonb)
    INTO v_filings
    FROM (
        SELECT jsonb_build_object(
            'corp_id', cf.corp_id,
            'securityid', cf.securityid,
            'summary', cf.summary,
            'fileurl', cf.fileurl,
            'date', cf.date,
            'ai_summary', cf.ai_summary,
            'category', cf.category,
            'isin', cf.isin,
            'companyname', cf.companyname,
            'symbol', cf.symbol,
            'headline', cf.headline,
            'sentiment', cf.sentiment,
            'verified', cf.verified,
            'is_read', CASE WHEN urf.corp_id IS NOT NULL THEN true ELSE false END,
            'investorCorp', COALESCE(
                (
                    SELECT jsonb_agg(jsonb_build_object(
                        'id', ic.id,
                        'investor_id', ic.investor_id,
                        'investor_name', ic.investor_name,
                        'aliasBool', ic."aliasBool",
                        'aliasName', ic."aliasName",
                        'verified', ic.verified,
                        'type', ic.type,
                        'alias_id', ic.alias_id
                    ))
                    FROM "investorCorp" ic
                    WHERE ic.corp_id = cf.corp_id
                ),
                '[]'::jsonb
            )
        ) AS filing
        FROM corporatefilings cf
        LEFT JOIN user_read_filings urf
            ON urf.corp_id = cf.corp_id::text AND urf.user_id = p_user_id
        WHERE
            (v_start_iso IS NULL OR cf.date >= v_start_iso)
            AND (v_end_iso IS NULL OR cf.date <= v_end_iso)
            AND (p_categories IS NULL OR cf.category = ANY(p_categories))
            AND (p_categories IS NOT NULL OR cf.category IS DISTINCT FROM 'Procedural/Administrative')
            AND cf.category IS DISTINCT FROM 'Error'
            AND (p_symbols IS NULL OR cf.symbol = ANY(p_symbols))
            AND (p_isins IS NULL OR cf.isin = ANY(p_isins))
            AND (
                NOT p_watchlist_only
                OR cf.isin IN (
                    SELECT DISTINCT w.isin
                    FROM watchlistdata w
                    WHERE w.userid = p_user_id::uuid AND w.isin IS NOT NULL
                )
            )
            AND (
                p_marketcap IS NULL
                OR cf.isin IN (
                    SELECT s.isin FROM stocklistdata s
                    WHERE
                        ('large' = ANY(p_marketcap) AND s.market_cap > 20000)
                        OR ('mid' = ANY(p_marketcap) AND s.market_cap >= 5000 AND s.market_cap <= 20000)
                        OR ('small' = ANY(p_marketcap) AND s.market_cap >= 500 AND s.market_cap < 5000)
                        OR ('micro' = ANY(p_marketcap) AND s.market_cap >= 100 AND s.market_cap < 500)
                        OR ('nano' = ANY(p_marketcap) AND s.market_cap < 100)
                )
            )
            AND (p_include_duplicates OR cf.is_duplicate IS NOT TRUE)
            AND (
                p_read_filter = 'all'
                OR (p_read_filter = 'read' AND urf.corp_id IS NOT NULL)
                OR (p_read_filter = 'unread' AND urf.corp_id IS NULL)
            )
        ORDER BY cf.date DESC
        LIMIT v_effective_page_size
        OFFSET v_offset
    ) sub;

    RETURN jsonb_build_object(
        'filings', v_filings,
        'total_count', v_total_count,
        'total_pages', v_total_pages,
        'current_page', GREATEST(p_page, 1),
        'page_size', v_effective_page_size,
        'has_next', GREATEST(p_page, 1) < v_total_pages,
        'has_previous', GREATEST(p_page, 1) > 1,
        'count', jsonb_array_length(v_filings)
    );
END;
$$;
