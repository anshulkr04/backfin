#!/usr/bin/env python3
"""
Company Change Detection and Verification Workflow

This is the main entry point for detecting and submitting company changes.
Safe for use in cronjobs - handles errors gracefully and provides clear logging.

Workflow:
1. Compare current stocklistdata with new exchange data
2. Detect changes (new companies, ISIN changes, name changes, etc.)
3. Submit detected changes to company_changes_pending table (with duplicate prevention)
4. Admin verifies each change through verification API
5. Verified changes are applied to stocklistdata table

Usage:
    # Standard run
    python detect_changes.py --source-dir ../common
    
    # Check statistics only
    python detect_changes.py --stats-only
    
    # Cronjob example
    0 6 * * * cd /path/to/company_management && python3 detect_changes.py --source-dir ../common >> /var/log/company_changes.log 2>&1

Exit Codes:
    0 - Success
    1 - Error occurred
    130 - Interrupted by user (Ctrl+C)
"""

import pandas as pd
import sys
import os
from pathlib import Path
from typing import Dict, List, Tuple
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent / 'common'))
from compare_stockdata import compare_stockdata, clean_string, clean_exchange_value

load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL2")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

def initialize_supabase():
    """Initialize Supabase client"""
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def parse_change_type(change_str: str) -> List[str]:
    """Parse comma-separated change types"""
    if not change_str or change_str == 'no_change':
        return []
    return [c.strip() for c in change_str.split(',')]

def map_change_to_columns(change_row: pd.Series) -> Dict:
    """Map detected changes to company_changes_pending columns"""
    change_types = parse_change_type(change_row['change'])
    
    # Determine primary change type for the column
    # Valid values: 'new', 'isin', 'name', 'bsecode', 'nsecode', 'symbol', 'securityid', 'sector', 'multiple'
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
        # Multiple changes detected - use 'multiple' instead of comma-separated list
        primary_change_type = 'multiple'
    elif len(change_types) == 1:
        primary_change_type = change_types[0]
    else:
        primary_change_type = 'multiple'
    
    # Build the pending change record
    pending_change = {
        'isin': clean_string(change_row.get('isin', '')),
        'change_type': primary_change_type,
        
        # New values (cleaned)
        'new_isin': clean_string(change_row.get('isin', '')),
        'new_securityid': int(change_row['securityid']) if pd.notna(change_row.get('securityid')) else None,
        'new_bsecode': clean_exchange_value(change_row.get('newbsecode', '')),
        'new_nsecode': clean_exchange_value(change_row.get('newnsecode', '')),
        'new_name': clean_string(change_row.get('newname', '')),
        'new_sector': clean_string(change_row.get('sector', '')),
        'new_symbol': clean_exchange_value(change_row.get('symbol', '')),
        
        # Old values (for tracking what changed)
        'old_isin': clean_string(change_row.get('oldisin', '')) if pd.notna(change_row.get('oldisin')) else None,
        'old_securityid': int(change_row['oldsecurityid']) if pd.notna(change_row.get('oldsecurityid')) else None,
        'old_bsecode': clean_exchange_value(change_row.get('oldbsecode', '')) if pd.notna(change_row.get('oldbsecode')) else None,
        'old_nsecode': clean_exchange_value(change_row.get('oldnsecode', '')) if pd.notna(change_row.get('oldnsecode')) else None,
        'old_name': clean_string(change_row.get('oldname', '')) if pd.notna(change_row.get('oldname')) else None,
        'old_symbol': clean_exchange_value(change_row.get('oldsymbol', '')) if pd.notna(change_row.get('oldsymbol')) else None,
        
        # Company ID (None for new companies)
        'company_id': change_row.get('company_id') if pd.notna(change_row.get('company_id')) and change_row.get('company_id') != '' else None,
        
        # Metadata
        'source_file': 'stockdata_changes.csv',
        'change_detection_metadata': {
            'detected_changes': change_types,
            'detection_date': datetime.now().isoformat(),
            'has_bse': bool(change_row.get('newbsecode')),
            'has_nse': bool(change_row.get('newnsecode'))
        }
    }
    
    # Clean None values
    return {k: v for k, v in pending_change.items() if v is not None}

