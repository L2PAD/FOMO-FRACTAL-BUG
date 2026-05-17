"""
Market Context Engine Tests — iteration 354
Tests for the Market Context feature in Intelligence Panel:
- Backend: market_context object in render-seeds and render endpoints
- Structure: type, confidence, summary, bullish_score, bearish_score, drivers[], risks[]
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

TEST_ADDRESS = "0x1f2f10d1c40777ae1da742455c65828ff36df387"
TEST_NODE_ID = f"wallet:{TEST_ADDRESS}:ethereum"


class TestMarketContextAPI:
    """Test Market Context presence and structure in API responses"""

    def test_health_check(self):
        """Verify backend is healthy"""
        resp = requests.get(f"{BASE_URL}/api/exchange/health")
        assert resp.status_code in [200, 503], f"Expected 200 or 503, got {resp.status_code}"
        data = resp.json()
        assert data.get("status") in ["HEALTHY", "DEGRADED", "CRITICAL"], f"Unexpected status: {data.get('status')}"
        print(f"[PASS] Health check passed: {data.get('status')}")

    def test_render_seeds_returns_market_context(self):
        """render-seeds endpoint returns market_context alongside intelligence array"""
        url = f"{BASE_URL}/api/graph-core/render-seeds"
        params = {
            "seeds": TEST_NODE_ID,
            "limit": 50,
            "mode": "smart_money"
        }
        resp = requests.get(url, params=params)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        assert "market_context" in data, "market_context missing from render-seeds response"
        
        mc = data["market_context"]
        if mc is None:
            pytest.skip("No market_context computed for this test data")
        
        # Validate structure
        assert "type" in mc, "market_context.type missing"
        assert mc["type"] in ["bullish", "bearish", "neutral", "uncertain"], f"Invalid type: {mc['type']}"
        
        assert "confidence" in mc, "market_context.confidence missing"
        assert 0 <= mc["confidence"] <= 1, f"Confidence out of range: {mc['confidence']}"
        
        assert "summary" in mc, "market_context.summary missing"
        assert isinstance(mc["summary"], str), "summary should be string"
        
        assert "bullish_score" in mc, "market_context.bullish_score missing"
        assert "bearish_score" in mc, "market_context.bearish_score missing"
        
        assert "drivers" in mc, "market_context.drivers missing"
        assert isinstance(mc["drivers"], list), "drivers should be list"
        
        assert "risks" in mc, "market_context.risks missing"
        assert isinstance(mc["risks"], list), "risks should be list"
        
        print(f"[PASS] render-seeds returns valid market_context: type={mc['type']}, confidence={mc['confidence']}")

    def test_render_endpoint_returns_market_context(self):
        """render/{id} endpoint returns market_context"""
        url = f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}"
        params = {
            "mode": "entity",
            "depth": 2,
            "limit": 50
        }
        resp = requests.get(url, params=params)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        assert "market_context" in data, "market_context missing from render endpoint"
        
        mc = data["market_context"]
        if mc is None:
            pytest.skip("No market_context computed for this test data")
        
        # Validate basic structure
        assert "type" in mc
        assert "confidence" in mc
        assert "summary" in mc
        
        print(f"[PASS] render endpoint returns valid market_context: type={mc['type']}")

    def test_market_context_drivers_structure(self):
        """Verify drivers array has correct structure"""
        url = f"{BASE_URL}/api/graph-core/render-seeds"
        params = {"seeds": TEST_NODE_ID, "limit": 50, "mode": "smart_money"}
        resp = requests.get(url, params=params)
        data = resp.json()
        
        mc = data.get("market_context")
        if not mc or not mc.get("drivers"):
            pytest.skip("No drivers in market_context")
        
        for driver in mc["drivers"]:
            assert "type" in driver, "driver.type missing"
            assert "confidence" in driver, "driver.confidence missing"
            assert "weight" in driver, "driver.weight missing"
            assert "contribution" in driver, "driver.contribution missing"
        
        print(f"[PASS] drivers structure valid: {len(mc['drivers'])} drivers")

    def test_market_context_risks_structure(self):
        """Verify risks array has correct structure"""
        url = f"{BASE_URL}/api/graph-core/render-seeds"
        params = {"seeds": TEST_NODE_ID, "limit": 50, "mode": "smart_money"}
        resp = requests.get(url, params=params)
        data = resp.json()
        
        mc = data.get("market_context")
        if not mc or not mc.get("risks"):
            pytest.skip("No risks in market_context")
        
        for risk in mc["risks"]:
            assert "type" in risk, "risk.type missing"
            assert "confidence" in risk, "risk.confidence missing"
            assert "weight" in risk, "risk.weight missing"
            assert "contribution" in risk, "risk.contribution missing"
        
        print(f"[PASS] risks structure valid: {len(mc['risks'])} risks")

    def test_market_context_with_different_modes(self):
        """market_context returned for different intelligence modes"""
        modes = ["smart_money", "entity", "risk", "token_rotation"]
        
        for mode in modes:
            url = f"{BASE_URL}/api/graph-core/render-seeds"
            params = {"seeds": TEST_NODE_ID, "limit": 50, "mode": mode}
            resp = requests.get(url, params=params)
            
            if resp.status_code != 200:
                print(f"[SKIP] Mode {mode}: status {resp.status_code}")
                continue
            
            data = resp.json()
            # market_context key should always be present (may be null)
            assert "market_context" in data, f"market_context key missing for mode={mode}"
            
            mc = data.get("market_context")
            if mc:
                print(f"[PASS] Mode {mode}: type={mc['type']}, bullish={mc['bullish_score']}, bearish={mc['bearish_score']}")
            else:
                print(f"[INFO] Mode {mode}: market_context is null (no signals)")

    def test_intelligence_array_coexists_with_market_context(self):
        """Verify both intelligence array and market_context are returned together"""
        url = f"{BASE_URL}/api/graph-core/render-seeds"
        params = {"seeds": TEST_NODE_ID, "limit": 50, "mode": "smart_money"}
        resp = requests.get(url, params=params)
        data = resp.json()
        
        assert "intelligence" in data, "intelligence array missing"
        assert "market_context" in data, "market_context missing"
        
        intel_count = len(data.get("intelligence", []))
        mc = data.get("market_context")
        
        print(f"[PASS] intelligence ({intel_count} signals) and market_context coexist")
        
        # If we have intelligence signals, market_context should be computed
        if intel_count > 0 and mc:
            assert mc.get("type") is not None, "market_context.type should be set when signals exist"

    def test_all_mode_returns_market_context_null(self):
        """All mode (no mode param) may return null market_context"""
        url = f"{BASE_URL}/api/graph-core/render-seeds"
        params = {"seeds": TEST_NODE_ID, "limit": 50}  # no mode
        resp = requests.get(url, params=params)
        data = resp.json()
        
        # Key should exist
        assert "market_context" in data, "market_context key should be present even without mode"
        print(f"[PASS] market_context key present for all mode: {data.get('market_context')}")


class TestMarketContextComputation:
    """Test market context computation logic"""

    def test_bullish_type_when_bullish_dominates(self):
        """When bullish_score > bearish_score, type should be bullish"""
        # This is a behavioral test - we need actual data to verify
        url = f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}"
        params = {"mode": "entity", "depth": 2, "limit": 50}
        resp = requests.get(url, params=params)
        data = resp.json()
        
        mc = data.get("market_context")
        if not mc:
            pytest.skip("No market_context")
        
        if mc["bullish_score"] > mc["bearish_score"]:
            assert mc["type"] == "bullish", f"Expected bullish when bullish > bearish, got {mc['type']}"
            print(f"[PASS] bullish type correct: bull={mc['bullish_score']} > bear={mc['bearish_score']}")
        else:
            print(f"[INFO] bearish or neutral: bull={mc['bullish_score']}, bear={mc['bearish_score']}")

    def test_bearish_type_when_bearish_dominates(self):
        """When bearish_score > bullish_score, type should be bearish"""
        url = f"{BASE_URL}/api/graph-core/render-seeds"
        params = {"seeds": TEST_NODE_ID, "limit": 50, "mode": "smart_money"}
        resp = requests.get(url, params=params)
        data = resp.json()
        
        mc = data.get("market_context")
        if not mc:
            pytest.skip("No market_context")
        
        if mc["bearish_score"] > mc["bullish_score"]:
            assert mc["type"] == "bearish", f"Expected bearish when bearish > bullish, got {mc['type']}"
            print(f"[PASS] bearish type correct: bear={mc['bearish_score']} > bull={mc['bullish_score']}")
        else:
            print(f"[INFO] bullish or neutral: bull={mc['bullish_score']}, bear={mc['bearish_score']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
