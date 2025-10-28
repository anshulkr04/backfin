# import requests
# import pandas as pd
# from io import StringIO
# import pandas as pd
# from supabase import create_client
# import os
# import traceback
# from dotenv import load_dotenv

# load_dotenv()

# # Exchange segment (update as needed)
# exchange_segments = ['BSE_EQ' , 'NSE_EQ']


# for exchange_segment in exchange_segments:
#     # API endpoint
#     url = f'https://api.dhan.co/v2/instrument/{exchange_segment}'

#     # Make the request
#     response = requests.get(url)

#     # Check if the request was successful
#     if response.status_code == 200:
#         try:
#             # Read CSV content from response.text
#             df = pd.read_csv(StringIO(response.text), header=None)
#             df.to_csv(f'{exchange_segment}_instruments.csv', index=False)
#             print(f'Data saved to {exchange_segment}_instruments.csv')
#         except Exception as e:
#             print("Error parsing CSV:", e)
#     else:
#         print("Failed to fetch data:", response.status_code, response.text)


# # Supabase connection details - replace with your actual credentials
# SUPABASE_URL = os.environ.get("SUPABASE_URL2")
# SUPABASE_KEY = os.environ.get("SUPABASE_KEY2")

# def get_databaseStocks():
#     TABLE = "stocklistdata"
#     OUTFILE = "stonks.csv"

#     url = f"{SUPABASE_URL}/rest/v1/{TABLE}?select=*"

#     headers = {
#         "apikey": SUPABASE_KEY,
#         "Authorization": f"Bearer {SUPABASE_KEY}",
#         "Accept": "text/csv"   # request CSV
#     }

#     # Stream to file to avoid high memory usage
#     with requests.get(url, headers=headers, stream=True) as r:
#         r.raise_for_status()
#         with open(OUTFILE, "wb") as f:
#             for chunk in r.iter_content(chunk_size=8192):
#                 if chunk:
#                     f.write(chunk)

#     print(f"Saved CSV to {OUTFILE}")




# if __name__ == "__main__":
#     update_security_ids()

import pandas as pd
import os
import time
import json
from supabase import create_client
from requests.exceptions import RequestException
import concurrent.futures
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Supabase configuration - replace with your actual credentials
SUPABASE_URL = os.getenv("SUPABASE_URL2")
SUPABASE_KEY = os.getenv("SUPABASE_KEY2")

# Constants for retry mechanism
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
BATCH_SIZE = 50  # Process records in batches to prevent connection issues

# Global variables to track progress
processed_isins = set()
progress_file = "stock_data_progress.json"

def initialize_supabase():
    """Initialize and return a new Supabase client"""
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def with_retry(func, *args, **kwargs):
    """Execute a function with retry logic"""
    for attempt in range(MAX_RETRIES):
        try:
            return func(*args, **kwargs)
        except RequestException as e:
            if attempt < MAX_RETRIES - 1:
                print(f"Connection error: {str(e)}. Retrying in {RETRY_DELAY} seconds... (Attempt {attempt+1}/{MAX_RETRIES})")
                time.sleep(RETRY_DELAY * (attempt + 1))  # Exponential backoff
                # Reinitialize the Supabase client
                global supabase
                supabase = initialize_supabase()
            else:
                print(f"Failed after {MAX_RETRIES} attempts: {str(e)}")
                raise
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            raise

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

def check_isin_exists(isin):
    """Check if an ISIN already exists in the database with retry logic"""
    def _check():
        result = supabase.table('testtable').select('*').eq('isin', isin).execute()
        return len(result.data) > 0
    
    return with_retry(_check)

def update_record(isin, data):
    """Update an existing record with retry logic"""
    def _update():
        supabase.table('testtable').update(data).eq('isin', isin).execute()
        return True
    
    return with_retry(_update)

def insert_record(data):
    """Insert a new record with retry logic"""
    def _insert():
        supabase.table('testtable').insert(data).execute()
        return True
    
    return with_retry(_insert)

def process_batch(batch_data, is_nse=True):
    """Process a batch of records"""
    successful = 0
    
    for _, row in batch_data.iterrows():
        isin = row['ISIN']
        
        # Skip if already processed
        if isin in processed_isins:
            print(f"Skipping already processed ISIN: {isin}")
            continue
            
        try:
            if is_nse:
                process_nse_record(row)
            else:
                process_bse_record(row)
                
            processed_isins.add(isin)
            successful += 1
            
            # Print progress every 10 records
            if successful % 10 == 0:
                print(f"Successfully processed {successful} records in current batch")
                
        except Exception as e:
            print(f"Error processing {'NSE' if is_nse else 'BSE'} record for ISIN {isin}: {str(e)}")
    
    return successful

def process_nse_record(row):
    """Process a single NSE record"""
    isin = row['ISIN']
    nsecode = row['UNDERLYING_SYMBOL']
    display_name = row['DISPLAY_NAME']
    security_id = row['SECURITY_ID']
    
    # Check if record exists
    exists = check_isin_exists(isin)
    
    if exists:
        # Update existing record
        update_record(isin, {
            'newnsecode': nsecode,
            'newname': display_name,
            'securityid': security_id
        })
        print(f"Updated NSE data for ISIN: {isin}")
    else:
        # Insert new record
        insert_record({
            'isin': isin,
            'newnsecode': nsecode,
            'newname': display_name,
            'securityid': security_id
        })
        print(f"Inserted new NSE record for ISIN: {isin}")

