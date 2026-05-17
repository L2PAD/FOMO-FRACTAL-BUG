"""
Entity Node Enrichment + Aggregation Pipeline
==============================================

P2: Adds feature scores to entity_graph_nodes:
  - sentimentScore, mentionCount24h, newsCount24h
  - twitterMentions24h, velocity, importanceAvg, lastUpdated

P2.5: Time dimension: window_24h, window_7d

P3: Creates entity_signals collection as ML input:
  - sentiment, sentimentTrend, newsVelocity, twitterVelocity
  - importanceScore, signal categories, updatedAt

Sources: RSS (news_articles), Twitter (twitter_results), Entity Graph
"""

import asyncio
import os
import sys
import logging
import time
from datetime import datetime, timezone, timedelta
from collections import defaultdict

from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("Enrichment")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
DB_NAME = os.environ.get("DB_NAME", "intelligence_engine")


async def compute_news_features(db, window_hours=24):
    """Compute per-entity news features from news_articles"""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=window_hours)

    entity_news = defaultdict(lambda: {"count": 0, "total_entity_count": 0, "sources": set()})

    cursor = db.news_articles.find(
        {"entity_count": {"$gt": 0}, "ingested_at": {"$gte": cutoff}},
        {"_id": 0, "entities_mentioned": 1, "entity_count": 1, "source_name": 1}
    )

    async for article in cursor:
        for entity in article.get("entities_mentioned", []):
            e = entity_news[entity]
            e["count"] += 1
            e["total_entity_count"] += article.get("entity_count", 0)
            e["sources"].add(article.get("source_name", ""))

    # Convert sets to counts
    for entity in entity_news:
        entity_news[entity]["source_diversity"] = len(entity_news[entity]["sources"])
        del entity_news[entity]["sources"]

    logger.info(f"[NEWS] {len(entity_news)} entities with {window_hours}h news data")
    return dict(entity_news)


async def compute_twitter_features(db, window_hours=24):
    """Compute per-entity twitter features from twitter_results"""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=window_hours)

    entity_twitter = defaultdict(lambda: {
        "count": 0, "likes": 0, "views": 0, "reposts": 0,
        "verified_mentions": 0, "max_followers": 0
    })

    cursor = db.twitter_results.find(
        {"entity_count": {"$gt": 0}, "parsedAt": {"$gte": cutoff}},
        {"_id": 0, "entities_mentioned": 1, "likes": 1, "views": 1, "reposts": 1, "author": 1}
    )

    async for tweet in cursor:
        author = tweet.get("author", {})
        for entity in tweet.get("entities_mentioned", []):
            e = entity_twitter[entity]
            e["count"] += 1
            e["likes"] += tweet.get("likes", 0)
            e["views"] += tweet.get("views", 0)
            e["reposts"] += tweet.get("reposts", 0)
            if author.get("verified"):
                e["verified_mentions"] += 1
            if author.get("followers", 0) > e["max_followers"]:
                e["max_followers"] = author["followers"]

    logger.info(f"[TWITTER] {len(entity_twitter)} entities with {window_hours}h twitter data")
    return dict(entity_twitter)


async def compute_graph_features(db):
    """Compute graph-level features per entity from entity_graph"""
    entity_graph = defaultdict(lambda: {"edge_count": 0, "edge_types": set(), "importance_sum": 0})

    # Count edges per entity
    cursor = db.entity_graph_relations.find({}, {"_id": 0, "source_id": 1, "target_id": 1, "relation_type": 1, "weight": 1})
    async for edge in cursor:
        for node_id in [edge.get("source_id", ""), edge.get("target_id", "")]:
            # Extract entity name from node_id (e.g., "project:ethereum" -> "ethereum")
            parts = node_id.split(":", 1)
            if len(parts) == 2:
                entity_name = parts[1]
                g = entity_graph[entity_name]
                g["edge_count"] += 1
                g["edge_types"].add(edge.get("relation_type", ""))
                g["importance_sum"] += edge.get("weight", 0.5)

    for entity in entity_graph:
        e = entity_graph[entity]
        e["edge_type_count"] = len(e["edge_types"])
        del e["edge_types"]

    logger.info(f"[GRAPH] {len(entity_graph)} entities with graph features")
    return dict(entity_graph)


def compute_velocity(current_count, previous_count):
    """Compute velocity (rate of change) between two windows"""
    if previous_count == 0:
        return current_count * 1.0  # New entity
    return (current_count - previous_count) / max(previous_count, 1)


