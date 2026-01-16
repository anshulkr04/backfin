#!/usr/bin/env python3
"""
Company Change Detection and Verification Workflow - Self-Contained Version

This script is completely self-contained and includes:
1. Downloading NSE/BSE instrument data from Dhan API
2. Fetching current stocklistdata from Supabase
3. Generating merged stocklist (combining NSE + BSE data)
4. Comparing and detecting changes
5. Submitting changes to verification queue
6. Automatic cleanup of temporary files

No dependencies on common folder - everything is in this single file.

Usage:
    # Standard run (downloads fresh data, detects changes, submits)
    python3 detect_changes.py
    
    # Check statistics only
    python3 detect_changes.py --stats-only
    
    # Keep downloaded files (for debugging)
    python3 detect_changes.py --keep-files
    
    # Cronjob example
    0 6 * * * cd /path/to/company_management && python3 detect_changes.py >> /var/log/company_changes.log 2>&1

Exit Codes:
    0 - Success
    1 - Error occurred
    130 - Interrupted by user (Ctrl+C)
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

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL2")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

print(SUPABASE_KEY)
print(SUPABASE_URL)

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
            # Read CSV content
            df = pd.read_csv(StringIO(response.text), header=None)
            df.to_csv(output_file, index=False)
            logging.info(f"✅ Downloaded {len(df)} records to {output_file}")
            return True
        else:
            logging.error(f"❌ Failed to download {exchange_segment}: {response.status_code}")
            return False
            
    except Exception as e:
        logging.error(f"❌ Error downloading {exchange_segment}: {str(e)}")
        return False

def download_all_exchange_data() -> bool:
    """Download both NSE and BSE data"""
    logging.info("=" * 80)
    logging.info("STEP 1: DOWNLOADING EXCHANGE DATA")
    logging.info("=" * 80)
    
    nse_success = download_exchange_data('NSE_EQ', NSE_FILE)
    bse_success = download_exchange_data('BSE_EQ', BSE_FILE)
    
    if not (nse_success and bse_success):
        logging.error("Failed to download exchange data")
        return False
    
    logging.info("✅ All exchange data downloaded successfully\n")
    return True

# =============================================================================
# STEP 2: Fetch Current Stocklistdata from Supabase
# =============================================================================

def fetch_current_stocklistdata(supabase) -> pd.DataFrame:
    """Fetch all current stocklistdata from Supabase"""
    logging.info("=" * 80)
    logging.info("STEP 2: FETCHING CURRENT STOCKLISTDATA")
    logging.info("=" * 80)
    
    try:
        all_rows = []
        batch_size = 1000
        start = 0
        
        while True:
            end = start + batch_size - 1
            resp = supabase.table('stocklistdata').select("*").range(start, end).execute()
            rows = resp.data if hasattr(resp, "data") else resp.get("data", [])
            
            if not rows:
                break
            
            all_rows.extend(rows)
            start += batch_size
            
            if len(rows) < batch_size:
                break
        
        df = pd.DataFrame(all_rows)
        logging.info(f"✅ Fetched {len(df)} records from stocklistdata table")
        
        # Save to CSV for comparison
        df.to_csv(CURRENT_DATA_FILE, index=False)
        logging.info(f"✅ Saved current data to {CURRENT_DATA_FILE}\n")
        
        return df
        
    except Exception as e:
        logging.error(f"❌ Error fetching stocklistdata: {str(e)}")
        return pd.DataFrame()

# =============================================================================
# STEP 3: Process and Merge Exchange Data
# =============================================================================

def process_nse_data(nse_file_path: str) -> pd.DataFrame:
    """Process NSE CSV file and return filtered dataframe"""
    logging.info("Processing NSE data...")
    
    try:
        df = pd.read_csv(nse_file_path, skiprows=1)
        
        required_columns = ['ISIN', 'INSTRUMENT_TYPE', 'UNDERLYING_SYMBOL', 'DISPLAY_NAME', 'SECURITY_ID']
        if not all(col in df.columns for col in required_columns):
            logging.error(f"Missing required NSE columns")
            return pd.DataFrame()
        
        # Filter: ISIN starts with INE and (INSTRUMENT_TYPE is ES OR (INSTRUMENT_TYPE is Other and SERIES is EQ))
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
        
        logging.info(f"  Processed {len(nse_processed)} NSE records")
        return nse_processed
        
    except Exception as e:
        logging.error(f"Error processing NSE data: {str(e)}")
        return pd.DataFrame()

def process_bse_data(bse_file_path: str) -> pd.DataFrame:
    """Process BSE CSV file and return filtered dataframe"""
    logging.info("Processing BSE data...")
    
    try:
        df = pd.read_csv(bse_file_path, skiprows=1)
        
        required_columns = ['ISIN', 'INSTRUMENT_TYPE', 'UNDERLYING_SYMBOL', 'DISPLAY_NAME', 'SECURITY_ID']
        if not all(col in df.columns for col in required_columns):
            logging.error(f"Missing required BSE columns")
            return pd.DataFrame()
        
        # Filter: ISIN starts with INE and INSTRUMENT_TYPE is ES
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
        
        logging.info(f"  Processed {len(bse_processed)} BSE records")
        return bse_processed
        
    except Exception as e:
        logging.error(f"Error processing BSE data: {str(e)}")
        return pd.DataFrame()

def merge_exchange_data(nse_df: pd.DataFrame, bse_df: pd.DataFrame) -> pd.DataFrame:
    """Merge NSE and BSE dataframes on ISIN"""
    logging.info("Merging NSE and BSE data...")
    
    merged_df = nse_df.merge(bse_df, on='isin', how='outer', suffixes=('_nse', '_bse'))
    
    final_df = pd.DataFrame()
    final_df['isin'] = merged_df['isin']
    final_df['securityid'] = merged_df['securityid_bse'].fillna(merged_df['securityid_nse'])
    final_df['newbsecode'] = merged_df['newbsecode']
    final_df['newnsecode'] = merged_df['newnsecode']
    final_df['newname'] = merged_df['newname_nse'].fillna(merged_df['newname_bse'])
    final_df['symbol'] = final_df['newbsecode'].fillna(final_df['newnsecode'])
    final_df['sector'] = None
    
    # Remove rows where both codes are null
    final_df = final_df.dropna(subset=['newbsecode', 'newnsecode'], how='all')
    
    # Convert securityid to integer
    final_df['securityid'] = pd.to_numeric(final_df['securityid'], errors='coerce').astype('Int64')
    
    # Clean data
    final_df = final_df.drop_duplicates(subset=['isin'])
    final_df['newname'] = final_df['newname'].str.strip().str.replace(r'\s+', ' ', regex=True)
    
    # Validate ISIN format
    valid_isin_mask = final_df['isin'].str.match(r'^INE[A-Z0-9]{9}$')
    final_df = final_df[valid_isin_mask]
    
    logging.info(f"✅ Merged and cleaned: {len(final_df)} records")
    logging.info(f"  Records with NSE codes: {final_df['newnsecode'].notna().sum()}")
    logging.info(f"  Records with BSE codes: {final_df['newbsecode'].notna().sum()}")
    logging.info(f"  Records with both: {(final_df['newnsecode'].notna() & final_df['newbsecode'].notna()).sum()}\n")
    
    return final_df

def generate_new_stocklist() -> bool:
    """Generate new stocklist from downloaded exchange data"""
    logging.info("=" * 80)
    logging.info("STEP 3: GENERATING NEW STOCKLIST")
    logging.info("=" * 80)
    
    try:
        nse_df = process_nse_data(NSE_FILE)
        if nse_df.empty:
            logging.error("No NSE data found")
            return False
        
        bse_df = process_bse_data(BSE_FILE)
        if bse_df.empty:
            logging.error("No BSE data found")
            return False
        
        final_df = merge_exchange_data(nse_df, bse_df)
        
        # Save to CSV
        final_df = final_df.sort_values('isin')
        final_df.to_csv(NEW_DATA_FILE, index=False)
        
        logging.info(f"✅ New stocklist generated: {NEW_DATA_FILE}")
        logging.info(f"  Total records: {len(final_df)}\n")
        
        return True
        
    except Exception as e:
        logging.error(f"❌ Error generating stocklist: {str(e)}")
        return False

# =============================================================================
# STEP 4: Compare and Detect Changes
# =============================================================================

def clean_string(value):
    """Clean string values for comparison"""
    if pd.isna(value) or value == '':
        return ''
    return str(value).strip().upper()

def clean_exchange_value(value):
    """Clean exchange codes by removing $ and other unwanted characters"""
    if pd.isna(value) or value == '':
        return ''
    return str(value).strip().replace('$', '')

def detect_field_changes(existing_row, new_row) -> Tuple[str, Dict, Dict]:
    """Detect what fields have changed between two rows"""
    changes = []
    updated_values = {}
    old_values = {}
    
    fields_to_compare = {
        'isin': 'isin',
        'securityid': 'securityid',
        'symbol': 'symbol',
        'newname': 'name',
        'newbsecode': 'bsecode',
        'newnsecode': 'nsecode'
    }
    
    old_field_mapping = {
        'isin': 'oldisin',
        'securityid': 'oldsecurityid',
        'symbol': 'oldsymbol',
        'newname': 'oldname',
        'newbsecode': 'oldbsecode',
        'newnsecode': 'oldnsecode'
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
        
        if target_symbol and row_symbol:
            total_checks += 1
            if target_symbol == row_symbol:
                matches += 1
        
        if target_name and row_name:
            total_checks += 1
            if target_name == row_name:
                matches += 1
        
        if target_securityid and row_securityid:
            total_checks += 1
            if target_securityid == row_securityid:
                matches += 1
        
        if target_bsecode and row_bsecode:
            total_checks += 1
            if target_bsecode == row_bsecode:
                matches += 1
        
        if target_nsecode and row_nsecode:
            total_checks += 1
            if target_nsecode == row_nsecode:
                matches += 1
        
        if total_checks >= 2 and matches >= 2:
            return idx
        
        if (target_symbol == row_symbol and target_securityid == row_securityid 
            and target_symbol and target_securityid):
            return idx
    
    return None

def compare_stockdata(existing_df: pd.DataFrame, new_df: pd.DataFrame) -> pd.DataFrame:
    """Compare existing and new stocklistdata"""
    logging.info("=" * 80)
    logging.info("STEP 4: COMPARING AND DETECTING CHANGES")
    logging.info("=" * 80)
    
    results = []
    used_new_indices = set()
    
    # Phase 1: ISIN-based exact matching
    logging.info("Phase 1: ISIN-based exact matching...")
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
        
        if idx > 0 and idx % 1000 == 0:
            logging.info(f"  Processed {idx} existing records...")
    
    logging.info(f"  Found {exact_matches} exact ISIN matches")
    logging.info(f"  Detected changes in {changes_detected} records")
    
    # Phase 2: Alternative matching for ISIN changes
    logging.info("Phase 2: Alternative matching for unmatched records...")
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
    
    logging.info(f"  Found {isin_changes_detected} potential ISIN changes")
    
    # Phase 3: New companies
    logging.info("Phase 3: Detecting new companies...")
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
    
    logging.info(f"  Found {new_companies} completely new companies")
    
    results_df = pd.DataFrame(results)
    changes_only_df = results_df[results_df['change'] != 'no_change'].copy()
    
    logging.info(f"\n✅ Comparison Summary:")
    logging.info(f"  Total records processed: {len(results_df)}")
    logging.info(f"  Records with no changes: {len(results_df[results_df['change'] == 'no_change'])}")
    logging.info(f"  Records with changes: {len(changes_only_df)}")
    
    if len(changes_only_df) > 0:
        change_breakdown = changes_only_df['change'].value_counts()
        logging.info(f"\n  Change breakdown:")
        for change_type, count in change_breakdown.head(10).items():
            logging.info(f"    {change_type}: {count}")
    
    logging.info("")
    return changes_only_df

# =============================================================================
# STEP 5: Submit Changes for Verification
# =============================================================================

def map_change_to_columns(change_row: pd.Series) -> Dict:
    """Map detected changes to company_changes_pending columns"""
    change_types = [c.strip() for c in change_row['change'].split(',') if c.strip() and c.strip() != 'no_change']
    
    # Determine primary change type
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
    elif 'securityid' in change_types:
        primary_change_type = 'securityid'
    elif 'sector' in change_types:
        primary_change_type = 'sector'
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
    
    pending_change = {
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
        'source_file': 'detect_changes.py',
        'change_detection_metadata': {
            'detected_changes': change_types,
            'detection_date': datetime.now().isoformat(),
            'has_bse': bool(change_row.get('newbsecode')),
            'has_nse': bool(change_row.get('newnsecode'))
        }
    }
    
    return {k: v for k, v in pending_change.items() if v is not None}

def check_duplicate_pending_change(supabase, isin: str, change_type: str, company_id: str = None) -> Tuple[bool, str]:
    """Check if this change is already pending verification"""
    # Check 1: Exact match
    result = supabase.table('company_changes_pending')\
        .select('id, change_type')\
        .eq('isin', isin)\
        .eq('change_type', change_type)\
        .eq('applied', False)\
        .execute()
    
    if len(result.data) > 0:
        return True, f"exact match (ISIN={isin}, type={change_type})"
    
    # Check 2: Any pending change for this ISIN
    result = supabase.table('company_changes_pending')\
        .select('id, change_type')\
        .eq('isin', isin)\
        .eq('applied', False)\
        .execute()
    
    if len(result.data) > 0:
        existing_types = [r['change_type'] for r in result.data]
        return True, f"pending change exists for ISIN={isin} (types: {', '.join(existing_types)})"
    
    # Check 3: Any pending change for this company_id
    if company_id:
        result = supabase.table('company_changes_pending')\
            .select('id, change_type, isin')\
            .eq('company_id', company_id)\
            .eq('applied', False)\
            .execute()
        
        if len(result.data) > 0:
            existing_types = [r['change_type'] for r in result.data]
            return True, f"pending change exists for company_id={company_id} (types: {', '.join(existing_types)})"
    
    return False, ""

def submit_changes_for_verification(changes_df: pd.DataFrame, supabase) -> Dict:
    """Submit detected changes to the verification queue"""
    logging.info("=" * 80)
    logging.info("STEP 5: SUBMITTING CHANGES FOR VERIFICATION")
    logging.info("=" * 80)
    
    stats = {
        'total_changes': len(changes_df),
        'submitted': 0,
        'skipped_duplicates': 0,
        'errors': 0,
        'by_type': {},
        'skip_reasons': {}
    }
    
    logging.info(f"Checking for existing pending changes to avoid duplicates...\n")
    
    for idx, row in changes_df.iterrows():
        try:
            change_record = map_change_to_columns(row)
            isin = change_record['isin']
            change_type = change_record['change_type']
            company_id = change_record.get('company_id')
            
            is_duplicate, reason = check_duplicate_pending_change(supabase, isin, change_type, company_id)
            if is_duplicate:
                stats['skipped_duplicates'] += 1
                stats['skip_reasons'][reason] = stats['skip_reasons'].get(reason, 0) + 1
                if stats['skipped_duplicates'] <= 10:
                    logging.info(f"⏭️  Skipping: ISIN {isin} ({change_type}) - {reason}")
                elif stats['skipped_duplicates'] == 11:
                    logging.info(f"⏭️  ... (suppressing further duplicate messages)")
                continue
            
            result = supabase.table('company_changes_pending').insert(change_record).execute()
            
            if result.data:
                stats['submitted'] += 1
                stats['by_type'][change_type] = stats['by_type'].get(change_type, 0) + 1
                name = change_record.get('new_name', 'N/A')[:40]
                logging.info(f"✅ Submitted: {name} - ISIN {isin} ({change_type})")
            
            if stats['submitted'] > 0 and stats['submitted'] % 50 == 0:
                logging.info(f"\n📊 Progress: {stats['submitted']} submitted, {stats['skipped_duplicates']} skipped\n")
        
        except Exception as e:
            stats['errors'] += 1
            logging.error(f"❌ Error submitting change for ISIN {row.get('isin', 'unknown')}: {str(e)}")
    
    return stats

def print_submission_summary(stats: Dict):
    """Print summary of submission"""
    logging.info("\n" + "=" * 80)
    logging.info("SUBMISSION SUMMARY")
    logging.info("=" * 80)
    logging.info(f"Total changes detected:     {stats['total_changes']}")
    logging.info(f"Successfully submitted:     {stats['submitted']}")
    logging.info(f"Skipped (duplicates):       {stats['skipped_duplicates']}")
    logging.info(f"Errors:                     {stats['errors']}")
    
    if stats['submitted'] > 0:
        logging.info(f"\n✅ New changes submitted by type:")
        for change_type, count in sorted(stats['by_type'].items()):
            logging.info(f"  {change_type:20s}: {count}")
    
    if stats['skipped_duplicates'] > 0:
        logging.info(f"\n⏭️  Skipped reasons:")
        for reason, count in sorted(stats['skip_reasons'].items(), key=lambda x: x[1], reverse=True)[:10]:
            logging.info(f"  {count:3d} - {reason}")
    
    if stats['submitted'] > 0:
        logging.info(f"\n✅ Changes submitted to verification queue!")
        logging.info(f"👤 Admin action required: Verify changes through the admin API")
    elif stats['skipped_duplicates'] > 0:
        logging.info(f"\n✨ All detected changes are already in the verification queue!")
        logging.info(f"   No new submissions needed. Review existing pending changes.")
    else:
        logging.info(f"\n✨ No changes to submit!")

# =============================================================================
# STEP 6: Cleanup
# =============================================================================

def cleanup_temp_files(keep_files: bool = False):
    """Remove temporary downloaded files"""
    if keep_files:
        logging.info("\n📁 Keeping temporary files for inspection")
        return
    
    logging.info("\n🧹 Cleaning up temporary files...")
    
    temp_files = [NSE_FILE, BSE_FILE, CURRENT_DATA_FILE, NEW_DATA_FILE]
    
    for file in temp_files:
        if os.path.exists(file):
            try:
                os.remove(file)
                logging.info(f"  Removed {file}")
            except Exception as e:
                logging.warning(f"  Could not remove {file}: {str(e)}")
    
    logging.info("✅ Cleanup complete")

# =============================================================================
# Main Workflow
# =============================================================================

def get_verification_stats(supabase):
    """Get current verification queue statistics"""
    try:
        result = supabase.table('company_changes_stats').select('*').execute()
        
        if result.data and len(result.data) > 0:
            stats = result.data[0]
            logging.info("\n" + "=" * 80)
            logging.info("VERIFICATION QUEUE STATISTICS")
            logging.info("=" * 80)
            logging.info(f"Pending verification:       {stats.get('pending_verification', 0)}")
            logging.info(f"Ready to apply:             {stats.get('ready_to_apply', 0)}")
            logging.info(f"Applied:                    {stats.get('applied', 0)}")
            logging.info(f"Rejected:                   {stats.get('rejected', 0)}")
            logging.info(f"\nBreakdown:")
            logging.info(f"  New companies:            {stats.get('new_companies', 0)}")
            logging.info(f"  ISIN changes:             {stats.get('isin_changes', 0)}")
            logging.info(f"  Name changes:             {stats.get('name_changes', 0)}")
            logging.info(f"  Code changes:             {stats.get('code_changes', 0)}")
        else:
            logging.info("\n📊 No statistics available yet")
    
    except Exception as e:
        logging.error(f"Error fetching statistics: {str(e)}")

def detect_and_submit_changes(keep_files: bool = False):
    """Main workflow function"""
    logging.info("=" * 80)
    logging.info("COMPANY CHANGE DETECTION AND VERIFICATION WORKFLOW")
    logging.info("=" * 80)
    logging.info(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    try:
        # Initialize Supabase
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Step 1: Download exchange data
        if not download_all_exchange_data():
            return False
        
        # Step 2: Fetch current stocklistdata
        existing_df = fetch_current_stocklistdata(supabase)
        if existing_df.empty:
            logging.error("No current stocklistdata found")
            return False
        
        # Step 3: Generate new stocklist
        if not generate_new_stocklist():
            return False
        
        # Load the generated new stocklist
        new_df = pd.read_csv(NEW_DATA_FILE)
        
        # Step 4: Compare and detect changes
        changes_df = compare_stockdata(existing_df, new_df)
        
        if len(changes_df) == 0:
            logging.info("✨ No changes detected. Database is up to date!")
            cleanup_temp_files(keep_files)
            return True
        
        # Step 5: Submit for verification
        stats = submit_changes_for_verification(changes_df, supabase)
        print_submission_summary(stats)
        
        # Step 6: Cleanup
        cleanup_temp_files(keep_files)
        
        return True
        
    except Exception as e:
        logging.error(f"\n❌ Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    parser = argparse.ArgumentParser(
        description='Detect and submit company changes for verification (self-contained)',
        epilog='Example: python3 detect_changes.py'
    )
    parser.add_argument('--stats-only', action='store_true',
                       help='Only show verification queue statistics')
    parser.add_argument('--keep-files', action='store_true',
                       help='Keep downloaded CSV files for inspection (default: delete)')
    
    args = parser.parse_args()
    
    try:
        if args.stats_only:
            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            get_verification_stats(supabase)
            sys.exit(0)
        else:
            success = detect_and_submit_changes(args.keep_files)
            sys.exit(0 if success else 1)
    
    except KeyboardInterrupt:
        logging.info("\n\n⚠️  Process interrupted by user")
        sys.exit(130)
    
    except Exception as e:
        logging.error(f"\n\n❌ Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
