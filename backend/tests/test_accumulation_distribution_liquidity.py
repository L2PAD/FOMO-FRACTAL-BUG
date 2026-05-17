"""
Accumulation/Distribution Node Ring Colors & Liquidity Map Panel Tests
======================================================================
Tests for:
1. Render endpoint node ring coloring (ACCUMULATION/DISTRIBUTION)
2. Ring opacity formula: |net|/volume clamped [0.35, 1.0]
3. Threshold filtering: |net| < volume * 0.05 → ring_color=null, flow_state=NEUTRAL
4. Liquidity Map API: inflow/outflow/net/volume/flow_state/from_aggregates/to_aggregates
5. Liquidity Map refresh endpoint
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com').rstrip('/')

# Entity ID from the test requirements (Binance hot wallet)
TEST_ENTITY_ID = "cex:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"


class TestRenderEndpointNodeRingColors:
    """Test GET /api/graph-core/render/{id} returns correct ring coloring fields"""

    def test_render_endpoint_returns_ring_fields(self):
        """Verify render endpoint returns ring_color, ring_opacity, flow_state fields on nodes"""
        url = f"{BASE_URL}/api/graph-core/render/{TEST_ENTITY_ID}?depth=2&limit=20"
        response = requests.get(url, timeout=30)

        print(f"Render endpoint status: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        nodes = data.get("nodes", [])

        print(f"Returned {len(nodes)} nodes")
        assert len(nodes) > 0, "Expected at least 1 node"

        # Check that all nodes have the required ring fields
        for node in nodes:
            assert "ring_color" in node, f"Node {node.get('id')} missing ring_color"
            assert "ring_opacity" in node, f"Node {node.get('id')} missing ring_opacity"
            assert "flow_state" in node, f"Node {node.get('id')} missing flow_state"

            # Verify flow_state is one of expected values
            flow_state = node.get("flow_state")
            assert flow_state in ["ACCUMULATION", "DISTRIBUTION", "NEUTRAL"], \
                f"Invalid flow_state '{flow_state}' for node {node.get('id')}"

            # Verify ring_color is correct for flow_state
            ring_color = node.get("ring_color")
            if flow_state == "ACCUMULATION":
                assert ring_color == "#22c55e", f"ACCUMULATION should have green ring (#22c55e), got {ring_color}"
            elif flow_state == "DISTRIBUTION":
                assert ring_color == "#EF4444", f"DISTRIBUTION should have red ring (#EF4444), got {ring_color}"
            elif flow_state == "NEUTRAL":
                assert ring_color is None, f"NEUTRAL should have null ring_color, got {ring_color}"

        print("All nodes have correct ring_color, ring_opacity, flow_state fields")

    def test_ring_opacity_clamping(self):
        """Verify ring_opacity is in range [0, 1.0] and clamped [0.35, 1.0] when active"""
        url = f"{BASE_URL}/api/graph-core/render/{TEST_ENTITY_ID}?depth=2&limit=30"
        response = requests.get(url, timeout=30)

        assert response.status_code == 200

        data = response.json()
        nodes = data.get("nodes", [])

        active_nodes = [n for n in nodes if n.get("ring_color") is not None]
        neutral_nodes = [n for n in nodes if n.get("ring_color") is None]

        print(f"Active ring nodes: {len(active_nodes)}, Neutral nodes: {len(neutral_nodes)}")

        # Check opacity for active nodes is clamped [0.35, 1.0]
        for node in active_nodes:
            opacity = node.get("ring_opacity", 0)
            assert 0.35 <= opacity <= 1.0, \
                f"Active node {node.get('id')} ring_opacity {opacity} not in [0.35, 1.0]"

        # Check opacity for neutral nodes is 0
        for node in neutral_nodes:
            opacity = node.get("ring_opacity", 0)
            assert opacity == 0, \
                f"Neutral node {node.get('id')} should have ring_opacity=0, got {opacity}"

        print("Ring opacity clamping verified")

    def test_flow_category_field_matches_flow_state(self):
        """Verify flow_category is lowercase version of flow_state"""
        url = f"{BASE_URL}/api/graph-core/render/{TEST_ENTITY_ID}?depth=2&limit=20"
        response = requests.get(url, timeout=30)

        assert response.status_code == 200

        data = response.json()
        nodes = data.get("nodes", [])

        for node in nodes:
            flow_state = node.get("flow_state", "")
            flow_category = node.get("flow_category", "")
            assert flow_category == flow_state.lower(), \
                f"flow_category '{flow_category}' should be lowercase of flow_state '{flow_state}'"

        print("flow_category matches lowercase flow_state for all nodes")


class TestLiquidityMapAPI:
    """Test GET/POST /api/graph-core/liquidity-map endpoints"""

    def test_liquidity_map_returns_summary_fields(self):
        """Verify liquidity-map returns inflow, outflow, net, volume, flow_state in summary"""
        url = f"{BASE_URL}/api/graph-core/liquidity-map"
        response = requests.get(url, timeout=30)

        print(f"Liquidity map status: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        summary = data.get("summary", {})

        print(f"Summary keys: {list(summary.keys())}")

        # Required fields in new summary structure
        required_fields = ["inflow", "outflow", "net", "volume", "flow_state"]
        for field in required_fields:
            assert field in summary, f"Missing required summary field: {field}"

        # Verify flow_state is valid
        flow_state = summary.get("flow_state")
        assert flow_state in ["ACCUMULATION", "DISTRIBUTION", "NEUTRAL"], \
            f"Invalid flow_state in summary: {flow_state}"

        # Verify numeric fields are present
        assert isinstance(summary.get("inflow"), (int, float)), "inflow should be numeric"
        assert isinstance(summary.get("outflow"), (int, float)), "outflow should be numeric"
        assert isinstance(summary.get("net"), (int, float)), "net should be numeric"
        assert isinstance(summary.get("volume"), (int, float)), "volume should be numeric"

        print(f"Summary verified: inflow={summary['inflow']}, outflow={summary['outflow']}, "
              f"net={summary['net']}, volume={summary['volume']}, flow_state={flow_state}")

    def test_liquidity_map_returns_from_to_aggregates(self):
        """Verify liquidity-map returns from_aggregates and to_aggregates objects"""
        url = f"{BASE_URL}/api/graph-core/liquidity-map"
        response = requests.get(url, timeout=30)

        assert response.status_code == 200

        data = response.json()

        # Check from_aggregates
        from_agg = data.get("from_aggregates", {})
        assert isinstance(from_agg, dict), "from_aggregates should be an object"
        print(f"from_aggregates keys: {list(from_agg.keys())}")

        # Check to_aggregates
        to_agg = data.get("to_aggregates", {})
        assert isinstance(to_agg, dict), "to_aggregates should be an object"
        print(f"to_aggregates keys: {list(to_agg.keys())}")

        # Expected keys in aggregates (CEX, Wallets, DEX, Bridge)
        expected_keys = ["CEX", "Wallets", "DEX", "Bridge"]
        for key in expected_keys:
            if key in from_agg:
                assert isinstance(from_agg[key], (int, float)), f"from_aggregates[{key}] should be numeric"
            if key in to_agg:
                assert isinstance(to_agg[key], (int, float)), f"to_aggregates[{key}] should be numeric"

        print("from_aggregates and to_aggregates verified")

    def test_liquidity_map_refresh(self):
        """Verify POST /api/graph-core/liquidity-map/refresh returns updated summary"""
        url = f"{BASE_URL}/api/graph-core/liquidity-map/refresh"
        response = requests.post(url, timeout=60)

        print(f"Liquidity map refresh status: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()

        # Should have status and summary
        assert "status" in data, "Refresh response should have 'status' field"
        assert data["status"] == "refreshed", f"Expected status 'refreshed', got {data['status']}"

        summary = data.get("summary", {})
        print(f"Refresh summary keys: {list(summary.keys())}")

        # Verify summary has new structure fields
        if summary:
            for field in ["inflow", "outflow", "net", "volume", "flow_state"]:
                assert field in summary, f"Refresh summary missing {field}"

        print("Liquidity map refresh verified")


class TestNodeRingColorFormula:
    """Test the mathematical formula for ring coloring"""

    def test_threshold_formula(self):
        """
        Verify threshold logic:
        - threshold = volume * 0.05
        - If |net| < threshold → ring_color=null, flow_state=NEUTRAL
        """
        url = f"{BASE_URL}/api/graph-core/render/{TEST_ENTITY_ID}?depth=2&limit=50"
        response = requests.get(url, timeout=30)

        assert response.status_code == 200

        data = response.json()
        edges = data.get("edges", [])
        nodes = data.get("nodes", [])

        print(f"Testing formula with {len(nodes)} nodes and {len(edges)} edges")

        # We can't directly test the formula server-side without knowing internal flow values,
        # but we can verify the constraints are met:
        # 1. NEUTRAL nodes must have ring_color=null and ring_opacity=0
        # 2. Active nodes must have opacity in [0.35, 1.0]

        neutral_count = 0
        active_count = 0
        
        for node in nodes:
            flow_state = node.get("flow_state")
            ring_color = node.get("ring_color")
            ring_opacity = node.get("ring_opacity", 0)

            if flow_state == "NEUTRAL":
                neutral_count += 1
                assert ring_color is None, f"NEUTRAL node should have ring_color=null"
                assert ring_opacity == 0, f"NEUTRAL node should have ring_opacity=0"
            else:
                active_count += 1
                assert ring_color is not None, f"Active node should have ring_color set"
                assert 0.35 <= ring_opacity <= 1.0, f"Active node opacity should be [0.35, 1.0]"

        print(f"Neutral nodes: {neutral_count}, Active nodes: {active_count}")
        print("Formula constraints verified")


class TestLiquidityMapFlowStateLogic:
    """Test flow state determination logic in liquidity map"""

    def test_flow_state_consistency(self):
        """
        Verify flow_state in summary is consistent with net flow direction:
        - net > 0 → ACCUMULATION (unless below threshold)
        - net < 0 → DISTRIBUTION (unless below threshold)
        - |net| < threshold OR volume=0 → NEUTRAL
        """
        url = f"{BASE_URL}/api/graph-core/liquidity-map"
        response = requests.get(url, timeout=30)

        assert response.status_code == 200

        data = response.json()
        summary = data.get("summary", {})

        inflow = summary.get("inflow", 0)
        outflow = summary.get("outflow", 0)
        net = summary.get("net", 0)
        volume = summary.get("volume", 0)
        flow_state = summary.get("flow_state", "")

        print(f"Inflow: {inflow}, Outflow: {outflow}, Net: {net}, Volume: {volume}, State: {flow_state}")

        # Check consistency
        threshold = volume * 0.05 if volume > 0 else 0

        if volume == 0 or abs(net) < threshold:
            assert flow_state == "NEUTRAL", \
                f"With net={net}, threshold={threshold}, expected NEUTRAL, got {flow_state}"
        elif net > 0:
            assert flow_state == "ACCUMULATION", \
                f"With positive net={net}, expected ACCUMULATION, got {flow_state}"
        else:
            assert flow_state == "DISTRIBUTION", \
                f"With negative net={net}, expected DISTRIBUTION, got {flow_state}"

        print("Flow state logic verified")


class TestHealthEndpoint:
    """Basic health check"""

    def test_graph_core_health(self):
        """Verify graph-core health endpoint is working"""
        url = f"{BASE_URL}/api/graph-core/health"
        response = requests.get(url, timeout=10)

        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok", f"Health check failed: {data}"
        print("Graph core health: OK")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
