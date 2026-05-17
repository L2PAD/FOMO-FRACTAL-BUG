"""
Backers & Alerts & Actor-Scores Router — powers Backers, Feed, and actor scoring tabs.
"""
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import APIRouter, Query, Request
from pymongo import MongoClient, DESCENDING

load_dotenv()
logger = logging.getLogger(__name__)

router = APIRouter(tags=["backers-alerts"])

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
client = MongoClient(MONGO_URL)
db = client["test_database"]


# ─── BACKERS TAB ───────────────────────────────────────────

# Stabilization Sprint C2 (2026-05-11) — shadowed by bakery_engine (registered earlier in server.py).
async def list_backers(limit: int = 50, offset: int = 0):
    """List all backers from funding data."""
    # Get unique funders/investors from raw_funding
    pipeline = [
        {"$group": {
            "_id": "$source",
            "totalProjects": {"$sum": 1},
            "totalCap": {"$sum": {"$ifNull": ["$market_cap", 0]}},
            "projects": {"$push": {"name": "$name", "symbol": "$symbol"}},
        }},
        {"$sort": {"totalCap": -1}},
        {"$skip": offset},
        {"$limit": limit},
    ]
    sources = list(db.raw_funding.aggregate(pipeline))

    # Also check canonical_projects for backer links
    projects_with_backers = list(db.canonical_projects.find(
        {"metadata.backers": {"$exists": True, "$ne": []}},
        {"_id": 0, "name": 1, "symbol": 1, "metadata.backers": 1}
    ).limit(20))

    backers = []
    backer_map = {}
    for p in projects_with_backers:
        for b in p.get("metadata", {}).get("backers", []):
            bname = b if isinstance(b, str) else b.get("name", "")
            if bname and bname not in backer_map:
                backer_map[bname] = {
                    "id": bname.lower().replace(" ", "-"),
                    "name": bname,
                    "type": "vc",
                    "projects": [],
                    "totalInvestments": 0,
                }
            if bname:
                backer_map[bname]["projects"].append(p.get("symbol", p.get("name")))
                backer_map[bname]["totalInvestments"] += 1

    backers = sorted(backer_map.values(), key=lambda x: -x["totalInvestments"])

    return {"ok": True, "backers": backers, "total": len(backers)}


# Stabilization Sprint C2 — shadowed by bakery_engine::active_money_flow.
async def active_backers():
    """Active money flow from backers."""
    # Aggregate recent funding activity
    pipeline = [
        {"$match": {"market_cap": {"$gt": 0}}},
        {"$group": {
            "_id": "$category",
            "count": {"$sum": 1},
            "totalCap": {"$sum": "$market_cap"},
            "avgVolume": {"$avg": "$volume_24h"},
        }},
        {"$sort": {"totalCap": -1}},
        {"$limit": 10},
    ]
    flows = list(db.raw_funding.aggregate(pipeline))

    return {
        "ok": True,
        "flows": [
            {
                "sector": f.get("_id") or "Other",
                "count": f["count"],
                "totalCap": f["totalCap"],
                "avgVolume": f.get("avgVolume", 0),
            }
            for f in flows
        ]
    }


@router.get("/api/backers/{backer_id}")
async def backer_detail(backer_id: str):
    """Backer detail view."""
    projects = list(db.canonical_projects.find(
        {"metadata.backers": {"$regex": backer_id, "$options": "i"}},
        {"_id": 0, "name": 1, "symbol": 1, "metadata": 1}
    ).limit(50))

    return {
        "ok": True,
        "backer": {
            "id": backer_id,
            "name": backer_id.replace("-", " ").title(),
            "type": "vc",
            "projectCount": len(projects),
        },
        "projects": projects,
    }


# ─── ALERTS / FEED TAB ────────────────────────────────────

