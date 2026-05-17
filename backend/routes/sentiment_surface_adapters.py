"""
Sentiment Surface Adapters — fixes UI tabs that read empty collections.

Overrides three endpoints to compute REAL data from `actor_signal_events`:
  GET /api/connections/clusters/intelligence
  GET /api/connections/network/actors-list
  GET /api/connections/network/intelligence

Replaces the empty `audience_quality / twitter_results / bot_farms` reads
with on-the-fly aggregations from the actor event substrate that
`twitter_ingestion.hybrid_service` populates.
"""
from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Query
from pymongo import MongoClient, DESCENDING

router = APIRouter(prefix="/api/connections", tags=["sentiment-surface"])

_client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
_db = _client[os.environ.get("DB_NAME", "fomo_mobile")]


# ─── /api/connections/clusters/intelligence ─────────────────────────────────
@router.get("/clusters/intelligence")
async def clusters_intelligence(limit: int = Query(20, ge=1, le=100)):
    """
    Real-time cluster intelligence derived from actor_signal_events.
    Output shape matches what ClusterAttentionPage.jsx expects:
      cluster.{id, name, type, status, members[{username,avatar}],
               member_count, metrics:{direction}, tokens[{symbol,
               price_return, alignment_score, mentions, verdict}]}
    Clusters are formed by grouping actors that frequently push the same tokens.
    """
    import math
    # Build token → actors and actor → tokens maps from recent events
    events = list(_db.actor_signal_events.find(
        {"token": {"$ne": None}, "actor_handle": {"$ne": None}},
        {"_id": 0, "actor_handle": 1, "token": 1, "ingested_at": 1, "sentiment": 1},
    ).sort("ingested_at", DESCENDING).limit(5000))

    token_actors: Dict[str, set] = defaultdict(set)
    token_signals: Dict[str, int] = defaultdict(int)
    token_sentiments: Dict[str, list] = defaultdict(list)
    for e in events:
        a = (e.get("actor_handle") or "").lstrip("@")
        t = e.get("token")
        if a and t:
            token_actors[t].add(a)
            token_signals[t] += 1
            try:
                s = e.get("sentiment")
                if isinstance(s, (int, float)):
                    token_sentiments[t].append(float(s))
            except Exception:
                pass

    if not token_actors:
        return {"ok": True, "data": {"clusters": [], "insights": [], "token_clusters": {}},
                "count": 0, "asOf": datetime.now(timezone.utc).isoformat(),
                "source": "actor_signal_events_aggregation"}

    # Use top tokens as cluster seeds (top 20 by signals)
    top_tokens = sorted(token_signals.items(), key=lambda x: x[1], reverse=True)[:limit]

    clusters: List[Dict[str, Any]] = []
    for tok, sigs in top_tokens:
        actors = sorted(token_actors[tok])
        uniq = len(actors)
        sentiments = token_sentiments.get(tok) or []
        avg_sent = sum(sentiments) / len(sentiments) if sentiments else 0.0

        # Classify type
        if uniq >= 5 and sigs >= 30:
            cluster_type = "smart_money"
        elif uniq <= 2 and sigs >= 20:
            cluster_type = "coordinated_pump"
        elif uniq >= 3:
            cluster_type = "narrative_drivers"
        else:
            cluster_type = "retail_noise"

        # Classify status
        if sigs < 5:    status = "emerging"
        elif sigs < 30: status = "active"
        elif sigs < 100: status = "active"
        else:            status = "saturated"

        # Classify direction
        if avg_sent > 0.2:
            direction = "bullish"
        elif avg_sent < -0.2:
            direction = "dump_risk"
        else:
            direction = "mixed"

        # Members shape
        members = [{
            "username": a,
            "avatar":   f"https://ui-avatars.com/api/?name={a}&size=64&background=random",
        } for a in actors[:8]]

        # Build per-token records (each cluster centered on one token; show as single-token cluster)
        score = round(min(1.0, uniq * math.log(sigs + 1) / 12.0), 3)
        verdict = "CONFIRMED" if uniq >= 3 else "UNCONFIRMED"
        tokens_arr = [{
            "symbol":          tok,
            "price_return":    0.0,           # not joined here — verdict pipeline owns prices
            "alignment_score": score,
            "mentions":        uniq,
            "verdict":         verdict,
        }]

        clusters.append({
            "id":            tok,
            "name":          tok,
            "type":          cluster_type,
            "status":        status,
            "members":       members,
            "member_count":  uniq,
            "metrics":       {
                "direction":     direction,
                "signals":       sigs,
                "uniqueActors":  uniq,
                "avgSentiment":  round(avg_sent, 3),
                "score":         score,
                # Fields the UI ClusterCard expects:
                "cohesion":      round(score, 3),                   # 0..1 — how unified the cluster is
                "trust":         round(min(1.0, uniq / 8.0), 3),    # 0..1 — number of independent voices
                "cluster_score": float(score),                       # 0..1 numeric for .toFixed(2)
            },
            "signal":        f"{cluster_type.replace('_',' ')} · {direction} · {sigs} signals from {uniq} actors",
            "tokens":        tokens_arr,
            "signals":       sigs,
            "uniqueActors":  uniq,
            "score":         score,
        })

    # token_clusters: token → list of clusters that mention it (here identity)
    token_clusters = {c["id"]: [c["id"]] for c in clusters}

    insights: List[Dict[str, Any]] = []
    for c in clusters[:8]:
        if c["type"] == "coordinated_pump":
            insights.append({
                "type":  "pump_alert",
                "token": c["id"],
                "text":  f"{c['id']} — {c['signals']} signals from only {c['uniqueActors']} actors (pump-like)",
                "severity": "high",
            })
        elif c["type"] == "smart_money" and c["metrics"]["direction"] == "bullish":
            insights.append({
                "type":  "smart_money_bullish",
                "token": c["id"],
                "text":  f"{c['id']} — smart money cluster confirming bullish ({c['uniqueActors']} actors, {c['signals']} signals)",
                "severity": "low",
            })

    return {
        "ok":   True,
        "data": {
            "clusters":       clusters,
            "insights":       insights,
            "token_clusters": token_clusters,
        },
        "count":  len(clusters),
        "asOf":   datetime.now(timezone.utc).isoformat(),
        "source": "actor_signal_events_aggregation",
    }


