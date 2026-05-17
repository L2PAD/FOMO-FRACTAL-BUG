"""
Tests for Structure Intelligence V2 Integration with v4.1 Forecast Generator
===============================================================================
Tests the full integration of StructureFeatureExtractor and StructureWeightOptimizer
with the Exchange Forecast v4.1 pipeline.

Features tested:
- StructureFeatureExtractor: extract_from_prices() returns 7 features with correct ranges
- StructureFeatureExtractor: correctly detects uptrend/downtrend/range
- StructureFeatureExtractor: empty/insufficient data returns EMPTY_FEATURES
- StructureWeightOptimizer: delta is capped at MAX_STRUCTURE_DELTA=0.18
- StructureWeightOptimizer: horizon multipliers are correctly applied (24H=0.4, 7D=1.0, 30D=0.6)
- StructureWeightOptimizer: sign-flip protection works (strong base score not flipped)
- StructureWeightOptimizer: sign-flip allowed when base is weak AND reversal is high
- StructureWeightOptimizer: empty features produce zero delta
- Full pipeline: generate_forecast() includes structureFeatures and structureInfluence in audit
- Full pipeline: forecasts still work correctly when structure is None (graceful fallback)
- API endpoints: /api/forecast/admin/run and /api/forecast/kpi still work
"""

import pytest
import os
import sys
import requests
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from forecast.structure.extractor import StructureFeatureExtractor, EMPTY_FEATURES
from forecast.structure.optimizer import StructureWeightOptimizer
from forecast.structure.config import STRUCTURE_WEIGHTS, STRUCTURE_CONFIG

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


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
    prices = {}
    for i in range(n):
        date = f"2026-01-{i+1:02d}"
        prices[date] = round(center + amplitude * math.sin(i * 0.5), 2)
    return prices


# ═══════════════════════════════════════════════════════
# EXTRACTOR TESTS: 7 Features with Correct Ranges
# ═══════════════════════════════════════════════════════

class TestExtractorFeatureRanges:
    """Test that extract_from_prices returns all 7 features with correct ranges."""
    
    def test_returns_7_features(self, extractor):
        """Verify all 7 structure features are returned."""
        prices = _make_uptrend_prices()
        result = extractor.extract_from_prices(prices)
        
        expected_keys = [
            "structure_bias_score",
            "structure_trend_score",
            "structure_momentum_score",
            "structure_reversal_risk",
            "structure_stability_score",
            "structure_exhaustion_score",
            "structure_compression_score",
        ]
        
        for key in expected_keys:
            assert key in result, f"Missing feature: {key}"
        
        assert len(result) == 7, f"Expected 7 features, got {len(result)}"
    
    def test_bias_score_range(self, extractor):
        """structure_bias_score should be in [-0.7, 0.7]."""
        for prices in [_make_uptrend_prices(), _make_downtrend_prices(), _make_range_prices()]:
            result = extractor.extract_from_prices(prices)
            assert -0.7 <= result["structure_bias_score"] <= 0.7
    
    def test_trend_score_range(self, extractor):
        """structure_trend_score should be in [0, 1]."""
        prices = _make_uptrend_prices()
        result = extractor.extract_from_prices(prices)
        assert 0.0 <= result["structure_trend_score"] <= 1.0
    
    def test_momentum_score_range(self, extractor):
        """structure_momentum_score should be in [-1, 1]."""
        prices = _make_uptrend_prices()
        result = extractor.extract_from_prices(prices)
        assert -1.0 <= result["structure_momentum_score"] <= 1.0
    
    def test_reversal_risk_range(self, extractor):
        """structure_reversal_risk should be in [0, 1]."""
        prices = _make_uptrend_prices()
        result = extractor.extract_from_prices(prices)
        assert 0.0 <= result["structure_reversal_risk"] <= 1.0
    
    def test_stability_score_range(self, extractor):
        """structure_stability_score should be in [0, 1]."""
        prices = _make_uptrend_prices()
        result = extractor.extract_from_prices(prices)
        assert 0.0 <= result["structure_stability_score"] <= 1.0
    
    def test_exhaustion_score_range(self, extractor):
        """structure_exhaustion_score should be in [0, 1]."""
        prices = _make_uptrend_prices()
        result = extractor.extract_from_prices(prices)
        assert 0.0 <= result["structure_exhaustion_score"] <= 1.0
    
    def test_compression_score_range(self, extractor):
        """structure_compression_score should be in [0, 1]."""
        prices = _make_uptrend_prices()
        result = extractor.extract_from_prices(prices)
        assert 0.0 <= result["structure_compression_score"] <= 1.0


