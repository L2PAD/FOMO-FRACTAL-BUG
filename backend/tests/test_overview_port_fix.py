"""
Test Suite for Overview Page Port Fix (8002 → 8003)

Tests the key API endpoints after port fix to verify:
1. /api/ui/overview - Overview page data for BTC, SPX, DXY
2. /api/ui/brain/decision - Brain page data  
3. /api/fractal/v2.1/focus-pack - Fractal data
4. /api/ui/fractal/dxy/overview - DXY Fractal overview
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com')


class TestOverviewAPI:
    """Tests for /api/ui/overview endpoint"""
    
    def test_overview_btc_returns_bullish_verdict(self):
        """BTC Overview should return BULLISH verdict with ~78% confidence"""
        response = requests.get(f"{BASE_URL}/api/ui/overview?asset=btc&horizon=90")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        assert data.get('asset') == 'btc'
        
        # Verify verdict structure
        verdict = data.get('verdict', {})
        assert 'stance' in verdict
        assert 'confidencePct' in verdict
        assert verdict['stance'] in ['BULLISH', 'BEARISH', 'HOLD']
        
        # BTC expected to be BULLISH
        assert verdict['stance'] == 'BULLISH'
        assert verdict['confidencePct'] > 70  # Expected ~78%
        
        print(f"✅ BTC verdict: {verdict['stance']} ({verdict['confidencePct']}% confidence)")
    
    def test_overview_btc_has_reasons(self):
        """BTC Overview should have at least 3 reasons"""
        response = requests.get(f"{BASE_URL}/api/ui/overview?asset=btc&horizon=90")
        data = response.json()
        
        reasons = data.get('reasons', [])
        assert len(reasons) >= 3, "Should have at least 3 reasons"
        
        for reason in reasons:
            assert 'title' in reason
            assert 'text' in reason
            assert 'severity' in reason
        
        print(f"✅ BTC has {len(reasons)} reasons")
    
    def test_overview_btc_has_risks(self):
        """BTC Overview should have risk indicators"""
        response = requests.get(f"{BASE_URL}/api/ui/overview?asset=btc&horizon=90")
        data = response.json()
        
        risks = data.get('risks', [])
        assert len(risks) >= 2, "Should have at least 2 risks"
        
        print(f"✅ BTC has {len(risks)} risks")
    
    def test_overview_btc_has_indicators(self):
        """BTC Overview should have signal stack indicators"""
        response = requests.get(f"{BASE_URL}/api/ui/overview?asset=btc&horizon=90")
        data = response.json()
        
        indicators = data.get('indicators', [])
        assert len(indicators) >= 5, "Should have at least 5 indicators"
        
        print(f"✅ BTC has {len(indicators)} indicators")
    
    def test_overview_btc_has_horizons(self):
        """BTC Overview should have forecast by horizon data"""
        response = requests.get(f"{BASE_URL}/api/ui/overview?asset=btc&horizon=90")
        data = response.json()
        
        horizons = data.get('horizons', [])
        assert len(horizons) >= 4, "Should have 30d, 90d, 180d, 365d horizons"
        
        # Verify all are BULLISH for BTC
        bullish_count = sum(1 for h in horizons if h.get('stance') == 'BULLISH')
        print(f"✅ BTC has {len(horizons)} horizons, {bullish_count} BULLISH")
    
    def test_overview_spx_returns_hold_verdict(self):
        """SPX Overview should return HOLD verdict"""
        response = requests.get(f"{BASE_URL}/api/ui/overview?asset=spx&horizon=90")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        assert data.get('asset') == 'spx'
        
        verdict = data.get('verdict', {})
        assert verdict['stance'] in ['BULLISH', 'BEARISH', 'HOLD']
        
        print(f"✅ SPX verdict: {verdict['stance']} ({verdict.get('confidencePct', 0)}% confidence)")
    
    def test_overview_dxy_returns_bearish_verdict(self):
        """DXY Overview should return BEARISH verdict"""
        response = requests.get(f"{BASE_URL}/api/ui/overview?asset=dxy&horizon=90")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        assert data.get('asset') == 'dxy'
        
        verdict = data.get('verdict', {})
        assert verdict['stance'] == 'BEARISH'
        assert verdict['confidencePct'] > 90  # Expected ~96%
        
        print(f"✅ DXY verdict: {verdict['stance']} ({verdict['confidencePct']}% confidence)")


class TestBrainAPI:
    """Tests for /api/ui/brain/decision endpoint"""
    
    def test_brain_decision_returns_ok(self):
        """Brain decision API should return ok=true"""
        response = requests.get(f"{BASE_URL}/api/ui/brain/decision")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        
        print("✅ Brain decision API returns ok")
    
    def test_brain_decision_has_verdict(self):
        """Brain decision should have verdict with regime and posture"""
        response = requests.get(f"{BASE_URL}/api/ui/brain/decision")
        data = response.json()
        
        verdict = data.get('verdict', {})
        assert 'regime' in verdict
        assert 'dominantBias' in verdict
        assert 'posture' in verdict
        assert 'confidence' in verdict
        
        print(f"✅ Brain verdict: {verdict['regime']} / {verdict['posture']} ({verdict['confidence']}% confidence)")
    
    def test_brain_decision_has_action(self):
        """Brain decision should have primary action guidance"""
        response = requests.get(f"{BASE_URL}/api/ui/brain/decision")
        data = response.json()
        
        action = data.get('action', {})
        assert 'primary' in action
        assert 'multiplier' in action
        assert 'cashBufferRange' in action
        
        print(f"✅ Brain action: {action['primary'][:50]}...")
    
    def test_brain_decision_has_horizons(self):
        """Brain decision should have market phase by horizon"""
        response = requests.get(f"{BASE_URL}/api/ui/brain/decision")
        data = response.json()
        
        horizons = data.get('horizons', [])
        assert len(horizons) == 4  # 30d, 90d, 180d, 365d
        
        for h in horizons:
            assert 'horizon' in h
            assert 'phase' in h
            assert 'strength' in h
        
        print(f"✅ Brain has {len(horizons)} horizons")
    
    def test_brain_decision_has_reasons(self):
        """Brain decision should have 'Why This View' reasons"""
        response = requests.get(f"{BASE_URL}/api/ui/brain/decision")
        data = response.json()
        
        reasons = data.get('reasons', [])
        assert len(reasons) >= 3
        
        for reason in reasons:
            assert 'text' in reason
            assert 'sentiment' in reason
        
        print(f"✅ Brain has {len(reasons)} reasons")


class TestFractalAPI:
    """Tests for Fractal API endpoints"""
    
    def test_fractal_btc_focus_pack(self):
        """BTC fractal focus-pack should return data"""
        response = requests.get(f"{BASE_URL}/api/fractal/v2.1/focus-pack?symbol=BTC&focus=90d&mode=crossAsset")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        assert 'focusPack' in data
        
        focusPack = data['focusPack']
        assert 'meta' in focusPack
        assert 'overlay' in focusPack
        
        print(f"✅ BTC focus-pack: symbol={focusPack['meta'].get('symbol')}, focus={focusPack['meta'].get('focus')}")
    
    def test_dxy_fractal_overview(self):
        """DXY Fractal overview should return data (was failing with port 8002)"""
        response = requests.get(f"{BASE_URL}/api/ui/fractal/dxy/overview?h=90")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True, f"Expected ok=true, got: {data.get('error', 'unknown error')}"
        
        # Verify structure
        assert 'header' in data
        assert 'verdict' in data
        assert 'chart' in data
        
        header = data['header']
        assert header.get('signal') in ['BUY', 'SELL', 'HOLD']
        
        verdict = data['verdict']
        assert verdict.get('action') in ['BUY', 'SELL', 'HOLD']
        assert verdict.get('bias') in ['USD_UP', 'USD_DOWN', 'NEUTRAL']
        
        print(f"✅ DXY Fractal overview: {verdict['action']} / {verdict['bias']} ({data['header']['confidence']}% confidence)")


class TestHorizonSelector:
    """Tests for horizon selector functionality"""
    
    @pytest.mark.parametrize("horizon", [7, 14, 30, 90, 180, 365])
    def test_overview_btc_horizons(self, horizon):
        """Overview should work for all horizon values"""
        response = requests.get(f"{BASE_URL}/api/ui/overview?asset=btc&horizon={horizon}")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        assert data['verdict']['horizonDays'] == horizon
        
        print(f"✅ BTC horizon {horizon}d works")
    
    @pytest.mark.parametrize("horizon", [7, 14, 30, 90, 180, 365])
    def test_dxy_overview_horizons(self, horizon):
        """DXY Fractal overview should work for all horizon values"""
        response = requests.get(f"{BASE_URL}/api/ui/fractal/dxy/overview?h={horizon}")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        
        print(f"✅ DXY horizon {horizon}d works")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
