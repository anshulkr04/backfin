#!/usr/bin/env python3
"""
Robust Ephemeral Supabase Worker
- Uses BRPOPLPUSH -> processing:<worker_id> (atomic move)
- Runs each job in a child process with a hard timeout so the main process never blocks
- Keeps processing metadata (Redis hash) so a sweeper can requeue stuck jobs
- Retries failed jobs up to MAX_RETRIES then moves them to a dead-letter queue
- Logs durations and exceptions
"""

import os
import sys
import time
import json
import logging
import signal
import threading
from datetime import datetime, timezone
from pathlib import Path
from multiprocessing import Process
from typing import Optional

import redis

# Keep your project imports (assumes same paths as your original worker)
sys.path.append(str(Path(__file__).parent.parent))
from src.queue.redis_client import RedisConfig, QueueNames
from src.queue.job_types import deserialize_job, SupabaseUploadJob, InvestorAnalysisJob, serialize_job

# Constants (tune these)
MAIN_QUEUE = QueueNames.SUPABASE_UPLOAD  # 'backfin:queue:supabase_upload'
PROCESSING_LIST_PREFIX = "processing:"   # final list name -> processing:<worker_id>
PROCESSING_META_HASH = "processing_meta"  # hash job_id -> moved_at (epoch seconds)
PROCESSING_PAYLOAD_HASH = "processing_payload"  # hash job_id -> job_json
JOB_RETRIES_HASH = "processing_retries"  # hash job_id -> int
FAILED_QUEUE = QueueNames.FAILED_JOBS
INVESTOR_QUEUE = QueueNames.INVESTOR_PROCESSING

BRPOP_TIMEOUT = 3            # seconds to block waiting for job (brpoplpush equivalent uses timeout)
JOB_TIMEOUT = 60             # per-job hard timeout in seconds (child process join timeout)
PROCESSING_TTL = 90          # if job stuck in processing longer than this (seconds) -> requeue
REQUEUE_SWEEPER_INTERVAL = 30  # seconds between sweeper runs
MAX_RETRIES = 3              # number of attempts before sending to failed queue
REDIS_SOCKET_CONNECT_TIMEOUT = 3
REDIS_SOCKET_TIMEOUT = 30
HEARTBEAT_INTERVAL = 30      # log heartbeat every N seconds

# Setup logging
worker_id = f"ephemeral_supabase_{os.getpid()}"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(worker_id)


