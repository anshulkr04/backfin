#!/usr/bin/env python3
"""
Ephemeral Investor Worker - Processes investor analysis jobs then shuts down
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
from src.queue.job_types import deserialize_job, InvestorAnalysisJob

# Setup logging
worker_id = f"ephemeral_investor_{os.getpid()}"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(worker_id)

class EphemeralInvestorWorker:
    """Investor worker that processes available jobs then shuts down"""
    
    def __init__(self):
        self.worker_id = worker_id
        self.redis_config = RedisConfig()
        self.redis_client = None
        self.jobs_processed = 0
        self.max_jobs_per_session = 8  # Process max 8 jobs then shutdown
        self.idle_timeout = 20  # Shutdown after 20 seconds of no jobs
        
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
    
    def process_investor_job(self, job: InvestorAnalysisJob) -> bool:
        """Process an investor analysis job"""
        try:
            logger.info(f"👥 Analyzing investors for corp_id: {job.corp_id}")
            
            # Simulate investor analysis
            time.sleep(3)  # Simulate analysis time
            
            # Log analysis results
            individual_count = len(job.individual_investors)
            company_count = len(job.company_investors)
            
            logger.info(f"📊 Analysis complete for {job.corp_id}: "
                       f"{individual_count} individuals, {company_count} companies")
            
            # Here you would typically:
            # 1. Send notifications to matched investors
            # 2. Update investor databases
            # 3. Generate reports
            
            logger.info(f"✅ Investor analysis completed for corp_id: {job.corp_id}")
            self.jobs_processed += 1
            return True
            
        except Exception as e:
            logger.error(f"❌ Investor analysis failed for {job.corp_id}: {e}")
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
                    result = self.redis_client.brpop(QueueNames.INVESTOR_PROCESSING, timeout=4)
                    
                    if result:
                        queue_name, job_json = result
                        job = deserialize_job(job_json)
                        
                        if isinstance(job, InvestorAnalysisJob):
                            self.process_investor_job(job)
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
    worker = EphemeralInvestorWorker()
    worker.run()

if __name__ == "__main__":
    main()