def compute_sentiment_score(news_count, twitter_count, twitter_likes, twitter_views):
    """Simple sentiment proxy (higher = more discussed positively)"""
    # Weighted combination: twitter engagement is stronger signal
    raw = (news_count * 1.0) + (twitter_count * 2.0) + (twitter_likes * 0.01) + (twitter_views * 0.0001)
    # Normalize to 0-1 range (sigmoid-like)
    return min(1.0, raw / (raw + 10.0))


def compute_importance(graph_edges, news_source_diversity, twitter_verified, max_followers):
    """Compute importance score 0-100"""
    score = 0
    score += min(30, graph_edges * 3)  # Graph connectivity
    score += min(20, news_source_diversity * 5)  # News diversity
    score += min(20, twitter_verified * 10)  # Verified twitter mentions
    score += min(30, max_followers / 100000)  # Follower reach
    return min(100, round(score, 1))


async def enrich_entity_nodes(db):
    """P2: Update entity_graph_nodes with feature scores"""
    logger.info("=" * 60)
    logger.info("NODE ENRICHMENT — START")
    logger.info("=" * 60)

    now = datetime.now(timezone.utc)

    # Compute features for 24h and 7d windows
    news_24h = await compute_news_features(db, 24)
    news_7d = await compute_news_features(db, 168)
    twitter_24h = await compute_twitter_features(db, 24)
    twitter_7d = await compute_twitter_features(db, 168)
    graph_features = await compute_graph_features(db)

    # Get all entity nodes
    nodes = await db.entity_graph_nodes.find({}, {"_id": 0, "id": 1, "label": 1, "type": 1}).to_list(1000)
    logger.info(f"Processing {len(nodes)} entity nodes")

    updated = 0
    for node in nodes:
        node_id = node["id"]
        # Extract entity name (e.g., "project:ethereum" -> "ethereum")
        parts = node_id.split(":", 1)
        entity_name = parts[1] if len(parts) == 2 else node_id

        n24 = news_24h.get(entity_name, {})
        n7d = news_7d.get(entity_name, {})
        t24 = twitter_24h.get(entity_name, {})
        t7d = twitter_7d.get(entity_name, {})
        gf = graph_features.get(entity_name, {})

        news_count_24h = n24.get("count", 0)
        news_count_7d = n7d.get("count", 0)
        twitter_count_24h = t24.get("count", 0)
        twitter_count_7d = t7d.get("count", 0)

        sentiment = compute_sentiment_score(
            news_count_24h,
            twitter_count_24h,
            t24.get("likes", 0),
            t24.get("views", 0)
        )

        importance = compute_importance(
            gf.get("edge_count", 0),
            n24.get("source_diversity", 0),
            t24.get("verified_mentions", 0),
            t24.get("max_followers", 0)
        )

        news_velocity = compute_velocity(news_count_24h, max(1, news_count_7d / 7))
        twitter_velocity = compute_velocity(twitter_count_24h, max(1, twitter_count_7d / 7))

        enrichment = {
            "features": {
                "sentimentScore": round(sentiment, 4),
                "mentionCount24h": news_count_24h + twitter_count_24h,
                "newsCount24h": news_count_24h,
                "twitterMentions24h": twitter_count_24h,
                "newsVelocity": round(news_velocity, 3),
                "twitterVelocity": round(twitter_velocity, 3),
                "importanceAvg": importance,
                "graphEdges": gf.get("edge_count", 0),
                "graphEdgeTypes": gf.get("edge_type_count", 0),
            },
            "window_24h": {
                "newsCount": news_count_24h,
                "twitterCount": twitter_count_24h,
                "twitterLikes": t24.get("likes", 0),
                "twitterViews": t24.get("views", 0),
                "twitterReposts": t24.get("reposts", 0),
            },
            "window_7d": {
                "newsCount": news_count_7d,
                "twitterCount": twitter_count_7d,
                "twitterLikes": t7d.get("likes", 0),
                "twitterViews": t7d.get("views", 0),
            },
            "lastUpdated": now,
        }

        await db.entity_graph_nodes.update_one(
            {"id": node_id},
            {"$set": enrichment}
        )
        updated += 1

    logger.info(f"[ENRICHMENT] Updated {updated} nodes with features")
    return updated


