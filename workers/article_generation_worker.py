#!/usr/bin/env python3
"""
Ephemeral Article Generation Worker

Spawned by worker-spawner when ARTICLE_GENERATION queue has items.
Drains all available jobs using non-blocking RPOP, then exits immediately.

NO polling, NO blocking, NO idle timeouts.
Worker spawner handles re-spawning when new jobs arrive.

Flow:
    worker_spawner sees LLEN(ARTICLE_GENERATION) > 0
        -> spawns this script
        -> RPOP all jobs one-by-one (non-blocking)
        -> generate article via Grok
        -> insert into news_articles
        -> queue empty -> exit immediately
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
FAILED_QUEUE = QueueNames.FAILED_JOBS
MAX_RETRIES = 2
MAX_JOBS_PER_SESSION = 200
INTER_JOB_DELAY = 2  # seconds between Grok calls (rate limit)

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
    from src.ai.grok_writer import generate_article

    corp_id = filing.get("corp_id")
    if not corp_id:
        return False

    sb = _get_supabase()

    # Deduplicate
    existing = (
        sb.table("news_articles")
        .select("id")
        .eq("corp_id", corp_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        logger.info(f"Article already exists for {corp_id}, skipping")
        return False

    # Enrich with stocklistdata if missing
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
    logger.info(f"Article published: '{article.headline}' [{article.article_category}] (id={article_id})")
    return True


# ---------------------------------------------------------------------------
# Main: drain queue and exit
# ---------------------------------------------------------------------------
def main():
    if not os.getenv("XAI_API_KEY"):
        logger.error("XAI_API_KEY environment variable is required")
        sys.exit(1)

    logger.info(f"Starting ephemeral article worker: {worker_id}")

    # Connect to Redis
    try:
        rc = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_DB", 0)),
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=10,
        )
        rc.ping()
        logger.info("Connected to Redis")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        sys.exit(1)

    generated = 0
    skipped = 0
    failed = 0
    start_time = time.time()

    # Drain the queue using non-blocking RPOP
    for _ in range(MAX_JOBS_PER_SESSION):
        job_json = rc.rpop(ARTICLE_QUEUE)
        if not job_json:
            # Queue empty -> done
            break

        if isinstance(job_json, bytes):
            job_json = job_json.decode("utf-8")

        # Deserialize
        try:
            job = deserialize_job(job_json)
        except Exception as e:
            logger.error(f"Failed to deserialize job: {e}")
            rc.lpush(FAILED_QUEUE, job_json)
            failed += 1
            continue

        if not isinstance(job, ArticleGenerationJob):
            logger.warning(f"Unexpected job type: {type(job).__name__}, skipping")
            skipped += 1
            continue

        filing = job.filing_data
        corp_id = job.corp_id
        symbol = filing.get("symbol", "?")
        category = filing.get("category", "?")

        logger.info(f"Processing: {symbol} ({corp_id}) - {category}")

        # Check worthiness
        if not is_article_worthy(filing):
            logger.info(f"Not article-worthy, skipping")
            skipped += 1
            continue

        # Generate article
        try:
            result = _generate_and_store(filing)
            if result:
                generated += 1
            else:
                skipped += 1
        except Exception as e:
            logger.exception(f"Error generating article for {corp_id}: {e}")
            # Push to failed queue for inspection
            try:
                fail_data = json.loads(job_json)
                fail_data["error"] = str(e)
                fail_data["failed_at"] = datetime.now(timezone.utc).isoformat()
                rc.lpush(FAILED_QUEUE, json.dumps(fail_data))
            except Exception:
                rc.lpush(FAILED_QUEUE, job_json)
            failed += 1

        # Rate limit between Grok API calls
        if generated > 0:
            time.sleep(INTER_JOB_DELAY)

    runtime = time.time() - start_time
    logger.info(
        f"Worker done - generated={generated}, skipped={skipped}, "
        f"failed={failed}, runtime={runtime:.1f}s"
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
