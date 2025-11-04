import pandas as pd
import os
import time
import json
from datetime import datetime

# Constants for processing
BATCH_SIZE = 1000
progress_file = "csv_generation_progress.json"

# Global variables to track progress
processed_isins = set()

def save_progress():
    """Save the current progress to a file"""
    with open(progress_file, 'w') as f:
        json.dump(list(processed_isins), f)
    print(f"Progress saved: {len(processed_isins)} records processed")

def load_progress():
    """Load progress from a file if it exists"""
    global processed_isins
    if os.path.exists(progress_file):
        with open(progress_file, 'r') as f:
            processed_isins = set(json.load(f))
        print(f"Loaded progress: {len(processed_isins)} records already processed")

def process_nse_data(nse_file_path):
    """
    Process NSE CSV file and return filtered dataframe.
    
    Filter conditions:
    - ISIN starts with 'INE' and INSTRUMENT_TYPE is 'ES'
    - OR ISIN starts with 'INE' and INSTRUMENT_TYPE is 'Other' and SERIES is 'EQ'
    """
    print(f"Processing NSE data from {nse_file_path}...")
    
    try:
        # Read the CSV file, skipping the first row which contains column numbers
        df = pd.read_csv(nse_file_path, skiprows=1)
        
        # Debug: Print column names to understand the structure
        print(f"NSE CSV columns: {list(df.columns)}")
        print(f"NSE CSV shape: {df.shape}")
        print(f"NSE CSV first few rows:\n{df.head()}")
        
        # Check if required columns exist
        required_columns = ['ISIN', 'INSTRUMENT_TYPE', 'UNDERLYING_SYMBOL', 'DISPLAY_NAME', 'SECURITY_ID']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            print(f"Missing required columns: {missing_columns}")
            print("Available columns:", list(df.columns))
            return pd.DataFrame()
        
        # Filter data based on conditions
        filtered_df = df[
            ((df['ISIN'].str.startswith('INE')) & (df['INSTRUMENT_TYPE'] == 'ES')) |
            ((df['ISIN'].str.startswith('INE')) & (df['INSTRUMENT_TYPE'] == 'Other') & (df['SERIES'] == 'EQ'))
        ]
        
        # Standardize column names for our CSV format
        nse_processed = pd.DataFrame({
            'isin': filtered_df['ISIN'],
            'securityid': filtered_df['SECURITY_ID'],
            'newnsecode': filtered_df['UNDERLYING_SYMBOL'],
            'newname': filtered_df['DISPLAY_NAME'],
            'data_source': 'NSE'
        })
        
        total_records = len(nse_processed)
        print(f"Found {total_records} eligible NSE records.")
        
        return nse_processed
    
    except Exception as e:
        print(f"Error processing NSE data: {str(e)}")
        return pd.DataFrame()

def process_bse_data(bse_file_path):
    """
    Process BSE CSV file and return filtered dataframe.
    
    Filter condition:
    - ISIN starts with 'INE' and INSTRUMENT_TYPE is 'ES'
    """
    print(f"Processing BSE data from {bse_file_path}...")
    
    try:
        # Read the CSV file, skipping the first row which contains column numbers
        df = pd.read_csv(bse_file_path, skiprows=1)
        
        # Debug: Print column names to understand the structure
        print(f"BSE CSV columns: {list(df.columns)}")
        print(f"BSE CSV shape: {df.shape}")
        print(f"BSE CSV first few rows:\n{df.head()}")
        
        # Check if required columns exist
        required_columns = ['ISIN', 'INSTRUMENT_TYPE', 'UNDERLYING_SYMBOL', 'DISPLAY_NAME', 'SECURITY_ID']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            print(f"Missing required columns: {missing_columns}")
            print("Available columns:", list(df.columns))
            return pd.DataFrame()
        
        # Filter data based on conditions
        filtered_df = df[
            (df['ISIN'].str.startswith('INE')) & (df['INSTRUMENT_TYPE'] == 'ES')
        ]
        
        # Standardize column names for our CSV format
        bse_processed = pd.DataFrame({
            'isin': filtered_df['ISIN'],
            'securityid': filtered_df['SECURITY_ID'],
            'newbsecode': filtered_df['UNDERLYING_SYMBOL'],
            'newname': filtered_df['DISPLAY_NAME'],
            'data_source': 'BSE'
        })
        
        total_records = len(bse_processed)
        print(f"Found {total_records} eligible BSE records.")
        
        return bse_processed
    
    except Exception as e:
        print(f"Error processing BSE data: {str(e)}")
        return pd.DataFrame()

