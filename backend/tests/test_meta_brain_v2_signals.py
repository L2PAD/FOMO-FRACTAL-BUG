"""
META BRAIN V2 — SIGNAL LAYER TESTS
==================================

Tests for Phase 1 of Meta Brain v2:
- GET /api/meta-brain-v2/status
- GET /api/meta-brain-v2/signals
- GET /api/meta-brain-v2/signals/aligned
- Verify v1 endpoints still work

Key validation:
- Signals must NOT have anchorTs (only alignment layer adds it)
- Aligned signals MUST have anchorTs
- Dropped signals must have reason (STALE/SKEW/TIMEOUT/ERROR)
- Provider timeout: no hang beyond 1200ms
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestMetaBrainV2Status:
    """Test GET /api/meta-brain-v2/status endpoint"""

    def test_status_endpoint_returns_ok(self):
        """Status endpoint should return ok:true with 4 providers"""
        resp = requests.get(f"{BASE_URL}/api/meta-brain-v2/status", timeout=5)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        assert data.get('ok') is True, "Expected ok=true"
        assert data.get('providersCount') == 4, f"Expected 4 providers, got {data.get('providersCount')}"
        
    def test_status_has_all_four_providers(self):
        """Status should list all 4 providers: fractal, exchange, onchain, sentiment"""
        resp = requests.get(f"{BASE_URL}/api/meta-brain-v2/status", timeout=5)
        data = resp.json()
        
        providers = data.get('providers', [])
        provider_keys = [p.get('key') for p in providers]
        
        expected_keys = ['fractal', 'exchange', 'onchain', 'sentiment']
        for key in expected_keys:
            assert key in provider_keys, f"Missing provider: {key}. Got: {provider_keys}"
            
    def test_status_has_policy_config(self):
        """Status should include policy configuration"""
        resp = requests.get(f"{BASE_URL}/api/meta-brain-v2/status", timeout=5)
        data = resp.json()
        
        policy = data.get('policy', {})
        assert 'anchorMode' in policy, "Missing anchorMode in policy"
        assert 'ttl' in policy, "Missing ttl in policy"
        assert 'maxSkew' in policy, "Missing maxSkew in policy"
        assert 'fallback' in policy, "Missing fallback in policy"


class TestMetaBrainV2Signals:
    """Test GET /api/meta-brain-v2/signals endpoint (raw signals)"""
    
    def test_signals_horizon_7d_returns_signals(self):
        """Signals endpoint should return raw signals for BTC 7D horizon"""
        start = time.time()
        resp = requests.get(f"{BASE_URL}/api/meta-brain-v2/signals?asset=BTC&horizon=7", timeout=10)
        duration = (time.time() - start) * 1000
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        assert data.get('ok') is True, "Expected ok=true"
        assert data.get('asset') == 'BTC', f"Expected asset=BTC, got {data.get('asset')}"
        assert data.get('horizonDays') == 7, f"Expected horizonDays=7, got {data.get('horizonDays')}"
        
        # Timeout check: should not hang beyond 1200ms per provider (allow some overhead)
        # With 4 parallel providers, total should be ~1200ms + overhead
        assert duration < 5000, f"Request took too long: {duration:.0f}ms (expected <5000ms)"
        print(f"  Signals 7D request completed in {duration:.0f}ms")
        
    def test_signals_have_required_fields(self):
        """Each signal must have required fields as per contract"""
        resp = requests.get(f"{BASE_URL}/api/meta-brain-v2/signals?asset=BTC&horizon=7", timeout=10)
        data = resp.json()
        
        signals = data.get('signals', [])
        assert len(signals) > 0, "Expected at least 1 signal"
        
        required_fields = ['module', 'direction', 'score', 'confidence', 'asOfTs', 'ttlMs', 'sourceId', 'health', 'reasons']
        
        for sig in signals:
            for field in required_fields:
                assert field in sig, f"Signal missing field '{field}': {sig.get('module', 'unknown')}"
                
    def test_raw_signals_do_not_have_anchorTs(self):
        """Raw signals from /signals endpoint must NOT have anchorTs (only alignment adds it)"""
        resp = requests.get(f"{BASE_URL}/api/meta-brain-v2/signals?asset=BTC&horizon=7", timeout=10)
        data = resp.json()
        
        signals = data.get('signals', [])
        for sig in signals:
            assert 'anchorTs' not in sig, f"Raw signal {sig.get('module')} has anchorTs - should only be set by alignment layer"
            
    def test_signals_direction_values_valid(self):
        """Signal direction must be LONG, SHORT, or NEUTRAL"""
        resp = requests.get(f"{BASE_URL}/api/meta-brain-v2/signals?asset=BTC&horizon=7", timeout=10)
        data = resp.json()
        
        valid_directions = ['LONG', 'SHORT', 'NEUTRAL']
        for sig in data.get('signals', []):
            direction = sig.get('direction')
            assert direction in valid_directions, f"Invalid direction '{direction}' for {sig.get('module')}"
            
    def test_signals_score_in_range(self):
        """Signal score must be in range [-1, +1]"""
        resp = requests.get(f"{BASE_URL}/api/meta-brain-v2/signals?asset=BTC&horizon=7", timeout=10)
        data = resp.json()
        
        for sig in data.get('signals', []):
            score = sig.get('score', 0)
            assert -1 <= score <= 1, f"Score {score} out of range [-1,+1] for {sig.get('module')}"
            
    def test_signals_confidence_in_range(self):
        """Signal confidence must be in range [0, 1]"""
        resp = requests.get(f"{BASE_URL}/api/meta-brain-v2/signals?asset=BTC&horizon=7", timeout=10)
        data = resp.json()
        
        for sig in data.get('signals', []):
            conf = sig.get('confidence', 0)
            assert 0 <= conf <= 1, f"Confidence {conf} out of range [0,1] for {sig.get('module')}"
            
    def test_signals_horizon_1d(self):
        """Signals endpoint should work for 1D horizon"""
        resp = requests.get(f"{BASE_URL}/api/meta-brain-v2/signals?asset=BTC&horizon=1", timeout=10)
        assert resp.status_code == 200
        
        data = resp.json()
        assert data.get('ok') is True
        assert data.get('horizonDays') == 1
        
    def test_signals_horizon_30d(self):
        """Signals endpoint should work for 30D horizon"""
        resp = requests.get(f"{BASE_URL}/api/meta-brain-v2/signals?asset=BTC&horizon=30", timeout=10)
        assert resp.status_code == 200
        
        data = resp.json()
        assert data.get('ok') is True
        assert data.get('horizonDays') == 30


class TestMetaBrainV2SignalsAligned:
    """Test GET /api/meta-brain-v2/signals/aligned endpoint"""
    
    def test_aligned_returns_anchor_and_coverage(self):
        """Aligned endpoint should return anchorTs (UTC 00:00) and coverage object"""
        resp = requests.get(f"{BASE_URL}/api/meta-brain-v2/signals/aligned?asset=BTC&horizon=7", timeout=10)
        assert resp.status_code == 200
        
        data = resp.json()
        assert data.get('ok') is True
        
        # Must have anchorTs
        assert 'anchorTs' in data, "Missing anchorTs in aligned response"
        anchor_ts = data.get('anchorTs')
        assert isinstance(anchor_ts, int) or isinstance(anchor_ts, float), f"anchorTs should be number, got {type(anchor_ts)}"
        
        # Check anchorTs is UTC midnight (divisible by 86400000)
        assert anchor_ts % 86400000 == 0, f"anchorTs {anchor_ts} is not UTC 00:00 (should be divisible by 86400000)"
        
    def test_aligned_has_coverage_object(self):
        """Aligned response must have coverage object with total/aligned/dropped"""
        resp = requests.get(f"{BASE_URL}/api/meta-brain-v2/signals/aligned?asset=BTC&horizon=7", timeout=10)
        data = resp.json()
        
        coverage = data.get('coverage', {})
        assert 'total' in coverage, "Missing coverage.total"
        assert 'aligned' in coverage, "Missing coverage.aligned"
        assert 'dropped' in coverage, "Missing coverage.dropped"
        
        # Total should be 4 (all providers)
        assert coverage.get('total') == 4, f"Expected total=4, got {coverage.get('total')}"
        
        # Sum of aligned + dropped should equal total
        assert coverage.get('aligned', 0) + coverage.get('dropped', 0) == coverage.get('total', 0), \
            "aligned + dropped should equal total"
            
    def test_aligned_signals_have_anchorTs(self):
        """Each aligned signal MUST have anchorTs field"""
        resp = requests.get(f"{BASE_URL}/api/meta-brain-v2/signals/aligned?asset=BTC&horizon=7", timeout=10)
        data = resp.json()
        
        aligned = data.get('aligned', [])
        anchor_ts = data.get('anchorTs')
        
        for sig in aligned:
            assert 'anchorTs' in sig, f"Aligned signal {sig.get('module')} missing anchorTs"
            assert sig.get('anchorTs') == anchor_ts, f"Signal anchorTs {sig.get('anchorTs')} doesn't match response anchorTs {anchor_ts}"
            
    def test_dropped_signals_have_reason(self):
        """Each dropped signal must have reason: STALE/SKEW/TIMEOUT/ERROR"""
        resp = requests.get(f"{BASE_URL}/api/meta-brain-v2/signals/aligned?asset=BTC&horizon=7", timeout=10)
        data = resp.json()
        
        dropped = data.get('dropped', [])
        valid_reasons = ['STALE', 'SKEW', 'TIMEOUT', 'ERROR', 'NO_DATA']
        
        for d in dropped:
            assert 'module' in d, f"Dropped item missing 'module': {d}"
            assert 'reason' in d, f"Dropped signal {d.get('module')} missing 'reason'"
            reason = d.get('reason')
            assert reason in valid_reasons, f"Invalid drop reason '{reason}' for {d.get('module')}. Valid: {valid_reasons}"
            print(f"  Dropped: {d.get('module')} - reason={reason}")
            
    def test_aligned_has_arrays(self):
        """Response must have aligned and dropped arrays"""
        resp = requests.get(f"{BASE_URL}/api/meta-brain-v2/signals/aligned?asset=BTC&horizon=7", timeout=10)
        data = resp.json()
        
        assert 'aligned' in data, "Missing 'aligned' array"
        assert 'dropped' in data, "Missing 'dropped' array"
        assert isinstance(data.get('aligned'), list), "aligned should be array"
        assert isinstance(data.get('dropped'), list), "dropped should be array"


class TestMetaBrainV1Compatibility:
    """Verify Meta Brain v1 routes still work (no breaking changes)"""
    
    def test_v1_invariants_endpoint_works(self):
        """GET /api/v10/meta-brain/invariants should still work"""
        resp = requests.get(f"{BASE_URL}/api/v10/meta-brain/invariants", timeout=5)
        assert resp.status_code == 200, f"v1 invariants endpoint broken: status={resp.status_code}"
        
        data = resp.json()
        assert data.get('ok') is True, "v1 invariants should return ok=true"
        assert 'data' in data, "v1 invariants missing data field"
        
        inv_data = data.get('data', {})
        assert 'invariants' in inv_data, "v1 invariants missing invariants list"
        assert isinstance(inv_data.get('invariants'), list), "invariants should be array"
        print(f"  v1 invariants count: {len(inv_data.get('invariants', []))}")
        
    def test_v1_impact_rules_endpoint_works(self):
        """GET /api/v10/meta-brain/impact/rules should still work"""
        resp = requests.get(f"{BASE_URL}/api/v10/meta-brain/impact/rules", timeout=5)
        assert resp.status_code == 200, f"v1 impact/rules endpoint broken: status={resp.status_code}"
        
        data = resp.json()
        assert data.get('ok') is True, "v1 impact/rules should return ok=true"
        assert 'rules' in data, "v1 impact/rules missing rules field"


class TestProviderTimeout:
    """Verify providers have proper timeout handling"""
    
    def test_no_provider_causes_hang(self):
        """Total request time should not exceed reasonable threshold"""
        # Run multiple requests to verify consistent behavior
        max_duration = 0
        
        for _ in range(3):
            start = time.time()
            resp = requests.get(f"{BASE_URL}/api/meta-brain-v2/signals?asset=BTC&horizon=7", timeout=10)
            duration = (time.time() - start) * 1000
            max_duration = max(max_duration, duration)
            
            assert resp.status_code == 200
            
        # With 1200ms timeout per provider running in parallel, total should be well under 5s
        assert max_duration < 5000, f"Request took too long: {max_duration:.0f}ms. Possible provider timeout issue."
        print(f"  Max request duration over 3 runs: {max_duration:.0f}ms")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
