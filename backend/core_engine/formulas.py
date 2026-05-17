"""
Core Engine V2 — Pure Formulas.
All computations are stateless functions.
"""

import math
from .config import (
    REGIME_TEMPERATURE, RISK_WEIGHTS, RISK_LOW, RISK_HIGH,
    SHIFT_FORMULA, TRIGGER_WEIGHTS, TRANSITION_MATRIX,
    EXECUTION_CONFIG, INTEGRITY_CONFIG, MACRO_CONFIG,
    BIAS_STRONG, BIAS_SLIGHT, CONFIDENCE_HIGH, CONFIDENCE_MODERATE,
    GATE_DQ_MIN, GATE_LIQUIDITY_MAX, GATE_MANIPULATION_MAX,
    TF_PROFILES, DEFAULT_TIMEFRAME,
)


def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


# ═══════════════════════════════════════════════
# 1. INTEGRITY PENALTY
# ═══════════════════════════════════════════════

def compute_integrity_penalty(f: dict, divergence: dict) -> dict:
    """Compute unified integrity penalty multiplier."""
    integrity = f.get("integrity", {})
    freshness_sec = integrity.get("freshnessSec", 9999)
    coverage_pct = integrity.get("coveragePct", 0)
    status = integrity.get("status", "CRITICAL").lower()

    # Freshness factor
    freshness_factor = INTEGRITY_CONFIG["freshness_fallback"]
    for threshold, factor in INTEGRITY_CONFIG["freshness_thresholds"]:
        if freshness_sec <= threshold:
            freshness_factor = factor
            break

    # Coverage factor
    coverage_factor = clamp(coverage_pct / 100, 0.3, 1.0)

    # Data quality factor
    dq_map = INTEGRITY_CONFIG["data_quality_map"]
    if status in ("healthy", "ok"):
        data_quality_factor = dq_map["healthy"]
    elif status == "partial":
        data_quality_factor = dq_map["partial"]
    elif status == "degraded":
        data_quality_factor = dq_map["degraded"]
    else:
        data_quality_factor = dq_map["critical"]

    # Venue consistency factor
    div_score = divergence.get("score", 0)
    if div_score > 0.85:
        venue_factor = INTEGRITY_CONFIG["venue_consistency_map"]["extreme"]
    elif div_score > 0.25:
        venue_factor = INTEGRITY_CONFIG["venue_consistency_map"]["conflict"]
    else:
        venue_factor = INTEGRITY_CONFIG["venue_consistency_map"]["ok"]

    penalty = freshness_factor * coverage_factor * data_quality_factor * venue_factor
    penalty = clamp(penalty, 0.2, 1.0)

    warnings = []
    if freshness_sec > 180:
        warnings.append("STALE_DATA")
    if coverage_pct < 70:
        warnings.append("LOW_COVERAGE")
    if status not in ("healthy", "ok"):
        warnings.append("DATA_QUALITY_DEGRADED")
    if div_score > 0.25:
        warnings.append("VENUE_CONFLICT")

    return {
        "penalty": round(penalty, 4),
        "freshnessFactor": round(freshness_factor, 2),
        "coverageFactor": round(coverage_factor, 2),
        "dataQualityFactor": round(data_quality_factor, 2),
        "venueConsistencyFactor": round(venue_factor, 2),
        "warnings": warnings,
        "freshnessSec": freshness_sec,
        "coveragePct": coverage_pct,
        "status": status,
    }


# ═══════════════════════════════════════════════
# 2. MACRO CONFIDENCE MULTIPLIER (V2 — passthrough)
# ═══════════════════════════════════════════════

def compute_macro_multiplier(macro: dict) -> dict:
    """Pass through pre-computed macro context from Macro V2 engine.
    
    Core does NOT compute macro — Macro V2 is the single source of truth.
    If macro.available == false → multiplier = 1.0, no blocks.
    """
    if not macro.get("available", False):
        return {
            "multiplier": 1.0,
            "fearGreed": 50,
            "fearGreedLabel": "NEUTRAL",
            "regime": "NEUTRAL",
            "regimeLabel": "Neutral",
            "riskOffProb": 0.5,
            "strongActionsBlocked": False,
            "altExposureReduced": False,
            "available": False,
        }

    return {
        "multiplier": round(macro["multiplier"], 4),
        "fearGreed": macro.get("fearGreed", 50),
        "fearGreedLabel": macro.get("fearGreedLabel", "NEUTRAL"),
        "regime": macro.get("regime", "NEUTRAL"),
        "regimeLabel": macro.get("regimeLabel", "Neutral"),
        "riskOffProb": macro.get("riskOffProb", 0.5),
        "strongActionsBlocked": macro.get("strongActionsBlocked", False),
        "altExposureReduced": macro.get("altExposureReduced", False),
        "available": True,
    }


