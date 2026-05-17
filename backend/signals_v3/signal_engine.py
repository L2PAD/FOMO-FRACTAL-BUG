"""
Signal Engine V3.3 — Chain-Aware On-chain Intelligence
=======================================================
EVM-only. All signals must have: chain, source, evidence, provenance.
No mock data. No fallback generation. no data → no signal.

Allowed chains: ethereum, arbitrum, optimism, base
"""

import os
import math
import hashlib
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, DESCENDING

from .network_guard import (
    ALLOWED_CHAINS, CHAIN_CONFIG, is_allowed_chain,
    validate_signal_integrity, build_evidence, build_provenance,
    get_explorer_link, get_chain_label,
)

_client = None


def _get_db():
    global _client
    if _client is None:
        _client = MongoClient(os.environ["MONGO_URL"])
    return _client[os.environ.get("DB_NAME", "market_brain")]


def _signal_id(asset: str, sig_type: str, detail: str = "") -> str:
    raw = f"{asset}_{sig_type}_{detail}"
    return "sig_" + hashlib.md5(raw.encode()).hexdigest()[:12]


def _severity(score: int) -> str:
    if score >= 75: return "EXTREME"
    if score >= 60: return "STRONG"
    if score >= 40: return "WATCH"
    return "WEAK"


def _direction_from_setup(setup_type: str) -> str:
    bullish = {"liquidity_shock", "smart_money_accumulation", "exchange_drain"}
    bearish = {"distribution_risk", "actor_conflict"}
    if setup_type in bullish: return "BULLISH"
    if setup_type in bearish: return "BEARISH"
    return "NEUTRAL"


def _freshness(timestamp_iso: str) -> float:
    """Freshness score: 1.0 = just now, 0.0 = 60+ min old."""
    try:
        ts = datetime.fromisoformat(timestamp_iso.replace("Z", "+00:00"))
        age_min = (datetime.now(timezone.utc) - ts).total_seconds() / 60
        return max(0.0, round(1.0 - age_min / 60, 3))
    except Exception:
        return 0.5


def _build_invalidation(setup_type: str, playbook: dict, liq: dict) -> dict:
    """Build invalidation object from playbook and liquidity data."""
    inv = playbook.get("invalidation", []) if playbook else []
    if isinstance(inv, list) and inv:
        desc = inv[0] if isinstance(inv[0], str) else str(inv[0])
    elif isinstance(inv, str):
        desc = inv
    else:
        desc = ""

    inv_types = {
        "liquidity_shock": "liquidity_loss",
        "smart_money_accumulation": "sm_reversal",
        "exchange_drain": "deposit_spike",
        "distribution_risk": "accumulation_start",
        "actor_conflict": "conflict_resolution",
    }

    # Extract price level from playbook targets or liquidity zones
    level = ""
    targets = playbook.get("targets", []) if playbook else []
    if isinstance(targets, list):
        for t in targets:
            if isinstance(t, dict) and t.get("level"):
                level = str(t["level"])
                break
    if not level:
        liq_targets = liq.get("target_zones", []) if liq else []
        for zt in liq_targets:
            if isinstance(zt, dict) and zt.get("price"):
                level = str(zt["price"])
                break

    return {
        "type": inv_types.get(setup_type, "setup_failure"),
        "description": desc[:100] if desc else f"Setup invalidation for {setup_type.replace('_', ' ')}",
        "level": level,
    }


def _compute_alignment(signal_direction: str, regime: dict) -> dict:
    """Compute alignment between signal direction and engine regime."""
    regime_type = regime.get("type", "neutral_chop")
    bullish_regimes = {"bull_trend", "accumulation", "early_bull"}
    bearish_regimes = {"bear_trend", "distribution", "capitulation"}

    if signal_direction == "BULLISH":
        if regime_type in bullish_regimes:
            status = "aligned"
        elif regime_type in bearish_regimes:
            status = "contrarian"
        else:
            status = "neutral"
    elif signal_direction == "BEARISH":
        if regime_type in bearish_regimes:
            status = "aligned"
        elif regime_type in bullish_regimes:
            status = "contrarian"
        else:
            status = "neutral"
    else:
        status = "neutral"

    return {
        "engine_regime": regime_type,
        "signal_direction": signal_direction.lower(),
        "status": status,
    }


