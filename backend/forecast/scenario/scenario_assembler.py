"""
Scenario Assembler
===================
Main entry point for the 30D Scenario Engine.

Orchestrates: builder → weighting → ranges → final ScenarioSet.

Usage:
    from forecast.scenario.scenario_assembler import build_scenarios
    result = build_scenarios(scenario_input)
"""

from forecast.scenario.scenario_types import (
    ScenarioInput, ScenarioSet, Scenario, SCENARIO_NAMES,
)
from forecast.scenario.scenario_builder import build_scenario_centers
from forecast.scenario.scenario_weighting import compute_scenario_weights
from forecast.scenario.scenario_ranges import build_scenario_ranges


def build_scenarios(inp: ScenarioInput) -> ScenarioSet:
    """
    Build complete scenario set from pipeline data.

    Pipeline: centers → weights → ranges → assembly.
    """
    # Step 1: Generate scenario centers
    centers = build_scenario_centers(inp)

    # Step 2: Compute probabilities
    weights = compute_scenario_weights(inp)

    # Step 3: Build ranges (depends on weights + centers)
    ranges = build_scenario_ranges(
        centers=centers,
        weights=weights,
        volatility=inp["volatility"],
        std_return=inp["std_return"],
        decision_uncertainty=inp.get("decision_uncertainty", 0.5),
        dominant_regime=inp.get("dominant_regime", "range"),
    )

    # Step 4: Assemble scenarios
    narratives = _build_narratives(inp, centers, weights)

    scenarios: list[Scenario] = []
    for stype in SCENARIO_NAMES:
        scenarios.append({
            "type": stype,
            "probability": weights[stype],
            "range": ranges[stype],
            "expected_move": centers[stype],
            "narrative": narratives[stype],
        })

    # Determine dominant scenario
    dominant = max(SCENARIO_NAMES, key=lambda s: weights[s])

    # Confidence tag based on probability concentration + distribution shape
    max_prob = max(weights[s] for s in SCENARIO_NAMES)
    min_prob = min(weights[s] for s in SCENARIO_NAMES)
    prob_spread = max_prob - min_prob
    # Entropy-like measure: how uniform is the distribution?
    # Uniform (0.33/0.33/0.33) → entropy=1.0, concentrated → entropy→0
    import math
    entropy = -sum(
        weights[s] * math.log(max(weights[s], 0.01))
        for s in SCENARIO_NAMES
    ) / math.log(3)  # normalize to [0, 1]

    if max_prob > 0.42 and prob_spread > 0.15 and entropy < 0.98:
        confidence_tag = "high_confidence"
    elif prob_spread < 0.07 or (entropy > 0.996 and max_prob < 0.38):
        confidence_tag = "uncertain"
    else:
        confidence_tag = "moderate"

    # Total spread
    all_lows = [ranges[s][0] for s in SCENARIO_NAMES]
    all_highs = [ranges[s][1] for s in SCENARIO_NAMES]
    spread = max(all_highs) - min(all_lows)

    return {
        "scenarios": scenarios,
        "dominant": dominant,
        "spread": round(spread, 2),
        "confidence_tag": confidence_tag,
        "_audit": {
            "centers": centers,
            "weights": {k: v for k, v in weights.items() if not k.startswith("_")},
            "ranges": {k: v for k, v in ranges.items() if not k.startswith("_")},
            "weights_debug": weights.get("_debug"),
            "ranges_debug": ranges.get("_debug"),
            "centers_debug": centers.get("_raw"),
        },
    }


def _build_narratives(inp: ScenarioInput, centers: dict, weights: dict) -> dict:
    """Generate human-readable labels for each scenario."""
    dominant = inp.get("dominant_regime", "range")
    momentum = inp["momentum"]

    # Bullish narrative
    if dominant == "trend" and momentum > 0:
        bull_narr = "Trend continuation with momentum support"
    elif dominant == "pullback":
        bull_narr = "Recovery from pullback, mean reversion upward"
    elif dominant == "breakdown":
        bull_narr = "Reversal from oversold, recovery bounce"
    else:
        bull_narr = "Positive momentum scenario"

    # Base narrative
    if dominant == "range":
        base_narr = "Range-bound consolidation"
    elif dominant == "transition":
        base_narr = "Low conviction, consolidation likely"
    else:
        base_narr = "Most probable path based on current conditions"

    # Bearish narrative
    if dominant == "breakdown":
        bear_narr = "Continued downside pressure, structural weakness"
    elif dominant == "trend" and momentum < 0:
        bear_narr = "Bearish trend continuation"
    elif dominant == "late_trend" if hasattr(dominant, '__len__') else False:
        bear_narr = "Trend exhaustion, correction risk"
    else:
        bear_narr = "Downside risk scenario"

    return {
        "bullish": bull_narr,
        "base": base_narr,
        "bearish": bear_narr,
    }
