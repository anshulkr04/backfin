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
if not (SUPABASE_URL and SUPABASE_KEY):
    logger.error("Missing Supabase credentials")
    logger.warning("Will operate in limited mode without Supabase credentials")

# Initialize Supabase client
supabase = None
try:
    if SUPABASE_URL and SUPABASE_KEY:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Supabase client: {e}")
    logger.warning("Continuing without Supabase connection")

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
        filename = get_data_dir() / "latest_announcement_bse.json"
    try:
        with open(filename, 'w') as f:
            json.dump(announcement, f, indent=4)
        logger.info(f"Saved latest announcement to {filename}")
    except Exception as e:
        logger.error(f"Error saving latest announcement to file: {e}")

def load_latest_announcement(filename=None):
    """Load the latest processed announcement from JSON file"""
    if filename is None:
        filename = get_data_dir() / "latest_announcement_bse.json"
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
    fields_to_compare = ['XML_NAME']
    
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
        "Spurt","Grievance Redressal","Monitoring Agency","Regulation",
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


# Initialize Gemini client with retries
genai_client = None
try:
    if API_KEY:
        genai_client = RateLimitedGeminiClient(api_key=API_KEY)
except Exception as e:
    logger.error(f"Failed to initialize Gemini client: {e}")
    logger.warning("AI processing will be skipped")


class BseScraper:
    def __init__(self, prev_date, to_date, max_retries=3, request_timeout=30):
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
        
        # Track if this is the first run
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
                wait_time = 2 ** attempt  # Exponential backoff
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                logger.error(f"Failed to fetch data after {self.max_retries} attempts")
                return []  # Return empty list after all retries fail

    def ai_process(self, filename):
        """Process PDF with AI, with proper error handling"""
        if not filename:
            logger.error("No valid filename provided for AI processing")
            return "Error", "No valid filename provided"
            
        if not os.path.exists(filename):
            logger.error(f"File not found: {filename}")
            return "Error", "File not found"
            
        # Handle case where Gemini client failed to initialize
        if not genai_client:
            logger.error("Cannot process file: Gemini client not initialized")
            return "Procedural/Administrative", "AI processing unavailable"

        uploaded_file = None
        chat_session = None
        
        try:
            logger.info(f"Uploading file: {filename}")
            # Upload the PDF file
            uploaded_file = genai_client.files.upload(file=filename)
            
            # Create a chat session
            chat_session = genai_client.chats().create(model="gemini-2.0-flash")
            
            prompt = os.getenv("PROMPT")
            
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
                return "Error", "Failed to extract category from AI response"
                
        except Exception as e:
            logger.error(f"Error in AI processing: {e}")
            return "Error", f"Error processing file: {str(e)}"

    def process_pdf(self, pdf_file, max_pages=200):
        """Download and process PDF with error handling"""
        if not pdf_file:
            logger.error("No PDF file specified")
            return "Error", "No PDF file specified"
            
        # Use the temp directory for downloads
        filepath = os.path.join(self.temp_dir, pdf_file.split("/")[-1])
        
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
                category, ai_summary = self.ai_process(filepath)
                if category == "Error":
                    logger.error(f"AI processing error: {ai_summary}")
                    return "Error", ai_summary
                
                
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
                wait_time = 2 ** attempt
                logger.info(f"Retrying ISIN lookup in {wait_time} seconds...")
                time.sleep(wait_time)
                
        logger.error(f"Failed to get ISIN for {scrip_id} after {self.max_retries} attempts")
        return "N/A"

    def process_data(self, announcement):
        """Process a single announcement with comprehensive error handling"""
        try:
            # Extract and validate announcement data
            scrip_id = announcement.get("SCRIP_CD")
            bse_summary = announcement.get("HEADLINE", "")
            pdf_file = announcement.get("ATTACHMENTNAME", "")
            date = announcement.get("News_submission_dt")
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

            ai_summary = None
            category = "Procedural/Administrative"
            
            # Check for negative keywords
            if check_for_negative_keywords(bse_summary):
                logger.info(f"Negative keyword found in announcement: {bse_summary}")
                return False
            elif check_for_pdf(pdf_file):
                logger.info(f"Processing PDF: {pdf_file}")
                category, ai_summary = self.process_pdf(pdf_file) 
                ai_summary = remove_markdown_tags(ai_summary)
                ai_summary = clean_summary(ai_summary)
            
            # Get ISIN
            isin = self.get_isin(scrip_id)
            
            # Validate ISIN format
            if not isin or isin == "N/A" or (len(isin) > 3 and isin[2] != "E"):
                logger.warning(f"Invalid ISIN: {isin} for scrip_id {scrip_id}")
                return False
                
            # Create file URL
            file_url = f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{pdf_file}" if pdf_file else None
            
            # Prepare data for upload
            data = {
                "corp_id": str(uuid.uuid4()),
                "securityid": scrip_id,
                "summary": bse_summary,
                "fileurl": file_url,
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
                        logger.info(f"Data uploaded to Supabase for {scrip_id}")
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
            return False

    def processLatestAnnouncement(self):
        """Process the latest announcement and send to database and websocket"""
        
        announcements = self.fetch_data()
        if not announcements:
            logger.warning("No announcements found")
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

                if data.get("category") == "Procedural/Administrative":
                    logger.info("Announcement is Procedural/Administrative, skipping API call")
                    return
                # Send to API endpoint (which will handle websocket communication)
                try:
                    post_url = "http://localhost:8000/api/insert_new_announcement"
                    data["is_fresh"] = True  # Mark as fresh for broadcasting
                    res = requests.post(url=post_url, json=data)
                    if res.status_code >= 200 and res.status_code < 300:
                        logger.info(f"Sent to API for websocket: Status code {res.status_code}")
                    else:
                        logger.error(f"API returned error: {res.status_code}, {res.text}")
                except Exception as e:
                    logger.error(f"Error sending to API: {e}")
                    
                return True
            else:
                logger.warning("Failed to process latest announcement")
                return False
    
    def process_all_announcements(self):
        """Process all announcements"""
        announcements = self.fetch_data()
        if not announcements:
            logger.warning("No announcements found")
            return False
            
        # Process all announcements except the latest one (which will be handled by processLatestAnnouncement)
        for announcement in announcements[1:]:
            self.process_data(announcement)
            time.sleep(1)  # Small delay to avoid overwhelming the API
        return True
    
    def run_continuous(self, check_interval=10):
        """Run the scraper in continuous mode, checking for new announcements at regular intervals"""
        while True:
            try:
                if self.processLatestAnnouncement():
                    logger.info("New announcement processed successfully")
                else:
                    logger.info("No new announcements to process")
                    
                time.sleep(check_interval)
            except Exception as e:
                logger.error(f"Error in continuous mode: {e}")
                time.sleep(check_interval)
    
    def run(self):
        """Main method to run the scraper - compatible with liveserver.py"""
        logger.info("Starting BSE scraper run")
        
        # Check if this is the first run by looking for the flag file
        is_first_run = os.path.exists(self.first_run_flag_path)
        
        if is_first_run:
            logger.info("First run detected - processing all announcements")
            # Process all announcements on first run
            success = self.process_all_announcements()
            
            # Also process the latest announcement to send a WebSocket message
            latest_success = self.processLatestAnnouncement()
            
            return success or latest_success
        else:
            logger.info("Incremental run - processing only the latest announcement")
            # Process only the latest announcement on subsequent runs
            return self.processLatestAnnouncement()


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