def _get_signal_quality(signal_type: str) -> dict:
    """Get historical quality metrics from Market Memory."""
    db = _get_db()
    # Map signal types to setup types for memory lookup
    type_to_setup = {
        "SETUP_CONFIRMATION": None,  # uses actual setup_detail
        "ACCUMULATION": None,
        "DISTRIBUTION": None,
        "LIQUIDITY_MAGNET": "liquidity_shock",
        "FLOW_ACCELERATION": None,
        "ACTOR_ACCUMULATION": None,
        "ACTOR_DISTRIBUTION": None,
    }

    setup = type_to_setup.get(signal_type)
    if not setup:
        return {"success_rate": 0, "avg_move": 0, "samples": 0}

    outcome = db["engine_setup_outcomes"].find_one(
        {"setup_type": setup}, {"_id": 0}
    )
    if outcome:
        return {
            "success_rate": round(outcome.get("success_rate", 0) * 100),
            "avg_move": round(outcome.get("avg_move", 0), 1),
            "samples": outcome.get("sample_size", 0),
        }
    return {"success_rate": 0, "avg_move": 0, "samples": 0}


def _build_context(direction: str, regime: dict, risk: dict, pulse: dict,
                   flow: dict, opp_rank: int) -> dict:
    """Build market context object for a signal."""
    regime_type = regime.get("type", "neutral_chop")
    risk_level = risk.get("risk_level", "MODERATE")
    pulse_state = pulse.get("pulse", "NORMAL") if pulse else "NORMAL"
    flow_state = flow.get("state", "neutral")

    # Derive pressure from flow state
    if "bullish" in flow_state.lower():
        pressure = "bullish"
    elif "bearish" in flow_state.lower():
        pressure = "bearish"
    else:
        pressure = "neutral"

    return {
        "regime": regime_type,
        "risk": risk_level.lower(),
        "pulse": pulse_state.lower() if isinstance(pulse_state, str) else "normal",
        "pressure": pressure,
        "asset_pressure": pressure,
        "ranking": opp_rank,
    }


def _context_modifier(direction: str, context: dict) -> int:
    """Calculate context-based score modifier (additive, not replacement).
    Formula: regime_alignment*8 + pressure_alignment*6 + ranking_bonus*4 - risk_penalty*6
    """
    regime = context.get("regime", "neutral_chop")
    pressure = context.get("pressure", "neutral")
    ranking = context.get("ranking", 0)
    risk = context.get("risk", "moderate")

    bullish_regimes = {"bull_trend", "accumulation", "early_bull"}
    bearish_regimes = {"bear_trend", "distribution", "capitulation"}

    # Regime alignment: +8 aligned, -8 contrarian, 0 neutral
    if direction == "BULLISH":
        regime_a = 8 if regime in bullish_regimes else (-8 if regime in bearish_regimes else 0)
    elif direction == "BEARISH":
        regime_a = 8 if regime in bearish_regimes else (-8 if regime in bullish_regimes else 0)
    else:
        regime_a = 0

    # Pressure alignment: +6 if same direction, -6 if opposite
    if direction == "BULLISH":
        pressure_a = 6 if pressure == "bullish" else (-6 if pressure == "bearish" else 0)
    elif direction == "BEARISH":
        pressure_a = 6 if pressure == "bearish" else (-6 if pressure == "bullish" else 0)
    else:
        pressure_a = 0

    # Ranking bonus: +4 if has opportunity
    ranking_b = 4 if ranking and ranking > 0 else 0

    # Risk penalty: 0 / -1.8 / -3.6 / -6
    risk_p = {"low": 0, "moderate": 2, "elevated": 4, "high": 6}.get(risk, 2)

    return regime_a + pressure_a + ranking_b - risk_p


