#!/usr/bin/env python3
"""
Unified Insider Trading Data Scraper and Uploader
Collects insider trading data from both NSE and BSE, deduplicates, and uploads to database.
Can be run as a cronjob.
"""

import os
import sys
import time
import glob
import shutil
import logging
import json
import requests
import random
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from decimal import Decimal
import math
from typing import Optional, Dict, Any, List

# Selenium imports for BSE
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import ElementClickInterceptedException, TimeoutException, JavascriptException
from webdriver_manager.chrome import ChromeDriverManager

# Supabase
try:
    from supabase import create_client
except ImportError:
    print("Error: supabase package not installed. Run: pip install supabase")
    sys.exit(1)

# Environment
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

# ============================================================================
# CONFIGURATION
# ============================================================================

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('InsiderTradingDetector')

# Supabase credentials
SUPABASE_URL = os.environ.get("SUPABASE_URL2")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY2")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("SUPABASE_URL2 and SUPABASE_KEY2 environment variables are required")
    sys.exit(1)

# Database table
TABLE_NAME = "insider_trading"

# Temporary files
TEMP_DIR = os.path.abspath(os.getcwd())
BSE_CSV = os.path.join(TEMP_DIR, "bse_insider_trading.csv")
NSE_JSON = os.path.join(TEMP_DIR, "nse_insider_trading.json")


# ============================================================================
# NSE SCRAPER CLASS
# ============================================================================

