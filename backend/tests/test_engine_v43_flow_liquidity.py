"""
Engine V4.3 Sprint Tests - E3 OTC/MM, Flow Acceleration, Liquidity Map
=======================================================================
Tests for Engine V4.3 integration:
- OTC/MM scoring influence
- Flow acceleration detection
- Liquidity map layer
- Probability adjustments
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "http://localhost:8001"


class TestEngineV43Integration:
    """Engine V4.3 API integration tests"""

    def test_engine_context_returns_200(self):
        """Test engine context endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/engine/context?window=30d")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True

    def test_meta_version_is_43(self):
        """Test meta.version = '4.3'"""
        response = requests.get(f"{BASE_URL}/api/engine/context?window=30d")
        data = response.json()
        assert data.get("meta", {}).get("version") == "4.3"

    def test_otc_mm_influence_structure(self):
        """Test otc_mm_influence has correct structure"""
        response = requests.get(f"{BASE_URL}/api/engine/context?window=30d")
        data = response.json()
        otc_mm = data.get("otc_mm_influence", {})
        
        # Required fields
        assert "otc_bias" in otc_mm
        assert "mm_presence" in otc_mm
        assert "confidence_adjustment" in otc_mm
        assert "risk_adjustment" in otc_mm
        assert "drivers" in otc_mm
        
        # Validate types
        assert otc_mm["otc_bias"] in ["bullish", "bearish", "neutral"]
        assert isinstance(otc_mm["mm_presence"], bool)
        assert isinstance(otc_mm["confidence_adjustment"], (int, float))
        assert isinstance(otc_mm["risk_adjustment"], (int, float))
        assert isinstance(otc_mm["drivers"], list)

    def test_flow_engine_structure(self):
        """Test flow_engine has correct structure"""
        response = requests.get(f"{BASE_URL}/api/engine/context?window=30d")
        data = response.json()
        flow = data.get("flow_engine", {})
        
        # Required fields
        assert "state" in flow
        assert "strength" in flow
        assert "velocity" in flow
        assert "drivers" in flow
        
        # Validate values
        valid_states = ["bullish_acceleration", "bearish_acceleration", "liquidity_expansion", "flow_exhaustion", "neutral"]
        assert flow["state"] in valid_states
        assert 0 <= flow["strength"] <= 1
        assert flow["velocity"] in ["high", "moderate", "low"]
        assert isinstance(flow["drivers"], list)

    def test_flow_engine_bullish_acceleration(self):
        """Test flow_engine state is bullish_acceleration as expected"""
        response = requests.get(f"{BASE_URL}/api/engine/context?window=30d")
        data = response.json()
        flow = data.get("flow_engine", {})
        
        # As per test expectations
        assert flow["state"] == "bullish_acceleration"

    def test_liquidity_map_structure(self):
        """Test liquidity_map has correct structure"""
        response = requests.get(f"{BASE_URL}/api/engine/context?window=30d")
        data = response.json()
        liq = data.get("liquidity_map", {})
        
        # Required fields
        assert "magnet_zones" in liq
        assert "void_zones" in liq
        assert "target_zones" in liq
        assert "primary_direction" in liq
        assert "summary" in liq
        
        # Validate types
        assert isinstance(liq["magnet_zones"], list)
        assert isinstance(liq["void_zones"], list)
        assert isinstance(liq["target_zones"], list)
        assert liq["primary_direction"] in ["above", "below", "neutral"]
        assert isinstance(liq["summary"], str)

    def test_liquidity_map_has_targets(self):
        """Test liquidity_map has target zones"""
        response = requests.get(f"{BASE_URL}/api/engine/context?window=30d")
        data = response.json()
        liq = data.get("liquidity_map", {})
        
        targets = liq.get("target_zones", [])
        assert len(targets) >= 1
        
        # Validate target structure
        for target in targets:
            assert "direction" in target
            assert "confidence" in target
            assert "type" in target
            assert "reason" in target

    def test_liquidity_map_has_magnets(self):
        """Test liquidity_map has magnet zones"""
        response = requests.get(f"{BASE_URL}/api/engine/context?window=30d")
        data = response.json()
        liq = data.get("liquidity_map", {})
        
        magnets = liq.get("magnet_zones", [])
        assert len(magnets) >= 1
        
        # Validate magnet structure
        for magnet in magnets:
            assert "type" in magnet
            assert "direction" in magnet
            assert "strength" in magnet
            assert "reason" in magnet

    def test_liquidity_map_primary_direction_above(self):
        """Test liquidity_map primary_direction is 'above' as expected"""
        response = requests.get(f"{BASE_URL}/api/engine/context?window=30d")
        data = response.json()
        liq = data.get("liquidity_map", {})
        
        assert liq["primary_direction"] == "above"

    def test_probability_layer_continuation_above_65(self):
        """Test probability_layer continuation > 0.65"""
        response = requests.get(f"{BASE_URL}/api/engine/context?window=30d")
        data = response.json()
        prob = data.get("probability_layer", {})
        
        assert "continuation" in prob
        assert prob["continuation"] > 0.65

    def test_probability_layer_structure(self):
        """Test probability_layer has correct structure"""
        response = requests.get(f"{BASE_URL}/api/engine/context?window=30d")
        data = response.json()
        prob = data.get("probability_layer", {})
        
        # Required fields
        assert "continuation" in prob
        assert "failure" in prob
        assert "upgrade" in prob
        
        # Validate ranges
        assert 0 <= prob["continuation"] <= 1
        assert 0 <= prob["failure"] <= 1
        assert 0 <= prob["upgrade"] <= 1

    def test_otc_mm_influence_otc_bias_bullish(self):
        """Test otc_mm_influence otc_bias is 'bullish' as expected"""
        response = requests.get(f"{BASE_URL}/api/engine/context?window=30d")
        data = response.json()
        otc_mm = data.get("otc_mm_influence", {})
        
        assert otc_mm["otc_bias"] == "bullish"


class TestFlowAccelerationService:
    """Flow acceleration service tests"""

    def test_flow_engine_drivers_not_empty(self):
        """Test flow_engine has drivers"""
        response = requests.get(f"{BASE_URL}/api/engine/context?window=30d")
        data = response.json()
        flow = data.get("flow_engine", {})
        
        assert len(flow.get("drivers", [])) > 0

    def test_flow_strength_moderate_or_high(self):
        """Test flow strength is moderate or high"""
        response = requests.get(f"{BASE_URL}/api/engine/context?window=30d")
        data = response.json()
        flow = data.get("flow_engine", {})
        
        # For bullish_acceleration, expect strength >= 0.20
        assert flow["strength"] >= 0.20


class TestLiquidityMapService:
    """Liquidity map service tests"""

    def test_liquidity_summary_exists(self):
        """Test liquidity map has summary text"""
        response = requests.get(f"{BASE_URL}/api/engine/context?window=30d")
        data = response.json()
        liq = data.get("liquidity_map", {})
        
        assert len(liq.get("summary", "")) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
