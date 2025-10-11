#!/usr/bin/env python3
"""
Ephemeral AI Worker - Processes jobs then shuts down
"""

import time
import sys
import logging
import os
from pathlib import Path
from datetime import datetime
import redis

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.queue.redis_client import RedisConfig, QueueNames
from src.queue.job_types import deserialize_job, AIProcessingJob, SupabaseUploadJob, serialize_job

# Setup logging
worker_id = f"ephemeral_ai_{os.getpid()}"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(worker_id)

class EphemeralAIWorker:
    """AI worker that processes available jobs then shuts down"""
    
    def __init__(self):
        self.worker_id = worker_id
        self.redis_config = RedisConfig()
        self.redis_client = None
        self.jobs_processed = 0
        self.max_jobs_per_session = 10  # Process max 10 jobs then shutdown
        self.idle_timeout = 30  # Shutdown after 30 seconds of no jobs
        
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
    
    def process_ai_job(self, job: AIProcessingJob) -> bool:
        """Process an AI job"""
        try:
            logger.info(f"🤖 Processing AI job for corp_id: {job.corp_id}")
            
            # Simulate AI processing
            time.sleep(2)  # Simulate processing time
            
            # Create result for Supabase upload
            processed_data = {
                "corp_id": job.corp_id,
                "company_name": job.company_name,
                "security_id": job.security_id,
                "summary": f"AI-generated summary for {job.company_name}",
                "category": "auto_categorized",
                "sentiment": "neutral",
                "processed_by": self.worker_id,
                "processed_at": datetime.now().isoformat()
            }
            
            # Create Supabase upload job
            supabase_job = SupabaseUploadJob(
                job_id=f"{job.job_id}_upload",
                corp_id=job.corp_id,
                processed_data=processed_data
            )
            
            # Add to Supabase queue
            self.redis_client.lpush(QueueNames.SUPABASE_UPLOAD, serialize_job(supabase_job))
            
            logger.info(f"✅ AI processing completed for corp_id: {job.corp_id}")
            self.jobs_processed += 1
            return True
            
        except Exception as e:
            logger.error(f"❌ AI processing failed for {job.corp_id}: {e}")
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
                    result = self.redis_client.brpop(QueueNames.AI_PROCESSING, timeout=5)
                    
                    if result:
                        queue_name, job_json = result
                        job = deserialize_job(job_json)
                        
                        if isinstance(job, AIProcessingJob):
                            self.process_ai_job(job)
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