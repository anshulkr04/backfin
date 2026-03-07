#!/usr/bin/env python3
"""
Company Change Detection and Auto-Application

Fully automated version that:
1. Downloads NSE/BSE instrument data from Dhan API
2. Fetches current stocklistdata from Supabase
3. Generates merged stocklist (combining NSE + BSE data)
4. Compares and detects changes
5. Auto-applies changes (no manual verification needed)
6. Records ISIN changes in isin_history
7. Cascades ISIN changes to corporatefilings (Nov 2025+)
8. Automatic cleanup of temporary files

Usage:
    python3 auto_apply_changes.py                 # Standard run
    python3 auto_apply_changes.py --dry-run       # Preview only
    python3 auto_apply_changes.py --stats-only    # Show stats only
    python3 auto_apply_changes.py --keep-files    # Keep temp CSV files

Cron:
    0 6 * * * cd /path/to/company_management && python3 auto_apply_changes.py >> /var/log/company_changes.log 2>&1
"""

import pandas as pd
import numpy as np
import sys
import os
import logging
import requests
from io import StringIO
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime

# Load environment
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL2")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# File paths for temporary data
NSE_FILE = "NSE_EQ_instruments.csv"
BSE_FILE = "BSE_EQ_instruments.csv"
CURRENT_DATA_FILE = "current_stocklistdata.csv"
NEW_DATA_FILE = "new_stocklistdata.csv"


# =============================================================================
# STEP 1: Download Exchange Data from Dhan API
# =============================================================================

def download_exchange_data(exchange_segment: str, output_file: str) -> bool:
    """Download instrument data from Dhan API"""
    url = f'https://api.dhan.co/v2/instrument/{exchange_segment}'
    logging.info(f"Downloading {exchange_segment} data from Dhan API...")
    
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            df = pd.read_csv(StringIO(response.text), header=None)
            df.to_csv(output_file, index=False)
            logging.info(f"  Downloaded {len(df)} records to {output_file}")
            return True
        else:
            logging.error(f"  Failed to download {exchange_segment}: {response.status_code}")
            return False
    except Exception as e:
        logging.error(f"  Error downloading {exchange_segment}: {str(e)}")
        return False


def download_all_exchange_data() -> bool:
    """Download both NSE and BSE data"""
    logging.info("STEP 1: Downloading exchange data...")
    nse_success = download_exchange_data('NSE_EQ', NSE_FILE)
    bse_success = download_exchange_data('BSE_EQ', BSE_FILE)
    
    if not (nse_success and bse_success):
        logging.error("Failed to download exchange data")
        return False
    
    logging.info("  All exchange data downloaded\n")
    return True


# =============================================================================
# STEP 2: Fetch Current Stocklistdata
# =============================================================================

def fetch_current_stocklistdata(supabase) -> pd.DataFrame:
    """Fetch all current stocklistdata from Supabase"""
    logging.info("STEP 2: Fetching current stocklistdata...")
    
    try:
        all_rows = []
        batch_size = 1000
        start = 0
        
        while True:
            end = start + batch_size - 1
            resp = supabase.table('stocklistdata').select("*").range(start, end).execute()
            rows = resp.data if hasattr(resp, "data") else []
            if not rows:
                break
            all_rows.extend(rows)
            start += batch_size
            if len(rows) < batch_size:
                break
        
        df = pd.DataFrame(all_rows)
        logging.info(f"  Fetched {len(df)} records from stocklistdata\n")
        df.to_csv(CURRENT_DATA_FILE, index=False)
        return df
    except Exception as e:
        logging.error(f"  Error fetching stocklistdata: {str(e)}")
        return pd.DataFrame()


# =============================================================================
# STEP 3: Process and Merge Exchange Data
# =============================================================================

