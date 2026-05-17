"""
Tests for Structure Intelligence V2
====================================
Tests the StructureFeatureExtractor and StructureWeightOptimizer.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from forecast.structure.extractor import StructureFeatureExtractor, EMPTY_FEATURES
from forecast.structure.optimizer import StructureWeightOptimizer
from forecast.structure.config import STRUCTURE_WEIGHTS, STRUCTURE_CONFIG


# ═══════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════

@pytest.fixture
def extractor():
    return StructureFeatureExtractor()


@pytest.fixture
def optimizer():
    return StructureWeightOptimizer()


def _make_uptrend_prices(n=30, start=100.0, step=2.0):
    """Generate uptrend price series with HH/HL pattern."""
    prices = {}
    p = start
    for i in range(n):
        date = f"2026-01-{i+1:02d}"
        if i % 4 == 0:
            p += step * 1.5  # swing high
        elif i % 4 == 2:
            p -= step * 0.7  # swing low (higher than prev low)
        else:
            p += step * 0.3
        prices[date] = round(p, 2)
    return prices


def _make_downtrend_prices(n=30, start=200.0, step=2.0):
    """Generate downtrend price series with LL/LH pattern."""
    prices = {}
    p = start
    for i in range(n):
        date = f"2026-01-{i+1:02d}"
        if i % 4 == 0:
            p -= step * 1.5  # swing low
        elif i % 4 == 2:
            p += step * 0.7  # swing high (lower than prev high)
        else:
            p -= step * 0.3
        prices[date] = round(p, 2)
    return prices


def _make_range_prices(n=30, center=150.0, amplitude=5.0):
    """Generate range-bound price series."""
    import math
    prices = {}
    for i in range(n):
        date = f"2026-01-{i+1:02d}"
        prices[date] = round(center + amplitude * math.sin(i * 0.5), 2)
    return prices


# ═══════════════════════════════════════════════════════
# EXTRACTOR TESTS
# ═══════════════════════════════════════════════════════

class TestExtractorEmptyInput:
    def test_none_input(self, extractor):
        result = extractor.extract_from_prices(None)
        assert result == EMPTY_FEATURES

    def test_empty_dict(self, extractor):
        result = extractor.extract_from_prices({})
        assert result == EMPTY_FEATURES

    def test_too_few_prices(self, extractor):
        prices = {f"2026-01-{i:02d}": 100 + i for i in range(1, 10)}
        result = extractor.extract_from_prices(prices)
        assert result == EMPTY_FEATURES

    def test_structure_none_input(self, extractor):
        result = extractor.extract_from_structure(None)
        assert result == EMPTY_FEATURES


class TestExtractorUptrend:
    def test_positive_bias(self, extractor):
        prices = _make_uptrend_prices()
        result = extractor.extract_from_prices(prices)
        assert result["structure_bias_score"] >= 0.0, "Uptrend should have non-negative bias"

    def test_all_features_present(self, extractor):
        prices = _make_uptrend_prices()
        result = extractor.extract_from_prices(prices)
        for key in EMPTY_FEATURES:
            assert key in result, f"Missing key: {key}"

    def test_feature_ranges(self, extractor):
        prices = _make_uptrend_prices()
        result = extractor.extract_from_prices(prices)
        assert -0.7 <= result["structure_bias_score"] <= 0.7
        assert 0.0 <= result["structure_trend_score"] <= 1.0
        assert -1.0 <= result["structure_momentum_score"] <= 1.0
        assert 0.0 <= result["structure_reversal_risk"] <= 1.0
        assert 0.0 <= result["structure_stability_score"] <= 1.0
        assert 0.0 <= result["structure_exhaustion_score"] <= 1.0
        assert 0.0 <= result["structure_compression_score"] <= 1.0


class TestExtractorDowntrend:
    def test_negative_bias(self, extractor):
        prices = _make_downtrend_prices()
        result = extractor.extract_from_prices(prices)
        assert result["structure_bias_score"] <= 0.0, "Downtrend should have non-positive bias"


class TestExtractorRange:
    def test_neutral_bias(self, extractor):
        prices = _make_range_prices()
        result = extractor.extract_from_prices(prices)
        assert abs(result["structure_bias_score"]) <= 0.01, "Range should have near-zero bias"


class TestExtractorFromStructure:
    def test_uptrend_structure(self, extractor):
        data = {
            "trend": "uptrend",
            "legs": [
                {"direction": "up", "size": 10, "abs_size": 10},
                {"direction": "down", "size": -5, "abs_size": 5},
                {"direction": "up", "size": 12, "abs_size": 12},
                {"direction": "down", "size": -4, "abs_size": 4},
                {"direction": "up", "size": 8, "abs_size": 8},
            ],
            "bos_events": [{"type": "bos_bull"}],
            "choch_events": [],
        }
        result = extractor.extract_from_structure(data)
        assert result["structure_bias_score"] == 0.7
        assert result["structure_reversal_risk"] == 0.0
        assert result["structure_stability_score"] == 1.0

    def test_reversal_structure(self, extractor):
        data = {
            "trend": "downtrend",
            "legs": [
                {"direction": "down", "size": -10, "abs_size": 10},
                {"direction": "up", "size": 5, "abs_size": 5},
            ],
            "bos_events": [],
            "choch_events": [{"type": "choch_bull"}, {"type": "choch_bull"}],
        }
        result = extractor.extract_from_structure(data)
        assert result["structure_bias_score"] == -0.7
        assert result["structure_reversal_risk"] == 1.0
        assert result["structure_stability_score"] == 0.0


class TestExtractorExhaustion:
    def test_shrinking_legs_high_exhaustion(self, extractor):
        data = {
            "trend": "uptrend",
            "legs": [
                {"direction": "up", "size": 20, "abs_size": 20},
                {"direction": "down", "size": -5, "abs_size": 5},
                {"direction": "up", "size": 15, "abs_size": 15},
                {"direction": "down", "size": -4, "abs_size": 4},
                {"direction": "up", "size": 5, "abs_size": 5},
            ],
            "bos_events": [],
            "choch_events": [],
        }
        result = extractor.extract_from_structure(data)
        # Last 3 legs: [15, 4, 5] → decay = 5/15 = 0.33 → exhaustion = 0.67
        assert result["structure_exhaustion_score"] > 0.3

    def test_growing_legs_low_exhaustion(self, extractor):
        data = {
            "trend": "uptrend",
            "legs": [
                {"direction": "up", "size": 5, "abs_size": 5},
                {"direction": "down", "size": -3, "abs_size": 3},
                {"direction": "up", "size": 10, "abs_size": 10},
                {"direction": "down", "size": -3, "abs_size": 3},
                {"direction": "up", "size": 20, "abs_size": 20},
            ],
            "bos_events": [],
            "choch_events": [],
        }
        result = extractor.extract_from_structure(data)
        # Last 3 legs: [10, 3, 20] → decay = 20/10 = 2.0 → exhaustion = max(0, 1-2) = 0
        assert result["structure_exhaustion_score"] == 0.0


# ═══════════════════════════════════════════════════════
# OPTIMIZER TESTS
# ═══════════════════════════════════════════════════════

class TestOptimizerDeltaCap:
    def test_delta_capped_at_max(self, optimizer):
        """Extreme structure features should not exceed MAX_STRUCTURE_DELTA."""
        sf = {
            "structure_bias_score": 0.7,
            "structure_trend_score": 1.0,
            "structure_momentum_score": 1.0,
            "structure_reversal_risk": 0.0,
            "structure_exhaustion_score": 0.0,
            "structure_stability_score": 1.0,
            "structure_compression_score": 1.0,
        }
        result = optimizer.compute_delta("7D", sf, base_score=0.0)
        assert abs(result["capped_delta"]) <= STRUCTURE_CONFIG["max_delta"]

    def test_negative_delta_capped(self, optimizer):
        sf = {
            "structure_bias_score": -0.7,
            "structure_trend_score": 0.0,
            "structure_momentum_score": -1.0,
            "structure_reversal_risk": 1.0,
            "structure_exhaustion_score": 1.0,
            "structure_stability_score": 0.0,
            "structure_compression_score": 0.0,
        }
        result = optimizer.compute_delta("7D", sf, base_score=0.0)
        assert abs(result["capped_delta"]) <= STRUCTURE_CONFIG["max_delta"]


class TestOptimizerHorizonMultiplier:
    def test_7d_full_influence(self, optimizer):
        sf = {"structure_bias_score": 0.5, "structure_trend_score": 0.5,
              "structure_momentum_score": 0.5, "structure_reversal_risk": 0.0,
              "structure_exhaustion_score": 0.0, "structure_stability_score": 0.5,
              "structure_compression_score": 0.5}
        r7 = optimizer.compute_delta("7D", sf, 0.0)
        assert r7["horizon_multiplier"] == 1.00

    def test_30d_reduced_influence(self, optimizer):
        sf = {"structure_bias_score": 0.5, "structure_trend_score": 0.5,
              "structure_momentum_score": 0.5, "structure_reversal_risk": 0.0,
              "structure_exhaustion_score": 0.0, "structure_stability_score": 0.5,
              "structure_compression_score": 0.5}
        r30 = optimizer.compute_delta("30D", sf, 0.0)
        assert r30["horizon_multiplier"] == 0.60

    def test_24h_minimal_influence(self, optimizer):
        sf = {"structure_bias_score": 0.5, "structure_trend_score": 0.5,
              "structure_momentum_score": 0.5, "structure_reversal_risk": 0.0,
              "structure_exhaustion_score": 0.0, "structure_stability_score": 0.5,
              "structure_compression_score": 0.5}
        r24 = optimizer.compute_delta("24H", sf, 0.0)
        assert r24["horizon_multiplier"] == 0.40

    def test_30d_delta_smaller_than_7d(self, optimizer):
        sf = {"structure_bias_score": 0.5, "structure_trend_score": 0.5,
              "structure_momentum_score": 0.5, "structure_reversal_risk": 0.0,
              "structure_exhaustion_score": 0.0, "structure_stability_score": 0.5,
              "structure_compression_score": 0.5}
        r7 = optimizer.compute_delta("7D", sf, 0.0)
        r30 = optimizer.compute_delta("30D", sf, 0.0)
        assert abs(r30["raw_delta"]) < abs(r7["raw_delta"])


class TestOptimizerSignFlip:
    def test_no_sign_flip_strong_base(self, optimizer):
        """Strong base score should NOT be flipped by structure."""
        sf = {
            "structure_bias_score": -0.7,
            "structure_trend_score": 0.0,
            "structure_momentum_score": -1.0,
            "structure_reversal_risk": 0.9,
            "structure_exhaustion_score": 0.0,
            "structure_stability_score": 0.0,
            "structure_compression_score": 0.0,
        }
        result = optimizer.compute_delta("7D", sf, base_score=0.5)
        assert result["score_after_structure"] >= 0.0, "Strong positive score should not flip to negative"
        assert not result["sign_flip_allowed"]

    def test_sign_flip_allowed_weak_base(self, optimizer):
        """Weak base + high reversal + strong momentum → flip allowed."""
        sf = {
            "structure_bias_score": -0.7,
            "structure_trend_score": 0.0,
            "structure_momentum_score": -0.8,
            "structure_reversal_risk": 0.9,
            "structure_exhaustion_score": 0.0,
            "structure_stability_score": 0.0,
            "structure_compression_score": 0.0,
        }
        result = optimizer.compute_delta("7D", sf, base_score=0.1)
        assert result["sign_flip_allowed"]

    def test_no_sign_flip_low_reversal(self, optimizer):
        """Even with weak base, low reversal risk blocks flip."""
        sf = {
            "structure_bias_score": -0.7,
            "structure_trend_score": 0.0,
            "structure_momentum_score": -0.8,
            "structure_reversal_risk": 0.3,
            "structure_exhaustion_score": 0.0,
            "structure_stability_score": 0.0,
            "structure_compression_score": 0.0,
        }
        result = optimizer.compute_delta("7D", sf, base_score=0.1)
        assert not result["sign_flip_allowed"]


class TestOptimizerScoreClip:
    def test_final_score_clipped(self, optimizer):
        """Final score must be in [-1, 1]."""
        sf = {
            "structure_bias_score": 0.7,
            "structure_trend_score": 1.0,
            "structure_momentum_score": 1.0,
            "structure_reversal_risk": 0.0,
            "structure_exhaustion_score": 0.0,
            "structure_stability_score": 1.0,
            "structure_compression_score": 1.0,
        }
        result = optimizer.compute_delta("7D", sf, base_score=0.95)
        assert -1.0 <= result["score_after_structure"] <= 1.0


class TestOptimizerEmptyFeatures:
    def test_empty_features_no_change(self, optimizer):
        """Empty structure features should produce zero delta."""
        result = optimizer.compute_delta("7D", EMPTY_FEATURES, base_score=0.3)
        assert result["capped_delta"] == 0.0
        assert result["score_after_structure"] == 0.3


class TestOptimizerBullishStructure:
    def test_bullish_structure_increases_score(self, optimizer):
        """Strong bullish structure should increase a neutral base score."""
        sf = {
            "structure_bias_score": 0.7,
            "structure_trend_score": 0.8,
            "structure_momentum_score": 0.6,
            "structure_reversal_risk": 0.1,
            "structure_exhaustion_score": 0.1,
            "structure_stability_score": 0.8,
            "structure_compression_score": 0.5,
        }
        result = optimizer.compute_delta("7D", sf, base_score=0.0)
        assert result["score_after_structure"] > 0.0


class TestOptimizerBearishStructure:
    def test_bearish_structure_decreases_score(self, optimizer):
        """Strong bearish structure should decrease a neutral base score."""
        sf = {
            "structure_bias_score": -0.7,
            "structure_trend_score": 0.8,
            "structure_momentum_score": -0.6,
            "structure_reversal_risk": 0.1,
            "structure_exhaustion_score": 0.1,
            "structure_stability_score": 0.8,
            "structure_compression_score": 0.5,
        }
        result = optimizer.compute_delta("7D", sf, base_score=0.0)
        assert result["score_after_structure"] < 0.0
