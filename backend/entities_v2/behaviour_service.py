"""
Entities V2 — Phase 6: Behaviour Engine
==========================================
Classifies entity behaviour from Holdings + Flows + Token Matrix.

Pipeline:
  entity_flows_v2        → net flow bias, velocity, direction
  entity_token_matrix_v2 → role breakdown, stablecoin dependency
  entity_holdings_v2     → portfolio structure, concentration

Output:
  behaviour_type: accumulation | distribution | market_making |
                  liquidity_provision | treasury | mixed
  confidence: 0.0 – 1.0
  drivers: list of human-readable reasons

Persisted to: entity_behaviour_v2
"""

import os
import time
from datetime import datetime, timezone
from pymongo import MongoClient, ASCENDING

_client = None
_db = None


def _get_db():
    global _client, _db
    if _db is None:
        _client = MongoClient(os.environ.get("MONGO_URL"))
        _db = _client[os.environ.get("DB_NAME", "test_database")]
    return _db


_cache: dict = {}
_CACHE_TTL = 300


def _cache_get(k: str):
    e = _cache.get(k)
    return e["data"] if e and time.time() - e["ts"] < _CACHE_TTL else None


def _cache_set(k: str, data):
    _cache[k] = {"data": data, "ts": time.time()}


# ══════════════════════════════════════════════════════════
#  SIGNAL EXTRACTION
# ══════════════════════════════════════════════════════════

def _extract_flow_signals(flow_data: dict) -> dict:
    """Extract behaviour signals from flow data."""
    all_time = flow_data.get("all_time", {})
    inflow = all_time.get("inflow_usd", 0)
    outflow = all_time.get("outflow_usd", 0)
    total = inflow + outflow

    if total <= 0:
        return {
            "has_flows": False,
            "net_flow_bias": 0,
            "direction": "none",
            "velocity": 0,
            "inflow_usd": 0,
            "outflow_usd": 0,
            "net_flow_usd": 0,
        }

    net = all_time.get("net_flow_usd", 0)
    inflow_ratio = inflow / total

    return {
        "has_flows": True,
        "net_flow_bias": round(inflow_ratio, 4),
        "direction": flow_data.get("direction", "balanced"),
        "velocity": flow_data.get("flow_velocity", 0),
        "inflow_usd": inflow,
        "outflow_usd": outflow,
        "net_flow_usd": net,
    }


def _extract_matrix_signals(matrix_data: dict) -> dict:
    """Extract behaviour signals from token flow matrix."""
    roles = matrix_data.get("role_breakdown", {})
    total_vol = matrix_data.get("total_flow_volume_usd", 0)

    # Volume share per role
    role_shares = {}
    for role_name, info in roles.items():
        vol = info.get("volume_usd", 0)
        role_shares[role_name] = round(vol / total_vol, 4) if total_vol > 0 else 0

    # Count accumulation vs distribution tokens (by count, not volume)
    accum_count = roles.get("accumulation_token", {}).get("count", 0)
    distrib_count = roles.get("distribution_token", {}).get("count", 0)
    liquidity_count = roles.get("liquidity_token", {}).get("count", 0)

    return {
        "has_matrix": total_vol > 0,
        "stablecoin_dependency": matrix_data.get("stablecoin_dependency", 0),
        "top3_concentration": matrix_data.get("top3_concentration", 0),
        "role_shares": role_shares,
        "accum_token_count": accum_count,
        "distrib_token_count": distrib_count,
        "liquidity_token_count": liquidity_count,
        "total_flow_volume_usd": total_vol,
        "priced_tokens": matrix_data.get("priced_tokens", 0),
    }


def _extract_holdings_signals(holdings_data: dict) -> dict:
    """Extract behaviour signals from holdings data."""
    portfolio = holdings_data.get("portfolio", {})
    total_usd = holdings_data.get("total_value_usd", 0)

    stable_share = 0
    major_share = 0
    altcoin_share = 0
    if total_usd > 0:
        for h in holdings_data.get("holdings", []):
            cls = h.get("token_class", "altcoin")
            share = h.get("value_usd", 0) / total_usd
            if cls == "stablecoin":
                stable_share += share
            elif cls == "major":
                major_share += share
            else:
                altcoin_share += share

    return {
        "has_holdings": total_usd > 0,
        "total_value_usd": total_usd,
        "stablecoin_share": round(stable_share, 4),
        "major_share": round(major_share, 4),
        "altcoin_share": round(altcoin_share, 4),
        "concentration": portfolio.get("concentration_score", 0),
    }


