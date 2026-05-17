"""
News Parser
===========

Parses news articles from RSS feeds and web pages.
"""

import re
import hashlib
import logging
import feedparser
import httpx
from typing import List, Optional, Dict
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from motor.motor_asyncio import AsyncIOMotorDatabase

from .models import (
    NewsArticle, NewsSource, NewsCategory, 
    NEWS_SOURCES
)

logger = logging.getLogger(__name__)


# Keywords for category detection
CATEGORY_KEYWORDS = {
    NewsCategory.DEFI: ["defi", "yield", "lending", "amm", "liquidity", "staking"],
    NewsCategory.NFT: ["nft", "opensea", "blur", "collectible", "pfp"],
    NewsCategory.REGULATION: ["sec", "regulation", "lawsuit", "legal", "congress", "ban"],
    NewsCategory.MARKET: ["price", "bull", "bear", "rally", "dump", "ath", "breakout"],
    NewsCategory.TECHNOLOGY: ["upgrade", "fork", "layer", "scaling", "ethereum", "solana"],
    NewsCategory.BREAKING: ["breaking", "just in", "urgent"],
}

# Token patterns for entity extraction
TOKEN_PATTERN = re.compile(r'\b(BTC|ETH|SOL|DOGE|XRP|ADA|AVAX|MATIC|DOT|LINK|UNI|AAVE)\b', re.IGNORECASE)
PROJECT_KEYWORDS = ["bitcoin", "ethereum", "solana", "polygon", "arbitrum", "optimism", "avalanche"]


