"""
Prediction On-chain Market Service
====================================
Aggregates on-chain data for market prediction page.
Reads from: engine_context_snapshots, onchain_v2_altflow_points,
entity_activity, entity_behaviour_v2, discovery_signals, graph_alpha_signals,
token_flow_buckets, engine_alerts.
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
        _db = _client["intelligence_engine"]
    return _db


# ── Regime → market state mapping ──
REGIME_STATE = {
    "bull_trend": "BULLISH",
    "bear_trend": "BEARISH",
    "accumulation": "BULLISH",
    "distribution": "BEARISH",
    "neutral_chop": "NEUTRAL",
    "breakout": "BULLISH",
    "range": "NEUTRAL",
}

SETUP_BIAS = {
    "liquidity_shock": "BUY",
    "smart_money_accumulation": "BUY",
    "exchange_drain": "BUY",
    "distribution_risk": "SELL",
    "rotation": "RANGE",
    "actor_conflict": "RANGE",
    "mixed": "RANGE",
}

FLOW_TO_ALT = {
    "bullish_acceleration": "STRONG",
    "liquidity_expansion": "STRONG",
    "bearish_acceleration": "WEAK",
    "flow_exhaustion": "ROTATION",
    "neutral": "NEUTRAL",
}


def _build_header(snap: dict) -> dict:
    """Block 1: Market Prediction Header."""
    regime = snap.get("regime_engine", {}).get("primary", {})
    setup = snap.get("setup_engine", {}).get("primary", {})
    flow = snap.get("flow_engine", {})
    prob = snap.get("probability_layer", {})
    risk = snap.get("risk_engine", {})
    conf = snap.get("confidence", {})

    regime_type = regime.get("type", "neutral_chop")
    market_state = REGIME_STATE.get(regime_type, "NEUTRAL")
    flow_state = flow.get("state", "neutral")
    alts_state = FLOW_TO_ALT.get(flow_state, "NEUTRAL")
    setup_type = setup.get("type", "mixed")
    bias = SETUP_BIAS.get(setup_type, "RANGE")
    confidence = conf.get("score", 0)
    flow_strength = flow.get("strength", 0)

    # Determine horizon from setup window
    window = setup.get("window", "")
    if "1" in window or "short" in window.lower():
        horizon = "SHORT"
    elif "30" in window or "long" in window.lower() or "swing" in window.lower():
        horizon = "SWING"
    else:
        horizon = "MID"

    # Expected moves based on regime + flow
    base_mult = 1.0 if market_state == "BULLISH" else (-1.0 if market_state == "BEARISH" else 0.3)
    strength_mult = max(flow_strength, 0.3)
    eth_lo = round(abs(base_mult * strength_mult * 4), 1)
    eth_hi = round(abs(base_mult * strength_mult * 9), 1)
    alt_lo = round(abs(base_mult * strength_mult * 8), 1)
    alt_hi = round(abs(base_mult * strength_mult * 25), 1)
    sign = "+" if base_mult >= 0 else "-"

    return {
        "market_state": market_state,
        "altcoins_state": alts_state,
        "bias": bias,
        "confidence": confidence,
        "horizon": horizon,
        "regime_type": regime_type.replace("_", " ").title(),
        "regime_confidence": round((regime.get("confidence", 0)) * 100),
        "flow_state": flow_state.replace("_", " ").title(),
        "probability_continuation": round((prob.get("continuation", 0)) * 100),
        "risk_level": risk.get("risk_level", "MODERATE"),
        "risk_score": risk.get("risk_score", 50),
        "expected_moves": {
            "ETH": f"{sign}{eth_lo}-{eth_hi}%",
            "ALTS": f"{sign}{alt_lo}-{alt_hi}%",
        },
    }


def _build_alt_predictions(db) -> dict:
    """Block 2: Altcoins Direction — TOP 10 UP / DOWN from real flow data."""
    # Get latest altflow points for each symbol
    pipeline = [
        {"$sort": {"t": -1}},
        {"$group": {
            "_id": {"symbol": "$symbol", "window": "$window"},
            "score": {"$first": "$score"},
            "confidence": {"$first": "$confidence"},
            "dexNetUsd": {"$first": "$dexNetUsd"},
            "drivers": {"$first": "$drivers"},
            "t": {"$first": "$t"},
        }},
        {"$match": {"_id.window": "24h"}},
    ]
    points = list(db["onchain_v2_altflow_points"].aggregate(pipeline))

    # Also get token flow buckets for additional tokens
    recent_buckets = list(db["token_flow_buckets"].find(
        {}, {"_id": 0, "tokenSymbol": 1, "netUsd": 1, "transfers": 1, "uniqueWallets": 1}
    ).sort("bucketTs", DESCENDING).limit(50))

    # Aggregate bucket data by symbol
    bucket_scores = {}
    for b in recent_buckets:
        sym = b.get("tokenSymbol", "")
        if not sym:
            continue
        if sym not in bucket_scores:
            bucket_scores[sym] = {"net": 0, "transfers": 0, "wallets": 0, "count": 0}
        bucket_scores[sym]["net"] += b.get("netUsd", 0)
        bucket_scores[sym]["transfers"] += b.get("transfers", 0)
        bucket_scores[sym]["wallets"] += b.get("uniqueWallets", 0)
        bucket_scores[sym]["count"] += 1

    tokens = {}

    # From altflow points
    for p in points:
        sym = p["_id"]["symbol"]
        score = p.get("score", 0)
        conf = p.get("confidence", 0)
        net = p.get("dexNetUsd", 0)
        drivers = p.get("drivers", [])

        # Estimate expected % move from score + confidence
        move_pct = round(score * conf * 15, 1)  # rough estimate
        tokens[sym] = {
            "symbol": sym,
            "score": score,
            "confidence": round(conf * 100),
            "net_flow_usd": round(net),
            "expected_move": f"{'+' if move_pct >= 0 else ''}{move_pct}%",
            "move_pct": move_pct,
            "drivers": drivers[:2] if drivers else [],
        }

    # Enrich from bucket data
    for sym, bdata in bucket_scores.items():
        clean_sym = sym.replace("W", "") if sym.startswith("W") and len(sym) > 3 else sym
        if clean_sym not in tokens and sym not in tokens:
            avg_net = bdata["net"] / max(bdata["count"], 1)
            direction = 1 if avg_net > 0 else -1
            strength = min(abs(avg_net) / 100000, 1.0)  # normalize
            move_pct = round(direction * strength * 8, 1)
            tokens[sym] = {
                "symbol": sym,
                "score": round(direction * strength, 2),
                "confidence": round(min(bdata["wallets"] / max(bdata["count"], 1) * 5, 100)),
                "net_flow_usd": round(avg_net),
                "expected_move": f"{'+' if move_pct >= 0 else ''}{move_pct}%",
                "move_pct": move_pct,
                "drivers": [f"{bdata['transfers']} transfers", f"{bdata['wallets']} wallets"],
            }

    all_tokens = list(tokens.values())
    all_tokens.sort(key=lambda x: x["move_pct"], reverse=True)

    gainers = [t for t in all_tokens if t["move_pct"] > 0][:10]
    losers = [t for t in all_tokens if t["move_pct"] < 0][:10]
    losers.sort(key=lambda x: x["move_pct"])

    return {"gainers": gainers, "losers": losers, "total_tokens": len(all_tokens)}


def _build_regime(snap: dict) -> dict:
    """Block 3: Market Regime & Risk."""
    regime = snap.get("regime_engine", {}).get("primary", {})
    risk = snap.get("risk_engine", {})
    flow = snap.get("flow_engine", {})
    cm = snap.get("context_matrix", {})
    token = cm.get("token", {})

    regime_type = regime.get("type", "neutral_chop")
    risk_score = risk.get("risk_score", 50)

    # Volatility from risk components
    components = risk.get("components", {})
    flow_instability = components.get("flow_instability", 0)
    if flow_instability > 60:
        volatility = "High"
    elif flow_instability > 30:
        volatility = "Medium"
    else:
        volatility = "Low"

    # Liquidity state from flow engine
    flow_state = flow.get("state", "neutral")
    if "expansion" in flow_state or "bullish" in flow_state:
        liquidity_state = "Expanding"
    elif "exhaustion" in flow_state or "bearish" in flow_state:
        liquidity_state = "Contracting"
    else:
        liquidity_state = "Stable"

    # Risk mode
    risk_mode = "Risk ON" if risk_score < 50 else "Risk OFF"

    return {
        "regime": regime_type.replace("_", " ").title(),
        "regime_confidence": round((regime.get("confidence", 0)) * 100),
        "risk_mode": risk_mode,
        "risk_score": risk_score,
        "volatility": volatility,
        "liquidity_state": liquidity_state,
        "token_regime": token.get("regime", "neutral").title(),
        "token_pattern": token.get("pattern", "").replace("_", " ").title(),
    }


def _build_narrative(snap: dict) -> str:
    """Block 4: AI Market Narrative — 3-4 line summary."""
    cm = snap.get("context_matrix", {})
    sm = cm.get("smart_money", {})
    cex = cm.get("cex", {})
    ent = cm.get("entities", {})
    flow = snap.get("flow_engine", {})
    regime = snap.get("regime_engine", {}).get("primary", {}).get("type", "neutral")

    lines = []

    # Smart money line
    net_flow_fmt = sm.get("net_flow_fmt", "")
    conviction = sm.get("conviction", 50)
    if conviction >= 60:
        lines.append(f"Smart money accumulating with {net_flow_fmt} net flow, conviction {conviction}%.")
    elif conviction <= 40:
        lines.append(f"Smart money distributing, net flow {net_flow_fmt}.")
    else:
        lines.append(f"Smart money neutral. Net flow: {net_flow_fmt}.")

    # Exchange line
    cex_bias = cex.get("market_bias", "neutral")
    inv_state = cex.get("inventory_state", "stable")
    if cex_bias == "bullish" or inv_state == "shrinking":
        lines.append("Exchange outflows increasing — sell pressure decreasing.")
    elif cex_bias == "bearish":
        lines.append("Exchange inflows rising — potential sell pressure building.")
    else:
        lines.append(f"Exchange flows balanced. Inventory: {inv_state}.")

    # Alt/regime line
    pressure = ent.get("pressure_balance", "neutral")
    if "bull" in regime or "accumulation" in regime:
        lines.append("Market in accumulation phase — altcoins positioned for expansion.")
    elif "bear" in regime or "distribution" in regime:
        lines.append("Distribution phase — caution on altcoin exposure.")
    else:
        lines.append(f"Market in ranging phase. Entity pressure: {pressure}.")

    return " ".join(lines)


def _build_drivers(snap: dict) -> list:
    """Block 5: Prediction Drivers."""
    cm = snap.get("context_matrix", {})
    flow = snap.get("flow_engine", {})
    cex = cm.get("cex", {})
    sm = cm.get("smart_money", {})
    ent = cm.get("entities", {})
    token = cm.get("token", {})

    drivers = []

    # Exchange Flow driver
    cex_bias = cex.get("market_bias", "neutral")
    shock = cex.get("liquidity_shock", "")
    if "bullish" in shock:
        drivers.append({"name": "Exchange Flow", "signal": "SELL PRESSURE DOWN", "direction": "up", "strength": 80, "confidence": 85})
    elif cex_bias == "bearish":
        drivers.append({"name": "Exchange Flow", "signal": "SELL PRESSURE UP", "direction": "down", "strength": 65, "confidence": 70})
    else:
        drivers.append({"name": "Exchange Flow", "signal": "BALANCED", "direction": "neutral", "strength": 50, "confidence": 60})

    # Smart Money driver
    conviction = sm.get("conviction", 50)
    clusters = sm.get("clusters", 0)
    if conviction >= 60:
        drivers.append({"name": "Smart Money", "signal": "ACCUMULATION", "direction": "up", "strength": conviction, "confidence": min(conviction + 10, 100)})
    elif conviction <= 40:
        drivers.append({"name": "Smart Money", "signal": "DISTRIBUTION", "direction": "down", "strength": 100 - conviction, "confidence": min(100 - conviction + 10, 100)})
    else:
        drivers.append({"name": "Smart Money", "signal": "NEUTRAL", "direction": "neutral", "strength": 50, "confidence": 55})

    # Cluster Activity driver
    if clusters >= 5:
        drivers.append({"name": "Clusters", "signal": "HIGH ACTIVITY", "direction": "up", "strength": min(clusters * 12, 100), "confidence": 70})
    else:
        drivers.append({"name": "Clusters", "signal": "LOW ACTIVITY", "direction": "neutral", "strength": max(clusters * 15, 20), "confidence": 50})

    # Liquidity driver
    flow_strength = flow.get("strength", 0)
    flow_state = flow.get("state", "neutral")
    if "expansion" in flow_state or "bullish" in flow_state:
        drivers.append({"name": "Liquidity", "signal": "EXPANDING", "direction": "up", "strength": round(flow_strength * 100), "confidence": 75})
    elif "exhaustion" in flow_state or "bearish" in flow_state:
        drivers.append({"name": "Liquidity", "signal": "CONTRACTING", "direction": "down", "strength": round(flow_strength * 100), "confidence": 70})
    else:
        drivers.append({"name": "Liquidity", "signal": "STABLE", "direction": "neutral", "strength": 45, "confidence": 55})

    # Stablecoin driver
    stable_bias = cex.get("stablecoin_bias", "neutral")
    stable_net = cex.get("stablecoin_net", 0)
    if stable_bias == "buying_power" and stable_net > 0:
        drivers.append({"name": "Stablecoins", "signal": "INFLOW", "direction": "up", "strength": 70, "confidence": 75})
    elif stable_net < -10000:
        drivers.append({"name": "Stablecoins", "signal": "OUTFLOW", "direction": "down", "strength": 60, "confidence": 65})
    else:
        drivers.append({"name": "Stablecoins", "signal": "NEUTRAL", "direction": "neutral", "strength": 45, "confidence": 50})

    return drivers


def _build_smart_money(snap: dict) -> dict:
    """Block 6: Smart Money Positioning."""
    cm = snap.get("context_matrix", {})
    sm = cm.get("smart_money", {})
    ent = cm.get("entities", {})

    net_flow = sm.get("net_flow", 0)
    net_flow_fmt = sm.get("net_flow_fmt", "$0")
    conviction = sm.get("conviction", 50)
    clusters = sm.get("clusters", 0)
    signals = sm.get("signal_count", 0)

    if conviction >= 65:
        accumulation = "HIGH"
        distribution = "LOW"
    elif conviction <= 35:
        accumulation = "LOW"
        distribution = "HIGH"
    else:
        accumulation = "MODERATE"
        distribution = "MODERATE"

    # Rotation signal from entities
    top_bullish = ent.get("top_bullish", [])
    rotation = ""
    if top_bullish:
        rotation = " → ".join([e.get("name", "") for e in top_bullish[:3]])

    return {
        "net_flow": net_flow_fmt,
        "net_flow_raw": net_flow,
        "active_clusters": clusters,
        "signal_count": signals,
        "conviction": conviction,
        "accumulation": accumulation,
        "distribution": distribution,
        "rotation": rotation,
    }


def _build_liquidity(snap: dict, db) -> dict:
    """Block 7: Liquidity & Exchange Flows."""
    cm = snap.get("context_matrix", {})
    cex = cm.get("cex", {})
    liq = snap.get("liquidity_map", {})

    net_liq = cex.get("net_liquidity", 0)
    stable_net = cex.get("stablecoin_net", 0)
    inv_state = cex.get("inventory_state", "stable")
    shock = cex.get("liquidity_shock", "none")

    # Get largest recent entity transfer
    latest_transfer = db["entity_activity"].find_one(
        {}, {"_id": 0, "entity": 1, "chain": 1, "tx_type": 1, "value_eth": 1},
        sort=[("timestamp", DESCENDING)]
    )
    largest_transfer = ""
    if latest_transfer:
        entity = latest_transfer.get("entity", "Unknown")
        tx_type = latest_transfer.get("tx_type", "transfer").replace("_", " ")
        largest_transfer = f"{entity} — {tx_type}"

    # Liquidity targets
    targets = liq.get("target_zones", [])
    primary_target = targets[0].get("reason", "") if targets else ""

    flow_type = "outflow" if net_liq < 0 else "inflow" if net_liq > 0 else "neutral"

    return {
        "exchange_net_flow": round(net_liq),
        "exchange_net_flow_fmt": f"{'−' if net_liq < 0 else '+'}{abs(round(net_liq)):,}",
        "flow_type": flow_type,
        "stablecoin_net": round(stable_net),
        "stablecoin_net_fmt": f"{'−' if stable_net < 0 else '+'}{abs(round(stable_net)):,}",
        "inventory_state": inv_state.replace("_", " ").title(),
        "liquidity_shock": shock.replace("_", " ").title(),
        "largest_transfer": largest_transfer,
        "primary_target": primary_target,
    }


def _build_model_state(snap: dict, db) -> dict:
    """Block 8: Confidence + Model State."""
    conf = snap.get("confidence", {})
    meta = snap.get("snapshot_meta", {}) or snap.get("meta", {})
    risk = snap.get("risk_engine", {})

    confidence = conf.get("score", 0)
    level = conf.get("level", "LOW")

    # Data quality from entity coverage
    cm = snap.get("context_matrix", {})
    ent = cm.get("entities", {})
    entity_count = ent.get("entity_count", 0)
    clusters = cm.get("smart_money", {}).get("clusters", 0)

    if entity_count >= 10 and clusters >= 5:
        data_quality = "GOOD"
    elif entity_count >= 5:
        data_quality = "MODERATE"
    else:
        data_quality = "LIMITED"

    # Coverage
    coverage_wallets = ent.get("cluster_wallets", 0)
    coverage_entities = entity_count

    # Signal strength
    signals = cm.get("smart_money", {}).get("signal_count", 0)
    if signals >= 5:
        signal_strength = "HIGH"
    elif signals >= 2:
        signal_strength = "MEDIUM"
    else:
        signal_strength = "LOW"

    # Warning
    warning = ""
    if data_quality == "LIMITED":
        warning = "LOW DATA — reduce confidence"
    elif risk.get("risk_score", 0) >= 70:
        warning = "HIGH RISK — exercise caution"

    return {
        "confidence": confidence,
        "confidence_level": level,
        "data_quality": data_quality,
        "coverage_entities": coverage_entities,
        "coverage_wallets": coverage_wallets,
        "coverage_clusters": clusters,
        "signal_strength": signal_strength,
        "engine_version": meta.get("version", meta.get("engine_version", "—")),
        "warning": warning,
    }


def _build_signals(db) -> list:
    """Block 9: Signals Feed (lite) — top recent signals."""
    signals = []

    # From graph_alpha_signals
    for doc in db["graph_alpha_signals"].find({}, {"_id": 0}).sort("generated_at", DESCENDING).limit(5):
        signals.append({
            "type": doc.get("signal_type", "unknown").upper().replace("_", " "),
            "description": doc.get("description", ""),
            "direction": doc.get("direction", "neutral"),
            "confidence": round(doc.get("confidence", 0) * 100),
            "source": "graph",
        })

    # From discovery_signals
    for doc in db["discovery_signals"].find({}, {"_id": 0}).sort("timestamp", DESCENDING).limit(5):
        signals.append({
            "type": doc.get("signal_type", "unknown").upper().replace("_", " "),
            "description": doc.get("detail", ""),
            "direction": doc.get("direction", "NEUTRAL").lower(),
            "confidence": doc.get("score", 0),
            "source": "discovery",
            "entity": doc.get("entity", ""),
            "chain": doc.get("chain", ""),
        })

    # From engine_alerts (recent)
    one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()
    for doc in db["engine_alerts"].find(
        {"timestamp": {"$gte": one_hour_ago}}, {"_id": 0}
    ).sort("timestamp", DESCENDING).limit(5):
        signals.append({
            "type": doc.get("type", "alert").upper().replace("_", " "),
            "description": doc.get("message", ""),
            "direction": "neutral",
            "confidence": 0,
            "source": "engine",
            "severity": doc.get("severity", "INFO"),
        })

    return signals[:10]


def get_onchain_market_prediction() -> dict:
    """Main aggregator — builds all blocks from snapshot data."""
    db = _get_db()
    snap = db["engine_context_snapshots"].find_one(
        {}, {"_id": 0, "created_at": 0}, sort=[("timestamp", DESCENDING)]
    )
    if not snap:
        return {"empty": True}

    return {
        "header": _build_header(snap),
        "alt_predictions": _build_alt_predictions(db),
        "regime": _build_regime(snap),
        "narrative": _build_narrative(snap),
        "drivers": _build_drivers(snap),
        "smart_money": _build_smart_money(snap),
        "liquidity": _build_liquidity(snap, db),
        "model_state": _build_model_state(snap, db),
        "signals": _build_signals(db),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