# ══════════════════════════════════════════════════════════
#  BEHAVIOUR CLASSIFICATION ENGINE
# ══════════════════════════════════════════════════════════

def _classify_behaviour(flow_sig: dict, matrix_sig: dict, holdings_sig: dict) -> dict:
    """
    Multi-signal behaviour classification.

    Returns: {behaviour_type, confidence, drivers}
    """
    scores = {
        "accumulation": 0.0,
        "distribution": 0.0,
        "market_making": 0.0,
        "liquidity_provision": 0.0,
        "treasury": 0.0,
    }
    drivers_map = {k: [] for k in scores}

    # ── No data at all ──
    if not flow_sig["has_flows"] and not matrix_sig["has_matrix"]:
        return {
            "behaviour_type": "mixed",
            "confidence": 0.0,
            "drivers": ["insufficient data"],
        }

    # ════════════════════════════════════════════
    # SIGNAL 1: Net Flow Bias
    # ════════════════════════════════════════════
    bias = flow_sig["net_flow_bias"]  # inflow / total
    direction = flow_sig["direction"]

    if bias >= 0.70:
        scores["accumulation"] += 0.30
        drivers_map["accumulation"].append("strong net inflow bias")
    elif bias >= 0.60:
        scores["accumulation"] += 0.15
        drivers_map["accumulation"].append("positive net flow")

    if bias <= 0.30:
        scores["distribution"] += 0.30
        drivers_map["distribution"].append("strong net outflow bias")
    elif bias <= 0.40:
        scores["distribution"] += 0.15
        drivers_map["distribution"].append("negative net flow")

    if 0.40 <= bias <= 0.60:
        scores["market_making"] += 0.15
        drivers_map["market_making"].append("balanced flows")
        scores["liquidity_provision"] += 0.15
        drivers_map["liquidity_provision"].append("balanced flows")

    # ════════════════════════════════════════════
    # SIGNAL 2: Stablecoin Dependency
    # ════════════════════════════════════════════
    stable_dep = matrix_sig["stablecoin_dependency"]

    if stable_dep >= 0.80:
        # High stablecoin flow + inflow = buy pressure (accumulation)
        if bias >= 0.60:
            scores["accumulation"] += 0.20
            drivers_map["accumulation"].append("stablecoin inflow dominance")
        # High stablecoin flow + outflow = sell pressure (distribution)
        elif bias <= 0.40:
            scores["distribution"] += 0.20
            drivers_map["distribution"].append("stablecoin outflow dominance")
        # High stablecoin + balanced = liquidity provision
        else:
            scores["liquidity_provision"] += 0.20
            drivers_map["liquidity_provision"].append("stablecoin-heavy balanced flow")

    if stable_dep >= 0.90:
        scores["liquidity_provision"] += 0.10
        drivers_map["liquidity_provision"].append("high stablecoin dependency")

    # ════════════════════════════════════════════
    # SIGNAL 3: Token Role Distribution
    # ════════════════════════════════════════════
    role_shares = matrix_sig["role_shares"]

    accum_share = role_shares.get("accumulation_token", 0)
    distrib_share = role_shares.get("distribution_token", 0)
    liquidity_share = role_shares.get("liquidity_token", 0)

    if accum_share >= 0.50:
        scores["accumulation"] += 0.15
        drivers_map["accumulation"].append("token accumulation pattern")
    if distrib_share >= 0.50:
        scores["distribution"] += 0.15
        drivers_map["distribution"].append("token distribution pattern")
    if liquidity_share >= 0.40:
        scores["liquidity_provision"] += 0.20
        drivers_map["liquidity_provision"].append("liquidity token dominance")
        scores["market_making"] += 0.10
        drivers_map["market_making"].append("liquidity token activity")

    # Token rotation: both accum and distrib tokens present with volume
    if matrix_sig["accum_token_count"] >= 1 and matrix_sig["distrib_token_count"] >= 1:
        if accum_share > 0 and distrib_share > 0:
            scores["market_making"] += 0.10
            drivers_map["market_making"].append("token rotation detected")

    # ════════════════════════════════════════════
    # SIGNAL 4: Flow Velocity
    # ════════════════════════════════════════════
    velocity = flow_sig["velocity"]

    if velocity >= 1_000_000:
        scores["market_making"] += 0.15
        drivers_map["market_making"].append("high flow velocity")
        scores["liquidity_provision"] += 0.10
        drivers_map["liquidity_provision"].append("high throughput")
    elif velocity >= 100_000:
        scores["market_making"] += 0.05
        drivers_map["market_making"].append("moderate flow velocity")
    elif velocity <= 10_000 and flow_sig["has_flows"]:
        scores["treasury"] += 0.20
        drivers_map["treasury"].append("low flow velocity")

    # ════════════════════════════════════════════
    # SIGNAL 5: Holdings Structure
    # ════════════════════════════════════════════
    if holdings_sig["has_holdings"]:
        h_stable = holdings_sig["stablecoin_share"]
        h_conc = holdings_sig["concentration"]

        # High stablecoin holdings + low velocity = treasury
        if h_stable >= 0.70 and velocity <= 50_000:
            scores["treasury"] += 0.15
            drivers_map["treasury"].append("stablecoin-heavy portfolio")

        # High concentration = less diversified, could be treasury
        if h_conc >= 80:
            scores["treasury"] += 0.05
            drivers_map["treasury"].append("concentrated portfolio")

        # Diversified holdings + high activity = market making
        if h_conc <= 40 and velocity >= 100_000:
            scores["market_making"] += 0.05
            drivers_map["market_making"].append("diversified active portfolio")

    # ════════════════════════════════════════════
    # FINAL CLASSIFICATION
    # ════════════════════════════════════════════
    # Pick the highest-scoring behaviour
    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]

    # If no signal strong enough → mixed
    if best_score < 0.10:
        return {
            "behaviour_type": "mixed",
            "confidence": round(best_score, 2),
            "drivers": ["no dominant behaviour pattern"],
        }

    # Confidence = best score normalized to 0-1 range
    # Max theoretical score ~ 0.80, normalize to 1.0
    confidence = min(1.0, round(best_score / 0.80, 2))

    # Check for mixed: if top two are very close
    sorted_scores = sorted(scores.values(), reverse=True)
    if len(sorted_scores) >= 2 and sorted_scores[0] > 0:
        gap = sorted_scores[0] - sorted_scores[1]
        if gap < 0.05 and best_score < 0.30:
            return {
                "behaviour_type": "mixed",
                "confidence": round(confidence * 0.7, 2),
                "drivers": drivers_map[best_type][:3] + ["weak signal differentiation"],
            }

    drivers = drivers_map[best_type][:5]
    return {
        "behaviour_type": best_type,
        "confidence": confidence,
        "drivers": drivers,
    }


