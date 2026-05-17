"""
RSS Ingestion Pipeline — Sprint 3
===================================

1. Fetch articles from active RSS news sources
2. Store in news_articles collection
3. Extract entity mentions → link to graph entities
4. Rate-limited, parallel-safe

Target: 1k-5k articles from 120 sources
"""

import asyncio
import os
import sys
import re
import time
import logging
import hashlib
import feedparser
import httpx
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from html import unescape

from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("RSSPipeline")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
DB_NAME = os.environ.get("DB_NAME", "intelligence_engine")

# Entity keywords for extraction
CRYPTO_ENTITIES = {
    "bitcoin": "bitcoin", "btc": "bitcoin", "ethereum": "ethereum", "eth": "ethereum",
    "solana": "solana", "sol": "solana", "cardano": "cardano", "ada": "cardano",
    "polkadot": "polkadot", "dot": "polkadot", "avalanche": "avalanche", "avax": "avalanche",
    "polygon": "polygon", "matic": "polygon", "chainlink": "chainlink", "link": "chainlink",
    "uniswap": "uniswap", "uni": "uniswap", "aave": "aave", "maker": "maker", "mkr": "maker",
    "compound": "compound", "comp": "compound", "curve": "curve-finance", "crv": "curve-finance",
    "lido": "lido", "arbitrum": "arbitrum", "arb": "arbitrum", "optimism": "optimism", "op": "optimism",
    "base": "base", "sui": "sui", "aptos": "aptos", "apt": "aptos", "near": "near",
    "cosmos": "cosmos", "atom": "cosmos", "celestia": "celestia", "tia": "celestia",
    "starknet": "starknet", "zksync": "zksync", "eigenlayer": "eigenlayer",
    "pendle": "pendle", "gmx": "gmx", "synthetix": "synthetix", "snx": "synthetix",
    "dydx": "dydx", "injective": "injective", "inj": "injective", "sei": "sei",
    "mantle": "mantle", "mnt": "mantle", "blast": "blast", "scroll": "scroll",
    "linea": "linea", "berachain": "berachain", "monad": "monad",
    "binance": "binance", "bnb": "binance", "coinbase": "coinbase", "kraken": "kraken",
    "okx": "okx", "bybit": "bybit", "tether": "tether", "usdt": "tether",
    "usdc": "usdc", "circle": "usdc", "ripple": "ripple", "xrp": "ripple",
    "dogecoin": "dogecoin", "doge": "dogecoin", "shiba": "shiba-inu", "shib": "shiba-inu",
    "litecoin": "litecoin", "ltc": "litecoin", "tron": "tron", "trx": "tron",
    # VCs
    "a16z": "a16z", "andreessen": "a16z", "paradigm": "paradigm", "polychain": "polychain",
    "pantera": "pantera", "dragonfly": "dragonfly", "multicoin": "multicoin",
    "galaxy digital": "galaxy", "sequoia": "sequoia", "coinbase ventures": "coinbase-ventures",
    "binance labs": "binance-labs", "jump crypto": "jump-crypto", "framework ventures": "framework",
}

# Compiled regex for entity extraction (word boundaries)
ENTITY_PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(k) for k in sorted(CRYPTO_ENTITIES.keys(), key=len, reverse=True)) + r')\b',
    re.IGNORECASE
)


def clean_html(text):
    """Strip HTML tags and decode entities"""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:2000]  # Cap at 2000 chars


def extract_entities(text):
    """Extract crypto entity mentions from text"""
    if not text:
        return []
    matches = ENTITY_PATTERN.findall(text.lower())
    entities = list(set(CRYPTO_ENTITIES[m.lower()] for m in matches if m.lower() in CRYPTO_ENTITIES))
    return entities


def parse_date(entry):
    """Parse RSS entry date"""
    for field in ['published_parsed', 'updated_parsed']:
        parsed = entry.get(field)
        if parsed:
            try:
                from time import mktime
                return datetime.fromtimestamp(mktime(parsed), tz=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)


