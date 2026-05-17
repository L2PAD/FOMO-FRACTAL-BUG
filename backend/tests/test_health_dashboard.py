"""
Exchange Health Metrics Tests — Stabilization Dashboard
========================================================
Tests for the 3-metric monitoring system.
"""

import pytest
from exchange.monitoring.health_metrics import (
    _compute_base_dominance,
    _compute_scenario_truthfulness,
    _compute_catastrophic_rate,
    _compute_overall_status,
)


# ── Base Dominance ──

class TestBaseDominance:
    def test_no_30d_forecasts(self):
        result = _compute_base_dominance([{"horizon": "7D"}])
        assert result["status"] == "no_data"

    def test_all_base(self):
        forecasts = [
            {"horizon": "30D", "scenarios": {"dominant": "base"}},
            {"horizon": "30D", "scenarios": {"dominant": "base"}},
        ]
        result = _compute_base_dominance(forecasts)
        assert result["rate"] == 1.0
        assert result["status"] == "problem"

    def test_no_base(self):
        forecasts = [
            {"horizon": "30D", "scenarios": {"dominant": "bullish"}},
            {"horizon": "30D", "scenarios": {"dominant": "bearish"}},
        ]
        result = _compute_base_dominance(forecasts)
        assert result["rate"] == 0.0
        assert result["status"] == "ok"

    def test_mixed_ok(self):
        forecasts = [
            {"horizon": "30D", "scenarios": {"dominant": "bullish"}},
            {"horizon": "30D", "scenarios": {"dominant": "base"}},
            {"horizon": "30D", "scenarios": {"dominant": "bearish"}},
        ]
        result = _compute_base_dominance(forecasts)
        assert abs(result["rate"] - 0.3333) < 0.01
        assert result["status"] == "ok"

    def test_watch_threshold(self):
        # 5 out of 10 = 50% → watch
        forecasts = [
            {"horizon": "30D", "scenarios": {"dominant": "base"}} for _ in range(5)
        ] + [
            {"horizon": "30D", "scenarios": {"dominant": "bullish"}} for _ in range(5)
        ]
        result = _compute_base_dominance(forecasts)
        assert result["status"] == "watch"


# ── Scenario Truthfulness ──

class TestScenarioTruthfulness:
    def test_no_evaluated(self):
        result = _compute_scenario_truthfulness([{"horizon": "7D"}])
        assert result["status"] == "no_data"

    def test_correct_prediction(self):
        forecasts = [{
            "evaluated": True,
            "horizon": "7D",
            "outcome": {"actualPriceAtEval": 105},
            "entryPrice": 100,
            "scenarios": {"dominant": "bullish"},
        }]
        result = _compute_scenario_truthfulness(forecasts)
        assert result["correct"] == 1
        assert result["rate"] == 1.0

    def test_wrong_prediction(self):
        forecasts = [{
            "evaluated": True,
            "horizon": "7D",
            "outcome": {"actualPriceAtEval": 92},
            "entryPrice": 100,
            "scenarios": {"dominant": "bullish"},
        }]
        result = _compute_scenario_truthfulness(forecasts)
        assert result["correct"] == 0

    def test_no_data_when_zero_total(self):
        forecasts = [{
            "evaluated": True,
            "outcome": {"something": True},
            # No scenarios or missing prices
        }]
        result = _compute_scenario_truthfulness(forecasts)
        assert result["status"] == "no_data"


# ── Catastrophic Rate ──

class TestCatastrophicRate:
    def test_long_big_drop(self):
        forecasts = [{
            "evaluated": True,
            "direction": "LONG",
            "horizon": "7D",
            "entryPrice": 100,
            "outcome": {"actualPriceAtEval": 90},
        }]
        result = _compute_catastrophic_rate(forecasts)
        assert result["count"] == 1
        assert result["rate"] == 1.0
        assert result["status"] == "problem"

    def test_long_small_gain(self):
        forecasts = [{
            "evaluated": True,
            "direction": "LONG",
            "horizon": "7D",
            "entryPrice": 100,
            "outcome": {"actualPriceAtEval": 102},
        }]
        result = _compute_catastrophic_rate(forecasts)
        assert result["count"] == 0
        assert result["status"] == "ok"

    def test_no_evaluated(self):
        result = _compute_catastrophic_rate([{"horizon": "7D"}])
        assert result["status"] == "no_data"


# ── Overall Status ──

class TestOverallStatus:
    def test_stable(self):
        assert _compute_overall_status(
            {"status": "ok"}, {"status": "ok"}, {"status": "ok"}
        ) == "STABLE"

    def test_warning_one_problem(self):
        assert _compute_overall_status(
            {"status": "ok"}, {"status": "problem"}, {"status": "ok"}
        ) == "WARNING"

    def test_unstable_two_problems(self):
        assert _compute_overall_status(
            {"status": "problem"}, {"status": "problem"}, {"status": "ok"}
        ) == "UNSTABLE"

    def test_no_data_ignored(self):
        assert _compute_overall_status(
            {"status": "ok"}, {"status": "no_data"}, {"status": "ok"}
        ) == "STABLE"

    def test_warning_two_watches(self):
        assert _compute_overall_status(
            {"status": "watch"}, {"status": "watch"}, {"status": "ok"}
        ) == "WARNING"
