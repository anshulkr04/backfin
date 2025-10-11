#!/usr/bin/env python3
"""
Ephemeral AI Worker - Processes jobs then shuts down
Now includes retry logic for AI processing failures
"""

import time
import sys
import logging
import os
from pathlib import Path
from datetime import datetime
import redis
import json

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.queue.redis_client import RedisConfig, QueueNames
from src.queue.job_types import deserialize_job, AIProcessingJob, SupabaseUploadJob, serialize_job

# Import your actual AI processing function
sys.path.append(str(Path(__file__).parent.parent / "src" / "ai"))

# Setup logging first
worker_id = f"ephemeral_ai_{os.getpid()}"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(worker_id)

try:
    from src.ai.prompts import *  # Import prompts
    # You'll need to implement the actual AI processing function here
    # For now, I'll create a placeholder that calls your existing AI logic
except ImportError:
    logger.warning("Could not import AI prompts")

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
    
    def call_ai_processing_function(self, job: AIProcessingJob) -> tuple:
        """
        Call your actual AI processing function here.
        This is a placeholder - you need to integrate with your existing AI processing logic.
        
        Returns: (category, summary, headline, findata, individual_investor_list, company_investor_list, sentiment)
        """
        try:
            # TODO: Replace this with your actual AI processing call
            # For example, if you have a PDF file path in the job:
            # from replay import ai_process_pdf
            # return ai_process_pdf(job.pdf_file_path)
            
            # For now, simulate AI processing
            time.sleep(2)  # Simulate processing time
            
            # Simulate different outcomes for testing
            import random
            rand = random.random()
            
            if rand < 0.1:  # 10% chance of "Error"
                return ("Error", "AI processing failed", "", "", [], [], "Neutral")
            elif rand < 0.2:  # 10% chance of invalid category
                return ("Invalid Category", "AI-generated summary", "", "", [], [], "Neutral")
            else:  # 80% chance of success
                return ("Financial Results", f"AI-generated summary for {job.company_name}", 
                       "Test headline", "", [], [], "Neutral")
                
        except Exception as e:
            logger.error(f"AI processing exception: {e}")
            return ("Error", f"Exception in AI processing: {str(e)}", "", "", [], [], "Neutral")
    
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
            
            # Create processed data for Supabase upload
            processed_data = {
                "corp_id": job.corp_id,
                "company_name": job.company_name,
                "security_id": job.security_id,
                "summary": summary,
                "category": category,
                "headline": headline,
                "findata": findata,
                "individual_investor_list": individual_investor_list,
                "company_investor_list": company_investor_list,
                "sentiment": sentiment,
                "processed_by": self.worker_id,
                "processed_at": datetime.now().isoformat(),
                "retry_count": retry_count
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