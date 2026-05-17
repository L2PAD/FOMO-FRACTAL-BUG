"""
Alt Season API Tests - Tests for GET /api/altseason endpoint
Tests the Alt Alpha Engine that computes altseason index from real market data.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAltseasonAPI:
    """Tests for /api/altseason endpoint"""
    
    def test_altseason_returns_ok(self):
        """Test that /api/altseason returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/altseason")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True, f"Expected ok:true, got {data}"
    
    def test_altseason_index_in_range(self):
        """Test that index value is between 0-100"""
        response = requests.get(f"{BASE_URL}/api/altseason")
        data = response.json()
        assert "index" in data, "Missing 'index' field"
        assert isinstance(data["index"], (int, float)), f"Index should be numeric, got {type(data['index'])}"
        assert 0 <= data["index"] <= 100, f"Index {data['index']} not in range 0-100"
    
    def test_altseason_state_valid(self):
        """Test that state is one of FULL_ALT/ALTSEASON/EARLY_ALT/BTC_DOMINANCE"""
        response = requests.get(f"{BASE_URL}/api/altseason")
        data = response.json()
        valid_states = ["FULL_ALT", "ALTSEASON", "EARLY_ALT", "BTC_DOMINANCE"]
        assert "state" in data, "Missing 'state' field"
        assert data["state"] in valid_states, f"Invalid state: {data['state']}, expected one of {valid_states}"
    
    def test_altseason_confidence(self):
        """Test that confidence is present and valid"""
        response = requests.get(f"{BASE_URL}/api/altseason")
        data = response.json()
        assert "confidence" in data, "Missing 'confidence' field"
        assert isinstance(data["confidence"], (int, float)), f"Confidence should be numeric"
        assert 0 <= data["confidence"] <= 1, f"Confidence {data['confidence']} not in range 0-1"
    
    def test_altseason_components_all_fields(self):
        """Test that components has all 5 required fields"""
        response = requests.get(f"{BASE_URL}/api/altseason")
        data = response.json()
        assert "components" in data, "Missing 'components' field"
        
        required_fields = ["outperformance", "twitterShare", "clusterStrength", "breadth", "marketBias"]
        for field in required_fields:
            assert field in data["components"], f"Missing component field: {field}"
            value = data["components"][field]
            assert isinstance(value, (int, float)), f"Component {field} should be numeric"
            assert 0 <= value <= 1, f"Component {field} value {value} not in range 0-1"
    
    def test_altseason_top_opportunities_structure(self):
        """Test that top_opportunities has correct structure"""
        response = requests.get(f"{BASE_URL}/api/altseason")
        data = response.json()
        assert "top_opportunities" in data, "Missing 'top_opportunities' field"
        assert isinstance(data["top_opportunities"], list), "top_opportunities should be a list"
        
        if len(data["top_opportunities"]) > 0:
            opp = data["top_opportunities"][0]
            required_fields = ["symbol", "score", "phase", "action", "signal", "priceChange24h", "price", "mentions"]
            for field in required_fields:
                assert field in opp, f"Missing opportunity field: {field}"
    
    def test_altseason_opportunity_phases(self):
        """Test that opportunity phases are valid"""
        response = requests.get(f"{BASE_URL}/api/altseason")
        data = response.json()
        valid_phases = ["EARLY", "MOMENTUM", "LATE", "NEUTRAL"]
        
        for opp in data.get("top_opportunities", []):
            assert opp["phase"] in valid_phases, f"Invalid phase: {opp['phase']}"
    
    def test_altseason_opportunity_actions(self):
        """Test that opportunity actions match phases"""
        response = requests.get(f"{BASE_URL}/api/altseason")
        data = response.json()
        
        phase_action_map = {
            "EARLY": "ACCUMULATE",
            "MOMENTUM": "RIDE",
            "LATE": "EXIT",
            "NEUTRAL": "WAIT"
        }
        
        for opp in data.get("top_opportunities", []):
            expected_action = phase_action_map.get(opp["phase"])
            assert opp["action"] == expected_action, f"Phase {opp['phase']} should have action {expected_action}, got {opp['action']}"
    
    def test_altseason_token_momentum_structure(self):
        """Test that token_momentum has correct structure"""
        response = requests.get(f"{BASE_URL}/api/altseason")
        data = response.json()
        assert "token_momentum" in data, "Missing 'token_momentum' field"
        assert isinstance(data["token_momentum"], list), "token_momentum should be a list"
        
        if len(data["token_momentum"]) > 0:
            token = data["token_momentum"][0]
            required_fields = ["symbol", "momentum", "phase", "score", "priceChange24h", "mentions"]
            for field in required_fields:
                assert field in token, f"Missing token_momentum field: {field}"
    
    def test_altseason_token_momentum_count(self):
        """Test that token_momentum has up to 25 tokens"""
        response = requests.get(f"{BASE_URL}/api/altseason")
        data = response.json()
        assert len(data.get("token_momentum", [])) <= 25, "token_momentum should have max 25 tokens"
    
    def test_altseason_token_momentum_sorted(self):
        """Test that token_momentum is sorted by momentum descending"""
        response = requests.get(f"{BASE_URL}/api/altseason")
        data = response.json()
        
        momentums = [t["momentum"] for t in data.get("token_momentum", [])]
        assert momentums == sorted(momentums, reverse=True), "token_momentum should be sorted by momentum descending"
    
    def test_altseason_meta_fields(self):
        """Test that meta contains expected fields"""
        response = requests.get(f"{BASE_URL}/api/altseason")
        data = response.json()
        assert "meta" in data, "Missing 'meta' field"
        
        expected_meta_fields = ["totalTokens", "totalSnapshots", "totalTweets", "totalClusters", "computedAt"]
        for field in expected_meta_fields:
            assert field in data["meta"], f"Missing meta field: {field}"
    
    def test_altseason_early_phase_accumulate(self):
        """Test that EARLY phase tokens have ACCUMULATE action"""
        response = requests.get(f"{BASE_URL}/api/altseason")
        data = response.json()
        
        early_opps = [o for o in data.get("top_opportunities", []) if o["phase"] == "EARLY"]
        for opp in early_opps:
            assert opp["action"] == "ACCUMULATE", f"EARLY phase should have ACCUMULATE action"
    
    def test_altseason_momentum_phase_ride(self):
        """Test that MOMENTUM phase tokens have RIDE action"""
        response = requests.get(f"{BASE_URL}/api/altseason")
        data = response.json()
        
        momentum_opps = [o for o in data.get("top_opportunities", []) if o["phase"] == "MOMENTUM"]
        for opp in momentum_opps:
            assert opp["action"] == "RIDE", f"MOMENTUM phase should have RIDE action"
    
    def test_altseason_neutral_phase_wait(self):
        """Test that NEUTRAL phase tokens have WAIT action"""
        response = requests.get(f"{BASE_URL}/api/altseason")
        data = response.json()
        
        neutral_opps = [o for o in data.get("top_opportunities", []) if o["phase"] == "NEUTRAL"]
        for opp in neutral_opps:
            assert opp["action"] == "WAIT", f"NEUTRAL phase should have WAIT action"
    
    def test_altseason_opportunity_score_range(self):
        """Test that opportunity scores are in valid range"""
        response = requests.get(f"{BASE_URL}/api/altseason")
        data = response.json()
        
        for opp in data.get("top_opportunities", []):
            assert 0 <= opp["score"] <= 1, f"Score {opp['score']} not in range 0-1"
    
    def test_altseason_signal_is_list(self):
        """Test that opportunity signal is a list"""
        response = requests.get(f"{BASE_URL}/api/altseason")
        data = response.json()
        
        for opp in data.get("top_opportunities", []):
            assert isinstance(opp["signal"], list), f"Signal should be a list, got {type(opp['signal'])}"
