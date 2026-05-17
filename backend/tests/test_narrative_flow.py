"""
Narrative Flow API Tests
Tests for /api/narrative-flow endpoint - narrative decision engine
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestNarrativeFlowAPI:
    """Tests for /api/narrative-flow endpoint"""

    def test_narrative_flow_returns_ok(self):
        """Test that API returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/narrative-flow")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True

    def test_narrative_flow_has_required_arrays(self):
        """Test that response has narratives, rotations, frontRuns, tokens arrays"""
        response = requests.get(f"{BASE_URL}/api/narrative-flow")
        data = response.json()
        
        assert "narratives" in data
        assert "rotations" in data
        assert "frontRuns" in data
        assert "tokens" in data
        
        assert isinstance(data["narratives"], list)
        assert isinstance(data["rotations"], list)
        assert isinstance(data["frontRuns"], list)
        assert isinstance(data["tokens"], list)

    def test_narratives_have_required_fields(self):
        """Test that narratives have key, name, phase, score, action, confidence, velocity, mentions, influencers, tokens"""
        response = requests.get(f"{BASE_URL}/api/narrative-flow")
        data = response.json()
        
        required_fields = ["key", "name", "phase", "score", "action", "confidence", "velocity", "mentions", "influencers", "tokens"]
        
        for narrative in data.get("narratives", []):
            for field in required_fields:
                assert field in narrative, f"Missing field '{field}' in narrative {narrative.get('key')}"

    def test_narrative_action_formula_buy_early(self):
        """Test BUY EARLY action: score>0.75 && IGNITION"""
        response = requests.get(f"{BASE_URL}/api/narrative-flow")
        data = response.json()
        
        for n in data.get("narratives", []):
            if n["score"] > 0.75 and n["phase"] == "IGNITION":
                assert n["action"] == "BUY EARLY", f"Expected BUY EARLY for {n['name']} (score={n['score']}, phase={n['phase']})"

    def test_narrative_action_formula_watch(self):
        """Test WATCH action: score>0.65 && IGNITION (but not >0.75)"""
        response = requests.get(f"{BASE_URL}/api/narrative-flow")
        data = response.json()
        
        for n in data.get("narratives", []):
            if 0.65 < n["score"] <= 0.75 and n["phase"] == "IGNITION":
                assert n["action"] == "WATCH", f"Expected WATCH for {n['name']} (score={n['score']}, phase={n['phase']})"

    def test_narrative_action_formula_late(self):
        """Test LATE action: phase == EXPANSION"""
        response = requests.get(f"{BASE_URL}/api/narrative-flow")
        data = response.json()
        
        for n in data.get("narratives", []):
            if n["phase"] == "EXPANSION":
                assert n["action"] == "LATE", f"Expected LATE for {n['name']} (phase={n['phase']})"

    def test_rotations_have_required_fields(self):
        """Test that rotations have from, to, score, signal, topTokens"""
        response = requests.get(f"{BASE_URL}/api/narrative-flow")
        data = response.json()
        
        required_fields = ["from", "to", "score", "signal", "topTokens"]
        
        for rotation in data.get("rotations", []):
            for field in required_fields:
                assert field in rotation, f"Missing field '{field}' in rotation"

    def test_frontrun_signals_have_required_fields(self):
        """Test that frontRuns have name, score, label, velocity, mentions, infRatio, tokens"""
        response = requests.get(f"{BASE_URL}/api/narrative-flow")
        data = response.json()
        
        required_fields = ["name", "score", "label", "velocity", "mentions", "infRatio", "tokens"]
        
        for signal in data.get("frontRuns", []):
            for field in required_fields:
                assert field in signal, f"Missing field '{field}' in frontRun signal"

    def test_tokens_have_required_fields(self):
        """Test that tokens have token, score, action, narrative, phase, mentions, sentiment"""
        response = requests.get(f"{BASE_URL}/api/narrative-flow")
        data = response.json()
        
        required_fields = ["token", "score", "action", "narrative", "phase", "mentions", "sentiment"]
        
        for token in data.get("tokens", []):
            for field in required_fields:
                assert field in token, f"Missing field '{field}' in token {token.get('token')}"

    def test_narratives_count(self):
        """Test that we have 6 narratives as expected"""
        response = requests.get(f"{BASE_URL}/api/narrative-flow")
        data = response.json()
        
        assert len(data.get("narratives", [])) == 6, f"Expected 6 narratives, got {len(data.get('narratives', []))}"

    def test_narrative_scores_are_valid(self):
        """Test that narrative scores are between 0 and 1"""
        response = requests.get(f"{BASE_URL}/api/narrative-flow")
        data = response.json()
        
        for n in data.get("narratives", []):
            assert 0 <= n["score"] <= 1, f"Invalid score {n['score']} for {n['name']}"

    def test_rotation_signals_valid_values(self):
        """Test that rotation signals are EARLY, FORMING, or WEAK"""
        response = requests.get(f"{BASE_URL}/api/narrative-flow")
        data = response.json()
        
        valid_signals = ["EARLY", "FORMING", "WEAK"]
        for r in data.get("rotations", []):
            assert r["signal"] in valid_signals, f"Invalid signal '{r['signal']}' in rotation"

    def test_frontrun_labels_valid_values(self):
        """Test that frontRun labels are FRONT-RUN, EARLY, or FORMING"""
        response = requests.get(f"{BASE_URL}/api/narrative-flow")
        data = response.json()
        
        valid_labels = ["FRONT-RUN", "EARLY", "FORMING"]
        for f in data.get("frontRuns", []):
            assert f["label"] in valid_labels, f"Invalid label '{f['label']}' in frontRun"

    def test_token_actions_valid_values(self):
        """Test that token actions are BUY, WATCH, LATE, or AVOID"""
        response = requests.get(f"{BASE_URL}/api/narrative-flow")
        data = response.json()
        
        valid_actions = ["BUY", "WATCH", "LATE", "AVOID"]
        for t in data.get("tokens", []):
            assert t["action"] in valid_actions, f"Invalid action '{t['action']}' for token {t['token']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
