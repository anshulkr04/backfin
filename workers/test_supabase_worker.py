#!/usr/bin/env python3
"""
Simple Supabase Upload Worker for testing
"""

import time
import sys
import logging
from pathlib import Path
import redis
import json

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.queue.redis_client import RedisConfig, QueueNames
from src.queue.job_types import deserialize_job, SupabaseUploadJob

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(f"supabase_worker_{os.getpid() if 'os' in globals() else 'test'}")

def main():
    """Main worker loop"""
    import os
    worker_id = f"supabase_worker_{os.getpid()}"
    logger.info(f"Supabase Worker {worker_id} starting up")
    
    # Setup Redis
    config = RedisConfig()
    redis_client = redis.Redis(
        host=config.redis_host,
        port=config.redis_port,
        db=config.redis_db,
        decode_responses=True
    )
    
    logger.info(f"Supabase Worker {worker_id} started, waiting for jobs...")
    
    try:
        while True:
            try:
                # Get job from queue (blocking wait with timeout)
                result = redis_client.brpop(QueueNames.SUPABASE_UPLOAD, timeout=5)
                
                if result:
                    queue_name, job_json = result
                    job = deserialize_job(job_json)
                    
                    if isinstance(job, SupabaseUploadJob):
                        logger.info(f"Processing Supabase upload for corp_id: {job.corp_id}")
                        
                        # Simulate Supabase upload
                        time.sleep(2)  # Simulate processing time
                        
                        logger.info(f"Supabase upload completed for corp_id: {job.corp_id}")
                        
                        # Could create investor analysis job here
                        # For now, just log completion
                        
                    else:
                        logger.warning(f"Unexpected job type: {type(job)}")
                        
            except redis.TimeoutError:
                # No jobs available, continue waiting
                continue
            except Exception as e:
                logger.error(f"Worker error: {e}")
                time.sleep(1)
                
    except KeyboardInterrupt:
        logger.info(f"Supabase Worker {worker_id} shutting down")

if __name__ == "__main__":
    main()