# ═══════════════════════════════════════════════
# 3. REGIME PROBABILITIES (Softmax)
# ═══════════════════════════════════════════════

def _softmax(scores: dict, temperature: float) -> dict:
    """Softmax with temperature parameter."""
    scaled = {k: v / temperature for k, v in scores.items()}
    max_s = max(scaled.values())
    exps = {k: math.exp(v - max_s) for k, v in scaled.items()}
    total = sum(exps.values())
    if total == 0:
        n = len(exps)
        return {k: round(1.0 / n, 4) for k in exps}
    return {k: round(v / total, 4) for k, v in exps.items()}


def compute_regime_probabilities(f: dict, integrity_penalty: float, tf_profile: dict = None) -> dict:
    """Compute regime probabilities using softmax with TF-dependent temperature."""
    # Use TF-specific temperature (lower = more decisive)
    temperature = (tf_profile or {}).get("temperature", REGIME_TEMPERATURE)

    # Range score: compression high, momentum/flow low
    score_range = (
        0.30 * f["compression"] +
        0.25 * clamp(1 - f["momentum_abn"]) +
        0.25 * clamp(1 - f["flow_abn"]) +
        0.20 * clamp(1 - f["participation_abn"])
    )

    # Trend score: strong momentum, flow, participation
    score_trend = (
        0.35 * f["momentum_abn"] +
        0.30 * f["flow_abn"] +
        0.20 * f["participation_abn"] +
        0.15 * clamp(1 - f["conflict_abn"])
    )

    # Breakout score: compression + thin liquidity + divergence potential
    score_breakout = (
        0.25 * f["compression"] +
        0.20 * f["liquidity_abn"] +
        0.20 * f["volatility_abn"] +
        0.20 * f["momentum_abn"] +
        0.15 * clamp(1 - f["manipulation_abn"])
    )

    # Distribution score: manipulation + selling + stress
    score_distribution = (
        0.30 * f["manipulation_abn"] +
        0.25 * f["stress_abn"] +
        0.25 * f["liquidation_risk"] +
        0.20 * f["conflict_abn"]
    )

    raw_scores = {
        "breakout": score_breakout,
        "range": score_range,
        "distribution": score_distribution,
        "trend": score_trend,
    }

    probs = _softmax(raw_scores, temperature)

    # Apply integrity penalty: reduce confidence spread
    # Lower penalty → probs closer to uniform
    if integrity_penalty < 0.8:
        uniform = 1.0 / len(probs)
        blend = integrity_penalty
        probs = {k: round(blend * v + (1 - blend) * uniform, 4) for k, v in probs.items()}
        # Renormalize
        total = sum(probs.values())
        if total > 0:
            probs = {k: round(v / total, 4) for k, v in probs.items()}

    dominant = max(probs, key=probs.get)
    confidence = probs[dominant]

    # Confidence level
    if confidence >= CONFIDENCE_HIGH:
        conf_level = "high"
    elif confidence >= CONFIDENCE_MODERATE:
        conf_level = "moderate"
    else:
        conf_level = "low"

    # Dominance gap (pmax - p2)
    sorted_p = sorted(probs.values(), reverse=True)
    dominance_gap = round(sorted_p[0] - sorted_p[1], 4) if len(sorted_p) > 1 else 0

    # Entropy (for display)
    entropy = 0
    for p in probs.values():
        if p > 0:
            entropy -= p * math.log(p)
    max_entropy = math.log(max(len(probs), 1))
    entropy_norm = entropy / max_entropy if max_entropy > 0 else 0

    return {
        "dominant": dominant,
        "confidence": round(confidence, 4),
        "confidenceLevel": conf_level,
        "dominanceGap": dominance_gap,
        "entropy": round(entropy_norm, 4),
        "probabilities": probs,
        "rawScores": {k: round(v, 4) for k, v in raw_scores.items()},
    }


