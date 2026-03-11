#!/usr/bin/env python3
"""
Article Generation Worker

Consumes ArticleGenerationJob from the Redis ARTICLE_GENERATION queue,
generates news articles via Grok (xai_sdk), and stores them in Supabase.

Follows the same BRPOP pattern as telegram_notification_worker.py.
"""

import os
import sys
import time
import json
import logging
import signal
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
FAILED_QUEUE = QueueNames.FAILED_JOBS
BRPOP_TIMEOUT = 5            # seconds to wait on BRPOP
MAX_RETRIES = 2               # Grok calls are expensive; don't retry too many times
IDLE_SHUTDOWN = 300            # shut down after 5 min idle (optional, 0 = never)
INTER_JOB_DELAY = 2           # seconds between articles to respect Grok rate limits

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
# Article-worthiness check (lightweight — no network calls)
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

    # Deduplicate — skip if article already exists for this filing
    existing = (
        sb.table("news_articles")
        .select("id")
        .eq("corp_id", corp_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        logger.debug(f"Article already exists for {corp_id} — skipping")
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

    # Insert article (all articles are free — no tier system)
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
        f"📰 Article published: '{article.headline}' "
        f"[{article.article_category}] (id={article_id})"
    )
    return True


# ---------------------------------------------------------------------------
# Worker class
# ---------------------------------------------------------------------------
class ArticleGenerationWorker:
    """Consumes from ARTICLE_GENERATION Redis queue and generates articles."""

    def __init__(self):
        self.worker_id = worker_id
        self.redis_config = RedisConfig()
        self.redis_client: Optional[redis.Redis] = None
        self.processing_list = f"{PROCESSING_LIST_PREFIX}{self.worker_id}"
        self.running = False
        self.jobs_processed = 0
        self.jobs_skipped = 0

        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False

    # ---- Redis connection ----
    def connect_redis(self) -> bool:
        try:
            self.redis_client = self.redis_config.get_connection()
            self.redis_client.ping()
            logger.info("Connected to Redis")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            return False

    # ---- Job lifecycle helpers ----
    def get_job(self) -> Optional[str]:
        """BRPOPLPUSH: atomically move job from main queue → processing list."""
        try:
            result = self.redis_client.brpoplpush(
                ARTICLE_QUEUE, self.processing_list, timeout=BRPOP_TIMEOUT
            )
            return result
        except Exception as e:
            logger.error(f"Error getting job from queue: {e}")
            return None

    def complete_job(self, job_json: str):
        """Remove finished job from the processing list."""
        try:
            self.redis_client.lrem(self.processing_list, 1, job_json)
        except Exception as e:
            logger.warning(f"Error removing completed job from processing list: {e}")

    def fail_job(self, job_json: str, error: str):
        """Move failed job to FAILED_JOBS queue."""
        try:
            try:
                job_data = json.loads(job_json)
                job_data["error"] = error
                job_data["failed_at"] = datetime.now(timezone.utc).isoformat()
                job_json_updated = json.dumps(job_data)
            except Exception:
                job_json_updated = job_json

            self.redis_client.lpush(FAILED_QUEUE, job_json_updated)
            self.redis_client.lrem(self.processing_list, 1, job_json)
            logger.warning(f"Moved job to failed queue: {error}")
        except Exception as e:
            logger.error(f"Error moving job to failed queue: {e}")

    # ---- Process one job ----
    def process_job(self, job_json: str) -> bool:
        """Deserialize, check worthiness, generate article."""
        try:
            job = deserialize_job(job_json)
            if not isinstance(job, ArticleGenerationJob):
                logger.warning(f"Unexpected job type: {type(job).__name__}")
                return False

            filing = job.filing_data
            corp_id = job.corp_id
            logger.info(
                f"Processing article job for {filing.get('symbol', '?')} "
                f"({corp_id}) — category: {filing.get('category', '?')}"
            )

            if not is_article_worthy(filing):
                logger.info(f"Filing {corp_id} is not article-worthy — skipping")
                self.jobs_skipped += 1
                return True  # not a failure, just skipped

            success = _generate_and_store(filing)
            if success:
                self.jobs_processed += 1
            else:
                self.jobs_skipped += 1

            return True  # even if skipped/deduplicated, don't move to failed queue

        except Exception as e:
            logger.exception(f"Error processing article job: {e}")
            return False

    # ---- Main loop ----
    def run(self):
        """Blocking worker loop."""
        logger.info(f"Starting article generation worker: {self.worker_id}")

        if not self.connect_redis():
            logger.error("Failed to connect to Redis — exiting")
            return

        self.running = True
        last_job_time = time.time()

        while self.running:
            try:
                job_json = self.get_job()

                if not job_json:
                    # Idle timeout check
                    if IDLE_SHUTDOWN > 0 and (time.time() - last_job_time) > IDLE_SHUTDOWN:
                        logger.info(f"Idle for {IDLE_SHUTDOWN}s — shutting down")
                        break
                    continue

                last_job_time = time.time()

                try:
                    success = self.process_job(job_json)
                    if success:
                        self.complete_job(job_json)
                    else:
                        self.fail_job(job_json, "Processing returned False")
                except Exception as e:
                    logger.exception(f"Job processing error: {e}")
                    self.fail_job(job_json, str(e))

                # Small delay between articles to respect Grok rate limits
                time.sleep(INTER_JOB_DELAY)

            except Exception as e:
                logger.exception(f"Worker loop error: {e}")
                time.sleep(5)

        logger.info(
            f"Worker stopped. Generated={self.jobs_processed}, "
            f"Skipped={self.jobs_skipped}"
        )


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------
def main():
    if not os.getenv("XAI_API_KEY"):
        logger.error("XAI_API_KEY environment variable is required")
        sys.exit(1)

    worker = ArticleGenerationWorker()
    worker.run()


if __name__ == "__main__":
    main()
