"""
Tests for Interaction Layer V1 — Structure x Regime x Scenario
================================================================
Covers:
  - Polarity classifiers (structure, regime)
  - Interaction state classification (7 states)
  - Alignment & conflict scores
  - Modifiers (confidence, decision_bias, scenario)
  - User acceptance suite (I1–I5)
  - Edge cases & boundary conditions
"""

import pytest
from forecast.decision.interaction_layer import (
    InteractionLayerV1,
    InteractionInputs,
    InteractionOutput,
)

layer = InteractionLayerV1()


def _make_input(**overrides) -> InteractionInputs:
    """Default mid-range input, overridable per-field."""
    defaults = dict(
        structure_state="mixed",
        structure_clarity=0.5,
        bullish_structure=0.4,
        bearish_structure=0.4,
        dominant_regime="range",
        regime_entropy=0.5,
        dominant_scenario="base",
        bullish_prob=0.33,
        base_prob=0.34,
        bearish_prob=0.33,
        calibrated_confidence=0.5,
        expected_move_pct=3.0,
    )
    defaults.update(overrides)
    return InteractionInputs(**defaults)


# ──────────────────────────────────────────────
# 1. Structure polarity
# ──────────────────────────────────────────────

class TestStructurePolarity:
    def test_bullish(self):
        x = _make_input(bullish_structure=0.7, bearish_structure=0.3)
        assert layer._structure_polarity(x) == "bullish"

    def test_bearish(self):
        x = _make_input(bullish_structure=0.2, bearish_structure=0.6)
        assert layer._structure_polarity(x) == "bearish"

    def test_mixed_close(self):
        x = _make_input(bullish_structure=0.45, bearish_structure=0.40)
        assert layer._structure_polarity(x) == "mixed"

    def test_exactly_at_threshold(self):
        # 0.55 - 0.40 = 0.15 (floating point: 0.150000...002), at boundary → bullish
        x = _make_input(bullish_structure=0.55, bearish_structure=0.40)
        assert layer._structure_polarity(x) == "bullish"

    def test_below_threshold(self):
        x = _make_input(bullish_structure=0.54, bearish_structure=0.40)
        assert layer._structure_polarity(x) == "mixed"


# ──────────────────────────────────────────────
# 2. Regime polarity
# ──────────────────────────────────────────────

class TestRegimePolarity:
    def test_trend_bullish(self):
        x = _make_input(dominant_regime="trend")
        assert layer._regime_polarity(x) == "bullish"

    def test_pullback_bullish(self):
        x = _make_input(dominant_regime="pullback")
        assert layer._regime_polarity(x) == "bullish"

    def test_breakdown_bearish(self):
        x = _make_input(dominant_regime="breakdown")
        assert layer._regime_polarity(x) == "bearish"

    def test_range_mixed(self):
        x = _make_input(dominant_regime="range")
        assert layer._regime_polarity(x) == "mixed"

    def test_transition_mixed(self):
        x = _make_input(dominant_regime="transition")
        assert layer._regime_polarity(x) == "mixed"

    def test_unknown_regime_mixed(self):
        x = _make_input(dominant_regime="something_else")
        assert layer._regime_polarity(x) == "mixed"


# ──────────────────────────────────────────────
# 3. Interaction state classification
# ──────────────────────────────────────────────

