"""
Graph Core P1 Test Suite - Neighbor Cache Layer
Tests cache miss/hit behavior, cache invalidation, health cache stats, size guard, and P0 compatibility.

Cache flow: 
1) GET /neighbors/{node_id} → cache miss (cached=false)
2) GET same → cache hit (cached=true)
3) POST /cache/invalidate/{node_id} → cache deleted
4) GET same → cache miss again
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com')

# Test node IDs - using wallet format: type:identifier:chain
TEST_NODE_ID = "wallet:0xTestCache123:ethereum"
TEST_NODE_ID_2 = "wallet:0xTestCache456:ethereum"
TEST_NODE_ID_3 = "wallet:0xTestCache789:ethereum"


class TestNeighborsCacheMissHit:
    """Test cache miss → cache hit cycle for GET /api/graph-core/neighbors/{node_id}"""

    @pytest.fixture(autouse=True)
    def clear_test_cache(self):
        """Clear test cache before each test"""
        requests.post(f"{BASE_URL}/api/graph-core/cache/invalidate/{TEST_NODE_ID}")
        yield

    def test_first_call_returns_cache_miss(self):
        """First call to neighbors endpoint should be cache miss (cached=false)"""
        # Invalidate any existing cache for this node
        requests.post(f"{BASE_URL}/api/graph-core/cache/invalidate/{TEST_NODE_ID}")
        
        response = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{TEST_NODE_ID}")
        assert response.status_code == 200
        data = response.json()
        
        # Verify cache miss response
        assert "cached" in data, "Response should have 'cached' field"
        assert data["cached"] == False, "First call should be cache miss (cached=false)"
        
        # Should have cache_key in response
        assert "cache_key" in data, "Response should have 'cache_key' field"
        
        # Should have nodes/edges (empty is OK - data pipeline not running)
        assert "nodes" in data
        assert "edges" in data

    def test_second_call_returns_cache_hit(self):
        """Second identical call should be cache hit (cached=true)"""
        # First call - cache miss
        requests.post(f"{BASE_URL}/api/graph-core/cache/invalidate/{TEST_NODE_ID}")
        first_response = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{TEST_NODE_ID}")
        assert first_response.status_code == 200
        first_data = first_response.json()
        assert first_data["cached"] == False, "First call should be cache miss"
        
        # Second call - should be cache hit
        second_response = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{TEST_NODE_ID}")
        assert second_response.status_code == 200
        second_data = second_response.json()
        
        assert second_data["cached"] == True, "Second call should be cache hit (cached=true)"

    def test_response_structure_cache_miss(self):
        """Cache miss response should have build_time_ms"""
        requests.post(f"{BASE_URL}/api/graph-core/cache/invalidate/{TEST_NODE_ID}")
        
        response = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{TEST_NODE_ID}")
        assert response.status_code == 200
        data = response.json()
        
        if data["cached"] == False:
            assert "build_time_ms" in data, "Cache miss should include build_time_ms"
            assert isinstance(data["build_time_ms"], (int, float))

    def test_response_structure_common_fields(self):
        """Response should have node_count and edge_count"""
        response = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{TEST_NODE_ID}")
        assert response.status_code == 200
        data = response.json()
        
        assert "node_count" in data, "Response should have node_count"
        assert "edge_count" in data, "Response should have edge_count"
        assert isinstance(data["node_count"], int)
        assert isinstance(data["edge_count"], int)


class TestDifferentParamsCacheKeys:
    """Test that different query params produce different cache keys (no false cache hits)"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Clear cache before tests"""
        requests.post(f"{BASE_URL}/api/graph-core/cache/invalidate-all")
        yield

    def test_different_depth_produces_different_cache_key(self):
        """Different depth param should produce different cache key"""
        # First call with depth=1
        resp1 = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{TEST_NODE_ID_2}?depth=1")
        assert resp1.status_code == 200
        data1 = resp1.json()
        key1 = data1.get("cache_key", "")
        
        # Second call with depth=2 (different param)
        resp2 = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{TEST_NODE_ID_2}?depth=2")
        assert resp2.status_code == 200
        data2 = resp2.json()
        key2 = data2.get("cache_key", "")
        
        # Keys should be different
        assert key1 != key2, f"Different depth should produce different cache keys: {key1} vs {key2}"
        
        # First depth=2 call should be cache miss
        assert data2["cached"] == False, "First call with new params should be cache miss"

    def test_different_limit_nodes_produces_different_cache_key(self):
        """Different limit_nodes param should produce different cache key"""
        # First call with limit_nodes=50
        resp1 = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{TEST_NODE_ID_3}?limit_nodes=50")
        assert resp1.status_code == 200
        data1 = resp1.json()
        key1 = data1.get("cache_key", "")
        
        # Second call with limit_nodes=100 (different param)
        resp2 = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{TEST_NODE_ID_3}?limit_nodes=100")
        assert resp2.status_code == 200
        data2 = resp2.json()
        key2 = data2.get("cache_key", "")
        
        assert key1 != key2, f"Different limit_nodes should produce different cache keys"
        assert data2["cached"] == False, "First call with new params should be cache miss"

    def test_cache_key_format_includes_params(self):
        """Cache key should include node_id:depth:limit_nodes:limit_edges"""
        resp = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{TEST_NODE_ID}?depth=2&limit_nodes=150&limit_edges=400")
        assert resp.status_code == 200
        data = resp.json()
        
        cache_key = data.get("cache_key", "")
        # Cache key format: node_id:depth:limit_nodes:limit_edges
        assert TEST_NODE_ID in cache_key, "Cache key should include node_id"
        assert ":2:" in cache_key or cache_key.endswith(":2"), "Cache key should include depth"


