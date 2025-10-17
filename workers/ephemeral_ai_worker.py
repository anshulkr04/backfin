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
from pathlib import Path
from datetime import datetime
import redis
from google import genai
from pydantic import BaseModel, Field

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.queue.redis_client import RedisConfig, QueueNames
from src.queue.job_types import deserialize_job, AIProcessingJob, SupabaseUploadJob, serialize_job

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
    
    def generate_content(self, contents, config=None):
        """Generate content with rate limiting"""
        if not self.client:
            raise Exception("Gemini client not initialized")
        
        # Rate limiting
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        try:
            response = self.client.generate_content(contents=contents, config=config)
            self.last_request_time = time.time()
            return response
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
        """Upload file with rate limiting"""
        if not self.files_client:
            raise Exception("Files client not available")
        
        # Rate limiting
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            logger.debug(f"Rate limiting file upload: sleeping for {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        try:
            result = self.files_client.upload(file=file)
            self.last_request_time = time.time()
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
            self.redis_client = redis.Redis(
                host=self.redis_config.redis_host,
                port=self.redis_config.redis_port,
                db=self.redis_config.redis_db,
                decode_responses=True
            )
            self.redis_client.ping()
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
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            with open(filepath, "wb") as file:
                file.write(response.content)
            
            logger.info(f"✅ Downloaded PDF to: {filepath}")
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
                config={
                    "response_mime_type": "application/json",
                    "response_schema": list[StrucOutput]
                },
            )
            
            if not hasattr(response, 'text'):
                logger.error("AI response missing text attribute")
                return "Error", "AI processing failed: invalid response format", "", "", [], [], "Neutral"
                
            # Parse JSON response
            logger.info("📝 Parsing AI response...")
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
                
                logger.info(f"✅ AI processing completed successfully")
                logger.info(f"📊 Category: {category_text}")
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
        finally:
            # Clean up uploaded file
            try:
                if uploaded_file and hasattr(uploaded_file, 'delete'):
                    uploaded_file.delete()
            except:
                pass  # Ignore cleanup errors
    
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
            
            # Try different possible fields for PDF URL
            if isinstance(announcement_data, dict):
                pdf_url = (announcement_data.get('PDFPATH') or 
                          announcement_data.get('pdf_url') or 
                          announcement_data.get('fileurl') or
                          announcement_data.get('AttchmntFile'))
            
            if not pdf_url:
                logger.error(f"No PDF URL found in announcement data for job {job.job_id}")
                return "Error", "No PDF URL found in announcement data", "", "", [], [], "Neutral"
            
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
    
    def process_ai_job_with_retry(self, job: AIProcessingJob) -> bool:
        """Process an AI job with retry logic for failures"""
        logger.info(f"🤖 Processing AI job for corp_id: {job.corp_id}")
        
        last_result = None
        retry_count = 0
        
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
                        # Use the last result even if it failed
                        result = last_result or ("Error", "Max retries exceeded", "", "", [], [], "Neutral")
                        break
                else:
                    # Success! Valid category returned
                    logger.info(f"✅ AI processing successful for corp_id: {job.corp_id}, category: {category}")
                    break
                    
            except Exception as e:
                retry_count += 1
                logger.error(f"❌ AI processing exception (attempt {retry_count}): {e}")
                
                if retry_count >= self.max_retries_per_job:
                    result = ("Error", f"Exception after {self.max_retries_per_job} retries: {str(e)}", "", "", [], [], "Neutral")
                    break
                    
                time.sleep(2 * retry_count)  # Exponential backoff
        
        # Process the final result
        try:
            category, summary, headline, findata, individual_investor_list, company_investor_list, sentiment = result
            
            # Extract additional data from the job for Supabase upload
            announcement_data = job.announcement_data or {}
            
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
                "processed_by": self.worker_id,
                "processed_at": datetime.now().isoformat(),
                "retry_count": retry_count,
                # Include original announcement data
                "securityid": announcement_data.get('SCRIP_CD') or announcement_data.get('securityid', ''),
                "companyname": announcement_data.get('COMPNAME') or announcement_data.get('companyname', ''),
                "symbol": announcement_data.get('SYMBOL') or announcement_data.get('symbol', ''),
                "isin": announcement_data.get('ISIN') or announcement_data.get('isin', ''),
                "date": announcement_data.get('DT_TM') or announcement_data.get('date', ''),
                "fileurl": announcement_data.get('PDFPATH') or announcement_data.get('fileurl', ''),
                "newsid": announcement_data.get('NEWSID') or announcement_data.get('newsid', ''),
            }
            
            # Create Supabase upload job
            supabase_job = SupabaseUploadJob(
                job_id=f"{job.job_id}_upload",
                corp_id=job.corp_id,
                processed_data=processed_data
            )
            
            # Add to Supabase queue
            self.redis_client.lpush(QueueNames.SUPABASE_UPLOAD, serialize_job(supabase_job))
            
            logger.info(f"✅ AI processing completed for corp_id: {job.corp_id} (retries: {retry_count})")
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
                    result = self.redis_client.brpop(QueueNames.AI_PROCESSING, timeout=5)
                    
                    if result:
                        queue_name, job_json = result
                        job = deserialize_job(job_json)
                        
                        if isinstance(job, AIProcessingJob):
                            self.process_ai_job_with_retry(job)
                            last_job_time = time.time()
                        else:
                            logger.warning(f"⚠️ Unexpected job type: {type(job)}")
                    
                except redis.TimeoutError:
                    # No jobs available, continue checking
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