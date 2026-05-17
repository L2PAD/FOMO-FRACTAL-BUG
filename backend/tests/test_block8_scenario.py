"""Block 8.3 — Scenario Probability Calibration Tests"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from exchange.calibration.scenario_calibrator import (
    label_scenario_outcome,
    compute_scenario_reliability,
    calibrate_scenario_probs,
    build_calibration_map,
    SCENARIO_THRESHOLDS,
)


class TestOutcomeLabeling:
    """Scenario outcome labeling."""

    def test_bullish_move_30d(self):
        assert label_scenario_outcome(8.0, None, "30D") == "bullish"

    def test_bearish_move_30d(self):
        assert label_scenario_outcome(-7.0, None, "30D") == "bearish"

    def test_base_move_30d(self):
        assert label_scenario_outcome(2.0, None, "30D") == "base"

    def test_bullish_move_7d(self):
        assert label_scenario_outcome(4.0, None, "7D") == "bullish"

    def test_bearish_move_7d(self):
        assert label_scenario_outcome(-4.0, None, "7D") == "bearish"

    def test_base_move_7d(self):
        assert label_scenario_outcome(1.0, None, "7D") == "base"

    def test_explicit_scenario_ranges(self):
        scenarios = {
            "scenarios": [
                {"type": "bullish", "range": [5.0, 15.0]},
                {"type": "base", "range": [-5.0, 5.0]},
                {"type": "bearish", "range": [-15.0, -5.0]},
            ]
        }
        assert label_scenario_outcome(7.0, scenarios, "30D") == "bullish"
        assert label_scenario_outcome(0.0, scenarios, "30D") == "base"
        assert label_scenario_outcome(-10.0, scenarios, "30D") == "bearish"

    def test_edge_case_at_threshold(self):
        assert label_scenario_outcome(5.0, None, "30D") == "bullish"
        assert label_scenario_outcome(-5.0, None, "30D") == "bearish"


class TestReliability:
    """Scenario reliability analysis."""

    def test_empty_dataset(self):
        result = compute_scenario_reliability([])
        assert result.get("status") == "INSUFFICIENT_DATA"

    def test_balanced_dataset(self):
        dataset = [
            {"rawProbs": {"bullish": 0.33, "base": 0.34, "bearish": 0.33}, "realized": "bullish"},
            {"rawProbs": {"bullish": 0.33, "base": 0.34, "bearish": 0.33}, "realized": "base"},
            {"rawProbs": {"bullish": 0.33, "base": 0.34, "bearish": 0.33}, "realized": "bearish"},
        ]
        result = compute_scenario_reliability(dataset)
        assert result["sampleSize"] == 3
        assert result["brierScore"] is not None
        assert "outcomeDistribution" in result

    def test_brier_score_perfect(self):
        dataset = [
            {"rawProbs": {"bullish": 1.0, "base": 0.0, "bearish": 0.0}, "realized": "bullish"},
            {"rawProbs": {"bullish": 0.0, "base": 1.0, "bearish": 0.0}, "realized": "base"},
        ]
        result = compute_scenario_reliability(dataset)
        assert result["brierScore"] == 0.0

    def test_brier_score_worst(self):
        dataset = [
            {"rawProbs": {"bullish": 0.0, "base": 0.0, "bearish": 1.0}, "realized": "bullish"},
        ]
        result = compute_scenario_reliability(dataset)
        assert result["brierScore"] == 2.0  # (0-1)^2 + (0-0)^2 + (1-0)^2 = 2


class TestCalibration:
    """Calibration and renormalization."""

    def test_renormalization_sums_to_one(self):
        cal_map = {
            "status": "OK",
            "anchors": {
                "bullish": [(0.0, 0.0), (0.5, 0.3), (1.0, 1.0)],
                "base": [(0.0, 0.0), (0.5, 0.4), (1.0, 1.0)],
                "bearish": [(0.0, 0.0), (0.5, 0.3), (1.0, 1.0)],
            },
        }
        raw = {"bullish": 0.3, "base": 0.4, "bearish": 0.3}
        cal = calibrate_scenario_probs(raw, cal_map)
        total = sum(cal.values())
        assert abs(total - 1.0) < 0.01

    def test_no_calibration_map(self):
        raw = {"bullish": 0.3, "base": 0.4, "bearish": 0.3}
        cal = calibrate_scenario_probs(raw, None)
        assert cal == raw

    def test_calibration_preserves_order(self):
        cal_map = {
            "status": "OK",
            "anchors": {
                "bullish": [(0.0, 0.0), (1.0, 1.0)],
                "base": [(0.0, 0.0), (1.0, 1.0)],
                "bearish": [(0.0, 0.0), (1.0, 1.0)],
            },
        }
        raw = {"bullish": 0.2, "base": 0.5, "bearish": 0.3}
        cal = calibrate_scenario_probs(raw, cal_map)
        assert cal["base"] >= cal["bullish"]
        assert cal["base"] >= cal["bearish"]

    def test_insufficient_data_map(self):
        dataset = [
            {"rawProbs": {"bullish": 0.33, "base": 0.34, "bearish": 0.33}, "realized": "bullish"},
        ] * 5
        cal_map = build_calibration_map(dataset)
        assert cal_map["status"] == "INSUFFICIENT_DATA"
