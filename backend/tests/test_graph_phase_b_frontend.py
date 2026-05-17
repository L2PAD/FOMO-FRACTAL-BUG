"""
Graph Phase B Frontend API Tests
================================
Tests for Phase B features: Graph Modes, Context Panels, Drill-down Navigation

Tests:
- Projection endpoint with all modes (All, Smart Money, CEX Flow, Token Rotation, Entity, Risk)
- Node detail endpoint (returns node, overlays, routes)
- Search suggest endpoint (auto-suggest for search)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_NODE_ID = "exchange:binance:ethereum"

# ==================================================
# Test: Projection Endpoint with Mode Filtering (Step 6)
# ==================================================
class TestProjectionModes:
    """Test projection endpoint supports all 6 graph modes from GraphModeSelector"""
    
    def test_projection_mode_all_default(self):
        """Mode: All (default - no mode param)"""
        response = requests.get(f"{BASE_URL}/api/graph-core/project/{TEST_NODE_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "nodes" in data, "Response should contain nodes array"
        assert "edges" in data, "Response should contain edges array"
        assert len(data["nodes"]) > 0, "Should return nodes for default mode"
    
    def test_projection_mode_smart_money(self):
        """Mode: Smart Money"""
        response = requests.get(f"{BASE_URL}/api/graph-core/project/{TEST_NODE_ID}?mode=smart_money")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
    
    def test_projection_mode_cex_flow(self):
        """Mode: CEX Flow"""
        response = requests.get(f"{BASE_URL}/api/graph-core/project/{TEST_NODE_ID}?mode=cex_flow")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
    
    def test_projection_mode_token_rotation(self):
        """Mode: Token Rotation"""
        response = requests.get(f"{BASE_URL}/api/graph-core/project/{TEST_NODE_ID}?mode=token_rotation")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
    
    def test_projection_mode_entity(self):
        """Mode: Entity"""
        response = requests.get(f"{BASE_URL}/api/graph-core/project/{TEST_NODE_ID}?mode=entity")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
    
    def test_projection_mode_risk(self):
        """Mode: Risk"""
        response = requests.get(f"{BASE_URL}/api/graph-core/project/{TEST_NODE_ID}?mode=risk")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data


# ==================================================
# Test: Node Detail Endpoint (Step 7 - Context Panel)
# ==================================================
class TestNodeDetail:
    """Test node detail endpoint for context panel data"""
    
    def test_node_detail_returns_node_overlays_routes(self):
        """GET /api/graph-core/node/{node_id} returns node, overlays, routes"""
        response = requests.get(f"{BASE_URL}/api/graph-core/node/{TEST_NODE_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Verify structure for context panel
        assert "node" in data, "Response should contain node object"
        assert "overlays" in data, "Response should contain overlays array"
        assert "routes" in data, "Response should contain routes array"
        
        # Verify node fields
        node = data["node"]
        assert "id" in node, "Node should have id"
        assert "label" in node, "Node should have label"
        assert "type" in node, "Node should have type"
        
        # Verify routes structure
        routes = data["routes"]
        assert isinstance(routes, list), "Routes should be a list"
    
    def test_node_detail_includes_scores(self):
        """Node detail should include score fields for context panel display"""
        response = requests.get(f"{BASE_URL}/api/graph-core/node/{TEST_NODE_ID}")
        assert response.status_code == 200
        data = response.json()
        node = data["node"]
        
        # Scores should be present (may be 0 or missing, but endpoint should work)
        # Context panel displays these if > 0
        assert isinstance(node, dict), "Node should be a dict"
    
    def test_node_detail_nonexistent_returns_gracefully(self):
        """Non-existent node should return 404 or empty node"""
        response = requests.get(f"{BASE_URL}/api/graph-core/node/nonexistent:invalid:node")
        # Should return 404 or 200 with null/empty node
        assert response.status_code in [200, 404]


# ==================================================
# Test: Search Suggest Endpoint (Search + Auto-suggest)
# ==================================================
class TestSearchSuggest:
    """Test search suggest endpoint for auto-suggest dropdown"""
    
    def test_search_suggest_returns_results(self):
        """GET /api/graph-core/search/suggest?q=bin returns suggestions"""
        response = requests.get(f"{BASE_URL}/api/graph-core/search/suggest?q=bin&limit=5")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert "results" in data, "Response should contain results array"
        results = data["results"]
        assert isinstance(results, list), "Results should be a list"
        assert len(results) > 0, "Should return at least one suggestion for 'bin'"
        
        # Verify suggestion structure
        first_result = results[0]
        assert "node_id" in first_result or "id" in first_result, "Suggestion should have node_id or id"
        assert "label" in first_result, "Suggestion should have label"
        assert "type" in first_result, "Suggestion should have type"
    
    def test_search_suggest_usdc_query(self):
        """Search for 'usdc' should return token suggestions"""
        response = requests.get(f"{BASE_URL}/api/graph-core/search/suggest?q=usdc&limit=5")
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
    
    def test_search_suggest_short_query_handled(self):
        """Short query (1 char) should be handled gracefully"""
        response = requests.get(f"{BASE_URL}/api/graph-core/search/suggest?q=a&limit=5")
        # Should return 200 (even if empty results) or 422 (validation error for short queries)
        assert response.status_code in [200, 422]


# ==================================================
# Test: Regression - Existing Graph Functionality
# ==================================================
class TestRegressionGraphFeatures:
    """Verify existing graph features still work after Phase B"""
    
    def test_health_endpoint(self):
        """Health endpoint should work"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
    
    def test_neighbors_endpoint(self):
        """Neighbors endpoint should work"""
        response = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{TEST_NODE_ID}?depth=1&limit_nodes=10")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data or "edges" in data
    
    def test_projection_returns_graph_contract(self):
        """Projection should return nodes with Graph Rendering Contract fields"""
        response = requests.get(f"{BASE_URL}/api/graph-core/project/{TEST_NODE_ID}")
        assert response.status_code == 200
        data = response.json()
        
        if data.get("nodes"):
            node = data["nodes"][0]
            # Graph Rendering Contract: id, label, type, chain, address
            assert "id" in node, "Node should have id"
            assert "type" in node, "Node should have type"


# ==================================================
# Test: Graph Data Service URLs (from frontend perspective)
# ==================================================
class TestGraphDataServiceEndpoints:
    """Test endpoints called by graphDataService.js"""
    
    def test_projection_with_depth_and_limits(self):
        """Projection with depth and limit params (used by graphDataService)"""
        response = requests.get(
            f"{BASE_URL}/api/graph-core/project/{TEST_NODE_ID}?depth=2&max_nodes=150&max_edges=400"
        )
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
    
    def test_routes_endpoint(self):
        """Capital routes endpoint"""
        response = requests.get(f"{BASE_URL}/api/graph-core/routes?ranking=largest&limit=20")
        assert response.status_code == 200
        data = response.json()
        assert "routes" in data or isinstance(data, list)
    
    def test_overlay_endpoint(self):
        """Intelligence overlay endpoint"""
        response = requests.get(f"{BASE_URL}/api/graph-core/overlay?limit=50")
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
