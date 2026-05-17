"""
Decision Layer V1 — Acceptance Suite
=======================================
Synthetic test cases from the architecture spec.
Groups:
  A — Strong directional (LONG/SHORT, mode=directional)
  B — Moderate directional (cautious_directional)
  C — Must be NEUTRAL
  D — Edge cases
"""

import pytest
from forecast.decision.contracts import DecisionInputs
from forecast.decision.engine import DecisionLayerV1

engine = DecisionLayerV1()


# ═══════════════════════════════════════════
# Group A — Strong directional
# ═══════════════════════════════════════════

CASE_A1 = DecisionInputs(
    asset="BTC", horizon="30D",
    calibrated_confidence=0.58,
    forecast_direction="bullish",
    regime_entropy=0.32, regime_gap=0.18, dominant_regime="trend",
    structure_strength=0.78, bullish_structure=0.82, bearish_structure=0.22,
    context_alignment=0.70, negative_context=0.18,
    expected_move_pct=8.5,
    dominant_scenario="bullish", dominant_scenario_prob=0.55,
    bullish_prob=0.55, base_prob=0.28, bearish_prob=0.17,
)

CASE_A2 = DecisionInputs(
    asset="ETH", horizon="30D",
    calibrated_confidence=0.60,
    forecast_direction="bearish",
    regime_entropy=0.30, regime_gap=0.20, dominant_regime="breakdown",
    structure_strength=0.74, bullish_structure=0.20, bearish_structure=0.80,
    context_alignment=0.25, negative_context=0.72,
    expected_move_pct=9.0,
    dominant_scenario="bearish", dominant_scenario_prob=0.58,
    bullish_prob=0.18, base_prob=0.24, bearish_prob=0.58,
)


def test_a1_strong_bullish():
    result = engine.decide(CASE_A1)
    assert result.direction == "LONG", f"Expected LONG, got {result.direction}"
    assert result.decision_mode == "directional", f"Expected directional, got {result.decision_mode}"


def test_a2_strong_bearish():
    result = engine.decide(CASE_A2)
    assert result.direction == "SHORT", f"Expected SHORT, got {result.direction}"
    assert result.decision_mode == "directional", f"Expected directional, got {result.decision_mode}"


# ═══════════════════════════════════════════
# Group B — Moderate directional (cautious)
# ═══════════════════════════════════════════

CASE_B1 = DecisionInputs(
    asset="BTC", horizon="7D",
    calibrated_confidence=0.50,
    forecast_direction="bullish",
    regime_entropy=0.48, regime_gap=0.10, dominant_regime="pullback",
    structure_strength=0.64, bullish_structure=0.68, bearish_structure=0.30,
    context_alignment=0.58, negative_context=0.30,
    expected_move_pct=5.5,
    dominant_scenario="bullish", dominant_scenario_prob=0.46,
    bullish_prob=0.46, base_prob=0.34, bearish_prob=0.20,
)

CASE_B2 = DecisionInputs(
    asset="SOL", horizon="7D",
    calibrated_confidence=0.52,
    forecast_direction="bearish",
    regime_entropy=0.50, regime_gap=0.09, dominant_regime="transition",
    structure_strength=0.60, bullish_structure=0.35, bearish_structure=0.65,
    context_alignment=0.40, negative_context=0.62,
    expected_move_pct=6.0,
    dominant_scenario="bearish", dominant_scenario_prob=0.45,
    bullish_prob=0.25, base_prob=0.30, bearish_prob=0.45,
)


def test_b1_moderate_bullish():
    result = engine.decide(CASE_B1)
    assert result.direction == "LONG", f"Expected LONG, got {result.direction}"
    assert result.decision_mode == "cautious_directional", f"Expected cautious_directional, got {result.decision_mode}"


def test_b2_moderate_bearish():
    result = engine.decide(CASE_B2)
    assert result.direction == "SHORT", f"Expected SHORT, got {result.direction}"
    assert result.decision_mode == "cautious_directional", f"Expected cautious_directional, got {result.decision_mode}"


# ═══════════════════════════════════════════
# Group C — Must be NEUTRAL
# ═══════════════════════════════════════════

CASE_C1 = DecisionInputs(
    asset="BTC", horizon="30D",
    calibrated_confidence=0.44,
    forecast_direction="neutral",
    regime_entropy=0.78, regime_gap=0.04, dominant_regime="range",
    structure_strength=0.50, bullish_structure=0.48, bearish_structure=0.47,
    context_alignment=0.50, negative_context=0.48,
    expected_move_pct=4.0,
    dominant_scenario="base", dominant_scenario_prob=0.38,
    bullish_prob=0.31, base_prob=0.38, bearish_prob=0.31,
)

CASE_C2 = DecisionInputs(
    asset="ETH", horizon="24H",
    calibrated_confidence=0.48,
    forecast_direction="bullish",
    regime_entropy=0.45, regime_gap=0.07, dominant_regime="range",
    structure_strength=0.60, bullish_structure=0.62, bearish_structure=0.30,
    context_alignment=0.55, negative_context=0.35,
    expected_move_pct=1.2,
    dominant_scenario="bullish", dominant_scenario_prob=0.47,
    bullish_prob=0.47, base_prob=0.33, bearish_prob=0.20,
)

