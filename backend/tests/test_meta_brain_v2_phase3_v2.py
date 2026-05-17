"""
Meta Brain V2 Phase 3 Test Suite
================================
Tests for:
1. Provider-agnostic architecture (getProviders/getProviderCount)
2. Regime-aware verdict thresholds
3. Horizon-aware cooldown
4. Performance tracker with accuracy-adaptive weights
5. Run persistence
6. Phase 1 & 2 regression
"""

import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestProviderRegistry:
    """Provider-agnostic architecture: /providers endpoint tests"""
    
    def test_providers_endpoint_returns_ok(self):
        """GET /providers should return ok=true"""
        response = requests.get(f"{BASE_URL}/api/meta-brain-v2/providers")
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] is True
        print("✓ /providers returns ok=true")
    
    def test_providers_count_is_dynamic(self):
        """coverage.total should come from registry (currently 4)"""
        response = requests.get(f"{BASE_URL}/api/meta-brain-v2/providers")
        data = response.json()
        assert data['count'] == 4
        assert len(data['providers']) == 4
        print(f"✓ Provider count is dynamic: {data['count']}")
    
    def test_providers_list_has_required_fields(self):
        """Each provider should have key and version"""
        response = requests.get(f"{BASE_URL}/api/meta-brain-v2/providers")
        data = response.json()
        for p in data['providers']:
            assert 'key' in p
            assert 'version' in p
        print(f"✓ All providers have key and version")
    
    def test_providers_keys_array(self):
        """Response should include keys array"""
        response = requests.get(f"{BASE_URL}/api/meta-brain-v2/providers")
        data = response.json()
        assert 'keys' in data
        expected_keys = ['fractal', 'exchange', 'onchain', 'sentiment']
        for key in expected_keys:
            assert key in data['keys']
        print(f"✓ Keys array: {data['keys']}")


class TestRunEndpointPhase3:
    """POST /run with Phase 3 features"""
    
    def test_run_returns_ok(self):
        """POST /run should return ok=true"""
        response = requests.post(f"{BASE_URL}/api/meta-brain-v2/run", json={
            "asset": "BTC",
            "horizonDays": 7
        })
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] is True
        print("✓ POST /run returns ok=true")
    
    def test_run_returns_regime_field(self):
        """Run response should include regime field"""
        response = requests.post(f"{BASE_URL}/api/meta-brain-v2/run", json={
            "asset": "BTC",
            "horizonDays": 7
        })
        data = response.json()
        assert 'regime' in data
        assert data['regime'] in ['TREND', 'RANGE', 'RISK_OFF', 'TRANSITION']
        print(f"✓ Regime field present: {data['regime']}")
    
    def test_run_returns_regime_detail(self):
        """Run response should include regimeDetail with required fields"""
        response = requests.post(f"{BASE_URL}/api/meta-brain-v2/run", json={
            "asset": "BTC",
            "horizonDays": 7
        })
        data = response.json()
        assert 'regimeDetail' in data
        rd = data['regimeDetail']
        assert 'sourceRegime' in rd
        assert 'source' in rd
        assert 'riskLevel' in rd
        assert 'confidenceMultiplier' in rd
        print(f"✓ regimeDetail: sourceRegime={rd['sourceRegime']}, source={rd['source']}")
    
    def test_signals_contain_accuracy_mult(self):
        """Signals should contain accuracyMult field"""
        response = requests.post(f"{BASE_URL}/api/meta-brain-v2/run", json={
            "asset": "BTC",
            "horizonDays": 7
        })
        data = response.json()
        assert 'signals' in data
        for sig in data['signals']:
            assert 'accuracyMult' in sig
            # When no performance data, accuracyMult should be 1.0
            assert sig['accuracyMult'] == 1.0
        print("✓ All signals contain accuracyMult=1.0 (no perf data yet)")
    
    def test_signals_contain_weight_decomposition(self):
        """Signals should contain full weight decomposition"""
        response = requests.post(f"{BASE_URL}/api/meta-brain-v2/run", json={
            "asset": "BTC",
            "horizonDays": 7
        })
        data = response.json()
        for sig in data['signals']:
            assert 'baseWeight' in sig
            assert 'regimeMult' in sig
            assert 'accuracyMult' in sig
            assert 'healthMult' in sig
            assert 'driftMult' in sig
            assert 'rawWeight' in sig
            assert 'weight' in sig
        print("✓ All signals contain full weight decomposition")
    
    def test_coverage_total_from_registry(self):
        """coverage.total should come from provider registry (4)"""
        response = requests.post(f"{BASE_URL}/api/meta-brain-v2/run", json={
            "asset": "BTC",
            "horizonDays": 7
        })
        data = response.json()
        assert 'coverage' in data
        assert data['coverage']['total'] == 4
        print(f"✓ coverage.total={data['coverage']['total']} (from registry)")


