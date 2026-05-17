"""
Test Suite for BTC Prediction Terminal v1.1
Tests prediction exchange API endpoints:
- /api/prediction/exchange/live-price
- /api/prediction/exchange/graph3
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestLivePrice:
    """Test /api/prediction/exchange/live-price endpoint - Binance live BTC price"""
    
    def test_live_price_returns_ok(self):
        """Test live-price endpoint returns valid response"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/live-price?asset=BTC")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["ok"] == True, "Response should have ok=True"
        assert data["asset"] == "BTC", "Asset should be BTC"
        assert "price" in data, "Response should have price field"
        assert isinstance(data["price"], (int, float)), "Price should be numeric"
        assert data["price"] > 0, "Price should be positive"
        print(f"✅ Live price: ${data['price']:,.2f} from {data.get('source', 'unknown')}")
    
    def test_live_price_has_source_and_timestamp(self):
        """Test live-price includes source and timestamp metadata"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/live-price?asset=BTC")
        data = response.json()
        
        assert "source" in data, "Response should have source field"
        assert data["source"] in ["binance", "coinpaprika", "unavailable"], f"Unexpected source: {data['source']}"
        assert "ts" in data, "Response should have timestamp field"
        print(f"✅ Source: {data['source']}, Timestamp: {data['ts']}")


class TestGraph3Endpoint:
    """Test /api/prediction/exchange/graph3 endpoint - Chart data with forecasts"""
    
    def test_graph3_7d_horizon_returns_ok(self):
        """Test graph3 with 7D horizon returns valid response"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=7D&lookback=90")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["ok"] == True, "Response should have ok=True"
        assert data["asset"] == "BTC", "Asset should be BTC"
        assert data["horizon"] == "7D", "Horizon should be 7D"
        print(f"✅ graph3 7D response ok, nowPrice: ${data.get('nowPrice', 0):,.2f}")
    
    def test_graph3_returns_price_series(self):
        """Test graph3 returns priceSeries array with valid data"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=7D&lookback=90")
        data = response.json()
        
        assert "priceSeries" in data, "Response should have priceSeries"
        assert isinstance(data["priceSeries"], list), "priceSeries should be a list"
        assert len(data["priceSeries"]) > 0, "priceSeries should not be empty"
        
        # Verify price series structure
        first_pt = data["priceSeries"][0]
        assert "t" in first_pt, "Price point should have 't' (timestamp)"
        assert "p" in first_pt, "Price point should have 'p' (price)"
        print(f"✅ priceSeries has {len(data['priceSeries'])} points")
    
    def test_graph3_returns_rolling_forecasts(self):
        """Test graph3 returns rollingForecasts array"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=7D&lookback=90")
        data = response.json()
        
        assert "rollingForecasts" in data, "Response should have rollingForecasts"
        assert isinstance(data["rollingForecasts"], list), "rollingForecasts should be a list"
        
        if len(data["rollingForecasts"]) > 0:
            f = data["rollingForecasts"][0]
            required_fields = ["createdBucket", "evalTs", "entryPrice", "finalTarget", "direction", "confidence"]
            for field in required_fields:
                assert field in f, f"Forecast should have '{field}' field"
            print(f"✅ rollingForecasts has {len(data['rollingForecasts'])} forecasts")
        else:
            print("⚠️ rollingForecasts is empty")
    
    def test_graph3_returns_risk_profile(self):
        """Test graph3 returns riskProfile object with expected fields"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=7D&lookback=90")
        data = response.json()
        
        assert "riskProfile" in data, "Response should have riskProfile"
        risk = data["riskProfile"]
        
        required_fields = ["upside", "neutral", "downside", "worstCase", "bestCase", "sampleSize"]
        for field in required_fields:
            assert field in risk, f"riskProfile should have '{field}'"
        
        # Validate distribution sums to ~1
        total = risk["upside"] + risk["neutral"] + risk["downside"]
        assert 0.95 <= total <= 1.05, f"Distribution should sum to ~1, got {total}"
        print(f"✅ riskProfile: upside={risk['upside']:.2%}, neutral={risk['neutral']:.2%}, downside={risk['downside']:.2%}")
        print(f"   Range: ${risk['worstCase']:,.0f} - ${risk['bestCase']:,.0f}")
    
    def test_graph3_returns_regime_info(self):
        """Test graph3 returns regime information"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=7D&lookback=90")
        data = response.json()
        
        assert "regime" in data, "Response should have regime"
        regime = data["regime"]
        
        assert "current" in regime, "regime should have 'current' field"
        assert "confidence" in regime, "regime should have 'confidence' field"
        print(f"✅ Current regime: {regime['current']} (conf: {regime['confidence']:.2f})")
    
    def test_graph3_returns_summary_stats(self):
        """Test graph3 returns summary with performance stats"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=7D&lookback=90")
        data = response.json()
        
        assert "summary" in data, "Response should have summary"
        summary = data["summary"]
        
        required_fields = ["winRate", "dirHitRate", "avgDeviation", "evaluated", "overdue"]
        for field in required_fields:
            assert field in summary, f"summary should have '{field}'"
        
        print(f"✅ Summary: Win Rate={summary['winRate']:.1%}, Dir Hit={summary['dirHitRate']:.1%}, Avg Dev={summary['avgDeviation']:.1f}%, Eval={summary['evaluated']}")
    
    def test_graph3_30d_horizon(self):
        """Test graph3 with 30D horizon returns valid data"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=30D&lookback=90")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] == True
        assert data["horizon"] == "30D"
        print(f"✅ graph3 30D horizon working")
    
    def test_graph3_current_forecast(self):
        """Test graph3 returns current forecast object"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=7D&lookback=90")
        data = response.json()
        
        assert "current" in data, "Response should have 'current' forecast"
        if data["current"]:
            current = data["current"]
            assert "direction" in current, "current should have direction"
            assert "finalTarget" in current, "current should have finalTarget"
            assert "confidence" in current, "current should have confidence"
            print(f"✅ Current forecast: {current['direction']} -> ${current['finalTarget']:,.0f} (conf: {current['confidence']:.2%})")
        else:
            print("⚠️ No current forecast available")


class TestForecastEndpoint:
    """Test /api/prediction/exchange/forecast endpoint - Forecast targets"""
    
    def test_forecast_returns_targets(self):
        """Test forecast endpoint returns targets for different horizons"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/forecast?asset=BTC")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] == True
        assert "targets" in data
        
        if len(data["targets"]) > 0:
            print(f"✅ Forecast targets available: {[t['horizon'] for t in data['targets']]}")
        else:
            print("⚠️ No forecast targets available")