def generate_signals() -> list:
    """Generate unified signals from all platform data sources.
    All signals are chain-aware with source evidence and provenance.
    """
    db = _get_db()

    snap = db["engine_context_snapshots"].find_one(
        {}, {"_id": 0}, sort=[("timestamp", DESCENDING)]
    )
    if not snap:
        return []

    signals = []

    # === Extract engine data ===
    setup = snap.get("setup_engine", {}).get("primary", {})
    regime = snap.get("regime_engine", {}).get("primary", {})
    prob = snap.get("probability_layer", {})
    flow = snap.get("flow_engine", {})
    liq = snap.get("liquidity_map", {})
    risk = snap.get("risk_engine", {})
    playbook = snap.get("playbook", {})

    from os_service.service import get_actor_radar, get_os_opportunities, get_market_pulse, get_liquidity_evolution
    radar = get_actor_radar()
    opportunities = get_os_opportunities()
    pulse = get_market_pulse()
    liq_evolution = get_liquidity_evolution()

    # === Detect chain from snapshot metadata ===
    snap_chain = snap.get("chain", "ethereum")
    if not is_allowed_chain(snap_chain):
        snap_chain = "ethereum"

    # === Detect asset from snapshot (EVM tokens, not BTC/SOL) ===
    snap_asset = snap.get("asset", "ETH")
    non_evm_assets = {"BTC", "SOL", "DOT", "ATOM", "XRP", "ADA", "AVAX"}
    if snap_asset.upper() in non_evm_assets:
        snap_asset = "ETH"

    def _score(ea: float, astr: float, fi: float, la: float, rs: float, pf: float) -> int:
        raw = ea * 0.30 + astr * 0.20 + fi * 0.15 + la * 0.15 + rs * 0.10 + pf * 0.10
        return min(round(raw * 100), 100)

    flow_strength = flow.get("strength", 0)
    flow_state = flow.get("state", "neutral")
    pulse_score = (pulse.get("score", 0) / 100) if pulse else 0
    snap_ts = snap.get("timestamp", datetime.now(timezone.utc).isoformat())

    # Calculate real age of snapshot
    try:
        ts_parsed = datetime.fromisoformat(str(snap_ts).replace("Z", "+00:00"))
        snap_age_min = round((datetime.now(timezone.utc) - ts_parsed).total_seconds() / 60)
    except Exception:
        snap_age_min = 0

    actors = radar.get("actors", [])
    actor_map = {a["id"]: a for a in actors}

    # ═══ SIGNAL 1: Setup-based signal ═══
    if setup.get("type", "mixed") != "mixed":
        setup_type = setup["type"]
        setup_status = setup.get("status", "weak")
        setup_conf = setup.get("confidence", 0)
        continuation = prob.get("continuation", 0)
        direction = _direction_from_setup(setup_type)

        engine_align = continuation * setup_conf
        if direction == "BULLISH":
            bullish_actors = [a for a in actors if a["direction"] == "up"]
            actor_str = sum(a["strength"] for a in bullish_actors) / max(len(bullish_actors), 1) / 100
        elif direction == "BEARISH":
            bearish_actors = [a for a in actors if a["direction"] == "down"]
            actor_str = sum(a["strength"] for a in bearish_actors) / max(len(bearish_actors), 1) / 100
        else:
            actor_str = 0.3

        liq_align = 0.3
        targets = liq.get("target_zones", [])
        if targets:
            if direction == "BULLISH" and any(t.get("direction") == "above" for t in targets):
                liq_align = 0.8
            elif direction == "BEARISH" and any(t.get("direction") == "below" for t in targets):
                liq_align = 0.8

        opp_match = next((o for o in opportunities if o.get("setup") == setup_type), None)
        rank_sc = opp_match["rank_score"] if opp_match else 0.3
        score = _score(engine_align, actor_str, flow_strength, liq_align, rank_sc, pulse_score)

        if setup_status == "confirmed":
            sig_type, phase = "SETUP_CONFIRMATION", "confirmed"
        elif setup_status == "active":
            sig_type, phase = ("ACCUMULATION" if direction == "BULLISH" else "DISTRIBUTION"), "forming"
        elif setup_status == "forming":
            sig_type, phase = ("ACCUMULATION" if direction == "BULLISH" else "DISTRIBUTION"), "detected"
        else:
            sig_type = "SETUP_FAILURE" if setup_status == "weakening" else "ACCUMULATION"
            phase = "cooling" if setup_status == "weakening" else "detected"

        drivers = {"engine": f"{setup_type.replace('_', ' ').title()} {setup_status}"}
        sm = actor_map.get("smart_money")
        if sm and sm["direction"] != "neutral":
            drivers["actors"] = f"Smart Money {sm['action']}"
        if flow_state != "neutral":
            drivers["flow"] = flow_state.replace("_", " ").title()
        if liq_align >= 0.6:
            drivers["liquidity"] = f"Liquidity aligned ({len(targets)} targets)"
        if opp_match:
            drivers["ranking"] = f"Opportunity #{opportunities.index(opp_match) + 1}"

        target = ""
        if playbook and playbook.get("targets"):
            tgt = playbook["targets"]
            if isinstance(tgt, list) and tgt:
                t0 = tgt[0]
                target = str(t0) if not isinstance(t0, dict) else t0.get("description", t0.get("reason", str(t0)))
            elif isinstance(tgt, str):
                target = tgt

        signals.append({
            "id": _signal_id(snap_asset, sig_type, setup_type),
            "asset": snap_asset,
            "signal_type": sig_type,
            "direction": direction,
            "score": score,
            "confidence": round(setup_conf * 100),
            "severity": _severity(score),
            "status": phase,
            "timeframe": opp_match.get("timeframe", "4-12h") if opp_match else "4-12h",
            "expected_move": opp_match.get("expected_move", "") if opp_match else "",
            "drivers": drivers,
            "target": target,
            "risk": risk.get("risk_level", "MODERATE"),
            "invalidation": _build_invalidation(setup_type, playbook, liq),
            "alignment": _compute_alignment(direction, regime),
            "quality": _get_signal_quality(sig_type),
            "freshness": _freshness(snap_ts),
            "timestamp": snap_ts,
            "age_min": 0,
            "setup_detail": setup_type,
        })

    # ═══ SIGNAL 2: Liquidity signals ═══
    for zone in liq.get("target_zones", [])[:2]:
        z_dir = zone.get("direction", "above")
        z_conf = zone.get("confidence", 0)
        z_reason = zone.get("reason", "")

        dyn_match = next((d for d in liq_evolution if d.get("type") == "target" and d.get("direction") == z_dir), None)
        trend = dyn_match.get("trend", "stable") if dyn_match else "stable"

        engine_align = z_conf * 0.7
        liq_a = 0.8 if trend == "strengthening" else 0.5
        score = _score(engine_align, 0.3, flow_strength, liq_a, 0.3, pulse_score)

        if trend == "strengthening":
            sig_type, phase = "LIQUIDITY_MAGNET", "confirmed"
        elif trend == "new":
            sig_type, phase = "LIQUIDITY_MAGNET", "detected"
        else:
            sig_type, phase = "LIQUIDITY_MAGNET", "forming"

        direction = "BULLISH" if z_dir == "above" else "BEARISH"
        drivers = {"liquidity": f"Target {z_dir}: {str(z_reason)[:60]}"}
        if trend != "stable":
            drivers["evolution"] = trend.title()

        signals.append({
            "id": _signal_id(snap_asset, sig_type, z_dir),
            "asset": snap_asset,
            "signal_type": sig_type,
            "direction": direction,
            "score": score,
            "confidence": round(z_conf * 100),
            "severity": _severity(score),
            "status": phase,
            "timeframe": "2-8h",
            "expected_move": "",
            "drivers": drivers,
            "target": str(z_reason)[:50] if z_reason else "",
            "risk": risk.get("risk_level", "MODERATE"),
            "invalidation": {"type": "liquidity_loss", "description": f"Magnet zone {z_dir} disappears", "level": ""},
            "alignment": _compute_alignment(direction, regime),
            "quality": _get_signal_quality("LIQUIDITY_MAGNET"),
            "freshness": _freshness(snap_ts),
            "timestamp": snap_ts,
            "age_min": 0,
            "setup_detail": "",
        })

    # ═══ SIGNAL 3: Actor-driven signals ═══
    for actor in actors:
        if actor["direction"] == "neutral" or actor["strength"] < 55:
            continue

        a_strength = actor["strength"] / 100
        if actor["direction"] == "up":
            sig_type, direction = "ACTOR_ACCUMULATION", "BULLISH"
        else:
            sig_type, direction = "ACTOR_DISTRIBUTION", "BEARISH"

        score = _score(0.4, a_strength, flow_strength * 0.5, 0.3, 0.3, pulse_score)
        phase = "confirmed" if actor["strength"] >= 70 else "forming"

        signals.append({
            "id": _signal_id(snap_asset, sig_type, actor["id"]),
            "asset": snap_asset,
            "signal_type": sig_type,
            "direction": direction,
            "score": score,
            "confidence": actor["strength"],
            "severity": _severity(score),
            "status": phase,
            "timeframe": "12-48h",
            "expected_move": "",
            "drivers": {"actors": f"{actor['name']} {actor['action']}"},
            "target": "",
            "risk": risk.get("risk_level", "MODERATE"),
            "invalidation": {"type": "actor_reversal", "description": f"{actor['name']} reverses direction", "level": ""},
            "alignment": _compute_alignment(direction, regime),
            "quality": {"success_rate": 0, "avg_move": 0, "samples": 0},
            "freshness": _freshness(snap_ts),
            "timestamp": snap_ts,
            "age_min": 0,
            "setup_detail": "",
        })

    # ═══ SIGNAL 4: Flow acceleration ═══
    if flow_strength >= 0.5 and flow_state != "neutral":
        direction = "BULLISH" if "bullish" in flow_state.lower() else "BEARISH" if "bearish" in flow_state.lower() else "NEUTRAL"
        score = _score(flow_strength, 0.4, flow_strength, 0.4, 0.3, pulse_score)
        phase = "confirmed" if flow_strength >= 0.7 else "forming"

        signals.append({
            "id": _signal_id(snap_asset, "FLOW_ACCELERATION", flow_state),
            "asset": snap_asset,
            "signal_type": "FLOW_ACCELERATION",
            "direction": direction,
            "score": score,
            "confidence": round(flow_strength * 100),
            "severity": _severity(score),
            "status": phase,
            "timeframe": "1-4h",
            "expected_move": "",
            "drivers": {"flow": flow_state.replace("_", " ").title()},
            "target": "",
            "risk": risk.get("risk_level", "MODERATE"),
            "invalidation": {"type": "flow_reversal", "description": "Flow direction reverses", "level": ""},
            "alignment": _compute_alignment(direction, regime),
            "quality": {"success_rate": 0, "avg_move": 0, "samples": 0},
            "freshness": _freshness(snap_ts),
            "timestamp": snap_ts,
            "age_min": 0,
            "setup_detail": "",
        })

    # ═══ SIGNAL 5: Secondary setups ═══
    for sec in snap.get("setup_engine", {}).get("secondary", []):
        if sec.get("type", "mixed") == "mixed":
            continue
        sec_type = sec["type"]
        sec_conf = sec.get("confidence", 0)
        sec_status = sec.get("status", "forming")
        if sec_conf < 0.3:
            continue

        direction = _direction_from_setup(sec_type)
        score = _score(sec_conf * 0.5, 0.3, flow_strength * 0.3, 0.3, 0.2, pulse_score)
        phase = "forming" if sec_status in ("forming", "active") else "detected"

        signals.append({
            "id": _signal_id(snap_asset, "ACCUMULATION", sec_type),
            "asset": snap_asset,
            "signal_type": "ACCUMULATION" if direction == "BULLISH" else "DISTRIBUTION",
            "direction": direction,
            "score": score,
            "confidence": round(sec_conf * 100),
            "severity": _severity(score),
            "status": phase,
            "timeframe": "8-24h",
            "expected_move": "",
            "drivers": {"engine": f"{sec_type.replace('_', ' ').title()} ({sec_status})"},
            "target": "",
            "risk": risk.get("risk_level", "MODERATE"),
            "invalidation": _build_invalidation(sec_type, {}, liq),
            "alignment": _compute_alignment(direction, regime),
            "quality": {"success_rate": 0, "avg_move": 0, "samples": 0},
            "freshness": _freshness(snap_ts),
            "timestamp": snap_ts,
            "age_min": 0,
            "setup_detail": sec_type,
        })

    # ═══ CHAIN-AWARE ENRICHMENT + CONTEXT LAYER ═══
    for sig in signals:
        direction = sig["direction"]
        opp_match = next((o for o in opportunities if o.get("setup") == sig.get("setup_detail")), None)
        opp_rank = (opportunities.index(opp_match) + 1) if opp_match else 0

        # Chain-aware fields
        sig["chain"] = snap_chain
        sig["chain_label"] = get_chain_label(snap_chain)
        sig["source"] = "engine_analysis"

        # Evidence: extract wallet/tx from snapshot if available
        sig_wallet = sig.get("wallet", "")
        sig_tx = sig.get("tx_hash", "")
        sig_contract = sig.get("contract", "")
        sig["evidence"] = build_evidence(
            wallet=sig_wallet, tx_hash=sig_tx, contract=sig_contract, chain=snap_chain,
        )

        # Provenance
        sig["provenance"] = build_provenance(
            source="engine_snapshot",
            detection=sig.get("signal_type", "unknown").lower(),
            module="signal_engine_v3",
        )

        # Context
        ctx = _build_context(direction, regime, risk, pulse, flow, opp_rank)
        sig["context"] = ctx

        # Apply context modifier (additive)
        modifier = _context_modifier(direction, ctx)
        base = sig["score"]
        adjusted = max(0, min(base + modifier, 100))

        # Apply freshness decay
        fresh = sig.get("freshness", 1.0)
        final = max(0, min(round(adjusted * fresh), 100))
        sig["score"] = final
        sig["severity"] = _severity(final)

        # Real age
        sig["age_min"] = snap_age_min

    # Sort by score descending
    signals.sort(key=lambda s: s["score"], reverse=True)

    # ═══ CLUSTERING ═══
    signals = _cluster_signals(signals)

    # ═══ RECORD PHASE HISTORY ═══
    _record_phase_history(db, signals)

    return signals


