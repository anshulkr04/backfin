import requests
import os
import logging
import time 
import json
from google import genai
from dotenv import load_dotenv
from collections import deque
import re
from supabase import create_client, Client
from urllib.parse import urlparse
import tempfile
import shutil
from datetime import datetime, timezone
import uuid
import threading
from pathlib import Path
try:
    import PyPDF2
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
from pydantic import BaseModel, Field
from prompt import *
from invanl import uploadInvestor
import fcntl  
import contextlib
import sqlite3

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bse_scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("BSEScraper")

# Load environment variables
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    logger.error("Missing GEMINI_API_KEY environment variable")
    logger.warning("Will skip AI processing without GEMINI_API_KEY")

SUPABASE_URL = os.getenv("SUPABASE_URL2")
SUPABASE_KEY = os.getenv("SUPABASE_KEY2")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not (SUPABASE_URL and SUPABASE_KEY):
    logger.error("Missing Supabase credentials")
    logger.warning("Will operate in limited mode without Supabase credentials")




# Initialize Supabase client
supabase = None
try:
    if SUPABASE_URL and SUPABASE_KEY:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY if SUPABASE_SERVICE_ROLE_KEY else SUPABASE_KEY)
        logger.info("Supabase client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Supabase client: {e}")
    logger.warning("Continuing without Supabase connection")

def safely_upload_financial_data(supabase, financial_data, symbol, isin, max_retries=3):
    """Safely upload financial data with proper duplicate checking and updating"""
    try:
        # Check if record exists for this ISIN and period
        existing_query = supabase.table("financial_results").select("*").eq("isin", isin)
        
        # Only filter by period if it's not empty
        if financial_data.get("period"):
            existing_query = existing_query.eq("period", financial_data.get("period"))
            
        existing_result = existing_query.execute()
        
        if existing_result.data and len(existing_result.data) > 0:
            existing_record = existing_result.data[0]
            logger.info(f"Found existing financial record for ISIN {isin}, period: {financial_data.get('period')}")
            
            # Check if existing record has missing data that we can fill
            update_needed = False
            update_data = {}
            
            for field in ["sales_current", "sales_previous_year", "pat_current", "pat_previous_year"]:
                existing_value = existing_record.get(field)
                new_value = financial_data.get(field)
                
                # Update if existing field is empty/null and new value is not empty
                if (not existing_value or existing_value.strip() == "") and new_value and new_value.strip():
                    update_data[field] = new_value
                    update_needed = True
            
            if update_needed:
                # Update the existing record
                for attempt in range(1, max_retries + 1):
                    try:
                        update_result = supabase.table("financial_results").update(update_data).eq("isin", isin).eq("period", financial_data.get("period", "")).execute()
                        logger.info(f"Updated financial data for {symbol} (ISIN: {isin}) with missing fields")
                        return True
                    except Exception as e:
                        logger.error(f"Error updating financial data (attempt {attempt}/{max_retries}): {e}")
                        if attempt < max_retries:
                            time.sleep(5)
                        else:
                            logger.error(f"Failed to update financial data after {max_retries} attempts")
                            return False
            else:
                logger.info(f"Financial data for {symbol} (ISIN: {isin}) already complete, skipping")
                return True
        else:
            # No existing record, insert new one
            for attempt in range(1, max_retries + 1):
                try:
                    insert_result = supabase.table("financial_results").insert(financial_data).execute()
                    logger.info(f"Inserted new financial data for {symbol} (ISIN: {isin})")
                    return True
                except Exception as e:
                    logger.error(f"Error inserting financial data (attempt {attempt}/{max_retries}): {e}")
                    if attempt < max_retries:
                        time.sleep(5)
                    else:
                        logger.error(f"Failed to insert financial data after {max_retries} attempts")
                        return False
    except Exception as e:
        logger.error(f"Error in safely_upload_financial_data: {e}")
        return False


class StrucOutput(BaseModel):
    """Schema for structured output from the model."""
    category: str = Field(... , description = category_prompt)
    headline: str = Field(..., description= headline_prompt)
    summary: str = Field(..., description= sum_prompt)
    findata: str =Field(..., description= financial_data_prompt)
    individual_investor_list: list[str] = Field(..., description="List of individual investors not company mentioned in the announcement. It should be in a form of an array of strings.")
    company_investor_list: list[str] = Field(..., description="List of company investors mentioned in the announcement. It should be in a form of an array of strings.")
    sentiment: str = Field(..., description = "Analyze the sentiment of the announcement and give appropriate output. The output should be only: Postive, Negative and Netural. Nothing other than these." )



# Add functions to handle announcement tracking in JSON file
def get_data_dir():
    """Get or create the data directory"""
    # Create a 'data' directory in the same folder as this script
    data_dir = Path(__file__).parent / "data"
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


LOCAL_DB_PATH = get_data_dir() / "bse_raw.db"

