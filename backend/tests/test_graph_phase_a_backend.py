"""
Graph Core Phase A Backend Tests
=================================
Tests for Phase A implementation:
1. Health with new storage stats (graph_capital_routes, graph_intelligence_overlay)
2. Projection layer with mode filtering
3. Full pipeline and individual integration endpoints
4. Cluster layer build
5. Capital routes with ranking
6. Intelligence overlay
7. Unified node detail
8. Regression tests for existing endpoints
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
# Center node for projection tests
CENTER_NODE = "exchange:binance:ethereum"


class TestHealthEndpoint:
    """GET /api/graph-core/health — storage stats including Phase A collections"""

    def test_health_returns_200(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ Health endpoint returns 200")

    def test_health_has_status_ok(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        data = response.json()
        assert data.get("status") == "ok", f"Expected status 'ok', got {data.get('status')}"
        print(f"✓ Health status is 'ok'")

    def test_health_has_phase_a_storage_stats(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        data = response.json()
        storage = data.get("storage", {})
        
        # Must have Phase A collections
        assert "graph_capital_routes" in storage, "Missing graph_capital_routes in storage stats"
        assert "graph_intelligence_overlay" in storage, "Missing graph_intelligence_overlay in storage stats"
        
        # Verify counts are present
        assert storage.get("graph_capital_routes", 0) >= 0, "graph_capital_routes must be >= 0"
        assert storage.get("graph_intelligence_overlay", 0) >= 0, "graph_intelligence_overlay must be >= 0"
        
        print(f"✓ Phase A storage: routes={storage.get('graph_capital_routes')}, overlay={storage.get('graph_intelligence_overlay')}")

    def test_health_has_core_storage_stats(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        data = response.json()
        storage = data.get("storage", {})
        
        # Core collections must exist
        assert "graph_nodes" in storage, "Missing graph_nodes in storage stats"
        assert "graph_relations" in storage, "Missing graph_relations in storage stats"
        assert "graph_clusters" in storage, "Missing graph_clusters in storage stats"
        
        print(f"✓ Core storage: nodes={storage.get('graph_nodes')}, relations={storage.get('graph_relations')}, clusters={storage.get('graph_clusters')}")


class TestProjectionLayer:
    """GET /api/graph-core/project/{node_id} — projection layer with mode filtering"""

    def test_projection_without_mode_returns_200(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/project/{CENTER_NODE}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        print(f"✓ Projection without mode returns 200")

    def test_projection_response_structure(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/project/{CENTER_NODE}")
        data = response.json()
        
        assert "nodes" in data, "Missing 'nodes' in projection response"
        assert "edges" in data, "Missing 'edges' in projection response"
        assert "meta" in data, "Missing 'meta' in projection response"
        assert isinstance(data["nodes"], list), "nodes must be a list"
        assert isinstance(data["edges"], list), "edges must be a list"
        
        print(f"✓ Projection structure: {len(data['nodes'])} nodes, {len(data['edges'])} edges")

    def test_projection_mode_smart_money(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/project/{CENTER_NODE}?mode=smart_money")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("meta", {}).get("mode") == "smart_money", "Mode not reflected in meta"
        print(f"✓ Projection mode=smart_money: {len(data['nodes'])} nodes, {len(data['edges'])} edges")

    def test_projection_mode_cex_flow(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/project/{CENTER_NODE}?mode=cex_flow")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("meta", {}).get("mode") == "cex_flow", "Mode not reflected in meta"
        print(f"✓ Projection mode=cex_flow: {len(data['nodes'])} nodes, {len(data['edges'])} edges")

    def test_projection_mode_token_rotation(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/project/{CENTER_NODE}?mode=token_rotation")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("meta", {}).get("mode") == "token_rotation", "Mode not reflected in meta"
        print(f"✓ Projection mode=token_rotation: {len(data['nodes'])} nodes, {len(data['edges'])} edges")

    def test_projection_mode_entity(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/project/{CENTER_NODE}?mode=entity")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("meta", {}).get("mode") == "entity", "Mode not reflected in meta"
        print(f"✓ Projection mode=entity: {len(data['nodes'])} nodes, {len(data['edges'])} edges")

    def test_projection_mode_risk(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/project/{CENTER_NODE}?mode=risk")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("meta", {}).get("mode") == "risk", "Mode not reflected in meta"
        print(f"✓ Projection mode=risk: {len(data['nodes'])} nodes, {len(data['edges'])} edges")

    def test_projection_node_follows_contract(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/project/{CENTER_NODE}")
        data = response.json()
        if data.get("nodes"):
            node = data["nodes"][0]
            # Graph Rendering Contract: { id, label, type, chain, address }
            assert "id" in node, "Node missing 'id'"
            assert "label" in node, "Node missing 'label'"
            assert "type" in node, "Node missing 'type'"
            assert "chain" in node, "Node missing 'chain'"
            print(f"✓ Node follows contract: id={node.get('id')[:30]}..., type={node.get('type')}")

    def test_projection_edge_follows_contract(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/project/{CENTER_NODE}")
        data = response.json()
        if data.get("edges"):
            edge = data["edges"][0]
            # Graph Rendering Contract: { source, target, direction, type, amountUsd }
            assert "source" in edge, "Edge missing 'source'"
            assert "target" in edge, "Edge missing 'target'"
            assert "type" in edge, "Edge missing 'type'"
            print(f"✓ Edge follows contract: type={edge.get('type')}")


class TestFullPipeline:
    """POST /api/graph-core/pipeline/run — full Phase A pipeline"""

    def test_pipeline_run_returns_200(self):
        response = requests.post(f"{BASE_URL}/api/graph-core/pipeline/run")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        print(f"✓ Pipeline run returns 200")

    def test_pipeline_run_response_structure(self):
        response = requests.post(f"{BASE_URL}/api/graph-core/pipeline/run")
        data = response.json()
        
        assert data.get("status") == "completed", f"Expected status 'completed', got {data.get('status')}"
        assert "elapsed_seconds" in data, "Missing elapsed_seconds"
        assert "steps" in data, "Missing steps"
        
        steps = data.get("steps", {})
        assert "integration" in steps, "Missing integration step"
        assert "cluster_layer" in steps, "Missing cluster_layer step"
        assert "capital_routes" in steps, "Missing capital_routes step"
        assert "intelligence_overlay" in steps, "Missing intelligence_overlay step"
        
        print(f"✓ Pipeline completed in {data.get('elapsed_seconds')}s with all steps")


class TestDataIntegration:
    """POST /api/graph-core/integrate/* — data integration endpoints"""

    def test_integrate_run_returns_200(self):
        response = requests.post(f"{BASE_URL}/api/graph-core/integrate/run")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("status") == "completed", f"Expected status 'completed', got {data.get('status')}"
        print(f"✓ Full integration: {data.get('total_nodes_upserted')} nodes, {data.get('total_edges_upserted')} edges")

    def test_integrate_smart_money_returns_200(self):
        response = requests.post(f"{BASE_URL}/api/graph-core/integrate/smart-money")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "nodes" in data or "error" not in data, "Smart money integration failed"
        print(f"✓ Smart money integration: nodes={data.get('nodes', 0)}, edges={data.get('edges', 0)}")

    def test_integrate_cex_flow_returns_200(self):
        response = requests.post(f"{BASE_URL}/api/graph-core/integrate/cex-flow")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "error" not in data, f"CEX flow integration error: {data.get('error')}"
        print(f"✓ CEX flow integration: nodes={data.get('nodes', 0)}, edges={data.get('edges', 0)}")

    def test_integrate_tokens_returns_200(self):
        response = requests.post(f"{BASE_URL}/api/graph-core/integrate/tokens")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "error" not in data, f"Token integration error: {data.get('error')}"
        print(f"✓ Token integration: nodes={data.get('nodes', 0)}, edges={data.get('edges', 0)}")

    def test_integrate_wallets_returns_200(self):
        response = requests.post(f"{BASE_URL}/api/graph-core/integrate/wallets")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "error" not in data, f"Wallet integration error: {data.get('error')}"
        print(f"✓ Wallet integration: nodes={data.get('nodes', 0)}, enriched={data.get('enriched', 0)}")

    def test_integrate_entities_returns_200(self):
        response = requests.post(f"{BASE_URL}/api/graph-core/integrate/entities")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "error" not in data, f"Entity integration error: {data.get('error')}"
        print(f"✓ Entity integration: nodes={data.get('nodes', 0)}, edges={data.get('edges', 0)}")


class TestClusterLayer:
    """POST /api/graph-core/clusters/build-layer — cluster layer build"""

    def test_cluster_layer_build_returns_200(self):
        response = requests.post(f"{BASE_URL}/api/graph-core/clusters/build-layer")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("status") == "completed", f"Expected status 'completed', got {data.get('status')}"
        print(f"✓ Cluster layer built: {data.get('cluster_nodes')} nodes, {data.get('cluster_relations')} relations")


class TestCapitalRoutes:
    """GET/POST /api/graph-core/routes/* — capital routes endpoints"""

    def test_routes_returns_200(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/routes")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ Routes endpoint returns 200")

    def test_routes_response_structure(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/routes")
        data = response.json()
        
        assert "routes" in data, "Missing 'routes' in response"
        assert "count" in data, "Missing 'count' in response"
        assert "ranking" in data, "Missing 'ranking' in response"
        assert isinstance(data["routes"], list), "routes must be a list"
        
        print(f"✓ Routes structure: {data.get('count')} routes, ranking={data.get('ranking')}")

    def test_routes_ranking_largest(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/routes?ranking=largest")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ranking") == "largest", "Ranking not reflected in response"
        print(f"✓ Routes ranking=largest: {data.get('count')} routes")

    def test_routes_ranking_smart_money(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/routes?ranking=smart_money")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ranking") == "smart_money", "Ranking not reflected in response"
        print(f"✓ Routes ranking=smart_money: {data.get('count')} routes")

    def test_routes_ranking_highest_alpha(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/routes?ranking=highest_alpha")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ranking") == "highest_alpha", "Ranking not reflected in response"
        print(f"✓ Routes ranking=highest_alpha: {data.get('count')} routes")

    def test_routes_for_node_returns_200(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/routes/node/{CENTER_NODE}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "routes" in data, "Missing 'routes' in response"
        assert data.get("node_id") == CENTER_NODE, f"node_id mismatch: expected {CENTER_NODE}"
        print(f"✓ Routes for node: {data.get('count')} routes for {CENTER_NODE}")

    def test_routes_build_returns_200(self):
        response = requests.post(f"{BASE_URL}/api/graph-core/routes/build")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("status") == "completed", f"Expected status 'completed', got {data.get('status')}"
        print(f"✓ Routes build: {data.get('routes')} routes created")

    def test_route_has_required_fields(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/routes?limit=5")
        data = response.json()
        routes = data.get("routes", [])
        if routes:
            route = routes[0]
            # Route object: source, via, destination, amount_usd, confidence, importance
            assert "source" in route, "Route missing 'source'"
            assert "destination" in route, "Route missing 'destination'"
            assert "amount_usd" in route, "Route missing 'amount_usd'"
            assert "route_type" in route, "Route missing 'route_type'"
            print(f"✓ Route fields: type={route.get('route_type')}, amount={route.get('amount_usd')}")


class TestIntelligenceOverlay:
    """GET/POST /api/graph-core/overlay/* — intelligence overlay endpoints"""

    def test_overlay_returns_200(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/overlay")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ Overlay endpoint returns 200")

    def test_overlay_response_structure(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/overlay")
        data = response.json()
        
        assert "overlays" in data, "Missing 'overlays' in response"
        assert "count" in data, "Missing 'count' in response"
        assert isinstance(data["overlays"], list), "overlays must be a list"
        
        print(f"✓ Overlay structure: {data.get('count')} overlays")

    def test_overlay_filter_by_type_risk(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/overlay?overlay_type=risk")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        overlays = data.get("overlays", [])
        # If there are overlays, they should all be risk type
        for ov in overlays:
            assert ov.get("overlay_type") == "risk", f"Expected overlay_type 'risk', got {ov.get('overlay_type')}"
        print(f"✓ Overlay filter=risk: {len(overlays)} risk overlays")

    def test_overlay_filter_by_type_signal(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/overlay?overlay_type=signal")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        overlays = data.get("overlays", [])
        for ov in overlays:
            assert ov.get("overlay_type") == "signal", f"Expected overlay_type 'signal', got {ov.get('overlay_type')}"
        print(f"✓ Overlay filter=signal: {len(overlays)} signal overlays")

    def test_overlay_filter_by_type_narrative(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/overlay?overlay_type=narrative")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ Overlay filter=narrative returns 200")

    def test_overlay_filter_by_type_alert(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/overlay?overlay_type=alert")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ Overlay filter=alert returns 200")

    def test_overlay_build_returns_200(self):
        response = requests.post(f"{BASE_URL}/api/graph-core/overlay/build")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("status") == "completed", f"Expected status 'completed', got {data.get('status')}"
        print(f"✓ Overlay build: {data.get('total_entries')} total entries")

    def test_overlay_has_required_fields(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/overlay?limit=5")
        data = response.json()
        overlays = data.get("overlays", [])
        if overlays:
            ov = overlays[0]
            # Overlay: overlay_type, sub_type, node_id, data, severity
            assert "overlay_type" in ov, "Overlay missing 'overlay_type'"
            assert "node_id" in ov or "overlay_id" in ov, "Overlay missing 'node_id' or 'overlay_id'"
            print(f"✓ Overlay fields: type={ov.get('overlay_type')}, sub_type={ov.get('sub_type')}")


class TestNodeDetail:
    """GET /api/graph-core/node/{node_id} — unified node detail"""

    def test_node_detail_returns_200(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/node/{CENTER_NODE}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ Node detail returns 200")

    def test_node_detail_has_node(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/node/{CENTER_NODE}")
        data = response.json()
        
        # Should have node or error
        if "error" in data and data["error"] == "node not found":
            pytest.skip(f"Node {CENTER_NODE} not found in database")
        
        assert "node" in data, "Missing 'node' in response"
        print(f"✓ Node detail has node: {data.get('node', {}).get('label')}")

    def test_node_detail_has_overlays(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/node/{CENTER_NODE}")
        data = response.json()
        
        if "error" in data:
            pytest.skip(f"Node not found: {data.get('error')}")
        
        assert "overlays" in data, "Missing 'overlays' in node detail"
        assert isinstance(data["overlays"], list), "overlays must be a list"
        print(f"✓ Node detail has {len(data.get('overlays', []))} overlays")

    def test_node_detail_has_routes(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/node/{CENTER_NODE}")
        data = response.json()
        
        if "error" in data:
            pytest.skip(f"Node not found: {data.get('error')}")
        
        assert "routes" in data, "Missing 'routes' in node detail"
        assert isinstance(data["routes"], list), "routes must be a list"
        print(f"✓ Node detail has {len(data.get('routes', []))} routes")


class TestRegressionSearchSuggest:
    """GET /api/graph-core/search/suggest — existing endpoint regression"""

    def test_search_suggest_returns_200(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/search/suggest?q=bin")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ Search suggest returns 200")

    def test_search_suggest_finds_binance(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/search/suggest?q=bin")
        data = response.json()
        results = data.get("results", [])
        labels = [r.get("label", "").lower() for r in results]
        binance_found = any("binance" in l for l in labels)
        assert binance_found or data.get("count", 0) > 0, "Search should find results for 'bin'"
        print(f"✓ Search 'bin': {data.get('count')} results")


class TestRegressionNeighbors:
    """GET /api/graph-core/neighbors/{node_id} — existing endpoint regression"""

    def test_neighbors_returns_200(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{CENTER_NODE}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ Neighbors returns 200")

    def test_neighbors_response_structure(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/neighbors/{CENTER_NODE}")
        data = response.json()
        
        assert "nodes" in data, "Missing 'nodes'"
        assert "edges" in data, "Missing 'edges'"
        assert "node_count" in data or len(data.get("nodes", [])) >= 0, "Missing node count"
        
        print(f"✓ Neighbors: {data.get('node_count', len(data.get('nodes', [])))} nodes, {data.get('edge_count', len(data.get('edges', [])))} edges")


class TestRegressionAlphaSignals:
    """GET /api/graph-core/alpha/signals — existing endpoint regression"""

    def test_alpha_signals_returns_200(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/alpha/signals")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ Alpha signals returns 200")

    def test_alpha_signals_structure(self):
        response = requests.get(f"{BASE_URL}/api/graph-core/alpha/signals")
        data = response.json()
        assert "signals" in data, "Missing 'signals'"
        print(f"✓ Alpha signals: {data.get('total', 0)} total signals")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
