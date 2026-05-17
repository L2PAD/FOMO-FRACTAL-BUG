"""
Test V3.1 Chart Controls and Forecast Series API
================================================
Tests the unified control bar features and API endpoints:
- /api/market/forecast-series endpoint (models: combined, exchange)
- Multiple horizons (1D, 7D, 30D)
- Multiple formats (candles, line)
- Error handling for invalid parameters
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestForecastSeriesAPI:
    """Tests for /api/market/forecast-series endpoint"""
    
    def test_forecast_series_combined_candles(self):
        """Test combined model with candles format"""
        response = requests.get(
            f"{BASE_URL}/api/market/forecast-series",
            params={"symbol": "BTC", "horizon": "1D", "model": "combined", "format": "candles"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("model") == "combined"
        assert data.get("symbol") == "BTC"
        assert data.get("horizon") == "1D"
        assert "candles" in data
        print(f"✅ Combined model candles format: {len(data.get('candles', []))} candles")
    
    def test_forecast_series_exchange_candles(self):
        """Test exchange model with candles format"""
        response = requests.get(
            f"{BASE_URL}/api/market/forecast-series",
            params={"symbol": "BTC", "horizon": "1D", "model": "exchange", "format": "candles"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("model") == "exchange"
        print(f"✅ Exchange model candles format: {len(data.get('candles', []))} candles")
    
    def test_forecast_series_line_format(self):
        """Test line format response structure"""
        response = requests.get(
            f"{BASE_URL}/api/market/forecast-series",
            params={"symbol": "BTC", "horizon": "1D", "model": "combined", "format": "line"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "line" in data
        # Line format should have time and value fields
        if data.get("line"):
            assert "time" in data["line"][0]
            assert "value" in data["line"][0]
        print(f"✅ Line format: {len(data.get('line', []))} points")
    
    def test_forecast_series_7d_horizon(self):
        """Test 7D horizon"""
        response = requests.get(
            f"{BASE_URL}/api/market/forecast-series",
            params={"symbol": "BTC", "horizon": "7D", "model": "combined", "format": "candles"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("horizon") == "7D"
        print("✅ 7D horizon working")
    
    def test_forecast_series_30d_horizon(self):
        """Test 30D horizon"""
        response = requests.get(
            f"{BASE_URL}/api/market/forecast-series",
            params={"symbol": "BTC", "horizon": "30D", "model": "combined", "format": "candles"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("horizon") == "30D"
        print("✅ 30D horizon working")
    
    def test_forecast_series_invalid_model(self):
        """Test invalid model returns proper error"""
        response = requests.get(
            f"{BASE_URL}/api/market/forecast-series",
            params={"symbol": "BTC", "horizon": "1D", "model": "invalid_model", "format": "candles"}
        )
        assert response.status_code == 400
        data = response.json()
        assert data.get("ok") is False
        assert data.get("error") == "INVALID_MODEL"
        print("✅ Invalid model returns proper 400 error")
    
    def test_forecast_series_invalid_horizon(self):
        """Test invalid horizon returns proper error"""
        response = requests.get(
            f"{BASE_URL}/api/market/forecast-series",
            params={"symbol": "BTC", "horizon": "invalid", "model": "combined", "format": "candles"}
        )
        assert response.status_code == 400
        data = response.json()
        assert data.get("ok") is False
        assert data.get("error") == "INVALID_HORIZON"
        print("✅ Invalid horizon returns proper 400 error")


class TestMarketCandlesAPI:
    """Tests for /api/market/candles endpoint used by TradingViewChartV2"""
    
    def test_market_candles_btc(self):
        """Test fetching BTC market candles"""
        response = requests.get(
            f"{BASE_URL}/api/market/candles",
            params={"symbol": "BTCUSDT", "range": "7d"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        candles = data.get("candles", [])
        assert len(candles) > 0
        # Verify OHLC structure
        if candles:
            c = candles[0]
            assert "time" in c
            assert "open" in c
            assert "high" in c
            assert "low" in c
            assert "close" in c
        print(f"✅ Market candles for BTC: {len(candles)} candles")
    
    def test_market_candles_different_ranges(self):
        """Test different chart ranges"""
        ranges = ["24h", "7d", "30d", "90d"]
        for r in ranges:
            response = requests.get(
                f"{BASE_URL}/api/market/candles",
                params={"symbol": "BTCUSDT", "range": r}
            )
            assert response.status_code == 200
            data = response.json()
            assert data.get("ok") is True
            print(f"✅ Range {r}: {len(data.get('candles', []))} candles")


class TestPriceExpectationV4API:
    """Tests for V4 endpoint used on PriceExpectationV2Page"""
    
    def test_v4_endpoint_returns_verdict(self):
        """Test V4 endpoint returns verdict data"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v4",
            params={"asset": "BTC", "range": "7d", "horizon": "1D"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        # Check verdict structure
        assert "verdict" in data
        if data.get("verdict"):
            v = data["verdict"]
            assert "action" in v or "confidence" in v
        print("✅ V4 endpoint returns verdict data")
    
    def test_v4_endpoint_horizons(self):
        """Test all horizons work on V4 endpoint"""
        horizons = ["1D", "7D", "30D"]
        for h in horizons:
            response = requests.get(
                f"{BASE_URL}/api/market/chart/price-vs-expectation-v4",
                params={"asset": "BTC", "range": "7d", "horizon": h}
            )
            assert response.status_code == 200
            data = response.json()
            assert data.get("ok") is True
            print(f"✅ V4 horizon {h} working")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