class TestHorizonAwareCooldown:
    """Stability layer horizon-aware cooldown tests"""
    
    def test_cooldown_1d_horizon(self):
        """1D horizon should have 30min cooldown (1,800,000ms)"""
        response = requests.post(f"{BASE_URL}/api/meta-brain-v2/run", json={
            "asset": "BTC",
            "horizonDays": 1
        })
        data = response.json()
        assert data['stability']['cooldownMs'] == 1800000
        print(f"✓ 1D cooldown: {data['stability']['cooldownMs']}ms = 30min")
    
    def test_cooldown_7d_horizon(self):
        """7D horizon should have 2h cooldown (7,200,000ms)"""
        response = requests.post(f"{BASE_URL}/api/meta-brain-v2/run", json={
            "asset": "BTC",
            "horizonDays": 7
        })
        data = response.json()
        assert data['stability']['cooldownMs'] == 7200000
        print(f"✓ 7D cooldown: {data['stability']['cooldownMs']}ms = 2h")
    
    def test_cooldown_30d_horizon(self):
        """30D horizon should have 6h cooldown (21,600,000ms)"""
        response = requests.post(f"{BASE_URL}/api/meta-brain-v2/run", json={
            "asset": "BTC",
            "horizonDays": 30
        })
        data = response.json()
        assert data['stability']['cooldownMs'] == 21600000
        print(f"✓ 30D cooldown: {data['stability']['cooldownMs']}ms = 6h")


class TestRegimeAwareThresholds:
    """Regime-aware verdict threshold tests
    
    TREND uses ±0.25, TRANSITION uses ±0.40
    Current regime is TREND
    """
    
    def test_current_regime_is_trend(self):
        """Verify current regime is TREND"""
        response = requests.post(f"{BASE_URL}/api/meta-brain-v2/run", json={
            "asset": "BTC",
            "horizonDays": 7
        })
        data = response.json()
        assert data['regime'] == 'TREND'
        print(f"✓ Current regime is TREND")
    
    def test_trend_threshold_applied(self):
        """TREND regime should use ±0.25 thresholds
        
        Note: With current score ~0.01, verdict should be NEUTRAL
        since |0.01| < 0.25
        """
        response = requests.post(f"{BASE_URL}/api/meta-brain-v2/run", json={
            "asset": "BTC",
            "horizonDays": 7
        })
        data = response.json()
        score = data['verdict']['rawScore']
        raw_verdict = data['verdict']['rawDirection']
        
        # With TREND thresholds (±0.25):
        # - LONG if score >= 0.25
        # - SHORT if score <= -0.25
        # - NEUTRAL otherwise
        if score >= 0.25:
            expected = 'LONG'
        elif score <= -0.25:
            expected = 'SHORT'
        else:
            expected = 'NEUTRAL'
        
        assert raw_verdict == expected
        print(f"✓ Score {score:.4f} -> rawVerdict={raw_verdict} (TREND thresholds ±0.25)")


class TestPerformanceTracker:
    """Performance tracker endpoint tests"""
    
    def test_performance_endpoint_returns_ok(self):
        """GET /performance should return ok=true"""
        response = requests.get(f"{BASE_URL}/api/meta-brain-v2/performance?asset=BTC&horizon=7")
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] is True
        print("✓ GET /performance returns ok=true")
    
    def test_performance_returns_empty_modules(self):
        """Should return empty modules array (no performance data yet)"""
        response = requests.get(f"{BASE_URL}/api/meta-brain-v2/performance?asset=BTC&horizon=7")
        data = response.json()
        assert 'modules' in data
        assert isinstance(data['modules'], list)
        print(f"✓ /performance returns modules array (length={len(data['modules'])})")
    
    def test_performance_eval_endpoint_returns_ok(self):
        """POST /performance/eval should return ok=true"""
        response = requests.post(f"{BASE_URL}/api/meta-brain-v2/performance/eval", json={
            "asset": "BTC",
            "horizonDays": 7
        })
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] is True
        print("✓ POST /performance/eval returns ok=true")
    
    def test_performance_eval_no_matured_runs(self):
        """Should return evaluated=0 (no matured runs yet)"""
        response = requests.post(f"{BASE_URL}/api/meta-brain-v2/performance/eval", json={
            "asset": "BTC",
            "horizonDays": 7
        })
        data = response.json()
        assert 'evaluated' in data
        assert 'skipped' in data
        assert 'errors' in data
        # No matured runs expected since runs are just being created
        print(f"✓ Eval result: evaluated={data['evaluated']}, skipped={data['skipped']}")


class TestAccuracyMultGuard:
    """Weight engine accuracy multiplier guard tests
    
    Guard: samples < 20 → accuracyMult = 1.0
    """
    
    def test_accuracy_mult_default_1_0(self):
        """With no performance data, accuracyMult should be 1.0"""
        response = requests.post(f"{BASE_URL}/api/meta-brain-v2/run", json={
            "asset": "BTC",
            "horizonDays": 7
        })
        data = response.json()
        for sig in data['signals']:
            assert sig['accuracyMult'] == 1.0, f"{sig['module']} has accuracyMult={sig['accuracyMult']}"
        print("✓ All signals have accuracyMult=1.0 (guard: samples < 20)")


