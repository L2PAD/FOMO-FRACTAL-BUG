"""
CEX Flow v2.1 Sprint A — Backend API Tests
============================================
Tests the enhanced v2.1 fields: drivers, offsetting_factors, indicators,
market_liquidity, exchange behavior labels, transfer impact labels,
pump setup drivers, and rotation fallback.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestCexContextV21Fields:
    """Test all v2.1 Sprint A backend API fields."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Skip if BASE_URL not set."""
        if not BASE_URL:
            pytest.skip("BASE_URL not configured")
    
    def test_api_returns_ok(self):
        """API returns ok=true for 30d window."""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=60)
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True

    def test_drivers_field_exists(self):
        """V2.1: drivers array is present and contains strings."""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=60)
        data = response.json()
        assert 'drivers' in data, "Missing drivers field"
        assert isinstance(data['drivers'], list), "drivers should be a list"
        # 30d should have at least one driver
        assert len(data['drivers']) >= 1, "Expected at least 1 driver for 30d data"
        for d in data['drivers']:
            assert isinstance(d, str), "Each driver should be a string"
    
    def test_offsetting_factors_field_exists(self):
        """V2.1: offsetting_factors array is present."""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=60)
        data = response.json()
        assert 'offsetting_factors' in data, "Missing offsetting_factors field"
        assert isinstance(data['offsetting_factors'], list), "offsetting_factors should be a list"
    
    def test_indicators_object_structure(self):
        """V2.1: indicators object contains sell_pressure, liquidity, confidence."""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=60)
        data = response.json()
        assert 'indicators' in data, "Missing indicators field"
        ind = data['indicators']
        assert isinstance(ind, dict), "indicators should be an object"
        
        # Check all 3 indicator gauges
        for key in ['sell_pressure', 'liquidity', 'confidence']:
            assert key in ind, f"Missing indicators.{key}"
            assert isinstance(ind[key], (int, float)), f"indicators.{key} should be numeric"
            assert 0 <= ind[key] <= 100, f"indicators.{key} should be 0-100 percentage"
    
    def test_market_liquidity_object_structure(self):
        """V2.1: market_liquidity object with buy_power, sell_supply, net_liquidity."""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=60)
        data = response.json()
        assert 'market_liquidity' in data, "Missing market_liquidity field"
        ml = data['market_liquidity']
        assert isinstance(ml, dict), "market_liquidity should be an object"
        
        required_keys = ['buy_power', 'buy_power_fmt', 'sell_supply', 'sell_supply_fmt', 
                        'net_liquidity', 'net_liquidity_fmt', 'bias']
        for key in required_keys:
            assert key in ml, f"Missing market_liquidity.{key}"
        
        # Verify bias is bullish or bearish
        assert ml['bias'] in ['bullish', 'bearish'], "market_liquidity.bias should be bullish/bearish"
    
    def test_top_exchanges_v21_fields(self):
        """V2.1: top_exchanges include market_share, dominant_direction, behavior_label."""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=60)
        data = response.json()
        assert 'top_exchanges' in data, "Missing top_exchanges field"
        exchanges = data['top_exchanges']
        assert isinstance(exchanges, list), "top_exchanges should be a list"
        
        if len(exchanges) > 0:
            ex = exchanges[0]
            # Check v2.1 behavior fields
            assert 'market_share' in ex, "Missing market_share in exchange"
            assert 'dominant_direction' in ex, "Missing dominant_direction in exchange"
            assert 'behavior_label' in ex, "Missing behavior_label in exchange"
            
            assert isinstance(ex['market_share'], (int, float)), "market_share should be numeric"
            assert ex['dominant_direction'] in ['Deposits dominant', 'Withdrawals dominant', 'Balanced'], \
                "Invalid dominant_direction value"
            assert ex['behavior_label'] in ['Distribution', 'Accumulation', 'Inventory Rebalance', 'Neutral'], \
                "Invalid behavior_label value"
    
    def test_largest_transfers_impact_label(self):
        """V2.1: largest_transfers include impact_label badge."""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=60)
        data = response.json()
        assert 'largest_transfers' in data, "Missing largest_transfers field"
        transfers = data['largest_transfers']
        
        if len(transfers) > 0:
            t = transfers[0]
            assert 'impact_label' in t, "Missing impact_label in transfer"
            valid_labels = ['BUY LIQUIDITY', 'SELL PRESSURE', 'ACCUMULATION', 'CAPITAL EXIT']
            assert t['impact_label'] in valid_labels, f"Invalid impact_label: {t['impact_label']}"
    
    def test_rotation_fallback_field_exists(self):
        """V2.1: rotation_fallback array is present (may be empty for 30d)."""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=60)
        data = response.json()
        assert 'rotation_fallback' in data, "Missing rotation_fallback field"
        assert isinstance(data['rotation_fallback'], list), "rotation_fallback should be a list"
    
    def test_pump_setups_drivers(self):
        """V2.1: pump_setups include drivers array for each token."""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=60)
        data = response.json()
        assert 'pump_setups' in data, "Missing pump_setups field"
        setups = data['pump_setups']
        
        if len(setups) > 0:
            s = setups[0]
            assert 'drivers' in s, "Missing drivers in pump_setup"
            assert isinstance(s['drivers'], list), "pump_setup.drivers should be a list"
            # Should have at least some drivers
            assert len(s['drivers']) >= 1, "Expected at least 1 driver in pump_setup"
    
    def test_exchange_pressure_standard_fields(self):
        """Verify exchange_pressure has deposits/withdrawals/net_flow."""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=60)
        data = response.json()
        assert 'exchange_pressure' in data, "Missing exchange_pressure field"
        ep = data['exchange_pressure']
        
        required_keys = ['deposits', 'deposits_fmt', 'withdrawals', 'withdrawals_fmt',
                        'net_flow', 'net_fmt', 'active_exchanges', 'total_transfers']
        for key in required_keys:
            assert key in ep, f"Missing exchange_pressure.{key}"


class TestCexContextWindows:
    """Test API with different time windows."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        if not BASE_URL:
            pytest.skip("BASE_URL not configured")
    
    def test_24h_window_returns_indicators(self):
        """24h window returns indicators (may have low values)."""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=24h", timeout=60)
        assert response.status_code == 200
        data = response.json()
        assert 'indicators' in data
        assert 'sell_pressure' in data['indicators']
    
    def test_7d_window_returns_market_liquidity(self):
        """7d window returns market_liquidity object."""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=7d", timeout=60)
        assert response.status_code == 200
        data = response.json()
        assert 'market_liquidity' in data
        assert 'buy_power' in data['market_liquidity']
    
    def test_30d_window_has_data(self):
        """30d window returns substantive data."""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=60)
        assert response.status_code == 200
        data = response.json()
        # 30d should have active exchanges
        assert data['exchange_pressure']['total_transfers'] > 1000, "Expected 30d to have many transfers"


class TestTokenIntelligenceRegression:
    """Regression test: Token Intelligence tab still loads."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        if not BASE_URL:
            pytest.skip("BASE_URL not configured")
    
    def test_intelligence_context_endpoint(self):
        """Token Intelligence API still works."""
        response = requests.get(f"{BASE_URL}/api/onchain/intelligence-context?chainId=1&window=30d", timeout=60)
        assert response.status_code == 200
        data = response.json()
        assert 'ok' in data or 'trading_decision' in data or 'tokens' in data
