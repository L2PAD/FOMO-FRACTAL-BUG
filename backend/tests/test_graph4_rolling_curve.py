"""
Test Graph4 Rolling Expectation Curve API
Tests for the new /api/prediction/exchange/graph4 endpoint
that provides data for BtcForecastChart component

Features tested:
- GET /api/prediction/exchange/graph4?horizon=7D returns priceSeries and rollingForecasts
- GET /api/prediction/exchange/graph4?horizon=30D returns priceSeries and rollingForecasts
- rollingForecasts have correct fields: madeAtTs, horizonDays, entryPrice, targetPrice, expectedMovePct, direction, confidence
- 30D horizon includes band data for probabilistic forecasts
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestGraph4Endpoint:
    """Tests for GET /api/prediction/exchange/graph4"""

    def test_graph4_7d_returns_ok(self):
        """Graph4 7D endpoint returns ok=True"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph4?asset=BTC&horizon=7D")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') is True, f"Expected ok=True, got {data.get('ok')}"
        assert data.get('asset') == 'BTC', f"Expected asset=BTC, got {data.get('asset')}"
        assert data.get('horizon') == '7D', f"Expected horizon=7D, got {data.get('horizon')}"
        print(f"✓ Graph4 7D returns ok=True")

    def test_graph4_7d_has_price_series(self):
        """Graph4 7D returns priceSeries with data"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph4?asset=BTC&horizon=7D")
        assert response.status_code == 200
        
        data = response.json()
        price_series = data.get('priceSeries', [])
        
        assert len(price_series) > 0, "priceSeries should not be empty"
        
        # Verify price series structure
        first_price = price_series[0]
        assert 't' in first_price, "priceSeries item should have 't' (timestamp)"
        assert 'p' in first_price, "priceSeries item should have 'p' (price)"
        assert isinstance(first_price['t'], int), "timestamp should be integer"
        assert isinstance(first_price['p'], (int, float)), "price should be numeric"
        
        print(f"✓ Graph4 7D has priceSeries with {len(price_series)} data points")

    def test_graph4_7d_has_rolling_forecasts(self):
        """Graph4 7D returns rollingForecasts with data"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph4?asset=BTC&horizon=7D")
        assert response.status_code == 200
        
        data = response.json()
        rolling_forecasts = data.get('rollingForecasts', [])
        
        assert len(rolling_forecasts) > 0, "rollingForecasts should not be empty"
        print(f"✓ Graph4 7D has rollingForecasts with {len(rolling_forecasts)} forecasts")

    def test_graph4_7d_forecast_fields(self):
        """Graph4 7D rollingForecasts have all required fields"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph4?asset=BTC&horizon=7D")
        assert response.status_code == 200
        
        data = response.json()
        rolling_forecasts = data.get('rollingForecasts', [])
        assert len(rolling_forecasts) > 0, "Need at least one forecast to test fields"
        
        required_fields = ['madeAtTs', 'horizonDays', 'entryPrice', 'targetPrice', 
                          'expectedMovePct', 'direction', 'confidence']
        
        forecast = rolling_forecasts[0]
        for field in required_fields:
            assert field in forecast, f"Forecast missing required field: {field}"
        
        # Verify field types and values
        assert isinstance(forecast['madeAtTs'], int), "madeAtTs should be integer timestamp"
        assert forecast['madeAtTs'] > 0, "madeAtTs should be positive"
        
        assert isinstance(forecast['horizonDays'], int), "horizonDays should be integer"
        assert forecast['horizonDays'] == 7, f"horizonDays should be 7 for 7D, got {forecast['horizonDays']}"
        
        assert isinstance(forecast['entryPrice'], (int, float)), "entryPrice should be numeric"
        assert forecast['entryPrice'] > 0, "entryPrice should be positive"
        
        assert isinstance(forecast['targetPrice'], (int, float)), "targetPrice should be numeric"
        assert forecast['targetPrice'] > 0, "targetPrice should be positive"
        
        assert isinstance(forecast['expectedMovePct'], (int, float)), "expectedMovePct should be numeric"
        
        assert forecast['direction'] in ['UP', 'DOWN', 'NEUTRAL', 'LONG', 'SHORT'], \
            f"direction should be valid, got {forecast['direction']}"
        
        assert isinstance(forecast['confidence'], (int, float)), "confidence should be numeric"
        assert 0 <= forecast['confidence'] <= 1, f"confidence should be 0-1, got {forecast['confidence']}"
        
        print(f"✓ Graph4 7D forecast fields valid: {required_fields}")

    def test_graph4_30d_returns_ok(self):
        """Graph4 30D endpoint returns ok=True"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph4?asset=BTC&horizon=30D")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') is True, f"Expected ok=True, got {data.get('ok')}"
        assert data.get('horizon') == '30D', f"Expected horizon=30D, got {data.get('horizon')}"
        print(f"✓ Graph4 30D returns ok=True")

    def test_graph4_30d_has_rolling_forecasts(self):
        """Graph4 30D returns rollingForecasts with data"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph4?asset=BTC&horizon=30D")
        assert response.status_code == 200
        
        data = response.json()
        rolling_forecasts = data.get('rollingForecasts', [])
        
        assert len(rolling_forecasts) > 0, "rollingForecasts should not be empty for 30D"
        
        # Verify 30D horizon
        forecast = rolling_forecasts[0]
        assert forecast.get('horizonDays') == 30, f"30D forecast should have horizonDays=30, got {forecast.get('horizonDays')}"
        
        print(f"✓ Graph4 30D has rollingForecasts with {len(rolling_forecasts)} forecasts")

    def test_graph4_30d_has_band_data(self):
        """Graph4 30D returns band data for probabilistic forecasts"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph4?asset=BTC&horizon=30D")
        assert response.status_code == 200
        
        data = response.json()
        band = data.get('band')
        
        assert band is not None, "30D should have band data"
        
        # Verify band structure
        assert 'medianTarget' in band, "band should have medianTarget"
        assert 'bandCore' in band, "band should have bandCore"
        assert 'bandWide' in band, "band should have bandWide"
        assert 'bias' in band, "band should have bias"
        assert 'signalStrength' in band, "band should have signalStrength"
        
        # Verify bandCore structure
        assert 'low' in band['bandCore'], "bandCore should have low"
        assert 'high' in band['bandCore'], "bandCore should have high"
        
        # Verify bandWide structure
        assert 'low' in band['bandWide'], "bandWide should have low"
        assert 'high' in band['bandWide'], "bandWide should have high"
        
        # Verify ordering: bandWide.low < bandCore.low < median < bandCore.high < bandWide.high
        assert band['bandWide']['low'] < band['bandCore']['low'], \
            "bandWide.low should be < bandCore.low"
        assert band['bandCore']['low'] < band['medianTarget'], \
            "bandCore.low should be < medianTarget"
        assert band['medianTarget'] < band['bandCore']['high'], \
            "medianTarget should be < bandCore.high"
        assert band['bandCore']['high'] < band['bandWide']['high'], \
            "bandCore.high should be < bandWide.high"
        
        print(f"✓ Graph4 30D has valid band data: medianTarget={band['medianTarget']}, bias={band['bias']}")

    def test_graph4_has_now_price(self):
        """Graph4 returns nowPrice and nowTs for chart reference"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph4?asset=BTC&horizon=7D")
        assert response.status_code == 200
        
        data = response.json()
        
        assert 'nowPrice' in data, "Response should have nowPrice"
        assert 'nowTs' in data, "Response should have nowTs"
        
        assert isinstance(data['nowPrice'], (int, float)), "nowPrice should be numeric"
        assert data['nowPrice'] > 0, "nowPrice should be positive"
        
        assert isinstance(data['nowTs'], int), "nowTs should be integer"
        assert data['nowTs'] > 0, "nowTs should be positive"
        
        print(f"✓ Graph4 has nowPrice={data['nowPrice']}, nowTs={data['nowTs']}")

    def test_graph4_has_stats(self):
        """Graph4 returns stats for evaluated forecasts"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph4?asset=BTC&horizon=7D")
        assert response.status_code == 200
        
        data = response.json()
        stats = data.get('stats')
        
        assert stats is not None, "Response should have stats"
        assert 'winRate' in stats, "stats should have winRate"
        assert 'dirHit' in stats, "stats should have dirHit"
        assert 'avgDev' in stats, "stats should have avgDev"
        assert 'evaluatedCount' in stats, "stats should have evaluatedCount"
        
        print(f"✓ Graph4 has stats: winRate={stats.get('winRate')}, evaluatedCount={stats.get('evaluatedCount')}")

    def test_graph4_7d_no_band(self):
        """Graph4 7D should NOT have band data (point forecast only)"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph4?asset=BTC&horizon=7D")
        assert response.status_code == 200
        
        data = response.json()
        band = data.get('band')
        
        # 7D uses point forecasts, so band should be null
        assert band is None, f"7D should not have band data (got {band})"
        print(f"✓ Graph4 7D correctly has no band data")


class TestGraph4DataConsistency:
    """Tests for data consistency and quality"""

    def test_price_series_chronological(self):
        """Price series should be in chronological order"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph4?asset=BTC&horizon=7D")
        assert response.status_code == 200
        
        data = response.json()
        price_series = data.get('priceSeries', [])
        
        for i in range(1, len(price_series)):
            assert price_series[i]['t'] > price_series[i-1]['t'], \
                f"Price series not chronological at index {i}"
        
        print(f"✓ Price series is chronologically ordered")

    def test_forecasts_chronological(self):
        """Rolling forecasts should be in chronological order"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph4?asset=BTC&horizon=7D")
        assert response.status_code == 200
        
        data = response.json()
        forecasts = data.get('rollingForecasts', [])
        
        for i in range(1, len(forecasts)):
            assert forecasts[i]['madeAtTs'] >= forecasts[i-1]['madeAtTs'], \
                f"Forecasts not chronological at index {i}"
        
        print(f"✓ Rolling forecasts are chronologically ordered")

    def test_expected_move_derived_correctly(self):
        """expectedMovePct should match (target - entry) / entry * 100"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph4?asset=BTC&horizon=7D")
        assert response.status_code == 200
        
        data = response.json()
        forecasts = data.get('rollingForecasts', [])
        
        for forecast in forecasts[:5]:  # Check first 5
            entry = forecast['entryPrice']
            target = forecast['targetPrice']
            expected_move = forecast['expectedMovePct']
            
            if entry > 0 and target > 0:
                calculated = ((target - entry) / entry) * 100
                # Allow small floating point tolerance
                assert abs(calculated - expected_move) < 0.1, \
                    f"expectedMovePct mismatch: calculated={calculated:.4f}, got={expected_move}"
        
        print(f"✓ expectedMovePct values are correctly calculated")


class TestFeatureFlag:
    """Tests for REACT_APP_EXCHANGE_GRAPH_VERSION feature flag"""

    def test_graph4_accessible(self):
        """Graph4 endpoint should be accessible (feature flag enabled)"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph4?asset=BTC&horizon=7D")
        assert response.status_code == 200, f"Graph4 endpoint should be accessible"
        
        data = response.json()
        assert data.get('ok') is True, "Graph4 should return ok=True"
        
        print(f"✓ Graph4 endpoint is accessible (feature flag working)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
