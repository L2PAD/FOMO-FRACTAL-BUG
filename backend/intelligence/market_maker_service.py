"""
Intelligence Layer — Market Maker Detection
==============================================
Detects probable hidden market makers by analyzing 4 signals:
  1. Bidirectional Flow Ratio — inflow ≈ outflow (ratio < 0.25)
  2. Exchange Interaction Density — ≥3 venue interactions
  3. Stablecoin Recycling — stablecoin_flow / total_flow > 0.4
  4. Velocity — volume / portfolio_size > 2

Score: 0.35 bidirectional + 0.25 exchange_density + 0.25 stablecoin_recycling + 0.15 velocity
If score > 0.7 → probable market maker
"""

import os
import time
import math
from pymongo import MongoClient
from mock_wallets import get_wallets_for_entity

_client = None
_db = None
_cache: dict = {}
_CACHE_TTL = 300


def _get_db():
    global _client, _db
    if _db is None:
        _client = MongoClient(os.environ.get("MONGO_URL"))
        _db = _client[os.environ.get("DB_NAME", "intelligence_engine")]
    return _db


def _cache_get(k):
    e = _cache.get(k)
    return e["data"] if e and time.time() - e["ts"] < _CACHE_TTL else None


def _cache_set(k, data):
    _cache[k] = {"data": data, "ts": time.time()}


MM_THRESHOLD = 0.50  # Minimum score to flag as probable MM


def detect_market_makers() -> dict:
    """
    Scan all entities for hidden market maker patterns.
    Returns scored list of probable market makers.
    """
    ck = "market_maker_detections"
    cached = _cache_get(ck)
    if cached is not None:
        return cached

    db = _get_db()
    entities = list(db["entities_v2"].find({}, {"_id": 0, "slug": 1, "name": 1, "type": 1}))

    detections = []

    for entity in entities:
        slug = entity["slug"]
        score_data = _score_entity_as_mm(slug, entity, db)
        if score_data and score_data["score"] >= MM_THRESHOLD:
            detections.append(score_data)

    detections.sort(key=lambda x: x["score"], reverse=True)

    result = {
        "market_makers": detections,
        "count": len(detections),
        "threshold": MM_THRESHOLD,
        "total_entities_scanned": len(entities),
    }

    _cache_set(ck, result)
    return result


def _score_entity_as_mm(slug: str, entity: dict, db) -> dict | None:
    """Score a single entity for market maker characteristics."""
    flows = db["entity_flows_v2"].find_one(
        {"$or": [{"slug": slug}, {"entity_slug": slug}]}, {"_id": 0}
    )
    if not flows:
        return None

    matrix = db["entity_token_matrix_v2"].find_one(
        {"$or": [{"slug": slug}, {"entity_slug": slug}]}, {"_id": 0}
    )
    holdings = db["entity_holdings_v2"].find_one(
        {"$or": [{"slug": slug}, {"entity_slug": slug}]}, {"_id": 0}
    )
    interactions = db.get_collection("entity_interactions_v2").find_one(
        {"$or": [{"slug": slug}, {"entity_slug": slug}]}, {"_id": 0}
    )

    all_time = flows.get("all_time", {})
    inflow = all_time.get("inflow_usd", 0)
    outflow = all_time.get("outflow_usd", 0)
    volume = inflow + outflow

    if volume < 100_000:
        return None

    # Signal 1: Bidirectional Flow Ratio
    # ratio = abs(inflow - outflow) / volume — lower = more bidirectional
    if volume > 0:
        asymmetry = abs(inflow - outflow) / volume
        bidirectional = max(0, 1.0 - asymmetry * 4)  # 0.25 asymmetry → 0 score
    else:
        bidirectional = 0

    # Signal 2: Exchange Interaction Density
    venue_count = 0
    if interactions:
        nodes = interactions.get("nodes", [])
        exchange_nodes = [n for n in nodes if n.get("type") in ("exchange", "dex", "protocol")]
        venue_count = len(exchange_nodes)
    exchange_density = min(1.0, venue_count / 5)  # 5+ venues = max score

    # Signal 3: Stablecoin Recycling
    stablecoin_dep = 0
    if matrix:
        stablecoin_dep = matrix.get("stablecoin_dependency", 0)
    stablecoin_recycling = min(1.0, stablecoin_dep / 0.6) if stablecoin_dep >= 0.2 else 0

    # Signal 4: Velocity (volume / portfolio_size)
    portfolio_value = holdings.get("total_value_usd", 0) if holdings else 0
    if portfolio_value > 0:
        velocity_ratio = volume / portfolio_value
        velocity = min(1.0, velocity_ratio / 5)  # 5x turnover = max score
    else:
        velocity = 0.5  # Unknown portfolio, moderate assumption

    # Weighted score
    score = round(
        0.35 * bidirectional
        + 0.25 * exchange_density
        + 0.25 * stablecoin_recycling
        + 0.15 * velocity,
        2,
    )

    # Classification
    if score >= 0.7:
        mm_type = "market_maker"
    elif score >= 0.5:
        mm_type = "probable_mm"
    else:
        mm_type = "unlikely"

    return {
        "entity": slug,
        "name": entity.get("name", slug),
        "entity_type": entity.get("type", "unknown"),
        "type": mm_type,
        "score": score,
        "signals": {
            "bidirectional_flow": round(bidirectional, 2),
            "exchange_density": round(exchange_density, 2),
            "stablecoin_recycling": round(stablecoin_recycling, 2),
            "velocity": round(velocity, 2),
        },
        "details": {
            "volume_usd": round(volume, 2),
            "inflow_outflow_ratio": round(inflow / max(outflow, 1), 2),
            "venue_count": venue_count,
            "stablecoin_dependency": round(stablecoin_dep, 4),
        },
        "wallet_addresses": get_wallets_for_entity(entity.get("name", slug), limit=3),
    }
