"""
Cluster Intelligence Engine
Reads real influencer_clusters from MongoDB, enriches with actor data,
links tokens, computes: type, status, score, direction, top tokens, insights.
"""
import os
import math
import httpx
from datetime import datetime, timezone
from fastapi import APIRouter
from pymongo import MongoClient
from typing import Optional

router = APIRouter(prefix="/api/connections/clusters", tags=["cluster-engine"])

MONGO_URL = os.environ.get("MONGO_URL")


# Legacy function required by graph_core_routes.py
async def run_clustering(db=None, client=None):
    """Backward-compatible clustering stub. Real logic is in /intelligence endpoint."""
    if db is None:
        return []
    try:
        clusters = await db["influencer_clusters"].find({}, {"_id": 0}).to_list(100)
        return clusters if clusters else []
    except Exception:
        return []


DB_NAME = os.environ.get("DB_NAME", "intelligence_engine")
NODE_BACKEND = "http://127.0.0.1:8003"

_client: Optional[MongoClient] = None


def _db():
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URL)
    return _client[DB_NAME]


def _clamp(v, lo, hi):
    return max(lo, min(v, hi))


def _classify_cluster_type(authority, cohesion, trust, orig_type):
    if authority > 0.8 and cohesion > 0.6:
        return "smart_money"
    if cohesion > 0.75 and trust < 0.55:
        return "coordinated_pump"
    if authority > 0.6 and trust > 0.5:
        return "narrative_drivers"
    return "retail_noise"


def _compute_status(cluster_name, mentions_count):
    db = _db()
    prev = db.cluster_snapshots.find_one(
        {"cluster_name": cluster_name},
        sort=[("timestamp", -1)]
    )
    prev_mentions = prev.get("mentions_count", 0) if prev else 0

    if prev_mentions == 0:
        return "active" if mentions_count > 0 else "emerging"

    growth = mentions_count / max(prev_mentions, 1)
    if growth > 1.5:
        return "emerging"
    if growth > 0.7:
        return "active"
    if growth > 0.3:
        return "saturated"
    return "dead"


def _compute_direction(tokens):
    if not tokens:
        return "mixed"
    positive = sum(1 for t in tokens if t.get("price_return", 0) > 0)
    negative = sum(1 for t in tokens if t.get("price_return", 0) < 0)
    ratio = positive / max(positive + negative, 1)
    if ratio >= 0.65:
        return "bullish"
    if ratio <= 0.35:
        return "dump_risk"
    return "mixed"


def _compute_cluster_score(cohesion, authority, trust, engagement_norm, novelty):
    return (
        cohesion * 0.20 +
        authority * 0.25 +
        trust * 0.15 +
        engagement_norm * 0.15 +
        novelty * 0.25
    )


def _generate_signal(cluster_type, status, direction, score):
    if status == "emerging" and direction == "bullish":
        return "Strong momentum forming"
    if cluster_type == "smart_money" and direction == "bullish":
        return "Smart money accumulation"
    if cluster_type == "coordinated_pump":
        return "Coordinated activity — high risk"
    if status == "saturated":
        return "Signal fading"
    if direction == "dump_risk":
        return "Dump risk detected"
    if score > 0.7:
        return "High conviction signal"
    if status == "active":
        return "Momentum forming"
    return "Low signal — monitoring"