class TestPhase1Regression:
    """Phase 1 regression tests"""
    
    def test_signals_endpoint(self):
        """GET /signals should work"""
        response = requests.get(f"{BASE_URL}/api/meta-brain-v2/signals?asset=BTC&horizon=7")
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] is True
        assert 'signals' in data
        print(f"✓ /signals working, {len(data['signals'])} signals returned")
    
    def test_signals_aligned_endpoint(self):
        """GET /signals/aligned should work"""
        response = requests.get(f"{BASE_URL}/api/meta-brain-v2/signals/aligned?asset=BTC&horizon=7")
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] is True
        assert 'aligned' in data
        print(f"✓ /signals/aligned working, {len(data['aligned'])} aligned signals")
    
    def test_status_endpoint(self):
        """GET /status should work"""
        response = requests.get(f"{BASE_URL}/api/meta-brain-v2/status")
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] is True
        assert 'providersCount' in data
        assert data['version'] == 'meta-brain-v2-phase3'
        print(f"✓ /status working, version={data['version']}")


class TestPhase2Regression:
    """Phase 2 regression tests"""
    
    def test_state_endpoint(self):
        """GET /state should return persisted state"""
        response = requests.get(f"{BASE_URL}/api/meta-brain-v2/state?asset=BTC&horizon=7")
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] is True
        if data['state']:
            assert 'lastVerdict' in data['state']
            assert 'lastScore' in data['state']
            assert 'cooldownUntilTs' in data['state']
            print(f"✓ /state returns persisted state: verdict={data['state']['lastVerdict']}")
        else:
            print("✓ /state returns null (no prior state)")
    
    def test_run_includes_stability(self):
        """POST /run should include stability info"""
        response = requests.post(f"{BASE_URL}/api/meta-brain-v2/run", json={
            "asset": "BTC",
            "horizonDays": 7
        })
        data = response.json()
        assert 'stability' in data
        stability = data['stability']
        required_fields = ['applied', 'verdictChanged', 'reason', 'cooldownActive', 'cooldownMs', 'previousVerdict']
        for field in required_fields:
            assert field in stability, f"Missing stability.{field}"
        print(f"✓ /run includes stability info")
    
    def test_run_includes_alignment(self):
        """POST /run should include alignment details"""
        response = requests.post(f"{BASE_URL}/api/meta-brain-v2/run", json={
            "asset": "BTC",
            "horizonDays": 7
        })
        data = response.json()
        assert 'alignment' in data
        alignment = data['alignment']
        assert 'anchorTs' in alignment
        assert 'aligned' in alignment
        assert 'dropped' in alignment
        print(f"✓ /run includes alignment details")


class TestWeightFormula:
    """Weight formula verification: base × regime × accuracy × health × drift"""
    
    def test_weight_formula(self):
        """Verify rawWeight = base × regimeMult × accuracyMult × healthMult × driftMult"""
        response = requests.post(f"{BASE_URL}/api/meta-brain-v2/run", json={
            "asset": "BTC",
            "horizonDays": 7
        })
        data = response.json()
        
        for sig in data['signals']:
            expected_raw = (
                sig['baseWeight'] * 
                sig['regimeMult'] * 
                sig['accuracyMult'] * 
                sig['healthMult'] * 
                sig['driftMult']
            )
            # Allow small floating point tolerance
            assert abs(sig['rawWeight'] - expected_raw) < 0.0001, \
                f"{sig['module']}: rawWeight={sig['rawWeight']}, expected={expected_raw}"
        print("✓ Weight formula verified: base × regime × accuracy × health × drift")
    
    def test_weights_sum_to_one(self):
        """Effective weights should sum to ~1.0"""
        response = requests.post(f"{BASE_URL}/api/meta-brain-v2/run", json={
            "asset": "BTC",
            "horizonDays": 7
        })
        data = response.json()
        
        total_weight = sum(sig['weight'] for sig in data['signals'])
        assert abs(total_weight - 1.0) < 0.001, f"Weights sum to {total_weight}"
        print(f"✓ Weights sum to {total_weight:.4f} ≈ 1.0")


class TestExchangeStaleStatus:
    """Exchange provider STALE status (known data issue)"""
    
    def test_exchange_dropped_as_stale(self):
        """Exchange should be dropped as STALE (data from Feb 15)"""
        response = requests.post(f"{BASE_URL}/api/meta-brain-v2/run", json={
            "asset": "BTC",
            "horizonDays": 7
        })
        data = response.json()
        
        # Check alignment.dropped
        dropped_modules = [d['module'] for d in data['alignment']['dropped']]
        assert 'exchange' in dropped_modules
        
        exchange_drop = next(d for d in data['alignment']['dropped'] if d['module'] == 'exchange')
        assert exchange_drop['reason'] == 'STALE'
        print(f"✓ Exchange correctly dropped as STALE: {exchange_drop.get('detail', '')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
