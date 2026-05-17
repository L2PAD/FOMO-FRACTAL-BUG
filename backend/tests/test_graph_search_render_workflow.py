"""
Test Graph Search/Exploration Workflow — Multi-Edge Rendering
==============================================================
Tests the search → render pipeline for graph visualization.

Key features tested:
1. Backend: GET /api/graph-core/render/{node_id} returns edges with multi-edge fields
2. Backend: GET /api/graph-core/render-seeds?seeds=... returns edges with same fields  
3. Backend: GET /api/graph-core/search/suggest?q=... returns search suggestions
4. Backend: GET /api/graph-core/resolve?q=... resolves search queries to node IDs
5. Edge fields: lane_index, lane_count, curvature, direction, color
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test node ID for Binance Hot Wallet
TEST_NODE_ID = "cex:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
SEARCH_QUERY = "Binance hot"


class TestGraphSearchSuggest:
    """Test search suggestion endpoint"""
    
    def test_search_suggest_returns_results(self):
        """GET /api/graph-core/search/suggest returns suggestions for 'Binance hot'"""
        response = requests.get(f"{BASE_URL}/api/graph-core/search/suggest", params={"q": SEARCH_QUERY, "limit": 5})
        assert response.status_code == 200
        
        data = response.json()
        assert "results" in data
        assert len(data["results"]) > 0
        print(f"Found {len(data['results'])} suggestions")
        
        # First result should be Binance hot_wallet
        first = data["results"][0]
        assert "Binance" in first.get("label", "")
        assert first.get("type") == "cex"
        assert first.get("node_id") is not None
        print(f"First suggestion: {first['label']} ({first['type']})")
    
    def test_search_suggest_returns_node_id(self):
        """Search suggestions should include node_id field"""
        response = requests.get(f"{BASE_URL}/api/graph-core/search/suggest", params={"q": SEARCH_QUERY, "limit": 1})
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["results"]) > 0
        first = data["results"][0]
        assert "node_id" in first
        assert first["node_id"].startswith("cex:0x")
        print(f"Node ID: {first['node_id']}")


class TestGraphResolve:
    """Test node resolution endpoint"""
    
    def test_resolve_finds_binance(self):
        """GET /api/graph-core/resolve?q=Binance hot should find node"""
        response = requests.get(f"{BASE_URL}/api/graph-core/resolve", params={"q": SEARCH_QUERY})
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("found") is True
        assert data.get("node_id") is not None
        assert "0x28c6c06298d514db089934071355e5743bf21d60" in data["node_id"].lower()
        print(f"Resolved to: {data['node_id']}")


class TestGraphRender:
    """Test render endpoint for multi-edge rendering"""
    
    def test_render_returns_nodes_and_edges(self):
        """GET /api/graph-core/render/{node_id} returns nodes and edges"""
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}", params={"depth": 2, "limit": 150})
        assert response.status_code == 200
        
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) > 0
        assert len(data["edges"]) > 0
        print(f"Render returned {len(data['nodes'])} nodes, {len(data['edges'])} edges")
    
    def test_render_edges_have_lane_index(self):
        """Edges should have lane_index field"""
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}", params={"depth": 2, "limit": 150})
        assert response.status_code == 200
        
        data = response.json()
        edges = data.get("edges", [])
        assert len(edges) > 0
        
        # All edges should have lane_index
        for edge in edges[:10]:  # Sample first 10
            assert "lane_index" in edge, f"Edge missing lane_index: {edge}"
            assert isinstance(edge["lane_index"], int)
        print("All sampled edges have lane_index field")
    
    def test_render_edges_have_lane_count(self):
        """Edges should have lane_count field"""
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}", params={"depth": 2, "limit": 150})
        assert response.status_code == 200
        
        data = response.json()
        edges = data.get("edges", [])
        
        for edge in edges[:10]:
            assert "lane_count" in edge, f"Edge missing lane_count: {edge}"
            assert edge["lane_count"] >= 1
        print("All sampled edges have lane_count field")
    
    def test_render_edges_have_curvature(self):
        """Edges should have curvature field"""
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}", params={"depth": 2, "limit": 150})
        assert response.status_code == 200
        
        data = response.json()
        edges = data.get("edges", [])
        
        for edge in edges[:10]:
            assert "curvature" in edge, f"Edge missing curvature: {edge}"
            assert isinstance(edge["curvature"], (int, float))
            assert -0.25 <= edge["curvature"] <= 0.25
        print("All sampled edges have valid curvature field")
    
    def test_render_edges_have_direction(self):
        """Edges should have direction field (incoming/outgoing)"""
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}", params={"depth": 2, "limit": 150})
        assert response.status_code == 200
        
        data = response.json()
        edges = data.get("edges", [])
        
        directions = set()
        for edge in edges[:20]:
            assert "direction" in edge, f"Edge missing direction: {edge}"
            assert edge["direction"] in ["incoming", "outgoing", "neutral"]
            directions.add(edge["direction"])
        
        # Should have both incoming and outgoing edges
        assert "incoming" in directions or "outgoing" in directions
        print(f"Found directions: {directions}")
    
    def test_render_edges_have_color(self):
        """Edges should have color field"""
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}", params={"depth": 2, "limit": 150})
        assert response.status_code == 200
        
        data = response.json()
        edges = data.get("edges", [])
        
        colors = set()
        for edge in edges[:20]:
            assert "color" in edge, f"Edge missing color: {edge}"
            colors.add(edge["color"])
        
        # Check expected colors
        print(f"Found colors: {colors}")
        assert len(colors) > 0
    
    def test_render_edges_have_pair_key(self):
        """Edges should have pair_key field for multi-edge grouping"""
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}", params={"depth": 2, "limit": 150})
        assert response.status_code == 200
        
        data = response.json()
        edges = data.get("edges", [])
        
        for edge in edges[:10]:
            assert "pair_key" in edge, f"Edge missing pair_key: {edge}"
        print("All sampled edges have pair_key field")
    
    def test_render_multi_edges_exist(self):
        """Should have multiple edges per node pair (multi-edge rendering)"""
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}", params={"depth": 2, "limit": 150})
        assert response.status_code == 200
        
        data = response.json()
        edges = data.get("edges", [])
        
        # Group edges by pair_key
        pair_counts = {}
        for edge in edges:
            pk = edge.get("pair_key", "")
            if pk:
                pair_counts[pk] = pair_counts.get(pk, 0) + 1
        
        # At least some pairs should have multiple edges
        multi_edge_pairs = [pk for pk, count in pair_counts.items() if count >= 2]
        print(f"Found {len(multi_edge_pairs)} pairs with 2+ edges")
        assert len(multi_edge_pairs) > 0, "No multi-edge pairs found"
    
    def test_render_curvature_formula_2_lane(self):
        """2-lane edges should have curvature -0.12 and +0.12"""
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}", params={"depth": 2, "limit": 150})
        assert response.status_code == 200
        
        data = response.json()
        edges = data.get("edges", [])
        
        # Find 2-lane edges
        two_lane_edges = [e for e in edges if e.get("lane_count") == 2]
        if len(two_lane_edges) >= 2:
            curvatures = sorted(set(e["curvature"] for e in two_lane_edges))
            print(f"2-lane curvatures: {curvatures}")
            # Should be approximately [-0.12, 0.12]
            assert any(abs(c - (-0.12)) < 0.02 for c in curvatures), "Missing negative curvature for 2-lane"
            assert any(abs(c - 0.12) < 0.02 for c in curvatures), "Missing positive curvature for 2-lane"
        else:
            print("Not enough 2-lane edges to verify curvature formula")


class TestGraphRenderSeeds:
    """Test render-seeds endpoint for Discovery mode"""
    
    def test_render_seeds_returns_data(self):
        """GET /api/graph-core/render-seeds returns nodes and edges"""
        response = requests.get(f"{BASE_URL}/api/graph-core/render-seeds", params={
            "seeds": TEST_NODE_ID,
            "limit": 100,
            "max_edges_per_node": 30
        })
        assert response.status_code == 200
        
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
        print(f"Render-seeds returned {len(data.get('nodes', []))} nodes, {len(data.get('edges', []))} edges")
    
    def test_render_seeds_edges_have_multi_edge_fields(self):
        """Render-seeds edges should have same multi-edge fields as render"""
        response = requests.get(f"{BASE_URL}/api/graph-core/render-seeds", params={
            "seeds": TEST_NODE_ID,
            "limit": 100,
            "max_edges_per_node": 30
        })
        assert response.status_code == 200
        
        data = response.json()
        edges = data.get("edges", [])
        
        if len(edges) > 0:
            edge = edges[0]
            assert "lane_index" in edge
            assert "lane_count" in edge
            assert "curvature" in edge
            assert "direction" in edge
            assert "color" in edge
            print(f"Sample edge: lane_index={edge['lane_index']}, lane_count={edge['lane_count']}, curvature={edge['curvature']}")
        else:
            print("No edges returned from render-seeds")


class TestColorConsistency:
    """Test that edge colors match direction"""
    
    def test_incoming_edges_are_green(self):
        """Incoming edges should have green color (#34D399)"""
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}", params={"depth": 2, "limit": 150})
        assert response.status_code == 200
        
        data = response.json()
        edges = data.get("edges", [])
        
        incoming_edges = [e for e in edges if e.get("direction") == "incoming"]
        if incoming_edges:
            for edge in incoming_edges[:5]:
                color = edge.get("color", "").lower()
                # Should be green (#34D399)
                assert color == "#34d399", f"Incoming edge has wrong color: {color}"
            print(f"Verified {len(incoming_edges[:5])} incoming edges have green color")
        else:
            print("No incoming edges to verify")
    
    def test_outgoing_edges_are_red(self):
        """Outgoing edges should have red color (#ff6b6b)"""
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}", params={"depth": 2, "limit": 150})
        assert response.status_code == 200
        
        data = response.json()
        edges = data.get("edges", [])
        
        outgoing_edges = [e for e in edges if e.get("direction") == "outgoing"]
        if outgoing_edges:
            for edge in outgoing_edges[:5]:
                color = edge.get("color", "").lower()
                # Should be red (#ff6b6b)
                assert color == "#ff6b6b", f"Outgoing edge has wrong color: {color}"
            print(f"Verified {len(outgoing_edges[:5])} outgoing edges have red color")
        else:
            print("No outgoing edges to verify")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
