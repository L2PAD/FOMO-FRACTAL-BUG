"""
Scenario Engine Core Tests
============================
Tests for Block 3 scenario engine: types, builder, weighting, ranges.
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_input(**overrides) -> dict:
    """Create a ScenarioInput with sensible defaults."""
    base = {
        "momentum": 0.1,
        "volatility": 0.025,
        "ret_7d": 0.02,
        "ret_14d": 0.03,
        "median_return": 0.01,
        "std_return": 0.05,
        "p25_return": -0.04,
        "p75_return": 0.06,
        "mean_return": 0.01,
        "structure_bias": 0.1,
        "mode": "aligned",
        "regime_probs": {"trend": 0.35, "range": 0.30, "pullback": 0.15, "transition": 0.12, "breakdown": 0.08},
        "dominant_regime": "trend",
        "regime_entropy": 0.7,
        "decision_uncertainty": 0.4,
        "context_phase": "continuation",
    }
    base.update(overrides)
    return base


class TestScenarioTypes:
    def test_scenario_names(self):
        from forecast.scenario.scenario_types import SCENARIO_NAMES
        assert SCENARIO_NAMES == ["bullish", "base", "bearish"]

    def test_scenario_type_literals(self):
        from forecast.scenario.scenario_types import ScenarioType
        assert ScenarioType is not None


class TestScenarioBuilder:
    def test_centers_monotonic(self):
        """bullish > base > bearish always."""
        from forecast.scenario.scenario_builder import build_scenario_centers
        inp = _make_input()
        c = build_scenario_centers(inp)
        assert c["bullish"] > c["base"] > c["bearish"]

    def test_centers_with_strong_bullish_momentum(self):
        from forecast.scenario.scenario_builder import build_scenario_centers
        c = build_scenario_centers(_make_input(momentum=0.5))
        assert c["bullish"] > 3.0  # should be meaningfully positive

    def test_centers_with_strong_bearish_momentum(self):
        from forecast.scenario.scenario_builder import build_scenario_centers
        c = build_scenario_centers(_make_input(momentum=-0.5))
        assert c["bearish"] < -3.0  # should be meaningfully negative

    def test_centers_transition_compresses(self):
        """Transition regime should compress the spread."""
        from forecast.scenario.scenario_builder import build_scenario_centers
        c_trend = build_scenario_centers(_make_input(dominant_regime="trend"))
        c_trans = build_scenario_centers(_make_input(dominant_regime="transition"))
        spread_trend = c_trend["bullish"] - c_trend["bearish"]
        spread_trans = c_trans["bullish"] - c_trans["bearish"]
        assert spread_trans < spread_trend

    def test_centers_always_different(self):
        from forecast.scenario.scenario_builder import build_scenario_centers
        c = build_scenario_centers(_make_input())
        assert c["bullish"] != c["base"]
        assert c["base"] != c["bearish"]

    def test_centers_various_regimes(self):
        """Test all 5 regimes produce valid centers."""
        from forecast.scenario.scenario_builder import build_scenario_centers
        for regime in ["trend", "range", "pullback", "transition", "breakdown"]:
            c = build_scenario_centers(_make_input(dominant_regime=regime))
            assert c["bullish"] > c["base"] > c["bearish"], f"Failed for regime {regime}"


class TestScenarioWeighting:
    def test_probabilities_sum_to_one(self):
        from forecast.scenario.scenario_weighting import compute_scenario_weights
        w = compute_scenario_weights(_make_input())
        total = w["bullish"] + w["base"] + w["bearish"]
        assert abs(total - 1.0) < 0.001

    def test_bullish_momentum_boosts_bullish(self):
        from forecast.scenario.scenario_weighting import compute_scenario_weights
        w_bull = compute_scenario_weights(_make_input(momentum=0.6, structure_bias=0.3))
        w_bear = compute_scenario_weights(_make_input(momentum=-0.6, structure_bias=-0.3))
        assert w_bull["bullish"] > w_bear["bullish"]
        assert w_bear["bearish"] > w_bull["bearish"]

    def test_uncertainty_flattens_distribution(self):
        """High uncertainty → more uniform probabilities."""
        from forecast.scenario.scenario_weighting import compute_scenario_weights
        w_low_u = compute_scenario_weights(_make_input(decision_uncertainty=0.1))
        w_high_u = compute_scenario_weights(_make_input(decision_uncertainty=0.9))
        max_low = max(w_low_u["bullish"], w_low_u["base"], w_low_u["bearish"])
        max_high = max(w_high_u["bullish"], w_high_u["base"], w_high_u["bearish"])
        # High uncertainty should have lower max prob (more uniform)
        assert max_high < max_low

    def test_no_scenario_below_minimum(self):
        from forecast.scenario.scenario_weighting import compute_scenario_weights
        for regime in ["trend", "range", "pullback", "transition", "breakdown"]:
            w = compute_scenario_weights(_make_input(dominant_regime=regime))
            assert w["bullish"] >= 0.08
            assert w["base"] >= 0.08
            assert w["bearish"] >= 0.08

    def test_not_all_equal(self):
        """Scenarios should NOT all be ~33%."""
        from forecast.scenario.scenario_weighting import compute_scenario_weights
        w = compute_scenario_weights(_make_input(momentum=0.3))
        probs = [w["bullish"], w["base"], w["bearish"]]
        spread = max(probs) - min(probs)
        assert spread > 0.05, "Distribution too uniform, weighting may be broken"

    def test_no_regime_probs_fallback(self):
        """Without regime_probs, should still work via dominant regime."""
        from forecast.scenario.scenario_weighting import compute_scenario_weights
        w = compute_scenario_weights(_make_input(regime_probs=None))
        total = w["bullish"] + w["base"] + w["bearish"]
        assert abs(total - 1.0) < 0.001

    def test_regime_not_direct_mapping(self):
        """trend=0.7 should NOT produce bullish=0.7."""
        from forecast.scenario.scenario_weighting import compute_scenario_weights
        w = compute_scenario_weights(_make_input(
            regime_probs={"trend": 0.7, "range": 0.1, "pullback": 0.1, "transition": 0.05, "breakdown": 0.05},
            momentum=0.3,
        ))
        # bullish should be boosted but NOT 0.7
        assert w["bullish"] < 0.60, f"bullish={w['bullish']} is too close to trend prob"


class TestScenarioRanges:
    def test_ranges_ordered(self):
        """bearish_range < base_range < bullish_range."""
        from forecast.scenario.scenario_ranges import build_scenario_ranges
        centers = {"bullish": 6.0, "base": 1.0, "bearish": -4.0}
        weights = {"bullish": 0.3, "base": 0.45, "bearish": 0.25}
        r = build_scenario_ranges(centers, weights, 0.025, 0.05)
        assert r["bearish"][1] <= r["base"][0] + 0.5  # small overlap ok at boundary
        assert r["base"][1] <= r["bullish"][0] + 0.5

    def test_ranges_wider_with_uncertainty(self):
        from forecast.scenario.scenario_ranges import build_scenario_ranges
        centers = {"bullish": 6.0, "base": 1.0, "bearish": -4.0}
        weights = {"bullish": 0.3, "base": 0.45, "bearish": 0.25}
        r_low = build_scenario_ranges(centers, weights, 0.025, 0.05, decision_uncertainty=0.1)
        r_high = build_scenario_ranges(centers, weights, 0.025, 0.05, decision_uncertainty=0.9)
        spread_low = r_low["bullish"][1] - r_low["bearish"][0]
        spread_high = r_high["bullish"][1] - r_high["bearish"][0]
        assert spread_high > spread_low

    def test_ranges_non_degenerate(self):
        from forecast.scenario.scenario_ranges import build_scenario_ranges
        centers = {"bullish": 2.0, "base": 0.5, "bearish": -1.0}
        weights = {"bullish": 0.33, "base": 0.34, "bearish": 0.33}
        r = build_scenario_ranges(centers, weights, 0.025, 0.05)
        for s in ["bullish", "base", "bearish"]:
            assert r[s][1] > r[s][0], f"{s} range is degenerate"


class TestScenarioAssembler:
    def test_full_pipeline(self):
        from forecast.scenario.scenario_assembler import build_scenarios
        result = build_scenarios(_make_input())
        assert len(result["scenarios"]) == 3
        assert result["dominant"] in ["bullish", "base", "bearish"]
        probs = [s["probability"] for s in result["scenarios"]]
        assert abs(sum(probs) - 1.0) < 0.001

    def test_various_market_conditions(self):
        """Test multiple realistic conditions."""
        from forecast.scenario.scenario_assembler import build_scenarios
        conditions = [
            {"momentum": 0.5, "dominant_regime": "trend", "decision_uncertainty": 0.2},
            {"momentum": -0.3, "dominant_regime": "breakdown", "decision_uncertainty": 0.8},
            {"momentum": 0.0, "dominant_regime": "range", "decision_uncertainty": 0.5},
            {"momentum": 0.2, "dominant_regime": "pullback", "decision_uncertainty": 0.3},
            {"momentum": -0.1, "dominant_regime": "transition", "decision_uncertainty": 0.9},
        ]
        for cond in conditions:
            result = build_scenarios(_make_input(**cond))
            assert len(result["scenarios"]) == 3
            probs = [s["probability"] for s in result["scenarios"]]
            assert abs(sum(probs) - 1.0) < 0.001
            # Check monotonic centers
            centers = {s["type"]: s["expected_move"] for s in result["scenarios"]}
            assert centers["bullish"] > centers["base"] > centers["bearish"], \
                f"Centers not monotonic for {cond}: {centers}"

    def test_confidence_tags(self):
        """high_confidence / moderate / uncertain differentiation."""
        from forecast.scenario.scenario_assembler import build_scenarios
        # Low uncertainty + strong signal → high_confidence
        r1 = build_scenarios(_make_input(
            momentum=0.7, decision_uncertainty=0.15, structure_bias=0.4,
            regime_probs={"trend": 0.70, "range": 0.10, "pullback": 0.08, "transition": 0.07, "breakdown": 0.05},
            dominant_regime="trend", regime_entropy=0.35, context_phase="continuation",
        ))
        assert r1["confidence_tag"] == "high_confidence"
        # High uncertainty → uncertain
        r2 = build_scenarios(_make_input(
            momentum=0.0, decision_uncertainty=0.92, dominant_regime="transition",
            regime_entropy=0.92, context_phase="unstable_transition", structure_bias=-0.05,
            regime_probs={"trend": 0.18, "range": 0.22, "pullback": 0.10, "transition": 0.35, "breakdown": 0.15},
        ))
        assert r2["confidence_tag"] == "uncertain"

    def test_scenarios_have_narratives(self):
        from forecast.scenario.scenario_assembler import build_scenarios
        result = build_scenarios(_make_input())
        for s in result["scenarios"]:
            assert len(s["narrative"]) > 5

    def test_spread_positive(self):
        from forecast.scenario.scenario_assembler import build_scenarios
        result = build_scenarios(_make_input())
        assert result["spread"] > 0

    def test_variation_across_inputs(self):
        """Probabilities should vary meaningfully across different inputs."""
        from forecast.scenario.scenario_assembler import build_scenarios
        r1 = build_scenarios(_make_input(momentum=0.5, dominant_regime="trend"))
        r2 = build_scenarios(_make_input(momentum=-0.5, dominant_regime="breakdown"))
        p1 = {s["type"]: s["probability"] for s in r1["scenarios"]}
        p2 = {s["type"]: s["probability"] for s in r2["scenarios"]}
        # Should have different probability profiles
        assert abs(p1["bullish"] - p2["bullish"]) > 0.03
        assert abs(p1["bearish"] - p2["bearish"]) > 0.03


class TestScenarioEvaluator:
    def _build_case(self, overrides, real_move):
        from forecast.scenario.scenario_assembler import build_scenarios
        inp = _make_input(**overrides)
        ss = build_scenarios(inp)
        return {"scenarios": ss, "real_move_pct": real_move}

    def test_evaluate_batch(self):
        from forecast.scenario.scenario_evaluator import evaluate_scenario_set
        cases = [
            self._build_case({"momentum": 0.4, "dominant_regime": "trend", "decision_uncertainty": 0.2}, 5.0),
            self._build_case({"momentum": -0.3, "dominant_regime": "breakdown", "decision_uncertainty": 0.7}, -4.0),
            self._build_case({"momentum": 0.0, "dominant_regime": "range", "decision_uncertainty": 0.5}, 1.0),
        ]
        result = evaluate_scenario_set(cases)
        assert result["n"] == 3
        assert 0 <= result["coverage"]["total_hit_rate"] <= 1.0
        assert 0 <= result["direction_signal"]["dominant_direction_accuracy"] <= 1.0

    def test_evaluate_single(self):
        from forecast.scenario.scenario_assembler import build_scenarios
        from forecast.scenario.scenario_evaluator import evaluate_single
        ss = build_scenarios(_make_input(momentum=0.3, decision_uncertainty=0.2))
        result = evaluate_single(ss, 3.0)
        assert result["real_move_pct"] == 3.0
        assert result["real_direction"] == "UP"
        assert result["dominant"] in ["bullish", "base", "bearish"]
        assert isinstance(result["any_hit"], bool)

    def test_empty_cases(self):
        from forecast.scenario.scenario_evaluator import evaluate_scenario_set
        result = evaluate_scenario_set([])
        assert result["n"] == 0
        assert "error" in result

    def test_confidence_calibration_exists(self):
        from forecast.scenario.scenario_evaluator import evaluate_scenario_set
        cases = [
            self._build_case({"momentum": 0.6, "dominant_regime": "trend", "decision_uncertainty": 0.15,
                "structure_bias": 0.4, "regime_entropy": 0.35, "context_phase": "continuation",
                "regime_probs": {"trend": 0.7, "range": 0.1, "pullback": 0.08, "transition": 0.07, "breakdown": 0.05}}, 6.0),
            self._build_case({"momentum": -0.05, "dominant_regime": "transition", "decision_uncertainty": 0.92,
                "structure_bias": -0.05, "regime_entropy": 0.92, "context_phase": "unstable_transition",
                "regime_probs": {"trend": 0.18, "range": 0.22, "pullback": 0.10, "transition": 0.35, "breakdown": 0.15}}, 0.5),
        ]
        result = evaluate_scenario_set(cases)
        assert "confidence_calibration" in result
        # Should have at least 1 tag
        assert len(result["confidence_calibration"]) >= 1
