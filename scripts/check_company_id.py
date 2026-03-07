#!/usr/bin/env python3
"""Quick check of company_id usage in corporatefilings"""
from dotenv import load_dotenv
import os
load_dotenv()
from supabase import create_client
supabase = create_client(os.getenv('SUPABASE_URL2'), os.getenv('SUPABASE_SERVICE_ROLE_KEY'))

# Check how company_id is used in corporatefilings
result = supabase.table('corporatefilings').select('corp_id, isin, symbol, companyname, company_id').not_.is_('company_id', 'null').limit(5).execute()
print('Filings with company_id:')
for r in result.data:
    print(f"  corp={r['corp_id'][:8]}... isin={r.get('isin')} symbol={r.get('symbol')} company_id={r.get('company_id')}")

# Check recent filings (last month) for company_id usage - avoids timeout on 200k rows
result2 = supabase.table('corporatefilings').select('company_id', count='exact').not_.is_('company_id', 'null').gte('date', '2026-02-01').execute()
print(f'\nRecent filings (Feb 2026+) with company_id: {result2.count}')

result3 = supabase.table('corporatefilings').select('company_id', count='exact').is_('company_id', 'null').gte('date', '2026-02-01').execute()
print(f'Recent filings (Feb 2026+) without company_id: {result3.count}')

# Check stocklistdata company_id
result5 = supabase.table('stocklistdata').select('company_id', count='exact').not_.is_('company_id', 'null').execute()
print(f'\nstocklistdata records with company_id: {result5.count}')

# Check a sample company_id and see if it links
sample = supabase.table('stocklistdata').select('isin, company_id, symbol, newname').eq('symbol', 'RELIANCE').execute()
if sample.data:
    print(f'\nRELIANCE in stocklistdata: {sample.data[0]}')
    cid = sample.data[0]['company_id']
    filings = supabase.table('corporatefilings').select('corp_id, isin, companyname', count='exact').eq('company_id', cid).execute()
    print(f'Filings linked to RELIANCE company_id: {filings.count}')