class TestTableColumns:
    """Verify the forecast table columns match v1.1 spec (NO Weight/Stage/Drift columns)"""
    
    def test_rolling_forecasts_no_drift_ece_fields(self):
        """Test that rollingForecasts doesn't expose drift/ece fields"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=7D&lookback=90")
        data = response.json()
        
        if data.get("rollingForecasts"):
            f = data["rollingForecasts"][0]
            # These fields should NOT be in the normalized forecast
            unwanted_fields = ["drift", "driftScore", "ece", "calibration"]
            for field in unwanted_fields:
                assert field not in f, f"Forecast should NOT have '{field}' field"
            print("✅ No drift/ece fields in rollingForecasts (correct for v1.1)")
    
    def test_table_columns_match_spec(self):
        """Verify expected columns: Eval, Dir, Entry, Target, Move, Conf, Actual, Outcome"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph3?asset=BTC&horizon=7D&lookback=90")
        data = response.json()
        
        if data.get("rollingForecasts"):
            f = data["rollingForecasts"][0]
            # Required fields for the table
            required_for_table = ["evalTs", "direction", "entryPrice", "finalTarget", "confidence", "actual", "outcomeLabel"]
            for field in required_for_table:
                assert field in f, f"Forecast should have '{field}' for table display"
            print("✅ All required table fields present")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
