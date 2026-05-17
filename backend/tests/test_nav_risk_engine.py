"""
Test: 2-Level Navigation + Market Risk Engine
Tests backend APIs for the navigation refactor and risk engine features.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestOSStateAPI:
    """Tests for GET /api/os/state endpoint with market_risk field."""
    
    def test_os_state_returns_ok(self):
        """OS state endpoint returns ok=true"""
        r = requests.get(f"{BASE_URL}/api/os/state")
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True
        
    def test_os_state_has_market_risk(self):
        """OS state includes market_risk field"""
        r = requests.get(f"{BASE_URL}/api/os/state")
        data = r.json()
        assert "market_risk" in data
        market_risk = data["market_risk"]
        assert market_risk is not None
        
    def test_market_risk_has_risk_score(self):
        """market_risk includes risk_score (0-100)"""
        r = requests.get(f"{BASE_URL}/api/os/state")
        data = r.json()
        risk = data["market_risk"]
        assert "risk_score" in risk
        score = risk["risk_score"]
        assert isinstance(score, (int, float))
        assert 0 <= score <= 100
        
    def test_market_risk_has_risk_level(self):
        """market_risk includes risk_level (one of LOW/MODERATE/ELEVATED/HIGH)"""
        r = requests.get(f"{BASE_URL}/api/os/state")
        data = r.json()
        risk = data["market_risk"]
        assert "risk_level" in risk
        level = risk["risk_level"]
        assert level in ["LOW", "MODERATE", "ELEVATED", "HIGH"]
        
    def test_market_risk_has_drivers(self):
        """market_risk includes drivers array"""
        r = requests.get(f"{BASE_URL}/api/os/state")
        data = r.json()
        risk = data["market_risk"]
        assert "drivers" in risk
        assert isinstance(risk["drivers"], list)
        
    def test_market_risk_has_components(self):
        """market_risk includes components breakdown"""
        r = requests.get(f"{BASE_URL}/api/os/state")
        data = r.json()
        risk = data["market_risk"]
        assert "components" in risk
        components = risk["components"]
        # Check expected component keys
        expected_keys = ["exchange", "actor_conflict", "liquidity", "setup_failure", "flow_instability"]
        for key in expected_keys:
            assert key in components, f"Missing component: {key}"
            
    def test_market_risk_has_invalidation(self):
        """market_risk includes invalidation conditions"""
        r = requests.get(f"{BASE_URL}/api/os/state")
        data = r.json()
        risk = data["market_risk"]
        assert "invalidation" in risk
        assert isinstance(risk["invalidation"], list)
        
    def test_os_state_has_all_blocks(self):
        """OS state has all required blocks: market_state, top_opportunity, actor_pressure, liquidity_targets, alerts"""
        r = requests.get(f"{BASE_URL}/api/os/state")
        data = r.json()
        required_blocks = ["market_state", "market_risk", "top_opportunity", "actor_pressure", "liquidity_targets", "alerts"]
        for block in required_blocks:
            assert block in data, f"Missing block: {block}"


class TestEngineContextAPI:
    """Tests for GET /api/engine/context - verifies risk_engine field is present."""
    
    def test_engine_context_returns_ok(self):
        """Engine context endpoint returns ok=true"""
        r = requests.get(f"{BASE_URL}/api/engine/context")
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True
        
    def test_engine_context_has_risk_engine(self):
        """Engine context includes risk_engine field"""
        r = requests.get(f"{BASE_URL}/api/engine/context")
        data = r.json()
        assert "risk_engine" in data
        risk = data["risk_engine"]
        assert risk is not None
        
    def test_engine_risk_engine_structure(self):
        """risk_engine has same structure as market_risk"""
        r = requests.get(f"{BASE_URL}/api/engine/context")
        data = r.json()
        risk = data["risk_engine"]
        assert "risk_score" in risk
        assert "risk_level" in risk
        assert "drivers" in risk
        assert "components" in risk
        assert "invalidation" in risk
        
    def test_engine_risk_level_valid(self):
        """risk_engine.risk_level is one of LOW/MODERATE/ELEVATED/HIGH"""
        r = requests.get(f"{BASE_URL}/api/engine/context")
        data = r.json()
        level = data["risk_engine"]["risk_level"]
        assert level in ["LOW", "MODERATE", "ELEVATED", "HIGH"]


class TestRiskScoreConsistency:
    """Verify risk_engine data is consistent between endpoints."""
    
    def test_risk_score_consistency(self):
        """OS state and engine context should have same risk data"""
        os_r = requests.get(f"{BASE_URL}/api/os/state")
        engine_r = requests.get(f"{BASE_URL}/api/engine/context")
        
        os_risk = os_r.json()["market_risk"]
        engine_risk = engine_r.json()["risk_engine"]
        
        # Risk score and level should match (data from same source)
        assert os_risk["risk_score"] == engine_risk["risk_score"]
        assert os_risk["risk_level"] == engine_risk["risk_level"]


class TestEngineExistingFeatures:
    """Verify existing engine features still work."""
    
    def test_engine_has_decision(self):
        """Engine context has decision field"""
        r = requests.get(f"{BASE_URL}/api/engine/context")
        data = r.json()
        assert "decision" in data
        assert data["decision"] in ["BUY", "SELL", "NEUTRAL"]
        
    def test_engine_has_confidence(self):
        """Engine context has confidence object"""
        r = requests.get(f"{BASE_URL}/api/engine/context")
        data = r.json()
        assert "confidence" in data
        conf = data["confidence"]
        assert "level" in conf
        assert "score" in conf
        
    def test_engine_has_regime_engine(self):
        """Engine context has regime_engine"""
        r = requests.get(f"{BASE_URL}/api/engine/context")
        data = r.json()
        assert "regime_engine" in data
        
    def test_engine_has_setup_engine(self):
        """Engine context has setup_engine"""
        r = requests.get(f"{BASE_URL}/api/engine/context")
        data = r.json()
        assert "setup_engine" in data
        
    def test_engine_has_probability_layer(self):
        """Engine context has probability_layer"""
        r = requests.get(f"{BASE_URL}/api/engine/context")
        data = r.json()
        assert "probability_layer" in data
        
    def test_engine_has_flow_engine(self):
        """Engine context has flow_engine"""
        r = requests.get(f"{BASE_URL}/api/engine/context")
        data = r.json()
        assert "flow_engine" in data
        
    def test_engine_has_liquidity_map(self):
        """Engine context has liquidity_map"""
        r = requests.get(f"{BASE_URL}/api/engine/context")
        data = r.json()
        assert "liquidity_map" in data