def check_duplicate_pending_change(supabase, isin: str, change_type: str, company_id: str = None) -> Tuple[bool, str]:
    """Check if this change is already pending verification
    
    Returns:
        Tuple[bool, str]: (is_duplicate, reason)
    """
    # Check 1: Exact match - same ISIN, same change type, not applied
    result = supabase.table('company_changes_pending')\
        .select('id, change_type')\
        .eq('isin', isin)\
        .eq('change_type', change_type)\
        .eq('applied', False)\
        .execute()
    
    if len(result.data) > 0:
        return True, f"exact match (ISIN={isin}, type={change_type})"
    
    # Check 2: Any pending change for this ISIN (different type)
    result = supabase.table('company_changes_pending')\
        .select('id, change_type')\
        .eq('isin', isin)\
        .eq('applied', False)\
        .execute()
    
    if len(result.data) > 0:
        existing_types = [r['change_type'] for r in result.data]
        return True, f"pending change exists for ISIN={isin} (types: {', '.join(existing_types)})"
    
    # Check 3: If company_id provided, check for any pending changes on this company
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
    stats = {
        'total_changes': len(changes_df),
        'submitted': 0,
        'skipped_duplicates': 0,
        'errors': 0,
        'by_type': {},
        'skip_reasons': {}
    }
    
    print(f"\n=== Submitting {len(changes_df)} changes for verification ===")
    print("Checking for existing pending changes to avoid duplicates...\n")
    
    for idx, row in changes_df.iterrows():
        try:
            change_record = map_change_to_columns(row)
            isin = change_record['isin']
            change_type = change_record['change_type']
            company_id = change_record.get('company_id')
            
            # Check for duplicates (any pending change for this ISIN or company)
            is_duplicate, reason = check_duplicate_pending_change(supabase, isin, change_type, company_id)
            if is_duplicate:
                stats['skipped_duplicates'] += 1
                stats['skip_reasons'][reason] = stats['skip_reasons'].get(reason, 0) + 1
                if stats['skipped_duplicates'] <= 10:  # Show first 10 skips
                    print(f"⏭️  Skipping: ISIN {isin} ({change_type}) - {reason}")
                elif stats['skipped_duplicates'] == 11:
                    print(f"⏭️  ... (suppressing further duplicate messages)")
                continue
            
            # Insert into pending changes
            result = supabase.table('company_changes_pending').insert(change_record).execute()
            
            if result.data:
                stats['submitted'] += 1
                stats['by_type'][change_type] = stats['by_type'].get(change_type, 0) + 1
                name = change_record.get('new_name', 'N/A')[:40]
                print(f"✅ Submitted: {name} - ISIN {isin} ({change_type})")
            
            # Progress update
            if stats['submitted'] > 0 and stats['submitted'] % 50 == 0:
                print(f"\n📊 Progress: {stats['submitted']} submitted, {stats['skipped_duplicates']} skipped\n")
                
        except Exception as e:
            stats['errors'] += 1
            print(f"❌ Error submitting change for ISIN {row.get('isin', 'unknown')}: {str(e)}")
    
    return stats

