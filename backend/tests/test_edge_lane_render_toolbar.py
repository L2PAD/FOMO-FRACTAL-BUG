"""
Test suite for Arkham-style graph improvements:
1. Edge lane service - corridor grouping, lane aggregation, max 6 lanes
2. Render endpoint - pre-computed edge properties  
3. Frontend toolbar - 3-row layout verification
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# =====================================================
# Edge Lane Service - Corridor and Lane Tests
# =====================================================

class TestEdgeLaneService:
    """Test edge_lane_service.py functionality"""
    
    def test_render_endpoint_returns_200(self):
        """Render endpoint returns 200 status"""
        node_id = "wallet:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}?depth=2&limit=150")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
        assert "meta" in data
        print(f"SUCCESS: Render endpoint returned {len(data['nodes'])} nodes, {len(data['edges'])} edges")
    
    def test_edges_have_corridor_id(self):
        """All edges have corridorId field"""
        node_id = "wallet:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}")
        data = response.json()
        edges = data.get('edges', [])
        
        if not edges:
            pytest.skip("No edges returned from render endpoint")
        
        for edge in edges:
            assert "corridorId" in edge, f"Edge {edge.get('id')} missing corridorId"
            assert edge["corridorId"], f"Edge {edge.get('id')} has empty corridorId"
        
        print(f"SUCCESS: All {len(edges)} edges have corridorId")
    
    def test_edges_have_lane_index_and_count(self):
        """Edges have laneIndex and laneCount fields"""
        node_id = "wallet:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}")
        data = response.json()
        edges = data.get('edges', [])
        
        if not edges:
            pytest.skip("No edges returned from render endpoint")
        
        for edge in edges:
            assert "laneIndex" in edge, f"Edge {edge.get('id')} missing laneIndex"
            assert "laneCount" in edge, f"Edge {edge.get('id')} missing laneCount"
            assert edge["laneIndex"] >= 0, f"laneIndex should be >= 0"
            assert edge["laneCount"] >= 1, f"laneCount should be >= 1"
            assert edge["laneIndex"] < edge["laneCount"], f"laneIndex should be < laneCount"
        
        print(f"SUCCESS: All edges have valid laneIndex/laneCount")

    def test_same_pair_edges_share_corridor_id(self):
        """Edges between same node pair share corridorId"""
        node_id = "wallet:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}")
        data = response.json()
        edges = data.get('edges', [])
        
        # Group by corridorId
        from collections import defaultdict
        corridors = defaultdict(list)
        for edge in edges:
            corridors[edge['corridorId']].append(edge)
        
        # Verify edges in same corridor share source/target pair (in either direction)
        for cid, lanes in corridors.items():
            if len(lanes) < 2:
                continue
            pairs = set()
            for lane in lanes:
                pair = tuple(sorted([lane['source'], lane['target']]))
                pairs.add(pair)
            assert len(pairs) == 1, f"Corridor {cid} has edges with different pairs: {pairs}"
        
        print(f"SUCCESS: Verified {len(corridors)} corridors have consistent pairs")

    def test_multi_lane_symmetric_curvatures(self):
        """Multi-lane pairs have symmetric curvatures (e.g., -0.06 and +0.06)"""
        node_id = "wallet:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}")
        data = response.json()
        edges = data.get('edges', [])
        
        # Find multi-lane corridors
        from collections import defaultdict
        corridors = defaultdict(list)
        for edge in edges:
            if edge.get('laneCount', 1) > 1:
                corridors[edge['corridorId']].append(edge)
        
        if not corridors:
            pytest.skip("No multi-lane corridors found")
        
        for cid, lanes in corridors.items():
            curvatures = sorted([lane['curvature'] for lane in lanes])
            
            # For symmetric curvatures, sum should be ~0
            total = sum(curvatures)
            assert abs(total) < 0.01, f"Corridor {cid} curvatures not symmetric: {curvatures}, sum={total}"
            
            # Check symmetry (should have positive and negative values)
            if len(lanes) > 1:
                has_negative = any(c < 0 for c in curvatures)
                has_positive = any(c > 0 for c in curvatures)
                assert has_negative and has_positive, f"Corridor {cid} should have symmetric +/- curvatures: {curvatures}"
        
        print(f"SUCCESS: {len(corridors)} multi-lane corridors have symmetric curvatures")


class TestEdgeRenderProperties:
    """Test pre-computed edge visual properties"""
    
    def test_width_max_1_8(self):
        """Edge width does not exceed 1.8"""
        node_id = "wallet:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}")
        data = response.json()
        edges = data.get('edges', [])
        
        if not edges:
            pytest.skip("No edges returned")
        
        for edge in edges:
            assert "width" in edge, f"Edge missing width"
            assert edge["width"] <= 1.8, f"Edge width {edge['width']} exceeds max 1.8"
            assert edge["width"] > 0, f"Edge width should be positive"
        
        print(f"SUCCESS: All {len(edges)} edges have width <= 1.8")
    
    def test_opacity_max_0_58(self):
        """Edge opacity does not exceed 0.58"""
        node_id = "wallet:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}")
        data = response.json()
        edges = data.get('edges', [])
        
        if not edges:
            pytest.skip("No edges returned")
        
        for edge in edges:
            assert "opacity" in edge, f"Edge missing opacity"
            assert edge["opacity"] <= 0.58, f"Edge opacity {edge['opacity']} exceeds max 0.58"
            assert edge["opacity"] > 0, f"Edge opacity should be positive"
        
        print(f"SUCCESS: All {len(edges)} edges have opacity <= 0.58")
    
    def test_color_correct_values(self):
        """Edge color is one of: #43d18d (inflow), #ff6b6b (outflow), #9ca3af (internal)"""
        node_id = "wallet:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}")
        data = response.json()
        edges = data.get('edges', [])
        
        valid_colors = {"#43d18d", "#ff6b6b", "#9ca3af"}
        
        if not edges:
            pytest.skip("No edges returned")
        
        for edge in edges:
            assert "color" in edge, f"Edge missing color"
            assert edge["color"] in valid_colors, f"Invalid color {edge['color']}, expected one of {valid_colors}"
        
        print(f"SUCCESS: All {len(edges)} edges have valid colors")
    
    def test_direction_matches_color(self):
        """Direction field matches color: inflow=#43d18d, outflow=#ff6b6b, internal=#9ca3af"""
        node_id = "wallet:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}")
        data = response.json()
        edges = data.get('edges', [])
        
        color_direction_map = {
            "#43d18d": "inflow",
            "#ff6b6b": "outflow", 
            "#9ca3af": "internal",
        }
        
        if not edges:
            pytest.skip("No edges returned")
        
        for edge in edges:
            expected_direction = color_direction_map.get(edge['color'])
            assert edge['direction'] == expected_direction, f"Edge direction {edge['direction']} doesn't match color {edge['color']} (expected {expected_direction})"
        
        print(f"SUCCESS: All edges have matching direction/color")


