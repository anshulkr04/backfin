#!/usr/bin/env python3
"""
Ephemeral AI Worker - Processes jobs then shuts down
Behavior:
- Retry AI processing up to max_retries_per_job on failures (including timeouts)
- If retries are exhausted, move the job to the delayed sorted set: "<AI_PROCESSING>:delayed"
- Do NOT create any new queues. Use existing QueueNames (including FAILED_JOBS for raw/deserialization failures).
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
from pathlib import Path
from datetime import datetime
import redis
from google import genai
from pydantic import BaseModel, Field
from google.genai import types
from google.genai.errors import ClientError

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.queue.redis_client import RedisConfig, QueueNames
from src.queue.job_types import deserialize_job, AIProcessingJob, SupabaseUploadJob, serialize_job

# --- Timeout utility ---
class TimeoutError(Exception):
    """Custom timeout exception"""
    pass

def timeout_handler(signum, frame):
    raise TimeoutError("Operation timed out")

def with_timeout(func, timeout_seconds=300):
    """Execute function with timeout using signals (Unix only)."""
    def wrapper(*args, **kwargs):
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout_seconds)
        try:
            return func(*args, **kwargs)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
    return wrapper

# --- Helpers ---
def extract_symbol(url):
    if not url:
        return None
    try:
        from urllib.parse import urlparse
        path = urlparse(url).path
        segments = path.strip('/').split('/')
        if len(segments) >= 2 and segments[-1].isdigit():
            return segments[-2]
    except Exception as e:
        logging.getLogger(__name__).error(f"Error extracting symbol from URL {url}: {e}")
    return None

def get_isin(scrip_id: str, max_retries: int = 3, request_timeout: int = 10) -> str:
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

# --- AI prompts import (may fail) ---
try:
    from src.ai.prompts import *
    AI_IMPORTS_AVAILABLE = True
except Exception:
    AI_IMPORTS_AVAILABLE = False

# --- Logging setup ---
worker_id = f"ephemeral_ai_{os.getpid()}"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(worker_id)

if not AI_IMPORTS_AVAILABLE:
    logger.warning("Could not import AI prompts")

# --- Structured output model ---
class StrucOutput(BaseModel):
    category: str = Field(... , description = category_prompt)
    headline: str = Field(..., description= headline_prompt)
    summary: str = Field(..., description= all_prompt)
    findata: str =Field(..., description= financial_data_prompt)
    individual_investor_list: list[str] = Field(..., description="List of individual investors not company mentioned in the announcement. It should be in a form of an array of strings.")
    company_investor_list: list[str] = Field(..., description="List of company investors mentioned in the announcement. It should be in a form of an array of strings.")
    sentiment: str = Field(..., description = "Analyze the sentiment of the announcement and give appropriate output. The output should be only: Postive, Negative and Netural. Nothing other than these." )

class CategoryResponse(BaseModel):
    category: str = Field(... , description = category_prompt)

# --- Gemini wrappers with proper TimeoutError propagation ---
class RateLimitedGeminiClient:
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
        return RateLimitedFiles(self.client.files if self.client else None, self.rate_limit_delay)
    

    def generate_content(self, contents, config=None, model="gemini-2.5-flash-lite"):
        if not self.client:
            raise Exception("Gemini client not initialized")
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last)

        def _generate():
            return self.client.models.generate_content(
                model=model,
                contents=contents,
                config=config
            )

        try:
            # If the inner call times out, with_timeout will raise TimeoutError
            response = with_timeout(_generate, timeout_seconds=180)()
            self.last_request_time = time.time()
            return response
        except TimeoutError:
            logger.error("Gemini API call timed out after 3 minutes")
            # re-raise TimeoutError so callers know it's a timeout
            raise
        except Exception as e:
            logger.error(f"Error in generate_content: {e}")
            raise

class RateLimitedFiles:
    def __init__(self, files_client, rate_limit_delay):
        self.files_client = files_client
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0

    def upload(self, file):
        if not self.files_client:
            raise Exception("Files client not available")

        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last)

        def _upload():
            return self.files_client.upload(file=file)

        try:
            result = with_timeout(_upload, timeout_seconds=90)()
            self.last_request_time = time.time()
            return result
        except TimeoutError:
            logger.error("File upload timed out after 90 seconds")
            raise
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            raise

# --- Initialize gemini client if key present ---
genai_client = None
try:
    API_KEY = os.getenv('GEMINI_API_KEY')
    if API_KEY:
        genai_client = RateLimitedGeminiClient(api_key=API_KEY)
    else:
        logger.error("GEMINI_API_KEY environment variable not set")
except Exception as e:
    logger.error(f"Failed to initialize Gemini client: {e}")

# --- Valid categories ---
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

# --- The worker class ---
class EphemeralAIWorker:
    """AI worker that processes available jobs then shuts down"""

    def __init__(self):
        self.worker_id = worker_id
        self.redis_config = RedisConfig()
        self.redis_client = None
        self.jobs_processed = 0
        self.max_jobs_per_session = 10
        self.idle_timeout = 30
        self.max_retries_per_job = 3
        self.current_lock_key = None

        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        logger.warning(f"🛑 Received signal {signum}, cleaning up...")
        if self.current_lock_key and self.redis_client:
            try:
                self.redis_client.delete(self.current_lock_key)
                logger.info(f"🔓 Cleaned up processing lock: {self.current_lock_key}")
            except Exception as e:
                logger.error(f"❌ Failed to cleanup lock {self.current_lock_key}: {e}")
        logger.info(f"🏁 {self.worker_id} shutting down gracefully")
        sys.exit(0)

    def setup_redis(self):
        try:
            self.redis_client = self.redis_config.get_connection()
            logger.info("✅ Redis client initialized successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            return False

    def download_pdf_file(self, url: str) -> str:
        if not url:
            raise ValueError("No PDF URL provided")

        filename = url.split("/")[-1]
        if not filename.endswith('.pdf'):
            filename += '.pdf'

        temp_dir = tempfile.gettempdir()
        filepath = os.path.join(temp_dir, f"{uuid.uuid4()}_{filename}")

        try:
            logger.info(f"📥 Downloading PDF: {url}")
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

    def ai_process_pdf(self, filepath: str, original_summary: str) -> tuple:
        if not filepath:
            logger.error("No valid filename provided for AI processing")
            return "Error", "No valid filename provided", "", "", [], [], "Neutral"

        if not os.path.exists(filepath):
            logger.error(f"File not found: {filepath}")
            return "Error", "File not found", "", "", [], [], "Neutral"

        if not genai_client or not genai_client.client:
            logger.error("Cannot process file: Gemini client not initialized")
            return "Procedural/Administrative", "AI processing unavailable", "", "", [], [], "Neutral"

        uploaded_file = None
        try:
            logger.info(f"📤 Uploading file to Gemini: {filepath}")
            uploaded_file = genai_client.files().upload(file=filepath)

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

            logger.info("📝 Parsing AI response...")
            logger.info(f"🔍 Raw response text: {response.text[:500]}...")
            summary = json.loads(response.text.strip())

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

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from AI response: {e}")
            return "Error", "Failed to parse AI response", "", "", [], [], "Neutral"
        except TimeoutError:
            logger.error("AI file processing timed out")
            # bubble up timeout so caller can count it as a retry attempt
            raise

        except ClientError as e:
            # Check if it's the token limit error
            if e.status_code == 400 and "exceeds the maximum number of tokens" in str(e):
                response = genai_client.generate_content(
                    contents=[original_summary],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=CategoryResponse,
                    )
                )
                category_prompt = json.loads(response.text.strip())
                category_text = category_prompt.get("category", "Procedural/Administrative")
                headline = original_summary
                summary_text = original_summary + "\n Refer to the original document for details."
                financial_data = ""
                individual_investor_list = []
                company_investor_list = []
                sentiment = "Neutral"
                logger.info(f"✅ AI processing (fallback) completed successfully with category: {category_text}")
                return category_text, summary_text, headline, financial_data, individual_investor_list, company_investor_list, sentiment
            else:
                logger.error(f"ClientError in AI processing: {e}")
                return "Error", f"ClientError processing file: {str(e)}", "", "", [], [], "Neutral"
            
        except Exception as e:
            logger.error(f"Error in AI processing: {e}")
            return "Error", f"Error processing file: {str(e)}", "", "", [], [], "Neutral"

        finally:
            try:
                if uploaded_file and hasattr(uploaded_file, 'delete'):
                    uploaded_file.delete()
            except:
                pass

    def ai_process_text(self, headline: str, content: str) -> tuple:
        if not headline and not content:
            logger.error("No text content provided for AI processing")
            return "Error", "No text content provided", "", "", [], [], "Neutral"

        if not genai_client or not genai_client.client:
            logger.error("Cannot process text: Gemini client not initialized")
            return "Procedural/Administrative", "AI processing unavailable", "", "", [], [], "Neutral"

        try:
            full_text = f"Headline: {headline}\n\nContent: {content}" if headline and content else (headline or content)
            logger.info(f"🤖 Processing text content with AI (length: {len(full_text)} chars)")

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

            logger.info("📝 Parsing AI text processing response...")
            summary = json.loads(response.text.strip())

            if isinstance(summary, list) and len(summary) > 0:
                data = summary[0]
            elif isinstance(summary, dict):
                data = summary
            else:
                logger.error(f"Unexpected text response format: {type(summary)}")
                return "Error", "Unexpected response format", "", "", [], [], "Neutral"

            category_text = data["category"]
            headline_processed = data["headline"]
            summary_text = data["summary"]
            financial_data = data["findata"]
            individual_investor_list = data["individual_investor_list"]
            company_investor_list = data["company_investor_list"]
            sentiment = data["sentiment"]

            logger.info(f"✅ AI text processing completed successfully")
            logger.info(f"📊 Category: {category_text}")
            return category_text, summary_text, headline_processed, financial_data, individual_investor_list, company_investor_list, sentiment

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from AI text response: {e}")
            return "Error", "Failed to parse AI text response", "", "", [], [], "Neutral"
        except TimeoutError:
            logger.error("AI text processing timed out")
            raise
        except Exception as e:
            logger.error(f"Error in AI text processing: {e}")
            return "Error", f"Error processing text: {str(e)}", "", "", [], [], "Neutral"

    def call_ai_processing_function(self, job: AIProcessingJob) -> tuple:
        try:
            announcement_data = job.announcement_data
            pdf_url = None
            original_summary = announcement_data.get('HEADLINE', '')
            if (check_for_negative_keywords(original_summary)):
                logger.info(f"🛑 Negative keywords found in announcement for job {job.job_id}, treating as Procedural/Administrative")
                return (
                    "Procedural/Administrative",
                    "Refer to the original document for details",
                    original_summary,
                    "",
                    [],
                    [],
                    "Neutral"
                )

            if isinstance(announcement_data, dict):
                pdf_file = announcement_data.get('ATTACHMENTNAME', '')
                if pdf_file:
                    pdf_url = f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{pdf_file}"
                    logger.info(f"📄 Constructed PDF URL from ATTACHMENTNAME: {pdf_url}")
                else:
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

            if not pdf_url:
                logger.info(f"📝 No PDF URL found for job {job.job_id}, treating as Procedural/Administrative")
                headline = announcement_data.get('HEADLINE', announcement_data.get('NEWSSUB', ''))
                summary = announcement_data.get('MORE', announcement_data.get('HEADLINE', ''))
                if not headline and not summary:
                    logger.error(f"No content found in announcement data for job {job.job_id}")
                    return "Error", "No content found in announcement data", "", "", [], [], "Neutral"
                return (
                    "Procedural/Administrative",
                    summary or headline,
                    headline,
                    "",
                    [],
                    [],
                    "Neutral"
                )

            try:
                filepath = self.download_pdf_file(pdf_url)
            except Exception as e:
                logger.error(f"Failed to download PDF: {e}")
                return "Error", f"Failed to download PDF: {str(e)}", "", "", [], [], "Neutral"

            try:
                result = self.ai_process_pdf(filepath,original_summary)
                logger.info(f"🎯 AI processing result for {job.job_id}: {result[0] if result else 'None'}")
                return result
            finally:
                try:
                    if os.path.exists(filepath):
                        os.unlink(filepath)
                        logger.debug(f"🗑️ Cleaned up temporary file: {filepath}")
                except:
                    pass

        except Exception as e:
            logger.error(f"AI processing exception for job {job.job_id}: {e}")
            return "Error", f"Exception in AI processing: {str(e)}", "", "", [], [], "Neutral"

    def is_valid_category(self, category: str) -> bool:
        return category in VALID_CATEGORIES

    def should_retry_processing(self, category: str) -> bool:
        return category == "Error" or not self.is_valid_category(category)

    def requeue_failed_job(self, job: AIProcessingJob, retry_count: int, reason: str) -> bool:
        try:
            logger.info(f"🔄 Requeuing failed job {getattr(job, 'job_id', '<unknown>')} with reason: {reason}")
            base_delay = 300  # 5 minutes
            max_delay = 3600  # 1 hour
            total_retries = retry_count + 1
            delay = min(base_delay * (2 ** min(total_retries // 3, 6)), max_delay)
            future_timestamp = time.time() + delay
            job_data = serialize_job(job)
            delayed_queue_name = f"{QueueNames.AI_PROCESSING}:delayed"
            self.redis_client.zadd(delayed_queue_name, {job_data: future_timestamp})
            logger.warning(f"🔄 Requeued failed job {job.corp_id} for retry in {delay/60:.1f} minutes (attempts: {getattr(job, 'retry_count', 0)})")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to requeue job {getattr(job, 'corp_id', '<unknown>')}: {e}")
            return False

    def process_ai_job_with_retry(self, job: AIProcessingJob) -> bool:
        """
        Core retry loop:
        - Attempts AI processing up to self.max_retries_per_job.
        - If any attempt raises TimeoutError or returns category that should retry, it increments retry_count.
        - If retries exhausted -> requeue_failed_job (moves to delayed sorted set).
        - Returns True if successful and enqueue to SUPABASE_UPLOAD succeeded, False otherwise.
        """
        ann_newsid = None
        try:
            ann_newsid = (job.announcement_data or {}).get('NEWSID')
        except Exception:
            ann_newsid = None

        try:
            # Optional duplicate check in Supabase (best-effort)
            try:
                from supabase import create_client
                supabase_url = os.getenv('SUPABASE_URL2')
                supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
                if supabase_url and supabase_key:
                    supabase = create_client(supabase_url, supabase_key)
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
                        return True
            except Exception as db_check_error:
                logger.warning(f"⚠️ Could not check Supabase for duplicates: {db_check_error}")

            logger.info(f"🤖 Starting AI processing for corp_id: {job.corp_id}")
            if not job.announcement_data:
                logger.error(f"❌ No announcement data for corp_id: {job.corp_id}")
                return False

            last_result = None
            retry_count = 0

        except Exception as pre_err:
            logger.error(f"❌ Pre-processing error for corp_id {job.corp_id}: {pre_err}")
            return False

        while retry_count < self.max_retries_per_job:
            try:
                result = self.call_ai_processing_function(job)
                category = result[0] if result else "Error"

                if self.should_retry_processing(category):
                    retry_count += 1
                    last_result = result
                    if retry_count < self.max_retries_per_job:
                        logger.warning(f"⚠️ AI processing returned retryable category='{category}', attempt {retry_count}/{self.max_retries_per_job} for corp_id: {job.corp_id}")
                        time.sleep(2 * retry_count)
                        continue
                    else:
                        logger.error(f"❌ AI processing failed after {self.max_retries_per_job} attempts for corp_id: {job.corp_id}")
                        # Move to delayed queue
                        requeued = self.requeue_failed_job(job, retry_count, "Max retries exceeded")
                        if not requeued:
                            # If requeue fails, push nothing extra — we do not create new queues.
                            logger.error(f"❌ Could not move job {job.job_id} to delayed queue after retries")
                        return False
                else:
                    logger.info(f"✅ AI processing successful for corp_id: {job.corp_id}, category: {category}")
                    break

            except TimeoutError as te:
                retry_count += 1
                logger.warning(f"⏱️ Timeout during AI processing (attempt {retry_count}/{self.max_retries_per_job}) for corp_id {job.corp_id}: {te}")
                if retry_count < self.max_retries_per_job:
                    time.sleep(2 * retry_count)
                    continue
                else:
                    logger.error(f"❌ Timeout persisted after {self.max_retries_per_job} attempts for corp_id {job.corp_id}")
                    requeued = self.requeue_failed_job(job, retry_count, "Timeout after retries")
                    if not requeued:
                        logger.error(f"❌ Could not move job {job.job_id} to delayed queue after timeout retries")
                    return False

            except Exception as e:
                retry_count += 1
                logger.error(f"❌ AI processing exception (attempt {retry_count}/{self.max_retries_per_job}) for corp_id {job.corp_id}: {e}")
                if retry_count < self.max_retries_per_job:
                    time.sleep(2 * retry_count)
                    continue
                else:
                    logger.error(f"❌ Exception persisted after {self.max_retries_per_job} attempts for corp_id {job.corp_id}")
                    requeued = self.requeue_failed_job(job, retry_count, f"Exception after retries: {e}")
                    if not requeued:
                        logger.error(f"❌ Could not move job {job.job_id} to delayed queue after exception retries")
                    return False

        # If we reach here, result variable holds the successful AI output
        try:
            category, summary, headline, findata, individual_investor_list, company_investor_list, sentiment = result

            if category == "Error":
                logger.error(f"❌ Final category is 'Error' for corp_id {job.corp_id}; not uploading.")
                return False

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

            processed_data = {
                "corp_id": job.corp_id,
                "summary": summary,
                "category": category,
                "headline": headline,
                "findata": findata,
                "individual_investor_list": individual_investor_list,
                "company_investor_list": company_investor_list,
                "sentiment": sentiment,
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

            supabase_job = SupabaseUploadJob(
                job_id=f"{job.job_id}_upload",
                corp_id=job.corp_id,
                processed_data=processed_data
            )

            queue_length = self.redis_client.lpush(QueueNames.SUPABASE_UPLOAD, serialize_job(supabase_job))
            logger.info(f"📊 Added job to Supabase queue - queue now has {queue_length} jobs")
            self.jobs_processed += 1
            return True

        except Exception as e:
            logger.error(f"❌ Failed to create Supabase job for {job.corp_id}: {e}")
            # Try to move to delayed queue
            requeued = self.requeue_failed_job(job, retry_count, f"Failed to prepare supabase upload: {e}")
            if not requeued:
                logger.error(f"❌ Could not move job {job.job_id} to delayed queue after supabase preparation failure")
            return False

    def process_ai_job(self, job: AIProcessingJob) -> bool:
        return self.process_ai_job_with_retry(job)

    def run(self):
        import traceback

        logger.info(f"🚀 {self.worker_id} starting (ephemeral mode with retry logic)")

        if not self.setup_redis():
            return False

        start_time = time.time()
        last_job_time = time.time()

        try:
            while True:
                if self.jobs_processed >= self.max_jobs_per_session:
                    logger.info(f"✅ Processed {self.jobs_processed} jobs, shutting down")
                    break

                if time.time() - last_job_time > self.idle_timeout:
                    logger.info(f"⏰ No jobs for {self.idle_timeout}s, shutting down")
                    break

                try:
                    logger.info(f"🔍 Checking for jobs in {QueueNames.AI_PROCESSING}")
                    result = self.redis_client.brpop(QueueNames.AI_PROCESSING, timeout=5)

                    if not result:
                        logger.debug("💤 No jobs available in queue")
                        continue

                    queue_name, job_json = result
                    # job_json may be bytes depending on redis client - ensure string
                    try:
                        job_json_str = job_json.decode() if isinstance(job_json, (bytes, bytearray)) else str(job_json)
                    except Exception:
                        job_json_str = str(job_json)

                    logger.info(f"📦 Got job from {queue_name}: {job_json_str[:200]}...")

                    try:
                        job = deserialize_job(job_json)
                    except Exception as job_error:
                        logger.error(f"❌ Failed to deserialize job: {job_error}")
                        # Push raw payload to your existing FAILED_JOBS queue for inspection
                        try:
                            self.redis_client.lpush(QueueNames.FAILED_JOBS, job_json)
                            logger.info(f"📥 Raw job pushed to {QueueNames.FAILED_JOBS}")
                        except Exception as push_err:
                            logger.error(f"❌ Failed to push raw job to {QueueNames.FAILED_JOBS}: {push_err}")
                        continue

                    if not isinstance(job, AIProcessingJob):
                        logger.warning(f"⚠️ Unexpected job type: {type(job)} - skipping")
                        continue

                    lock_key = f"worker_processing:{job.corp_id}:{job.job_id}"
                    self.current_lock_key = lock_key
                    try:
                        lock_acquired = self.redis_client.set(lock_key, self.worker_id, nx=True, ex=360)
                    except Exception as e:
                        logger.warning(f"⚠️ Redis lock attempt failed for {job.job_id}: {e}")
                        lock_acquired = False

                    if not lock_acquired:
                        logger.warning(f"⚠️ Job {job.job_id} already being processed - SKIPPING")
                        self.current_lock_key = None
                        continue

                    try:
                        logger.info(f"🤖 Processing AI job for corp_id: {job.corp_id}")
                        success = False
                        try:
                            success = self.process_ai_job_with_retry(job)
                        except TimeoutError as te:
                            # A TimeoutError here means the processing wrapper raised; but
                            # process_ai_job_with_retry already handles TimeoutError and will requeue on exhaustion,
                            # so we treat this as failure and continue.
                            logger.error(f"⏱️ Unhandled timeout for job {job.job_id}: {te}")
                            # best-effort: try to move job to delayed queue right now
                            try:
                                self.requeue_failed_job(job, getattr(job, "retry_count", 0) or 0, f"Unhandled timeout: {te}")
                            except Exception:
                                logger.error(f"❌ Failed to move job {job.job_id} to delayed queue after unhandled timeout")
                            success = False
                        except Exception as e:
                            logger.error(f"❌ Unhandled exception processing job {job.job_id}: {e}")
                            logger.debug(traceback.format_exc())
                            # process_ai_job_with_retry should have moved to delayed queue on exhaustion
                            success = False

                        last_job_time = time.time()
                        if success:
                            logger.info(f"✅ Job {job.job_id} processed successfully")
                        else:
                            logger.warning(f"⚠️ Job {job.job_id} not completed in this run (may be requeued to delayed)")

                    finally:
                        try:
                            self.redis_client.delete(lock_key)
                            self.current_lock_key = None
                            logger.debug(f"🔓 Released lock for {job.job_id}")
                        except Exception as unlock_err:
                            logger.warning(f"Failed to release lock for {job.job_id}: {unlock_err}")
                            self.current_lock_key = None

                except redis.TimeoutError:
                    logger.debug("⏰ Queue timeout, continuing...")
                    continue
                except Exception as e:
                    logger.error(f"❌ Worker loop error: {e}")
                    logger.debug(traceback.format_exc())
                    time.sleep(1)

        except KeyboardInterrupt:
            logger.info(f"🛑 {self.worker_id} interrupted")

        finally:
            runtime = time.time() - start_time
            logger.info(f"🏁 {self.worker_id} finished - {self.jobs_processed} jobs in {runtime:.1f}s")
        return True

def main():
    worker = EphemeralAIWorker()
    worker.run()

if __name__ == "__main__":
    main()
