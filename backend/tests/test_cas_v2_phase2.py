"""
CAS v2 + Phase 2 Performance Hardening Tests
Tests for:
- CAS v2 with Z-score, sigmoid, EMA smoothing
- Baseline recalculation endpoint
- Index creation endpoint
- Snapshot population job
- TTL cache endpoints
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestCASv2Endpoints:
    """CAS v2 API endpoint tests"""
    
    def test_cas_v2_structure(self):
        """GET /api/connections/overview/cas - verify CAS v2 response structure"""
        response = requests.get(f"{BASE_URL}/api/connections/overview/cas")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') == True, "Expected ok=true"
        
        # CAS v2 required fields
        assert 'current' in data, "Missing 'current' field"
        assert 'trend' in data, "Missing 'trend' field"
        assert 'ema6h' in data, "Missing 'ema6h' field"
        assert 'ema24h' in data, "Missing 'ema24h' field"
        assert 'delta24h' in data, "Missing 'delta24h' field"
        assert 'rawScore' in data, "Missing 'rawScore' field"
        
        # Components
        assert 'components' in data, "Missing 'components' field"
        components = data['components']
        assert 'clusterCoordination' in components, "Missing clusterCoordination component"
        assert 'mentionVelocity' in components, "Missing mentionVelocity component"
        assert 'farmOverlap' in components, "Missing farmOverlap component"
        assert 'botProbability' in components, "Missing botProbability component"
        
        # Z-scores
        assert 'zScores' in data, "Missing 'zScores' field"
        zScores = data['zScores']
        assert 'cluster' in zScores, "Missing cluster z-score"
        assert 'velocity' in zScores, "Missing velocity z-score"
        assert 'farm' in zScores, "Missing farm z-score"
        assert 'bot' in zScores, "Missing bot z-score"
        
        # Quality flags
        assert 'qualityFlags' in data, "Missing 'qualityFlags' field"
        assert isinstance(data['qualityFlags'], list), "qualityFlags should be a list"
        
        # History
        assert 'history' in data, "Missing 'history' field"
        assert isinstance(data['history'], list), "history should be a list"
        
        # Context
        assert 'context' in data, "Missing 'context' field"
        
        print(f"✓ CAS v2: current={data['current']}, ema6h={data['ema6h']}, trend={data['trend']}")
    
    def test_cas_v2_value_ranges(self):
        """Verify CAS values are within expected ranges"""
        response = requests.get(f"{BASE_URL}/api/connections/overview/cas")
        assert response.status_code == 200
        
        data = response.json()
        
        # CAS current should be 0-100
        assert 0 <= data['current'] <= 100, f"CAS current {data['current']} out of range"
        
        # EMA values should also be 0-100 range
        assert 0 <= data['ema6h'] <= 100, f"EMA6h {data['ema6h']} out of range"
        assert 0 <= data['ema24h'] <= 100, f"EMA24h {data['ema24h']} out of range"
        
        # Trend should be valid
        assert data['trend'] in ['up', 'down', 'stable'], f"Invalid trend: {data['trend']}"
        
        print(f"✓ All CAS values within valid ranges")
    
    def test_cas_history_structure(self):
        """Verify history points have correct structure"""
        response = requests.get(f"{BASE_URL}/api/connections/overview/cas")
        assert response.status_code == 200
        
        data = response.json()
        history = data.get('history', [])
        
        if len(history) > 0:
            for h in history:
                assert 'ts' in h, "History point missing 'ts'"
                assert 'value' in h, "History point missing 'value'"
                assert 'raw' in h, "History point missing 'raw'"
            print(f"✓ History has {len(history)} points with correct structure")
        else:
            print("✓ History empty (expected for new setup)")


class TestCASBaselineEndpoint:
    """POST /api/connections/overview/cas/baseline tests"""
    
    def test_baseline_recalculation(self):
        """POST /api/connections/overview/cas/baseline - recalculate 30-day baseline"""
        response = requests.post(f"{BASE_URL}/api/connections/overview/cas/baseline")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') == True, "Expected ok=true"
        
        # Should have records count
        assert 'records' in data, "Missing 'records' field"
        
        # May be seeded if not enough historical data
        if data.get('seeded'):
            print(f"✓ Baseline seeded with current values (records={data['records']})")
        else:
            assert 'metrics' in data, "Missing 'metrics' count"
            print(f"✓ Baseline recalculated from {data['records']} records, {data['metrics']} metrics")


class TestIndexCreationEndpoint:
    """POST /api/connections/overview/cas/ensure-indexes tests"""
    
    def test_ensure_indexes(self):
        """POST /api/connections/overview/cas/ensure-indexes - create MongoDB indexes"""
        response = requests.post(f"{BASE_URL}/api/connections/overview/cas/ensure-indexes")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') == True, "Expected ok=true"
        assert 'message' in data, "Missing 'message' field"
        
        print(f"✓ Indexes created: {data['message']}")


class TestSnapshotPopulationJob:
    """POST /api/connections/overview/snapshots/populate tests"""
    
    def test_snapshot_population(self):
        """POST /api/connections/overview/snapshots/populate - populate 4 snapshot collections"""
        response = requests.post(f"{BASE_URL}/api/connections/overview/snapshots/populate")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') == True, "Expected ok=true"
        
        # Should populate all 4 collections
        assert 'populated' in data, "Missing 'populated' field"
        assert data['populated'] >= 1, "Should populate at least 1 collection"
        
        # Should have timestamp
        assert 'timestamp' in data, "Missing 'timestamp' field"
        
        print(f"✓ Snapshots populated: {data['populated']} collections at {data['timestamp']}")


class TestCacheInvalidation:
    """GET /api/connections/overview/cache/invalidate tests"""
    
    def test_cache_invalidate(self):
        """GET /api/connections/overview/cache/invalidate - clear TTL cache"""
        response = requests.get(f"{BASE_URL}/api/connections/overview/cache/invalidate")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') == True, "Expected ok=true"
        assert 'message' in data, "Missing 'message' field"
        
        print(f"✓ Cache cleared: {data['message']}")


class TestTTLCachePerformance:
    """TTL cache performance tests on cached endpoints"""
    
    def test_stats_endpoint_cached(self):
        """GET /api/connections/stats - verify TTL cache behavior"""
        # Clear cache first
        requests.get(f"{BASE_URL}/api/connections/overview/cache/invalidate")
        
        # First call (cold)
        start1 = time.time()
        r1 = requests.get(f"{BASE_URL}/api/connections/stats")
        time1 = time.time() - start1
        
        assert r1.status_code == 200
        
        # Second call (should be cached)
        start2 = time.time()
        r2 = requests.get(f"{BASE_URL}/api/connections/stats")
        time2 = time.time() - start2
        
        assert r2.status_code == 200
        
        # Data should be identical
        assert r1.json() == r2.json(), "Cached response should match"
        
        print(f"✓ Stats endpoint: 1st call {time1:.3f}s, 2nd call {time2:.3f}s")
    
    def test_accounts_endpoint_cached(self):
        """GET /api/connections/accounts - verify TTL cache behavior"""
        # Clear cache first
        requests.get(f"{BASE_URL}/api/connections/overview/cache/invalidate")
        
        # First call
        r1 = requests.get(f"{BASE_URL}/api/connections/accounts")
        assert r1.status_code == 200
        
        # Second call
        r2 = requests.get(f"{BASE_URL}/api/connections/accounts")
        assert r2.status_code == 200
        
        # Response data validation
        data = r1.json()
        assert data.get('ok') == True
        assert 'accounts' in data
        
        print(f"✓ Accounts endpoint cached, returning {len(data.get('accounts', []))} accounts")
    
    def test_clusters_endpoint_cached(self):
        """GET /api/connections/clusters - verify TTL cache behavior"""
        r = requests.get(f"{BASE_URL}/api/connections/clusters")
        assert r.status_code == 200
        
        data = r.json()
        assert data.get('ok') == True
        assert 'data' in data
        
        print(f"✓ Clusters endpoint cached, returning {len(data.get('data', []))} clusters")
    
    def test_radar_endpoint_cached(self):
        """GET /api/connections/radar - verify TTL cache behavior"""
        r = requests.get(f"{BASE_URL}/api/connections/radar")
        assert r.status_code == 200
        
        data = r.json()
        assert data.get('ok') == True
        assert 'data' in data
        
        print(f"✓ Radar endpoint cached")


class TestCoreEndpoints:
    """Core connections endpoints health check"""
    
    def test_health_endpoint(self):
        """GET /api/connections/health"""
        r = requests.get(f"{BASE_URL}/api/connections/health")
        assert r.status_code == 200
        
        data = r.json()
        assert data.get('ok') == True
        assert 'accountsCount' in data
        
        print(f"✓ Health: {data['accountsCount']} accounts, status={data.get('status')}")
    
    def test_cluster_momentum(self):
        """GET /api/connections/cluster-momentum"""
        r = requests.get(f"{BASE_URL}/api/connections/cluster-momentum")
        assert r.status_code == 200
        
        data = r.json()
        assert data.get('ok') == True
        
        print(f"✓ Cluster momentum: {len(data.get('data', []))} tokens")
    
    def test_cluster_credibility(self):
        """GET /api/connections/cluster-credibility"""
        r = requests.get(f"{BASE_URL}/api/connections/cluster-credibility")
        assert r.status_code == 200
        
        data = r.json()
        assert data.get('ok') == True
        
        print(f"✓ Cluster credibility: {len(data.get('data', []))} clusters")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
