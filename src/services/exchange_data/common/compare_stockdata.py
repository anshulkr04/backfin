import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional

def load_data():
    """Load both CSV files for comparison"""
    print("Loading data files...")
    
    # Load existing data (testtablenew.csv)
    existing_df = pd.read_csv('testtablenew.csv')
    print(f"Loaded {len(existing_df)} existing records from testtablenew.csv")
    
    # Load new data (stocklistdata.csv)
    new_df = pd.read_csv('stocklistdata.csv')
    print(f"Loaded {len(new_df)} new records from stocklistdata.csv")
    
    return existing_df, new_df

def clean_string(value):
    """Clean string values for comparison"""
    if pd.isna(value) or value == '':
        return ''
    return str(value).strip().upper()

def clean_exchange_value(value):
    """Clean exchange codes and symbols by removing $ and other unwanted characters"""
    if pd.isna(value) or value == '':
        return ''
    # Remove $ symbol and strip whitespace
    cleaned = str(value).strip().replace('$', '')
    return cleaned

def detect_field_changes(existing_row, new_row) -> Tuple[str, Dict, Dict]:
    """Detect what fields have changed between two rows"""
    changes = []
    updated_values = {}
    old_values = {}
    
    # Define fields to compare (excluding company_id which doesn't exist in new data)
    fields_to_compare = {
        'isin': 'isin',
        'securityid': 'securityid',
        'symbol': 'symbol', 
        'newname': 'name',
        'newbsecode': 'bsecode',
        'newnsecode': 'nsecode'
    }
    
    # Map fields to their corresponding "old" columns
    old_field_mapping = {
        'isin': 'oldisin',
        'securityid': 'oldsecurityid',
        'symbol': 'oldsymbol',
        'newname': 'oldname',
        'newbsecode': 'oldbsecode',
        'newnsecode': 'oldnsecode'
    }
    
    # Fields that need special cleaning (exchange codes and symbols)
    exchange_fields = {'symbol', 'newbsecode', 'newnsecode'}
    
    for field, change_type in fields_to_compare.items():
        if field in existing_row and field in new_row:
            # Use appropriate cleaning function based on field type
            if field in exchange_fields:
                existing_val = clean_string(clean_exchange_value(existing_row[field]))
                new_val = clean_string(clean_exchange_value(new_row[field]))
                # Store cleaned new value
                cleaned_new_value = clean_exchange_value(new_row[field])
            else:
                existing_val = clean_string(existing_row[field])
                new_val = clean_string(new_row[field])
                cleaned_new_value = new_row[field]
            
            if existing_val != new_val:
                changes.append(change_type)
                # Store the cleaned new value to update the main field
                updated_values[field] = cleaned_new_value
                # Store the old value in the corresponding "old" field
                old_field = old_field_mapping[field]
                old_values[old_field] = existing_row[field]
    
    if not changes:
        return 'no_change', updated_values, old_values
    elif len(changes) == 1:
        return changes[0], updated_values, old_values
    else:
        # Return comma-separated list of changes instead of just "multiple"
        return ','.join(sorted(changes)), updated_values, old_values

def find_company_by_alternative_matching(target_row, df, used_indices) -> Optional[int]:
    """Try to find a company using alternative matching criteria"""
    
    target_symbol = clean_string(clean_exchange_value(target_row.get('symbol', '')))
    target_name = clean_string(target_row.get('newname', ''))
    target_securityid = clean_string(target_row.get('securityid', ''))
    target_bsecode = clean_string(clean_exchange_value(target_row.get('newbsecode', '')))
    target_nsecode = clean_string(clean_exchange_value(target_row.get('newnsecode', '')))
    
    # Skip if key fields are empty
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
        
        # Try multiple matching strategies
        matches = 0
        total_checks = 0
        
        # Strategy 1: Symbol + Name match
        if target_symbol and row_symbol:
            total_checks += 1
            if target_symbol == row_symbol:
                matches += 1
                
        if target_name and row_name:
            total_checks += 1
            if target_name == row_name:
                matches += 1
        
        # Strategy 2: Security ID + Symbol match
        if target_securityid and row_securityid:
            total_checks += 1
            if target_securityid == row_securityid:
                matches += 1
                
        # Strategy 3: Exchange codes match
        if target_bsecode and row_bsecode:
            total_checks += 1
            if target_bsecode == row_bsecode:
                matches += 1
                
        if target_nsecode and row_nsecode:
            total_checks += 1
            if target_nsecode == row_nsecode:
                matches += 1
        
        # If at least 2 fields match, consider it a match
        if total_checks >= 2 and matches >= 2:
            return idx
            
        # Special case: if symbol and security ID both match perfectly
        if (target_symbol == row_symbol and target_securityid == row_securityid 
            and target_symbol and target_securityid):
            return idx
    
    return None

