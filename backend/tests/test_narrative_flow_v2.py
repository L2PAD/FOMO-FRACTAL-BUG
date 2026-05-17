"""
Test Narrative Flow v2 - Enhanced Features
Tests: tradeSetup, topPicks, origins, rotation actions, tighter front-run labels
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestNarrativeFlowV2:
    """Tests for Narrative Decision Engine v2 enhancements"""
    
    def test_api_returns_ok(self):
        """API returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/narrative-flow")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print("PASS: API returns ok:true")
    
    def test_response_has_all_required_arrays(self):
        """Response has tradeSetup, narratives, rotations, frontRuns, topPicks, tokens, origins"""
        response = requests.get(f"{BASE_URL}/api/narrative-flow")
        data = response.json()
        
        required_keys = ["tradeSetup", "narratives", "rotations", "frontRuns", "topPicks", "tokens", "origins"]
        for key in required_keys:
            assert key in data, f"Missing key: {key}"
        print(f"PASS: All required keys present: {required_keys}")
    
    # ─── TRADE SETUP TESTS ───────────────────────────────────
    
    def test_trade_setup_structure(self):
        """tradeSetup has: narrative, phase, action, tokens array, rotation info, frontRun label"""
        response = requests.get(f"{BASE_URL}/api/narrative-flow")
        data = response.json()
        setup = data.get("tradeSetup")
        
        assert setup is not None, "tradeSetup is None"
        
        # Required fields
        assert "narrative" in setup, "Missing narrative"
        assert "phase" in setup, "Missing phase"
        assert "action" in setup, "Missing action"
        assert "tokens" in setup, "Missing tokens"
        assert isinstance(setup["tokens"], list), "tokens should be array"
        assert len(setup["tokens"]) > 0, "tokens array should not be empty"
        
        # Optional but expected fields
        assert "narrativeKey" in setup, "Missing narrativeKey"
        assert "score" in setup, "Missing score"
        
        print(f"PASS: tradeSetup structure valid - narrative={setup['narrative']}, phase={setup['phase']}, action={setup['action']}, tokens={len(setup['tokens'])}")
    
    def test_trade_setup_tokens_have_action(self):
        """tradeSetup tokens have token, score, action fields"""
        response = requests.get(f"{BASE_URL}/api/narrative-flow")
        data = response.json()
        setup = data.get("tradeSetup")
        
        for token in setup.get("tokens", []):
            assert "token" in token, "Token missing 'token' field"
            assert "score" in token, "Token missing 'score' field"
            assert "action" in token, "Token missing 'action' field"
        
        print(f"PASS: All {len(setup['tokens'])} tradeSetup tokens have required fields")
    
    # ─── ROTATION TESTS ──────────────────────────────────────
    
    def test_rotations_have_action_field(self):
        """rotations include 'action' field (BUY/WATCH/AVOID) alongside 'signal' field"""
        response = requests.get(f"{BASE_URL}/api/narrative-flow")
        data = response.json()
        rotations = data.get("rotations", [])
        
        for r in rotations:
            assert "signal" in r, f"Rotation missing 'signal' field"
            assert "action" in r, f"Rotation missing 'action' field"
            assert r["action"] in ["BUY", "WATCH", "AVOID"], f"Invalid action: {r['action']}"
        
        print(f"PASS: All {len(rotations)} rotations have both 'signal' and 'action' fields")
    
    def test_rotations_have_required_fields(self):
        """rotations have from, to, score, signal, action, topTokens"""
        response = requests.get(f"{BASE_URL}/api/narrative-flow")
        data = response.json()
        rotations = data.get("rotations", [])
        
        required = ["from", "to", "score", "signal", "action", "topTokens"]
        for r in rotations:
            for field in required:
                assert field in r, f"Rotation missing '{field}'"
        
        print(f"PASS: All rotations have required fields: {required}")
    
    # ─── FRONT-RUN TESTS ─────────────────────────────────────
    
    def test_frontrun_labels_are_tight(self):
        """frontRuns have label field with STRONG/EARLY/WEAK (not FRONT-RUN/FORMING)"""
        response = requests.get(f"{BASE_URL}/api/narrative-flow")
        data = response.json()
        front_runs = data.get("frontRuns", [])
        
        valid_labels = ["STRONG", "EARLY", "WEAK"]
        invalid_labels = ["FRONT-RUN", "FORMING"]
        
        for fr in front_runs:
            assert "label" in fr, "frontRun missing 'label' field"
            assert fr["label"] in valid_labels, f"Invalid label: {fr['label']} - expected one of {valid_labels}"
            assert fr["label"] not in invalid_labels, f"Old label format detected: {fr['label']}"
        
        labels_found = [fr["label"] for fr in front_runs]
        print(f"PASS: All frontRun labels are tight: {set(labels_found)}")
    
    def test_frontrun_has_required_fields(self):
        """frontRuns have name, key, score, label, velocity, mentions, infRatio, tokens"""
        response = requests.get(f"{BASE_URL}/api/narrative-flow")
        data = response.json()
        front_runs = data.get("frontRuns", [])
        
        required = ["name", "key", "score", "label", "velocity", "mentions", "infRatio", "tokens"]
        for fr in front_runs:
            for field in required:
                assert field in fr, f"frontRun missing '{field}'"
        
        print(f"PASS: All frontRuns have required fields: {required}")
    
    # ─── TOP PICKS TESTS ─────────────────────────────────────
    
    def test_top_picks_is_array_of_buy_tokens(self):
        """topPicks is array of top BUY tokens"""
        response = requests.get(f"{BASE_URL}/api/narrative-flow")
        data = response.json()
        top_picks = data.get("topPicks", [])
        
        assert isinstance(top_picks, list), "topPicks should be array"
        
        for pick in top_picks:
            assert "token" in pick, "topPick missing 'token'"
            assert "action" in pick, "topPick missing 'action'"
            assert pick["action"] == "BUY", f"topPick should have action=BUY, got {pick['action']}"
        
        print(f"PASS: topPicks has {len(top_picks)} BUY tokens")
    
    def test_top_picks_max_three(self):
        """topPicks should have at most 3 tokens"""
        response = requests.get(f"{BASE_URL}/api/narrative-flow")
        data = response.json()
        top_picks = data.get("topPicks", [])
        
        assert len(top_picks) <= 3, f"topPicks should have max 3 tokens, got {len(top_picks)}"
        print(f"PASS: topPicks has {len(top_picks)} tokens (max 3)")
    
    # ─── ORIGINS TESTS ───────────────────────────────────────
    
    def test_origins_has_required_fields(self):
        """origins array has: author, score, label (FIRST/EARLY), narrative, token, reach, timing, impact"""
        response = requests.get(f"{BASE_URL}/api/narrative-flow")
        data = response.json()
        origins = data.get("origins", [])
        
        required = ["author", "score", "label", "narrative", "token", "reach", "timing", "impact"]
        for o in origins:
            for field in required:
                assert field in o, f"origin missing '{field}'"
        
        print(f"PASS: All {len(origins)} origins have required fields: {required}")
    
    def test_origins_labels_are_valid(self):
        """origins have label FIRST or EARLY (not NOISE)"""
        response = requests.get(f"{BASE_URL}/api/narrative-flow")
        data = response.json()
        origins = data.get("origins", [])
        
        valid_labels = ["FIRST", "EARLY"]
        for o in origins:
            assert o["label"] in valid_labels, f"Invalid origin label: {o['label']}"
        
        labels_found = [o["label"] for o in origins]
        print(f"PASS: All origin labels valid: {set(labels_found)}")
    
    def test_origins_have_numeric_metrics(self):
        """origins have numeric reach, timing, impact"""
        response = requests.get(f"{BASE_URL}/api/narrative-flow")
        data = response.json()
        origins = data.get("origins", [])
        
        for o in origins:
            assert isinstance(o["reach"], (int, float)), f"reach should be numeric"
            assert isinstance(o["timing"], (int, float)), f"timing should be numeric"
            assert isinstance(o["impact"], (int, float)), f"impact should be numeric"
            assert 0 <= o["timing"] <= 1, f"timing should be 0-1, got {o['timing']}"
            assert 0 <= o["impact"] <= 1, f"impact should be 0-1, got {o['impact']}"
        
        print(f"PASS: All origins have valid numeric metrics")
    
    # ─── NARRATIVES TESTS ────────────────────────────────────
    
    def test_narratives_have_action_column(self):
        """narratives have action field (BUY EARLY/WATCH/LATE/AVOID)"""
        response = requests.get(f"{BASE_URL}/api/narrative-flow")
        data = response.json()
        narratives = data.get("narratives", [])
        
        valid_actions = ["BUY EARLY", "WATCH", "LATE", "AVOID"]
        for n in narratives:
            assert "action" in n, f"narrative missing 'action'"
            assert n["action"] in valid_actions, f"Invalid action: {n['action']}"
        
        actions_found = [n["action"] for n in narratives]
        print(f"PASS: All narratives have valid actions: {set(actions_found)}")
    
    # ─── TOKENS TESTS ────────────────────────────────────────
    
    def test_tokens_have_action_field(self):
        """tokens have action field (BUY/WATCH/LATE/AVOID)"""
        response = requests.get(f"{BASE_URL}/api/narrative-flow")
        data = response.json()
        tokens = data.get("tokens", [])
        
        valid_actions = ["BUY", "WATCH", "LATE", "AVOID"]
        for t in tokens:
            assert "action" in t, f"token missing 'action'"
            assert t["action"] in valid_actions, f"Invalid token action: {t['action']}"
        
        print(f"PASS: All {len(tokens)} tokens have valid actions")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
