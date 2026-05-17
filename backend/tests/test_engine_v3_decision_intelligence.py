"""
Engine V3 — Decision Intelligence Layer Tests
==============================================
Testing: Decision Gates, Confidence Engine, Setup Classifier, Risk Engine, Evidence Engine, Diagnostics
Sprint: Engine V3 complete rewrite (iteration_238)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')


class TestEngineV3Endpoint:
    """Test GET /api/engine/v3/context endpoint returns valid response"""
    
    def test_endpoint_returns_200_with_ok_true(self):
        """Basic endpoint health: Returns 200 with ok=true"""
        response = requests.get(f"{BASE_URL}/api/engine/v3/context?window=30d", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true in response"
    
    def test_decision_field_valid_values(self):
        """Decision must be one of STRONG_BUY/BUY/WATCH/REDUCE/AVOID/NO_DECISION"""
        response = requests.get(f"{BASE_URL}/api/engine/v3/context?window=30d", timeout=30)
        data = response.json()
        valid_decisions = ["STRONG_BUY", "BUY", "WATCH", "REDUCE", "AVOID", "NO_DECISION"]
        assert data.get("decision") in valid_decisions, f"Invalid decision: {data.get('decision')}"


class TestEngineV3Confidence:
    """Test confidence engine output structure"""
    
    def test_confidence_has_level(self):
        """Confidence must have level: HIGH/MODERATE/LOW/INSUFFICIENT"""
        response = requests.get(f"{BASE_URL}/api/engine/v3/context?window=30d", timeout=30)
        data = response.json()
        confidence = data.get("confidence", {})
        valid_levels = ["HIGH", "MODERATE", "LOW", "INSUFFICIENT"]
        assert confidence.get("level") in valid_levels, f"Invalid confidence level: {confidence.get('level')}"
    
    def test_confidence_has_score_0_to_100(self):
        """Confidence score must be 0-100"""
        response = requests.get(f"{BASE_URL}/api/engine/v3/context?window=30d", timeout=30)
        data = response.json()
        confidence = data.get("confidence", {})
        score = confidence.get("score")
        assert isinstance(score, (int, float)), f"Score should be numeric, got {type(score)}"
        assert 0 <= score <= 100, f"Score {score} not in 0-100 range"
    
    def test_confidence_has_factors(self):
        """Confidence must have factors dict"""
        response = requests.get(f"{BASE_URL}/api/engine/v3/context?window=30d", timeout=30)
        data = response.json()
        confidence = data.get("confidence", {})
        assert "factors" in confidence, "Missing 'factors' in confidence"
        assert isinstance(confidence["factors"], dict), "factors should be dict"


class TestEngineV3Setup:
    """Test setup classifier output"""
    
    def test_setup_has_type(self):
        """Setup must have type field"""
        response = requests.get(f"{BASE_URL}/api/engine/v3/context?window=30d", timeout=30)
        data = response.json()
        setup = data.get("setup", {})
        assert "type" in setup, "Missing 'type' in setup"
        assert isinstance(setup["type"], str), "setup.type should be string"
    
    def test_setup_has_bias(self):
        """Setup must have bias field"""
        response = requests.get(f"{BASE_URL}/api/engine/v3/context?window=30d", timeout=30)
        data = response.json()
        setup = data.get("setup", {})
        assert "bias" in setup, "Missing 'bias' in setup"
    
    def test_setup_has_description(self):
        """Setup must have description field"""
        response = requests.get(f"{BASE_URL}/api/engine/v3/context?window=30d", timeout=30)
        data = response.json()
        setup = data.get("setup", {})
        assert "description" in setup, "Missing 'description' in setup"
        assert isinstance(setup["description"], str), "setup.description should be string"


class TestEngineV3WindowAndScores:
    """Test window and scores fields"""
    
    def test_window_is_non_empty_string(self):
        """Window should be non-empty string like '2-8h'"""
        response = requests.get(f"{BASE_URL}/api/engine/v3/context?window=30d", timeout=30)
        data = response.json()
        window = data.get("window")
        assert isinstance(window, str), f"Window should be string, got {type(window)}"
        assert len(window) > 0, "Window should not be empty"
    
    def test_scores_has_all_fields(self):
        """Scores must have composite, smart_money, cex, token, wallet"""
        response = requests.get(f"{BASE_URL}/api/engine/v3/context?window=30d", timeout=30)
        data = response.json()
        scores = data.get("scores", {})
        required_fields = ["composite", "smart_money", "cex", "token", "wallet"]
        for field in required_fields:
            assert field in scores, f"Missing '{field}' in scores"
    
    def test_scores_all_in_0_100_range(self):
        """All scores must be in 0-100 range"""
        response = requests.get(f"{BASE_URL}/api/engine/v3/context?window=30d", timeout=30)
        data = response.json()
        scores = data.get("scores", {})
        for field in ["composite", "smart_money", "cex", "token", "wallet"]:
            score = scores.get(field)
            if score is not None:
                assert 0 <= score <= 100, f"Score {field}={score} not in 0-100 range"


class TestEngineV3Gates:
    """Test Decision Gates structure"""
    
    def test_gates_has_evidence(self):
        """Gates must have evidence gate with status"""
        response = requests.get(f"{BASE_URL}/api/engine/v3/context?window=30d", timeout=30)
        data = response.json()
        gates = data.get("gates", {})
        evidence = gates.get("evidence", {})
        assert "status" in evidence, "Missing 'status' in evidence gate"
        assert evidence["status"] in ["PASS", "WEAK", "FAIL"], f"Invalid evidence status: {evidence['status']}"
    
    def test_gates_has_risk(self):
        """Gates must have risk gate with status LOW/MEDIUM/HIGH"""
        response = requests.get(f"{BASE_URL}/api/engine/v3/context?window=30d", timeout=30)
        data = response.json()
        gates = data.get("gates", {})
        risk = gates.get("risk", {})
        assert "status" in risk, "Missing 'status' in risk gate"
        assert risk["status"] in ["LOW", "MEDIUM", "HIGH"], f"Invalid risk status: {risk['status']}"
    
    def test_gates_has_coverage(self):
        """Gates must have coverage gate with status FULL/PARTIAL/LOW"""
        response = requests.get(f"{BASE_URL}/api/engine/v3/context?window=30d", timeout=30)
        data = response.json()
        gates = data.get("gates", {})
        coverage = gates.get("coverage", {})
        assert "status" in coverage, "Missing 'status' in coverage gate"
        assert coverage["status"] in ["FULL", "PARTIAL", "LOW"], f"Invalid coverage status: {coverage['status']}"


class TestEngineV3DriversAndRisks:
    """Test drivers and risks arrays"""
    
    def test_drivers_is_array_of_strings(self):
        """Drivers must be array of strings"""
        response = requests.get(f"{BASE_URL}/api/engine/v3/context?window=30d", timeout=30)
        data = response.json()
        drivers = data.get("drivers", [])
        assert isinstance(drivers, list), f"Drivers should be list, got {type(drivers)}"
        for d in drivers:
            assert isinstance(d, str), f"Driver item should be string, got {type(d)}"
    
    def test_risks_is_array_of_strings(self):
        """Risks must be array of strings"""
        response = requests.get(f"{BASE_URL}/api/engine/v3/context?window=30d", timeout=30)
        data = response.json()
        risks = data.get("risks", [])
        assert isinstance(risks, list), f"Risks should be list, got {type(risks)}"
        for r in risks:
            assert isinstance(r, str), f"Risk item should be string, got {type(r)}"


class TestEngineV3Evidence:
    """Test evidence array structure"""
    
    def test_evidence_is_array_of_objects(self):
        """Evidence must be array of objects"""
        response = requests.get(f"{BASE_URL}/api/engine/v3/context?window=30d", timeout=30)
        data = response.json()
        evidence = data.get("evidence", [])
        assert isinstance(evidence, list), f"Evidence should be list, got {type(evidence)}"
    
    def test_evidence_objects_have_required_fields(self):
        """Each evidence object must have module, summary, detail, signals"""
        response = requests.get(f"{BASE_URL}/api/engine/v3/context?window=30d", timeout=30)
        data = response.json()
        evidence = data.get("evidence", [])
        required_fields = ["module", "summary", "detail", "signals"]
        for i, ev in enumerate(evidence):
            for field in required_fields:
                assert field in ev, f"Evidence[{i}] missing '{field}'"


class TestEngineV3Diagnostics:
    """Test diagnostics structure"""
    
    def test_diagnostics_has_integrity(self):
        """Diagnostics must have integrity with confirmed/contradicted/neutral/agreement_rate"""
        response = requests.get(f"{BASE_URL}/api/engine/v3/context?window=30d", timeout=30)
        data = response.json()
        diagnostics = data.get("diagnostics", {})
        integrity = diagnostics.get("integrity", {})
        required_fields = ["confirmed", "contradicted", "neutral", "agreement_rate"]
        for field in required_fields:
            assert field in integrity, f"Missing '{field}' in diagnostics.integrity"
    
    def test_diagnostics_has_data_quality(self):
        """Diagnostics must have data_quality with coverage/risk_level"""
        response = requests.get(f"{BASE_URL}/api/engine/v3/context?window=30d", timeout=30)
        data = response.json()
        diagnostics = data.get("diagnostics", {})
        data_quality = diagnostics.get("data_quality", {})
        assert "coverage" in data_quality, "Missing 'coverage' in diagnostics.data_quality"
        assert "risk_level" in data_quality, "Missing 'risk_level' in diagnostics.data_quality"


class TestEngineV3ContextMatrix:
    """Test context matrix structure"""
    
    def test_context_matrix_has_four_modules(self):
        """Context matrix must have cex, smart_money, token, wallet"""
        response = requests.get(f"{BASE_URL}/api/engine/v3/context?window=30d", timeout=30)
        data = response.json()
        matrix = data.get("context_matrix", {})
        required_modules = ["cex", "smart_money", "token", "wallet"]
        for module in required_modules:
            assert module in matrix, f"Missing '{module}' in context_matrix"


class TestRegressionExistingEndpoints:
    """Regression: Ensure existing endpoints still work"""
    
    def test_market_context_still_works(self):
        """/api/onchain/market/context should still return 200"""
        response = requests.get(f"{BASE_URL}/api/onchain/market/context?window=30d", timeout=30)
        assert response.status_code == 200, f"Market context failed with {response.status_code}"
        data = response.json()
        assert data.get("ok") is True, "Market context should return ok=true"
    
    def test_cex_context_still_works(self):
        """/api/onchain/cex/context should still return 200"""
        response = requests.get(f"{BASE_URL}/api/onchain/cex/context?window=30d", timeout=30)
        assert response.status_code == 200, f"CEX context failed with {response.status_code}"
        data = response.json()
        assert data.get("ok") is True, "CEX context should return ok=true"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
