#!/usr/bin/env python3
"""
Ephemeral AI Worker - Processes jobs then shuts down
Now includes retry logic for AI processing failures and actual AI implementation
"""

import time
import sys
import logging
import os
import json
import requests
import tempfile
import uuid
import signal
import threading
from pathlib import Path
from datetime import datetime
import redis
from google import genai
from pydantic import BaseModel, Field
from google.genai import types
# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.queue.redis_client import RedisConfig, QueueNames
from src.queue.job_types import deserialize_job, AIProcessingJob, SupabaseUploadJob, serialize_job

class TimeoutError(Exception):
    """Custom timeout exception"""
    pass

def timeout_handler(signum, frame):
    """Signal handler for timeout"""
    raise TimeoutError("Operation timed out")

def with_timeout(func, timeout_seconds=300):
    """Execute function with timeout using signals"""
    def wrapper(*args, **kwargs):
        # Set up signal handler
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout_seconds)
        
        try:
            result = func(*args, **kwargs)
            signal.alarm(0)  # Cancel alarm
            return result
        except TimeoutError:
            logger.error(f"Operation timed out after {timeout_seconds} seconds")
            raise
        finally:
            signal.signal(signal.SIGALRM, old_handler)  # Restore old handler
    
    return wrapper

class EphemeralAIWorker:
    """Ephemeral worker that processes AI jobs and exits"""
    
    def __init__(self):
        self.worker_id = f"ai_worker_{int(time.time())}"
        self.redis_config = RedisConfig()
        self.redis_client = None
        self.jobs_processed = 0
        self.idle_timeout = 30  # Shutdown after 30 seconds of no jobs
        self.current_lock_key = None  # Track current processing lock for cleanup
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format=f'%(asctime)s - {self.worker_id} - %(levelname)s - %(message)s'
        )
        
    def _signal_handler(self, signum, frame):
        """Handle termination signals and cleanup locks"""
        logger.warning(f"🛑 Received signal {signum}, cleaning up...")
        
        # Cleanup current processing lock if exists
        if self.current_lock_key and self.redis_client:
            try:
                self.redis_client.delete(self.current_lock_key)
                logger.info(f"🔓 Cleaned up processing lock: {self.current_lock_key}")
            except Exception as e:
                logger.error(f"❌ Failed to cleanup lock {self.current_lock_key}: {e}")
        
        logger.info(f"🏁 {self.worker_id} shutting down gracefully")
        sys.exit(0)

def extract_symbol(url):
    """Extract symbol from URL safely"""
    if not url:
        return None
        
    try:
        from urllib.parse import urlparse
        path = urlparse(url).path  # get the path from URL
        segments = path.strip('/').split('/')  # split path into parts
        if len(segments) >= 2 and segments[-1].isdigit():
            return segments[-2]  # return the segment just before the numeric ID
    except Exception as e:
        logging.getLogger(__name__).error(f"Error extracting symbol from URL {url}: {e}")
    
    return None

def get_isin(scrip_id: str, max_retries: int = 3, request_timeout: int = 10) -> str:
    """Lookup ISIN for a given BSE scrip code with retries and proper headers."""
    if not scrip_id:
        logger.error("Invalid scrip ID for ISIN lookup")
        return "N/A"

    isin_url = (
        "https://api.bseindia.com/BseIndiaAPI/api/ComHeadernew/w"
        f"?quotetype=EQ&scripcode={scrip_id}&seriesid="
    )

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.bseindia.com/",
        "Origin": "https://www.bseindia.com",
        "Accept": "application/json",
    }

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(isin_url, headers=headers, timeout=request_timeout)
            resp.raise_for_status()
            data = resp.json()
            return data.get("ISIN") or data.get("isin") or "N/A"
        except requests.exceptions.Timeout:
            logger.warning(f"ISIN request timed out (attempt {attempt}/{max_retries})")
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error getting ISIN: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error getting ISIN: {e}")
        except ValueError as e:
            logger.error(f"Error parsing ISIN JSON: {e}")
        except Exception as e:
            logger.error(f"Unexpected error getting ISIN: {e}")

        if attempt < max_retries:
            time.sleep(5)

    logger.error(f"Failed to get ISIN for {scrip_id} after {max_retries} attempts")
    return "N/A"