class NewsParser:
    """
    News article parser.
    Supports RSS feeds and HTML scraping.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.articles = db.news_articles
        self.sources = db.news_sources
    
    # ═══════════════════════════════════════════════════════════════
    # SOURCE MANAGEMENT
    # ═══════════════════════════════════════════════════════════════
    
    async def initialize_sources(self) -> dict:
        """Initialize default news sources"""
        created = 0
        
        for source_data in NEWS_SOURCES:
            existing = await self.sources.find_one({"id": source_data["id"]})
            if not existing:
                now = datetime.now(timezone.utc)
                doc = {
                    **source_data,
                    "enabled": True,
                    "last_crawl": None,
                    "articles_count": 0,
                    "created_at": now.isoformat()
                }
                await self.sources.insert_one(doc)
                created += 1
        
        return {"ok": True, "created": created, "total": len(NEWS_SOURCES)}
    
    async def get_sources(self, enabled_only: bool = True) -> List[dict]:
        """Get news sources"""
        query = {"enabled": True} if enabled_only else {}
        sources = []
        cursor = self.sources.find(query, {"_id": 0}).sort("priority", 1)
        async for source in cursor:
            sources.append(source)
        return sources
    
    async def get_source(self, source_id: str) -> Optional[dict]:
        """Get source by ID"""
        source = await self.sources.find_one({"id": source_id}, {"_id": 0})
        return source
    
    # ═══════════════════════════════════════════════════════════════
    # RSS PARSING
    # ═══════════════════════════════════════════════════════════════
    
    async def parse_rss_feed(self, source_id: str) -> dict:
        """Parse RSS feed for a source"""
        source = await self.get_source(source_id)
        if not source:
            return {"ok": False, "error": "Source not found"}
        
        feed_url = source.get("feed_url")
        if not feed_url:
            return {"ok": False, "error": "No feed URL configured"}
        
        try:
            # Fetch feed
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(feed_url)
                feed_content = response.text
            
            # Parse feed
            feed = feedparser.parse(feed_content)
            
            articles_created = 0
            articles_updated = 0
            
            for entry in feed.entries:
                article = self._parse_feed_entry(entry, source)
                
                if article:
                    # Check if exists
                    existing = await self.articles.find_one({"url": article.url})
                    
                    if existing:
                        articles_updated += 1
                    else:
                        # Save article
                        await self._save_article(article)
                        articles_created += 1
            
            # Update source
            await self.sources.update_one(
                {"id": source_id},
                {"$set": {
                    "last_crawl": datetime.now(timezone.utc).isoformat()
                },
                "$inc": {"articles_count": articles_created}}
            )
            
            return {
                "ok": True,
                "source": source_id,
                "created": articles_created,
                "updated": articles_updated,
                "total_entries": len(feed.entries)
            }
            
        except Exception as e:
            logger.error(f"RSS parse error for {source_id}: {e}")
            return {"ok": False, "error": str(e)}
    
    def _parse_feed_entry(self, entry: dict, source: dict) -> Optional[NewsArticle]:
        """Parse single RSS entry into NewsArticle"""
        try:
            # Generate ID
            url = entry.get("link", "")
            article_id = hashlib.md5(url.encode()).hexdigest()[:16]
            
            # Get title
            title = entry.get("title", "").strip()
            if not title:
                return None
            
            # Get content
            content = ""
            if entry.get("content"):
                content = entry.content[0].get("value", "")
            elif entry.get("summary"):
                content = entry.summary
            elif entry.get("description"):
                content = entry.description
            
            # Clean content
            content = self._clean_html(content)
            
            # Get summary (first 500 chars)
            summary = content[:500] + "..." if len(content) > 500 else content
            
            # Get image
            image = None
            if entry.get("media_content"):
                image = entry.media_content[0].get("url")
            elif entry.get("media_thumbnail"):
                image = entry.media_thumbnail[0].get("url")
            
            # Parse date
            published_at = None
            if entry.get("published_parsed"):
                published_at = datetime(*entry.published_parsed[:6])
            elif entry.get("updated_parsed"):
                published_at = datetime(*entry.updated_parsed[:6])
            
            # Get author
            author = entry.get("author")
            
            # Detect category
            category = self._detect_category(title + " " + content)
            
            # Extract tags
            tags = []
            if entry.get("tags"):
                tags = [t.get("term", "") for t in entry.tags if t.get("term")]
            
            # Extract mentioned entities
            mentioned_tokens = TOKEN_PATTERN.findall(title + " " + content)
            mentioned_tokens = list(set([t.upper() for t in mentioned_tokens]))
            
            mentioned_projects = []
            text_lower = (title + " " + content).lower()
            for project in PROJECT_KEYWORDS:
                if project in text_lower:
                    mentioned_projects.append(project)
            
            return NewsArticle(
                id=article_id,
                title=title,
                content=content,
                summary=summary,
                image=image,
                url=url,
                source=source["id"],
                source_name=source["name"],
                author=author,
                category=category,
                tags=tags,
                mentioned_projects=mentioned_projects,
                mentioned_tokens=mentioned_tokens,
                language=source.get("language", "en"),
                published_at=published_at,
                crawled_at=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            logger.error(f"Entry parse error: {e}")
            return None
    
    def _clean_html(self, html: str) -> str:
        """Clean HTML and extract text"""
        if not html:
            return ""
        
        soup = BeautifulSoup(html, "html.parser")
        
        # Remove scripts and styles
        for tag in soup(["script", "style", "iframe"]):
            tag.decompose()
        
        # Get text
        text = soup.get_text(separator=" ")
        
        # Clean whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def _detect_category(self, text: str) -> NewsCategory:
        """Detect article category from text"""
        text_lower = text.lower()
        
        scores = {}
        for category, keywords in CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[category] = score
        
        if scores:
            return max(scores, key=scores.get)
        
        return NewsCategory.GENERAL
    
    async def _save_article(self, article: NewsArticle) -> None:
        """Save article to database"""
        doc = {
            "id": article.id,
            "title": article.title,
            "content": article.content,
            "summary": article.summary,
            "image": article.image,
            "url": article.url,
            "source": article.source,
            "source_name": article.source_name,
            "author": article.author,
            "category": article.category.value,
            "tags": article.tags,
            "mentioned_projects": article.mentioned_projects,
            "mentioned_tokens": article.mentioned_tokens,
            "language": article.language,
            "score": article.score,
            "relevance_score": article.relevance_score,
            "recency_score": article.recency_score,
            "published_at": article.published_at.isoformat() if article.published_at else None,
            "crawled_at": article.crawled_at.isoformat() if article.crawled_at else None
        }
        
        await self.articles.update_one(
            {"id": article.id},
            {"$set": doc},
            upsert=True
        )
    
    # ═══════════════════════════════════════════════════════════════
    # ARTICLE QUERIES
    # ═══════════════════════════════════════════════════════════════
    
    async def get_articles(
        self,
        source: Optional[str] = None,
        category: Optional[str] = None,
        language: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> dict:
        """Get news articles with filters"""
        query = {}
        if source:
            query["source"] = source
        if category:
            query["category"] = category
        if language:
            query["language"] = language
        
        total = await self.articles.count_documents(query)
        
        articles = []
        cursor = self.articles.find(query, {"_id": 0}).sort("published_at", -1).skip(offset).limit(limit)
        async for article in cursor:
            articles.append(article)
        
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "articles": articles
        }
    
    async def get_article(self, article_id: str) -> Optional[dict]:
        """Get article by ID"""
        article = await self.articles.find_one({"id": article_id}, {"_id": 0})
        return article
    
    async def search_articles(self, query: str, limit: int = 20) -> List[dict]:
        """Search articles by text"""
        # Simple text search
        regex = re.compile(re.escape(query), re.IGNORECASE)
        
        articles = []
        cursor = self.articles.find(
            {"$or": [
                {"title": {"$regex": regex}},
                {"content": {"$regex": regex}},
                {"tags": {"$regex": regex}}
            ]},
            {"_id": 0}
        ).sort("published_at", -1).limit(limit)
        
        async for article in cursor:
            articles.append(article)
        
        return articles
    
    # ═══════════════════════════════════════════════════════════════
    # CRAWL ALL SOURCES
    # ═══════════════════════════════════════════════════════════════
    
    async def crawl_all_sources(self) -> dict:
        """Crawl all enabled news sources"""
        sources = await self.get_sources(enabled_only=True)
        
        results = {}
        total_created = 0
        
        for source in sources:
            result = await self.parse_rss_feed(source["id"])
            results[source["id"]] = result
            if result.get("ok"):
                total_created += result.get("created", 0)
        
        return {
            "ok": True,
            "sources_crawled": len(sources),
            "total_articles_created": total_created,
            "results": results
        }
    
    # ═══════════════════════════════════════════════════════════════
    # STATISTICS
    # ═══════════════════════════════════════════════════════════════
    
    async def get_stats(self) -> dict:
        """Get news statistics"""
        total = await self.articles.count_documents({})
        
        # By source
        sources_pipeline = [
            {"$group": {"_id": "$source", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        by_source = {}
        async for doc in self.articles.aggregate(sources_pipeline):
            by_source[doc["_id"]] = doc["count"]
        
        # By category
        categories_pipeline = [
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        by_category = {}
        async for doc in self.articles.aggregate(categories_pipeline):
            by_category[doc["_id"]] = doc["count"]
        
        # By language
        languages_pipeline = [
            {"$group": {"_id": "$language", "count": {"$sum": 1}}}
        ]
        by_language = {}
        async for doc in self.articles.aggregate(languages_pipeline):
            by_language[doc["_id"]] = doc["count"]
        
        return {
            "total_articles": total,
            "articles_by_source": by_source,
            "articles_by_category": by_category,
            "articles_by_language": by_language
        }
