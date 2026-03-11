#!/usr/bin/env python3
"""
Ephemeral Article Generation Worker

Spawned by the worker-spawner when the ARTICLE_GENERATION queue has items.
Drains all available jobs, generates news articles via Grok (xai-sdk),
stores them in Supabase, then exits.

Flow:
    worker_spawner sees LLEN(ARTICLE_GENERATION) > 0
        -> spawns this script as a subprocess
        -> this script BRPOPLPUSH jobs one-by-one
        -> calls Grok to generate article
        -> inserts into news_articles table
        -> exits when queue is empty (idle timeout)
"""

import os
import sys
import time
import json
import logging
import signal
import threading
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import redis

from src.queue.redis_client import RedisConfig, QueueNames
from src.queue.job_types import (
    ArticleGenerationJob,
    deserialize_job,
    serialize_job,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ARTICLE_QUEUE = QueueNames.ARTICLE_GENERATION
PROCESSING_LIST_PREFIX = "article_processing:"
PROCESSING_META_HASH = "article_processing_meta"
PROCESSING_PAYLOAD_HASH = "article_processing_payload"
JOB_RETRIES_HASH = "article_processing_retries"
FAILED_QUEUE = QueueNames.FAILED_JOBS

BRPOP_TIMEOUT = 3             # seconds waiting for a job
REDIS_SOCKET_CONNECT_TIMEOUT = 3
REDIS_SOCKET_TIMEOUT = 30     # must be > BRPOP_TIMEOUT to avoid "Timeout reading from socket"
MAX_RETRIES = 2               # Grok calls are expensive; don't retry too many times
IDLE_SHUTDOWN = 60             # exit after 60s idle (worker spawner will re-spawn if needed)
MAX_JOBS_PER_SESSION = 200     # max jobs before exiting (safety limit)
INTER_JOB_DELAY = 2           # seconds between articles to respect Grok rate limits
HEARTBEAT_INTERVAL = 30
PROCESSING_TTL = 120           # requeue if processing older than this (seconds)
SWEEPER_INTERVAL = 30

worker_id = f"article_worker_{os.getpid()}"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(worker_id)


# ---------------------------------------------------------------------------
# Lazy Supabase helper
# ---------------------------------------------------------------------------
_supabase = None


def _get_supabase():
    global _supabase
    if _supabase is None:
        from supabase import create_client
        url = os.getenv("SUPABASE_URL2")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY2")
        if not url or not key:
            raise RuntimeError("Supabase credentials missing (SUPABASE_URL2 / SUPABASE_SERVICE_ROLE_KEY)")
        _supabase = create_client(url, key)
    return _supabase


# ---------------------------------------------------------------------------
# Article-worthiness check (lightweight -- no network calls)
# ---------------------------------------------------------------------------
from src.ai.news_prompts import ARTICLE_WORTHY_CATEGORIES  # noqa: E402


def is_article_worthy(filing: dict) -> bool:
    """Return True if the filing should generate a news article."""
    category = (filing.get("category") or "").strip()
    if category not in ARTICLE_WORTHY_CATEGORIES:
        return False

    ai_summary = (filing.get("ai_summary") or "").strip()
    if not ai_summary or len(ai_summary) < 30:
        return False

    if filing.get("is_duplicate"):
        return False

    return True


# ---------------------------------------------------------------------------
# Core: generate and store an article for one filing
# ---------------------------------------------------------------------------
def _generate_and_store(filing: dict) -> bool:
    """
    Generate article via Grok and insert into news_articles.
    Returns True on success, False on skip/failure.
    """
    from src.ai.grok_writer import generate_article  # local import (heavy deps)

    corp_id = filing.get("corp_id")
    if not corp_id:
        return False

    sb = _get_supabase()

    # Deduplicate -- skip if article already exists for this filing
    existing = (
        sb.table("news_articles")
        .select("id")
        .eq("corp_id", corp_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        logger.debug(f"Article already exists for {corp_id} -- skipping")
        return False

    # Enrich with stocklistdata (sector, market_cap) if missing
    isin = filing.get("isin")
    if isin and not filing.get("sector"):
        try:
            stock_resp = (
                sb.table("stocklistdata")
                .select("sector, market_cap")
                .eq("isin", isin)
                .limit(1)
                .execute()
            )
            if stock_resp.data:
                filing["sector"] = stock_resp.data[0].get("sector")
                filing["market_cap"] = stock_resp.data[0].get("market_cap")
        except Exception:
            pass

    # Call Grok
    article = generate_article(filing)
    if article is None:
        logger.warning(f"Grok returned None for {corp_id}")
        return False

    # Insert article (all articles are free -- no tier system)
    article_row = {
        "corp_id": corp_id,
        "company_id": filing.get("company_id"),
        "isin": isin,
        "symbol": filing.get("symbol"),
        "companyname": filing.get("companyname"),
        "sector": filing.get("sector"),
        "headline": article.headline,
        "slug": article.slug,
        "seo_description": article.seo_description,
        "body": article.body,
        "sentiment": article.sentiment.value,
        "article_category": article.article_category,
        "tags": article.tags,
        "key_figures": article.key_figures,
        "category": filing.get("category"),
        "filing_date": filing.get("date"),
        "source_url": filing.get("fileurl"),
        "status": "published",
    }

    insert_resp = sb.table("news_articles").insert(article_row).execute()
    article_id = insert_resp.data[0]["id"] if insert_resp.data else None

    logger.info(
        f"Article published: '{article.headline}' "
        f"[{article.article_category}] (id={article_id})"
    )
    return True


# ---------------------------------------------------------------------------
# Ephemeral Worker
# ---------------------------------------------------------------------------
class EphemeralArticleWorker:
    """
    Spawned by worker-spawner when ARTICLE_GENERATION queue has items.
    Drains jobs, generates articles, then exits when idle.
    """

    def __init__(self):
        self.worker_id = worker_id
        self.redis_config = RedisConfig()
        self.redis_client: Optional[redis.Redis] = None
        self.processing_list = f"{PROCESSING_LIST_PREFIX}{self.worker_id}"
        self.jobs_processed = 0
        self.jobs_skipped = 0
        self._stop_event = threading.Event()
        self._last_heartbeat = time.time()

        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        self.sweeper_thread = threading.Thread(target=self._processing_requeue_sweeper, daemon=True)

    def _signal_handler(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self._stop_event.set()

    # ---- Redis connection (with proper socket_timeout > BRPOP_TIMEOUT) ----
    def setup_redis(self) -> bool:
        for attempt in range(3):
            try:
                # Create connection with socket_timeout > BRPOP_TIMEOUT to avoid
                # "Timeout reading from socket" errors during blocking pops.
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
                logger.info("Connected to Redis")
                return True
            except Exception as e:
                logger.warning(f"Redis connect attempt {attempt + 1}/3 failed: {e}")
                time.sleep(2)
        logger.error("Redis connection failed after retries")
        return False

    # ---- Stale job sweeper (background thread) ----
    def _processing_requeue_sweeper(self):
        """Re-enqueue jobs stuck in processing lists."""
        while not self._stop_event.is_set():
            try:
                all_meta = self.redis_client.hgetall(PROCESSING_META_HASH) or {}
                now = time.time()
                for job_id, ts_str in all_meta.items():
                    try:
                        ts = float(ts_str)
                    except (ValueError, TypeError):
                        continue
                    if now - ts > PROCESSING_TTL:
                        payload = self.redis_client.hget(PROCESSING_PAYLOAD_HASH, job_id)
                        if payload:
                            self.redis_client.lpush(ARTICLE_QUEUE, payload)
                            logger.warning(f"Requeued stale job {job_id}")
                        self.redis_client.hdel(PROCESSING_META_HASH, job_id)
                        self.redis_client.hdel(PROCESSING_PAYLOAD_HASH, job_id)
            except Exception as e:
                logger.debug(f"Sweeper error: {e}")
            self._stop_event.wait(SWEEPER_INTERVAL)

    def start_sweeper(self):
        if not self.sweeper_thread.is_alive():
            self.sweeper_thread = threading.Thread(target=self._processing_requeue_sweeper, daemon=True)
            self.sweeper_thread.start()

    # ---- Main loop ----
    def run(self) -> bool:
        logger.info(f"Starting ephemeral article worker: {self.worker_id}")

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
                        qlen = self.redis_client.llen(ARTICLE_QUEUE)
                    except Exception:
                        qlen = -1
                    logger.info(
                        f"Heartbeat: generated={self.jobs_processed}, "
                        f"skipped={self.jobs_skipped}, queue_len={qlen}"
                    )
                    self._last_heartbeat = time.time()

                # Session job limit
                if self.jobs_processed + self.jobs_skipped >= MAX_JOBS_PER_SESSION:
                    logger.info(f"Max session jobs reached ({MAX_JOBS_PER_SESSION}), exiting")
                    break

                # BRPOPLPUSH: atomically move job from main queue -> processing list
                try:
                    job_json = self.redis_client.brpoplpush(
                        ARTICLE_QUEUE, self.processing_list, timeout=BRPOP_TIMEOUT
                    )
                except Exception as e:
                    logger.error(f"Redis BRPOPLPUSH error: {e}")
                    time.sleep(1)
                    continue

                if not job_json:
                    # Check idle timeout
                    if time.time() - last_job_time > IDLE_SHUTDOWN:
                        logger.info(f"Idle for {IDLE_SHUTDOWN}s, shutting down")
                        break
                    continue

                if isinstance(job_json, bytes):
                    job_json = job_json.decode("utf-8")

                # Track for sweeper
                job_id = f"article_{int(time.time() * 1000)}"
                try:
                    self.redis_client.hset(PROCESSING_META_HASH, job_id, time.time())
                    self.redis_client.hset(PROCESSING_PAYLOAD_HASH, job_id, job_json)
                except Exception:
                    pass

                last_job_time = time.time()

                # Deserialize
                try:
                    job = deserialize_job(job_json)
                except Exception as e:
                    logger.exception(f"Failed to deserialize job: {e}")
                    self.redis_client.lpush(FAILED_QUEUE, job_json)
                    self.redis_client.lrem(self.processing_list, 0, job_json)
                    continue

                if not isinstance(job, ArticleGenerationJob):
                    logger.warning(f"Unexpected job type: {type(job).__name__}")
                    self.redis_client.lrem(self.processing_list, 0, job_json)
                    continue

                filing = job.filing_data
                corp_id = job.corp_id
                logger.info(
                    f"Processing article for {filing.get('symbol', '?')} "
                    f"({corp_id}) - category: {filing.get('category', '?')}"
                )

                # Process the job
                success = False
                try:
                    if not is_article_worthy(filing):
                        logger.info(f"Filing {corp_id} not article-worthy, skipping")
                        self.jobs_skipped += 1
                        success = True  # not a failure
                    else:
                        result = _generate_and_store(filing)
                        if result:
                            self.jobs_processed += 1
                        else:
                            self.jobs_skipped += 1
                        success = True
                except Exception as e:
                    logger.exception(f"Error generating article for {corp_id}: {e}")

                if success:
                    # Clean up
                    try:
                        self.redis_client.lrem(self.processing_list, 0, job_json)
                        self.redis_client.hdel(PROCESSING_META_HASH, job_id)
                        self.redis_client.hdel(PROCESSING_PAYLOAD_HASH, job_id)
                    except Exception:
                        pass
                    logger.info(
                        f"Completed ({self.jobs_processed} generated, "
                        f"{self.jobs_skipped} skipped)"
                    )
                else:
                    # Retry or fail
                    try:
                        retries = self.redis_client.hincrby(JOB_RETRIES_HASH, job_id, 1)
                    except Exception:
                        retries = 1

                    if retries <= MAX_RETRIES:
                        self.redis_client.lpush(ARTICLE_QUEUE, job_json)
                        logger.info(f"Requeued job for retry {retries}/{MAX_RETRIES}")
                    else:
                        self.redis_client.lpush(FAILED_QUEUE, job_json)
                        logger.error(f"Job exceeded max retries, moved to failed queue")

                    try:
                        self.redis_client.lrem(self.processing_list, 0, job_json)
                        self.redis_client.hdel(PROCESSING_META_HASH, job_id)
                        self.redis_client.hdel(PROCESSING_PAYLOAD_HASH, job_id)
                    except Exception:
                        pass

                # Rate limit between Grok calls
                time.sleep(INTER_JOB_DELAY)

        except KeyboardInterrupt:
            logger.info("Interrupted")
        except Exception as e:
            logger.exception(f"Fatal worker error: {e}")
        finally:
            runtime = time.time() - start_time
            logger.info(
                f"Worker finished - generated={self.jobs_processed}, "
                f"skipped={self.jobs_skipped}, runtime={runtime:.1f}s"
            )
            self._stop_event.set()

        return True


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------
def main():
    if not os.getenv("XAI_API_KEY"):
        logger.error("XAI_API_KEY environment variable is required")
        sys.exit(1)

    worker = EphemeralArticleWorker()
    success = worker.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
