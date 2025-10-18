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
        self.active_workers = {}  # worker_type -> list of (process, start_time, worker_id)
        self.worker_configs = {
            QueueNames.AI_PROCESSING: {
                'script': 'workers/ephemeral_ai_worker.py',
                'max_runtime': 300,  # 5 minutes max
                'cooldown': 10,      # 10 seconds between spawns
                'max_concurrent': 3  # Allow up to 3 AI workers simultaneously
            },
            QueueNames.SUPABASE_UPLOAD: {
                'script': 'workers/ephemeral_supabase_worker.py', 
                'max_runtime': 180,  # 3 minutes max
                'cooldown': 5,
                'max_concurrent': 2  # Allow up to 2 upload workers
            },
            QueueNames.INVESTOR_PROCESSING: {
                'script': 'workers/ephemeral_investor_worker.py',
                'max_runtime': 240,  # 4 minutes max
                'cooldown': 15,
                'max_concurrent': 1  # Single investor worker is fine
            },
            'delayed_queue_processor': {
                'script': 'workers/delayed_queue_processor.py',
                'max_runtime': 3600,  # 1 hour max (long-running service)
                'cooldown': 60,       # 1 minute between spawns
                'max_concurrent': 1   # Only one delayed processor needed
            }
        }
        self.last_spawn_time = {}
        self.running = True
        
    def setup_redis(self):
        """Setup Redis connection"""
        try:
            self.redis_client = self.redis_config.get_connection()
            logger.info("✅ Redis connection established")
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
        """Check if any worker for queue is running"""
        if queue_name not in self.active_workers:
            return False
        
        # Clean up dead workers
        alive_workers = []
        max_runtime = self.worker_configs[queue_name]['max_runtime']
        
        for worker_data in self.active_workers[queue_name]:
            process, start_time, worker_id = worker_data
            
            # Check if process is still alive
            if process.poll() is not None:
                logger.info(f"🏁 Worker {worker_id} for {queue_name} finished")
                continue
            
            # Check if worker has been running too long
            if (datetime.now() - start_time).total_seconds() > max_runtime:
                logger.warning(f"⚠️ Worker {worker_id} for {queue_name} exceeded max runtime, terminating")
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                except Exception as e:
                    logger.error(f"❌ Error terminating worker {worker_id}: {e}")
                continue
            
            alive_workers.append(worker_data)
        
        # Update active workers list
        if alive_workers:
            self.active_workers[queue_name] = alive_workers
            return True
        else:
            del self.active_workers[queue_name]
            return False
    
    def get_active_worker_count(self, queue_name: str) -> int:
        """Get number of active workers for a queue"""
        if queue_name not in self.active_workers:
            return 0
        
        # Clean up dead workers first
        self.is_worker_running(queue_name)
        
        return len(self.active_workers.get(queue_name, []))
    
    def can_spawn_worker(self, queue_name: str) -> bool:
        """Check if we can spawn a worker for this queue"""
        # Check if we've reached max concurrent workers
        max_concurrent = self.worker_configs[queue_name]['max_concurrent']
        current_count = self.get_active_worker_count(queue_name)
        
        if current_count >= max_concurrent:
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
            # Generate unique worker ID
            worker_id = f"{queue_name.split(':')[-1]}_{int(datetime.now().timestamp())}"
            
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
            if queue_name not in self.active_workers:
                self.active_workers[queue_name] = []
            
            self.active_workers[queue_name].append((process, datetime.now(), worker_id))
            self.last_spawn_time[queue_name] = datetime.now()
            
            queue_short = queue_name.split(':')[-1].upper()
            worker_count = len(self.active_workers[queue_name])
            logger.info(f"🚀 Spawned worker {worker_id} for {queue_short} (PID: {process.pid}, Total: {worker_count})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to spawn worker for {queue_name}: {e}")
            return False
    
    def terminate_worker(self, queue_name: str, worker_id: str = None):
        """Terminate worker(s) for specified queue"""
        if queue_name not in self.active_workers:
            return
        
        if worker_id:
            # Terminate specific worker
            workers = self.active_workers[queue_name]
            for i, (process, start_time, w_id) in enumerate(workers):
                if w_id == worker_id:
                    try:
                        process.terminate()
                        process.wait(timeout=5)
                        logger.info(f"🛑 Terminated worker {worker_id} for {queue_name}")
                    except subprocess.TimeoutExpired:
                        process.kill()
                        logger.warning(f"🔪 Killed worker {worker_id} for {queue_name}")
                    except Exception as e:
                        logger.error(f"❌ Error terminating worker {worker_id}: {e}")
                    finally:
                        workers.pop(i)
                        if not workers:
                            del self.active_workers[queue_name]
                    break
        else:
            # Terminate all workers for this queue
            workers = self.active_workers[queue_name][:]
            for process, start_time, w_id in workers:
                try:
                    process.terminate()
                    process.wait(timeout=5)
                    logger.info(f"🛑 Terminated worker {w_id} for {queue_name}")
                except subprocess.TimeoutExpired:
                    process.kill()
                    logger.warning(f"🔪 Killed worker {w_id} for {queue_name}")
                except Exception as e:
                    logger.error(f"❌ Error terminating worker {w_id}: {e}")
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
                    if job_count > 0:
                        current_workers = self.get_active_worker_count(queue_name)
                        max_workers = self.worker_configs[queue_name]['max_concurrent']
                        
                        # Spawn workers up to max concurrent or until we have enough workers for jobs
                        workers_needed = min(job_count, max_workers) - current_workers
                        
                        if workers_needed > 0:
                            for _ in range(workers_needed):
                                if self.spawn_worker(queue_name):
                                    queue_short = queue_name.split(':')[-1].upper()
                                    current_after = self.get_active_worker_count(queue_name)
                                    logger.info(f"📤 {queue_short}: {job_count} jobs -> worker spawned ({current_after}/{max_workers})")
                                else:
                                    break  # Failed to spawn, likely due to cooldown
                
                # Ensure delayed queue processor is always running
                if self.get_active_worker_count('delayed_queue_processor') == 0:
                    if self.spawn_worker('delayed_queue_processor'):
                        logger.info("🕒 Spawned delayed queue processor")
                
                # Log current status with detailed worker counts
                total_workers = sum(len(workers) for workers in self.active_workers.values())
                total_jobs = sum(queue_status.values())
                
                if total_workers > 0 or total_jobs > 0:
                    status_parts = []
                    for queue_name in self.worker_configs.keys():
                        worker_count = self.get_active_worker_count(queue_name)
                        max_count = self.worker_configs[queue_name]['max_concurrent']
                        job_count = queue_status.get(queue_name, 0)
                        queue_short = queue_name.split(':')[-1].upper()
                        
                        if worker_count > 0 or job_count > 0:
                            status_parts.append(f"{queue_short}: {worker_count}/{max_count} workers, {job_count} jobs")
                    
                    if status_parts:
                        logger.info(f"📊 {' | '.join(status_parts)}")
                
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