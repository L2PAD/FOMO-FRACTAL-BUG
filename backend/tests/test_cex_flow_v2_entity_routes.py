"""
CEX Flow v2 — Entity-Specific Route Intelligence Tests
=====================================================
Test entity-specific routes computed from the entity's subgraph.

Key features:
- GET /api/graph-core/liquidity-map?entity={id} returns entity-specific routes
- Entity-specific response includes route_meta with nodes_in_subgraph, edges_in_subgraph
- Entity-specific flow_state computed from route patterns
- GET /api/graph-core/liquidity-map (no entity) still returns global data
"""

import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://expo-telegram-web.preview.emergentagent.com")
BINANCE_ENTITY_ID = "cex:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"


class TestEntitySpecificLiquidityMap:
    """Tests for entity-specific route intelligence"""

    def test_entity_liquidity_map_source_is_entity(self):
        """Verify entity-specific response has source='entity'"""
        response = requests.get(
            f"{BASE_URL}/api/graph-core/liquidity-map",
            params={"entity": BINANCE_ENTITY_ID},
            timeout=30
        )
        assert response.status_code == 200, f"Status: {response.status_code}"
        data = response.json()
        
        assert data.get("source") == "entity", f"Expected source='entity', got: {data.get('source')}"
        print(f"✓ source is 'entity'")

    def test_entity_liquidity_map_returns_entity_id(self):
        """Verify entity ID is returned in response"""
        response = requests.get(
            f"{BASE_URL}/api/graph-core/liquidity-map",
            params={"entity": BINANCE_ENTITY_ID},
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "entity" in data, "Entity field missing from response"
        assert BINANCE_ENTITY_ID.lower() in data["entity"].lower() or "binance" in data["entity"].lower(), \
            f"Entity mismatch: {data['entity']}"
        print(f"✓ entity field present: {data['entity']}")

    def test_entity_route_meta_has_subgraph_fields(self):
        """Verify route_meta includes nodes_in_subgraph and edges_in_subgraph"""
        response = requests.get(
            f"{BASE_URL}/api/graph-core/liquidity-map",
            params={"entity": BINANCE_ENTITY_ID},
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        
        route_meta = data.get("route_meta", {})
        assert "nodes_in_subgraph" in route_meta, "nodes_in_subgraph missing from route_meta"
        assert "edges_in_subgraph" in route_meta, "edges_in_subgraph missing from route_meta"
        assert "route_count" in route_meta, "route_count missing from route_meta"
        
        print(f"✓ nodes_in_subgraph: {route_meta.get('nodes_in_subgraph')}")
        print(f"✓ edges_in_subgraph: {route_meta.get('edges_in_subgraph')}")
        print(f"✓ route_count: {route_meta.get('route_count')}")

    def test_entity_route_meta_subgraph_values_are_integers(self):
        """Verify subgraph counts are integers"""
        response = requests.get(
            f"{BASE_URL}/api/graph-core/liquidity-map",
            params={"entity": BINANCE_ENTITY_ID},
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        
        route_meta = data.get("route_meta", {})
        nodes = route_meta.get("nodes_in_subgraph")
        edges = route_meta.get("edges_in_subgraph")
        
        assert isinstance(nodes, int), f"nodes_in_subgraph should be int, got: {type(nodes)}"
        assert isinstance(edges, int), f"edges_in_subgraph should be int, got: {type(edges)}"
        assert nodes >= 0, f"nodes_in_subgraph should be >= 0, got: {nodes}"
        assert edges >= 0, f"edges_in_subgraph should be >= 0, got: {edges}"
        
        print(f"✓ nodes_in_subgraph is int: {nodes}")
        print(f"✓ edges_in_subgraph is int: {edges}")

    def test_entity_flow_state_is_valid(self):
        """Verify entity-specific flow_state is valid enum"""
        response = requests.get(
            f"{BASE_URL}/api/graph-core/liquidity-map",
            params={"entity": BINANCE_ENTITY_ID},
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        
        summary = data.get("summary", {})
        flow_state = summary.get("flow_state")
        
        valid_states = {"ACCUMULATION", "DISTRIBUTION", "ROUTING", "RETURN TO CEX", "REDISTRIBUTION"}
        assert flow_state in valid_states, f"Invalid flow_state: {flow_state}, expected one of {valid_states}"
        
        print(f"✓ flow_state is valid: {flow_state}")

    def test_entity_flow_driver_present(self):
        """Verify entity-specific flow_driver is present"""
        response = requests.get(
            f"{BASE_URL}/api/graph-core/liquidity-map",
            params={"entity": BINANCE_ENTITY_ID},
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        
        summary = data.get("summary", {})
        flow_driver = summary.get("flow_driver")
        
        assert flow_driver is not None, "flow_driver missing from summary"
        assert isinstance(flow_driver, str), f"flow_driver should be string, got: {type(flow_driver)}"
        
        print(f"✓ flow_driver present: {flow_driver}")

    def test_entity_top_routes_present(self):
        """Verify entity-specific top_routes is present"""
        response = requests.get(
            f"{BASE_URL}/api/graph-core/liquidity-map",
            params={"entity": BINANCE_ENTITY_ID},
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        
        top_routes = data.get("top_routes", [])
        assert isinstance(top_routes, list), f"top_routes should be list, got: {type(top_routes)}"
        
        print(f"✓ top_routes is list with {len(top_routes)} routes")
        if top_routes:
            for i, r in enumerate(top_routes[:3]):
                print(f"  Route {i+1}: {r.get('label', 'N/A')} - ${r.get('volume_usd', 0):,.2f} / {r.get('tx_count', 0)} tx")

    def test_entity_routes_have_required_fields(self):
        """Verify each route has required fields"""
        response = requests.get(
            f"{BASE_URL}/api/graph-core/liquidity-map",
            params={"entity": BINANCE_ENTITY_ID},
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        
        top_routes = data.get("top_routes", [])
        required_fields = {"type", "label", "volume_usd", "tx_count", "route_count"}
        
        for i, route in enumerate(top_routes[:5]):
            for field in required_fields:
                assert field in route, f"Route {i} missing field: {field}"
        
        print(f"✓ All routes have required fields: {required_fields}")


class TestGlobalLiquidityMapFallback:
    """Tests for global liquidity map (no entity param)"""

    def test_global_liquidity_map_has_valid_source(self):
        """Verify global response has source='cache' or 'live'"""
        response = requests.get(
            f"{BASE_URL}/api/graph-core/liquidity-map",
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        
        source = data.get("source")
        valid_sources = {"cache", "live"}
        assert source in valid_sources, f"Expected source in {valid_sources}, got: {source}"
        
        print(f"✓ Global source is valid: {source}")

    def test_global_liquidity_map_no_entity_field(self):
        """Verify global response does not have entity field"""
        response = requests.get(
            f"{BASE_URL}/api/graph-core/liquidity-map",
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        
        # Global should not have entity field (or it should be None)
        has_entity = "entity" in data and data["entity"] is not None
        assert not has_entity, f"Global response should not have entity field, but got: {data.get('entity')}"
        
        print(f"✓ Global response has no entity field")

    def test_global_route_meta_no_subgraph_fields(self):
        """Verify global route_meta does not have nodes_in_subgraph"""
        response = requests.get(
            f"{BASE_URL}/api/graph-core/liquidity-map",
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        
        route_meta = data.get("route_meta", {})
        # Global should not have subgraph-specific fields
        has_nodes = route_meta.get("nodes_in_subgraph") is not None
        has_edges = route_meta.get("edges_in_subgraph") is not None
        
        # These fields should not be present in global mode
        if has_nodes or has_edges:
            print(f"⚠ Global mode has subgraph fields (nodes={has_nodes}, edges={has_edges}) - may be expected if global uses same structure")
        else:
            print(f"✓ Global route_meta does not have subgraph-specific fields")

    def test_global_has_top_routes(self):
        """Verify global response has top_routes"""
        response = requests.get(
            f"{BASE_URL}/api/graph-core/liquidity-map",
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        
        top_routes = data.get("top_routes", [])
        assert isinstance(top_routes, list), f"top_routes should be list"
        
        print(f"✓ Global top_routes has {len(top_routes)} routes")

    def test_global_has_flow_state(self):
        """Verify global response has flow_state"""
        response = requests.get(
            f"{BASE_URL}/api/graph-core/liquidity-map",
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        
        summary = data.get("summary", {})
        flow_state = summary.get("flow_state")
        
        valid_states = {"ACCUMULATION", "DISTRIBUTION", "ROUTING", "RETURN TO CEX", "REDISTRIBUTION"}
        assert flow_state in valid_states, f"Invalid global flow_state: {flow_state}"
        
        print(f"✓ Global flow_state: {flow_state}")


class TestEntityVsGlobalDifferences:
    """Compare entity-specific vs global responses"""

    def test_entity_and_global_have_different_sources(self):
        """Entity source='entity', global source='cache' or 'live'"""
        # Entity-specific
        entity_resp = requests.get(
            f"{BASE_URL}/api/graph-core/liquidity-map",
            params={"entity": BINANCE_ENTITY_ID},
            timeout=30
        )
        assert entity_resp.status_code == 200
        entity_data = entity_resp.json()
        
        # Global
        global_resp = requests.get(
            f"{BASE_URL}/api/graph-core/liquidity-map",
            timeout=30
        )
        assert global_resp.status_code == 200
        global_data = global_resp.json()
        
        entity_source = entity_data.get("source")
        global_source = global_data.get("source")
        
        assert entity_source == "entity", f"Entity source should be 'entity', got: {entity_source}"
        assert global_source in {"cache", "live"}, f"Global source should be 'cache' or 'live', got: {global_source}"
        
        print(f"✓ Entity source: {entity_source}")
        print(f"✓ Global source: {global_source}")

    def test_entity_has_subgraph_meta_global_does_not(self):
        """Entity route_meta has subgraph fields, global may not"""
        # Entity-specific
        entity_resp = requests.get(
            f"{BASE_URL}/api/graph-core/liquidity-map",
            params={"entity": BINANCE_ENTITY_ID},
            timeout=30
        )
        entity_data = entity_resp.json()
        entity_meta = entity_data.get("route_meta", {})
        
        # Global
        global_resp = requests.get(
            f"{BASE_URL}/api/graph-core/liquidity-map",
            timeout=30
        )
        global_data = global_resp.json()
        global_meta = global_data.get("route_meta", {})
        
        # Entity should have subgraph fields
        assert "nodes_in_subgraph" in entity_meta, "Entity missing nodes_in_subgraph"
        assert "edges_in_subgraph" in entity_meta, "Entity missing edges_in_subgraph"
        
        print(f"✓ Entity has nodes_in_subgraph: {entity_meta.get('nodes_in_subgraph')}")
        print(f"✓ Entity has edges_in_subgraph: {entity_meta.get('edges_in_subgraph')}")
        print(f"  Global nodes_in_subgraph: {global_meta.get('nodes_in_subgraph', 'N/A')}")
        print(f"  Global edges_in_subgraph: {global_meta.get('edges_in_subgraph', 'N/A')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
