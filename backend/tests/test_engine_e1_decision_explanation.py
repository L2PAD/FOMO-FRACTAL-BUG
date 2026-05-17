"""
Engine E1 Decision Explanation Layer Tests
==========================================
Tests for the new decision_explanation, hero_summary, decision_integrity,
and signal impact tags features.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
# Use localhost for faster testing per agent note
LOCAL_URL = "http://localhost:8001"


class TestEngineE1DecisionExplanation:
    """Test decision_explanation structure with 4 arrays"""
    
    def test_engine_context_returns_ok(self):
        """Test that engine context endpoint returns ok response"""
        response = requests.get(f"{LOCAL_URL}/api/engine/context?window=30d", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") is True, "Expected ok to be True"
        print("PASS: Engine context returns ok=True")
    
    def test_decision_explanation_has_four_arrays(self):
        """Test that decision_explanation contains all 4 required arrays"""
        response = requests.get(f"{LOCAL_URL}/api/engine/context?window=30d", timeout=60)
        data = response.json()
        
        explanation = data.get("decision_explanation")
        assert explanation is not None, "decision_explanation missing from response"
        
        required_keys = ["bullish_drivers", "bearish_or_contradictions", "decision_blockers", "upgrade_triggers"]
        for key in required_keys:
            assert key in explanation, f"Missing key '{key}' in decision_explanation"
            assert isinstance(explanation[key], list), f"'{key}' should be a list"
        
        print(f"PASS: decision_explanation has 4 arrays: {required_keys}")
        print(f"  - bullish_drivers: {len(explanation['bullish_drivers'])} items")
        print(f"  - bearish_or_contradictions: {len(explanation['bearish_or_contradictions'])} items")
        print(f"  - decision_blockers: {len(explanation['decision_blockers'])} items")
        print(f"  - upgrade_triggers: {len(explanation['upgrade_triggers'])} items")
    
    def test_bullish_drivers_format(self):
        """Test that bullish_drivers array contains string items"""
        response = requests.get(f"{LOCAL_URL}/api/engine/context?window=30d", timeout=60)
        data = response.json()
        
        bullish = data.get("decision_explanation", {}).get("bullish_drivers", [])
        for i, item in enumerate(bullish):
            assert isinstance(item, str), f"bullish_drivers[{i}] should be string, got {type(item)}"
        
        print(f"PASS: bullish_drivers contains {len(bullish)} string items")
        if bullish:
            print(f"  Sample: {bullish[0]}")
    
    def test_bearish_or_contradictions_format(self):
        """Test that bearish_or_contradictions array contains string items"""
        response = requests.get(f"{LOCAL_URL}/api/engine/context?window=30d", timeout=60)
        data = response.json()
        
        bearish = data.get("decision_explanation", {}).get("bearish_or_contradictions", [])
        for i, item in enumerate(bearish):
            assert isinstance(item, str), f"bearish_or_contradictions[{i}] should be string, got {type(item)}"
        
        print(f"PASS: bearish_or_contradictions contains {len(bearish)} string items")
        if bearish:
            print(f"  Sample: {bearish[0]}")
    
    def test_decision_blockers_format(self):
        """Test that decision_blockers array contains string items"""
        response = requests.get(f"{LOCAL_URL}/api/engine/context?window=30d", timeout=60)
        data = response.json()
        
        blockers = data.get("decision_explanation", {}).get("decision_blockers", [])
        for i, item in enumerate(blockers):
            assert isinstance(item, str), f"decision_blockers[{i}] should be string, got {type(item)}"
        
        print(f"PASS: decision_blockers contains {len(blockers)} string items")
        if blockers:
            print(f"  Sample: {blockers[0]}")
    
    def test_upgrade_triggers_format(self):
        """Test that upgrade_triggers array contains string items"""
        response = requests.get(f"{LOCAL_URL}/api/engine/context?window=30d", timeout=60)
        data = response.json()
        
        triggers = data.get("decision_explanation", {}).get("upgrade_triggers", [])
        for i, item in enumerate(triggers):
            assert isinstance(item, str), f"upgrade_triggers[{i}] should be string, got {type(item)}"
        
        print(f"PASS: upgrade_triggers contains {len(triggers)} string items")
        if triggers:
            print(f"  Sample: {triggers[0]}")


class TestEngineE1HeroSummary:
    """Test hero_summary structure"""
    
    def test_hero_summary_has_required_fields(self):
        """Test that hero_summary contains reason, primary_blocker, primary_trigger"""
        response = requests.get(f"{LOCAL_URL}/api/engine/context?window=30d", timeout=60)
        data = response.json()
        
        hero = data.get("hero_summary")
        assert hero is not None, "hero_summary missing from response"
        
        # reason is always required
        assert "reason" in hero, "hero_summary missing 'reason'"
        assert isinstance(hero["reason"], str), "hero_summary.reason should be string"
        assert len(hero["reason"]) > 0, "hero_summary.reason should not be empty"
        
        # primary_blocker and primary_trigger can be null
        assert "primary_blocker" in hero, "hero_summary missing 'primary_blocker'"
        assert "primary_trigger" in hero, "hero_summary missing 'primary_trigger'"
        
        print(f"PASS: hero_summary has required fields")
        print(f"  - reason: {hero['reason'][:80]}...")
        print(f"  - primary_blocker: {hero.get('primary_blocker')}")
        print(f"  - primary_trigger: {hero.get('primary_trigger')}")


class TestEngineE1DecisionIntegrity:
    """Test decision_integrity structure"""
    
    def test_decision_integrity_has_required_fields(self):
        """Test that decision_integrity contains evidence, risk, coverage, primary_blocker"""
        response = requests.get(f"{LOCAL_URL}/api/engine/context?window=30d", timeout=60)
        data = response.json()
        
        integrity = data.get("decision_integrity")
        assert integrity is not None, "decision_integrity missing from response"
        
        required_keys = ["evidence", "risk", "coverage", "primary_blocker"]
        for key in required_keys:
            assert key in integrity, f"decision_integrity missing '{key}'"
        
        # Validate status values
        assert integrity["evidence"] in ["PASS", "WEAK", "FAIL"], f"Invalid evidence status: {integrity['evidence']}"
        assert integrity["risk"] in ["LOW", "MEDIUM", "HIGH"], f"Invalid risk status: {integrity['risk']}"
        assert integrity["coverage"] in ["FULL", "PARTIAL", "LOW"], f"Invalid coverage status: {integrity['coverage']}"
        
        print(f"PASS: decision_integrity has required fields")
        print(f"  - evidence: {integrity['evidence']}")
        print(f"  - risk: {integrity['risk']}")
        print(f"  - coverage: {integrity['coverage']}")
        print(f"  - primary_blocker: {integrity['primary_blocker']}")


class TestEngineE1SignalImpactTags:
    """Test signal impact tags"""
    
    def test_signals_have_impact_field(self):
        """Test that signals array items have 'impact' field"""
        response = requests.get(f"{LOCAL_URL}/api/engine/context?window=30d", timeout=60)
        data = response.json()
        
        signals = data.get("signals", [])
        assert len(signals) > 0, "Expected at least one signal"
        
        valid_impacts = {"bullish_driver", "contradiction", "discovery", "neutral"}
        impact_counts = {"bullish_driver": 0, "contradiction": 0, "discovery": 0, "neutral": 0}
        
        for i, sig in enumerate(signals):
            assert "impact" in sig, f"Signal {i} missing 'impact' field"
            assert sig["impact"] in valid_impacts, f"Signal {i} has invalid impact: {sig['impact']}"
            impact_counts[sig["impact"]] += 1
        
        print(f"PASS: All {len(signals)} signals have valid impact tags")
        print(f"  Impact distribution: {impact_counts}")
    
    def test_signals_structure_complete(self):
        """Test that signals have all expected fields"""
        response = requests.get(f"{LOCAL_URL}/api/engine/context?window=30d", timeout=60)
        data = response.json()
        
        signals = data.get("signals", [])
        required_fields = ["type", "source", "description", "confidence", "phase", "age_h", "impact"]
        
        for i, sig in enumerate(signals[:5]):  # Test first 5 signals
            for field in required_fields:
                assert field in sig, f"Signal {i} missing field '{field}'"
        
        print(f"PASS: Signals have complete structure with impact tags")


class TestEngineE1MetaVersion:
    """Test meta version"""
    
    def test_meta_version_is_41(self):
        """Test that meta.version = '4.1'"""
        response = requests.get(f"{LOCAL_URL}/api/engine/context?window=30d", timeout=60)
        data = response.json()
        
        meta = data.get("meta", {})
        assert "version" in meta, "meta.version missing"
        assert meta["version"] == "4.1", f"Expected meta.version='4.1', got '{meta['version']}'"
        
        print(f"PASS: meta.version = '{meta['version']}'")


class TestEngineE1ExternalEndpoint:
    """Test via external URL (may be slower)"""
    
    def test_external_endpoint_structure(self):
        """Test that external endpoint also has E1 features"""
        if not BASE_URL:
            pytest.skip("REACT_APP_BACKEND_URL not set")
        
        try:
            response = requests.get(f"{BASE_URL}/api/engine/context?window=30d", timeout=120)
            assert response.status_code == 200
            data = response.json()
            
            # Verify key E1 fields exist
            assert "decision_explanation" in data
            assert "hero_summary" in data
            assert "decision_integrity" in data
            assert data.get("meta", {}).get("version") == "4.1"
            
            print(f"PASS: External endpoint has E1 features")
        except requests.exceptions.Timeout:
            pytest.skip("External endpoint timed out - use localhost for testing")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
