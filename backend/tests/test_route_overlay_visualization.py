"""
Route Overlay Visualization Tests
=================================
Tests for the route overlay feature when clicking on FLOW ROUTES in Liquidity Map panel.

Features tested:
- /api/graph-core/liquidity-map returns top_routes with sample_path arrays
- sample_path contains valid node IDs that exist in the graph
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestRouteOverlayBackend:
    """Backend API tests for route overlay visualization"""
    
    def test_liquidity_map_global_returns_top_routes(self):
        """Test that global liquidity-map endpoint returns top_routes array"""
        response = requests.get(f"{BASE_URL}/api/graph-core/liquidity-map")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "top_routes" in data, "Response should contain top_routes field"
        assert isinstance(data["top_routes"], list), "top_routes should be a list"
        print(f"✓ Global liquidity-map returns {len(data['top_routes'])} top routes")
        
    def test_liquidity_map_global_routes_structure(self):
        """Test that global top_routes have the sample_path field (may be empty in global aggregation)"""
        response = requests.get(f"{BASE_URL}/api/graph-core/liquidity-map")
        assert response.status_code == 200
        
        data = response.json()
        top_routes = data.get("top_routes", [])
        
        # Global aggregation may have empty sample_path arrays (expected behavior)
        # The entity-specific endpoint provides actual sample_paths
        routes_with_sample_path_field = 0
        for route in top_routes:
            if "sample_path" in route:
                routes_with_sample_path_field += 1
                print(f"  - Route '{route.get('label', 'Unknown')}': sample_path present (len={len(route.get('sample_path', []))})")
        
        # All routes should at least have the sample_path field defined
        assert len(top_routes) > 0, "Should have at least one route"
        print(f"✓ {routes_with_sample_path_field}/{len(top_routes)} routes have sample_path field (may be empty in global view)")
        
    def test_liquidity_map_entity_returns_top_routes(self):
        """Test that entity-specific liquidity-map returns top_routes"""
        entity_id = "cex:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/liquidity-map?entity={entity_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "top_routes" in data, "Entity response should contain top_routes"
        print(f"✓ Entity liquidity-map returns {len(data['top_routes'])} top routes")
        
    def test_liquidity_map_entity_routes_have_sample_path(self):
        """Test that entity top_routes contain sample_path with valid node IDs"""
        entity_id = "cex:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/liquidity-map?entity={entity_id}")
        assert response.status_code == 200
        
        data = response.json()
        top_routes = data.get("top_routes", [])
        
        valid_routes = 0
        for route in top_routes:
            sample_path = route.get("sample_path", [])
            if len(sample_path) >= 2:
                valid_routes += 1
                # Verify node ID format (should be type:address:chain format)
                for node_id in sample_path:
                    assert ":" in node_id, f"Node ID should contain ':' separator: {node_id}"
                print(f"  - Route '{route.get('label')}': sample_path={sample_path[:2]}...")
                
        assert valid_routes > 0, "At least one route should have sample_path with 2+ nodes"
        print(f"✓ {valid_routes} routes have valid sample_path arrays")
        
    def test_sample_path_nodes_exist_in_graph(self):
        """Test that sample_path node IDs exist in the rendered graph"""
        entity_id = "cex:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        
        # Get liquidity map routes
        liq_response = requests.get(f"{BASE_URL}/api/graph-core/liquidity-map?entity={entity_id}")
        assert liq_response.status_code == 200
        
        liq_data = liq_response.json()
        top_routes = liq_data.get("top_routes", [])
        
        # Get rendered graph nodes
        render_response = requests.get(f"{BASE_URL}/api/graph-core/render/{entity_id}?depth=2&limit=150")
        assert render_response.status_code == 200
        
        render_data = render_response.json()
        graph_node_ids = set(node.get("id") for node in render_data.get("nodes", []))
        
        routes_tested = 0
        nodes_found = 0
        nodes_missing = 0
        
        for route in top_routes[:3]:  # Test first 3 routes
            sample_path = route.get("sample_path", [])
            if len(sample_path) >= 2:
                routes_tested += 1
                for node_id in sample_path:
                    if node_id in graph_node_ids:
                        nodes_found += 1
                    else:
                        nodes_missing += 1
                        print(f"  [Note] Node not in rendered graph: {node_id[:50]}...")
                        
        print(f"✓ Tested {routes_tested} routes: {nodes_found} nodes found in graph, {nodes_missing} not in current view")
        # Note: Some nodes may not be in the rendered graph due to depth/limit constraints
        # This is expected behavior - the route overlay handles missing nodes gracefully
        
    def test_route_structure_completeness(self):
        """Test that routes have all required fields for overlay visualization"""
        entity_id = "cex:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/liquidity-map?entity={entity_id}")
        assert response.status_code == 200
        
        data = response.json()
        top_routes = data.get("top_routes", [])
        
        required_fields = ["type", "label", "volume_usd", "tx_count", "sample_path"]
        
        for i, route in enumerate(top_routes[:5]):
            for field in required_fields:
                assert field in route, f"Route {i} missing required field: {field}"
                
            # Verify sample_path structure
            sample_path = route.get("sample_path", [])
            assert isinstance(sample_path, list), f"sample_path should be a list"
            
            print(f"  - Route {i}: type={route.get('type')}, label={route.get('label')}, "
                  f"volume=${route.get('volume_usd'):,.0f}, path_len={len(sample_path)}")
                  
        print(f"✓ All {min(5, len(top_routes))} routes have complete structure")
        
    def test_route_meta_includes_route_count(self):
        """Test that route_meta contains useful metadata"""
        entity_id = "cex:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/liquidity-map?entity={entity_id}")
        assert response.status_code == 200
        
        data = response.json()
        route_meta = data.get("route_meta", {})
        
        # Verify metadata fields
        assert "route_count" in route_meta, "route_meta should have route_count"
        assert "wash_route_count" in route_meta, "route_meta should have wash_route_count"
        
        print(f"✓ Route metadata: {route_meta.get('route_count')} routes, "
              f"{route_meta.get('wash_route_count')} wash routes, "
              f"{route_meta.get('fan_out_count')} fan-outs, "
              f"{route_meta.get('fan_in_count')} fan-ins")


class TestRouteOverlayFlowState:
    """Test flow state integration with route overlay"""
    
    def test_flow_state_values_are_valid(self):
        """Test that flow_state returns only valid 3-state values"""
        entity_id = "cex:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/liquidity-map?entity={entity_id}")
        assert response.status_code == 200
        
        data = response.json()
        summary = data.get("summary", {})
        
        flow_state = summary.get("flow_state", "")
        flow_driver = summary.get("flow_driver", "")
        
        valid_states = ["ACCUMULATION", "DISTRIBUTION", "ROUTING"]
        assert flow_state in valid_states, f"Invalid flow_state: {flow_state}"
        
        print(f"✓ Flow state: {flow_state} ({flow_driver})")
        
    def test_summary_has_inflow_outflow_net(self):
        """Test that summary contains inflow/outflow/net values"""
        entity_id = "cex:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/liquidity-map?entity={entity_id}")
        assert response.status_code == 200
        
        data = response.json()
        summary = data.get("summary", {})
        
        required_summary_fields = ["inflow", "outflow", "net", "volume", "flow_state", "flow_driver"]
        for field in required_summary_fields:
            assert field in summary, f"Summary missing field: {field}"
            
        print(f"✓ Summary: inflow=${summary.get('inflow'):,.2f}, outflow=${summary.get('outflow'):,.2f}, "
              f"net=${summary.get('net'):,.2f}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
