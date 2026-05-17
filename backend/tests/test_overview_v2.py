"""
Overview V2 Intelligence API Tests
Tests GET /api/overview endpoint for decision intelligence dashboard
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestOverviewV2API:
    """Tests for Overview V2 Decision Intelligence endpoint"""
    
    # --- Core Response Tests ---
    
    def test_overview_returns_ok_true(self):
        """API returns ok:true with full response structure"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT"})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok:true"
        assert data.get("asset") == "BTCUSDT", "Expected asset BTCUSDT"
        assert "timestamp" in data, "Expected timestamp"
        
        # Verify all main sections present
        assert "decision" in data, "Expected decision section"
        assert "core" in data, "Expected core section"
        assert "signals" in data, "Expected signals section"
        assert "macro" in data, "Expected macro section"
        assert "risk" in data, "Expected risk section"
        assert "hybrid" in data, "Expected hybrid section"
        assert "alerts" in data, "Expected alerts section"
    
    # --- Decision Tests ---
    
    def test_decision_action_valid_enum(self):
        """decision.action is one of BUY, SELL, HOLD, NO_TRADE"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT"})
        assert response.status_code == 200
        
        data = response.json()
        action = data.get("decision", {}).get("action")
        valid_actions = ["BUY", "SELL", "HOLD", "NO_TRADE"]
        assert action in valid_actions, f"action '{action}' not in {valid_actions}"
    
    def test_decision_size_mult_range(self):
        """decision.sizeMult is number 0.0 to 1.2"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT"})
        assert response.status_code == 200
        
        data = response.json()
        size_mult = data.get("decision", {}).get("sizeMult")
        assert isinstance(size_mult, (int, float)), f"sizeMult should be number, got {type(size_mult)}"
        assert 0.0 <= size_mult <= 1.2, f"sizeMult {size_mult} out of range [0.0, 1.2]"
    
    def test_decision_mode_valid_enum(self):
        """decision.mode is DEFENSIVE, NEUTRAL, or AGGRESSIVE"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT"})
        assert response.status_code == 200
        
        data = response.json()
        mode = data.get("decision", {}).get("mode")
        valid_modes = ["DEFENSIVE", "NEUTRAL", "AGGRESSIVE"]
        assert mode in valid_modes, f"mode '{mode}' not in {valid_modes}"
    
    def test_decision_gates_is_array(self):
        """decision.gates is array of strings"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT"})
        assert response.status_code == 200
        
        data = response.json()
        gates = data.get("decision", {}).get("gates")
        assert isinstance(gates, list), f"gates should be list, got {type(gates)}"
        for gate in gates:
            assert isinstance(gate, str), f"gate '{gate}' should be string"
    
    def test_decision_reasons_structure(self):
        """decision.reasons has layer and text fields"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT"})
        assert response.status_code == 200
        
        data = response.json()
        reasons = data.get("decision", {}).get("reasons", [])
        assert isinstance(reasons, list), "reasons should be list"
        assert len(reasons) > 0, "reasons should have at least one entry"
        
        for reason in reasons:
            assert "layer" in reason, f"reason missing 'layer' field: {reason}"
            assert "text" in reason, f"reason missing 'text' field: {reason}"
            assert isinstance(reason["layer"], str), "layer should be string"
            assert isinstance(reason["text"], str), "text should be string"
    
    def test_decision_confidence_in_range(self):
        """decision.confidence is 0-1"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT"})
        assert response.status_code == 200
        
        data = response.json()
        confidence = data.get("decision", {}).get("confidence")
        assert isinstance(confidence, (int, float)), "confidence should be number"
        assert 0 <= confidence <= 1, f"confidence {confidence} out of range [0, 1]"
    
    # --- Core Snapshot Tests ---
    
    def test_core_has_required_fields(self):
        """core has regime, regimeProb, bias, edgeScore, outcomes"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT"})
        assert response.status_code == 200
        
        data = response.json()
        core = data.get("core", {})
        
        assert "regime" in core, "core missing regime"
        assert "regimeProb" in core, "core missing regimeProb"
        assert "bias" in core, "core missing bias"
        assert "edgeScore" in core, "core missing edgeScore"
        assert "outcomes" in core, "core missing outcomes"
    
    def test_core_outcomes_structure(self):
        """core.outcomes has bull, base, bear fields"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT"})
        assert response.status_code == 200
        
        data = response.json()
        outcomes = data.get("core", {}).get("outcomes", {})
        
        assert "bull" in outcomes, "outcomes missing bull"
        assert "base" in outcomes, "outcomes missing base"
        assert "bear" in outcomes, "outcomes missing bear"
        
        # Sum should be ~1.0
        total = outcomes.get("bull", 0) + outcomes.get("base", 0) + outcomes.get("bear", 0)
        assert 0.9 <= total <= 1.1, f"outcomes sum {total} should be ~1.0"
    
    # --- Signals Summary Tests ---
    
    def test_signals_has_required_fields(self):
        """signals has executionScore, bias, activityMode, contributors, topEvents"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT"})
        assert response.status_code == 200
        
        data = response.json()
        signals = data.get("signals", {})
        
        assert "executionScore" in signals, "signals missing executionScore"
        assert "bias" in signals, "signals missing bias"
        assert "activityMode" in signals, "signals missing activityMode"
        assert "contributors" in signals, "signals missing contributors"
        assert "topEvents" in signals, "signals missing topEvents"
    
    def test_signals_top_events_have_source(self):
        """signals.topEvents have source field"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT"})
        assert response.status_code == 200
        
        data = response.json()
        top_events = data.get("signals", {}).get("topEvents", [])
        
        for event in top_events:
            assert "source" in event, f"topEvent missing 'source': {event}"
            assert "title" in event, f"topEvent missing 'title': {event}"
            assert "impact" in event, f"topEvent missing 'impact': {event}"
    
    # --- Macro Context Tests ---
    
    def test_macro_has_required_fields(self):
        """macro has regime, riskOffProb, macroMult, fearGreed, blocked"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT"})
        assert response.status_code == 200
        
        data = response.json()
        macro = data.get("macro", {})
        
        assert "regime" in macro, "macro missing regime"
        assert "riskOffProb" in macro, "macro missing riskOffProb"
        assert "macroMult" in macro, "macro missing macroMult"
        assert "fearGreed" in macro, "macro missing fearGreed"
        assert "blocked" in macro, "macro missing blocked"
    
    def test_macro_risk_off_prob_in_range(self):
        """macro.riskOffProb is 0-1"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT"})
        assert response.status_code == 200
        
        data = response.json()
        risk_off = data.get("macro", {}).get("riskOffProb")
        assert isinstance(risk_off, (int, float)), "riskOffProb should be number"
        assert 0 <= risk_off <= 1, f"riskOffProb {risk_off} out of range [0, 1]"
    
    # --- Risk Split Tests ---
    
    def test_risk_has_structural_tactical_total(self):
        """risk has structural, tactical, total (0-100)"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT"})
        assert response.status_code == 200
        
        data = response.json()
        risk = data.get("risk", {})
        
        assert "structural" in risk, "risk missing structural"
        assert "tactical" in risk, "risk missing tactical"
        assert "total" in risk, "risk missing total"
        
        # Values should be 0-100
        structural = risk.get("structural")
        tactical = risk.get("tactical")
        total = risk.get("total")
        
        assert 0 <= structural <= 100, f"structural {structural} out of range"
        assert 0 <= tactical <= 100, f"tactical {tactical} out of range"
        assert 0 <= total <= 100, f"total {total} out of range"
    
    # --- Hybrid Tests ---
    
    def test_hybrid_has_required_fields(self):
        """hybrid has beta, correlation, spillover, hybridScore, interpretation"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT"})
        assert response.status_code == 200
        
        data = response.json()
        hybrid = data.get("hybrid", {})
        
        assert "beta" in hybrid, "hybrid missing beta"
        assert "correlation" in hybrid, "hybrid missing correlation"
        assert "spillover" in hybrid, "hybrid missing spillover"
        assert "hybridScore" in hybrid, "hybrid missing hybridScore"
        assert "interpretation" in hybrid, "hybrid missing interpretation"
    
    # --- Alerts Tests ---
    
    def test_alerts_has_required_fields(self):
        """alerts has active count, highPriority count, triggers array"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT"})
        assert response.status_code == 200
        
        data = response.json()
        alerts = data.get("alerts", {})
        
        assert "active" in alerts, "alerts missing active"
        assert "highPriority" in alerts, "alerts missing highPriority"
        assert "triggers" in alerts, "alerts missing triggers"
        
        assert isinstance(alerts["active"], int), "active should be int"
        assert isinstance(alerts["highPriority"], int), "highPriority should be int"
        assert isinstance(alerts["triggers"], list), "triggers should be list"
    
    # --- Consistency Tests ---
    
    def test_no_trade_has_zero_size(self):
        """If action is NO_TRADE, sizeMult should be 0"""
        response = requests.get(f"{BASE_URL}/api/overview", params={"asset": "BTCUSDT"})
        assert response.status_code == 200
        
        data = response.json()
        decision = data.get("decision", {})
        
        if decision.get("action") == "NO_TRADE":
            assert decision.get("sizeMult") == 0.0, "NO_TRADE should have sizeMult=0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
