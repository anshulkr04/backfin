"""
Stock Price Data Helper Module for Admin API
Simplified version for refreshing stock price data by security ID
"""

import pandas as pd
import os
import json
import time
from datetime import datetime, date
from supabase import create_client, Client
import requests
import pytz

# Supabase configuration
def get_supabase_client():
    """Get Supabase client using environment variables"""
    supabase_url = os.environ.get("SUPABASE_URL2")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY2")
    return create_client(supabase_url, supabase_key)

# Table names
STOCK_DATA_TABLE = "stockpricedata"
STOCK_CODE_TABLE = "stocklistdata"

# Rate limiting configuration
MAX_RETRIES = 3
RETRY_DELAY = 5
UPLOAD_CHUNK_SIZE = 1500
TIME_OFFSET = 315619200 - 86400  # Approximately 10 years

# Custom JSON encoder
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super(DateTimeEncoder, self).default(obj)


def fetch_and_process_historical_data(symbol, security_id, isin, from_date, to_date, access_token, exchange_segment="NSE_EQ"):
    """Fetch historical data from Dhan API"""
    url = "https://api.dhan.co/charts/historical"
    
    headers = {
        "Content-Type": "application/json",
        "access-token": access_token
    }
    
    data = {
        "symbol": symbol,
        "exchangeSegment": exchange_segment,
        "instrument": "EQUITY",
        "expiryCode": 0,
        "fromDate": from_date,
        "toDate": to_date
    }
    
    print(f"Fetching data for {symbol} (Security ID: {security_id}, ISIN: {isin}) from {from_date} to {to_date} on {exchange_segment}")
    
    # Retry logic
    for retry in range(MAX_RETRIES):
        try:
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code == 429:
                wait_time = (retry + 1) * RETRY_DELAY
                print(f"Rate limit hit, waiting for {wait_time} seconds...")
                time.sleep(wait_time)
                continue
                
            if response.status_code != 200:
                print(f"Error: {response.status_code} - {response.text}")
                if retry < MAX_RETRIES - 1:
                    time.sleep((retry + 1) * RETRY_DELAY)
                    continue
                return None
            
            break
        except Exception as e:
            print(f"Request error: {str(e)}")
            if retry < MAX_RETRIES - 1:
                time.sleep((retry + 1) * RETRY_DELAY)
            else:
                return None
    
    try:
        response_data = response.json()
        
        if not response_data or 'start_Time' not in response_data:
            return None
        
        df = pd.DataFrame(response_data)
        
        # Convert timestamps to dates
        def convert_unix_to_date(unix_timestamp):
            ist_timezone = pytz.timezone('Asia/Kolkata')
            dt_utc = datetime.fromtimestamp(unix_timestamp, pytz.UTC)
            dt_ist = dt_utc.astimezone(ist_timezone)
            return dt_ist
        
        df['adjusted_timestamp'] = df['start_Time'] + TIME_OFFSET
        df['date'] = df['adjusted_timestamp'].apply(lambda ts: convert_unix_to_date(ts).strftime('%Y-%m-%d'))
        
        df['symbol'] = symbol
        df['security_id'] = security_id
        df['isin'] = isin
        
        df = df[['symbol', 'security_id', 'isin', 'close', 'date']]
        df['close'] = df['close'].astype(float)
        
        print(f"Processed {len(df)} records for {symbol} on {exchange_segment}")
        return df
    except Exception as e:
        print(f"Error processing data: {str(e)}")
        return None


