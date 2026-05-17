"""
Test suite for Macro V2 Live Data APIs
Tests the LIVE market data integration with CryptoCompare, CoinPaprika, Alternative.me
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestMacroV2Snapshot:
    """Tests for /api/core/macro/snapshot with LIVE data"""
    
    def test_snapshot_returns_ok(self):
        """Snapshot endpoint returns ok=true"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True, f"Expected ok=true, got {data}"
    
    def test_snapshot_data_source_is_live(self):
        """Data source should be 'live' not 'synthetic'"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=30)
        data = response.json()
        assert data.get('dataSource') == 'live', f"Expected dataSource='live', got {data.get('dataSource')}"
    
    def test_snapshot_btc_price_realistic(self):
        """BTC price should be realistic (20k-200k range for 2025-2026)"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=30)
        data = response.json()
        raw = data.get('raw', {})
        btc_price = raw.get('btcPrice', 0)
        assert 20000 < btc_price < 200000, f"BTC price {btc_price} out of realistic range"
    
    def test_snapshot_fear_greed_matches_alternative_me(self):
        """Fear & Greed should match Alternative.me API (within tolerance)"""
        # Get live F&G from Alternative.me
        fng_response = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        fng_data = fng_response.json()
        live_fg = float(fng_data['data'][0]['value'])
        
        # Get our snapshot
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=30)
        data = response.json()
        snapshot_fg = data.get('raw', {}).get('fearGreed', 0)
        
        # Should be within 5 points (cache staleness tolerance)
        assert abs(snapshot_fg - live_fg) <= 5, f"F&G mismatch: snapshot={snapshot_fg}, live={live_fg}"
    
    def test_snapshot_btc_dominance_realistic(self):
        """BTC dominance should be realistic (35-75% range)"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=30)
        data = response.json()
        btc_dom = data.get('raw', {}).get('btcDom', 0)
        assert 35 < btc_dom < 75, f"BTC dominance {btc_dom}% out of realistic range"
    
    def test_snapshot_stable_dominance_realistic(self):
        """Stable dominance should be realistic (3-25% range)"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=30)
        data = response.json()
        stable_dom = data.get('raw', {}).get('stableDom', 0)
        assert 3 < stable_dom < 25, f"Stable dominance {stable_dom}% out of realistic range"
    
    def test_snapshot_computed_fields_present(self):
        """All computed fields should be present"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=30)
        data = response.json()
        computed = data.get('computed', {})
        
        assert 'regime' in computed, "Missing 'regime' in computed"
        assert 'riskOffProb' in computed, "Missing 'riskOffProb' in computed"
        assert 'macroMult' in computed, "Missing 'macroMult' in computed"
        assert 'regimeProbs' in computed, "Missing 'regimeProbs' in computed"
        assert 'cpi' in computed, "Missing 'cpi' in computed"
    
    def test_snapshot_regime_valid(self):
        """Regime should be one of valid values"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=30)
        data = response.json()
        regime = data.get('computed', {}).get('regime')
        valid_regimes = ['FLIGHT_TO_BTC', 'ALT_ROTATION', 'CAPITAL_EXIT', 'NEUTRAL']
        assert regime in valid_regimes, f"Invalid regime: {regime}"
    
    def test_snapshot_riskoff_prob_range(self):
        """RiskOff probability should be 0-1"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=30)
        data = response.json()
        riskoff = data.get('computed', {}).get('riskOffProb', -1)
        assert 0 <= riskoff <= 1, f"RiskOff prob {riskoff} out of range"
    
    def test_snapshot_macro_mult_range(self):
        """MacroMult should be in reasonable range (0.4-1.1)"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=30)
        data = response.json()
        macro_mult = data.get('computed', {}).get('macroMult', 0)
        assert 0.4 <= macro_mult <= 1.1, f"MacroMult {macro_mult} out of range"
    
    def test_snapshot_lmi_present(self):
        """LMI (Liquidity Migration Index) should be present"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=30)
        data = response.json()
        lmi = data.get('lmi', {})
        assert 'lmi' in lmi, "Missing 'lmi' value in lmi"
        assert 'state' in lmi, "Missing 'state' in lmi"
        assert lmi['state'] in ['INFLOW_TO_SAFETY', 'OUTFLOW_FROM_SAFETY', 'NEUTRAL']
    
    def test_snapshot_risk_split_present(self):
        """Risk decomposition should be present"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=30)
        data = response.json()
        risk_split = data.get('riskSplit', {})
        assert 'structural' in risk_split, "Missing 'structural' in riskSplit"
        assert 'tactical' in risk_split, "Missing 'tactical' in riskSplit"
        assert 'total' in risk_split, "Missing 'total' in riskSplit"


