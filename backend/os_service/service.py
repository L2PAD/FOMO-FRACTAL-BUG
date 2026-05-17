"""
OS Service — Market Intelligence OS
=====================================
Aggregates snapshot data from multiple sources for the OS page.
NEVER runs calculations — only reads from pre-computed collections.

Endpoints:
  GET /api/os/state          — full OS state (market + pressure + opportunities + alerts)
  GET /api/os/opportunities  — active market opportunities
"""

import os
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, DESCENDING

_client = None
_db = None


def _get_db():
    global _client, _db
    if _db is None:
        _client = MongoClient(os.environ.get("MONGO_URL"))
        _db = _client[os.environ.get("DB_NAME", "test_database")]
    return _db


def _get_market_state() -> dict:
    """Read latest engine snapshot for market state."""
    db = _get_db()
    snap = db["engine_context_snapshots"].find_one(
        {}, {"_id": 0, "created_at": 0}, sort=[("timestamp", DESCENDING)]
    )
    if not snap:
        return {}

    regime = snap.get("regime_engine", {}).get("primary", {})
    setup = snap.get("setup_engine", {}).get("primary", {})
    flow = snap.get("flow_engine", {})
    prob = snap.get("probability_layer", {})

    return {
        "regime": regime.get("type", "neutral_chop"),
        "regime_status": regime.get("status", "weak"),
        "regime_confidence": regime.get("confidence", 0),
        "setup": setup.get("type", "mixed"),
        "setup_status": setup.get("status", "weak"),
        "setup_confidence": setup.get("confidence", 0),
        "flow_state": flow.get("state", "neutral"),
        "flow_strength": flow.get("strength", 0),
        "decision": snap.get("decision", "NEUTRAL"),
        "confidence_score": snap.get("confidence", {}).get("score", 0),
        "confidence_level": snap.get("confidence", {}).get("level", "LOW"),
        "composite": snap.get("scores", {}).get("composite", 50),
        "probability_continuation": prob.get("continuation", 0),
        "probability_failure": prob.get("failure", 0),
        "snapshot_timestamp": snap.get("timestamp"),
    }


def _get_top_opportunity(snap: dict = None) -> dict:
    """Extract top opportunity from engine setup + probability."""
    db = _get_db()
    if not snap:
        snap = db["engine_context_snapshots"].find_one(
            {}, {"_id": 0, "created_at": 0}, sort=[("timestamp", DESCENDING)]
        )
    if not snap:
        return {}

    setup = snap.get("setup_engine", {}).get("primary", {})
    prob = snap.get("probability_layer", {})
    liq = snap.get("liquidity_map", {})
    targets = liq.get("target_zones", [])

    primary_target = targets[0] if targets else {}

    return {
        "setup": setup.get("type", "mixed"),
        "status": setup.get("status", "weak"),
        "confidence": setup.get("confidence", 0),
        "probability": prob.get("continuation", 0),
        "target": primary_target.get("reason", ""),
        "target_direction": primary_target.get("direction", "neutral"),
        "supports": setup.get("supports", [])[:3],
        "window": setup.get("window", ""),
    }


def _get_actor_pressure() -> dict:
    """Read actor pressure from entities data."""
    db = _get_db()

    # Read latest engine snapshot for entity/actor data
    snap = db["engine_context_snapshots"].find_one(
        {}, {"_id": 0, "context_matrix": 1}, sort=[("timestamp", DESCENDING)]
    )

    if not snap:
        return {"bullish": 0, "bearish": 0, "neutral": 0, "actors": []}

    matrix = snap.get("context_matrix", {})
    entities = matrix.get("entities", {})
    sm = matrix.get("smart_money", {})

    # Derive pressure from scores
    entity_score = entities.get("score", 50)
    sm_score = sm.get("score", 50)

    # Categorize
    bullish = 0
    bearish = 0
    neutral = 0

    actors = []

    # Smart money pressure
    if sm_score >= 60:
        bullish += 1
        actors.append({"name": "Smart Money", "action": "accumulating", "score": sm_score})
    elif sm_score <= 40:
        bearish += 1
        actors.append({"name": "Smart Money", "action": "distributing", "score": sm_score})
    else:
        neutral += 1
        actors.append({"name": "Smart Money", "action": "neutral", "score": sm_score})

    # Entity pressure
    if entity_score >= 60:
        bullish += 1
        actors.append({"name": "Key Entities", "action": "accumulating", "score": entity_score})
    elif entity_score <= 40:
        bearish += 1
        actors.append({"name": "Key Entities", "action": "distributing", "score": entity_score})
    else:
        neutral += 1
        actors.append({"name": "Key Entities", "action": "neutral", "score": entity_score})

    # CEX pressure
    cex = matrix.get("cex", {})
    cex_score = cex.get("score", 50)
    if cex_score >= 60:
        bullish += 1
        actors.append({"name": "Exchanges", "action": "outflows (bullish)", "score": cex_score})
    elif cex_score <= 40:
        bearish += 1
        actors.append({"name": "Exchanges", "action": "inflows (bearish)", "score": cex_score})
    else:
        neutral += 1
        actors.append({"name": "Exchanges", "action": "neutral flows", "score": cex_score})

    # Token metrics
    token = matrix.get("token", {})
    token_score = token.get("score", 50)
    if token_score >= 60:
        bullish += 1
        actors.append({"name": "Token Metrics", "action": "bullish structure", "score": token_score})
    elif token_score <= 40:
        bearish += 1
        actors.append({"name": "Token Metrics", "action": "bearish structure", "score": token_score})
    else:
        neutral += 1
        actors.append({"name": "Token Metrics", "action": "neutral", "score": token_score})

    return {
        "bullish": bullish,
        "bearish": bearish,
        "neutral": neutral,
        "actors": actors,
    }