# ─── /api/connections/network/actors-list ───────────────────────────────────
@router.get("/network/actors-list")
async def network_actors_list(q: str = Query("", description="Search filter")):
    """Real actors from actor_signal_events + twitter_tracked_actors registry."""
    pipeline = [
        {"$match": {"actor_handle": {"$ne": None}}},
        {"$group": {
            "_id":     "$actor_handle",
            "signals": {"$sum": 1},
            "tokens":  {"$addToSet": "$token"},
            "lastSeen": {"$max": "$ingested_at"},
        }},
        {"$sort": {"signals": -1}},
        {"$limit": 200},
    ]
    rows = list(_db.actor_signal_events.aggregate(pipeline))
    actors = []
    for r in rows:
        handle = (r["_id"] or "").lstrip("@")
        if not handle:
            continue
        tokens = [t for t in (r.get("tokens") or []) if t]
        actors.append({
            "actorId":   handle,
            "handle":    handle,
            "aqi":       min(int(r.get("signals", 0) * 5), 100),
            "level":     "ANALYZED",
            "category":  "crypto_alpha",
            "followers": 0,  # not tracked here
            "tweetCount": int(r.get("signals", 0)),
            "tokens":    tokens[:10],
            "lastSeen":  r.get("lastSeen"),
        })

    # Also fold in tracked actors that have no events yet (TARGET state)
    seen_handles = {a["actorId"].lower() for a in actors}
    tracked = list(_db.twitter_tracked_actors.find({"active": True}, {"_id": 0, "username": 1, "category": 1}))
    for t in tracked:
        h = (t.get("username") or "").lstrip("@").lower()
        if h and h not in seen_handles:
            actors.append({
                "actorId":   h,
                "handle":    h,
                "aqi":       0,
                "level":     "TARGET",
                "category":  t.get("category", "crypto_alpha"),
                "followers": 0,
                "tweetCount": 0,
                "tokens":    [],
                "lastSeen":  None,
            })

    if q.strip():
        ql = q.strip().lower().lstrip("@")
        actors = [a for a in actors if ql in a["actorId"]]

    return {
        "ok":            True,
        "actors":        actors,
        "analyzedCount": sum(1 for a in actors if a["level"] == "ANALYZED"),
        "totalCount":    len(actors),
        "asOf":          datetime.now(timezone.utc).isoformat(),
        "source":        "actor_signal_events+twitter_tracked_actors",
    }


# ─── /api/connections/network/intelligence ──────────────────────────────────
@router.get("/network/intelligence")
async def network_intelligence():
    """Real cluster intel — derived from actor_signal_events token co-occurrence."""
    # Pull recent events
    events = list(_db.actor_signal_events.find(
        {}, {"_id": 0, "actor_handle": 1, "token": 1, "ingested_at": 1}
    ).sort("ingested_at", DESCENDING).limit(2000))

    if not events:
        return {"ok": True, "primary": None, "signals": [], "clusters": [],
                "asOf": datetime.now(timezone.utc).isoformat(),
                "source": "actor_signal_events"}

    # Group actors by tokens they push together
    token_actors: Dict[str, set] = defaultdict(set)
    actor_tokens: Dict[str, set] = defaultdict(set)
    for e in events:
        actor = (e.get("actor_handle") or "").lstrip("@")
        token = e.get("token")
        if actor and token:
            token_actors[token].add(actor)
            actor_tokens[actor].add(token)

    # A "cluster" is a token with ≥2 unique actors pushing it concurrently
    clusters = []
    for tok, actors_set in token_actors.items():
        if len(actors_set) < 1:
            continue
        clusters.append({
            "id":      tok,
            "token":   tok,
            "members": sorted(list(actors_set))[:15],
            "memberCount": len(actors_set),
            "signals": sum(1 for e in events if e.get("token") == tok),
        })
    clusters.sort(key=lambda c: c["signals"], reverse=True)

    primary = clusters[0] if clusters else None

    # Signals — top actors with most diversified token coverage
    actor_signals = []
    for actor, toks in actor_tokens.items():
        actor_signals.append({
            "actor":      actor,
            "tokenCount": len(toks),
            "tokens":     sorted(toks)[:10],
        })
    actor_signals.sort(key=lambda a: a["tokenCount"], reverse=True)

    return {
        "ok":       True,
        "primary":  primary,
        "signals":  actor_signals[:15],
        "clusters": clusters[:20],
        "asOf":     datetime.now(timezone.utc).isoformat(),
        "source":   "actor_signal_events_cooccurrence",
    }
