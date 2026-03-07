-- Migration: Add market_cap column to stocklistdata
-- Date: 2026-03-07
-- Purpose: Store market capitalization (in crores) for each company

-- Add market_cap column (numeric, in crores)
ALTER TABLE public.stocklistdata ADD COLUMN IF NOT EXISTS market_cap numeric;

-- Add index for market_cap filtering (enables efficient cap-based queries)
CREATE INDEX IF NOT EXISTS idx_stocklistdata_market_cap ON public.stocklistdata(market_cap);

-- Add index for sector filtering
CREATE INDEX IF NOT EXISTS idx_stocklistdata_sector ON public.stocklistdata(sector);

-- Also add these to the testtable and testtablenew if they exist
ALTER TABLE public.testtable ADD COLUMN IF NOT EXISTS market_cap numeric;
ALTER TABLE public.testtablenew ADD COLUMN IF NOT EXISTS market_cap numeric;

COMMENT ON COLUMN public.stocklistdata.market_cap IS 'Market capitalization in crores (INR). Source: external market data provider.';
COMMENT ON COLUMN public.stocklistdata.sector IS 'Industry sector name. Source: external market data provider.';
