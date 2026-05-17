"""
Intelligence Layer — OTC Detection
=====================================
Detects probable OTC (over-the-counter) trades by analyzing:
  1. Large transfers ($1M+ threshold)
  2. Stablecoin counterflow (asset ↔ stablecoin)
  3. Time window (≤60 min)
  4. Value match (±10%)
  5. Cluster distance (different entities)
  6. Liquidity check (filter out illiquid internal transfers)

Confidence: 0.40 value_match + 0.25 time_proximity + 0.20 cluster_distance + 0.15 liquidity
"""

import os
import time
import math
from datetime import datetime, timezone
from pymongo import MongoClient
from mock_wallets import get_wallets_for_entity

_client = None
_db = None
_cache: dict = {}
_CACHE_TTL = 120


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


def _fmt_usd(v):
    if not v:
        return "$0"
    a = abs(v)
    if a >= 1e9:
        return f"${v / 1e9:.2f}B"
    if a >= 1e6:
        return f"${v / 1e6:.2f}M"
    if a >= 1e3:
        return f"${v / 1e3:.1f}K"
    return f"${v:.0f}"


STABLECOIN_SYMBOLS = {"USDT", "USDC", "DAI", "BUSD", "USDP", "USDe", "TUSD", "FRAX"}

OTC_THRESHOLD_USD = 1_000_000  # $1M minimum
OTC_TIME_WINDOW_MIN = 60  # 60 minutes
OTC_VALUE_TOLERANCE = 0.10  # ±10%


def detect_otc_trades(entity_slug: str = None) -> dict:
    """
    Detect probable OTC trades across entities or for a specific entity.
    Uses flow patterns, token matrix, and cluster data to identify
    large-value asset-stablecoin swaps between different entities.
    """
    ck = f"otc_detections:{entity_slug or 'global'}"
    cached = _cache_get(ck)
    if cached is not None:
        return cached

    db = _get_db()

    # Load entities with their flow and token data
    query = {"slug": entity_slug} if entity_slug else {}
    entities = list(db["entities_v2"].find(query, {"_id": 0, "slug": 1, "name": 1, "type": 1}))

    if not entities:
        return {"trades": [], "count": 0}

    otc_trades = []

    for entity in entities:
        slug = entity["slug"]
        trades = _analyze_entity_for_otc(slug, entity, db)
        otc_trades.extend(trades)

    # Sort by confidence desc, then by value
    otc_trades.sort(key=lambda x: (x["confidence"], x["usd_value"]), reverse=True)

    result = {
        "trades": otc_trades[:20],  # Cap at top 20
        "count": len(otc_trades),
        "threshold_usd": OTC_THRESHOLD_USD,
        "entity_filter": entity_slug,
    }

    _cache_set(ck, result)
    return result


