"""
Scenario Ranges
================
Builds probability-weighted ranges for each scenario.

Ranges depend on:
  - scenario probability (lower prob → wider range)
  - volatility (higher vol → wider ranges)
  - decision_uncertainty (higher → wider ranges)
  - dominant regime (transition/range → wider)

Constraints:
  - No chaotic overlap between scenarios
  - Ranges must be meaningful (not too narrow or too wide)
  - Adjacent scenarios share a boundary (base_high ≈ bullish_low)
"""


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def build_scenario_ranges(
    centers: dict,
    weights: dict,
    volatility: float,
    std_return: float,
    decision_uncertainty: float = 0.5,
    dominant_regime: str = "range",
) -> dict:
    """
    Build ranges for each scenario.

    Strategy:
      - Base width = f(volatility, std_return)
      - Width scaled by uncertainty and probability
      - Lower probability → wider range (more uncertain about that path)
      - Ranges are adjacent: bearish_upper → base_lower → base_upper → bullish_lower
    """
    bull_center = centers["bullish"]
    base_center = centers["base"]
    bear_center = centers["bearish"]

    # ── Base range width (in %) ──
    # Anchored to regime std_return, with volatility influence
    base_width_pct = std_return * 100 * 0.8  # ~80% of 1 std dev in pct
    vol_factor = _clamp(volatility / 0.025, 0.6, 2.0)  # normalize around 2.5% daily vol
    base_width = base_width_pct * vol_factor

    # Minimum width guard
    base_width = max(base_width, 1.5)  # at least 1.5%

    # ── Uncertainty scaling ──
    # High uncertainty → wider ranges
    # Mapped: 0 → 0.8x, 0.5 → 1.0x, 1.0 → 1.4x
    uncertainty_scale = 0.8 + 0.6 * decision_uncertainty
    base_width *= uncertainty_scale

    # ── Regime scaling ──
    _REGIME_WIDTH_SCALE = {
        "trend": 0.85,       # trend → narrower (more conviction)
        "range": 1.10,       # range → wider (flatter distribution)
        "pullback": 0.90,    # pullback → slightly narrower
        "transition": 1.25,  # transition → much wider
        "breakdown": 1.15,   # breakdown → wider (stress)
    }
    regime_scale = _REGIME_WIDTH_SCALE.get(dominant_regime, 1.0)
    base_width *= regime_scale

    # ── Per-scenario width (inversely proportional to probability) ──
    # Higher probability → narrower range (more certain about center)
    # Lower probability → wider range (could be anywhere in that zone)
    bull_prob = max(weights["bullish"], 0.08)
    base_prob = max(weights["base"], 0.08)
    bear_prob = max(weights["bearish"], 0.08)

    # Width inversely proportional to probability: w = base * (0.5 / prob)^0.3
    # Capped to prevent extreme widths
    bull_width = base_width * _clamp((0.33 / bull_prob) ** 0.3, 0.7, 1.8)
    base_width_adj = base_width * _clamp((0.33 / base_prob) ** 0.3, 0.7, 1.5)
    bear_width = base_width * _clamp((0.33 / bear_prob) ** 0.3, 0.7, 1.8)

    # ── Build ranges as (lower, upper) ──
    # Use midpoint between adjacent scenarios as shared boundaries
    bull_bear_gap = bull_center - bear_center
    base_bull_mid = (base_center + bull_center) / 2
    base_bear_mid = (base_center + bear_center) / 2

    bullish_range = (
        round(base_bull_mid, 2),
        round(bull_center + bull_width / 2, 2),
    )
    base_range = (
        round(base_bear_mid, 2),
        round(base_bull_mid, 2),
    )
    bearish_range = (
        round(bear_center - bear_width / 2, 2),
        round(base_bear_mid, 2),
    )

    # ── Sanity: ensure non-degenerate ranges ──
    def fix_range(r):
        if r[1] <= r[0]:
            mid = (r[0] + r[1]) / 2
            return (round(mid - 0.5, 2), round(mid + 0.5, 2))
        return r

    bullish_range = fix_range(bullish_range)
    base_range = fix_range(base_range)
    bearish_range = fix_range(bearish_range)

    return {
        "bullish": bullish_range,
        "base": base_range,
        "bearish": bearish_range,
        "_debug": {
            "base_width_raw": round(base_width_pct, 4),
            "vol_factor": round(vol_factor, 4),
            "uncertainty_scale": round(uncertainty_scale, 4),
            "regime_scale": round(regime_scale, 4),
            "bull_width": round(bull_width, 4),
            "base_width": round(base_width_adj, 4),
            "bear_width": round(bear_width, 4),
        },
    }
