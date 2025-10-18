#!/usr/bin/env python3
"""
Delayed Queue Processor - Moves ready delayed jobs back to immediate processing queues
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
from src.queue.job_types import deserialize_job

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("delayed_queue_processor")

class DelayedQueueProcessor:
    """Processes delayed jobs and moves them back to immediate queues when ready"""
    
    def __init__(self):
        self.redis_config = RedisConfig()
        self.redis_client = None
        self.running = True
        self.check_interval = 30  # Check every 30 seconds
        
        # Gap management configuration (can be overridden by environment variables)
        self.min_gap_between_delayed_jobs = int(os.getenv('DELAYED_JOB_GAP_SECONDS', '120'))  # Default 2 minutes
        self.max_delayed_jobs_per_cycle = int(os.getenv('MAX_DELAYED_JOBS_PER_CYCLE', '3'))  # Default 3 jobs
        
        # Adaptive gap management - faster processing when queues are empty
        self.rapid_gap_when_empty = int(os.getenv('RAPID_GAP_WHEN_EMPTY_SECONDS', '30'))  # 30 seconds when queues empty
        self.rapid_max_jobs_when_empty = int(os.getenv('RAPID_MAX_JOBS_WHEN_EMPTY', '5'))  # More jobs when queues empty
        
        self.last_delayed_job_release_time = {}  # Track last release time per queue
        
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
    
    def are_main_queues_empty(self) -> bool:
        """Check if all main processing queues are empty"""
        try:
            main_queues = [QueueNames.AI_PROCESSING, QueueNames.SUPABASE_UPLOAD, QueueNames.INVESTOR_PROCESSING]
            
            for queue_name in main_queues:
                queue_length = self.redis_client.llen(queue_name)
                if queue_length > 0:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking main queue status: {e}")
            return False  # Assume not empty on error to be conservative
    
    def get_adaptive_gap_settings(self, queue_name: str) -> tuple[int, int]:
        """Get adaptive gap settings based on main queue status"""
        main_queues_empty = self.are_main_queues_empty()
        
        if main_queues_empty:
            # Rapid processing when no real-time work
            gap = self.rapid_gap_when_empty
            max_jobs = self.rapid_max_jobs_when_empty
            mode = "RAPID"
        else:
            # Normal conservative processing when there's real-time work
            gap = self.min_gap_between_delayed_jobs
            max_jobs = self.max_delayed_jobs_per_cycle
            mode = "NORMAL"
        
        return gap, max_jobs, mode
    
    def process_delayed_queue(self, queue_name: str) -> int:
        """Process delayed jobs for a specific queue with adaptive gap management"""
        try:
            delayed_queue_name = f"{queue_name}:delayed"
            current_time = time.time()
            
            # Get adaptive gap settings based on main queue status
            adaptive_gap, max_jobs, processing_mode = self.get_adaptive_gap_settings(queue_name)
            
            # Check if enough time has passed since last delayed job release for this queue
            last_release = self.last_delayed_job_release_time.get(queue_name, 0)
            time_since_last_release = current_time - last_release
            
            if time_since_last_release < adaptive_gap:
                remaining_wait = adaptive_gap - time_since_last_release
                logger.debug(f"⏳ Delayed queue {queue_name.split(':')[-1].upper()} ({processing_mode}): waiting {remaining_wait:.1f}s before next release")
                return 0
            
            # Get jobs that are ready (score <= current time)
            ready_jobs = self.redis_client.zrangebyscore(
                delayed_queue_name, 
                0, 
                current_time, 
                withscores=True, 
                start=0, 
                num=max_jobs  # Use adaptive max jobs
            )
            
            if not ready_jobs:
                return 0
            
            moved_count = 0
            jobs_to_release = min(len(ready_jobs), max_jobs)
            
            logger.info(f"🕒 Releasing {jobs_to_release} delayed jobs from {queue_name.split(':')[-1].upper()} queue ({processing_mode} mode - gap: {time_since_last_release/60:.1f} min)")
            
            for i, (job_data, score) in enumerate(ready_jobs[:jobs_to_release]):
                try:
                    # Remove from delayed queue first
                    removed = self.redis_client.zrem(delayed_queue_name, job_data)
                    
                    if removed:
                        # Add back to immediate processing queue with adaptive staggering
                        # In rapid mode, use shorter stagger (15s), in normal mode use 30s
                        stagger_interval = 15 if processing_mode == "RAPID" else 30
                        stagger_delay = i * stagger_interval
                        
                        if stagger_delay > 0:
                            # Re-add to delayed queue with short stagger delay
                            stagger_timestamp = current_time + stagger_delay
                            self.redis_client.zadd(delayed_queue_name, {job_data: stagger_timestamp})
                            logger.debug(f"⏱️ Staggered job {i+1} by {stagger_delay}s ({processing_mode} mode)")
                        else:
                            # Release immediately
                            self.redis_client.lpush(queue_name, job_data)
                            moved_count += 1
                            
                            # Log job details if possible
                            try:
                                job = deserialize_job(job_data)
                                delay_minutes = (current_time - score + 300) / 60  # Approximate original delay
                                logger.info(f"🔄 Released delayed job {getattr(job, 'corp_id', 'unknown')} to {queue_name.split(':')[-1].upper()} queue ({processing_mode} - delayed {delay_minutes:.1f} min)")
                            except:
                                logger.info(f"🔄 Released delayed job to {queue_name.split(':')[-1].upper()} queue ({processing_mode} mode)")
                        
                except Exception as e:
                    logger.error(f"Error processing delayed job: {e}")
                    # Job will remain in delayed queue for next check
            
            # Update last release time only if we actually released jobs
            if moved_count > 0:
                self.last_delayed_job_release_time[queue_name] = current_time
                    
            return moved_count
            
        except Exception as e:
            logger.error(f"Error processing delayed queue {queue_name}: {e}")
            return 0
    
    def get_delayed_queue_stats(self) -> dict:
        """Get comprehensive statistics for delayed queues"""
        stats = {
            "timestamp": time.time(),
            "uptime_seconds": time.time() - self.start_time,
            "total_processed": self.total_processed,
            "processing_rate_per_hour": (self.total_processed / max((time.time() - self.start_time) / 3600, 0.001)),
            "queues": {}
        }
        
        for queue_name in self.queue_names:
            delayed_queue_name = f"{queue_name}:delayed"
            
            # Get delayed queue size
            delayed_count = self.redis_client.zcard(delayed_queue_name)
            
            # Get main queue status and adaptive settings
            main_queue_empty = self.redis_client.llen(queue_name) == 0
            adaptive_gap, max_jobs, processing_mode = self.get_adaptive_gap_settings(queue_name)
            
            # Check ready jobs
            current_time = time.time()
            ready_count = self.redis_client.zcount(delayed_queue_name, 0, current_time)
            
            # Get next release time
            last_release = self.last_delayed_job_release_time.get(queue_name, 0)
            next_release_in = max(0, (last_release + adaptive_gap) - current_time)
            
            # Get oldest job timestamp
            oldest_job = self.redis_client.zrange(delayed_queue_name, 0, 0, withscores=True)
            oldest_timestamp = oldest_job[0][1] if oldest_job else None
            
            queue_stats = {
                "delayed_jobs": delayed_count,
                "ready_to_process": ready_count,
                "next_release_in_seconds": round(next_release_in, 1),
                "processing_mode": processing_mode,
                "adaptive_gap_seconds": adaptive_gap,
                "adaptive_max_jobs": max_jobs,
                "main_queue_empty": main_queue_empty,
                "last_release_ago_seconds": round(current_time - last_release, 1) if last_release > 0 else None,
                "oldest_job_age_minutes": round((current_time - oldest_timestamp) / 60, 1) if oldest_timestamp else None
            }
            
            stats["queues"][queue_name.split(':')[-1].upper()] = queue_stats
        
        return stats
    
    def run(self):
        """Main processing loop with adaptive gap management"""
        logger.info("🕒 Starting Delayed Queue Processor")
        
        if not self.setup_redis():
            logger.error("Failed to setup Redis connection")
            return False
        
        logger.info(f"✅ Connected to Redis, processing {len(self.queue_names)} delayed queues")
        logger.info(f"⚙️ Config: normal_gap={self.min_gap_between_delayed_jobs}s, rapid_gap={self.rapid_gap_when_empty}s")
        logger.info(f"📊 Check interval: {self.check_interval}s")
        
        next_stats_time = time.time() + 300  # Show stats every 5 minutes
        
        try:
            while self.running:
                start_time = time.time()
                total_moved = 0
                
                # Process delayed jobs for all configured queues
                for queue_name in self.queue_names:
                    moved = self.process_delayed_queue(queue_name)
                    total_moved += moved
                
                self.total_processed += total_moved
                
                # Log comprehensive statistics periodically
                if time.time() >= next_stats_time or total_moved > 0:
                    stats = self.get_delayed_queue_stats()
                    uptime_hours = stats["uptime_seconds"] / 3600
                    
                    # Show processing modes for each queue
                    mode_summary = []
                    queue_details = []
                    
                    for queue_short, queue_stats in stats["queues"].items():
                        mode = queue_stats["processing_mode"]
                        delayed_count = queue_stats["delayed_jobs"]
                        ready_count = queue_stats["ready_to_process"]
                        next_in = queue_stats["next_release_in_seconds"]
                        
                        mode_summary.append(f"{queue_short}:{mode}({delayed_count})")
                        
                        if delayed_count > 0:
                            queue_details.append(f"   {queue_short}: {delayed_count} delayed, {ready_count} ready, next in {next_in}s ({mode} mode)")
                    
                    logger.info(f"📊 Processed {stats['total_processed']} jobs | Rate: {stats['processing_rate_per_hour']:.1f}/hr | Uptime: {uptime_hours:.1f}h")
                    logger.info(f"🎯 Queue modes: {', '.join(mode_summary)}")
                    
                    # Show detailed queue status if there are delayed jobs
                    for detail in queue_details:
                        logger.info(detail)
                    
                    if total_moved > 0:
                        logger.info(f"🔄 Released {total_moved} jobs this cycle")
                    
                    next_stats_time = time.time() + 300  # Next stats in 5 minutes
                
                # Sleep for remainder of check interval
                elapsed = time.time() - start_time
                sleep_time = max(0, self.check_interval - elapsed)
                time.sleep(sleep_time)
                
        except KeyboardInterrupt:
            logger.info("🛑 Delayed Queue Processor interrupted")
            self.running = False
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
        finally:
            logger.info("🏁 Delayed Queue Processor finished")
        
        return True

def main():
    """Main function"""
    processor = DelayedQueueProcessor()
    processor.run()

if __name__ == "__main__":
    main()