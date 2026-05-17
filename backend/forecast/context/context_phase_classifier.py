"""
Context Phase Classifier
==========================
Classifies market phase from context features.
7 distinct phases, evaluated in priority order.
"""


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def classify_phase(ctx: dict) -> dict:
    """
    Classify market phase from context features.
    Returns phase, confidence, and diagnostic flags.
    Priority order matters — first match wins.

    Thresholds calibrated against real BTC feature distribution:
      trend_strength  range ~[0, 0.52]
      trend_persist.  range ~[0.74, 0.94]
      trend_exhaust.  range ~[0, 0.50]
      reversal_risk   range ~[0.05, 0.24]
      drawdown_press. range ~[0, 0.60]
    """
    ts = ctx["trend_strength"]
    tp = ctx["trend_persistence"]
    te = ctx["trend_exhaustion"]
    rr = ctx["reversal_risk"]
    dp = ctx["drawdown_pressure"]

    flags = []

    # Phase 1: Strong continuation — strong trend, high persistence, low reversal
    if ts > 0.45 and tp > 0.80 and rr < 0.10:
        phase = "continuation"
        flags.append("strong_trend")
        flags.append("low_reversal")

    # Phase 2: Late trend — moderate+ trend with growing exhaustion
    elif ts > 0.35 and te > 0.20:
        phase = "late_trend"
        flags.append("exhaustion_rising")

    # Phase 3: Pullback within trend — moderate+ trend, very low reversal
    elif ts > 0.35 and rr < 0.10:
        phase = "pullback"
        flags.append("trend_intact")

    # Phase 4: Breakdown — high drawdown pressure
    elif dp > 0.40:
        phase = "breakdown"
        flags.append("high_drawdown")

    # Phase 5: Recovery attempt — moderate drawdown + weak trend
    elif dp > 0.18 and ts < 0.38:
        phase = "recovery_attempt"
        flags.append("weak_recovery")

    # Phase 6: Unstable transition — elevated reversal risk
    elif rr > 0.14:
        phase = "unstable_transition"
        flags.append("elevated_reversal_risk")

    # Phase 7: Default — mixed range (no clear signal)
    else:
        phase = "mixed_range"
        flags.append("no_clear_phase")

    # Confidence: higher when trend/persistence strong, reversal low
    context_confidence = _clamp(
        0.5 * ts + 0.3 * tp + 0.2 * (1.0 - rr)
    )

    return {
        "market_phase": phase,
        "context_confidence": round(context_confidence, 4),
        "flags": flags,
    }