def process_nse_data(nse_file_path: str) -> pd.DataFrame:
    """Process NSE CSV file"""
    logging.info("  Processing NSE data...")
    try:
        df = pd.read_csv(nse_file_path, skiprows=1)
        required_columns = ['ISIN', 'INSTRUMENT_TYPE', 'UNDERLYING_SYMBOL', 'DISPLAY_NAME', 'SECURITY_ID']
        if not all(col in df.columns for col in required_columns):
            logging.error(f"Missing required NSE columns")
            return pd.DataFrame()
        
        filtered_df = df[
            ((df['ISIN'].str.startswith('INE')) & (df['INSTRUMENT_TYPE'] == 'ES')) |
            ((df['ISIN'].str.startswith('INE')) & (df['INSTRUMENT_TYPE'] == 'Other') & (df['SERIES'] == 'EQ'))
        ]
        
        nse_processed = pd.DataFrame({
            'isin': filtered_df['ISIN'],
            'securityid': filtered_df['SECURITY_ID'],
            'newnsecode': filtered_df['UNDERLYING_SYMBOL'],
            'newname': filtered_df['DISPLAY_NAME'],
            'data_source': 'NSE'
        })
        logging.info(f"    {len(nse_processed)} NSE records")
        return nse_processed
    except Exception as e:
        logging.error(f"Error processing NSE data: {str(e)}")
        return pd.DataFrame()


def process_bse_data(bse_file_path: str) -> pd.DataFrame:
    """Process BSE CSV file"""
    logging.info("  Processing BSE data...")
    try:
        df = pd.read_csv(bse_file_path, skiprows=1)
        required_columns = ['ISIN', 'INSTRUMENT_TYPE', 'UNDERLYING_SYMBOL', 'DISPLAY_NAME', 'SECURITY_ID']
        if not all(col in df.columns for col in required_columns):
            logging.error(f"Missing required BSE columns")
            return pd.DataFrame()
        
        filtered_df = df[
            (df['ISIN'].str.startswith('INE')) & (df['INSTRUMENT_TYPE'] == 'ES')
        ]
        
        bse_processed = pd.DataFrame({
            'isin': filtered_df['ISIN'],
            'securityid': filtered_df['SECURITY_ID'],
            'newbsecode': filtered_df['UNDERLYING_SYMBOL'],
            'newname': filtered_df['DISPLAY_NAME'],
            'data_source': 'BSE'
        })
        logging.info(f"    {len(bse_processed)} BSE records")
        return bse_processed
    except Exception as e:
        logging.error(f"Error processing BSE data: {str(e)}")
        return pd.DataFrame()


def merge_exchange_data(nse_df: pd.DataFrame, bse_df: pd.DataFrame) -> pd.DataFrame:
    """Merge NSE and BSE dataframes on ISIN"""
    logging.info("  Merging NSE and BSE data...")
    
    merged_df = nse_df.merge(bse_df, on='isin', how='outer', suffixes=('_nse', '_bse'))
    
    final_df = pd.DataFrame()
    final_df['isin'] = merged_df['isin']
    final_df['securityid'] = merged_df['securityid_bse'].fillna(merged_df['securityid_nse'])
    final_df['newbsecode'] = merged_df['newbsecode']
    final_df['newnsecode'] = merged_df['newnsecode']
    final_df['newname'] = merged_df['newname_nse'].fillna(merged_df['newname_bse'])
    final_df['symbol'] = final_df['newbsecode'].fillna(final_df['newnsecode'])
    final_df['sector'] = None
    
    final_df = final_df.dropna(subset=['newbsecode', 'newnsecode'], how='all')
    final_df['securityid'] = pd.to_numeric(final_df['securityid'], errors='coerce').astype('Int64')
    final_df = final_df.drop_duplicates(subset=['isin'])
    final_df['newname'] = final_df['newname'].str.strip().str.replace(r'\s+', ' ', regex=True)
    
    valid_isin_mask = final_df['isin'].str.match(r'^INE[A-Z0-9]{9}$')
    final_df = final_df[valid_isin_mask]
    
    logging.info(f"  Merged: {len(final_df)} records (NSE: {final_df['newnsecode'].notna().sum()}, BSE: {final_df['newbsecode'].notna().sum()})\n")
    return final_df


