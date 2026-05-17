"""
Forecast Series API Tests (Block F1, F2, F3)
=============================================

Tests for:
- Block F1: GET /api/market/forecast-series endpoint
- Block F2: Multi-series data for chart overlay
- Block F3: UI Controls API integration

Test Coverage:
- Candles format returns candles array
- Line format returns line array
- Multiple models (combined, exchange)
- Multiple horizons (1D, 7D, 30D)
- Invalid parameters handling
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestForecastSeriesAPI:
    """Block F1: Forecast Series Endpoint Tests"""
    
    def test_forecast_series_candles_format_btc_combined(self):
        """Test /api/market/forecast-series returns candles for BTC with combined model"""
        response = requests.get(
            f"{BASE_URL}/api/market/forecast-series",
            params={
                "symbol": "BTC",
                "model": "combined",
                "horizon": "1D",
                "format": "candles"
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") == True, "Response should have ok: true"
        assert data.get("symbol") == "BTC", "Symbol should be BTC"
        assert data.get("model") == "combined", "Model should be combined"
        assert data.get("horizon") == "1D", "Horizon should be 1D"
        assert "candles" in data, "Response should contain candles array"
        assert "points" in data, "Response should contain points array"
        
        print(f"✅ Candles format: {len(data.get('candles', []))} candles returned")
    
    def test_forecast_series_line_format_btc_combined(self):
        """Test /api/market/forecast-series returns line data for BTC"""
        response = requests.get(
            f"{BASE_URL}/api/market/forecast-series",
            params={
                "symbol": "BTC",
                "model": "combined",
                "horizon": "1D",
                "format": "line"
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") == True, "Response should have ok: true"
        assert "line" in data, "Response should contain line array for line format"
        
        # In line mode, candles should be empty
        candles = data.get("candles", [])
        assert len(candles) == 0, f"Candles should be empty in line mode, got {len(candles)}"
        
        print(f"✅ Line format: {len(data.get('line', []))} points returned")
    
    def test_forecast_series_exchange_model(self):
        """Test /api/market/forecast-series with exchange model"""
        response = requests.get(
            f"{BASE_URL}/api/market/forecast-series",
            params={
                "symbol": "BTC",
                "model": "exchange",
                "horizon": "1D",
                "format": "candles"
            }
        )
        
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        assert data.get("model") == "exchange", "Model should be exchange"
        
        print(f"✅ Exchange model: {len(data.get('candles', []))} candles returned")
    
    def test_forecast_series_7d_horizon(self):
        """Test 7D horizon returns data"""
        response = requests.get(
            f"{BASE_URL}/api/market/forecast-series",
            params={
                "symbol": "BTC",
                "model": "combined",
                "horizon": "7D"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("horizon") == "7D"
        
        print(f"✅ 7D horizon: ok")
    
    def test_forecast_series_30d_horizon(self):
        """Test 30D horizon returns data"""
        response = requests.get(
            f"{BASE_URL}/api/market/forecast-series",
            params={
                "symbol": "BTC",
                "model": "combined",
                "horizon": "30D"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("horizon") == "30D"
        
        print(f"✅ 30D horizon: ok")
    
    def test_forecast_series_eth_symbol(self):
        """Test forecast series with ETH symbol"""
        response = requests.get(
            f"{BASE_URL}/api/market/forecast-series",
            params={
                "symbol": "ETH",
                "model": "combined",
                "horizon": "1D"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("symbol") == "ETH"
        
        print(f"✅ ETH symbol: ok")
    
    def test_forecast_series_sol_symbol(self):
        """Test forecast series with SOL symbol"""
        response = requests.get(
            f"{BASE_URL}/api/market/forecast-series",
            params={
                "symbol": "SOL",
                "model": "combined",
                "horizon": "1D"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("symbol") == "SOL"
        
        print(f"✅ SOL symbol: ok")
    
    def test_forecast_series_invalid_model_returns_400(self):
        """Test that invalid model returns 400 error"""
        response = requests.get(
            f"{BASE_URL}/api/market/forecast-series",
            params={
                "symbol": "BTC",
                "model": "invalid_model",
                "horizon": "1D"
            }
        )
        
        assert response.status_code == 400, f"Expected 400 for invalid model, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") == False
        assert "INVALID_MODEL" in data.get("error", "")
        
        print(f"✅ Invalid model validation: ok")
    
    def test_forecast_series_invalid_horizon_returns_400(self):
        """Test that invalid horizon returns 400 error"""
        response = requests.get(
            f"{BASE_URL}/api/market/forecast-series",
            params={
                "symbol": "BTC",
                "model": "combined",
                "horizon": "invalid"
            }
        )
        
        assert response.status_code == 400, f"Expected 400 for invalid horizon, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") == False
        assert "INVALID_HORIZON" in data.get("error", "")
        
        print(f"✅ Invalid horizon validation: ok")
    
    def test_forecast_candles_structure(self):
        """Test that forecast candles have correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/market/forecast-series",
            params={
                "symbol": "BTC",
                "model": "combined",
                "horizon": "1D",
                "format": "candles"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        candles = data.get("candles", [])
        if len(candles) > 0:
            candle = candles[0]
            
            # Check required OHLC fields
            assert "time" in candle, "Candle should have time field"
            assert "open" in candle, "Candle should have open field"
            assert "high" in candle, "Candle should have high field"
            assert "low" in candle, "Candle should have low field"
            assert "close" in candle, "Candle should have close field"
            
            # Check metadata fields
            assert "model" in candle, "Candle should have model field"
            assert "horizon" in candle, "Candle should have horizon field"
            assert "confidence" in candle, "Candle should have confidence field"
            assert "direction" in candle, "Candle should have direction field"
            
            print(f"✅ Candle structure valid: time={candle['time']}, open={candle['open']}")
        else:
            print(f"⚠️ No candles to verify structure (may need more data points)")
    
    def test_forecast_line_structure(self):
        """Test that line data has correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/market/forecast-series",
            params={
                "symbol": "BTC",
                "model": "combined",
                "horizon": "1D",
                "format": "line"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        line = data.get("line", [])
        if len(line) > 0:
            point = line[0]
            
            # Check required fields for line series
            assert "time" in point, "Line point should have time field"
            assert "value" in point, "Line point should have value field"
            
            print(f"✅ Line structure valid: time={point['time']}, value={point['value']}")
        else:
            print(f"⚠️ No line points to verify structure (may need more data points)")


class TestForecastPointsData:
    """Block F1: Points array structure tests"""
    
    def test_points_have_required_fields(self):
        """Test that points array has required fields"""
        response = requests.get(
            f"{BASE_URL}/api/market/forecast-series",
            params={
                "symbol": "BTC",
                "model": "combined",
                "horizon": "1D"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        points = data.get("points", [])
        if len(points) > 0:
            point = points[0]
            
            # Required fields for forecast point
            assert "symbol" in point, "Point should have symbol"
            assert "model" in point, "Point should have model"
            assert "horizon" in point, "Point should have horizon"
            assert "basePrice" in point, "Point should have basePrice"
            assert "confidence" in point, "Point should have confidence"
            assert "direction" in point, "Point should have direction"
            assert "expectedMovePct" in point, "Point should have expectedMovePct"
            
            print(f"✅ Point fields valid: basePrice={point['basePrice']}, direction={point['direction']}")
        else:
            print(f"⚠️ No points to verify structure")


class TestMultiModelForecast:
    """Block F2: Multi-model tests for chart overlay"""
    
    def test_both_models_return_data(self):
        """Test that both combined and exchange models return data"""
        models = ["combined", "exchange"]
        results = {}
        
        for model in models:
            response = requests.get(
                f"{BASE_URL}/api/market/forecast-series",
                params={
                    "symbol": "BTC",
                    "model": model,
                    "horizon": "1D",
                    "format": "candles"
                }
            )
            
            assert response.status_code == 200, f"Model {model} failed with {response.status_code}"
            data = response.json()
            assert data.get("ok") == True, f"Model {model} returned ok: false"
            
            results[model] = {
                "candles": len(data.get("candles", [])),
                "points": len(data.get("points", []))
            }
        
        print(f"✅ Combined: {results['combined']['candles']} candles, {results['combined']['points']} points")
        print(f"✅ Exchange: {results['exchange']['candles']} candles, {results['exchange']['points']} points")
    
    def test_different_horizons_return_data(self):
        """Test that all horizons return data for chart"""
        horizons = ["1D", "7D", "30D"]
        
        for horizon in horizons:
            response = requests.get(
                f"{BASE_URL}/api/market/forecast-series",
                params={
                    "symbol": "BTC",
                    "model": "combined",
                    "horizon": horizon
                }
            )
            
            assert response.status_code == 200, f"Horizon {horizon} failed"
            data = response.json()
            assert data.get("ok") == True
            assert data.get("horizon") == horizon
            
            print(f"✅ Horizon {horizon}: ok")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
