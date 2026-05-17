"""
Test Market Context Redesign (Prediction > Exchange page bottom section)

Features tested:
1. Macro Impact API returns Fear & Greed, BTC Dominance, Stable Dominance
2. Sector Rotation API returns sectors with scores
3. Labs Alerts API returns active alerts
4. Funding API is intentionally NOT_FOUND (removed due to broken API)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com')


class TestMarketContextAPIs:
    """API tests for Market Context section data sources"""

    def test_macro_impact_api_returns_ok(self):
        """Test /api/v10/macro/impact returns ok:true with data"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/impact")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        assert 'data' in data

    def test_macro_impact_has_fear_greed(self):
        """Test macro API has Fear & Greed in bullets or signal"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/impact")
        data = response.json()
        assert data.get('ok') == True
        
        signal = data.get('data', {}).get('signal', {})
        explain = signal.get('explain', {})
        bullets = explain.get('bullets', [])
        
        # Check Fear & Greed is present
        has_fg = any('Fear & Greed' in b for b in bullets)
        assert has_fg, "Fear & Greed not found in bullets"

    def test_macro_impact_has_btc_dominance(self):
        """Test macro API has BTC Dominance data"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/impact")
        data = response.json()
        
        bullets = data.get('data', {}).get('signal', {}).get('explain', {}).get('bullets', [])
        has_btc_dom = any('BTC Dominance' in b for b in bullets)
        assert has_btc_dom, "BTC Dominance not found in bullets"

    def test_macro_impact_has_stable_dominance(self):
        """Test macro API has Stablecoin Dominance data"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/impact")
        data = response.json()
        
        bullets = data.get('data', {}).get('signal', {}).get('explain', {}).get('bullets', [])
        has_stable_dom = any('Stablecoin Dominance' in b or 'Stable' in b for b in bullets)
        assert has_stable_dom, "Stablecoin Dominance not found in bullets"

    def test_macro_impact_has_blocked_flag(self):
        """Test macro API returns blockedStrong flag"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/impact")
        data = response.json()
        
        impact = data.get('data', {}).get('impact', {})
        assert 'blockedStrong' in impact, "blockedStrong flag missing"

    def test_sector_rotation_api_returns_ok(self):
        """Test /api/market/rotation/sectors returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/market/rotation/sectors?window=4h")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True

    def test_sector_rotation_has_sectors(self):
        """Test sectors API returns sectors array"""
        response = requests.get(f"{BASE_URL}/api/market/rotation/sectors?window=4h")
        data = response.json()
        
        sectors = data.get('sectors', [])
        assert len(sectors) > 0, "No sectors returned"

    def test_sector_rotation_has_expected_sectors(self):
        """Test that expected sectors are present (GAMING, RWA, AI, etc)"""
        response = requests.get(f"{BASE_URL}/api/market/rotation/sectors?window=4h")
        data = response.json()
        
        sector_names = [s.get('sector') for s in data.get('sectors', [])]
        expected = ['GAMING', 'RWA', 'AI', 'L2', 'INFRA', 'ORACLE']
        
        for expected_sector in expected:
            assert expected_sector in sector_names, f"{expected_sector} not found in sectors"

    def test_sector_has_rotation_score(self):
        """Test each sector has a rotationScore"""
        response = requests.get(f"{BASE_URL}/api/market/rotation/sectors?window=4h")
        data = response.json()
        
        for sector in data.get('sectors', []):
            assert 'rotationScore' in sector, f"rotationScore missing for {sector.get('sector')}"
            assert isinstance(sector['rotationScore'], (int, float))

    def test_labs_alerts_api_returns_ok(self):
        """Test POST /api/v10/exchange/labs/v3/alerts/check returns ok:true"""
        response = requests.post(f"{BASE_URL}/api/v10/exchange/labs/v3/alerts/check?symbol=BTC")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True

    def test_labs_alerts_has_counts(self):
        """Test labs API returns alert counts"""
        response = requests.post(f"{BASE_URL}/api/v10/exchange/labs/v3/alerts/check?symbol=BTC")
        data = response.json()
        
        counts = data.get('counts', {})
        expected_keys = ['EMERGENCY', 'CRITICAL', 'WARNING', 'INFO']
        for key in expected_keys:
            assert key in counts, f"{key} missing from counts"

    def test_labs_alerts_has_active_alerts_array(self):
        """Test labs API returns activeAlerts array"""
        response = requests.post(f"{BASE_URL}/api/v10/exchange/labs/v3/alerts/check?symbol=BTC")
        data = response.json()
        
        assert 'activeAlerts' in data
        assert isinstance(data['activeAlerts'], list)

    def test_funding_api_removed(self):
        """Test /api/v10/exchange/funding/sentiment returns 404 (intentionally removed)"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/funding/sentiment?symbol=BTCUSDT")
        data = response.json()
        
        # Funding API should return ok:false or NOT_FOUND - this is expected behavior
        assert data.get('ok') == False or data.get('error') == 'NOT_FOUND', \
            "Funding API should be disabled/removed"


class TestExchangeAltSignalsTable:
    """Test Exchange Alt Signals table above Market Context"""

    def test_top_alts_api_returns_ok(self):
        """Test /api/market/exchange/top-alts-v2 returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/market/exchange/top-alts-v2?horizon=7D&limit=20")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True

    def test_top_alts_has_rows(self):
        """Test top-alts API returns rows array"""
        response = requests.get(f"{BASE_URL}/api/market/exchange/top-alts-v2?horizon=7D&limit=20")
        data = response.json()
        
        rows = data.get('rows', [])
        assert len(rows) > 0, "No rows returned"

    def test_top_alts_row_structure(self):
        """Test each row has required fields"""
        response = requests.get(f"{BASE_URL}/api/market/exchange/top-alts-v2?horizon=7D&limit=10")
        data = response.json()
        
        for row in data.get('rows', []):
            assert 'symbol' in row
            assert 'direction' in row
            assert row['direction'] in ['LONG', 'SHORT']
            assert 'confidenceFinal' in row
            assert 'expectedMovePctFinal' in row


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