def generate_new_stocklist() -> bool:
    """Generate new stocklist from downloaded exchange data"""
    logging.info("STEP 3: Generating new stocklist...")
    try:
        nse_df = process_nse_data(NSE_FILE)
        if nse_df.empty:
            return False
        bse_df = process_bse_data(BSE_FILE)
        if bse_df.empty:
            return False
        
        final_df = merge_exchange_data(nse_df, bse_df)
        final_df = final_df.sort_values('isin')
        final_df.to_csv(NEW_DATA_FILE, index=False)
        return True
    except Exception as e:
        logging.error(f"Error generating stocklist: {str(e)}")
        return False


# =============================================================================
# STEP 4: Compare and Detect Changes
# =============================================================================

def clean_string(value):
    if pd.isna(value) or value == '':
        return ''
    return str(value).strip().upper()


def clean_exchange_value(value):
    if pd.isna(value) or value == '':
        return ''
    return str(value).strip().replace('$', '')


def detect_field_changes(existing_row, new_row) -> Tuple[str, Dict, Dict]:
    """Detect what fields have changed between two rows"""
    changes = []
    updated_values = {}
    old_values = {}
    
    fields_to_compare = {
        'isin': 'isin', 'securityid': 'securityid', 'symbol': 'symbol',
        'newname': 'name', 'newbsecode': 'bsecode', 'newnsecode': 'nsecode'
    }
    old_field_mapping = {
        'isin': 'oldisin', 'securityid': 'oldsecurityid', 'symbol': 'oldsymbol',
        'newname': 'oldname', 'newbsecode': 'oldbsecode', 'newnsecode': 'oldnsecode'
    }
    exchange_fields = {'symbol', 'newbsecode', 'newnsecode'}
    
    for field, change_type in fields_to_compare.items():
        if field in existing_row and field in new_row:
            if field in exchange_fields:
                existing_val = clean_string(clean_exchange_value(existing_row[field]))
                new_val = clean_string(clean_exchange_value(new_row[field]))
                cleaned_new_value = clean_exchange_value(new_row[field])
            else:
                existing_val = clean_string(existing_row[field])
                new_val = clean_string(new_row[field])
                cleaned_new_value = new_row[field]
            
            if existing_val != new_val:
                changes.append(change_type)
                updated_values[field] = cleaned_new_value
                old_field = old_field_mapping[field]
                old_values[old_field] = existing_row[field]
    
    if not changes:
        return 'no_change', updated_values, old_values
    elif len(changes) == 1:
        return changes[0], updated_values, old_values
    else:
        return ','.join(sorted(changes)), updated_values, old_values


def find_company_by_alternative_matching(target_row, df, used_indices) -> Optional[int]:
    """Try to find a company using alternative matching criteria"""
    target_symbol = clean_string(clean_exchange_value(target_row.get('symbol', '')))
    target_name = clean_string(target_row.get('newname', ''))
    target_securityid = clean_string(target_row.get('securityid', ''))
    target_bsecode = clean_string(clean_exchange_value(target_row.get('newbsecode', '')))
    target_nsecode = clean_string(clean_exchange_value(target_row.get('newnsecode', '')))
    
    if not target_symbol and not target_name and not target_securityid:
        return None
    
    for idx, row in df.iterrows():
        if idx in used_indices:
            continue
        
        row_symbol = clean_string(clean_exchange_value(row.get('symbol', '')))
        row_name = clean_string(row.get('newname', ''))
        row_securityid = clean_string(row.get('securityid', ''))
        row_bsecode = clean_string(clean_exchange_value(row.get('newbsecode', '')))
        row_nsecode = clean_string(clean_exchange_value(row.get('newnsecode', '')))
        
        matches = 0
        total_checks = 0
        
        for t, r in [(target_symbol, row_symbol), (target_name, row_name), 
                      (target_securityid, row_securityid), (target_bsecode, row_bsecode),
                      (target_nsecode, row_nsecode)]:
            if t and r:
                total_checks += 1
                if t == r:
                    matches += 1
        
        if total_checks >= 2 and matches >= 2:
            return idx
        
        if (target_symbol == row_symbol and target_securityid == row_securityid 
            and target_symbol and target_securityid):
            return idx
    
    return None