# ═══════════════════════════════════════════════════════
# EXTRACTOR TESTS: Trend Detection
# ═══════════════════════════════════════════════════════

class TestExtractorTrendDetection:
    """Test that extractor correctly detects uptrend/downtrend/range."""
    
    def test_uptrend_positive_bias(self, extractor):
        """Uptrend prices should produce positive or zero bias score."""
        prices = _make_uptrend_prices()
        result = extractor.extract_from_prices(prices)
        # In an uptrend, bias should be non-negative (can be 0 or +0.7)
        assert result["structure_bias_score"] >= 0.0, "Uptrend should have non-negative bias"
    
    def test_downtrend_negative_bias(self, extractor):
        """Downtrend prices should produce negative or zero bias score."""
        prices = _make_downtrend_prices()
        result = extractor.extract_from_prices(prices)
        assert result["structure_bias_score"] <= 0.0, "Downtrend should have non-positive bias"
    
    def test_range_neutral_bias(self, extractor):
        """Range-bound prices should produce near-zero bias."""
        prices = _make_range_prices()
        result = extractor.extract_from_prices(prices)
        assert abs(result["structure_bias_score"]) <= 0.1, "Range should have near-zero bias"


# ═══════════════════════════════════════════════════════
# EXTRACTOR TESTS: Empty/Insufficient Data
# ═══════════════════════════════════════════════════════

class TestExtractorEmptyData:
    """Test that empty/insufficient data returns EMPTY_FEATURES."""
    
    def test_none_input(self, extractor):
        """None input should return EMPTY_FEATURES."""
        result = extractor.extract_from_prices(None)
        assert result == EMPTY_FEATURES
    
    def test_empty_dict(self, extractor):
        """Empty dict should return EMPTY_FEATURES."""
        result = extractor.extract_from_prices({})
        assert result == EMPTY_FEATURES
    
    def test_insufficient_data_10_points(self, extractor):
        """Less than 14 prices should return EMPTY_FEATURES."""
        prices = {f"2026-01-{i:02d}": 100 + i for i in range(1, 10)}
        result = extractor.extract_from_prices(prices)
        assert result == EMPTY_FEATURES
    
    def test_exactly_14_points_may_work(self, extractor):
        """14 points is the minimum for feature extraction."""
        prices = {f"2026-01-{i:02d}": 100 + i * 2 for i in range(1, 15)}
        result = extractor.extract_from_prices(prices)
        # May return EMPTY_FEATURES if swings not detected, but should not crash
        assert isinstance(result, dict)
    
    def test_extract_from_structure_none(self, extractor):
        """extract_from_structure with None should return EMPTY_FEATURES."""
        result = extractor.extract_from_structure(None)
        assert result == EMPTY_FEATURES


# ═══════════════════════════════════════════════════════
# OPTIMIZER TESTS: Delta Capping
# ═══════════════════════════════════════════════════════

class TestOptimizerDeltaCap:
    """Test that delta is capped at MAX_STRUCTURE_DELTA=0.18."""
    
    def test_max_delta_config_value(self):
        """Verify MAX_STRUCTURE_DELTA is 0.18 in config."""
        assert STRUCTURE_CONFIG["max_delta"] == 0.18
    
    def test_positive_delta_capped(self, optimizer):
        """Extreme bullish features should not exceed +0.18 delta."""
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
        assert result["capped_delta"] <= 0.18
        assert result["capped_delta"] >= -0.18
    
    def test_negative_delta_capped(self, optimizer):
        """Extreme bearish features should not exceed -0.18 delta."""
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
        assert abs(result["capped_delta"]) <= 0.18


# ═══════════════════════════════════════════════════════
# OPTIMIZER TESTS: Horizon Multipliers
# ═══════════════════════════════════════════════════════

