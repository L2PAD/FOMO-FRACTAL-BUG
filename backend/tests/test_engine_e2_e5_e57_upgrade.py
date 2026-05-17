"""
Test Engine Upgrade - E2/E5 Setup Engine, E5.5 Regime Engine, E5.7 Probability Layer
=====================================================================================
Tests for the new engine components integrated into /api/engine/context:
  - Regime Engine: 6 regime types (bull_trend, bear_trend, accumulation, distribution, rotation, neutral_chop)
  - Setup Engine: 7 setup types (liquidity_shock, smart_money_accumulation, distribution_risk, exchange_drain, rotation, actor_conflict, otc_transfer, mixed)
  - Probability Layer: continuation, failure, upgrade probabilities with summary
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "http://localhost:8001"


class TestEngineRegimeEngine:
    """E5.5 Regime Engine tests"""

    def test_regime_engine_exists(self):
        """regime_engine key exists in response"""
        resp = requests.get(f"{BASE_URL}/api/engine/context?window=30d", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert "regime_engine" in data, "Missing regime_engine in response"

    def test_regime_engine_primary_structure(self):
        """primary regime has required fields: type, confidence, status, drivers, invalidation"""
        resp = requests.get(f"{BASE_URL}/api/engine/context?window=30d", timeout=30)
        data = resp.json()
        primary = data.get("regime_engine", {}).get("primary", {})
        
        assert "type" in primary, "Missing type in primary regime"
        assert "confidence" in primary, "Missing confidence in primary regime"
        assert "status" in primary, "Missing status in primary regime"
        assert "drivers" in primary, "Missing drivers in primary regime"
        assert "invalidation" in primary, "Missing invalidation in primary regime"
        
        # Validate types
        assert isinstance(primary["type"], str)
        assert isinstance(primary["confidence"], (int, float))
        assert isinstance(primary["status"], str)
        assert isinstance(primary["drivers"], list)
        assert isinstance(primary["invalidation"], list)

    def test_regime_engine_valid_regime_type(self):
        """primary.type is one of 6 valid regime types"""
        valid_types = ["bull_trend", "bear_trend", "accumulation", "distribution", "rotation", "neutral_chop"]
        resp = requests.get(f"{BASE_URL}/api/engine/context?window=30d", timeout=30)
        data = resp.json()
        regime_type = data.get("regime_engine", {}).get("primary", {}).get("type")
        assert regime_type in valid_types, f"Invalid regime type: {regime_type}"

    def test_regime_engine_confidence_range(self):
        """primary.confidence is between 0 and 1"""
        resp = requests.get(f"{BASE_URL}/api/engine/context?window=30d", timeout=30)
        data = resp.json()
        confidence = data.get("regime_engine", {}).get("primary", {}).get("confidence", 0)
        assert 0 <= confidence <= 1, f"Confidence out of range: {confidence}"

    def test_regime_engine_valid_status(self):
        """primary.status is one of valid statuses"""
        valid_statuses = ["confirmed", "active", "forming", "weak", "weakening"]
        resp = requests.get(f"{BASE_URL}/api/engine/context?window=30d", timeout=30)
        data = resp.json()
        status = data.get("regime_engine", {}).get("primary", {}).get("status")
        assert status in valid_statuses, f"Invalid status: {status}"

    def test_regime_engine_secondary_array(self):
        """secondary is an array of regime objects"""
        resp = requests.get(f"{BASE_URL}/api/engine/context?window=30d", timeout=30)
        data = resp.json()
        secondary = data.get("regime_engine", {}).get("secondary", [])
        assert isinstance(secondary, list), "secondary must be a list"
        
        for s in secondary:
            assert "type" in s, "Secondary regime missing type"
            assert "confidence" in s, "Secondary regime missing confidence"
            assert "status" in s, "Secondary regime missing status"


class TestEngineSetupEngine:
    """E2/E5 Setup Engine tests"""

    def test_setup_engine_exists(self):
        """setup_engine key exists in response"""
        resp = requests.get(f"{BASE_URL}/api/engine/context?window=30d", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert "setup_engine" in data, "Missing setup_engine in response"

    def test_setup_engine_primary_structure(self):
        """primary setup has required fields: type, confidence, status, window, supports, contradictions, invalidation"""
        resp = requests.get(f"{BASE_URL}/api/engine/context?window=30d", timeout=30)
        data = resp.json()
        primary = data.get("setup_engine", {}).get("primary", {})
        
        assert "type" in primary, "Missing type in primary setup"
        assert "confidence" in primary, "Missing confidence in primary setup"
        assert "status" in primary, "Missing status in primary setup"
        assert "window" in primary, "Missing window in primary setup"
        assert "supports" in primary, "Missing supports in primary setup"
        assert "contradictions" in primary, "Missing contradictions in primary setup"
        assert "invalidation" in primary, "Missing invalidation in primary setup"

    def test_setup_engine_valid_setup_type(self):
        """primary.type is one of 8 valid setup types"""
        valid_types = ["liquidity_shock", "smart_money_accumulation", "distribution_risk", 
                       "exchange_drain", "rotation", "actor_conflict", "otc_transfer", "mixed"]
        resp = requests.get(f"{BASE_URL}/api/engine/context?window=30d", timeout=30)
        data = resp.json()
        setup_type = data.get("setup_engine", {}).get("primary", {}).get("type")
        assert setup_type in valid_types, f"Invalid setup type: {setup_type}"

    def test_setup_engine_confidence_range(self):
        """primary.confidence is between 0 and 1"""
        resp = requests.get(f"{BASE_URL}/api/engine/context?window=30d", timeout=30)
        data = resp.json()
        confidence = data.get("setup_engine", {}).get("primary", {}).get("confidence", 0)
        assert 0 <= confidence <= 1, f"Confidence out of range: {confidence}"

    def test_setup_engine_valid_status(self):
        """primary.status is one of valid statuses"""
        valid_statuses = ["confirmed", "active", "forming", "weak"]
        resp = requests.get(f"{BASE_URL}/api/engine/context?window=30d", timeout=30)
        data = resp.json()
        status = data.get("setup_engine", {}).get("primary", {}).get("status")
        assert status in valid_statuses, f"Invalid status: {status}"

    def test_setup_engine_window_present(self):
        """primary.window is a non-empty string"""
        resp = requests.get(f"{BASE_URL}/api/engine/context?window=30d", timeout=30)
        data = resp.json()
        window = data.get("setup_engine", {}).get("primary", {}).get("window", "")
        assert isinstance(window, str) and len(window) > 0, "Window must be non-empty string"

    def test_setup_engine_supports_array(self):
        """supports is an array of strings"""
        resp = requests.get(f"{BASE_URL}/api/engine/context?window=30d", timeout=30)
        data = resp.json()
        supports = data.get("setup_engine", {}).get("primary", {}).get("supports", [])
        assert isinstance(supports, list), "supports must be a list"
        for s in supports:
            assert isinstance(s, str), "Each support must be a string"

    def test_setup_engine_secondary_array(self):
        """secondary is an array of setup objects"""
        resp = requests.get(f"{BASE_URL}/api/engine/context?window=30d", timeout=30)
        data = resp.json()
        secondary = data.get("setup_engine", {}).get("secondary", [])
        assert isinstance(secondary, list), "secondary must be a list"
        
        for s in secondary:
            assert "type" in s, "Secondary setup missing type"
            assert "confidence" in s, "Secondary setup missing confidence"
            assert "status" in s, "Secondary setup missing status"


class TestEngineProbabilityLayer:
    """E5.7 Probability Layer tests"""

    def test_probability_layer_exists(self):
        """probability_layer key exists in response"""
        resp = requests.get(f"{BASE_URL}/api/engine/context?window=30d", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert "probability_layer" in data, "Missing probability_layer in response"

    def test_probability_layer_continuation(self):
        """continuation probability exists and is in range [0, 1]"""
        resp = requests.get(f"{BASE_URL}/api/engine/context?window=30d", timeout=30)
        data = resp.json()
        prob = data.get("probability_layer", {})
        assert "continuation" in prob, "Missing continuation probability"
        assert 0 <= prob["continuation"] <= 1, f"continuation out of range: {prob['continuation']}"

    def test_probability_layer_failure(self):
        """failure probability exists and is in range [0, 1]"""
        resp = requests.get(f"{BASE_URL}/api/engine/context?window=30d", timeout=30)
        data = resp.json()
        prob = data.get("probability_layer", {})
        assert "failure" in prob, "Missing failure probability"
        assert 0 <= prob["failure"] <= 1, f"failure out of range: {prob['failure']}"

    def test_probability_layer_upgrade(self):
        """upgrade probability exists and is in range [0, 1]"""
        resp = requests.get(f"{BASE_URL}/api/engine/context?window=30d", timeout=30)
        data = resp.json()
        prob = data.get("probability_layer", {})
        assert "upgrade" in prob, "Missing upgrade probability"
        assert 0 <= prob["upgrade"] <= 1, f"upgrade out of range: {prob['upgrade']}"

    def test_probability_layer_summary(self):
        """summary text exists and is non-empty"""
        resp = requests.get(f"{BASE_URL}/api/engine/context?window=30d", timeout=30)
        data = resp.json()
        prob = data.get("probability_layer", {})
        assert "summary" in prob, "Missing summary in probability layer"
        assert isinstance(prob["summary"], str), "summary must be string"
        assert len(prob["summary"]) > 0, "summary must be non-empty"

    def test_probability_layer_sum_near_one(self):
        """continuation + failure should be approximately 1"""
        resp = requests.get(f"{BASE_URL}/api/engine/context?window=30d", timeout=30)
        data = resp.json()
        prob = data.get("probability_layer", {})
        total = prob.get("continuation", 0) + prob.get("failure", 0)
        # Allow some tolerance
        assert 0.95 <= total <= 1.05, f"continuation + failure should ~= 1, got {total}"


class TestEngineMetaVersion:
    """Meta version tests"""

    def test_meta_version_42(self):
        """meta.version should be '4.2'"""
        resp = requests.get(f"{BASE_URL}/api/engine/context?window=30d", timeout=30)
        data = resp.json()
        version = data.get("meta", {}).get("version")
        assert version == "4.2", f"Expected version 4.2, got {version}"


class TestEngineIntegration:
    """Integration tests - verify all 3 new components work together"""

    def test_all_three_engines_present(self):
        """All 3 new engine components exist in single response"""
        resp = requests.get(f"{BASE_URL}/api/engine/context?window=30d", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        
        assert "regime_engine" in data, "Missing regime_engine"
        assert "setup_engine" in data, "Missing setup_engine"
        assert "probability_layer" in data, "Missing probability_layer"
        
        # Verify all have primary data
        assert data["regime_engine"].get("primary"), "regime_engine.primary empty"
        assert data["setup_engine"].get("primary"), "setup_engine.primary empty"
        assert data["probability_layer"].get("continuation") is not None, "probability_layer incomplete"

    def test_expected_values_match_context(self):
        """Verify expected values based on context note"""
        resp = requests.get(f"{BASE_URL}/api/engine/context?window=30d", timeout=30)
        data = resp.json()
        
        # Expected regime: bull_trend ~90% confirmed
        regime = data.get("regime_engine", {}).get("primary", {})
        assert regime.get("type") == "bull_trend", f"Expected bull_trend, got {regime.get('type')}"
        assert regime.get("confidence", 0) >= 0.85, f"Expected confidence >= 85%, got {regime.get('confidence')}"
        assert regime.get("status") == "confirmed", f"Expected confirmed status, got {regime.get('status')}"
        
        # Expected setup: liquidity_shock ~75% confirmed
        setup = data.get("setup_engine", {}).get("primary", {})
        assert setup.get("type") == "liquidity_shock", f"Expected liquidity_shock, got {setup.get('type')}"
        assert setup.get("confidence", 0) >= 0.70, f"Expected confidence >= 70%, got {setup.get('confidence')}"
        
        # Expected probability: continuation ~68%, failure ~32%, upgrade ~62%
        prob = data.get("probability_layer", {})
        assert prob.get("continuation", 0) >= 0.60, f"Expected continuation >= 60%, got {prob.get('continuation')}"
        assert prob.get("upgrade", 0) >= 0.55, f"Expected upgrade >= 55%, got {prob.get('upgrade')}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
