"""
Drift Execution Hook
======================
FIX 6.2

Converts drift intelligence into execution-level adjustments.
Drift is no longer just an observation — it directly modulates risk.

Three defense levels:
  - drift_score > 0.7 → defensive mode (sizeFactor *= 0.6)
  - drift_score > 0.5 → cautious mode (sizeFactor *= 0.8)
  - catastrophic_rate > 0.25 → additional reduction (* 0.7)

Never blocks execution — only modulates.
"""


def compute_drift_adjustments(drift_score: float, catastrophic_rate: float) -> dict:
    """
    Compute execution adjustments from drift intelligence.

    Args:
        drift_score: 0..1 from drift scoring engine
        catastrophic_rate: 0..1 from drift metrics

    Returns:
        {
            "size_mult": float (0.4..1.0),
            "mode": str (normal/cautious/defensive),
            "flags": list[str],
        }
    """
    size_mult = 1.0
    mode = "normal"
    flags = []

    # Level 1: drift_score based
    if drift_score > 0.7:
        mode = "defensive"
        size_mult *= 0.6
        flags.append("drift_defensive")
    elif drift_score > 0.5:
        mode = "cautious"
        size_mult *= 0.8
        flags.append("drift_cautious")

    # Level 2: catastrophic rate based
    if catastrophic_rate > 0.25:
        size_mult *= 0.7
        flags.append("high_catastrophic_rate")

    # Level 3: combined extreme
    if drift_score > 0.7 and catastrophic_rate > 0.25:
        flags.append("extreme_risk_mode")

    return {
        "size_mult": round(max(size_mult, 0.3), 3),  # floor at 0.3
        "mode": mode,
        "flags": flags,
        "drift_score": round(drift_score, 3),
        "catastrophic_rate": round(catastrophic_rate, 3),
    }
