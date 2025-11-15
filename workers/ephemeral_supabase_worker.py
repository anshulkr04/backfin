#!/usr/bin/env python3
"""
Robust Ephemeral Supabase Worker (v2)

- BRPOPLPUSH -> processing:<worker_id> pattern (atomic move)
- Runs each job in a child process with a hard JOB_TIMEOUT
- Requeue sweeper for stuck jobs (PROCESSING_META_HASH + PROCESSING_PAYLOAD_HASH)
- Retries + dead-letter handling
- Detailed timing and exception logging
"""

import os
import sys
import time
import json
import logging
import signal
import threading
from datetime import datetime,date
from pathlib import Path
from multiprocessing import Process
from typing import Optional
import requests

import redis

# Add project src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.queue.redis_client import RedisConfig, QueueNames
from src.queue.job_types import deserialize_job, SupabaseUploadJob, InvestorAnalysisJob, serialize_job

# ---- Configuration ----
MAIN_QUEUE = QueueNames.SUPABASE_UPLOAD
PROCESSING_LIST_PREFIX = "processing:"
PROCESSING_META_HASH = "processing_meta"
PROCESSING_PAYLOAD_HASH = "processing_payload"
JOB_RETRIES_HASH = "processing_retries"
FAILED_QUEUE = QueueNames.FAILED_JOBS
INVESTOR_QUEUE = QueueNames.INVESTOR_PROCESSING

BRPOP_TIMEOUT = 3            # seconds waiting for a job
JOB_TIMEOUT = 60             # per-job child hard timeout (seconds)
PROCESSING_TTL = 90          # requeue if processing older than this (seconds)
REQUEUE_SWEEPER_INTERVAL = 30
MAX_RETRIES = 3

REDIS_SOCKET_CONNECT_TIMEOUT = 3
REDIS_SOCKET_TIMEOUT = 30
HEARTBEAT_INTERVAL = 30

# ---- Logging ----
worker_id = f"ephemeral_supabase_{os.getpid()}"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(worker_id)

def _send_to_api_if_needed(data):
        """Helper method to send data to API if needed"""
        category = data.get("category")
        if category in (None, "Procedural/Administrative", "Error"):
            logger.info("Announcement is non-broadcast category, skipping API call")
            return
        # Guard against empty content
        summary = data.get("summary") or ""
        ai_summary = data.get("ai_summary") or ""
        if not isinstance(summary, str):
            summary = str(summary)
        if not isinstance(ai_summary, str):
            ai_summary = str(ai_summary)
        if summary.strip() == "" and ai_summary.strip() == "":
            logger.info("Skipping API call due to empty summary and ai_summary")
            return
        
        # Send to API endpoint (which will handle websocket communication)
        try:
            # Use Docker service name for container communication
            api_host = os.getenv("API_HOST", "api")  # Docker service name
            api_port = os.getenv("API_PORT", "8000")
            post_url = f"http://{api_host}:{api_port}/api/insert_new_announcement"  # BSE
            data["is_fresh"] = True  # Mark as fresh for broadcasting
            res = requests.post(url=post_url, json=data)
            if res.status_code >= 200 and res.status_code < 300:
                logger.info(f"Sent to API for websocket: Status code {res.status_code}")
            else:
                logger.error(f"API returned error: {res.status_code}, {res.text}")
        except Exception as e:
            logger.error(f"Error sending to API: {e}")


