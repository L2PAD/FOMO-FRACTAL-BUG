"""
Incrypted.com Parser
====================

Parser for incrypted.com - Ukrainian crypto news and analytics portal.
Fetches news articles via RSS feed and scrapes additional content.

Features:
- RSS feed parsing for latest news
- Article content extraction
- Category detection (news, analytics, guides)
- Multi-language support (Russian/Ukrainian)
"""

import httpx
import logging
import feedparser
import re
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from bs4 import BeautifulSoup
import hashlib

logger = logging.getLogger(__name__)

# Configuration
INCRYPTED_RSS_FEED = "https://incrypted.com/feed/"
INCRYPTED_NEWS_URL = "https://incrypted.com/news/"
INCRYPTED_BASE_URL = "https://incrypted.com"

# Category mapping for event classification
CATEGORY_MAP = {
    "биткоин": "bitcoin",
    "btc": "bitcoin",
    "ethereum": "ethereum",
    "eth": "ethereum",
    "defi": "defi",
    "nft": "nft",
    "регулирование": "regulation",
    "regulation": "regulation",
    "фандрейзинг": "funding",
    "funding": "funding",
    "ai": "ai",
    "ии": "ai",
    "новости": "news",
    "news": "news",
    "стейблкоины": "stablecoins",
    "хакеры": "security",
    "безопасность": "security",
    "пресс-релизы": "press_release",
}


def generate_article_id(url: str) -> str:
    """Generate unique article ID from URL"""
    url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
    return f"incrypted_{url_hash}"


def extract_category(tags: List[str], title: str = "") -> str:
    """Extract category from tags or title"""
    text = " ".join(tags + [title]).lower()
    
    for keyword, category in CATEGORY_MAP.items():
        if keyword in text:
            return category
    
    return "news"


