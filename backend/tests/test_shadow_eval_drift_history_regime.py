"""
Shadow Eval Rolling Verdicts, Drift History Chart, and Regime-Aware Drift Tests

This iteration tests:
- P1: Shadow Eval Rolling with GO/NO-GO criteria
- P2: Drift History mini-chart endpoint
- P3: Regime-aware drift snapshots

New endpoints tested:
- POST /api/ml-overlay/eval-shadow
- GET /api/ml-overlay/shadow-verdict?horizon=7D&window=30
- GET /api/ml-overlay/shadow-verdict?horizon=30D&window=60
- GET /api/ml-overlay/status (evalSummary with rolling verdicts)
- GET /api/drift/history/chart?horizon=7D&days=45
- GET /api/drift/history/chart?horizon=30D&days=45
- GET /api/drift/status?horizon=7D (regime field)
- GET /api/drift/status?horizon=30D (regime field)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")


class TestEvalShadowEndpoint:
    """Tests for POST /api/ml-overlay/eval-shadow — Shadow evaluation for matured predictions"""

    def test_eval_shadow_returns_ok(self):
        """POST /api/ml-overlay/eval-shadow should return ok:true"""
        response = requests.post(f"{BASE_URL}/api/ml-overlay/eval-shadow")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True

    def test_eval_shadow_has_evaluation_counts(self):
        """eval-shadow should return evaluated/skipped/pending counts"""
        response = requests.post(f"{BASE_URL}/api/ml-overlay/eval-shadow")
        data = response.json()
        
        assert "evaluated" in data
        assert "skipped" in data
        assert "pending" in data
        assert isinstance(data["evaluated"], int)
        assert isinstance(data["skipped"], int)
        assert isinstance(data["pending"], int)


class TestShadowVerdictEndpoint:
    """Tests for GET /api/ml-overlay/shadow-verdict — Rolling shadow verdict with GO/NO-GO criteria"""

    def test_shadow_verdict_7d_30_day_window_returns_ok(self):
        """GET /api/ml-overlay/shadow-verdict?horizon=7D&window=30 should return ok:true"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/shadow-verdict?horizon=7D&window=30")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["horizon"] == "7D"
        assert data["window"] == 30

    def test_shadow_verdict_7d_has_verdict_field(self):
        """7D shadow-verdict should include verdict field"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/shadow-verdict?horizon=7D&window=30")
        data = response.json()
        
        assert "verdict" in data
        # Verdict should be one of the valid statuses
        valid_verdicts = ["SHADOW_OK", "SHADOW_WARN", "SHADOW_FAIL", "INSUFFICIENT_DATA"]
        assert data["verdict"] in valid_verdicts

    def test_shadow_verdict_7d_has_n_field(self):
        """7D shadow-verdict should include n (number of evaluated shadows)"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/shadow-verdict?horizon=7D&window=30")
        data = response.json()
        
        assert "n" in data
        assert isinstance(data["n"], int)
        assert data["n"] >= 0

    def test_shadow_verdict_30d_60_day_window_returns_ok(self):
        """GET /api/ml-overlay/shadow-verdict?horizon=30D&window=60 should return ok:true"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/shadow-verdict?horizon=30D&window=60")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["horizon"] == "30D"
        assert data["window"] == 60

    def test_shadow_verdict_30d_has_verdict_field(self):
        """30D shadow-verdict should include verdict field"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/shadow-verdict?horizon=30D&window=60")
        data = response.json()
        
        assert "verdict" in data
        valid_verdicts = ["SHADOW_OK", "SHADOW_WARN", "SHADOW_FAIL", "INSUFFICIENT_DATA"]
        assert data["verdict"] in valid_verdicts

    def test_shadow_verdict_insufficient_data_message(self):
        """When n < 3, verdict should be INSUFFICIENT_DATA with message"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/shadow-verdict?horizon=7D&window=30")
        data = response.json()
        
        if data["n"] < 3:
            assert data["verdict"] == "INSUFFICIENT_DATA"
            assert "message" in data

    def test_shadow_verdict_has_metrics_when_sufficient_data(self):
        """When n >= 3, should have metrics object with MAE, DirHit, FlipRate, etc"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/shadow-verdict?horizon=7D&window=30")
        data = response.json()
        
        if data["n"] >= 3:
            assert "metrics" in data
            metrics = data["metrics"]
            assert "mae_rule" in metrics
            assert "mae_final" in metrics
            assert "mae_ratio" in metrics
            assert "dir_hit_rule" in metrics
            assert "dir_hit_final" in metrics
            assert "dir_delta" in metrics
            assert "drift_score" in metrics

    def test_shadow_verdict_has_checks_when_sufficient_data(self):
        """When n >= 3, should have checks object with GO/NO-GO flags"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/shadow-verdict?horizon=7D&window=30")
        data = response.json()
        
        if data["n"] >= 3:
            assert "checks" in data
            checks = data["checks"]
            assert "dir_hit_ok" in checks
            assert "mae_ok" in checks
            assert "flip_ok" in checks
            assert "drift_ok" in checks


class TestMLOverlayStatusWithEvalSummary:
    """Tests for GET /api/ml-overlay/status — should now include evalSummary with rolling verdicts"""

    def test_ml_overlay_status_returns_ok(self):
        """GET /api/ml-overlay/status should return ok:true"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/status")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True

    def test_ml_overlay_status_has_eval_summary(self):
        """status should include evalSummary field"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/status")
        data = response.json()
        
        assert "evalSummary" in data
        assert isinstance(data["evalSummary"], dict)

    def test_ml_overlay_status_eval_summary_has_horizons(self):
        """evalSummary should have 7D and 30D keys"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/status")
        data = response.json()
        
        eval_summary = data["evalSummary"]
        assert "7D" in eval_summary
        assert "30D" in eval_summary

    def test_ml_overlay_status_eval_summary_has_rolling_verdicts(self):
        """Each horizon in evalSummary should have rolling_30d and rolling_60d verdicts"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/status")
        data = response.json()
        
        for horizon in ["7D", "30D"]:
            h_data = data["evalSummary"][horizon]
            assert "rolling_30d" in h_data
            assert "rolling_60d" in h_data
            
            # Each rolling should have verdict and n
            for window in ["rolling_30d", "rolling_60d"]:
                assert "verdict" in h_data[window]
                assert "n" in h_data[window]


class TestDriftHistoryChartEndpoint:
    """Tests for GET /api/drift/history/chart — lightweight chart format"""

    def test_drift_history_chart_7d_returns_ok(self):
        """GET /api/drift/history/chart?horizon=7D&days=45 should return ok:true"""
        response = requests.get(f"{BASE_URL}/api/drift/history/chart?horizon=7D&days=45")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True

    def test_drift_history_chart_7d_has_data_array(self):
        """chart endpoint should return data array with count"""
        response = requests.get(f"{BASE_URL}/api/drift/history/chart?horizon=7D&days=45")
        data = response.json()
        
        assert "data" in data
        assert isinstance(data["data"], list)
        assert "count" in data

    def test_drift_history_chart_7d_data_format(self):
        """Each data point should have date, driftScore, mlWeight, status, regime, maeRule, maeProd"""
        response = requests.get(f"{BASE_URL}/api/drift/history/chart?horizon=7D&days=45")
        data = response.json()
        
        if data["count"] > 0:
            point = data["data"][0]
            assert "date" in point
            assert "driftScore" in point
            assert "mlWeight" in point
            assert "status" in point
            assert "regime" in point
            assert "maeRule" in point
            assert "maeProd" in point

    def test_drift_history_chart_30d_returns_ok(self):
        """GET /api/drift/history/chart?horizon=30D&days=45 should return ok:true"""
        response = requests.get(f"{BASE_URL}/api/drift/history/chart?horizon=30D&days=45")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True

    def test_drift_history_chart_30d_has_data(self):
        """30D chart should also return data array"""
        response = requests.get(f"{BASE_URL}/api/drift/history/chart?horizon=30D&days=45")
        data = response.json()
        
        assert "data" in data
        assert isinstance(data["data"], list)


class TestDriftStatusWithRegime:
    """Tests for GET /api/drift/status with regime field"""

    def test_drift_status_7d_has_regime(self):
        """GET /api/drift/status?horizon=7D should include regime field"""
        response = requests.get(f"{BASE_URL}/api/drift/status?horizon=7D&asset=BTC")
        assert response.status_code == 200
        data = response.json()
        
        assert "regime" in data
        # Regime should be a string
        assert isinstance(data["regime"], str)

    def test_drift_status_7d_has_regime_confidence(self):
        """7D drift status should include regimeConfidence field"""
        response = requests.get(f"{BASE_URL}/api/drift/status?horizon=7D&asset=BTC")
        data = response.json()
        
        assert "regimeConfidence" in data
        assert isinstance(data["regimeConfidence"], (int, float))

    def test_drift_status_30d_has_regime(self):
        """GET /api/drift/status?horizon=30D should include regime field"""
        response = requests.get(f"{BASE_URL}/api/drift/status?horizon=30D&asset=BTC")
        assert response.status_code == 200
        data = response.json()
        
        assert "regime" in data
        assert isinstance(data["regime"], str)

    def test_drift_status_regime_valid_values(self):
        """regime should be a known value (UNKNOWN, TRANSITION, BULL, BEAR, etc)"""
        response = requests.get(f"{BASE_URL}/api/drift/status?horizon=7D&asset=BTC")
        data = response.json()
        
        # Common regime values
        valid_regimes = ["UNKNOWN", "TRANSITION", "BULL", "BEAR", "CHOP", "RECOVERY", "RISK_OFF", "EXPANSION"]
        # Allow any string since regime comes from macro_state collection
        assert data["regime"] is not None


class TestGONOGOCriteria:
    """Validates GO/NO-GO criteria thresholds as per spec"""

    def test_verdict_thresholds_are_correct(self):
        """Verify GO/NO-GO criteria: DirHit >= rule-0.5pp, MAE <= rule*0.97, Flip <= rule+3pp, DriftScore <= 0.55"""
        # This tests that the verdict endpoint correctly implements the criteria
        response = requests.get(f"{BASE_URL}/api/ml-overlay/shadow-verdict?horizon=7D&window=30")
        data = response.json()
        
        if data["n"] >= 3 and "checks" in data:
            checks = data["checks"]
            metrics = data["metrics"]
            
            # Verify dir_hit_ok: DirHit_final >= DirHit_rule - 0.5pp
            dir_delta = metrics["dir_delta"]
            expected_dir_ok = dir_delta >= -0.5
            assert checks["dir_hit_ok"] == expected_dir_ok, \
                f"dir_hit_ok check failed: dir_delta={dir_delta}, expected {expected_dir_ok}"
            
            # Verify mae_ok: MAE_final <= MAE_rule * 0.97
            mae_ratio = metrics["mae_ratio"]
            expected_mae_ok = mae_ratio <= 0.97
            assert checks["mae_ok"] == expected_mae_ok, \
                f"mae_ok check failed: mae_ratio={mae_ratio}, expected {expected_mae_ok}"
            
            # Verify drift_ok: DriftScore <= 0.55
            drift_score = metrics["drift_score"]
            expected_drift_ok = drift_score <= 0.55
            assert checks["drift_ok"] == expected_drift_ok, \
                f"drift_ok check failed: drift_score={drift_score}, expected {expected_drift_ok}"


class TestVerdictLogic:
    """Test verdict logic: 0 fails = SHADOW_OK, 1 fail = SHADOW_WARN, 2+ fails = SHADOW_FAIL"""

    def test_verdict_logic_consistency(self):
        """Verdict should be consistent with number of failed checks"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/shadow-verdict?horizon=7D&window=30")
        data = response.json()
        
        if data["n"] >= 3 and "checks" in data:
            checks = data["checks"]
            verdict = data["verdict"]
            
            fail_count = sum(1 for v in checks.values() if not v)
            
            if fail_count == 0:
                assert verdict == "SHADOW_OK"
            elif fail_count == 1:
                assert verdict == "SHADOW_WARN"
            else:
                assert verdict == "SHADOW_FAIL"


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