def compare_stockdata(existing_df: pd.DataFrame, new_df: pd.DataFrame) -> pd.DataFrame:
    """Compare existing and new stocklistdata"""
    logging.info("STEP 4: Comparing and detecting changes...")
    
    results = []
    used_new_indices = set()
    
    # Phase 1: ISIN-based exact matching
    exact_matches = 0
    changes_detected = 0
    
    for idx, existing_row in existing_df.iterrows():
        existing_isin = clean_string(existing_row.get('isin', ''))
        if not existing_isin:
            continue
        
        new_matches = new_df[new_df['isin'].apply(clean_string) == existing_isin]
        
        if len(new_matches) > 0:
            exact_matches += 1
            new_row = new_matches.iloc[0]
            used_new_indices.add(new_matches.index[0])
            
            change_type, updated_values, old_values = detect_field_changes(existing_row, new_row)
            if change_type != 'no_change':
                changes_detected += 1
            
            result_row = existing_row.to_dict()
            result_row['change'] = change_type
            for field, new_value in updated_values.items():
                result_row[field] = new_value
            for old_field, old_value in old_values.items():
                result_row[old_field] = old_value
            results.append(result_row)
    
    logging.info(f"  Phase 1 (ISIN match): {exact_matches} matches, {changes_detected} changes")
    
    # Phase 2: Alternative matching for ISIN changes
    isin_changes_detected = 0
    
    for idx, existing_row in existing_df.iterrows():
        existing_isin = clean_string(existing_row.get('isin', ''))
        if existing_isin:
            new_matches = new_df[new_df['isin'].apply(clean_string) == existing_isin]
            if len(new_matches) > 0:
                continue
        
        match_idx = find_company_by_alternative_matching(existing_row, new_df, used_new_indices)
        
        if match_idx is not None:
            isin_changes_detected += 1
            new_row = new_df.iloc[match_idx]
            used_new_indices.add(match_idx)
            
            result_row = existing_row.to_dict()
            result_row['change'] = 'isin'
            result_row['oldisin'] = existing_row['isin']
            result_row['isin'] = new_row['isin']
            
            change_type, updated_values, old_values = detect_field_changes(existing_row, new_row)
            if change_type != 'no_change':
                other_changes = change_type.split(',') if ',' in change_type else [change_type]
                all_changes = ['isin'] + other_changes
                result_row['change'] = ','.join(sorted(all_changes))
                for field, new_value in updated_values.items():
                    result_row[field] = new_value
                for old_field, old_value in old_values.items():
                    result_row[old_field] = old_value
            
            results.append(result_row)
    
    logging.info(f"  Phase 2 (alt match): {isin_changes_detected} ISIN changes")
    
    # Phase 3: New companies
    new_companies = 0
    for idx, new_row in new_df.iterrows():
        if idx not in used_new_indices:
            new_companies += 1
            result_row = {
                'isin': new_row['isin'],
                'securityid': new_row['securityid'],
                'newbsecode': clean_exchange_value(new_row.get('newbsecode', '')),
                'newnsecode': clean_exchange_value(new_row.get('newnsecode', '')),
                'newname': new_row.get('newname', ''),
                'symbol': clean_exchange_value(new_row['symbol']),
                'company_id': '',
                'sector': new_row.get('sector', ''),
                'change': 'new'
            }
            results.append(result_row)
    
    logging.info(f"  Phase 3 (new companies): {new_companies}")
    
    results_df = pd.DataFrame(results)
    changes_only_df = results_df[results_df['change'] != 'no_change'].copy()
    
    logging.info(f"  Summary: {len(changes_only_df)} total changes\n")
    
    if len(changes_only_df) > 0:
        change_breakdown = changes_only_df['change'].value_counts()
        for change_type, count in change_breakdown.head(10).items():
            logging.info(f"    {change_type}: {count}")
        logging.info("")
    
    return changes_only_df


# =============================================================================
# STEP 5: Auto-Apply Changes
# =============================================================================

