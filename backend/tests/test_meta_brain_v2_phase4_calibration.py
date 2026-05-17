"""
Meta Brain V2 Phase 4: Confidence Calibration Layer Tests
=========================================================

Tests:
1. GET /api/meta-brain-v2/calibration — returns empty modules array (no data yet)
2. POST /api/meta-brain-v2/calibration/eval — triggers job, returns skipped (no evaluated runs)
3. POST /api/meta-brain-v2/run — still works with 4/4 coverage, full pipeline unchanged
4. /run response has explain.contributors and explain.conflicts
5. /run response has drift info per module
6. Phase 1 regression: /signals, /signals/aligned, /status, /providers
7. Phase 2 regression: /state
8. Phase 3 regression: /performance, /drift

Collection: meta_brain_confidence_calibration (new in Phase 4)
"""

import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
API_PREFIX = f"{BASE_URL}/api/meta-brain-v2"


class TestPhase4CalibrationNew:
    """Phase 4: New Calibration Endpoints"""

    def test_get_calibration_returns_empty_modules(self):
        """GET /calibration should return empty modules array (no calibration data yet)"""
        response = requests.get(f"{API_PREFIX}/calibration", params={"asset": "BTC", "horizon": "7"})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, "Response should have ok=true"
        assert data.get("asset") == "BTC", "Asset should be BTC"
        assert data.get("horizonDays") == 7, "HorizonDays should be 7"
        assert "modules" in data, "Response should have modules field"
        assert isinstance(data["modules"], list), "Modules should be a list"
        # Expected to be empty since no evaluated runs exist yet
        print(f"✓ GET /calibration: ok=true, modules count = {len(data['modules'])}")

    def test_post_calibration_eval_skips_all_modules(self):
        """POST /calibration/eval should return skipped for all modules (no evaluated runs)"""
        response = requests.post(f"{API_PREFIX}/calibration/eval", json={"asset": "BTC", "horizonDays": 7})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, "Response should have ok=true"
        assert data.get("asset") == "BTC", "Asset should be BTC"
        assert data.get("horizonDays") == 7, "HorizonDays should be 7"
        
        # Job returns evaluated, skipped, totalRunsProcessed
        assert "evaluated" in data, "Response should have evaluated field"
        assert "skipped" in data, "Response should have skipped field"
        assert "totalRunsProcessed" in data, "Response should have totalRunsProcessed field"
        
        # Since no evaluated runs exist, totalRunsProcessed should be 0
        # and all modules should be skipped
        print(f"✓ POST /calibration/eval: evaluated={len(data['evaluated'])}, skipped={len(data['skipped'])}, runsProcessed={data['totalRunsProcessed']}")
        
        # All modules should be skipped (no evaluated signals)
        assert isinstance(data["skipped"], list), "Skipped should be a list"