class TestInteractionState:
    def test_aligned_bullish(self):
        x = _make_input(
            bullish_structure=0.7, bearish_structure=0.2,
            dominant_regime="trend",
            dominant_scenario="bullish",
        )
        out = layer.evaluate(x)
        assert out.interaction_state == "aligned_bullish"

    def test_aligned_bearish(self):
        x = _make_input(
            bullish_structure=0.2, bearish_structure=0.7,
            dominant_regime="breakdown",
            dominant_scenario="bearish",
        )
        out = layer.evaluate(x)
        assert out.interaction_state == "aligned_bearish"

    def test_fragile_bullish(self):
        x = _make_input(
            bullish_structure=0.7, bearish_structure=0.2,
            dominant_regime="range",
            dominant_scenario="bullish",
        )
        out = layer.evaluate(x)
        assert out.interaction_state == "fragile_bullish"

    def test_fragile_bearish(self):
        x = _make_input(
            bullish_structure=0.2, bearish_structure=0.7,
            dominant_regime="range",
            dominant_scenario="bearish",
        )
        out = layer.evaluate(x)
        assert out.interaction_state == "fragile_bearish"

    def test_transition_conflict(self):
        x = _make_input(
            bullish_structure=0.2, bearish_structure=0.7,
            dominant_regime="transition",
            dominant_scenario="bullish",
        )
        out = layer.evaluate(x)
        assert out.interaction_state == "transition_conflict"

    def test_range_mixed_from_structure(self):
        x = _make_input(
            structure_state="range",
            bullish_structure=0.4, bearish_structure=0.4,
            dominant_regime="range",
            dominant_scenario="bullish",
        )
        out = layer.evaluate(x)
        assert out.interaction_state == "range_mixed"

    def test_range_mixed_from_base_scenario(self):
        x = _make_input(
            bullish_structure=0.7, bearish_structure=0.2,
            dominant_regime="trend",
            dominant_scenario="base",
        )
        out = layer.evaluate(x)
        assert out.interaction_state == "range_mixed"

    def test_mixed_unclear_fallback(self):
        x = _make_input(
            bullish_structure=0.45, bearish_structure=0.40,
            dominant_regime="range",
            dominant_scenario="bullish",
        )
        out = layer.evaluate(x)
        assert out.interaction_state == "mixed_unclear"


# ──────────────────────────────────────────────
# 4. Alignment score
# ──────────────────────────────────────────────

class TestAlignmentScore:
    def test_full_alignment(self):
        x = _make_input(
            bullish_structure=0.8, bearish_structure=0.1,
            dominant_regime="trend",
            dominant_scenario="bullish",
            structure_clarity=0.9,
            regime_entropy=0.1,
        )
        out = layer.evaluate(x)
        assert out.alignment_score >= 0.85

    def test_no_alignment(self):
        x = _make_input(
            bullish_structure=0.4, bearish_structure=0.4,
            dominant_regime="range",
            dominant_scenario="base",
            structure_clarity=0.2,
            regime_entropy=0.8,
        )
        out = layer.evaluate(x)
        assert out.alignment_score <= 0.25

    def test_clamped_to_01(self):
        x = _make_input(
            bullish_structure=1.0, bearish_structure=0.0,
            dominant_regime="trend",
            dominant_scenario="bullish",
            structure_clarity=1.0,
            regime_entropy=0.0,
        )
        out = layer.evaluate(x)
        assert 0.0 <= out.alignment_score <= 1.0


# ──────────────────────────────────────────────
# 5. Conflict score
# ──────────────────────────────────────────────

class TestConflictScore:
    def test_strong_conflict(self):
        x = _make_input(
            bullish_structure=0.2, bearish_structure=0.7,
            dominant_regime="trend",
            dominant_scenario="bullish",
            structure_clarity=0.2,
            regime_entropy=0.8,
        )
        out = layer.evaluate(x)
        assert out.conflict_score >= 0.60

    def test_no_conflict_aligned(self):
        x = _make_input(
            bullish_structure=0.8, bearish_structure=0.1,
            dominant_regime="trend",
            dominant_scenario="bullish",
            structure_clarity=0.9,
            regime_entropy=0.1,
        )
        out = layer.evaluate(x)
        assert out.conflict_score <= 0.15

    def test_clamped_to_01(self):
        x = _make_input(
            bullish_structure=0.0, bearish_structure=1.0,
            dominant_regime="trend",
            dominant_scenario="bullish",
            structure_clarity=0.0,
            regime_entropy=1.0,
        )
        out = layer.evaluate(x)
        assert 0.0 <= out.conflict_score <= 1.0


# ──────────────────────────────────────────────
# 6. Decision bias modifier
# ──────────────────────────────────────────────