@router.get("/intelligence")
async def cluster_intelligence():
    db = _db()

    raw_clusters = list(db.influencer_clusters.find({}, {"_id": 0}))
    if not raw_clusters:
        return {"ok": True, "data": {"clusters": [], "insights": [], "token_clusters": {}}}

    actors_map = {}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{NODE_BACKEND}/api/connections/unified", params={"facet": "REAL_TWITTER", "limit": 500})
            if resp.status_code == 200:
                for a in resp.json().get("data", []):
                    handle = (a.get("handle") or "").replace("@", "").lower()
                    if handle:
                        actors_map[handle] = a
    except Exception:
        pass

    momentum_tokens = []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{NODE_BACKEND}/api/connections/cluster-momentum")
            if resp.status_code == 200:
                momentum_tokens = resp.json().get("data", [])
    except Exception:
        pass

    alignment_map = {}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{NODE_BACKEND}/api/connections/cluster-alignment")
            if resp.status_code == 200:
                for al in resp.json().get("data", []):
                    alignment_map[al["token"]] = al
    except Exception:
        pass

    clusters = []
    all_cluster_tokens = {}

    for raw in raw_clusters:
        name = raw["name"]
        members = raw.get("members", [])
        metrics = raw.get("metrics", {})

        enriched_members = []
        total_followers = 0
        total_engagement = 0
        for handle in members:
            actor = actors_map.get(handle.lower(), {})
            enriched_members.append({
                "username": handle,
                "display_name": actor.get("title") or handle,
                "avatar": actor.get("avatar") or f"https://unavatar.io/twitter/{handle}",
                "authority": round(actor.get("authority", 0), 2),
                "followers": actor.get("followers", 0),
            })
            total_followers += actor.get("followers", 0)
            total_engagement += actor.get("engagement", 0)

        cluster_tokens = []
        name_lower = name.lower()
        for mt in momentum_tokens:
            token = mt["token"]
            al = alignment_map.get(token, {})
            classification = mt.get("classification", "").lower()

            # Match token classification to cluster type for relevance
            relevance = 0.5
            if "defi" in name_lower or "whale" in name_lower:
                if classification in ("momentum", "confirmed"):
                    relevance = 0.9
                elif "pump" in classification:
                    relevance = 0.3
            elif "meme" in name_lower:
                if "pump" in classification or "hype" in classification:
                    relevance = 0.9
                else:
                    relevance = 0.5
            elif "vc" in name_lower or "alliance" in name_lower:
                if classification in ("confirmed", "momentum"):
                    relevance = 0.8
                elif "pump" in classification:
                    relevance = 0.2
            elif "ai" in name_lower or "narrative" in name_lower:
                if classification in ("momentum",) or "hype" in classification:
                    relevance = 0.85
            elif "l2" in name_lower or "builder" in name_lower:
                if classification in ("confirmed",):
                    relevance = 0.8
                elif "pump" in classification:
                    relevance = 0.3

            if relevance < 0.4:
                continue

            cluster_tokens.append({
                "symbol": token,
                "mentions": mt.get("uniqueMentioners", 0),
                "score": round(mt.get("score", 0) * relevance, 3),
                "price_return": al.get("priceReturn", 0),
                "alignment_score": al.get("alignmentScore", 0),
                "verdict": al.get("verdict", "UNCONFIRMED"),
                "classification": mt.get("classification", ""),
            })

        cluster_tokens.sort(key=lambda t: t["score"], reverse=True)
        top_tokens = cluster_tokens[:5]

        for t in top_tokens:
            sym = t["symbol"]
            if sym not in all_cluster_tokens:
                all_cluster_tokens[sym] = []
            all_cluster_tokens[sym].append(name)

        authority = metrics.get("authority", 0.5)
        cohesion = metrics.get("cohesion", 0.5)
        trust = metrics.get("avgTrust", metrics.get("density", 0.5))
        engagement_norm = _clamp(total_engagement / max(len(members), 1), 0, 1)
        novelty = _clamp(len(cluster_tokens) / 12, 0, 1)

        cluster_type = _classify_cluster_type(authority, cohesion, trust, raw.get("type", ""))
        status = _compute_status(name, len(cluster_tokens))
        direction = _compute_direction(top_tokens)
        score = _compute_cluster_score(cohesion, authority, trust, engagement_norm, novelty)
        signal = _generate_signal(cluster_type, status, direction, score)

        db.cluster_snapshots.update_one(
            {"cluster_name": name},
            {"$set": {
                "cluster_name": name,
                "mentions_count": len(cluster_tokens),
                "score": round(score, 3),
                "status": status,
                "timestamp": datetime.now(timezone.utc),
            }},
            upsert=True,
        )

        clusters.append({
            "id": raw.get("id", name.lower().replace(" ", "_")),
            "name": name,
            "type": cluster_type,
            "status": status,
            "members": enriched_members,
            "member_count": len(members),
            "tokens": top_tokens,
            "metrics": {
                "cohesion": round(cohesion, 2),
                "authority": round(authority, 2),
                "trust": round(trust, 2),
                "cluster_score": round(score, 3),
                "direction": direction,
                "engagement_norm": round(engagement_norm, 2),
                "pump_score": round(
                    cohesion * 0.25 + (1 - trust) * 0.2 + engagement_norm * 0.25 + novelty * 0.3,
                    3
                ) if cluster_type == "coordinated_pump" else 0,
            },
            "signal": signal,
            "total_followers": total_followers,
        })

    clusters.sort(key=lambda c: c["metrics"]["cluster_score"], reverse=True)

    insights = []
    smart_money = [c for c in clusters if c["type"] == "smart_money" and c["metrics"]["direction"] == "bullish"]
    if smart_money:
        tokens_pushed = set()
        for c in smart_money:
            for t in c["tokens"][:2]:
                tokens_pushed.add(t["symbol"])
        if tokens_pushed:
            insights.append({
                "type": "coordinated",
                "text": f"{len(smart_money)} smart money cluster{'s' if len(smart_money) > 1 else ''} pushing {', '.join(list(tokens_pushed)[:3])}",
                "severity": "high"
            })

    emerging = [c for c in clusters if c["status"] == "emerging"]
    if len(emerging) >= 2:
        insights.append({
            "type": "emerging",
            "text": f"{len(emerging)} clusters emerging — early trend signal",
            "severity": "medium"
        })

    multi_confirmed = {t: cs for t, cs in all_cluster_tokens.items() if len(cs) >= 3}
    if multi_confirmed and len(insights) < 2:
        top_token = max(multi_confirmed, key=lambda t: len(multi_confirmed[t]))
        insights.append({
            "type": "multi_cluster",
            "text": f"{top_token} confirmed by {len(multi_confirmed[top_token])} clusters",
            "severity": "high"
        })

    return {
        "ok": True,
        "data": {
            "clusters": clusters,
            "insights": insights[:2],
            "token_clusters": {t: cs for t, cs in all_cluster_tokens.items() if len(cs) >= 2},
            "total": len(clusters),
        }
    }
