"""
Sprint Test: Opportunity & Operational Intelligence
=====================================================
Tests for:
  - /api/engine/context — playbook + market_memory integration
  - /api/os/state — ranked opportunities + market_risk
  - /api/os/opportunities — sorted by rank_score desc
  - Alert relative time format
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL')


class TestEngineContext:
    """Test /api/engine/context endpoint — playbook + market_memory"""
    
    def test_engine_context_returns_ok(self):
        """Check that engine context returns ok: true"""
        response = requests.get(f"{BASE_URL}/api/engine/context")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data.get('ok')}"
        print("PASS: /api/engine/context returns ok: true")
    
    def test_engine_context_has_playbook(self):
        """Check playbook object with all required sections"""
        response = requests.get(f"{BASE_URL}/api/engine/context")
        data = response.json()
        assert data.get("ok") is True
        
        playbook = data.get("playbook")
        assert playbook is not None, "playbook field is missing"
        
        # Check all 5 sections
        assert "bias" in playbook, "playbook.bias missing"
        assert "confirmation" in playbook, "playbook.confirmation missing"
        assert "invalidation" in playbook, "playbook.invalidation missing"
        assert "targets" in playbook, "playbook.targets missing"
        assert "risk_note" in playbook, "playbook.risk_note missing"
        
        # Validate bias is a valid value
        valid_biases = ["bullish", "cautiously bullish", "bearish", "cautiously bearish", "neutral"]
        assert playbook["bias"] in valid_biases, f"Invalid bias: {playbook['bias']}"
        
        # Validate confirmation is a list
        assert isinstance(playbook["confirmation"], list), "confirmation should be a list"
        
        # Validate invalidation is a list
        assert isinstance(playbook["invalidation"], list), "invalidation should be a list"
        
        # Validate targets is a list with expected structure
        assert isinstance(playbook["targets"], list), "targets should be a list"
        if playbook["targets"]:
            t = playbook["targets"][0]
            assert "type" in t, "target.type missing"
            assert "reason" in t, "target.reason missing"
            assert "direction" in t, "target.direction missing"
        
        # Validate risk_note is a string
        assert isinstance(playbook["risk_note"], str), "risk_note should be a string"
        
        print(f"PASS: playbook has all 5 sections: bias={playbook['bias']}")
    
    def test_engine_context_has_market_memory(self):
        """Check market_memory object with required fields"""
        response = requests.get(f"{BASE_URL}/api/engine/context")
        data = response.json()
        assert data.get("ok") is True
        
        memory = data.get("market_memory")
        assert memory is not None, "market_memory field is missing"
        
        # Check required fields
        assert "setup" in memory, "market_memory.setup missing"
        assert "sample_size" in memory, "market_memory.sample_size missing"
        assert "success_rate" in memory, "market_memory.success_rate missing"
        assert "failure_rate" in memory, "market_memory.failure_rate missing"
        assert "avg_duration" in memory, "market_memory.avg_duration missing"
        assert "by_regime" in memory, "market_memory.by_regime missing"
        
        # Validate types
        assert isinstance(memory["sample_size"], int), "sample_size should be int"
        assert isinstance(memory["success_rate"], (int, float)), "success_rate should be numeric"
        assert isinstance(memory["failure_rate"], (int, float)), "failure_rate should be numeric"
        assert isinstance(memory["by_regime"], dict), "by_regime should be dict"
        
        print(f"PASS: market_memory present — setup={memory['setup']}, sample_size={memory['sample_size']}")
    
    def test_engine_context_has_alerts(self):
        """Check alerts array is present"""
        response = requests.get(f"{BASE_URL}/api/engine/context")
        data = response.json()
        assert data.get("ok") is True
        
        alerts = data.get("alerts")
        assert alerts is not None, "alerts field is missing"
        assert isinstance(alerts, list), "alerts should be a list"
        
        print(f"PASS: alerts present — count={len(alerts)}")
    
    def test_engine_context_has_core_fields(self):
        """Verify core engine fields are still present"""
        response = requests.get(f"{BASE_URL}/api/engine/context")
        data = response.json()
        assert data.get("ok") is True
        
        # Core fields
        assert "decision" in data, "decision missing"
        assert "confidence" in data, "confidence missing"
        assert "scores" in data, "scores missing"
        assert "regime_engine" in data, "regime_engine missing"
        assert "setup_engine" in data, "setup_engine missing"
        assert "probability_layer" in data, "probability_layer missing"
        assert "flow_engine" in data, "flow_engine missing"
        assert "liquidity_map" in data, "liquidity_map missing"
        assert "narrative" in data, "narrative missing"
        assert "risk_engine" in data, "risk_engine missing"
        
        print("PASS: All core engine fields present")


class TestOSState:
    """Test /api/os/state endpoint — opportunities + risk + alerts"""
    
    def test_os_state_returns_ok(self):
        """Check that OS state returns ok: true"""
        response = requests.get(f"{BASE_URL}/api/os/state")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data.get('ok')}"
        print("PASS: /api/os/state returns ok: true")
    
    def test_os_state_has_opportunities_with_rank_score(self):
        """Check opportunities array has rank_score for ranking"""
        response = requests.get(f"{BASE_URL}/api/os/state")
        data = response.json()
        assert data.get("ok") is True
        
        opportunities = data.get("opportunities")
        assert opportunities is not None, "opportunities field is missing"
        assert isinstance(opportunities, list), "opportunities should be a list"
        
        if opportunities:
            for i, opp in enumerate(opportunities):
                assert "rank_score" in opp, f"opportunity[{i}] missing rank_score"
                assert "setup" in opp, f"opportunity[{i}] missing setup"
                assert "confidence" in opp, f"opportunity[{i}] missing confidence"
                assert "probability" in opp, f"opportunity[{i}] missing probability"
                
                # Validate rank_score is numeric
                assert isinstance(opp["rank_score"], (int, float)), "rank_score should be numeric"
        
        print(f"PASS: opportunities present with rank_score — count={len(opportunities)}")
    
    def test_os_state_has_market_risk(self):
        """Check market_risk object with risk_score and risk_level"""
        response = requests.get(f"{BASE_URL}/api/os/state")
        data = response.json()
        assert data.get("ok") is True
        
        risk = data.get("market_risk")
        assert risk is not None, "market_risk field is missing"
        
        # Required fields
        assert "risk_score" in risk, "market_risk.risk_score missing"
        assert "risk_level" in risk, "market_risk.risk_level missing"
        
        # Validate risk_score is 0-100
        assert 0 <= risk["risk_score"] <= 100, f"risk_score out of range: {risk['risk_score']}"
        
        # Validate risk_level is one of expected values
        valid_levels = ["LOW", "MODERATE", "ELEVATED", "HIGH"]
        assert risk["risk_level"] in valid_levels, f"Invalid risk_level: {risk['risk_level']}"
        
        print(f"PASS: market_risk present — score={risk['risk_score']}, level={risk['risk_level']}")
    
    def test_os_state_has_all_blocks(self):
        """Check all required OS blocks are present"""
        response = requests.get(f"{BASE_URL}/api/os/state")
        data = response.json()
        assert data.get("ok") is True
        
        required_blocks = ["market_state", "market_risk", "opportunities", "actor_pressure", "liquidity_targets", "alerts"]
        for block in required_blocks:
            assert block in data, f"{block} is missing from OS state"
        
        print(f"PASS: All required blocks present: {required_blocks}")
    
    def test_os_state_market_state_structure(self):
        """Check market_state has all required fields"""
        response = requests.get(f"{BASE_URL}/api/os/state")
        data = response.json()
        assert data.get("ok") is True
        
        market_state = data.get("market_state")
        assert market_state is not None, "market_state is missing"
        
        expected_fields = ["regime", "setup", "decision", "flow_state", "composite"]
        for field in expected_fields:
            assert field in market_state, f"market_state.{field} missing"
        
        print(f"PASS: market_state has all fields — regime={market_state.get('regime')}, decision={market_state.get('decision')}")


class TestOSOpportunities:
    """Test /api/os/opportunities endpoint — ranked list"""
    
    def test_os_opportunities_returns_ok(self):
        """Check that opportunities endpoint returns ok: true"""
        response = requests.get(f"{BASE_URL}/api/os/opportunities")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data.get('ok')}"
        print("PASS: /api/os/opportunities returns ok: true")
    
    def test_os_opportunities_sorted_by_rank_score_desc(self):
        """Verify opportunities are sorted by rank_score descending"""
        response = requests.get(f"{BASE_URL}/api/os/opportunities")
        data = response.json()
        assert data.get("ok") is True
        
        opportunities = data.get("opportunities", [])
        if len(opportunities) >= 2:
            rank_scores = [opp["rank_score"] for opp in opportunities]
            # Verify descending order
            for i in range(len(rank_scores) - 1):
                assert rank_scores[i] >= rank_scores[i + 1], \
                    f"Opportunities not sorted desc: {rank_scores[i]} < {rank_scores[i + 1]}"
        
        print(f"PASS: opportunities sorted by rank_score desc — {[o.get('rank_score') for o in opportunities[:5]]}")
    
    def test_os_opportunities_has_count(self):
        """Check that count field is present and matches array length"""
        response = requests.get(f"{BASE_URL}/api/os/opportunities")
        data = response.json()
        assert data.get("ok") is True
        
        assert "count" in data, "count field missing"
        opportunities = data.get("opportunities", [])
        assert data["count"] == len(opportunities), f"count mismatch: {data['count']} vs {len(opportunities)}"
        
        print(f"PASS: count={data['count']} matches opportunities length")


class TestAlertFormat:
    """Test alerts use relative time format"""
    
    def test_alerts_have_timestamp(self):
        """Check alerts have timestamp field for relative time calculation"""
        response = requests.get(f"{BASE_URL}/api/engine/alerts?limit=10")
        data = response.json()
        assert data.get("ok") is True
        
        alerts = data.get("alerts", [])
        if alerts:
            for i, alert in enumerate(alerts[:5]):
                assert "timestamp" in alert, f"alert[{i}] missing timestamp"
                assert "message" in alert, f"alert[{i}] missing message"
                assert "severity" in alert, f"alert[{i}] missing severity"
                
                # Validate timestamp is ISO format
                ts = alert["timestamp"]
                assert "T" in ts, f"timestamp not ISO format: {ts}"
        
        print(f"PASS: alerts have timestamp for relative time — count={len(alerts)}")


class TestDataConsistency:
    """Test data consistency between endpoints"""
    
    def test_engine_and_os_risk_consistency(self):
        """Check that risk data is consistent between engine and OS"""
        engine_resp = requests.get(f"{BASE_URL}/api/engine/context")
        os_resp = requests.get(f"{BASE_URL}/api/os/state")
        
        engine_data = engine_resp.json()
        os_data = os_resp.json()
        
        assert engine_data.get("ok") is True
        assert os_data.get("ok") is True
        
        engine_risk = engine_data.get("risk_engine", {})
        os_risk = os_data.get("market_risk", {})
        
        # Risk scores should be the same
        engine_score = engine_risk.get("risk_score")
        os_score = os_risk.get("risk_score")
        
        if engine_score is not None and os_score is not None:
            assert engine_score == os_score, f"Risk scores differ: engine={engine_score}, os={os_score}"
        
        print(f"PASS: risk data consistent — score={os_score}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