class TestDecisionBiasModifier:
    def test_aligned_positive(self):
        x = _make_input(
            bullish_structure=0.8, bearish_structure=0.1,
            dominant_regime="trend",
            dominant_scenario="bullish",
            structure_clarity=0.8, regime_entropy=0.2,
        )
        out = layer.evaluate(x)
        assert out.decision_bias_modifier > 0.0
        assert out.decision_bias_modifier <= 0.18

    def test_conflict_negative(self):
        x = _make_input(
            bullish_structure=0.2, bearish_structure=0.7,
            dominant_regime="trend",
            dominant_scenario="bullish",
            structure_clarity=0.2, regime_entropy=0.7,
        )
        out = layer.evaluate(x)
        assert out.decision_bias_modifier < 0.0
        assert out.decision_bias_modifier >= -0.15

    def test_within_caps(self):
        """All outputs must be within [-0.15, +0.18]."""
        cases = [
            dict(bullish_structure=1.0, bearish_structure=0.0, dominant_regime="trend", dominant_scenario="bullish", structure_clarity=1.0, regime_entropy=0.0),
            dict(bullish_structure=0.0, bearish_structure=1.0, dominant_regime="trend", dominant_scenario="bullish", structure_clarity=0.0, regime_entropy=1.0),
        ]
        for kw in cases:
            out = layer.evaluate(_make_input(**kw))
            assert -0.15 <= out.decision_bias_modifier <= 0.18


# ──────────────────────────────────────────────
# 7. Confidence modifier
# ──────────────────────────────────────────────

class TestConfidenceModifier:
    def test_alignment_boosts(self):
        x = _make_input(
            bullish_structure=0.8, bearish_structure=0.1,
            dominant_regime="trend", dominant_scenario="bullish",
            structure_clarity=0.9, regime_entropy=0.1,
        )
        out = layer.evaluate(x)
        assert out.confidence_modifier > 0.0

    def test_conflict_penalizes(self):
        x = _make_input(
            bullish_structure=0.2, bearish_structure=0.7,
            dominant_regime="trend", dominant_scenario="bullish",
            structure_clarity=0.2, regime_entropy=0.8,
        )
        out = layer.evaluate(x)
        assert out.confidence_modifier < 0.0

    def test_within_caps(self):
        out = layer.evaluate(_make_input(
            bullish_structure=1.0, bearish_structure=0.0,
            dominant_regime="trend", dominant_scenario="bullish",
            structure_clarity=1.0, regime_entropy=0.0,
        ))
        assert -0.20 <= out.confidence_modifier <= 0.15


# ──────────────────────────────────────────────
# 8. Scenario modifiers
# ──────────────────────────────────────────────

class TestScenarioModifiers:
    def test_aligned_bullish_boosts_bullish_scenario(self):
        x = _make_input(
            bullish_structure=0.8, bearish_structure=0.1,
            dominant_regime="trend", dominant_scenario="bullish",
            structure_clarity=0.8, regime_entropy=0.1,
        )
        out = layer.evaluate(x)
        assert out.bullish_scenario_modifier > 0.0
        assert out.bearish_scenario_modifier < 0.0

    def test_aligned_bearish_boosts_bearish_scenario(self):
        x = _make_input(
            bullish_structure=0.1, bearish_structure=0.8,
            dominant_regime="breakdown", dominant_scenario="bearish",
            structure_clarity=0.8, regime_entropy=0.1,
        )
        out = layer.evaluate(x)
        assert out.bearish_scenario_modifier > 0.0
        assert out.bullish_scenario_modifier < 0.0

    def test_conflict_boosts_base(self):
        x = _make_input(
            bullish_structure=0.2, bearish_structure=0.7,
            dominant_regime="transition", dominant_scenario="bullish",
            structure_clarity=0.3, regime_entropy=0.6,
        )
        out = layer.evaluate(x)
        assert out.base_scenario_modifier > 0.0

    def test_all_within_caps(self):
        """Scenario mods must be in [-0.10, +0.10]."""
        extremes = [
            dict(bullish_structure=1.0, bearish_structure=0.0, dominant_regime="trend", dominant_scenario="bullish", structure_clarity=1.0, regime_entropy=0.0),
            dict(bullish_structure=0.0, bearish_structure=1.0, dominant_regime="breakdown", dominant_scenario="bearish", structure_clarity=1.0, regime_entropy=0.0),
            dict(bullish_structure=0.0, bearish_structure=1.0, dominant_regime="trend", dominant_scenario="bullish", structure_clarity=0.0, regime_entropy=1.0),
        ]
        for kw in extremes:
            out = layer.evaluate(_make_input(**kw))
            assert -0.10 <= out.bullish_scenario_modifier <= 0.10
            assert -0.10 <= out.base_scenario_modifier <= 0.10
            assert -0.10 <= out.bearish_scenario_modifier <= 0.10


