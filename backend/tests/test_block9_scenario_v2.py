"""
Block 9 — Scenario Engine V2: Phase 1 Sanity Tests
=====================================================
3 mandatory cases:
  Case 1 — Strong Trend: bullish dominates, base < 0.35, path = continuation/grind_up
  Case 2 — High Entropy: base grows, path = range_hold, confidence ↓
  Case 3 — Breakdown: bearish grows, path = breakdown/distribution
"""

import pytest
from forecast.scenario.engine_v2 import ScenarioEngineV2, TruthInputs, ScenarioNode


@pytest.fixture
def engine():
    return ScenarioEngineV2(temperature=0.9, calibrator=None)


# ── Case 1: Strong Trend ──

def _make_strong_trend() -> TruthInputs:
    return TruthInputs(
        asset="BTC",
        horizon="30D",
        spot_price=100000.0,
        direction="bull",
        calibrated_confidence=0.65,
        regime_probs={"trend": 0.72, "range": 0.08, "pullback": 0.10, "transition": 0.05, "breakdown": 0.05},
        dominant_regime="trend",
        regime_entropy=0.25,
        regime_gap=0.62,
        structure_strength=0.80,
        bullish_structure=0.85,
        bearish_structure=0.10,
        context_alignment=0.75,
        negative_context=0.05,
        volatility_norm=0.40,
        expected_move_pct=0.08,
        range_state_score=0.15,
        drawdown_pressure=0.05,
    )


def test_case1_strong_trend_bullish_dominates(engine):
    truth = _make_strong_trend()
    result = engine.build(truth)

    scenarios = result["scenarios"]
    dominant = result["dominant"]

    assert dominant == "bullish", f"Expected bullish dominant, got {dominant}"
    probs = {s["type"]: s["probability"] for s in scenarios}
    assert probs["bullish"] > probs["base"], "Bullish should beat base"
    assert probs["bullish"] > probs["bearish"], "Bullish should beat bearish"


def test_case1_strong_trend_base_below_035(engine):
    truth = _make_strong_trend()
    result = engine.build(truth)

    probs = {s["type"]: s["probability"] for s in result["scenarios"]}
    assert probs["base"] < 0.35, f"Base should be < 0.35, got {probs['base']:.4f}"


def test_case1_strong_trend_path(engine):
    truth = _make_strong_trend()
    result = engine.build(truth)

    bull_scenario = next(s for s in result["scenarios"] if s["type"] == "bullish")
    assert bull_scenario["path_type"] in ("continuation", "grind_up"), \
        f"Expected continuation/grind_up, got {bull_scenario['path_type']}"


def test_case1_strong_trend_confidence_tag(engine):
    truth = _make_strong_trend()
    result = engine.build(truth)

    bull_scenario = next(s for s in result["scenarios"] if s["type"] == "bullish")
    assert bull_scenario["confidence_tag"] in ("strong", "moderate"), \
        f"Expected strong/moderate, got {bull_scenario['confidence_tag']}"


# ── Case 2: High Entropy ──

def _make_high_entropy() -> TruthInputs:
    return TruthInputs(
        asset="ETH",
        horizon="30D",
        spot_price=3500.0,
        direction="neutral",
        calibrated_confidence=0.40,
        regime_probs={"trend": 0.18, "range": 0.35, "pullback": 0.15, "transition": 0.22, "breakdown": 0.10},
        dominant_regime="range",
        regime_entropy=0.75,
        regime_gap=0.13,
        structure_strength=0.45,
        bullish_structure=0.35,
        bearish_structure=0.30,
        context_alignment=0.30,
        negative_context=0.20,
        volatility_norm=0.50,
        expected_move_pct=0.05,
        range_state_score=0.65,
        drawdown_pressure=0.15,
    )


def test_case2_high_entropy_base_grows(engine):
    truth = _make_high_entropy()
    result = engine.build(truth)

    probs = {s["type"]: s["probability"] for s in result["scenarios"]}
    # Base should be competitive (not dominated by either direction)
    assert probs["base"] >= 0.30, f"Base should be >= 0.30 in high entropy, got {probs['base']:.4f}"


def test_case2_high_entropy_path(engine):
    truth = _make_high_entropy()
    result = engine.build(truth)

    base_scenario = next(s for s in result["scenarios"] if s["type"] == "base")
    assert base_scenario["path_type"] == "range_hold", \
        f"Expected range_hold, got {base_scenario['path_type']}"


def test_case2_high_entropy_no_strong_confidence(engine):
    truth = _make_high_entropy()
    result = engine.build(truth)

    # No scenario should be "strong" in high entropy
    for s in result["scenarios"]:
        assert s["confidence_tag"] != "strong", \
            f"No scenario should be 'strong' in high entropy, but {s['type']} is"