def _get_liquidity_targets() -> list:
    """Read liquidity targets from engine snapshot."""
    db = _get_db()
    snap = db["engine_context_snapshots"].find_one(
        {}, {"_id": 0, "liquidity_map": 1}, sort=[("timestamp", DESCENDING)]
    )
    if not snap:
        return []

    liq = snap.get("liquidity_map", {})
    targets = liq.get("target_zones", [])
    magnets = liq.get("magnet_zones", [])
    voids = liq.get("void_zones", [])

    result = []
    for t in targets[:3]:
        result.append({**t, "zone_type": "target"})
    for m in magnets[:2]:
        result.append({**m, "zone_type": "magnet"})
    for v in voids[:2]:
        result.append({**v, "zone_type": "void"})

    return result


def _get_active_alerts(limit: int = 8) -> list:
    """Read active non-expired alerts."""
    db = _get_db()
    now = datetime.now(timezone.utc).isoformat()
    return list(
        db["engine_alerts"].find(
            {"expires_at": {"$gte": now}},
            {"_id": 0},
        ).sort("timestamp", DESCENDING).limit(limit)
    )


def _get_market_risk() -> dict:
    """Read market risk from latest engine snapshot."""
    db = _get_db()
    snap = db["engine_context_snapshots"].find_one(
        {}, {"_id": 0, "risk_engine": 1}, sort=[("timestamp", DESCENDING)]
    )
    if not snap:
        return {}
    return snap.get("risk_engine", {})