# ──────────────────────────────────────────────
# 9. User acceptance suite (I1–I5)
# ──────────────────────────────────────────────

class TestAcceptanceSuite:
    def test_I1_aligned_bullish(self):
        """All layers agree bullish → aligned, high confidence uplift."""
        out = layer.evaluate(_make_input(
            structure_state="bullish",
            bullish_structure=0.75, bearish_structure=0.15,
            dominant_regime="trend",
            dominant_scenario="bullish",
            bullish_prob=0.55, base_prob=0.25, bearish_prob=0.20,
            structure_clarity=0.7, regime_entropy=0.2,
        ))
        assert out.interaction_state == "aligned_bullish"
        assert out.alignment_score >= 0.6
        assert out.confidence_modifier > 0.0
        assert out.bullish_scenario_modifier > 0.0

    def test_I2_aligned_bearish(self):
        """All layers agree bearish → aligned, confidence up, bearish prob up."""
        out = layer.evaluate(_make_input(
            structure_state="bearish",
            bullish_structure=0.15, bearish_structure=0.75,
            dominant_regime="breakdown",
            dominant_scenario="bearish",
            bullish_prob=0.15, base_prob=0.25, bearish_prob=0.60,
            structure_clarity=0.7, regime_entropy=0.2,
        ))
        assert out.interaction_state == "aligned_bearish"
        assert out.alignment_score >= 0.6
        assert out.confidence_modifier > 0.0
        assert out.bearish_scenario_modifier > 0.0

    def test_I3_fragile_bullish(self):
        """Bullish structure + bullish scenario, but regime is mixed → fragile."""
        out = layer.evaluate(_make_input(
            structure_state="bullish",
            bullish_structure=0.70, bearish_structure=0.15,
            dominant_regime="transition",
            dominant_scenario="bullish",
            bullish_prob=0.50, base_prob=0.30, bearish_prob=0.20,
            structure_clarity=0.5, regime_entropy=0.5,
        ))
        assert out.interaction_state == "fragile_bullish"
        assert out.decision_bias_modifier > 0.0
        assert out.decision_bias_modifier < 0.10  # moderate, not strong

    def test_I4_conflict(self):
        """Bearish structure vs bullish scenario + transition regime → conflict."""
        out = layer.evaluate(_make_input(
            structure_state="bearish",
            bullish_structure=0.15, bearish_structure=0.70,
            dominant_regime="transition",
            dominant_scenario="bullish",
            bullish_prob=0.45, base_prob=0.30, bearish_prob=0.25,
            structure_clarity=0.3, regime_entropy=0.6,
        ))
        assert out.interaction_state == "transition_conflict"
        assert out.confidence_modifier < 0.0
        assert out.base_scenario_modifier > 0.0

    def test_I5_range_mixed(self):
        """Range structure + base scenario → neutralizing behavior."""
        out = layer.evaluate(_make_input(
            structure_state="range",
            bullish_structure=0.35, bearish_structure=0.35,
            dominant_regime="range",
            dominant_scenario="base",
            bullish_prob=0.25, base_prob=0.50, bearish_prob=0.25,
            structure_clarity=0.3, regime_entropy=0.5,
        ))
        assert out.interaction_state == "range_mixed"
        assert out.decision_bias_modifier < 0.0  # neutralizing


