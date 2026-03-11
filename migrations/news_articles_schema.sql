-- Migration: News Articles System
-- Creates the news_articles table and supporting indexes.
-- Run this in the Supabase SQL Editor.

-- ============================================================
-- 1. news_articles table
-- ============================================================
CREATE TABLE IF NOT EXISTS news_articles (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Link back to the source filing
    corp_id       UUID NOT NULL REFERENCES corporatefilings(corp_id),
    -- Company info (denormalized for fast queries / joins-free reads)
    company_id    UUID,
    isin          TEXT,
    symbol        TEXT,
    companyname   TEXT,
    sector        TEXT,
    -- Article content
    headline      TEXT NOT NULL,
    slug          TEXT NOT NULL UNIQUE,
    seo_description TEXT,
    body          TEXT NOT NULL,
    sentiment     TEXT CHECK (sentiment IN ('Positive','Negative','Neutral','Mixed')),
    tags          TEXT[],              -- Postgres array of tags
    key_figures   TEXT,
    -- Classification
    category      TEXT NOT NULL,       -- filing category (Financial Results, etc.)
    article_category TEXT,             -- article display category (Earnings & Results, etc.)
    -- Metadata
    filing_date   TIMESTAMPTZ,         -- date of the original filing
    published_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW(),
    -- Status
    status        TEXT NOT NULL DEFAULT 'published' CHECK (status IN ('draft','published','archived')),
    -- Source
    source_url    TEXT,                -- original PDF / filing URL
    -- Engagement (updated async)
    view_count    INTEGER DEFAULT 0
);

-- ============================================================
-- 2. Indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_na_corp_id      ON news_articles(corp_id);
CREATE INDEX IF NOT EXISTS idx_na_slug         ON news_articles(slug);
CREATE INDEX IF NOT EXISTS idx_na_isin         ON news_articles(isin);
CREATE INDEX IF NOT EXISTS idx_na_symbol       ON news_articles(symbol);
CREATE INDEX IF NOT EXISTS idx_na_category     ON news_articles(category);
CREATE INDEX IF NOT EXISTS idx_na_article_cat  ON news_articles(article_category);
CREATE INDEX IF NOT EXISTS idx_na_status       ON news_articles(status);
CREATE INDEX IF NOT EXISTS idx_na_published_at ON news_articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_na_filing_date  ON news_articles(filing_date DESC);
CREATE INDEX IF NOT EXISTS idx_na_sentiment    ON news_articles(sentiment);
CREATE INDEX IF NOT EXISTS idx_na_company_id   ON news_articles(company_id);
CREATE INDEX IF NOT EXISTS idx_na_tags         ON news_articles USING GIN(tags);

-- ============================================================
-- 3. RLS — allow service role full access
-- ============================================================
ALTER TABLE news_articles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access on news_articles"
    ON news_articles FOR ALL USING (true) WITH CHECK (true);

-- ============================================================
-- 5. Updated_at trigger
-- ============================================================
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_news_articles_updated ON news_articles;
CREATE TRIGGER trg_news_articles_updated
    BEFORE UPDATE ON news_articles
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();