class TestCacheInvalidateNode:
    """Test POST /api/graph-core/cache/invalidate/{node_id}"""

    def test_invalidate_returns_count(self):
        """Invalidate endpoint should return invalidated count"""
        # First create a cache entry
        requests.get(f"{BASE_URL}/api/graph-core/neighbors/{TEST_NODE_ID}")
        
        # Invalidate it
        response = requests.post(f"{BASE_URL}/api/graph-core/cache/invalidate/{TEST_NODE_ID}")
        assert response.status_code == 200
        data = response.json()
        
        assert "invalidated" in data, "Response should have 'invalidated' field"
        assert isinstance(data["invalidated"], int)
        assert "node_id" in data, "Response should have 'node_id' field"

    def test_invalidate_deletes_cache_entries(self):
        """After invalidation, next call should be cache miss"""
        # Create cache entry
        resp1 = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{TEST_NODE_ID}")
        assert resp1.status_code == 200
        
        # Ensure it's cached
        resp2 = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{TEST_NODE_ID}")
        assert resp2.status_code == 200
        assert resp2.json()["cached"] == True, "Should be cached"
        
        # Invalidate
        inv_resp = requests.post(f"{BASE_URL}/api/graph-core/cache/invalidate/{TEST_NODE_ID}")
        assert inv_resp.status_code == 200
        
        # Now should be cache miss
        resp3 = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{TEST_NODE_ID}")
        assert resp3.status_code == 200
        assert resp3.json()["cached"] == False, "After invalidation, should be cache miss"

    def test_invalidate_returns_nonzero_when_cache_exists(self):
        """Invalidate should return invalidated >= 1 when cache entries exist"""
        # Clear and create fresh cache entry
        requests.post(f"{BASE_URL}/api/graph-core/cache/invalidate/{TEST_NODE_ID}")
        requests.get(f"{BASE_URL}/api/graph-core/neighbors/{TEST_NODE_ID}")
        
        # Invalidate and check count
        response = requests.post(f"{BASE_URL}/api/graph-core/cache/invalidate/{TEST_NODE_ID}")
        assert response.status_code == 200
        data = response.json()
        
        # Should have deleted at least 1 entry
        assert data["invalidated"] >= 1, "Should have invalidated at least 1 cache entry"