# ══════════════════════════════════════════════════════════
#  BEHAVIOUR BUILDER
# ══════════════════════════════════════════════════════════

def build_entity_behaviour(slug: str) -> dict | None:
    """Build behaviour classification for a single entity."""
    db = _get_db()
    entity = db["entities_v2"].find_one({"slug": slug}, {"_id": 0})
    if not entity:
        return None

    # Gather data from previous phases
    flow_data = db["entity_flows_v2"].find_one({"entity_slug": slug}, {"_id": 0})
    matrix_data = db["entity_token_matrix_v2"].find_one({"entity_slug": slug}, {"_id": 0})
    holdings_data = db["entity_holdings_v2"].find_one({"entity_slug": slug}, {"_id": 0})

    # Extract signals
    flow_sig = _extract_flow_signals(flow_data or {})
    matrix_sig = _extract_matrix_signals(matrix_data or {})
    holdings_sig = _extract_holdings_signals(holdings_data or {})

    # Classify
    classification = _classify_behaviour(flow_sig, matrix_sig, holdings_sig)

    now = datetime.now(timezone.utc)

    result = {
        "entity": {
            "slug": entity["slug"],
            "name": entity["name"],
            "type": entity["type"],
            "category": entity["category"],
        },
        "behaviour_type": classification["behaviour_type"],
        "confidence": classification["confidence"],
        "drivers": classification["drivers"],
        "signals": {
            "flow": {
                "has_data": flow_sig["has_flows"],
                "direction": flow_sig["direction"],
                "net_flow_bias": flow_sig["net_flow_bias"],
                "velocity_usd": round(flow_sig["velocity"], 2),
                "inflow_usd": round(flow_sig["inflow_usd"], 2),
                "outflow_usd": round(flow_sig["outflow_usd"], 2),
                "net_flow_usd": round(flow_sig["net_flow_usd"], 2),
            },
            "token_matrix": {
                "has_data": matrix_sig["has_matrix"],
                "stablecoin_dependency": matrix_sig["stablecoin_dependency"],
                "top3_concentration": matrix_sig["top3_concentration"],
                "role_shares": matrix_sig["role_shares"],
                "priced_tokens": matrix_sig["priced_tokens"],
            },
            "holdings": {
                "has_data": holdings_sig["has_holdings"],
                "total_value_usd": round(holdings_sig["total_value_usd"], 2),
                "stablecoin_share": holdings_sig["stablecoin_share"],
                "concentration": holdings_sig["concentration"],
            },
        },
        "computed_at": now.isoformat(),
    }

    # Persist
    col = db["entity_behaviour_v2"]
    col.create_index([("entity_slug", ASCENDING)], unique=True, background=True)
    col.update_one(
        {"entity_slug": slug},
        {"$set": {"entity_slug": slug, **result, "computed_at": now.isoformat()}},
        upsert=True,
    )

    _cache.clear()
    return result