CASE_C3 = DecisionInputs(
    asset="SOL", horizon="7D",
    calibrated_confidence=0.46,
    forecast_direction="neutral",
    regime_entropy=0.60, regime_gap=0.02, dominant_regime="transition",
    structure_strength=0.52, bullish_structure=0.50, bearish_structure=0.49,
    context_alignment=0.50, negative_context=0.50,
    expected_move_pct=5.0,
    dominant_scenario="base", dominant_scenario_prob=0.36,
    bullish_prob=0.33, base_prob=0.36, bearish_prob=0.31,
)


def test_c1_high_entropy_range():
    result = engine.decide(CASE_C1)
    assert result.direction == "NEUTRAL", f"Expected NEUTRAL, got {result.direction}"
    assert result.decision_mode == "neutral_filter"


def test_c2_low_expected_move():
    result = engine.decide(CASE_C2)
    assert result.direction == "NEUTRAL", f"Expected NEUTRAL, got {result.direction}"


def test_c3_flat_scenarios():
    result = engine.decide(CASE_C3)
    assert result.direction == "NEUTRAL", f"Expected NEUTRAL, got {result.direction}"


# ═══════════════════════════════════════════
# Group D — Edge cases
# ═══════════════════════════════════════════

CASE_D1 = DecisionInputs(
    asset="BTC", horizon="30D",
    calibrated_confidence=0.50,
    forecast_direction="bullish",
    regime_entropy=0.55, regime_gap=0.03, dominant_regime="transition",
    structure_strength=0.60, bullish_structure=0.64, bearish_structure=0.60,
    context_alignment=0.52, negative_context=0.50,
    expected_move_pct=7.0,
    dominant_scenario="bullish", dominant_scenario_prob=0.41,
    bullish_prob=0.41, base_prob=0.20, bearish_prob=0.39,
)

CASE_D2 = DecisionInputs(
    asset="BTC", horizon="30D",
    calibrated_confidence=0.52,
    forecast_direction="bullish",
    regime_entropy=0.74, regime_gap=0.05, dominant_regime="transition",
    structure_strength=0.70, bullish_structure=0.75, bearish_structure=0.30,
    context_alignment=0.65, negative_context=0.30,
    expected_move_pct=10.0,
    dominant_scenario="bullish", dominant_scenario_prob=0.52,
    bullish_prob=0.52, base_prob=0.30, bearish_prob=0.18,
)

CASE_D3 = DecisionInputs(
    asset="ETH", horizon="24H",
    calibrated_confidence=0.55,
    forecast_direction="bullish",
    regime_entropy=0.40, regime_gap=0.12, dominant_regime="trend",
    structure_strength=0.70, bullish_structure=0.75, bearish_structure=0.20,
    context_alignment=0.68, negative_context=0.25,
    expected_move_pct=1.4,
    dominant_scenario="bullish", dominant_scenario_prob=0.53,
    bullish_prob=0.53, base_prob=0.27, bearish_prob=0.20,
)


def test_d1_conflict_balanced():
    """Bullish vs bearish nearly equal → NEUTRAL."""
    result = engine.decide(CASE_D1)
    assert result.direction == "NEUTRAL", f"Expected NEUTRAL, got {result.direction}"


def test_d2_strong_move_high_entropy():
    """Strong move but entropy too high → NEUTRAL."""
    result = engine.decide(CASE_D2)
    assert result.direction == "NEUTRAL", f"Expected NEUTRAL, got {result.direction}"


def test_d3_strong_scenario_tiny_move():
    """Strong scenario but tiny expected move → NEUTRAL."""
    result = engine.decide(CASE_D3)
    assert result.direction == "NEUTRAL", f"Expected NEUTRAL, got {result.direction}"


# ═══════════════════════════════════════════
# Structural invariants
# ═══════════════════════════════════════════

def test_output_has_audit():
    """Every decision must have an audit dict with scores."""
    result = engine.decide(CASE_A1)
    assert "long_score" in result.audit
    assert "short_score" in result.audit
    assert "neutral_pressure" in result.audit
    assert "norm_move" in result.audit
    assert "ambiguity" in result.audit


def test_output_has_rationale():
    """Every directional decision must have at least one rationale."""
    result = engine.decide(CASE_A1)
    assert len(result.rationale) >= 1


def test_confidence_in_range():
    """Decision confidence must be in [0, 1]."""
    for case in [CASE_A1, CASE_A2, CASE_B1, CASE_B2, CASE_C1, CASE_C2, CASE_C3, CASE_D1, CASE_D2, CASE_D3]:
        result = engine.decide(case)
        assert 0.0 <= result.decision_confidence <= 1.0, f"Confidence out of range: {result.decision_confidence}"
        assert 0.0 <= result.decision_strength <= 1.0, f"Strength out of range: {result.decision_strength}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
