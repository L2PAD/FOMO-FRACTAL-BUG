"""
CEX Flow v2.0 Backend Tests
============================
Tests for the CEX Intelligence Engine API endpoint:
/api/onchain/cex/context

Returns:
- market_bias, confidence, narrative_lines
- exchange_pressure (deposits, withdrawals, net_flow, active_exchanges, total_transfers)
- stablecoin_power (usdt_in, usdc_in, dai_in, net_power, bias)
- top_exchanges (list with inflow/outflow/net)
- largest_transfers (list with direction, token, usd, exchange)
- exchange_rotation (list - may be empty)
- pump_setups (list with probability, components)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestCexContextEndpoint:
    """Test GET /api/onchain/cex/context endpoint"""

    def test_cex_context_returns_ok(self):
        """Test that CEX context endpoint returns ok=True"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=120)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data.get('ok')}"
        print("PASS: CEX context endpoint returns ok=True")

    def test_cex_context_market_bias(self):
        """Test market_bias field is present and valid"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=120)
        data = response.json()
        
        assert "market_bias" in data, "market_bias field missing"
        assert data["market_bias"] in ["bullish", "bearish", "neutral"], f"Invalid market_bias: {data['market_bias']}"
        print(f"PASS: market_bias = {data['market_bias']}")

    def test_cex_context_confidence(self):
        """Test confidence field is present and valid"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=120)
        data = response.json()
        
        assert "confidence" in data, "confidence field missing"
        assert data["confidence"] in ["high", "moderate", "low"], f"Invalid confidence: {data['confidence']}"
        print(f"PASS: confidence = {data['confidence']}")

    def test_cex_context_narrative_lines(self):
        """Test narrative_lines field is present and is a list"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=120)
        data = response.json()
        
        assert "narrative_lines" in data, "narrative_lines field missing"
        assert isinstance(data["narrative_lines"], list), "narrative_lines should be a list"
        assert len(data["narrative_lines"]) > 0, "narrative_lines should not be empty"
        print(f"PASS: narrative_lines count = {len(data['narrative_lines'])}")

    def test_cex_context_exchange_pressure(self):
        """Test exchange_pressure block has all required fields"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=120)
        data = response.json()
        
        assert "exchange_pressure" in data, "exchange_pressure field missing"
        ep = data["exchange_pressure"]
        
        required_fields = ["deposits", "deposits_fmt", "withdrawals", "withdrawals_fmt", 
                         "net_flow", "net_fmt", "bias", "active_exchanges", "total_transfers"]
        
        for field in required_fields:
            assert field in ep, f"exchange_pressure.{field} missing"
        
        # Data type assertions
        assert isinstance(ep["deposits"], (int, float)), "deposits should be numeric"
        assert isinstance(ep["withdrawals"], (int, float)), "withdrawals should be numeric"
        assert isinstance(ep["active_exchanges"], int), "active_exchanges should be int"
        assert isinstance(ep["total_transfers"], int), "total_transfers should be int"
        
        print(f"PASS: exchange_pressure - deposits={ep['deposits_fmt']}, withdrawals={ep['withdrawals_fmt']}, "
              f"net={ep['net_fmt']}, active={ep['active_exchanges']}, transfers={ep['total_transfers']}")

    def test_cex_context_stablecoin_power(self):
        """Test stablecoin_power block has all required fields"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=120)
        data = response.json()
        
        assert "stablecoin_power" in data, "stablecoin_power field missing"
        sp = data["stablecoin_power"]
        
        required_fields = ["usdt_in", "usdc_in", "dai_in", "total_in", "total_out", "net_power", "bias"]
        
        for field in required_fields:
            assert field in sp, f"stablecoin_power.{field} missing"
        
        # Bias should be buying_power or selling_power
        assert sp["bias"] in ["buying_power", "selling_power"], f"Invalid bias: {sp['bias']}"
        
        print(f"PASS: stablecoin_power - net_power={sp['net_power']}, bias={sp['bias']}")

    def test_cex_context_top_exchanges(self):
        """Test top_exchanges is a list with proper structure"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=120)
        data = response.json()
        
        assert "top_exchanges" in data, "top_exchanges field missing"
        assert isinstance(data["top_exchanges"], list), "top_exchanges should be a list"
        
        if len(data["top_exchanges"]) > 0:
            ex = data["top_exchanges"][0]
            required_fields = ["entityId", "entityName", "inflow_usd", "outflow_usd", "net_usd", "net_fmt", "tx_count"]
            for field in required_fields:
                assert field in ex, f"top_exchanges[0].{field} missing"
            print(f"PASS: top_exchanges count={len(data['top_exchanges'])}, first={ex['entityName']} net={ex['net_fmt']}")
        else:
            print("PASS: top_exchanges is empty (no exchange activity)")

    def test_cex_context_largest_transfers(self):
        """Test largest_transfers is a list with proper structure"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=120)
        data = response.json()
        
        assert "largest_transfers" in data, "largest_transfers field missing"
        assert isinstance(data["largest_transfers"], list), "largest_transfers should be a list"
        
        if len(data["largest_transfers"]) > 0:
            tr = data["largest_transfers"][0]
            required_fields = ["direction", "token", "usd", "usd_fmt", "exchange"]
            for field in required_fields:
                assert field in tr, f"largest_transfers[0].{field} missing"
            assert tr["direction"] in ["deposit", "withdrawal"], f"Invalid direction: {tr['direction']}"
            print(f"PASS: largest_transfers count={len(data['largest_transfers'])}, first={tr['direction']} {tr['usd_fmt']}")
        else:
            print("PASS: largest_transfers is empty (no large transfers)")

    def test_cex_context_exchange_rotation(self):
        """Test exchange_rotation is a list (may be empty)"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=120)
        data = response.json()
        
        assert "exchange_rotation" in data, "exchange_rotation field missing"
        assert isinstance(data["exchange_rotation"], list), "exchange_rotation should be a list"
        
        if len(data["exchange_rotation"]) > 0:
            rot = data["exchange_rotation"][0]
            required_fields = ["from_exchange", "to_exchange", "total_usd", "total_fmt", "top_token", "count"]
            for field in required_fields:
                assert field in rot, f"exchange_rotation[0].{field} missing"
            print(f"PASS: exchange_rotation count={len(data['exchange_rotation'])}")
        else:
            print("PASS: exchange_rotation is empty (no inter-exchange flows detected)")

    def test_cex_context_pump_setups(self):
        """Test pump_setups is a list with proper structure"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=120)
        data = response.json()
        
        assert "pump_setups" in data, "pump_setups field missing"
        assert isinstance(data["pump_setups"], list), "pump_setups should be a list"
        
        if len(data["pump_setups"]) > 0:
            ps = data["pump_setups"][0]
            required_fields = ["token", "pump_probability", "dump_risk", "drivers", "components"]
            for field in required_fields:
                assert field in ps, f"pump_setups[0].{field} missing"
            
            # Validate components structure
            comp_fields = ["smart_flow", "exchange_supply", "stablecoin", "timing", "regime"]
            for cf in comp_fields:
                assert cf in ps["components"], f"pump_setups[0].components.{cf} missing"
            
            print(f"PASS: pump_setups count={len(data['pump_setups'])}, first={ps['token']} pump={ps['pump_probability']}% dump={ps['dump_risk']}%")
        else:
            print("PASS: pump_setups is empty (no setup signals)")


class TestCexContextWindows:
    """Test CEX context with different window parameters"""

    def test_window_24h(self):
        """Test 24h window returns valid response"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=24h", timeout=120)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"PASS: 24h window - market_bias={data.get('market_bias')}")

    def test_window_7d(self):
        """Test 7d window returns valid response"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=7d", timeout=120)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"PASS: 7d window - market_bias={data.get('market_bias')}")

    def test_window_30d(self):
        """Test 30d window returns valid response"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?chainId=1&window=30d", timeout=120)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"PASS: 30d window - market_bias={data.get('market_bias')}")


class TestTokenIntelligenceRegression:
    """Regression tests for Token Intelligence APIs that were working in previous iterations"""

    def test_intelligence_context_endpoint(self):
        """Verify /api/onchain/smart-money/intelligence-context still works"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/intelligence-context?chainId=1&window=7d", timeout=60)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True, "intelligence-context should return ok=True"
        
        # Check required fields
        assert "narrative" in data, "narrative missing"
        assert "token_scores" in data, "token_scores missing"
        assert "signals" in data, "signals missing"
        assert "patterns" in data, "patterns missing"
        print(f"PASS: intelligence-context - {len(data.get('token_scores', []))} tokens, {len(data.get('signals', []))} signals")

    def test_token_profile_endpoint(self):
        """Verify token profile endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/token/WETH/context?chainId=1&window=7d", timeout=60)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True, "token profile should return ok=True"
        print(f"PASS: token profile - WETH score={data.get('score', {}).get('alpha_score', 'N/A')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