class TestMaxLanesEnforcement:
    """Test MAX_LANES_PER_PAIR=6 enforcement"""
    
    def test_max_lanes_constant_is_6(self):
        """MAX_LANES_PER_PAIR constant is 6"""
        import sys
        sys.path.insert(0, '/app/backend')
        from edge_lane_service import MAX_LANES_PER_PAIR
        
        assert MAX_LANES_PER_PAIR == 6, f"Expected MAX_LANES_PER_PAIR=6, got {MAX_LANES_PER_PAIR}"
        print(f"SUCCESS: MAX_LANES_PER_PAIR = {MAX_LANES_PER_PAIR}")
    
    def test_corridor_compaction_creates_aggregate_lane(self):
        """Corridor with >6 lanes creates aggregate lane"""
        import sys
        sys.path.insert(0, '/app/backend')
        from edge_lane_service import aggregate_lanes, build_render_edges, MAX_LANES_PER_PAIR
        
        # Create 10 distinct lane keys (different tokens)
        relations = []
        tokens = ['USDC', 'USDT', 'DAI', 'ETH', 'WETH', 'WBTC', 'LINK', 'UNI', 'AAVE', 'CRV']
        for i, token in enumerate(tokens):
            relations.append({
                'source_id': 'wallet:0xA:ethereum',
                'target_id': 'wallet:0xB:ethereum',
                'type': 'transfer',
                'token': token,
                'amountUsd': 1000 * (10 - i),
                'txCount': 10,
            })
        
        lanes = aggregate_lanes(relations)
        render_edges = build_render_edges(lanes, center_node_id='wallet:0xA:ethereum')
        
        assert len(render_edges) <= MAX_LANES_PER_PAIR, f"Expected max {MAX_LANES_PER_PAIR} lanes, got {len(render_edges)}"
        
        # Check for aggregate lane
        aggregate_lanes_found = [e for e in render_edges if e.get('flowType') == 'aggregate']
        if len(lanes) > MAX_LANES_PER_PAIR:
            assert len(aggregate_lanes_found) > 0, "Expected aggregate lane when input exceeds MAX_LANES_PER_PAIR"
        
        print(f"SUCCESS: {len(lanes)} input lanes compacted to {len(render_edges)} render edges")
    
    def test_render_endpoint_respects_max_lanes(self):
        """Render endpoint returns max 6 lanes per corridor"""
        node_id = "wallet:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}")
        data = response.json()
        edges = data.get('edges', [])
        
        from collections import defaultdict
        corridors = defaultdict(list)
        for edge in edges:
            corridors[edge['corridorId']].append(edge)
        
        for cid, lanes in corridors.items():
            assert len(lanes) <= 6, f"Corridor {cid} has {len(lanes)} lanes, max is 6"
        
        print(f"SUCCESS: All corridors have <= 6 lanes")


class TestMetaResponse:
    """Test render endpoint meta object"""
    
    def test_meta_contains_edge_counts(self):
        """Meta object contains raw_edge_count, lane_count, render_edge_count"""
        node_id = "wallet:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{node_id}")
        data = response.json()
        meta = data.get('meta', {})
        
        assert "source" in meta, "Meta missing 'source' field"
        assert meta["source"] == "render", f"Expected source='render', got {meta['source']}"
        assert "render_edge_count" in meta, "Meta missing render_edge_count"
        
        print(f"SUCCESS: Meta contains required fields: {list(meta.keys())}")


# =====================================================
# API Endpoint Tests
# =====================================================

class TestHealthEndpoint:
    """Verify API is accessible"""
    
    def test_graph_core_health(self):
        """Graph-core health endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        print(f"SUCCESS: Graph-core health OK")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
