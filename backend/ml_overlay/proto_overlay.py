"""
Proto Overlay (Rule-Based)
=============================
Block 5.A.6

Temporary rule-based risk overlay to close the risk gap while ML data accumulates.
Uses already-proven weak zones from monitoring (Block 4) and tactical (Block X) analysis.

NOT ML — purely deterministic rules based on known patterns:
  - unstable_transition phase: 8% accuracy → high risk
  - high entropy: confused regime → elevated risk
  - wide scenario spread: high uncertainty → elevated risk
  - tactical bearish + high uncertainty: dangerous combination
"""


def compute_proto_overlay_risk(ctx: dict) -> dict:
    """
    Compute rule-based risk score from context.

    Args:
        ctx: Dictionary with available context fields:
            - phase: str (context phase)
            - entropy: float (regime entropy)
            - uncertainty: float (0..1)
            - scenario_spread: float (% spread between scenarios)
            - tactical_bias: str ("bullish"/"neutral"/"bearish")
            - tactical_quality: str ("high"/"medium"/"low")
            - regime_flags: list[str] (regime adjustment flags)

    Returns:
        {
            "risk_score": float (0..1),
            "size_mult": float (0.5..1.0),
            "confidence_mult": float (0.7..1.0),
            "flags": list[str],
            "action": str
        }
    """
    risk = 0.0
    flags = []

    # ── Rule 1: Phase Risk (from Block 4 monitoring: 8% accuracy) ──
    regime_flags = ctx.get("regime_flags") or []
    if "transition_caution" in regime_flags or "transition_hard_dampen" in regime_flags:
        risk += 0.4
        flags.append("unstable_transition")

    # ── Rule 2: High Entropy ──
    entropy = ctx.get("entropy", 0.5)
    if entropy > 0.7:
        risk += 0.3
        flags.append("high_entropy")
    elif entropy > 0.5:
        risk += 0.1

    # ── Rule 3: Wide Scenario Spread ──
    spread = ctx.get("scenario_spread", 0.0)
    if spread > 20:
        risk += 0.2
        flags.append("wide_scenario_spread")
    elif spread > 15:
        risk += 0.1

    # ── Rule 4: Tactical Warning ──
    tactical_bias = ctx.get("tactical_bias", "neutral")
    uncertainty = ctx.get("uncertainty", 0.5)

    if tactical_bias == "bearish" and uncertainty > 0.5:
        risk += 0.3
        flags.append("tactical_bearish_high_uncertainty")
    elif tactical_bias == "bearish":
        risk += 0.15
        flags.append("tactical_bearish")

    # ── Rule 5: High Uncertainty alone ──
    if uncertainty > 0.7:
        risk += 0.15
        flags.append("high_uncertainty")

    # Cap at 1.0
    risk = min(risk, 1.0)

    # ── Compute multipliers ──
    if risk > 0.6:
        size_mult = 0.7
        confidence_mult = 0.8
        action = "strong_penalty"
    elif risk > 0.3:
        size_mult = 0.85
        confidence_mult = 0.9
        action = "soft_penalty"
    elif risk > 0.1:
        size_mult = 0.95
        confidence_mult = 0.95
        action = "flag_only"
    else:
        size_mult = 1.0
        confidence_mult = 1.0
        action = "none"

    return {
        "risk_score": round(risk, 3),
        "size_mult": round(size_mult, 3),
        "confidence_mult": round(confidence_mult, 3),
        "flags": flags,
        "action": action,
    }