def init_local_db(db_path=LOCAL_DB_PATH):
    db_path = str(db_path)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30, isolation_level=None)
    try:
        # Use WAL for safer concurrency
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS raw_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fetched_at TEXT NOT NULL,
                url TEXT,
                params TEXT,
                raw_json TEXT NOT NULL
            )
        """)
        # Full announcements table with checkpoint columns
        cur.execute("""
            CREATE TABLE IF NOT EXISTS announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                newsid TEXT,
                scrip_cd INTEGER,
                headline TEXT,
                fetched_at TEXT NOT NULL,
                raw_json TEXT NOT NULL,
                downloaded_pdf_file TEXT,
                pdf_pages INTEGER,
                pdf_downloaded_at TEXT,
                ai_processed INTEGER DEFAULT 0,
                ai_summary TEXT,
                ai_error TEXT,
                ai_processed_at TEXT,
                sent_to_supabase INTEGER DEFAULT 0,
                sent_to_supabase_at TEXT,
                UNIQUE(newsid)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_announcements_newsid ON announcements(newsid);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_announcements_scrip ON announcements(scrip_cd);")
        conn.commit()

        # In case this is an older DB without the new columns, try adding them (safe-guard with try/except)
        extra_cols = {
            "downloaded_pdf_file": "TEXT",
            "pdf_pages": "INTEGER",
            "pdf_downloaded_at": "TEXT",
            "ai_processed": "INTEGER DEFAULT 0",
            "ai_summary": "TEXT",
            "ai_error": "TEXT",
            "ai_processed_at": "TEXT",
            "sent_to_supabase": "INTEGER DEFAULT 0",
            "sent_to_supabase_at": "TEXT"
        }
        for col, coltype in extra_cols.items():
            try:
                cur.execute(f"ALTER TABLE announcements ADD COLUMN {col} {coltype};")
            except sqlite3.OperationalError:
                # Column already exists — that's fine
                pass
        conn.commit()
    finally:
        conn.close()


def update_announcement_checkpoint(newsid=None, ann_id=None, db_path=LOCAL_DB_PATH, **fields):
    """
    Update announcements row identified by newsid or id with provided fields.
    Example fields: downloaded_pdf_file='x.pdf', pdf_pages=12, ai_processed=1, ai_summary='...', sent_to_supabase=1
    """
    if not newsid and not ann_id:
        logger.warning("update_announcement_checkpoint called without newsid or ann_id")
        return False

    db_path = str(db_path)
    init_local_db(db_path)
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        cur = conn.cursor()
        # Build SET clause
        set_parts = []
        params = []
        for k, v in fields.items():
            set_parts.append(f"{k} = ?")
            params.append(v)
        if not set_parts:
            return False
        params.append(newsid if newsid is not None else ann_id)
        if newsid is not None:
            sql = f"UPDATE announcements SET {', '.join(set_parts)} WHERE newsid = ?"
        else:
            sql = f"UPDATE announcements SET {', '.join(set_parts)} WHERE id = ?"
        cur.execute(sql, params)
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to update announcement checkpoint: {e}")
        return False
    finally:
        conn.close()


# small helper to acquire a file lock for DB writes (prevents two processes racing)
def _with_file_lock(path):
    lockfile = str(Path(path).with_suffix(".lock"))
    f = open(lockfile, "w")
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        f.close()

