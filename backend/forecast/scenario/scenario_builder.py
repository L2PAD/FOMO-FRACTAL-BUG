"""
Scenario Builder
=================
Generates raw scenario centers from forecast pipeline data.

Centers represent the expected move (%) for each scenario:
  - bullish: optimistic path
  - base: most probable path (NOT just 0 or forecast)
  - bearish: pessimistic path

Key principle: base = the most probable path, which may lean
bullish or bearish depending on momentum + structure.

Centers are generated BEFORE weighting and ranges.
"""

from forecast.scenario.scenario_types import ScenarioInput


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def build_scenario_centers(inp: ScenarioInput) -> dict:
    """
    Generate scenario centers (expected moves in %).

    Logic:
      - base_center: median return, shifted by momentum + structure
      - bullish_center: p75 anchor, boosted by trend signals
      - bearish_center: p25 anchor, stressed by risk signals

    Returns dict with {bullish, base, bearish} centers.
    """
    median = inp["median_return"]
    p25 = inp["p25_return"]
    p75 = inp["p75_return"]
    std = max(inp["std_return"], 0.005)
    momentum = inp["momentum"]
    structure_bias = inp.get("structure_bias", 0.0)
    volatility = inp["volatility"]

    # ── Base center ──
    # Start from median, shift by momentum + structure
    # Momentum influence: moderate (scaled by 0.3)
    # Structure influence: gentle (scaled by 0.15)
    momentum_shift = momentum * std * 0.3
    structure_shift = structure_bias * std * 0.15
    base_center = median + momentum_shift + structure_shift

    # ── Bullish center ──
    # Anchor at p75, with upward push from trend/momentum
    bullish_anchor = p75
    # Stronger momentum → center moves further into tail
    trend_push = max(0, momentum) * std * 0.5
    bullish_center = bullish_anchor + trend_push

    # Ensure bullish > base
    if bullish_center <= base_center:
        bullish_center = base_center + 0.3 * std

    # ── Bearish center ──
    # Anchor at p25, with downward push from risk signals
    bearish_anchor = p25
    # Negative momentum → push deeper into bear territory
    risk_push = min(0, momentum) * std * 0.5  # negative value
    bearish_center = bearish_anchor + risk_push

    # Ensure bearish < base
    if bearish_center >= base_center:
        bearish_center = base_center - 0.3 * std

    # ── Regime-based adjustments ──
    dominant = inp.get("dominant_regime", "range")
    if dominant == "trend":
        # Trend: stretch the bullish tail, compress bearish
        bullish_center += 0.15 * std
        bearish_center += 0.05 * std  # less negative
    elif dominant == "breakdown":
        # Breakdown: stretch bearish, compress bullish
        bearish_center -= 0.15 * std
        bullish_center -= 0.05 * std  # less positive
    elif dominant == "transition":
        # Transition: compress all toward center (low conviction)
        spread_factor = 0.8
        mid = (bullish_center + bearish_center) / 2
        bullish_center = mid + (bullish_center - mid) * spread_factor
        bearish_center = mid + (bearish_center - mid) * spread_factor
    elif dominant == "pullback":
        # Pullback: base is mean-reverting, so slightly boost base
        base_center += 0.05 * std * (-1 if momentum > 0 else 1)

    # ── Ensure monotonic ordering ──
    # bullish > base > bearish (always)
    min_gap = 0.2 * std
    if bullish_center - base_center < min_gap:
        bullish_center = base_center + min_gap
    if base_center - bearish_center < min_gap:
        bearish_center = base_center - min_gap

    return {
        "bullish": round(bullish_center * 100, 2),  # convert to %
        "base": round(base_center * 100, 2),
        "bearish": round(bearish_center * 100, 2),
        "_raw": {
            "median": round(median * 100, 4),
            "p25": round(p25 * 100, 4),
            "p75": round(p75 * 100, 4),
            "momentum_shift": round(momentum_shift * 100, 4),
            "structure_shift": round(structure_shift * 100, 4),
            "std_pct": round(std * 100, 4),
            "dominant_regime": dominant,
        },
    }