# ══════════════════════════════════════════════════════════
#  QUERY FUNCTIONS
# ══════════════════════════════════════════════════════════

def get_entity_behaviour(slug: str) -> dict | None:
    """Get behaviour classification for an entity."""
    ck = f"behaviour:{slug}"
    cached = _cache_get(ck)
    if cached:
        return cached

    db = _get_db()
    entity = db["entities_v2"].find_one({"slug": slug}, {"_id": 0})
    if not entity:
        return None

    stored = db["entity_behaviour_v2"].find_one({"entity_slug": slug}, {"_id": 0})
    if stored:
        stored.pop("entity_slug", None)
        _cache_set(ck, stored)
        return stored

    # Compute on-the-fly
    result = build_entity_behaviour(slug)
    if result:
        _cache_set(ck, result)
    return result


def build_all_behaviours() -> dict:
    """Build behaviour classifications for all entities."""
    db = _get_db()
    entities = list(db["entities_v2"].find({"status": "active"}, {"_id": 0, "slug": 1}))

    stats = {
        "total_entities": len(entities),
        "computed": 0,
        "by_type": {},
        "errors": 0,
    }

    for ent in entities:
        try:
            result = build_entity_behaviour(ent["slug"])
            if result:
                stats["computed"] += 1
                bt = result["behaviour_type"]
                stats["by_type"][bt] = stats["by_type"].get(bt, 0) + 1
        except Exception as e:
            stats["errors"] += 1
            print(f"[Behaviour] Error for {ent['slug']}: {e}")

    stats["built_at"] = datetime.now(timezone.utc).isoformat()
    _cache.clear()
    return stats


def get_behaviour_overview() -> dict:
    """Overview of all entity behaviours — distribution of types."""
    db = _get_db()
    all_behaviours = list(db["entity_behaviour_v2"].find({}, {"_id": 0}))

    if not all_behaviours:
        return {
            "total_entities": 0,
            "type_distribution": {},
            "entities": [],
        }

    type_dist: dict = {}
    entity_list = []

    for b in all_behaviours:
        bt = b.get("behaviour_type", "mixed")
        type_dist[bt] = type_dist.get(bt, 0) + 1

        entity_list.append({
            "slug": b.get("entity", {}).get("slug", b.get("entity_slug", "?")),
            "name": b.get("entity", {}).get("name", "?"),
            "type": b.get("entity", {}).get("type", "?"),
            "behaviour_type": bt,
            "confidence": b.get("confidence", 0),
            "drivers": b.get("drivers", []),
        })

    # Sort by confidence descending
    entity_list.sort(key=lambda x: x["confidence"], reverse=True)

    return {
        "total_entities": len(all_behaviours),
        "type_distribution": type_dist,
        "entities": entity_list,
    }
