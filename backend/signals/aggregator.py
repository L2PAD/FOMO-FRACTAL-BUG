"""
Signal Intelligence Layer — Execution Aggregator (VFinal)

Three-level signal hierarchy:
  L1: Execution Signal (weighted aggregate)
  L2: Structural Components (exchange, accDist, onchain)
  L3: Event Feed (short-term triggers)

Data sources:
  - Core Engine: pressure, factors, regime, risk, execution
  - Macro V2: capitalFlow, riskOff, regime, lmi, riskSplit
"""

import math
import time
from datetime import datetime, timezone


def _clamp(x, lo=-1.0, hi=1.0):
    return max(lo, min(hi, x))


def _sigmoid(x, k=4.0):
    return 1.0 / (1.0 + math.exp(-k * x))


def _bias_label(score):
    if score > 0.45:
        return "bullish_pressure"
    if score < -0.45:
        return "bearish_pressure"
    return "balanced"


def _direction(score):
    if score > 0.1:
        return "bullish"
    if score < -0.1:
        return "bearish"
    return "neutral"


def _narrative(bias, score, contributors):
    """Generate explanatory micro-copy for current state."""
    abs_score = abs(score)

    if bias == "balanced":
        if abs_score < 0.08:
            return "Market structurally balanced. No dominant flow pressure detected."
        return "Slight directional pressure present, but below execution threshold."

    # Find dominant contributor
    sorted_c = sorted(contributors.items(), key=lambda x: abs(x[1]), reverse=True)
    top_name = {"exchange": "exchange flow", "accDist": "accumulation patterns", "onchain": "on-chain activity"}
    dominant = top_name.get(sorted_c[0][0], sorted_c[0][0]) if sorted_c else "mixed signals"

    if bias == "bullish_pressure":
        if abs_score > 0.7:
            return f"Strong bullish structural pressure driven by {dominant}."
        return f"Moderate bullish pressure. Primary driver: {dominant}."

    if abs_score > 0.7:
        return f"Strong bearish structural pressure driven by {dominant}."
    return f"Moderate bearish pressure. Primary driver: {dominant}."


# ═══════════════════════════════════════════════
# STRUCTURAL COMPONENT SCORES
# ═══════════════════════════════════════════════

def compute_exchange_score(core_data, macro_data):
    """Exchange Pressure: capital flow direction from exchange activity.

    Sources:
      - Core: pressure.biasScore (directional flow from orderbook/trades)
      - Macro: capitalFlow.btc.pressure, capitalFlow.stable.pressure
    """
    # Core pressure bias: [-1, 1] already
    core_bias = core_data.get("pressure", {}).get("biasScore", 0)

    # Macro capital flow signals
    cf = macro_data.get("capitalFlow", {})
    btc_pressure = cf.get("btc", {}).get("pressure", "FLAT")
    stable_pressure = cf.get("stable", {}).get("pressure", "FLAT")

    # Convert macro pressures to numeric
    macro_signal = 0.0
    if btc_pressure == "IN":
        macro_signal += 0.3
    elif btc_pressure == "OUT":
        macro_signal -= 0.3

    if stable_pressure == "RISK_SHELTER":
        macro_signal -= 0.25  # Risk-off = bearish for execution
    elif stable_pressure == "DEPLOYING":
        macro_signal += 0.25  # Capital deploying = bullish

    # Blend core (real-time) with macro (daily)
    score = _clamp(0.6 * core_bias + 0.4 * macro_signal)

    # Strength: how far from zero
    strength = min(abs(score) * 1.5, 1.0)

    # Confidence from data availability
    has_core = abs(core_bias) > 0.001
    has_macro = btc_pressure != "FLAT" or stable_pressure != "FLAT"
    confidence = 0.5 + 0.25 * has_core + 0.25 * has_macro

    return {
        "score": round(score, 4),
        "strength": round(strength, 4),
        "confidence": round(confidence, 4),
        "direction": _direction(score),
        "details": {
            "coreBias": round(core_bias, 4),
            "btcPressure": btc_pressure,
            "stablePressure": stable_pressure,
            "macroSignal": round(macro_signal, 4),
        },
    }