def detect_and_submit_changes(source_dir: str = None):
    """
    Main workflow function:
    1. Run change detection (compare_stockdata)
    2. Submit detected changes for verification
    """
    print("=" * 80)
    print("COMPANY CHANGE DETECTION AND VERIFICATION WORKFLOW")
    print("=" * 80)
    
    # Change to source directory if provided
    if source_dir:
        os.chdir(source_dir)
        print(f"Working directory: {os.getcwd()}")
    
    # Step 1: Detect changes
    print("\n📊 Step 1: Detecting changes from exchange data...")
    print("-" * 80)
    
    try:
        changes_df = compare_stockdata()
        print(f"\n✅ Change detection complete: {len(changes_df)} changes detected")
    except Exception as e:
        print(f"❌ Error during change detection: {str(e)}")
        return
    
    if len(changes_df) == 0:
        print("✨ No changes detected. Database is up to date!")
        return
    
    # Step 2: Submit for verification
    print("\n📤 Step 2: Submitting changes for admin verification...")
    print("-" * 80)
    
    try:
        supabase = initialize_supabase()
        stats = submit_changes_for_verification(changes_df, supabase)
        
        print("\n" + "=" * 80)
        print("SUBMISSION SUMMARY")
        print("=" * 80)
        print(f"Total changes detected:     {stats['total_changes']}")
        print(f"Successfully submitted:     {stats['submitted']}")
        print(f"Skipped (duplicates):       {stats['skipped_duplicates']}")
        print(f"Errors:                     {stats['errors']}")
        
        if stats['submitted'] > 0:
            print("\n✅ New changes submitted by type:")
            for change_type, count in sorted(stats['by_type'].items()):
                print(f"  {change_type:20s}: {count}")
        
        if stats['skipped_duplicates'] > 0:
            print("\n⏭️  Skipped reasons:")
            for reason, count in sorted(stats['skip_reasons'].items(), key=lambda x: x[1], reverse=True):
                print(f"  {count:3d} - {reason}")
        
        if stats['submitted'] > 0:
            print("\n✅ Changes submitted to verification queue!")
            print("👤 Admin action required: Verify changes through the admin API")
            print("   - Endpoint: GET /api/admin/company-changes/pending")
            print("   - Verify each change: POST /api/admin/company-changes/{id}/verify")
            print("   - Apply verified changes: POST /api/admin/company-changes/apply-verified")
        elif stats['skipped_duplicates'] > 0:
            print("\n✨ All detected changes are already in the verification queue!")
            print("   No new submissions needed. Review existing pending changes.")
        else:
            print("\n✨ No changes to submit!")
        
    except Exception as e:
        print(f"❌ Error submitting changes: {str(e)}")
        return

def get_verification_stats(supabase):
    """Get current verification queue statistics"""
    result = supabase.table('company_changes_stats').select('*').execute()
    
    if result.data and len(result.data) > 0:
        stats = result.data[0]
        print("\n" + "=" * 80)
        print("VERIFICATION QUEUE STATISTICS")
        print("=" * 80)
        print(f"Pending verification:       {stats.get('pending_verification', 0)}")
        print(f"Ready to apply:             {stats.get('ready_to_apply', 0)}")
        print(f"Applied:                    {stats.get('applied', 0)}")
        print(f"Rejected:                   {stats.get('rejected', 0)}")
        print("\nBreakdown:")
        print(f"  New companies:            {stats.get('new_companies', 0)}")
        print(f"  ISIN changes:             {stats.get('isin_changes', 0)}")
        print(f"  Name changes:             {stats.get('name_changes', 0)}")
        print(f"  Code changes:             {stats.get('code_changes', 0)}")

if __name__ == "__main__":
    import argparse
    import logging
    
    # Setup logging for cronjob
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    parser = argparse.ArgumentParser(
        description='Detect and submit company changes for verification',
        epilog='Example: python detect_changes.py --source-dir ../common'
    )
    parser.add_argument('--source-dir', type=str, 
                       help='Source directory containing CSV files',
                       default='../common')
    parser.add_argument('--stats-only', action='store_true', 
                       help='Only show verification queue statistics')
    parser.add_argument('--dry-run', action='store_true',
                       help='Detect changes but do not submit to database')
    
    args = parser.parse_args()
    
    try:
        if args.stats_only:
            supabase = initialize_supabase()
            get_verification_stats(supabase)
            sys.exit(0)
        else:
            detect_and_submit_changes(args.source_dir)
            sys.exit(0)
    except KeyboardInterrupt:
        logging.info("\n\n⚠️  Process interrupted by user")
        sys.exit(130)
    except Exception as e:
        logging.error(f"\n\n❌ Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
