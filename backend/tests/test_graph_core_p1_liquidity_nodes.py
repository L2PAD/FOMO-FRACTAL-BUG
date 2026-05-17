"""
Graph Core P1 Testing - Liquidity Map + Node Ranking + Cache Expansion
=======================================================================
Tests for:
- GET /api/graph-core/liquidity-map (summary with cex_inflow, cex_outflow, categories, top_routes)
- POST /api/graph-core/liquidity-map/refresh (rebuild and cache)
- GET /api/graph-core/nodes/top (sorted by importance_score)
- GET /api/graph-core/nodes/top?sort_by=degree (sorted by degree)
- GET /api/graph-core/health (cache ~152, snapshots ~81)
- GET /api/graph-core/search/suggest?q=bin (Binance results)
- GET /api/graph-core/neighbors/{node_id} (Binance neighbors)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestLiquidityMapEndpoint:
    """Test liquidity map API endpoints."""

    def test_get_liquidity_map_returns_200(self):
        """GET /api/graph-core/liquidity-map should return 200."""
        response = requests.get(f"{BASE_URL}/api/graph-core/liquidity-map", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert "source" in data
        print(f"[PASS] Liquidity map returned with source: {data.get('source')}")

    def test_liquidity_map_has_summary(self):
        """Liquidity map should have summary with cex_inflow, cex_outflow."""
        response = requests.get(f"{BASE_URL}/api/graph-core/liquidity-map", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        # Check summary exists
        assert "summary" in data
        summary = data["summary"]
        
        # Check required fields
        assert "cex_inflow" in summary
        assert "cex_outflow" in summary
        assert "cex_net_flow" in summary
        assert "total_volume" in summary
        
        print(f"[PASS] Summary: CEX inflow=${summary.get('cex_inflow')}, outflow=${summary.get('cex_outflow')}")

    def test_liquidity_map_has_categories(self):
        """Liquidity map should have flow categories."""
        response = requests.get(f"{BASE_URL}/api/graph-core/liquidity-map", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        assert "categories" in data
        categories = data["categories"]
        assert isinstance(categories, dict)
        
        # Should have at least some categories
        print(f"[PASS] Categories found: {list(categories.keys())}")

    def test_liquidity_map_has_top_routes(self):
        """Liquidity map should have top_routes list."""
        response = requests.get(f"{BASE_URL}/api/graph-core/liquidity-map", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        assert "top_routes" in data
        top_routes = data["top_routes"]
        assert isinstance(top_routes, list)
        
        if top_routes:
            route = top_routes[0]
            assert "route" in route
            assert "amount_usd" in route
            print(f"[PASS] Top route: {route.get('route')[:50]}... ${route.get('amount_usd')}")

    def test_refresh_liquidity_map(self):
        """POST /api/graph-core/liquidity-map/refresh should rebuild map."""
        response = requests.post(f"{BASE_URL}/api/graph-core/liquidity-map/refresh", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("status") == "refreshed"
        assert "summary" in data
        print(f"[PASS] Liquidity map refreshed, total_volume=${data['summary'].get('total_volume')}")


class TestNodesTopEndpoint:
    """Test nodes/top ranking endpoint."""

    def test_get_top_nodes_default_sort(self):
        """GET /api/graph-core/nodes/top should return nodes sorted by importance_score."""
        response = requests.get(f"{BASE_URL}/api/graph-core/nodes/top?limit=10", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        assert "nodes" in data
        assert "count" in data
        assert data.get("sort_by") == "importance_score"
        
        nodes = data["nodes"]
        assert len(nodes) > 0
        
        # Check first node has importance_score
        first_node = nodes[0]
        assert "importance_score" in first_node
        assert first_node["importance_score"] > 0
        
        print(f"[PASS] Top node: {first_node.get('label')} (score={first_node.get('importance_score'):.4f})")

    def test_get_top_nodes_sorted_by_degree(self):
        """GET /api/graph-core/nodes/top?sort_by=degree should sort by degree."""
        response = requests.get(f"{BASE_URL}/api/graph-core/nodes/top?sort_by=degree&limit=10", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("sort_by") == "degree"
        nodes = data["nodes"]
        
        # Verify sorted by degree descending
        if len(nodes) >= 2:
            assert nodes[0]["degree"] >= nodes[1]["degree"]
        
        print(f"[PASS] Top by degree: {nodes[0].get('label')} (degree={nodes[0].get('degree')})")

    def test_top_nodes_have_required_fields(self):
        """Top nodes should have id, label, type, degree, importance_score."""
        response = requests.get(f"{BASE_URL}/api/graph-core/nodes/top?limit=5", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        for node in data["nodes"]:
            assert "id" in node
            assert "label" in node
            assert "type" in node
            assert "degree" in node
            assert "importance_score" in node
        
        print(f"[PASS] All {len(data['nodes'])} nodes have required fields")


class TestHealthEndpoint:
    """Test health endpoint with updated stats."""

    def test_health_returns_ok(self):
        """GET /api/graph-core/health should return status: ok."""
        response = requests.get(f"{BASE_URL}/api/graph-core/health", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("status") == "ok"
        print("[PASS] Health status: ok")

    def test_health_has_expanded_cache(self):
        """Health should show cache ~152 entries (expanded from 61)."""
        response = requests.get(f"{BASE_URL}/api/graph-core/health", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        storage = data.get("storage", {})
        cache_count = storage.get("graph_neighbors_cache", 0)
        
        # Should be around 152 (expanded from 61)
        assert cache_count >= 100, f"Expected cache >= 100, got {cache_count}"
        print(f"[PASS] Cache entries: {cache_count} (target ~152)")

    def test_health_has_hot_snapshots(self):
        """Health should show snapshots ~81 (expanded from 29)."""
        response = requests.get(f"{BASE_URL}/api/graph-core/health", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        storage = data.get("storage", {})
        snapshot_count = storage.get("graph_snapshots", 0)
        
        # Should be around 81 (expanded from 29)
        assert snapshot_count >= 50, f"Expected snapshots >= 50, got {snapshot_count}"
        print(f"[PASS] Snapshots: {snapshot_count} (target ~81)")

    def test_health_all_collections(self):
        """Health should include all 6 collection counts."""
        response = requests.get(f"{BASE_URL}/api/graph-core/health", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        storage = data.get("storage", {})
        expected_keys = [
            "graph_nodes", "graph_relations", "graph_snapshots",
            "graph_clusters", "graph_neighbors_cache", "graph_anchor_entities"
        ]
        
        for key in expected_keys:
            assert key in storage, f"Missing {key} in storage stats"
        
        print(f"[PASS] All 6 collections present: nodes={storage['graph_nodes']}, relations={storage['graph_relations']}")


class TestSearchSuggestEndpoint:
    """Test search/suggest endpoint."""

    def test_suggest_binance_returns_results(self):
        """GET /api/graph-core/search/suggest?q=bin should return Binance results."""
        response = requests.get(f"{BASE_URL}/api/graph-core/search/suggest?q=bin", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        assert "results" in data
        assert "count" in data
        assert data["count"] > 0
        
        # Should include Binance
        labels = [r.get("label", "").lower() for r in data["results"]]
        assert any("binance" in l for l in labels)
        
        print(f"[PASS] Suggest 'bin': {data['count']} results including Binance")

    def test_suggest_result_structure(self):
        """Suggest results should have node_id, label, type, chain."""
        response = requests.get(f"{BASE_URL}/api/graph-core/search/suggest?q=bin", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        for result in data["results"]:
            assert "node_id" in result
            assert "label" in result
            assert "type" in result
            assert "chain" in result
        
        print("[PASS] All suggest results have required structure")


class TestNeighborsEndpoint:
    """Test neighbors endpoint for Binance node."""

    def test_binance_neighbors_returns_200(self):
        """GET /api/graph-core/neighbors/cex:0x28c6...:ethereum should return 200."""
        node_id = "cex:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{node_id}", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        assert "nodes" in data
        assert "edges" in data
        print(f"[PASS] Binance neighbors: {len(data['nodes'])} nodes, {len(data['edges'])} edges")

    def test_binance_neighbors_cached(self):
        """Binance neighbors should be cached (snapshot or cache)."""
        node_id = "cex:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{node_id}", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        # Should be from cache or snapshot
        assert data.get("cached") or data.get("source") in ["snapshot", "cache", "build"]
        print(f"[PASS] Source: {data.get('source')}, cached: {data.get('cached')}")

    def test_neighbors_have_importance_score(self):
        """Neighbor nodes should have importance_score field."""
        node_id = "cex:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{node_id}", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        # Check some nodes have importance_score
        nodes_with_score = [n for n in data["nodes"] if "importance_score" in n]
        assert len(nodes_with_score) > 0
        print(f"[PASS] {len(nodes_with_score)}/{len(data['nodes'])} nodes have importance_score")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
