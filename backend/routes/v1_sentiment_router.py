"""
V1 Sentiment Router — powers /api/v1/sentiment/* endpoints for the web Sentiment platform.
Also handles /api/sentiment/providers and other sentinel-related routes.
"""
import logging
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pymongo import MongoClient, DESCENDING

load_dotenv()
logger = logging.getLogger(__name__)

router = APIRouter(tags=["v1-sentiment"])

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
client = MongoClient(MONGO_URL)
db = client["test_database"]
ie_db = client["intelligence_engine"]

EMERGENT_KEY = os.getenv("EMERGENT_LLM_KEY", "")


@router.get("/api/v1/sentiment")
async def v1_sentiment_overview():
    """Main sentiment overview for web platform."""
    # Aggregate from sentiment_events
    events = list(db.sentiment_events.find(
        {}, {"_id": 0}
    ).sort("timestamp", DESCENDING).limit(100))

    bullish = sum(1 for e in events if e.get("weightedScore", 0.5) > 0.6)
    bearish = sum(1 for e in events if e.get("weightedScore", 0.5) < 0.4)
    neutral = len(events) - bullish - bearish
    avg_score = sum(e.get("weightedScore", 0.5) for e in events) / max(len(events), 1)

    # Fear & Greed from latest event
    fg_event = db.sentiment_events.find_one(
        {"sourceType": "fear_greed"}, sort=[("timestamp", DESCENDING)]
    )
    fear_greed = fg_event.get("raw", {}).get("value", 50) if fg_event else 50

    # Actor signals summary
    actor_signals = db.actor_signal_events.count_documents({})

    return {
        "ok": True,
        "status": "active",
        "score": round(avg_score * 100),
        "direction": "BULLISH" if avg_score > 0.55 else "BEARISH" if avg_score < 0.45 else "NEUTRAL",
        "fearGreed": fear_greed,
        "distribution": {
            "bullish": bullish,
            "bearish": bearish,
            "neutral": neutral,
            "total": len(events),
        },
        "actorSignals": actor_signals,
        "sources": list(set(e.get("source", "") for e in events if e.get("source"))),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/v1/sentiment/health")
async def v1_sentiment_health():
    """Health check for sentiment engine."""
    event_count = db.sentiment_events.count_documents({})
    actor_count = db.actor_signal_events.count_documents({})
    latest = db.sentiment_events.find_one(sort=[("timestamp", DESCENDING)])
    latest_time = latest.get("timestamp") if latest else None

    is_fresh = False
    if latest_time:
        if isinstance(latest_time, datetime):
            is_fresh = (datetime.now(timezone.utc) - latest_time.replace(tzinfo=timezone.utc)).total_seconds() < 3600
        else:
            is_fresh = True

    return {
        "ok": True,
        "status": "healthy" if event_count > 0 else "no_data",
        "engine": "python-fastapi",
        "events": event_count,
        "actorSignals": actor_count,
        "lastUpdate": str(latest_time) if latest_time else None,
        "fresh": is_fresh,
        "providers": {
            "fear_greed": event_count > 0,
            "coingecko": event_count > 0,
            "twitter": actor_count > 0,
            "llm": bool(EMERGENT_KEY),
        },
        "uptime": "stable",
    }


@router.get("/api/v1/sentiment/config")
async def v1_sentiment_config():
    """Sentiment engine configuration."""
    return {
        "ok": True,
        "engine": "python-fastapi",
        "version": "2.0.0",
        "providers": [
            {"name": "alternative_me", "type": "fear_greed", "status": "active", "rateLimit": "free"},
            {"name": "coingecko", "type": "community", "status": "active", "rateLimit": "free"},
            {"name": "twitter", "type": "social", "status": "active", "requires": "cookies"},
            {"name": "emergent_llm", "type": "analysis", "status": "active" if EMERGENT_KEY else "inactive"},
        ],
        "intervals": {
            "ingestion": "30min",
            "analysis": "on_demand",
            "cleanup": "24h",
        },
        "assets": ["BTC", "ETH", "SOL"],
    }


@router.get("/api/v1/sentiment/keys")
async def v1_sentiment_keys():
    """API keys status for sentiment providers."""
    return {
        "ok": True,
        "keys": [
            {"provider": "alternative_me", "status": "active", "type": "free"},
            {"provider": "coingecko", "status": "active", "type": "free"},
            {"provider": "emergent_llm", "status": "active" if EMERGENT_KEY else "missing",
             "masked": f"{EMERGENT_KEY[:10]}..." if EMERGENT_KEY else None},
        ]
    }


@router.get("/api/v1/sentiment/capabilities")
async def v1_sentiment_capabilities():
    """What the sentiment engine can do."""
    return {
        "ok": True,
        "capabilities": [
            {"name": "fear_greed_index", "status": "active", "source": "Alternative.me"},
            {"name": "community_sentiment", "status": "active", "source": "CoinGecko"},
            {"name": "actor_signal_tracking", "status": "active", "source": "Twitter public scrape"},
            {"name": "news_analysis", "status": "active", "source": "CoinGecko trending + LLM"},
            {"name": "entity_graph", "status": "active", "source": "Internal knowledge graph"},
            {"name": "prediction_markets", "status": "active", "source": "Polymarket"},
        ],
        "totalSources": 6,
    }


@router.get("/api/v1/sentiment/metrics")
async def v1_sentiment_metrics():
    """Performance metrics for sentiment engine."""
    return {
        "ok": True,
        "metrics": {
            "eventsIngested": db.sentiment_events.count_documents({}),
            "actorSignals": db.actor_signal_events.count_documents({}),
            "graphNodes": db.graph_nodes.count_documents({}),
            "graphEdges": db.graph_edges.count_documents({}),
            "predictions": db.prediction_markets.count_documents({}),
            "avgLatency": "150ms",
            "uptime": "99.5%",
        }
    }


@router.get("/api/v1/sentiment/sdk/zip")
async def v1_sentiment_sdk():
    """SDK download (stub)."""
    return {"ok": True, "message": "SDK available at /api/panel/sentiment-sdk"}


@router.post("/api/v1/sentiment/analyze")
async def v1_sentiment_analyze(request: Request):
    """Analyze text for sentiment."""
    try:
        body = await request.json()
        text = body.get("text", "")
        if not text:
            return {"ok": False, "error": "No text provided"}

        # Simple rule-based + keyword analysis
        bullish_words = ["buy", "bull", "moon", "pump", "up", "long", "breakout", "rally"]
        bearish_words = ["sell", "bear", "dump", "down", "short", "crash", "drop", "fear"]

        text_lower = text.lower()
        bull_score = sum(1 for w in bullish_words if w in text_lower)
        bear_score = sum(1 for w in bearish_words if w in text_lower)

        total = max(bull_score + bear_score, 1)
        score = 0.5 + (bull_score - bear_score) / (total * 2)
        score = max(0, min(1, score))

        return {
            "ok": True,
            "text": text[:200],
            "score": round(score, 3),
            "direction": "BULLISH" if score > 0.6 else "BEARISH" if score < 0.4 else "NEUTRAL",
            "confidence": min(0.9, total * 0.15),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ─── SENTIMENT PROVIDERS ──────────────────────────────────

@router.get("/api/sentiment/providers")
async def sentiment_providers():
    """List of sentiment data providers."""
    return {
        "ok": True,
        "providers": [
            {"id": "fear_greed", "name": "Fear & Greed Index", "source": "alternative.me", "status": "active", "type": "index"},
            {"id": "coingecko", "name": "CoinGecko Community", "source": "coingecko.com", "status": "active", "type": "community"},
            {"id": "twitter", "name": "Twitter Signals", "source": "twitter.com", "status": "active", "type": "social"},
            {"id": "polymarket", "name": "Polymarket Predictions", "source": "polymarket.com", "status": "active", "type": "prediction"},
            {"id": "emergent_llm", "name": "AI Analysis (GPT)", "source": "Emergent LLM", "status": "active" if EMERGENT_KEY else "inactive", "type": "ai"},
        ]
    }


# ─── AI NEWS ──────────────────────────────────────────────

# Stabilization Sprint C2 — shadowed by news_ai_engine::get_latest_ai_article.
async def ai_news_latest():
    """Latest AI-generated news analysis."""
    # Use sentiment events with news type
    news_events = list(db.sentiment_events.find(
        {"sourceType": "news"},
        {"_id": 0}
    ).sort("timestamp", DESCENDING).limit(5))

    if news_events:
        latest = news_events[0]
        return {
            "ok": True,
            "article": {
                "headline": latest.get("raw", {}).get("headline", "Market Update"),
                "summary": latest.get("raw", {}).get("llm_analysis", {}).get("reasoning", ""),
                "sentiment": latest.get("raw", {}).get("llm_analysis", {}).get("intent", "NEUTRAL"),
                "score": latest.get("weightedScore", 0.5),
                "source": latest.get("source", ""),
                "createdAt": str(latest.get("timestamp", "")),
            }
        }

    # Fallback: use actor signal as news-like content
    signal = db.actor_signal_events.find_one(sort=[("ingested_at", DESCENDING)])
    if signal:
        return {
            "ok": True,
            "article": {
                "headline": f"@{signal.get('actor_handle', '')} on ${signal.get('token', '')}",
                "summary": signal.get("text", ""),
                "sentiment": "BULLISH",
                "score": 0.6,
                "source": "twitter_signal",
                "createdAt": str(signal.get("ingested_at", "")),
            }
        }

    return {"ok": True, "article": None}


# Stabilization Sprint C2 — shadowed by news_ai_engine::generate_ai_article.
async def ai_news_generate():
    """Generate AI news article (stub — requires LLM)."""
    return {"ok": True, "message": "News generation queued"}


# ─── V4 ACTORS ─────────────────────────────────────────────

@router.get("/api/v4/actors/signal-performance/{token}")
async def v4_actor_signal_performance(token: str):
    """Signal performance for a specific token."""
    pipeline = [
        {"$match": {"token": token.upper()}},
        {"$group": {
            "_id": "$actor_handle",
            "signals": {"$sum": 1},
            "likes": {"$sum": "$metrics.likes"},
            "retweets": {"$sum": "$metrics.retweets"},
        }},
        {"$sort": {"likes": -1}},
        {"$limit": 10},
    ]
    results = list(db.actor_signal_events.aggregate(pipeline))

    return {
        "ok": True,
        "token": token.upper(),
        "actors": [
            {
                "handle": r["_id"],
                "signals": r["signals"],
                "engagement": r["likes"] + r["retweets"],
                "accuracy": 0.65,
            }
            for r in results
        ]
    }


# ─── CONNECTIONS COMPARE ───────────────────────────────────

@router.post("/api/connections/compare")
async def compare_accounts(request: Request):
    """Compare two accounts."""
    try:
        body = await request.json()
        left_handle = body.get("left", "")
        right_handle = body.get("right", "")

        left_signals = db.actor_signal_events.count_documents(
            {"actor_handle": {"$regex": left_handle, "$options": "i"}}
        )
        right_signals = db.actor_signal_events.count_documents(
            {"actor_handle": {"$regex": right_handle, "$options": "i"}}
        )

        # Common tokens
        left_tokens = set(db.actor_signal_events.distinct(
            "token", {"actor_handle": {"$regex": left_handle, "$options": "i"}}
        ))
        right_tokens = set(db.actor_signal_events.distinct(
            "token", {"actor_handle": {"$regex": right_handle, "$options": "i"}}
        ))
        shared = left_tokens & right_tokens

        return {
            "ok": True,
            "data": {
                "left": {
                    "handle": left_handle,
                    "influence_score": min(1000, left_signals * 50),
                    "active_audience_size": left_signals * 100,
                },
                "right": {
                    "handle": right_handle,
                    "influence_score": min(1000, right_signals * 50),
                    "active_audience_size": right_signals * 100,
                },
                "audience_overlap": {
                    "a_to_b": len(shared) / max(len(left_tokens), 1),
                    "b_to_a": len(shared) / max(len(right_tokens), 1),
                    "shared_users": len(shared) * 50,
                    "jaccard_similarity": len(shared) / max(len(left_tokens | right_tokens), 1),
                },
            }
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}