def auto_apply_change_directly(supabase, change_record: Dict) -> Tuple[bool, str]:
    """
    Auto-apply a single change directly to the database.
    No verification queue needed.
    """
    change_type = change_record['change_type']
    isin = change_record.get('isin') or change_record.get('new_isin')
    
    try:
        if change_type == 'new':
            # New company: insert into stocklistdata
            insert_data = {
                'isin': change_record.get('new_isin'),
                'securityid': change_record.get('new_securityid'),
                'newbsecode': change_record.get('new_bsecode'),
                'newnsecode': change_record.get('new_nsecode'),
                'newname': change_record.get('new_name'),
                'symbol': change_record.get('new_symbol'),
                'sector': change_record.get('new_sector')
            }
            # Remove None values
            insert_data = {k: v for k, v in insert_data.items() if v is not None}
            
            try:
                supabase.table('stocklistdata').insert(insert_data).execute()
                return True, f"New company: {change_record.get('new_name', 'N/A')}"
            except Exception as e:
                if 'duplicate key' in str(e).lower() or '23505' in str(e):
                    return True, f"Already exists: {isin}"
                raise
        
        elif 'isin' in change_type:
            # ISIN change
            old_isin = change_record.get('old_isin')
            new_isin = change_record.get('new_isin')
            
            if not old_isin or not new_isin:
                return False, f"Missing old_isin or new_isin"
            
            # Get company_id from stocklistdata
            result = supabase.table('stocklistdata').select('company_id').eq('isin', old_isin).execute()
            company_id = result.data[0]['company_id'] if result.data else None
            
            if company_id:
                # Record in isin_history
                try:
                    supabase.table('isin_history').insert({
                        'company_id': company_id,
                        'old_isin': old_isin,
                        'new_isin': new_isin,
                        'source': 'auto_apply_changes'
                    }).execute()
                except Exception:
                    pass  # Non-critical, continue
                
                # Update stocklistdata
                update_data = {'isin': new_isin}
                if change_record.get('new_securityid'):
                    update_data['securityid'] = change_record['new_securityid']
                if change_record.get('new_bsecode'):
                    update_data['newbsecode'] = change_record['new_bsecode']
                if change_record.get('new_nsecode'):
                    update_data['newnsecode'] = change_record['new_nsecode']
                if change_record.get('new_name'):
                    update_data['newname'] = change_record['new_name']
                if change_record.get('new_symbol'):
                    update_data['symbol'] = change_record['new_symbol']
                
                supabase.table('stocklistdata').update(update_data).eq('company_id', company_id).execute()
                
                # Update recent corporatefilings (Nov 2025+)
                try:
                    supabase.table('corporatefilings').update({
                        'isin': new_isin,
                        'company_id': company_id
                    }).eq('isin', old_isin).gte('date', '2025-11-01').execute()
                except Exception:
                    pass  # Non-critical
                
                # Set company_id on filings that have the new ISIN but no company_id
                try:
                    supabase.table('corporatefilings').update({
                        'company_id': company_id
                    }).eq('isin', new_isin).is_('company_id', 'null').gte('date', '2025-11-01').execute()
                except Exception:
                    pass  # Non-critical
                
                return True, f"ISIN change: {old_isin} → {new_isin}"
            else:
                return False, f"Company not found for old ISIN: {old_isin}"
        
        else:
            # Other changes (name, bsecode, nsecode, etc.)
            update_data = {}
            if change_record.get('new_securityid'):
                update_data['securityid'] = change_record['new_securityid']
            if change_record.get('new_bsecode'):
                update_data['newbsecode'] = change_record['new_bsecode']
            if change_record.get('new_nsecode'):
                update_data['newnsecode'] = change_record['new_nsecode']
            if change_record.get('new_name'):
                update_data['newname'] = change_record['new_name']
            if change_record.get('new_symbol'):
                update_data['symbol'] = change_record['new_symbol']
            
            if update_data:
                supabase.table('stocklistdata').update(update_data).eq('isin', isin).execute()
            
            return True, f"{change_type}: {change_record.get('new_name', isin)}"
    
    except Exception as e:
        return False, str(e)