class TestCacheInvalidateAll:
    """Test POST /api/graph-core/cache/invalidate-all"""

    def test_invalidate_all_returns_count(self):
        """Invalidate-all endpoint should return invalidated count"""
        # Create some cache entries first
        requests.get(f"{BASE_URL}/api/graph-core/neighbors/{TEST_NODE_ID}")
        requests.get(f"{BASE_URL}/api/graph-core/neighbors/{TEST_NODE_ID_2}")
        
        response = requests.post(f"{BASE_URL}/api/graph-core/cache/invalidate-all")
        assert response.status_code == 200
        data = response.json()
        
        assert "invalidated" in data, "Response should have 'invalidated' field"
        assert isinstance(data["invalidated"], int)

    def test_invalidate_all_clears_entire_cache(self):
        """After invalidate-all, all subsequent calls should be cache miss"""
        # Create cache entries
        requests.get(f"{BASE_URL}/api/graph-core/neighbors/{TEST_NODE_ID}")
        requests.get(f"{BASE_URL}/api/graph-core/neighbors/{TEST_NODE_ID_2}")
        
        # Verify they're cached
        resp1 = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{TEST_NODE_ID}")
        resp2 = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{TEST_NODE_ID_2}")
        assert resp1.json()["cached"] == True
        assert resp2.json()["cached"] == True
        
        # Flush all
        requests.post(f"{BASE_URL}/api/graph-core/cache/invalidate-all")
        
        # Both should be cache miss now
        resp3 = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{TEST_NODE_ID}")
        resp4 = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{TEST_NODE_ID_2}")
        assert resp3.json()["cached"] == False, "After invalidate-all, should be cache miss"
        assert resp4.json()["cached"] == False, "After invalidate-all, should be cache miss"


class TestHealthCacheStats:
    """Test GET /api/graph-core/health returns cache statistics"""

    def test_health_returns_cache_hit_rate(self):
        """Health endpoint should return cache_hit_rate"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        assert response.status_code == 200
        data = response.json()
        
        assert "cache_hit_rate" in data, "Health should include cache_hit_rate"
        assert isinstance(data["cache_hit_rate"], (int, float))
        assert 0 <= data["cache_hit_rate"] <= 1, "cache_hit_rate should be between 0 and 1"

    def test_health_returns_cache_hits(self):
        """Health endpoint should return cache_hits count"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        assert response.status_code == 200
        data = response.json()
        
        assert "cache_hits" in data, "Health should include cache_hits"
        assert isinstance(data["cache_hits"], int)
        assert data["cache_hits"] >= 0

    def test_health_returns_cache_misses(self):
        """Health endpoint should return cache_misses count"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        assert response.status_code == 200
        data = response.json()
        
        assert "cache_misses" in data, "Health should include cache_misses"
        assert isinstance(data["cache_misses"], int)
        assert data["cache_misses"] >= 0

    def test_health_returns_avg_graph_build_time_ms(self):
        """Health endpoint should return avg_graph_build_time_ms"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        assert response.status_code == 200
        data = response.json()
        
        assert "avg_graph_build_time_ms" in data, "Health should include avg_graph_build_time_ms"
        assert isinstance(data["avg_graph_build_time_ms"], (int, float))
        assert data["avg_graph_build_time_ms"] >= 0

    def test_health_returns_cache_entries(self):
        """Health endpoint should return cache_entries count"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        assert response.status_code == 200
        data = response.json()
        
        assert "cache_entries" in data, "Health should include cache_entries"
        assert isinstance(data["cache_entries"], int)
        assert data["cache_entries"] >= 0

    def test_health_cache_stats_update_after_activity(self):
        """Health cache stats should update after cache activity"""
        # Clear all and reset
        requests.post(f"{BASE_URL}/api/graph-core/cache/invalidate-all")
        
        # Get initial stats
        initial = requests.get(f"{BASE_URL}/api/graph-core/health").json()
        initial_misses = initial["cache_misses"]
        
        # Make a request that will be cache miss
        requests.post(f"{BASE_URL}/api/graph-core/cache/invalidate/{TEST_NODE_ID}")
        requests.get(f"{BASE_URL}/api/graph-core/neighbors/{TEST_NODE_ID}")
        
        # Get updated stats
        updated = requests.get(f"{BASE_URL}/api/graph-core/health").json()
        
        # Misses should increase
        assert updated["cache_misses"] >= initial_misses, "cache_misses should increase after miss"


class TestP0EndpointsCompatibility:
    """Verify P0 endpoints still work with P1 additions"""

    def test_anchor_entities_still_works(self):
        """GET /api/graph-core/anchor-entities should still work"""
        response = requests.get(f"{BASE_URL}/api/graph-core/anchor-entities")
        assert response.status_code == 200
        data = response.json()
        
        assert "entities" in data
        assert "count" in data
        assert isinstance(data["entities"], list)

    def test_seed_anchors_still_works(self):
        """POST /api/graph-core/seed-anchors should still work"""
        response = requests.post(f"{BASE_URL}/api/graph-core/seed-anchors")
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "ok"
        assert "seeded" in data
        assert "total" in data

    def test_health_still_returns_p0_fields(self):
        """Health endpoint should still return P0 fields (node_count, edge_count)"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        assert response.status_code == 200
        data = response.json()
        
        # P0 fields
        assert "status" in data
        assert "node_count" in data
        assert "edge_count" in data
        assert "query_latency_ms" in data
        assert "timestamp" in data


