"""
S10.4 — Liquidation Cascade API Tests

Tests for cascade detection, history, and active cascades endpoints.
Uses mock data due to Binance API being blocked in environment.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestS104LiquidationCascadeAPIs:
    """Test S10.4 Liquidation Cascade endpoints"""
    
    # Supported symbols
    SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT']
    
    def test_cascade_state_btcusdt(self):
        """Test GET /api/v10/exchange/liquidation-cascade/BTCUSDT"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/liquidation-cascade/BTCUSDT")
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        assert data.get('ok') == True
        assert 'data' in data
        
        cascade_data = data['data']
        
        # Required fields
        assert 'status' in cascade_data  # NONE or ACTIVE
        assert cascade_data['status'] in ['NONE', 'ACTIVE']
        assert 'symbol' in cascade_data
        assert cascade_data['symbol'] == 'BTCUSDT'
        assert 'active' in cascade_data
        assert isinstance(cascade_data['active'], bool)
        
        # Intensity fields
        assert 'intensity' in cascade_data
        assert cascade_data['intensity'] in ['LOW', 'MEDIUM', 'HIGH', 'EXTREME']
        assert 'intensityScore' in cascade_data
        assert isinstance(cascade_data['intensityScore'], (int, float))
        
        # Volume and impact fields
        assert 'liquidationVolumeUsd' in cascade_data
        assert 'oiDeltaPct' in cascade_data
        assert 'priceDeltaPct' in cascade_data
        
        # Context fields
        assert 'regimeContext' in cascade_data
        assert 'confidence' in cascade_data
        assert 'timestamp' in cascade_data
        assert 'drivers' in cascade_data
        assert isinstance(cascade_data['drivers'], list)
        
        print(f"OK Cascade state for BTCUSDT: status={cascade_data['status']}, intensity={cascade_data['intensity']}")
    
    def test_cascade_history_btcusdt(self):
        """Test GET /api/v10/exchange/liquidation-cascade/history/BTCUSDT"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/liquidation-cascade/history/BTCUSDT")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') == True
        assert 'symbol' in data
        assert data['symbol'] == 'BTCUSDT'
        assert 'count' in data
        assert isinstance(data['count'], int)
        assert 'data' in data
        assert isinstance(data['data'], list)
        
        print("OK Cascade history endpoint working")
    
    def test_active_cascades(self):
        """Test GET /api/v10/exchange/liquidation-cascade/active"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/liquidation-cascade/active")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') == True
        assert 'count' in data
        assert isinstance(data['count'], int)
        assert 'data' in data
        assert isinstance(data['data'], list)
        assert data['count'] == len(data['data'])
        
        print("OK Active cascades endpoint working")

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