# ═══════════════════════════════════════════════
# 4. RISK SURFACE
# ═══════════════════════════════════════════════

def compute_risk_surface(f: dict, macro_mult: float, tf_profile: dict = None) -> dict:
    """Compute total risk and axis breakdown. TF damping applied."""
    risk_damping = (tf_profile or {}).get("risk_damping", 1.0)

    liq = clamp(f["liquidity_risk"]) * 100
    stress = clamp(f["stress_risk"]) * 100
    manip = clamp(f["manipulation_risk"]) * 100
    struct = clamp(f["regime_risk"]) * 100
    conflict = clamp(f["conflict_risk"]) * 100

    w = RISK_WEIGHTS
    overall = (
        w["liquidity"] * liq +
        w["stress"] * stress +
        w["manipulation"] * manip +
        w["structure"] * struct +
        w["conflict"] * conflict
    )

    # TF damping: higher TF → smoother risk perception
    overall *= risk_damping

    # Macro penalty: lower confidence → higher risk
    if macro_mult < 1.0:
        overall *= (1.0 / max(macro_mult, 0.3))
    overall = clamp(overall, 0, 100)
    idx = round(overall)

    if idx < RISK_LOW:
        level = "low"
    elif idx > RISK_HIGH:
        level = "high"
    else:
        level = "moderate"

    return {
        "totalIndex": idx,
        "level": level,
        "breakdown": {
            "liquidity": round(liq),
            "stress": round(stress),
            "manipulation": round(manip),
            "structure": round(struct),
            "conflict": round(conflict),
        },
    }


# ═══════════════════════════════════════════════
# 5. FACTOR DECOMPOSITION
# ═══════════════════════════════════════════════

def compute_factors(f: dict) -> dict:
    """Compute 5 meta-factors (quality/strength, not danger)."""
    structure = clamp(
        0.30 * f["regime_abn"] +
        0.25 * f["compression"] +
        0.25 * f["momentum_abn"] +
        0.20 * f["participation_abn"]
    )

    flow = clamp(
        0.35 * f["flow_abn"] +
        0.35 * clamp(abs(f["flow_conv"]) * 4) +
        0.30 * f["volume_abn"]
    )

    liquidity = clamp(
        0.50 * (1 - f["liquidity_risk"]) +
        0.30 * (1 - f["liquidity_abn"]) +
        0.20 * (1 - f["stress_risk"])
    )

    smart_money = clamp(
        0.45 * f["whale_abn"] +
        0.30 * clamp(abs(f["whale_conv"]) * 4) +
        0.25 * (1 - f["liquidation_risk"])
    )

    stability = clamp(
        0.35 * (1 - f["stress_abn"]) +
        0.35 * (1 - f["conflict_abn"]) +
        0.30 * f["data_quality_conf"]
    )

    return {
        "structure": round(structure * 100),
        "flow": round(flow * 100),
        "liquidity": round(liquidity * 100),
        "smartMoney": round(smart_money * 100),
        "stability": round(stability * 100),
    }


# ═══════════════════════════════════════════════
# 6. PRESSURE & BIAS
# ═══════════════════════════════════════════════

def compute_pressure(f: dict, factors: dict, tf_profile: dict = None) -> dict:
    """Compute directional pressure and net bias via sigmoid.
    TF bias_damping: higher TF = stronger signal (less noise).
    """
    bias_damping = (tf_profile or {}).get("bias_damping", 1.0)

    dir_momentum = f["momentum_conv"] * 4
    dir_flow = f["flow_conv"] * 4
    dir_whale = f["whale_conv"] * 4
    dir_liquidation = -f["liquidation_risk"]
    dir_stress = -f["stress_abn"] * 0.5

    bias_score = clamp(
        0.30 * dir_flow +
        0.25 * dir_momentum +
        0.20 * dir_whale +
        0.15 * dir_liquidation +
        0.10 * dir_stress,
        -1, 1
    )

    # Apply bias_damping: >1 amplifies signal (higher TF), <1 dampens (lower TF)
    bias_score_scaled = clamp(bias_score * bias_damping, -1, 1)

    sig = 1 / (1 + math.exp(-bias_score_scaled * 4))
    up = round(sig * 100)
    down = 100 - up
    net = up - down

    strength = clamp(abs(bias_score_scaled))

    if net > 15:
        label = "bullish"
    elif net > 5:
        label = "slight_bullish"
    elif net < -15:
        label = "bearish"
    elif net < -5:
        label = "slight_bearish"
    else:
        label = "neutral"

    return {
        "upward": up,
        "downward": down,
        "netBias": net,
        "biasLabel": label,
        "biasStrength": round(strength, 4),
        "biasScore": round(bias_score_scaled, 4),
    }