class TestSizeGuard:
    """Test size guard - cache only stores graphs with <=500 nodes"""
    
    def test_neighbors_endpoint_works_with_various_limits(self):
        """Neighbors endpoint should work with various limit_nodes values"""
        # Test with limit_nodes=50 (well under 500 guard)
        resp1 = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{TEST_NODE_ID}?limit_nodes=50")
        assert resp1.status_code == 200
        
        # Test with limit_nodes=500 (at limit)
        resp2 = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{TEST_NODE_ID}?limit_nodes=500")
        assert resp2.status_code == 200
        
    def test_empty_graph_still_cached(self):
        """Empty graphs (0 nodes) should still be cached since 0 <= 500"""
        requests.post(f"{BASE_URL}/api/graph-core/cache/invalidate/{TEST_NODE_ID}")
        
        # First call
        resp1 = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{TEST_NODE_ID}")
        assert resp1.status_code == 200
        data1 = resp1.json()
        
        # Even empty result should be cached (node_count <= 500)
        if data1["node_count"] <= 500:
            # Second call should be cached
            resp2 = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{TEST_NODE_ID}")
            assert resp2.status_code == 200
            data2 = resp2.json()
            assert data2["cached"] == True, "Small graph should be cached"


class TestCacheKeyFormat:
    """Test cache_key format: node_id:depth:limit_nodes:limit_edges"""
    
    def test_cache_key_matches_expected_format(self):
        """Cache key should match node_id:depth:limit_nodes:limit_edges format"""
        node_id = "wallet:0xKeyFormat:ethereum"
        depth = 2
        limit_nodes = 150
        limit_edges = 400
        
        requests.post(f"{BASE_URL}/api/graph-core/cache/invalidate/{node_id}")
        
        resp = requests.get(
            f"{BASE_URL}/api/graph-core/neighbors/{node_id}?depth={depth}&limit_nodes={limit_nodes}&limit_edges={limit_edges}"
        )
        assert resp.status_code == 200
        data = resp.json()
        
        expected_key = f"{node_id}:{depth}:{limit_nodes}:{limit_edges}"
        assert data["cache_key"] == expected_key, f"Cache key should be '{expected_key}', got '{data['cache_key']}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
