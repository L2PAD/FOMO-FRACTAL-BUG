"""
Test Edge Lane Multi-Lane Render Endpoint
==========================================
Tests for GET /api/graph-core/render/{node_id}
Validates Arkham-style multi-lane edge aggregation with pre-computed:
- curvature (symmetric for lanes between same pair)
- width (log10 formula, max 1.8)
- opacity (log10 formula, max 0.55)
- color (#43d18d inflow, #ff6b6b outflow, #9ca3af internal)
- lane_index and lane_count fields
- meta object with raw_edge_count, lane_count, render_edge_count
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestRenderEndpoint:
    """Tests for /api/graph-core/render/{node_id}"""
    
    def test_render_endpoint_returns_200(self):
        """Render endpoint returns 200 for valid node_id"""
        node_id = "wallet:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}?depth=2&limit=50")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "nodes" in data, "Response should have 'nodes' field"
        assert "edges" in data, "Response should have 'edges' field"
        assert "meta" in data, "Response should have 'meta' field"
        print("PASS: Render endpoint returns 200 with correct structure")
    
    def test_render_edges_have_lane_fields(self):
        """All render edges have lane_index and lane_count fields"""
        node_id = "wallet:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}?depth=2&limit=50")
        assert response.status_code == 200
        data = response.json()
        edges = data.get("edges", [])
        
        if not edges:
            pytest.skip("No edges returned from render endpoint")
        
        for edge in edges:
            assert "lane_index" in edge, f"Edge {edge.get('id')} missing lane_index"
            assert "lane_count" in edge, f"Edge {edge.get('id')} missing lane_count"
            assert isinstance(edge["lane_index"], int), f"lane_index should be int"
            assert isinstance(edge["lane_count"], int), f"lane_count should be int"
            assert edge["lane_index"] >= 0, "lane_index should be >= 0"
            assert edge["lane_count"] >= 1, "lane_count should be >= 1"
            assert edge["lane_index"] < edge["lane_count"], f"lane_index {edge['lane_index']} should be < lane_count {edge['lane_count']}"
        
        print(f"PASS: All {len(edges)} edges have valid lane_index and lane_count fields")
    
    def test_render_edges_have_curvature(self):
        """All render edges have curvature field"""
        node_id = "wallet:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}?depth=2&limit=50")
        assert response.status_code == 200
        data = response.json()
        edges = data.get("edges", [])
        
        if not edges:
            pytest.skip("No edges returned from render endpoint")
        
        for edge in edges:
            assert "curvature" in edge, f"Edge {edge.get('id')} missing curvature"
            curv = edge["curvature"]
            assert isinstance(curv, (int, float)), f"curvature should be numeric, got {type(curv)}"
            assert -0.25 <= curv <= 0.25, f"curvature {curv} should be between -0.24 and 0.24"
        
        print(f"PASS: All {len(edges)} edges have valid curvature values")
    
    def test_symmetric_curvatures_for_same_pair(self):
        """Edges between same node pair have symmetric curvatures (e.g., -0.06 and +0.06)"""
        node_id = "wallet:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}?depth=2&limit=100")
        assert response.status_code == 200
        data = response.json()
        edges = data.get("edges", [])
        
        # Group edges by node pair
        pair_edges = {}
        for edge in edges:
            src, tgt = edge.get("source", ""), edge.get("target", "")
            pair_key = tuple(sorted([src, tgt]))
            if pair_key not in pair_edges:
                pair_edges[pair_key] = []
            pair_edges[pair_key].append(edge)
        
        # Find pairs with >1 lane
        multi_lane_pairs = {k: v for k, v in pair_edges.items() if len(v) > 1}
        
        if not multi_lane_pairs:
            pytest.skip("No multi-lane pairs found to test symmetry")
        
        for pair, edges_list in multi_lane_pairs.items():
            curvatures = sorted([e["curvature"] for e in edges_list])
            # For 2 lanes: should be symmetric around 0 (e.g., -0.06, 0.06)
            if len(edges_list) == 2:
                assert abs(curvatures[0] + curvatures[1]) < 0.01, \
                    f"Pair {pair} has non-symmetric curvatures: {curvatures}"
                print(f"  Pair {pair[:40]}... has symmetric curvatures: {curvatures}")
        
        print(f"PASS: {len(multi_lane_pairs)} multi-lane pairs have symmetric curvatures")
    
    def test_render_edges_have_width(self):
        """All render edges have width field with max 1.8"""
        node_id = "wallet:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}?depth=2&limit=50")
        assert response.status_code == 200
        data = response.json()
        edges = data.get("edges", [])
        
        if not edges:
            pytest.skip("No edges returned from render endpoint")
        
        for edge in edges:
            assert "width" in edge, f"Edge {edge.get('id')} missing width"
            width = edge["width"]
            assert isinstance(width, (int, float)), f"width should be numeric"
            assert 0 < width <= 1.8, f"width {width} should be between 0 and 1.8 (max)"
        
        print(f"PASS: All {len(edges)} edges have valid width values (max 1.8)")
    
    def test_render_edges_have_opacity(self):
        """All render edges have opacity field with max 0.55"""
        node_id = "wallet:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}?depth=2&limit=50")
        assert response.status_code == 200
        data = response.json()
        edges = data.get("edges", [])
        
        if not edges:
            pytest.skip("No edges returned from render endpoint")
        
        for edge in edges:
            assert "opacity" in edge, f"Edge {edge.get('id')} missing opacity"
            opacity = edge["opacity"]
            assert isinstance(opacity, (int, float)), f"opacity should be numeric"
            assert 0 < opacity <= 0.55, f"opacity {opacity} should be between 0 and 0.55 (max)"
        
        print(f"PASS: All {len(edges)} edges have valid opacity values (max 0.55)")
    
    def test_render_edges_have_color(self):
        """All render edges have color field with valid hex colors"""
        node_id = "wallet:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}?depth=2&limit=50")
        assert response.status_code == 200
        data = response.json()
        edges = data.get("edges", [])
        
        if not edges:
            pytest.skip("No edges returned from render endpoint")
        
        valid_colors = {"#43d18d", "#ff6b6b", "#9ca3af"}  # inflow, outflow, internal
        
        for edge in edges:
            assert "color" in edge, f"Edge {edge.get('id')} missing color"
            color = edge["color"]
            assert isinstance(color, str), f"color should be string"
            assert color.startswith("#"), f"color {color} should be hex"
            assert color in valid_colors, f"color {color} should be one of {valid_colors}"
        
        colors_found = set(e["color"] for e in edges)
        print(f"PASS: All {len(edges)} edges have valid colors. Colors found: {colors_found}")
    
    def test_color_logic_inflow_green(self):
        """Edges with target=center_node should be green (#43d18d)"""
        node_id = "wallet:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}?depth=2&limit=50")
        assert response.status_code == 200
        data = response.json()
        edges = data.get("edges", [])
        center = node_id
        
        inflow_edges = [e for e in edges if e.get("target") == center]
        
        if not inflow_edges:
            # Check meta - there might be no direct inflow edges to this exact node
            print("INFO: No direct inflow edges to center node found - testing internal color logic")
        else:
            for edge in inflow_edges:
                assert edge["color"] == "#43d18d", f"Inflow edge {edge.get('id')} should be green (#43d18d), got {edge['color']}"
            print(f"PASS: {len(inflow_edges)} inflow edges (target=center) are green")
    
    def test_color_logic_outflow_red(self):
        """Edges with source=center_node should be red (#ff6b6b)"""
        node_id = "wallet:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}?depth=2&limit=50")
        assert response.status_code == 200
        data = response.json()
        edges = data.get("edges", [])
        center = node_id
        
        outflow_edges = [e for e in edges if e.get("source") == center]
        
        if not outflow_edges:
            print("INFO: No direct outflow edges from center node found")
        else:
            for edge in outflow_edges:
                assert edge["color"] == "#ff6b6b", f"Outflow edge {edge.get('id')} should be red (#ff6b6b), got {edge['color']}"
            print(f"PASS: {len(outflow_edges)} outflow edges (source=center) are red")
    
    def test_meta_object_fields(self):
        """Meta object includes raw_edge_count, lane_count, render_edge_count"""
        node_id = "wallet:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}?depth=2&limit=50")
        assert response.status_code == 200
        data = response.json()
        meta = data.get("meta", {})
        
        assert "raw_edge_count" in meta, "meta should have raw_edge_count"
        assert "lane_count" in meta, "meta should have lane_count"
        assert "render_edge_count" in meta, "meta should have render_edge_count"
        
        assert isinstance(meta["raw_edge_count"], int), "raw_edge_count should be int"
        assert isinstance(meta["lane_count"], int), "lane_count should be int"
        assert isinstance(meta["render_edge_count"], int), "render_edge_count should be int"
        
        print(f"PASS: meta object has all required fields: raw_edge_count={meta['raw_edge_count']}, lane_count={meta['lane_count']}, render_edge_count={meta['render_edge_count']}")
    
    def test_max_lanes_per_pair_enforced(self):
        """Max 6 lanes per node pair enforced"""
        node_id = "wallet:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}?depth=2&limit=200")
        assert response.status_code == 200
        data = response.json()
        edges = data.get("edges", [])
        
        # Group edges by node pair
        pair_counts = {}
        for edge in edges:
            src, tgt = edge.get("source", ""), edge.get("target", "")
            pair_key = tuple(sorted([src, tgt]))
            pair_counts[pair_key] = pair_counts.get(pair_key, 0) + 1
        
        max_lanes = max(pair_counts.values()) if pair_counts else 0
        
        assert max_lanes <= 6, f"Max lanes per pair should be <= 6, got {max_lanes}"
        print(f"PASS: Max lanes per pair enforced. Max found: {max_lanes}, Pairs checked: {len(pair_counts)}")


