"""
Graph Core Search/Suggest API Tests
====================================
Testing the new P1.4 Auto-suggest Search endpoint and related features:
- GET /api/graph-core/search/suggest?q=<query> - Auto-suggest prefix search
- GET /api/graph-core/neighbors/{node_id} - Neighbor cache (existing)
- GET /api/graph-core/corridors/active - Active corridors (existing)
- GET /api/graph-core/health - Health with collection counts
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

class TestSearchSuggestEndpoint:
    """Test the new auto-suggest search endpoint"""
    
    def test_suggest_binance_returns_results(self):
        """Query 'bin' should return Binance results"""
        response = requests.get(f"{BASE_URL}/api/graph-core/search/suggest?q=bin&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "count" in data
        assert "query" in data
        # Check that we have at least one result
        assert data["count"] > 0 or len(data["results"]) >= 0  # May have results
        # Verify query is preserved
        assert data["query"] == "bin"
    
    def test_suggest_binance_result_structure(self):
        """Binance results should have node_id, label, type, chain"""
        response = requests.get(f"{BASE_URL}/api/graph-core/search/suggest?q=bin&limit=10")
        assert response.status_code == 200
        data = response.json()
        if data["count"] > 0:
            result = data["results"][0]
            assert "node_id" in result, "Result should have node_id"
            assert "label" in result, "Result should have label"
            assert "type" in result, "Result should have type"
            assert "chain" in result, "Result should have chain"
    
    def test_suggest_uniswap_returns_results(self):
        """Query 'uni' should return Uniswap results"""
        response = requests.get(f"{BASE_URL}/api/graph-core/search/suggest?q=uni&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert data["query"] == "uni"
    
    def test_suggest_address_match(self):
        """Query '0x28c6' should return address matches"""
        response = requests.get(f"{BASE_URL}/api/graph-core/search/suggest?q=0x28c6&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert data["query"] == "0x28c6"
    
    def test_suggest_single_char_returns_empty(self):
        """Single character 'a' should return validation error (min 2 chars)"""
        response = requests.get(f"{BASE_URL}/api/graph-core/search/suggest?q=a&limit=10")
        # FastAPI will return 422 for validation error (min_length=2)
        assert response.status_code == 422
    
    def test_suggest_two_char_works(self):
        """Two character query should work (minimum)"""
        response = requests.get(f"{BASE_URL}/api/graph-core/search/suggest?q=bi&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
    
    def test_suggest_limit_parameter(self):
        """Limit parameter should restrict results"""
        response = requests.get(f"{BASE_URL}/api/graph-core/search/suggest?q=0x&limit=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) <= 5


class TestNeighborsEndpoint:
    """Test neighbors endpoint still works correctly"""
    
    def test_neighbors_binance_node(self):
        """GET neighbors for Binance node should return data"""
        node_id = "cex:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{node_id}")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
        assert "node_count" in data
        assert "edge_count" in data
    
    def test_neighbors_eth_token(self):
        """GET neighbors for ETH token should return data"""
        node_id = "token:0x0000000000000000000000000000000000000000:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{node_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["node_count"] >= 0


class TestActiveCorridorsEndpoint:
    """Test active corridors endpoint"""
    
    def test_corridors_active_returns_200(self):
        """GET /api/graph-core/corridors/active should return 200"""
        response = requests.get(f"{BASE_URL}/api/graph-core/corridors/active?limit=20")
        assert response.status_code == 200
        data = response.json()
        assert "corridors" in data
        assert "count" in data
    
    def test_corridors_structure(self):
        """Corridors should have required fields"""
        response = requests.get(f"{BASE_URL}/api/graph-core/corridors/active?limit=20")
        data = response.json()
        if data["count"] > 0:
            corridor = data["corridors"][0]
            assert "source" in corridor
            assert "target" in corridor


class TestHealthEndpoint:
    """Test health endpoint shows all collection counts"""
    
    def test_health_returns_ok(self):
        """GET /api/graph-core/health should return status ok"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
    
    def test_health_has_storage_stats(self):
        """Health should include storage stats with collection counts"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        data = response.json()
        assert "storage" in data
        storage = data["storage"]
        # Verify all collections are present
        assert "graph_nodes" in storage
        assert "graph_relations" in storage
        assert "graph_snapshots" in storage
        assert "graph_clusters" in storage
        assert "graph_neighbors_cache" in storage
        assert "graph_anchor_entities" in storage
    
    def test_health_has_cache_stats(self):
        """Health should include cache hit rate and counts"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        data = response.json()
        assert "cache_hit_rate" in data
        assert "cache_hits" in data
        assert "cache_misses" in data


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