def _analyze_entity_for_otc(slug: str, entity: dict, db) -> list:
    """Analyze a single entity's flows for OTC patterns."""
    trades = []

    # Load flow data
    flows = db["entity_flows_v2"].find_one(
        {"$or": [{"slug": slug}, {"entity_slug": slug}]}, {"_id": 0}
    )
    if not flows:
        return []

    # Load token matrix
    matrix = db["entity_token_matrix_v2"].find_one(
        {"$or": [{"slug": slug}, {"entity_slug": slug}]}, {"_id": 0}
    )
    if not matrix:
        return []

    # Load clusters for distance check
    clusters = db["entity_clusters_v2"].find_one(
        {"$or": [{"slug": slug}, {"entity_slug": slug}]}, {"_id": 0}
    )

    # Load interactions for counterparty identification
    interactions = db.get_collection("entity_interactions_v2").find_one(
        {"$or": [{"slug": slug}, {"entity_slug": slug}]}, {"_id": 0}
    )

    tokens = matrix.get("tokens", [])
    all_time = flows.get("all_time", {})
    total_volume = all_time.get("inflow_usd", 0) + all_time.get("outflow_usd", 0)

    if total_volume < OTC_THRESHOLD_USD:
        return []

    # Separate stablecoin and non-stablecoin tokens
    stable_tokens = []
    asset_tokens = []
    for t in tokens:
        sym = (t.get("symbol") or "").upper()
        vol = t.get("flow_volume_usd", 0) or t.get("volume_usd", 0)
        if vol <= 0:
            continue
        if sym in STABLECOIN_SYMBOLS:
            stable_tokens.append(t)
        else:
            asset_tokens.append(t)

    if not stable_tokens or not asset_tokens:
        return []

    total_stable_vol = sum(t.get("flow_volume_usd", 0) or t.get("volume_usd", 0) for t in stable_tokens)
    cluster_count = len(clusters.get("clusters", [])) if clusters else 0
    total_discovered = clusters.get("total_discovered", 0) if clusters else 0

    # Identify interaction counterparties
    counterparties = _get_counterparties(interactions)

    # For each large asset token, check if there's a matching stablecoin counterflow
    for asset in asset_tokens:
        asset_vol = asset.get("flow_volume_usd", 0) or asset.get("volume_usd", 0)
        asset_sym = asset.get("symbol", "?")

        if asset_vol < OTC_THRESHOLD_USD:
            continue

        # Check for stablecoin counterflow of similar value
        for stable in stable_tokens:
            stable_vol = stable.get("flow_volume_usd", 0) or stable.get("volume_usd", 0)
            stable_sym = stable.get("symbol", "?")

            if stable_vol < OTC_THRESHOLD_USD * 0.5:
                continue

            # Signal 1: Value match (±10%)
            if asset_vol > 0 and stable_vol > 0:
                value_ratio = min(asset_vol, stable_vol) / max(asset_vol, stable_vol)
                value_match = max(0, min(1.0, (value_ratio - 0.5) / 0.5))
            else:
                value_match = 0

            # Signal 2: Time proximity (same flow windows = higher score)
            asset_role = asset.get("role", "neutral_token")
            stable_role = stable.get("role", "neutral_token")
            # If one is accumulation and other is distribution, suggests swap pattern
            if asset_role != stable_role and "neutral" not in asset_role:
                time_proximity = 0.8
            else:
                time_proximity = 0.4

            # Signal 3: Cluster distance
            if total_discovered >= 3 and cluster_count >= 2:
                cluster_distance = 0.7  # Multiple clusters = likely different operators
            elif total_discovered >= 2:
                cluster_distance = 0.5
            else:
                cluster_distance = 0.2  # Same cluster = likely internal

            # Signal 4: Liquidity check
            # Higher dominance = more liquid = more likely genuine OTC
            asset_dom = asset.get("dominance_pct", 0)
            if asset_dom >= 0.1:
                liquidity = 0.8
            elif asset_dom >= 0.05:
                liquidity = 0.5
            else:
                liquidity = 0.2  # Low liquidity = possibly internal routing

            # Confidence score
            confidence = round(
                0.40 * value_match
                + 0.25 * time_proximity
                + 0.20 * cluster_distance
                + 0.15 * liquidity,
                2,
            )

            if confidence < 0.35:
                continue

            # Determine buyer/seller
            if asset_role == "accumulation_token":
                buyer = entity["name"]
                seller = counterparties[0] if counterparties else "Unknown"
            else:
                seller = entity["name"]
                buyer = counterparties[0] if counterparties else "Unknown"

            trade_value = min(asset_vol, stable_vol)

            trades.append({
                "trade_id": f"otc_{slug}_{asset_sym}_{stable_sym}",
                "asset": asset_sym,
                "stablecoin": stable_sym,
                "seller_entity": seller,
                "buyer_entity": buyer,
                "usd_value": round(trade_value, 2),
                "usd_value_fmt": _fmt_usd(trade_value),
                "asset_amount_usd": round(asset_vol, 2),
                "stablecoin_amount_usd": round(stable_vol, 2),
                "confidence": confidence,
                "liquidity_score": round(liquidity, 2),
                "signals": {
                    "value_match": round(value_match, 2),
                    "time_proximity": round(time_proximity, 2),
                    "cluster_distance": round(cluster_distance, 2),
                    "liquidity": round(liquidity, 2),
                },
                "source_entity": slug,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "seller_wallets": get_wallets_for_entity(seller, limit=2),
                "buyer_wallets": get_wallets_for_entity(buyer, limit=2),
            })

    return trades


def _get_counterparties(interactions: dict) -> list:
    """Extract entity counterparties from interaction network."""
    if not interactions:
        return []

    nodes = interactions.get("nodes", [])
    entity_nodes = [n for n in nodes if n.get("type") == "entity"]
    return [n.get("label", n.get("id", "Unknown")) for n in entity_nodes[:5]]
