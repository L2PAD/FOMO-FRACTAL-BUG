"""
Scenario Types
===============
Type definitions for the 30D Scenario Engine (Block 3).

Three scenarios: bullish / base / bearish
Each has probability, range, expected move, and narrative.
"""

from typing import Literal, TypedDict


ScenarioType = Literal["bullish", "base", "bearish"]

SCENARIO_NAMES: list[ScenarioType] = ["bullish", "base", "bearish"]


class Scenario(TypedDict):
    type: ScenarioType
    probability: float          # [0, 1], sum of all 3 = 1.0
    range: tuple[float, float]  # (lower_pct, upper_pct) in move %
    expected_move: float        # center of scenario in move %
    narrative: str              # human-readable label


class ScenarioSet(TypedDict):
    scenarios: list[Scenario]
    dominant: ScenarioType      # highest probability scenario
    spread: float               # total range width (max_upper - min_lower)
    confidence_tag: str         # "concentrated" | "distributed" | "uncertain"


class ScenarioInput(TypedDict):
    """All inputs needed for scenario generation."""
    # From base features
    momentum: float             # [-1, 1] directional momentum
    volatility: float           # daily volatility (e.g. 0.02-0.06)
    ret_7d: float               # 7-day return
    ret_14d: float              # 14-day return

    # From regime baselines
    median_return: float        # regime-specific median 30D return
    std_return: float           # regime-specific std dev
    p25_return: float           # 25th percentile return
    p75_return: float           # 75th percentile return
    mean_return: float          # mean return

    # From structure (optional)
    structure_bias: float       # [-1, 1] fused structure bias
    mode: str                   # pullback / aligned / range / mixed_range

    # From regime V2 (optional, computed separately)
    regime_probs: dict | None   # {trend: 0.4, range: 0.3, ...} or None
    dominant_regime: str        # trend/range/pullback/transition/breakdown
    regime_entropy: float       # [0, 1]
    decision_uncertainty: float # [0, 1]

    # From context (optional)
    context_phase: str | None   # continuation/pullback/breakdown/etc or None