def compare_stockdata():
    """Main comparison function"""
    existing_df, new_df = load_data()
    
    # Prepare results list
    results = []
    used_new_indices = set()
    
    print("\n=== Phase 1: ISIN-based exact matching ===")
    exact_matches = 0
    changes_detected = 0
    
    for idx, existing_row in existing_df.iterrows():
        existing_isin = clean_string(existing_row.get('isin', ''))
        
        if not existing_isin:
            continue
            
        # Look for exact ISIN match in new data
        new_matches = new_df[new_df['isin'].apply(clean_string) == existing_isin]
        
        if len(new_matches) > 0:
            exact_matches += 1
            new_row = new_matches.iloc[0]
            used_new_indices.add(new_matches.index[0])
            
            # Detect what changed
            change_type, updated_values, old_values = detect_field_changes(existing_row, new_row)
            
            if change_type != 'no_change':
                changes_detected += 1
            
            # Create result row with all existing columns
            result_row = existing_row.to_dict()
            result_row['change'] = change_type
            
            # Update main fields with new values and store old values in old columns
            for field, new_value in updated_values.items():
                result_row[field] = new_value
            
            for old_field, old_value in old_values.items():
                result_row[old_field] = old_value
                
            results.append(result_row)
        
        if idx % 1000 == 0:
            print(f"Processed {idx} existing records...")
    
    print(f"Found {exact_matches} exact ISIN matches")
    print(f"Detected changes in {changes_detected} records")
    
    print("\n=== Phase 2: Alternative matching for unmatched existing records ===")
    isin_changes_detected = 0
    
    for idx, existing_row in existing_df.iterrows():
        existing_isin = clean_string(existing_row.get('isin', ''))
        
        # Skip if already matched by ISIN
        if existing_isin:
            new_matches = new_df[new_df['isin'].apply(clean_string) == existing_isin]
            if len(new_matches) > 0:
                continue
        
        # Try alternative matching
        match_idx = find_company_by_alternative_matching(existing_row, new_df, used_new_indices)
        
        if match_idx is not None:
            isin_changes_detected += 1
            new_row = new_df.iloc[match_idx]
            used_new_indices.add(match_idx)
            
            # This is likely an ISIN change
            result_row = existing_row.to_dict()
            result_row['change'] = 'isin'
            result_row['oldisin'] = existing_row['isin']  # Store old ISIN
            result_row['isin'] = new_row['isin']  # Update to new ISIN
            
            # Also check for other changes
            change_type, updated_values, old_values = detect_field_changes(existing_row, new_row)
            if change_type != 'no_change':
                # Combine ISIN change with other changes
                other_changes = change_type.split(',') if ',' in change_type else [change_type]
                all_changes = ['isin'] + other_changes
                result_row['change'] = ','.join(sorted(all_changes))
                
                # Update main fields with new values and store old values
                for field, new_value in updated_values.items():
                    result_row[field] = new_value
                
                for old_field, old_value in old_values.items():
                    result_row[old_field] = old_value
            
            results.append(result_row)
    
    print(f"Found {isin_changes_detected} potential ISIN changes through alternative matching")
    
    print("\n=== Phase 3: New companies not in existing data ===")
    new_companies = 0
    
    for idx, new_row in new_df.iterrows():
        if idx not in used_new_indices:
            new_companies += 1
            
            # Create result row with new company data (cleaned)
            result_row = {
                'isin': new_row['isin'],
                'securityid': new_row['securityid'],
                'newbsecode': clean_exchange_value(new_row.get('newbsecode', '')),
                'oldbsecode': new_row.get('oldbsecode', ''),
                'newnsecode': clean_exchange_value(new_row.get('newnsecode', '')),
                'oldnsecode': new_row.get('oldnsecode', ''),
                'newname': new_row.get('newname', ''),
                'oldname': new_row.get('oldname', ''),
                'symbol': clean_exchange_value(new_row['symbol']),
                'company_id': '',  # New companies don't have company_id yet
                'sector': new_row.get('sector', ''),
                'change': 'new'
            }
            
            results.append(result_row)
    
    print(f"Found {new_companies} completely new companies")
    
    # Convert results to DataFrame
    results_df = pd.DataFrame(results)
    
    # Define column order (existing columns + old columns)
    base_columns = ['isin', 'securityid', 'newbsecode', 'oldbsecode', 'newnsecode', 'oldnsecode', 
                   'newname', 'oldname', 'symbol', 'company_id', 'sector', 'change']
    
    # Add old value columns for tracking changes
    old_value_columns = ['oldisin', 'oldsecurityid', 'oldsymbol']
    
    all_columns = base_columns + old_value_columns
    
    # Reorder columns and fill missing columns
    for col in all_columns:
        if col not in results_df.columns:
            results_df[col] = ''
    
    results_df = results_df[all_columns]
    
    # Filter to only include records with changes (exclude no_change)
    changes_only_df = results_df[results_df['change'] != 'no_change'].copy()
    
    # Save full results for reference
    full_output_filename = 'stockdata_changes_full.csv'
    results_df.to_csv(full_output_filename, index=False)
    
    # Save changes-only results (main output)
    changes_output_filename = 'stockdata_changes.csv'
    changes_only_df.to_csv(changes_output_filename, index=False)
    
    print(f"\n=== Summary ===")
    print(f"Total records processed: {len(results_df)}")
    print(f"Records with no changes: {len(results_df[results_df['change'] == 'no_change'])}")
    print(f"Records with changes: {len(changes_only_df)}")
    
    change_breakdown = changes_only_df['change'].value_counts()
    print(f"\nChange breakdown (changes only):")
    for change_type, count in change_breakdown.items():
        print(f"  {change_type}: {count}")
    
    print(f"\nChanges-only results saved to: {changes_output_filename}")
    print(f"Full results (including no_change) saved to: {full_output_filename}")
    
    return changes_only_df

if __name__ == "__main__":
    compare_stockdata()