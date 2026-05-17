"""
Block 20: Model Health Panel API Tests
Tests the /api/market/chart/price-vs-expectation-v2 endpoint for metrics data
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestModelHealthAPI:
    """Tests for Model Health Panel metrics in price-vs-expectation-v2 API"""
    
    def test_api_returns_metrics_object(self):
        """Verify API returns metrics object with required fields"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v2",
            params={"asset": "BTC", "range": "30d"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") == True, "API response should have ok=true"
        assert "metrics" in data, "Response should contain 'metrics' object"
        
        metrics = data["metrics"]
        print(f"Metrics received: {metrics}")
        
    def test_metrics_has_direction_accuracy(self):
        """Verify directionMatchPct is present and valid"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v2",
            params={"asset": "BTC", "range": "30d"}
        )
        
        assert response.status_code == 200
        metrics = response.json()["metrics"]
        
        assert "directionMatchPct" in metrics, "Should have directionMatchPct"
        assert isinstance(metrics["directionMatchPct"], (int, float)), "directionMatchPct should be numeric"
        assert 0 <= metrics["directionMatchPct"] <= 100, "directionMatchPct should be 0-100"
        print(f"Direction Accuracy: {metrics['directionMatchPct']}%")
        
    def test_metrics_has_hit_rate(self):
        """Verify hitRatePct is present and valid"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v2",
            params={"asset": "BTC", "range": "30d"}
        )
        
        assert response.status_code == 200
        metrics = response.json()["metrics"]
        
        assert "hitRatePct" in metrics, "Should have hitRatePct"
        assert isinstance(metrics["hitRatePct"], (int, float)), "hitRatePct should be numeric"
        assert 0 <= metrics["hitRatePct"] <= 100, "hitRatePct should be 0-100"
        print(f"Hit Rate: {metrics['hitRatePct']}%")
        
    def test_metrics_has_avg_deviation(self):
        """Verify avgDeviationPct is present and valid"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v2",
            params={"asset": "BTC", "range": "30d"}
        )
        
        assert response.status_code == 200
        metrics = response.json()["metrics"]
        
        assert "avgDeviationPct" in metrics, "Should have avgDeviationPct"
        assert isinstance(metrics["avgDeviationPct"], (int, float)), "avgDeviationPct should be numeric"
        assert metrics["avgDeviationPct"] >= 0, "avgDeviationPct should be non-negative"
        print(f"Avg Error: {metrics['avgDeviationPct']}%")
        
    def test_metrics_has_calibration_score(self):
        """Block 20 specific: Verify calibrationScore is present"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v2",
            params={"asset": "BTC", "range": "30d"}
        )
        
        assert response.status_code == 200
        metrics = response.json()["metrics"]
        
        assert "calibrationScore" in metrics, "Should have calibrationScore (Block 20 feature)"
        assert isinstance(metrics["calibrationScore"], (int, float)), "calibrationScore should be numeric"
        assert 0 <= metrics["calibrationScore"] <= 100, "calibrationScore should be 0-100"
        print(f"Calibration Score: {metrics['calibrationScore']}")
        
    def test_metrics_has_expected_calibration(self):
        """Block 20 specific: Verify expectedCalibration is present"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v2",
            params={"asset": "BTC", "range": "30d"}
        )
        
        assert response.status_code == 200
        metrics = response.json()["metrics"]
        
        assert "expectedCalibration" in metrics, "Should have expectedCalibration (Block 20 feature)"
        assert isinstance(metrics["expectedCalibration"], (int, float)), "expectedCalibration should be numeric"
        print(f"Expected Calibration: {metrics['expectedCalibration']}%")
        
    def test_metrics_has_model_score(self):
        """Block 20 specific: Verify modelScore is present"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v2",
            params={"asset": "BTC", "range": "30d"}
        )
        
        assert response.status_code == 200
        metrics = response.json()["metrics"]
        
        assert "modelScore" in metrics, "Should have modelScore (Block 20 feature)"
        assert isinstance(metrics["modelScore"], (int, float)), "modelScore should be numeric"
        assert 0 <= metrics["modelScore"] <= 100, "modelScore should be 0-100"
        print(f"Model Score: {metrics['modelScore']}/100")
        
    def test_metrics_has_evaluated_count(self):
        """Verify evaluatedCount (Samples) is present"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v2",
            params={"asset": "BTC", "range": "30d"}
        )
        
        assert response.status_code == 200
        metrics = response.json()["metrics"]
        
        assert "evaluatedCount" in metrics, "Should have evaluatedCount (Samples)"
        assert isinstance(metrics["evaluatedCount"], int), "evaluatedCount should be integer"
        assert metrics["evaluatedCount"] >= 0, "evaluatedCount should be non-negative"
        print(f"Samples: {metrics['evaluatedCount']}")
        
    def test_metrics_has_breakdown(self):
        """Verify breakdown (TP/FP/FN/WEAK) is present"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v2",
            params={"asset": "BTC", "range": "30d"}
        )
        
        assert response.status_code == 200
        metrics = response.json()["metrics"]
        
        assert "breakdown" in metrics, "Should have breakdown object"
        breakdown = metrics["breakdown"]
        
        assert "tp" in breakdown, "Breakdown should have 'tp'"
        assert "fp" in breakdown, "Breakdown should have 'fp'"
        assert "fn" in breakdown, "Breakdown should have 'fn'"
        assert "weak" in breakdown, "Breakdown should have 'weak'"
        
        # All should be non-negative integers
        for key in ["tp", "fp", "fn", "weak"]:
            assert isinstance(breakdown[key], int), f"{key} should be integer"
            assert breakdown[key] >= 0, f"{key} should be non-negative"
        
        print(f"Breakdown - TP: {breakdown['tp']}, FP: {breakdown['fp']}, FN: {breakdown['fn']}, WEAK: {breakdown['weak']}")
        
    def test_expected_values_from_test_data(self):
        """Verify expected values match test data: directionMatchPct=80, hitRatePct=40, avgDeviationPct=2.48, calibrationScore=76, modelScore=67, evaluatedCount=5"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v2",
            params={"asset": "BTC", "range": "30d"}
        )
        
        assert response.status_code == 200
        metrics = response.json()["metrics"]
        
        # Verify expected values from agent_to_agent_context_note
        assert metrics["directionMatchPct"] == 80, f"Expected directionMatchPct=80, got {metrics['directionMatchPct']}"
        assert metrics["hitRatePct"] == 40, f"Expected hitRatePct=40, got {metrics['hitRatePct']}"
        assert metrics["avgDeviationPct"] == 2.48, f"Expected avgDeviationPct=2.48, got {metrics['avgDeviationPct']}"
        assert metrics["calibrationScore"] == 76, f"Expected calibrationScore=76, got {metrics['calibrationScore']}"
        assert metrics["modelScore"] == 67, f"Expected modelScore=67, got {metrics['modelScore']}"
        assert metrics["evaluatedCount"] == 5, f"Expected evaluatedCount=5, got {metrics['evaluatedCount']}"
        
        # Verify breakdown
        breakdown = metrics["breakdown"]
        assert breakdown["tp"] == 2, f"Expected tp=2, got {breakdown['tp']}"
        assert breakdown["fp"] == 1, f"Expected fp=1, got {breakdown['fp']}"
        assert breakdown["fn"] == 1, f"Expected fn=1, got {breakdown['fn']}"
        assert breakdown["weak"] == 1, f"Expected weak=1, got {breakdown['weak']}"
        
        print("All expected values match test data!")
        
    def test_horizon_in_metrics(self):
        """Verify horizon is correctly returned in metrics"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v2",
            params={"asset": "BTC", "range": "30d", "horizon": "1D"}
        )
        
        assert response.status_code == 200
        metrics = response.json()["metrics"]
        
        assert "horizon" in metrics, "Should have horizon field"
        assert metrics["horizon"] == "1D", f"Expected horizon=1D, got {metrics['horizon']}"
        print(f"Horizon: {metrics['horizon']}")


class TestModelHealthEmptyState:
    """Tests for empty state when no evaluated forecasts"""
    
    def test_different_asset_returns_metrics(self):
        """Test that other assets also return metrics structure (may be empty)"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v2",
            params={"asset": "ETH", "range": "30d"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "metrics" in data, "Response should contain metrics even for other assets"
        metrics = data["metrics"]
        
        # Should have all required fields even if values are 0
        required_fields = ["directionMatchPct", "hitRatePct", "avgDeviationPct", 
                          "calibrationScore", "expectedCalibration", "modelScore", 
                          "evaluatedCount", "breakdown"]
        for field in required_fields:
            assert field in metrics, f"Should have {field} even for assets with no data"
        
        print(f"ETH metrics: evaluatedCount={metrics['evaluatedCount']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
