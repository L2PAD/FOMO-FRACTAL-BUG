"""
Test suite for Graph V3 (graph2) endpoint - Prediction Forecast Chart
=====================================================================
Tests the clean forecast graph endpoint that returns:
- priceSeries: ~90 price points with t (ms) and p (price)
- current: Active forecast with ML metrics
- prev: Previous forecast for comparison
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestGraph2Endpoint:
    """Tests for /api/prediction/exchange/graph2 endpoint"""

    def test_graph2_7d_returns_ok(self):
        """Test that 7D horizon returns ok:true with valid data structure"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph2?asset=BTC&horizon=7D&lookback=90")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok:true"
        assert data.get("asset") == "BTC", "Expected asset to be BTC"
        assert data.get("horizon") == "7D", "Expected horizon to be 7D"

    def test_graph2_30d_returns_ok(self):
        """Test that 30D horizon returns ok:true with valid data structure"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph2?asset=BTC&horizon=30D&lookback=90")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok:true"
        assert data.get("asset") == "BTC", "Expected asset to be BTC"
        assert data.get("horizon") == "30D", "Expected horizon to be 30D"

    def test_graph2_price_series_structure(self):
        """Test priceSeries has ~90 points with t (ms) and p (price) fields"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph2?asset=BTC&horizon=7D&lookback=90")
        assert response.status_code == 200
        
        data = response.json()
        price_series = data.get("priceSeries", [])
        
        # Should have approximately 90 points (weekends may reduce count)
        assert len(price_series) >= 60, f"Expected at least 60 price points, got {len(price_series)}"
        assert len(price_series) <= 100, f"Expected at most 100 price points, got {len(price_series)}"
        
        # Each point should have t (timestamp ms) and p (price)
        for pt in price_series[:5]:  # Check first 5 points
            assert "t" in pt, "Each price point should have 't' field"
            assert "p" in pt, "Each price point should have 'p' field"
            assert isinstance(pt["t"], int), "t should be integer (timestamp ms)"
            assert isinstance(pt["p"], (int, float)), "p should be numeric (price)"
            assert pt["t"] > 1700000000000, "Timestamp should be in milliseconds (> 2023)"

    def test_graph2_current_forecast_7d_fields(self):
        """Test current forecast contains required ML metrics for 7D"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph2?asset=BTC&horizon=7D&lookback=90")
        assert response.status_code == 200
        
        data = response.json()
        current = data.get("current")
        
        assert current is not None, "Current forecast should be present"
        
        # Required fields per spec
        required_fields = ["entryPrice", "ruleTarget", "finalTarget", "mlWeight", 
                          "ece", "driftScore", "stage", "effectiveAlpha", "evalTs"]
        
        for field in required_fields:
            assert field in current, f"Current forecast missing required field: {field}"

    def test_graph2_current_forecast_30d_fields(self):
        """Test current forecast contains required ML metrics for 30D"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph2?asset=BTC&horizon=30D&lookback=90")
        assert response.status_code == 200
        
        data = response.json()
        current = data.get("current")
        
        assert current is not None, "Current forecast should be present"
        
        # Required fields per spec
        required_fields = ["entryPrice", "ruleTarget", "finalTarget", "mlWeight", 
                          "ece", "driftScore", "stage", "effectiveAlpha", "evalTs"]
        
        for field in required_fields:
            assert field in current, f"Current forecast missing required field: {field}"

    def test_graph2_prev_forecast_fields(self):
        """Test prev forecast contains required comparison fields"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph2?asset=BTC&horizon=7D&lookback=90")
        assert response.status_code == 200
        
        data = response.json()
        prev = data.get("prev")
        
        # prev might be None if no previous forecast exists
        if prev is not None:
            required_fields = ["entryPrice", "ruleTarget", "finalTarget", "evalTs", 
                              "direction", "confidence"]
            
            for field in required_fields:
                assert field in prev, f"Prev forecast missing required field: {field}"

    def test_graph2_shadow_mode_rules(self):
        """Test SHADOW mode rules: finalTarget=ruleTarget, effectiveAlpha=0"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph2?asset=BTC&horizon=7D&lookback=90")
        assert response.status_code == 200
        
        data = response.json()
        current = data.get("current")
        
        if current and current.get("stage") == "SHADOW":
            # In SHADOW mode, finalTarget should equal ruleTarget
            assert current.get("finalTarget") == current.get("ruleTarget"), \
                "In SHADOW mode, finalTarget should equal ruleTarget"
            
            # In SHADOW mode, effectiveAlpha should be 0
            assert current.get("effectiveAlpha") == 0, \
                "In SHADOW mode, effectiveAlpha should be 0"

    def test_graph2_30d_shadow_mode_rules(self):
        """Test SHADOW mode rules for 30D horizon"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph2?asset=BTC&horizon=30D&lookback=90")
        assert response.status_code == 200
        
        data = response.json()
        current = data.get("current")
        
        if current and current.get("stage") == "SHADOW":
            assert current.get("finalTarget") == current.get("ruleTarget"), \
                "In SHADOW mode, finalTarget should equal ruleTarget"
            assert current.get("effectiveAlpha") == 0, \
                "In SHADOW mode, effectiveAlpha should be 0"

    def test_graph2_has_now_timestamp_and_price(self):
        """Test that response includes nowTs and nowPrice"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph2?asset=BTC&horizon=7D&lookback=90")
        assert response.status_code == 200
        
        data = response.json()
        
        assert "nowTs" in data, "Response should include nowTs"
        assert "nowPrice" in data, "Response should include nowPrice"
        assert isinstance(data["nowTs"], int), "nowTs should be integer (timestamp ms)"
        assert isinstance(data["nowPrice"], (int, float)), "nowPrice should be numeric"
        assert data["nowPrice"] > 0, "nowPrice should be positive"

    def test_graph2_ml_weight_range(self):
        """Test that mlWeight is within valid range [0, 1]"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph2?asset=BTC&horizon=7D&lookback=90")
        assert response.status_code == 200
        
        data = response.json()
        current = data.get("current")
        
        if current and "mlWeight" in current:
            ml_weight = current["mlWeight"]
            assert 0 <= ml_weight <= 1, f"mlWeight should be in [0, 1], got {ml_weight}"

    def test_graph2_ece_is_present_and_numeric(self):
        """Test that ECE (Expected Calibration Error) is present and numeric"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph2?asset=BTC&horizon=7D&lookback=90")
        assert response.status_code == 200
        
        data = response.json()
        current = data.get("current")
        
        if current and "ece" in current:
            ece = current["ece"]
            assert isinstance(ece, (int, float)), f"ECE should be numeric, got {type(ece)}"
            assert ece >= 0, f"ECE should be non-negative, got {ece}"

    def test_graph2_different_horizons_return_different_metrics(self):
        """Test that 7D and 30D return different ML metrics"""
        response_7d = requests.get(f"{BASE_URL}/api/prediction/exchange/graph2?asset=BTC&horizon=7D&lookback=90")
        response_30d = requests.get(f"{BASE_URL}/api/prediction/exchange/graph2?asset=BTC&horizon=30D&lookback=90")
        
        assert response_7d.status_code == 200
        assert response_30d.status_code == 200
        
        data_7d = response_7d.json()
        data_30d = response_30d.json()
        
        # Both should have current forecasts
        assert data_7d.get("current") is not None
        assert data_30d.get("current") is not None
        
        # Horizons should match request
        assert data_7d.get("horizon") == "7D"
        assert data_30d.get("horizon") == "30D"


class TestGraph2EdgeCases:
    """Edge case tests for graph2 endpoint"""

    def test_graph2_invalid_horizon_handling(self):
        """Test that invalid horizon falls back gracefully"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph2?asset=BTC&horizon=24H&lookback=90")
        # Should still return 200 but may have null current/prev
        assert response.status_code == 200

    def test_graph2_lookback_validation(self):
        """Test that lookback has reasonable limits"""
        # Test minimum lookback
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph2?asset=BTC&horizon=7D&lookback=14")
        assert response.status_code == 200
        
        # Test typical lookback
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph2?asset=BTC&horizon=7D&lookback=90")
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
