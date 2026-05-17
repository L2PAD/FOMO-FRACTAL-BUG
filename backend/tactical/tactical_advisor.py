"""
Tactical Advisor
==================
Block X — Task X.4

Converts tactical bias + context into actionable execution advice.
Combines tactical layer with existing intelligence layers:
  - uncertainty (from v4.3)
  - regime/phase
  - volatility

Output: human-readable advice that doesn't conflict with 7D/30D strategy.
"""

from tactical.tactical_types import (
    TacticalFusion, TacticalAdvice, MicrostructureSnapshot,
)


def build_tactical_advice(
    fusion: TacticalFusion,
    snap: MicrostructureSnapshot,
) -> TacticalAdvice:
    """
    Generate tactical execution advice.

    Rules:
      - Advisory only (never hard-blocks)
      - Consistent with P1 execution layer
      - Explain reasoning clearly
    """
    bias = fusion["bias"]
    strength = fusion["signal_strength"]
    score = fusion["score"]
    active = fusion["active_signals"]
    uncertainty = snap.get("uncertainty", 0.5)
    regime = snap.get("regime", "range")

    # ── Volatility expectation ──
    high_vol = any(s in active for s in [
        "high_volatility", "forced_selling", "forced_buying",
    ])
    oi_delta = abs(snap.get("oi_delta_pct", 0))

    if high_vol or oi_delta > 5.0:
        vol_expect = "extreme"
    elif high_vol or oi_delta > 3.0:
        vol_expect = "high"
    elif oi_delta > 1.0:
        vol_expect = "moderate"
    else:
        vol_expect = "low"

    # ── Trade quality ──
    # Based on signal clarity + uncertainty + volatility
    if strength >= 0.35 and uncertainty < 0.4 and vol_expect in ("low", "moderate"):
        quality = "high"
    elif bias != "neutral" and strength >= 0.15:
        quality = "medium"
    elif bias == "neutral" and vol_expect in ("low", "moderate"):
        quality = "medium"
    else:
        quality = "low"

    # Cascade active → always low quality (dangerous environment)
    if "forced_selling" in active or "forced_buying" in active:
        quality = "low"

    # ── Execution advice ──
    # When bias is directional, always give directional advice.
    # Strength modulates intensity, not gates it.
    if bias == "bearish":
        if "forced_selling" in active:
            advice = "wait"
            note = "Active liquidation cascade — avoid new positions until cascade fades"
        elif uncertainty >= 0.6 or strength >= 0.3:
            advice = "wait" if uncertainty >= 0.6 else "reduced"
            note = (
                "Bearish microstructure + high uncertainty — wait for clarity"
                if uncertainty >= 0.6
                else "Bearish flow pressure — reduce directional exposure"
            )
        else:
            advice = "reduced"
            note = "Bearish microstructure detected — consider reducing exposure"

    elif bias == "bullish":
        if "forced_buying" in active:
            advice = "avoid_aggressive"
            note = "Short squeeze in progress — avoid aggressive shorts, but don't chase"
        elif uncertainty >= 0.6:
            advice = "avoid_aggressive"
            note = "Bullish microstructure but high uncertainty — proceed cautiously"
        elif strength >= 0.3:
            advice = "normal"
            note = "Bullish flow alignment — normal execution"
        else:
            advice = "normal"
            note = "Mild bullish signal — standard execution with positive bias"

    elif bias == "neutral":
        if vol_expect in ("high", "extreme"):
            advice = "avoid_aggressive"
            note = "No clear directional edge but elevated volatility — reduce size"
        elif uncertainty >= 0.6:
            advice = "reduced"
            note = "Mixed signals + high uncertainty — reduced exposure recommended"
        else:
            advice = "normal"
            note = "Neutral microstructure — standard execution"

    else:
        advice = "normal"
        note = "Weak tactical signal — defer to strategic forecast"

    # ── Build reason flags ──
    reason_flags = list(active)

    # Add contextual flags
    if uncertainty >= 0.6:
        reason_flags.append("high_uncertainty")
    if vol_expect in ("high", "extreme"):
        reason_flags.append(f"volatility_{vol_expect}")

    return {
        "tacticalBias": bias,
        "tradeQuality": quality,
        "executionAdvice": advice,
        "volatilityExpectation": vol_expect,
        "reasonFlags": reason_flags,
        "signalStrength": strength,
        "fusionScore": score,
        "note": note,
    }
