#!/usr/bin/env python3
"""Run SQL migration to add market_cap column to stocklistdata"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

url = os.getenv('SUPABASE_URL2')
key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

headers = {
    'apikey': key,
    'Authorization': f'Bearer {key}',
    'Content-Type': 'application/json',
    'Prefer': 'return=representation'
}

# Use Supabase's SQL query endpoint (management API)
# The pg-meta / SQL editor endpoint
project_ref = url.split('//')[1].split('.')[0]  # Extract project ref from URL

print(f"Project ref: {project_ref}")
print(f"Supabase URL: {url}")

# Try using the SQL endpoint via management API
# Supabase projects expose a /pg/ endpoint for direct SQL in some configurations
# But safest is to just create a temporary RPC function

# Alternative: Use the REST API to check if column exists by trying to query it
try:
    resp = requests.get(
        f'{url}/rest/v1/stocklistdata?select=market_cap&limit=1',
        headers=headers
    )
    if resp.status_code == 200:
        print("market_cap column already exists!")
    else:
        print(f"Column check response: {resp.status_code} - {resp.text[:200]}")
        print("\n" + "="*60)
        print("MANUAL ACTION REQUIRED:")
        print("="*60)
        print("Please run this SQL in the Supabase SQL Editor:")
        print()
        print("ALTER TABLE public.stocklistdata ADD COLUMN IF NOT EXISTS market_cap numeric;")
        print("CREATE INDEX IF NOT EXISTS idx_stocklistdata_market_cap ON public.stocklistdata(market_cap);")
        print("CREATE INDEX IF NOT EXISTS idx_stocklistdata_sector ON public.stocklistdata(sector);")
        print()
        print("Then re-run the backfill script:")
        print("  python3 scripts/backfill_sector_marketcap.py")
except Exception as e:
    print(f"Error: {e}")
