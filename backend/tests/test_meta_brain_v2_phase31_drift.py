"""
META BRAIN V2 — PHASE 3.1 DRIFT DETECTOR + EXPLAINABILITY + EXCHANGE KEEPALIVE TESTS
=====================================================================================

Testing:
- P0 Exchange fix: POST /api/meta-brain-v2/exchange/refresh (keepalive)
- P1 Drift Detector: GET /drift, GET /drift/history, POST /drift/eval
- P2 Explainability: explain block in POST /run response
- Phase 1/2 regression: /signals, /signals/aligned, /status, /state, /performance
- Weight formula with driftPenalty: base × regime × accuracy × driftPenalty × health × driftMult
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
META_BRAIN_V2_PREFIX = f"{BASE_URL}/api/meta-brain-v2"


class TestMetaBrainV2Providers:
    """Test provider registry - should return 4 providers"""
    
    def test_providers_endpoint(self):
        """GET /providers returns 4 providers"""
        resp = requests.get(f"{META_BRAIN_V2_PREFIX}/providers", timeout=10)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data["ok"] == True
        assert data["count"] == 4, f"Expected 4 providers, got {data['count']}"
        assert "providers" in data
        assert set(data["keys"]) == {"fractal", "exchange", "onchain", "sentiment"}, f"Got keys: {data['keys']}"
        print(f"✓ GET /providers: count={data['count']}, keys={data['keys']}")


class TestExchangeRefresh:
    """P0 Exchange fix: keepalive scheduler + manual refresh"""
    
    def test_exchange_refresh_endpoint(self):
        """POST /exchange/refresh should work and return refresh status"""
        resp = requests.post(f"{META_BRAIN_V2_PREFIX}/exchange/refresh", timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data["ok"] == True
        # Response should contain: refreshed, skipped, failed arrays
        assert "refreshed" in data or "skipped" in data or "failed" in data
        print(f"✓ POST /exchange/refresh: refreshed={data.get('refreshed', [])}, skipped={data.get('skipped', [])}, failed={data.get('failed', [])}")


class TestDriftDetectorEndpoints:
    """P1 Drift Detector: GET /drift, GET /drift/history, POST /drift/eval"""
    
    def test_get_drift_state(self):
        """GET /drift returns drift state for all modules"""
        resp = requests.get(f"{META_BRAIN_V2_PREFIX}/drift?asset=BTC&horizon=7", timeout=10)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data["ok"] == True
        assert data["asset"] == "BTC"
        assert data["horizonDays"] == 7
        assert "modules" in data
        # modules may be empty initially or have drift states
        print(f"✓ GET /drift: asset={data['asset']}, modules count={len(data['modules'])}")
        if data["modules"]:
            for m in data["modules"][:3]:  # Show first 3
                print(f"  - {m['moduleId']}: score={m.get('driftScore', 'N/A')}, status={m.get('status', 'N/A')}")
        return data
    
    def test_get_drift_history(self):
        """GET /drift/history returns drift history for a specific module"""
        # Default moduleId is 'exchange'
        resp = requests.get(f"{META_BRAIN_V2_PREFIX}/drift/history?moduleId=exchange&asset=BTC&horizon=7&days=30", timeout=10)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data["ok"] == True
        assert data["moduleId"] == "exchange"
        assert data["asset"] == "BTC"
        assert data["horizonDays"] == 7
        assert data["days"] == 30
        assert "history" in data
        print(f"✓ GET /drift/history: moduleId={data['moduleId']}, history entries={len(data['history'])}")
        if data["history"]:
            # Show latest entry
            latest = data["history"][-1] if data["history"] else {}
            print(f"  Latest: date={latest.get('dateBucket', 'N/A')}, score={latest.get('driftScore', 'N/A')}")
        return data
    
    def test_post_drift_eval(self):
        """POST /drift/eval triggers drift evaluation and returns states"""
        resp = requests.post(
            f"{META_BRAIN_V2_PREFIX}/drift/eval",
            json={"asset": "BTC", "horizonDays": 7, "limit": 60},
            timeout=30
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data["ok"] == True
        assert data["asset"] == "BTC"
        assert data["horizonDays"] == 7
        # Response should have: evaluated, skipped, states
        assert "evaluated" in data
        assert "skipped" in data
        assert "states" in data
        print(f"✓ POST /drift/eval: evaluated={data['evaluated']}, skipped={len(data['skipped'])}, states count={len(data['states'])}")
        if data["states"]:
            for s in data["states"][:3]:
                print(f"  - {s['moduleId']}: driftScore={s.get('driftScore', 'N/A'):.3f}, penalty={s.get('penalty', 'N/A'):.3f}, status={s.get('status', 'N/A')}")
        return data


class TestRunEndpointExplainability:
    """P2 Explainability: POST /run response includes explain and drift blocks"""
    
    def test_run_with_explain_block(self):
        """POST /run returns explain block with contributors and conflicts"""
        resp = requests.post(
            f"{META_BRAIN_V2_PREFIX}/run",
            json={"asset": "BTC", "horizonDays": 7},
            timeout=30
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data["ok"] == True
        
        # Check explain block
        assert "explain" in data, "Response should have 'explain' block"
        explain = data["explain"]
        assert "contributors" in explain, "Explain block should have 'contributors'"
        assert "conflicts" in explain, "Explain block should have 'conflicts'"
        
        # Validate contributors structure
        contributors = explain["contributors"]
        assert isinstance(contributors, list), "Contributors should be a list"
        if contributors:
            # Check first contributor has required fields
            c = contributors[0]
            assert "module" in c, "Contributor should have 'module'"
            assert "weight" in c, "Contributor should have 'weight'"
            assert "signal" in c, "Contributor should have 'signal'"
            assert "impact" in c, "Contributor should have 'impact'"
            # Check sorted by impact (descending abs value)
            if len(contributors) > 1:
                assert abs(contributors[0]["impact"]) >= abs(contributors[-1]["impact"]), "Contributors should be sorted by abs(impact) desc"
        
        print(f"✓ POST /run explain.contributors: {len(contributors)} modules")
        for c in contributors[:4]:
            print(f"  - {c['module']}: weight={c['weight']:.3f}, signal={c['signal']:.3f}, impact={c['impact']:.3f}")
        
        # Check conflicts
        conflicts = explain["conflicts"]
        assert isinstance(conflicts, list), "Conflicts should be a list"
        print(f"✓ POST /run explain.conflicts: {len(conflicts)} conflicts found")
        for cf in conflicts[:3]:
            print(f"  - {cf['a']} vs {cf['b']}: {cf['type']}")
        
        return data
    
    def test_run_with_drift_block(self):
        """POST /run returns drift block with drift info per module"""
        resp = requests.post(
            f"{META_BRAIN_V2_PREFIX}/run",
            json={"asset": "BTC", "horizonDays": 7},
            timeout=30
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data["ok"] == True
        
        # Check drift block
        assert "drift" in data, "Response should have 'drift' block"
        drift = data["drift"]
        assert isinstance(drift, dict), "Drift should be a dict (moduleId -> info)"
        
        print(f"✓ POST /run drift block: {len(drift)} modules")
        for module_id, info in list(drift.items())[:4]:
            print(f"  - {module_id}: score={info.get('score', 'N/A')}, penalty={info.get('penalty', 'N/A')}, status={info.get('status', 'N/A')}")
        
        return data
    
    def test_signals_have_drift_penalty(self):
        """Signals in POST /run should include driftPenalty field in weight decomposition"""
        resp = requests.post(
            f"{META_BRAIN_V2_PREFIX}/run",
            json={"asset": "BTC", "horizonDays": 7},
            timeout=30
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        
        # Check signals have driftPenalty
        signals = data.get("signals", [])
        assert len(signals) > 0, "Should have at least one signal"
        
        for sig in signals:
            assert "driftPenalty" in sig, f"Signal {sig.get('module')} should have 'driftPenalty'"
            # driftPenalty should be a number between 0 and 1 (exp(-2*driftScore))
            dp = sig["driftPenalty"]
            assert isinstance(dp, (int, float)), f"driftPenalty should be a number, got {type(dp)}"
            assert 0 <= dp <= 1, f"driftPenalty should be [0, 1], got {dp}"
        
        print(f"✓ POST /run signals driftPenalty:")
        for sig in signals[:4]:
            print(f"  - {sig['module']}: driftPenalty={sig['driftPenalty']:.3f}, weight={sig['weight']:.3f}")
        
        return data


class TestCoverageFourProviders:
    """Verify coverage.total=4 and exchange is now active"""
    
    def test_coverage_is_4(self):
        """POST /run should show 4 total providers in coverage"""
        resp = requests.post(
            f"{META_BRAIN_V2_PREFIX}/run",
            json={"asset": "BTC", "horizonDays": 7},
            timeout=30
        )
        assert resp.status_code == 200
        data = resp.json()
        
        coverage = data.get("coverage", {})
        assert coverage.get("total") == 4, f"Expected coverage.total=4, got {coverage.get('total')}"
        
        print(f"✓ POST /run coverage: total={coverage['total']}, aligned={coverage.get('aligned')}, active={coverage.get('active')}, dropped={coverage.get('dropped')}")
        
        # Check if exchange is active (not dropped)
        gated = data.get("gatedModules", [])
        dropped = data.get("alignment", {}).get("dropped", [])
        all_dropped_modules = [g["module"] for g in gated] + [d["module"] for d in dropped]
        
        print(f"  Dropped/gated modules: {all_dropped_modules}")
        
        # Exchange should ideally be active now (not STALE)
        signals = data.get("signals", [])
        signal_modules = [s["module"] for s in signals]
        print(f"  Active signal modules: {signal_modules}")
        
        return data


class TestWeightFormula:
    """Weight formula: base × regime × accuracy × driftPenalty × health × driftMult → renorm"""
    
    def test_weight_decomposition_fields(self):
        """Signals should have all weight decomposition fields"""
        resp = requests.post(
            f"{META_BRAIN_V2_PREFIX}/run",
            json={"asset": "BTC", "horizonDays": 7},
            timeout=30
        )
        assert resp.status_code == 200
        data = resp.json()
        
        signals = data.get("signals", [])
        assert len(signals) > 0, "Should have at least one signal"
        
        required_fields = ["baseWeight", "regimeMult", "accuracyMult", "driftPenalty", "healthMult", "driftMult", "rawWeight", "weight"]
        
        for sig in signals:
            for field in required_fields:
                assert field in sig, f"Signal {sig.get('module')} missing '{field}'"
        
        print(f"✓ POST /run weight decomposition fields present")
        for sig in signals[:4]:
            print(f"  - {sig['module']}: base={sig['baseWeight']:.3f} × regime={sig['regimeMult']:.2f} × acc={sig['accuracyMult']:.2f} × driftP={sig['driftPenalty']:.2f} × health={sig['healthMult']:.2f} × driftM={sig['driftMult']:.2f} → raw={sig['rawWeight']:.4f} → w={sig['weight']:.3f}")
        
        # Check weights sum to ~1.0
        weight_sum = sum(s["weight"] for s in signals)
        assert abs(weight_sum - 1.0) < 0.01, f"Weights should sum to ~1.0, got {weight_sum}"
        print(f"  Weights sum: {weight_sum:.4f} ✓")
        
        return data


class TestPhase1Regression:
    """Phase 1 regression: /signals, /signals/aligned, /status"""
    
    def test_signals_endpoint(self):
        """GET /signals works"""
        resp = requests.get(f"{META_BRAIN_V2_PREFIX}/signals?asset=BTC&horizon=7", timeout=20)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] == True
        assert "signals" in data
        assert "dropped" in data
        print(f"✓ GET /signals: {len(data['signals'])} signals, {len(data['dropped'])} dropped")
    
    def test_signals_aligned_endpoint(self):
        """GET /signals/aligned works"""
        resp = requests.get(f"{META_BRAIN_V2_PREFIX}/signals/aligned?asset=BTC&horizon=7", timeout=20)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] == True
        assert "aligned" in data
        assert "coverage" in data
        print(f"✓ GET /signals/aligned: {len(data['aligned'])} aligned, coverage={data['coverage']}")
    
    def test_status_endpoint(self):
        """GET /status works"""
        resp = requests.get(f"{META_BRAIN_V2_PREFIX}/status", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] == True
        assert data["version"] == "meta-brain-v2-phase3"
        assert data["providersCount"] == 4
        print(f"✓ GET /status: version={data['version']}, providers={data['providersCount']}")


class TestPhase2Regression:
    """Phase 2 regression: /state, /performance"""
    
    def test_state_endpoint(self):
        """GET /state works"""
        resp = requests.get(f"{META_BRAIN_V2_PREFIX}/state?asset=BTC&horizon=7", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] == True
        assert data["asset"] == "BTC"
        print(f"✓ GET /state: asset={data['asset']}, state={'present' if data.get('state') else 'null'}")
    
    def test_performance_endpoint(self):
        """GET /performance works"""
        resp = requests.get(f"{META_BRAIN_V2_PREFIX}/performance?asset=BTC&horizon=7", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] == True
        assert "modules" in data
        print(f"✓ GET /performance: {len(data['modules'])} modules with performance data")


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