# ═══════════════════════════════════════════════
# 7. TRANSITION ENGINE
# ═══════════════════════════════════════════════

def compute_transition(f: dict, regime: dict, risk: dict, divergence: dict, tf_profile: dict = None) -> dict:
    """Compute shift probability, instability, and top transitions.
    
    Key fix: instability = normalized entropy (H/Hmax).
    shift = 0.45*instability + 0.35*risk/100 + 0.20*transitionTrigger
    TF scaling: shift_scale amplifies/dampens shift, noise_floor adds minimum instability.
    """
    shift_scale = (tf_profile or {}).get("shift_scale", 1.0)
    noise_floor = (tf_profile or {}).get("noise_floor", 0.0)

    probs = regime.get("probabilities", {})
    dominant = regime.get("dominant", "range")
    div_norm = clamp(divergence.get("score", 0))
    risk_norm = risk["totalIndex"] / 100

    # Instability = normalized entropy (section 1.8)
    entropy = 0
    for p in probs.values():
        if p > 0:
            entropy -= p * math.log(p)
    max_entropy = math.log(max(len(probs), 1))
    entropy_norm = entropy / max_entropy if max_entropy > 0 else 0
    # Apply noise_floor: lower TFs have inherently higher minimum instability
    instability = max(entropy_norm, noise_floor)

    # Transition trigger (section 1.9)
    # Breakout signals + vol expansion
    tw = TRIGGER_WEIGHTS
    transition_trigger = clamp(
        tw["vol_expansion"] * f["volatility_abn"] +
        tw["compression"] * f["compression"] +
        tw["divergence"] * div_norm +
        tw["liquidity_thin"] * f["liquidity_abn"]
    )

    # Shift probability (section 1.9)
    # shift = 0.45*instability + 0.35*risk + 0.20*trigger
    # Then scaled by TF: lower TF = more volatile (shift_scale > 1)
    sw = SHIFT_FORMULA
    shift_prob = clamp(
        (sw["instability_weight"] * instability +
         sw["risk_weight"] * risk_norm +
         sw["trigger_weight"] * transition_trigger) * shift_scale
    )

    # Competitiveness (how close are top 2 regimes — kept for display)
    sorted_probs = sorted(probs.values(), reverse=True)
    p_max = sorted_probs[0] if sorted_probs else 0.25
    p_second = sorted_probs[1] if len(sorted_probs) > 1 else 0.25
    competitiveness = clamp(p_second / (p_max + 0.001))

    # Top transitions from dominant regime
    transitions = []
    for key, weights in TRANSITION_MATRIX.items():
        if not key.startswith(dominant + "_to_"):
            continue
        target = key.split("_to_")[1]

        score = 0
        for feature_key, w in weights.items():
            if feature_key == "compression":
                score += w * f["compression"]
            elif feature_key == "liquidity_thin":
                score += w * f["liquidity_abn"]
            elif feature_key == "divergence":
                score += w * div_norm
            elif feature_key == "participation":
                score += w * f["participation_abn"]
            elif feature_key == "momentum_strong":
                score += w * f["momentum_abn"]
            elif feature_key == "flow_strong":
                score += w * f["flow_abn"]
            elif feature_key == "manipulation":
                score += w * f["manipulation_abn"]
            elif feature_key == "stress":
                score += w * f["stress_abn"]
            elif feature_key == "conflict":
                score += w * f["conflict_abn"]
            elif feature_key == "liquidation":
                score += w * f["liquidation_risk"]
            elif feature_key == "sellers":
                score += w * clamp(max(0, -f["flow_conv"]) * 4)
            elif feature_key == "momentum_fade":
                score += w * clamp(1 - f["momentum_abn"])
            elif feature_key == "volume_drop":
                score += w * clamp(1 - f["volume_abn"])
            elif feature_key == "flow_fade":
                score += w * clamp(1 - f["flow_abn"])
            elif feature_key in ("stress_low", "conflict_low", "manipulation_low"):
                base = feature_key.replace("_low", "")
                score += w * clamp(1 - f.get(f"{base}_abn", 0))

        prob = clamp(score * shift_prob * 2)
        transitions.append({
            "from": dominant,
            "to": target,
            "probability": round(prob, 4),
            "key": key,
        })

    transitions.sort(key=lambda x: x["probability"], reverse=True)

    return {
        "shiftProbability": round(shift_prob, 4),
        "instability": round(instability, 4),
        "competitiveness": round(competitiveness, 4),
        "entropy": round(entropy_norm, 4),
        "transitionTrigger": round(transition_trigger, 4),
        "transitions": transitions,
    }