def process_bse_record(row):
    """Process a single BSE record"""
    isin = row['ISIN']
    bsecode = row['UNDERLYING_SYMBOL']
    display_name = row['DISPLAY_NAME']
    security_id = row['SECURITY_ID']
    
    # Check if record exists
    exists = check_isin_exists(isin)
    
    if exists:
        # Update existing record - only update the BSE code
        update_record(isin, {
            'newbsecode': bsecode
        })
        print(f"Updated BSE code for existing ISIN: {isin}")
    else:
        # Insert new record
        insert_record({
            'isin': isin,
            'newbsecode': bsecode,
            'newname': display_name,
            'securityid': security_id
        })
        print(f"Inserted new BSE record for ISIN: {isin}")

def process_nse_data(nse_file_path):
    """
    Process NSE CSV file and update Supabase table.
    
    Filter conditions:
    - ISIN starts with 'INE' and INSTRUMENT_TYPE is 'ES'
    - OR ISIN starts with 'INE' and INSTRUMENT_TYPE is 'Other' and SERIES is 'EQ'
    """
    print(f"Processing NSE data from {nse_file_path}...")
    
    try:
        # Read the CSV file
        df = pd.read_csv(nse_file_path)
        
        # Filter data based on conditions
        filtered_df = df[
            ((df['ISIN'].str.startswith('INE')) & (df['INSTRUMENT_TYPE'] == 'ES')) |
            ((df['ISIN'].str.startswith('INE')) & (df['INSTRUMENT_TYPE'] == 'Other') & (df['SERIES'] == 'EQ'))
        ]
        
        total_records = len(filtered_df)
        print(f"Found {total_records} eligible NSE records.")
        
        if total_records == 0:
            return 0
            
        # Process in batches
        processed_count = 0
        for i in range(0, total_records, BATCH_SIZE):
            batch_df = filtered_df.iloc[i:i+BATCH_SIZE]
            print(f"Processing NSE batch {i//BATCH_SIZE + 1}/{(total_records + BATCH_SIZE - 1)//BATCH_SIZE} ({len(batch_df)} records)")
            
            batch_processed = process_batch(batch_df, is_nse=True)
            processed_count += batch_processed
            
            # Save progress after each batch
            save_progress()
            
            # Sleep briefly to prevent overwhelming the server
            if i + BATCH_SIZE < total_records:
                print(f"Sleeping for 1 second before next batch...")
                time.sleep(1)
        
        return processed_count
    
    except Exception as e:
        print(f"Error processing NSE data: {str(e)}")
        return 0

def process_bse_data(bse_file_path):
    """
    Process BSE CSV file and update Supabase table.
    
    Filter condition:
    - ISIN starts with 'INE' and INSTRUMENT_TYPE is 'ES'
    
    Update logic:
    - If ISIN exists, update newbsecode only
    - If ISIN doesn't exist, create new row
    """
    print(f"Processing BSE data from {bse_file_path}...")
    
    try:
        # Read the CSV file
        df = pd.read_csv(bse_file_path)
        
        # Filter data based on conditions
        filtered_df = df[
            (df['ISIN'].str.startswith('INE')) & (df['INSTRUMENT_TYPE'] == 'ES')
        ]
        
        total_records = len(filtered_df)
        print(f"Found {total_records} eligible BSE records.")
        
        if total_records == 0:
            return 0
            
        # Process in batches
        processed_count = 0
        for i in range(0, total_records, BATCH_SIZE):
            batch_df = filtered_df.iloc[i:i+BATCH_SIZE]
            print(f"Processing BSE batch {i//BATCH_SIZE + 1}/{(total_records + BATCH_SIZE - 1)//BATCH_SIZE} ({len(batch_df)} records)")
            
            batch_processed = process_batch(batch_df, is_nse=False)
            processed_count += batch_processed
            
            # Save progress after each batch
            save_progress()
            
            # Sleep briefly to prevent overwhelming the server
            if i + BATCH_SIZE < total_records:
                print(f"Sleeping for 1 second before next batch...")
                time.sleep(1)
        
        return processed_count
    
    except Exception as e:
        print(f"Error processing BSE data: {str(e)}")
        return 0

def main():
    # File paths - update these to your actual file paths
    nse_file_path = "NSE_EQ_instruments.csv"
    bse_file_path = "BSE_EQ_instruments.csv"
    
    # Check if files exist
    if not os.path.exists(nse_file_path):
        print(f"NSE file not found: {nse_file_path}")
        return
    
    if not os.path.exists(bse_file_path):
        print(f"BSE file not found: {bse_file_path}")
        return
    
    # Initialize Supabase client
    global supabase
    supabase = initialize_supabase()
    
    # Load progress if any
    load_progress()
    
    try:
        # Process NSE data first
        nse_count = process_nse_data(nse_file_path)
        print(f"Processed {nse_count} NSE records.")
        
        # Then process BSE data
        bse_count = process_bse_data(bse_file_path)
        print(f"Processed {bse_count} BSE records.")
        
        print("Data processing complete.")
        
    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Saving progress...")
        save_progress()
        print("You can resume later from where you left off.")
    
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        print("Saving progress...")
        save_progress()
        print("You can resume later from where you left off.")

if __name__ == "__main__":
    main()