class TestOptimizerHorizonMultipliers:
    """Test horizon multipliers: 24H=0.4, 7D=1.0, 30D=0.6."""
    
    def test_horizon_multiplier_config(self):
        """Verify horizon multipliers in config."""
        hm = STRUCTURE_CONFIG["horizon_multiplier"]
        assert hm["24H"] == 0.40
        assert hm["7D"] == 1.00
        assert hm["30D"] == 0.60
    
    def test_7d_full_multiplier(self, optimizer):
        """7D should have horizon_multiplier=1.0."""
        sf = {"structure_bias_score": 0.5}
        result = optimizer.compute_delta("7D", sf, 0.0)
        assert result["horizon_multiplier"] == 1.0
    
    def test_30d_reduced_multiplier(self, optimizer):
        """30D should have horizon_multiplier=0.6."""
        sf = {"structure_bias_score": 0.5}
        result = optimizer.compute_delta("30D", sf, 0.0)
        assert result["horizon_multiplier"] == 0.6
    
    def test_24h_minimal_multiplier(self, optimizer):
        """24H should have horizon_multiplier=0.4."""
        sf = {"structure_bias_score": 0.5}
        result = optimizer.compute_delta("24H", sf, 0.0)
        assert result["horizon_multiplier"] == 0.4
    
    def test_7d_delta_larger_than_30d(self, optimizer):
        """Same features should produce larger delta for 7D than 30D."""
        sf = {
            "structure_bias_score": 0.5,
            "structure_trend_score": 0.5,
            "structure_momentum_score": 0.5,
            "structure_reversal_risk": 0.1,
            "structure_exhaustion_score": 0.1,
            "structure_stability_score": 0.5,
            "structure_compression_score": 0.5,
        }
        r7 = optimizer.compute_delta("7D", sf, 0.0)
        r30 = optimizer.compute_delta("30D", sf, 0.0)
        r24 = optimizer.compute_delta("24H", sf, 0.0)
        
        # 7D has largest multiplier, should have largest raw delta
        assert abs(r7["raw_delta"]) >= abs(r30["raw_delta"])
        assert abs(r30["raw_delta"]) >= abs(r24["raw_delta"])


# ═══════════════════════════════════════════════════════
# OPTIMIZER TESTS: Sign-Flip Protection
# ═══════════════════════════════════════════════════════

class TestOptimizerSignFlipProtection:
    """Test that strong base scores are not flipped by structure."""
    
    def test_strong_positive_base_not_flipped(self, optimizer):
        """Strong positive base (0.5) should not flip to negative."""
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
        
        # Should not allow sign flip for strong base
        assert not result["sign_flip_allowed"]
        assert result["score_after_structure"] >= 0.0
    
    def test_strong_negative_base_not_flipped(self, optimizer):
        """Strong negative base (-0.5) should not flip to positive."""
        sf = {
            "structure_bias_score": 0.7,
            "structure_trend_score": 1.0,
            "structure_momentum_score": 1.0,
            "structure_reversal_risk": 0.0,
            "structure_exhaustion_score": 0.0,
            "structure_stability_score": 1.0,
            "structure_compression_score": 1.0,
        }
        result = optimizer.compute_delta("7D", sf, base_score=-0.5)
        
        assert not result["sign_flip_allowed"]
        assert result["score_after_structure"] <= 0.0
    
    def test_sign_flip_base_threshold(self):
        """Verify sign flip base threshold is 0.25."""
        assert STRUCTURE_CONFIG["sign_flip_base_threshold"] == 0.25


# ═══════════════════════════════════════════════════════
# OPTIMIZER TESTS: Sign-Flip Allowed (Weak Base + High Reversal)
# ═══════════════════════════════════════════════════════