# ═══════════════════════════════════════════════
# 8. EXECUTION CONTROLS
# ═══════════════════════════════════════════════

def compute_execution(risk: dict, factors: dict, integrity: dict, macro: dict, shift_prob: float) -> dict:
    """Compute execution modifiers with specific gate reasons."""
    risk_norm = risk["totalIndex"] / 100
    penalty = integrity["penalty"]
    macro_mult = macro["multiplier"]
    q = penalty

    aggression = clamp(1 - 0.7 * risk_norm - 0.4 * shift_prob)
    aggression *= macro_mult

    leverage = clamp(1 - 0.9 * risk_norm - 0.6 * (1 - q))

    signal_amp = clamp(q * (1 - 0.6 * risk_norm) * (1 - 0.4 * shift_prob))
    signal_amp *= macro_mult

    # Gate checks with specific reasons
    blocked_gates = []
    liq_risk = risk.get("breakdown", {}).get("liquidity", 0)
    manip_risk = risk.get("breakdown", {}).get("manipulation", 0)

    if macro.get("strongActionsBlocked"):
        regime_label = macro.get("regimeLabel", "Unknown")
        riskoff_pct = round(macro.get("riskOffProb", 0) * 100)
        blocked_gates.append({"gate": "macro", "reason": f"Macro: {regime_label} (Risk-Off {riskoff_pct}%)"})
    if q < GATE_DQ_MIN:
        blocked_gates.append({"gate": "data_quality", "reason": f"Data quality too low ({q:.0%})"})
    if liq_risk > GATE_LIQUIDITY_MAX:
        blocked_gates.append({"gate": "liquidity", "reason": f"Liquidity risk {liq_risk}/100"})
    if manip_risk > GATE_MANIPULATION_MAX:
        blocked_gates.append({"gate": "manipulation", "reason": f"Manipulation risk {manip_risk}/100"})
    if risk["totalIndex"] > 70:
        blocked_gates.append({"gate": "risk", "reason": f"Total risk {risk['totalIndex']}/100"})

    strong_actions_blocked = len(blocked_gates) > 0

    if integrity.get("status") in ("degraded", "critical"):
        signal_amp = min(signal_amp, 0.4)
    if strong_actions_blocked:
        aggression = min(aggression, 0.3)

    # Decision rules
    allowed = []
    blocked = []

    if risk_norm < 0.5 and shift_prob < 0.4:
        allowed.append("Directional trades")
    if risk_norm < 0.35:
        allowed.append("Moderate leverage")
    if signal_amp > 0.5:
        allowed.append("Signal-based entries")
    if aggression > 0.5:
        allowed.append("Aggressive positioning")

    if risk_norm > 0.6:
        blocked.append("High leverage")
    if shift_prob > 0.5:
        blocked.append("Counter-trend entries")
    if signal_amp < 0.3:
        blocked.append("Low-confidence signals")
    if q < 0.6:
        blocked.append("Size scaling (data quality)")

    # Add gate reasons to blocked
    for g in blocked_gates:
        blocked.append(g["reason"])

    if not allowed:
        allowed.append("Defensive positioning only")

    return {
        "aggressionMultiplier": round(clamp(aggression), 4),
        "leverageMultiplier": round(clamp(leverage), 4),
        "signalAmplification": round(clamp(signal_amp), 4),
        "strongActionsBlocked": strong_actions_blocked,
        "integrityGated": penalty < 0.6,
        "blockedGates": blocked_gates,
        "decision": {
            "allowed": allowed,
            "blocked": blocked,
        },
    }