# Import AI processing components
try:
    from src.ai.prompts import *
    AI_IMPORTS_AVAILABLE = True
except ImportError:
    # Will log warning after logger is set up
    AI_IMPORTS_AVAILABLE = False

# Setup logging first
worker_id = f"ephemeral_ai_{os.getpid()}"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(worker_id)

# Log import warning if needed
if not AI_IMPORTS_AVAILABLE:
    logger.warning("Could not import AI prompts")

# Structured output model for AI
class StrucOutput(BaseModel):
    """Schema for structured output from the model."""
    category: str = Field(... , description = category_prompt)
    headline: str = Field(..., description= headline_prompt)
    summary: str = Field(..., description= all_prompt)
    findata: str =Field(..., description= financial_data_prompt)
    individual_investor_list: list[str] = Field(..., description="List of individual investors not company mentioned in the announcement. It should be in a form of an array of strings.")
    company_investor_list: list[str] = Field(..., description="List of company investors mentioned in the announcement. It should be in a form of an array of strings.")
    sentiment: str = Field(..., description = "Analyze the sentiment of the announcement and give appropriate output. The output should be only: Postive, Negative and Netural. Nothing other than these." )

# Rate-limited Gemini client
class RateLimitedGeminiClient:
    """Gemini client with rate limiting and error handling"""
    
    def __init__(self, api_key, rate_limit_delay=2):
        self.api_key = api_key
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0
        self.client = None
        
        try:
            self.client = genai.Client(api_key=api_key)
            logger.info("✅ Gemini client initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Gemini client: {e}")
    
    def files(self):
        """Return files interface with rate limiting"""
        return RateLimitedFiles(self.client.files if self.client else None, self.rate_limit_delay)
    
    def generate_content(self, contents, config=None, model="gemini-2.5-flash"):
        """Generate content with rate limiting and timeout"""
        if not self.client:
            raise Exception("Gemini client not initialized")
        
        # Rate limiting
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        def _generate():
            return self.client.models.generate_content(
                model=model,
                contents=contents,
                config=config
            )
        
        try:
            # Apply timeout wrapper (5 minutes max for AI calls)
            response = with_timeout(_generate, timeout_seconds=300)()
            self.last_request_time = time.time()
            return response
        except TimeoutError:
            logger.error("Gemini API call timed out after 5 minutes")
            raise Exception("AI processing timed out")
        except Exception as e:
            logger.error(f"Error in generate_content: {e}")
            raise

