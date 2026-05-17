"""
Decision Discipline V2 — Shadow Mode
=====================================
Sprint 4 C2: Fixes 5 root causes from C1 audit:
  1. Narrow NEUTRAL zone
  2. Anti-bull trap (regime direction awareness)
  3. Exchange bias integration
  4. Meaningful confidence
  5. Reversal unlock

Operates in SHADOW mode: computes V2 decision in parallel with V1,
logs to audit["decision_v2"], but does NOT modify the actual forecast.
"""

from typing import Dict, Any, Tuple

# ── C2.8: Mode control ──
DECISION_V2_MODE = "shadow"  # "shadow" | "live"

# ── C2.2: New thresholds ──
LONG_THRESHOLD = 0.10
SHORT_THRESHOLD = -0.10

# Dynamic thresholds when exchange signal is strong
LONG_THRESHOLD_DYNAMIC = 0.08
SHORT_THRESHOLD_DYNAMIC = -0.08
EXCHANGE_DYNAMIC_TRIGGER = 0.4  # abs(exchange_bias) > this → use dynamic thresholds


def detect_regime_direction(audit: dict) -> str:
    """
    Determine if the trend is UP or DOWN using regime_v2 features.
    Returns: "TREND_UP", "TREND_DOWN", or "RANGE".
    """
    regime = audit.get("regime", "RANGE")
    rv2 = audit.get("regimeV2", {})

    # Use regime_v2 dominant_regime if available
    rv2_dominant = rv2.get("dominant_regime", "") if isinstance(rv2, dict) else ""
    if rv2_dominant in ("breakdown", "bearish_trend"):
        return "TREND_DOWN"
    if rv2_dominant in ("bullish_trend",):
        return "TREND_UP"

    # Fallback: use score direction + regime
    score_final = audit.get("scoreFinal", 0) or 0

    if regime in ("TREND",):
        # Use score sign to determine trend direction
        if score_final < -0.05:
            return "TREND_DOWN"
        elif score_final > 0.05:
            return "TREND_UP"
        # Use features for tie-breaking
        features = audit.get("features", {})
        if isinstance(features, dict):
            ret_7d = features.get("ret_7d", 0) or 0
            momentum = features.get("momentum", 0) or 0
            if ret_7d < -0.02 or momentum < -0.005:
                return "TREND_DOWN"
            elif ret_7d > 0.02 or momentum > 0.005:
                return "TREND_UP"

    return "RANGE"


def compute_decision_v2(
    base_score: float,
    exchange_signal: dict,
    audit: dict,
    v1_direction: str,
    v1_confidence: float,
) -> Dict[str, Any]:
    """
    Decision V2 — shadow computation.

    Args:
        base_score: scoreFinal from the V1 pipeline
        exchange_signal: dict with micro_bias, funding_bias, etc.
        audit: full forecast audit dict (for regime, features, etc.)
        v1_direction: the V1 direction (LONG/SHORT/NEUTRAL)
        v1_confidence: the V1 confidence (0..1)

    Returns:
        dict with V2 decision + audit trail.
    """
    micro_bias = exchange_signal.get("micro_bias", 0.0) if exchange_signal else 0.0

    # ── C2.1: New direction score ──
    regime_dir = detect_regime_direction(audit)
    if regime_dir == "TREND_DOWN":
        regime_bias = -0.3
    elif regime_dir == "TREND_UP":
        regime_bias = 0.3
    else:
        regime_bias = 0.0

    direction_score = (
        base_score
        + micro_bias * 0.3
        + regime_bias * 0.2
    )

    # ── C2.3: Anti-bull trap ──
    anti_trap_applied = False
    if regime_dir == "TREND_DOWN" and direction_score > 0:
        direction_score -= 0.15
        anti_trap_applied = True
    elif regime_dir == "TREND_UP" and direction_score < 0:
        direction_score += 0.15
        anti_trap_applied = True

    # ── C2.4: Reversal unlock ──
    reversal_signal = False
    # Detect previous trend from features
    features = audit.get("features", {})
    ret_7d = features.get("ret_7d", 0) or 0 if isinstance(features, dict) else 0
    previous_trend = "UP" if ret_7d > 0.02 else ("DOWN" if ret_7d < -0.02 else "FLAT")

    if micro_bias < -0.5 and previous_trend == "UP":
        reversal_signal = True
        direction_score -= 0.2
    elif micro_bias > 0.5 and previous_trend == "DOWN":
        reversal_signal = True
        direction_score += 0.2

    # ── C2.2: Thresholds (static or dynamic) ──
    if abs(micro_bias) > EXCHANGE_DYNAMIC_TRIGGER:
        long_th = LONG_THRESHOLD_DYNAMIC
        short_th = SHORT_THRESHOLD_DYNAMIC
    else:
        long_th = LONG_THRESHOLD
        short_th = SHORT_THRESHOLD

    # ── C2.6: Final direction ──
    if direction_score >= long_th:
        direction = "LONG"
    elif direction_score <= short_th:
        direction = "SHORT"
    else:
        direction = "NEUTRAL"

    # ── C2.5: Meaningful confidence ──
    # Scenario confidence from audit
    scenario_conf = 0.5
    dl = audit.get("decisionLayer", {})
    if isinstance(dl, dict):
        scenario_conf = dl.get("confidence", 0.5) or 0.5

    confidence = (
        0.4 * min(abs(direction_score), 1.0)
        + 0.3 * min(abs(micro_bias), 1.0)
        + 0.3 * scenario_conf
    )

    # Conflict penalty
    conflict_score = 0.0
    interaction = audit.get("interaction", {})
    if isinstance(interaction, dict):
        conflict_score = interaction.get("conflict_score", 0.0) or 0.0
    if conflict_score > 0.5:
        confidence *= 0.7

    # Exchange boost
    if abs(micro_bias) > 0.6:
        confidence += 0.05

    # Anti-trap penalty to confidence
    if anti_trap_applied:
        confidence *= 0.7

    confidence = round(max(0.05, min(0.85, confidence)), 4)

    # ── Audit trail ──
    return {
        "mode": DECISION_V2_MODE,
        "direction": direction,
        "confidence": confidence,
        "direction_score": round(direction_score, 6),
        "components": {
            "base_score": round(base_score, 6),
            "exchange_bias_contrib": round(micro_bias * 0.3, 6),
            "regime_bias_contrib": round(regime_bias * 0.2, 6),
        },
        "regime_direction": regime_dir,
        "regime_bias": round(regime_bias, 4),
        "anti_trap_applied": anti_trap_applied,
        "reversal_signal": reversal_signal,
        "previous_trend": previous_trend,
        "thresholds": {"long": long_th, "short": short_th, "dynamic": abs(micro_bias) > EXCHANGE_DYNAMIC_TRIGGER},
        "conflict_score": round(conflict_score, 4),
        "v1_comparison": {
            "v1_direction": v1_direction,
            "v2_direction": direction,
            "direction_changed": v1_direction != direction,
            "v1_confidence": round(v1_confidence, 4),
            "v2_confidence": confidence,
        },
    }
