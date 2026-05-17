"""
Narrative Flow Adapter
======================
Overrides /api/narrative-flow with REAL data aggregated from
actor_signal_events.  The legacy `alt_season_routes.run_narrative_flow()`
returns empty arrays for narratives/rotations/frontRuns; this adapter
provides the same shape filled with live aggregations so the
NarrativesPage UI surfaces real Top Picks / Tokens / Rotations.
"""
from __future__ import annotations

import math
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter
from pymongo import MongoClient, DESCENDING

router = APIRouter(tags=["narrative-flow-adapter"])

_client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
_db = _client[os.environ.get("DB_NAME", "fomo_mobile")]


@router.get("/api/narrative-flow")
async def narrative_flow():
    """
    Compose narratives from actor_signal_events:
      • Group events by token, compute strength, dispersion, freshness
      • Identify rotations (token freshness rising or new actors)
      • Identify front-runs (low-signal tokens with single insider actor)
      • Top picks = ORGANIC + high strength
    """
    now = datetime.now(timezone.utc)
    cutoff_24h_iso = (now - timedelta(hours=24)).isoformat()
    cutoff_6h_iso  = (now - timedelta(hours=6)).isoformat()

    pipeline = [
        {"$match": {"token": {"$ne": None}}},
        {"$group": {
            "_id":      "$token",
            "signals":  {"$sum": 1},
            "actors":   {"$addToSet": "$actor_handle"},
            "signals24h": {
                "$sum": {"$cond": [{"$gte": ["$ingested_at", cutoff_24h_iso]}, 1, 0]}
            },
            "signals6h": {
                "$sum": {"$cond": [{"$gte": ["$ingested_at", cutoff_6h_iso]}, 1, 0]}
            },
            "lastSeen": {"$max": "$ingested_at"},
            "firstSeen": {"$min": "$ingested_at"},
        }},
        {"$project": {
            "_id":         0,
            "token":       "$_id",
            "signals":     1,
            "uniqueActors": {"$size": "$actors"},
            "actors":      1,
            "signals24h":  1,
            "signals6h":   1,
            "lastSeen":    1,
            "firstSeen":   1,
        }},
        {"$sort": {"signals": -1}},
        {"$limit": 80},
    ]
    rows = list(_db.actor_signal_events.aggregate(pipeline))

    narratives: List[Dict[str, Any]] = []
    rotations:  List[Dict[str, Any]] = []
    front_runs: List[Dict[str, Any]] = []
    top_picks:  List[Dict[str, Any]] = []
    tokens:     List[Dict[str, Any]] = []
    origins:    List[Dict[str, Any]] = []

    for r in rows:
        tok = r["token"]
        signals  = int(r.get("signals", 0))
        sig24h   = int(r.get("signals24h", 0))
        sig6h    = int(r.get("signals6h", 0))
        uniq     = int(r.get("uniqueActors", 0))
        if uniq >= 5 and signals >= 30:
            classification = "ORGANIC"
        elif uniq <= 2 and signals >= 20:
            classification = "PUMP_LIKE"
        elif uniq <= 1:
            classification = "ISOLATED"
        else:
            classification = "EMERGING"

        strength = round(min(1.0, uniq * math.log(signals + 1) / 12.0), 3)
        velocity = round(sig6h / max(sig24h / 4, 1e-6), 3)  # vs 6h slice of 24h avg

        # Phase / action / confidence (UI-friendly strings)
        if classification == "ORGANIC" and sig24h > 10:
            phase = "EXPANSION"
            action = "FOLLOW"
        elif classification == "ORGANIC":
            phase = "MATURE"
            action = "HOLD"
        elif classification == "PUMP_LIKE":
            phase = "IGNITION"
            action = "AVOID"
        elif classification == "EMERGING":
            phase = "FORMATION"
            action = "WATCH"
        else:
            phase = "DORMANT"
            action = "PASS"

        confidence_num = round(min(1.0, signals / 50.0), 3)
        confidence_label = "HIGH" if confidence_num >= 0.7 else "MEDIUM" if confidence_num >= 0.3 else "LOW"

        narrative_obj = {
            "name":            tok,
            "token":           tok,
            "tokens":          [tok],
            "phase":           phase,
            "action":          action,
            "score":           strength,                # 0..1 — used by UI as score*100
            "signals":         signals,
            "signals24h":      sig24h,
            "signals6h":       sig6h,
            "uniqueActors":    uniq,
            "influencers":     uniq,                    # UI alias
            "actors":          (r.get("actors") or [])[:10],
            "classification":  classification,
            "strength":        strength,
            "confidence":      confidence_label,        # HIGH/MEDIUM/LOW for UI
            "confidenceScore": confidence_num,
            "mentions":        signals,                 # alias for UI
            "mentionCount":    signals * 5,
            "velocity":        velocity,
            "lastSeen":        r.get("lastSeen"),
            "firstSeen":       r.get("firstSeen"),
        }
        narratives.append(narrative_obj)
        tokens.append({"symbol": tok, "signals": signals, "actors": uniq, "classification": classification})

        # Rotations — narratives whose recent 6h signals account for >40% of 24h
        if sig24h > 5 and sig6h / sig24h > 0.4:
            rotations.append({
                "token":      tok,
                "trigger":    "fresh_burst",
                "share6h":    round(sig6h / sig24h, 3),
                "signals6h":  sig6h,
                "signals24h": sig24h,
                "primaryActors": (r.get("actors") or [])[:5],
            })

        # Front-runs — single-actor tokens with growing presence
        if uniq == 1 and signals >= 5 and signals <= 25:
            front_runs.append({
                "token":   tok,
                "actor":   (r.get("actors") or [None])[0],
                "signals": signals,
                "alpha":   "single-actor-accumulation",
            })

        # Top picks — ORGANIC with high strength
        if classification == "ORGANIC" and strength >= 0.5:
            top_picks.append({
                "token":     tok,
                "score":     int(strength * 100),
                "rationale": f"{uniq} actors · {signals} signals · sustained dispersion",
                "actors":    (r.get("actors") or [])[:5],
            })

    # Origin — top actor → tokens pushed
    actor_signals = defaultdict(int)
    actor_tokens  = defaultdict(set)
    for r in rows:
        for a in (r.get("actors") or []):
            actor_signals[a] += r["signals"]
            actor_tokens[a].add(r["token"])
    for actor, score in sorted(actor_signals.items(), key=lambda x: x[1], reverse=True)[:10]:
        origins.append({
            "actor":      actor,
            "score":      score,
            "tokenCount": len(actor_tokens[actor]),
            "tokens":     sorted(actor_tokens[actor])[:8],
        })

    # Trade setup = top pick (if any)
    trade_setup = None
    if top_picks:
        tp = top_picks[0]
        trade_setup = {
            "token":   tp["token"],
            "side":    "LONG",
            "score":   tp["score"],
            "reason":  tp["rationale"],
            "actors":  tp["actors"],
        }

    narratives.sort(key=lambda x: x["strength"], reverse=True)
    rotations.sort(key=lambda x: x.get("share6h", 0), reverse=True)
    top_picks.sort(key=lambda x: x["score"], reverse=True)

    return {
        "ok":          True,
        "tradeSetup":  trade_setup,
        "narratives":  narratives[:20],
        "rotations":   rotations[:10],
        "frontRuns":   front_runs[:10],
        "topPicks":    top_picks[:10],
        "tokens":      tokens[:30],
        "origins":     origins,
        "asOf":        now.isoformat(),
        "source":      "actor_signal_events_aggregation",
    }
