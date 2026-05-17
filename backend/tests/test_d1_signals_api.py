"""
Test D1 Signals API Endpoints
=============================
Tests for the D1 signals backend API at /api/d1-signals
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com').rstrip('/')


class TestD1SignalsAPI:
    """Test D1 Signals API endpoints"""
    
    def test_get_signals_with_default_window(self):
        """Test GET /api/d1-signals?window=7d returns ok:true with proper structure"""
        response = requests.get(f"{BASE_URL}/api/d1-signals?window=7d")
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        assert data.get('ok') == True
        assert 'items' in data
        assert 'meta' in data
        assert isinstance(data['items'], list)
        
        # Validate meta structure
        meta = data['meta']
        assert meta.get('window') == '7d'
        assert 'page' in meta
        assert 'limit' in meta
        assert 'total' in meta
        assert 'hasMore' in meta
        
        print(f"✅ GET /api/d1-signals?window=7d - ok:true, items count: {len(data['items'])}, total: {meta.get('total')}")
    
    def test_get_signals_with_24h_window(self):
        """Test GET /api/d1-signals?window=24h"""
        response = requests.get(f"{BASE_URL}/api/d1-signals?window=24h")
        
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        assert data['meta'].get('window') == '24h'
        print(f"✅ GET /api/d1-signals?window=24h - ok:true")
    
    def test_get_signals_with_30d_window(self):
        """Test GET /api/d1-signals?window=30d"""
        response = requests.get(f"{BASE_URL}/api/d1-signals?window=30d")
        
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        assert data['meta'].get('window') == '30d'
        print(f"✅ GET /api/d1-signals?window=30d - ok:true")
    
    def test_get_signals_with_status_filter(self):
        """Test GET /api/d1-signals with status filter"""
        response = requests.get(f"{BASE_URL}/api/d1-signals?window=7d&status=new,active")
        
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        print(f"✅ GET /api/d1-signals with status filter - ok:true")
    
    def test_get_signals_with_pagination(self):
        """Test GET /api/d1-signals with pagination params"""
        response = requests.get(f"{BASE_URL}/api/d1-signals?window=7d&page=1&limit=5")
        
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        assert data['meta'].get('page') == 1
        assert data['meta'].get('limit') == 5
        print(f"✅ GET /api/d1-signals with pagination - ok:true")


class TestD1SignalsStatsAPI:
    """Test D1 Signals Stats API endpoints"""
    
    def test_get_stats_summary_7d(self):
        """Test GET /api/d1-signals/stats/summary?window=7d returns ok:true with proper structure"""
        response = requests.get(f"{BASE_URL}/api/d1-signals/stats/summary?window=7d")
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        assert data.get('ok') == True
        assert 'data' in data
        
        stats_data = data['data']
        assert stats_data.get('window') == '7d'
        assert 'counts' in stats_data
        
        # Validate counts structure
        counts = stats_data['counts']
        assert 'active' in counts
        assert 'new' in counts
        assert 'total' in counts
        
        print(f"✅ GET /api/d1-signals/stats/summary?window=7d - ok:true, counts: {counts}")
    
    def test_get_stats_summary_24h(self):
        """Test GET /api/d1-signals/stats/summary?window=24h"""
        response = requests.get(f"{BASE_URL}/api/d1-signals/stats/summary?window=24h")
        
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        assert data['data'].get('window') == '24h'
        print(f"✅ GET /api/d1-signals/stats/summary?window=24h - ok:true")
    
    def test_get_stats_summary_30d(self):
        """Test GET /api/d1-signals/stats/summary?window=30d"""
        response = requests.get(f"{BASE_URL}/api/d1-signals/stats/summary?window=30d")
        
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        assert data['data'].get('window') == '30d'
        print(f"✅ GET /api/d1-signals/stats/summary?window=30d - ok:true")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
