"""
TradingView Candlestick Chart API Tests
======================================
Tests for the /api/market/candles endpoint that provides OHLC data
for the TradingView Lightweight Charts implementation.

Features tested:
- OHLC candlestick data format
- Dynamic resolution based on time range
- Multiple assets (BTC, ETH, SOL, BNB)
- Volume histogram data
- Y-axis auto-scaling data
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com')


class TestCandlesEndpoint:
    """Test /api/market/candles endpoint for TradingView chart"""
    
    def test_btc_7d_returns_ohlc_data(self):
        """Test BTC with 7d range returns proper OHLC candles"""
        response = requests.get(f"{BASE_URL}/api/market/candles?symbol=BTC&range=7d")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') is True, "Response should have ok: true"
        assert data.get('symbol') == 'BTC', f"Expected BTC, got {data.get('symbol')}"
        assert data.get('range') == '7d', f"Expected 7d, got {data.get('range')}"
        assert data.get('resolution') == '15m', f"Expected 15m resolution for 7d, got {data.get('resolution')}"
        
        # Verify candle count (should be ~672 for 7d with 15m)
        candle_count = data.get('candleCount', 0)
        assert candle_count > 600, f"Expected >600 candles, got {candle_count}"
        
        # Verify OHLC structure
        candles = data.get('candles', [])
        assert len(candles) > 0, "Candles array should not be empty"
        
        first_candle = candles[0]
        assert 'time' in first_candle, "Candle should have time"
        assert 'open' in first_candle, "Candle should have open"
        assert 'high' in first_candle, "Candle should have high"
        assert 'low' in first_candle, "Candle should have low"
        assert 'close' in first_candle, "Candle should have close"
        assert 'volume' in first_candle, "Candle should have volume"
        
        # Verify OHLC values make sense
        assert first_candle['high'] >= first_candle['low'], "High should be >= low"
        assert first_candle['high'] >= first_candle['open'], "High should be >= open"
        assert first_candle['high'] >= first_candle['close'], "High should be >= close"
        assert first_candle['low'] <= first_candle['open'], "Low should be <= open"
        assert first_candle['low'] <= first_candle['close'], "Low should be <= close"
    
    def test_24h_resolution(self):
        """Test 24h range uses 5m resolution"""
        response = requests.get(f"{BASE_URL}/api/market/candles?symbol=BTC&range=24h")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        assert data.get('resolution') == '5m', f"Expected 5m resolution for 24h, got {data.get('resolution')}"
        assert data.get('candleCount', 0) > 250, "Expected >250 candles for 24h"
    
    def test_30d_resolution(self):
        """Test 30d range uses 1h resolution"""
        response = requests.get(f"{BASE_URL}/api/market/candles?symbol=SOL&range=30d")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        assert data.get('resolution') == '1h', f"Expected 1h resolution for 30d, got {data.get('resolution')}"
        assert data.get('candleCount', 0) > 700, "Expected >700 candles for 30d"
    
    def test_90d_resolution(self):
        """Test 90d range uses 4h resolution"""
        response = requests.get(f"{BASE_URL}/api/market/candles?symbol=BNB&range=90d")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        assert data.get('resolution') == '4h', f"Expected 4h resolution for 90d, got {data.get('resolution')}"
        assert data.get('candleCount', 0) > 500, "Expected >500 candles for 90d"
    
    def test_eth_asset(self):
        """Test ETH asset returns valid data"""
        response = requests.get(f"{BASE_URL}/api/market/candles?symbol=ETH&range=7d")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        assert data.get('symbol') == 'ETH'
        assert len(data.get('candles', [])) > 0
    
    def test_sol_asset(self):
        """Test SOL asset returns valid data"""
        response = requests.get(f"{BASE_URL}/api/market/candles?symbol=SOL&range=7d")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        assert data.get('symbol') == 'SOL'
        assert len(data.get('candles', [])) > 0
    
    def test_bnb_asset(self):
        """Test BNB asset returns valid data"""
        response = requests.get(f"{BASE_URL}/api/market/candles?symbol=BNB&range=7d")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        assert data.get('symbol') == 'BNB'
        assert len(data.get('candles', [])) > 0
    
    def test_volume_data_returned(self):
        """Test that volume data is returned separately for histogram"""
        response = requests.get(f"{BASE_URL}/api/market/candles?symbol=BTC&range=7d")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        
        # Volume array should exist
        volume = data.get('volume', [])
        assert len(volume) > 0, "Volume array should not be empty"
        
        # Each volume entry should have time, value, color
        first_vol = volume[0]
        assert 'time' in first_vol, "Volume should have time"
        assert 'value' in first_vol, "Volume should have value"
        assert 'color' in first_vol, "Volume should have color for histogram"
    
    def test_time_in_unix_seconds(self):
        """Test that time is in UNIX seconds (required by lightweight-charts)"""
        response = requests.get(f"{BASE_URL}/api/market/candles?symbol=BTC&range=7d")
        
        assert response.status_code == 200
        data = response.json()
        
        candles = data.get('candles', [])
        assert len(candles) > 0
        
        first_time = candles[0]['time']
        # UNIX seconds should be ~10 digits, not 13 (milliseconds)
        assert first_time < 10000000000, "Time should be in UNIX seconds, not milliseconds"
        assert first_time > 1700000000, "Time should be a valid UNIX timestamp"
    
    def test_provider_info_returned(self):
        """Test that provider information is returned"""
        response = requests.get(f"{BASE_URL}/api/market/candles?symbol=BTC&range=7d")
        
        assert response.status_code == 200
        data = response.json()
        
        assert 'provider' in data, "Should return provider info"
        assert 'dataMode' in data, "Should return dataMode"
        # Provider should be BYBIT or BINANCE
        assert 'BYBIT' in data['provider'] or 'BINANCE' in data['provider']
    
    def test_default_range_is_7d(self):
        """Test that default range is 7d when not specified"""
        response = requests.get(f"{BASE_URL}/api/market/candles?symbol=BTC")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        assert data.get('range') == '7d', f"Default range should be 7d, got {data.get('range')}"
    
    def test_symbol_normalization(self):
        """Test that symbol is normalized (BTCUSDT -> BTC)"""
        response = requests.get(f"{BASE_URL}/api/market/candles?symbol=BTCUSDT&range=7d")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        assert data.get('symbol') == 'BTC', "BTCUSDT should be normalized to BTC"
    
    def test_lowercase_symbol(self):
        """Test that lowercase symbols work"""
        response = requests.get(f"{BASE_URL}/api/market/candles?symbol=btc&range=7d")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        assert data.get('symbol') == 'BTC', "Lowercase btc should work"


class TestCandlesDataQuality:
    """Test data quality and consistency of candles endpoint"""
    
    def test_candles_sorted_by_time(self):
        """Test that candles are sorted by time ascending"""
        response = requests.get(f"{BASE_URL}/api/market/candles?symbol=BTC&range=7d")
        
        assert response.status_code == 200
        data = response.json()
        
        candles = data.get('candles', [])
        assert len(candles) > 1
        
        for i in range(1, len(candles)):
            assert candles[i]['time'] > candles[i-1]['time'], \
                f"Candles should be sorted ascending at index {i}"
    
    def test_prices_are_realistic(self):
        """Test that BTC prices are in realistic range"""
        response = requests.get(f"{BASE_URL}/api/market/candles?symbol=BTC&range=7d")
        
        assert response.status_code == 200
        data = response.json()
        
        candles = data.get('candles', [])
        
        for candle in candles[:10]:  # Check first 10
            assert candle['open'] > 1000, "BTC price should be > $1000"
            assert candle['open'] < 500000, "BTC price should be < $500000"
    
    def test_eth_prices_are_realistic(self):
        """Test that ETH prices are in realistic range"""
        response = requests.get(f"{BASE_URL}/api/market/candles?symbol=ETH&range=7d")
        
        assert response.status_code == 200
        data = response.json()
        
        candles = data.get('candles', [])
        
        for candle in candles[:10]:  # Check first 10
            assert candle['open'] > 100, "ETH price should be > $100"
            assert candle['open'] < 50000, "ETH price should be < $50000"
    
    def test_volume_positive(self):
        """Test that volume values are positive"""
        response = requests.get(f"{BASE_URL}/api/market/candles?symbol=BTC&range=7d")
        
        assert response.status_code == 200
        data = response.json()
        
        candles = data.get('candles', [])
        
        for candle in candles[:10]:
            assert candle['volume'] >= 0, "Volume should be >= 0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