class RateLimitedFiles:
    """Rate-limited files interface"""
    
    def __init__(self, files_client, rate_limit_delay):
        self.files_client = files_client
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0
    
    def upload(self, file):
        """Upload file with rate limiting and timeout"""
        if not self.files_client:
            raise Exception("Files client not available")
        
        # Rate limiting
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            logger.debug(f"Rate limiting file upload: sleeping for {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        def _upload():
            return self.files_client.upload(file=file)
        
        try:
            # Apply timeout wrapper (2 minutes max for file uploads)
            result = with_timeout(_upload, timeout_seconds=120)()
            self.last_request_time = time.time()
            return result
        except TimeoutError:
            logger.error("File upload timed out after 2 minutes")
            raise Exception("File upload timed out")
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            raise
            return result
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            raise

# Initialize Gemini client
genai_client = None
try:
    API_KEY = os.getenv('GEMINI_API_KEY')
    if API_KEY:
        genai_client = RateLimitedGeminiClient(api_key=API_KEY)
    else:
        logger.error("GEMINI_API_KEY environment variable not set")
except Exception as e:
    logger.error(f"Failed to initialize Gemini client: {e}")

# Valid categories list
VALID_CATEGORIES = [
    "Financial Results",
    "Investor Presentation", 
    "Procedural/Administrative",
    "Agreements/MoUs",
    "Annual Report",
    "Anti-dumping Duty",
    "Bonus/Stock Split",
    "Buyback",
    "Change in Address",
    "Change in KMP",
    "Change in MOA",
    "Clarifications/Confirmations",
    "Closure of Factory",
    "Concall Transcript",
    "Consolidation of Shares",
    "Credit Rating",
    "Debt & Financing",
    "Debt Reduction",
    "Delisting",
    "Demerger",
    "Demise of KMP",
    "Disruption of Operations",
    "Divestitures",
    "DRHP",
    "Expansion",
    "Fundraise - Preferential Issue",
    "Fundraise - QIP",
    "Fundraise - Rights Issue",
    "Global Pharma Regulation",
    "Incorporation/Cessation of Subsidiary",
    "Increase in Share Capital",
    "Insolvency and Bankruptcy",
    "Interest Rates Updates",
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
    "Reduction in Share Capital",
    "Regulatory Approvals/Orders",
    "Trading Suspension",
    "USFDA"
]

class EphemeralAIWorker:
    """AI worker that processes available jobs then shuts down"""
    
    def __init__(self):
        self.worker_id = worker_id
        self.redis_config = RedisConfig()
        self.redis_client = None
        self.jobs_processed = 0
        self.max_jobs_per_session = 10  # Process max 10 jobs then shutdown
        self.idle_timeout = 30  # Shutdown after 30 seconds of no jobs
        self.max_retries_per_job = 3  # Maximum retries for failed AI processing
        
    def setup_redis(self):
        """Setup Redis connection"""
        try:
            self.redis_client = self.redis_config.get_connection()
            logger.info("✅ Redis client initialized successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            return False
    
    def download_pdf_file(self, url: str) -> str:
        """Download PDF file from URL and return local file path"""
        if not url:
            raise ValueError("No PDF URL provided")
        
        # Create temporary file
        filename = url.split("/")[-1]
        if not filename.endswith('.pdf'):
            filename += '.pdf'
        
        temp_dir = tempfile.gettempdir()
        filepath = os.path.join(temp_dir, f"{uuid.uuid4()}_{filename}")
        
        try:
            logger.info(f"📥 Downloading PDF: {url}")
            
            # Use proper headers for BSE PDF downloads (same as BSE scraper)
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.bseindia.com/",
                "Origin": "https://www.bseindia.com"
            }
            
            response = requests.get(url, timeout=30, headers=headers)
            response.raise_for_status()
            
            with open(filepath, "wb") as file:
                file.write(response.content)
            
            logger.info(f"✅ Downloaded PDF to: {filepath} (size: {len(response.content)} bytes)")
            return filepath
            
        except Exception as e:
            logger.error(f"❌ Failed to download PDF {url}: {e}")
            raise
    
    def ai_process_pdf(self, filepath: str) -> tuple:
        """Process PDF with AI using Gemini API (migrated from scrapers)"""
        if not filepath:
            logger.error("No valid filename provided for AI processing")
            return "Error", "No valid filename provided", "", "", [], [], "Neutral"
            
        if not os.path.exists(filepath):
            logger.error(f"File not found: {filepath}")
            return "Error", "File not found", "", "", [], [], "Neutral"
            
        # Handle case where Gemini client failed to initialize
        if not genai_client or not genai_client.client:
            logger.error("Cannot process file: Gemini client not initialized")
            return "Procedural/Administrative", "AI processing unavailable", "", "", [], [], "Neutral"

        uploaded_file = None
        
        try:
            logger.info(f"📤 Uploading file to Gemini: {filepath}")
            # Upload the PDF file
            uploaded_file = genai_client.files().upload(file=filepath)
            
            # Generate content with structured output
            logger.info("🤖 Generating AI content...")
            response = genai_client.generate_content(
                contents=[all_prompt, uploaded_file],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=StrucOutput,
                    thinking_config=types.ThinkingConfig(
                        thinking_budget = -1
                    )
                )
            )
            
            if not hasattr(response, 'text'):
                logger.error("AI response missing text attribute")
                return "Error", "AI processing failed: invalid response format", "", "", [], [], "Neutral"
                
            # Parse JSON response
            logger.info("📝 Parsing AI response...")
            logger.info(f"🔍 Raw response text: {response.text[:500]}...")  # Log first 500 chars
            
            summary = json.loads(response.text.strip())
            logger.info(f"🔍 Parsed JSON type: {type(summary)}")
            logger.info(f"🔍 Parsed JSON content: {summary}")
            
            # Extract all fields from the summary
            try:
                # Handle both array and direct object responses
                if isinstance(summary, list) and len(summary) > 0:
                    data = summary[0]
                elif isinstance(summary, dict):
                    data = summary
                else:
                    logger.error(f"Unexpected response format: {type(summary)}")
                    return "Error", "Unexpected response format", "", "", [], [], "Neutral"
                
                category_text = data["category"]
                headline = data["headline"]
                summary_text = data["summary"]
                financial_data = data["findata"]
                individual_investor_list = data["individual_investor_list"]
                company_investor_list = data["company_investor_list"]
                sentiment = data["sentiment"]
                
                logger.info(f"✅ AI processing completed successfully")
                logger.info(f"📊 Category: {category_text}")
                return category_text, summary_text, headline, financial_data, individual_investor_list, company_investor_list, sentiment
                
            except (IndexError, KeyError) as e:
                logger.error(f"Failed to extract fields from AI response: {e}")
                logger.error(f"Available keys in response: {list(data.keys()) if 'data' in locals() and isinstance(data, dict) else 'Not a dict'}")
                return "Error", "Failed to extract fields from AI response", "", "", [], [], "Neutral"
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from AI response: {e}")
            return "Error", "Failed to parse AI response", "", "", [], [], "Neutral"
        except Exception as e:
            logger.error(f"Error in AI processing: {e}")
            return "Error", f"Error processing file: {str(e)}", "", "", [], [], "Neutral"
        finally:
            # Clean up uploaded file
            try:
                if uploaded_file and hasattr(uploaded_file, 'delete'):
                    uploaded_file.delete()
            except:
                pass  # Ignore cleanup errors
                
    def ai_process_text(self, headline: str, content: str) -> tuple:
        """Process text content with AI (for announcements without PDFs)"""
        if not headline and not content:
            logger.error("No text content provided for AI processing")
            return "Error", "No text content provided", "", "", [], [], "Neutral"
            
        # Handle case where Gemini client failed to initialize
        if not genai_client or not genai_client.client:
            logger.error("Cannot process text: Gemini client not initialized")
            return "Procedural/Administrative", "AI processing unavailable", "", "", [], [], "Neutral"
            
        try:
            # Combine headline and content
            full_text = f"Headline: {headline}\n\nContent: {content}" if headline and content else (headline or content)
            
            logger.info(f"🤖 Processing text content with AI (length: {len(full_text)} chars)")
            
            # Generate content with structured output
            response = genai_client.generate_content(
                contents=[f"{all_prompt}\n\nText to analyze:\n{full_text}"],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=StrucOutput,
                    thinking_config=types.ThinkingConfig(
                        thinking_budget = -1
                    )
                )
            )
            
            if not hasattr(response, 'text'):
                logger.error("AI response missing text attribute")
                return "Error", "AI processing failed: invalid response format", "", "", [], [], "Neutral"
                
            # Parse JSON response
            logger.info("📝 Parsing AI text processing response...")
            summary = json.loads(response.text.strip())
            
            # Extract all fields from the summary
            try:
                category_text = summary[0]["category"]
                headline_processed = summary[0]["headline"]
                summary_text = summary[0]["summary"]
                financial_data = summary[0]["findata"]
                individual_investor_list = summary[0]["individual_investor_list"]
                company_investor_list = summary[0]["company_investor_list"]
                sentiment = summary[0]["sentiment"]
                
                logger.info(f"✅ AI text processing completed successfully")
                logger.info(f"📊 Category: {category_text}")
                return category_text, summary_text, headline_processed, financial_data, individual_investor_list, company_investor_list, sentiment
                
            except (IndexError, KeyError) as e:
                logger.error(f"Failed to extract fields from AI text response: {e}")
                return "Error", "Failed to extract fields from AI text response", "", "", [], [], "Neutral"
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from AI text response: {e}")
            return "Error", "Failed to parse AI text response", "", "", [], [], "Neutral"
        except Exception as e:
            logger.error(f"Error in AI text processing: {e}")
            return "Error", f"Error processing text: {str(e)}", "", "", [], [], "Neutral"
    
    def call_ai_processing_function(self, job: AIProcessingJob) -> tuple:
        """
        Call actual AI processing function with PDF download and processing.
        Now implemented with real AI processing logic migrated from scrapers.
        
        Returns: (category, summary, headline, findata, individual_investor_list, company_investor_list, sentiment)
        """
        try:
            # Extract PDF URL from announcement data
            announcement_data = job.announcement_data
            pdf_url = None
            
            # Construct PDF URL from BSE attachment data
            pdf_url = None
            if isinstance(announcement_data, dict):
                # Get PDF filename from ATTACHMENTNAME field
                pdf_file = announcement_data.get('ATTACHMENTNAME', '')
                
                if pdf_file:
                    # Construct the full PDF URL using BSE's attachment URL pattern
                    pdf_url = f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{pdf_file}"
                    logger.info(f"📄 Constructed PDF URL from ATTACHMENTNAME: {pdf_url}")
                else:
                    # Try other possible PDF URL fields as fallback
                    pdf_url = (announcement_data.get('PDFPATH') or
                              announcement_data.get('pdf_url') or
                              announcement_data.get('fileurl') or
                              announcement_data.get('AttchmntFile'))
                    
                    if pdf_url:
                        logger.info(f"📄 Found PDF URL from fallback fields: {pdf_url}")
                
                att_name = announcement_data.get('ATTACHMENTNAME')
                fileurl = (
                    f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{att_name}" if att_name else
                    announcement_data.get('PDFPATH') or announcement_data.get('fileurl') or announcement_data.get('AttchmntFile')
                )
                companyname = (
                    announcement_data.get('SLONGNAME')
                    or announcement_data.get('SC_FULLNAME')
                    or announcement_data.get('SC_NAME')
                    or ""
                )
                if isinstance(companyname, str):
                    companyname = companyname.replace('$','').replace('-','')
            
            # If no PDF URL found, process text content instead
            if not pdf_url:
                logger.info(f"📝 No PDF URL found for job {job.job_id}, processing text content instead")
                
                # Extract text content from announcement
                headline = announcement_data.get('HEADLINE', announcement_data.get('NEWSSUB', ''))
                content = announcement_data.get('MORE', announcement_data.get('HEADLINE', ''))
                
                if not headline and not content:
                    logger.error(f"No content found in announcement data for job {job.job_id}")
                    return "Error", "No content found in announcement data", "", "", [], [], "Neutral"
                
                # Process text content directly
                try:
                    logger.info(f"🤖 Processing text content for job {job.job_id}")
                    result = self.ai_process_text(headline, content)
                    return result
                except Exception as e:
                    logger.error(f"Failed to process text content: {e}")
                    return "Error", f"Failed to process text content: {str(e)}", "", "", [], [], "Neutral"
            
            # Download PDF file
            try:
                filepath = self.download_pdf_file(pdf_url)
            except Exception as e:
                logger.error(f"Failed to download PDF: {e}")
                return "Error", f"Failed to download PDF: {str(e)}", "", "", [], [], "Neutral"
            
            try:
                # Process PDF with AI
                result = self.ai_process_pdf(filepath)
                logger.info(f"🎯 AI processing result for {job.job_id}: {result[0]}")
                return result
                
            finally:
                # Clean up downloaded file
                try:
                    if os.path.exists(filepath):
                        os.unlink(filepath)
                        logger.debug(f"🗑️ Cleaned up temporary file: {filepath}")
                except:
                    pass  # Ignore cleanup errors
                
        except Exception as e:
            logger.error(f"AI processing exception for job {job.job_id}: {e}")
            return "Error", f"Exception in AI processing: {str(e)}", "", "", [], [], "Neutral"
    
    def is_valid_category(self, category: str) -> bool:
        """Check if the category is in the valid categories list"""
        return category in VALID_CATEGORIES
    
    def should_retry_processing(self, category: str) -> bool:
        """Determine if AI processing should be retried based on the category"""
        return category == "Error" or not self.is_valid_category(category)
    
    def requeue_failed_job(self, job: AIProcessingJob, retry_count: int, reason: str) -> bool:
        """Push failed job back to the queue for later retry with delay"""
        try:
            # Create a new job for retry instead of modifying the existing one
            # to avoid Pydantic model field issues
            logger.info(f"🔄 Requeuing failed job {job.job_id} with reason: {reason}")
            
            # Calculate delay based on retry attempts (exponential backoff)
            base_delay = 300  # 5 minutes base delay
            max_delay = 3600  # 1 hour max delay
            total_retries = retry_count + 1
            delay = min(base_delay * (2 ** min(total_retries // 3, 6)), max_delay)
            
            # Use Redis ZADD with score as timestamp for delayed processing
            future_timestamp = time.time() + delay
            
            # Serialize job for delayed queue
            job_data = serialize_job(job)
            
            # Add to delayed queue (sorted set) instead of immediate queue
            delayed_queue_name = f"{QueueNames.AI_PROCESSING}:delayed"
            self.redis_client.zadd(delayed_queue_name, {job_data: future_timestamp})
            
            logger.warning(f"🔄 Requeued failed job {job.corp_id} for retry in {delay/60:.1f} minutes (total attempts: {job.retry_count}, reason: {reason})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to requeue job {job.corp_id}: {e}")
            return False
    
    def process_ai_job_with_retry(self, job: AIProcessingJob) -> bool:
        """Process an AI job with retry logic for failures"""
        # Check if already processed in Supabase to prevent duplicate processing
        ann_newsid = None
        try:
            ann_newsid = (job.announcement_data or {}).get('NEWSID')
        except Exception:
            ann_newsid = None
            
        try:
            # Check if already processed in Supabase to prevent duplicate processing
            try:
                from supabase import create_client
                supabase_url = os.getenv('SUPABASE_URL2')
                supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
                
                if supabase_url and supabase_key:
                    supabase = create_client(supabase_url, supabase_key)
                    # Prefer deterministic corp_id derived from NEWSID if present
                    expected_corp_id = job.corp_id
                    if ann_newsid:
                        try:
                            import uuid
                            expected_corp_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"bse:{ann_newsid}"))
                        except Exception:
                            pass
                    existing = supabase.table("corporatefilings").select("corp_id").eq("corp_id", expected_corp_id).execute()
                    
                    if existing.data and len(existing.data) > 0:
                        logger.warning(f"⚠️ Corp_id {expected_corp_id} already exists in Supabase - skipping duplicate processing")
                        return True  # Already processed, skip
            except Exception as db_check_error:
                logger.warning(f"⚠️ Could not check Supabase for duplicates: {db_check_error}")
                # Continue processing even if check fails
            
            logger.info(f"🤖 Starting AI processing for corp_id: {job.corp_id}")
            
            # Basic validation
            if not job.announcement_data:
                logger.error(f"❌ No announcement data for corp_id: {job.corp_id}")
                return False
                
            logger.info(f"📝 Announcement data keys: {list(job.announcement_data.keys()) if isinstance(job.announcement_data, dict) else 'Not a dict'}")
        
            last_result = None
            retry_count = 0

        except Exception as pre_err:
            logger.error(f"❌ Pre-processing error for corp_id {job.corp_id}: {pre_err}")
            return False

        while retry_count < self.max_retries_per_job:
            try:
                # Call AI processing function
                result = self.call_ai_processing_function(job)
                category = result[0] if result else "Error"
                
                # Check if we should retry
                if self.should_retry_processing(category):
                    retry_count += 1
                    last_result = result
                    
                    if retry_count < self.max_retries_per_job:
                        logger.warning(f"⚠️ AI processing failed (category='{category}'), retrying {retry_count}/{self.max_retries_per_job} for corp_id: {job.corp_id}")
                        time.sleep(2 * retry_count)  # Exponential backoff
                        continue
                    else:
                        logger.error(f"❌ AI processing failed after {self.max_retries_per_job} retries for corp_id: {job.corp_id}")
                        # Push back to queue for later retry instead of uploading Error
                        return self.requeue_failed_job(job, retry_count, "Max retries exceeded in current session")
                else:
                    # Success! Valid category returned
                    logger.info(f"✅ AI processing successful for corp_id: {job.corp_id}, category: {category}")
                    break
                    
            except Exception as e:
                retry_count += 1
                logger.error(f"❌ AI processing exception (attempt {retry_count}): {e}")
                
                if retry_count >= self.max_retries_per_job:
                    # Push back to queue for later retry instead of uploading Error
                    return self.requeue_failed_job(job, retry_count, f"Exception after retries: {str(e)}")
                    
                time.sleep(2 * retry_count)  # Exponential backoff
        
        # Process the final result
        try:
            category, summary, headline, findata, individual_investor_list, company_investor_list, sentiment = result
            
            # Check if category is still "Error" after all retries
            if category == "Error":
                logger.error(f"❌ Skipping upload for corp_id: {job.corp_id} - category is still 'Error' after {retry_count} retries")
                # Return false to indicate processing failed
                return False
            
            # Extract additional data from the job for Supabase upload
            announcement_data = job.announcement_data or {}
            symbol = extract_symbol(announcement_data.get('NSURL'))
            isin = get_isin(announcement_data.get('SCRIP_CD'))
            att_name = announcement_data.get('ATTACHMENTNAME')
            fileurl = (
                f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{att_name}" if att_name else
                announcement_data.get('PDFPATH') or announcement_data.get('fileurl') or announcement_data.get('AttchmntFile')
            )
            companyname = (
                announcement_data.get('SLONGNAME')
                or announcement_data.get('SC_FULLNAME')
                or announcement_data.get('SC_NAME')
                or ""
            )
            if isinstance(companyname, str):
                companyname = companyname.replace('$','').replace('-','')
            # Create processed data for Supabase upload
            processed_data = {
                "corp_id": job.corp_id,
                "summary": summary,
                "category": category,
                "headline": headline,
                "findata": findata,
                "individual_investor_list": individual_investor_list,
                "company_investor_list": company_investor_list,
                "sentiment": sentiment,
                # "processed_by": self.worker_id,
                # "processed_at": datetime.now().isoformat(),
                # "retry_count": retry_count,
                # # Include original announcement data
                "securityid": announcement_data.get('SCRIP_CD'),
                "companyname": companyname,
                "symbol": symbol,
                "isin": isin,
                "date": announcement_data.get('DT_TM'),
                "fileurl": fileurl,
                "newsid": announcement_data.get('NEWSID') or announcement_data.get('newsid', ''),
                    "original_summary": (
                        announcement_data.get('HEADLINE')
                        or announcement_data.get('NEWSSUB')
                        or announcement_data.get('SUB')
                        or announcement_data.get('MORE')
                        or ""
                    )
            }
            
            # Create Supabase upload job
            logger.info(f"📤 Creating Supabase upload job for corp_id: {job.corp_id}")
            supabase_job = SupabaseUploadJob(
                job_id=f"{job.job_id}_upload",
                corp_id=job.corp_id,
                processed_data=processed_data
            )
            logger.info(f"✅ Supabase job created successfully")
            
            # Add to Supabase queue
            queue_length = self.redis_client.lpush(QueueNames.SUPABASE_UPLOAD, serialize_job(supabase_job))
            logger.info(f"📊 Added job to Supabase queue - queue now has {queue_length} jobs")
            
            logger.info(f"✅ AI processing completed for corp_id: {job.corp_id} (retries: {retry_count}, category: {category})")
            self.jobs_processed += 1
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create Supabase job for {job.corp_id}: {e}")
            return False
    
    def process_ai_job(self, job: AIProcessingJob) -> bool:
        """Process an AI job (legacy method for compatibility)"""
        return self.process_ai_job_with_retry(job)
    
    def run(self):
        """Main worker loop - process jobs then shutdown"""
        logger.info(f"🚀 {self.worker_id} starting (ephemeral mode with retry logic)")
        
        if not self.setup_redis():
            return False
        
        start_time = time.time()
        last_job_time = time.time()
        
        try:
            while True:
                # Check shutdown conditions
                if self.jobs_processed >= self.max_jobs_per_session:
                    logger.info(f"✅ Processed {self.jobs_processed} jobs, shutting down")
                    break
                
                if time.time() - last_job_time > self.idle_timeout:
                    logger.info(f"⏰ No jobs for {self.idle_timeout}s, shutting down")
                    break
                
                try:
                    # Get job with short timeout
                    logger.info(f"🔍 Checking for jobs in {QueueNames.AI_PROCESSING}")
                    result = self.redis_client.brpop(QueueNames.AI_PROCESSING, timeout=5)
                    
                    if result:
                        queue_name, job_json = result
                        logger.info(f"📦 Got job from {queue_name}: {job_json[:100]}...")
                        
                        try:
                            job = deserialize_job(job_json)
                            logger.info(f"✅ Deserialized job: {type(job)}")
                            
                            if isinstance(job, AIProcessingJob):
                                # IMMEDIATE lock acquisition to prevent duplicate processing
                                lock_key = f"worker_processing:{job.corp_id}:{job.job_id}"
                                self.current_lock_key = lock_key  # Track for cleanup
                                
                                lock_acquired = self.redis_client.set(
                                    lock_key, 
                                    self.worker_id, 
                                    nx=True,  # Only set if not exists
                                    ex=600    # 10 minute lock (longer than processing time)
                                )
                                
                                if not lock_acquired:
                                    logger.warning(f"⚠️ Job {job.job_id} is already being processed by another worker - SKIPPING")
                                    self.current_lock_key = None  # Clear tracking
                                    continue  # Skip this job, don't count as processed
                                    
                                try:
                                    logger.info(f"🤖 Processing AI job for corp_id: {job.corp_id}")
                                    success = self.process_ai_job_with_retry(job)
                                    logger.info(f"🔄 Job processing result: {success}")
                                    last_job_time = time.time()
                                    self.jobs_processed += 1
                                    
                                finally:
                                    # Always release the lock
                                    try:
                                        self.redis_client.delete(lock_key)
                                        self.current_lock_key = None  # Clear tracking
                                        logger.debug(f"🔓 Released processing lock for {job.job_id}")
                                    except Exception as unlock_err:
                                        logger.warning(f"Failed to release lock for {job.job_id}: {unlock_err}")
                                        self.current_lock_key = None  # Clear tracking anyway
                            else:
                                logger.warning(f"⚠️ Unexpected job type: {type(job)}")
                        except Exception as job_error:
                            logger.error(f"❌ Error processing job: {job_error}")
                            logger.error(f"Raw job data: {job_json}")
                    else:
                        logger.debug(f"💤 No jobs available in queue")
                    
                except redis.TimeoutError:
                    # No jobs available, continue checking
                    logger.debug(f"⏰ Queue timeout, continuing...")
                    continue
                except Exception as e:
                    logger.error(f"❌ Worker error: {e}")
                    time.sleep(1)
        
        except KeyboardInterrupt:
            logger.info(f"🛑 {self.worker_id} interrupted")
        
        finally:
            runtime = time.time() - start_time
            logger.info(f"🏁 {self.worker_id} finished - {self.jobs_processed} jobs in {runtime:.1f}s")
        
        return True

def main():
    """Main function"""
    worker = EphemeralAIWorker()
    worker.run()

if __name__ == "__main__":
    main()