def merge_exchange_data(nse_df, bse_df):
    """
    Merge NSE and BSE dataframes on ISIN to create unified stocklist.
    Priority: NSE data for company names and security IDs, BSE as supplementary
    """
    print("Merging NSE and BSE data...")
    
    # Start with NSE data as base (outer join to keep all records)
    merged_df = nse_df.merge(bse_df, on='isin', how='outer', suffixes=('_nse', '_bse'))
    
    # Create the final structure matching your table schema
    final_df = pd.DataFrame()
    
    # ISIN (primary key)
    final_df['isin'] = merged_df['isin']
    
    # Security ID - prefer BSE if available, fallback to NSE
    # This matches the requirement that BSE security ID should take priority
    final_df['securityid'] = merged_df['securityid_bse'].fillna(merged_df['securityid_nse'])
    
    # BSE Code
    final_df['newbsecode'] = merged_df['newbsecode']
    
    # Old BSE Code (placeholder for now - can be populated if you have historical data)
    final_df['oldbsecode'] = None
    
    # NSE Code
    final_df['newnsecode'] = merged_df['newnsecode']
    
    # Old NSE Code (placeholder for now - can be populated if you have historical data)
    final_df['oldnsecode'] = None
    
    # Company Name - prefer NSE, fallback to BSE
    final_df['newname'] = merged_df['newname_nse'].fillna(merged_df['newname_bse'])
    
    # Old Name (placeholder for now - can be populated if you have historical data)
    final_df['oldname'] = None
    
    # Symbol - matches your SQL logic: COALESCE(newbsecode, newnsecode)
    final_df['symbol'] = final_df['newbsecode'].fillna(final_df['newnsecode'])
    
    # Sector (placeholder for now - can be enriched from other data sources)
    final_df['sector'] = None
    
    # Remove rows where both newbsecode and newnsecode are null (invalid records)
    final_df = final_df.dropna(subset=['newbsecode', 'newnsecode'], how='all')
    
    # Convert securityid to integer where possible
    final_df['securityid'] = pd.to_numeric(final_df['securityid'], errors='coerce').astype('Int64')
    
    print(f"Merged data: {len(final_df)} total records")
    print(f"Records with NSE codes: {final_df['newnsecode'].notna().sum()}")
    print(f"Records with BSE codes: {final_df['newbsecode'].notna().sum()}")
    print(f"Records with both codes: {(final_df['newnsecode'].notna() & final_df['newbsecode'].notna()).sum()}")
    
    return final_df

def validate_and_clean_data(df):
    """
    Validate and clean the merged data
    """
    print("Validating and cleaning data...")
    
    initial_count = len(df)
    
    # Remove duplicates based on ISIN
    df = df.drop_duplicates(subset=['isin'])
    
    # Clean company names
    df['newname'] = df['newname'].str.strip()
    df['newname'] = df['newname'].str.replace(r'\s+', ' ', regex=True)  # Replace multiple spaces with single space
    
    # Validate ISIN format (should start with INE and be 12 characters)
    valid_isin_mask = df['isin'].str.match(r'^INE[A-Z0-9]{9}$')
    invalid_isins = df[~valid_isin_mask]['isin'].tolist()
    
    if invalid_isins:
        print(f"Warning: Found {len(invalid_isins)} records with invalid ISIN format")
        print(f"Invalid ISINs: {invalid_isins[:5]}...")  # Show first 5
    
    # Keep only valid ISINs
    df = df[valid_isin_mask]
    
    final_count = len(df)
    print(f"Data cleaning complete: {initial_count} -> {final_count} records")
    
    return df

def generate_csv(output_filename="stocklistdata.csv"):
    """
    Main function to generate the stocklist CSV file
    """
    # File paths - update these to your actual file paths
    nse_file_path = "NSE_EQ_instruments.csv"
    bse_file_path = "BSE_EQ_instruments.csv"
    
    # Check if files exist
    if not os.path.exists(nse_file_path):
        print(f"NSE file not found: {nse_file_path}")
        return False
    
    if not os.path.exists(bse_file_path):
        print(f"BSE file not found: {bse_file_path}")
        return False
    
    try:
        print("Starting stocklist CSV generation...")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Process NSE data
        nse_df = process_nse_data(nse_file_path)
        if nse_df.empty:
            print("No NSE data found. Aborting.")
            return False
        
        # Process BSE data
        bse_df = process_bse_data(bse_file_path)
        if bse_df.empty:
            print("No BSE data found. Aborting.")
            return False
        
        # Merge the datasets
        merged_df = merge_exchange_data(nse_df, bse_df)
        
        # Validate and clean
        final_df = validate_and_clean_data(merged_df)
        
        # Sort by ISIN for consistency
        final_df = final_df.sort_values('isin')
        
        # Generate CSV with exact column order matching your table
        csv_columns = [
            'isin',
            'securityid', 
            'newbsecode',
            'oldbsecode',
            'newnsecode', 
            'oldnsecode',
            'newname',
            'oldname',
            'symbol',
            'sector'
        ]
        
        # Reorder columns to match schema
        final_df = final_df[csv_columns]
        
        # Export to CSV
        final_df.to_csv(output_filename, index=False)
        
        print(f"✅ CSV file generated successfully: {output_filename}")
        print(f"📊 Total records: {len(final_df)}")
        print(f"💾 File size: {os.path.getsize(output_filename) / 1024 / 1024:.2f} MB")
        
        # Show sample of the data
        print("\n📋 Sample data (first 5 rows):")
        print(final_df.head().to_string(index=False))
        
        return True
        
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
        return False
    
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return False

def main():
    """Main function"""
    success = generate_csv()
    
    if success:
        print("\n🎉 Stocklist CSV generation completed successfully!")
    else:
        print("\n❌ Stocklist CSV generation failed.")

if __name__ == "__main__":
    main()