class NSEInsiderScraper:
    """NSE Corporate PIT Data Scraper"""
    
    def __init__(self):
        self.base_url = "https://www.nseindia.com"
        self.session = requests.Session()
        self.setup_session()
    
    def setup_session(self):
        """Setup session with headers"""
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
        """Random delay to appear more human"""
        time.sleep(random.uniform(min_sec, max_sec))
    
    def establish_session(self) -> bool:
        """Establish a proper session by visiting NSE pages"""
        try:
            logger.info("NSE: Establishing session...")
            
            # Visit homepage
            response = self.session.get(self.base_url)
            if response.status_code != 200:
                return False
            self.random_delay(2, 4)
            
            # Visit market data
            self.session.get(f"{self.base_url}/market-data")
            self.random_delay(2, 4)
            
            # Visit companies listing
            self.session.get(f"{self.base_url}/companies-listing")
            self.random_delay(2, 4)
            
            # Visit corporate filings page
            response = self.session.get(
                f"{self.base_url}/companies-listing/corporate-filings-insider-trading"
            )
            if response.status_code != 200:
                return False
            
            self.random_delay(3, 6)
            logger.info(f"NSE: Session established. Cookies: {len(self.session.cookies)}")
            return True
            
        except Exception as e:
            logger.error(f"NSE: Session establishment failed: {str(e)}")
            return False
    
    def scrape_data(self, from_date: str, to_date: str) -> Optional[Dict[Any, Any]]:
        """Scrape NSE corporate PIT data"""
        try:
            if not self.establish_session():
                logger.error("NSE: Failed to establish session")
                return None
            
            # Format dates (DD-MM-YYYY)
            from_date = self.format_date(from_date)
            to_date = self.format_date(to_date)
            
            api_url = f"{self.base_url}/api/corporates-pit"
            params = {
                'index': 'equities',
                'from_date': from_date,
                'to_date': to_date
            }
            
            api_headers = {
                'accept': '*/*',
                'referer': 'https://www.nseindia.com/companies-listing/corporate-filings-insider-trading',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin'
            }
            
            logger.info(f"NSE: Making API call for {from_date} to {to_date}")
            response = self.session.get(api_url, params=params, headers=api_headers)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data is None:
                        logger.info("NSE: API returned null data")
                        return None
                    
                    # Count records
                    if isinstance(data, dict):
                        if 'data' in data:
                            count = len(data['data']) if data['data'] else 0
                        else:
                            count = 1 if data else 0
                    elif isinstance(data, list):
                        count = len(data)
                    else:
                        count = 1 if data else 0
                    
                    logger.info(f"NSE: Retrieved {count} records")
                    return data
                    
                except json.JSONDecodeError:
                    logger.error("NSE: Failed to parse JSON response")
                    return None
            else:
                logger.error(f"NSE: API failed with status {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"NSE: Scraping failed: {str(e)}")
            return None
    
    def format_date(self, date_str: str) -> str:
        """Ensure date is in DD-MM-YYYY format"""
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
    
    def parse_int(self, value):
        """Parse integer value"""
        if value is None or value == '' or value == 'Nil':
            return None
        try:
            clean_value = str(value).replace(',', '').strip()
            if clean_value.lower() in ['nil', 'na', 'n/a', '-']:
                return None
            return int(float(clean_value))
        except (ValueError, TypeError):
            return None
    
    def parse_decimal(self, value):
        """Parse decimal value"""
        if value is None or value == '' or value == 'Nil':
            return None
        try:
            clean_value = str(value).replace(',', '').replace('%', '').strip()
            if clean_value.lower() in ['nil', 'na', 'n/a', '-']:
                return None
            return float(clean_value)
        except (ValueError, TypeError):
            return None
    
    def parse_date(self, date_str):
        """Parse date string into YYYY-MM-DD format"""
        if not date_str or date_str.strip() in ['', '-', 'NA', 'N/A']:
            return None
        
        try:
            date_str = date_str.strip()
            if ' ' in date_str:
                date_str = date_str.split(' ')[0]
            
            formats = ['%d-%m-%Y', '%d/%m/%Y', '%d-%b-%Y', '%d %b %Y', '%Y-%m-%d']
            
            for fmt in formats:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.date().isoformat()
                except ValueError:
                    continue
            
            dt = pd.to_datetime(date_str, dayfirst=True, errors='coerce')
            if pd.isna(dt):
                return None
            return dt.date().isoformat()
            
        except Exception:
            return None
    
    def process_nse_data(self, data: Dict[Any, Any]) -> pd.DataFrame:
        """Process NSE data into standardized format"""
        if not data:
            logger.warning("NSE: No data to process")
            return pd.DataFrame()
        
        # Handle different data structures
        if isinstance(data, dict):
            if 'data' in data:
                records = data['data']
            else:
                records = [data]
        elif isinstance(data, list):
            records = data
        else:
            logger.warning("NSE: Invalid data format")
            return pd.DataFrame()
        
        if not records:
            logger.info("NSE: No records found")
            return pd.DataFrame()
        
        processed_records = []
        
        for record in records:
            try:
                processed_record = {
                    'sec_code': None,  # Will be populated by trigger
                    'sec_name': record.get('company', ''),
                    'person_name': record.get('acqName', ''),
                    'person_cat': record.get('personCategory', ''),
                    'pre_sec_type': record.get('secType', ''),
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
                    'exchange': 'NSE',
                    'symbol': record.get('symbol', ''),
                    'reported_to_exchange': datetime.now().date().isoformat()
                }
                processed_records.append(processed_record)
            except Exception as e:
                logger.error(f"NSE: Error processing record: {e}")
                continue
        
        if processed_records:
            df = pd.DataFrame(processed_records)
            logger.info(f"NSE: Processed {len(df)} records")
            return df
        else:
            return pd.DataFrame()
    
    def close(self):
        """Close the session"""
        self.session.close()


# ============================================================================
# BSE SCRAPER CLASS
# ============================================================================

class BSEInsiderScraper:
    """BSE Insider Trading Data Scraper using Selenium"""
    
    def __init__(self, download_dir: str = TEMP_DIR):
        self.download_dir = download_dir
        self.driver = None
    
    def setup_driver(self):
        """Setup Selenium Chrome driver"""
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        
        prefs = {
            "download.default_directory": self.download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
    
    def enable_chrome_downloads(self):
        """Enable downloads in headless mode"""
        try:
            params = {"behavior": "allow", "downloadPath": self.download_dir}
            self.driver.execute_cdp_cmd("Page.setDownloadBehavior", params)
            return True
        except Exception as e:
            logger.warning(f"BSE: Could not set download behavior: {e}")
            return False
    
    def wait_for_download(self, before_files, timeout=180):
        """Wait for file download to complete"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            current_files = set(os.listdir(self.download_dir))
            new_files = current_files - before_files
            if new_files:
                for fname in new_files:
                    if fname.endswith(".crdownload"):
                        continue
                    return os.path.join(self.download_dir, fname)
            time.sleep(1.0)
        return None
    
    def scrape_data(self) -> Optional[str]:
        """Download BSE insider trading CSV"""
        try:
            logger.info("BSE: Starting download...")
            self.setup_driver()
            
            url = "https://www.bseindia.com/corporates/Insider_Trading_new.aspx?expandable=2"
            self.driver.get(url)
            
            self.enable_chrome_downloads()
            
            wait = WebDriverWait(self.driver, 30)
            
            # Wait for download button
            download_btn = wait.until(
                EC.presence_of_element_located((By.ID, "ContentPlaceHolder1_lnkDownload"))
            )
            logger.info("BSE: Found download button")
            
            # Snapshot files before download
            before_files = set(os.listdir(self.download_dir))
            
            # Scroll and click
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});",
                download_btn
            )
            time.sleep(0.5)
            
            # Try to click
            clicked = False
            try:
                download_btn.click()
                clicked = True
                logger.info("BSE: Clicked download button")
            except ElementClickInterceptedException:
                try:
                    from selenium.webdriver.common.action_chains import ActionChains
                    ActionChains(self.driver).move_to_element(download_btn).click().perform()
                    clicked = True
                    logger.info("BSE: ActionChains click succeeded")
                except:
                    self.driver.execute_script("arguments[0].click();", download_btn)
                    clicked = True
                    logger.info("BSE: JS click executed")
            
            if not clicked:
                raise RuntimeError("BSE: Could not click download button")
            
            # Wait for download
            logger.info("BSE: Waiting for download...")
            downloaded_path = self.wait_for_download(before_files, timeout=240)
            
            if downloaded_path is None:
                raise RuntimeError("BSE: Download timeout")
            
            logger.info(f"BSE: Downloaded file: {downloaded_path}")
            
            # Move to predictable filename
            final_path = BSE_CSV
            if os.path.exists(final_path):
                os.remove(final_path)
            shutil.move(downloaded_path, final_path)
            
            logger.info(f"BSE: Saved to {final_path}")
            return final_path
            
        except Exception as e:
            logger.error(f"BSE: Scraping failed: {str(e)}")
            return None
        finally:
            if self.driver:
                self.driver.quit()
    
    def parse_int(self, x):
        """Parse integer value"""
        if pd.isna(x):
            return None
        s = str(x).replace(",", "").replace("—", "").strip()
        if s in ("", "-", "NA", "N/A", "nan"):
            return None
        try:
            if "." in s:
                return int(float(s))
            return int(s)
        except Exception:
            import re
            m = re.search(r"(\d+)", s.replace(" ", ""))
            return int(m.group(1)) if m else None
    
    def parse_decimal(self, x):
        """Parse decimal value - matches original BSE script logic"""
        if pd.isna(x):
            return None
        s = str(x).replace(",", "").strip().replace("%", "")
        if s in ("", "-", "NA", "N/A", "nan"):
            return None
        try:
            # Try direct conversion to Decimal first
            return Decimal(s)
        except Exception:
            try:
                # Fallback: convert to float then Decimal
                return Decimal(str(float(s)))
            except Exception:
                return None
    
    def parse_date(self, x):
        """Parse date string"""
        if pd.isna(x):
            return None
        s = str(x).strip()
        if s in ("", "-", "NA", "N/A", "nan"):
            return None
        
        formats = (
            "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d",
            "%d %b %Y", "%d %B %Y", "%Y.%m.%d", "%d.%m.%Y",
            "%b %d, %Y", "%d %b, %Y"
        )
        
        for fmt in formats:
            try:
                dt = datetime.strptime(s, fmt)
                return dt.date().isoformat()
            except Exception:
                continue
        
        try:
            dt = pd.to_datetime(s, dayfirst=True, errors="coerce")
            if pd.isna(dt):
                return None
            return dt.date().isoformat()
        except Exception:
            return None
    
    def is_bse_val(self, x):
        """Check if value indicates BSE exchange"""
        if pd.isna(x):
            return False
        s = str(x).upper()
        if "BSE" in s or "BOMBAY" in s or "BSE LTD" in s:
            return True
        parts = [p.strip() for p in s.replace("/", ",").split(",")]
        return any(p.startswith("BSE") or p == "BSE" for p in parts)
    
    def norm(self, s):
        """Normalize string for pattern matching"""
        if pd.isna(s):
            return ""
        return "".join(c.lower() for c in str(s).strip()).replace(" ", "").replace("_", "")
    
    def build_col_map(self, headers):
        """Build column mapping for BSE CSV with comprehensive pattern matching"""
        # Direct mapping for exact BSE column names (case-insensitive)
        exact_mappings = {
            "security code": "sec_code",
            "security name": "sec_name",
            "name of person": "person_name",
            "category of person": "person_cat",
            "type of securities held prior to acquisition/disposed)": "pre_sec_type",
            "number of securities held prior to acquisition/disposed": "pre_sec_num",
            "%   of  securities held prior to acquisition/disposed": "pre_sec_pct",
            "type of securities Acquired/disposed/pledge etc.": "trans_sec_type",
            "number of securities acquired/disposed/pledge etc.": "trans_sec_num",
            "value  of securities acquired/disposed/pledge etc": "trans_value",
            "transaction type ( buy/sale/pledge/revoke/invoke)": "trans_type",
            "type of securities held post  acquisition/disposed/pledge  etc": "post_sec_type",
            "number of securities held post  acquisition/disposed/pledge etc": "post_sec_num",
            "post-transaction % of shareholding": "post_sec_pct",
            "date of acquisition of shares/sale of shares/date of allotment(from date)": "date_from",
            "date of acquisition of shares/sale of shares/date of allotment( to date  )": "date_to",
            "date of intimation to company": "date_intimation",
            "mode of acquisition": "mode_acq",
            "exchange on which the trade was executed": "exchange"
        }
        
        col_map = {}
        for header in headers:
            # Try exact match first (normalize spaces and case)
            normalized_header = " ".join(header.lower().strip().split())
            
            # Check for exact matches
            if normalized_header in exact_mappings:
                col_map[header] = exact_mappings[normalized_header]
                continue
            
            # Fallback to pattern matching for variations
            n = self.norm(header)
            mapped = None
            
            # Pattern-based matching for common variations
            if "securitycode" in n or "seccode" in n:
                mapped = "sec_code"
            elif "securityname" in n or "secname" in n:
                mapped = "sec_name"
            elif "nameofperson" in n:
                mapped = "person_name"
            elif "categoryofperson" in n:
                mapped = "person_cat"
            elif "typeofsecuritiesheldprior" in n:
                mapped = "pre_sec_type"
            elif "numberofsecuritiesheldprior" in n:
                mapped = "pre_sec_num"
            elif "%ofsecuritiesheldprior" in n or "percentofsecuritiesheldprior" in n:
                mapped = "pre_sec_pct"
            elif "typeofsecuritiesacquired" in n or "typeofsecuritiesdisposed" in n or "typeofsecuritiespledge" in n:
                mapped = "trans_sec_type"
            elif "numberofsecuritiesacquired" in n or "numberofsecuritiesdisposed" in n or "numberofsecuritiespledge" in n:
                mapped = "trans_sec_num"
            elif "valueofsecuritiesacquired" in n or "valueofsecuritiesdisposed" in n or "valueofsecuritiespledge" in n:
                mapped = "trans_value"
            elif "transactiontype" in n:
                mapped = "trans_type"
            elif "typeofsecuritiesheldpost" in n:
                mapped = "post_sec_type"
            elif "numberofsecuritiesheldpost" in n:
                mapped = "post_sec_num"
            elif "posttransaction" in n and ("%" in header or "percent" in n):
                mapped = "post_sec_pct"
            elif "dateofacquisition" in n and "fromdate" in n:
                mapped = "date_from"
            elif "dateofacquisition" in n and "todate" in n:
                mapped = "date_to"
            elif "dateofintimation" in n:
                mapped = "date_intimation"
            elif "modeofacquisition" in n:
                mapped = "mode_acq"
            elif "exchangeonwhich" in n or "tradewasexecuted" in n:
                mapped = "exchange"
            elif n == "symbol" or "scripsymbol" in n or "scrip" == n:
                mapped = "symbol"
            
            if mapped:
                col_map[header] = mapped
        
        return col_map
    
    def process_bse_csv(self, csv_path: str) -> pd.DataFrame:
        """Process BSE CSV into standardized format"""
        if not os.path.exists(csv_path):
            logger.error(f"BSE: CSV not found: {csv_path}")
            return pd.DataFrame()
        
        # Try reading with different delimiters - use the same logic as original BSE script
        df = None
        for sep in [",", ";", "\t", "|"]:
            try:
                tmp = pd.read_csv(csv_path, sep=sep, engine="python")
                # Check if this delimiter gives us reasonable data
                header_join = "".join([self.norm(h) for h in tmp.columns])
                if any(k in header_join for k in ["security", "exchange", "transaction"]):
                    df = tmp
                    logger.info(f"BSE: Successfully read CSV with delimiter '{sep}'")
                    break
            except Exception as e:
                logger.debug(f"BSE: Failed to read with delimiter '{sep}': {e}")
                pass
        
        if df is None:
            logger.info("BSE: Trying to read with automatic delimiter detection")
            df = pd.read_csv(csv_path, engine="python", encoding="latin1")
        
        logger.info(f"BSE: Detected {len(df.columns)} columns")
        
        headers = list(df.columns)
        col_map = self.build_col_map(headers)
        
        logger.info(f"BSE: Mapped {len(col_map)} columns")
        logger.info("BSE: Column mapping results:")
        for orig, mapped in col_map.items():
            logger.info(f"  '{orig}' -> '{mapped}'")
        
        # Check for unmapped critical columns
        mapped_cols = set(col_map.values())
        critical_cols = {'sec_code', 'sec_name', 'person_name', 'trans_sec_num', 'trans_value'}
        missing_critical = critical_cols - mapped_cols
        if missing_critical:
            logger.warning(f"BSE: Missing critical column mappings: {missing_critical}")
        
        # Expected columns
        expected_cols = [
            "sec_code", "sec_name", "person_name", "person_cat",
            "pre_sec_type", "pre_sec_num", "pre_sec_pct",
            "trans_sec_type", "trans_sec_num", "trans_value", "trans_type",
            "post_sec_type", "post_sec_num", "post_sec_pct",
            "date_from", "date_to", "date_intimation", "mode_acq",
            "exchange", "symbol", "reported_to_exchange"
        ]
        
        out = pd.DataFrame(columns=expected_cols)
        
        # Apply mappings
        for src, dst in col_map.items():
            if src in df.columns:
                out[dst] = df[src]
                logger.info(f"BSE: Mapped column '{src}' to '{dst}' with {df[src].notna().sum()} non-null values")
        
        # Fallback attempts for missing critical columns
        if out["person_name"].isna().all() or "person_name" not in col_map.values():
            logger.warning("BSE: person_name column not mapped, trying fallback detection")
            for c in headers:
                c_norm = self.norm(c)
                if "person" in c_norm or ("name" in c_norm and "security" not in c_norm and "company" not in c_norm):
                    out["person_name"] = df[c]
                    logger.info(f"BSE: Fallback: mapped '{c}' to person_name")
                    break
        
        # Additional fallbacks for other critical fields
        if out["sec_code"].isna().all() or "sec_code" not in col_map.values():
            for c in headers:
                if "code" in self.norm(c) and "security" in self.norm(c).lower():
                    out["sec_code"] = df[c]
                    logger.info(f"BSE: Fallback: mapped '{c}' to sec_code")
                    break
        
        if out["trans_sec_num"].isna().all() or "trans_sec_num" not in col_map.values():
            for c in headers:
                c_norm = self.norm(c)
                if "number" in c_norm and ("acquired" in c_norm or "disposed" in c_norm or "pledge" in c_norm):
                    out["trans_sec_num"] = df[c]
                    logger.info(f"BSE: Fallback: mapped '{c}' to trans_sec_num")
                    break
        
        # Strip whitespace
        out = out.applymap(lambda x: x.strip() if isinstance(x, str) else x)
        
        # BSE CSV contains only BSE data - no filtering needed
        # Just keep all records from the CSV
        logger.info(f"BSE: Keeping all {len(out)} records from BSE CSV (no filtering applied)")
        filtered = out.copy()
        
        # Parse numeric and date fields
        for col in ["pre_sec_num", "trans_sec_num", "post_sec_num"]:
            if col in filtered.columns:
                filtered[col] = filtered[col].apply(self.parse_int)
        
        for col in ["pre_sec_pct", "post_sec_pct", "trans_value"]:
            if col in filtered.columns:
                filtered[col] = filtered[col].apply(self.parse_decimal)
        
        for col in ["date_from", "date_to", "date_intimation"]:
            if col in filtered.columns:
                filtered[col] = filtered[col].apply(self.parse_date)
        
        # Set exchange to BSE
        filtered['exchange'] = 'BSE'
        logger.info("BSE: Set exchange column to 'BSE' for all records")
        
        # Ensure sec_code is treated as string (not parsed as number)
        if 'sec_code' in filtered.columns:
            def clean_sec_code(x):
                if x is None or pd.isna(x):
                    return None
                s = str(x).strip()
                if s in ('', 'nan', 'None'):
                    return None
                # Remove decimal point for integer values (e.g., '532540.0' -> '532540')
                if '.' in s:
                    try:
                        float_val = float(s)
                        if float_val == int(float_val):  # Check if it's a whole number
                            s = str(int(float_val))
                    except (ValueError, OverflowError):
                        pass
                return s
            filtered['sec_code'] = filtered['sec_code'].apply(clean_sec_code)
        
        # Handle symbol column - use from CSV if available, otherwise set to None for database trigger
        if 'symbol' not in filtered.columns:
            filtered['symbol'] = None
            logger.info("BSE: Symbol column not in CSV, set to None - database trigger will populate from sec_code")
        else:
            # Clean symbol field
            symbol_non_null = filtered['symbol'].notna().sum()
            if symbol_non_null > 0:
                logger.info(f"BSE: Found symbol column in CSV with {symbol_non_null}/{len(filtered)} non-null values")
                filtered['symbol'] = filtered['symbol'].apply(lambda x: str(x).strip() if x is not None and not pd.isna(x) and str(x).strip() not in ('', 'nan', 'None') else None)
            else:
                logger.info("BSE: Symbol column in CSV but all empty, set to None - database trigger will populate from sec_code")
        
        # Add reported_to_exchange column with today's date
        filtered['reported_to_exchange'] = datetime.now().date().isoformat()
        logger.info(f"BSE: Set reported_to_exchange to {datetime.now().date().isoformat()}")
        
        filtered = filtered[expected_cols]
        
        # Log data quality summary
        logger.info("BSE: Data quality summary after preprocessing:")
        for col in expected_cols:
            non_null_count = filtered[col].notna().sum()
            total_count = len(filtered)
            if total_count > 0:
                logger.info(f"  {col}: {non_null_count}/{total_count} non-null values ({non_null_count/total_count*100:.1f}%)")
        
        logger.info(f"BSE: Processed {len(filtered)} records")
        return filtered


# ============================================================================
# DEDUPLICATION AND UPLOAD
# ============================================================================

class InsiderTradingManager:
    """Manages insider trading data collection, deduplication, and upload"""
    
    def __init__(self):
        self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.nse_scraper = NSEInsiderScraper()
        self.bse_scraper = BSEInsiderScraper()
    
    def deduplicate_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Deduplicate insider trading records based on sec_name and person_name.
        When duplicates are found, prefer BSE data over NSE data.
        """
        if df.empty:
            return df
        
        logger.info(f"Deduplication: Starting with {len(df)} total records")
        
        # Create a deduplication key
        df['dedup_key'] = (
            df['sec_name'].fillna('').str.strip().str.lower() + '|' +
            df['person_name'].fillna('').str.strip().str.lower() + '|' +
            df['date_from'].fillna('').astype(str) + '|' +
            df['date_to'].fillna('').astype(str) + '|' +
            df['trans_sec_num'].fillna(0).astype(str)
        )
        
        # Count duplicates
        duplicates = df[df.duplicated(subset=['dedup_key'], keep=False)]
        if not duplicates.empty:
            logger.info(f"Deduplication: Found {len(duplicates)} duplicate records")
        
        # Sort by exchange (BSE first) to prefer BSE data
        df['exchange_priority'] = df['exchange'].map({'BSE': 0, 'NSE': 1})
        df_sorted = df.sort_values('exchange_priority')
        
        # Keep first occurrence (which will be BSE if duplicate exists)
        df_deduped = df_sorted.drop_duplicates(subset=['dedup_key'], keep='first')
        
        # Drop helper columns
        df_deduped = df_deduped.drop(columns=['dedup_key', 'exchange_priority'])
        
        removed_count = len(df) - len(df_deduped)
        logger.info(f"Deduplication: Removed {removed_count} duplicates, kept {len(df_deduped)} unique records")
        
        # Log distribution
        exchange_counts = df_deduped['exchange'].value_counts().to_dict()
        logger.info(f"Deduplication: Final distribution - {exchange_counts}")
        
        return df_deduped
    
    def prepare_for_upload(self, df: pd.DataFrame) -> List[Dict]:
        """Prepare DataFrame for Supabase upload"""
        if df.empty:
            return []
        
        # Convert Decimal to float and handle NaN
        df_serializable = df.copy()
        
        # Convert Decimal objects to float for all columns first (handles BSE Decimal values)
        for col in df_serializable.columns:
            if df_serializable[col].dtype == 'object':
                df_serializable[col] = df_serializable[col].apply(
                    lambda x: float(x) if isinstance(x, Decimal) else x
                )
        
        # Integer columns
        int_columns = ['pre_sec_num', 'trans_sec_num', 'post_sec_num']
        for col in int_columns:
            if col in df_serializable.columns:
                df_serializable[col] = df_serializable[col].apply(
                    lambda x: int(x) if x is not None and not pd.isna(x) else None
                )
        
        # Float columns
        float_columns = ['pre_sec_pct', 'post_sec_pct', 'trans_value']
        for col in float_columns:
            if col in df_serializable.columns:
                df_serializable[col] = df_serializable[col].apply(
                    lambda x: float(x) if x is not None and not pd.isna(x) else None
                )
        
        # Replace NaN with None
        df_serializable = df_serializable.replace({float('nan'): None})
        df_serializable = df_serializable.where(pd.notnull(df_serializable), None)
        
        # Truncate string fields
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
                # Ensure string fields remain strings and are truncated properly
                df_serializable[col] = df_serializable[col].apply(
                    lambda x: (str(x)[:max_length] if len(str(x)) > max_length else str(x)) if x is not None and str(x).strip() not in ('', 'nan', 'None') else None
                )
        
        # Convert to records
        records = df_serializable.to_dict(orient="records")
        
        # Log sample record for debugging (before final cleanup)
        if records:
            sample = records[0].copy()
            logger.info(f"Sample record before final cleanup: sec_code={sample.get('sec_code')}, sec_name={sample.get('sec_name')}, person_name={sample.get('person_name')}, exchange={sample.get('exchange')}, symbol={sample.get('symbol')}")
        
        # Final cleanup
        for record in records:
            for key, value in record.items():
                if isinstance(value, float) and math.isnan(value):
                    record[key] = None
                elif key in int_columns and value is not None:
                    try:
                        record[key] = int(float(value))
                    except (ValueError, TypeError):
                        record[key] = None
                elif key in float_columns and value is not None:
                    try:
                        record[key] = float(value)
                    except (ValueError, TypeError):
                        record[key] = None
        
        return records
    
    def upload_to_database(self, records: List[Dict]) -> bool:
        """Upload records to Supabase in batches"""
        if not records:
            logger.warning("No records to upload")
            return False
        
        try:
            batch_size = 100
            total_records = len(records)
            
            logger.info(f"Uploading {total_records} records in batches of {batch_size}")
            
            for i in range(0, total_records, batch_size):
                batch = records[i:i+batch_size]
                try:
                    self.supabase.table(TABLE_NAME).insert(batch).execute()
                    logger.info(f"Uploaded batch {i//batch_size + 1}: {len(batch)} records")
                except Exception as e:
                    logger.error(f"Failed to upload batch {i//batch_size + 1}: {e}")
                    logger.error(f"Sample record: {batch[0] if batch else 'Empty'}")
                    return False
            
            logger.info(f"Successfully uploaded {total_records} records")
            return True
            
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return False
    
    def cleanup_temp_files(self):
        """Clean up temporary files"""
        files_to_delete = [BSE_CSV, NSE_JSON]
        for file_path in files_to_delete:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Cleaned up: {file_path}")
            except Exception as e:
                logger.warning(f"Could not delete {file_path}: {e}")
    
    def run(self, from_date: str = None, to_date: str = None):
        """
        Main execution method.
        Collects data from NSE and BSE, deduplicates, and uploads.
        """
        logger.info("=" * 80)
        logger.info("INSIDER TRADING DATA COLLECTION")
        logger.info("=" * 80)
        
        # Use today's date if not provided
        if from_date is None or to_date is None:
            today = datetime.now().strftime("%d-%m-%Y")
            from_date = today
            to_date = today
        
        logger.info(f"Date range: {from_date} to {to_date}")
        
        all_data = []
        
        # Collect NSE data
        logger.info("\n" + "=" * 80)
        logger.info("STEP 1: Collecting NSE Data")
        logger.info("=" * 80)
        
        try:
            nse_data = self.nse_scraper.scrape_data(from_date, to_date)
            if nse_data:
                nse_df = self.nse_scraper.process_nse_data(nse_data)
                if not nse_df.empty:
                    all_data.append(nse_df)
                    logger.info(f"NSE: Collected {len(nse_df)} records")
                else:
                    logger.info("NSE: No records found")
            else:
                logger.info("NSE: No data retrieved")
        except Exception as e:
            logger.error(f"NSE: Collection failed: {e}")
        finally:
            self.nse_scraper.close()
        
        # Collect BSE data
        logger.info("\n" + "=" * 80)
        logger.info("STEP 2: Collecting BSE Data")
        logger.info("=" * 80)
        
        try:
            bse_csv_path = self.bse_scraper.scrape_data()
            if bse_csv_path and os.path.exists(bse_csv_path):
                bse_df = self.bse_scraper.process_bse_csv(bse_csv_path)
                if not bse_df.empty:
                    all_data.append(bse_df)
                    logger.info(f"BSE: Collected {len(bse_df)} records")
                else:
                    logger.info("BSE: No records found")
            else:
                logger.info("BSE: No data retrieved")
        except Exception as e:
            logger.error(f"BSE: Collection failed: {e}")
        
        # Combine and deduplicate
        logger.info("\n" + "=" * 80)
        logger.info("STEP 3: Deduplication")
        logger.info("=" * 80)
        
        if not all_data:
            logger.warning("No data collected from any source")
            self.cleanup_temp_files()
            return
        
        combined_df = pd.concat(all_data, ignore_index=True)
        logger.info(f"Combined total: {len(combined_df)} records")
        
        deduped_df = self.deduplicate_data(combined_df)
        
        # Upload to database
        logger.info("\n" + "=" * 80)
        logger.info("STEP 4: Uploading to Database")
        logger.info("=" * 80)
        
        records = self.prepare_for_upload(deduped_df)
        
        if records:
            success = self.upload_to_database(records)
            if success:
                logger.info("✅ Upload completed successfully!")
            else:
                logger.error("❌ Upload failed")
        else:
            logger.warning("No records to upload after processing")
        
        # Cleanup
        logger.info("\n" + "=" * 80)
        logger.info("STEP 5: Cleanup")
        logger.info("=" * 80)
        
        self.cleanup_temp_files()
        
        logger.info("\n" + "=" * 80)
        logger.info("INSIDER TRADING DATA COLLECTION COMPLETED")
        logger.info("=" * 80)


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main function to run as cronjob"""
    try:
        manager = InsiderTradingManager()
        manager.run()
    except KeyboardInterrupt:
        logger.info("\n⏹️ Cancelled by user")
    except Exception as e:
        logger.error(f"\n💥 Error: {str(e)}")
        logging.exception("Fatal error:")
        sys.exit(1)


if __name__ == "__main__":
    main()
