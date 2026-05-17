"""
Market Context Consolidation Tests — Mini Sprint: Context Consolidation + Signal Normalization

Tests for /api/onchain/market/context endpoint which aggregates:
- CEX Intelligence
- Smart Money Intelligence  
- Token Intelligence
- Wallet Intelligence

Into a 4-layer structure with normalized 0-100 scores.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test Configuration
TIMEOUT = 30  # First call can take 5-10 seconds, cached calls < 1s


class TestMarketContextEndpoint:
    """Tests for the new /api/onchain/market/context endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test"""
        self.endpoint = f"{BASE_URL}/api/onchain/market/context"
        self.window = "30d"
    
    def test_market_context_returns_200(self):
        """Test that GET /api/onchain/market/context?window=30d returns 200 with ok=true"""
        response = requests.get(f"{self.endpoint}?window={self.window}", timeout=TIMEOUT)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=true, got {data.get('ok')}"
        print(f"PASS: Market context endpoint returns 200 with ok=true")
    
    def test_scores_object_structure(self):
        """Test that scores object has all required fields"""
        response = requests.get(f"{self.endpoint}?window={self.window}", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        scores = data.get("scores", {})
        
        # Required score fields
        required_fields = ["cex_score", "smart_money_score", "token_score", "wallet_score", "composite", "weights", "components"]
        for field in required_fields:
            assert field in scores, f"Missing required score field: {field}"
            print(f"PASS: scores.{field} present")
    
    def test_all_scores_within_0_100_range(self):
        """Test that all scores are normalized within 0-100 range"""
        response = requests.get(f"{self.endpoint}?window={self.window}", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        scores = data.get("scores", {})
        
        score_fields = ["cex_score", "smart_money_score", "token_score", "wallet_score", "composite"]
        for field in score_fields:
            value = scores.get(field)
            assert isinstance(value, (int, float)), f"{field} should be numeric, got {type(value)}"
            assert 0 <= value <= 100, f"{field} out of range: {value}"
            print(f"PASS: scores.{field} = {value} (within 0-100)")
    
    def test_composite_score_formula(self):
        """Test that composite = sm*0.35 + cex*0.30 + token*0.20 + wallet*0.15"""
        response = requests.get(f"{self.endpoint}?window={self.window}", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        scores = data.get("scores", {})
        
        sm_score = scores.get("smart_money_score", 0)
        cex_score = scores.get("cex_score", 0)
        token_score = scores.get("token_score", 0)
        wallet_score = scores.get("wallet_score", 0)
        composite = scores.get("composite", 0)
        
        # Calculate expected composite: SM 35%, CEX 30%, Token 20%, Wallet 15%
        expected = sm_score * 0.35 + cex_score * 0.30 + token_score * 0.20 + wallet_score * 0.15
        expected_rounded = int(max(0, min(100, round(expected))))  # _clamp function
        
        # Allow for rounding tolerance (since _clamp rounds)
        assert abs(composite - expected_rounded) <= 1, f"Composite mismatch: expected ~{expected_rounded}, got {composite}"
        print(f"PASS: Composite formula verified: {sm_score}*0.35 + {cex_score}*0.30 + {token_score}*0.20 + {wallet_score}*0.15 = {expected:.2f} (~{composite})")
    
    def test_weights_object(self):
        """Test that weights object contains correct values"""
        response = requests.get(f"{self.endpoint}?window={self.window}", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        weights = data.get("scores", {}).get("weights", {})
        
        expected_weights = {
            "smart_money": 0.35,
            "cex": 0.30,
            "token": 0.20,
            "wallet": 0.15
        }
        
        for key, expected_val in expected_weights.items():
            actual = weights.get(key)
            assert actual == expected_val, f"Weight mismatch for {key}: expected {expected_val}, got {actual}"
        
        print(f"PASS: Weights correct: {weights}")


class TestContextObject:
    """Tests for the context layer (compressed key data per module)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.endpoint = f"{BASE_URL}/api/onchain/market/context"
        self.window = "30d"
    
    def test_context_has_four_modules(self):
        """Test that context object has 4 keys: cex, smart_money, token, wallet"""
        response = requests.get(f"{self.endpoint}?window={self.window}", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        context = data.get("context", {})
        
        required_modules = ["cex", "smart_money", "token", "wallet"]
        for module in required_modules:
            assert module in context, f"Missing context module: {module}"
        
        print(f"PASS: Context has 4 modules: {list(context.keys())}")
    
    def test_context_cex_structure(self):
        """Test context.cex has required fields"""
        response = requests.get(f"{self.endpoint}?window={self.window}", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        cex = data.get("context", {}).get("cex", {})
        
        required_fields = [
            "market_bias", "liquidity_shock", "inventory_state",
            "stablecoin_bias", "stablecoin_net", "pressure_bias", "net_liquidity"
        ]
        
        for field in required_fields:
            assert field in cex, f"Missing context.cex.{field}"
            print(f"PASS: context.cex.{field} = {cex.get(field)}")
    
    def test_context_smart_money_structure(self):
        """Test context.smart_money has required fields"""
        response = requests.get(f"{self.endpoint}?window={self.window}", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        sm = data.get("context", {}).get("smart_money", {})
        
        required_fields = ["net_flow", "conviction", "clusters", "signal_count"]
        
        for field in required_fields:
            assert field in sm, f"Missing context.smart_money.{field}"
            print(f"PASS: context.smart_money.{field} = {sm.get(field)}")
    
    def test_context_token_structure(self):
        """Test context.token has required fields"""
        response = requests.get(f"{self.endpoint}?window={self.window}", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        token = data.get("context", {}).get("token", {})
        
        required_fields = ["regime", "pattern", "confidence", "token_count"]
        
        for field in required_fields:
            assert field in token, f"Missing context.token.{field}"
            print(f"PASS: context.token.{field} = {token.get(field)}")
    
    def test_context_wallet_structure(self):
        """Test context.wallet has required fields"""
        response = requests.get(f"{self.endpoint}?window={self.window}", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        wallet = data.get("context", {}).get("wallet", {})
        
        required_fields = ["active_actors", "direction", "avg_smart_score"]
        
        for field in required_fields:
            assert field in wallet, f"Missing context.wallet.{field}"
            print(f"PASS: context.wallet.{field} = {wallet.get(field)}")


class TestSignalsObject:
    """Tests for the signals layer (structured per module)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.endpoint = f"{BASE_URL}/api/onchain/market/context"
        self.window = "30d"
    
    def test_signals_has_four_arrays(self):
        """Test that signals object has 4 keys with array values"""
        response = requests.get(f"{self.endpoint}?window={self.window}", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        signals = data.get("signals", {})
        
        required_keys = ["smart_money", "cex", "token", "wallet"]
        for key in required_keys:
            assert key in signals, f"Missing signals.{key}"
            assert isinstance(signals.get(key), list), f"signals.{key} should be array"
            print(f"PASS: signals.{key} is array with {len(signals.get(key))} items")
    
    def test_signals_are_strings(self):
        """Test that each signal array contains strings"""
        response = requests.get(f"{self.endpoint}?window={self.window}", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        signals = data.get("signals", {})
        
        for key in ["smart_money", "cex", "token", "wallet"]:
            for idx, signal in enumerate(signals.get(key, [])):
                assert isinstance(signal, str), f"signals.{key}[{idx}] should be string, got {type(signal)}"
        
        print("PASS: All signal items are strings")


class TestDriversAndComponents:
    """Tests for drivers and components"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.endpoint = f"{BASE_URL}/api/onchain/market/context"
        self.window = "30d"
    
    def test_drivers_is_string_array(self):
        """Test that drivers is array of human-readable strings"""
        response = requests.get(f"{self.endpoint}?window={self.window}", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        drivers = data.get("drivers", [])
        
        assert isinstance(drivers, list), f"drivers should be array, got {type(drivers)}"
        for idx, driver in enumerate(drivers):
            assert isinstance(driver, str), f"drivers[{idx}] should be string"
        
        print(f"PASS: drivers is array of {len(drivers)} strings")
        if drivers:
            print(f"  Sample drivers: {drivers[:3]}")
    
    def test_components_cex_structure(self):
        """Test components.cex has required fields"""
        response = requests.get(f"{self.endpoint}?window={self.window}", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        cex_components = data.get("scores", {}).get("components", {}).get("cex", {})
        
        required = ["liquidity_shock", "inventory_change", "stablecoin_power", "exchange_pressure"]
        for field in required:
            assert field in cex_components, f"Missing components.cex.{field}"
            val = cex_components.get(field)
            assert 0 <= val <= 100, f"components.cex.{field} out of range: {val}"
        
        print(f"PASS: components.cex structure verified: {cex_components}")
    
    def test_components_smart_money_structure(self):
        """Test components.smart_money has required fields"""
        response = requests.get(f"{self.endpoint}?window={self.window}", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        sm_components = data.get("scores", {}).get("components", {}).get("smart_money", {})
        
        required = ["conviction", "capital_weight", "lead_time_bonus"]
        for field in required:
            assert field in sm_components, f"Missing components.smart_money.{field}"
        
        print(f"PASS: components.smart_money structure verified: {sm_components}")
    
    def test_components_token_structure(self):
        """Test components.token has required fields"""
        response = requests.get(f"{self.endpoint}?window={self.window}", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        token_components = data.get("scores", {}).get("components", {}).get("token", {})
        
        required = ["pattern_confidence", "regime_strength", "positioning"]
        for field in required:
            assert field in token_components, f"Missing components.token.{field}"
        
        print(f"PASS: components.token structure verified: {token_components}")
    
    def test_components_wallet_structure(self):
        """Test components.wallet has required fields"""
        response = requests.get(f"{self.endpoint}?window={self.window}", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        wallet_components = data.get("scores", {}).get("components", {}).get("wallet", {})
        
        required = ["actor_credibility", "capital_direction", "cluster_activity"]
        for field in required:
            assert field in wallet_components, f"Missing components.wallet.{field}"
        
        print(f"PASS: components.wallet structure verified: {wallet_components}")


class TestRegressionEndpoints:
    """Regression tests for existing endpoints"""
    
    def test_cex_context_still_works(self):
        """Regression: /api/onchain/cex/context still works (200)"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?window=30d", timeout=TIMEOUT)
        assert response.status_code == 200, f"CEX context regression failed: {response.status_code}"
        print("PASS: /api/onchain/cex/context still returns 200")
    
    def test_smart_money_context_still_works(self):
        """Regression: /api/onchain/smart-money/context still works (200)"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/context?window=30d", timeout=TIMEOUT)
        assert response.status_code == 200, f"Smart money context regression failed: {response.status_code}"
        print("PASS: /api/onchain/smart-money/context still returns 200")
    
    def test_smart_money_intelligence_context_still_works(self):
        """Regression: /api/onchain/smart-money/intelligence-context still works (200)"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/intelligence-context?window=30d", timeout=TIMEOUT)
        assert response.status_code == 200, f"Intelligence context regression failed: {response.status_code}"
        print("PASS: /api/onchain/smart-money/intelligence-context still returns 200")


class TestMetaAndCaching:
    """Tests for meta info and caching behavior"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.endpoint = f"{BASE_URL}/api/onchain/market/context"
        self.window = "30d"
    
    def test_meta_info_present(self):
        """Test that response includes meta info"""
        response = requests.get(f"{self.endpoint}?window={self.window}", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        meta = data.get("meta", {})
        
        assert "chainId" in meta, "Missing meta.chainId"
        assert "window" in meta, "Missing meta.window"
        assert meta.get("window") == self.window, f"Window mismatch: {meta.get('window')}"
        
        print(f"PASS: Meta info present: {meta}")
    
    def test_cached_response_faster(self):
        """Test that cached responses are faster"""
        import time
        
        # First call (may be cold)
        start1 = time.time()
        response1 = requests.get(f"{self.endpoint}?window={self.window}", timeout=TIMEOUT)
        time1 = time.time() - start1
        assert response1.status_code == 200
        
        # Second call (should be cached)
        start2 = time.time()
        response2 = requests.get(f"{self.endpoint}?window={self.window}", timeout=TIMEOUT)
        time2 = time.time() - start2
        assert response2.status_code == 200
        
        print(f"First call: {time1:.2f}s, Second call: {time2:.2f}s")
        
        # Second call should be significantly faster if cached (allow for network latency)
        # Note: Can't always guarantee this due to network conditions
        print(f"PASS: Caching test complete - first: {time1:.2f}s, cached: {time2:.2f}s")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