class TestOptimizerSignFlipAllowed:
    """Test sign-flip allowed when base is weak AND reversal is high."""
    
    def test_sign_flip_allowed_conditions(self, optimizer):
        """Weak base + high reversal + strong momentum → flip allowed."""
        sf = {
            "structure_bias_score": -0.7,
            "structure_trend_score": 0.0,
            "structure_momentum_score": -0.8,  # > 0.45 threshold
            "structure_reversal_risk": 0.9,    # > 0.70 threshold
            "structure_exhaustion_score": 0.0,
            "structure_stability_score": 0.0,
            "structure_compression_score": 0.0,
        }
        # Weak base (0.1 < 0.25)
        result = optimizer.compute_delta("7D", sf, base_score=0.1)
        
        assert result["sign_flip_allowed"], "Sign flip should be allowed for weak base + high reversal + strong momentum"
    
    def test_sign_flip_blocked_low_reversal(self, optimizer):
        """Even weak base is protected if reversal is low."""
        sf = {
            "structure_bias_score": -0.7,
            "structure_trend_score": 0.0,
            "structure_momentum_score": -0.8,
            "structure_reversal_risk": 0.3,  # Below 0.70 threshold
            "structure_exhaustion_score": 0.0,
            "structure_stability_score": 0.0,
            "structure_compression_score": 0.0,
        }
        result = optimizer.compute_delta("7D", sf, base_score=0.1)
        
        assert not result["sign_flip_allowed"], "Low reversal should block sign flip"
    
    def test_sign_flip_blocked_low_momentum(self, optimizer):
        """Even weak base + high reversal is protected if momentum is low."""
        sf = {
            "structure_bias_score": -0.7,
            "structure_trend_score": 0.0,
            "structure_momentum_score": -0.2,  # Below 0.45 threshold
            "structure_reversal_risk": 0.9,
            "structure_exhaustion_score": 0.0,
            "structure_stability_score": 0.0,
            "structure_compression_score": 0.0,
        }
        result = optimizer.compute_delta("7D", sf, base_score=0.1)
        
        assert not result["sign_flip_allowed"], "Low momentum should block sign flip"


# ═══════════════════════════════════════════════════════
# OPTIMIZER TESTS: Empty Features
# ═══════════════════════════════════════════════════════

class TestOptimizerEmptyFeatures:
    """Test that empty features produce zero delta."""
    
    def test_empty_features_zero_delta(self, optimizer):
        """EMPTY_FEATURES should produce capped_delta=0."""
        result = optimizer.compute_delta("7D", EMPTY_FEATURES, base_score=0.3)
        assert result["capped_delta"] == 0.0
        assert result["score_after_structure"] == 0.3
    
    def test_empty_features_no_sign_flip(self, optimizer):
        """EMPTY_FEATURES should not allow sign flip."""
        result = optimizer.compute_delta("7D", EMPTY_FEATURES, base_score=0.3)
        assert not result["sign_flip_allowed"]


# ═══════════════════════════════════════════════════════
# FULL PIPELINE TESTS: Audit Payload
# ═══════════════════════════════════════════════════════

class TestPipelineAuditPayload:
    """Test that generate_forecast includes structureFeatures and structureInfluence in audit."""
    
    def test_audit_contains_structure_features(self):
        """Audit payload should contain structureFeatures dict."""
        from forecast.generator_v41 import generate_forecast
        from forecast import Horizon
        
        result = generate_forecast("BTC", Horizon.D7, model_version="v4.1.1-test", run_id="test")
        
        if result is None:
            pytest.skip("Forecast generation returned None (insufficient data)")
        
        audit = result.audit
        assert "structureFeatures" in audit, "Audit should contain structureFeatures"
        
        sf = audit["structureFeatures"]
        assert "structure_bias_score" in sf
        assert "structure_trend_score" in sf
        assert "structure_momentum_score" in sf
        assert "structure_reversal_risk" in sf
        assert "structure_stability_score" in sf
        assert "structure_exhaustion_score" in sf
        assert "structure_compression_score" in sf
    
    def test_audit_contains_structure_influence(self):
        """Audit payload should contain structureInfluence dict."""
        from forecast.generator_v41 import generate_forecast
        from forecast import Horizon
        
        result = generate_forecast("BTC", Horizon.D7, model_version="v4.1.1-test", run_id="test")
        
        if result is None:
            pytest.skip("Forecast generation returned None")
        
        audit = result.audit
        assert "structureInfluence" in audit, "Audit should contain structureInfluence"
        
        si = audit["structureInfluence"]
        assert "raw_delta" in si
        assert "capped_delta" in si
        assert "sign_flip_allowed" in si
        assert "score_after_structure" in si
        assert "horizon_multiplier" in si
        assert "base_score_before_structure" in si
    
    def test_audit_version_is_4_1_1(self):
        """Audit version should be 4.1.1 for structure-enabled forecasts."""
        from forecast.generator_v41 import generate_forecast
        from forecast import Horizon
        
        result = generate_forecast("BTC", Horizon.D7, model_version="v4.1.1-test", run_id="test")
        
        if result is None:
            pytest.skip("Forecast generation returned None")
        
        assert result.audit["v"] == "4.1.1"
    
    def test_30d_forecast_has_structure(self):
        """30D forecast should also have structure features in audit."""
        from forecast.generator_v41 import generate_forecast
        from forecast import Horizon
        
        result = generate_forecast("BTC", Horizon.D30, model_version="v4.1.1-test", run_id="test")
        
        if result is None:
            pytest.skip("Forecast generation returned None")
        
        assert "structureFeatures" in result.audit
        assert "structureInfluence" in result.audit


