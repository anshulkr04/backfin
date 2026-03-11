"""
Article Pipeline -- utility for queuing article generation via Redis.

Real-time path:
    supabase worker -> LPUSH ArticleGenerationJob -> ARTICLE_GENERATION queue
    -> article_generation_worker.py (BRPOP) -> Grok -> news_articles table

This module provides:
    - is_article_worthy(filing) -- lightweight filter
    - enqueue_article(filing, redis_client) -- push a job onto the Redis queue

All articles are FREE -- no tier / paywall system.
"""

import os
import time
import logging

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Filtering
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
# Enqueue via Redis
# ---------------------------------------------------------------------------
def enqueue_article(filing: dict, redis_client=None) -> bool:
    """
    Push an ArticleGenerationJob onto the Redis ARTICLE_GENERATION queue.

    If no redis_client is given, creates one from env vars.
    Returns True if queued, False if skipped.
    """
    if not is_article_worthy(filing):
        return False

    corp_id = filing.get("corp_id")
    if not corp_id:
        return False

    try:
        from src.queue.redis_client import QueueNames, RedisConfig
        from src.queue.job_types import ArticleGenerationJob, serialize_job

        if redis_client is None:
            redis_client = RedisConfig().get_connection()

        job = ArticleGenerationJob(
            job_id=f"article_{corp_id}_{int(time.time())}",
            corp_id=corp_id,
            filing_data=filing,
        )
        redis_client.lpush(QueueNames.ARTICLE_GENERATION, serialize_job(job))
        logger.info(f"Enqueued article job for {filing.get('symbol')} ({corp_id})")
        return True

    except Exception as e:
        logger.error(f"Failed to enqueue article for {corp_id}: {e}")
        return False
