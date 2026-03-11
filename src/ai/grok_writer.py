"""
Grok-powered article writer.

Uses xai_sdk with grok-4-1-fast-reasoning and structured output (Pydantic)
to generate publication-ready news articles from corporate filings.
"""

import os
import logging
from typing import Optional

from dotenv import load_dotenv
from xai_sdk import Client
from xai_sdk.chat import system, user

from src.ai.article_models import GeneratedArticle
from src.ai.news_prompts import get_prompt_for_category

load_dotenv()
logger = logging.getLogger(__name__)

MODEL = "grok-4-1-fast-reasoning"


def _build_user_message(filing: dict) -> str:
    """
    Assemble the user-message payload from a corporatefilings row.

    Expected keys: companyname, symbol, isin, category, date,
                   ai_summary, headline (existing), summary, fileurl
    """
    parts = []

    company = filing.get("companyname") or "Unknown Company"
    symbol = filing.get("symbol") or ""
    isin = filing.get("isin") or ""
    category = filing.get("category") or ""
    date = filing.get("date") or ""
    ai_summary = filing.get("ai_summary") or ""
    raw_summary = filing.get("summary") or ""
    headline = filing.get("headline") or ""
    fileurl = filing.get("fileurl") or ""
    sector = filing.get("sector") or ""
    market_cap = filing.get("market_cap")

    parts.append(f"Company: {company} ({symbol})")
    if isin:
        parts.append(f"ISIN: {isin}")
    if sector:
        parts.append(f"Sector: {sector}")
    if market_cap:
        parts.append(f"Market Cap: ₹{market_cap:,.2f} Cr")
    parts.append(f"Category: {category}")
    parts.append(f"Filing Date: {date}")
    if headline:
        parts.append(f"Filing Headline: {headline}")
    if ai_summary:
        parts.append(f"\n--- AI Summary of Filing ---\n{ai_summary}")
    if raw_summary and raw_summary != ai_summary:
        parts.append(f"\n--- Raw Summary / Exchange Description ---\n{raw_summary}")
    if fileurl:
        parts.append(f"\nSource PDF: {fileurl}")

    return "\n".join(parts)


def generate_article(filing: dict) -> Optional[GeneratedArticle]:
    """
    Generate a structured article for a single corporate filing.

    Args:
        filing: Dict with corporatefilings row data (must include 'category').

    Returns:
        GeneratedArticle on success, None on failure.
    """
    category = (filing.get("category") or "").strip()
    if not category:
        logger.warning("Filing has no category — skipping article generation")
        return None

    prompt = get_prompt_for_category(category)
    if prompt is None:
        logger.info(f"No article prompt for category '{category}' — skipping")
        return None

    api_key = os.getenv("GROK_API_KEY")
    if not api_key:
        logger.error("GROK_API_KEY not set in environment")
        return None

    try:
        client = Client(api_key=api_key)
        chat = client.chat.create(model=MODEL)

        chat.append(system(prompt))
        chat.append(user(_build_user_message(filing)))

        _response, article = chat.parse(GeneratedArticle)

        if not isinstance(article, GeneratedArticle):
            logger.error("Grok returned unexpected type instead of GeneratedArticle")
            return None

        logger.info(
            f"Article generated: '{article.headline}' "
            f"[{article.sentiment.value}] ({len(article.body)} chars)"
        )
        return article

    except Exception as e:
        logger.error(f"Grok article generation failed for '{filing.get('companyname')}': {e}")
        return None
