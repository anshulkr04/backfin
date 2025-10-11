#!/usr/bin/env python3
"""
Event-Driven Worker Spawner
Monitors queues and spawns workers only when jobs are available
"""

import time
import sys
import logging
import subprocess
import signal
import os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import redis
import threading

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.queue.redis_client import RedisConfig, QueueNames

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("worker_spawner")

class WorkerSpawner:
    """Event-driven worker spawner"""
    
    def __init__(self):
        self.redis_config = RedisConfig()
        self.redis_client = None
        self.active_workers = {}  # worker_type -> (process, start_time)
        self.worker_configs = {
            QueueNames.AI_PROCESSING: {
                'script': 'workers/ephemeral_ai_worker.py',
                'max_runtime': 300,  # 5 minutes max
                'cooldown': 10       # 10 seconds between spawns
            },
            QueueNames.SUPABASE_UPLOAD: {
                'script': 'workers/ephemeral_supabase_worker.py', 
                'max_runtime': 180,  # 3 minutes max
                'cooldown': 5
            },
            QueueNames.INVESTOR_PROCESSING: {
                'script': 'workers/ephemeral_investor_worker.py',
                'max_runtime': 240,  # 4 minutes max
                'cooldown': 15
            }
        }
        self.last_spawn_time = {}
        self.running = True
        
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
            logger.info("✅ Connected to Redis")
            return True
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            return False
    
    def check_queue_status(self) -> Dict[str, int]:
        """Check status of all monitored queues"""
        queue_status = {}
        for queue_name in self.worker_configs.keys():
            try:
                length = self.redis_client.llen(queue_name)
                queue_status[queue_name] = length
            except Exception as e:
                logger.error(f"Error checking queue {queue_name}: {e}")
                queue_status[queue_name] = 0
        return queue_status
    
    def is_worker_running(self, queue_name: str) -> bool:
        """Check if worker for queue is already running"""
        if queue_name not in self.active_workers:
            return False
        
        process, start_time = self.active_workers[queue_name]
        
        # Check if process is still alive
        if process.poll() is not None:
            # Process finished
            logger.info(f"🏁 Worker for {queue_name} finished")
            del self.active_workers[queue_name]
            return False
        
        # Check if worker has been running too long
        max_runtime = self.worker_configs[queue_name]['max_runtime']
        if (datetime.now() - start_time).total_seconds() > max_runtime:
            logger.warning(f"⚠️ Worker for {queue_name} exceeded max runtime, terminating")
            self.terminate_worker(queue_name)
            return False
        
        return True
    
    def can_spawn_worker(self, queue_name: str) -> bool:
        """Check if we can spawn a worker for this queue"""
        if self.is_worker_running(queue_name):
            return False
        
        # Check cooldown period
        if queue_name in self.last_spawn_time:
            cooldown = self.worker_configs[queue_name]['cooldown']
            time_since_last = (datetime.now() - self.last_spawn_time[queue_name]).total_seconds()
            if time_since_last < cooldown:
                return False
        
        return True
    
    def spawn_worker(self, queue_name: str) -> bool:
        """Spawn a worker for the specified queue"""
        if not self.can_spawn_worker(queue_name):
            return False
        
        config = self.worker_configs[queue_name]
        script_path = config['script']
        
        try:
            # Spawn worker process
            cmd = [sys.executable, script_path]
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=Path(__file__).parent.parent
            )
            
            # Track active worker
            self.active_workers[queue_name] = (process, datetime.now())
            self.last_spawn_time[queue_name] = datetime.now()
            
            queue_short = queue_name.split(':')[-1].upper()
            logger.info(f"🚀 Spawned worker for {queue_short} (PID: {process.pid})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to spawn worker for {queue_name}: {e}")
            return False
    
    def terminate_worker(self, queue_name: str):
        """Terminate worker for specified queue"""
        if queue_name in self.active_workers:
            process, start_time = self.active_workers[queue_name]
            try:
                process.terminate()
                process.wait(timeout=5)
                logger.info(f"🛑 Terminated worker for {queue_name}")
            except subprocess.TimeoutExpired:
                process.kill()
                logger.warning(f"🔪 Killed worker for {queue_name}")
            except Exception as e:
                logger.error(f"❌ Error terminating worker: {e}")
            finally:
                del self.active_workers[queue_name]
    
    def cleanup_workers(self):
        """Cleanup all active workers"""
        logger.info("🧹 Cleaning up all workers...")
        for queue_name in list(self.active_workers.keys()):
            self.terminate_worker(queue_name)
    
    def monitor_and_spawn(self):
        """Main monitoring loop"""
        logger.info("👀 Starting queue monitoring and worker spawning...")
        
        while self.running:
            try:
                # Check queue status
                queue_status = self.check_queue_status()
                
                # Clean up finished workers
                for queue_name in list(self.active_workers.keys()):
                    self.is_worker_running(queue_name)
                
                # Spawn workers for queues with jobs
                for queue_name, job_count in queue_status.items():
                    if job_count > 0 and not self.is_worker_running(queue_name):
                        if self.spawn_worker(queue_name):
                            queue_short = queue_name.split(':')[-1].upper()
                            logger.info(f"📤 {queue_short}: {job_count} jobs -> worker spawned")
                
                # Log current status
                active_count = len(self.active_workers)
                total_jobs = sum(queue_status.values())
                
                if active_count > 0 or total_jobs > 0:
                    logger.info(f"📊 Active workers: {active_count}, Total jobs: {total_jobs}")
                
                # Wait before next check
                time.sleep(5)
                
            except KeyboardInterrupt:
                logger.info("🛑 Received interrupt signal")
                self.running = False
                break
            except Exception as e:
                logger.error(f"❌ Monitor error: {e}")
                time.sleep(5)
    
    def run(self):
        """Run the worker spawner"""
        logger.info("🎯 EPHEMERAL WORKER SPAWNER STARTING")
        logger.info("=" * 60)
        
        if not self.setup_redis():
            return False
        
        # Setup signal handlers
        def signal_handler(signum, frame):
            logger.info(f"🛑 Received signal {signum}")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            self.monitor_and_spawn()
        finally:
            self.cleanup_workers()
            logger.info("🏁 Worker spawner stopped")
        
        return True

def main():
    """Main function"""
    spawner = WorkerSpawner()
    spawner.run()

if __name__ == "__main__":
    main()