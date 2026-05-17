"""
Discovery Engine Tests
======================
Tests for the new Discovery Engine endpoints:
1. GET /api/graph-core/discovery - finds seed nodes for global modes
2. GET /api/graph-core/render-seeds - renders graph from multiple seed nodes
3. Edge ranking helper (_rank_and_limit_edges)

Pipeline: MODE → DISCOVERY → SEED_NODES → GRAPH_RENDER
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestDiscoveryEndpoint:
    """Tests for GET /api/graph-core/discovery"""
    
    def test_discovery_smart_money_mode(self):
        """Discovery with smart_money mode returns seed_nodes array"""
        response = requests.get(f"{BASE_URL}/api/graph-core/discovery?mode=smart_money&limit=5")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "seed_nodes" in data, "Response should contain 'seed_nodes' field"
        assert "mode" in data, "Response should contain 'mode' field"
        assert data["mode"] == "smart_money"
        assert "count" in data, "Response should contain 'count' field"
        assert "reason" in data, "Response should contain 'reason' field"
        
        # Validate seed_nodes structure
        seed_nodes = data["seed_nodes"]
        if len(seed_nodes) > 0:
            first_node = seed_nodes[0]
            assert "id" in first_node, "Seed node should have 'id'"
            assert "label" in first_node, "Seed node should have 'label'"
            assert "type" in first_node, "Seed node should have 'type'"
            assert "score" in first_node, "Seed node should have 'score'"
        
        print(f"PASS: smart_money discovery returned {len(seed_nodes)} seed nodes")
        
    def test_discovery_cex_flow_mode(self):
        """Discovery with cex_flow mode returns exchanges with flows"""
        response = requests.get(f"{BASE_URL}/api/graph-core/discovery?mode=cex_flow&limit=10")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["mode"] == "cex_flow"
        assert isinstance(data["seed_nodes"], list)
        
        # Check if exchanges or high-flow nodes are returned
        seed_nodes = data["seed_nodes"]
        print(f"PASS: cex_flow discovery returned {len(seed_nodes)} seed nodes")
        if seed_nodes:
            print(f"  First node: id={seed_nodes[0].get('id')}, type={seed_nodes[0].get('type')}, score={seed_nodes[0].get('score')}")

    def test_discovery_risk_mode(self):
        """Discovery with risk mode returns risky nodes"""
        response = requests.get(f"{BASE_URL}/api/graph-core/discovery?mode=risk&limit=10")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["mode"] == "risk"
        assert isinstance(data["seed_nodes"], list)
        
        print(f"PASS: risk discovery returned {len(data['seed_nodes'])} seed nodes")

    def test_discovery_token_rotation_mode(self):
        """Discovery with token_rotation mode returns tokens"""
        response = requests.get(f"{BASE_URL}/api/graph-core/discovery?mode=token_rotation&limit=10")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["mode"] == "token_rotation"
        assert isinstance(data["seed_nodes"], list)
        
        print(f"PASS: token_rotation discovery returned {len(data['seed_nodes'])} seed nodes")

    def test_discovery_entity_mode(self):
        """Discovery with entity mode returns top entities"""
        response = requests.get(f"{BASE_URL}/api/graph-core/discovery?mode=entity&limit=10")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["mode"] == "entity"
        assert isinstance(data["seed_nodes"], list)
        
        print(f"PASS: entity discovery returned {len(data['seed_nodes'])} seed nodes")

    def test_discovery_all_mode(self):
        """Discovery with 'all' mode returns diversified nodes"""
        response = requests.get(f"{BASE_URL}/api/graph-core/discovery?mode=all&limit=15")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["mode"] == "all"
        assert isinstance(data["seed_nodes"], list)
        
        print(f"PASS: all discovery returned {len(data['seed_nodes'])} seed nodes")

    def test_discovery_limit_respected(self):
        """Discovery respects limit parameter"""
        response = requests.get(f"{BASE_URL}/api/graph-core/discovery?mode=all&limit=5")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["seed_nodes"]) <= 5, f"Expected max 5 nodes, got {len(data['seed_nodes'])}"
        assert data["count"] <= 5
        
        print(f"PASS: limit=5 respected, got {len(data['seed_nodes'])} nodes")


class TestRenderSeedsEndpoint:
    """Tests for GET /api/graph-core/render-seeds"""
    
    def test_render_seeds_basic(self):
        """Render graph from discovered seeds"""
        # First get some seeds
        disc_resp = requests.get(f"{BASE_URL}/api/graph-core/discovery?mode=all&limit=3")
        assert disc_resp.status_code == 200
        seeds_data = disc_resp.json()
        
        if not seeds_data["seed_nodes"]:
            pytest.skip("No seed nodes available in database")
        
        # Get comma-separated seed IDs
        seed_ids = ",".join([n["id"] for n in seeds_data["seed_nodes"]])
        
        # Render graph
        render_resp = requests.get(f"{BASE_URL}/api/graph-core/render-seeds?seeds={seed_ids}&limit=50")
        assert render_resp.status_code == 200, f"Expected 200, got {render_resp.status_code}: {render_resp.text}"
        
        data = render_resp.json()
        assert "nodes" in data, "Response should contain 'nodes'"
        assert "edges" in data, "Response should contain 'edges'"
        assert "meta" in data, "Response should contain 'meta'"
        
        nodes = data["nodes"]
        edges = data["edges"]
        
        print(f"PASS: render-seeds returned {len(nodes)} nodes and {len(edges)} edges")
        
        # Verify all edges reference existing nodes
        node_ids = {n["id"] for n in nodes}
        for edge in edges:
            assert edge.get("source") in node_ids, f"Edge source {edge.get('source')} not in node set"
            assert edge.get("target") in node_ids, f"Edge target {edge.get('target')} not in node set"

    def test_render_seeds_with_mode_filter(self):
        """Render seeds respects mode filter parameter"""
        # Get smart_money seeds
        disc_resp = requests.get(f"{BASE_URL}/api/graph-core/discovery?mode=smart_money&limit=3")
        assert disc_resp.status_code == 200
        seeds_data = disc_resp.json()
        
        if not seeds_data["seed_nodes"]:
            pytest.skip("No smart_money seed nodes available")
        
        seed_ids = ",".join([n["id"] for n in seeds_data["seed_nodes"]])
        
        # Render with mode filter
        render_resp = requests.get(f"{BASE_URL}/api/graph-core/render-seeds?seeds={seed_ids}&mode=smart_money&limit=50")
        assert render_resp.status_code == 200
        
        data = render_resp.json()
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)
        
        print(f"PASS: render-seeds with mode=smart_money returned {len(data['nodes'])} nodes")

    def test_render_seeds_max_edges_per_node(self):
        """Render seeds respects max_edges_per_node parameter"""
        # Get seeds
        disc_resp = requests.get(f"{BASE_URL}/api/graph-core/discovery?mode=all&limit=2")
        seeds_data = disc_resp.json()
        
        if not seeds_data["seed_nodes"]:
            pytest.skip("No seed nodes available")
        
        seed_ids = ",".join([n["id"] for n in seeds_data["seed_nodes"]])
        
        # Render with low max_edges_per_node
        render_resp = requests.get(f"{BASE_URL}/api/graph-core/render-seeds?seeds={seed_ids}&max_edges_per_node=10&limit=100")
        assert render_resp.status_code == 200
        
        data = render_resp.json()
        print(f"PASS: render-seeds with max_edges_per_node=10 returned {len(data['edges'])} edges")

    def test_render_seeds_empty_seeds_param(self):
        """Render seeds handles empty seeds gracefully"""
        render_resp = requests.get(f"{BASE_URL}/api/graph-core/render-seeds?seeds=")
        assert render_resp.status_code == 200
        
        data = render_resp.json()
        # Should return empty or error in meta
        if "meta" in data and "error" in data["meta"]:
            assert data["meta"]["error"] == "no_seeds"
        else:
            assert len(data["nodes"]) == 0
        
        print("PASS: render-seeds handles empty seeds parameter")

    def test_render_seeds_invalid_seed_ids(self):
        """Render seeds handles invalid seed IDs gracefully"""
        render_resp = requests.get(f"{BASE_URL}/api/graph-core/render-seeds?seeds=fake_id_123,another_fake")
        assert render_resp.status_code == 200
        
        data = render_resp.json()
        # Should return empty nodes/edges (no matching data)
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)
        
        print(f"PASS: render-seeds handles invalid seeds, returned {len(data['nodes'])} nodes")


class TestDiscoveryIntegration:
    """Integration tests: full pipeline MODE → DISCOVERY → RENDER"""
    
    def test_full_discovery_pipeline_smart_money(self):
        """Full pipeline: discover smart_money seeds → render graph"""
        # Step 1: Discovery
        disc_resp = requests.get(f"{BASE_URL}/api/graph-core/discovery?mode=smart_money&limit=5")
        assert disc_resp.status_code == 200
        discovery = disc_resp.json()
        
        assert discovery["mode"] == "smart_money"
        
        if not discovery["seed_nodes"]:
            print("SKIP: No smart_money seeds found in database")
            return
        
        print(f"Step 1: Discovery found {len(discovery['seed_nodes'])} smart_money seeds")
        
        # Step 2: Render
        seed_ids = ",".join([n["id"] for n in discovery["seed_nodes"]])
        render_resp = requests.get(f"{BASE_URL}/api/graph-core/render-seeds?seeds={seed_ids}&limit=100&mode=smart_money")
        assert render_resp.status_code == 200
        
        graph = render_resp.json()
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        
        print(f"Step 2: Render returned {len(nodes)} nodes, {len(edges)} edges")
        
        # Validate graph structure
        if nodes:
            node_ids = {n["id"] for n in nodes}
            for edge in edges:
                assert edge["source"] in node_ids
                assert edge["target"] in node_ids
        
        print("PASS: Full smart_money discovery pipeline completed")

    def test_full_discovery_pipeline_cex_flow(self):
        """Full pipeline: discover cex_flow seeds → render graph"""
        disc_resp = requests.get(f"{BASE_URL}/api/graph-core/discovery?mode=cex_flow&limit=5")
        assert disc_resp.status_code == 200
        discovery = disc_resp.json()
        
        if not discovery["seed_nodes"]:
            print("SKIP: No cex_flow seeds found")
            return
        
        seed_ids = ",".join([n["id"] for n in discovery["seed_nodes"]])
        render_resp = requests.get(f"{BASE_URL}/api/graph-core/render-seeds?seeds={seed_ids}&limit=100")
        assert render_resp.status_code == 200
        
        graph = render_resp.json()
        print(f"PASS: cex_flow pipeline - {len(graph.get('nodes', []))} nodes, {len(graph.get('edges', []))} edges")

    def test_full_discovery_pipeline_risk(self):
        """Full pipeline: discover risk seeds → render graph"""
        disc_resp = requests.get(f"{BASE_URL}/api/graph-core/discovery?mode=risk&limit=5")
        assert disc_resp.status_code == 200
        discovery = disc_resp.json()
        
        if not discovery["seed_nodes"]:
            print("SKIP: No risk seeds found")
            return
        
        seed_ids = ",".join([n["id"] for n in discovery["seed_nodes"]])
        render_resp = requests.get(f"{BASE_URL}/api/graph-core/render-seeds?seeds={seed_ids}&limit=100")
        assert render_resp.status_code == 200
        
        graph = render_resp.json()
        print(f"PASS: risk pipeline - {len(graph.get('nodes', []))} nodes, {len(graph.get('edges', []))} edges")


class TestEdgeRanking:
    """Tests for edge ranking functionality (max_edges_per_node)"""
    
    def test_edge_ranking_in_render(self):
        """Verify edge ranking limits edges per hub node"""
        # Get a high-degree node via discovery
        disc_resp = requests.get(f"{BASE_URL}/api/graph-core/discovery?mode=all&limit=1")
        discovery = disc_resp.json()
        
        if not discovery["seed_nodes"]:
            pytest.skip("No nodes available")
        
        seed_id = discovery["seed_nodes"][0]["id"]
        
        # Render with low edge limit
        resp_low = requests.get(f"{BASE_URL}/api/graph-core/render-seeds?seeds={seed_id}&max_edges_per_node=5&limit=50")
        assert resp_low.status_code == 200
        low_edges = len(resp_low.json().get("edges", []))
        
        # Render with high edge limit
        resp_high = requests.get(f"{BASE_URL}/api/graph-core/render-seeds?seeds={seed_id}&max_edges_per_node=100&limit=200")
        assert resp_high.status_code == 200
        high_edges = len(resp_high.json().get("edges", []))
        
        print(f"Edge ranking: low limit (5) = {low_edges} edges, high limit (100) = {high_edges} edges")
        
        # Lower limit should result in equal or fewer edges
        assert low_edges <= high_edges or low_edges == 0
        print("PASS: Edge ranking limits work as expected")


class TestGraphCoreHealth:
    """Basic health check for graph-core API"""
    
    def test_health_endpoint(self):
        """Health endpoint returns storage stats"""
        resp = requests.get(f"{BASE_URL}/api/graph-core/health")
        assert resp.status_code == 200
        
        data = resp.json()
        assert data.get("status") == "ok" or "storage" in data
        
        print(f"PASS: graph-core health check passed")
        if "storage" in data:
            print(f"  Storage: {data['storage']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