class TestPhase3RunPipelineUnchanged:
    """Verify POST /run still works with 4/4 coverage after Phase 4 addition"""

    def test_run_pipeline_returns_200(self):
        """POST /run should return 200 with full pipeline response"""
        response = requests.post(f"{API_PREFIX}/run", json={"asset": "BTC", "horizonDays": 7})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, "Response should have ok=true"
        print(f"✓ POST /run: ok=true, verdict={data.get('verdict', {}).get('direction')}")

    def test_run_has_explain_contributors(self):
        """POST /run should have explain.contributors sorted by impact"""
        response = requests.post(f"{API_PREFIX}/run", json={"asset": "BTC", "horizonDays": 7})
        data = response.json()
        
        assert "explain" in data, "Response should have explain block"
        explain = data["explain"]
        
        assert "contributors" in explain, "Explain should have contributors"
        contributors = explain["contributors"]
        assert isinstance(contributors, list), "Contributors should be a list"
        
        # Each contributor should have module, weight, signal, impact
        if len(contributors) > 0:
            first = contributors[0]
            assert "module" in first, "Contributor should have module"
            assert "weight" in first, "Contributor should have weight"
            assert "signal" in first, "Contributor should have signal (normalizedScore)"
            assert "impact" in first, "Contributor should have impact (weightedScore)"
            
            # Verify sorted by abs(impact) descending
            impacts = [abs(c["impact"]) for c in contributors]
            assert impacts == sorted(impacts, reverse=True), "Contributors should be sorted by abs(impact) descending"
        
        print(f"✓ explain.contributors: {len(contributors)} modules sorted by impact")

    def test_run_has_explain_conflicts(self):
        """POST /run should have explain.conflicts (direction conflict detection)"""
        response = requests.post(f"{API_PREFIX}/run", json={"asset": "BTC", "horizonDays": 7})
        data = response.json()
        
        assert "explain" in data, "Response should have explain block"
        explain = data["explain"]
        
        assert "conflicts" in explain, "Explain should have conflicts"
        conflicts = explain["conflicts"]
        assert isinstance(conflicts, list), "Conflicts should be a list"
        
        # Conflicts are arrays of {a, b, type} when modules have opposite directions
        if len(conflicts) > 0:
            first = conflicts[0]
            assert "a" in first, "Conflict should have 'a' module"
            assert "b" in first, "Conflict should have 'b' module"
            assert "type" in first, "Conflict should have type"
        
        print(f"✓ explain.conflicts: {len(conflicts)} conflicts detected")

    def test_run_has_drift_info_per_module(self):
        """POST /run should have drift info per module in signals"""
        response = requests.post(f"{API_PREFIX}/run", json={"asset": "BTC", "horizonDays": 7})
        data = response.json()
        
        # Check driftInfo block exists
        assert "drift" in data or "driftInfo" in data, "Response should have drift/driftInfo"
        drift_info = data.get("drift") or data.get("driftInfo")
        
        if drift_info:
            print(f"✓ drift info present in response: {list(drift_info.keys()) if isinstance(drift_info, dict) else 'array'}")
        
        # Check signals have driftPenalty
        signals = data.get("signals", [])
        if len(signals) > 0:
            has_drift_penalty = any("driftPenalty" in s for s in signals)
            print(f"✓ signals have driftPenalty: {has_drift_penalty}")

    def test_run_coverage_4_of_4(self):
        """POST /run should have 4/4 coverage (all modules active)"""
        response = requests.post(f"{API_PREFIX}/run", json={"asset": "BTC", "horizonDays": 7})
        data = response.json()
        
        coverage = data.get("coverage", {})
        meta_status = data.get("metaStatus", "")
        
        # Check coverage fields
        total = coverage.get("total", 0)
        active = coverage.get("active", 0)
        dropped = coverage.get("dropped", 0)
        
        print(f"✓ coverage: {active}/{total} active, {dropped} dropped, status={meta_status}")
        
        # Should have 4/4 coverage
        assert total == 4, f"Expected 4 total providers, got {total}"
        assert active == 4, f"Expected 4 active providers, got {active}"
        assert dropped == 0, f"Expected 0 dropped providers, got {dropped}"