def upload_data_to_supabase(supabase, df):
    """Upload DataFrame to Supabase"""
    if df is None or len(df) == 0:
        return False
    
    records = df.to_dict('records')
    total_records = len(records)
    print(f"Prepared {total_records} rows for upload")
    
    if total_records <= UPLOAD_CHUNK_SIZE:
        # Upload all at once
        json_records = json.dumps(records, cls=DateTimeEncoder)
        parsed_records = json.loads(json_records)
        
        for retry in range(MAX_RETRIES):
            try:
                print(f"Uploading all {total_records} records to {STOCK_DATA_TABLE}")
                response = supabase.table(STOCK_DATA_TABLE).insert(parsed_records).execute()
                
                if not (hasattr(response, 'error') and response.error):
                    print(f"Successfully uploaded all {total_records} records!")
                    return True
                
                if retry < MAX_RETRIES - 1:
                    time.sleep((retry + 1) * RETRY_DELAY)
                    
            except Exception as e:
                print(f"Upload error: {str(e)}")
                if retry < MAX_RETRIES - 1:
                    time.sleep((retry + 1) * RETRY_DELAY)
        
        return False
    else:
        # Upload in chunks
        successful_uploads = 0
        
        for i in range(0, total_records, UPLOAD_CHUNK_SIZE):
            chunk = records[i:i+UPLOAD_CHUNK_SIZE]
            chunk_size = len(chunk)
            
            json_records = json.dumps(chunk, cls=DateTimeEncoder)
            parsed_records = json.loads(json_records)
            
            for retry in range(MAX_RETRIES):
                try:
                    print(f"Uploading chunk {i//UPLOAD_CHUNK_SIZE + 1} ({chunk_size} records)")
                    response = supabase.table(STOCK_DATA_TABLE).insert(parsed_records).execute()
                    
                    if not (hasattr(response, 'error') and response.error):
                        successful_uploads += chunk_size
                        break
                        
                    if retry < MAX_RETRIES - 1:
                        time.sleep((retry + 1) * RETRY_DELAY)
                        
                except Exception as e:
                    print(f"Upload error: {str(e)}")
                    if retry < MAX_RETRIES - 1:
                        time.sleep((retry + 1) * RETRY_DELAY)
            
            if i + UPLOAD_CHUNK_SIZE < total_records:
                time.sleep(2)  # Wait between chunks
        
        print(f"Successfully uploaded {successful_uploads} out of {total_records} rows!")
        return successful_uploads > 0


def refresh_stock_price_data_by_security_id(security_id, from_date=None, to_date=None, access_token=None):
    """
    Refresh stock price data for a specific security ID
    
    Args:
        security_id: Security ID to refresh data for (required)
        from_date: Start date in format "YYYY-MM-DD" (default: 2025-01-01)
        to_date: End date in format "YYYY-MM-DD" (default: today)
        access_token: Dhan API access token (uses env var if not provided)
        
    Returns:
        dict: Result with success status, metadata, and error if any
    """
    try:
        supabase = get_supabase_client()
        
        # Get access token
        if not access_token:
            access_token = os.environ.get("DHAN_ACCESS_TOKEN")
            if not access_token:
                return {
                    "success": False,
                    "error": "DHAN_ACCESS_TOKEN not configured",
                    "securityid": security_id
                }
        
        # Set default dates
        if not from_date:
            from_date = "2025-01-01"
        if not to_date:
            to_date = datetime.now().strftime("%Y-%m-%d")
        
        # Query stocklistdata to get stock details
        result = supabase.table(STOCK_CODE_TABLE).select("*").eq("securityid", security_id).execute()
        
        if not result.data or len(result.data) == 0:
            return {
                "success": False,
                "error": f"Security ID {security_id} not found in {STOCK_CODE_TABLE}",
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
        delete_response = supabase.table(STOCK_DATA_TABLE)\
            .delete()\
            .eq("security_id", security_id)\
            .gte("date", from_date)\
            .lte("date", to_date)\
            .execute()
        
        deleted_count = len(delete_response.data) if delete_response.data else 0
        print(f"Deleted {deleted_count} existing records for security ID {security_id}")
        
        # Fetch data from Dhan API
        df = fetch_and_process_historical_data(
            symbol, security_id, isin, from_date, to_date, access_token, exchange_segment
        )
        
        # Upload to Supabase
        success = upload_data_to_supabase(supabase, df)
        
        if success:
            # Count how many records were inserted
            count_response = supabase.table(STOCK_DATA_TABLE)\
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