def map_change_to_record(change_row: pd.Series) -> Dict:
    """Map detected changes to a structured record"""
    change_types = [c.strip() for c in change_row['change'].split(',') if c.strip() and c.strip() != 'no_change']
    
    if 'new' in change_types:
        primary_change_type = 'new'
    elif 'isin' in change_types:
        primary_change_type = 'isin'
    elif 'name' in change_types:
        primary_change_type = 'name'
    elif 'bsecode' in change_types:
        primary_change_type = 'bsecode'
    elif 'nsecode' in change_types:
        primary_change_type = 'nsecode'
    elif 'symbol' in change_types:
        primary_change_type = 'symbol'
    elif len(change_types) > 1:
        primary_change_type = 'multiple'
    elif len(change_types) == 1:
        primary_change_type = change_types[0]
    else:
        primary_change_type = 'multiple'
    
    def clean_str(val):
        if pd.isna(val) or val == '':
            return None
        return str(val).strip()
    
    def clean_int(val):
        if pd.isna(val):
            return None
        try:
            return int(val)
        except:
            return None
    
    return {
        'isin': clean_str(change_row.get('isin', '')),
        'change_type': primary_change_type,
        'new_isin': clean_str(change_row.get('isin', '')),
        'new_securityid': clean_int(change_row.get('securityid')),
        'new_bsecode': clean_str(change_row.get('newbsecode', '')),
        'new_nsecode': clean_str(change_row.get('newnsecode', '')),
        'new_name': clean_str(change_row.get('newname', '')),
        'new_sector': clean_str(change_row.get('sector', '')),
        'new_symbol': clean_str(change_row.get('symbol', '')),
        'old_isin': clean_str(change_row.get('oldisin')) if pd.notna(change_row.get('oldisin')) else None,
        'old_securityid': clean_int(change_row.get('oldsecurityid')) if pd.notna(change_row.get('oldsecurityid')) else None,
        'old_bsecode': clean_str(change_row.get('oldbsecode')) if pd.notna(change_row.get('oldbsecode')) else None,
        'old_nsecode': clean_str(change_row.get('oldnsecode')) if pd.notna(change_row.get('oldnsecode')) else None,
        'old_name': clean_str(change_row.get('oldname')) if pd.notna(change_row.get('oldname')) else None,
        'old_symbol': clean_str(change_row.get('oldsymbol')) if pd.notna(change_row.get('oldsymbol')) else None,
        'company_id': change_row.get('company_id') if pd.notna(change_row.get('company_id')) and change_row.get('company_id') != '' else None,
    }


def auto_apply_all_changes(changes_df: pd.DataFrame, supabase, dry_run: bool = False) -> Dict:
    """Auto-apply all detected changes"""
    logging.info("STEP 5: Auto-applying changes...")
    
    stats = {
        'total': len(changes_df),
        'applied': 0,
        'skipped': 0,
        'errors': 0,
        'by_type': {},
        'error_details': []
    }
    
    for idx, row in changes_df.iterrows():
        change_record = map_change_to_record(row)
        change_type = change_record['change_type']
        
        if dry_run:
            stats['applied'] += 1
            stats['by_type'][change_type] = stats['by_type'].get(change_type, 0) + 1
            if stats['applied'] <= 15:
                logging.info(f"  [DRY RUN] Would apply: {change_type} - {change_record.get('new_name', change_record.get('isin', 'N/A'))}")
            continue
        
        success, message = auto_apply_change_directly(supabase, change_record)
        
        if success:
            stats['applied'] += 1
            stats['by_type'][change_type] = stats['by_type'].get(change_type, 0) + 1
            
            if stats['applied'] <= 20 or stats['applied'] % 100 == 0:
                logging.info(f"  Applied: {message}")
        else:
            stats['errors'] += 1
            stats['error_details'].append(message)
            if stats['errors'] <= 10:
                logging.error(f"  Error: {message}")
        
        # Also log to company_changes_pending for audit trail
        if not dry_run:
            try:
                audit_record = {
                    'isin': change_record.get('isin'),
                    'change_type': change_type,
                    'new_isin': change_record.get('new_isin'),
                    'new_securityid': change_record.get('new_securityid'),
                    'new_bsecode': change_record.get('new_bsecode'),
                    'new_nsecode': change_record.get('new_nsecode'),
                    'new_name': change_record.get('new_name'),
                    'new_symbol': change_record.get('new_symbol'),
                    'old_isin': change_record.get('old_isin'),
                    'old_name': change_record.get('old_name'),
                    'old_symbol': change_record.get('old_symbol'),
                    'verified': True,
                    'review_status': 'approved',
                    'applied': True,
                    'applied_at': datetime.now().isoformat(),
                    'source_file': 'auto_apply_changes.py',
                    'change_detection_metadata': {
                        'auto_applied': True,
                        'detection_date': datetime.now().isoformat(),
                        'success': success
                    }
                }
                audit_record = {k: v for k, v in audit_record.items() if v is not None}
                supabase.table('company_changes_pending').insert(audit_record).execute()
            except Exception:
                pass  # Audit trail is non-critical
    
    return stats


