import requests
import json
import time
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging
import os
import pandas as pd
from decimal import Decimal
import math

# Optional: load env from .env if you use that
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

class NSECorporateScraper:
    """
    NSE Corporate PIT Data Scraper with advanced cookie acquisition.
    Handles Akamai Bot Manager and other anti-bot protections.
    """
    
    def __init__(self):
        self.base_url = "https://www.nseindia.com"
        self.session = requests.Session()
        self.setup_logging()
        self.setup_session()
    
    def setup_logging(self):
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def setup_session(self):
        """Setup session with headers that match working browser requests."""
        # Use the exact headers from your working curl command
        self.session.headers.update({
            'accept': '*/*',
            'accept-encoding': 'gzip, deflate, br, zstd',
            'accept-language': 'en-US,en;q=0.9,hi;q=0.8',
            'priority': 'u=1, i',
            'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'
        })
        self.session.timeout = 30
    
    def random_delay(self, min_sec=1, max_sec=3):
        """Random delay to appear more human."""
        time.sleep(random.uniform(min_sec, max_sec))
    
    def establish_session(self) -> bool:
        """
        Establish a proper session by visiting NSE pages in sequence.
        This is the key to getting the right cookies.
        """
        try:
            self.logger.info("🚀 Starting NSE session establishment...")
            
            # Step 1: Visit homepage with document navigation headers
            self.logger.info("📍 Step 1: Visiting NSE homepage...")
            homepage_headers = {
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'sec-fetch-dest': 'document',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-site': 'none',
                'sec-fetch-user': '?1',
                'upgrade-insecure-requests': '1'
            }
            
            response = self.session.get(self.base_url, headers=homepage_headers)
            if response.status_code != 200:
                self.logger.error(f"❌ Homepage failed: {response.status_code}")
                return False
                
            self.logger.info(f"✅ Homepage loaded. Cookies: {len(self.session.cookies)}")
            self.random_delay(2, 4)
            
            # Step 2: Visit market data to trigger authentication
            self.logger.info("📍 Step 2: Visiting market data page...")
            market_headers = {
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'sec-fetch-dest': 'document',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-site': 'same-origin',
                'referer': self.base_url
            }
            
            self.session.get(f"{self.base_url}/market-data", headers=market_headers)
            self.random_delay(2, 4)
            
            # Step 3: Visit companies listing
            self.logger.info("📍 Step 3: Visiting companies listing...")
            companies_headers = {
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'sec-fetch-dest': 'document',
                'sec-fetch-mode': 'navigate', 
                'sec-fetch-site': 'same-origin',
                'referer': f"{self.base_url}/market-data"
            }
            
            self.session.get(f"{self.base_url}/companies-listing", headers=companies_headers)
            self.random_delay(2, 4)
            
            # Step 4: Visit corporate filings page (CRITICAL)
            self.logger.info("📍 Step 4: Visiting corporate filings page...")
            corporate_headers = {
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'sec-fetch-dest': 'document',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-site': 'same-origin',
                'referer': f"{self.base_url}/companies-listing"
            }
            
            response = self.session.get(
                f"{self.base_url}/companies-listing/corporate-filings-insider-trading",
                headers=corporate_headers
            )
            
            if response.status_code != 200:
                self.logger.error(f"❌ Corporate filings page failed: {response.status_code}")
                return False
                
            self.logger.info(f"✅ Corporate filings loaded. Total cookies: {len(self.session.cookies)}")
            self.random_delay(3, 6)
            
            # Step 5: Make a test API call to warm up the session
            self.logger.info("📍 Step 5: Testing session with simple API...")
            test_headers = {
                'accept': '*/*',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'referer': f"{self.base_url}/companies-listing/corporate-filings-insider-trading"
            }
            
            try:
                test_response = self.session.get(
                    f"{self.base_url}/api/equity-master",
                    headers=test_headers,
                    timeout=15
                )
                self.logger.info(f"🧪 Test API response: {test_response.status_code}")
            except:
                self.logger.info("🧪 Test API failed, continuing...")
            
            self.random_delay(2, 4)
            
            # Log final cookie status
            all_cookies = list(self.session.cookies.keys())
            self.logger.info(f"🍪 Session ready. Total cookies: {len(all_cookies)}")
            
            # Check for important cookies
            important_cookies = ['nsit', 'nseappid', 'bm_sz', '_abck']
            found_important = [c for c in important_cookies if c in all_cookies]
            self.logger.info(f"🔑 Important cookies found: {found_important}")
            
            return len(all_cookies) > 0  # Return True if we have any cookies
            
        except Exception as e:
            self.logger.error(f"❌ Session establishment failed: {str(e)}")
            return False
    
    def scrape_corporate_pit_data(self, from_date: str, to_date: str) -> Optional[Dict[Any, Any]]:
        """
        Scrape corporate PIT data from NSE API.
        """
        try:
            # Establish session first
            if not self.establish_session():
                self.logger.error("❌ Failed to establish session")
                return None
            
            # Format dates (ensure DD-MM-YYYY format)
            from_date = self.format_date(from_date)
            to_date = self.format_date(to_date)
            
            # Prepare API call
            api_url = f"{self.base_url}/api/corporates-pit"
            params = {
                'index': 'equities',
                'from_date': from_date,
                'to_date': to_date
            }
            
            # Use the exact headers from your working request
            api_headers = {
                'accept': '*/*',
                'accept-encoding': 'gzip, deflate, br, zstd',
                'accept-language': 'en-US,en;q=0.9,hi;q=0.8',
                'priority': 'u=1, i',
                'referer': 'https://www.nseindia.com/companies-listing/corporate-filings-insider-trading',
                'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"macOS"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin'
            }
            
            self.logger.info(f"🎯 Making API call: {from_date} to {to_date}")
            self.logger.info(f"🔗 URL: {api_url}")
            
            # Make the API request
            response = self.session.get(api_url, params=params, headers=api_headers)
            
            self.logger.info(f"📊 API Response: {response.status_code}")
            
            if response.status_code == 200:
                self.logger.info(f"📄 Response content type: {response.headers.get('content-type', 'unknown')}")
                self.logger.info(f"📏 Response text length: {len(response.text)} characters")
                self.logger.info(f"📦 Response content length: {len(response.content)} bytes")
                self.logger.info(f"🗜️ Content encoding: {response.headers.get('content-encoding', 'none')}")
                
                try:
                    # First, try normal JSON parsing
                    data = response.json()
                    
                    # Handle empty or null responses
                    if data is None:
                        self.logger.info("📭 API returned null data")
                        return None
                    
                    # Count records based on data structure
                    if isinstance(data, dict):
                        if 'data' in data:
                            count = len(data['data']) if data['data'] else 0
                        else:
                            count = 1 if data else 0
                    elif isinstance(data, list):
                        count = len(data)
                    else:
                        count = 1 if data else 0
                    
                    if count > 0:
                        self.logger.info(f"✅ SUCCESS! Retrieved {count} records")
                    else:
                        self.logger.info("📭 No data available for the requested date range")
                    
                    return data
                    
                except json.JSONDecodeError as e:
                    self.logger.info(f"🔧 JSON parsing failed, trying compression handling...")
                    
                    # Work with raw bytes to avoid encoding issues
                    raw_content = response.content
                    self.logger.info(f"📦 Raw content first 20 bytes (hex): {raw_content[:20].hex()}")
                    
                    # Try different decompression methods
                    decompressed_text = None
                    
                    # Method 1: Try GZIP
                    try:
                        import gzip
                        decompressed = gzip.decompress(raw_content)
                        decompressed_text = decompressed.decode('utf-8')
                        self.logger.info(f"✅ GZIP decompression successful!")
                    except Exception as e:
                        self.logger.info(f"❌ GZIP failed: {str(e)}")
                    
                    # Method 2: Try DEFLATE if GZIP failed
                    if decompressed_text is None:
                        try:
                            import zlib
                            decompressed = zlib.decompress(raw_content)
                            decompressed_text = decompressed.decode('utf-8')
                            self.logger.info(f"✅ DEFLATE decompression successful!")
                        except Exception as e:
                            self.logger.info(f"❌ DEFLATE failed: {str(e)}")
                    
                    # Method 3: Try DEFLATE with -15 window size (raw deflate)
                    if decompressed_text is None:
                        try:
                            import zlib
                            decompressed = zlib.decompress(raw_content, -15)
                            decompressed_text = decompressed.decode('utf-8')
                            self.logger.info(f"✅ Raw DEFLATE decompression successful!")
                        except Exception as e:
                            self.logger.info(f"❌ Raw DEFLATE failed: {str(e)}")
                    
                    # Method 4: Try Brotli if available
                    if decompressed_text is None:
                        try:
                            import brotli
                            decompressed = brotli.decompress(raw_content)
                            decompressed_text = decompressed.decode('utf-8')
                            self.logger.info(f"✅ Brotli decompression successful!")
                        except ImportError:
                            self.logger.info("📋 Brotli not available (pip install brotli)")
                        except Exception as e:
                            self.logger.info(f"❌ Brotli failed: {str(e)}")
                    
                    # Method 5: Try different encodings on raw content
                    if decompressed_text is None:
                        self.logger.info("🔧 Trying different encodings...")
                        for encoding in ['latin1', 'iso-8859-1', 'cp1252', 'utf-16', 'utf-32']:
                            try:
                                decompressed_text = raw_content.decode(encoding)
                                self.logger.info(f"✅ Encoding {encoding} worked!")
                                break
                            except Exception as e:
                                self.logger.info(f"❌ Encoding {encoding} failed: {str(e)}")
                    
                    # If we got decompressed text, try to parse as JSON
                    if decompressed_text:
                        self.logger.info(f"📏 Decompressed length: {len(decompressed_text)} characters")
                        self.logger.info(f"📝 Decompressed preview: {decompressed_text[:200]}...")
                        
                        try:
                            data = json.loads(decompressed_text)
                            count = len(data) if isinstance(data, list) else 1
                            self.logger.info(f"🎉 SUCCESS! Retrieved {count} records after decompression")
                            return data
                        except json.JSONDecodeError as json_err:
                            self.logger.error(f"❌ Decompressed content is not valid JSON: {str(json_err)}")
                            self.logger.error(f"📋 Content sample: {decompressed_text[:300]}...")
                    
                    # Last resort: Check if response is actually empty/no data
                    if len(raw_content) == 0:
                        self.logger.info("📭 Response is completely empty - no data for this date range")
                        return []
                    else:
                        self.logger.error("❌ All decompression methods failed")
                        self.logger.error(f"🔢 Raw bytes sample: {raw_content[:50]}")
                        
                    return None
            else:
                self.logger.error(f"❌ API failed: {response.status_code}")
                self.logger.error(f"Response preview: {response.text[:200]}...")
                
                if response.status_code == 401:
                    self.logger.error("🔒 401 Unauthorized - NSE rejected the request")
                    self.logger.error("💡 This usually means anti-bot protection detected automation")
                elif response.status_code == 403:
                    self.logger.error("🚫 403 Forbidden - Access denied")
                elif response.status_code == 429:
                    self.logger.error("⏰ 429 Rate Limited - Too many requests")
                
                return None
                
        except Exception as e:
            self.logger.error(f"❌ Scraping failed: {str(e)}")
            return None
    
    def format_date(self, date_str: str) -> str:
        """Ensure date is in DD-MM-YYYY format."""
        try:
            for fmt in ('%d-%m-%Y', '%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d'):
                try:
                    date_obj = datetime.strptime(date_str, fmt)
                    return date_obj.strftime('%d-%m-%Y')
                except ValueError:
                    continue
            return date_str
        except:
            return date_str
    
    def save_to_json(self, data: Dict[Any, Any], filename: str = None) -> bool:
        """Save data to JSON file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"nse_corporate_pit_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.logger.info(f"💾 Data saved to {filename}")
            return True
        except Exception as e:
            self.logger.error(f"❌ Save failed: {str(e)}")
            return False
    
    def process_nse_data_for_upload(self, data: Dict[Any, Any]) -> pd.DataFrame:
        """Process NSE data into a standardized format for database upload."""
        if not data:
            self.logger.warning("No data provided to process")
            return pd.DataFrame()
        
        # Handle different data structures
        if isinstance(data, dict):
            if 'data' in data:
                records = data['data']
            else:
                # If no 'data' key, treat the dict as a single record
                records = [data]
        elif isinstance(data, list):
            records = data
        else:
            self.logger.warning("Invalid data format for processing")
            return pd.DataFrame()
        
        # Check if records is empty or None
        if not records:
            self.logger.info("No records found in data")
            return pd.DataFrame()
        processed_records = []
        
        for record in records:
            try:
                # Map NSE fields to our standardized schema
                # For NSE: symbol goes to symbol column, trigger will populate sec_code from stocklistdata
                processed_record = {
                    'sec_code': None,  # Leave empty - database trigger will populate from stocklistdata
                    'sec_name': record.get('company', ''),
                    'person_name': record.get('acqName', ''),
                    'person_cat': record.get('personCategory', ''),
                    'pre_sec_type': record.get('secType', ''),  # Using secType as pre type
                    'pre_sec_num': self.parse_int(record.get('befAcqSharesNo')),
                    'pre_sec_pct': self.parse_decimal(record.get('befAcqSharesPer')),
                    'trans_sec_type': record.get('secType', ''),
                    'trans_sec_num': self.parse_int(record.get('secAcq')),
                    'trans_value': self.parse_decimal(record.get('secVal')),
                    'trans_type': record.get('tdpTransactionType', ''),
                    'post_sec_type': record.get('securitiesTypePost', ''),
                    'post_sec_num': self.parse_int(record.get('afterAcqSharesNo')),
                    'post_sec_pct': self.parse_decimal(record.get('afterAcqSharesPer')),
                    'date_from': self.parse_date(record.get('acqfromDt')),
                    'date_to': self.parse_date(record.get('acqtoDt')),
                    'date_intimation': self.parse_date(record.get('intimDt')),
                    'mode_acq': record.get('acqMode', ''),
                    'exchange': 'NSE',  # Always NSE since this is NSE data
                    'symbol': record.get('symbol', '')  # NSE symbol goes here
                }
                processed_records.append(processed_record)
            except Exception as e:
                self.logger.error(f"Error processing record: {e}")
                continue
        
        if processed_records:
            df = pd.DataFrame(processed_records)
            self.logger.info(f"Processed {len(df)} records for upload")
            return df
        else:
            return pd.DataFrame()
    
    def parse_int(self, value):
        """Parse integer value, handling various formats."""
        if value is None or value == '' or value == 'Nil':
            return None
        try:
            # Remove commas and convert
            clean_value = str(value).replace(',', '').strip()
            if clean_value.lower() in ['nil', 'na', 'n/a', '-']:
                return None
            # Convert to float first to handle decimal strings, then to int
            return int(float(clean_value))
        except (ValueError, TypeError):
            return None
    
    def parse_decimal(self, value):
        """Parse decimal value, handling various formats."""
        if value is None or value == '' or value == 'Nil':
            return None
        try:
            clean_value = str(value).replace(',', '').replace('%', '').strip()
            if clean_value.lower() in ['nil', 'na', 'n/a', '-']:
                return None
            return float(clean_value)  # Return float instead of Decimal for JSON compatibility
        except (ValueError, TypeError):
            return None
    
    def parse_date(self, date_str):
        """Parse date string into YYYY-MM-DD format."""
        if not date_str or date_str.strip() in ['', '-', 'NA', 'N/A']:
            return None
        
        try:
            # NSE format is typically DD-MMM-YYYY or DD-MM-YYYY
            date_str = date_str.strip()
            
            # Handle datetime strings (remove time part)
            if ' ' in date_str:
                date_str = date_str.split(' ')[0]
            
            # Try different date formats
            formats = [
                '%d-%m-%Y',
                '%d/%m/%Y', 
                '%d-%b-%Y',
                '%d %b %Y',
                '%Y-%m-%d'
            ]
            
            for fmt in formats:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.date().isoformat()
                except ValueError:
                    continue
            
            # Fallback to pandas
            dt = pd.to_datetime(date_str, dayfirst=True, errors='coerce')
            if pd.isna(dt):
                return None
            return dt.date().isoformat()
            
        except Exception:
            return None
    
    def upload_to_supabase(self, df: pd.DataFrame) -> bool:
        """Upload processed data to Supabase."""
        if df.empty:
            self.logger.warning("No data to upload")
            return False
        
        try:
            from supabase import create_client
            
            supabase_url = os.environ.get("SUPABASE_URL2")
            supabase_key = os.environ.get("SUPABASE_KEY2")
            
            if not supabase_url or not supabase_key:
                raise RuntimeError("SUPABASE_URL2 and SUPABASE_KEY2 environment variables are required.")
            
            supabase = create_client(supabase_url, supabase_key)
            
            # Handle data type conversion properly
            df_serializable = df.copy()
            
            # Integer columns that should be integers (bigint in database)
            int_columns = ['pre_sec_num', 'trans_sec_num', 'post_sec_num']
            for col in int_columns:
                if col in df_serializable.columns:
                    df_serializable[col] = df_serializable[col].apply(
                        lambda x: int(x) if x is not None and not pd.isna(x) else None
                    )
            
            # Float columns that should be floats (numeric in database)
            float_columns = ['pre_sec_pct', 'post_sec_pct', 'trans_value']
            for col in float_columns:
                if col in df_serializable.columns:
                    df_serializable[col] = df_serializable[col].apply(
                        lambda x: float(x) if x is not None and not pd.isna(x) else None
                    )
            
            # Replace NaN values with None (which becomes null in JSON)
            df_serializable = df_serializable.replace({float('nan'): None})
            df_serializable = df_serializable.where(pd.notnull(df_serializable), None)
            
            # Truncate string fields to match database schema limits
            field_limits = {
                'sec_code': 20,
                'sec_name': 255,
                'person_name': 255,
                'person_cat': 50,
                'pre_sec_type': 50,
                'trans_sec_type': 50,
                'trans_type': 20,
                'post_sec_type': 50,
                'mode_acq': 50,
                'exchange': 50,
                'symbol': 50
            }
            
            for col, max_length in field_limits.items():
                if col in df_serializable.columns:
                    df_serializable[col] = df_serializable[col].apply(
                        lambda x: str(x)[:max_length] if x is not None and isinstance(x, str) and len(str(x)) > max_length else x
                    )
            
            # Convert to records for upload
            records = df_serializable.to_dict(orient="records")
            
            # Final cleanup: ensure no NaN values remain and proper types
            for record in records:
                for key, value in record.items():
                    if isinstance(value, float) and math.isnan(value):
                        record[key] = None
                    elif key in int_columns and value is not None:
                        try:
                            record[key] = int(float(value))  # Ensure it's an integer
                        except (ValueError, TypeError):
                            record[key] = None
                    elif key in float_columns and value is not None:
                        try:
                            record[key] = float(value)  # Ensure it's a float
                        except (ValueError, TypeError):
                            record[key] = None
            
            # Log sample record for debugging
            if records:
                self.logger.info(f"Sample record for upload: {records[0]}")
            
            # Upload in batches
            batch_size = 100
            total_records = len(records)
            
            for i in range(0, total_records, batch_size):
                batch = records[i:i+batch_size]
                try:
                    res = supabase.table("insider_trading").insert(batch).execute()
                    self.logger.info(f"✅ Uploaded batch {i//batch_size + 1}: {len(batch)} records")
                except Exception as e:
                    self.logger.error(f"❌ Failed to upload batch {i//batch_size + 1}: {e}")
                    # Log the problematic batch for debugging
                    self.logger.error(f"Problematic batch sample: {batch[0] if batch else 'Empty batch'}")
                    return False
            
            self.logger.info(f"🎉 Successfully uploaded {total_records} records to Supabase")
            return True
            
        except ImportError:
            self.logger.error("❌ Supabase client not installed. Run: pip install supabase")
            return False
        except Exception as e:
            self.logger.error(f"❌ Upload failed: {e}")
            return False
    
    def cleanup_json_file(self, filename: str):
        """Clean up JSON file after successful upload."""
        try:
            if os.path.exists(filename):
                os.remove(filename)
                self.logger.info(f"🗑️ Cleaned up file: {filename}")
        except Exception as e:
            self.logger.warning(f"⚠️ Could not delete {filename}: {e}")
    
    def close(self):
        """Close the session."""
        self.session.close()


def main():
    """Main function to run the scraper."""
    
    print("🚀 NSE Corporate PIT Data Scraper")
    print("=" * 50)
    print("⚠️  NSE uses advanced Akamai Bot Manager protection")
    print("⏳ This may take 30-60 seconds...")
    print()
    
    scraper = NSECorporateScraper()
    
    try:
        # Use today's date for scraping
        today = datetime.now().strftime("%d-%m-%Y")
        from_date = today
        to_date = today

        
        print(f"📅 Scraping data for today: {today}")
        print()
        
        data = scraper.scrape_corporate_pit_data(from_date, to_date)
        
        if data is not None:
            # Handle different data structures and empty responses
            if isinstance(data, dict):
                if 'data' in data:
                    records = data['data']
                    count = len(records) if records else 0
                else:
                    # If no 'data' key, treat the dict as the data
                    records = [data] if data else []
                    count = len(records)
            elif isinstance(data, list):
                records = data
                count = len(records)
            else:
                records = []
                count = 0
            
            if count > 0:
                print(f"\n🎉 SUCCESS! Retrieved {count} records")
            else:
                print(f"\n📭 No insider trading data found for {today}")
                print("ℹ️  This is normal - not all days have insider trading activity")
                return
            
            # Show sample data if available
            if count > 0 and records:
                print("\n📋 Sample record:")
                print("-" * 30)
                sample_record = records[0] if isinstance(records, list) else records
                print(json.dumps(sample_record, indent=2)[:500] + "...")
            
            # Save to file only if we have data
            filename = None
            if scraper.save_to_json(data):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"nse_corporate_pit_{timestamp}.json"
                print("✅ Data saved successfully")
                
                # Process and upload to Supabase
                try:
                    print("\n📤 Processing data for Supabase upload...")
                    df = scraper.process_nse_data_for_upload(data)
                    
                    if not df.empty:
                        print(f"📊 Processed {len(df)} records")
                        
                        if scraper.upload_to_supabase(df):
                            print("🎉 Upload to Supabase completed successfully!")
                            
                            # Clean up JSON file after successful upload
                            if filename:
                                scraper.cleanup_json_file(filename)
                            print("🧹 Cleanup completed.")
                        else:
                            print("❌ Failed to upload to Supabase")
                    else:
                        print("⚠️ No valid records to upload after processing")
                        # Still clean up the file if no valid data
                        if filename:
                            scraper.cleanup_json_file(filename)
                        
                except Exception as e:
                    print(f"❌ Error during processing/upload: {e}")
                    logging.exception("Error during processing/upload: %s", e)
                    # Clean up file on error
                    if filename:
                        scraper.cleanup_json_file(filename)
        else:
            print("\n❌ FAILED to retrieve data")
            print("\n🔧 Troubleshooting:")
            print("1. NSE uses sophisticated anti-bot protection (Akamai)")
            print("2. Try running during Indian business hours (9:15 AM - 3:30 PM IST)")
            print("3. Consider using NSE's official data APIs instead")
            print("4. The protection may require a real browser with JavaScript")
            print("\n💡 Alternative approach:")
            print("- Use Selenium with a real browser")
            print("- Use NSE's official data products")
            print("- Try during off-peak hours")
            
    except KeyboardInterrupt:
        print("\n⏹️ Cancelled by user")
    except Exception as e:
        print(f"\n💥 Error: {str(e)}")
        logging.exception("Error in main: %s", e)
    finally:
        scraper.close()


if __name__ == "__main__":
    main()