def compute_accdist_score(core_data, macro_data):
    """Accumulation/Distribution: capital concentration patterns.

    Sources:
      - Core: factors.flow, factors.smartMoney
      - Macro: lmi (Liquidity Migration Index), capitalFlow deltas
    """
    factors = core_data.get("factors", {})
    flow_factor = factors.get("flow", 50) / 100  # normalize 0-1
    smart_money = factors.get("smartMoney", 50) / 100

    # Flow direction from core
    flow_conv = core_data.get("_raw_factors", {}).get("flow_conv", 0)

    # Macro LMI: positive = accumulation, negative = distribution
    lmi = macro_data.get("lmi", {})
    lmi_score_raw = lmi.get("score", 0) if isinstance(lmi, dict) else 0

    # Capital flow deltas
    cf = macro_data.get("capitalFlow", {})
    btc_delta = cf.get("btc", {}).get("delta7d", 0)
    stable_delta = cf.get("stable", {}).get("delta7d", 0)

    # Accumulation signal: BTC dom rising + stables deploying = accumulation
    macro_acc = _clamp(btc_delta * 0.3 - stable_delta * 0.2)

    # Combine
    core_signal = _clamp(flow_conv * 2 + (smart_money - 0.5) * 0.6)
    score = _clamp(0.5 * core_signal + 0.3 * _clamp(lmi_score_raw) + 0.2 * macro_acc)

    strength = min(abs(score) * 1.5, 1.0)
    confidence = 0.5 + 0.2 * (flow_factor > 0.3) + 0.15 * (smart_money > 0.3) + 0.15 * (abs(lmi_score_raw) > 0.01)

    return {
        "score": round(score, 4),
        "strength": round(strength, 4),
        "confidence": round(confidence, 4),
        "direction": _direction(score),
        "details": {
            "flowFactor": round(flow_factor, 4),
            "smartMoney": round(smart_money, 4),
            "lmiScore": round(lmi_score_raw, 4),
            "macroAcc": round(macro_acc, 4),
        },
    }


def compute_onchain_score(core_data, macro_data):
    """On-chain Activity: wallet activity momentum and large transaction shifts.

    Sources:
      - Core: factors.structure, factors.stability, regime confidence
      - Macro: riskSplit, regime probabilities
    """
    factors = core_data.get("factors", {})
    structure = factors.get("structure", 50) / 100
    stability = factors.get("stability", 50) / 100

    # Regime confidence as signal
    regime = core_data.get("regime", {})
    regime_conf = regime.get("confidence", 0.25)
    dominant = regime.get("dominant", "range")

    # Directional interpretation of regime
    regime_dir = 0.0
    if dominant == "trend":
        regime_dir = 0.3
    elif dominant == "breakout":
        regime_dir = 0.2
    elif dominant == "distribution":
        regime_dir = -0.3

    # Macro regime alignment
    macro_regime = macro_data.get("computed", {}).get("regime", "NEUTRAL")
    macro_dir = 0.0
    if macro_regime == "FLIGHT_TO_BTC":
        macro_dir = 0.15
    elif macro_regime == "ALT_ROTATION":
        macro_dir = 0.1
    elif macro_regime == "CAPITAL_EXIT":
        macro_dir = -0.25

    # Activity momentum: high structure + high stability = strong activity
    activity = (structure - 0.5) * 0.6 + (stability - 0.5) * 0.4

    score = _clamp(
        0.4 * activity +
        0.35 * regime_dir * min(regime_conf * 2, 1.0) +
        0.25 * macro_dir
    )

    strength = min(abs(score) * 1.5, 1.0)
    confidence = 0.4 + 0.3 * (regime_conf > 0.3) + 0.3 * (structure > 0.4)

    return {
        "score": round(score, 4),
        "strength": round(strength, 4),
        "confidence": round(confidence, 4),
        "direction": _direction(score),
        "details": {
            "structure": round(structure, 4),
            "stability": round(stability, 4),
            "regimeDirection": round(regime_dir, 4),
            "macroDirection": round(macro_dir, 4),
            "activityMomentum": round(activity, 4),
        },
    }


# ═══════════════════════════════════════════════
# EXECUTION AGGREGATOR (L1)
# ═══════════════════════════════════════════════

WEIGHTS = {
    "exchange": 0.45,
    "accDist": 0.35,
    "onchain": 0.20,
}


def compute_execution_signal(exchange, accdist, onchain):
    """Aggregate structural components into execution signal."""
    score = _clamp(
        WEIGHTS["exchange"] * exchange["score"] +
        WEIGHTS["accDist"] * accdist["score"] +
        WEIGHTS["onchain"] * onchain["score"]
    )

    # Weighted confidence
    confidence = (
        WEIGHTS["exchange"] * exchange["confidence"] +
        WEIGHTS["accDist"] * accdist["confidence"] +
        WEIGHTS["onchain"] * onchain["confidence"]
    )

    # Strength: sigmoid-shaped from score magnitude
    strength = _sigmoid(abs(score), k=5.0) * 2 - 1  # maps 0→0, 1→~0.99
    strength = round(max(0, strength), 4)

    bias = _bias_label(score)

    contributors = {
        "exchange": round(WEIGHTS["exchange"] * exchange["score"], 4),
        "accDist": round(WEIGHTS["accDist"] * accdist["score"], 4),
        "onchain": round(WEIGHTS["onchain"] * onchain["score"], 4),
    }

    narrative = _narrative(bias, score, contributors)

    # Activity Mode: formalized from sum of absolute structural scores
    # Activity = (|Exchange| + |AccDist| + |OnChain|) / 3, normalized [0,1]
    raw_activity = (abs(exchange["score"]) + abs(accdist["score"]) + abs(onchain["score"])) / 3.0
    activity_norm = min(raw_activity / 0.5, 1.0)  # normalize: 0.5 raw → 1.0

    if activity_norm > 0.65:
        execution_mode = "HIGH_ACTIVITY"
    elif activity_norm > 0.35:
        execution_mode = "MODERATE_ACTIVITY"
    else:
        execution_mode = "LOW_ACTIVITY"

    return {
        "score": round(score, 4),
        "bias": bias,
        "strength": strength,
        "confidence": round(confidence, 4),
        "executionMode": execution_mode,
        "activityLevel": round(activity_norm, 4),
        "contributors": contributors,
        "weights": WEIGHTS,
        "narrative": narrative,
    }