def test_case2_high_entropy_spread_low(engine):
    truth = _make_high_entropy()
    result = engine.build(truth)

    probs = {s["type"]: s["probability"] for s in result["scenarios"]}
    spread = max(probs.values()) - min(probs.values())
    # Spread should be moderate, not huge
    assert spread < 0.30, f"Spread should be < 0.30 in high entropy, got {spread:.4f}"


# ── Case 3: Breakdown ──

def _make_breakdown() -> TruthInputs:
    return TruthInputs(
        asset="SOL",
        horizon="30D",
        spot_price=150.0,
        direction="bear",
        calibrated_confidence=0.55,
        regime_probs={"trend": 0.05, "range": 0.08, "pullback": 0.07, "transition": 0.15, "breakdown": 0.65},
        dominant_regime="breakdown",
        regime_entropy=0.30,
        regime_gap=0.50,
        structure_strength=0.30,
        bullish_structure=0.10,
        bearish_structure=0.80,
        context_alignment=0.10,
        negative_context=0.75,
        volatility_norm=0.85,
        expected_move_pct=0.12,
        range_state_score=0.10,
        drawdown_pressure=0.70,
    )


def test_case3_breakdown_bearish_dominates(engine):
    truth = _make_breakdown()
    result = engine.build(truth)

    dominant = result["dominant"]
    assert dominant == "bearish", f"Expected bearish dominant, got {dominant}"

    probs = {s["type"]: s["probability"] for s in result["scenarios"]}
    assert probs["bearish"] > probs["bullish"], "Bearish should beat bullish"


def test_case3_breakdown_path(engine):
    truth = _make_breakdown()
    result = engine.build(truth)

    bear_scenario = next(s for s in result["scenarios"] if s["type"] == "bearish")
    assert bear_scenario["path_type"] in ("breakdown", "distribution", "flush_then_recover"), \
        f"Expected breakdown/distribution/flush_then_recover, got {bear_scenario['path_type']}"


def test_case3_breakdown_bearish_high_prob(engine):
    truth = _make_breakdown()
    result = engine.build(truth)

    probs = {s["type"]: s["probability"] for s in result["scenarios"]}
    assert probs["bearish"] > 0.35, f"Bearish should be > 0.35, got {probs['bearish']:.4f}"


def test_case3_breakdown_base_suppressed(engine):
    truth = _make_breakdown()
    result = engine.build(truth)

    probs = {s["type"]: s["probability"] for s in result["scenarios"]}
    assert probs["base"] < 0.35, f"Base should be < 0.35 in breakdown, got {probs['base']:.4f}"


# ── Output Format Tests ──

def test_output_format_complete(engine):
    truth = _make_strong_trend()
    result = engine.build(truth)

    assert "scenarios" in result
    assert "dominant" in result
    assert "spread" in result
    assert "confidence_tag" in result
    assert "engine_version" in result
    assert result["engine_version"] == "v2"

    for s in result["scenarios"]:
        assert "type" in s
        assert "probability" in s
        assert "range" in s
        assert "target_low" in s
        assert "target_high" in s
        assert "expected_move" in s
        assert "path_type" in s
        assert "confidence_tag" in s
        assert "narrative" in s


def test_probabilities_sum_to_one(engine):
    for make_fn in [_make_strong_trend, _make_high_entropy, _make_breakdown]:
        truth = make_fn()
        result = engine.build(truth)
        total = sum(s["probability"] for s in result["scenarios"])
        assert abs(total - 1.0) < 0.01, f"Probabilities should sum to ~1.0, got {total:.4f}"


def test_ranges_are_sane(engine):
    for make_fn in [_make_strong_trend, _make_high_entropy, _make_breakdown]:
        truth = make_fn()
        result = engine.build(truth)

        for s in result["scenarios"]:
            if s["type"] == "bullish":
                assert s["target_low"] >= truth.spot_price, \
                    f"Bullish target_low ({s['target_low']}) should be >= spot ({truth.spot_price})"
                assert s["target_high"] > s["target_low"], \
                    f"Bullish target_high ({s['target_high']}) should be > target_low ({s['target_low']})"
            elif s["type"] == "bearish":
                assert s["target_high"] <= truth.spot_price, \
                    f"Bearish target_high ({s['target_high']}) should be <= spot ({truth.spot_price})"
                assert s["target_low"] < s["target_high"], \
                    f"Bearish target_low ({s['target_low']}) should be < target_high ({s['target_high']})"


