"""
News Pipeline — fetches RSS from all active news sources.

Reads news_sources collection (120+ active sources).
For each source with RSS URL, fetches feed, extracts articles,
deduplicates, and stores in news_articles.

Supports HTML fallback for sources without RSS.
"""

import httpx
import logging
import asyncio
import re
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

try:
    import feedparser
except ImportError:
    feedparser = None
    logger.warning("feedparser not installed, RSS parsing disabled")


def _article_id(source_id, url):
    """Deterministic article ID from source + URL."""
    return hashlib.md5(f"{source_id}:{url}".encode()).hexdigest()[:16]


def _clean_html(text):
    """Strip HTML tags from text."""
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    return soup.get_text(separator=" ", strip=True)[:1000]


def _extract_entities(text):
    """Extract crypto entity mentions from text."""
    if not text:
        return []
    # Common crypto tokens/projects
    patterns = [
        r'\b(Bitcoin|BTC|Ethereum|ETH|Solana|SOL|Cardano|ADA|Polkadot|DOT)\b',
        r'\b(Avalanche|AVAX|Chainlink|LINK|Polygon|MATIC|Uniswap|UNI)\b',
        r'\b(Aave|AAVE|Arbitrum|ARB|Optimism|OP|Cosmos|ATOM)\b',
        r'\b(Binance|Coinbase|Kraken|FTX|OpenSea|MetaMask)\b',
        r'\b(DeFi|NFT|Layer\s?2|L2|DAO|DEX|CEX)\b',
        r'\b(Tether|USDT|USDC|DAI|stablecoin)\b',
        r'\b(a16z|Paradigm|Sequoia|Multicoin|Polychain)\b',
    ]
    entities = set()
    for pat in patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        entities.update(m.strip() for m in matches)
    return sorted(entities)


async def _fetch_rss(url, timeout=20):
    """Fetch and parse a single RSS feed."""
    if not feedparser:
        return []

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; CryptoIntel/1.0)"
            })
            if resp.status_code != 200:
                return []

            feed = feedparser.parse(resp.text)
            articles = []
            for entry in feed.entries[:30]:
                articles.append({
                    "title": entry.get("title", ""),
                    "url": entry.get("link", ""),
                    "summary": _clean_html(entry.get("summary", "")),
                    "published": entry.get("published", ""),
                    "author": entry.get("author", ""),
                    "tags": [t.get("term", "") for t in entry.get("tags", [])],
                })
            return articles
    except Exception as e:
        logger.debug(f"RSS fetch error for {url}: {e}")
        return []


async def _fetch_html_fallback(url, timeout=15):
    """HTML fallback: scrape article links from a news site homepage."""
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; CryptoIntel/1.0)"
            })
            if resp.status_code != 200:
                return []

            soup = BeautifulSoup(resp.text, "html.parser")
            articles = []

            # Extract article links from common patterns
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                text = a_tag.get_text(strip=True)

                # Filter: article links usually have long text and specific URL patterns
                if len(text) < 20 or len(text) > 300:
                    continue
                if not any(p in href for p in ["/news/", "/post/", "/article/", "/blog/", "202"]):
                    continue

                # Make absolute URL
                if href.startswith("/"):
                    from urllib.parse import urljoin
                    href = urljoin(url, href)

                if href.startswith("http"):
                    articles.append({
                        "title": text,
                        "url": href,
                        "summary": "",
                        "published": "",
                        "author": "",
                        "tags": [],
                    })

            # Deduplicate by URL
            seen = set()
            unique = []
            for a in articles[:20]:
                if a["url"] not in seen:
                    seen.add(a["url"])
                    unique.append(a)

            return unique
    except Exception as e:
        logger.debug(f"HTML fallback error for {url}: {e}")
        return []


