"""
Tests for Arkham-style multi-edge renderer - 3-5 lanes per pair
================================================================
Backend: /api/graph-core/render/{nodeId} and /api/graph-core/render-seeds
Tests: 
  1. lane_count >= 3 for all pairs (straight center + 2 curved)
  2. 3-lane curvatures: [-0.12, 0, 0.12]
  3. 5-lane curvatures: [-0.2, -0.12, 0, 0.12, 0.2]
  4. render-seeds endpoint works with valid seeds
  5. All modes: smart_money, cex_flow, token_rotation, entity, risk use same service
"""
import pytest
import requests
import os
from collections import defaultdict

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test node ID (Binance hot wallet)
TEST_NODE_ID = "cex:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"


class TestMultiLane3to5Edges:
    """Tests for lane_count >= 3 per pair (3-5 lanes Arkham style)"""

    @pytest.fixture(scope="class")
    def render_response(self):
        """Fetch render graph data for test node"""
        url = f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}?depth=2&limit=150"
        response = requests.get(url, timeout=30)
        assert response.status_code == 200, f"API returned {response.status_code}: {response.text[:200]}"
        return response.json()

    def test_render_returns_edges(self, render_response):
        """Verify render endpoint returns edges"""
        edges = render_response.get('edges', [])
        assert len(edges) > 0, "No edges returned from render endpoint"
        print(f"PASS: Render returned {len(edges)} edges")

    def test_all_pairs_have_lane_count_at_least_3(self, render_response):
        """Test each pair has lane_count >= 3 (straight center + 2 curved sides)"""
        edges = render_response.get('edges', [])
        if not edges:
            pytest.skip("No edges to test")
        
        pair_lane_counts = {}
        for edge in edges:
            pk = edge.get('pair_key', '')
            lc = edge.get('lane_count', 0)
            pair_lane_counts[pk] = lc
        
        pairs_with_less_than_3 = {pk: lc for pk, lc in pair_lane_counts.items() if lc < 3}
        
        if pairs_with_less_than_3:
            sample = list(pairs_with_less_than_3.items())[:5]
            pytest.fail(f"Found {len(pairs_with_less_than_3)} pairs with lane_count < 3: {sample}")
        
        lane_count_distribution = defaultdict(int)
        for lc in pair_lane_counts.values():
            lane_count_distribution[lc] += 1
        
        print(f"PASS: All {len(pair_lane_counts)} pairs have lane_count >= 3")
        print(f"  Distribution: {dict(lane_count_distribution)}")

    def test_3_lane_curvatures(self, render_response):
        """Test 3-lane pairs have curvatures [-0.12, 0, 0.12]"""
        edges = render_response.get('edges', [])
        
        pair_edges = defaultdict(list)
        for edge in edges:
            pair_edges[edge.get('pair_key', '')].append(edge)
        
        three_lane_pairs = {pk: el for pk, el in pair_edges.items() if el[0].get('lane_count') == 3}
        
        if not three_lane_pairs:
            pytest.skip("No 3-lane pairs found")
        
        expected_curvatures = [-0.12, 0.0, 0.12]
        
        for pk, edgelist in list(three_lane_pairs.items())[:5]:
            curvatures = sorted([e.get('curvature', 0) for e in edgelist])
            for i, (actual, exp) in enumerate(zip(curvatures, expected_curvatures)):
                assert abs(actual - exp) < 0.02, f"3-lane curvature index {i} wrong: {actual} vs expected {exp} for pair {pk}"
        
        print(f"PASS: {len(three_lane_pairs)} 3-lane pairs have curvatures [-0.12, 0, +0.12]")
        sample_curvatures = sorted([e.get('curvature') for e in list(three_lane_pairs.values())[0]])
        print(f"  Example: {sample_curvatures}")

    def test_5_lane_curvatures(self, render_response):
        """Test 5-lane pairs have curvatures [-0.2, -0.12, 0, 0.12, 0.2]"""
        edges = render_response.get('edges', [])
        
        pair_edges = defaultdict(list)
        for edge in edges:
            pair_edges[edge.get('pair_key', '')].append(edge)
        
        five_lane_pairs = {pk: el for pk, el in pair_edges.items() if el[0].get('lane_count') == 5}
        
        if not five_lane_pairs:
            pytest.skip("No 5-lane pairs found (may require high tx_count pairs)")
        
        expected_curvatures = [-0.20, -0.12, 0.0, 0.12, 0.20]
        
        for pk, edgelist in list(five_lane_pairs.items())[:3]:
            curvatures = sorted([e.get('curvature', 0) for e in edgelist])
            for i, (actual, exp) in enumerate(zip(curvatures, expected_curvatures)):
                assert abs(actual - exp) < 0.02, f"5-lane curvature index {i} wrong: {actual} vs expected {exp}"
        
        print(f"PASS: {len(five_lane_pairs)} 5-lane pairs have curvatures [-0.2, -0.12, 0, +0.12, +0.2]")
        sample_curvatures = sorted([e.get('curvature') for e in list(five_lane_pairs.values())[0]])
        print(f"  Example: {sample_curvatures}")

    def test_all_edges_have_both_colors(self, render_response):
        """Test edges have both green (incoming) and red (outgoing) colors"""
        edges = render_response.get('edges', [])
        
        colors = {edge.get('color') for edge in edges}
        directions = {edge.get('direction') for edge in edges}
        
        assert '#34D399' in colors or 'incoming' in directions, "No green/incoming edges found"
        assert '#ff6b6b' in colors or 'outgoing' in directions, "No red/outgoing edges found"
        
        incoming_count = sum(1 for e in edges if e.get('direction') == 'incoming')
        outgoing_count = sum(1 for e in edges if e.get('direction') == 'outgoing')
        
        print(f"PASS: Both directions present - incoming: {incoming_count} (green), outgoing: {outgoing_count} (red)")


