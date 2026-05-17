"""
Block 10.2 — Execution Adapter Tests
======================================
Tests for execution_adapter.py derivation logic.
"""

import pytest
from exchange.output.execution_adapter import (
    _derive_bias,
    _derive_strength,
    _derive_risk_mode,
    _derive_timing_quality,
    _derive_execution_hint,
    _build_reasons,
)


# ── Bias ──

class TestDeriveBias:
    def test_bullish_consensus_good_agreement(self):
        assert _derive_bias({"consensus_direction": "bullish", "horizon_agreement": 0.67, "avg_confidence": 0.35}) == "bullish"

    def test_bearish_consensus_good_agreement(self):
        assert _derive_bias({"consensus_direction": "bearish", "horizon_agreement": 0.67, "avg_confidence": 0.35}) == "bearish"

    def test_low_agreement_forces_neutral(self):
        assert _derive_bias({"consensus_direction": "bullish", "horizon_agreement": 0.33, "avg_confidence": 0.35}) == "neutral"

    def test_low_confidence_forces_neutral(self):
        assert _derive_bias({"consensus_direction": "bullish", "horizon_agreement": 0.67, "avg_confidence": 0.15}) == "neutral"

    def test_neutral_stays_neutral(self):
        assert _derive_bias({"consensus_direction": "neutral", "horizon_agreement": 1.0, "avg_confidence": 0.50}) == "neutral"


# ── Strength ──

class TestDeriveStrength:
    def test_high_strength(self):
        s = _derive_strength(
            {"avg_confidence": 0.65, "horizon_agreement": 1.0},
            {"probabilities": {"bullish": 0.70, "base": 0.20, "bearish": 0.10}},
        )
        assert s > 0.50

    def test_low_strength(self):
        s = _derive_strength(
            {"avg_confidence": 0.20, "horizon_agreement": 0.33},
            {"probabilities": {"bullish": 0.34, "base": 0.33, "bearish": 0.33}},
        )
        assert s < 0.40

    def test_no_30d(self):
        s = _derive_strength({"avg_confidence": 0.40, "horizon_agreement": 0.67}, None)
        assert 0.0 <= s <= 1.0

    def test_bounded(self):
        s = _derive_strength({"avg_confidence": 1.0, "horizon_agreement": 1.0}, {"probabilities": {"bullish": 1.0}})
        assert s <= 1.0


# ── Risk Mode ──

class TestDeriveRiskMode:
    def test_defensive_on_high_uncertainty(self):
        horizons = {
            "24H": {"uncertainty": "high"},
            "7D": {"uncertainty": "high"},
            "30D": {"uncertainty": "medium", "path": "range_hold", "dominant": "base"},
        }
        assert _derive_risk_mode(horizons) == "defensive"

    def test_defensive_on_breakdown_path(self):
        horizons = {
            "24H": {"uncertainty": "medium"},
            "7D": {"uncertainty": "low"},
            "30D": {"uncertainty": "medium", "path": "breakdown", "dominant": "bearish"},
        }
        assert _derive_risk_mode(horizons) == "defensive"

    def test_normal_on_low_uncertainty_continuation(self):
        horizons = {
            "24H": {"uncertainty": "low"},
            "7D": {"uncertainty": "low"},
            "30D": {"uncertainty": "medium", "path": "continuation", "dominant": "bullish"},
        }
        assert _derive_risk_mode(horizons) == "normal"

    def test_cautious_default(self):
        horizons = {
            "24H": {"uncertainty": "medium"},
            "7D": {"uncertainty": "low"},
            "30D": {"uncertainty": "medium", "path": "range_hold", "dominant": "base"},
        }
        assert _derive_risk_mode(horizons) == "cautious"


# ── Timing Quality ──

class TestDeriveTimingQuality:
    def test_low_on_high_uncertainty(self):
        summary = {"horizon_agreement": 0.67, "avg_confidence": 0.40}
        horizons = {
            "24H": {"uncertainty": "high"},
            "7D": {"uncertainty": "high"},
            "30D": {"uncertainty": "high", "dominant": "base"},
        }
        assert _derive_timing_quality(summary, horizons) == "low"

    def test_low_on_poor_agreement(self):
        summary = {"horizon_agreement": 0.33, "avg_confidence": 0.50}
        horizons = {
            "24H": {"uncertainty": "low"},
            "7D": {"uncertainty": "low"},
            "30D": {"uncertainty": "low", "dominant": "bullish"},
        }
        assert _derive_timing_quality(summary, horizons) == "low"

    def test_high_on_strong_setup(self):
        summary = {"horizon_agreement": 0.67, "avg_confidence": 0.55}
        horizons = {
            "24H": {"uncertainty": "low"},
            "7D": {"uncertainty": "medium"},
            "30D": {"uncertainty": "low", "dominant": "bullish"},
        }
        assert _derive_timing_quality(summary, horizons) == "high"

    def test_medium_default(self):
        summary = {"horizon_agreement": 0.67, "avg_confidence": 0.35}
        horizons = {
            "24H": {"uncertainty": "medium"},
            "7D": {"uncertainty": "low"},
            "30D": {"uncertainty": "medium", "dominant": "base"},
        }
        assert _derive_timing_quality(summary, horizons) == "medium"


# ── Execution Hint ──

class TestDeriveExecutionHint:
    def test_wait_on_defensive(self):
        assert _derive_execution_hint("defensive", "medium", 0.50) == "wait"

    def test_wait_on_low_timing(self):
        assert _derive_execution_hint("cautious", "low", 0.50) == "wait"

    def test_allow_on_good_setup(self):
        assert _derive_execution_hint("normal", "high", 0.50) == "allow"

    def test_allow_reduced_default(self):
        assert _derive_execution_hint("cautious", "medium", 0.40) == "allow_reduced"

    def test_allow_reduced_when_normal_but_medium_timing(self):
        assert _derive_execution_hint("normal", "medium", 0.50) == "allow_reduced"


# ── Reasons ──

class TestBuildReasons:
    def test_includes_30d_dominant(self):
        reasons = _build_reasons(
            {"horizon_agreement": 0.67},
            {"30D": {"dominant": "bullish", "path": "continuation", "uncertainty": "low"},
             "7D": {"direction": "bullish"}, "24H": {"direction": "bullish"}},
            "bullish", "normal",
        )
        assert any("30D bullish-dominant" in r for r in reasons)

    def test_includes_path(self):
        reasons = _build_reasons(
            {"horizon_agreement": 0.67},
            {"30D": {"dominant": "base", "path": "range_hold", "uncertainty": "medium"},
             "7D": {"direction": "neutral"}, "24H": {"direction": "bullish"}},
            "neutral", "cautious",
        )
        assert any("range_hold" in r for r in reasons)


# ── Consistency: prediction ↔ execution ──

class TestPredictionExecutionConsistency:
    def test_bullish_prediction_not_bearish_execution(self):
        """If prediction consensus is bullish with decent agreement, execution bias should not be bearish."""
        summary = {"consensus_direction": "bullish", "horizon_agreement": 0.67, "avg_confidence": 0.40}
        bias = _derive_bias(summary)
        assert bias != "bearish"

    def test_bearish_prediction_not_bullish_execution(self):
        summary = {"consensus_direction": "bearish", "horizon_agreement": 0.67, "avg_confidence": 0.40}
        bias = _derive_bias(summary)
        assert bias != "bullish"