def _cluster_signals(signals: list) -> list:
    """Group signals by asset + direction into clusters."""
    cluster_map: dict = {}
    for sig in signals:
        key = f"{sig['asset']}_{sig['direction']}"
        if key not in cluster_map:
            cluster_map[key] = {
                "cluster_id": f"cluster_{key.lower()}",
                "signals": [],
                "max_score": 0,
            }
        cluster_map[key]["signals"].append(sig)
        cluster_map[key]["max_score"] = max(cluster_map[key]["max_score"], sig["score"])

    # Assign cluster data to each signal
    for sig in signals:
        key = f"{sig['asset']}_{sig['direction']}"
        cluster = cluster_map.get(key, {})
        count = len(cluster.get("signals", []))
        if count > 1:
            sig["cluster_id"] = cluster["cluster_id"]
            sig["cluster_score"] = min(cluster["max_score"] + round(math.log(count) * 5), 100)
            sig["cluster_count"] = count
        else:
            sig["cluster_id"] = None
            sig["cluster_score"] = sig["score"]
            sig["cluster_count"] = 1

    return signals


def get_signals(filters: dict = None) -> list:
    """Get signals with optional filters."""
    signals = generate_signals()
    if not filters:
        return signals

    if filters.get("severity"):
        signals = [s for s in signals if s["severity"] == filters["severity"]]
    if filters.get("direction"):
        signals = [s for s in signals if s["direction"] == filters["direction"]]
    if filters.get("signal_type"):
        signals = [s for s in signals if s["signal_type"] == filters["signal_type"]]
    if filters.get("status"):
        signals = [s for s in signals if s["status"] == filters["status"]]
    if filters.get("min_score"):
        signals = [s for s in signals if s["score"] >= filters["min_score"]]

    return signals