# ═══════════════════════════════════════════════
# EVENT GENERATOR (L3)
# ═══════════════════════════════════════════════

def generate_events(core_data, macro_data):
    """Generate short-term trigger events from threshold crossings."""
    events = []
    now = datetime.now(timezone.utc).isoformat()

    # Check for extreme fear/greed
    fg = macro_data.get("raw", {}).get("fearGreed", 50)
    if fg <= 20:
        events.append({
            "type": "EXTREME_FEAR",
            "source": "macro",
            "level": "EVENT",
            "direction": "bearish",
            "strength": round(min((25 - fg) / 25, 1.0), 2),
            "confidence": 0.85,
            "impactOnExecution": round(-0.15 * min((25 - fg) / 25, 1.0), 4),
            "ttl": "24h",
            "description": f"Fear & Greed at {fg} — extreme fear zone",
            "timestamp": now,
        })
    elif fg >= 80:
        events.append({
            "type": "EXTREME_GREED",
            "source": "macro",
            "level": "EVENT",
            "direction": "bullish",
            "strength": round(min((fg - 75) / 25, 1.0), 2),
            "confidence": 0.75,
            "impactOnExecution": round(0.10 * min((fg - 75) / 25, 1.0), 4),
            "ttl": "24h",
            "description": f"Fear & Greed at {fg} — extreme greed zone",
            "timestamp": now,
        })

    # Risk-off spike
    riskoff = macro_data.get("computed", {}).get("riskOffProb", 0.5)
    if riskoff > 0.7:
        events.append({
            "type": "RISKOFF_SPIKE",
            "source": "macro",
            "level": "EVENT",
            "direction": "bearish",
            "strength": round(min((riskoff - 0.6) / 0.4, 1.0), 2),
            "confidence": 0.80,
            "impactOnExecution": round(-0.20 * min((riskoff - 0.6) / 0.4, 1.0), 4),
            "ttl": "12h",
            "description": f"Risk-Off probability at {riskoff:.0%}",
            "timestamp": now,
        })

    # Strong actions blocked
    if macro_data.get("computed", {}).get("strongActionsBlocked"):
        events.append({
            "type": "ACTIONS_BLOCKED",
            "source": "macro",
            "level": "EVENT",
            "direction": "bearish",
            "strength": 0.90,
            "confidence": 0.95,
            "impactOnExecution": -0.25,
            "ttl": "until_clear",
            "description": "Strong actions blocked by macro conditions",
            "timestamp": now,
        })

    # Capital exit regime
    regime = macro_data.get("computed", {}).get("regime", "NEUTRAL")
    regime_probs = macro_data.get("computed", {}).get("regimeProbs", {})
    if regime == "CAPITAL_EXIT" and regime_probs.get("CAPITAL_EXIT", 0) > 0.4:
        events.append({
            "type": "CAPITAL_EXIT_REGIME",
            "source": "macro",
            "level": "EVENT",
            "direction": "bearish",
            "strength": round(regime_probs["CAPITAL_EXIT"], 2),
            "confidence": 0.82,
            "impactOnExecution": -0.20,
            "ttl": "24h",
            "description": f"Capital Exit regime at {regime_probs['CAPITAL_EXIT']:.0%} probability",
            "timestamp": now,
        })

    # High shift probability (regime instability)
    shift_prob = core_data.get("transition", {}).get("shiftProbability", 0)
    if shift_prob > 0.5:
        events.append({
            "type": "REGIME_INSTABILITY",
            "source": "structural",
            "level": "EVENT",
            "direction": "neutral",
            "strength": round(min(shift_prob, 1.0), 2),
            "confidence": 0.70,
            "impactOnExecution": round(-0.10 * shift_prob, 4),
            "ttl": "8h",
            "description": f"Regime shift probability at {shift_prob:.0%}",
            "timestamp": now,
        })

    # High risk level
    risk_idx = core_data.get("risk", {}).get("totalIndex", 50)
    if risk_idx > 65:
        events.append({
            "type": "HIGH_RISK",
            "source": "structural",
            "level": "EVENT",
            "direction": "bearish",
            "strength": round(min((risk_idx - 50) / 50, 1.0), 2),
            "confidence": 0.78,
            "impactOnExecution": round(-0.15 * min((risk_idx - 50) / 50, 1.0), 4),
            "ttl": "6h",
            "description": f"Risk index elevated at {risk_idx}/100",
            "timestamp": now,
        })

    # BTC dominance surge (from macro capital flow)
    btc_delta7d = macro_data.get("capitalFlow", {}).get("btc", {}).get("delta7d", 0)
    if abs(btc_delta7d) > 1.0:
        direction = "bullish" if btc_delta7d > 0 else "bearish"
        events.append({
            "type": "BTC_DOMINANCE_SHIFT",
            "source": "structural",
            "level": "EVENT",
            "direction": direction,
            "strength": round(min(abs(btc_delta7d) / 3.0, 1.0), 2),
            "confidence": 0.72,
            "impactOnExecution": round(0.08 * (1 if btc_delta7d > 0 else -1) * min(abs(btc_delta7d) / 3.0, 1.0), 4),
            "ttl": "24h",
            "description": f"BTC dominance shifted {btc_delta7d:+.2f}% in 7d",
            "timestamp": now,
        })

    # Sort by absolute impact
    events.sort(key=lambda e: abs(e.get("impactOnExecution", 0)), reverse=True)

    return events


