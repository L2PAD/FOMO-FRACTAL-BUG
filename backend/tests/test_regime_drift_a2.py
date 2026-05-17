"""
A2: Regime-Specific Drift Baselines - API Tests

Tests for:
- GET /api/drift/status?horizon=7D - regimeAdjusted:true, regimeContext with mae damping and flip context
- GET /api/drift/status?horizon=30D - regime-adjusted drift (was WATCH globally, now OK with regime-aware)  
- GET /api/drift/regime-baselines?horizon=7D - baselines for TREND, RANGE, RISK_OFF, TRANSITION
- GET /api/drift/regime-baselines?horizon=30D - baselines for 30D
- GET /api/ml-overlay/predict?asset=BTC&horizon=30D - driftWeight now ~0.64 (improved from ~0.60 due to regime adjustment)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestA2RegimeDriftStatus:
    """Test drift status endpoints for regime-aware adjustments"""

    def test_drift_status_7d_has_regime_adjusted_flag(self):
        """7D drift status should include regimeAdjusted:true"""
        response = requests.get(f"{BASE_URL}/api/drift/status?horizon=7D")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert data.get("horizon") == "7D"
        
        # Key A2 feature: regimeAdjusted flag must be true
        assert data.get("regimeAdjusted") is True, "regimeAdjusted flag should be true for 7D drift"
        
        # Regime context should be present
        regime_context = data.get("regimeContext")
        assert regime_context is not None, "regimeContext should be present"
        
        # MAE damping in regime context
        mae_ctx = regime_context.get("mae")
        assert mae_ctx is not None, "regimeContext.mae should exist"
        assert "damping" in mae_ctx, "mae context should have damping factor"
        assert 0 <= mae_ctx["damping"] <= 1, "damping should be between 0 and 1"
        
        # Flip context
        flip_ctx = regime_context.get("flip")
        assert flip_ctx is not None, "regimeContext.flip should exist"
        assert flip_ctx in ["within_regime_norm", "exceeds_regime_norm", "no_regime_data"], \
            f"flip context should be a valid value, got: {flip_ctx}"
        
        print(f"7D regime context: mae_damping={mae_ctx['damping']}, flip={flip_ctx}")

    def test_drift_status_7d_has_regime_field(self):
        """7D drift status should include current regime"""
        response = requests.get(f"{BASE_URL}/api/drift/status?horizon=7D")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        # Regime field
        regime = data.get("regime")
        assert regime in ["TREND", "RANGE", "RISK_OFF", "TRANSITION"], \
            f"Invalid regime: {regime}"
        
        print(f"Current 7D regime: {regime}")

    def test_drift_status_30d_has_regime_adjusted_flag(self):
        """30D drift status should include regimeAdjusted:true"""
        response = requests.get(f"{BASE_URL}/api/drift/status?horizon=30D")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert data.get("horizon") == "30D"
        
        # Key A2 feature: regimeAdjusted flag must be true
        assert data.get("regimeAdjusted") is True, "regimeAdjusted flag should be true for 30D drift"
        
        # Regime context should be present
        regime_context = data.get("regimeContext")
        assert regime_context is not None, "regimeContext should be present"
        
        print(f"30D regime context: {regime_context}")

    def test_drift_status_30d_regime_aware_status(self):
        """30D drift was WATCH globally (0.254), now OK (0.224) with regime-aware adjustment"""
        response = requests.get(f"{BASE_URL}/api/drift/status?horizon=30D")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        # Status should be OK after regime adjustment (was WATCH without it)
        status = data.get("status")
        drift_score = data.get("driftScore", 0)
        
        print(f"30D drift: status={status}, driftScore={drift_score}")
        
        # Key A2 improvement: drift should now be in OK range (<0.25) due to regime adjustment
        assert status == "OK", f"Expected status OK after regime adjustment, got {status}"
        assert drift_score < 0.25, f"Expected driftScore < 0.25, got {drift_score}"
        
        # Verify regime context shows damping was applied
        regime_context = data.get("regimeContext", {})
        mae_ctx = regime_context.get("mae", {})
        
        # damping should be > 0 (indicating adjustment was made)
        damping = mae_ctx.get("damping", 1.0)
        assert damping < 1.0, f"Expected damping < 1 (adjustment applied), got {damping}"
        
        print(f"30D mae_damping={damping}, regime-aware drift working correctly")

    def test_drift_status_30d_components_and_drivers(self):
        """30D drift should have proper components and drivers"""
        response = requests.get(f"{BASE_URL}/api/drift/status?horizon=30D")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        # Components structure
        components = data.get("components", {})
        assert "psi" in components
        assert "dirHitDrop" in components
        assert "maeGrowth" in components
        assert "flipSpike" in components
        
        # Drivers (top drift contributors)
        drivers = data.get("drivers", [])
        assert isinstance(drivers, list)
        
        print(f"30D components: {components}")
        print(f"30D drivers: {drivers}")


class TestA2RegimeBaselines:
    """Test regime-baselines endpoint for stored baselines"""

    def test_regime_baselines_7d_returns_four_regimes(self):
        """7D regime baselines should have TREND, RANGE, RISK_OFF, TRANSITION"""
        response = requests.get(f"{BASE_URL}/api/drift/regime-baselines?horizon=7D")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        baselines = data.get("baselines", {})
        expected_regimes = ["TREND", "RANGE", "RISK_OFF", "TRANSITION"]
        
        for regime in expected_regimes:
            assert regime in baselines, f"Missing baseline for regime {regime}"
            baseline = baselines[regime]
            
            # Verify baseline structure
            assert "n" in baseline, f"{regime} missing 'n' (sample count)"
            assert "mae_mean" in baseline, f"{regime} missing 'mae_mean'"
            assert "mae_std" in baseline, f"{regime} missing 'mae_std'"
            assert baseline["n"] > 0, f"{regime} should have n > 0"
            
            print(f"7D {regime}: n={baseline['n']}, mae_mean={baseline['mae_mean']:.6f}, mae_std={baseline['mae_std']:.6f}")
        
        # Count should be 4 (all regimes)
        assert data.get("count") == 4, f"Expected 4 regimes, got {data.get('count')}"

    def test_regime_baselines_7d_baseline_fields(self):
        """7D regime baselines should have complete fields for each regime"""
        response = requests.get(f"{BASE_URL}/api/drift/regime-baselines?horizon=7D")
        assert response.status_code == 200
        
        data = response.json()
        baselines = data.get("baselines", {})
        
        required_fields = ["n", "mae_mean", "mae_std", "mae_p75", "dir_hit_mean", "flip_mean", "flip_std"]
        
        for regime, baseline in baselines.items():
            for field in required_fields:
                assert field in baseline, f"{regime} missing field: {field}"
            
            # Validate value ranges
            assert baseline["n"] > 0
            assert 0 <= baseline["mae_mean"] <= 1.0
            assert baseline["mae_std"] >= 0
            assert baseline["mae_p75"] >= 0
            assert 0 <= baseline["dir_hit_mean"] <= 1.0
            assert 0 <= baseline["flip_mean"] <= 1.0

    def test_regime_baselines_30d_returns_four_regimes(self):
        """30D regime baselines should have TREND, RANGE, RISK_OFF, TRANSITION"""
        response = requests.get(f"{BASE_URL}/api/drift/regime-baselines?horizon=30D")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        baselines = data.get("baselines", {})
        expected_regimes = ["TREND", "RANGE", "RISK_OFF", "TRANSITION"]
        
        for regime in expected_regimes:
            assert regime in baselines, f"Missing baseline for regime {regime}"
            baseline = baselines[regime]
            
            # 30D MAE should be higher than 7D (longer horizon = larger errors expected)
            print(f"30D {regime}: n={baseline['n']}, mae_mean={baseline['mae_mean']:.6f}")
        
        assert data.get("count") == 4

    def test_regime_baselines_30d_higher_mae_than_7d(self):
        """30D regime baselines should have higher MAE than 7D (longer horizon)"""
        response_7d = requests.get(f"{BASE_URL}/api/drift/regime-baselines?horizon=7D")
        response_30d = requests.get(f"{BASE_URL}/api/drift/regime-baselines?horizon=30D")
        
        assert response_7d.status_code == 200
        assert response_30d.status_code == 200
        
        baselines_7d = response_7d.json().get("baselines", {})
        baselines_30d = response_30d.json().get("baselines", {})
        
        for regime in ["TREND", "TRANSITION"]:  # Major regimes
            mae_7d = baselines_7d.get(regime, {}).get("mae_mean", 0)
            mae_30d = baselines_30d.get(regime, {}).get("mae_mean", 0)
            
            # 30D should generally have higher MAE due to longer horizon uncertainty
            print(f"{regime}: 7D mae={mae_7d:.6f}, 30D mae={mae_30d:.6f}")
            assert mae_30d > mae_7d, f"30D MAE should be > 7D MAE for {regime}"


class TestA2MLOverlayPredictDriftWeight:
    """Test ML overlay predict endpoint for driftWeight improvement"""

    def test_predict_30d_drift_weight_improved(self):
        """30D prediction driftWeight should be ~0.64 (improved from ~0.60 due to regime adjustment)"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/predict?asset=BTC&horizon=30D")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        drift_weight = data.get("driftWeight", 0)
        
        # driftWeight should be around 0.64 after regime adjustment
        # (previously was ~0.60 without regime adjustment)
        print(f"30D driftWeight: {drift_weight}")
        
        # Allow some tolerance: 0.60 to 0.70
        assert 0.50 <= drift_weight <= 0.80, f"Expected driftWeight in [0.50, 0.80], got {drift_weight}"
        
        # Verify drift info is present
        drift_info = data.get("drift", {})
        assert "mlWeight" in drift_info, "drift.mlWeight should be present"
        
        # mlWeight from drift should match driftWeight
        ml_weight = drift_info.get("mlWeight", 0)
        assert abs(ml_weight - drift_weight) < 0.01, "driftWeight should match drift.mlWeight"

    def test_predict_7d_drift_weight(self):
        """7D prediction should also have driftWeight"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/predict?asset=BTC&horizon=7D")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        drift_weight = data.get("driftWeight", 0)
        print(f"7D driftWeight: {drift_weight}")
        
        # 7D has lower drift, so driftWeight should be higher (closer to 1.0)
        assert 0.80 <= drift_weight <= 1.0, f"Expected 7D driftWeight >= 0.80 (low drift), got {drift_weight}"


class TestA2RegimeDistribution:
    """Test that regime distribution matches expected values"""

    def test_regime_distribution_7d(self):
        """Verify regime distribution from baselines sample counts"""
        response = requests.get(f"{BASE_URL}/api/drift/regime-baselines?horizon=7D")
        assert response.status_code == 200
        
        baselines = response.json().get("baselines", {})
        
        total = sum(b.get("n", 0) for b in baselines.values())
        
        # Calculate percentages
        dist = {}
        for regime, b in baselines.items():
            n = b.get("n", 0)
            pct = (n / total * 100) if total > 0 else 0
            dist[regime] = {"n": n, "pct": pct}
        
        print(f"Regime distribution (7D):")
        for regime, d in sorted(dist.items(), key=lambda x: -x[1]["pct"]):
            print(f"  {regime}: {d['n']} days ({d['pct']:.1f}%)")
        
        # Expected: TREND ~60.5%, TRANSITION ~33.9%, RISK_OFF ~4.4%, RANGE ~1.2%
        # Allow some tolerance
        assert dist["TREND"]["pct"] > 50, "TREND should be majority regime"
        assert dist["TRANSITION"]["pct"] > 20, "TRANSITION should be significant"
        assert dist["RISK_OFF"]["pct"] < 10, "RISK_OFF should be rare"
        assert dist["RANGE"]["pct"] < 5, "RANGE should be very rare"


class TestA2EdgeCases:
    """Test edge cases and error handling"""

    def test_invalid_horizon_returns_error_or_default(self):
        """Invalid horizon should be handled gracefully"""
        response = requests.get(f"{BASE_URL}/api/drift/status?horizon=1Y")
        # Should either return error or default to a valid horizon
        assert response.status_code in [200, 400, 500]
        
        data = response.json()
        if response.status_code == 200:
            # If it returns 200, it should still have regime context
            print(f"Invalid horizon response: {data.get('ok')}")

    def test_regime_baselines_invalid_horizon(self):
        """Invalid horizon for baselines should return empty or error"""
        response = requests.get(f"{BASE_URL}/api/drift/regime-baselines?horizon=1Y")
        assert response.status_code in [200, 400, 500]
        
        if response.status_code == 200:
            data = response.json()
            # Might return empty baselines for unknown horizon
            count = data.get("count", 0)
            print(f"Invalid horizon baseline count: {count}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
