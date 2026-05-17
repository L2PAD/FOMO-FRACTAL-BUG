"""
Test suite for /api/market/symbols endpoint and related functionality
Tests the dynamic symbol search feature for the financial prediction app
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com')

class TestSymbolsAPI:
    """Tests for GET /api/market/symbols endpoint"""
    
    def test_symbols_endpoint_returns_ok(self):
        """Test that symbols endpoint returns ok: true"""
        response = requests.get(f"{BASE_URL}/api/market/symbols")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') == True, "Expected ok: true"
        print(f"SUCCESS: Symbols endpoint returned ok: true")
    
    def test_symbols_returns_count(self):
        """Test that symbols endpoint returns symbol count"""
        response = requests.get(f"{BASE_URL}/api/market/symbols")
        data = response.json()
        
        assert 'count' in data, "Expected 'count' field in response"
        assert data['count'] > 0, "Expected at least one symbol"
        print(f"SUCCESS: Symbols endpoint returned {data['count']} symbols")
    
    def test_symbols_returns_array(self):
        """Test that symbols endpoint returns symbols array"""
        response = requests.get(f"{BASE_URL}/api/market/symbols")
        data = response.json()
        
        assert 'symbols' in data, "Expected 'symbols' field in response"
        assert isinstance(data['symbols'], list), "Expected symbols to be an array"
        assert len(data['symbols']) > 0, "Expected at least one symbol in array"
        print(f"SUCCESS: Symbols array contains {len(data['symbols'])} items")
    
    def test_symbol_structure(self):
        """Test that each symbol has required fields"""
        response = requests.get(f"{BASE_URL}/api/market/symbols")
        data = response.json()
        
        required_fields = ['symbol', 'base', 'quote', 'name', 'logo']
        
        for sym in data['symbols']:
            for field in required_fields:
                assert field in sym, f"Missing field '{field}' in symbol: {sym}"
        
        print(f"SUCCESS: All symbols have required fields: {required_fields}")
    
    def test_symbol_normalization(self):
        """Test that symbols are in normalized format (XXXUSDT)"""
        response = requests.get(f"{BASE_URL}/api/market/symbols")
        data = response.json()
        
        for sym in data['symbols']:
            # Symbol should end with USDT
            assert sym['symbol'].endswith('USDT'), f"Symbol should end with USDT: {sym['symbol']}"
            # Quote should be USDT
            assert sym['quote'] == 'USDT', f"Quote should be USDT: {sym['quote']}"
            # Base should not be empty
            assert len(sym['base']) > 0, f"Base should not be empty"
        
        print(f"SUCCESS: All symbols are normalized to XXXUSDT format")
    
    def test_priority_assets_first(self):
        """Test that priority assets (BTC, ETH, SOL, BNB) come first"""
        response = requests.get(f"{BASE_URL}/api/market/symbols")
        data = response.json()
        
        symbols = data['symbols']
        priority_assets = ['BTC', 'ETH', 'SOL', 'BNB']
        
        # Check first 4 symbols are priority assets
        first_four = [s['base'] for s in symbols[:4]]
        assert first_four == priority_assets, f"Expected priority order {priority_assets}, got {first_four}"
        
        print(f"SUCCESS: Priority assets appear first: {first_four}")
    
    def test_core_assets_present(self):
        """Test that core trading assets are present"""
        response = requests.get(f"{BASE_URL}/api/market/symbols")
        data = response.json()
        
        symbols = {s['base'] for s in data['symbols']}
        core_assets = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA']
        
        for asset in core_assets:
            assert asset in symbols, f"Core asset '{asset}' should be present"
        
        print(f"SUCCESS: All core assets present: {core_assets}")
    
    def test_response_timing(self):
        """Test that symbols endpoint responds quickly (< 500ms)"""
        response = requests.get(f"{BASE_URL}/api/market/symbols")
        data = response.json()
        
        assert '__timings' in data, "Expected timing info in response"
        total_ms = data['__timings'].get('totalMs', 0)
        
        # Should be fast (< 500ms)
        assert total_ms < 500, f"Response too slow: {total_ms}ms"
        print(f"SUCCESS: Response time acceptable: {total_ms}ms")


class TestCandlesAPI:
    """Tests for /api/market/candles endpoint"""
    
    def test_candles_endpoint_returns_ok(self):
        """Test that candles endpoint returns data for BTC"""
        response = requests.get(f"{BASE_URL}/api/market/candles?symbol=BTCUSDT&range=7d")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') == True, "Expected ok: true"
        print(f"SUCCESS: Candles endpoint returned ok: true")
    
    def test_candles_returns_array(self):
        """Test that candles endpoint returns candles array"""
        response = requests.get(f"{BASE_URL}/api/market/candles?symbol=BTCUSDT&range=7d")
        data = response.json()
        
        assert 'candles' in data, "Expected 'candles' field in response"
        assert isinstance(data['candles'], list), "Expected candles to be an array"
        assert len(data['candles']) > 0, "Expected at least one candle"
        print(f"SUCCESS: Candles array contains {len(data['candles'])} items")
    
    def test_candle_structure(self):
        """Test that each candle has OHLC structure"""
        response = requests.get(f"{BASE_URL}/api/market/candles?symbol=BTCUSDT&range=7d")
        data = response.json()
        
        required_fields = ['time', 'open', 'high', 'low', 'close']
        
        for candle in data['candles'][:5]:  # Check first 5
            for field in required_fields:
                assert field in candle, f"Missing field '{field}' in candle"
        
        print(f"SUCCESS: Candles have OHLC structure")
    
    def test_candles_for_sol(self):
        """Test candles for SOL (different symbol)"""
        response = requests.get(f"{BASE_URL}/api/market/candles?symbol=SOLUSDT&range=7d")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') == True, "Expected ok: true for SOL"
        assert len(data.get('candles', [])) > 0, "Expected candles for SOL"
        print(f"SUCCESS: Candles endpoint works for SOL")
    
    def test_symbol_normalization_short_form(self):
        """Test that short form (BTC) is normalized to full form (BTCUSDT)"""
        response = requests.get(f"{BASE_URL}/api/market/candles?symbol=BTC&range=7d")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Should work even with short symbol
        assert data.get('ok') == True or len(data.get('candles', [])) > 0, \
            "Expected candles for short-form BTC"
        print(f"SUCCESS: Short-form symbol normalization works")


class TestV4PredictionEndpoint:
    """Tests for the V4 prediction endpoint"""
    
    def test_v4_endpoint_returns_ok(self):
        """Test that v4 endpoint returns ok: true"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v4?asset=BTC&range=7d&horizon=1D"
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') == True, "Expected ok: true"
        print(f"SUCCESS: V4 endpoint returned ok: true")
    
    def test_v4_returns_verdict(self):
        """Test that v4 endpoint returns verdict object"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v4?asset=BTC&range=7d&horizon=1D"
        )
        data = response.json()
        
        assert 'verdict' in data, "Expected 'verdict' field in response"
        verdict = data['verdict']
        
        # Check verdict structure
        assert 'action' in verdict, "Verdict should have 'action'"
        assert 'confidence' in verdict, "Verdict should have 'confidence'"
        print(f"SUCCESS: V4 endpoint returns verdict with action={verdict.get('action')}")
    
    def test_v4_returns_explain(self):
        """Test that v4 endpoint returns explain object (Block A)"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v4?asset=BTC&range=7d&horizon=1D"
        )
        data = response.json()
        
        assert 'explain' in data, "Expected 'explain' field in response"
        explain = data['explain']
        
        # Check explain structure
        assert 'horizon' in explain, "Explain should have 'horizon'"
        assert 'final' in explain, "Explain should have 'final'"
        assert 'drivers' in explain, "Explain should have 'drivers'"
        print(f"SUCCESS: V4 endpoint returns explain object for Block A")
    
    def test_v4_different_horizons(self):
        """Test that v4 endpoint works for different horizons"""
        horizons = ['1D', '7D', '30D']
        
        for horizon in horizons:
            response = requests.get(
                f"{BASE_URL}/api/market/chart/price-vs-expectation-v4?asset=BTC&range=7d&horizon={horizon}"
            )
            assert response.status_code == 200, f"Expected 200 for horizon {horizon}"
            
            data = response.json()
            assert data.get('ok') == True, f"Expected ok: true for horizon {horizon}"
        
        print(f"SUCCESS: V4 endpoint works for all horizons: {horizons}")
    
    def test_v4_different_assets(self):
        """Test that v4 endpoint works for different assets"""
        assets = ['BTC', 'ETH', 'SOL']
        
        for asset in assets:
            response = requests.get(
                f"{BASE_URL}/api/market/chart/price-vs-expectation-v4?asset={asset}&range=7d&horizon=1D"
            )
            assert response.status_code == 200, f"Expected 200 for asset {asset}"
            
            data = response.json()
            assert data.get('ok') == True, f"Expected ok: true for asset {asset}"
        
        print(f"SUCCESS: V4 endpoint works for all assets: {assets}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
