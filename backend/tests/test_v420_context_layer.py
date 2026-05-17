"""
Tests for v4.2.0 Market Context Layer
======================================
Validates:
  1. Feature builder produces valid [0,1] signals
  2. Phase classifier reaches all 7 phases
  3. Adjustment engine never modifies score (confidence-only mode)
  4. Adjustment engine respects safety caps
  5. Integration with backfill system
"""
import pytest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from forecast.context.context_feature_builder import build_context_features
from forecast.context.context_phase_classifier import classify_phase
from forecast.context.context_adjustment_engine import apply_context
from forecast.context.context_audit_builder import build_context_audit


# ═══════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════

@pytest.fixture
def base_features():
    return {"momentum": 0.03, "volatility": 0.03}


@pytest.fixture
def bullish_structure():
    return {
        "structure_bias_score": 0.7,
        "structure_trend_score": 0.6,
        "structure_momentum_score": 0.5,
        "structure_reversal_risk": 0.1,
        "structure_exhaustion_score": 0.1,
        "structure_stability_score": 0.85,
    }


@pytest.fixture
def aligned_multiscale():
    return {
        "major": {
            "structure_bias_score": 0.6,
            "structure_reversal_risk": 0.1,
            "structure_exhaustion_score": 0.1,
        },
        "minor": {
            "structure_bias_score": 0.5,
            "structure_reversal_risk": 0.12,
        },
        "mode": "aligned",
    }


PHASE_INPUTS = {
    "continuation": {
        "trend_strength": 0.50, "trend_persistence": 0.85,
        "trend_exhaustion": 0.10, "reversal_risk": 0.05,
        "drawdown_pressure": 0.0, "volatility_state": "normal",
    },
    "late_trend": {
        "trend_strength": 0.40, "trend_persistence": 0.6,
        "trend_exhaustion": 0.30, "reversal_risk": 0.12,
        "drawdown_pressure": 0.0, "volatility_state": "normal",
    },
    "pullback": {
        "trend_strength": 0.40, "trend_persistence": 0.8,
        "trend_exhaustion": 0.05, "reversal_risk": 0.05,
        "drawdown_pressure": 0.0, "volatility_state": "normal",
    },
    "breakdown": {
        "trend_strength": 0.10, "trend_persistence": 0.5,
        "trend_exhaustion": 0.1, "reversal_risk": 0.1,
        "drawdown_pressure": 0.50, "volatility_state": "expanded",
    },
    "recovery_attempt": {
        "trend_strength": 0.20, "trend_persistence": 0.6,
        "trend_exhaustion": 0.1, "reversal_risk": 0.1,
        "drawdown_pressure": 0.25, "volatility_state": "normal",
    },
    "unstable_transition": {
        "trend_strength": 0.10, "trend_persistence": 0.5,
        "trend_exhaustion": 0.1, "reversal_risk": 0.20,
        "drawdown_pressure": 0.1, "volatility_state": "normal",
    },
    "mixed_range": {
        "trend_strength": 0.20, "trend_persistence": 0.8,
        "trend_exhaustion": 0.1, "reversal_risk": 0.12,
        "drawdown_pressure": 0.1, "volatility_state": "compressed",
    },
}


# ═══════════════════════════════════════════════════════
# Feature Builder Tests
# ═══════════════════════════════════════════════════════

class TestContextFeatureBuilder:

    def test_output_keys(self, base_features, bullish_structure, aligned_multiscale):
        ctx = build_context_features(base_features, bullish_structure, aligned_multiscale)
        expected_keys = {
            "trend_strength", "trend_persistence", "trend_exhaustion",
            "reversal_risk", "drawdown_pressure", "volatility_state",
        }
        assert set(ctx.keys()) == expected_keys

    def test_numeric_values_in_range(self, base_features, bullish_structure, aligned_multiscale):
        ctx = build_context_features(base_features, bullish_structure, aligned_multiscale)
        for key in ["trend_strength", "trend_persistence", "trend_exhaustion",
                     "reversal_risk", "drawdown_pressure"]:
            assert 0.0 <= ctx[key] <= 1.0, f"{key}={ctx[key]} out of [0,1]"

    def test_volatility_state_categorical(self, base_features, bullish_structure, aligned_multiscale):
        ctx = build_context_features(base_features, bullish_structure, aligned_multiscale)
        assert ctx["volatility_state"] in ("compressed", "normal", "expanded")

    def test_volatility_compressed(self, bullish_structure, aligned_multiscale):
        ctx = build_context_features(
            {"momentum": 0.01, "volatility": 0.01},
            bullish_structure, aligned_multiscale,
        )
        assert ctx["volatility_state"] == "compressed"

    def test_volatility_expanded(self, bullish_structure, aligned_multiscale):
        ctx = build_context_features(
            {"momentum": 0.01, "volatility": 0.08},
            bullish_structure, aligned_multiscale,
        )
        assert ctx["volatility_state"] == "expanded"

    def test_zero_inputs(self):
        ctx = build_context_features(
            {"momentum": 0.0, "volatility": 0.0},
            {},
            {"major": {}, "minor": {}, "mode": "mixed_range"},
        )
        for key in ["trend_strength", "trend_persistence", "trend_exhaustion",
                     "reversal_risk", "drawdown_pressure"]:
            assert 0.0 <= ctx[key] <= 1.0


