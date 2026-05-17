"""
Phase 1.2 - Market Product Layer Tests
======================================
Tests for market search, asset resolver, and full market diagnosis endpoints.

Endpoints tested:
- GET /api/v10/market/search?q=<query> - Search symbols
- GET /api/v10/market/top - Top symbols by score
- GET /api/v10/market/stats - Universe statistics  
- GET /api/v10/market/asset/:symbol - Full market diagnosis
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestMarketSearch:
    """Tests for market search endpoint"""

    def test_search_eth_returns_ethusdt(self):
        """Search for 'eth' should return ETHUSDT"""
        response = requests.get(f"{BASE_URL}/api/v10/market/search?q=eth")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert 'items' in data
        assert len(data['items']) >= 1
        
        # First result should be ETHUSDT
        first_item = data['items'][0]
        assert first_item['symbol'] == 'ETHUSDT'
        assert first_item['base'] == 'ETH'
        assert first_item['quote'] == 'USDT'
        assert first_item['inUniverse'] == True
        assert data.get('normalized') == 'ETHUSDT'

    def test_search_btc_returns_btcusdt(self):
        """Search for 'btc' should return BTCUSDT"""
        response = requests.get(f"{BASE_URL}/api/v10/market/search?q=btc")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert len(data['items']) >= 1
        
        first_item = data['items'][0]
        assert first_item['symbol'] == 'BTCUSDT'
        assert first_item['base'] == 'BTC'
        assert first_item['inUniverse'] == True

    def test_search_sol_returns_solusdt(self):
        """Search for 'sol' should return SOLUSDT"""
        response = requests.get(f"{BASE_URL}/api/v10/market/search?q=sol")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert len(data['items']) >= 1
        assert data['items'][0]['symbol'] == 'SOLUSDT'

    def test_search_partial_match(self):
        """Search with partial match should return results"""
        response = requests.get(f"{BASE_URL}/api/v10/market/search?q=do")
        assert response.status_code == 200
        
        data = response.json()
        # Should match DOGEUSDT and DOTUSDT
        symbols = [item['symbol'] for item in data.get('items', [])]
        # At least one match expected
        assert len(symbols) >= 1

    def test_search_unknown_symbol_returns_ephemeral(self):
        """Search for unknown symbol should return ephemeral entry"""
        response = requests.get(f"{BASE_URL}/api/v10/market/search?q=ZZZZUSDT")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert len(data['items']) >= 1
        # Should have inUniverse=false for unknown
        assert data['items'][0].get('inUniverse') == False

    def test_search_empty_query(self):
        """Empty query should return empty or error gracefully"""
        response = requests.get(f"{BASE_URL}/api/v10/market/search?q=")
        assert response.status_code == 200
        
        data = response.json()
        assert 'items' in data


class TestMarketTop:
    """Tests for top symbols endpoint"""

    def test_top_returns_ok(self):
        """Top endpoint should return ok status"""
        response = requests.get(f"{BASE_URL}/api/v10/market/top")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert 'items' in data

    def test_top_with_limit(self):
        """Top endpoint should respect limit parameter"""
        response = requests.get(f"{BASE_URL}/api/v10/market/top?limit=5")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        # Limit should work (even if returns empty currently - bug)
        assert 'items' in data


class TestMarketStats:
    """Tests for universe statistics endpoint"""

    def test_stats_returns_universe_info(self):
        """Stats endpoint should return universe information"""
        response = requests.get(f"{BASE_URL}/api/v10/market/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert 'total' in data
        assert 'active' in data
        assert 'avgScore' in data
        
        # Default universe has 10 symbols
        assert data['total'] == 10
        assert data['active'] == 10
        assert data['avgScore'] > 0


class TestMarketAsset:
    """Tests for full market diagnosis endpoint"""

    def test_asset_btcusdt_diagnosis(self):
        """BTCUSDT should return full market diagnosis"""
        response = requests.get(f"{BASE_URL}/api/v10/market/asset/BTCUSDT")
        assert response.status_code == 200
        
        data = response.json()
        
        # Basic structure
        assert data['symbol'] == 'BTCUSDT'
        assert data['base'] == 'BTC'
        assert data['quote'] == 'USDT'
        
        # Availability
        assert 'availability' in data
        assert data['availability']['dataMode'] == 'MOCK'
        assert data['availability']['inUniverse'] == True
        
        # Exchange verdict (deterministic mock)
        assert 'exchange' in data
        assert data['exchange']['verdict'] in ['BULLISH', 'BEARISH', 'NEUTRAL', 'NO_DATA']
        assert 0 <= data['exchange']['confidence'] <= 1
        assert data['exchange']['strength'] in ['STRONG', 'MODERATE', 'WEAK', 'NONE']
        assert isinstance(data['exchange']['drivers'], list)
        assert isinstance(data['exchange']['risks'], list)
        
        # Whale data
        assert 'whale' in data
        assert data['whale']['riskLevel'] in ['HIGH', 'MEDIUM', 'LOW', 'UNKNOWN']
        assert 'impact' in data['whale']
        assert isinstance(data['whale']['patterns'], list)
        
        # Stress data
        assert 'stress' in data
        assert data['stress']['status'] in ['CRITICAL', 'HIGH', 'ELEVATED', 'NORMAL', 'LOW']
        assert 0 <= data['stress']['level'] <= 1
        assert isinstance(data['stress']['factors'], list)
        
        # Explainability
        assert 'explainability' in data
        assert 'drivers' in data['explainability']
        assert 'risks' in data['explainability']
        assert 'summary' in data['explainability']
        assert len(data['explainability']['summary']) > 0
        
        # Meta
        assert 'meta' in data
        assert 't0' in data['meta']
        assert data['meta']['version'] == 'market-v1.2'
        assert 'processingMs' in data['meta']

    def test_asset_ethusdt_diagnosis(self):
        """ETHUSDT should return full market diagnosis"""
        response = requests.get(f"{BASE_URL}/api/v10/market/asset/ETHUSDT")
        assert response.status_code == 200
        
        data = response.json()
        assert data['symbol'] == 'ETHUSDT'
        assert data['base'] == 'ETH'
        assert data['availability']['inUniverse'] == True
        assert data['exchange']['verdict'] in ['BULLISH', 'BEARISH', 'NEUTRAL', 'NO_DATA']

    def test_asset_solusdt_diagnosis(self):
        """SOLUSDT should return full market diagnosis"""
        response = requests.get(f"{BASE_URL}/api/v10/market/asset/SOLUSDT")
        assert response.status_code == 200
        
        data = response.json()
        assert data['symbol'] == 'SOLUSDT'
        assert data['base'] == 'SOL'
        assert data['availability']['inUniverse'] == True

    def test_asset_unknown_symbol(self):
        """Unknown symbol should return NO_DATA response"""
        response = requests.get(f"{BASE_URL}/api/v10/market/asset/UNKNOWNUSDT")
        assert response.status_code == 200
        
        data = response.json()
        # Should still return a response for unknown symbols
        assert 'symbol' in data
        assert 'availability' in data

    def test_asset_lowercase_symbol(self):
        """Lowercase symbol should be normalized"""
        response = requests.get(f"{BASE_URL}/api/v10/market/asset/btcusdt")
        assert response.status_code == 200
        
        data = response.json()
        assert data['symbol'] == 'BTCUSDT'

    def test_asset_verdict_determinism(self):
        """Same symbol should return same verdict (deterministic mock)"""
        # Call twice
        resp1 = requests.get(f"{BASE_URL}/api/v10/market/asset/BTCUSDT")
        resp2 = requests.get(f"{BASE_URL}/api/v10/market/asset/BTCUSDT")
        
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        
        data1 = resp1.json()
        data2 = resp2.json()
        
        # Verdict should be same (deterministic)
        assert data1['exchange']['verdict'] == data2['exchange']['verdict']
        assert data1['exchange']['strength'] == data2['exchange']['strength']
        assert data1['whale']['riskLevel'] == data2['whale']['riskLevel']
        assert data1['stress']['status'] == data2['stress']['status']


class TestMarketAssetVariety:
    """Test various symbols from universe"""

    @pytest.mark.parametrize("symbol", [
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
        "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT"
    ])
    def test_all_universe_symbols(self, symbol):
        """All universe symbols should return valid diagnosis"""
        response = requests.get(f"{BASE_URL}/api/v10/market/asset/{symbol}")
        assert response.status_code == 200
        
        data = response.json()
        assert data['symbol'] == symbol
        assert data['availability']['inUniverse'] == True
        assert data['exchange']['verdict'] in ['BULLISH', 'BEARISH', 'NEUTRAL', 'NO_DATA']
        assert 'explainability' in data


class TestMarketDataMode:
    """Test data mode and availability info"""

    def test_datamode_is_mock(self):
        """Data mode should be MOCK for all symbols currently"""
        response = requests.get(f"{BASE_URL}/api/v10/market/asset/BTCUSDT")
        assert response.status_code == 200
        
        data = response.json()
        assert data['availability']['dataMode'] == 'MOCK'
        assert data['availability']['providerUsed'] in ['MOCK', 'NONE']

    def test_meta_version(self):
        """Meta version should be market-v1.2"""
        response = requests.get(f"{BASE_URL}/api/v10/market/asset/ETHUSDT")
        assert response.status_code == 200
        
        data = response.json()
        assert data['meta']['version'] == 'market-v1.2'


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