class TestMacroV2History:
    """Tests for /api/core/macro/history with LIVE data"""
    
    def test_history_returns_ok(self):
        """History endpoint returns ok=true"""
        response = requests.get(f"{BASE_URL}/api/core/macro/history?limit=30", timeout=60)
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
    
    def test_history_returns_30_points(self):
        """History should return requested number of points"""
        response = requests.get(f"{BASE_URL}/api/core/macro/history?limit=30", timeout=60)
        data = response.json()
        points = data.get('points', [])
        # Allow some tolerance (might be fewer if data is limited)
        assert len(points) >= 25, f"Expected ~30 points, got {len(points)}"
    
    def test_history_point_structure(self):
        """Each history point should have required fields"""
        response = requests.get(f"{BASE_URL}/api/core/macro/history?limit=30", timeout=60)
        data = response.json()
        points = data.get('points', [])
        
        if points:
            point = points[-1]  # Check latest point
            assert 't' in point, "Missing 't' (timestamp)"
            assert 'regime' in point, "Missing 'regime'"
            assert 'fearGreed' in point, "Missing 'fearGreed'"
            assert 'riskOffProb' in point, "Missing 'riskOffProb'"
            assert 'macroMult' in point, "Missing 'macroMult'"


class TestMacroV2Status:
    """Tests for /api/core/macro/status endpoint"""
    
    def test_status_returns_live(self):
        """Status should indicate live data source"""
        response = requests.get(f"{BASE_URL}/api/core/macro/status", timeout=15)
        assert response.status_code == 200
        data = response.json()
        assert data.get('dataSource') == 'live', f"Expected live, got {data.get('dataSource')}"
    
    def test_status_live_api_available(self):
        """Live API should be marked as available"""
        response = requests.get(f"{BASE_URL}/api/core/macro/status", timeout=15)
        data = response.json()
        assert data.get('liveApiAvailable') is True
    
    def test_status_cryptocompare_reachable(self):
        """CryptoCompare should be reachable"""
        response = requests.get(f"{BASE_URL}/api/core/macro/status", timeout=15)
        data = response.json()
        apis = data.get('apis', {})
        assert apis.get('cryptocompare') == 'reachable', f"CryptoCompare status: {apis.get('cryptocompare')}"


class TestMacroSync:
    """Tests for /api/core/macro-sync endpoint"""
    
    def test_macro_sync_returns_ok(self):
        """Macro sync endpoint returns ok=true"""
        response = requests.get(f"{BASE_URL}/api/core/macro-sync?symbol=BTCUSDT&tf=1h", timeout=60)
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
    
    def test_macro_sync_alignment_score_present(self):
        """Alignment score should be present"""
        response = requests.get(f"{BASE_URL}/api/core/macro-sync?symbol=BTCUSDT&tf=1h", timeout=60)
        data = response.json()
        assert 'alignmentScore' in data
        assert 0 <= data['alignmentScore'] <= 100
    
    def test_macro_sync_conflict_score_present(self):
        """Conflict score should be present"""
        response = requests.get(f"{BASE_URL}/api/core/macro-sync?symbol=BTCUSDT&tf=1h", timeout=60)
        data = response.json()
        assert 'conflictScore' in data
        assert 0 <= data['conflictScore'] <= 100
    
    def test_macro_sync_state_valid(self):
        """State should be ALIGNED or CONFLICTED"""
        response = requests.get(f"{BASE_URL}/api/core/macro-sync?symbol=BTCUSDT&tf=1h", timeout=60)
        data = response.json()
        assert data.get('state') in ['ALIGNED', 'CONFLICTED', 'PARTIAL']
    
    def test_macro_sync_core_details(self):
        """Core engine details should be present"""
        response = requests.get(f"{BASE_URL}/api/core/macro-sync?symbol=BTCUSDT&tf=1h", timeout=60)
        data = response.json()
        core = data.get('core', {})
        assert 'bias' in core
        assert 'regime' in core
    
    def test_macro_sync_macro_details(self):
        """Macro details should be present"""
        response = requests.get(f"{BASE_URL}/api/core/macro-sync?symbol=BTCUSDT&tf=1h", timeout=60)
        data = response.json()
        macro = data.get('macro', {})
        assert 'riskOffProb' in macro
        assert 'macroMult' in macro
        assert 'regime' in macro


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