# =============================================================================
# STEP 6: Cleanup
# =============================================================================

def cleanup_temp_files(keep_files: bool = False):
    if keep_files:
        return
    for f in [NSE_FILE, BSE_FILE, CURRENT_DATA_FILE, NEW_DATA_FILE]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                pass


# =============================================================================
# Main Workflow
# =============================================================================

def detect_and_apply_changes(keep_files: bool = False, dry_run: bool = False):
    """Main workflow: detect changes and auto-apply them"""
    logging.info("=" * 70)
    logging.info("COMPANY CHANGE DETECTION AND AUTO-APPLICATION")
    logging.info(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logging.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    logging.info("=" * 70 + "\n")
    
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        if not download_all_exchange_data():
            return False
        
        existing_df = fetch_current_stocklistdata(supabase)
        if existing_df.empty:
            logging.error("No current stocklistdata found")
            return False
        
        if not generate_new_stocklist():
            return False
        
        new_df = pd.read_csv(NEW_DATA_FILE)
        changes_df = compare_stockdata(existing_df, new_df)
        
        if len(changes_df) == 0:
            logging.info("No changes detected. Database is up to date!")
            cleanup_temp_files(keep_files)
            return True
        
        stats = auto_apply_all_changes(changes_df, supabase, dry_run=dry_run)
        
        # Print summary
        logging.info("\n" + "=" * 70)
        logging.info("SUMMARY")
        logging.info("=" * 70)
        logging.info(f"Total changes:   {stats['total']}")
        logging.info(f"Applied:         {stats['applied']}")
        logging.info(f"Errors:          {stats['errors']}")
        
        if stats['by_type']:
            logging.info(f"\nBy type:")
            for ct, count in sorted(stats['by_type'].items()):
                logging.info(f"  {ct:20s}: {count}")
        
        if dry_run:
            logging.info(f"\nDRY RUN — no changes were made.")
        
        logging.info("=" * 70)
        
        cleanup_temp_files(keep_files)
        return True
    
    except Exception as e:
        logging.error(f"Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import argparse
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    parser = argparse.ArgumentParser(description='Detect and auto-apply company changes')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying')
    parser.add_argument('--keep-files', action='store_true', help='Keep temp CSV files')
    parser.add_argument('--stats-only', action='store_true', help='Show pending changes stats')
    
    args = parser.parse_args()
    
    try:
        if args.stats_only:
            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            result = supabase.table('company_changes_pending').select('change_type, applied', count='exact').eq('applied', False).execute()
            print(f"Pending (unapplied) changes: {result.count}")
            sys.exit(0)
        
        success = detect_and_apply_changes(args.keep_files, args.dry_run)
        sys.exit(0 if success else 1)
    
    except KeyboardInterrupt:
        logging.info("\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        logging.error(f"Fatal error: {str(e)}")
        sys.exit(1)
