"""
Test Graph V3 API - Rolling Forecast Evolution
================================================
Tests the new /api/prediction/exchange/graph3 endpoint which returns:
- priceSeries: historical prices
- rollingForecasts: last N daily forecasts (N = horizon days)
- ml object: ML metrics (weight, drift, ece, stage)

This is the final V3 chart API with rolling evolution, NO artificial curves.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestGraph3Endpoint:
    """Graph V3 rolling evolution endpoint tests"""

    # === 7D Horizon Tests ===
    def test_graph3_7d_returns_ok(self):
        """GET /api/prediction/exchange/graph3?asset=BTC&horizon=7D returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=7D")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("asset") == "BTC"
        assert data.get("horizon") == "7D"

    def test_graph3_7d_has_price_series(self):
        """7D response contains priceSeries with t and p fields"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=7D")
        data = response.json()
        
        price_series = data.get("priceSeries", [])
        assert len(price_series) > 0, "priceSeries should not be empty"
        
        # Check first price point structure
        first_pt = price_series[0]
        assert "t" in first_pt, "Each price point needs 't' (timestamp)"
        assert "p" in first_pt, "Each price point needs 'p' (price)"
        assert isinstance(first_pt["t"], int), "timestamp should be int (ms)"
        assert isinstance(first_pt["p"], (int, float)), "price should be numeric"

    def test_graph3_7d_returns_7_rolling_forecasts(self):
        """7D horizon returns exactly 7 rolling forecasts"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=7D")
        data = response.json()
        
        rolling = data.get("rollingForecasts", [])
        assert len(rolling) == 7, f"7D should return 7 forecasts, got {len(rolling)}"

    def test_graph3_7d_rolling_forecast_structure(self):
        """Each rolling forecast has required fields"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=7D")
        data = response.json()
        
        rolling = data.get("rollingForecasts", [])
        required_fields = [
            "createdBucket", "evalTs", "entryPrice", "ruleTarget", 
            "finalTarget", "direction", "confidence", "actual", "outcomeLabel"
        ]
        
        for i, f in enumerate(rolling):
            for field in required_fields:
                assert field in f, f"Rolling forecast {i} missing '{field}'"

    def test_graph3_7d_has_ml_object(self):
        """7D response contains ml object with metrics"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=7D")
        data = response.json()
        
        ml = data.get("ml")
        assert ml is not None, "Response should contain 'ml' object"
        assert "mlWeight" in ml, "ml object needs 'mlWeight'"
        assert "driftScore" in ml, "ml object needs 'driftScore'"
        assert "ece" in ml, "ml object needs 'ece'"
        assert "stage" in ml, "ml object needs 'stage'"

    def test_graph3_7d_has_current_and_prev(self):
        """7D response contains current and prev forecast objects"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=7D")
        data = response.json()
        
        current = data.get("current")
        prev = data.get("prev")
        
        assert current is not None, "Response should contain 'current' forecast"
        assert prev is not None or len(data.get("rollingForecasts", [])) < 2, "prev may be None if only 1 forecast"
        
        # Verify current is same as last rolling forecast
        rolling = data.get("rollingForecasts", [])
        if rolling:
            assert current.get("createdBucket") == rolling[-1].get("createdBucket")

    # === 30D Horizon Tests ===
    def test_graph3_30d_returns_ok(self):
        """GET /api/prediction/exchange/graph3?asset=BTC&horizon=30D returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=30D")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("horizon") == "30D"

    def test_graph3_30d_returns_30_rolling_forecasts(self):
        """30D horizon returns exactly 30 rolling forecasts"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=30D")
        data = response.json()
        
        rolling = data.get("rollingForecasts", [])
        assert len(rolling) == 30, f"30D should return 30 forecasts, got {len(rolling)}"

    def test_graph3_30d_different_ml_metrics(self):
        """30D has different ML metrics than 7D"""
        response_7d = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=7D")
        response_30d = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=30D")
        
        ml_7d = response_7d.json().get("ml")
        ml_30d = response_30d.json().get("ml")
        
        # At least some metrics should differ
        assert ml_7d != ml_30d, "ML metrics should differ between horizons"

    # === SHADOW Mode Tests ===
    def test_graph3_shadow_mode_final_equals_rule_target(self):
        """In SHADOW mode, all finalTarget values equal ruleTarget values"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=7D")
        data = response.json()
        
        ml = data.get("ml", {})
        rolling = data.get("rollingForecasts", [])
        
        if ml.get("stage") == "SHADOW":
            for i, f in enumerate(rolling):
                assert f.get("finalTarget") == f.get("ruleTarget"), \
                    f"SHADOW mode: forecast {i} finalTarget ({f.get('finalTarget')}) != ruleTarget ({f.get('ruleTarget')})"

    def test_graph3_shadow_mode_30d(self):
        """SHADOW mode verification for 30D horizon"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=30D")
        data = response.json()
        
        ml = data.get("ml", {})
        rolling = data.get("rollingForecasts", [])
        
        if ml.get("stage") == "SHADOW":
            for f in rolling:
                assert f.get("finalTarget") == f.get("ruleTarget"), \
                    "In SHADOW mode, finalTarget must equal ruleTarget"

    # === Data Quality Tests ===
    def test_graph3_rolling_forecasts_chronological(self):
        """Rolling forecasts are in chronological order"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=7D")
        data = response.json()
        
        rolling = data.get("rollingForecasts", [])
        if len(rolling) > 1:
            for i in range(1, len(rolling)):
                assert rolling[i]["evalTs"] >= rolling[i-1]["evalTs"], \
                    f"Forecasts not chronological at index {i}"

    def test_graph3_valid_direction_values(self):
        """Direction field has valid values (UP, DOWN, NEUTRAL, LONG, SHORT)"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=7D")
        data = response.json()
        
        valid_directions = {"UP", "DOWN", "NEUTRAL", "LONG", "SHORT"}
        rolling = data.get("rollingForecasts", [])
        
        for f in rolling:
            direction = f.get("direction")
            assert direction in valid_directions, \
                f"Invalid direction: {direction}"

    def test_graph3_confidence_in_range(self):
        """Confidence values are in valid range [0, 1]"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=7D")
        data = response.json()
        
        rolling = data.get("rollingForecasts", [])
        for f in rolling:
            conf = f.get("confidence", 0)
            assert 0 <= conf <= 1, f"Confidence {conf} out of range [0, 1]"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