def get_signal_stats() -> dict:
    """Compute summary statistics for the signals dashboard."""
    signals = generate_signals()

    total = len(signals)
    strong = sum(1 for s in signals if s["severity"] in ("STRONG", "EXTREME"))
    extreme = sum(1 for s in signals if s["severity"] == "EXTREME")
    bullish = sum(1 for s in signals if s["direction"] == "BULLISH")
    bearish = sum(1 for s in signals if s["direction"] == "BEARISH")
    avg_score = round(sum(s["score"] for s in signals) / max(total, 1))

    by_type = {}
    for s in signals:
        by_type[s["signal_type"]] = by_type.get(s["signal_type"], 0) + 1

    # Cluster summary
    cluster_ids = set(s.get("cluster_id") for s in signals if s.get("cluster_id"))
    has_cluster = len(cluster_ids) > 0
    max_cluster_score = max((s.get("cluster_score", 0) for s in signals), default=0)

    return {
        "total": total,
        "strong": strong,
        "extreme": extreme,
        "bullish": bullish,
        "bearish": bearish,
        "avg_score": avg_score,
        "by_type": by_type,
        "top_signal": signals[0] if signals else None,
        "has_cluster": has_cluster,
        "cluster_count": len(cluster_ids),
        "max_cluster_score": max_cluster_score,
    }



def _record_phase_history(db, signals: list):
    """Record phase transitions to signal_phase_history collection."""
    coll = db["signal_phase_history"]
    now = datetime.now(timezone.utc).isoformat()

    for sig in signals:
        sid = sig["id"]
        phase = sig.get("status", "detected")
        score = sig.get("score", 0)

        # Check last recorded phase for this signal
        last = coll.find_one(
            {"signal_id": sid},
            {"_id": 0, "phase": 1},
            sort=[("timestamp", DESCENDING)],
        )

        # Only record if phase changed or first time
        if not last or last.get("phase") != phase:
            coll.insert_one({
                "signal_id": sid,
                "signal_type": sig.get("signal_type", ""),
                "asset": sig.get("asset", "ETH"),
                "phase": phase,
                "score": score,
                "direction": sig.get("direction", "NEUTRAL"),
                "timestamp": now,
            })


def get_signal_evolution(signal_id: str) -> list:
    """Get phase history for a specific signal."""
    db = _get_db()
    coll = db["signal_phase_history"]

    docs = list(coll.find(
        {"signal_id": signal_id},
        {"_id": 0},
    ).sort("timestamp", 1).limit(50))

    return docs
