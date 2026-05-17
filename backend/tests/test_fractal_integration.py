"""
Fractal Engine Integration Tests
=================================
Tests for the Fractal Engine module integration:
- BTC Fractal terminal API
- SPX Fractal terminal API
- DXY Fractal terminal API
- SPX unified endpoint

These APIs power the Fractal pages at:
- /intelligence/fractal (BTC)
- /intelligence/fractal/spx (SPX)
- /intelligence/fractal/dxy (DXY)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com').rstrip('/')

class TestFractalBTC:
    """BTC Fractal Terminal API tests"""
    
    def test_btc_terminal_basic(self):
        """Test BTC terminal endpoint with default params"""
        response = requests.get(f"{BASE_URL}/api/fractal/v2.1/terminal?horizon=14d")
        assert response.status_code == 200
        
        data = response.json()
        # BTC terminal returns meta, chart, etc. at root level
        assert 'meta' in data
        assert 'chart' in data
        
    def test_btc_terminal_with_focus(self):
        """Test BTC terminal with focus param"""
        response = requests.get(f"{BASE_URL}/api/fractal/v2.1/terminal?horizon=30d")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('meta', {}).get('focus') == '30d'
        
    def test_btc_terminal_has_candles(self):
        """Test BTC terminal returns candle data"""
        response = requests.get(f"{BASE_URL}/api/fractal/v2.1/terminal?horizon=14d")
        assert response.status_code == 200
        
        data = response.json()
        candles = data.get('chart', {}).get('candles', [])
        assert len(candles) > 0, "No candles returned"


class TestFractalSPX:
    """SPX Fractal Terminal API tests"""
    
    def test_spx_terminal_basic(self):
        """Test SPX terminal endpoint"""
        response = requests.get(f"{BASE_URL}/api/fractal/spx/terminal?horizon=10d")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert data.get('symbol') == 'SPX'
        
    def test_spx_terminal_has_decision(self):
        """Test SPX terminal returns decision"""
        response = requests.get(f"{BASE_URL}/api/fractal/spx/terminal?horizon=30d")
        assert response.status_code == 200
        
        data = response.json()
        assert 'decision' in data
        assert data['decision'].get('action') in ['LONG', 'SHORT', 'HOLD']
        
    def test_spx_unified_endpoint(self):
        """Test SPX unified endpoint (BTC-compatible contract)"""
        response = requests.get(f"{BASE_URL}/api/fractal/spx?focus=30d")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert 'data' in data
        
        # Verify contract structure
        contract_data = data['data']
        assert 'decision' in contract_data
        assert 'horizons' in contract_data
        assert 'market' in contract_data
        
    def test_spx_market_info(self):
        """Test SPX returns market info"""
        response = requests.get(f"{BASE_URL}/api/fractal/spx?focus=30d")
        assert response.status_code == 200
        
        data = response.json()
        market = data.get('data', {}).get('market', {})
        
        assert 'phase' in market
        assert 'currentPrice' in market
        assert market['currentPrice'] > 0


class TestFractalDXY:
    """DXY Fractal Terminal API tests"""
    
    def test_dxy_terminal_basic(self):
        """Test DXY terminal endpoint"""
        response = requests.get(f"{BASE_URL}/api/fractal/dxy/terminal?horizon=5d")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert data.get('asset') == 'DXY'
        
    def test_dxy_terminal_has_core(self):
        """Test DXY terminal returns core data"""
        response = requests.get(f"{BASE_URL}/api/fractal/dxy/terminal?focus=30d")
        assert response.status_code == 200
        
        data = response.json()
        assert 'core' in data
        assert 'current' in data['core']
        assert 'matches' in data['core']
        
    def test_dxy_terminal_has_meta(self):
        """Test DXY terminal returns meta info"""
        response = requests.get(f"{BASE_URL}/api/fractal/dxy/terminal?focus=30d")
        assert response.status_code == 200
        
        data = response.json()
        assert 'meta' in data
        
    def test_dxy_matches_exist(self):
        """Test DXY returns historical matches"""
        response = requests.get(f"{BASE_URL}/api/fractal/dxy/terminal?focus=30d")
        assert response.status_code == 200
        
        data = response.json()
        matches = data.get('core', {}).get('matches', [])
        assert len(matches) > 0, "No DXY matches returned"


class TestPredictionPage:
    """Prediction page API tests (verifies lightweight-charts v5 compatibility)"""
    
    def test_market_candles_btc(self):
        """Test market candles endpoint for BTC"""
        response = requests.get(f"{BASE_URL}/api/market/candles?symbol=BTCUSDT&range=7d")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert 'candles' in data
        assert len(data['candles']) > 0
        
    def test_price_expectation_v4(self):
        """Test price vs expectation v4 endpoint"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v4?asset=BTC&range=7d&horizon=1D")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True


class TestHealthEndpoint:
    """Health check tests"""
    
    def test_health_ok(self):
        """Test health endpoint returns ok"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
