"""
Signal Engine — entity_signals → entity_alerts
================================================

Core formula:
  signalScore = velocity*0.35 + sentiment*0.25 + importance*0.20 + volume*0.10 + trend*0.10

Signal types:
  MOMENTUM  — signalScore > 75 && sentiment > 0.3
  RISK      — signalScore > 75 && sentiment < -0.3
  BREAKOUT  — signalScore > 60 && velocity up && importance > 60
  NOISE     — signalScore < 40 && velocity up

Trigger: signalScore > 70 && confidence > 60 && importanceBand != LOW
Dedupe: entityId + signalType + hourBucket
"""

import asyncio
import os
import sys
import logging
import time
import math
from datetime import datetime, timezone, timedelta

from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("SignalEngine")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
DB_NAME = os.environ.get("DB_NAME", "intelligence_engine")


def clamp(value, lo=0, hi=100):
    return max(lo, min(hi, value))


def compute_velocity_score(twitter_velocity, news_velocity):
    raw = (twitter_velocity + news_velocity) * 25
    return clamp(raw)


def compute_sentiment_score_normalized(sentiment_raw):
    """Normalize sentiment from 0-1 range to 0-100"""
    return clamp(sentiment_raw * 100)


def compute_volume_score(mention_count_24h, avg_baseline):
    if avg_baseline <= 0:
        avg_baseline = 1
    return clamp((mention_count_24h / avg_baseline) * 50)


def compute_trend_score(trend):
    if trend == "up":
        return 80
    elif trend == "down":
        return 20
    return 50


def compute_signal_score(velocity_score, sentiment_score, importance_score, volume_score, trend_score):
    return (
        velocity_score * 0.35
        + sentiment_score * 0.25
        + importance_score * 0.20
        + volume_score * 0.10
        + trend_score * 0.10
    )


def classify_signal(signal_score, sentiment_raw, velocity_score, importance_score):
    """Classify signal type"""
    if signal_score > 75 and sentiment_raw > 0.3:
        return "MOMENTUM"
    if signal_score > 75 and sentiment_raw < 0.15:
        return "RISK"
    if signal_score > 60 and velocity_score > 50 and importance_score > 60:
        return "BREAKOUT"
    if signal_score < 40 and velocity_score > 30:
        return "NOISE"
    if signal_score > 50:
        return "ATTENTION"
    return "NEUTRAL"


def compute_importance_band(importance_score):
    if importance_score >= 70:
        return "HIGH"
    elif importance_score >= 40:
        return "MEDIUM"
    return "LOW"


def compute_confidence(importance_score, sources_count, mention_count):
    """Confidence = how reliable is this signal"""
    raw = (
        importance_score * 0.4
        + min(sources_count, 5) * 10
        + min(mention_count, 20) * 2.5
    )
    return clamp(raw)


def compute_hour_bucket(dt):
    """Dedupe bucket: YYYY-MM-DD-HH"""
    return dt.strftime("%Y-%m-%d-%H")


async def compute_mention_baseline(db):
    """Average mention count across all entities (for volume normalization)"""
    pipeline = [
        {"$match": {"features": {"$exists": True}}},
        {"$group": {"_id": None, "avg_mentions": {"$avg": "$features.mentionCount24h"}}},
    ]
    result = await db.entity_graph_nodes.aggregate(pipeline).to_list(1)
    baseline = result[0]["avg_mentions"] if result else 1
    return max(baseline, 1)


