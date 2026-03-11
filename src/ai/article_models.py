"""
Pydantic models for structured article output from Grok API.

These models define the schema that the Grok `chat.parse()` method
will enforce, guaranteeing well-typed, predictable article data.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ArticleSentiment(str, Enum):
    """Sentiment classification for the article."""
    POSITIVE = "Positive"
    NEGATIVE = "Negative"
    NEUTRAL = "Neutral"
    MIXED = "Mixed"


# The exact set of article categories the model is allowed to pick from.
ARTICLE_CATEGORIES = [
    "Earnings & Results",
    "Mergers & Acquisitions",
    "Fundraising & Capital Markets",
    "Dividends & Corporate Actions",
    "Leadership Changes",
    "Regulatory & Legal",
    "Business Operations",
    "Debt & Credit",
    "Investor Relations",
    "Strategic Agreements",
    "Market Commentary",
]


class GeneratedArticle(BaseModel):
    """
    Full structured article output from Grok.
    Every field maps directly to a column in the `news_articles` table.
    """

    headline: str = Field(
        description="Article headline, 8–15 words, price-sensitive and specific"
    )
    slug: str = Field(
        description="URL-safe slug, lowercase, hyphenated, max 60 chars (e.g. 'reliance-q3-fy26-pat-jumps-18-pct')"
    )
    seo_description: str = Field(
        description="SEO meta description, 140–160 characters summarising the article for Google"
    )
    body: str = Field(
        description="Full article body in Markdown format (400–600 words typically)"
    )
    sentiment: ArticleSentiment = Field(
        description="Overall sentiment of the article"
    )
    article_category: str = Field(
        description=(
            "Pick exactly ONE category from this list: "
            "Earnings & Results, Mergers & Acquisitions, Fundraising & Capital Markets, "
            "Dividends & Corporate Actions, Leadership Changes, Regulatory & Legal, "
            "Business Operations, Debt & Credit, Investor Relations, Strategic Agreements, "
            "Market Commentary. Choose the single best fit for this article."
        )
    )
    tags: list[str] = Field(
        description="3–6 lowercase tags relevant to the article (e.g. 'quarterly results', 'reliance')"
    )
    key_figures: Optional[str] = Field(
        default=None,
        description="Comma-separated key financial figures mentioned (e.g. 'PAT ₹8,400 Cr, Revenue ₹2.4 lakh Cr')"
    )