class TestEdgeLaneService:
    """Tests for edge_lane_service.py functions"""
    
    def test_width_formula_log10(self):
        """Width computed via log10 formula (max 1.8)"""
        # Testing via render endpoint - high volume should produce max width
        node_id = "wallet:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}?depth=2&limit=100")
        assert response.status_code == 200
        data = response.json()
        edges = data.get("edges", [])
        
        if not edges:
            pytest.skip("No edges to test width formula")
        
        # Find edges with high volume
        high_vol_edges = [e for e in edges if e.get("volume_usd", 0) > 1000000]
        low_vol_edges = [e for e in edges if 0 < e.get("volume_usd", 0) < 1]
        
        # High volume edges should have higher width
        if high_vol_edges:
            max_width = max(e["width"] for e in high_vol_edges)
            assert max_width >= 1.5, f"High volume edges should have width >= 1.5, got {max_width}"
            print(f"  High volume edges width range: {min(e['width'] for e in high_vol_edges)} - {max_width}")
        
        print(f"PASS: Width formula appears correct. Total edges: {len(edges)}")
    
    def test_opacity_formula_log10(self):
        """Opacity computed via log10 formula (max 0.55)"""
        node_id = "wallet:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}?depth=2&limit=100")
        assert response.status_code == 200
        data = response.json()
        edges = data.get("edges", [])
        
        if not edges:
            pytest.skip("No edges to test opacity formula")
        
        # Find edges with high tx_count
        high_tx_edges = [e for e in edges if e.get("tx_count", 0) > 1000]
        
        if high_tx_edges:
            max_opacity = max(e["opacity"] for e in high_tx_edges)
            assert max_opacity >= 0.5, f"High tx_count edges should have opacity >= 0.5, got {max_opacity}"
            print(f"  High tx_count edges opacity range: {min(e['opacity'] for e in high_tx_edges)} - {max_opacity}")
        
        print(f"PASS: Opacity formula appears correct. Total edges: {len(edges)}")