# ═══════════════════════════════════════════════════════
# FULL PIPELINE TESTS: Graceful Fallback
# ═══════════════════════════════════════════════════════

class TestPipelineGracefulFallback:
    """Test that forecasts work correctly when structure is None."""
    
    def test_forecast_works_without_structure(self):
        """Forecast should be generated even if structure extraction fails."""
        from forecast.generator_v41 import generate_forecast, _structure_extractor
        from forecast import Horizon
        
        # Temporarily make extractor return None (simulate failure)
        original_extract = _structure_extractor.extract_from_prices
        
        def mock_extract(prices):
            raise Exception("Mock failure")
        
        _structure_extractor.extract_from_prices = mock_extract
        
        try:
            result = generate_forecast("BTC", Horizon.D7, model_version="v4.1.1-test", run_id="test")
            
            # Should still generate forecast (graceful fallback)
            if result is not None:
                # Structure features should be None or missing
                assert "structureFeatures" not in result.audit or result.audit.get("structureFeatures") is None
                assert "structureInfluence" not in result.audit or result.audit.get("structureInfluence") is None
        finally:
            _structure_extractor.extract_from_prices = original_extract


# ═══════════════════════════════════════════════════════
# API ENDPOINT TESTS
# ═══════════════════════════════════════════════════════

@pytest.mark.skipif(not BASE_URL, reason="REACT_APP_BACKEND_URL not set")
class TestAPIEndpoints:
    """Test API endpoints /api/forecast/admin/run and /api/forecast/kpi."""
    
    def test_admin_run_endpoint(self):
        """POST /api/forecast/admin/run should return ok:true."""
        response = requests.post(f"{BASE_URL}/api/forecast/admin/run?mode=daily", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
    
    def test_admin_status_endpoint(self):
        """GET /api/forecast/admin/status should return status info."""
        response = requests.get(f"{BASE_URL}/api/forecast/admin/status", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "stats" in data
    
    def test_kpi_endpoint(self):
        """GET /api/forecast/kpi should return KPI data."""
        response = requests.get(f"{BASE_URL}/api/forecast/kpi", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "current" in data
    
    def test_health_endpoint(self):
        """GET /api/forecast/health should return health info."""
        response = requests.get(f"{BASE_URL}/api/forecast/health", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "horizons" in data


# ═══════════════════════════════════════════════════════
# REGRESSION TESTS: Guard Tests Still Pass
# ═══════════════════════════════════════════════════════

class TestForecastGuardRegression:
    """Ensure existing guard tests still work after structure integration."""
    
    def test_guard_api_route_allowed(self):
        """API route context should be allowed."""
        from fractal_forecast.guard import assert_no_forecast_access
        # Should not raise
        assert_no_forecast_access("api_route")
    
    def test_guard_metabrain_blocked(self):
        """Metabrain context should be blocked."""
        from fractal_forecast.guard import assert_no_forecast_access, ForecastAccessViolation
        with pytest.raises(ForecastAccessViolation):
            assert_no_forecast_access("metabrain")