@router.get("/api/alerts/feed")
async def alerts_feed():
    """Live alerts feed combining all signal sources."""
    alerts = []

    # 1. Prediction alerts
    pred_alerts = list(db.prediction_alerts.find(
        {}, {"_id": 0}
    ).sort("created_at", DESCENDING).limit(15))

    for pa in pred_alerts:
        alerts.append({
            "id": str(pa.get("alert_id", "")),
            "type": "prediction",
            "severity": pa.get("severity", "medium"),
            "title": pa.get("title", ""),
            "message": pa.get("reasoning", ""),
            "token": pa.get("token", ""),
            "createdAt": str(pa.get("created_at", "")),
        })

    # 2. Actor signal events (high engagement)
    signals = list(db.actor_signal_events.find(
        {"metrics.likes": {"$gte": 500}},
        {"_id": 0}
    ).sort("ingested_at", DESCENDING).limit(10))

    for s in signals:
        m = s.get("metrics", {})
        alerts.append({
            "id": s.get("tweet_id", ""),
            "type": "actor_signal",
            "severity": "high" if m.get("likes", 0) > 5000 else "medium",
            "title": f"@{s.get('actor_handle', '')} mentioned ${s.get('token', '')}",
            "message": s.get("text", "")[:200],
            "token": s.get("token", ""),
            "engagement": m.get("likes", 0) + m.get("retweets", 0),
            "createdAt": str(s.get("ingested_at", "")),
        })

    # 3. Exchange signals
    ie_db = client["intelligence_engine"]
    exchange_signals = list(ie_db.exchange_forecasts.find(
        {}, {"_id": 0}
    ).sort("createdAt", DESCENDING).limit(5))

    for es in exchange_signals:
        alerts.append({
            "id": str(es.get("symbol", "")),
            "type": "exchange_signal",
            "severity": "high" if es.get("confidence", 0) > 0.7 else "low",
            "title": f"{es.get('symbol', '')} {es.get('action', '')} Signal",
            "message": f"Confidence: {es.get('confidence', 0):.0%}, Entry: ${es.get('entryPrice', 0):,.2f}",
            "token": es.get("asset", ""),
            "createdAt": str(es.get("createdAt", "")),
        })

    # Sort by time
    alerts.sort(key=lambda x: x.get("createdAt", ""), reverse=True)

    return {"ok": True, "alerts": alerts[:30]}


# ─── ACTOR SCORES ──────────────────────────────────────────

@router.get("/api/actor-scores")
async def actor_scores(window: str = "7d", limit: int = 100):
    """Actor influence scores."""
    pipeline = [
        {"$group": {
            "_id": "$actor_handle",
            "signalCount": {"$sum": 1},
            "tokens": {"$addToSet": "$token"},
            "totalLikes": {"$sum": "$metrics.likes"},
            "totalRetweets": {"$sum": "$metrics.retweets"},
            "totalReplies": {"$sum": "$metrics.replies"},
            "lastActive": {"$max": "$ingested_at"},
        }},
        {"$sort": {"totalLikes": -1}},
        {"$limit": limit},
    ]
    actors = list(db.actor_signal_events.aggregate(pipeline))

    results = []
    for a in actors:
        total_eng = a["totalLikes"] + a["totalRetweets"] * 3
        influence_score = min(1000, int(a["signalCount"] * 30 + total_eng * 0.01))
        results.append({
            "handle": a["_id"],
            "influenceScore": influence_score,
            "signalCount": a["signalCount"],
            "tokens": a["tokens"],
            "engagement": {
                "likes": a["totalLikes"],
                "retweets": a["totalRetweets"],
                "replies": a["totalReplies"],
            },
            "riskLevel": "low" if influence_score > 600 else "medium" if influence_score > 300 else "high",
            "lastActive": str(a.get("lastActive", "")),
        })

    return {"ok": True, "data": results}


@router.get("/api/actor-scores/summary")
async def actor_scores_summary(window: str = "7d"):
    """Summary of actor scores."""
    total = len(db.actor_signal_events.distinct("actor_handle"))
    return {
        "ok": True,
        "totalActors": total,
        "window": window,
        "avgScore": 500,
        "topPerformer": db.actor_signal_events.distinct("actor_handle")[:1],
    }


@router.get("/api/actor-scores/{handle}")
async def actor_score_detail(handle: str):
    """Detailed score for a specific actor."""
    signals = list(db.actor_signal_events.find(
        {"actor_handle": {"$regex": handle, "$options": "i"}},
        {"_id": 0}
    ).sort("ingested_at", DESCENDING).limit(50))

    if not signals:
        return {"ok": False, "error": "Actor not found"}

    total_likes = sum(s.get("metrics", {}).get("likes", 0) for s in signals)
    total_rt = sum(s.get("metrics", {}).get("retweets", 0) for s in signals)
    tokens = list(set(s.get("token", "") for s in signals))

    return {
        "ok": True,
        "handle": handle,
        "influenceScore": min(1000, int(len(signals) * 30 + total_likes * 0.01)),
        "signalCount": len(signals),
        "tokens": tokens,
        "engagement": {"likes": total_likes, "retweets": total_rt},
        "recentSignals": signals[:10],
    }


@router.get("/api/actor-scores/{handle}/history")
async def actor_score_history(handle: str, window: str = "7d", days: int = 30):
    """Historical scores for an actor."""
    signals = list(db.actor_signal_events.find(
        {"actor_handle": {"$regex": handle, "$options": "i"}},
        {"_id": 0, "ingested_at": 1, "metrics": 1, "token": 1}
    ).sort("ingested_at", DESCENDING).limit(100))

    return {
        "ok": True,
        "handle": handle,
        "window": window,
        "history": signals,
    }
