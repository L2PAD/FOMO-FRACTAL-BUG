"""
News Parser Data Models
=======================
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class NewsCategory(str, Enum):
    """News category types"""
    BREAKING = "breaking"
    ANALYSIS = "analysis"
    MARKET = "market"
    DEFI = "defi"
    NFT = "nft"
    REGULATION = "regulation"
    TECHNOLOGY = "technology"
    OPINION = "opinion"
    INTERVIEW = "interview"
    GENERAL = "general"


class NewsSource(BaseModel):
    """
    News source configuration.
    """
    id: str = Field(..., description="Source ID")
    name: str = Field(..., description="Display name")
    domain: str = Field(..., description="Source domain")
    
    # Feed config
    feed_url: Optional[str] = Field(None, description="RSS/Atom feed URL")
    feed_type: str = Field(default="rss", description="rss, atom, api, scrape")
    
    # Scraping config
    article_selector: Optional[str] = None
    title_selector: Optional[str] = None
    content_selector: Optional[str] = None
    date_selector: Optional[str] = None
    
    # Status
    enabled: bool = Field(default=True)
    priority: int = Field(default=1, description="Source priority for ranking")
    
    # Language
    language: str = Field(default="en")
    
    # Timestamps
    last_crawl: Optional[datetime] = None
    articles_count: int = Field(default=0)


# ═══════════════════════════════════════════════════════════════
# NEWS ARTICLE MODEL
# ═══════════════════════════════════════════════════════════════

class NewsArticle(BaseModel):
    """
    News article from crypto media.
    """
    id: str = Field(..., description="Article ID")
    
    # Content
    title: str = Field(..., description="Article title")
    content: Optional[str] = Field(None, description="Full article content")
    summary: Optional[str] = Field(None, description="Article summary")
    
    # Media
    image: Optional[str] = Field(None, description="Featured image URL")
    
    # Source
    url: str = Field(..., description="Original article URL")
    source: str = Field(..., description="Source ID")
    source_name: Optional[str] = None
    author: Optional[str] = None
    
    # Classification
    category: NewsCategory = Field(default=NewsCategory.GENERAL)
    tags: List[str] = Field(default=[])
    
    # Related entities
    mentioned_projects: List[str] = Field(default=[])
    mentioned_tokens: List[str] = Field(default=[])
    
    # Language
    language: str = Field(default="en")
    
    # Ranking
    score: float = Field(default=0.0, description="News ranking score")
    relevance_score: float = Field(default=0.0)
    recency_score: float = Field(default=0.0)
    
    # Timestamps
    published_at: Optional[datetime] = None
    crawled_at: datetime = Field(default_factory=lambda: datetime.now())


class NewsArticleCreate(BaseModel):
    """Schema for manual article creation"""
    title: str
    content: Optional[str] = None
    url: str
    source: str
    category: NewsCategory = NewsCategory.GENERAL
    tags: List[str] = []


# ═══════════════════════════════════════════════════════════════
# NEWS SOURCES REGISTRY
# ═══════════════════════════════════════════════════════════════

NEWS_SOURCES = [
    {
        "id": "incrypted",
        "name": "Incrypted",
        "domain": "incrypted.com",
        "feed_url": "https://incrypted.com/feed/",
        "feed_type": "rss",
        "language": "ru",
        "priority": 1
    },
    {
        "id": "cointelegraph",
        "name": "Cointelegraph",
        "domain": "cointelegraph.com",
        "feed_url": "https://cointelegraph.com/rss",
        "feed_type": "rss",
        "language": "en",
        "priority": 1
    },
    {
        "id": "decrypt",
        "name": "Decrypt",
        "domain": "decrypt.co",
        "feed_url": "https://decrypt.co/feed",
        "feed_type": "rss",
        "language": "en",
        "priority": 1
    },
    {
        "id": "theblock",
        "name": "The Block",
        "domain": "theblock.co",
        "feed_url": "https://www.theblock.co/rss.xml",
        "feed_type": "rss",
        "language": "en",
        "priority": 1
    },
    {
        "id": "blockworks",
        "name": "Blockworks",
        "domain": "blockworks.co",
        "feed_url": "https://blockworks.co/feed/",
        "feed_type": "rss",
        "language": "en",
        "priority": 2
    },
    {
        "id": "coindesk",
        "name": "CoinDesk",
        "domain": "coindesk.com",
        "feed_url": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "feed_type": "rss",
        "language": "en",
        "priority": 1
    }
]
