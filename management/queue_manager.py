"""
Queue management utilities for monitoring and controlling Redis queues
"""

import json
import time
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.queue.redis_client import redis_client, QueueNames
from src.queue.job_types import deserialize_job, BaseJob

class QueueManager:
    """Manager for Redis queue operations"""
    
    def __init__(self):
        self.redis = redis_client
        
    def get_queue_lengths(self) -> Dict[str, int]:
        """Get length of all queues"""
        lengths = {}
        for queue_name in QueueNames.all_queues():
            try:
                lengths[queue_name] = self.redis.llen(queue_name)
            except Exception as e:
                lengths[queue_name] = f"Error: {e}"
        return lengths
    
    def peek_queue(self, queue_name: str, count: int = 5) -> List[Dict[str, Any]]:
        """Peek at jobs in queue without removing them"""
        try:
            jobs = self.redis.lrange(queue_name, 0, count - 1)
            return [json.loads(job.decode('utf-8')) for job in jobs]
        except Exception as e:
            return [{"error": str(e)}]
    
    def move_job(self, from_queue: str, to_queue: str) -> bool:
        """Move a job from one queue to another"""
        try:
            job = self.redis.rpoplpush(from_queue, to_queue)
            return job is not None
        except Exception as e:
            print(f"Error moving job: {e}")
            return False
    
    def clear_queue(self, queue_name: str) -> int:
        """Clear all jobs from a queue"""
        try:
            return self.redis.delete(queue_name)
        except Exception as e:
            print(f"Error clearing queue {queue_name}: {e}")
            return 0
    
    def get_failed_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get failed jobs for investigation"""
        return self.peek_queue(QueueNames.FAILED_JOBS, limit)
    
    def retry_failed_jobs(self, max_jobs: int = 5) -> int:
        """Move jobs from failed queue back to appropriate processing queues"""
        retried = 0
        for _ in range(max_jobs):
            job_data = self.redis.rpop(QueueNames.FAILED_JOBS)
            if not job_data:
                break
                
            try:
                job = deserialize_job(job_data.decode('utf-8'))
                # Determine target queue based on original job type
                target_queue = self._get_target_queue_for_retry(job)
                if target_queue:
                    self.redis.lpush(target_queue, job_data)
                    retried += 1
            except Exception as e:
                # Put back in failed queue if we can't process it
                self.redis.lpush(QueueNames.FAILED_JOBS, job_data)
                print(f"Error retrying job: {e}")
        
        return retried
    
    def _get_target_queue_for_retry(self, job: BaseJob) -> Optional[str]:
        """Determine which queue a failed job should be retried in"""
        job_type_mapping = {
            "ai_processing": QueueNames.AI_PROCESSING,
            "supabase_upload": QueueNames.SUPABASE_UPLOAD,
            "investor_analysis": QueueNames.INVESTOR_PROCESSING,
        }
        return job_type_mapping.get(job.job_type)
    
    def print_status(self):
        """Print formatted queue status"""
        print("=" * 60)
        print(f"Queue Status - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        lengths = self.get_queue_lengths()
        for queue_name, length in lengths.items():
            queue_short = queue_name.split(':')[-1].upper()
            print(f"{queue_short:<20} | {length:>8}")
        
        print("\nFailed Jobs (last 3):")
        failed_jobs = self.get_failed_jobs(3)
        for i, job in enumerate(failed_jobs, 1):
            print(f"  {i}. {job.get('job_type', 'unknown')} - {job.get('error_message', 'No error message')[:50]}...")

def main():
    """CLI interface for queue management"""
    import sys
    
    manager = QueueManager()
    
    if len(sys.argv) < 2:
        print("Usage: python queue_manager.py [status|clear|retry|peek] [queue_name]")
        return
    
    command = sys.argv[1].lower()
    
    if command == "status":
        manager.print_status()
    
    elif command == "clear" and len(sys.argv) > 2:
        queue_name = sys.argv[2]
        cleared = manager.clear_queue(queue_name)
        print(f"Cleared {cleared} items from {queue_name}")
    
    elif command == "retry":
        retried = manager.retry_failed_jobs()
        print(f"Retried {retried} failed jobs")
    
    elif command == "peek" and len(sys.argv) > 2:
        queue_name = sys.argv[2]
        jobs = manager.peek_queue(queue_name, 10)
        print(f"First 10 jobs in {queue_name}:")
        for i, job in enumerate(jobs, 1):
            print(f"  {i}. {job.get('job_type', 'unknown')} - {job.get('created_at', 'unknown time')}")
    
    else:
        print("Invalid command or missing arguments")

if __name__ == "__main__":
    main()