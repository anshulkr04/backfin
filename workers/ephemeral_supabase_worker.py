#!/usr/bin/env python3
"""
Ephemeral Supabase Worker - Processes upload jobs then shuts down
"""

import time
import sys
import logging
import os
import json
from pathlib import Path
from datetime import datetime
import redis

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.queue.redis_client import RedisConfig, QueueNames
from src.queue.job_types import deserialize_job, SupabaseUploadJob, InvestorAnalysisJob, serialize_job

# Setup logging
worker_id = f"ephemeral_supabase_{os.getpid()}"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(worker_id)

class EphemeralSupabaseWorker:
    """Supabase worker that processes available jobs then shuts down"""
    
    def __init__(self):
        self.worker_id = worker_id
        self.redis_config = RedisConfig()
        self.redis_client = None
        self.jobs_processed = 0
        self.max_jobs_per_session = 15  # Process max 15 jobs then shutdown
        self.idle_timeout = 25  # Shutdown after 25 seconds of no jobs
        
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
    
    def process_supabase_job(self, job: SupabaseUploadJob) -> bool:
        """Process a Supabase upload job"""
        try:
            logger.info(f"📤 Uploading data to Supabase for corp_id: {job.corp_id}")
            
            processed_data = job.processed_data
            if not processed_data:
                logger.error(f"No processed data for corp_id: {job.corp_id}")
                return False
            
            # Check if category is Error - skip upload if so
            category = processed_data.get('category', '')
            if category == "Error":
                logger.warning(f"⚠️ Skipping Supabase upload for corp_id {job.corp_id} - category is 'Error'")
                return False
                
            # Initialize Supabase client
            try:
                from supabase import create_client, Client
                
                # Get Supabase credentials from environment
                supabase_url = os.getenv('SUPABASE_URL')
                supabase_key = os.getenv('SUPABASE_ANON_KEY')
                
                if not supabase_url or not supabase_key:
                    logger.error("Supabase credentials not found in environment")
                    return False
                
                supabase: Client = create_client(supabase_url, supabase_key)
                
            except Exception as e:
                logger.error(f"Failed to initialize Supabase client: {e}")
                return False
            
            # Prepare data for upload
            upload_data = {
                "corp_id": processed_data.get("corp_id"),
                "securityid": processed_data.get("securityid", ""),
                "summary": processed_data.get("summary", ""),
                "fileurl": processed_data.get("fileurl", ""),
                "date": processed_data.get("date", ""),
                "ai_summary": processed_data.get("summary", ""),  # Use summary as ai_summary
                "category": category,
                "isin": processed_data.get("isin", ""),
                "companyname": processed_data.get("companyname", ""),
                "symbol": processed_data.get("symbol", ""),
                "sentiment": processed_data.get("sentiment", "Neutral"),
                "headline": processed_data.get("headline", ""),
                "newsid": processed_data.get("newsid", "")
            }
            
            # Remove any None values
            upload_data = {k: v for k, v in upload_data.items() if v is not None}
            
            try:
                # Upload to Supabase
                response = supabase.table("corporatefilings").insert(upload_data).execute()
                
                if hasattr(response, 'error') and response.error:
                    logger.error(f"Supabase upload error: {response.error}")
                    return False
                
                logger.info(f"✅ Successfully uploaded to Supabase for corp_id: {job.corp_id}")
                
                # Upload financial data if available
                findata = processed_data.get('findata')
                if findata and findata != '{"period": "", "sales_current": "", "sales_previous_year": "", "pat_current": "", "pat_previous_year": ""}':
                    try:
                        financial_data = json.loads(findata) if isinstance(findata, str) else findata
                        if any(financial_data.values()):  # Only upload if there's actual data
                            financial_data.update({
                                'corp_id': job.corp_id,
                                'symbol': processed_data.get("symbol", ""),
                                'isin': processed_data.get("isin", "")
                            })
                            
                            fin_response = supabase.table("financial_results").insert(financial_data).execute()
                            logger.info(f"✅ Uploaded financial data for corp_id: {job.corp_id}")
                    except Exception as e:
                        logger.warning(f"Failed to upload financial data: {e}")
                
                # Upload investor data if available
                individual_investors = processed_data.get('individual_investor_list', [])
                company_investors = processed_data.get('company_investor_list', [])
                
                if individual_investors or company_investors:
                    try:
                        from src.services.investor_analyzer import uploadInvestor
                        uploadInvestor(individual_investors, company_investors, corp_id=job.corp_id)
                        logger.info(f"✅ Uploaded investor data for corp_id: {job.corp_id}")
                    except Exception as e:
                        logger.warning(f"Failed to upload investor data: {e}")
                
            except Exception as e:
                logger.error(f"Error uploading to Supabase: {e}")
                return False
                
            # Create investor analysis job if category suggests it
            if category not in ['Procedural/Administrative', 'routine', 'minor']:
                investor_job = InvestorAnalysisJob(
                    job_id=f"{job.job_id}_investor",
                    corp_id=job.corp_id,
                    category=category,
                    individual_investors=individual_investors,
                    company_investors=company_investors
                )
                
                # Add to investor processing queue
                self.redis_client.lpush(QueueNames.INVESTOR_PROCESSING, serialize_job(investor_job))
                logger.info(f"🔗 Created investor analysis job for {job.corp_id}")
            
            logger.info(f"✅ Supabase upload completed for corp_id: {job.corp_id}")
            self.jobs_processed += 1
            return True
            
        except Exception as e:
            logger.error(f"❌ Supabase upload failed for {job.corp_id}: {e}")
            return False
    
    def run(self):
        """Main worker loop - process jobs then shutdown"""
        logger.info(f"🚀 {self.worker_id} starting (ephemeral mode)")
        
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
                    result = self.redis_client.brpop(QueueNames.SUPABASE_UPLOAD, timeout=3)
                    
                    if result:
                        queue_name, job_json = result
                        job = deserialize_job(job_json)
                        
                        if isinstance(job, SupabaseUploadJob):
                            self.process_supabase_job(job)
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
    worker = EphemeralSupabaseWorker()
    worker.run()

if __name__ == "__main__":
    main()