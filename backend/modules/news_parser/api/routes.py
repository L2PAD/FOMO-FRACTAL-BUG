"""
News Parser API Routes
======================
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from datetime import datetime, timezone
import os

from motor.motor_asyncio import AsyncIOMotorClient

from ..parser import NewsParser
from ..ranker import NewsRanker

router = APIRouter(prefix="/api/news", tags=["News"])

# Database connection
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'test_database')]

# Services
parser = NewsParser(db)
ranker = NewsRanker(db)


# ═══════════════════════════════════════════════════════════════
# NEWS SOURCES
# ═══════════════════════════════════════════════════════════════

@router.post("/sources/initialize")
async def initialize_sources():
    """Initialize default news sources"""
    result = await parser.initialize_sources()
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **result
    }


@router.get("/sources")
async def list_sources(enabled_only: bool = True):
    """List news sources"""
    sources = await parser.get_sources(enabled_only)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "total": len(sources),
        "sources": sources
    }


@router.get("/sources/{source_id}")
async def get_source(source_id: str):
    """Get news source by ID"""
    source = await parser.get_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "source": source
    }


# ═══════════════════════════════════════════════════════════════
# CRAWLING
# ═══════════════════════════════════════════════════════════════

@router.post("/crawl/{source_id}")
async def crawl_source(source_id: str):
    """Crawl specific news source"""
    result = await parser.parse_rss_feed(source_id)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **result
    }


@router.post("/crawl")
async def crawl_all():
    """Crawl all enabled news sources"""
    result = await parser.crawl_all_sources()
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **result
    }


# ═══════════════════════════════════════════════════════════════
# NEWS FEED
# ═══════════════════════════════════════════════════════════════

@router.get("/feed")
async def get_news_feed(
    source: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """
    Get news feed.
    
    Filters:
    - source: incrypted, cointelegraph, decrypt, etc.
    - category: breaking, market, defi, regulation, etc.
    - language: en, ru
    """
    result = await parser.get_articles(source, category, language, limit, offset)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **result
    }


@router.get("/feed/top")
async def get_top_news(limit: int = Query(20, ge=1, le=100)):
    """Get top ranked news articles"""
    articles = await ranker.get_top_news(limit)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "total": len(articles),
        "articles": articles
    }


@router.get("/feed/trending")
async def get_trending_topics(limit: int = Query(10, ge=1, le=50)):
    """Get trending topics from recent news"""
    topics = await ranker.get_trending_topics(limit)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "topics": topics
    }


# ═══════════════════════════════════════════════════════════════
# ARTICLES
# ═══════════════════════════════════════════════════════════════

@router.get("/articles/{article_id}")
async def get_article(article_id: str):
    """Get article by ID"""
    article = await parser.get_article(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "article": article
    }


@router.get("/search")
async def search_articles(
    q: str = Query(..., min_length=2),
    limit: int = Query(20, ge=1, le=100)
):
    """Search news articles"""
    articles = await parser.search_articles(q, limit)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "query": q,
        "total": len(articles),
        "articles": articles
    }


# ═══════════════════════════════════════════════════════════════
# RANKING
# ═══════════════════════════════════════════════════════════════

@router.post("/rank")
async def rank_all_articles():
    """Recalculate ranking for all articles"""
    result = await ranker.rank_all_articles()
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **result
    }


# ═══════════════════════════════════════════════════════════════
# STATISTICS
# ═══════════════════════════════════════════════════════════════

@router.get("/stats")
async def get_news_stats():
    """Get news statistics"""
    stats = await parser.get_stats()
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **stats
    }