def test_audit_trace_present(engine):
    truth = _make_strong_trend()
    result = engine.build(truth)

    assert "_audit" in result
    audit = result["_audit"]
    assert "raw_weights" in audit
    assert "raw_probs" in audit
    assert "calibrated_probs" in audit
    assert "temperature" in audit
    assert "path_selection" in audit
    assert "confidence_tags" in audit


# ── Integration Helper Tests ──

def test_compute_regime_gap():
    from forecast.generator_v41 import _compute_regime_gap
    assert _compute_regime_gap(None) == 0.0
    assert _compute_regime_gap({}) == 0.0
    gap = _compute_regime_gap({"trend": 0.6, "range": 0.2, "pullback": 0.1, "transition": 0.05, "breakdown": 0.05})
    assert abs(gap - 0.4) < 0.01


def test_compute_bullish_structure():
    from forecast.generator_v41 import _compute_bullish_structure
    assert _compute_bullish_structure(None) == 0.5
    val = _compute_bullish_structure({"structure_bias_score": 0.8, "structure_trend_score": 0.7, "structure_momentum_score": 0.6})
    assert val > 0.5, f"Strong bullish features should give > 0.5, got {val}"
    val_bear = _compute_bullish_structure({"structure_bias_score": -0.8, "structure_trend_score": 0.2, "structure_momentum_score": -0.5})
    assert val_bear < 0.2, f"Bearish features should give low bullish, got {val_bear}"


def test_compute_bearish_structure():
    from forecast.generator_v41 import _compute_bearish_structure
    assert _compute_bearish_structure(None, None) == 0.5
    val = _compute_bearish_structure(
        {"structure_bias_score": -0.8, "structure_reversal_risk": 0.7, "structure_exhaustion_score": 0.6},
        {"drawdown_pressure": 0.8}
    )
    assert val > 0.4, f"Bearish features should give high bearish score, got {val}"


# ── Dominant Scenario Alignment Test ──

def test_dominant_alignment_consistency():
    """
    Verify that dominant scenario broadly aligns with input direction.
    Not 100% (too rigid) but better than 50% (broken).
    """
    engine = ScenarioEngineV2(temperature=0.9, calibrator=None)

    # Strong bullish inputs should produce bullish dominant
    bull_match = 0
    for conf in [0.55, 0.60, 0.65, 0.70, 0.75]:
        truth = TruthInputs(
            asset="BTC", horizon="30D", spot_price=100000.0,
            direction="bull", calibrated_confidence=conf,
            regime_probs={"trend": 0.65, "range": 0.10, "pullback": 0.12, "transition": 0.08, "breakdown": 0.05},
            dominant_regime="trend", regime_entropy=0.25 + (0.75 - conf) * 0.1,
            regime_gap=0.55, structure_strength=0.75,
            bullish_structure=0.80, bearish_structure=0.10,
            context_alignment=0.70, negative_context=0.05,
            volatility_norm=0.35, expected_move_pct=0.07,
            range_state_score=0.15, drawdown_pressure=0.05,
        )
        result = engine.build(truth)
        if result["dominant"] == "bullish":
            bull_match += 1

    assert bull_match >= 3, f"Bullish should dominate in 3+/5 strong-trend cases, got {bull_match}"

    # Strong bearish inputs should produce bearish dominant
    bear_match = 0
    for conf in [0.55, 0.60, 0.65, 0.70, 0.75]:
        truth = TruthInputs(
            asset="BTC", horizon="30D", spot_price=100000.0,
            direction="bear", calibrated_confidence=conf,
            regime_probs={"trend": 0.05, "range": 0.08, "pullback": 0.07, "transition": 0.15, "breakdown": 0.65},
            dominant_regime="breakdown", regime_entropy=0.30,
            regime_gap=0.50, structure_strength=0.30,
            bullish_structure=0.10, bearish_structure=0.80,
            context_alignment=0.10, negative_context=0.70,
            volatility_norm=0.80, expected_move_pct=0.10,
            range_state_score=0.10, drawdown_pressure=0.65,
        )
        result = engine.build(truth)
        if result["dominant"] == "bearish":
            bear_match += 1

    assert bear_match >= 3, f"Bearish should dominate in 3+/5 breakdown cases, got {bear_match}"



# ══════════════════════════════════════════════════════════
# Phase 2: Calibration Integration Tests
# ══════════════════════════════════════════════════════════

