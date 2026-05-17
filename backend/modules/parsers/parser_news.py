"""
News Parsers (Cointelegraph, The Block, CoinDesk)
=================================================

Parsers for crypto news sources using RSS feeds.
"""

import httpx
import logging
import feedparser
from typing import Dict, List, Any
from datetime import datetime, timezone
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)

# RSS Feed URLs
RSS_FEEDS = {
    "cointelegraph": "https://cointelegraph.com/rss",
    "theblock": "https://www.theblock.co/rss.xml",
    "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
}


async def fetch_rss_feed(url: str, limit: int = 30) -> List[Dict]:
    """Fetch and parse RSS feed"""
    articles = []
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            
            if response.status_code != 200:
                logger.warning(f"RSS feed returned {response.status_code}: {url}")
                return articles
            
            feed = feedparser.parse(response.text)
            
            for entry in feed.entries[:limit]:
                article = {
                    "title": entry.get("title", ""),
                    "url": entry.get("link", ""),
                    "summary": entry.get("summary", ""),
                    "published": entry.get("published", ""),
                    "author": entry.get("author", ""),
                    "tags": [t.get("term", "") for t in entry.get("tags", [])]
                }
                articles.append(article)
                
    except Exception as e:
        logger.error(f"RSS fetch error for {url}: {e}")
    
    return articles


async def sync_cointelegraph_data(db, limit: int = 30) -> Dict[str, Any]:
    """Sync Cointelegraph news to MongoDB"""
    now = datetime.now(timezone.utc).isoformat()
    results = {
        "ok": True,
        "source": "cointelegraph",
        "articles": 0,
        "errors": []
    }
    
    try:
        articles = await fetch_rss_feed(RSS_FEEDS["cointelegraph"], limit)
        
        for item in articles:
            doc = {
                "id": f"cointelegraph_{hash(item['url']) % 10000000}",
                "source": "cointelegraph",
                "type": "news",
                "title": item["title"],
                "url": item["url"],
                "summary": item["summary"][:500] if item["summary"] else "",
                "published": item["published"],
                "author": item["author"],
                "tags": item["tags"],
                "created_at": now,
                "updated_at": now
            }
            
            await db.news_articles.update_one(
                {"id": doc["id"]},
                {"$set": doc},
                upsert=True
            )
            results["articles"] += 1
    except Exception as e:
        results["errors"].append(str(e))
    
    # Update data source status
    await db.data_sources.update_one(
        {"id": "cointelegraph"},
        {
            "$set": {
                "last_sync": now,
                "status": "active",
                "updated_at": now
            },
            "$inc": {"sync_count": 1}
        }
    )
    
    logger.info(f"[Cointelegraph] Synced: {results['articles']} articles")
    return results


async def sync_theblock_data(db, limit: int = 30) -> Dict[str, Any]:
    """Sync The Block news to MongoDB"""
    now = datetime.now(timezone.utc).isoformat()
    results = {
        "ok": True,
        "source": "theblock",
        "articles": 0,
        "errors": []
    }
    
    try:
        articles = await fetch_rss_feed(RSS_FEEDS["theblock"], limit)
        
        for item in articles:
            doc = {
                "id": f"theblock_{hash(item['url']) % 10000000}",
                "source": "theblock",
                "type": "news",
                "title": item["title"],
                "url": item["url"],
                "summary": item["summary"][:500] if item["summary"] else "",
                "published": item["published"],
                "author": item["author"],
                "tags": item["tags"],
                "created_at": now,
                "updated_at": now
            }
            
            await db.news_articles.update_one(
                {"id": doc["id"]},
                {"$set": doc},
                upsert=True
            )
            results["articles"] += 1
    except Exception as e:
        results["errors"].append(str(e))
    
    # Update data source status
    await db.data_sources.update_one(
        {"id": "theblock"},
        {
            "$set": {
                "last_sync": now,
                "status": "active",
                "updated_at": now
            },
            "$inc": {"sync_count": 1}
        }
    )
    
    logger.info(f"[The Block] Synced: {results['articles']} articles")
    return results


async def sync_coindesk_data(db, limit: int = 30) -> Dict[str, Any]:
    """Sync CoinDesk news to MongoDB"""
    now = datetime.now(timezone.utc).isoformat()
    results = {
        "ok": True,
        "source": "coindesk",
        "articles": 0,
        "errors": []
    }
    
    try:
        articles = await fetch_rss_feed(RSS_FEEDS["coindesk"], limit)
        
        for item in articles:
            doc = {
                "id": f"coindesk_{hash(item['url']) % 10000000}",
                "source": "coindesk",
                "type": "news",
                "title": item["title"],
                "url": item["url"],
                "summary": item["summary"][:500] if item["summary"] else "",
                "published": item["published"],
                "author": item["author"],
                "tags": item["tags"],
                "created_at": now,
                "updated_at": now
            }
            
            await db.news_articles.update_one(
                {"id": doc["id"]},
                {"$set": doc},
                upsert=True
            )
            results["articles"] += 1
    except Exception as e:
        results["errors"].append(str(e))
    
    # Update data source status
    await db.data_sources.update_one(
        {"id": "coindesk"},
        {
            "$set": {
                "last_sync": now,
                "status": "active",
                "updated_at": now
            },
            "$inc": {"sync_count": 1}
        }
    )
    
    logger.info(f"[CoinDesk] Synced: {results['articles']} articles")
    return results