def parse_published_date(date_str: str) -> Optional[str]:
    """Parse published date from RSS feed"""
    try:
        # Try common RSS date formats
        formats = [
            "%a, %d %b %Y %H:%M:%S %z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S",
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.isoformat()
            except ValueError:
                continue
        
        # Fallback: use feedparser's parsed date
        return None
    except Exception:
        return None


def clean_html_content(html: str) -> str:
    """Clean HTML content, extract text"""
    if not html:
        return ""
    
    soup = BeautifulSoup(html, "html.parser")
    
    # Remove scripts and styles
    for element in soup(["script", "style", "nav", "footer"]):
        element.decompose()
    
    text = soup.get_text(separator=" ", strip=True)
    
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    return text


def extract_mentioned_projects(text: str) -> List[str]:
    """Extract mentioned crypto projects from text"""
    # Common crypto project patterns
    projects = []
    
    # Pattern for known projects
    known_projects = [
        "Bitcoin", "Ethereum", "Solana", "Cardano", "Polkadot",
        "Avalanche", "Polygon", "Arbitrum", "Optimism", "Base",
        "BNB", "Binance", "Coinbase", "Kraken", "OKX", "Bybit",
        "Tether", "USDC", "USDT", "Circle", "OpenAI", "Anthropic",
        "Monad", "Berachain", "LayerZero", "Sui", "Aptos",
        "TON", "Telegram", "dYdX", "Uniswap", "Aave",
    ]
    
    text_lower = text.lower()
    for project in known_projects:
        if project.lower() in text_lower:
            projects.append(project)
    
    return list(set(projects))


async def fetch_rss_articles(limit: int = 50) -> List[Dict]:
    """Fetch articles from Incrypted RSS feed"""
    articles = []
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                INCRYPTED_RSS_FEED,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
            
            if response.status_code != 200:
                logger.warning(f"[Incrypted] RSS feed returned {response.status_code}")
                return articles
            
            feed = feedparser.parse(response.text)
            
            for entry in feed.entries[:limit]:
                # Extract tags
                tags = [t.get("term", "") for t in entry.get("tags", [])]
                
                # Parse date
                published = entry.get("published", "")
                parsed_date = parse_published_date(published)
                if not parsed_date:
                    # Use current time as fallback
                    parsed_date = datetime.now(timezone.utc).isoformat()
                
                # Clean summary
                summary = entry.get("summary", "")
                clean_summary = clean_html_content(summary)
                
                # Extract mentioned projects
                title = entry.get("title", "")
                mentioned_projects = extract_mentioned_projects(title + " " + clean_summary)
                
                article = {
                    "title": title,
                    "url": entry.get("link", ""),
                    "summary": clean_summary[:1000] if clean_summary else "",
                    "published": published,
                    "published_iso": parsed_date,
                    "author": entry.get("author", "Incrypted"),
                    "tags": tags,
                    "category": extract_category(tags, title),
                    "mentioned_projects": mentioned_projects,
                }
                
                articles.append(article)
            
            logger.info(f"[Incrypted] Fetched {len(articles)} articles from RSS")
            
    except Exception as e:
        logger.error(f"[Incrypted] RSS fetch error: {e}")
    
    return articles


async def fetch_article_content(url: str) -> Optional[Dict]:
    """Fetch full article content from URL"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
            
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Find article content
            content_div = soup.find("article") or soup.find(class_="post-content")
            
            if content_div:
                # Extract text
                content_text = clean_html_content(str(content_div))
                
                # Find featured image
                img = content_div.find("img")
                image_url = img.get("src") if img else None
                
                return {
                    "full_content": content_text[:5000],
                    "image_url": image_url,
                }
            
            return None
            
    except Exception as e:
        logger.error(f"[Incrypted] Article fetch error for {url}: {e}")
        return None


async def sync_incrypted_data(db, limit: int = 50) -> Dict[str, Any]:
    """
    Sync Incrypted news data to MongoDB.
    
    Main sync function that:
    1. Fetches RSS feed
    2. Stores articles in news_articles collection
    3. Creates intel_events for Data Fusion Engine
    4. Updates data source status
    """
    now = datetime.now(timezone.utc).isoformat()
    results = {
        "ok": True,
        "source": "incrypted",
        "articles": 0,
        "events_created": 0,
        "errors": []
    }
    
    try:
        # Fetch RSS articles
        articles = await fetch_rss_articles(limit)
        
        for article in articles:
            article_id = generate_article_id(article["url"])
            
            # Store article in news_articles collection
            doc = {
                "id": article_id,
                "source": "incrypted",
                "source_name": "Incrypted",
                "type": "news",
                "title": article["title"],
                "url": article["url"],
                "summary": article["summary"],
                "published": article["published"],
                "published_iso": article["published_iso"],
                "author": article["author"],
                "tags": article["tags"],
                "category": article["category"],
                "mentioned_projects": article["mentioned_projects"],
                "language": "ru",  # Russian/Ukrainian
                "created_at": now,
                "updated_at": now
            }
            
            await db.news_articles.update_one(
                {"id": article_id},
                {"$set": doc},
                upsert=True
            )
            results["articles"] += 1
            
            # Create intel_event for Data Fusion Engine
            event_doc = {
                "id": f"event_{article_id}",
                "source": "incrypted",
                "type": "news",
                "title": article["title"],
                "description": article["summary"][:500] if article["summary"] else "",
                "url": article["url"],
                "date": article["published_iso"],
                "category": article["category"],
                "entities": article["mentioned_projects"],
                "impact_score": calculate_impact_score(article),
                "confidence": 0.85,  # High confidence for direct RSS source
                "raw_data": {
                    "tags": article["tags"],
                    "author": article["author"],
                },
                "created_at": now,
                "updated_at": now
            }
            
            await db.intel_events.update_one(
                {"id": event_doc["id"]},
                {"$set": event_doc},
                upsert=True
            )
            results["events_created"] += 1
        
        # Update data source status
        await db.data_sources.update_one(
            {"id": "incrypted"},
            {
                "$set": {
                    "last_sync": now,
                    "last_sync_status": "success",
                    "status": "active",
                    "updated_at": now
                },
                "$inc": {"sync_count": 1}
            }
        )
        
        logger.info(f"[Incrypted] Synced: {results['articles']} articles, {results['events_created']} events")
        
    except Exception as e:
        results["ok"] = False
        results["errors"].append(str(e))
        logger.error(f"[Incrypted] Sync error: {e}")
        
        # Update data source with error status
        await db.data_sources.update_one(
            {"id": "incrypted"},
            {
                "$set": {
                    "last_sync_status": "error",
                    "last_error": str(e),
                    "updated_at": now
                },
                "$inc": {"error_count": 1}
            }
        )
    
    return results


def calculate_impact_score(article: Dict) -> float:
    """
    Calculate impact score for article based on various factors.
    
    Factors:
    - Number of mentioned projects
    - Category importance
    - Tag relevance
    """
    score = 0.5  # Base score
    
    # Boost for mentioned projects
    mentioned = len(article.get("mentioned_projects", []))
    if mentioned > 0:
        score += min(mentioned * 0.05, 0.2)
    
    # Boost for important categories
    category = article.get("category", "news")
    category_boosts = {
        "funding": 0.15,
        "regulation": 0.12,
        "security": 0.10,
        "bitcoin": 0.08,
        "ethereum": 0.08,
        "defi": 0.05,
    }
    score += category_boosts.get(category, 0)
    
    # Boost for specific tags indicating importance
    tags = article.get("tags", [])
    important_tags = ["важное", "срочно", "breaking", "exclusive"]
    for tag in tags:
        if any(imp in tag.lower() for imp in important_tags):
            score += 0.1
            break
    
    return min(score, 1.0)


class IncryptedParser:
    """
    Incrypted.com Parser class for advanced usage.
    
    Provides methods for:
    - RSS feed parsing
    - Full article content extraction
    - Category analysis
    - Project mention detection
    """
    
    def __init__(self, db):
        self.db = db
        self.client = None
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()
    
    async def fetch_latest_news(self, limit: int = 30) -> List[Dict]:
        """Fetch latest news from RSS"""
        return await fetch_rss_articles(limit)
    
    async def get_article_details(self, url: str) -> Optional[Dict]:
        """Get full article content"""
        return await fetch_article_content(url)
    
    async def sync_to_database(self, limit: int = 50) -> Dict[str, Any]:
        """Sync news to database"""
        return await sync_incrypted_data(self.db, limit)
