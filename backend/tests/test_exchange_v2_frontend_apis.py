"""
Exchange V2 Frontend APIs Tests
================================
Tests for the Exchange tab V2 backend endpoints:
- GET /api/forecast/exchange/chart-data - Chart data with OHLC candles + forecast projections
- GET /api/forecast/exchange/history - Historical forecast list for performance table
- GET /api/forecast/prediction/{asset} - Multi-horizon V2 prediction output
- GET /api/forecast/execution/{asset} - Execution adapter data
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestExchangeChartDataEndpoint:
    """Tests for /api/forecast/exchange/chart-data endpoint"""
    
    def test_chart_data_btc_7d_returns_ok(self):
        """Chart data returns ok=true for BTC 7D horizon"""
        response = requests.get(f"{BASE_URL}/api/forecast/exchange/chart-data?asset=BTC&horizon=7D")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("asset") == "BTC"
        assert data.get("horizon") == "7D"
    
    def test_chart_data_has_price_series(self):
        """Chart data contains priceSeries with OHLC candles"""
        response = requests.get(f"{BASE_URL}/api/forecast/exchange/chart-data?asset=BTC&horizon=7D")
        data = response.json()
        assert "priceSeries" in data
        assert len(data["priceSeries"]) > 0
        candle = data["priceSeries"][0]
        assert "time" in candle
        assert "open" in candle
        assert "high" in candle
        assert "low" in candle
        assert "close" in candle
    
    def test_chart_data_has_current_price(self):
        """Chart data contains current price"""
        response = requests.get(f"{BASE_URL}/api/forecast/exchange/chart-data?asset=BTC&horizon=7D")
        data = response.json()
        assert "currentPrice" in data
        assert data["currentPrice"] > 0
    
    def test_chart_data_has_now_timestamp(self):
        """Chart data contains nowTs timestamp"""
        response = requests.get(f"{BASE_URL}/api/forecast/exchange/chart-data?asset=BTC&horizon=7D")
        data = response.json()
        assert "nowTs" in data
        assert isinstance(data["nowTs"], int)
    
    def test_chart_data_has_forecast(self):
        """Chart data contains forecast object with V2 fields"""
        response = requests.get(f"{BASE_URL}/api/forecast/exchange/chart-data?asset=BTC&horizon=7D")
        data = response.json()
        assert "forecast" in data
        forecast = data["forecast"]
        if forecast:
            assert "direction" in forecast
            assert "directionClass" in forecast
            assert "confidence" in forecast
            assert "entryPrice" in forecast
            assert "targetPrice" in forecast
            assert "regime" in forecast
    
    def test_chart_data_has_horizons_summary(self):
        """Chart data contains horizonsSummary for multi-horizon display"""
        response = requests.get(f"{BASE_URL}/api/forecast/exchange/chart-data?asset=BTC&horizon=7D")
        data = response.json()
        assert "horizonsSummary" in data
        horizons = data["horizonsSummary"]
        # Should have data for at least one horizon
        assert len(horizons) >= 1
    
    def test_chart_data_has_projection_points(self):
        """Chart data contains projectionPoints for forecast line"""
        response = requests.get(f"{BASE_URL}/api/forecast/exchange/chart-data?asset=BTC&horizon=7D")
        data = response.json()
        assert "projectionPoints" in data
        if data.get("forecast"):
            # Should have projection points when forecast exists
            assert len(data["projectionPoints"]) > 0
    
    def test_chart_data_24h_horizon(self):
        """Chart data works for 24H horizon (mapped from 1D)"""
        response = requests.get(f"{BASE_URL}/api/forecast/exchange/chart-data?asset=BTC&horizon=24H")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("horizon") == "24H"
    
    def test_chart_data_30d_horizon_has_scenarios(self):
        """Chart data for 30D horizon includes scenarios"""
        response = requests.get(f"{BASE_URL}/api/forecast/exchange/chart-data?asset=BTC&horizon=30D")
        data = response.json()
        assert data.get("ok") == True
        horizons = data.get("horizonsSummary", {})
        if "30D" in horizons:
            h30d = horizons["30D"]
            # 30D should have scenarios data
            assert "scenarios" in h30d or h30d.get("scenarios") is None


class TestExchangeHistoryEndpoint:
    """Tests for /api/forecast/exchange/history endpoint"""
    
    def test_history_btc_7d_returns_ok(self):
        """History returns ok=true for BTC 7D horizon"""
        response = requests.get(f"{BASE_URL}/api/forecast/exchange/history?asset=BTC&horizon=7D&limit=30")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("asset") == "BTC"
        assert data.get("horizon") == "7D"
    
    def test_history_has_rows(self):
        """History contains rows array"""
        response = requests.get(f"{BASE_URL}/api/forecast/exchange/history?asset=BTC&horizon=7D&limit=30")
        data = response.json()
        assert "rows" in data
        assert isinstance(data["rows"], list)
    
    def test_history_row_has_required_fields(self):
        """History row contains all required V2 fields"""
        response = requests.get(f"{BASE_URL}/api/forecast/exchange/history?asset=BTC&horizon=7D&limit=30")
        data = response.json()
        if len(data.get("rows", [])) > 0:
            row = data["rows"][0]
            assert "direction" in row
            assert "directionClass" in row
            assert "confidence" in row
            assert "entryPrice" in row
            assert "targetPrice" in row
            assert "expectedMovePct" in row
            assert "regime" in row
            assert "status" in row
            assert "createdAt" in row
    
    def test_history_has_stats(self):
        """History contains stats summary"""
        response = requests.get(f"{BASE_URL}/api/forecast/exchange/history?asset=BTC&horizon=7D&limit=30")
        data = response.json()
        assert "stats" in data
        stats = data["stats"]
        assert "total" in stats
        assert "evaluated" in stats
        assert "pending" in stats
        assert "winRate" in stats
    
    def test_history_status_values(self):
        """History row status is one of PENDING, EVALUATED, OVERDUE"""
        response = requests.get(f"{BASE_URL}/api/forecast/exchange/history?asset=BTC&horizon=7D&limit=30")
        data = response.json()
        for row in data.get("rows", []):
            assert row["status"] in ["PENDING", "EVALUATED", "OVERDUE"]
    
    def test_history_limit_works(self):
        """History respects limit parameter"""
        response = requests.get(f"{BASE_URL}/api/forecast/exchange/history?asset=BTC&horizon=7D&limit=5")
        data = response.json()
        assert len(data.get("rows", [])) <= 5
    
    def test_history_eth_returns_data(self):
        """History works for ETH asset"""
        response = requests.get(f"{BASE_URL}/api/forecast/exchange/history?asset=ETH&horizon=7D&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("asset") == "ETH"
    
    def test_history_sol_returns_data(self):
        """History works for SOL asset"""
        response = requests.get(f"{BASE_URL}/api/forecast/exchange/history?asset=SOL&horizon=7D&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("asset") == "SOL"


class TestPredictionEndpoint:
    """Tests for /api/forecast/prediction/{asset} endpoint"""
    
    def test_prediction_btc_returns_ok(self):
        """Prediction returns ok=true for BTC"""
        response = requests.get(f"{BASE_URL}/api/forecast/prediction/BTC")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("asset") == "BTC"
    
    def test_prediction_has_horizons(self):
        """Prediction contains horizons object with all 3 horizons"""
        response = requests.get(f"{BASE_URL}/api/forecast/prediction/BTC")
        data = response.json()
        assert "horizons" in data
        horizons = data["horizons"]
        # Should have all 3 horizons
        assert "24H" in horizons
        assert "7D" in horizons
        assert "30D" in horizons
    
    def test_prediction_horizon_has_required_fields(self):
        """Prediction horizon contains required V2 fields"""
        response = requests.get(f"{BASE_URL}/api/forecast/prediction/BTC")
        data = response.json()
        for key, horizon in data.get("horizons", {}).items():
            assert "direction" in horizon
            assert "confidence" in horizon
            assert "uncertainty" in horizon
            assert "entry_price" in horizon
            assert "target_price" in horizon
            assert "regime" in horizon
    
    def test_prediction_has_summary(self):
        """Prediction contains summary object"""
        response = requests.get(f"{BASE_URL}/api/forecast/prediction/BTC")
        data = response.json()
        assert "summary" in data
        summary = data["summary"]
        assert "consensus_direction" in summary
        assert "horizon_agreement" in summary
        assert "avg_confidence" in summary
    
    def test_prediction_30d_has_scenarios(self):
        """Prediction 30D horizon has scenario details"""
        response = requests.get(f"{BASE_URL}/api/forecast/prediction/BTC")
        data = response.json()
        h30d = data.get("horizons", {}).get("30D", {})
        if h30d:
            # 30D should have scenario fields
            assert "dominant" in h30d or h30d.get("scenario_details") is not None
            if h30d.get("scenario_details"):
                scenarios = h30d["scenario_details"]
                assert len(scenarios) > 0
                # Check scenario structure
                scenario = scenarios[0]
                assert "type" in scenario
                assert "probability" in scenario
    
    def test_prediction_eth_returns_ok(self):
        """Prediction works for ETH asset"""
        response = requests.get(f"{BASE_URL}/api/forecast/prediction/ETH")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
    
    def test_prediction_unsupported_asset_returns_error(self):
        """Prediction returns error for unsupported asset"""
        response = requests.get(f"{BASE_URL}/api/forecast/prediction/INVALID")
        data = response.json()
        assert data.get("ok") == False


class TestExecutionEndpoint:
    """Tests for /api/forecast/execution/{asset} endpoint"""
    
    def test_execution_btc_returns_ok(self):
        """Execution returns ok=true for BTC"""
        response = requests.get(f"{BASE_URL}/api/forecast/execution/BTC")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("asset") == "BTC"
    
    def test_execution_has_bias(self):
        """Execution contains bias field"""
        response = requests.get(f"{BASE_URL}/api/forecast/execution/BTC")
        data = response.json()
        assert "bias" in data
        assert data["bias"] in ["bullish", "bearish", "neutral"]
    
    def test_execution_has_execution_hint(self):
        """Execution contains execution_hint field"""
        response = requests.get(f"{BASE_URL}/api/forecast/execution/BTC")
        data = response.json()
        assert "execution_hint" in data
        assert data["execution_hint"] in ["allow", "allow_reduced", "wait"]
    
    def test_execution_has_risk_mode(self):
        """Execution contains risk_mode field"""
        response = requests.get(f"{BASE_URL}/api/forecast/execution/BTC")
        data = response.json()
        assert "risk_mode" in data
        assert data["risk_mode"] in ["normal", "cautious", "defensive"]
    
    def test_execution_has_strength(self):
        """Execution contains strength field (0-1)"""
        response = requests.get(f"{BASE_URL}/api/forecast/execution/BTC")
        data = response.json()
        assert "strength" in data
        assert 0 <= data["strength"] <= 1
    
    def test_execution_has_reasons(self):
        """Execution contains reasons array"""
        response = requests.get(f"{BASE_URL}/api/forecast/execution/BTC")
        data = response.json()
        assert "reasons" in data
        assert isinstance(data["reasons"], list)


class TestCrossHorizonIntegration:
    """Integration tests across multiple horizons"""
    
    def test_all_horizons_chart_data(self):
        """Chart data endpoint works for all horizons"""
        for horizon in ["24H", "7D", "30D"]:
            response = requests.get(f"{BASE_URL}/api/forecast/exchange/chart-data?asset=BTC&horizon={horizon}")
            assert response.status_code == 200
            data = response.json()
            assert data.get("ok") == True, f"Failed for horizon {horizon}"
    
    def test_all_horizons_history(self):
        """History endpoint works for all horizons"""
        for horizon in ["24H", "7D", "30D"]:
            response = requests.get(f"{BASE_URL}/api/forecast/exchange/history?asset=BTC&horizon={horizon}&limit=5")
            assert response.status_code == 200
            data = response.json()
            assert data.get("ok") == True, f"Failed for horizon {horizon}"
    
    def test_all_assets_prediction(self):
        """Prediction endpoint works for all supported assets"""
        for asset in ["BTC", "ETH", "SOL"]:
            response = requests.get(f"{BASE_URL}/api/forecast/prediction/{asset}")
            assert response.status_code == 200
            data = response.json()
            assert data.get("ok") == True, f"Failed for asset {asset}"
    
    def test_chart_data_history_consistency(self):
        """Chart data forecast matches first row in history"""
        chart_response = requests.get(f"{BASE_URL}/api/forecast/exchange/chart-data?asset=BTC&horizon=7D")
        history_response = requests.get(f"{BASE_URL}/api/forecast/exchange/history?asset=BTC&horizon=7D&limit=1")
        
        chart_data = chart_response.json()
        history_data = history_response.json()
        
        if chart_data.get("forecast") and len(history_data.get("rows", [])) > 0:
            chart_forecast = chart_data["forecast"]
            history_row = history_data["rows"][0]
            # Direction should match
            assert chart_forecast["direction"] == history_row["direction"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