async def fetch_rss_feed(client, source, timeout=15):
    """Fetch and parse a single RSS feed"""
    src_id = source.get("id", "?")
    rss_url = source.get("rss_url")
    if not rss_url:
        logger.warning(f"[FETCH] {src_id}: no rss_url field, SKIP")
        return []
    
    try:
        resp = await client.get(rss_url, timeout=timeout, follow_redirects=True)
        if resp.status_code != 200:
            logger.warning(f"[FETCH] {src_id}: HTTP {resp.status_code} from {rss_url}")
            return []
        
        feed = feedparser.parse(resp.text)
        raw_count = len(feed.entries) if feed.entries else 0
        if not feed.entries:
            logger.warning(f"[FETCH] {src_id}: 0 entries in feed (bozo={feed.bozo})")
            return []
        
        articles = []
        skipped_no_title = 0
        for entry in feed.entries[:30]:  # Max 30 per source
            title = clean_html(entry.get("title", ""))
            summary = clean_html(entry.get("summary", "") or entry.get("description", ""))
            link = entry.get("link", "")
            pub_date = parse_date(entry)
            
            if not title:
                skipped_no_title += 1
                continue
            
            full_text = f"{title} {summary}"
            entities = extract_entities(full_text)
            
            article_id = hashlib.md5(f"{source['id']}:{link or title}".encode()).hexdigest()
            
            articles.append({
                "id": article_id,
                "source_id": source["id"],
                "source_name": source["name"],
                "source_tier": source.get("tier", "D"),
                "title": title,
                "summary": summary[:500],
                "url": link,
                "language": source.get("language", "en"),
                "category": source.get("category", "news"),
                "entities_mentioned": entities,
                "entity_count": len(entities),
                "published_at": pub_date,
                "ingested_at": datetime.now(timezone.utc),
            })
        
        logger.info(f"[FETCH] {src_id}: raw={raw_count}, parsed={len(articles)}, skipped_no_title={skipped_no_title}")
        return articles
    except httpx.TimeoutException:
        logger.warning(f"[FETCH] {src_id}: TIMEOUT {rss_url}")
        return []
    except Exception as e:
        logger.warning(f"[FETCH] {src_id}: ERROR {type(e).__name__}: {e}")
        return []


