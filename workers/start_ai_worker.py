#!/usr/bin/env python3
"""
AI Worker Entry Point - Processes AI jobs from Redis queue
"""

import os
import sys
import time
import json
import logging
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.queue.redis_client import get_redis_client, QueueNames
from src.queue.job_types import deserialize_job, serialize_job, AIProcessingJob, FailedJob
from src.ai.prompts import all_prompt  # Will need to update import after restructure

class AIWorker:
    """Worker for processing AI analysis jobs"""
    
    def __init__(self):
        self.redis = get_redis_client()
        self.worker_id = f"ai_worker_{os.getpid()}"
        self.running = True
        
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format=f"%(asctime)s - {self.worker_id} - %(levelname)s - %(message)s"
        )
        self.logger = logging.getLogger(__name__)
        
        self.logger.info(f"AI Worker {self.worker_id} starting up")
    
    def process_job(self, job: AIProcessingJob) -> bool:
        """Process a single AI job"""
        try:
            self.logger.info(f"Processing AI job for corp_id: {job.corp_id}")
            
            # TODO: Move actual AI processing logic here from bse_scraper.py
            # This is where you'd call the Gemini API, process PDFs, etc.
            
            # Simulate processing for now
            time.sleep(2)
            
            # Create result job for Supabase upload
            from src.queue.job_types import SupabaseUploadJob
            result_job = SupabaseUploadJob(
                job_id=f"upload_{job.corp_id}_{int(time.time())}",
                corp_id=job.corp_id,
                processed_data={
                    "category": "Procedural/Administrative",  # From AI processing
                    "ai_summary": "AI processed summary",
                    "headline": "Generated headline",
                    "sentiment": "Neutral"
                }
            )
            
            # Push to Supabase upload queue
            self.redis.lpush(QueueNames.SUPABASE_UPLOAD, serialize_job(result_job))
            
            self.logger.info(f"AI processing completed for corp_id: {job.corp_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"AI processing failed for corp_id {job.corp_id}: {e}")
            
            # Create failed job
            failed_job = FailedJob(
                job_id=f"failed_{job.job_id}_{int(time.time())}",
                original_job_type=job.job_type,
                original_job_data=job.model_dump(),
                error_message=str(e)
            )
            
            # Push to failed queue
            self.redis.lpush(QueueNames.FAILED_JOBS, serialize_job(failed_job))
            return False
    
    def run(self):
        """Main worker loop"""
        self.logger.info(f"AI Worker {self.worker_id} started, waiting for jobs...")
        
        while self.running:
            try:
                # Block and wait for job (timeout after 5 seconds)
                job_data = self.redis.brpop(QueueNames.AI_PROCESSING, timeout=5)
                
                if job_data is None:
                    # Timeout - no jobs available
                    continue
                
                # Parse job
                _, job_json = job_data
                job = deserialize_job(job_json.decode('utf-8'))
                
                if not isinstance(job, AIProcessingJob):
                    self.logger.error(f"Received non-AI job: {job.job_type}")
                    continue
                
                # Process the job
                self.process_job(job)
                
            except KeyboardInterrupt:
                self.logger.info("Received shutdown signal")
                self.running = False
                
            except Exception as e:
                self.logger.error(f"Worker error: {e}")
                time.sleep(1)  # Brief pause before retrying
        
        self.logger.info(f"AI Worker {self.worker_id} shutting down")

def main():
    """Entry point for AI worker"""
    worker = AIWorker()
    
    try:
        worker.run()
    except KeyboardInterrupt:
        print("\\nShutting down AI worker...")
    except Exception as e:
        print(f"AI worker crashed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()