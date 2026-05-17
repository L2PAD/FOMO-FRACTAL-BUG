"""
Macro V2 API Tests — Capital Flow Intelligence Layer
Tests /api/core/macro/snapshot and /api/core/macro/history endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

VALID_REGIMES = ['FLIGHT_TO_BTC', 'ALT_ROTATION', 'CAPITAL_EXIT', 'NEUTRAL']


class TestMacroV2Snapshot:
    """Tests for GET /api/core/macro/snapshot"""
    
    def test_snapshot_returns_ok(self):
        """Test: Snapshot endpoint returns ok=true"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get('ok') is True, f"Expected ok=true, got {data.get('ok')}"
    
    def test_snapshot_has_all_sections(self):
        """Test: Snapshot has raw, computed, capitalFlow, drivers, riskoffDrivers, impact"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=30)
        data = response.json()
        
        required_sections = ['raw', 'computed', 'capitalFlow', 'drivers', 'riskoffDrivers', 'impact']
        for section in required_sections:
            assert section in data, f"Missing section: {section}"
            assert data[section], f"Section {section} is empty or null"
    
    def test_computed_regime_is_valid(self):
        """Test: computed.regime is one of FLIGHT_TO_BTC, ALT_ROTATION, CAPITAL_EXIT, NEUTRAL"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=30)
        data = response.json()
        
        computed = data.get('computed', {})
        regime = computed.get('regime')
        assert regime in VALID_REGIMES, f"Invalid regime: {regime}. Expected one of {VALID_REGIMES}"
    
    def test_regime_probs_sum_close_to_one(self):
        """Test: computed.regimeProbs sums close to 1.0 (tolerance 0.01)"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=30)
        data = response.json()
        
        computed = data.get('computed', {})
        probs = computed.get('regimeProbs', {})
        
        # Should have 4 regimes
        assert len(probs) == 4, f"Expected 4 regime probs, got {len(probs)}"
        
        # Sum should be close to 1.0
        prob_sum = sum(probs.values())
        assert 0.99 <= prob_sum <= 1.01, f"Regime probs sum to {prob_sum}, expected ~1.0"
    
    def test_riskoff_prob_range(self):
        """Test: computed.riskOffProb is between 0 and 1"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=30)
        data = response.json()
        
        computed = data.get('computed', {})
        riskoff = computed.get('riskOffProb')
        
        assert riskoff is not None, "riskOffProb is missing"
        assert 0.0 <= riskoff <= 1.0, f"riskOffProb {riskoff} outside range [0,1]"
    
    def test_macro_mult_range(self):
        """Test: computed.macroMult is between 0.40 and 1.05"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=30)
        data = response.json()
        
        computed = data.get('computed', {})
        mult = computed.get('macroMult')
        
        assert mult is not None, "macroMult is missing"
        assert 0.40 <= mult <= 1.05, f"macroMult {mult} outside range [0.40, 1.05]"
    
    def test_capital_flow_structure(self):
        """Test: capitalFlow has btc, alt, stable each with dominance, delta7d, delta30d, pressure"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=30)
        data = response.json()
        
        cf = data.get('capitalFlow', {})
        required_keys = ['btc', 'alt', 'stable']
        required_fields = ['dominance', 'delta7d', 'delta30d', 'pressure']
        
        for key in required_keys:
            assert key in cf, f"Missing capitalFlow.{key}"
            for field in required_fields:
                assert field in cf[key], f"Missing capitalFlow.{key}.{field}"
    
    def test_drivers_structure(self):
        """Test: drivers has btc_dom_delta, stable_dom_delta, btc_momentum, alt_relative_strength, fear_greed_impact"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=30)
        data = response.json()
        
        drivers = data.get('drivers', {})
        required_fields = ['btc_dom_delta', 'stable_dom_delta', 'btc_momentum', 
                          'alt_relative_strength', 'fear_greed_impact']
        
        for field in required_fields:
            assert field in drivers, f"Missing drivers.{field}"
            assert isinstance(drivers[field], (int, float)), f"drivers.{field} should be numeric"
    
    def test_riskoff_drivers_structure(self):
        """Test: riskoffDrivers has stable_dom, fear_greed, volatility, btc_drawdown"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=30)
        data = response.json()
        
        riskoff_drivers = data.get('riskoffDrivers', {})
        required_fields = ['stable_dom', 'fear_greed', 'volatility', 'btc_drawdown']
        
        for field in required_fields:
            assert field in riskoff_drivers, f"Missing riskoffDrivers.{field}"
    
    def test_impact_structure(self):
        """Test: impact has aggressionScale, riskSurfaceImpact, strongActionsBlocked, altExposureReduced"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=30)
        data = response.json()
        
        impact = data.get('impact', {})
        required_fields = ['aggressionScale', 'riskSurfaceImpact', 'strongActionsBlocked', 'altExposureReduced']
        
        for field in required_fields:
            assert field in impact, f"Missing impact.{field}"


class TestMacroV2History:
    """Tests for GET /api/core/macro/history"""
    
    def test_history_returns_ok(self):
        """Test: History endpoint returns ok=true with array of points"""
        response = requests.get(f"{BASE_URL}/api/core/macro/history?limit=30", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get('ok') is True, f"Expected ok=true, got {data.get('ok')}"
        assert 'points' in data, "Missing 'points' in response"
        assert isinstance(data['points'], list), "points should be a list"
    
    def test_history_points_have_required_fields(self):
        """Test: history points have t, cpi, riskOffProb, macroMult, regime, regimeProbs, fearGreed"""
        response = requests.get(f"{BASE_URL}/api/core/macro/history?limit=30", timeout=60)
        data = response.json()
        points = data.get('points', [])
        
        assert len(points) > 0, "No history points returned"
        
        required_fields = ['t', 'cpi', 'riskOffProb', 'macroMult', 'regime', 'regimeProbs', 'fearGreed']
        
        # Check first and last point
        for point in [points[0], points[-1]]:
            for field in required_fields:
                assert field in point, f"Missing field: {field} in history point"
    
    def test_history_regime_values_are_valid(self):
        """Test: All regime values in history are valid"""
        response = requests.get(f"{BASE_URL}/api/core/macro/history?limit=30", timeout=60)
        data = response.json()
        points = data.get('points', [])
        
        for point in points:
            regime = point.get('regime')
            assert regime in VALID_REGIMES, f"Invalid regime in history: {regime}"
    
    def test_history_respects_limit(self):
        """Test: Limit parameter is respected (with tolerance for available data)"""
        response = requests.get(f"{BASE_URL}/api/core/macro/history?limit=30", timeout=60)
        data = response.json()
        points = data.get('points', [])
        
        # Should have some points (may be less if not enough data)
        assert len(points) > 0, "History should return at least some points"
        assert len(points) <= 30, f"Too many points returned: {len(points)}, expected <= 30"


class TestMacroV2DataQuality:
    """Additional data quality tests"""
    
    def test_raw_data_fields(self):
        """Test: raw section contains expected market data"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=30)
        data = response.json()
        
        raw = data.get('raw', {})
        required_fields = ['fearGreed', 'btcDom', 'stableDom', 'altDom', 'btcPrice', 'altIndex']
        
        for field in required_fields:
            assert field in raw, f"Missing raw.{field}"
        
        # Fear & Greed should be 0-100
        fg = raw.get('fearGreed', -1)
        assert 0 <= fg <= 100, f"fearGreed {fg} outside expected range [0,100]"
        
        # Dominances should sum to ~100
        btc_dom = raw.get('btcDom', 0)
        stable_dom = raw.get('stableDom', 0)
        alt_dom = raw.get('altDom', 0)
        total_dom = btc_dom + stable_dom + alt_dom
        assert 95 <= total_dom <= 105, f"Dominances sum to {total_dom}, expected ~100"
    
    def test_capital_flow_pressure_values(self):
        """Test: Pressure fields have expected values"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=30)
        data = response.json()
        
        cf = data.get('capitalFlow', {})
        
        btc_pressure = cf.get('btc', {}).get('pressure')
        assert btc_pressure in ['IN', 'OUT', 'FLAT'], f"Invalid BTC pressure: {btc_pressure}"
        
        alt_pressure = cf.get('alt', {}).get('pressure')
        assert alt_pressure in ['OUTPERFORMING', 'UNDERPERFORMING', 'INLINE'], f"Invalid ALT pressure: {alt_pressure}"
        
        stable_pressure = cf.get('stable', {}).get('pressure')
        assert stable_pressure in ['RISK_SHELTER', 'DEPLOYING', 'FLAT'], f"Invalid STABLE pressure: {stable_pressure}"
    
    def test_data_source_field(self):
        """Test: dataSource field exists (should be 'synthetic' or 'live')"""
        response = requests.get(f"{BASE_URL}/api/core/macro/snapshot", timeout=30)
        data = response.json()
        
        data_source = data.get('dataSource')
        assert data_source in ['synthetic', 'live'], f"Invalid dataSource: {data_source}"
