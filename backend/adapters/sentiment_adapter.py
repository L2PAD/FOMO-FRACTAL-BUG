"""
Sentiment Adapter — REAL data from sentiment_events collection.

Entity-based: queries by asset symbol (BTC, ETH, SOL...).
Returns unified signal format: {bias, strength, confidence, ...}

Data source: intelligence_engine.sentiment_events
  - weightedScore (0-1, 0.5 = neutral)
  - weightedConfidence
  - eventType (bullish_signal, bearish_signal, neutral_info, ...)
  - sourceType (twitter, news, telegram)
  - sourceWeight (0-1)
"""
import os
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, DESCENDING


def _get_db():
    return MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "intelligence_engine")]


def get_sentiment_signal(asset: str = "BTC") -> dict | None:
    """
    Get real sentiment signal for an asset from sentiment_events.

    Returns unified format:
        {
            bias: "bullish"|"bearish"|"neutral",
            strength: 0.0-1.0,
            confidence: 0.0-1.0,
            direction: "bullish"|"bearish"|"neutral",
            delta: float (-1 to 1),
            signal_count: int,
            weighted_score: float,
            top_signals: [{text, impact, quality}]
        }
    or None if unavailable.
    """
    try:
        db = _get_db()
        now = datetime.now(timezone.utc)

        # Recent window: last 12h for delta, last 48h for baseline
        cutoff_12h = now - timedelta(hours=12)
        cutoff_48h = now - timedelta(hours=48)

        # Fetch recent 12h events
        recent_events = list(db["sentiment_events"].find(
            {"symbol": asset.upper(), "createdAt": {"$gte": cutoff_12h}},
            {"_id": 0, "weightedScore": 1, "weightedConfidence": 1,
             "eventType": 1, "sourceType": 1, "sourceWeight": 1, "authorHandle": 1},
        ).sort("createdAt", DESCENDING).limit(50))

        # Fetch older 12-48h events for delta comparison
        older_events = list(db["sentiment_events"].find(
            {"symbol": asset.upper(),
             "createdAt": {"$gte": cutoff_48h, "$lt": cutoff_12h}},
            {"_id": 0, "weightedScore": 1, "weightedConfidence": 1,
             "sourceWeight": 1},
        ).limit(100))

        # If no recent data, try last 7 days as fallback
        if not recent_events:
            cutoff_7d = now - timedelta(days=7)
            recent_events = list(db["sentiment_events"].find(
                {"symbol": asset.upper(), "createdAt": {"$gte": cutoff_7d}},
                {"_id": 0, "weightedScore": 1, "weightedConfidence": 1,
                 "eventType": 1, "sourceType": 1, "sourceWeight": 1, "authorHandle": 1},
            ).sort("createdAt", DESCENDING).limit(50))

        if not recent_events:
            return None

        # Compute weighted average score
        total_weight = 0.0
        weighted_sum = 0.0
        conf_sum = 0.0
        bullish_count = 0
        bearish_count = 0

        for e in recent_events:
            score = e.get("weightedScore", 0.5)
            conf = e.get("weightedConfidence", 0.3)
            sw = e.get("sourceWeight", 0.5)
            w = max(sw, 0.1)
            weighted_sum += score * w
            conf_sum += conf * w
            total_weight += w

            if score > 0.6:
                bullish_count += 1
            elif score < 0.4:
                bearish_count += 1

        avg_score = weighted_sum / total_weight if total_weight > 0 else 0.5
        avg_confidence = conf_sum / total_weight if total_weight > 0 else 0.3

        # Compute older baseline
        if older_events:
            old_total = 0.0
            old_sum = 0.0
            for e in older_events:
                sw = max(e.get("sourceWeight", 0.5), 0.1)
                old_sum += e.get("weightedScore", 0.5) * sw
                old_total += sw
            old_avg = old_sum / old_total if old_total > 0 else 0.5
        else:
            old_avg = 0.5

        # Delta: shift from baseline
        delta = avg_score - old_avg

        # Strength: how far from neutral (0.5)
        strength = min(1.0, abs(avg_score - 0.5) * 2.5)

        # Bias direction
        if avg_score > 0.55:
            bias = "bullish"
        elif avg_score < 0.45:
            bias = "bearish"
        else:
            bias = "neutral"

        # Confidence: combine model confidence + event density
        event_density = min(1.0, len(recent_events) / 20.0)
        confidence = min(0.95, avg_confidence * 0.5 + event_density * 0.3 + strength * 0.2)

        # Top signals for explainability
        top_signals = []
        for e in recent_events[:5]:
            impact = "bullish" if e.get("weightedScore", 0.5) > 0.6 else (
                "bearish" if e.get("weightedScore", 0.5) < 0.4 else "neutral")
            top_signals.append({
                "author": e.get("authorHandle", "unknown"),
                "impact": impact,
                "quality": round(e.get("sourceWeight", 0.5), 2),
                "type": e.get("eventType", "unknown"),
            })

        return {
            "bias": bias,
            "strength": round(strength, 4),
            "confidence": round(confidence, 4),
            "direction": bias,
            "delta": round(delta, 4),
            "signal_count": len(recent_events),
            "weighted_score": round(avg_score, 4),
            "bullish_count": bullish_count,
            "bearish_count": bearish_count,
            "top_signals": top_signals,
        }
    except Exception:
        return None