# ═══════════════════════════════════════════════
# SIGNAL STATS
# ═══════════════════════════════════════════════

def compute_signal_stats(execution, structural, events):
    """Compute summary stats for the signal dashboard."""
    active_events = len(events)
    bearish_events = sum(1 for e in events if e["direction"] == "bearish")
    bullish_events = sum(1 for e in events if e["direction"] == "bullish")

    # Overall structural strength
    struct_scores = [structural["exchange"]["strength"], structural["accDist"]["strength"], structural["onchain"]["strength"]]
    avg_strength = sum(struct_scores) / len(struct_scores)

    return {
        "activeEvents": active_events,
        "bearishEvents": bearish_events,
        "bullishEvents": bullish_events,
        "structuralStrength": round(avg_strength, 4),
        "executionScore": execution["score"],
        "executionBias": execution["bias"],
        "executionMode": execution["executionMode"],
    }


# ═══════════════════════════════════════════════
# MAIN AGGREGATION
# ═══════════════════════════════════════════════

def _compute_core_alignment(execution, core_data):
    """Compare Execution bias direction with Core Engine pressure direction.

    Returns: ALIGNED | MIXED | DIVERGING
    """
    exec_bias = execution["bias"]
    core_label = core_data.get("pressure", {}).get("biasLabel", "neutral")

    # Map to simple direction
    exec_dir = 0
    if exec_bias == "bullish_pressure":
        exec_dir = 1
    elif exec_bias == "bearish_pressure":
        exec_dir = -1

    core_dir = 0
    if core_label in ("bullish", "slight_bullish"):
        core_dir = 1
    elif core_label in ("bearish", "slight_bearish"):
        core_dir = -1

    if exec_dir == 0 and core_dir == 0:
        return {"status": "ALIGNED", "detail": "Both neutral"}
    if exec_dir == core_dir:
        return {"status": "ALIGNED", "detail": f"Both {['bearish','neutral','bullish'][exec_dir+1]}"}
    if exec_dir == 0 or core_dir == 0:
        return {"status": "MIXED", "detail": "One neutral, one directional"}
    return {"status": "DIVERGING", "detail": "Opposite directions"}


def compute_unified_signal(core_data, macro_data, asset="BTCUSDT"):
    """Compute full unified signal for an asset."""
    # L2: Structural components
    exchange = compute_exchange_score(core_data, macro_data)
    accdist = compute_accdist_score(core_data, macro_data)
    onchain = compute_onchain_score(core_data, macro_data)

    # L1: Execution signal
    execution = compute_execution_signal(exchange, accdist, onchain)

    # L3: Events
    events = generate_events(core_data, macro_data)

    # Core Alignment
    alignment = _compute_core_alignment(execution, core_data)

    # Stats
    stats = compute_signal_stats(execution, {"exchange": exchange, "accDist": accdist, "onchain": onchain}, events)

    return {
        "ok": True,
        "asset": asset,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "execution": execution,
        "structural": {
            "exchange": exchange,
            "accDist": accdist,
            "onchain": onchain,
        },
        "events": events,
        "coreAlignment": alignment,
        "stats": stats,
    }