def get_os_state() -> dict:
    """Aggregate full OS state from snapshot data. Zero calculations."""
    db = _get_db()

    # Read the full snapshot once
    snap = db["engine_context_snapshots"].find_one(
        {}, {"_id": 0, "created_at": 0}, sort=[("timestamp", DESCENDING)]
    )

    return {
        "market_state": _get_market_state(),
        "market_risk": _get_market_risk(),
        "market_pulse": get_market_pulse(),
        "regime_timeline": get_regime_timeline(),
        "actor_radar": get_actor_radar(),
        "liquidity_evolution": get_liquidity_evolution(),
        "opportunities": get_os_opportunities(),
        "actor_pressure": _get_actor_pressure(),
        "liquidity_targets": _get_liquidity_targets(),
        "alerts": _get_active_alerts(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def get_regime_timeline(limit: int = 20) -> list:
    """Read regime change history for the timeline block."""
    db = _get_db()
    docs = list(
        db["engine_regime_history"].find(
            {}, {"_id": 0}
        ).sort("timestamp", DESCENDING).limit(limit)
    )
    return docs


def get_actor_radar() -> dict:
    """Aggregate actor activity from engine snapshot data.
    Returns state for: smart_money, exchanges, market_makers, funds, whales
    Each has: action, direction (up/down/neutral), strength (0-100)
    """
    db = _get_db()
    snap = db["engine_context_snapshots"].find_one(
        {}, {"_id": 0, "context_matrix": 1, "flow_engine": 1, "otc_data": 1, "mm_data": 1},
        sort=[("timestamp", DESCENDING)]
    )
    if not snap:
        return {"actors": [], "summary": "No data"}

    matrix = snap.get("context_matrix", {})
    flow = snap.get("flow_engine", {})
    otc = snap.get("otc_data", {})
    mm = snap.get("mm_data", {})

    def _classify(score: float) -> tuple:
        """Returns (action, direction) based on score 0-100."""
        if score >= 70:
            return "accumulating", "up"
        elif score >= 55:
            return "buying", "up"
        elif score <= 30:
            return "distributing", "down"
        elif score <= 45:
            return "selling", "down"
        return "neutral", "neutral"

    actors = []

    # Smart Money
    sm = matrix.get("smart_money", {})
    sm_score = sm.get("score", 50)
    sm_action, sm_dir = _classify(sm_score)
    actors.append({
        "id": "smart_money",
        "name": "Smart Money",
        "action": sm_action,
        "direction": sm_dir,
        "strength": round(sm_score),
    })

    # Exchanges
    cex = matrix.get("cex", {})
    cex_score = cex.get("score", 50)
    # For exchanges, high score = outflows = bullish; low = inflows = bearish
    if cex_score >= 60:
        cex_action, cex_dir = "withdrawing", "up"
    elif cex_score <= 40:
        cex_action, cex_dir = "depositing", "down"
    else:
        cex_action, cex_dir = "neutral", "neutral"
    actors.append({
        "id": "exchanges",
        "name": "Exchanges",
        "action": cex_action,
        "direction": cex_dir,
        "strength": round(cex_score),
    })

    # Market Makers
    makers = mm.get("market_makers", [])
    if makers:
        avg_mm_score = sum(m.get("score", 0) for m in makers) / len(makers)
        mm_pct = round(avg_mm_score * 100)
        if mm_pct >= 60:
            mm_action, mm_dir = "providing liquidity", "up"
        elif mm_pct <= 30:
            mm_action, mm_dir = "withdrawing liquidity", "down"
        else:
            mm_action, mm_dir = "neutral", "neutral"
    else:
        mm_pct = 50
        mm_action, mm_dir = "neutral", "neutral"
    actors.append({
        "id": "market_makers",
        "name": "Market Makers",
        "action": mm_action,
        "direction": mm_dir,
        "strength": mm_pct,
    })

    # Funds (derived from entities data)
    ent = matrix.get("entities", {})
    ent_score = ent.get("score", 50)
    ent_action, ent_dir = _classify(ent_score)
    actors.append({
        "id": "funds",
        "name": "Funds",
        "action": ent_action,
        "direction": ent_dir,
        "strength": round(ent_score),
    })

    # Whales (derived from OTC + large flow signals)
    otc_trades = otc.get("trades", [])
    otc_count = len(otc_trades)
    flow_strength = flow.get("strength", 0)
    # Whale activity: combine OTC volume + flow strength
    whale_score = min(round(flow_strength * 60 + (otc_count / 3) * 40), 100)
    whale_action, whale_dir = _classify(whale_score)
    actors.append({
        "id": "whales",
        "name": "Whales",
        "action": whale_action,
        "direction": whale_dir,
        "strength": whale_score,
    })

    # Summary
    bullish = sum(1 for a in actors if a["direction"] == "up")
    bearish = sum(1 for a in actors if a["direction"] == "down")
    if bullish > bearish:
        summary = "Net Bullish"
    elif bearish > bullish:
        summary = "Net Bearish"
    else:
        summary = "Mixed"

    return {
        "actors": actors,
        "summary": summary,
        "bullish_count": bullish,
        "bearish_count": bearish,
    }


def get_liquidity_evolution(limit: int = 10) -> list:
    """Read recent liquidity zone dynamics for evolution display."""
    db = _get_db()
    latest = db["liquidity_level_history"].find_one(
        {}, {"_id": 0}, sort=[("timestamp", DESCENDING)]
    )
    if not latest:
        return []
    return latest.get("dynamics", [])



STATUS_MULTIPLIER = {
    "confirmed": 1.1,
    "active": 0.9,
    "forming": 0.7,
    "weakening": 0.5,
    "weak": 0.4,
}

# Map setup type → asset context label
SETUP_ASSET_CONTEXT = {
    "liquidity_shock": "CEX Liquidity",
    "exchange_drain": "CEX Outflows",
    "smart_money_accumulation": "Smart Money",
    "distribution_risk": "Distribution",
    "rotation": "Token Rotation",
    "actor_conflict": "Actor Conflict",
    "otc_transfer": "OTC",
}


def _get_opportunity_chains() -> list:
    """Get active EVM chains from entity_activity."""
    db = _get_db()
    try:
        chains = db["entity_activity"].distinct("chain")
        return sorted(chains) if chains else ["ethereum"]
    except Exception:
        return ["ethereum"]


def _derive_opp_asset(setup_type: str, cm: dict, chains: list) -> str:
    """Derive opportunity asset label from on-chain context instead of hardcoded BTC."""
    chain_tag = "/".join(c[:3].upper() for c in chains[:3])
    base_label = SETUP_ASSET_CONTEXT.get(setup_type, "EVM")

    # Enrich with entity context where relevant
    if setup_type in ("liquidity_shock", "exchange_drain"):
        ent_data = cm.get("entities", {})
        top_bullish = ent_data.get("top_bullish", [])
        if top_bullish:
            top_name = top_bullish[0].get("name", "")
            if top_name:
                return f"{base_label} · {top_name}"
        return f"{base_label} · {chain_tag}"

    if setup_type == "smart_money_accumulation":
        sm = cm.get("smart_money", {})
        clusters = sm.get("clusters", 0)
        net_fmt = sm.get("net_flow_fmt", "")
        if net_fmt:
            return f"{base_label} · {net_fmt}"
        return f"{base_label} · {clusters} clusters"

    if setup_type == "rotation":
        token = cm.get("token", {})
        cnt = token.get("token_count", 0)
        regime = token.get("regime", "")
        if cnt:
            return f"{base_label} · {cnt} tokens"
        return f"{base_label} · {chain_tag}"

    return f"{base_label} · {chain_tag}"


def _estimate_expected_move(setup_type: str, confidence: float) -> str:
    """Rule-based expected move estimation."""
    base_moves = {
        "liquidity_shock": (4, 8),
        "smart_money_accumulation": (3, 6),
        "distribution_risk": (3, 7),
        "exchange_drain": (2, 5),
        "rotation": (2, 4),
        "actor_conflict": (1, 3),
        "otc_transfer": (1, 3),
    }
    lo, hi = base_moves.get(setup_type, (1, 3))
    adj = confidence  # scale by confidence
    return f"{round(lo * adj, 1)}-{round(hi * adj, 1)}%"


def _estimate_timeframe(setup_type: str) -> str:
    """Rule-based timeframe estimation."""
    tf = {
        "liquidity_shock": "2-8h",
        "smart_money_accumulation": "12-48h",
        "distribution_risk": "6-24h",
        "exchange_drain": "4-12h",
        "rotation": "24-72h",
        "actor_conflict": "4-12h",
        "otc_transfer": "1-4h",
    }
    return tf.get(setup_type, "4-12h")


def _calc_liquidity_alignment(snap: dict, setup_type: str) -> float:
    """Calculate how aligned liquidity is with the setup direction."""
    liq = snap.get("liquidity_map", {})
    targets = liq.get("target_zones", [])
    if not targets:
        return 0.3
    primary_dir = liq.get("primary_direction", "neutral")
    bullish_setups = {"liquidity_shock", "smart_money_accumulation", "exchange_drain"}
    bearish_setups = {"distribution_risk"}
    if setup_type in bullish_setups and primary_dir == "above":
        return 0.8
    if setup_type in bearish_setups and primary_dir == "below":
        return 0.8
    if primary_dir == "both":
        return 0.5
    return 0.3


def get_os_opportunities() -> list:
    """Get ranked opportunities with enhanced scoring formula."""
    db = _get_db()
    snap = db["engine_context_snapshots"].find_one(
        {}, {"_id": 0}, sort=[("timestamp", DESCENDING)]
    )
    if not snap:
        return []

    risk = snap.get("risk_engine", {})
    risk_score = risk.get("risk_score", 50) / 100
    flow = snap.get("flow_engine", {})
    flow_strength = flow.get("strength", 0)
    cm = snap.get("context_matrix", {})
    chains = _get_opportunity_chains()

    opportunities = []

    # Primary setup
    primary = snap.get("setup_engine", {}).get("primary", {})
    prob = snap.get("probability_layer", {})
    if primary.get("type", "mixed") != "mixed":
        conf = primary.get("confidence", 0)
        p = prob.get("continuation", 0)
        status = primary.get("status", "weak")
        setup_type = primary.get("type")
        liq_align = _calc_liquidity_alignment(snap, setup_type)
        mult = STATUS_MULTIPLIER.get(status, 0.7)

        base = p * 0.35 + conf * 0.25 + flow_strength * 0.20 + liq_align * 0.10 + (1 - risk_score) * 0.10
        rank_score = base * mult

        opportunities.append({
            "asset": _derive_opp_asset(setup_type, cm, chains),
            "chains": chains,
            "setup": setup_type,
            "status": status,
            "confidence": round(conf, 3),
            "probability": round(p, 3),
            "risk_level": risk.get("risk_level", "MODERATE"),
            "rank_score": round(rank_score, 3),
            "expected_move": _estimate_expected_move(setup_type, conf),
            "move_confidence": round(min(conf * p, 1.0), 3),
            "liquidity_alignment": round(liq_align, 3),
            "timeframe": _estimate_timeframe(setup_type),
            "supports": primary.get("supports", [])[:3],
            "window": primary.get("window", ""),
        })

    # Secondary setups
    for sec in snap.get("setup_engine", {}).get("secondary", []):
        if sec.get("type", "mixed") != "mixed":
            sc = sec.get("confidence", 0)
            sp = sc * 0.6
            status = sec.get("status", "forming")
            setup_type = sec.get("type")
            liq_align = _calc_liquidity_alignment(snap, setup_type)
            mult = STATUS_MULTIPLIER.get(status, 0.7)

            base = sp * 0.35 + sc * 0.25 + flow_strength * 0.20 + liq_align * 0.10 + (1 - risk_score) * 0.10
            rank_score = base * mult

            opportunities.append({
                "asset": _derive_opp_asset(setup_type, cm, chains),
                "chains": chains,
                "setup": setup_type,
                "status": status,
                "confidence": round(sc, 3),
                "probability": round(sp, 3),
                "risk_level": risk.get("risk_level", "MODERATE"),
                "rank_score": round(rank_score, 3),
                "expected_move": _estimate_expected_move(setup_type, sc),
                "move_confidence": round(min(sc * sp, 1.0), 3),
                "liquidity_alignment": round(liq_align, 3),
                "timeframe": _estimate_timeframe(setup_type),
                "supports": [],
                "window": "",
            })

    opportunities.sort(key=lambda x: x["rank_score"], reverse=True)
    return opportunities


def get_market_pulse() -> dict:
    """Calculate Market Pulse — how active the market is right now."""
    db = _get_db()
    snap = db["engine_context_snapshots"].find_one(
        {}, {"_id": 0}, sort=[("timestamp", DESCENDING)]
    )
    if not snap:
        return {"pulse": "LOW", "score": 0, "drivers": []}

    # Components
    flow = snap.get("flow_engine", {})
    flow_velocity_raw = flow.get("strength", 0)
    flow_state = flow.get("state", "neutral")

    # Alert frequency (last hour)
    one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    alert_count = db["engine_alerts"].count_documents(
        {"timestamp": {"$gte": one_hour_ago}}
    )
    alert_rate = min(alert_count / 10, 1.0)  # normalize: 10 alerts/h = 1.0

    # Setup activity
    setup = snap.get("setup_engine", {}).get("primary", {})
    setup_status = setup.get("status", "weak")
    setup_conf = setup.get("confidence", 0)
    setup_activity = 0.8 if setup_status in ("confirmed", "active") else 0.4 if setup_status == "forming" else 0.1

    # Liquidity events
    liq = snap.get("liquidity_map", {})
    targets = len(liq.get("target_zones", []))
    magnets = len(liq.get("magnet_zones", []))
    liq_events = min((targets + magnets) / 5, 1.0)

    # Pulse formula
    pulse_score = round(
        flow_velocity_raw * 0.35
        + alert_rate * 0.25
        + setup_activity * 0.20
        + liq_events * 0.20,
        3
    )
    pulse_int = round(pulse_score * 100)

    # Level
    if pulse_int >= 75:
        level = "EXTREME"
    elif pulse_int >= 50:
        level = "HIGH"
    elif pulse_int >= 25:
        level = "NORMAL"
    else:
        level = "LOW"

    # Drivers
    drivers = []
    if flow_state != "neutral":
        drivers.append(flow_state.replace("_", " ").title())
    if setup_status in ("confirmed", "active"):
        drivers.append(f"{setup.get('type', 'setup').replace('_', ' ').title()}")
    if alert_count >= 5:
        drivers.append("High alert frequency")
    if targets >= 2:
        drivers.append("Multiple liquidity targets")

    return {
        "pulse": level,
        "score": pulse_int,
        "drivers": drivers[:3],
    }
