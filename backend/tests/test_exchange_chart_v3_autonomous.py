"""
Exchange Chart V3 Autonomous Candle Backend Tests
==================================================
Tests for the FINAL V3 implementation where:
- Each forecast candle is AUTONOMOUS (open=entryPrice, close=targetPrice)
- NO chaining, NO dailyMove, NO interpolation
- 1 DB forecast = 1 candle
- 30D mode includes overlay7DPoints
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestExchangeChartV3Horizons:
    """Test horizon-specific behavior: 1D, 7D, 30D"""
    
    def test_1d_horizon_returns_single_forecast_point(self):
        """1D: forecastPoints.length === 1, horizonDays === 1"""
        response = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=1D")
        assert response.status_code == 200
        data = response.json()
        
        assert data['ok'] is True
        assert data['horizonDays'] == 1
        assert len(data['forecastPoints']) == 1
        assert 'overlay7DPoints' not in data or data['overlay7DPoints'] is None
    
    def test_7d_horizon_returns_seven_forecast_points(self):
        """7D: forecastPoints.length === 7, horizonDays === 7"""
        response = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D")
        assert response.status_code == 200
        data = response.json()
        
        assert data['ok'] is True
        assert data['horizonDays'] == 7
        assert len(data['forecastPoints']) == 7
        # 7D should NOT have overlay7DPoints
        assert 'overlay7DPoints' not in data or data['overlay7DPoints'] is None
    
    def test_30d_horizon_returns_correct_structure(self):
        """30D: forecastPoints.length <= 30, overlay7DPoints.length === 7"""
        response = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=30D")
        assert response.status_code == 200
        data = response.json()
        
        assert data['ok'] is True
        assert data['horizonDays'] == 30
        assert len(data['forecastPoints']) <= 30
        # 30D MUST have overlay7DPoints array
        assert 'overlay7DPoints' in data
        assert data['overlay7DPoints'] is not None
        assert len(data['overlay7DPoints']) == 7


class TestForecastPointStructure:
    """Test that each forecastPoint has required fields"""
    
    def test_7d_forecast_points_have_entry_and_target_price(self):
        """Each forecastPoint has entryPrice AND targetPrice (both > 0)"""
        response = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D")
        assert response.status_code == 200
        data = response.json()
        
        for i, point in enumerate(data['forecastPoints']):
            assert 'entryPrice' in point, f"Point {i} missing entryPrice"
            assert 'targetPrice' in point, f"Point {i} missing targetPrice"
            assert point['entryPrice'] > 0, f"Point {i} entryPrice <= 0: {point['entryPrice']}"
            assert point['targetPrice'] > 0, f"Point {i} targetPrice <= 0: {point['targetPrice']}"
    
    def test_forecast_points_have_expected_move_pct(self):
        """Each forecastPoint has expectedMovePct field"""
        response = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D")
        assert response.status_code == 200
        data = response.json()
        
        for i, point in enumerate(data['forecastPoints']):
            assert 'expectedMovePct' in point, f"Point {i} missing expectedMovePct"
            # expectedMovePct can be 0, so we just check it's a number
            assert isinstance(point['expectedMovePct'], (int, float)), f"Point {i} expectedMovePct not a number"
    
    def test_forecast_points_sorted_by_target_date_ascending(self):
        """forecastPoints sorted by targetDateTs ascending"""
        response = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D")
        assert response.status_code == 200
        data = response.json()
        
        target_dates = [p['targetDateTs'] for p in data['forecastPoints']]
        assert target_dates == sorted(target_dates), f"forecastPoints not sorted: {target_dates}"
    
    def test_30d_overlay_points_have_entry_and_target_price(self):
        """overlay7DPoints also have entryPrice and targetPrice"""
        response = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=30D")
        assert response.status_code == 200
        data = response.json()
        
        for i, point in enumerate(data['overlay7DPoints']):
            assert 'entryPrice' in point, f"Overlay point {i} missing entryPrice"
            assert 'targetPrice' in point, f"Overlay point {i} missing targetPrice"
            assert point['entryPrice'] > 0, f"Overlay point {i} entryPrice <= 0"
            assert point['targetPrice'] > 0, f"Overlay point {i} targetPrice <= 0"


class TestMetaStability:
    """Test meta.stability field"""
    
    def test_stability_field_present_in_response(self):
        """meta.stability field present (stable/moderate/unstable)"""
        response = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D")
        assert response.status_code == 200
        data = response.json()
        
        assert 'meta' in data
        assert 'stability' in data['meta']
        assert data['meta']['stability'] in ['stable', 'moderate', 'unstable', 'unknown']
    
    def test_1d_stability_field(self):
        """1D response has stability field"""
        response = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=1D")
        assert response.status_code == 200
        data = response.json()
        
        assert data['meta']['stability'] in ['stable', 'moderate', 'unstable', 'unknown']
    
    def test_30d_stability_field(self):
        """30D response has stability field"""
        response = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=30D")
        assert response.status_code == 200
        data = response.json()
        
        assert data['meta']['stability'] in ['stable', 'moderate', 'unstable', 'unknown']


class TestAutonomousCandleArchitecture:
    """Test the autonomous candle architecture (open=entryPrice, close=targetPrice)"""
    
    def test_candles_are_autonomous_not_chained(self):
        """Verify each forecast is independent - entryPrice varies per point"""
        response = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D")
        assert response.status_code == 200
        data = response.json()
        
        # In autonomous architecture, each point has its own entryPrice
        # They should NOT all be the same (would indicate chaining from single source)
        entry_prices = [p['entryPrice'] for p in data['forecastPoints']]
        unique_entries = set(entry_prices)
        
        # We expect at least some variation in entry prices across different forecasts
        # (since each forecast was made at different times with different market prices)
        assert len(unique_entries) > 1, f"All entry prices identical, may indicate chaining: {entry_prices}"
    
    def test_no_daily_move_field_in_response(self):
        """Verify no dailyMovePct field (removed in V3 autonomous)"""
        response = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D")
        assert response.status_code == 200
        data = response.json()
        
        # dailyMovePct was removed in autonomous architecture
        for point in data['forecastPoints']:
            assert 'dailyMovePct' not in point, "dailyMovePct should not exist in autonomous architecture"


class TestRealCandles:
    """Test real candle data"""
    
    def test_real_candles_present(self):
        """realCandles array is populated"""
        response = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D")
        assert response.status_code == 200
        data = response.json()
        
        assert 'realCandles' in data
        assert len(data['realCandles']) > 0
    
    def test_real_candle_structure(self):
        """Real candles have OHLC structure"""
        response = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D")
        assert response.status_code == 200
        data = response.json()
        
        if data['realCandles']:
            candle = data['realCandles'][0]
            assert 'time' in candle
            assert 'open' in candle
            assert 'high' in candle
            assert 'low' in candle
            assert 'close' in candle


class TestResponseFields:
    """Test response contains all required fields"""
    
    def test_response_has_all_required_fields(self):
        """Verify response structure has all required fields"""
        response = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D")
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ['ok', 'symbol', 'nowTs', 'horizonDays', 'realCandles', 
                          'forecastPoints', 'target', 'confidence', 'direction', 'source', 'meta']
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # meta required fields
        assert 'stability' in data['meta']
        assert 'stabilityStddev' in data['meta']
        assert 'totalForecasts' in data['meta']
        assert 'uniqueTargetDates' in data['meta']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