async def fetch_source(db, source):
    """Fetch articles from a single news source (RSS first, HTML fallback)."""
    source_id = source.get("id", source.get("name", "unknown"))
    rss_url = source.get("rss_url", "")
    website = source.get("url", source.get("website", ""))
    name = source.get("name", source_id)

    articles = []

    # Try RSS first
    if rss_url:
        articles = await _fetch_rss(rss_url)

    # HTML fallback if RSS failed or unavailable
    if not articles and website:
        articles = await _fetch_html_fallback(website)

    if not articles:
        return 0

    saved = 0
    now = datetime.now(timezone.utc).isoformat()

    for a in articles:
        if not a.get("url") or not a.get("title"):
            continue

        aid = _article_id(source_id, a["url"])
        text = f"{a['title']} {a['summary']}"
        entities = _extract_entities(text)

        doc = {
            "id": aid,
            "source_name": name,
            "source_id": source_id,
            "category": source.get("category", "news"),
            "tier": source.get("tier", "C"),
            "title": a["title"],
            "url": a["url"],
            "summary": a["summary"][:500],
            "published_at": a["published"],
            "author": a["author"],
            "tags": a["tags"],
            "entities_mentioned": entities,
            "entity_count": len(entities),
            "language": source.get("lang", source.get("language", "en")),
            "ingested_at": now,
        }

        result = await db.news_articles.update_one(
            {"id": aid},
            {"$set": doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        if result.upserted_id or result.modified_count:
            saved += 1

    return saved


async def run_news_pipeline(db, limit_sources=None, tiers=None):
    """
    Fetch news from all active sources.
    tiers: filter by tier (e.g., ["A", "B"])
    """
    query = {"is_active": True}
    if tiers:
        query["tier"] = {"$in": tiers}

    sources = await db.news_sources.find(query, {"_id": 0}).to_list(300)

    if limit_sources:
        sources = sources[:limit_sources]

    results = []
    total_articles = 0
    errors = 0

    # Process in batches of 5 (rate limiting)
    batch_size = 5
    for i in range(0, len(sources), batch_size):
        batch = sources[i:i + batch_size]
        tasks = [fetch_source(db, s) for s in batch]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        for s, r in zip(batch, batch_results):
            name = s.get("name", s.get("id", "?"))
            if isinstance(r, Exception):
                results.append({"name": name, "ok": False, "error": str(r)[:100]})
                errors += 1
            else:
                results.append({"name": name, "ok": True, "articles": r})
                total_articles += r

        # Small delay between batches
        if i + batch_size < len(sources):
            await asyncio.sleep(1)

    # Update source last_sync timestamps
    now = datetime.now(timezone.utc).isoformat()
    for r in results:
        if r.get("ok") and r.get("articles", 0) > 0:
            await db.news_sources.update_one(
                {"name": r["name"]},
                {"$set": {"last_sync": now, "last_articles": r["articles"]}}
            )

    return {
        "ok": True,
        "pipeline": "NEWS",
        "sources_checked": len(sources),
        "total_articles": total_articles,
        "errors": errors,
        "sources_with_articles": sum(1 for r in results if r.get("ok") and r.get("articles", 0) > 0),
    }


async def get_news_stats(db):
    """Get news pipeline statistics."""
    total_articles = await db.news_articles.count_documents({})
    total_sources = await db.news_sources.count_documents({})
    active_sources = await db.news_sources.count_documents({"is_active": True})

    # Articles by source (top 10)
    pipeline = [
        {"$group": {"_id": "$source_name", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]
    top_sources = []
    async for d in db.news_articles.aggregate(pipeline):
        top_sources.append({"source": d["_id"], "articles": d["count"]})

    # Fresh articles (last 24h)
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    fresh = await db.news_articles.count_documents({"ingested_at": {"$gte": cutoff}})

    return {
        "ok": True,
        "total_articles": total_articles,
        "total_sources": total_sources,
        "active_sources": active_sources,
        "fresh_24h": fresh,
        "top_sources": top_sources,
    }