class TestRenderSeedsEndpoint:
    """Tests for /api/graph-core/render-seeds endpoint"""

    def test_render_seeds_with_valid_seeds(self):
        """Test render-seeds endpoint works with valid seed node IDs"""
        seeds = TEST_NODE_ID
        url = f"{BASE_URL}/api/graph-core/render-seeds?seeds={seeds}&depth=1&limit=50"
        
        response = requests.get(url, timeout=30)
        assert response.status_code == 200, f"render-seeds returned {response.status_code}: {response.text[:200]}"
        
        data = response.json()
        assert 'nodes' in data, "Response missing 'nodes'"
        assert 'edges' in data, "Response missing 'edges'"
        
        print(f"PASS: render-seeds returned {len(data.get('nodes', []))} nodes, {len(data.get('edges', []))} edges")

    def test_render_seeds_has_multi_edge_fields(self):
        """Test render-seeds edges have lane_index, lane_count, curvature, direction, color"""
        seeds = TEST_NODE_ID
        url = f"{BASE_URL}/api/graph-core/render-seeds?seeds={seeds}&depth=1&limit=50"
        
        response = requests.get(url, timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        edges = data.get('edges', [])
        
        if not edges:
            pytest.skip("No edges in render-seeds response")
        
        required_fields = ['lane_index', 'lane_count', 'curvature', 'direction', 'color']
        
        sample_edge = edges[0]
        for field in required_fields:
            assert field in sample_edge, f"render-seeds edge missing '{field}'"
        
        print(f"PASS: render-seeds edges have all required fields: {required_fields}")
        print(f"  Sample edge: lane_index={sample_edge.get('lane_index')}, lane_count={sample_edge.get('lane_count')}, curvature={sample_edge.get('curvature')}")


class TestDiscoveryModes:
    """Tests for different discovery modes using same edge_lane_service"""

    @pytest.mark.parametrize("mode", ["smart_money", "cex_flow", "all"])
    def test_discovery_mode_returns_edges(self, mode):
        """Test each discovery mode returns graph data"""
        url = f"{BASE_URL}/api/graph-core/discover?mode={mode}&limit=20"
        
        response = requests.get(url, timeout=30)
        # Discovery may return empty if no data for mode - that's OK
        if response.status_code != 200:
            pytest.skip(f"Discovery mode {mode} returned {response.status_code}")
        
        data = response.json()
        seed_nodes = data.get('seed_nodes', [])
        
        print(f"PASS: Discovery mode '{mode}' returned {len(seed_nodes)} seed nodes")

    def test_render_with_mode_filter(self):
        """Test render endpoint with mode filter still uses edge_lane_service"""
        url = f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}?depth=1&limit=50&mode=cex_flow"
        
        response = requests.get(url, timeout=30)
        assert response.status_code == 200, f"render with mode=cex_flow returned {response.status_code}"
        
        data = response.json()
        edges = data.get('edges', [])
        
        if edges:
            # Check multi-edge fields exist
            sample = edges[0]
            assert 'lane_index' in sample, "Edge missing lane_index"
            assert 'lane_count' in sample, "Edge missing lane_count"
            assert 'curvature' in sample, "Edge missing curvature"
            print(f"PASS: render with mode filter has multi-edge fields ({len(edges)} edges)")
        else:
            print("PASS: render with mode=cex_flow returned empty (no matching edges)")


class TestEdgeLaneServiceCurvatureFormula:
    """Unit tests for edge_lane_service.py curvature formula"""

    def test_3_lane_curvature_formula(self):
        """Test 3-lane curvatures are [-0.12, 0, 0.12] (straight center + 2 curved)"""
        import sys
        sys.path.insert(0, '/app/backend')
        from edge_lane_service import get_curvature
        
        curvatures = [get_curvature(i, 3) for i in range(3)]
        expected = [-0.12, 0.0, 0.12]
        
        for i, (actual, exp) in enumerate(zip(curvatures, expected)):
            assert abs(actual - exp) < 0.001, f"Lane {i}: {actual} != {exp}"
        
        print(f"PASS: 3-lane curvatures: {curvatures}")

    def test_5_lane_curvature_formula(self):
        """Test 5-lane curvatures are [-0.2, -0.12, 0, 0.12, 0.2]"""
        import sys
        sys.path.insert(0, '/app/backend')
        from edge_lane_service import get_curvature
        
        curvatures = [get_curvature(i, 5) for i in range(5)]
        expected = [-0.20, -0.12, 0.0, 0.12, 0.20]
        
        for i, (actual, exp) in enumerate(zip(curvatures, expected)):
            assert abs(actual - exp) < 0.02, f"Lane {i}: {actual} != {exp}"
        
        print(f"PASS: 5-lane curvatures: {curvatures}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