async def run_rss_ingestion(db, max_sources=120, batch_size=10):
    """Fetch RSS articles from all active sources"""
    logger.info(f"[RSS] Starting ingestion from up to {max_sources} sources...")
    
    # Check what query returns
    total_in_db = await db.news_sources.count_documents({})
    active_count = await db.news_sources.count_documents({"is_active": True})
    logger.info(f"[RSS] DB has {total_in_db} total sources, {active_count} with is_active=True")
    
    sources = await db.news_sources.find(
        {"is_active": True},
        {"_id": 0}
    ).sort("weight", -1).limit(max_sources).to_list(max_sources)
    
    logger.info(f"[RSS] Loaded {len(sources)} sources for processing")
    
    # Log how many have rss_url
    with_url = sum(1 for s in sources if s.get("rss_url"))
    without_url = sum(1 for s in sources if not s.get("rss_url"))
    logger.info(f"[RSS] Sources with rss_url: {with_url}, without: {without_url}")
    
    total_articles = 0
    total_new = 0
    total_updated = 0
    sources_ok = 0
    sources_failed = 0
    sources_empty = 0
    
    # Track articles before
    articles_before = await db.news_articles.count_documents({})
    
    async with httpx.AsyncClient(
        timeout=15,
        headers={"User-Agent": "Mozilla/5.0 (compatible; IntelligenceBot/1.0)"},
        follow_redirects=True
    ) as client:
        # Process in batches
        for i in range(0, len(sources), batch_size):
            batch = sources[i:i + batch_size]
            tasks = [fetch_rss_feed(client, s) for s in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            batch_articles = 0
            batch_new = 0
            for source, result in zip(batch, results):
                if isinstance(result, Exception):
                    sources_failed += 1
                    logger.warning(f"[SAVE] {source.get('id','?')}: EXCEPTION {type(result).__name__}: {result}")
                    continue
                
                if not result:
                    sources_empty += 1
                    continue
                
                sources_ok += 1
                for article in result:
                    res = await db.news_articles.update_one(
                        {"id": article["id"]},
                        {"$set": article},
                        upsert=True
                    )
                    total_articles += 1
                    batch_articles += 1
                    if res.upserted_id:
                        total_new += 1
                        batch_new += 1
                    elif res.modified_count > 0:
                        total_updated += 1
                
                # Update source status
                await db.news_sources.update_one(
                    {"id": source["id"]},
                    {"$set": {
                        "last_fetch": datetime.now(timezone.utc),
                        "last_article_count": len(result),
                        "status": "active"
                    }}
                )
            
            batch_num = i // batch_size + 1
            logger.info(f"[RSS] Batch {batch_num}/{(len(sources) + batch_size - 1) // batch_size}: "
                        f"processed={batch_articles}, new={batch_new}")
            await asyncio.sleep(0.5)  # Rate limiting between batches
    
    articles_after = await db.news_articles.count_documents({})
    
    logger.info("=" * 50)
    logger.info(f"[RSS] INGESTION SUMMARY:")
    logger.info(f"  Sources processed OK: {sources_ok}")
    logger.info(f"  Sources empty/no-data: {sources_empty}")
    logger.info(f"  Sources failed: {sources_failed}")
    logger.info(f"  Articles processed: {total_articles}")
    logger.info(f"  Articles NEW (inserted): {total_new}")
    logger.info(f"  Articles UPDATED: {total_updated}")
    logger.info(f"  DB articles before: {articles_before}")
    logger.info(f"  DB articles after: {articles_after}")
    logger.info(f"  Net new: {articles_after - articles_before}")
    logger.info("=" * 50)
    
    return {
        "articles": total_articles, 
        "new": total_new, 
        "updated": total_updated,
        "sources_ok": sources_ok, 
        "sources_failed": sources_failed,
        "sources_empty": sources_empty
    }


async def link_articles_to_graph(db):
    """Create edges from news articles to graph entities"""
    logger.info("[NewsGraph] Linking articles to graph entities...")
    now = datetime.now(timezone.utc)
    edges_created = 0
    
    # Get articles with entity mentions
    cursor = db.news_articles.find(
        {"entity_count": {"$gt": 0}},
        {"_id": 0, "id": 1, "source_id": 1, "entities_mentioned": 1, "published_at": 1, "title": 1}
    )
    
    entity_article_count = defaultdict(int)
    
    async for article in cursor:
        for entity in article.get("entities_mentioned", []):
            entity_article_count[entity] += 1
    
    # Create news_coverage edges for entities with significant coverage
    for entity, count in entity_article_count.items():
        if count < 2:
            continue
        
        # Store as sentiment overlay data (not graph edges — respecting data separation rule)
        await db.sentiment_events.update_one(
            {"entity": entity, "source": "rss_news"},
            {"$set": {
                "entity": entity,
                "source": "rss_news",
                "type": "news_coverage",
                "article_count": count,
                "signal_strength": min(10, count / 5),
                "updated_at": now
            }},
            upsert=True
        )
        edges_created += 1
    
    logger.info(f"[NewsGraph] Created {edges_created} sentiment events from news coverage")
    return edges_created


async def ensure_news_indexes(db):
    """Create indexes for news collections"""
    await db.news_articles.create_index("id", unique=True)
    await db.news_articles.create_index("source_id")
    await db.news_articles.create_index("published_at")
    await db.news_articles.create_index("entities_mentioned")
    await db.news_articles.create_index([("entity_count", -1)])
    await db.news_sources.create_index("id", unique=True)
    await db.news_sources.create_index("is_active")
    logger.info("[NewsIndexes] Done")


async def run_rss_pipeline():
    """Run the complete RSS ingestion pipeline"""
    start = time.time()
    logger.info("=" * 60)
    logger.info("RSS PIPELINE — START")
    logger.info("=" * 60)
    
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    # Step 1: Fetch RSS articles
    result = await run_rss_ingestion(db, max_sources=120, batch_size=10)
    
    # Step 2: Link articles to entities (as sentiment overlay, NOT graph edges)
    sentiment = await link_articles_to_graph(db)
    
    # Step 3: Indexes
    await ensure_news_indexes(db)
    
    # Report
    logger.info("=" * 60)
    logger.info("RSS PIPELINE — RESULTS")
    logger.info("=" * 60)
    for col in ["news_sources", "news_articles", "sentiment_events"]:
        cnt = await db[col].count_documents({})
        logger.info(f"  {col}: {cnt}")
    
    elapsed = time.time() - start
    logger.info(f"\nTotal time: {elapsed:.1f}s")
    logger.info("=" * 60)
    
    client.close()
    return result


if __name__ == "__main__":
    asyncio.run(run_rss_pipeline())