class EphemeralSupabaseWorkerV2:
    def __init__(self):
        self.worker_id = worker_id
        self.redis_config = RedisConfig()
        self.redis_client: Optional[redis.Redis] = None
        self.jobs_processed = 0
        self.max_jobs_per_session = 1000  # you can keep high; ephemeral nature controlled by external spawner if any
        self.processing_list = f"{PROCESSING_LIST_PREFIX}{self.worker_id}"
        self._stop_event = threading.Event()
        self._last_heartbeat = time.time()

        # signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        # sweeper thread will requeue stuck processing items
        self.sweeper_thread = threading.Thread(target=self._processing_requeue_sweeper, daemon=True)

    def _signal_handler(self, signum, frame):
        logger.warning(f"🛑 Received signal {signum}, shutting down gracefully...")
        self._stop_event.set()

    def setup_redis(self) -> bool:
        try:
            # Build redis connection with timeouts and decoding
            # RedisConfig.get_connection() may not set these, so create here explicitly
            # If RedisConfig returns a client we can use it; otherwise build one directly
            try:
                client = self.redis_config.get_connection()
                # Attempt to ping to confirm it's alive
                client.ping()
                # attempt to set recommended timeouts if attributes exist (best-effort)
                # If get_connection doesn't set decode_responses, wrap a new client using same params
                if getattr(client, "connection_pool", None) and not getattr(client, "decode_responses", False):
                    # Best-effort: create a new redis.Redis with similar options if possible
                    # Fallback: keep the client returned
                    pass
                self.redis_client = client
            except Exception as e:
                # Fallback to create a new client with safe options if RedisConfig failed
                logger.warning(f"RedisConfig.get_connection() failed or returned unusable client: {e}. Creating local client.")
                self.redis_client = redis.Redis(
                    host=os.getenv("REDIS_HOST", "localhost"),
                    port=int(os.getenv("REDIS_PORT", 6379)),
                    db=int(os.getenv("REDIS_DB", 0)),
                    socket_connect_timeout=REDIS_SOCKET_CONNECT_TIMEOUT,
                    socket_timeout=REDIS_SOCKET_TIMEOUT,
                    decode_responses=True,
                )

            # Ensure decode_responses is True to avoid bytes handling
            if not getattr(self.redis_client, "decode_responses", False):
                # Create a new client using same connection pool info if possible
                # If not possible, just re-create using environment variables
                self.redis_client = redis.Redis(
                    host=os.getenv("REDIS_HOST", "localhost"),
                    port=int(os.getenv("REDIS_PORT", 6379)),
                    db=int(os.getenv("REDIS_DB", 0)),
                    socket_connect_timeout=REDIS_SOCKET_CONNECT_TIMEOUT,
                    socket_timeout=REDIS_SOCKET_TIMEOUT,
                    decode_responses=True,
                )

            logger.info("✅ Redis client initialized successfully (decode_responses=True)")
            return True
        except Exception as e:
            logger.exception(f"❌ Redis connection failed: {e}")
            return False

    def start_sweeper(self):
        if not self.sweeper_thread.is_alive():
            self.sweeper_thread = threading.Thread(target=self._processing_requeue_sweeper, daemon=True)
            self.sweeper_thread.start()
            logger.info("🧭 Requeue sweeper started")

    def _processing_requeue_sweeper(self):
        """Periodically requeue stuck jobs from processing lists using processing_meta timestamps."""
        logger.debug("Requeue sweeper running")
        while not self._stop_event.is_set():
            try:
                now = time.time()
                # Get all processing metadata
                meta = self.redis_client.hgetall(PROCESSING_META_HASH) or {}
                for job_id, ts in meta.items():
                    try:
                        moved_at = float(ts)
                    except Exception:
                        # If parsing fails, immediately consider requeueing (defensive)
                        moved_at = 0.0
                    age = now - moved_at
                    if age > PROCESSING_TTL:
                        # Stuck job: get payload
                        job_json = self.redis_client.hget(PROCESSING_PAYLOAD_HASH, job_id)
                        if not job_json:
                            # If we don't have payload mapping, we can try to scan the processing list to find item
                            logger.warning(f"Stuck job {job_id} has no payload mapping; skipping for now")
                            # remove stale meta to avoid churn
                            self.redis_client.hdel(PROCESSING_META_HASH, job_id)
                            self.redis_client.hdel(PROCESSING_PAYLOAD_HASH, job_id)
                            continue

                        logger.warning(f"🔁 Requeuing stuck job {job_id} (age={int(age)}s)")
                        # Remove one occurrence from any processing lists (best-effort): use LREM on processing:<worker> lists.
                        # We don't maintain a list of worker processing lists; instead we try to remove from the global processing list for this worker.
                        # Best-effort: attempt to remove from the named processing list of this worker; if not present, push back to main queue anyway.
                        try:
                            # Attempt to remove occurrences across any "processing:*" keys (expensive if many workers)
                            # We'll attempt a few likely keys:
                            probable_key = f"{PROCESSING_LIST_PREFIX}{self.worker_id}"
                            removed = self.redis_client.lrem(probable_key, 0, job_json)
                            if removed == 0:
                                # Try to remove from any processing:* lists by scanning keys (use with caution)
                                keys = self.redis_client.keys(f"{PROCESSING_LIST_PREFIX}*")
                                for k in keys:
                                    try:
                                        r = self.redis_client.lrem(k, 0, job_json)
                                        if r > 0:
                                            logger.debug(f"Removed stuck job {job_id} from {k}")
                                            break
                                    except Exception:
                                        continue

                            # Push back to main queue for retry (LPUSH so it is processed sooner)
                            self.redis_client.lpush(MAIN_QUEUE, job_json)
                            # cleanup meta & payload
                            self.redis_client.hdel(PROCESSING_META_HASH, job_id)
                            self.redis_client.hdel(PROCESSING_PAYLOAD_HASH, job_id)

                        except Exception as e:
                            logger.exception(f"Failed to requeue stuck job {job_id}: {e}")
                # Sleep until next sweep
                for _ in range(int(REQUEUE_SWEEPER_INTERVAL)):
                    if self._stop_event.is_set():
                        break
                    time.sleep(1)
            except Exception as e:
                logger.exception(f"Requeue sweeper error: {e}")
                time.sleep(5)

    def _child_process_job_runner(self, job_json: str):
        """Child process target: performs the job. This runs in a separate process."""
        # We do not want the child to inherit the parent's Redis connection or other sockets; imports and client creation here are local.
        try:
            # Local imports & client creation (safe within child)
            from supabase import create_client, Client
            import sqlite3

            # Reconstruct job object (use same deserialize_job)
            job = deserialize_job(job_json)
            if not isinstance(job, SupabaseUploadJob):
                logger.error(f"Child: unexpected job type: {type(job)}")
                # return non-zero to indicate failure
                sys.exit(2)

            # Create supabase client inside the child process (so sockets are not shared)
            supabase_url = os.getenv('SUPABASE_URL2')
            supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
            if not supabase_url or not supabase_key:
                logger.error("Child: Supabase credentials missing in environment")
                sys.exit(3)

            try:
                supabase: Client = create_client(supabase_url, supabase_key)
            except Exception as e:
                logger.exception(f"Child: Failed to create Supabase client: {e}")
                sys.exit(4)

            # Begin actual processing with local timing logs
            start_all = time.time()
            logger.info(f"Child: Starting Supabase upload for corp_id={job.corp_id} job_id={job.job_id}")

            processed_data = job.processed_data or {}
            if not processed_data:
                logger.error(f"Child: No processed_data for corp_id={job.corp_id}")
                sys.exit(5)

            category = processed_data.get('category', '')
            if category == "Error":
                logger.warning(f"Child: Skipping upload for corp_id {job.corp_id} due to category 'Error'")
                sys.exit(0)  # treat as success (nothing to do)

            # Prepare upload_data same as original worker
            fileurl = processed_data.get("fileurl")
            if not fileurl and processed_data.get("pdf_file"):
                fileurl = f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{processed_data.get('pdf_file')}"

            upload_data = {
                "corp_id": processed_data.get("corp_id"),
                "securityid": processed_data.get("securityid"),
                "summary": processed_data.get("original_summary", ""),
                "fileurl": fileurl,
                "date": processed_data.get("date"),
                "ai_summary": processed_data.get("summary"),
                "category": category,
                "isin": processed_data.get("isin"),
                "companyname": processed_data.get("companyname"),
                "symbol": processed_data.get("symbol"),
                "sentiment": processed_data.get("sentiment"),
                "headline": processed_data.get("headline"),
                "company_id": processed_data.get("company_id")
            }

            # For reliability, wrap Supabase operations in retries (child-level; will still be bounded by child timeout)
            def supabase_insert_table(table_name: str, payload: dict):
                attempts = 0
                while attempts < 3:
                    attempts += 1
                    try:
                        resp = supabase.table(table_name).insert(payload).execute()
                        # handle SDK-level error representation
                        if hasattr(resp, "error") and resp.error:
                            # duplicate key -> treat as success
                            errstr = str(resp.error)
                            if "duplicate key" in errstr.lower() or "23505" in errstr:
                                logger.warning(f"Child: Duplicate key on insert to {table_name} for {job.corp_id} (treated as success)")
                                return True
                            else:
                                logger.warning(f"Child: Supabase insert error (attempt {attempts}): {resp.error}")
                                # retry
                                time.sleep(0.3 * attempts)
                                continue
                        # else success
                        return True
                    except Exception as e:
                        logger.exception(f"Child: Supabase insert exception (attempt {attempts}): {e}")
                        time.sleep(0.3 * attempts)
                return False

            # Check existence first (try/except)
            try:
                check_resp = supabase.table("corporatefilings").select("corp_id").eq("corp_id", job.corp_id).execute()
                if getattr(check_resp, "data", None):
                    if len(check_resp.data) > 0:
                        logger.warning(f"Child: corp_id {job.corp_id} already exists in Supabase - skipping insert")
                    else:
                        ok = supabase_insert_table("corporatefilings", upload_data)
                        if not ok:
                            logger.error("Child: Failed to insert into corporatefilings after retries")
                            sys.exit(6)
                else:
                    # If check_resp.data empty or None, still attempt insert (defensive)
                    ok = supabase_insert_table("corporatefilings", upload_data)
                    if not ok:
                        logger.error("Child: Failed to insert into corporatefilings after retries")
                        sys.exit(7)
            except Exception as e:
                logger.exception(f"Child: Error during existence check/insert: {e}")
                # let the child exit with failure code
                sys.exit(8)

            # Mark local sqlite DB row as sent if newsid present
            newsid = processed_data.get('newsid')
            if newsid:
                try:
                    db_path = Path("/app/data") / "bse_raw.db"
                    conn = sqlite3.connect(str(db_path), timeout=15)
                    # Enable WAL for resilience (best-effort)
                    try:
                        conn.execute("PRAGMA journal_mode=WAL;")
                    except Exception:
                        pass
                    cur = conn.cursor()
                    cur.execute(
                        "UPDATE announcements SET sent_to_supabase = 1, sent_to_supabase_at = datetime('now') WHERE newsid = ?",
                        (str(newsid),)
                    )
                    conn.commit()
                    conn.close()
                    logger.info(f"Child: Marked NEWSID {newsid} as sent_to_supabase")
                except Exception as e:
                    logger.warning(f"Child: Failed to mark local announcement as sent: {e}")

            # Upload financial data if present
            findata = processed_data.get('findata')
            if findata and findata != '{"period": "", "sales_current": "", "sales_previous_year": "", "pat_current": "", "pat_previous_year": ""}':
                try:
                    financial_data = json.loads(findata) if isinstance(findata, str) else findata
                    if any(financial_data.values()):
                        financial_data.update({
                            'corp_id': job.corp_id,
                            'symbol': processed_data.get("symbol", ""),
                            'isin': processed_data.get("isin", "")
                        })
                        ok = supabase_insert_table("financial_results", financial_data)
                        if ok:
                            logger.info("Child: Uploaded financial data")
                except Exception as e:
                    logger.warning(f"Child: Failed to upload financial data: {e}")

            # Upload investor data if available (call external helper)
            individual_investors = processed_data.get('individual_investor_list', [])
            company_investors = processed_data.get('company_investor_list', [])
            if individual_investors or company_investors:
                try:
                    from src.services.investor_analyzer import uploadInvestor
                    uploadInvestor(individual_investors, company_investors, corp_id=job.corp_id)
                    logger.info("Child: Uploaded investor data")
                except Exception as e:
                    logger.warning(f"Child: Failed to upload investor data: {e}")

            # Create investor analysis job if category warrants it
            if category not in ['Procedural/Administrative', 'routine', 'minor']:
                investor_job = InvestorAnalysisJob(
                    job_id=f"{job.job_id}_investor",
                    corp_id=job.corp_id,
                    category=category,
                    individual_investors=individual_investors,
                    company_investors=company_investors
                )
                # Push directly into investor processing queue (child has no redis client of parent)
                # Use environment Redis settings to push
                try:
                    r = redis.Redis(
                        host=os.getenv("REDIS_HOST", "localhost"),
                        port=int(os.getenv("REDIS_PORT", 6379)),
                        db=int(os.getenv("REDIS_DB", 0)),
                        socket_connect_timeout=REDIS_SOCKET_CONNECT_TIMEOUT,
                        socket_timeout=REDIS_SOCKET_TIMEOUT,
                        decode_responses=True,
                    )
                    r.lpush(INVESTOR_QUEUE, serialize_job(investor_job))
                    logger.info("Child: Created investor analysis job")
                except Exception as e:
                    logger.warning(f"Child: Failed to push investor job to queue: {e}")

            logger.info(f"Child: Completed job corp_id={job.corp_id} in {time.time() - start_all:.2f}s")
            sys.exit(0)

        except SystemExit as se:
            # Propagate sys.exit codes
            raise
        except Exception as e:
            # Capture unexpected child exceptions
            try:
                # Use logger to write to main process logs if possible (stdout/stderr)
                logger.exception(f"Child: Unhandled exception: {e}")
            except Exception:
                pass
            # Non-zero exit to signal failure
            sys.exit(10)

    def _run_job_with_timeout(self, job_json: str, job_id: str) -> bool:
        """Run job in a child process and enforce JOB_TIMEOUT. Returns True if child succeeded (exitcode==0)."""
        p = Process(target=self._child_process_job_runner, args=(job_json,))
        p.start()
        p.join(JOB_TIMEOUT)
        if p.is_alive():
            logger.warning(f"⚠️ Job {job_id} exceeded JOB_TIMEOUT ({JOB_TIMEOUT}s); terminating child process")
            p.terminate()
            p.join(5)
            # treat as failure (will requeue or move to failed)
            return False
        # child finished -- check exitcode
        if p.exitcode == 0:
            return True
        else:
            logger.warning(f"⚠️ Child exitcode for job {job_id} was {p.exitcode}")
            return False

    def run(self) -> bool:
        logger.info(f"🚀 {self.worker_id} starting (robust ephemeral mode)")
        if not self.setup_redis():
            return False

        self.start_sweeper()

        start_time = time.time()
        last_job_time = time.time()

        try:
            while not self._stop_event.is_set():
                # Heartbeat
                if time.time() - self._last_heartbeat > HEARTBEAT_INTERVAL:
                    try:
                        qlen = self.redis_client.llen(MAIN_QUEUE)
                    except Exception:
                        qlen = -1
                    logger.info(f"💓 Heartbeat: jobs_processed={self.jobs_processed}, main_queue_len={qlen}")
                    self._last_heartbeat = time.time()

                if self.jobs_processed >= self.max_jobs_per_session:
                    logger.info(f"✅ Processed {self.jobs_processed} jobs, shutting down")
                    break

                # Atomically move a job from main queue to processing list
                try:
                    # BRPOPLPUSH equivalent in redis-py: brpoplpush(source, destination, timeout)
                    job_json = self.redis_client.brpoplpush(MAIN_QUEUE, self.processing_list, timeout=BRPOP_TIMEOUT)
                except Exception as e:
                    logger.exception(f"❌ Redis BRPOPLPUSH error: {e}")
                    time.sleep(1)
                    continue

                if not job_json:
                    # no job received
                    # check idle timeout behavior
                    if time.time() - last_job_time > PROCESSING_TTL * 2:
                        logger.info("⏰ No jobs for a while, shutting down gracefully")
                        break
                    continue

                # We have a job moved to processing list; register meta and payload for requeue sweeper
                try:
                    # If job_json is bytes, ensure string
                    if isinstance(job_json, bytes):
                        job_json = job_json.decode("utf-8")

                    # Parse job just enough to get job_id
                    try:
                        job = deserialize_job(job_json)
                    except Exception as e:
                        # If deserialize failed, push job to failed queue and continue
                        logger.exception(f"Failed to deserialize job popped from queue: {e}. Moving to failed queue.")
                        self.redis_client.lpush(FAILED_QUEUE, job_json)
                        # remove from processing list
                        try:
                            self.redis_client.lrem(self.processing_list, 0, job_json)
                        except Exception:
                            pass
                        continue

                    job_id = getattr(job, "job_id", None) or f"job:{int(time.time()*1000)}"

                    # set meta & payload (used by sweeper)
                    now_ts = time.time()
                    try:
                        self.redis_client.hset(PROCESSING_META_HASH, job_id, now_ts)
                        self.redis_client.hset(PROCESSING_PAYLOAD_HASH, job_id, job_json)
                    except Exception as e:
                        logger.exception(f"Failed to write processing meta/payload for {job_id}: {e}")

                    logger.info(f"▶️ Picked job {job_id} (corp_id={getattr(job, 'corp_id', '-')}) into {self.processing_list}")

                    # Run job in child process with timeout
                    success = self._run_job_with_timeout(job_json, job_id)

                    if success:
                        # Clean up processing entry and increment count
                        try:
                            # Remove the job JSON from the processing list (LREM all occurrences of this payload)
                            self.redis_client.lrem(self.processing_list, 0, job_json)
                        except Exception as e:
                            logger.warning(f"Failed to remove processed job {job_id} from processing list: {e}")

                        try:
                            self.redis_client.hdel(PROCESSING_META_HASH, job_id)
                            self.redis_client.hdel(PROCESSING_PAYLOAD_HASH, job_id)
                            self.redis_client.hdel(JOB_RETRIES_HASH, job_id)
                        except Exception:
                            pass

                        self.jobs_processed += 1
                        last_job_time = time.time()
                        logger.info(f"✅ Completed job {job_id} ({self.jobs_processed}/{self.max_jobs_per_session})")
                        continue

                    # On failure: decide whether to retry or move to failed queue
                    try:
                        retries = self.redis_client.hincrby(JOB_RETRIES_HASH, job_id, 1)
                    except Exception:
                        retries = 1
                    if retries <= MAX_RETRIES:
                        # Requeue for retry (LPUSH so retried sooner)
                        try:
                            self.redis_client.lpush(MAIN_QUEUE, job_json)
                            logger.info(f"🔁 Requeued job {job_id} for retry {retries}/{MAX_RETRIES}")
                        except Exception as e:
                            logger.exception(f"Failed to requeue job {job_id}: {e}")
                    else:
                        # Move to failed queue for manual inspection
                        try:
                            self.redis_client.lpush(FAILED_QUEUE, job_json)
                            logger.error(f"💀 Job {job_id} exceeded max retries; moved to failed queue")
                        except Exception as e:
                            logger.exception(f"Failed to push job {job_id} to failed queue: {e}")

                    # Ensure removal from processing list & cleanup meta/payload
                    try:
                        self.redis_client.lrem(self.processing_list, 0, job_json)
                        self.redis_client.hdel(PROCESSING_META_HASH, job_id)
                        self.redis_client.hdel(PROCESSING_PAYLOAD_HASH, job_id)
                    except Exception:
                        pass

                except Exception as e:
                    logger.exception(f"❌ Unexpected error while handling job: {e}")
                    # Defensive: sleep a bit to avoid hot loop
                    time.sleep(1)

        except KeyboardInterrupt:
            logger.info("🛑 Interrupted by KeyboardInterrupt")
        except Exception as e:
            logger.exception(f"❌ Fatal worker error: {e}")
        finally:
            runtime = time.time() - start_time
            logger.info(f"🏁 {self.worker_id} finished - {self.jobs_processed} jobs in {runtime:.1f}s")
            self._stop_event.set()

        return True


def main():
    worker = EphemeralSupabaseWorkerV2()
    success = worker.run()
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