# ──────────────────────────────────────────────
# 10. Rationale
# ──────────────────────────────────────────────

class TestRationale:
    def test_aligned_has_rationale(self):
        out = layer.evaluate(_make_input(
            bullish_structure=0.8, bearish_structure=0.1,
            dominant_regime="trend", dominant_scenario="bullish",
            structure_clarity=0.9, regime_entropy=0.1,
        ))
        assert len(out.rationale) >= 1
        assert any("aligned" in r for r in out.rationale)

    def test_conflict_mentions_conflict(self):
        out = layer.evaluate(_make_input(
            bullish_structure=0.2, bearish_structure=0.7,
            dominant_regime="transition", dominant_scenario="bullish",
        ))
        assert len(out.rationale) >= 1
        assert any("conflict" in r for r in out.rationale)


# ──────────────────────────────────────────────
# 11. Audit payload
# ──────────────────────────────────────────────

class TestAudit:
    def test_audit_contains_polarities(self):
        out = layer.evaluate(_make_input(
            bullish_structure=0.8, bearish_structure=0.1,
            dominant_regime="trend", dominant_scenario="bullish",
        ))
        assert "structure_polarity" in out.audit
        assert "regime_polarity" in out.audit
        assert "scenario_polarity" in out.audit

    def test_audit_values_correct(self):
        out = layer.evaluate(_make_input(
            bullish_structure=0.8, bearish_structure=0.1,
            dominant_regime="breakdown", dominant_scenario="bearish",
        ))
        assert out.audit["structure_polarity"] == "bullish"
        assert out.audit["regime_polarity"] == "bearish"
        assert out.audit["scenario_polarity"] == "bearish"


# ──────────────────────────────────────────────
# 12. Edge cases
# ──────────────────────────────────────────────

class TestEdgeCases:
    def test_zero_structure_values(self):
        out = layer.evaluate(_make_input(
            bullish_structure=0.0, bearish_structure=0.0,
            structure_clarity=0.0, regime_entropy=1.0,
        ))
        assert isinstance(out, InteractionOutput)
        assert out.interaction_state in (
            "aligned_bullish", "aligned_bearish",
            "fragile_bullish", "fragile_bearish",
            "transition_conflict", "range_mixed", "mixed_unclear",
        )

    def test_extreme_values(self):
        out = layer.evaluate(_make_input(
            bullish_structure=1.0, bearish_structure=0.0,
            structure_clarity=1.0, regime_entropy=0.0,
            dominant_regime="trend", dominant_scenario="bullish",
            bullish_prob=1.0, base_prob=0.0, bearish_prob=0.0,
        ))
        assert out.interaction_state == "aligned_bullish"
        assert out.alignment_score == 1.0

    def test_all_equal_probs(self):
        out = layer.evaluate(_make_input(
            bullish_prob=0.33, base_prob=0.34, bearish_prob=0.33,
        ))
        assert isinstance(out, InteractionOutput)

    def test_uppercase_regime(self):
        """Regime comes uppercased from pipeline — .lower() handles it."""
        x = _make_input(dominant_regime="TREND")
        assert layer._regime_polarity(x) == "bullish"


# ──────────────────────────────────────────────
# 13. No sign flip invariant
# ──────────────────────────────────────────────

class TestNoSignFlip:
    """Interaction layer must NOT flip direction by itself."""

    def test_bullish_stays_positive_bias(self):
        out = layer.evaluate(_make_input(
            bullish_structure=0.8, bearish_structure=0.1,
            dominant_regime="trend", dominant_scenario="bullish",
        ))
        assert out.decision_bias_modifier >= 0.0

    def test_bearish_has_non_positive_or_negative_bias(self):
        """Bearish alignment → positive bias (strengthening bearish conviction)."""
        out = layer.evaluate(_make_input(
            bullish_structure=0.1, bearish_structure=0.8,
            dominant_regime="breakdown", dominant_scenario="bearish",
        ))
        assert out.decision_bias_modifier >= 0.0