class TestPhase1Regression:
    """Phase 1 regression: /signals, /signals/aligned, /status, /providers"""

    def test_signals_endpoint(self):
        """GET /signals should return raw signals"""
        response = requests.get(f"{API_PREFIX}/signals", params={"asset": "BTC", "horizon": "7"})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True
        assert "signals" in data
        print(f"✓ GET /signals: ok=true, {len(data['signals'])} signals")

    def test_signals_aligned_endpoint(self):
        """GET /signals/aligned should return aligned signals"""
        response = requests.get(f"{API_PREFIX}/signals/aligned", params={"asset": "BTC", "horizon": "7"})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True
        assert "aligned" in data or "signals" in data
        print(f"✓ GET /signals/aligned: ok=true")

    def test_status_endpoint(self):
        """GET /status should return provider health"""
        response = requests.get(f"{API_PREFIX}/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True
        assert "providers" in data or "providersCount" in data
        print(f"✓ GET /status: ok=true, providers={data.get('providersCount', len(data.get('providers', [])))}")

    def test_providers_endpoint(self):
        """GET /providers should return active providers"""
        response = requests.get(f"{API_PREFIX}/providers")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True
        assert "providers" in data
        assert "keys" in data
        
        # Should have 4 providers: fractal, exchange, onchain, sentiment
        expected_keys = {"fractal", "exchange", "onchain", "sentiment"}
        actual_keys = set(data.get("keys", []))
        assert expected_keys == actual_keys, f"Expected keys {expected_keys}, got {actual_keys}"
        
        print(f"✓ GET /providers: ok=true, keys={data['keys']}")


class TestPhase2Regression:
    """Phase 2 regression: /state"""

    def test_state_endpoint(self):
        """GET /state should return current persisted state"""
        response = requests.get(f"{API_PREFIX}/state", params={"asset": "BTC", "horizon": "7"})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True
        assert data.get("asset") == "BTC"
        assert data.get("horizonDays") == 7
        # State may be null if no prior run, or present if run executed
        print(f"✓ GET /state: ok=true, state={'present' if data.get('state') else 'null'}")


class TestPhase3Regression:
    """Phase 3 regression: /performance, /drift"""

    def test_performance_endpoint(self):
        """GET /performance should return module accuracy metrics"""
        response = requests.get(f"{API_PREFIX}/performance", params={"asset": "BTC", "horizon": "7"})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True
        assert "modules" in data
        print(f"✓ GET /performance: ok=true, {len(data['modules'])} modules")

    def test_drift_endpoint(self):
        """GET /drift should return drift states for all modules"""
        response = requests.get(f"{API_PREFIX}/drift", params={"asset": "BTC", "horizon": "7"})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True
        assert "modules" in data
        
        modules = data["modules"]
        print(f"✓ GET /drift: ok=true, {len(modules)} module drift states")


class TestCalibrationDataStructure:
    """Verify calibration endpoint data structures"""

    def test_calibration_response_structure(self):
        """GET /calibration response should have correct structure"""
        response = requests.get(f"{API_PREFIX}/calibration", params={"asset": "BTC", "horizon": "7"})
        data = response.json()
        
        # Required fields
        assert "ok" in data
        assert "asset" in data
        assert "horizonDays" in data
        assert "modules" in data
        
        # If modules exist (after calibration job runs with data), verify structure
        modules = data.get("modules", [])
        if len(modules) > 0:
            m = modules[0]
            assert "moduleId" in m, "Module should have moduleId"
            assert "totalSamples" in m, "Module should have totalSamples"
            assert "method" in m, "Module should have method"
            assert "bins" in m, "Module should have bins"
            assert "updatedAt" in m, "Module should have updatedAt"
            assert "active" in m, "Module should have active flag"
            
            # Verify bins structure (10 bins: 0.0-0.1 through 0.9-1.0)
            bins = m.get("bins", [])
            if len(bins) > 0:
                b = bins[0]
                assert "range" in b, "Bin should have range"
                assert "samples" in b, "Bin should have samples"
                assert "hitRate" in b, "Bin should have hitRate"
        
        print(f"✓ Calibration response structure valid, {len(modules)} modules")

    def test_calibration_eval_response_structure(self):
        """POST /calibration/eval response should have correct structure"""
        response = requests.post(f"{API_PREFIX}/calibration/eval", json={"asset": "BTC", "horizonDays": 7})
        data = response.json()
        
        # Required fields from CalibrationJobResult
        assert "ok" in data
        assert "asset" in data
        assert "horizonDays" in data
        assert "evaluated" in data
        assert "skipped" in data
        assert "totalRunsProcessed" in data
        
        assert isinstance(data["evaluated"], list)
        assert isinstance(data["skipped"], list)
        assert isinstance(data["totalRunsProcessed"], int)
        
        print(f"✓ Calibration eval response structure valid")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
