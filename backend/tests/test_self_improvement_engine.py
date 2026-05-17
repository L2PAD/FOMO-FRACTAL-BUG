"""
Self-Improvement Engine API Tests (Mega Sprint 3)

Tests for:
- GET /api/self-improvement/overview - Full dashboard data
- GET /api/self-improvement/patterns - Active pattern findings
- GET /api/self-improvement/drift - Drift states
- GET /api/self-improvement/params - Active model parameters
- GET /api/self-improvement/proposals - Tuning proposals
- GET /api/self-improvement/experiments - A/B experiments
- POST /api/self-improvement/seed-defaults - Seed 9 default parameters
- POST /api/self-improvement/scan - Trigger pattern scan + drift check
- POST /api/self-improvement/propose - Trigger proposal generation
- POST /api/self-improvement/approve - Approve proposal → start experiment
- POST /api/self-improvement/reject - Reject proposal
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestSelfImprovementOverview:
    """Tests for GET /api/self-improvement/overview endpoint"""
    
    def test_overview_returns_ok(self):
        """Overview endpoint returns ok=true with all required fields"""
        response = requests.get(f"{BASE_URL}/api/self-improvement/overview")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true"
        
        # Verify summary object exists with required fields
        assert "summary" in data, "Missing summary field"
        summary = data["summary"]
        assert "active_patterns" in summary, "Missing active_patterns in summary"
        assert "degrading_metrics" in summary, "Missing degrading_metrics in summary"
        assert "pending_proposals" in summary, "Missing pending_proposals in summary"
        assert "running_experiments" in summary, "Missing running_experiments in summary"
        assert "tunable_params_count" in summary, "Missing tunable_params_count in summary"
        assert "active_params_count" in summary, "Missing active_params_count in summary"
        
        # Verify arrays exist
        assert "patterns" in data, "Missing patterns array"
        assert "drift_states" in data, "Missing drift_states array"
        assert "active_params" in data, "Missing active_params array"
        assert "proposals" in data, "Missing proposals array"
        assert "experiments" in data, "Missing experiments array"
        
        # Verify types
        assert isinstance(data["patterns"], list), "patterns should be a list"
        assert isinstance(data["drift_states"], list), "drift_states should be a list"
        assert isinstance(data["active_params"], list), "active_params should be a list"
        assert isinstance(data["proposals"], list), "proposals should be a list"
        assert isinstance(data["experiments"], list), "experiments should be a list"
        
        print(f"✓ Overview: {summary}")


class TestSelfImprovementPatterns:
    """Tests for GET /api/self-improvement/patterns endpoint"""
    
    def test_patterns_returns_ok(self):
        """Patterns endpoint returns ok=true with active and history arrays"""
        response = requests.get(f"{BASE_URL}/api/self-improvement/patterns")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true"
        assert "active" in data, "Missing active array"
        assert "history" in data, "Missing history array"
        assert isinstance(data["active"], list), "active should be a list"
        assert isinstance(data["history"], list), "history should be a list"
        
        print(f"✓ Patterns: active={len(data['active'])}, history={len(data['history'])}")


class TestSelfImprovementDrift:
    """Tests for GET /api/self-improvement/drift endpoint"""
    
    def test_drift_returns_ok(self):
        """Drift endpoint returns ok=true with states and degrading_count"""
        response = requests.get(f"{BASE_URL}/api/self-improvement/drift")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true"
        assert "states" in data, "Missing states array"
        assert "degrading_count" in data, "Missing degrading_count"
        assert isinstance(data["states"], list), "states should be a list"
        assert isinstance(data["degrading_count"], int), "degrading_count should be an int"
        
        print(f"✓ Drift: states={len(data['states'])}, degrading_count={data['degrading_count']}")


class TestSelfImprovementParams:
    """Tests for GET /api/self-improvement/params endpoint"""
    
    def test_params_returns_ok(self):
        """Params endpoint returns ok=true with active array and specs object"""
        response = requests.get(f"{BASE_URL}/api/self-improvement/params")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true"
        assert "active" in data, "Missing active array"
        assert "specs" in data, "Missing specs object"
        assert isinstance(data["active"], list), "active should be a list"
        assert isinstance(data["specs"], dict), "specs should be a dict"
        
        # Verify specs contains expected tunable params
        expected_params = [
            "fair_prob.time_decay_weight",
            "fair_prob.liquidity_weight",
            "fair_prob.structure_weight",
            "fair_prob.volatility_weight",
            "confidence.buy_now_threshold",
            "confidence.buy_threshold",
            "sizing.low_liquidity_cap",
            "sizing.short_expiry_cap",
            "sizing.high_volatility_cap",
        ]
        for param in expected_params:
            assert param in data["specs"], f"Missing param spec: {param}"
        
        print(f"✓ Params: active={len(data['active'])}, specs={len(data['specs'])} params")


class TestSelfImprovementProposals:
    """Tests for GET /api/self-improvement/proposals endpoint"""
    
    def test_proposals_returns_ok(self):
        """Proposals endpoint returns ok=true with proposals array"""
        response = requests.get(f"{BASE_URL}/api/self-improvement/proposals")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true"
        assert "proposals" in data, "Missing proposals array"
        assert isinstance(data["proposals"], list), "proposals should be a list"
        
        print(f"✓ Proposals: count={len(data['proposals'])}")
    
    def test_proposals_with_status_filter(self):
        """Proposals endpoint accepts status query parameter"""
        response = requests.get(f"{BASE_URL}/api/self-improvement/proposals?status=SUGGESTED")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true"
        
        print(f"✓ Proposals (SUGGESTED filter): count={len(data.get('proposals', []))}")


class TestSelfImprovementExperiments:
    """Tests for GET /api/self-improvement/experiments endpoint"""
    
    def test_experiments_returns_ok(self):
        """Experiments endpoint returns ok=true with experiments array"""
        response = requests.get(f"{BASE_URL}/api/self-improvement/experiments")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true"
        assert "experiments" in data, "Missing experiments array"
        assert isinstance(data["experiments"], list), "experiments should be a list"
        
        print(f"✓ Experiments: count={len(data['experiments'])}")
    
    def test_experiments_with_status_filter(self):
        """Experiments endpoint accepts status query parameter"""
        response = requests.get(f"{BASE_URL}/api/self-improvement/experiments?status=RUNNING")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true"
        
        print(f"✓ Experiments (RUNNING filter): count={len(data.get('experiments', []))}")


class TestSelfImprovementSeedDefaults:
    """Tests for POST /api/self-improvement/seed-defaults endpoint"""
    
    def test_seed_defaults_is_idempotent(self):
        """Seed-defaults endpoint seeds 9 default parameters (idempotent)"""
        # First call
        response1 = requests.post(f"{BASE_URL}/api/self-improvement/seed-defaults")
        assert response1.status_code == 200, f"Expected 200, got {response1.status_code}"
        
        data1 = response1.json()
        assert data1.get("ok") is True, "Expected ok=true"
        assert "seeded" in data1, "Missing seeded count"
        assert "total" in data1, "Missing total count"
        assert data1["total"] == 9, f"Expected 9 total params, got {data1['total']}"
        
        first_seeded = data1["seeded"]
        print(f"✓ Seed defaults (1st call): seeded={first_seeded}, total={data1['total']}")
        
        # Second call should be idempotent (seeded=0 if already seeded)
        response2 = requests.post(f"{BASE_URL}/api/self-improvement/seed-defaults")
        assert response2.status_code == 200, f"Expected 200, got {response2.status_code}"
        
        data2 = response2.json()
        assert data2.get("ok") is True, "Expected ok=true"
        assert data2["seeded"] == 0, f"Expected 0 seeded on 2nd call (idempotent), got {data2['seeded']}"
        
        print(f"✓ Seed defaults (2nd call - idempotent): seeded={data2['seeded']}")
    
    def test_params_after_seeding(self):
        """After seeding, params endpoint should return 9 active params"""
        # Ensure seeded
        requests.post(f"{BASE_URL}/api/self-improvement/seed-defaults")
        
        response = requests.get(f"{BASE_URL}/api/self-improvement/params")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["active"]) >= 9, f"Expected at least 9 active params, got {len(data['active'])}"
        
        # Verify param structure
        for param in data["active"]:
            assert "param_key" in param, "Missing param_key"
            assert "value" in param, "Missing value"
            assert "source" in param, "Missing source"
        
        print(f"✓ Params after seeding: {len(data['active'])} active params")


class TestSelfImprovementScan:
    """Tests for POST /api/self-improvement/scan endpoint"""
    
    def test_scan_returns_ok(self):
        """Scan endpoint triggers pattern scan + drift check"""
        response = requests.post(f"{BASE_URL}/api/self-improvement/scan")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true"
        assert "patterns_found" in data, "Missing patterns_found"
        assert "drift_states_updated" in data, "Missing drift_states_updated"
        
        # With no forecast_results data, expect 0 patterns (graceful handling)
        print(f"✓ Scan: patterns_found={data['patterns_found']}, drift_states_updated={data['drift_states_updated']}")


class TestSelfImprovementPropose:
    """Tests for POST /api/self-improvement/propose endpoint"""
    
    def test_propose_returns_ok(self):
        """Propose endpoint triggers proposal generation"""
        response = requests.post(f"{BASE_URL}/api/self-improvement/propose")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true"
        assert "total_generated" in data, "Missing total_generated"
        assert "suggested" in data, "Missing suggested count"
        assert "rejected_by_governance" in data, "Missing rejected_by_governance count"
        assert "proposals" in data, "Missing proposals array"
        
        # With no patterns/drift, expect 0 proposals (graceful handling)
        print(f"✓ Propose: total={data['total_generated']}, suggested={data['suggested']}, rejected={data['rejected_by_governance']}")


class TestSelfImprovementApproveReject:
    """Tests for POST /api/self-improvement/approve and /reject endpoints"""
    
    def test_approve_invalid_proposal(self):
        """Approve with invalid proposal_id returns error"""
        response = requests.post(
            f"{BASE_URL}/api/self-improvement/approve",
            json={"proposal_id": "invalid_proposal_id_12345"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is False, "Expected ok=false for invalid proposal"
        assert "error" in data, "Expected error message"
        assert "not found" in data["error"].lower(), f"Expected 'not found' error, got: {data['error']}"
        
        print(f"✓ Approve invalid: {data['error']}")
    
    def test_reject_invalid_proposal(self):
        """Reject with invalid proposal_id returns error"""
        response = requests.post(
            f"{BASE_URL}/api/self-improvement/reject",
            json={"proposal_id": "invalid_proposal_id_12345", "reason": "Test rejection"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is False, "Expected ok=false for invalid proposal"
        assert "error" in data, "Expected error message"
        assert "not found" in data["error"].lower(), f"Expected 'not found' error, got: {data['error']}"
        
        print(f"✓ Reject invalid: {data['error']}")


class TestSelfImprovementIntegration:
    """Integration tests for the full self-improvement workflow"""
    
    def test_full_workflow_overview_to_params(self):
        """Test full workflow: seed → overview → params verification"""
        # 1. Seed defaults
        seed_resp = requests.post(f"{BASE_URL}/api/self-improvement/seed-defaults")
        assert seed_resp.status_code == 200
        
        # 2. Get overview
        overview_resp = requests.get(f"{BASE_URL}/api/self-improvement/overview")
        assert overview_resp.status_code == 200
        overview = overview_resp.json()
        
        # 3. Verify active_params_count matches
        params_resp = requests.get(f"{BASE_URL}/api/self-improvement/params")
        assert params_resp.status_code == 200
        params = params_resp.json()
        
        assert overview["summary"]["active_params_count"] == len(params["active"]), \
            "Overview active_params_count should match params active count"
        
        # 4. Verify tunable_params_count matches specs
        assert overview["summary"]["tunable_params_count"] == len(params["specs"]), \
            "Overview tunable_params_count should match specs count"
        
        print(f"✓ Integration: active_params={overview['summary']['active_params_count']}, tunable={overview['summary']['tunable_params_count']}")
    
    def test_scan_then_propose_workflow(self):
        """Test scan → propose workflow"""
        # 1. Run scan
        scan_resp = requests.post(f"{BASE_URL}/api/self-improvement/scan")
        assert scan_resp.status_code == 200
        scan_data = scan_resp.json()
        assert scan_data.get("ok") is True
        
        # 2. Run propose
        propose_resp = requests.post(f"{BASE_URL}/api/self-improvement/propose")
        assert propose_resp.status_code == 200
        propose_data = propose_resp.json()
        assert propose_data.get("ok") is True
        
        # 3. Verify proposals endpoint reflects any new proposals
        proposals_resp = requests.get(f"{BASE_URL}/api/self-improvement/proposals")
        assert proposals_resp.status_code == 200
        
        print(f"✓ Scan→Propose workflow: patterns={scan_data['patterns_found']}, proposals={propose_data['total_generated']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
