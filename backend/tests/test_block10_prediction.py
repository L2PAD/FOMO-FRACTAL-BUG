"""
Block 10.1 — Prediction Output Layer Tests
============================================
Tests for prediction_formatter.py and API endpoint.
"""

import pytest
from exchange.output.prediction_formatter import (
    _map_direction,
    _map_uncertainty,
    _format_horizon_1d_7d,
    _format_horizon_30d,
)


# ── Direction Mapping ──

class TestMapDirection:
    def test_strong_bull(self):
        assert _map_direction("STRONG_BULL") == "bullish"

    def test_mild_bull(self):
        assert _map_direction("MILD_BULL") == "bullish"

    def test_strong_bear(self):
        assert _map_direction("STRONG_BEAR") == "bearish"

    def test_mild_bear(self):
        assert _map_direction("MILD_BEAR") == "bearish"

    def test_neutral(self):
        assert _map_direction("NEUTRAL") == "neutral"

    def test_none(self):
        assert _map_direction(None) == "neutral"

    def test_lowercase(self):
        assert _map_direction("strong_bull") == "bullish"


# ── Uncertainty Mapping ──

class TestMapUncertainty:
    def test_high_confidence_low_uncertainty(self):
        assert _map_uncertainty(0.70) == "low"

    def test_medium_confidence_medium_uncertainty(self):
        assert _map_uncertainty(0.50) == "medium"

    def test_low_confidence_high_uncertainty(self):
        assert _map_uncertainty(0.25) == "high"

    def test_none_high_uncertainty(self):
        assert _map_uncertainty(None) == "high"

    def test_boundary_060(self):
        assert _map_uncertainty(0.60) == "low"

    def test_boundary_040(self):
        assert _map_uncertainty(0.40) == "medium"


# ── 1D/7D Formatter ──

class TestFormat1D7D:
    def test_basic_format(self):
        doc = {
            "directionClass": "MILD_BULL",
            "confidenceDirection": 0.55,
            "confidence": 0.50,
            "entryPrice": 70000.0,
            "targetPrice": 72000.0,
            "expectedMovePct": 2.86,
            "audit": {"regime": "TREND"},
            "modelVersion": "v4.1.3",
            "createdBucket": "2026-03-20_06h",
        }
        result = _format_horizon_1d_7d(doc)
        assert result["direction"] == "bullish"
        assert result["confidence"] == 0.55
        assert result["uncertainty"] == "medium"
        assert result["entry_price"] == 70000.0
        assert result["target_price"] == 72000.0
        assert result["regime"] == "TREND"

    def test_missing_fields(self):
        doc = {}
        result = _format_horizon_1d_7d(doc)
        assert result["direction"] == "neutral"
        assert result["confidence"] == 0.0
        assert result["uncertainty"] == "high"


# ── 30D Formatter ──

class TestFormat30D:
    def test_with_v2_scenarios(self):
        doc = {
            "directionClass": "NEUTRAL",
            "confidenceDirection": 0.45,
            "entryPrice": 100000.0,
            "targetPrice": 99000.0,
            "expectedMovePct": -1.0,
            "audit": {"regime": "RANGE"},
            "modelVersion": "v4.1.3",
            "createdBucket": "2026-03-20",
            "scenarios": {
                "scenarios": [
                    {
                        "type": "bullish", "probability": 0.57,
                        "path_type": "continuation", "confidence_tag": "strong",
                        "target_low": 103000, "target_high": 112000,
                        "narrative": "Trend continuation"
                    },
                    {
                        "type": "base", "probability": 0.28,
                        "path_type": "range_hold", "confidence_tag": "moderate",
                        "target_low": 96000, "target_high": 104000,
                        "narrative": "Range-bound"
                    },
                    {
                        "type": "bearish", "probability": 0.15,
                        "path_type": "distribution", "confidence_tag": "uncertain",
                        "target_low": 88000, "target_high": 97000,
                        "narrative": "Downside risk"
                    },
                ],
                "dominant": "bullish",
                "confidence_tag": "strong",
                "engine_version": "v2",
            },
        }
        result = _format_horizon_30d(doc)
        assert result["direction"] == "neutral"
        assert result["dominant"] == "bullish"
        assert result["probabilities"]["bullish"] == 0.57
        assert result["probabilities"]["base"] == 0.28
        assert result["probabilities"]["bearish"] == 0.15
        assert result["path"] == "continuation"
        assert result["engine_version"] == "v2"
        assert len(result["scenario_details"]) == 3

    def test_sum_of_probabilities(self):
        doc = {
            "directionClass": "MILD_BULL",
            "confidenceDirection": 0.50,
            "scenarios": {
                "scenarios": [
                    {"type": "bullish", "probability": 0.50},
                    {"type": "base", "probability": 0.30},
                    {"type": "bearish", "probability": 0.20},
                ],
                "dominant": "bullish",
            },
        }
        result = _format_horizon_30d(doc)
        total = sum(result["probabilities"].values())
        assert abs(total - 1.0) < 0.01

    def test_without_scenarios(self):
        doc = {
            "directionClass": "MILD_BEAR",
            "confidenceDirection": 0.45,
        }
        result = _format_horizon_30d(doc)
        assert result["direction"] == "bearish"
        assert "probabilities" not in result
        assert "dominant" not in result

    def test_v1_scenarios_null_fields(self):
        doc = {
            "directionClass": "NEUTRAL",
            "confidenceDirection": 0.35,
            "scenarios": {
                "scenarios": [
                    {"type": "bullish", "probability": 0.33},
                    {"type": "base", "probability": 0.34},
                    {"type": "bearish", "probability": 0.33},
                ],
                "dominant": "base",
            },
        }
        result = _format_horizon_30d(doc)
        assert result["dominant"] == "base"
        assert result["engine_version"] == "v1"
        # V1 scenarios don't have path_type
        for detail in result["scenario_details"]:
            assert detail["path_type"] is None


# ── Output Consistency ──

class TestOutputConsistency:
    def test_direction_vs_dominant_consistency(self):
        """30D: direction comes from model, dominant from scenarios — they can diverge."""
        doc = {
            "directionClass": "NEUTRAL",
            "confidenceDirection": 0.45,
            "scenarios": {
                "scenarios": [
                    {"type": "bullish", "probability": 0.57},
                    {"type": "base", "probability": 0.28},
                    {"type": "bearish", "probability": 0.15},
                ],
                "dominant": "bullish",
            },
        }
        result = _format_horizon_30d(doc)
        # It's valid for direction to differ from dominant
        # direction = model's overall direction, dominant = scenario probability leader
        assert result["direction"] == "neutral"
        assert result["dominant"] == "bullish"
