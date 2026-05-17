"""
META BRAIN V2 — Signal Influence Tracking Tests (Phase 7.1)
============================================================
Tests for:
1. GET /influence endpoint with contributors array
2. activeModules and droppedModules arrays
3. Sorting by absolute impact
4. Existing endpoints still work
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8003').rstrip('/')

class TestInfluenceEndpoint:
    """Tests for GET /api/meta-brain-v2/influence endpoint"""

    def test_influence_returns_ok(self):
        """GET /influence returns ok:true"""
        resp = requests.get(f"{BASE_URL}/api/meta-brain-v2/influence")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('ok') is True, f"Expected ok:true, got: {data}"

    def test_influence_has_contributors_array(self):
        """GET /influence returns contributors array"""
        resp = requests.get(f"{BASE_URL}/api/meta-brain-v2/influence")
        data = resp.json()
        assert 'contributors' in data, "Missing contributors field"
        assert isinstance(data['contributors'], list), "contributors should be an array"

    def test_influence_contributor_structure(self):
        """Each contributor has module/weight/signal/impact/pctImpact"""
        resp = requests.get(f"{BASE_URL}/api/meta-brain-v2/influence")
        data = resp.json()
        contributors = data.get('contributors', [])
        
        # Should have at least some contributors
        assert len(contributors) > 0, "No contributors returned"
        
        required_fields = ['module', 'weight', 'signal', 'impact', 'pctImpact']
        for c in contributors:
            for field in required_fields:
                assert field in c, f"Contributor missing field: {field}"
            # Verify types
            assert isinstance(c['module'], str), f"module should be string"
            assert isinstance(c['weight'], (int, float)), f"weight should be number"
            assert isinstance(c['signal'], (int, float)), f"signal should be number"
            assert isinstance(c['impact'], (int, float)), f"impact should be number"
            assert isinstance(c['pctImpact'], (int, float)), f"pctImpact should be number"

    def test_influence_has_active_modules(self):
        """GET /influence returns activeModules array"""
        resp = requests.get(f"{BASE_URL}/api/meta-brain-v2/influence")
        data = resp.json()
        assert 'activeModules' in data, "Missing activeModules field"
        assert isinstance(data['activeModules'], list), "activeModules should be an array"
        # Should have some active modules
        assert len(data['activeModules']) > 0, "No active modules"

    def test_influence_has_dropped_modules(self):
        """GET /influence returns droppedModules array"""
        resp = requests.get(f"{BASE_URL}/api/meta-brain-v2/influence")
        data = resp.json()
        assert 'droppedModules' in data, "Missing droppedModules field"
        assert isinstance(data['droppedModules'], list), "droppedModules should be an array"

    def test_influence_has_verdict_score_confidence(self):
        """GET /influence returns verdict, score, confidence fields"""
        resp = requests.get(f"{BASE_URL}/api/meta-brain-v2/influence")
        data = resp.json()
        
        assert 'verdict' in data, "Missing verdict field"
        assert data['verdict'] in ['LONG', 'SHORT', 'NEUTRAL'], f"Invalid verdict: {data['verdict']}"
        
        assert 'score' in data, "Missing score field"
        assert isinstance(data['score'], (int, float)), "score should be number"
        
        assert 'confidence' in data, "Missing confidence field"
        assert isinstance(data['confidence'], (int, float)), "confidence should be number"

    def test_influence_has_regime(self):
        """GET /influence returns regime field"""
        resp = requests.get(f"{BASE_URL}/api/meta-brain-v2/influence")
        data = resp.json()
        assert 'regime' in data, "Missing regime field"
        assert isinstance(data['regime'], str), "regime should be string"

    def test_influence_contributors_sorted_by_abs_impact(self):
        """Contributors are sorted by absolute impact (highest first)"""
        resp = requests.get(f"{BASE_URL}/api/meta-brain-v2/influence")
        data = resp.json()
        contributors = data.get('contributors', [])
        
        if len(contributors) > 1:
            abs_impacts = [abs(c['impact']) for c in contributors]
            # Verify sorted in descending order
            for i in range(len(abs_impacts) - 1):
                assert abs_impacts[i] >= abs_impacts[i + 1], \
                    f"Contributors not sorted: {abs_impacts[i]} < {abs_impacts[i + 1]}"

    def test_influence_pct_impact_sums_to_1(self):
        """pctImpact values should sum close to 1 (100%)"""
        resp = requests.get(f"{BASE_URL}/api/meta-brain-v2/influence")
        data = resp.json()
        contributors = data.get('contributors', [])
        
        total_pct = sum(c['pctImpact'] for c in contributors)
        # Allow small floating point tolerance
        assert 0.99 <= total_pct <= 1.01 or total_pct == 0, \
            f"pctImpact values sum to {total_pct}, expected ~1.0"

    def test_influence_with_asset_param(self):
        """GET /influence accepts asset query parameter"""
        resp = requests.get(f"{BASE_URL}/api/meta-brain-v2/influence?asset=BTC")
        data = resp.json()
        assert data.get('ok') is True
        assert data.get('asset') == 'BTC'


class TestExistingEndpointsStillWork:
    """Verify existing Meta Brain V2 endpoints still work"""

    def test_signals_endpoint_works(self):
        """GET /signals returns ok:true"""
        resp = requests.get(f"{BASE_URL}/api/meta-brain-v2/signals")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('ok') is True
        assert 'signals' in data

    def test_state_endpoint_works(self):
        """GET /state returns ok:true"""
        resp = requests.get(f"{BASE_URL}/api/meta-brain-v2/state")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('ok') is True

    def test_policy_endpoint_works(self):
        """GET /policy returns ok:true"""
        resp = requests.get(f"{BASE_URL}/api/meta-brain-v2/policy")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('ok') is True
        assert 'regime' in data
        assert 'policy' in data

    def test_modules_endpoint_works(self):
        """GET /modules returns ok:true with modules array"""
        resp = requests.get(f"{BASE_URL}/api/meta-brain-v2/modules")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('ok') is True
        assert 'modules' in data
        assert isinstance(data['modules'], list)
        assert len(data['modules']) >= 4, "Expected at least 4 modules"

    def test_performance_endpoint_works(self):
        """GET /performance returns ok:true"""
        resp = requests.get(f"{BASE_URL}/api/meta-brain-v2/performance")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('ok') is True


class TestRunEndpointActiveDroppedModules:
    """Test POST /run returns activeModules and droppedModules"""

    def test_run_returns_active_and_dropped_modules(self):
        """POST /run response includes activeModules and droppedModules"""
        resp = requests.post(
            f"{BASE_URL}/api/meta-brain-v2/run",
            json={"asset": "BTC", "horizonDays": 7}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('ok') is True
        
        # Check activeModules
        assert 'activeModules' in data, "Missing activeModules in /run response"
        assert isinstance(data['activeModules'], list)
        
        # Check droppedModules
        assert 'droppedModules' in data, "Missing droppedModules in /run response"
        assert isinstance(data['droppedModules'], list)
        
        # droppedModules should have module+reason structure if any exist
        for dropped in data['droppedModules']:
            assert 'module' in dropped, "Dropped module missing 'module' field"
            assert 'reason' in dropped, "Dropped module missing 'reason' field"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
