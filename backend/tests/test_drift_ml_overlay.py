"""
Drift Monitoring & ML Overlay API Tests
Tests the drift detection system with auto-downweighting ML model via exp(-alpha * driftScore).
Validates: drift status, weight, history endpoints + ML overlay predict with drift integration.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")

class TestDriftStatusAPI:
    """Tests for /api/drift/status endpoint"""

    def test_drift_status_7d_returns_ok(self):
        """GET /api/drift/status?horizon=7D&asset=BTC should return ok:true"""
        response = requests.get(f"{BASE_URL}/api/drift/status?horizon=7D&asset=BTC")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["asset"] == "BTC"
        assert data["horizon"] == "7D"

    def test_drift_status_7d_has_required_fields(self):
        """7D status should include driftScore, mlWeight, status, components, drivers, performance, features, calibration"""
        response = requests.get(f"{BASE_URL}/api/drift/status?horizon=7D&asset=BTC")
        data = response.json()
        
        assert "driftScore" in data
        assert "mlWeight" in data
        assert "status" in data
        assert "components" in data
        assert "drivers" in data
        assert "performance" in data
        assert "features" in data
        assert "calibration" in data
        
        # Components structure
        components = data["components"]
        assert "psi" in components
        assert "dirHitDrop" in components
        assert "maeGrowth" in components
        assert "flipSpike" in components

    def test_drift_status_7d_ok_status_mlweight_1(self):
        """7D drift should be OK with mlWeight near 1.0 (no significant drift)"""
        response = requests.get(f"{BASE_URL}/api/drift/status?horizon=7D&asset=BTC")
        data = response.json()
        
        # 7D should be OK per main agent context
        assert data["status"] == "OK"
        assert data["mlWeight"] >= 0.95  # Should be 1.0 or close
        assert data["driftScore"] < 0.25  # Below WATCH threshold

    def test_drift_status_30d_watch_status_with_mae_growth(self):
        """GET /api/drift/status?horizon=30D should return status=WATCH since MAE has growth"""
        response = requests.get(f"{BASE_URL}/api/drift/status?horizon=30D&asset=BTC")
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert data["horizon"] == "30D"
        # 30D should have detected drift (WATCH status)
        assert data["status"] in ["WATCH", "DRIFT"]
        # mlWeight should be auto-downweighted
        assert data["mlWeight"] < 1.0
        # MAE growth should be a driver
        assert data["components"]["maeGrowth"] > 0

    def test_drift_status_30d_mlweight_around_060(self):
        """30D mlWeight should be ~0.60 due to auto-downweighting"""
        response = requests.get(f"{BASE_URL}/api/drift/status?horizon=30D&asset=BTC")
        data = response.json()
        
        # mlWeight should be between 0.50 and 0.75 (around 0.60)
        assert 0.50 <= data["mlWeight"] <= 0.75, f"mlWeight {data['mlWeight']} not in expected range"

    def test_drift_status_30d_has_drivers(self):
        """30D should have drift drivers explaining the downweighting"""
        response = requests.get(f"{BASE_URL}/api/drift/status?horizon=30D&asset=BTC")
        data = response.json()
        
        drivers = data["drivers"]
        assert isinstance(drivers, list)
        # Should have at least one driver (MAE growth)
        if data["driftScore"] > 0.05:
            assert len(drivers) > 0
            # Check driver structure
            for driver in drivers:
                assert "name" in driver
                assert "value" in driver
                assert "contribution" in driver


class TestDriftWeightAPI:
    """Tests for /api/drift/weight endpoint"""

    def test_drift_weight_7d_returns_ok(self):
        """GET /api/drift/weight?horizon=7D should return ok:true with mlWeight and driftScore"""
        response = requests.get(f"{BASE_URL}/api/drift/weight?horizon=7D")
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "mlWeight" in data
        assert "driftScore" in data
        assert "status" in data
        assert "drivers" in data

    def test_drift_weight_7d_values(self):
        """7D weight should be 1.0 (no drift)"""
        response = requests.get(f"{BASE_URL}/api/drift/weight?horizon=7D")
        data = response.json()
        
        assert data["mlWeight"] >= 0.95
        assert data["status"] == "OK"


class TestDriftHistoryAPI:
    """Tests for /api/drift/history endpoint"""

    def test_drift_history_returns_ok(self):
        """GET /api/drift/history?horizon=7D&days=30 should return ok:true with history array"""
        response = requests.get(f"{BASE_URL}/api/drift/history?horizon=7D&days=30")
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "history" in data
        assert isinstance(data["history"], list)
        assert "count" in data

    def test_drift_history_has_snapshots(self):
        """History should contain snapshot documents with required fields"""
        response = requests.get(f"{BASE_URL}/api/drift/history?horizon=7D&days=30")
        data = response.json()
        
        if data["count"] > 0:
            snapshot = data["history"][0]
            assert "date" in snapshot
            assert "driftScore" in snapshot
            assert "mlWeight" in snapshot
            assert "status" in snapshot


class TestMLOverlayPredictWithDrift:
    """Tests for /api/ml-overlay/predict endpoint with drift integration"""

    def test_ml_overlay_predict_7d_returns_ok(self):
        """GET /api/ml-overlay/predict?asset=BTC&horizon=7D should return ok:true"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/predict?asset=BTC&horizon=7D")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True

    def test_ml_overlay_predict_7d_has_drift_fields(self):
        """7D predict should include driftWeight, drift, mlCorrectionBeforeDrift"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/predict?asset=BTC&horizon=7D")
        data = response.json()
        
        assert "driftWeight" in data
        assert "drift" in data
        assert "mlCorrectionBeforeDrift" in data
        assert data["mode"] == "SHADOW"

    def test_ml_overlay_predict_7d_drift_weight_1(self):
        """7D driftWeight should be 1.0 (no downweighting)"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/predict?asset=BTC&horizon=7D")
        data = response.json()
        
        assert data["driftWeight"] >= 0.95
        assert data["drift"]["mlWeight"] >= 0.95

    def test_ml_overlay_predict_30d_auto_downweighting(self):
        """GET /api/ml-overlay/predict?asset=BTC&horizon=30D should have driftWeight < 1.0"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/predict?asset=BTC&horizon=30D")
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        # 30D has detected drift, so driftWeight should be < 1.0
        assert data["driftWeight"] < 1.0, f"Expected driftWeight < 1.0, got {data['driftWeight']}"
        # Should be around 0.60
        assert 0.50 <= data["driftWeight"] <= 0.75

    def test_ml_overlay_predict_30d_drift_source(self):
        """30D drift info should have source = drift_snapshot"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/predict?asset=BTC&horizon=30D")
        data = response.json()
        
        assert data["drift"]["source"] == "drift_snapshot"

    def test_ml_overlay_predict_30d_correction_weighted(self):
        """30D mlCorrection should be less than mlCorrectionBeforeDrift due to drift weighting"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/predict?asset=BTC&horizon=30D")
        data = response.json()
        
        ml_corr = data["mlCorrection"]
        ml_corr_before = data["mlCorrectionBeforeDrift"]
        drift_weight = data["driftWeight"]
        
        # If there's drift weighting, the final correction should be reduced
        if drift_weight < 0.99:
            # mlCorrection = mlCorrectionBeforeDrift * driftWeight (approximately)
            expected_ratio = ml_corr / ml_corr_before if ml_corr_before != 0 else 1.0
            # Allow some tolerance due to capping and other gates
            assert expected_ratio <= 1.0, "mlCorrection should not exceed mlCorrectionBeforeDrift"


class TestDriftScoreFormula:
    """Validation tests for drift score formula: driftScore = 0.4*PSI + 0.3*DirHit_drop + 0.2*MAE_growth + 0.1*FlipRate_spike"""

    def test_drift_score_bounded_0_1(self):
        """driftScore should be between 0 and 1"""
        for horizon in ["7D", "30D"]:
            response = requests.get(f"{BASE_URL}/api/drift/status?horizon={horizon}&asset=BTC")
            data = response.json()
            assert 0 <= data["driftScore"] <= 1.0

    def test_mlweight_formula_exp_decay(self):
        """mlWeight = exp(-2.0 * driftScore) should match approximately"""
        import math
        
        for horizon in ["7D", "30D"]:
            response = requests.get(f"{BASE_URL}/api/drift/status?horizon={horizon}&asset=BTC")
            data = response.json()
            
            drift_score = data["driftScore"]
            ml_weight = data["mlWeight"]
            expected_weight = math.exp(-2.0 * drift_score)
            
            # Allow 1% tolerance for rounding
            assert abs(ml_weight - expected_weight) < 0.01, \
                f"mlWeight {ml_weight} != exp(-2.0 * {drift_score}) = {expected_weight}"

    def test_status_thresholds(self):
        """Status thresholds: OK < 0.25, WATCH 0.25-0.5, DRIFT >= 0.5"""
        for horizon in ["7D", "30D"]:
            response = requests.get(f"{BASE_URL}/api/drift/status?horizon={horizon}&asset=BTC")
            data = response.json()
            
            drift_score = data["driftScore"]
            status = data["status"]
            
            if drift_score < 0.25:
                assert status == "OK"
            elif drift_score < 0.5:
                assert status == "WATCH"
            else:
                assert status == "DRIFT"