class EphemeralSupabaseWorkerV2:
    def __init__(self):
        self.worker_id = worker_id
        self.redis_config = RedisConfig()
        self.redis_client: Optional[redis.Redis] = None
        self.jobs_processed = 0
        self.max_jobs_per_session = 1000
        self.processing_list = f"{PROCESSING_LIST_PREFIX}{self.worker_id}"
        self._stop_event = threading.Event()
        self._last_heartbeat = time.time()
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        self.sweeper_thread = threading.Thread(target=self._processing_requeue_sweeper, daemon=True)

    def _signal_handler(self, signum, frame):
        logger.warning(f"🛑 Received signal {signum}, shutting down...")
        self._stop_event.set()
        # Attempt graceful cleanup of processing metadata for this worker
        try:
            # Remove any processing payloads that reference this processing_list (best-effort)
            # We do not know job_ids held by this worker here; sweeper will handle stale meta.
            pass
        except Exception as e:
            logger.debug(f"Cleanup during signal failed: {e}")

    def setup_redis(self) -> bool:
        # Try a few times before giving up (helps if redis is starting)
        for attempt in range(3):
            try:
                client = self.redis_config.get_connection()
                # Ensure client can talk to redis
                client.ping()
                # If client doesn't decode responses, replace with a local one using env
                if not getattr(client, "decode_responses", False):
                    client = redis.Redis(
                        host=os.getenv("REDIS_HOST", "localhost"),
                        port=int(os.getenv("REDIS_PORT", 6379)),
                        db=int(os.getenv("REDIS_DB", 0)),
                        socket_connect_timeout=REDIS_SOCKET_CONNECT_TIMEOUT,
                        socket_timeout=REDIS_SOCKET_TIMEOUT,
                        decode_responses=True,
                    )
                    client.ping()
                self.redis_client = client
                logger.info("✅ Redis client initialized successfully")
                return True
            except Exception as e:
                logger.warning(f"Redis connect attempt {attempt+1}/3 failed: {e}")
                time.sleep(2)
        logger.exception("❌ Redis connection failed after retries")
        return False

    def start_sweeper(self):
        if not self.sweeper_thread.is_alive():
            self.sweeper_thread = threading.Thread(target=self._processing_requeue_sweeper, daemon=True)
            self.sweeper_thread.start()
            logger.info("🧭 Requeue sweeper started")

    def _processing_requeue_sweeper(self):
        """Requeue stuck jobs older than PROCESSING_TTL"""
        while not self._stop_event.is_set():
            try:
                now = time.time()
                meta = self.redis_client.hgetall(PROCESSING_META_HASH) or {}
                for job_id, ts in meta.items():
                    try:
                        moved_at = float(ts)
                    except Exception:
                        moved_at = 0.0
                    age = now - moved_at
                    if age > PROCESSING_TTL:
                        job_json = self.redis_client.hget(PROCESSING_PAYLOAD_HASH, job_id)
                        if not job_json:
                            # cleanup stale meta if no payload
                            self.redis_client.hdel(PROCESSING_META_HASH, job_id)
                            self.redis_client.hdel(PROCESSING_PAYLOAD_HASH, job_id)
                            continue
                        logger.warning(f"🔁 Requeuing stuck job {job_id} (age={int(age)}s)")
                        try:
                            # Attempt to remove from any processing lists (best-effort)
                            keys = self.redis_client.keys(f"{PROCESSING_LIST_PREFIX}*")
                            removed = 0
                            for k in keys:
                                try:
                                    r = self.redis_client.lrem(k, 0, job_json)
                                    removed += r
                                    if r > 0:
                                        logger.debug(f"Removed stuck job {job_id} from {k}")
                                except Exception:
                                    continue
                            # Push back to main queue
                            self.redis_client.lpush(MAIN_QUEUE, job_json)
                            # cleanup meta & payload
                            self.redis_client.hdel(PROCESSING_META_HASH, job_id)
                            self.redis_client.hdel(PROCESSING_PAYLOAD_HASH, job_id)
                        except Exception as e:
                            logger.exception(f"Failed to requeue stuck job {job_id}: {e}")
                # Sleep with stop checks
                for _ in range(int(REQUEUE_SWEEPER_INTERVAL)):
                    if self._stop_event.is_set():
                        break
                    time.sleep(1)
            except Exception as e:
                logger.exception(f"Requeue sweeper error: {e}")
                time.sleep(5)

    def _child_process_job_runner(self, job_json: str):
        """Child process target: does the heavy IO (Supabase/SQLite/Investor)"""
        try:
            # local imports to avoid inheriting parent's connections
            from supabase import create_client, Client
            import sqlite3

            job = deserialize_job(job_json)
            if not isinstance(job, SupabaseUploadJob):
                logger.error(f"Child: unexpected job type: {type(job)}")
                sys.exit(2)

            supabase_url = os.getenv('SUPABASE_URL2')
            supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
            if not supabase_url or not supabase_key:
                logger.error("Child: Supabase credentials missing")
                sys.exit(3)

            try:
                supabase: Client = create_client(supabase_url, supabase_key)
            except Exception as e:
                logger.exception(f"Child: Failed to create Supabase client: {e}")
                sys.exit(4)

            processed_data = job.processed_data or {}
            if not processed_data:
                logger.error(f"Child: No processed_data for corp_id={job.corp_id}")
                sys.exit(5)

            category = processed_data.get('category', '')
            if category == "Error":
                logger.warning(f"Child: Skipping corp_id {job.corp_id} due to category 'Error'")
                sys.exit(0)

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

            def supabase_insert_table(table_name: str, payload: dict):
                attempts = 0
                while attempts < 3:
                    attempts += 1
                    try:
                        resp = supabase.table(table_name).insert(payload).execute()
                        if hasattr(resp, "error") and resp.error:
                            errstr = str(resp.error)
                            if "duplicate key" in errstr.lower() or "23505" in errstr:
                                logger.warning(f"Child: Duplicate key for {payload.get('corp_id')} on {table_name} (treated as success)")
                                return True
                            else:
                                logger.warning(f"Child: Supabase insert error (attempt {attempts}): {resp.error}")
                                time.sleep(0.3 * attempts)
                                continue
                        return True
                    except Exception as e:
                        logger.exception(f"Child: Supabase insert exception (attempt {attempts}): {e}")
                        time.sleep(0.3 * attempts)
                return False
            
            def update_count(announcement):
                raw = announcement.get("date")
                # Convert to date object for processing
                date_obj = datetime.fromisoformat(raw).date()
                # Convert back to ISO string for Supabase
                today = date_obj.isoformat()
                category = announcement.get("category")

                # category is the column name, e.g. "Financial Results"
                # Increment logic: if row exists, increment; else start at 1

                # Step 1: Fetch today's row
                existing = (
                    supabase
                    .table("announcement_categories")
                    .select("*")
                    .eq("date", today)
                    .maybe_single()
                    .execute()
                )

                if existing.data is None:
                    # No row for today, create a new one
                    data = {"date": today, category: 1}
                    response = supabase.table("announcement_categories").insert(data).execute()
                    logger.info(f"Created new row for date {today} with {category}=1")
                else:
                    # Row exists; increment the category count
                    current_value = existing.data.get(category, 0) or 0
                    new_value = current_value + 1

                    response = (
                        supabase
                        .table("announcement_categories")
                        .update({category: new_value})
                        .eq("date", today)
                        .execute()
                    )
                    logger.info(f"Updated {category} count to {new_value} for date {today}")

                return response


            # Existence check & insert
            try:
                check_resp = supabase.table("corporatefilings").select("corp_id").eq("corp_id", job.corp_id).execute()
                if getattr(check_resp, "data", None) and len(check_resp.data) > 0:
                    logger.warning(f"Child: corp_id {job.corp_id} already exists - skipping insert")
                else:
                    ok = supabase_insert_table("corporatefilings", upload_data)
                    if not ok:
                        logger.error("Child: Failed to insert corporatefilings after retries")
                        sys.exit(6)
                    if ok:
                        logger.info(f"Child: Inserted corp_id {job.corp_id} into corporatefilings")
                        try:
                            update_count(upload_data)
                            logger.info("Child: Updated announcement count")
                        except Exception as e:
                            logger.warning(f"Child: Failed to update announcement count: {e}")
                        # Send to API for websocket broadcast if needed
                        _send_to_api_if_needed(upload_data)

            except Exception as e:
                logger.exception(f"Child: Error during existence check/insert: {e}")
                sys.exit(7)

            # Local SQLite mark as sent
            newsid = processed_data.get('newsid')
            if newsid:
                try:
                    db_path = Path("/app/data") / "bse_raw.db"
                    conn = sqlite3.connect(str(db_path), timeout=15)
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
                    logger.info(f"Child: Marked NEWSID {newsid} as sent")
                except Exception as e:
                    logger.warning(f"Child: Failed to mark local announcement as sent: {e}")

            # Financial data
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

            # Investor upload
            individual_investors = processed_data.get('individual_investor_list', [])
            company_investors = processed_data.get('company_investor_list', [])
            if individual_investors or company_investors:
                try:
                    from src.services.investor_analyzer import uploadInvestor
                    uploadInvestor(individual_investors, company_investors, corp_id=job.corp_id)
                    logger.info("Child: Uploaded investor data")
                except Exception as e:
                    logger.warning(f"Child: Failed to upload investor data: {e}")

            # # Create investor analysis job if needed
            # if category not in ['Procedural/Administrative', 'routine', 'minor']:
            #     investor_job = InvestorAnalysisJob(
            #         job_id=f"{job.job_id}_investor",
            #         corp_id=job.corp_id,
            #         category=category,
            #         individual_investors=individual_investors,
            #         company_investors=company_investors
            #     )
            #     try:
            #         r = redis.Redis(
            #             host=os.getenv("REDIS_HOST", "localhost"),
            #             port=int(os.getenv("REDIS_PORT", 6379)),
            #             db=int(os.getenv("REDIS_DB", 0)),
            #             socket_connect_timeout=REDIS_SOCKET_CONNECT_TIMEOUT,
            #             socket_timeout=REDIS_SOCKET_TIMEOUT,
            #             decode_responses=True,
            #         )
            #         r.lpush(INVESTOR_QUEUE, serialize_job(investor_job))
            #         logger.info("Child: Created investor analysis job")
            #     except Exception as e:
            #         logger.warning(f"Child: Failed to push investor job: {e}")

            logger.info(f"Child: Completed job corp_id={job.corp_id}")
            sys.exit(0)

        except SystemExit:
            raise
        except Exception as e:
            try:
                logger.exception(f"Child: Unhandled exception: {e}")
            except Exception:
                pass
            sys.exit(10)

    def _run_job_with_timeout(self, job_json: str, job_id: str) -> bool:
        """Start a child process and enforce JOB_TIMEOUT"""
        p = Process(target=self._child_process_job_runner, args=(job_json,))
        p.start()
        p.join(JOB_TIMEOUT)
        if p.is_alive():
            logger.warning(f"⚠️ Job {job_id} exceeded JOB_TIMEOUT ({JOB_TIMEOUT}s); terminating child")
            p.terminate()
            p.join(5)
            if p.is_alive():
                try:
                    p.kill()
                except Exception:
                    pass
            return False
        if p.exitcode == 0:
            return True
        logger.warning(f"⚠️ Child exitcode for job {job_id}: {p.exitcode}")
        return False

    def run(self) -> bool:
        logger.info(f"🚀 {self.worker_id} starting")
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
                    logger.info(f"💓 Heartbeat: processed={self.jobs_processed}, main_queue_len={qlen}")
                    self._last_heartbeat = time.time()

                if self.jobs_processed >= self.max_jobs_per_session:
                    logger.info(f"✅ Processed {self.jobs_processed} jobs, shutting down")
                    break

                try:
                    job_json = self.redis_client.brpoplpush(MAIN_QUEUE, self.processing_list, timeout=BRPOP_TIMEOUT)
                except Exception as e:
                    logger.exception(f"Redis BRPOPLPUSH error: {e}")
                    time.sleep(1)
                    continue

                if not job_json:
                    # idle check
                    if time.time() - last_job_time > PROCESSING_TTL * 2:
                        logger.info("⏰ Idle for a while, shutting down")
                        break
                    continue

                if isinstance(job_json, bytes):
                    job_json = job_json.decode("utf-8")

                try:
                    job = deserialize_job(job_json)
                except Exception as e:
                    logger.exception(f"Failed to deserialize job popped: {e}. Moving to failed queue.")
                    try:
                        self.redis_client.lpush(FAILED_QUEUE, job_json)
                        self.redis_client.lrem(self.processing_list, 0, job_json)
                    except Exception:
                        pass
                    continue

                job_id = getattr(job, "job_id", f"job:{int(time.time()*1000)}")
                now_ts = time.time()
                try:
                    self.redis_client.hset(PROCESSING_META_HASH, job_id, now_ts)
                    self.redis_client.hset(PROCESSING_PAYLOAD_HASH, job_id, job_json)
                except Exception:
                    logger.debug("Failed to write processing meta/payload (non-fatal)")

                logger.info(f"▶️ Picked job {job_id} (corp_id={getattr(job,'corp_id','-')})")

                success = self._run_job_with_timeout(job_json, job_id)

                if success:
                    try:
                        self.redis_client.lrem(self.processing_list, 0, job_json)
                    except Exception:
                        logger.debug("Failed to lrem processed job (non-fatal)")
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

                # Failure: retry or move to failed
                try:
                    retries = self.redis_client.hincrby(JOB_RETRIES_HASH, job_id, 1)
                except Exception:
                    retries = 1

                if retries <= MAX_RETRIES:
                    try:
                        self.redis_client.lpush(MAIN_QUEUE, job_json)
                        logger.info(f"🔁 Requeued job {job_id} for retry {retries}/{MAX_RETRIES}")
                    except Exception as e:
                        logger.exception(f"Failed to requeue job {job_id}: {e}")
                else:
                    try:
                        self.redis_client.lpush(FAILED_QUEUE, job_json)
                        logger.error(f"💀 Job {job_id} exceeded max retries; moved to failed queue")
                    except Exception as e:
                        logger.exception(f"Failed to move job {job_id} to failed queue: {e}")

                try:
                    self.redis_client.lrem(self.processing_list, 0, job_json)
                    self.redis_client.hdel(PROCESSING_META_HASH, job_id)
                    self.redis_client.hdel(PROCESSING_PAYLOAD_HASH, job_id)
                except Exception:
                    pass

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
