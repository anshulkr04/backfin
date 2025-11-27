import pandas as pd
import os
import json
import time
from datetime import datetime, date, timedelta
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Supabase configuration
supabase_url = os.environ.get("SUPABASE_URL2")
supabase_key = os.environ.get("SUPABASE_KEY2")
stock_data_table = "stockpricedata"  # The target table for price data
stock_code_table = "stocklistdata"  # The table with stock codes and security IDs

# Set specific date range
from_date = "2025-06-29"  # 29th June 2025
to_date = "2025-11-27"    # 27th November 2025

# Rate limiting configuration
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds between retries
BATCH_SIZE = 1000  # Number of records to process in a batch
BATCH_DELAY = 2  # seconds between batches
UPLOAD_CHUNK_SIZE = 1500  # Number of records to upload at once

# Custom JSON encoder to handle date objects
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super(DateTimeEncoder, self).default(obj)

# Function to fetch historical data from Dhan API
def fetch_and_process_historical_data(symbol, security_id, isin, from_date, to_date, access_token, exchange_segment="NSE_EQ"):
    import requests
    import pytz
    
    # API endpoint URL
    url = "https://api.dhan.co/charts/historical"
    
    # Headers
    headers = {
        "Content-Type": "application/json",
        "access-token": access_token
    }
    
    # Request parameters
    data = {
        "symbol": symbol,
        "exchangeSegment": exchange_segment,  # This can be NSE_EQ or BSE_EQ
        "instrument": "EQUITY",
        "expiryCode": 0,
        "fromDate": from_date,
        "toDate": to_date
    }
    
    # Time offset to add (in seconds)
    TIME_OFFSET = 315619200-86400  # Approximately 10 years
    
    print(f"Fetching data for {symbol} (Security ID: {security_id}, ISIN: {isin}) from {from_date} to {to_date} on {exchange_segment}")
    
    # Add retry logic for Dhan API
    for retry in range(MAX_RETRIES):
        try:
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code == 429:  # Too Many Requests
                wait_time = (retry + 1) * RETRY_DELAY
                print(f"Rate limit hit, waiting for {wait_time} seconds...")
                time.sleep(wait_time)
                continue
                
            if response.status_code != 200:
                print(f"Error: {response.status_code}")
                print(response.text)
                if retry < MAX_RETRIES - 1:
                    wait_time = (retry + 1) * RETRY_DELAY
                    print(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                return None
            
            break  # Success, exit retry loop
        except Exception as e:
            print(f"Request error: {str(e)}")
            if retry < MAX_RETRIES - 1:
                wait_time = (retry + 1) * RETRY_DELAY
                print(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                return None
    
    try:
        response_data = response.json()
        
        if not response_data or 'start_Time' not in response_data:
            return None
        
        # Create a DataFrame from the response
        df = pd.DataFrame(response_data)
        
        # Add offset to timestamps and convert to dates
        def convert_unix_to_date(unix_timestamp):
            ist_timezone = pytz.timezone('Asia/Kolkata')
            dt_utc = datetime.fromtimestamp(unix_timestamp, pytz.UTC)
            dt_ist = dt_utc.astimezone(ist_timezone)
            return dt_ist
        
        # Add adjusted date
        df['adjusted_timestamp'] = df['start_Time'] + TIME_OFFSET
        df['date'] = df['adjusted_timestamp'].apply(lambda ts: convert_unix_to_date(ts).strftime('%Y-%m-%d'))
        
        # Add symbol, security_id, and isin columns
        df['symbol'] = symbol
        df['security_id'] = security_id
        df['isin'] = isin  # Include ISIN
        
        # Keep only required columns that match the table structure
        df = df[['symbol', 'security_id', 'isin', 'close', 'date']]
        
        # Ensure all columns are using primitive types for JSON serialization
        df['close'] = df['close'].astype(float)
        
        print(f"Processed {len(df)} records for {symbol} on {exchange_segment}")
        return df
    except Exception as e:
        print(f"Error processing data: {str(e)}")
        return None

# Upload data directly from API to Supabase with retry logic
def upload_historical_data_to_supabase(symbol, security_id, isin, from_date, to_date, access_token, exchange_segment="NSE_EQ"):
    """
    Fetch historical data from Dhan API and upload directly to Supabase
    
    Args:
        symbol: Stock symbol (e.g., "TCS")
        security_id: Security ID for the stock
        isin: International Securities Identification Number
        from_date: Start date in format "YYYY-MM-DD"
        to_date: End date in format "YYYY-MM-DD"
        access_token: Dhan API access token
        exchange_segment: Exchange segment (NSE_EQ or BSE_EQ)
        
    Returns:
        bool: True if upload was successful, False otherwise
    """
    try:
        # Initialize Supabase client
        supabase = create_client(supabase_url, supabase_key)
        
        # Fetch and process data
        df = fetch_and_process_historical_data(symbol, security_id, isin, from_date, to_date, access_token, exchange_segment)
        
        if df is None or len(df) == 0:
            print(f"No data retrieved for {symbol} on {exchange_segment}")
            return False
        
        # Convert DataFrame to list of dictionaries
        records = df.to_dict('records')
        total_records = len(records)
        print(f"Prepared {total_records} rows for upload")
        
        # Handle the case where there are fewer records than UPLOAD_CHUNK_SIZE
        if total_records <= UPLOAD_CHUNK_SIZE:
            # Upload all records at once
            json_records = json.dumps(records, cls=DateTimeEncoder)
            parsed_records = json.loads(json_records)
            
            for retry in range(MAX_RETRIES):
                try:
                    print(f"Uploading all {total_records} records to Supabase table: {stock_data_table}")
                    response = supabase.table(stock_data_table).insert(parsed_records).execute()
                    
                    if not (hasattr(response, 'error') and response.error):
                        print(f"Successfully uploaded all {total_records} records for {symbol} on {exchange_segment}!")
                        return True
                    
                    print(f"Error uploading to Supabase: {response.error}")
                    if retry < MAX_RETRIES - 1:
                        wait_time = (retry + 1) * RETRY_DELAY
                        print(f"Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        print(f"Failed to upload after {MAX_RETRIES} attempts")
                        return False
                        
                except Exception as e:
                    print(f"Upload error: {str(e)}")
                    if retry < MAX_RETRIES - 1:
                        wait_time = (retry + 1) * RETRY_DELAY
                        print(f"Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        return False
        else:
            # Process in chunks for larger datasets
            successful_uploads = 0
            
            # Upload in chunks
            for i in range(0, total_records, UPLOAD_CHUNK_SIZE):
                chunk = records[i:i+UPLOAD_CHUNK_SIZE]
                chunk_size = len(chunk)
                
                # Upload to Supabase
                json_records = json.dumps(chunk, cls=DateTimeEncoder)
                parsed_records = json.loads(json_records)
                
                # Retry logic for Supabase uploads
                for retry in range(MAX_RETRIES):
                    try:
                        print(f"Uploading chunk {i//UPLOAD_CHUNK_SIZE + 1} ({chunk_size} records) to Supabase table: {stock_data_table}")
                        response = supabase.table(stock_data_table).insert(parsed_records).execute()
                        
                        # If we got a response with no error, break out of retry loop
                        if not (hasattr(response, 'error') and response.error):
                            successful_uploads += chunk_size
                            break
                            
                        # Handle rate limit or other errors
                        print(f"Error uploading to Supabase: {response.error}")
                        if retry < MAX_RETRIES - 1:
                            wait_time = (retry + 1) * RETRY_DELAY
                            print(f"Retrying in {wait_time} seconds...")
                            time.sleep(wait_time)
                        else:
                            print(f"Failed to upload chunk after {MAX_RETRIES} attempts")
                            
                    except Exception as e:
                        print(f"Upload error: {str(e)}")
                        if retry < MAX_RETRIES - 1:
                            wait_time = (retry + 1) * RETRY_DELAY
                            print(f"Retrying in {wait_time} seconds...")
                            time.sleep(wait_time)
                
                # Wait between chunks to respect rate limits, but only if there's more to process
                if i + UPLOAD_CHUNK_SIZE < total_records:
                    print(f"Waiting {BATCH_DELAY} seconds before next chunk...")
                    time.sleep(BATCH_DELAY)
            
            print(f"Successfully uploaded {successful_uploads} out of {total_records} rows to Supabase for {symbol} on {exchange_segment}!")
            return successful_uploads > 0
            
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

# Function to refresh stock price data for a specific security ID (for API endpoint)
def refresh_stock_price_data_by_security_id(security_id, from_date=None, to_date=None, access_token=None):
    """
    Refresh stock price data for a specific security ID
    This function is designed to be imported by admin API endpoints
    
    Args:
        security_id: Security ID to refresh data for (required)
        from_date: Start date in format "YYYY-MM-DD" (default: 2025-01-01)
        to_date: End date in format "YYYY-MM-DD" (default: today)
        access_token: Dhan API access token (uses env var if not provided)
        
    Returns:
        dict: Result with success status, metadata, and error if any
    """
    try:
        # Initialize Supabase client
        supabase = create_client(supabase_url, supabase_key)
        
        # Get access token
        if not access_token:
            access_token = os.environ.get("DHAN_ACCESS_TOKEN")
            if not access_token:
                return {
                    "success": False,
                    "error": "DHAN_ACCESS_TOKEN not configured",
                    "securityid": security_id
                }
        
        # Set default dates if not provided
        if not from_date:
            from_date = "2025-01-01"
        if not to_date:
            to_date = datetime.now().strftime("%Y-%m-%d")
        
        # Query stocklistdata to get stock details
        result = supabase.table(stock_code_table).select("*").eq("securityid", security_id).execute()
        
        if not result.data or len(result.data) == 0:
            return {
                "success": False,
                "error": f"Security ID {security_id} not found in {stock_code_table}",
                "securityid": security_id
            }
        
        stock = result.data[0]
        
        # Determine exchange and symbol (BSE priority)
        bse_code = stock.get('newbsecode')
        nse_code = stock.get('newnsecode')
        isin = stock.get('isin', '')
        
        if bse_code:
            symbol = bse_code
            exchange_segment = "BSE_EQ"
        elif nse_code:
            symbol = nse_code
            exchange_segment = "NSE_EQ"
        else:
            return {
                "success": False,
                "error": f"No valid exchange code found for security ID {security_id}",
                "securityid": security_id,
                "isin": isin
            }
        
        print(f"Refreshing stock price data for security ID {security_id}: {symbol} on {exchange_segment}")
        
        # Delete existing records for this security_id in the date range
        delete_response = supabase.table(stock_data_table)\
            .delete()\
            .eq("security_id", security_id)\
            .gte("date", from_date)\
            .lte("date", to_date)\
            .execute()
        
        deleted_count = len(delete_response.data) if delete_response.data else 0
        print(f"Deleted {deleted_count} existing records for security ID {security_id}")
        
        # Fetch and upload new data
        success = upload_historical_data_to_supabase(
            symbol, security_id, isin, from_date, to_date, access_token, exchange_segment
        )
        
        if success:
            # Count how many records were inserted
            count_response = supabase.table(stock_data_table)\
                .select("date", count="exact")\
                .eq("security_id", security_id)\
                .gte("date", from_date)\
                .lte("date", to_date)\
                .execute()
            
            records_count = count_response.count if hasattr(count_response, 'count') else 0
            
            return {
                "success": True,
                "securityid": security_id,
                "symbol": symbol,
                "isin": isin,
                "exchange": exchange_segment,
                "records_fetched": records_count,
                "from_date": from_date,
                "to_date": to_date,
                "error": None
            }
        else:
            return {
                "success": False,
                "error": "Failed to fetch or upload data from Dhan API",
                "securityid": security_id,
                "symbol": symbol,
                "isin": isin,
                "exchange": exchange_segment
            }
            
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error refreshing stock price data: {str(e)}")
        print(error_trace)
        return {
            "success": False,
            "error": str(e),
            "securityid": security_id
        }

# Function to process all records in the NseBseCode table
def process_all_stock_codes(start_offset=0):
    try:
        # Initialize Supabase client
        supabase = create_client(supabase_url, supabase_key)
        
        # Get access token for Dhan API
        access_token = os.environ.get("DHAN_ACCESS_TOKEN")
        if not access_token:
            print("Error: DHAN_ACCESS_TOKEN environment variable is not set")
            return False
        
        # Get total count of records
        count_response = supabase.table(stock_code_table).select("count", count="exact").execute()
        total_records = count_response.count if hasattr(count_response, 'count') else 0
        
        print(f"Total records in {stock_code_table} table: {total_records}")
        print(f"Using date range: {from_date} to {to_date}")
        
        # Process in batches to handle rate limits
        offset = start_offset
        processed_total = 0
        skipped_total = 0
        success_total = 0
        
        # Look for possible security ID field names (case-insensitive matching)
        security_id_fields = ['securityid', 'securityID', 'security_id', 'SecurityID', 'security_ID', 'securityId']
        
        # Look for possible ISIN field names
        isin_fields = ['isin', 'ISIN', 'Isin']
        
        # Look for possible NSE and BSE code field names
        nse_code_fields = ['newnsecode', 'NewNSEcode', 'NSECode', 'nsecode', 'nse_code']
        bse_code_fields = ['newbsecode', 'NewBSEcode', 'BSECode', 'bsecode', 'bse_code']
        
        # Get sample record to debug field names
        sample_response = supabase.table(stock_code_table).select("*").limit(1).execute()
        if sample_response.data and len(sample_response.data) > 0:
            print(f"Available fields in sample record: {list(sample_response.data[0].keys())}")
            print(f"Sample record data: {json.dumps(sample_response.data[0], indent=2, default=str)}")
        
        # Process in batches
        while offset < total_records:
            try:
                batch_size = min(BATCH_SIZE, total_records - offset)
                
                # Save current offset as checkpoint
                save_checkpoint(offset)
                
                # Get a batch of records
                response = supabase.table(stock_code_table).select("*").range(offset, offset + batch_size - 1).execute()
                records = response.data
                
                if not records or len(records) == 0:
                    print(f"No records returned for range {offset} to {offset + batch_size - 1}")
                    break
                    
                print(f"\n--- Processing batch of {len(records)} records (offset: {offset}/{total_records}) ---")
                
                processed_count = 0
                skipped_count = 0
                success_count = 0
                
                # Process each record in the batch
                for record in records:
                    # Try to find security ID using multiple potential field names
                    security_id = None
                    for field in security_id_fields:
                        if field in record and record[field]:
                            security_id = record[field]
                            break
                            
                    if not security_id:
                        record_id = record.get('id', 'unknown')
                        print(f"Skipping record {record_id} - missing securityID")
                        skipped_count += 1
                        continue
                    
                    # Get ISIN (use empty string if not available)
                    isin = ''
                    for field in isin_fields:
                        if field in record and record[field]:
                            isin = record[field]
                            break
                    
                    # Try to find NSE code
                    nse_code = None
                    for field in nse_code_fields:
                        if field in record and record[field]:
                            nse_code = record[field]
                            break
                            
                    # Try to find BSE code
                    bse_code = None
                    for field in bse_code_fields:
                        if field in record and record[field]:
                            bse_code = record[field]
                            break
                    
                    if nse_code:
                        # Use NSE code and exchange
                        symbol = nse_code
                        exchange_segment = "NSE_EQ"
                        print(f"Processing NSE stock: {symbol}")
                        success = upload_historical_data_to_supabase(
                            symbol, security_id, isin, from_date, to_date, access_token, exchange_segment)
                        
                        if success:
                            success_count += 1
                        processed_count += 1
                        
                    elif bse_code:
                        # Use BSE code and exchange
                        symbol = bse_code
                        exchange_segment = "BSE_EQ"
                        print(f"Processing BSE stock: {symbol}")
                        success = upload_historical_data_to_supabase(
                            symbol, security_id, isin, from_date, to_date, access_token, exchange_segment)
                        
                        if success:
                            success_count += 1
                        processed_count += 1
                        
                    else:
                        record_id = record.get('id', 'unknown')
                        print(f"Skipping record {record_id} - no valid exchange code")
                        skipped_count += 1
                
                # Update totals
                processed_total += processed_count
                skipped_total += skipped_count
                success_total += success_count
                
                print(f"Batch results - Processed: {processed_count}, Successful: {success_count}, Skipped: {skipped_count}")
                
                # Move to next batch
                offset += len(records)
                
                # Save updated checkpoint
                save_checkpoint(offset)
                
                # Wait between batches to respect rate limits, but only if there's more to process
                if offset < total_records:
                    print(f"Waiting {BATCH_DELAY} seconds before next batch...")
                    time.sleep(BATCH_DELAY)
                    
            except Exception as e:
                print(f"Error processing batch: {str(e)}")
                import traceback
                traceback.print_exc()
                
                # Continue with next batch despite errors
                offset += batch_size
                save_checkpoint(offset)  # Save checkpoint even after error
                
                print(f"Continuing with next batch at offset {offset}")
                time.sleep(BATCH_DELAY * 2)  # Wait longer after error
        
        print(f"\nProcessing complete. Total: {total_records}, Processed: {processed_total}, "
              f"Successful: {success_total}, Skipped: {skipped_total}")
        return True
        
    except Exception as e:
        print(f"Error processing stock codes: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

# Create a checkpoint system to resume from where it left off
def save_checkpoint(offset):
    with open('stock_processing_checkpoint.txt', 'w') as f:
        f.write(str(offset))
        
def load_checkpoint():
    try:
        with open('stock_processing_checkpoint.txt', 'r') as f:
            return int(f.read().strip())
    except:
        return 0

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Process stock data from NseBseCode and upload to stockpricedata')
    parser.add_argument('--from-date', help='Start date in format YYYY-MM-DD')
    parser.add_argument('--to-date', help='End date in format YYYY-MM-DD')
    parser.add_argument('--batch-size', type=int, help='Number of records to process in each batch')
    parser.add_argument('--batch-delay', type=int, help='Seconds to wait between batches')
    parser.add_argument('--upload-chunk-size', type=int, help='Number of records to upload at once')
    parser.add_argument('--resume', action='store_true', help='Resume from last checkpoint')
    
    args = parser.parse_args()
    
    # Update configuration if provided via command line
    if args.from_date:
        from_date = args.from_date
    if args.to_date:
        to_date = args.to_date
    if args.batch_size:
        BATCH_SIZE = args.batch_size
    if args.batch_delay:
        BATCH_DELAY = args.batch_delay
    if args.upload_chunk_size:
        UPLOAD_CHUNK_SIZE = args.upload_chunk_size
        
    print(f"Processing stock data for date range: {from_date} to {to_date}")
    print(f"Using batch size: {BATCH_SIZE}, batch delay: {BATCH_DELAY} seconds")
    print(f"Upload chunk size: {UPLOAD_CHUNK_SIZE}")
    
    start_offset = 0
    if args.resume:
        start_offset = load_checkpoint()
        print(f"Resuming from offset: {start_offset}")
    
    success = process_all_stock_codes(start_offset)
    
    if success:
        print("Processing completed successfully")
    else:
        print("Processing failed")