# ═══════════════════════════════════════════════════════
# Phase Classifier Tests
# ═══════════════════════════════════════════════════════

class TestContextPhaseClassifier:

    @pytest.mark.parametrize("expected_phase", list(PHASE_INPUTS.keys()))
    def test_phase_reachable(self, expected_phase):
        result = classify_phase(PHASE_INPUTS[expected_phase])
        assert result["market_phase"] == expected_phase

    def test_output_keys(self):
        result = classify_phase(PHASE_INPUTS["continuation"])
        assert "market_phase" in result
        assert "context_confidence" in result
        assert "flags" in result

    def test_context_confidence_range(self):
        for features in PHASE_INPUTS.values():
            result = classify_phase(features)
            assert 0.0 <= result["context_confidence"] <= 1.0

    def test_flags_not_empty(self):
        for features in PHASE_INPUTS.values():
            result = classify_phase(features)
            assert len(result["flags"]) > 0


# ═══════════════════════════════════════════════════════
# Adjustment Engine Tests
# ═══════════════════════════════════════════════════════

class TestContextAdjustmentEngine:

    @pytest.mark.parametrize("phase_name", list(PHASE_INPUTS.keys()))
    def test_score_never_changes(self, phase_name):
        """Core invariant: score_mult is always 1.0 (confidence-only mode)."""
        features = PHASE_INPUTS[phase_name]
        phase = classify_phase(features)
        for score in [-0.8, -0.3, -0.01, 0.0, 0.01, 0.3, 0.8]:
            result = apply_context(score, 0.5, 0.5, 1.0, features, phase)
            assert abs(result["score"] - round(score, 6)) < 1e-9, (
                f"Score changed for {phase_name}: {score} → {result['score']}"
            )

    @pytest.mark.parametrize("phase_name", list(PHASE_INPUTS.keys()))
    def test_output_keys(self, phase_name):
        features = PHASE_INPUTS[phase_name]
        phase = classify_phase(features)
        result = apply_context(0.3, 0.5, 0.5, 1.0, features, phase)
        assert "score" in result
        assert "conf_dir" in result
        assert "conf_tgt" in result
        assert "band_width" in result
        assert "adjustments" in result

    def test_continuation_boosts_confidence(self):
        features = PHASE_INPUTS["continuation"]
        phase = classify_phase(features)
        result = apply_context(0.3, 0.5, 0.5, 1.0, features, phase)
        assert result["conf_dir"] >= 0.5  # boosted
        assert result["band_width"] <= 1.0  # tightened

    def test_unstable_transition_reduces_confidence(self):
        features = PHASE_INPUTS["unstable_transition"]
        phase = classify_phase(features)
        result = apply_context(0.3, 0.5, 0.5, 1.0, features, phase)
        assert result["conf_dir"] < 0.5  # reduced
        assert result["band_width"] > 1.0  # widened

    def test_caps_respected(self):
        """All multipliers must stay within safety caps."""
        for phase_name, features in PHASE_INPUTS.items():
            phase = classify_phase(features)
            result = apply_context(0.3, 0.5, 0.5, 1.0, features, phase)
            adj = result["adjustments"]
            assert 0.90 <= adj["score_mult"] <= 1.08
            assert 0.80 <= adj["conf_dir_mult"] <= 1.10
            assert 0.80 <= adj["conf_tgt_mult"] <= 1.10
            assert 0.90 <= adj["band_mult"] <= 1.25


# ═══════════════════════════════════════════════════════
# Audit Builder Tests
# ═══════════════════════════════════════════════════════

class TestContextAuditBuilder:

    def test_audit_structure(self):
        features = PHASE_INPUTS["continuation"]
        phase = classify_phase(features)
        adj = apply_context(0.3, 0.5, 0.5, 1.0, features, phase)
        audit = build_context_audit(features, phase, adj)
        assert "market_context" in audit
        assert "context_phase" in audit
        assert "context_adjustments" in audit
        assert audit["context_phase"]["market_phase"] == "continuation"