async def build_entity_signals(db):
    """P3: Build entity_signals collection as ML input"""
    logger.info("=" * 60)
    logger.info("ENTITY SIGNALS — BUILD")
    logger.info("=" * 60)

    now = datetime.now(timezone.utc)

    # Read enriched nodes
    nodes = await db.entity_graph_nodes.find(
        {"features": {"$exists": True}},
        {"_id": 0}
    ).to_list(1000)

    logger.info(f"Building signals for {len(nodes)} enriched nodes")

    signals_created = 0
    for node in nodes:
        features = node.get("features", {})
        w24 = node.get("window_24h", {})
        w7d = node.get("window_7d", {})

        entity_id = node["id"]
        parts = entity_id.split(":", 1)
        entity_name = parts[1] if len(parts) == 2 else entity_id

        sentiment = features.get("sentimentScore", 0)
        news_velocity = features.get("newsVelocity", 0)
        twitter_velocity = features.get("twitterVelocity", 0)
        importance = features.get("importanceAvg", 0)

        # Compute trend
        news_24 = w24.get("newsCount", 0)
        news_7d_avg = max(1, w7d.get("newsCount", 0) / 7)
        tw_24 = w24.get("twitterCount", 0)
        tw_7d_avg = max(1, w7d.get("twitterCount", 0) / 7)

        if news_24 > news_7d_avg * 1.5 or tw_24 > tw_7d_avg * 1.5:
            trend = "up"
        elif news_24 < news_7d_avg * 0.5 and tw_24 < tw_7d_avg * 0.5:
            trend = "down"
        else:
            trend = "stable"

        signal = {
            "entityId": entity_name,
            "entityNodeId": entity_id,
            "entityType": node.get("type", ""),
            "entityLabel": node.get("label", ""),

            "sentiment": round(sentiment, 4),
            "sentimentTrend": trend,

            "newsVelocity": round(news_velocity, 3),
            "twitterVelocity": round(twitter_velocity, 3),

            "importanceScore": importance,

            "signals": {
                "news_activity": min(10, news_24),
                "twitter_activity": min(10, tw_24),
                "engagement": min(10, (w24.get("twitterLikes", 0) + w24.get("twitterReposts", 0)) / 100),
                "reach": min(10, w24.get("twitterViews", 0) / 10000),
            },

            "window_24h": w24,
            "window_7d": w7d,
            "features": features,

            "updatedAt": now,
        }

        await db.entity_signals.update_one(
            {"entityNodeId": entity_id},
            {"$set": signal},
            upsert=True,
        )
        signals_created += 1

    # Create indexes
    await db.entity_signals.create_index("entityId")
    await db.entity_signals.create_index("entityNodeId", unique=True)
    await db.entity_signals.create_index("entityType")
    await db.entity_signals.create_index("importanceScore")
    await db.entity_signals.create_index("sentiment")
    await db.entity_signals.create_index([("sentimentTrend", 1)])
    await db.entity_signals.create_index([("updatedAt", -1)])

    logger.info(f"[SIGNALS] Created {signals_created} entity signals")
    return signals_created


async def run_enrichment_pipeline():
    """Run complete enrichment pipeline"""
    start = time.time()
    logger.info("=" * 60)
    logger.info("ENRICHMENT PIPELINE — START")
    logger.info("=" * 60)

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # P2: Node enrichment
    enriched = await enrich_entity_nodes(db)

    # P3: Entity signals
    signals = await build_entity_signals(db)

    # Report
    logger.info("=" * 60)
    logger.info("ENRICHMENT PIPELINE — RESULTS")
    logger.info("=" * 60)
    logger.info(f"  Nodes enriched: {enriched}")
    logger.info(f"  Entity signals: {signals}")

    for col in ["entity_graph_nodes", "entity_signals"]:
        cnt = await db[col].count_documents({})
        logger.info(f"  {col}: {cnt}")

    # Top signals
    top = await db.entity_signals.find(
        {},
        {"_id": 0, "entityId": 1, "sentiment": 1, "importanceScore": 1, "sentimentTrend": 1}
    ).sort("importanceScore", -1).limit(10).to_list(10)
    logger.info("\nTop 10 entities by importance:")
    for t in top:
        logger.info(f"  {t['entityId']:20} importance={t['importanceScore']:>6.1f}  sentiment={t['sentiment']:.4f}  trend={t['sentimentTrend']}")

    elapsed = time.time() - start
    logger.info(f"\nTotal time: {elapsed:.1f}s")
    logger.info("=" * 60)

    client.close()


if __name__ == "__main__":
    asyncio.run(run_enrichment_pipeline())
