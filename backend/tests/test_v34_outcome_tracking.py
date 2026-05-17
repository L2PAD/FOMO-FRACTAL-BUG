"""
V3.4 Outcome Tracking API Tests
================================

Tests for forecast outcome tracking feature:
1. GET /api/market/forecast-outcomes - Get outcome markers for chart
2. GET /api/market/forecast-outcomes/stats - Get win/loss statistics
3. GET /api/market/forecast-outcomes/recent - Get recent outcomes
4. GET /api/market/forecast-only - Creates snapshot and returns data

This feature persists forecasts as snapshots in MongoDB and tracks 
their WIN/LOSS results after time horizon passes.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8003').rstrip('/')

class TestForecastOutcomesEndpoint:
    """Tests for GET /api/market/forecast-outcomes"""
    
    def test_forecast_outcomes_default_params(self):
        """Test forecast-outcomes with default parameters"""
        response = requests.get(f"{BASE_URL}/api/market/forecast-outcomes")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert 'symbol' in data
        assert 'layer' in data
        assert 'horizon' in data
        assert 'outcomes' in data
        assert 'count' in data
        assert isinstance(data['outcomes'], list)
        print(f"SUCCESS: forecast-outcomes returned {data['count']} outcomes")
    
    def test_forecast_outcomes_with_params(self):
        """Test forecast-outcomes with specific parameters"""
        params = {
            'symbol': 'BTC',
            'layer': 'forecast',
            'horizon': '7D',
            'limit': '10'
        }
        response = requests.get(f"{BASE_URL}/api/market/forecast-outcomes", params=params)
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert data['symbol'] == 'BTC'
        assert data['layer'] == 'forecast'
        assert data['horizon'] == '7D'
        print(f"SUCCESS: forecast-outcomes with params returned correctly")
    
    def test_forecast_outcomes_exchange_layer(self):
        """Test forecast-outcomes for exchange layer"""
        params = {
            'symbol': 'BTC',
            'layer': 'exchange',
            'horizon': '1D'
        }
        response = requests.get(f"{BASE_URL}/api/market/forecast-outcomes", params=params)
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert data['layer'] == 'exchange'
        print(f"SUCCESS: exchange layer outcomes returned")
    
    def test_forecast_outcomes_invalid_layer(self):
        """Test forecast-outcomes with invalid layer"""
        params = {'layer': 'invalid_layer'}
        response = requests.get(f"{BASE_URL}/api/market/forecast-outcomes", params=params)
        assert response.status_code == 400
        
        data = response.json()
        assert data['ok'] == False
        assert data['error'] == 'INVALID_LAYER'
        print("SUCCESS: Invalid layer returns 400 error")
    
    def test_forecast_outcomes_invalid_horizon(self):
        """Test forecast-outcomes with invalid horizon"""
        params = {'horizon': '5D'}
        response = requests.get(f"{BASE_URL}/api/market/forecast-outcomes", params=params)
        assert response.status_code == 400
        
        data = response.json()
        assert data['ok'] == False
        assert data['error'] == 'INVALID_HORIZON'
        print("SUCCESS: Invalid horizon returns 400 error")


class TestForecastOutcomesStatsEndpoint:
    """Tests for GET /api/market/forecast-outcomes/stats"""
    
    def test_stats_default_params(self):
        """Test stats endpoint with default parameters"""
        response = requests.get(f"{BASE_URL}/api/market/forecast-outcomes/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert 'total' in data
        assert 'wins' in data
        assert 'losses' in data
        assert 'draws' in data
        assert 'winRate' in data
        assert 'directionAccuracy' in data
        assert 'avgDeviation' in data
        assert 'avgConfidence' in data
        assert 'streak' in data
        print(f"SUCCESS: Stats endpoint returned total={data['total']}, winRate={data['winRate']}")
    
    def test_stats_with_params(self):
        """Test stats endpoint with specific parameters"""
        params = {
            'symbol': 'BTC',
            'layer': 'forecast',
            'horizon': '7D'
        }
        response = requests.get(f"{BASE_URL}/api/market/forecast-outcomes/stats", params=params)
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        # Stats should have numerical values
        assert isinstance(data['total'], int)
        assert isinstance(data['wins'], int)
        assert isinstance(data['losses'], int)
        print("SUCCESS: Stats with params returned correctly")
    
    def test_stats_exchange_layer(self):
        """Test stats for exchange layer"""
        params = {'layer': 'exchange'}
        response = requests.get(f"{BASE_URL}/api/market/forecast-outcomes/stats", params=params)
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        print("SUCCESS: Exchange layer stats returned")


class TestForecastOutcomesRecentEndpoint:
    """Tests for GET /api/market/forecast-outcomes/recent"""
    
    def test_recent_default_params(self):
        """Test recent endpoint with default parameters"""
        response = requests.get(f"{BASE_URL}/api/market/forecast-outcomes/recent")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert 'outcomes' in data
        assert 'count' in data
        assert isinstance(data['outcomes'], list)
        print(f"SUCCESS: Recent endpoint returned {data['count']} outcomes")
    
    def test_recent_with_limit(self):
        """Test recent endpoint with custom limit"""
        params = {
            'symbol': 'BTC',
            'layer': 'forecast',
            'horizon': '7D',
            'limit': '5'
        }
        response = requests.get(f"{BASE_URL}/api/market/forecast-outcomes/recent", params=params)
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert data['count'] <= 5
        print(f"SUCCESS: Recent with limit returned {data['count']} outcomes")
    
    def test_recent_all_horizons(self):
        """Test recent endpoint for all valid horizons"""
        horizons = ['1D', '7D', '30D']
        for horizon in horizons:
            params = {'horizon': horizon}
            response = requests.get(f"{BASE_URL}/api/market/forecast-outcomes/recent", params=params)
            assert response.status_code == 200
            data = response.json()
            assert data['ok'] == True
            assert data['horizon'] == horizon
            print(f"SUCCESS: Recent for {horizon} horizon returned correctly")


class TestForecastOnlyEndpoint:
    """Tests for GET /api/market/forecast-only - Snapshot creation"""
    
    def test_forecast_only_default_params(self):
        """Test forecast-only with default parameters"""
        response = requests.get(f"{BASE_URL}/api/market/forecast-only")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert 'symbol' in data
        assert 'layer' in data
        assert 'horizon' in data
        assert 'startPrice' in data
        assert 'targetPrice' in data
        assert 'expectedMovePct' in data
        assert 'confidence' in data
        assert 'direction' in data
        assert 'candles' in data
        assert isinstance(data['candles'], list)
        assert len(data['candles']) > 0
        print(f"SUCCESS: forecast-only returned {len(data['candles'])} candles")
    
    def test_forecast_only_creates_snapshot_or_exists(self):
        """Test that forecast-only creates a snapshot or returns existing"""
        params = {
            'symbol': 'BTC',
            'layer': 'exchange',
            'horizon': '7D'
        }
        response = requests.get(f"{BASE_URL}/api/market/forecast-only", params=params)
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        # snapshotId is optional - might be undefined if already exists
        if 'snapshotId' in data and data['snapshotId']:
            print(f"SUCCESS: New snapshot created with ID: {data['snapshotId']}")
        else:
            print("SUCCESS: Snapshot already exists for today (no new snapshotId)")
    
    def test_forecast_only_1d_horizon(self):
        """Test forecast-only with 1D horizon - should return 2 candles"""
        params = {
            'symbol': 'BTC',
            'layer': 'forecast',
            'horizon': '1D'
        }
        response = requests.get(f"{BASE_URL}/api/market/forecast-only", params=params)
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert data['horizon'] == '1D'
        assert len(data['candles']) == 2  # day0 + day1
        print(f"SUCCESS: 1D horizon returned 2 candles")
    
    def test_forecast_only_7d_horizon(self):
        """Test forecast-only with 7D horizon - should return 8 candles"""
        params = {
            'symbol': 'BTC',
            'layer': 'exchange',
            'horizon': '7D'
        }
        response = requests.get(f"{BASE_URL}/api/market/forecast-only", params=params)
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert data['horizon'] == '7D'
        assert len(data['candles']) == 8  # day0...day7
        print(f"SUCCESS: 7D horizon returned 8 candles")
    
    def test_forecast_only_30d_horizon(self):
        """Test forecast-only with 30D horizon - should return 31 candles"""
        params = {
            'symbol': 'BTC',
            'layer': 'forecast',
            'horizon': '30D'
        }
        response = requests.get(f"{BASE_URL}/api/market/forecast-only", params=params)
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert data['horizon'] == '30D'
        assert len(data['candles']) == 31  # day0...day30
        print(f"SUCCESS: 30D horizon returned 31 candles")
    
    def test_forecast_only_candle_structure(self):
        """Test that candles have correct OHLC structure"""
        response = requests.get(f"{BASE_URL}/api/market/forecast-only?horizon=1D")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        
        for candle in data['candles']:
            assert 'time' in candle
            assert 'open' in candle
            assert 'high' in candle
            assert 'low' in candle
            assert 'close' in candle
            # Validate OHLC constraints
            assert candle['high'] >= candle['low']
            assert candle['high'] >= candle['open']
            assert candle['high'] >= candle['close']
            assert candle['low'] <= candle['open']
            assert candle['low'] <= candle['close']
        print("SUCCESS: All candles have valid OHLC structure")
    
    def test_forecast_only_direction_values(self):
        """Test that direction is one of valid values"""
        response = requests.get(f"{BASE_URL}/api/market/forecast-only")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert data['direction'] in ['UP', 'DOWN', 'FLAT']
        print(f"SUCCESS: Direction is {data['direction']}")
    
    def test_forecast_only_invalid_layer(self):
        """Test forecast-only with invalid layer"""
        params = {'layer': 'invalid'}
        response = requests.get(f"{BASE_URL}/api/market/forecast-only", params=params)
        assert response.status_code == 400
        
        data = response.json()
        assert data['ok'] == False
        assert data['error'] == 'INVALID_LAYER'
        print("SUCCESS: Invalid layer returns 400")
    
    def test_forecast_only_frozen_layers(self):
        """Test that onchain and sentiment layers are frozen"""
        frozen_layers = ['onchain', 'sentiment']
        for layer in frozen_layers:
            params = {'layer': layer}
            response = requests.get(f"{BASE_URL}/api/market/forecast-only", params=params)
            assert response.status_code == 503
            
            data = response.json()
            assert data['ok'] == False
            assert data['error'] == 'LAYER_FROZEN'
            print(f"SUCCESS: {layer} layer returns 503 (frozen)")


class TestIntegration:
    """Integration tests for outcome tracking flow"""
    
    def test_full_workflow(self):
        """Test the full workflow: forecast -> outcomes -> stats"""
        # Step 1: Get a forecast (creates snapshot)
        forecast_response = requests.get(
            f"{BASE_URL}/api/market/forecast-only",
            params={'symbol': 'ETH', 'layer': 'exchange', 'horizon': '1D'}
        )
        assert forecast_response.status_code == 200
        forecast_data = forecast_response.json()
        assert forecast_data['ok'] == True
        print(f"Step 1: Forecast created for ETH")
        
        # Step 2: Check outcomes (should be empty or have data from previous)
        outcomes_response = requests.get(
            f"{BASE_URL}/api/market/forecast-outcomes",
            params={'symbol': 'ETH', 'layer': 'exchange', 'horizon': '1D'}
        )
        assert outcomes_response.status_code == 200
        outcomes_data = outcomes_response.json()
        assert outcomes_data['ok'] == True
        print(f"Step 2: Outcomes count: {outcomes_data['count']}")
        
        # Step 3: Check stats
        stats_response = requests.get(
            f"{BASE_URL}/api/market/forecast-outcomes/stats",
            params={'symbol': 'ETH', 'layer': 'exchange', 'horizon': '1D'}
        )
        assert stats_response.status_code == 200
        stats_data = stats_response.json()
        assert stats_data['ok'] == True
        print(f"Step 3: Stats - Total: {stats_data['total']}, WinRate: {stats_data['winRate']}")
        
        print("SUCCESS: Full workflow completed")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