class TestCalibratorAdapter:
    """Test ScenarioCalibratorAdapter with mock calibration map."""

    def test_adapter_calibrate_passthrough_when_no_map(self):
        """When calibration map isn't available, returns raw probs."""
        from forecast.scenario.engine_v2 import ScenarioCalibratorAdapter
        adapter = ScenarioCalibratorAdapter.__new__(ScenarioCalibratorAdapter)
        adapter._calibration_map = None
        adapter._last_build = 0.0
        adapter._cache_ttl = 0
        adapter._horizon = "30D"
        # Since _ensure_map will try DB and fail, calibrate should return raw
        raw = {"bullish": 0.40, "base": 0.35, "bearish": 0.25}
        result = adapter.calibrate(raw)
        assert result == raw

    def test_adapter_has_calibrate_method(self):
        from forecast.scenario.engine_v2 import ScenarioCalibratorAdapter
        adapter = ScenarioCalibratorAdapter(horizon="30D")
        assert hasattr(adapter, "calibrate")


class TestCalibrationGuardrails:
    """Test guardrails in _calibrate_probabilities."""

    def test_minimum_floor_prevents_zero(self):
        """No scenario should be exactly 0.0 after calibration."""

        class MockCalibrator:
            def calibrate(self, raw, ctx=None):
                return {"bullish": 0.0, "base": 0.60, "bearish": 0.40}

        engine = ScenarioEngineV2(temperature=0.9, calibrator=MockCalibrator())
        truth = _make_high_entropy()
        result = engine.build(truth)

        for s in result["scenarios"]:
            assert s["probability"] >= 0.04, \
                f"{s['type']} probability should be >= 0.04, got {s['probability']}"

    def test_dominant_preservation_with_strong_raw(self):
        """If raw dominant is strong (>0.45), calibration shouldn't flip it."""

        class MockCalibrator:
            def calibrate(self, raw, ctx=None):
                # Try to flip dominant from bullish to bearish
                return {"bullish": 0.20, "base": 0.30, "bearish": 0.50}

        engine = ScenarioEngineV2(temperature=0.9, calibrator=MockCalibrator())
        truth = _make_strong_trend()  # raw: bullish ~0.50
        result = engine.build(truth)
        # Due to guardrail 3, dominant should be preserved (blended)
        assert result["dominant"] == "bullish", \
            f"Dominant should stay bullish after preservation guard, got {result['dominant']}"

    def test_anti_collapse_blending(self):
        """If calibration collapses to uniform, should blend with raw."""

        class MockCalibrator:
            def calibrate(self, raw, ctx=None):
                return {"bullish": 0.334, "base": 0.333, "bearish": 0.333}

        engine = ScenarioEngineV2(temperature=0.9, calibrator=MockCalibrator())
        truth = _make_strong_trend()
        result = engine.build(truth)

        probs = {s["type"]: s["probability"] for s in result["scenarios"]}
        spread = max(probs.values()) - min(probs.values())
        assert spread > 0.03, f"Spread should be > 0.03 after anti-collapse blending, got {spread}"


class TestDominantSafeguard:
    """Test Phase 2 dominant < 0.40 → uncertain safeguard."""

    def test_low_dominant_forces_uncertain(self):
        """When dominant probability < 0.40, all tags should be uncertain."""

        class MockCalibrator:
            def calibrate(self, raw, ctx=None):
                return {"bullish": 0.35, "base": 0.35, "bearish": 0.30}

        engine = ScenarioEngineV2(temperature=0.9, calibrator=MockCalibrator())
        truth = _make_high_entropy()
        result = engine.build(truth)

        for s in result["scenarios"]:
            assert s["confidence_tag"] == "uncertain", \
                f"All tags should be uncertain when dominant < 0.40, but {s['type']} is {s['confidence_tag']}"

    def test_high_dominant_keeps_tags(self):
        """When dominant > 0.40, normal tag assignment works."""
        engine = ScenarioEngineV2(temperature=0.9, calibrator=None)
        truth = _make_strong_trend()
        result = engine.build(truth)

        dominant_prob = max(s["probability"] for s in result["scenarios"])
        assert dominant_prob > 0.40
        # At least one non-uncertain tag
        tags = [s["confidence_tag"] for s in result["scenarios"]]
        assert any(t != "uncertain" for t in tags)


class TestCalibrationAudit:
    """Test that audit trace includes calibration info."""

    def test_audit_has_calibration_applied_field(self):
        engine = ScenarioEngineV2(temperature=0.9, calibrator=None)
        truth = _make_strong_trend()
        result = engine.build(truth)
        assert "calibration_applied" in result["_audit"]
        assert result["_audit"]["calibration_applied"] is False

    def test_audit_calibration_applied_with_mock(self):

        class MockCalibrator:
            def calibrate(self, raw, ctx=None):
                return {"bullish": 0.50, "base": 0.30, "bearish": 0.20}

        engine = ScenarioEngineV2(temperature=0.9, calibrator=MockCalibrator())
        truth = _make_strong_trend()
        result = engine.build(truth)
        assert result["_audit"]["calibration_applied"] is True
