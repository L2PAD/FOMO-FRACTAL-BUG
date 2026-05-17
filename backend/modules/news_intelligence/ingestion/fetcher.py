"""
News Fetcher
============

Fetches articles from RSS feeds and other sources.
With Parser Sandbox, Validation, and Health Monitoring.
"""

import httpx
import feedparser
import hashlib
import logging
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from bs4 import BeautifulSoup

from ..models import RawArticle, NewsSource, SourceType
from .sandbox import get_sandbox, SandboxStatus
from .validator import get_validator
from .health import get_health_monitor

logger = logging.getLogger(__name__)


class NewsFetcher:
    """Fetches news from configured sources."""
    
    def __init__(self, db):
        self.db = db
        self.client = None
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 FOMO/2.0"
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()
    
    def _generate_article_id(self, url: str, source_id: str) -> str:
        """Generate unique article ID."""
        hash_input = f"{source_id}:{url}"
        return f"art_{hashlib.md5(hash_input.encode()).hexdigest()[:16]}"
    
    def _generate_content_hash(self, title: str, content: str = "") -> str:
        """Generate content hash for dedup."""
        text = f"{title}:{content[:500] if content else ''}"
        return hashlib.md5(text.lower().encode()).hexdigest()
    
    def _parse_rss_date(self, date_str: str) -> Optional[str]:
        """Parse RSS date string."""
        if not date_str:
            return None
        
        formats = [
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S %Z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.isoformat()
            except ValueError:
                continue
        
        return None
    
    def _clean_html(self, html: str) -> str:
        """Extract clean text from HTML."""
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "aside"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        return " ".join(text.split())[:5000]
    
    async def fetch_rss_source(self, source: NewsSource) -> List[RawArticle]:
        """Fetch articles from RSS feed."""
        articles = []
        
        if not source.rss_url:
            return articles
        
        try:
            response = await self.client.get(source.rss_url)
            
            if response.status_code != 200:
                logger.warning(f"[Fetcher] {source.name} RSS returned {response.status_code}")
                return articles
            
            feed = feedparser.parse(response.text)
            now = datetime.now(timezone.utc)
            
            for entry in feed.entries[:30]:
                url = entry.get("link", "")
                if not url:
                    continue
                
                title = entry.get("title", "").strip()
                if not title:
                    continue
                
                # Get content
                content = ""
                if entry.get("content"):
                    content = entry.content[0].get("value", "")
                elif entry.get("summary"):
                    content = entry.summary
                elif entry.get("description"):
                    content = entry.description
                
                clean_content = self._clean_html(content)
                
                # Tags
                tags = [t.get("term", "") for t in entry.get("tags", [])]
                
                # Author
                author = entry.get("author", "")
                
                # Image - try multiple sources
                image_url = None
                if entry.get("media_content"):
                    image_url = entry.media_content[0].get("url")
                elif entry.get("media_thumbnail"):
                    image_url = entry.media_thumbnail[0].get("url")
                elif entry.get("links"):
                    # Check for image in links
                    for link in entry.links:
                        if link.get("type", "").startswith("image/"):
                            image_url = link.get("href")
                            break
                
                # Try to extract from content if no media found
                if not image_url and content:
                    soup = BeautifulSoup(content, "html.parser")
                    img_tag = soup.find("img")
                    if img_tag and img_tag.get("src"):
                        img_src = img_tag.get("src")
                        if img_src.startswith("http"):
                            image_url = img_src
                
                # Try enclosures (podcasts, images)
                if not image_url and entry.get("enclosures"):
                    for enc in entry.enclosures:
                        if enc.get("type", "").startswith("image/"):
                            image_url = enc.get("url") or enc.get("href")
                            break
                
                # Published date
                published = entry.get("published", entry.get("updated", ""))
                
                article = RawArticle(
                    id=self._generate_article_id(url, source.id),
                    source_id=source.id,
                    source_name=source.name,
                    url=url,
                    external_id=entry.get("id", ""),
                    title_raw=title,
                    content_raw=clean_content,
                    html_raw=content[:10000] if content else None,
                    author_raw=author,
                    published_at_raw=published,
                    image_url_raw=image_url,
                    language_detected=source.language,
                    tags_raw=tags,
                    fetched_at=now,
                    content_hash=self._generate_content_hash(title, clean_content),
                    status="pending"
                )
                
                articles.append(article)
            
            logger.info(f"[Fetcher] {source.name}: fetched {len(articles)} articles")
            
        except Exception as e:
            logger.error(f"[Fetcher] {source.name} error: {e}")
            # Update error count
            await self.db.news_sources.update_one(
                {"id": source.id},
                {"$inc": {"error_count": 1}}
            )
        
        return articles
    
    async def fetch_source(self, source: NewsSource) -> List[RawArticle]:
        """Fetch articles from a source based on its type."""
        if source.source_type == SourceType.RSS:
            return await self.fetch_rss_source(source)
        # TODO: Add API and HTML fetchers
        return []
    
    async def fetch_all_sources(self, sources: List[NewsSource]) -> Dict[str, Any]:
        """Fetch from all sources with sandbox isolation and health monitoring."""
        from .sources import get_active_sources
        
        if not sources:
            sources = get_active_sources()
        
        sandbox = get_sandbox()
        validator = get_validator()
        health_monitor = get_health_monitor()
        
        results = {
            "ok": True,
            "sources_fetched": 0,
            "sources_skipped": 0,
            "articles_total": 0,
            "articles_new": 0,
            "articles_valid": 0,
            "articles_invalid": 0,
            "errors": [],
            "health_summary": {}
        }
        
        for source in sources:
            if not source.is_active:
                continue
            
            # Check if source is available (not paused)
            if not health_monitor.is_source_available(source.id):
                logger.info(f"[Fetcher] Skipping paused source: {source.name}")
                results["sources_skipped"] += 1
                continue
            
            start_time = time.time()
            
            try:
                # Execute in sandbox
                sandbox_result = await sandbox.execute(
                    source.id,
                    self.fetch_source,
                    source
                )
                
                latency_ms = (time.time() - start_time) * 1000
                
                if sandbox_result.status == SandboxStatus.SUCCESS:
                    articles = sandbox_result.articles or []
                    results["sources_fetched"] += 1
                    results["articles_total"] += len(articles)
                    
                    # Record successful fetch
                    health_monitor.record_fetch(
                        source.id,
                        source.name,
                        success=True,
                        articles_count=len(articles),
                        latency_ms=latency_ms
                    )
                    
                    # Validate and store articles
                    for article in articles:
                        # Validate article
                        validation_result = validator.validate(article.model_dump())
                        validator.update_source_stats(source.id, validation_result)
                        health_monitor.record_validation(
                            source.id,
                            validation_result.is_valid,
                            validation_result.confidence
                        )
                        
                        if not validation_result.is_valid:
                            results["articles_invalid"] += 1
                            logger.debug(f"[Fetcher] Invalid article: {validation_result.issues}")
                            continue
                        
                        results["articles_valid"] += 1
                        
                        # Check if exists
                        existing = await self.db.raw_articles.find_one({"id": article.id})
                        if not existing:
                            await self.db.raw_articles.insert_one(article.model_dump())
                            results["articles_new"] += 1
                    
                    # Update source last_fetch
                    await self.db.news_sources.update_one(
                        {"id": source.id},
                        {"$set": {"last_fetch": datetime.now(timezone.utc).isoformat()}}
                    )
                    
                    # Check for parser drift
                    if validator.detect_parser_drift(source.id):
                        logger.warning(f"[Fetcher] Parser drift detected for {source.name}")
                
                elif sandbox_result.status == SandboxStatus.TIMEOUT:
                    health_monitor.record_fetch(
                        source.id,
                        source.name,
                        success=False,
                        latency_ms=latency_ms,
                        error_message=sandbox_result.error_message,
                        is_timeout=True
                    )
                    results["errors"].append(f"{source.name}: timeout")
                
                else:
                    health_monitor.record_fetch(
                        source.id,
                        source.name,
                        success=False,
                        latency_ms=latency_ms,
                        error_message=sandbox_result.error_message
                    )
                    results["errors"].append(f"{source.name}: {sandbox_result.error_message}")
                
            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                health_monitor.record_fetch(
                    source.id,
                    source.name,
                    success=False,
                    latency_ms=latency_ms,
                    error_message=str(e)
                )
                results["errors"].append(f"{source.name}: {str(e)}")
                logger.error(f"[Fetcher] Error fetching {source.name}: {e}")
        
        # Add health summary
        results["health_summary"] = health_monitor.get_summary()
        
        return results
    
    async def store_raw_article(self, article: RawArticle) -> bool:
        """Store raw article if not duplicate."""
        existing = await self.db.raw_articles.find_one({
            "$or": [
                {"id": article.id},
                {"content_hash": article.content_hash}
            ]
        })
        
        if existing:
            return False
        
        await self.db.raw_articles.insert_one(article.model_dump())
        return True