class TestRenderQueryParams:
    """Tests for render endpoint query parameters"""
    
    def test_depth_parameter(self):
        """depth parameter works correctly"""
        node_id = "wallet:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        
        resp_d1 = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}?depth=1&limit=50")
        resp_d2 = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}?depth=2&limit=50")
        
        assert resp_d1.status_code == 200
        assert resp_d2.status_code == 200
        
        print(f"PASS: depth parameter works. depth=1: {len(resp_d1.json().get('nodes', []))} nodes, depth=2: {len(resp_d2.json().get('nodes', []))} nodes")
    
    def test_limit_parameter(self):
        """limit parameter works correctly"""
        node_id = "wallet:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        
        resp_10 = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}?depth=2&limit=10")
        resp_100 = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}?depth=2&limit=100")
        
        assert resp_10.status_code == 200
        assert resp_100.status_code == 200
        
        nodes_10 = len(resp_10.json().get('nodes', []))
        nodes_100 = len(resp_100.json().get('nodes', []))
        
        assert nodes_10 <= 10, f"limit=10 should return <= 10 nodes, got {nodes_10}"
        
        print(f"PASS: limit parameter works. limit=10: {nodes_10} nodes, limit=100: {nodes_100} nodes")
    
    def test_identity_level_parameter(self):
        """identity_level parameter accepted"""
        node_id = "wallet:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        
        for level in ["wallet", "cluster", "entity"]:
            response = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}?depth=2&limit=50&identity_level={level}")
            assert response.status_code == 200, f"identity_level={level} should return 200"
        
        print("PASS: identity_level parameter accepted for wallet, cluster, entity")
    
    def test_mode_parameter(self):
        """mode parameter accepted"""
        node_id = "wallet:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        
        for mode in ["smart_money", "cex_flow", "token_rotation", "risk"]:
            response = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}?depth=2&limit=50&mode={mode}")
            assert response.status_code == 200, f"mode={mode} should return 200"
        
        print("PASS: mode parameter accepted for various graph modes")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
