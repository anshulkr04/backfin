#!/usr/bin/env python3
"""
Event-Driven Worker Spawner (updated)
- Redirects worker stdout/stderr to per-worker log files to avoid PIPE blocking
- Increased SUPABASE_UPLOAD max_runtime to accommodate worker internals
"""

import time
import sys
import logging
import subprocess
import signal
import os
from pathlib import Path
from typing import Dict
from datetime import datetime
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
        # active_workers: queue_name -> list of tuples:
        # (process, start_time, worker_id, stdout_log_path, stderr_log_path, stdout_handle, stderr_handle)
        self.active_workers = {}
        self.worker_configs = {
            QueueNames.AI_PROCESSING: {
                'script': 'workers/ephemeral_ai_worker.py',
                'max_runtime': 300,
                'cooldown': 10,
                'max_concurrent': 3
            },
            QueueNames.SUPABASE_UPLOAD: {
                # point to hardened worker file
                'script': 'workers/ephemeral_supabase_worker.py',
                # increased max_runtime to allow JOB_TIMEOUT + cleanup margin
                'max_runtime': 120,
                'cooldown': 5,
                'max_concurrent': 2
            },
            QueueNames.INVESTOR_PROCESSING: {
                'script': 'workers/ephemeral_investor_worker.py',
                'max_runtime': 240,
                'cooldown': 15,
                'max_concurrent': 1
            },
            'delayed_queue_processor': {
                'script': 'workers/delayed_queue_processor.py',
                'max_runtime': 3600,
                'cooldown': 60,
                'max_concurrent': 1
            }
        }
        self.last_spawn_time = {}
        self.running = True
        # ensure logs dir exists
        self.log_dir = Path(__file__).parent.parent / "worker_logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def setup_redis(self):
        try:
            self.redis_client = self.redis_config.get_connection()
            logger.info("✅ Redis connection established")
            return True
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            return False

    def check_queue_status(self) -> Dict[str, int]:
        queue_status = {}
        for queue_name in self.worker_configs.keys():
            try:
                length = self.redis_client.llen(queue_name)
                queue_status[queue_name] = length
            except Exception as e:
                logger.error(f"Error checking queue {queue_name}: {e}")
                queue_status[queue_name] = 0
        return queue_status

    def _close_logs_and_tail_err(self, stdout_handle, stderr_handle, stdout_path, stderr_path, tail_lines=50):
        """Flush/close handles and return last stderr lines for logging"""
        try:
            if stdout_handle:
                try:
                    stdout_handle.flush()
                except Exception:
                    pass
                try:
                    stdout_handle.close()
                except Exception:
                    pass
            if stderr_handle:
                try:
                    stderr_handle.flush()
                except Exception:
                    pass
                try:
                    stderr_handle.close()
                except Exception:
                    pass
            # Tail last lines from stderr_path
            if stderr_path and stderr_path.exists():
                try:
                    with open(stderr_path, "rb") as f:
                        f.seek(0, os.SEEK_END)
                        size = f.tell()
                        block_size = 1024
                        data = b""
                        while size > 0 and tail_lines > 0:
                            read_size = min(block_size, size)
                            f.seek(size - read_size, os.SEEK_SET)
                            chunk = f.read(read_size)
                            data = chunk + data
                            size -= read_size
                            # crude line count
                            tail_lines = 50 - data.count(b"\n")
                        return data.decode("utf-8", errors="replace").splitlines()[-50:]
                except Exception:
                    return []
        except Exception:
            return []
        return []

    def is_worker_running(self, queue_name: str) -> bool:
        if queue_name not in self.active_workers:
            return False

        alive_workers = []
        max_runtime = self.worker_configs[queue_name]['max_runtime']

        for worker_data in self.active_workers[queue_name]:
            # unpack
            process, start_time, worker_id, stdout_path, stderr_path, stdout_handle, stderr_handle = worker_data

            # check if process finished
            if process.poll() is not None:
                exitcode = process.returncode
                logger.info(f"🏁 Worker {worker_id} for {queue_name} finished with exitcode={exitcode}")

                # close log handles and tail stderr for context
                tail_err = self._close_logs_and_tail_err(stdout_handle, stderr_handle, stdout_path, stderr_path)
                if tail_err:
                    for line in tail_err[-20:]:
                        logger.info(f"[{worker_id}] STDERR: {line}")
                continue

            # check runtime
            runtime = (datetime.now() - start_time).total_seconds()
            if runtime > max_runtime:
                logger.warning(f"⚠️ Worker {worker_id} for {queue_name} exceeded max runtime ({int(runtime)}s), terminating")
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                except Exception as e:
                    logger.error(f"❌ Error terminating worker {worker_id}: {e}")
                # close logs & tail
                self._close_logs_and_tail_err(stdout_handle, stderr_handle, stdout_path, stderr_path)
                continue

            alive_workers.append(worker_data)

        if alive_workers:
            self.active_workers[queue_name] = alive_workers
            return True
        else:
            # remove key safely
            try:
                del self.active_workers[queue_name]
            except KeyError:
                pass
            return False

    def get_active_worker_count(self, queue_name: str) -> int:
        if queue_name not in self.active_workers:
            return 0
        self.is_worker_running(queue_name)
        return len(self.active_workers.get(queue_name, []))

    def can_spawn_worker(self, queue_name: str) -> bool:
        max_concurrent = self.worker_configs[queue_name]['max_concurrent']
        current_count = self.get_active_worker_count(queue_name)

        if current_count >= max_concurrent:
            return False

        if queue_name in self.last_spawn_time:
            cooldown = self.worker_configs[queue_name]['cooldown']
            time_since_last = (datetime.now() - self.last_spawn_time[queue_name]).total_seconds()
            if time_since_last < cooldown:
                return False
        return True

    def spawn_worker(self, queue_name: str) -> bool:
        if not self.can_spawn_worker(queue_name):
            return False

        config = self.worker_configs[queue_name]
        script_path = config['script']

        try:
            worker_id = f"{queue_name.split(':')[-1]}_{int(datetime.now().timestamp())}"

            # Prepare log files for this worker
            stdout_log_path = self.log_dir / f"{worker_id}.out.log"
            stderr_log_path = self.log_dir / f"{worker_id}.err.log"
            stdout_handle = open(stdout_log_path, "a", encoding="utf-8")
            stderr_handle = open(stderr_log_path, "a", encoding="utf-8")

            cmd = [sys.executable, script_path]
            process = subprocess.Popen(
                cmd,
                stdout=stdout_handle,
                stderr=stderr_handle,
                text=True,
                cwd=Path(__file__).parent.parent
            )

            if queue_name not in self.active_workers:
                self.active_workers[queue_name] = []

            self.active_workers[queue_name].append(
                (process, datetime.now(), worker_id, stdout_log_path, stderr_log_path, stdout_handle, stderr_handle)
            )
            self.last_spawn_time[queue_name] = datetime.now()

            queue_short = queue_name.split(':')[-1].upper()
            worker_count = len(self.active_workers[queue_name])
            logger.info(f"🚀 Spawned worker {worker_id} for {queue_short} (PID: {process.pid}, Total: {worker_count})")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to spawn worker for {queue_name}: {e}")
            return False

    def terminate_worker(self, queue_name: str, worker_id: str = None):
        if queue_name not in self.active_workers:
            return

        if worker_id:
            workers = self.active_workers[queue_name]
            for i, (process, start_time, w_id, stdout_path, stderr_path, stdout_handle, stderr_handle) in enumerate(workers):
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
                        # Close logs
                        self._close_logs_and_tail_err(stdout_handle, stderr_handle, stdout_path, stderr_path)
                        workers.pop(i)
                        if not workers:
                            del self.active_workers[queue_name]
                    break
        else:
            workers = self.active_workers[queue_name][:]
            for process, start_time, w_id, stdout_path, stderr_path, stdout_handle, stderr_handle in workers:
                try:
                    process.terminate()
                    process.wait(timeout=5)
                    logger.info(f"🛑 Terminated worker {w_id} for {queue_name}")
                except subprocess.TimeoutExpired:
                    process.kill()
                    logger.warning(f"🔪 Killed worker {w_id} for {queue_name}")
                except Exception as e:
                    logger.error(f"❌ Error terminating worker {w_id}: {e}")
                finally:
                    self._close_logs_and_tail_err(stdout_handle, stderr_handle, stdout_path, stderr_path)
            try:
                del self.active_workers[queue_name]
            except KeyError:
                pass

    def cleanup_workers(self):
        logger.info("🧹 Cleaning up all workers...")
        for queue_name in list(self.active_workers.keys()):
            self.terminate_worker(queue_name)

    def monitor_and_spawn(self):
        logger.info("👀 Starting queue monitoring and worker spawning...")
        while self.running:
            try:
                queue_status = self.check_queue_status()
                # Clean up finished workers
                for queue_name in list(self.active_workers.keys()):
                    self.is_worker_running(queue_name)

                for queue_name, job_count in queue_status.items():
                    if job_count > 0:
                        current_workers = self.get_active_worker_count(queue_name)
                        max_workers = self.worker_configs[queue_name]['max_concurrent']
                        workers_needed = min(job_count, max_workers) - current_workers
                        if workers_needed > 0:
                            for _ in range(workers_needed):
                                if self.spawn_worker(queue_name):
                                    queue_short = queue_name.split(':')[-1].upper()
                                    current_after = self.get_active_worker_count(queue_name)
                                    logger.info(f"📤 {queue_short}: {job_count} jobs -> worker spawned ({current_after}/{max_workers})")
                                else:
                                    break

                # Ensure delayed queue processor runs
                if self.get_active_worker_count('delayed_queue_processor') == 0:
                    if self.spawn_worker('delayed_queue_processor'):
                        logger.info("🕒 Spawned delayed queue processor")

                # Status logging
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

                time.sleep(5)
            except KeyboardInterrupt:
                logger.info("🛑 Received interrupt signal")
                self.running = False
                break
            except Exception as e:
                logger.error(f"❌ Monitor error: {e}")
                time.sleep(5)

    def run(self):
        logger.info("🎯 EPHEMERAL WORKER SPAWNER STARTING")
        logger.info("=" * 60)

        if not self.setup_redis():
            return False

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
    spawner = WorkerSpawner()
    spawner.run()

if __name__ == "__main__":
    main()