def save_raw_fetch(announcements, url=None, params=None, db_path=LOCAL_DB_PATH):
    """Save raw API response and each announcement into DB.

    Returns True on success, False on failure.
    """
    db_path = str(db_path)
    fetched_at = datetime.now(timezone.utc).isoformat()
    raw_json_text = json.dumps(announcements, ensure_ascii=False)

    # Ensure DB exists / schema present
    init_local_db(db_path)

    # Use a file lock to be extra safe across processes
    lockfile = str(Path(db_path).with_suffix(".lock"))
    # open lockfile in append mode so it exists and we don't overwrite
    with open(lockfile, "a+") as lf:
        try:
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
            conn = sqlite3.connect(db_path, timeout=30)
            try:
                cur = conn.cursor()
                # Insert raw response
                try:
                    cur.execute(
                        "INSERT INTO raw_responses(fetched_at, url, params, raw_json) VALUES (?, ?, ?, ?)",
                        (fetched_at, url or "", json.dumps(params or {}), raw_json_text)
                    )
                except Exception as e:
                    logger.error(f"Failed to insert raw_responses row: {e}")
                    # Continue; we still want to try to insert announcements

                # Insert individual announcements (use parameterized queries)
                if isinstance(announcements, list):
                    for ann in announcements:
                        try:
                            newsid = ann.get("NEWSID")
                            scrip = ann.get("SCRIP_CD")
                            headline = ann.get("HEADLINE") or ""
                            ann_json = json.dumps(ann, ensure_ascii=False)

                            cur.execute(
                                """INSERT INTO announcements(
                                    newsid, scrip_cd, headline, fetched_at, raw_json,
                                    downloaded_pdf_file, pdf_pages, pdf_downloaded_at,
                                    ai_processed, ai_summary, ai_error, ai_processed_at,
                                    sent_to_supabase, sent_to_supabase_at
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                                (
                                    str(newsid) if newsid is not None else None,
                                    scrip,
                                    headline,
                                    fetched_at,
                                    ann_json,
                                    None,  # downloaded_pdf_file
                                    None,  # pdf_pages
                                    None,  # pdf_downloaded_at
                                    0,     # ai_processed
                                    None,  # ai_summary
                                    None,  # ai_error
                                    None,  # ai_processed_at
                                    0,     # sent_to_supabase
                                    None   # sent_to_supabase_at
                                )
                            )
                        except sqlite3.IntegrityError:
                            # unique constraint: duplicate NEWSID — skip or optionally update
                            logger.debug(f"Skipped duplicate announcement with NEWSID={ann.get('NEWSID')}")
                        except Exception as e:
                            logger.error(f"Failed to insert announcement NEWSID={ann.get('NEWSID')}: {e}")
                else:
                    # If announcements is not a list, still store the raw response and warn
                    logger.warning("save_raw_fetch expected announcements as list, got: %s", type(announcements))

                conn.commit()
                return True
            except Exception as e:
                logger.error(f"Database error in save_raw_fetch: {e}")
                try:
                    conn.rollback()
                except Exception:
                    pass
                return False
            finally:
                conn.close()
        finally:
            try:
                fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass




def save_latest_announcement(announcement, filename=None):
    """Save the latest announcement details to a JSON file with file locking"""
    if filename is None:
        # Use different filenames for BSE and NSE
        script_name = Path(__file__).stem  # Gets 'bse_scraper' or 'nse_scraper'
        filename = get_data_dir() / f"latest_announcement_{script_name}.json"
    
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        # Use file locking to prevent concurrent access
        with open(filename, 'w') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # Exclusive lock
            json.dump(announcement, f, indent=4)
        logger.info(f"Saved latest announcement to {filename}")
    except Exception as e:
        logger.error(f"Error saving latest announcement to file: {e}")

def load_latest_announcement(filename=None):
    """Load the latest processed announcement from JSON file with file locking"""
    if filename is None:
        # Use different filenames for BSE and NSE
        script_name = Path(__file__).stem  # Gets 'bse_scraper' or 'nse_scraper'
        filename = get_data_dir() / f"latest_announcement_{script_name}.json"
    
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # Shared lock for reading
                return json.load(f)
        return None
    except Exception as e:
        logger.error(f"Error loading latest announcement from file: {e}")
        return None

def announcements_are_equal(a1, a2):
    """Compare two announcements to check if they are the same"""
    if not a1 or not a2:
        return False
        
    # Compare key fields that would indicate it's the same announcement
    fields_to_compare = ['NEWSID']
    
    return all(a1.get(field) == a2.get(field) for field in fields_to_compare)


class RateLimitedGeminiClient:
    def __init__(self, api_key, rpm_limit=4000, max_retries=3):
        try:
            self.client = genai.Client(api_key=api_key)
            self.rpm_limit = rpm_limit
            self.request_timestamps = deque()
            self.max_retries = max_retries
            logger.info("Gemini client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            self.client = None

    def _enforce_rate_limit(self):
        """Enforce API rate limit (requests per minute)"""
        if not self.client:
            raise Exception("Gemini client not initialized")
            
        current_time = time.time()
        while self.request_timestamps and current_time - self.request_timestamps[0] > 60:
            self.request_timestamps.popleft()

        if len(self.request_timestamps) >= self.rpm_limit:
            wait_time = 60 - (current_time - self.request_timestamps[0]) + 0.1
            logger.info(f"Rate limit reached. Waiting {wait_time:.2f} seconds...")
            time.sleep(wait_time)

        self.request_timestamps.append(time.time())

    def generate_content(self, contents , config):
        """Rate-limited wrapper for generate_content with retries"""
        if not self.client:
            raise Exception("Gemini client not initialized")
        model = "gemini-2.5-flash-lite-preview-06-17"
            
        for attempt in range(1, self.max_retries + 1):
            try:
                self._enforce_rate_limit()
                return self.client.models.generate_content(model=model, contents=contents, config = config)
            except Exception as e:
                if attempt == self.max_retries:
                    logger.error(f"Failed to generate content after {self.max_retries} attempts: {e}")
                    raise
                logger.warning(f"Attempt {attempt} failed: {e}. Retrying...")
                time.sleep(2 * attempt)  # Exponential backoff

    def chats(self):
        """Rate-limited access to the chats API"""
        if not self.client:
            raise Exception("Gemini client not initialized")
        return RateLimitedChatWrapper(self)

    @property
    def files(self):
        """Expose the original client's .files attribute"""
        if not self.client:
            raise Exception("Gemini client not initialized")
        return self.client.files


class RateLimitedChatWrapper:
    def __init__(self, rate_limited_client):
        self.rate_limited_client = rate_limited_client
        self.client = rate_limited_client.client

    def create(self, model):
        """Rate-limited wrapper for chats.create"""
        try:
            self.rate_limited_client._enforce_rate_limit()
            return RateLimitedChatSession(self.client.chats.create(model=model), self.rate_limited_client)
        except Exception as e:
            logger.error(f"Failed to create chat session: {e}")
            raise


class RateLimitedChatSession:
    def __init__(self, chat_session, rate_limited_client):
        self.chat_session = chat_session
        self.rate_limited_client = rate_limited_client

    def send_message(self, content):
        """Rate-limited wrapper for send_message with retries"""
        for attempt in range(1, self.rate_limited_client.max_retries + 1):
            try:
                self.rate_limited_client._enforce_rate_limit()
                return self.chat_session.send_message(content)
            except Exception as e:
                if attempt == self.rate_limited_client.max_retries:
                    logger.error(f"Failed to send message after {self.rate_limited_client.max_retries} attempts: {e}")
                    raise
                logger.warning(f"Send message attempt {attempt} failed: {e}. Retrying...")
                time.sleep(2 * attempt)  # Exponential backoff


def remove_markdown_tags(text):
    """Remove Markdown tags and adjust indentation of the text"""
    if not isinstance(text, str):
        logger.warning(f"Expected string for markdown removal, got {type(text)}")
        return "" if text is None else str(text)
        
    # Check if code blocks are present
    has_code_blocks = re.search(r'```', text) is not None

    # Remove code blocks (content between ```)
    text = re.sub(r'```[^\n]*\n(.*?)```', r'\1', text, flags=re.DOTALL)
    
    # Remove HTML tags
    text = re.sub(r"<.*?>", "", text)
    
    # Only adjust indentation if code blocks were detected
    if has_code_blocks:
        lines = text.split('\n')
        if lines:
            # Find the minimum indentation (excluding empty lines)
            non_empty_lines = [line for line in lines if line.strip()]
            if non_empty_lines:
                min_indent = min(len(line) - len(line.lstrip()) for line in non_empty_lines)
                # Reduce indentation by half of the minimum (to maintain some indentation)
                shift = max(min_indent // 2, 1) if min_indent > 0 else 0
                lines = [line[shift:] if line.strip() else line for line in lines]
            text = '\n'.join(lines)
    
    return text.strip()

def clean_summary(text):
    """Removes everything before **Category:** and returns the rest."""
    marker = "**Category:**"
    if marker in text:
        return text[text.index(marker):].strip()
    else:
        return text


def check_for_negative_keywords(summary):
    """Check for negative keywords in the announcements"""
    if not isinstance(summary, str):
        logger.warning(f"Expected string for keyword check, got {type(summary)}")
        return True  # Treat non-string values as containing negative keywords
        
    negative_keywords = [
        "Trading Window", "Compliance Report", "Advertisement(s)", "Advertisement", "Public Announcement",
        "Share Certificate(s)", "Share Certificate", "Depositories and Participants", "Depository and Participant",
        "Depository and Participant", "Depository and Participants", "74(5)", "XBRL", "Newspaper Publication",
        "Published in the Newspapers", "Clippings", "Book Closure", "Change in Company Secretary/Compliance Officer",
        "Record Date","Code of Conduct","Cessation","Deviation","Declared Interim Dividend","IEPF","Investor Education","Registrar & Share Transfer Agent",
        "Registrar and Share Transfer Agent","Scrutinizers report","Utilisation of Funds","Postal Ballot","Defaults on Payment of Interest",
        "Newspaper Publication","Sustainability Report","Sustainability Reporting","Trading Plan","Letter of Confirmation","Forfeiture/Cancellation","Price movement",
        "Spurt","Grievance Redressal","Monitoring Agency","Regulation 57",
    ]

    special_keywords = [
        "Board", "Outcome", "General Updates",
    ]

    for keyword in special_keywords:
        if keyword.lower() in summary.lower():
            logger.info(f"Special keyword '{keyword}' found in announcement: {summary}")
            return False
            
    for keyword in negative_keywords:
        if keyword.lower() in summary.lower():
            logger.info(f"Negative keyword '{keyword}' found in announcement: {summary}")
            return True
            
    return False


def check_for_pdf(desc):
    """Check if the description contains a PDF file name"""
    return isinstance(desc, str) and desc.lower().endswith('.pdf')


def extract_symbol(url):
    """Extract symbol from URL safely"""
    if not url:
        logger.warning("Cannot extract symbol from empty URL")
        return None
        
    try:
        path = urlparse(url).path  # get the path from URL
        segments = path.strip('/').split('/')  # split path into parts
        if len(segments) >= 2 and segments[-1].isdigit():
            return segments[-2]  # return the segment just before the numeric ID
    except Exception as e:
        logger.error(f"Error extracting symbol from URL {url}: {e}")
    
    return None

def get_pdf_page_count(filepath, trim_if_large=False, max_pages=200, keep_pages=150):
    """Get the number of pages in a PDF file and optionally trim if too large"""
    if not PDF_SUPPORT:
        logger.warning("PyPDF2 not installed, cannot count PDF pages")
        return None
    
    try:
        with open(filepath, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            page_count = len(pdf_reader.pages)
            logger.info(f"PDF has {page_count} pages")

        # If trimming is requested and page count exceeds threshold
        if trim_if_large and page_count > max_pages:
            logger.info(f"Trimming {filepath}: keeping only first {keep_pages} pages")
            temp_file = filepath + ".tmp"
            writer = PyPDF2.PdfWriter()

            for i in range(min(keep_pages, page_count)):
                writer.add_page(pdf_reader.pages[i])

            with open(temp_file, "wb") as f:
                writer.write(f)

            os.replace(temp_file, filepath)  # overwrite safely
            logger.info(f"Trimmed {filepath} successfully")

            return keep_pages  # new page count

        return page_count

    except Exception as e:
        logger.error(f"Error counting/trimming PDF pages: {e}")
        return None
    

# Initialize Gemini client with retries
genai_client = None
try:
    if API_KEY:
        genai_client = RateLimitedGeminiClient(api_key=API_KEY)
except Exception as e:
    logger.error(f"Failed to initialize Gemini client: {e}")
    logger.warning("AI processing will be skipped")


class BseScraper:
    def __init__(self, prev_date, to_date, max_retries=50, request_timeout=30):
        self.url = "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w"
        self.params = {
            "pageno": 1,
            "strCat": -1,
            "strPrevDate": prev_date,
            "strScrip": "",
            "strSearch": "P",
            "strToDate": to_date,
            "strType": "C",
            "subcategory": -1
        }

        self.headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.bseindia.com/",
            "Origin": "https://www.bseindia.com"
        }
        
        self.max_retries = max_retries
        self.request_timeout = request_timeout
        self.temp_dir = tempfile.mkdtemp(prefix="bse_scraper_")
        logger.info(f"Created temporary directory: {self.temp_dir}")
        
        # Track if this is the first run - FIXED: Check if flag file does NOT exist
        self.first_run_flag_path = Path(__file__).parent / "data" / "first_run_flag.txt"

    def __del__(self):
        """Clean up temporary directory on object destruction"""
        try:
            if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                logger.info(f"Removed temporary directory: {self.temp_dir}")
        except Exception as e:
            logger.error(f"Error cleaning up temporary directory: {e}")

    def fetch_data(self):
        """Fetch announcement data with retries and error handling"""
        for attempt in range(1, self.max_retries + 1):
            try:
                with requests.Session() as session:
                    session.headers.update(self.headers)
                    response = session.get(
                        self.url, 
                        params=self.params, 
                        timeout=self.request_timeout
                    )
                    
                    response.raise_for_status()  # Raises an exception for 4XX/5XX responses
                    
                    data = response.json()
                    announcements = data.get("Table", [])
                    
                    if not announcements and isinstance(announcements, list):
                        logger.warning("API returned empty announcement list")
                    
                    return announcements
            except requests.exceptions.Timeout:
                logger.warning(f"Request timed out (attempt {attempt}/{self.max_retries})")
            except requests.exceptions.HTTPError as e:
                logger.error(f"HTTP error occurred: {e}, Status code: {e.response.status_code}")
            except requests.exceptions.ConnectionError:
                logger.error(f"Connection error (attempt {attempt}/{self.max_retries})")
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error: {e}")
            except ValueError as e:  # Includes JSONDecodeError
                logger.error(f"Failed to parse JSON response: {e}")
            except Exception as e:
                logger.error(f"Unexpected error in fetch_data: {e}")
                
            if attempt < self.max_retries:
                wait_time = 5  # Fixed 5-second wait for consistency
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                logger.error(f"Failed to fetch data after {self.max_retries} attempts")
                return []  # Return empty list after all retries fail

    def process_pdf(self, pdf_file, max_pages=200):
        """Download and process PDF with error handling"""
        if not pdf_file:
            logger.error("No PDF file specified")
            return "Error", "No PDF file specified", "", "", [], [], None, "Neutral"
            
        # Use the temp directory for downloads
        filepath = os.path.join(self.temp_dir, pdf_file.split("/")[-1])
        num_pages = None
        
        try:
            url = f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{pdf_file}"
            
            # Download with retries
            for attempt in range(1, self.max_retries + 1):
                try:
                    response = requests.get(url, timeout=self.request_timeout, headers=self.headers)
                    response.raise_for_status()
                    
                    with open(filepath, "wb") as file:
                        file.write(response.content)
                    logger.info(f"Downloaded: {filepath}")
                    pdf_filename = os.path.basename(filepath)
                    break
                except requests.exceptions.Timeout:
                    logger.warning(f"PDF download timed out (attempt {attempt}/{self.max_retries})")
                except requests.exceptions.HTTPError as e:
                    logger.error(f"HTTP error downloading PDF: {e}")
                    return "Error", f"Failed to download PDF: HTTP error {e.response.status_code}", "", "", [], [], None, "Neutral"
                except requests.exceptions.RequestException as e:
                    logger.error(f"Error downloading PDF (attempt {attempt}/{self.max_retries}): {e}")
                    return "Error", f"Failed to download PDF: HTTP error {e.response.status_code}", "", "", [], [], None, "Neutral"

                if attempt < self.max_retries:
                    wait_time = 5  # Fixed 5-second wait as requested
                    logger.info(f"Retrying download in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.error("Failed to download PDF after all retries")
                    return "Error", "Failed to download PDF after multiple attempts", "", "", [], [], None, "Neutral"
                    
            # Process the PDF if download was successful
            if os.path.exists(filepath):
                # Get page count first
                num_pages = get_pdf_page_count(filepath)
                
                # # Check page limit before AI processing
                # if num_pages and num_pages > max_pages:
                #     logger.warning(f"PDF has too many pages ({num_pages}), skipping AI processing")
                #     return "Procedural/Administrative", f"PDF too large ({num_pages} pages)", "", "", [], [], num_pages, "Neutral"
                
                category, ai_summary, headline, financial_data, individual_investor_list, company_investor_list, sentiment = self.ai_process(filepath)
                
                if category == "Error":
                    logger.error(f"AI processing error: {ai_summary}")
                    return "Error", ai_summary, "", "", [], [], num_pages, "Neutral"
                
                ai_summary = remove_markdown_tags(ai_summary)
                return category, ai_summary, headline, financial_data, individual_investor_list, company_investor_list, num_pages, sentiment
            else:
                logger.error("PDF file not found after download attempt")
                return "Error", "PDF file not found after download attempt", "", "", [], [], None, "Neutral"
                
        except Exception as e:
            logger.error(f"Unexpected error processing PDF: {e}")
            return "Error", f"Unexpected error: {str(e)}", "", "", [], [], None, "Neutral"
        finally:
            # Clean up even if an error occurred
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    logger.info(f"Deleted temporary file: {filepath}")
                except Exception as e:
                    logger.warning(f"Failed to delete temporary file {filepath}: {e}")

    def ai_process(self, filename):
        """Process PDF with AI, with proper error handling"""
        if not filename:
            logger.error("No valid filename provided for AI processing")
            return "Error", "No valid filename provided", "", "", [], [], "Neutral"
            
        if not os.path.exists(filename):
            logger.error(f"File not found: {filename}")
            return "Error", "File not found", "", "", [], [], "Neutral"
            
        # Handle case where Gemini client failed to initialize
        if not genai_client:
            logger.error("Cannot process file: Gemini client not initialized")
            return "Procedural/Administrative", "AI processing unavailable", "", "", [], [], "Neutral"

        uploaded_file = None
        
        try:
            logger.info(f"Uploading file: {filename}")
            # Upload the PDF file
            uploaded_file = genai_client.files.upload(file=filename)
            
            # Generate content with structured output
            response = genai_client.generate_content(
                contents=[all_prompt, uploaded_file],
                config = {
                    "response_mime_type": "application/json",
                    "response_schema": list[StrucOutput]
                },
            )
            
            if not hasattr(response, 'text'):
                logger.error("AI response missing text attribute")
                return "Error", "AI processing failed: invalid response format", "", "", [], [], "Neutral"
                
            # Parse JSON response
            summary = json.loads(response.text.strip())
            
            # Extract all fields from the summary
            try:
                category_text = summary[0]["category"]
                headline = summary[0]["headline"]
                summary_text = summary[0]["summary"]
                financial_data = summary[0]["findata"]
                individual_investor_list = summary[0]["individual_investor_list"]
                company_investor_list = summary[0]["company_investor_list"]
                sentiment = summary[0]["sentiment"]
                
                logger.info(f"AI processing completed successfully for {filename}")
                logger.info(f"Category: {category_text}")
                return category_text, summary_text, headline, financial_data, individual_investor_list, company_investor_list, sentiment
            except (IndexError, KeyError) as e:
                logger.error(f"Failed to extract fields from AI response: {e}")
                return "Error", "Failed to extract fields from AI response", "", "", [], [], "Neutral"
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from AI response: {e}")
            return "Error", "Failed to parse AI response", "", "", [], [], "Neutral"
        except Exception as e:
            logger.error(f"Error in AI processing: {e}")
            return "Error", f"Error processing file: {str(e)}", "", "", [], [], "Neutral"

    def get_isin(self, scrip_id):
        """Get ISIN with error handling and retries"""
        if not scrip_id:
            logger.error("Invalid scrip ID for ISIN lookup")
            return "N/A"
            
        isin_url = f"https://api.bseindia.com/BseIndiaAPI/api/ComHeadernew/w?quotetype=EQ&scripcode={scrip_id}&seriesid="
        
        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.get(isin_url, headers=self.headers, timeout=self.request_timeout)
                response.raise_for_status()
                
                data = response.json()
                isin = data.get("ISIN", "N/A")
                logger.info(f"ISIN for {scrip_id}: {isin}")
                return isin
            except requests.exceptions.Timeout:
                logger.warning(f"ISIN request timed out (attempt {attempt}/{self.max_retries})")
            except requests.exceptions.HTTPError as e:
                logger.error(f"HTTP error getting ISIN: {e}")
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error getting ISIN: {e}")
            except ValueError as e:  # JSON decode error
                logger.error(f"Error parsing ISIN response: {e}")
            except Exception as e:
                logger.error(f"Unexpected error getting ISIN: {e}")
                
            if attempt < self.max_retries:
                wait_time = 5  # Fixed 5-second wait for consistency
                logger.info(f"Retrying ISIN lookup in {wait_time} seconds...")
                time.sleep(wait_time)
                
        logger.error(f"Failed to get ISIN for {scrip_id} after {self.max_retries} attempts")
        return "N/A"
    def _get_lock_file_path(self):
        """Get the path for the lock file specific to this scraper type"""
        script_name = Path(__file__).stem  # Gets 'bse_scraper' or 'nse_scraper'
        return get_data_dir() / f"{script_name}_processing.lock"
    
    @contextlib.contextmanager
    def _processing_lock(self):
        """Context manager for processing lock to prevent concurrent execution"""
        lock_file = self._get_lock_file_path()
        try:
            # Create lock file
            with open(lock_file, 'w') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)  # Non-blocking exclusive lock
                f.write(f"Locked by PID {os.getpid()} at {datetime.now().isoformat()}")
                logger.info(f"Acquired processing lock: {lock_file}")
                yield
        except BlockingIOError:
            logger.warning("Another instance is already processing announcements, skipping this run")
            raise
        except Exception as e:
            logger.error(f"Error with processing lock: {e}")
            raise
        finally:
            # Remove lock file
            try:
                if os.path.exists(lock_file):
                    os.remove(lock_file)
                    logger.info(f"Released processing lock: {lock_file}")
            except Exception as e:
                logger.error(f"Error removing lock file: {e}")

    def process_data(self, announcement):
        """Process a single announcement with comprehensive error handling"""
        try:
            # Extract and validate announcement data
            scrip_id = announcement.get("SCRIP_CD")
            bse_summary = announcement.get("HEADLINE", "")
            pdf_file = announcement.get("ATTACHMENTNAME", "")
            date_raw = announcement.get("NEWS_DT", "")
            date = date_raw.split('.')[0] if isinstance(date_raw, str) and date_raw and '.' in date_raw else date_raw
            company_name = announcement.get("SLONGNAME", "")
            company_url = announcement.get("NSURL", "")
            
            # Log the announcement being processed
            logger.info(f"Processing announcement: {bse_summary}")
            
            # Basic validation
            if not scrip_id:
                logger.warning("Skipping announcement without scrip ID")
                return False
                
            # Check if this is scrip_id 1 (special case to skip)
            if scrip_id == 1:
                logger.info("Skipping announcement with scrip_id 1")
                return False
                
            # Format company name if needed
            if isinstance(company_name, str) and company_name.endswith(" LTD"):
                company_name = company_name[:-4]
            
            # Extract symbol from URL
            symbol = extract_symbol(company_url)
            if symbol:
                symbol = symbol.upper()
            else:
                symbol = ""

            # Initialize default values
            ai_summary = None
            category = "Procedural/Administrative"
            headline = ""
            findata = '{"period": "", "sales_current": "", "sales_previous_year": "", "pat_current": "", "pat_previous_year": ""}'
            individual_investor_list = []
            company_investor_list = []
            num_pages = None
            sentiment = "Neutral"

            # Check for negative keywords
            if check_for_negative_keywords(bse_summary):
                logger.info(f"Negative keyword found in announcement: {bse_summary}")
                num_pages = 0
                ai_summary = "Please refer to the original document provided."  # No PDF processing
                
            elif check_for_pdf(pdf_file):
            # else :
                logger.info(f"Processing PDF: {pdf_file}")
                category, ai_summary, headline, findata, individual_investor_list, company_investor_list, num_pages, sentiment = self.process_pdf(pdf_file)
                if ai_summary:
                    ai_summary = remove_markdown_tags(ai_summary)
                    ai_summary = clean_summary(ai_summary)
                    # Mark PDF downloaded info into local DB (use newsid if present)
                    newsid = announcement.get("NEWSID")
                    if pdf_file and newsid:
                        # set downloaded_pdf_file, pdf_pages and timestamp
                        now_ts = datetime.now(timezone.utc).isoformat()
                        # num_pages might be None if not available; that's fine
                        update_announcement_checkpoint(
                            newsid=newsid,
                            db_path=LOCAL_DB_PATH,
                            downloaded_pdf_file=pdf_file,
                            pdf_pages=num_pages,
                            pdf_downloaded_at=now_ts
                        )
            # After AI processed (if ai_summary available and not error)
            if ai_summary and newsid:
                now_ts = datetime.now(timezone.utc).isoformat()
                update_announcement_checkpoint(
                    newsid=newsid,
                    db_path=LOCAL_DB_PATH,
                    ai_processed=1,
                    ai_summary=ai_summary,
                    ai_error=None,
                    ai_processed_at=now_ts
                )
            elif (category == "Error" or isinstance(ai_summary, str) and ai_summary.startswith("Error")) and newsid:
                # If AI returned error, still mark and store message
                now_ts = datetime.now(timezone.utc).isoformat()
                update_announcement_checkpoint(
                    newsid=newsid,
                    db_path=LOCAL_DB_PATH,
                    ai_processed=0,
                    ai_summary=None,
                    ai_error=str(ai_summary) if ai_summary else "AI processing error",
                    ai_processed_at=now_ts
                )
            # # Skip if PDF has too many pages (already handled in process_pdf, but double-check)
            # if num_pages and num_pages > 200:
            #     logger.warning(f"PDF has too many pages ({num_pages}), skipping")
            #     return False
            
            # Get ISIN
            isin = self.get_isin(scrip_id)

            # Validate ISIN format 
            if not isin or isin == "N/A" or (len(isin) > 3 and isin[2] != "E"):
                logger.warning(f"Invalid ISIN: {isin} for scrip_id {scrip_id}")
                # return False

            # Get company_id from Supabase - FIXED: properly extract the result
            company_id = None
            if supabase:
                try:
                    company_result = supabase.table("stocklistdata").select("company_id").eq("isin", isin).execute()
                    if company_result.data and len(company_result.data) > 0:
                        company_id = company_result.data[0].get("company_id")
                    else:
                        logger.warning(f"No company found for ISIN: {isin}")
                except Exception as e:
                    logger.error(f"Error fetching company_id: {e}")
                
            # Create file URL
            file_url = f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{pdf_file}" if pdf_file else None

            corp_id = str(uuid.uuid4())  # Generate a unique corp_id
            
            # Prepare data for upload
            data = {
                "corp_id": corp_id,
                "securityid": scrip_id,
                "summary": bse_summary,
                "fileurl": file_url,
                "date": date,
                "ai_summary": ai_summary,
                "category": category,
                "isin": isin,
                "companyname": company_name,
                "symbol": symbol,
                "sentiment": sentiment,
                "headline": headline,
                "company_id": company_id
            }
            logger.info(f"Prepared data for corp_id {corp_id}: {data}")
            
            

            # FIXED: Safe JSON parsing for financial data
            try:
                findata_parsed = json.loads(findata)
                period = findata_parsed.get("period", "")
                sales_current = findata_parsed.get("sales_current", "")
                sales_previous_year = findata_parsed.get("sales_previous_year", "")
                pat_current = findata_parsed.get("pat_current", "")
                pat_previous_year = findata_parsed.get("pat_previous_year", "")
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to parse financial data: {e}")
                period = sales_current = sales_previous_year = pat_current = pat_previous_year = ""

            financial_data = {
                "corp_id": corp_id,
                "company_id": company_id,
                "period": period,
                "sales_current": sales_current,
                "sales_previous_year": sales_previous_year,
                "pat_current": pat_current,
                "pat_previous": pat_previous_year,
                "fileurl": file_url,
                "isin": isin,
                "verified": "false"
            }
            logger.info(f"Prepared financial data for corp_id {corp_id}: {financial_data}")
            
            # Only upload to Supabase if we have a connection
            if supabase:
                inserted = False
                # Retry only the insert operation
                for attempt in range(1, self.max_retries + 1):
                    try:
                        response = supabase.table("corporatefilings").insert(data).execute()
                        logger.info(f"Inserted data to Supabase for {scrip_id} (attempt {attempt})")
                        if newsid:
                            update_announcement_checkpoint(
                                newsid=newsid,
                                db_path=LOCAL_DB_PATH,
                                sent_to_supabase=1,
                                sent_to_supabase_at=datetime.now(timezone.utc).isoformat()
                            )
                        inserted = True
                        break
                    except Exception as e:
                        err_text = str(e)
                        logger.error(f"Error inserting to Supabase (attempt {attempt}/{self.max_retries}): {err_text}")

                        # If duplicate primary-key, stop retrying — row already exists
                        if "duplicate key" in err_text or "23505" in err_text:
                            logger.warning(f"Duplicate key for corp_id {corp_id} — assuming row already exists, stopping insert retries.")
                            if newsid:
                                update_announcement_checkpoint(
                                    newsid=newsid,
                                    db_path=LOCAL_DB_PATH,
                                    sent_to_supabase=1,
                                    sent_to_supabase_at=datetime.now(timezone.utc).isoformat()
                                )
                            inserted = True  # mark as present so investor upload will run (or you can choose not to)
                            break

                        # Otherwise treat as transient and retry
                        if attempt < self.max_retries:
                            wait_time = 5
                            logger.info(f"Retrying insert in {wait_time} seconds...")
                            time.sleep(wait_time)
                        else:
                            logger.error(f"Failed to insert after {self.max_retries} attempts")

                # Only attempt investor upload if the row exists or was inserted just now
                if inserted and (individual_investor_list or company_investor_list):
                    # Isolate investor uploads so errors here don't trigger insert retries
                    inv_attempts = 3
                    for inv_try in range(1, inv_attempts + 1):
                        try:
                            uploadInvestor(individual_investor_list, company_investor_list, corp_id=corp_id, saved_price=None)
                            logger.info(f"Uploaded investor data for corp_id: {corp_id}")
                            break
                        except Exception as ie:
                            logger.error(f"Error uploading investor data (attempt {inv_try}/{inv_attempts}): {ie}")
                            if inv_try < inv_attempts:
                                time.sleep(2)
                            else:
                                logger.error(f"Failed to upload investor data after {inv_attempts} attempts for corp_id {corp_id}")
                else:
                    if not inserted:
                        logger.warning("Skipping investor upload because insert failed and row is not present.")
                    else:
                        logger.info("No investor data to upload.")

                # Upload financial data only if we have meaningful data
                if any([period, sales_current, sales_previous_year, pat_current, pat_previous_year]):
                    safely_upload_financial_data(supabase, financial_data, symbol, isin, self.max_retries)

            else:
                logger.warning("Supabase not connected, skipping database upload")
            
            return data

                        
        except Exception as e:
            logger.error(f"Unexpected error processing announcement: {e}")
            return False

    def processNewAnnouncements(self):
        """Process ALL new announcements, not just the latest one"""
        try:
            # Use processing lock to prevent concurrent execution
            with self._processing_lock():
                announcements = self.fetch_data()
                if announcements:
                    try:
                        save_raw_fetch(announcements, url=self.url, params=self.params)
                    except Exception as e:
                        logger.error(f"Failed to save raw fetch to local DB: {e}")
                if not announcements:
                    logger.warning("No announcements found")
                    return False
                    
                # Load the last processed announcement
                last_latest_announcement = load_latest_announcement()
                
                # If no previous announcement saved, process only the latest one (first run)
                if not last_latest_announcement:
                    logger.info("No previous announcement found, processing latest announcement only")
                    data = self.process_data(announcements[0])
                    if data:
                        save_latest_announcement(announcements[0])
                        self._send_to_api_if_needed(data)
                    return True
                
                # Find all new announcements
                new_announcements = []
                last_newsid = last_latest_announcement.get('NEWSID')
                
                for announcement in announcements:
                    current_newsid = announcement.get('NEWSID')
                    
                    # Stop when we reach the last processed announcement
                    if current_newsid == last_newsid:
                        break
                        
                    new_announcements.append(announcement)
                
                if not new_announcements:
                    logger.info("No new announcements to process")
                    return False
                
                logger.info(f"Found {len(new_announcements)} new announcements to process")
                
                # Process new announcements in reverse order (oldest first)
                # This ensures proper chronological processing
                new_announcements.reverse()
                
                processed_count = 0
                for i, announcement in enumerate(new_announcements):
                    logger.info(f"Processing new announcement {i+1}/{len(new_announcements)}")
                    
                    data = self.process_data(announcement)
                    if data:
                        processed_count += 1
                        self._send_to_api_if_needed(data)
                        
                    # Small delay between processing announcements
                    time.sleep(0.5)
                
                # Save the newest announcement as the latest processed
                if new_announcements:
                    # Save the newest one (last in reversed list)
                    newest_announcement = new_announcements[-1]
                    save_latest_announcement(newest_announcement)
                    logger.info(f"Processed {processed_count} new announcements")
                    
                return processed_count > 0
                            
        except BlockingIOError:
            logger.info("Skipping this run - another instance is already processing")
            return False
        except Exception as e:
            logger.error(f"Error in processNewAnnouncements: {e}")
            return False

    def _send_to_api_if_needed(self, data):
        """Helper method to send data to API if needed"""
        if data.get("category") == "Procedural/Administrative":
            logger.info("Announcement is Procedural/Administrative, skipping API call")
            return
        
        # Send to API endpoint (which will handle websocket communication)
        try:
            post_url = "http://localhost:8000/api/insert_new_announcement"  # BSE
            data["is_fresh"] = True  # Mark as fresh for broadcasting
            res = requests.post(url=post_url, json=data)
            if res.status_code >= 200 and res.status_code < 300:
                logger.info(f"Sent to API for websocket: Status code {res.status_code}")
            else:
                logger.error(f"API returned error: {res.status_code}, {res.text}")
        except Exception as e:
            logger.error(f"Error sending to API: {e}")

    def run_continuous(self, check_interval=10):
        """Updated continuous mode to use the new logic"""
        while True:
            try:
                if self.processNewAnnouncements():  # Changed from processLatestAnnouncement
                    logger.info("New announcements processed successfully")
                else:
                    logger.info("No new announcements to process")
                    
                time.sleep(check_interval)
            except Exception as e:
                logger.error(f"Error in continuous mode: {e}")
                time.sleep(check_interval)

    def run(self):
        """Updated main method to use the new logic"""
        logger.info("Starting BSE scraper run")
        
        # Process new announcements (this will handle both first run and subsequent runs)
        success = self.processNewAnnouncements()  # Changed from processLatestAnnouncement
        
        return success



if __name__ == "__main__":
    today = datetime.today().strftime('%Y%m%d')
    scraper = BseScraper(today, today)
    
    try:
        # Run in standalone mode with continuous monitoring
        scraper.run_continuous(check_interval=10)
    except KeyboardInterrupt:
        logger.info("Script stopped by user")
    except Exception as e:
        logger.error(f"Script terminated due to error: {e}")