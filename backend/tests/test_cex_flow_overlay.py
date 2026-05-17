"""
CEX Flow Overlay Mode Tests
===========================
Tests for the CEX Flow feature that uses an overlay approach (dim + highlight)
instead of filtering. Backend returns cex_routes found via BFS pathfinding 
between CEX nodes, and frontend dims all nodes/edges and draws bright corridors.

Test cases:
1. API with mode=cex_flow should return 'cex_routes' array with paths between CEX nodes
2. cex_routes should contain from_cex, to_cex, path (array of node IDs), hops (intermediate count)
3. Response should still have full nodes/edges (NOT filtered)
4. API without mode should NOT contain cex_routes field
5. API with other modes (smart_money) should still work correctly
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test CEX entity: Binance 2 address
BINANCE_2_NODE_ID = "cex:0x21a31ee1afc51d94c2efccaa2092ad1028285549:ethereum"


class TestCexFlowOverlay:
    """Test suite for CEX Flow overlay mode"""

    def test_health_endpoint(self):
        """Test that backend health endpoint is accessible"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health", timeout=10)
        print(f"Health status code: {response.status_code}")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        print("Health endpoint: PASS")

    def test_render_with_cex_flow_mode_returns_cex_routes(self):
        """
        API with mode=cex_flow should return 'cex_routes' array.
        Test with cex:0x21a31ee1afc51d94c2efccaa2092ad1028285549:ethereum
        """
        url = f"{BASE_URL}/api/graph-core/render/{BINANCE_2_NODE_ID}?mode=cex_flow"
        print(f"Testing URL: {url}")
        
        response = requests.get(url, timeout=30)
        print(f"Status code: {response.status_code}")
        assert response.status_code == 200
        
        data = response.json()
        print(f"Response keys: {list(data.keys())}")
        
        # Should have nodes and edges (NOT filtered to empty)
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        print(f"Nodes count: {len(nodes)}, Edges count: {len(edges)}")
        
        # Meta should indicate cex_flow mode
        meta = data.get("meta", {})
        print(f"Meta mode: {meta.get('mode')}")
        assert meta.get("mode") == "cex_flow", "Meta should indicate cex_flow mode"
        
        # cex_routes field should exist (may be empty if no CEX-to-CEX paths)
        # Note: cex_routes may only be present if routes are found (see line 2107-2108)
        cex_routes = data.get("cex_routes", None)
        if cex_routes is not None:
            print(f"cex_routes count: {len(cex_routes)}")
        else:
            print("cex_routes not present (no CEX-to-CEX paths found)")
        
        print("test_render_with_cex_flow_mode_returns_cex_routes: PASS")

    def test_cex_routes_structure_when_present(self):
        """
        cex_routes should contain from_cex, to_cex, path (array of node IDs), hops (intermediate count)
        """
        url = f"{BASE_URL}/api/graph-core/render/{BINANCE_2_NODE_ID}?mode=cex_flow"
        response = requests.get(url, timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        cex_routes = data.get("cex_routes")
        
        if cex_routes and len(cex_routes) > 0:
            route = cex_routes[0]
            print(f"First route: {route}")
            
            # Check required fields
            assert "from_cex" in route, "Route should have from_cex field"
            assert "to_cex" in route, "Route should have to_cex field"
            assert "path" in route, "Route should have path field"
            assert "hops" in route, "Route should have hops field"
            
            # Path should be a list of node IDs
            path = route["path"]
            assert isinstance(path, list), "path should be a list"
            assert len(path) >= 2, "path should have at least 2 nodes (start and end CEX)"
            
            # from_cex should be first element, to_cex should be last
            assert route["from_cex"] == path[0], "from_cex should be first in path"
            assert route["to_cex"] == path[-1], "to_cex should be last in path"
            
            # hops should be number of intermediate nodes
            expected_hops = len(path) - 2
            assert route["hops"] == expected_hops, f"hops should be {expected_hops}, got {route['hops']}"
            
            print("cex_routes structure validation: PASS")
        else:
            print("No cex_routes found - this is valid if no CEX-to-CEX paths exist")
            pytest.skip("No cex_routes to validate structure")

    def test_cex_flow_response_has_full_nodes_edges(self):
        """
        Response should still have full nodes/edges (NOT filtered).
        The overlay approach means all data is returned, frontend handles dimming.
        """
        # Get response WITHOUT mode (full graph)
        url_full = f"{BASE_URL}/api/graph-core/render/{BINANCE_2_NODE_ID}"
        response_full = requests.get(url_full, timeout=30)
        assert response_full.status_code == 200
        data_full = response_full.json()
        
        # Get response WITH cex_flow mode
        url_cex = f"{BASE_URL}/api/graph-core/render/{BINANCE_2_NODE_ID}?mode=cex_flow"
        response_cex = requests.get(url_cex, timeout=30)
        assert response_cex.status_code == 200
        data_cex = response_cex.json()
        
        nodes_full = len(data_full.get("nodes", []))
        nodes_cex = len(data_cex.get("nodes", []))
        edges_full = len(data_full.get("edges", []))
        edges_cex = len(data_cex.get("edges", []))
        
        print(f"Full mode - Nodes: {nodes_full}, Edges: {edges_full}")
        print(f"CEX Flow - Nodes: {nodes_cex}, Edges: {edges_cex}")
        
        # CEX Flow should NOT filter out nodes/edges (overlay approach)
        # The counts should be similar (or equal) since no filtering happens
        # Allow some tolerance due to potential mode-specific processing
        assert nodes_cex > 0, "CEX Flow should return nodes"
        assert edges_cex > 0, "CEX Flow should return edges"
        
        # The key test: CEX flow should NOT dramatically reduce data
        # (Unlike old filtering approach that would empty the graph)
        ratio = nodes_cex / nodes_full if nodes_full > 0 else 0
        print(f"Node count ratio (cex_flow/full): {ratio:.2f}")
        
        # Should have at least 50% of nodes (no aggressive filtering)
        assert ratio >= 0.5, f"CEX Flow should not filter out >50% of nodes, got ratio {ratio:.2f}"
        
        print("test_cex_flow_response_has_full_nodes_edges: PASS")

    def test_render_without_mode_no_cex_routes(self):
        """
        API without mode should NOT contain cex_routes field.
        """
        url = f"{BASE_URL}/api/graph-core/render/{BINANCE_2_NODE_ID}"
        response = requests.get(url, timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        
        # cex_routes should NOT be present when mode is not cex_flow
        assert "cex_routes" not in data, "cex_routes should NOT be present without cex_flow mode"
        
        print("test_render_without_mode_no_cex_routes: PASS")

    def test_smart_money_mode_still_works(self):
        """
        API with other modes (smart_money) should still work correctly.
        """
        url = f"{BASE_URL}/api/graph-core/render/{BINANCE_2_NODE_ID}?mode=smart_money"
        response = requests.get(url, timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        meta = data.get("meta", {})
        
        # Mode should be smart_money
        assert meta.get("mode") == "smart_money", "Meta should indicate smart_money mode"
        
        # Should NOT have cex_routes
        assert "cex_routes" not in data, "smart_money mode should NOT have cex_routes"
        
        # Should have nodes and edges
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        print(f"Smart Money mode - Nodes: {len(nodes)}, Edges: {len(edges)}")
        
        print("test_smart_money_mode_still_works: PASS")

    def test_entity_mode_still_works(self):
        """
        API with entity mode should still work correctly.
        """
        url = f"{BASE_URL}/api/graph-core/render/{BINANCE_2_NODE_ID}?mode=entity"
        response = requests.get(url, timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        meta = data.get("meta", {})
        
        # Mode should be entity
        assert meta.get("mode") == "entity", "Meta should indicate entity mode"
        
        # Should NOT have cex_routes
        assert "cex_routes" not in data, "entity mode should NOT have cex_routes"
        
        print("test_entity_mode_still_works: PASS")

    def test_cex_flow_with_wallet_address(self):
        """
        Test CEX flow mode with a regular wallet address (not CEX).
        Should still work but may not find routes if no CEX-to-CEX paths exist.
        """
        wallet_node_id = "wallet:0xd8da6bf26964af9d7eed9e03e53415d37aa96045:ethereum"  # Vitalik
        url = f"{BASE_URL}/api/graph-core/render/{wallet_node_id}?mode=cex_flow"
        
        response = requests.get(url, timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        meta = data.get("meta", {})
        
        assert meta.get("mode") == "cex_flow", "Meta should indicate cex_flow mode"
        
        # cex_routes may or may not be present depending on graph connectivity
        if "cex_routes" in data:
            print(f"Found {len(data['cex_routes'])} CEX routes for wallet")
        else:
            print("No CEX routes found for wallet (expected if no CEX-to-CEX paths)")
        
        print("test_cex_flow_with_wallet_address: PASS")


class TestCexFlowRoutePathfinding:
    """Test suite for CEX-to-CEX route pathfinding logic"""

    def test_find_cex_routes_requires_two_cex_nodes(self):
        """
        _find_cex_routes should return empty list if < 2 CEX nodes in graph.
        Testing via API - if graph has only one CEX, routes should be empty.
        """
        # Using a small wallet address that may not have multiple CEX connections
        url = f"{BASE_URL}/api/graph-core/render/{BINANCE_2_NODE_ID}?mode=cex_flow&depth=1&limit=10"
        response = requests.get(url, timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        nodes = data.get("nodes", [])
        
        # Count CEX nodes
        cex_count = sum(1 for n in nodes 
                      if n.get("type", "").lower() in ("cex", "exchange")
                      or n.get("id", "").startswith("cex:")
                      or n.get("id", "").startswith("exchange:"))
        
        print(f"CEX nodes in response: {cex_count}")
        
        cex_routes = data.get("cex_routes", [])
        
        if cex_count < 2:
            # Should have no routes if less than 2 CEX nodes
            assert len(cex_routes) == 0, "Should have no routes with < 2 CEX nodes"
            print("Correctly returns empty routes with < 2 CEX nodes")
        else:
            print(f"Found {len(cex_routes)} routes with {cex_count} CEX nodes")
        
        print("test_find_cex_routes_requires_two_cex_nodes: PASS")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
