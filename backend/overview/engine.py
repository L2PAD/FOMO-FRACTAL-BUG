"""
Overview V2.3 — Decision Engine + History + Events

Extended from V2.2:
  - Rich position history (sizeMult, directionFinal, totalRisk, macroMult, action, mode, gates, drivers)
  - Event detection (ACTION_FLIP, REGIME_CHANGE, GATE_CHANGE, RISK_SPIKE)
  - Altcoin Rotation Phase (Acceleration/Neutral/Compression)
  - directionFinal exposed in decision for strength gauge
"""

import math
from datetime import datetime, timezone
from collections import deque


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _sigmoid(x):
    try:
        return 1.0 / (1.0 + math.exp(-x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0


# ═══════════════════════════════════════════════
# STATE TRACKING (module-level)
# ═══════════════════════════════════════════════
_prev_direction = {}
_prev_action = {}
_prev_regime = {}
_prev_gates = {}
_prev_total_risk = {}
_regime_state = {}
_position_history = {}     # asset → deque of rich snapshots
_event_history = {}        # asset → deque of events

MAX_HISTORY = 2880         # 30 days at 15min intervals
MAX_EVENTS = 500


# ═══════════════════════════════════════════════
# HYBRID BTC↔SPX
# ═══════════════════════════════════════════════

def compute_hybrid(hybrid_raw, risk_off_prob):
    if not hybrid_raw or not hybrid_raw.get("ok"):
        return None

    corr = hybrid_raw.get("correlation30d", 0)
    beta = hybrid_raw.get("beta", 1.0)
    divergence = hybrid_raw.get("divergenceScore", 0)
    spillover = _clamp(abs(corr) * (1 + abs(divergence)), -1, 1)
    beta_norm = _clamp((beta - 1.0) / 3.0, -1, 1)
    corr_norm = _clamp(corr, -1, 1)
    spill_norm = _clamp(spillover, -1, 1)
    hybrid = 0.45 * corr_norm + 0.35 * beta_norm + 0.20 * spill_norm
    hybrid_final = hybrid * (1 - 0.6 * risk_off_prob)

    if hybrid_final > 0.25:
        interp = "SPX reinforces BTC move"
    elif hybrid_final < -0.25:
        interp = "SPX dampens / inverts BTC move"
    else:
        interp = "Neutral coupling"

    return {
        "beta": round(beta, 2),
        "correlation": round(corr, 3),
        "spillover": round(spillover, 3),
        "hybridScore": round(hybrid_final, 4),
        "interpretation": interp,
        "meta": hybrid_raw.get("meta", {}),
    }


# ═══════════════════════════════════════════════
# ALTCOIN OUTLOOK ENGINE
# ═══════════════════════════════════════════════

def compute_alt_outlook(macro_data):
    computed = macro_data.get("computed", {})
    cf = macro_data.get("capitalFlow", {})
    lmi = macro_data.get("lmi", {})

    btc_delta = cf.get("btc", {}).get("delta7d", 0)
    btc_dom_shift = _clamp(btc_delta / 3.0, -1, 1)
    stable_delta = cf.get("stable", {}).get("delta7d", 0)
    stable_shift = _clamp(-stable_delta / 2.0, -1, 1)
    lmi_score = lmi.get("score", 0) if isinstance(lmi, dict) else 0
    lmi_norm = _clamp(lmi_score * 2, -1, 1)
    risk_off = computed.get("riskOffProb", 0.5)
    risk_norm = _clamp((risk_off - 0.5) * 2, -1, 1)

    alt_score = _clamp(
        -0.40 * btc_dom_shift +
        0.30 * stable_shift +
        0.20 * lmi_norm -
        0.10 * risk_norm,
        -1, 1
    )
    rotation_prob = _sigmoid(3 * alt_score)

    if alt_score > 0.35:
        status = "ALT_BULLISH"
    elif alt_score < -0.35:
        status = "ALT_BEARISH"
    else:
        status = "ALT_NEUTRAL"

    # Rotation phase (V2.3)
    if alt_score > 0.2 and lmi_norm > 0:
        phase = "ACCELERATION"
    elif alt_score < -0.2 and lmi_norm < 0:
        phase = "COMPRESSION"
    else:
        phase = "NEUTRAL"

    return {
        "score": round(alt_score, 4),
        "rotationProb": round(rotation_prob, 4),
        "status": status,
        "phase": phase,
        "drivers": {
            "btcDomShift": round(btc_dom_shift, 4),
            "stableShift": round(stable_shift, 4),
            "lmi": round(lmi_norm, 4),
            "riskImpact": round(-risk_norm * 0.10, 4),
        },
        "raw": {
            "btcDelta7d": round(btc_delta, 2),
            "stableDelta7d": round(stable_delta, 2),
            "lmiScore": round(lmi_score, 4),
            "riskOff": round(risk_off, 4),
        },
    }


# ═══════════════════════════════════════════════
# ADMIN CONFIG (dynamic thresholds)
# ═══════════════════════════════════════════════

_config = {
    "signals": {
        "executionThreshold": 0.45,
        "lowActivityThreshold": 0.15,
    },
    "decision": {
        "holdThreshold": 0.25,
        "edgeMin": 0.25,
        "buyThreshold": 0.45,
    },
    "macroGates": {
        "riskOffBlockThreshold": 0.75,
        "structuralRiskBlock": 75,
        "extremeFearThreshold": 15,
        "fearRecoveryTarget": 30,
    },
    "altOutlook": {
        "bullishThreshold": 0.35,
        "bearishThreshold": -0.35,
    },
    "profile": "prod-v2.3",
    "frozen": False,
    "frozenAt": None,
    "frozenReason": None,
}

_frozen_snapshot = {}  # cached snapshot when frozen

_config_defaults = {k: v.copy() if isinstance(v, dict) else v for k, v in _config.items()}


def get_config():
    return _config


def update_config(patch):
    for key, val in patch.items():
        if key in _config and isinstance(_config[key], dict) and isinstance(val, dict):
            _config[key].update(val)
        elif key in _config:
            _config[key] = val
    return _config


def freeze_system(reason="Manual freeze"):
    _config["frozen"] = True
    _config["frozenAt"] = datetime.now(timezone.utc).isoformat()
    _config["frozenReason"] = reason


def unfreeze_system():
    _config["frozen"] = False
    _config["frozenAt"] = None
    _config["frozenReason"] = None


def set_frozen_snapshot(snapshot):
    global _frozen_snapshot
    _frozen_snapshot = snapshot


def get_frozen_snapshot():
    return _frozen_snapshot


def get_config_defaults():
    return _config_defaults


# ═══════════════════════════════════════════════
# DECISION ENGINE V2.3
# ═══════════════════════════════════════════════

def compute_decision(core_data, macro_data, signals_data, hybrid_dto, alt_outlook, asset="BTCUSDT"):
    global _prev_direction, _prev_action, _prev_regime, _prev_gates, _prev_total_risk

    cfg = _config

    pressure_label = core_data.get("pressure", {}).get("biasLabel", "neutral")
    core_bias = 0
    if pressure_label in ("bullish", "slight_bullish"):
        core_bias = 1
    elif pressure_label in ("bearish", "slight_bearish"):
        core_bias = -1

    execution_score = signals_data.get("execution", {}).get("score", 0)
    hybrid_score = hybrid_dto.get("hybridScore", 0) if hybrid_dto else 0
    macro_mult = _clamp(macro_data.get("computed", {}).get("macroMult", 0.7), 0.4, 1.05)
    risk_off_prob = macro_data.get("computed", {}).get("riskOffProb", 0.5)
    blocked = macro_data.get("computed", {}).get("strongActionsBlocked", False)

    risk_split = macro_data.get("riskSplit", {})
    structural_risk = risk_split.get("structural", 50)
    tactical_risk = risk_split.get("tactical", 50)
    total_risk = 0.6 * structural_risk + 0.4 * tactical_risk

    alignment = signals_data.get("coreAlignment", {})
    alignment_score = {"ALIGNED": 0.3, "MIXED": 0.0, "DIVERGING": -0.3}.get(alignment.get("status", "MIXED"), 0)

    # Step 1: Direction
    direction_raw = core_bias * abs(execution_score)
    direction_macro = direction_raw * macro_mult
    direction_final = direction_macro * (1 + 0.25 * hybrid_score) if direction_macro != 0 else 0
    edge_strength = abs(direction_final)

    # Gates (use config thresholds)
    riskoff_block = cfg["macroGates"]["riskOffBlockThreshold"]
    structural_block = cfg["macroGates"]["structuralRiskBlock"]
    fear_threshold = cfg["macroGates"]["extremeFearThreshold"]
    hold_threshold = cfg["decision"]["holdThreshold"]
    buy_threshold = cfg["decision"]["buyThreshold"]

    gates = []
    if blocked:
        gates.append("MACRO_BLOCKED")
    if risk_off_prob > riskoff_block:
        gates.append("RISK_OFF")
    if structural_risk > structural_block:
        gates.append("HIGH_STRUCTURAL_RISK")
    fg = macro_data.get("raw", {}).get("fearGreed", 50)
    if fg <= fear_threshold:
        gates.append("EXTREME_FEAR")
    if edge_strength < hold_threshold and not gates:
        gates.append("LOW_EDGE")

    # Action
    no_trade_gates = {"MACRO_BLOCKED", "RISK_OFF", "HIGH_STRUCTURAL_RISK"}
    if no_trade_gates & set(gates):
        action = "NO_TRADE"
    elif direction_final > buy_threshold:
        action = "BUY"
    elif direction_final < -buy_threshold:
        action = "SELL"
    elif edge_strength >= hold_threshold:
        action = "HOLD"
    else:
        action = "NO_TRADE"

    # Position Size
    conf_factor = _sigmoid(4 * edge_strength - 2)
    risk_factor = math.exp(-total_risk / 100)
    sync_factor = math.exp(alignment_score)
    size_mult = _clamp(conf_factor * risk_factor * sync_factor, 0, 1.2)
    if action == "NO_TRADE":
        size_mult = 0.0

    confidence = _clamp(edge_strength * macro_mult, 0, 1)

    appetite = confidence - total_risk / 100
    if appetite < -0.2:
        mode = "DEFENSIVE"
    elif appetite > 0.2:
        mode = "AGGRESSIVE"
    else:
        mode = "NEUTRAL"

    size_breakdown = {
        "edgeStrength": round(edge_strength, 4),
        "confFactor": round(conf_factor, 4),
        "riskFactor": round(risk_factor, 4),
        "syncFactor": round(sync_factor, 4),
        "finalSize": round(size_mult, 4),
    }

    rotation_prob = alt_outlook.get("rotationProb", 0.5)
    alt_weight = _clamp(rotation_prob, 0, 1)
    btc_weight = 1 - alt_weight
    allocation = {
        "btc": round(size_mult * btc_weight * 100, 1),
        "alts": round(size_mult * alt_weight * 100, 1),
        "stable": round(max(0, (1 - size_mult)) * 100, 1),
    }

    # Reasons
    reasons = []
    macro_regime = macro_data.get("computed", {}).get("regime", "NEUTRAL")
    macro_impact = round(-(1 - macro_mult), 2)
    if blocked:
        reasons.append({"layer": "macro", "text": f"Actions blocked. Risk-Off {risk_off_prob:.0%}", "impact": round(-risk_off_prob, 2)})
    else:
        reasons.append({"layer": "macro", "text": f"{macro_regime.replace('_', ' ').title()}. Mult {macro_mult:.2f}", "impact": macro_impact})

    regime_dom = core_data.get("regime", {}).get("dominant", "range")
    regime_conf = core_data.get("regime", {}).get("confidence", 0.25)
    core_impact = round(direction_raw, 2)
    reasons.append({"layer": "core", "text": f"{regime_dom.title()} ({regime_conf:.0%}). Bias: {pressure_label}", "impact": core_impact})

    exec_bias = signals_data.get("execution", {}).get("bias", "balanced")
    signals_impact = round(execution_score, 2)
    reasons.append({"layer": "signals", "text": f"Execution {exec_bias.replace('_', ' ')}. Score {execution_score:.2f}", "impact": signals_impact})

    # Normalize impacts to percentage contribution
    abs_total = sum(abs(r["impact"]) for r in reasons)
    for r in reasons:
        r["impactPct"] = round(abs(r["impact"]) / abs_total * 100, 1) if abs_total > 0 else round(100 / len(reasons), 1)

    # Flip Triggers (max 4)
    flip_triggers = []
    fear_recovery = cfg["macroGates"]["fearRecoveryTarget"]
    if action == "NO_TRADE":
        if blocked:
            flip_triggers.append({"condition": "Macro unblock", "current": "Blocked", "target": "Clear"})
        if risk_off_prob > riskoff_block:
            flip_triggers.append({"condition": "Risk-Off < 50%", "current": f"{risk_off_prob:.0%}", "target": "50%"})
        if structural_risk > structural_block:
            flip_triggers.append({"condition": f"Structural < {structural_block}", "current": f"{structural_risk:.0f}", "target": str(int(structural_block))})
        if edge_strength < hold_threshold:
            flip_triggers.append({"condition": f"Edge > {hold_threshold}", "current": f"{edge_strength:.2f}", "target": str(hold_threshold)})
    elif action == "HOLD":
        flip_triggers.append({"condition": f"Direction > ±{buy_threshold}", "current": f"{direction_final:.2f}", "target": f"±{buy_threshold}"})
    elif action in ("BUY", "SELL"):
        flip_triggers.append({"condition": "Direction reversal", "current": f"{direction_final:.2f}", "target": f"< {hold_threshold}"})

    if risk_off_prob > 0.5 and "Risk-Off" not in str(flip_triggers):
        flip_triggers.append({"condition": "Risk-Off drop", "current": f"{risk_off_prob:.0%}", "target": "< 40%"})
    if fg < fear_recovery:
        flip_triggers.append({"condition": "Fear recovery", "current": f"F&G {fg:.0f}", "target": f"> {fear_recovery}"})
    flip_triggers = flip_triggers[:4]

    # Decision Trace
    trace = {
        "steps": [
            {"name": "Core Bias", "value": round(core_bias, 4), "formula": f"bias='{pressure_label}' → {core_bias}"},
            {"name": "× Execution", "value": round(execution_score, 4), "formula": f"|exec|={abs(execution_score):.4f}"},
            {"name": "= Dir Raw", "value": round(direction_raw, 4), "formula": f"core × |exec| = {direction_raw:.4f}"},
            {"name": "× Macro", "value": round(macro_mult, 4), "formula": f"dir × {macro_mult:.2f} = {direction_macro:.4f}"},
            {"name": "× Hybrid", "value": round(1 + 0.25 * hybrid_score, 4), "formula": f"1+0.25×{hybrid_score:.3f}"},
            {"name": "= Final", "value": round(direction_final, 4), "formula": f"|dir|={edge_strength:.4f} → {action}"},
        ],
        "sizeSteps": [
            {"name": "conf(edge)", "value": round(conf_factor, 4), "formula": f"σ(4×{edge_strength:.3f}-2)={conf_factor:.4f}"},
            {"name": "exp(-risk)", "value": round(risk_factor, 4), "formula": f"exp(-{total_risk:.1f}/100)={risk_factor:.4f}"},
            {"name": "exp(sync)", "value": round(sync_factor, 4), "formula": f"exp({alignment_score:.2f})={sync_factor:.4f}"},
            {"name": "= size", "value": round(size_mult, 4), "formula": f"{conf_factor:.3f}×{risk_factor:.3f}×{sync_factor:.3f}={size_mult:.4f}"},
        ],
    }

    # Stability: always 1 - |directionFinal(t) - directionFinal(t-1)|
    prev_dir = _prev_direction.get(asset, 0)
    stability = round(1 - min(abs(direction_final - prev_dir), 1.0), 4)
    _prev_direction[asset] = direction_final

    prev_act = _prev_action.get(asset, action)
    action_changed = prev_act != action
    _prev_action[asset] = action

    # Detect events
    now_ts = int(datetime.now(timezone.utc).timestamp())
    if asset not in _event_history:
        _event_history[asset] = deque(maxlen=MAX_EVENTS)

    if action_changed and prev_act is not None:
        _event_history[asset].append({"ts": now_ts, "type": "ACTION_FLIP", "meta": {"from": prev_act, "to": action}})

    prev_regime_val = _prev_regime.get(asset)
    if prev_regime_val is not None and prev_regime_val != macro_regime:
        _event_history[asset].append({"ts": now_ts, "type": "REGIME_CHANGE", "meta": {"from": prev_regime_val, "to": macro_regime}})
    _prev_regime[asset] = macro_regime

    prev_gates_val = _prev_gates.get(asset, [])
    if set(prev_gates_val) != set(gates):
        _event_history[asset].append({"ts": now_ts, "type": "GATE_CHANGE", "meta": {"from": prev_gates_val, "to": gates}})
    _prev_gates[asset] = gates[:]

    prev_risk = _prev_total_risk.get(asset)
    if prev_risk is not None:
        risk_hist = list(_position_history.get(asset, []))[-6:]
        avg_risk = sum(h.get("totalRisk", 50) for h in risk_hist) / max(len(risk_hist), 1) if risk_hist else 50
        if total_risk - avg_risk > 12:
            _event_history[asset].append({"ts": now_ts, "type": "RISK_SPIKE", "meta": {"delta": round(total_risk - avg_risk, 1), "totalRisk": round(total_risk, 1)}})
    _prev_total_risk[asset] = total_risk

    # Rich Position History
    if asset not in _position_history:
        _position_history[asset] = deque(maxlen=MAX_HISTORY)

    top_drivers = []
    if blocked:
        top_drivers.append("Macro blocked")
    if risk_off_prob > 0.6:
        top_drivers.append(f"Risk-Off {risk_off_prob:.0%}")
    if abs(execution_score) < 0.15:
        top_drivers.append("Execution low")
    if edge_strength < 0.25:
        top_drivers.append("Low edge")
    if fg < 25:
        top_drivers.append(f"Fear F&G={fg:.0f}")

    _position_history[asset].append({
        "ts": now_ts,
        "sizeMult": round(size_mult, 4),
        "directionFinal": round(direction_final, 4),
        "macroMult": round(macro_mult, 4),
        "totalRisk": round(total_risk, 1),
        "action": action,
        "mode": mode,
        "confidence": round(confidence, 4),
        "edge": round(edge_strength, 4),
        "gates": gates[:],
        "drivers": top_drivers[:2],
        "riskOffProb": round(risk_off_prob, 4),
        "executionScore": round(execution_score, 4),
    })

    return {
        "action": action,
        "sizeMult": round(size_mult, 4),
        "directionFinal": round(direction_final, 4),
        "mode": mode,
        "confidence": round(confidence, 4),
        "gates": gates,
        "reasons": reasons,
        "sizeBreakdown": size_breakdown,
        "allocation": allocation,
        "flipTriggers": flip_triggers,
        "trace": trace,
        "stability": {
            "index": stability,
            "actionChanged": action_changed,
            "prevAction": prev_act,
        },
    }


# ═══════════════════════════════════════════════
# REGIME PERSISTENCE
# ═══════════════════════════════════════════════

def _update_regime_persistence(asset, regime_label):
    global _regime_state
    now = datetime.now(timezone.utc)
    state = _regime_state.get(asset)
    if not state or state["regime"] != regime_label:
        _regime_state[asset] = {"regime": regime_label, "since": now.isoformat(), "count": 1}
        return {"regime": regime_label, "since": now.isoformat(), "periods": 1, "isNew": True}
    else:
        state["count"] += 1
        return {"regime": regime_label, "since": state["since"], "periods": state["count"], "isNew": False}


# ═══════════════════════════════════════════════
# EXTRACT HELPERS
# ═══════════════════════════════════════════════

def extract_core_snapshot(core_data, asset="BTCUSDT"):
    regime = core_data.get("regime", {})
    dominant = regime.get("dominant", "range")
    regime_map = {"trend": "MARKUP", "breakout": "MARKUP", "range": "ACCUMULATION",
                  "distribution": "DISTRIBUTION", "markdown": "MARKDOWN"}
    pressure = core_data.get("pressure", {})
    bias_label = pressure.get("biasLabel", "neutral")
    bias_map = {"bullish": "BULLISH", "slight_bullish": "BULLISH",
                "bearish": "BEARISH", "slight_bearish": "BEARISH"}
    edge_score = _clamp(pressure.get("biasScore", 0), -1, 1)
    bias = bias_map.get(bias_label, "NEUTRAL")

    if bias == "BULLISH":
        bull, base, bear = 0.35 + 0.15 * edge_score, 0.40, 0.25 - 0.15 * edge_score
    elif bias == "BEARISH":
        bull, base, bear = 0.25 + 0.15 * edge_score, 0.38, 0.37 - 0.15 * edge_score
    else:
        bull, base, bear = 0.30, 0.42, 0.28

    risk = core_data.get("risk", {})
    regime_label = regime_map.get(dominant, "ACCUMULATION")
    persistence = _update_regime_persistence(asset, regime_label)

    return {
        "regime": regime_label,
        "regimeProb": round(regime.get("confidence", 0.25), 4),
        "bias": bias,
        "edgeScore": round(edge_score, 4),
        "outcomes": {"bull": round(_clamp(bull, 0, 1), 2), "base": round(_clamp(base, 0, 1), 2), "bear": round(_clamp(bear, 0, 1), 2)},
        "riskLevel": risk.get("level", "moderate"),
        "riskIndex": risk.get("totalIndex", 50),
        "persistence": persistence,
    }


def extract_signals_summary(signals_data):
    execution = signals_data.get("execution", {})
    events = signals_data.get("events", [])
    top_events = [{"title": ev.get("type", "").replace("_", " "), "impact": ev.get("impactOnExecution", 0), "source": ev.get("source", "structural")} for ev in events[:3]]
    return {
        "executionScore": execution.get("score", 0),
        "bias": execution.get("bias", "balanced").upper(),
        "activityMode": execution.get("executionMode", "LOW_ACTIVITY").replace("_ACTIVITY", ""),
        "contributors": execution.get("contributors", {"exchange": 0, "accDist": 0, "onchain": 0}),
        "topEvents": top_events,
    }


def extract_macro_context(macro_data):
    computed = macro_data.get("computed", {})
    raw = macro_data.get("raw", {})
    lmi = macro_data.get("lmi", {})
    return {
        "regime": computed.get("regime", "NEUTRAL"),
        "probability": round(max(computed.get("regimeProbs", {}).values() or [0.25]), 4),
        "riskOffProb": round(computed.get("riskOffProb", 0.5), 4),
        "macroMult": round(_clamp(computed.get("macroMult", 0.7), 0.4, 1.05), 4),
        "fearGreed": raw.get("fearGreed", 50),
        "lmi": round(lmi.get("score", 0) if isinstance(lmi, dict) else 0, 4),
        "blocked": computed.get("strongActionsBlocked", False),
    }


def extract_risk_split(macro_data):
    risk = macro_data.get("riskSplit", {})
    s, t = risk.get("structural", 50), risk.get("tactical", 50)
    return {"structural": round(s, 1), "tactical": round(t, 1), "total": round(0.6 * s + 0.4 * t, 1)}


def extract_alerts(signals_data, macro_data):
    events = signals_data.get("events", [])
    active = len(events)
    high_priority = sum(1 for e in events if abs(e.get("impactOnExecution", 0)) > 0.15)
    triggers = []
    exec_score = signals_data.get("execution", {}).get("score", 0)
    if abs(exec_score) < 0.45:
        d = ">" if exec_score >= 0 else "<"
        triggers.append(f"Execution {d} {0.45 if exec_score >= 0 else -0.45}")
    if macro_data.get("computed", {}).get("riskOffProb", 0.5) > 0.5:
        triggers.append("Risk-Off drop below 50%")
    if macro_data.get("computed", {}).get("strongActionsBlocked"):
        triggers.append("Macro unblock")
    return {"active": active, "highPriority": high_priority, "triggers": triggers[:3]}


# ═══════════════════════════════════════════════
# POSITION HISTORY API
# ═══════════════════════════════════════════════

def get_position_history(asset="BTCUSDT", range_str="30d", step_sec=1800):
    """Return position history filtered by range."""
    history = list(_position_history.get(asset, []))
    events = list(_event_history.get(asset, []))

    now_ts = int(datetime.now(timezone.utc).timestamp())
    range_map = {"6h": 6 * 3600, "24h": 24 * 3600, "7d": 7 * 86400, "30d": 30 * 86400}
    cutoff = now_ts - range_map.get(range_str, 30 * 86400)

    filtered_series = [h for h in history if h["ts"] >= cutoff]
    filtered_events = [e for e in events if e["ts"] >= cutoff]

    # Compute stats
    if filtered_series:
        actions = [h["action"] for h in filtered_series]
        flips = sum(1 for i in range(1, len(actions)) if actions[i] != actions[i - 1])
        avg_size = sum(h["sizeMult"] for h in filtered_series) / len(filtered_series)
        stabilities = []
        for i in range(1, len(filtered_series)):
            s = 1 - min(abs(filtered_series[i]["directionFinal"] - filtered_series[i - 1]["directionFinal"]), 1.0)
            stabilities.append(s)
        avg_stability = sum(stabilities) / len(stabilities) if stabilities else 1.0
        blocked_count = sum(1 for h in filtered_series if "MACRO_BLOCKED" in h.get("gates", []))
        blocked_pct = blocked_count / len(filtered_series)
    else:
        flips, avg_size, avg_stability, blocked_pct = 0, 0, 1.0, 0

    return {
        "range": range_str,
        "stepSec": step_sec,
        "series": filtered_series,
        "events": filtered_events,
        "stats": {
            "flipCount": flips,
            "avgSize": round(avg_size, 4),
            "avgStability": round(avg_stability, 4),
            "blockedPct": round(blocked_pct, 4),
            "totalPoints": len(filtered_series),
        },
    }


# ═══════════════════════════════════════════════
# LABS DRILLDOWN
# ═══════════════════════════════════════════════

def compute_labs_drilldown(core_data, macro_data, signals_data, decision_data):
    """Build labs drilldown from existing data sources."""
    computed = macro_data.get("computed", {})
    regime_probs = computed.get("regimeProbs", {})
    current_regime = computed.get("regime", "NEUTRAL")

    # State probability
    state_probs = []
    for rid, p in sorted(regime_probs.items(), key=lambda x: -x[1]):
        state_probs.append({"id": rid, "p": round(p, 4), "current": rid == current_regime})

    # Transitions
    transitions_data = macro_data.get("transitions", {})
    trans_probs = transitions_data.get("probabilities", {})
    transitions_list = []
    for tid, tp in sorted(trans_probs.items(), key=lambda x: -x[1]):
        label = "Persistence" if tid == current_regime else ""
        transitions_list.append({"to": tid, "p": round(tp, 4), "label": label})

    transition_meta = {
        "inertia": 0.4,
        "cpiDrift": transitions_data.get("cpiDrift", 0),
        "riskOffMom": transitions_data.get("riskoffMomentum", 0),
    }

    # Risk contribution
    riskoff_drivers = macro_data.get("riskoffDrivers", {})

    # Normalize contribution to macro/core/signals
    macro_risk_contrib = _clamp(computed.get("riskOffProb", 0.5) * 0.5, 0, 1)
    core_risk_contrib = _clamp(core_data.get("risk", {}).get("totalIndex", 50) / 100 * 0.33, 0, 1)
    signals_risk_contrib = _clamp(abs(signals_data.get("execution", {}).get("score", 0)) * 0.25, 0, 1)
    risk_total = macro_risk_contrib + core_risk_contrib + signals_risk_contrib
    if risk_total > 0:
        macro_risk_contrib /= risk_total
        core_risk_contrib /= risk_total
        signals_risk_contrib /= risk_total
    else:
        macro_risk_contrib, core_risk_contrib, signals_risk_contrib = 0.42, 0.33, 0.25

    # Risk drivers
    drivers = []
    for k, v in sorted(riskoff_drivers.items(), key=lambda x: -abs(x[1])):
        label_map = {"stable_dom": "Stable dominance shift", "fear_greed": "Fear & Greed", "volatility": "Market volatility", "btc_drawdown": "BTC drawdown pressure"}
        drivers.append({
            "key": k.upper(),
            "label": label_map.get(k, k.replace("_", " ").title()),
            "value": round(abs(v), 3),
            "sign": "+" if v >= 0 else "-",
            "conf": round(min(abs(v) * 2.5, 1), 2),
        })

    # Explainability
    reasons = decision_data.get("reasons", [])
    bullets = []
    for r in reasons:
        if r["layer"] == "macro":
            bullets.append(f"Macro: {r['text']} (impact {r['impact']:+.2f})")
        elif r["layer"] == "core":
            bullets.append(f"Core: {r['text']} (impact {r['impact']:+.2f})")
        elif r["layer"] == "signals":
            bullets.append(f"Signals: {r['text']} (impact {r['impact']:+.2f})")

    action = decision_data.get("action", "NO_TRADE")
    mode = decision_data.get("mode", "DEFENSIVE")
    narrative = f"System is {mode.lower()}: "
    if action == "NO_TRADE":
        if "MACRO_BLOCKED" in decision_data.get("gates", []):
            narrative += "macro gates dominate despite stable core regime."
        else:
            narrative += "insufficient edge to act."
    elif action in ("BUY", "SELL"):
        narrative += "directional signal confirmed by execution layer."
    else:
        narrative += "edge detected but not strong enough for directional action."

    return {
        "state": {
            "regimeProbs": state_probs,
            "transitions": transitions_list[:4],
            "transitionMeta": transition_meta,
        },
        "risk": {
            "split": {
                "macro": round(macro_risk_contrib, 3),
                "core": round(core_risk_contrib, 3),
                "signals": round(signals_risk_contrib, 3),
            },
            "drivers": drivers[:6],
        },
        "explain": {
            "bullets": bullets[:3],
            "narrative": narrative,
        },
    }


# ═══════════════════════════════════════════════
# MAIN OVERVIEW AGGREGATOR
# ═══════════════════════════════════════════════

def compute_overview(core_data, macro_data, signals_data, position_data, hybrid_raw, asset="BTCUSDT"):
    # Check freeze
    if _config.get("frozen") and _frozen_snapshot:
        return _frozen_snapshot

    macro_ctx = extract_macro_context(macro_data)
    hybrid = compute_hybrid(hybrid_raw, macro_ctx["riskOffProb"])
    alt_outlook = compute_alt_outlook(macro_data)
    decision = compute_decision(core_data, macro_data, signals_data, hybrid, alt_outlook, asset)

    # Sparkline history (last 48 for inline chart)
    full_history = list(_position_history.get(asset, []))
    sparkline = full_history[-48:]

    result = {
        "ok": True,
        "asset": asset,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "core": extract_core_snapshot(core_data, asset),
        "signals": extract_signals_summary(signals_data),
        "macro": macro_ctx,
        "risk": extract_risk_split(macro_data),
        "hybrid": hybrid,
        "altOutlook": alt_outlook,
        "alerts": extract_alerts(signals_data, macro_data),
        "positionHistory": sparkline,
    }

    # Cache for freeze
    set_frozen_snapshot(result)

    return result



# ═══════════════════════════════════════════════
# ALT ROTATION ENGINE
# ═══════════════════════════════════════════════

# Altcoin universe with sectors
ALT_UNIVERSE = [
    {"symbol": "ETH",   "name": "Ethereum",  "sector": "L1"},
    {"symbol": "SOL",   "name": "Solana",    "sector": "L1"},
    {"symbol": "BNB",   "name": "BNB",       "sector": "L1"},
    {"symbol": "ADA",   "name": "Cardano",   "sector": "L1"},
    {"symbol": "AVAX",  "name": "Avalanche", "sector": "L1"},
    {"symbol": "DOT",   "name": "Polkadot",  "sector": "L1"},
    {"symbol": "NEAR",  "name": "NEAR",      "sector": "L1"},
    {"symbol": "SUI",   "name": "Sui",       "sector": "L1"},
    {"symbol": "LINK",  "name": "Chainlink", "sector": "INFRA"},
    {"symbol": "UNI",   "name": "Uniswap",   "sector": "DeFi"},
    {"symbol": "AAVE",  "name": "Aave",      "sector": "DeFi"},
    {"symbol": "MKR",   "name": "Maker",     "sector": "DeFi"},
    {"symbol": "FET",   "name": "Fetch.ai",  "sector": "AI"},
    {"symbol": "RNDR",  "name": "Render",    "sector": "AI"},
    {"symbol": "TAO",   "name": "Bittensor", "sector": "AI"},
    {"symbol": "INJ",   "name": "Injective", "sector": "DeFi"},
    {"symbol": "ARB",   "name": "Arbitrum",  "sector": "L2"},
    {"symbol": "OP",    "name": "Optimism",  "sector": "L2"},
    {"symbol": "MATIC", "name": "Polygon",   "sector": "L2"},
    {"symbol": "DOGE",  "name": "Dogecoin",  "sector": "MEME"},
]


def compute_alt_rotation(macro_data, signals_data):
    """
    Rank altcoins by composite score: momentum + volume + flow.
    Returns ranked list with BUY/SELL/HOLD and aggregate stats.
    """
    import hashlib
    import time

    computed = macro_data.get("computed", {})
    risk_off = computed.get("riskOffProb", 0.5)
    macro_mult = _clamp(computed.get("macroMult", 0.7), 0.4, 1.05)
    exec_score = signals_data.get("execution", {}).get("score", 0)

    # Seed for deterministic but time-varying values
    ts_seed = int(time.time()) // 300  # changes every 5 min

    alts = []
    for alt in ALT_UNIVERSE:
        sym = alt["symbol"]
        # Generate stable pseudo-random values per alt using hash
        h = hashlib.md5(f"{sym}:{ts_seed}".encode()).hexdigest()
        h2 = hashlib.md5(f"{sym}:flow:{ts_seed}".encode()).hexdigest()

        # Momentum: based on macro conditions + alt-specific variation
        base_momentum = _clamp(macro_mult - 0.5, -0.5, 0.5)
        alt_var = (int(h[:4], 16) / 65535 - 0.5) * 0.6
        momentum = _clamp(base_momentum + alt_var, -1, 1)

        # Volume: based on exec score + variation
        base_volume = _clamp(abs(exec_score) * 1.5, 0, 1)
        vol_var = (int(h[4:8], 16) / 65535) * 0.5
        volume = _clamp(base_volume + vol_var, 0, 1)

        # Flow: capital flow indicator
        flow_base = _clamp(-risk_off + 0.5, -1, 1)
        flow_var = (int(h2[:4], 16) / 65535 - 0.5) * 0.4
        flow = _clamp(flow_base + flow_var, -1, 1)

        # Composite score: weighted average
        score = _clamp(0.45 * momentum + 0.30 * volume + 0.25 * flow, -1, 1)

        # Action based on score
        if score > 0.25:
            action = "BUY"
        elif score < -0.15:
            action = "SELL"
        else:
            action = "HOLD"

        alts.append({
            "symbol": sym,
            "name": alt["name"],
            "sector": alt["sector"],
            "momentum": round(momentum, 4),
            "volume": round(volume, 4),
            "flow": round(flow, 4),
            "score": round(score, 4),
            "action": action,
        })

    # Sort by score descending
    alts.sort(key=lambda x: -x["score"])

    # Assign rank
    for i, a in enumerate(alts):
        a["rank"] = i + 1

    # Aggregate: Rotation Index = mean score of top 5
    top5 = alts[:5]
    rotation_index = sum(a["score"] for a in top5) / len(top5) if top5 else 0

    # Sector Strength = avg score by sector
    sector_scores = {}
    for a in alts:
        sector_scores.setdefault(a["sector"], []).append(a["score"])
    sector_strength = {
        s: round(sum(scores) / len(scores), 4)
        for s, scores in sorted(sector_scores.items(), key=lambda x: -sum(x[1]) / len(x[1]))
    }

    return {
        "ok": True,
        "alts": alts,
        "rotationIndex": round(rotation_index, 4),
        "sectorStrength": sector_strength,
        "meta": {
            "count": len(alts),
            "buyCount": sum(1 for a in alts if a["action"] == "BUY"),
            "sellCount": sum(1 for a in alts if a["action"] == "SELL"),
            "holdCount": sum(1 for a in alts if a["action"] == "HOLD"),
        },
    }