async def run_signal_engine(db):
    """Main signal engine: entity_signals → entity_alerts"""
    logger.info("=" * 60)
    logger.info("SIGNAL ENGINE — START")
    logger.info("=" * 60)

    now = datetime.now(timezone.utc)
    hour_bucket = compute_hour_bucket(now)

    # Compute baseline for volume normalization
    avg_mention_baseline = await compute_mention_baseline(db)
    logger.info(f"Mention baseline: {avg_mention_baseline:.2f}")

    # Load all entity signals
    signals = await db.entity_signals.find({}, {"_id": 0}).to_list(1000)
    logger.info(f"Processing {len(signals)} entity signals")

    alerts_created = 0
    alerts_triggered = 0
    alerts_deduped = 0
    type_counts = {}

    for sig in signals:
        entity_id = sig.get("entityId", "")
        entity_node_id = sig.get("entityNodeId", "")
        entity_type = sig.get("entityType", "")
        entity_label = sig.get("entityLabel", "")
        features = sig.get("features", {})
        w24 = sig.get("window_24h", {})

        # Extract raw values
        sentiment_raw = sig.get("sentiment", 0)
        sentiment_trend = sig.get("sentimentTrend", "stable")
        twitter_velocity = features.get("twitterVelocity", 0)
        news_velocity = features.get("newsVelocity", 0)
        importance = sig.get("importanceScore", 0)
        mention_count_24h = features.get("mentionCount24h", 0)
        news_count_24h = features.get("newsCount24h", 0)
        twitter_count_24h = features.get("twitterMentions24h", 0)

        # Compute scores
        velocity_score = compute_velocity_score(twitter_velocity, news_velocity)
        sentiment_score = compute_sentiment_score_normalized(sentiment_raw)
        volume_score = compute_volume_score(mention_count_24h, avg_mention_baseline)
        trend_score = compute_trend_score(sentiment_trend)
        importance_band = compute_importance_band(importance)

        signal_score = compute_signal_score(
            velocity_score, sentiment_score, importance, volume_score, trend_score
        )
        signal_score = round(signal_score, 2)

        # Classify
        signal_type = classify_signal(signal_score, sentiment_raw, velocity_score, importance)

        # Count sources (news + twitter = 2 channels, diversity from features)
        sources_count = 0
        if news_count_24h > 0:
            sources_count += 1
        if twitter_count_24h > 0:
            sources_count += 1

        # Confidence
        confidence = compute_confidence(importance, sources_count, mention_count_24h)
        confidence = round(confidence, 2)

        # Importance band boost
        if importance_band == "HIGH":
            signal_score = min(100, signal_score + 10)
        if sources_count >= 2:
            signal_score = min(100, signal_score + 5)

        # Dedupe key
        dedupe_key = f"{entity_id}:{signal_type}:{hour_bucket}"

        # Check if already exists in this hour bucket
        existing = await db.entity_alerts.find_one({"dedupeKey": dedupe_key})
        if existing:
            alerts_deduped += 1
            continue

        # Trigger logic
        triggered = (
            signal_score > 70
            and confidence > 60
            and importance_band != "LOW"
        )

        alert = {
            "entityId": entity_id,
            "entityNodeId": entity_node_id,
            "entityType": entity_type,
            "entityLabel": entity_label,

            "signalScore": signal_score,
            "signalType": signal_type,

            "sentiment": round(sentiment_raw, 4),
            "sentimentTrend": sentiment_trend,

            "velocity": {
                "twitter": round(twitter_velocity, 3),
                "news": round(news_velocity, 3),
                "score": round(velocity_score, 2),
            },

            "volume": {
                "mentionCount24h": mention_count_24h,
                "newsCount24h": news_count_24h,
                "twitterCount24h": twitter_count_24h,
                "score": round(volume_score, 2),
            },

            "importance": importance,
            "importanceBand": importance_band,

            "confidence": confidence,

            "context": {
                "sourcesCount": sources_count,
                "trendScore": trend_score,
                "sentimentScore": round(sentiment_score, 2),
            },

            "triggered": triggered,
            "dedupeKey": dedupe_key,
            "hourBucket": hour_bucket,

            # Backtest fields (to be filled later with price data)
            "futureReturn24h": None,
            "futureReturn7d": None,

            "createdAt": now,
        }

        await db.entity_alerts.insert_one(alert)
        alerts_created += 1
        type_counts[signal_type] = type_counts.get(signal_type, 0) + 1

        if triggered:
            alerts_triggered += 1

    # Indexes
    await db.entity_alerts.create_index("entityId")
    await db.entity_alerts.create_index("signalType")
    await db.entity_alerts.create_index("signalScore")
    await db.entity_alerts.create_index("triggered")
    await db.entity_alerts.create_index("dedupeKey", unique=True)
    await db.entity_alerts.create_index([("createdAt", -1)])
    await db.entity_alerts.create_index([("confidence", -1)])
    await db.entity_alerts.create_index("importanceBand")

    logger.info("=" * 60)
    logger.info("SIGNAL ENGINE — RESULTS")
    logger.info("=" * 60)
    logger.info(f"  Alerts created: {alerts_created}")
    logger.info(f"  Alerts TRIGGERED: {alerts_triggered}")
    logger.info(f"  Alerts deduped: {alerts_deduped}")
    logger.info(f"  Type breakdown:")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        logger.info(f"    {t}: {c}")

    # Top triggered alerts
    top = await db.entity_alerts.find(
        {"triggered": True},
        {"_id": 0, "entityId": 1, "signalScore": 1, "signalType": 1, "confidence": 1, "sentiment": 1}
    ).sort("signalScore", -1).limit(10).to_list(10)

    if top:
        logger.info(f"\n  TOP TRIGGERED ALERTS:")
        for t in top:
            logger.info(
                f"    {t['entityId']:20} score={t['signalScore']:>6.2f} "
                f"type={t['signalType']:10} conf={t['confidence']:>5.1f} "
                f"sent={t['sentiment']:.4f}"
            )

    total_alerts = await db.entity_alerts.count_documents({})
    logger.info(f"\n  Total alerts in DB: {total_alerts}")
    logger.info("=" * 60)

    return {
        "created": alerts_created,
        "triggered": alerts_triggered,
        "deduped": alerts_deduped,
        "types": type_counts,
    }


async def main():
    start = time.time()
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    result = await run_signal_engine(db)
    elapsed = time.time() - start
    logger.info(f"Total time: {elapsed:.1f}s")
    client.close()
    return result


if __name__ == "__main__":
    asyncio.run(main())
