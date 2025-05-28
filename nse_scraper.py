"""
NSE Corporate Announcements Scraper

This script fetches and processes corporate announcements from NSE (National Stock Exchange).

Required Environment Variables:
- GEMINI_API_KEY: API key for Google Gemini AI (for PDF processing)
- SUPABASE_URL2: Your Supabase project URL
- SUPABASE_KEY2: Your Supabase API key

Optional Environment Variables:
- PROMPT: Custom prompt for AI processing
- WEBSOCKET_API_ENDPOINT: API endpoint for real-time notifications (default: http://localhost:5001/api/insert_new_announcement)
- ENABLE_WEBSOCKET_API: Set to 'false' to disable WebSocket notifications (default: 'true')

Dependencies:
- pip install requests google-generativeai python-dotenv supabase
- pip install PyPDF2  # Optional, for PDF page counting

Example .env file:
GEMINI_API_KEY=your_gemini_api_key
SUPABASE_URL2=https://your-project.supabase.co
SUPABASE_KEY2=your_supabase_key
WEBSOCKET_API_ENDPOINT=http://localhost:5001/api/insert_new_announcement
ENABLE_WEBSOCKET_API=true

To disable WebSocket API errors when the API server is not running:
ENABLE_WEBSOCKET_API=false
"""

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
from datetime import datetime
import uuid
import threading
from pathlib import Path
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
try:
    import PyPDF2
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("nse_scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("NSEScraper")

# Note: This script requires PyPDF2 for PDF page counting
# Install with: pip install PyPDF2

# Load environment variables
load_dotenv()

# Check if PyPDF2 is available
if not PDF_SUPPORT:
    logger.warning("PyPDF2 not installed. PDF page counting will be disabled.")
    logger.warning("Install with: pip install PyPDF2")

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    logger.error("Missing GEMINI_API_KEY environment variable")
    logger.warning("Will skip AI processing without GEMINI_API_KEY")

SUPABASE_URL = os.getenv("SUPABASE_URL2")
SUPABASE_KEY = os.getenv("SUPABASE_KEY2")
if not (SUPABASE_URL and SUPABASE_KEY):
    logger.error("Missing Supabase credentials")
    logger.warning("Will operate in limited mode without Supabase credentials")

# API endpoint configuration
API_ENDPOINT = os.getenv("WEBSOCKET_API_ENDPOINT", "http://localhost:8000/api/insert_new_announcement")
ENABLE_WEBSOCKET_API = os.getenv("ENABLE_WEBSOCKET_API", "true").lower() == "true"

if ENABLE_WEBSOCKET_API:
    logger.info(f"WebSocket API enabled. Endpoint: {API_ENDPOINT}")
else:
    logger.info("WebSocket API disabled")

# Initialize Supabase client
supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        logger.warning("Continuing without Supabase connection")
else:
    logger.warning("Supabase credentials not provided. Database operations will be skipped.")
    logger.warning("Set SUPABASE_URL2 and SUPABASE_KEY2 environment variables to enable database storage.")

# Add functions to handle announcement tracking in JSON file
def get_data_dir():
    """Get or create the data directory"""
    # Create a 'data' directory in the same folder as this script
    data_dir = Path(__file__).parent / "data"
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

def save_latest_announcement(announcement, filename=None):
    """Save the latest announcement details to a JSON file"""
    if filename is None:
        filename = get_data_dir() / "latest_announcement_nse.json"
    try:
        with open(filename, 'w') as f:
            json.dump(announcement, f, indent=4)
        logger.info(f"Saved latest announcement to {filename}")
    except Exception as e:
        logger.error(f"Error saving latest announcement to file: {e}")

def load_latest_announcement(filename=None):
    """Load the latest processed announcement from JSON file"""
    if filename is None:
        filename = get_data_dir() / "latest_announcement_nse.json"
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
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
    fields_to_compare = ['symbol', 'sort_date', 'attchmntText', 'attchmntFile']
    
    return all(a1.get(field) == a2.get(field) for field in fields_to_compare)


class RateLimitedGeminiClient:
    def __init__(self, api_key, rpm_limit=15, max_retries=3):
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

    def generate_content(self, model, contents):
        """Rate-limited wrapper for generate_content with retries"""
        if not self.client:
            raise Exception("Gemini client not initialized")
            
        for attempt in range(1, self.max_retries + 1):
            try:
                self._enforce_rate_limit()
                return self.client.models.generate_content(model=model, contents=contents)
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
    if not text:  # Handle None or empty string
        return None
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
    if not text:  # Handle None or empty string
        return None
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
        "Record Date",
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


def get_pdf_page_count(filepath):
    """Get the number of pages in a PDF file"""
    if not PDF_SUPPORT:
        logger.warning("PyPDF2 not installed, cannot count PDF pages")
        return None
    
    try:
        with open(filepath, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            page_count = len(pdf_reader.pages)
            logger.info(f"PDF has {page_count} pages")
            return page_count
    except Exception as e:
        logger.error(f"Error counting PDF pages: {e}")
        return None


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


# Initialize Gemini client with retries
genai_client = None
try:
    if API_KEY:
        genai_client = RateLimitedGeminiClient(api_key=API_KEY)
except Exception as e:
    logger.error(f"Failed to initialize Gemini client: {e}")
    logger.warning("AI processing will be skipped")

def get_category(text):
    category_prompt = """now please categorize the document into one of the categories: [
    "Annual Report",
    "Agreements/MoUs",
    "Anti-dumping Duty",
    "Buyback",
    "Bonus/Stock Split",
    "Change in Address",
    "Change in MOA",
    "Clarifications/Confirmations",
    "Closure of Factory",
    "Concall Transcript",
    "Consolidation of Shares",
    "Credit Rating",
    "Debt Reduction",
    "Debt & Financing",
    "Delisting",
    "Demerger",
    "Change in KMP",
    "Demise of KMP",
    "Disruption of Operations",
    "Divestitures",
    "DRHP",
    "Expansion",
    "Financial Results",
    "Fundraise - Preferential Issue",
    "Fundraise - QIP",
    "Fundraise - Rights Issue",
    "Global Pharma Regulation",
    "Incorporation/Cessation of Subsidiary",
    "Increase in Share Capital",
    "Insolvency and Bankruptcy",
    "Interest Rates Updates",
    "Investor Presentation",
    "Investor/Analyst Meet",
    "Joint Ventures",
    "Litigation & Notices",
    "Mergers/Acquisitions",
    "Name Change",
    "New Order",
    "New Product",
    "One Time Settlement (OTS)",
    "Open Offer",
    "Operational Update",
    "PLI Scheme",
    "Procedural/Administrative",
    "Reduction in Share Capital",
    "Regulatory Approvals/Orders",
    "Trading Suspension",
    "USFDA"
]
just mention the category , nothing else.
"""
    chat_session = genai_client.chats().create(model="gemini-2.0-flash")
    response = chat_session.send_message(
        [category_prompt, text]
    )
    return response.text.strip() if hasattr(response, 'text') else "Category not generated"


class NseScraper:
    """
    NSE Corporate Announcements Scraper
    
    Environment Variables:
    - GEMINI_API_KEY: API key for Gemini AI processing
    - SUPABASE_URL2: Supabase project URL
    - SUPABASE_KEY2: Supabase API key
    - PROMPT: Custom prompt for AI processing (optional)
    - WEBSOCKET_API_ENDPOINT: API endpoint for WebSocket notifications (default: http://localhost:5001/api/insert_new_announcement)
    - ENABLE_WEBSOCKET_API: Enable/disable WebSocket API calls (default: true)
    """
    def __init__(self, prev_date, to_date, max_retries=3, request_timeout=30):
        self.prev_date = prev_date
        self.to_date = to_date
        
        # Configure a session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        
        # Base headers that look like a real browser
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            "Upgrade-Insecure-Requests": "1"
        }
        self.session.headers.update(self.headers)

        self.max_retries = max_retries
        self.request_timeout = request_timeout
        self.temp_dir = tempfile.mkdtemp(prefix="nse_scraper_")
        logger.info(f"Created temporary directory: {self.temp_dir}")
        
        # Track if this is the first run
        self.first_run_flag_path = get_data_dir() / "first_run_complete.txt"
    
    def _initialize_session(self):
        """Visit NSE pages to obtain necessary cookies"""
        logger.info("Initializing session...")
        
        try:
            # Step 1: Visit NSE homepage
            logger.info("Visiting NSE homepage...")
            resp = self.session.get("https://www.nseindia.com/", timeout=30)
            resp.raise_for_status()
            logger.info(f"Homepage status: {resp.status_code}")
            
            # Step 2: Visit corporate announcements page
            self.session.headers.update({
                "Referer": "https://www.nseindia.com/",
                "Sec-Fetch-Site": "same-origin"
            })
            
            logger.info("Visiting corporate announcements page...")
            resp = self.session.get(
                "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
                timeout=30
            )
            resp.raise_for_status()
            logger.info(f"Announcements page status: {resp.status_code}")
            
            # Print cookies for debugging
            logger.info(f"Session has {len(self.session.cookies)} cookies")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error initializing session: {e}")
            return False

    def __del__(self):
        """Clean up temporary directory on object destruction"""
        try:
            if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                logger.info(f"Removed temporary directory: {self.temp_dir}")
        except Exception as e:
            logger.error(f"Error cleaning up temporary directory: {e}")
            
        # Close session if it exists
        try:
            if hasattr(self, 'session'):
                self.session.close()
        except Exception as e:
            logger.error(f"Error closing session: {e}")

    def fetch_data(self):
        """Fetch corporate announcements for the given date range"""
        if not self._initialize_session():
            logger.error("Failed to initialize session, cannot proceed.")
            return None
        
        # Update headers for API request
        self.session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors"
        })
        
        # Prepare API request
        api_url = "https://www.nseindia.com/api/corporate-announcements"
        params = {
            "index": "equities",
            "from_date": self.prev_date,
            "to_date": self.to_date
        }
        
        logger.info(f"Requesting API data from {self.prev_date} to {self.to_date}...")
        try:
            # Make the request
            response = self.session.get(api_url, params=params, timeout=30)
            response.raise_for_status()
            
            logger.info(f"API response status: {response.status_code}")
            
            # Handle potential encoding issues
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                # Try manual decoding
                try:
                    content = response.content.decode('utf-8')
                    data = json.loads(content)
                except Exception as e2:
                    logger.error(f"Could not parse response as JSON: {e2}")
                    logger.error(f"Response headers: {response.headers}")
                    logger.error(f"First 200 bytes: {response.content[:200]}")
                    return None
            
            # Validate data structure
            if not isinstance(data, list):
                logger.error(f"Expected list of announcements, got {type(data)}")
                return None
                
            logger.info(f"Successfully fetched {len(data)} announcements")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching announcements: {e}")
            return None

    def ai_process(self, filename):
        """Process PDF with AI, with proper error handling"""
        if not filename:
            logger.error("No valid filename provided for AI processing")
            return "Error", "No valid filename provided"
            
        if not os.path.exists(filename):
            logger.error(f"File not found: {filename}")
            return "Error", "File not found"
            
        # Handle case where Gemini client failed to initialize
        if not genai_client or not genai_client.client:
            logger.error("Cannot process file: Gemini client not initialized")
            return "Procedural/Administrative", "AI processing unavailable"

        uploaded_file = None
        chat_session = None
        
        try:
            logger.info(f"Uploading file: {filename}")
            # Upload the PDF file
            uploaded_file = genai_client.files.upload(file=filename)
            
            # Create a chat session
            chat_session = genai_client.chats().create(model="gemini-2.0-flash-exp")
            
            prompt = os.getenv("PROMPT", "Please analyze this corporate announcement and provide a category and summary.")
            
            # Include the file in the message
            response = chat_session.send_message([prompt, uploaded_file])
            
            if not hasattr(response, 'text'):
                logger.error("AI response missing text attribute")
                return "Error", "AI processing failed: invalid response format"
                
            summary_text = response.text.strip()
            
            # Extract category from the summary
            try:
                category_text = summary_text.split("**Category:**")[1].split("**Headline:**")[0].strip()
                logger.info(f"Category: {category_text}")
                return category_text, summary_text
            except IndexError:
                logger.error("Failed to extract category from AI response")
                return "Procedural/Administrative", summary_text
                
        except Exception as e:
            logger.error(f"Error in AI processing: {e}")
            return "Error", f"Error processing file: {str(e)}"

    def process_pdf(self, url, max_pages=200):
        """Download and process PDF with error handling"""
        if not url:
            logger.error("No PDF file specified")
            return "Error", "No PDF file specified"
            
        # Use the temp directory for downloads
        filepath = os.path.join(self.temp_dir, url.split("/")[-1])
        
        try:
            # Download with retries
            for attempt in range(1, self.max_retries + 1):
                try:
                    response = requests.get(url, timeout=self.request_timeout, headers=self.headers)
                    response.raise_for_status()
                    
                    with open(filepath, "wb") as file:
                        file.write(response.content)
                    logger.info(f"Downloaded: {filepath}")
                    break
                except requests.exceptions.Timeout:
                    logger.warning(f"PDF download timed out (attempt {attempt}/{self.max_retries})")
                except requests.exceptions.HTTPError as e:
                    logger.error(f"HTTP error downloading PDF: {e}")
                    return "Error", f"Failed to download PDF: HTTP error {e.response.status_code}"
                except requests.exceptions.RequestException as e:
                    logger.error(f"Error downloading PDF (attempt {attempt}/{self.max_retries}): {e}")
                
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying download in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.error("Failed to download PDF after all retries")
                    return "Error", "Failed to download PDF after multiple attempts"
                    
            # Process the PDF if download was successful
            if os.path.exists(filepath):
                # Check page count
                page_count = get_pdf_page_count(filepath)
                if page_count is not None and page_count > max_pages:
                    logger.warning(f"PDF has {page_count} pages, exceeding {max_pages} page limit. Skipping AI processing.")
                    return None  # Return None for ai_summary
                elif page_count is None and PDF_SUPPORT:
                    logger.warning("Could not determine PDF page count, proceeding with AI processing")
                
                category, ai_summary = self.ai_process(filepath)
                if category == "Error":
                    logger.error(f"AI processing error: {ai_summary}")
                    return "Error", ai_summary
                
                if ai_summary:
                    ai_summary = remove_markdown_tags(ai_summary)
                return category, ai_summary
            else:
                logger.error("PDF file not found after download attempt")
                return "Error", "PDF file not found after download attempt"
                
        except Exception as e:
            logger.error(f"Unexpected error processing PDF: {e}")
            return "Error", f"Unexpected error: {str(e)}"
        finally:
            # Clean up even if an error occurred
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    logger.info(f"Deleted temporary file: {filepath}")
                except Exception as e:
                    logger.warning(f"Failed to delete temporary file {filepath}: {e}")

    def process_data(self, announcement):
        """Process a single announcement with comprehensive error handling"""
        try:
            # Extract and validate announcement data
            symbol = announcement.get("symbol")
            summary = announcement.get("attchmntText", "")
            url = announcement.get("attchmntFile", "")
            date = announcement.get("sort_date", "")
            if date:
                date = date.replace(" ", "T")
            company_name = announcement.get("sm_name", "")
            isin = announcement.get("sm_isin", "")
            
            # Log the announcement being processed
            logger.info(f"Processing announcement: {summary[:100]}...")
            
            # Check for negative keywords first
            if check_for_negative_keywords(summary):
                logger.info(f"Negative keyword found in announcement - skipping processing")
                return None  # Skip this announcement entirely
            
            # Format company name if needed
            if isinstance(company_name, str) and company_name.endswith(" LTD"):
                company_name = company_name[:-4]
            
            # Initialize variables
            ai_summary = None
            category = "Procedural/Administrative"
            securityid = ""
            newnsecode_exists = False
            
            # Validate ISIN format and check for newnsecode
            if isin and isin != "N/A" and len(isin) >= 3:
                if isin[2] == "E":  # Valid Indian equity ISIN
                    if supabase:
                        try:
                            # Fetch both securityid and newnsecode
                            result = supabase.table("dhanstockdata").select("securityid,newnsecode").eq("isin", isin).execute()
                            if result.data and len(result.data) > 0:
                                securityid = result.data[0].get("securityid", "")
                                newnsecode = result.data[0].get("newnsecode")
                                if newnsecode:  # Check if newnsecode exists and is not null/empty
                                    newnsecode_exists = True
                                    logger.info(f"Found newnsecode: {newnsecode} for ISIN: {isin}")
                                else:
                                    logger.warning(f"No newnsecode found for ISIN: {isin}")
                            else:
                                logger.warning(f"No data found for ISIN: {isin}")
                        except Exception as e:
                            logger.error(f"Error fetching data for ISIN {isin}: {e}")
                else:
                    logger.warning(f"Invalid ISIN format: {isin}")
            
            # Process PDF only if it exists and newnsecode exists
            if check_for_pdf(url):
                if newnsecode_exists:
                    logger.info(f"Processing PDF: {url}")
                    category, ai_summary = self.process_pdf(url) 
                    if ai_summary and category != "Error":
                        ai_summary = remove_markdown_tags(ai_summary)
                        if ai_summary:  # Check again after removing markdown
                            ai_summary = clean_summary(ai_summary)
                else:
                    logger.info(f"Skipping PDF processing - no newnsecode found for ISIN: {isin}")
                    # Still prepare data but without AI processing
            
            # Prepare data for upload
            data = {
                "corp_id": str(uuid.uuid4()),
                "securityid": securityid,
                "summary": summary,
                "fileurl": url,
                "date": date,
                "ai_summary": ai_summary,
                "category": category,
                "isin": isin,
                "companyname": company_name,
                "symbol": symbol
            }
            
            # Only upload to Supabase if we have a connection
            if supabase:
                # Upload to Supabase with retries
                for attempt in range(1, self.max_retries + 1):
                    try:
                        response = supabase.table("corporatefilings").insert(data).execute()
                        logger.info(f"Data uploaded to Supabase for {symbol} (ISIN: {isin})")
                        break
                    except Exception as e:
                        logger.error(f"Error uploading to Supabase (attempt {attempt}/{self.max_retries}): {e}")
                        
                        if attempt < self.max_retries:
                            wait_time = 2 ** attempt
                            logger.info(f"Retrying upload in {wait_time} seconds...")
                            time.sleep(wait_time)
                        else:
                            logger.error(f"Failed to upload after {self.max_retries} attempts")
            else:
                logger.warning("Supabase not connected, skipping database upload")

            return data 
                        
        except Exception as e:
            logger.error(f"Unexpected error processing announcement: {e}")
            return None

    def processLatestAnnouncement(self):
        """Process the latest announcement and send to database and websocket"""
        try:
            announcements = self.fetch_data()
            if not announcements:
                logger.warning("No announcements found")
                return False
            
            if not isinstance(announcements, list) or len(announcements) == 0:
                logger.warning("Invalid announcements data structure")
                return False
                
            latest_announcement = announcements[0]
            last_latest_announcement = load_latest_announcement()

            if announcements_are_equal(latest_announcement, last_latest_announcement):
                logger.info("No new announcements to process")
                return False
            else:
                logger.info("New announcement found, processing...")
                data = self.process_data(latest_announcement)
                
                if data:  # Check if process_data returned valid data
                    save_latest_announcement(latest_announcement)
                    
                    # Send to API endpoint (which will handle websocket communication)
                    if ENABLE_WEBSOCKET_API:
                        try:
                            data["is_fresh"] = True  # Mark as fresh for broadcasting
                            res = requests.post(url=API_ENDPOINT, json=data, timeout=10)
                            if res.status_code >= 200 and res.status_code < 300:
                                logger.info(f"Sent to API for websocket: Status code {res.status_code}")
                            else:
                                logger.error(f"API returned error: {res.status_code}, {res.text}")
                        except requests.exceptions.ConnectionError as e:
                            logger.warning(f"Could not connect to WebSocket API at {API_ENDPOINT}")
                            logger.warning("This is normal if the API server is not running")
                            logger.info("To disable these warnings, set ENABLE_WEBSOCKET_API=false in your .env file")
                        except requests.exceptions.Timeout:
                            logger.warning(f"WebSocket API request timed out after 10 seconds")
                        except Exception as e:
                            logger.error(f"Unexpected error sending to API: {e}")
                    else:
                        logger.info("WebSocket API disabled, skipping notification")
                        
                    return True
                else:
                    logger.warning("Failed to process latest announcement")
                    return False
        except Exception as e:
            logger.error(f"Error in processLatestAnnouncement: {e}")
            return False
    
    def process_all_announcements(self):
        """Process all announcements"""
        try:
            announcements = self.fetch_data()
            if not announcements:
                logger.warning("No announcements found")
                return False
            
            if not isinstance(announcements, list):
                logger.error("Invalid announcements data structure")
                return False
                
            logger.info(f"Processing {len(announcements)} announcements")
            
            # Process all announcements
            processed_count = 0
            skipped_count = 0
            for i, announcement in enumerate(announcements):
                try:
                    logger.info(f"Processing announcement {i+1}/{len(announcements)}")
                    result = self.process_data(announcement)
                    if result:
                        processed_count += 1
                    else:
                        skipped_count += 1
                        logger.info(f"Skipped announcement {i+1}")
                    time.sleep(1)  # Small delay to avoid overwhelming the API
                except Exception as e:
                    logger.error(f"Error processing announcement {i+1}: {e}")
                    continue
                    
            logger.info(f"Successfully processed {processed_count}/{len(announcements)} announcements, skipped {skipped_count}")
            return processed_count > 0
        except Exception as e:
            logger.error(f"Error in process_all_announcements: {e}")
            return False
    
    def check_api_health(self):
        """Check if the WebSocket API endpoint is reachable"""
        if not ENABLE_WEBSOCKET_API:
            logger.info("WebSocket API is disabled")
            return True
            
        try:
            # Try a simple GET request to check if the server is up
            # Most APIs respond to GET even if they expect POST
            response = requests.get(API_ENDPOINT.replace('/insert_new_announcement', ''), timeout=5)
            logger.info(f"API health check: Server responded with status {response.status_code}")
            return True
        except requests.exceptions.ConnectionError:
            logger.warning(f"API health check: Cannot connect to {API_ENDPOINT}")
            logger.warning("The scraper will continue but WebSocket notifications will fail")
            return False
        except Exception as e:
            logger.warning(f"API health check failed: {e}")
            return False
    
    def run_continuous(self, check_interval=10):
        """Run the scraper in continuous mode, checking for new announcements at regular intervals"""
        logger.info(f"Starting continuous mode with {check_interval}s check interval")
        
        api_check_counter = 0
        api_available = self.check_api_health()
        
        while True:
            try:
                # Periodically recheck API availability every 10 iterations
                api_check_counter += 1
                if api_check_counter >= 10:
                    api_check_counter = 0
                    new_api_status = self.check_api_health()
                    if new_api_status != api_available:
                        api_available = new_api_status
                        if api_available:
                            logger.info("WebSocket API is now available")
                        else:
                            logger.warning("WebSocket API is no longer available")
                
                if self.processLatestAnnouncement():
                    logger.info("New announcement processed successfully")
                else:
                    logger.info("No new announcements to process")
                    
                time.sleep(check_interval)
            except KeyboardInterrupt:
                logger.info("Continuous mode stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in continuous mode: {e}")
                time.sleep(check_interval)
    
    def run(self):
        """Main method to run the scraper - compatible with liveserver.py"""
        logger.info("Starting NSE scraper run")
        
        try:
            # Check if this is the first run
            is_first_run = not os.path.exists(self.first_run_flag_path)
            
            if is_first_run:
                logger.info("First run detected - processing all announcements")
                # Process all announcements on first run
                success = self.process_all_announcements()
                
                if success:
                    # Create the flag file to mark first run as complete
                    try:
                        with open(self.first_run_flag_path, 'w') as f:
                            f.write(f"First run completed at {datetime.now().isoformat()}")
                        logger.info("First run flag created")
                    except Exception as e:
                        logger.error(f"Error creating first run flag: {e}")
                
                # Also process the latest announcement to send a WebSocket message
                latest_success = self.processLatestAnnouncement()
                
                return success or latest_success
            else:
                logger.info("Incremental run - processing only the latest announcement")
                # Process only the latest announcement on subsequent runs
                return self.processLatestAnnouncement()
        except Exception as e:
            logger.error(f"Error in run method: {e}")
            return False


if __name__ == "__main__":
    try:
        today = datetime.today().strftime('%d-%m-%Y')  # NSE expects DD-MM-YYYY format
        scraper = NseScraper(today, today)
        
        # Check API health before starting
        scraper.check_api_health()
        
        # Print configuration info
        logger.info("=" * 50)
        logger.info("NSE Scraper Configuration:")
        logger.info(f"Date Range: {today} to {today}")
        logger.info(f"Gemini AI: {'Enabled' if API_KEY else 'Disabled (no API key)'}")
        logger.info(f"Supabase: {'Connected' if supabase else 'Disconnected'}")
        logger.info(f"WebSocket API: {'Enabled' if ENABLE_WEBSOCKET_API else 'Disabled'}")
        if ENABLE_WEBSOCKET_API:
            logger.info(f"API Endpoint: {API_ENDPOINT}")
        logger.info(f"PDF Page Counting: {'Enabled' if PDF_SUPPORT else 'Disabled (install PyPDF2)'}")
        logger.info("=" * 50)
        
        # Run in standalone mode with continuous monitoring
        scraper.run_continuous(check_interval=10)
    except KeyboardInterrupt:
        logger.info("Script stopped by user")
    except Exception as e:
        logger.error(f"Script terminated due to error: {e}")