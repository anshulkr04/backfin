#!/usr/bin/env python3
"""
Ephemeral Supabase Worker - Processes upload jobs then shuts down
"""

import time
import sys
import logging
import os
import json
import signal
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
        self.current_lock_key = None  # Track current processing lock for cleanup
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
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
        
    def setup_redis(self):
        """Setup Redis connection"""
        try:
            self.redis_client = self.redis_config.get_connection()
            logger.info("✅ Redis client initialized successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            return False
    
    def process_supabase_job(self, job: SupabaseUploadJob) -> bool:
        """Process a Supabase upload job with duplicate prevention"""
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
                return False            # Initialize Supabase client
            try:
                from supabase import create_client, Client
                
                # Get Supabase credentials from environment
                supabase_url = os.getenv('SUPABASE_URL2')
                supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
                
                if not supabase_url or not supabase_key:
                    logger.error("Supabase credentials not found in environment")
                    return False
                
                supabase: Client = create_client(supabase_url, supabase_key)
                
            except Exception as e:
                logger.error(f"Failed to initialize Supabase client: {e}")
                return False
            
            # Prepare data for upload (exactly matching BSE scraper structure)
            # Construct file URL if we have PDF path info
            fileurl = processed_data.get("fileurl")
            if not fileurl and processed_data.get("pdf_file"):
                fileurl = f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{processed_data.get('pdf_file')}"
            
            upload_data = {
                "corp_id": processed_data.get("corp_id"),
                "securityid": processed_data.get("securityid"),
                "summary": processed_data.get("original_summary", ""),  # Original BSE summary (if available)
                "fileurl": fileurl,
                "date": processed_data.get("date"),
                "ai_summary": processed_data.get("summary"),  # AI-generated analysis goes to ai_summary
                "category": category,
                "isin": processed_data.get("isin"),
                "companyname": processed_data.get("companyname"),
                "symbol": processed_data.get("symbol"),
                "sentiment": processed_data.get("sentiment"),
                "headline": processed_data.get("headline"),
                "company_id": processed_data.get("company_id")
            }
            
            logger.info(f"Prepared data for corp_id {job.corp_id}: {upload_data}")
            
            try:
                # Check if corp_id already exists in Supabase to prevent duplicates
                existing_check = supabase.table("corporatefilings").select("corp_id").eq("corp_id", job.corp_id).execute()
                
                if existing_check.data and len(existing_check.data) > 0:
                    logger.warning(f"⚠️ Corp_id {job.corp_id} already exists in Supabase - skipping upload to prevent duplicate")
                    # Best-effort local mark-as-sent using newsid to avoid future re-queuing
                    try:
                        newsid = processed_data.get('newsid')
                        if newsid:
                            import sqlite3
                            from pathlib import Path
                            db_path = Path("/app/data") / "bse_raw.db"
                            conn = sqlite3.connect(str(db_path), timeout=15)
                            cur = conn.cursor()
                            cur.execute(
                                "UPDATE announcements SET sent_to_supabase = 1, sent_to_supabase_at = datetime('now') WHERE newsid = ?",
                                (str(newsid),)
                            )
                            conn.commit()
                            conn.close()
                            logger.info(f"🧾 Marked NEWSID {newsid} as sent_to_supabase=1 (pre-existing row)")
                    except Exception as mark_err:
                        logger.warning(f"Failed to mark local announcement as sent (pre-existing): {mark_err}")
                    return True  # Return True since the data already exists
                
                # Upload to Supabase
                response = supabase.table("corporatefilings").insert(upload_data).execute()
                
                if hasattr(response, 'error') and response.error:
                    # Check if it's a duplicate key error (concurrent processing)
                    error_msg = str(response.error)
                    if "duplicate key" in error_msg.lower() or "23505" in error_msg:
                        logger.warning(f"⚠️ Duplicate key detected for corp_id {job.corp_id} - data already exists")
                        return True  # Consider this successful since data exists
                    else:
                        logger.error(f"Supabase upload error: {response.error}")
                        return False
                
                logger.info(f"✅ Successfully uploaded to Supabase for corp_id: {job.corp_id}")

                # Mark local announcements table as sent if possible using newsid
                try:
                    newsid = processed_data.get('newsid')
                    if newsid:
                        import sqlite3
                        from pathlib import Path
                        db_path = Path("/app/data") / "bse_raw.db"
                        conn = sqlite3.connect(str(db_path), timeout=15)
                        cur = conn.cursor()
                        cur.execute(
                            "UPDATE announcements SET sent_to_supabase = 1, sent_to_supabase_at = datetime('now') WHERE newsid = ?",
                            (str(newsid),)
                        )
                        conn.commit()
                        conn.close()
                        logger.info(f"🧾 Marked NEWSID {newsid} as sent_to_supabase=1 in local DB")
                except Exception as mark_err:
                    logger.warning(f"Failed to mark local announcement as sent: {mark_err}")
                
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
                            # IMMEDIATE lock acquisition to prevent duplicate processing
                            lock_key = f"worker_processing:{job.corp_id}:{job.job_id}"
                            self.current_lock_key = lock_key  # Track for cleanup
                            
                            lock_acquired = self.redis_client.set(
                                lock_key, 
                                self.worker_id, 
                                nx=True,  # Only set if not exists
                                ex=90     # 90 second lock (shorter for quick uploads)
                            )
                            
                            if not lock_acquired:
                                logger.warning(f"⚠️ Upload job {job.job_id} is already being processed by another worker - SKIPPING")
                                self.current_lock_key = None  # Clear tracking
                                continue  # Skip this job, don't count as processed
                                
                            try:
                                success = self.process_supabase_job(job)
                                if success:
                                    self.jobs_processed += 1
                                    logger.info(f"✅ Upload job {job.job_id} completed successfully ({self.jobs_processed}/{self.max_jobs_per_session})")
                                last_job_time = time.time()
                                
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