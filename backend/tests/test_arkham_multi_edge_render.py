"""
Tests for Arkham-style multi-edge graph renderer
================================================
Backend: /api/graph-core/render/{nodeId}
Tests: Required fields, direction values, color mapping, multi-edge pairs, MAX_LANES_PER_PAIR, curvature formula
"""
import pytest
import requests
import os
from collections import defaultdict

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test node ID from requirements
TEST_NODE_ID = "cex:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"


class TestArkhamMultiEdgeRender:
    """Tests for GET /api/graph-core/render/{nodeId}"""

    @pytest.fixture(scope="class")
    def graph_response(self):
        """Fetch graph data once for all tests in this class"""
        url = f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}?depth=2&limit=100"
        response = requests.get(url, timeout=30)
        assert response.status_code == 200, f"API returned {response.status_code}"
        return response.json()

    def test_api_returns_nodes_and_edges(self, graph_response):
        """Verify API returns graph structure with nodes and edges"""
        assert 'nodes' in graph_response, "Response missing 'nodes'"
        assert 'edges' in graph_response, "Response missing 'edges'"
        assert len(graph_response['nodes']) > 0, "No nodes returned"
        assert len(graph_response['edges']) > 0, "No edges returned"
        print(f"PASS: Got {len(graph_response['nodes'])} nodes and {len(graph_response['edges'])} edges")

    def test_all_edges_have_required_fields(self, graph_response):
        """Test all edges have required fields: id, source, target, direction, weight, lane_index, lane_count, pair_key, color"""
        required_fields = ['id', 'source', 'target', 'direction', 'weight', 'lane_index', 'lane_count', 'pair_key', 'color']
        edges = graph_response.get('edges', [])
        
        missing_fields = defaultdict(int)
        edges_with_all_fields = 0
        
        for edge in edges:
            has_all = True
            for field in required_fields:
                if field not in edge:
                    missing_fields[field] += 1
                    has_all = False
            if has_all:
                edges_with_all_fields += 1
        
        assert not missing_fields, f"Missing fields in edges: {dict(missing_fields)}"
        print(f"PASS: All {edges_with_all_fields} edges have required fields")

    def test_direction_values_valid(self, graph_response):
        """Test direction values are exactly 'incoming', 'outgoing', or 'neutral'"""
        edges = graph_response.get('edges', [])
        valid_directions = {'incoming', 'outgoing', 'neutral'}
        
        directions_found = defaultdict(int)
        invalid_directions = []
        
        for edge in edges:
            d = edge.get('direction', 'MISSING')
            directions_found[d] += 1
            if d not in valid_directions:
                invalid_directions.append(d)
        
        assert not invalid_directions, f"Invalid directions found: {set(invalid_directions)}"
        print(f"PASS: Direction distribution: {dict(directions_found)}")

    def test_colors_match_directions(self, graph_response):
        """Test color for incoming=#34D399 (green), outgoing=#ff6b6b (red), neutral=#8a8a8a (gray)"""
        edges = graph_response.get('edges', [])
        
        color_map = {
            'incoming': '#34D399',
            'outgoing': '#ff6b6b',
            'neutral': '#8a8a8a'
        }
        
        mismatches = []
        for edge in edges:
            d = edge.get('direction')
            c = edge.get('color')
            expected = color_map.get(d)
            if expected and c != expected:
                mismatches.append(f"direction={d}, color={c}, expected={expected}")
        
        assert not mismatches, f"Color mismatches: {mismatches[:5]}"
        print("PASS: All edge colors match their directions")

    def test_edges_not_deduplicated_multi_edge_pairs_exist(self, graph_response):
        """Test that multiple edges per pair exist (NOT deduplicated)"""
        edges = graph_response.get('edges', [])
        
        pair_counts = defaultdict(list)
        for edge in edges:
            pk = edge.get('pair_key', '')
            pair_counts[pk].append(edge)
        
        multi_edge_pairs = {pk: edgelist for pk, edgelist in pair_counts.items() if len(edgelist) >= 2}
        
        assert len(multi_edge_pairs) > 0, "No multi-edge pairs found - edges may be deduplicated!"
        
        # Show example
        sample_pk = list(multi_edge_pairs.keys())[0]
        sample_edges = multi_edge_pairs[sample_pk]
        print(f"PASS: Found {len(multi_edge_pairs)} pairs with 2+ edges")
        print(f"  Example pair_key: {sample_pk}")
        for e in sample_edges[:3]:
            print(f"    - lane_index={e.get('lane_index')}, direction={e.get('direction')}, color={e.get('color')}")

    def test_max_lanes_per_pair_enforcement(self, graph_response):
        """Test lane_count per pair <= 5 (MAX_LANES_PER_PAIR enforcement)"""
        edges = graph_response.get('edges', [])
        lane_counts = [edge.get('lane_count', 0) for edge in edges]
        max_lane_count = max(lane_counts) if lane_counts else 0
        
        assert max_lane_count <= 5, f"lane_count {max_lane_count} exceeds MAX_LANES_PER_PAIR=5"
        print(f"PASS: Max lane_count is {max_lane_count} (<=5)")

    def test_curvature_2_lane_pairs(self, graph_response):
        """Test for 2-lane pairs, curvature is -0.12 and +0.12"""
        edges = graph_response.get('edges', [])
        
        pair_edges = defaultdict(list)
        for edge in edges:
            pair_edges[edge.get('pair_key', '')].append(edge)
        
        two_lane_pairs = {pk: el for pk, el in pair_edges.items() if el[0].get('lane_count') == 2}
        
        if not two_lane_pairs:
            pytest.skip("No 2-lane pairs found to test curvature")
        
        for pk, edgelist in list(two_lane_pairs.items())[:5]:
            curvatures = sorted([e.get('curvature', 0) for e in edgelist])
            # Expected: [-0.12, 0.12]
            assert abs(curvatures[0] - (-0.12)) < 0.01, f"2-lane first curvature wrong: {curvatures[0]}"
            assert abs(curvatures[1] - 0.12) < 0.01, f"2-lane second curvature wrong: {curvatures[1]}"
        
        print(f"PASS: 2-lane pairs have curvature [-0.12, +0.12]")
        sample_curvatures = sorted([e.get('curvature') for e in list(two_lane_pairs.values())[0]])
        print(f"  Example: {sample_curvatures}")

    def test_curvature_4_lane_pairs(self, graph_response):
        """Test for 4-lane pairs, curvature is -0.20, -0.12, +0.12, +0.20"""
        edges = graph_response.get('edges', [])
        
        pair_edges = defaultdict(list)
        for edge in edges:
            pair_edges[edge.get('pair_key', '')].append(edge)
        
        four_lane_pairs = {pk: el for pk, el in pair_edges.items() if el[0].get('lane_count') == 4}
        
        if not four_lane_pairs:
            pytest.skip("No 4-lane pairs found to test curvature")
        
        for pk, edgelist in list(four_lane_pairs.items())[:3]:
            curvatures = sorted([e.get('curvature', 0) for e in edgelist])
            expected = [-0.20, -0.12, 0.12, 0.20]
            for i, (actual, exp) in enumerate(zip(curvatures, expected)):
                assert abs(actual - exp) < 0.02, f"4-lane curvature index {i} wrong: {actual} vs expected {exp}"
        
        print(f"PASS: 4-lane pairs have curvature [-0.20, -0.12, +0.12, +0.20]")
        sample_curvatures = sorted([e.get('curvature') for e in list(four_lane_pairs.values())[0]])
        print(f"  Example: {sample_curvatures}")

    def test_bidirectional_edges_exist(self, graph_response):
        """Test that both incoming and outgoing edges exist in the response"""
        edges = graph_response.get('edges', [])
        
        directions = {edge.get('direction') for edge in edges}
        
        assert 'incoming' in directions, "No incoming edges found"
        assert 'outgoing' in directions, "No outgoing edges found"
        
        incoming_count = sum(1 for e in edges if e.get('direction') == 'incoming')
        outgoing_count = sum(1 for e in edges if e.get('direction') == 'outgoing')
        
        print(f"PASS: Both directions present - incoming: {incoming_count}, outgoing: {outgoing_count}")

    def test_edge_id_format(self, graph_response):
        """Test edge IDs follow expected format: pair_key__lane_index"""
        edges = graph_response.get('edges', [])
        
        for edge in edges[:10]:
            edge_id = edge.get('id', '')
            pair_key = edge.get('pair_key', '')
            lane_index = edge.get('lane_index', 0)
            
            # ID should be pair_key__lane_index
            expected_id = f"{pair_key}__{lane_index}"
            assert edge_id == expected_id, f"ID format wrong: {edge_id} vs expected {expected_id}"
        
        print("PASS: Edge IDs follow format pair_key__lane_index")


class TestEdgeLaneServiceUnit:
    """Unit tests for edge_lane_service.py functions"""

    def test_get_curvature_1_lane(self):
        """Test curvature for 1-lane pair is 0"""
        import sys
        sys.path.insert(0, '/app/backend')
        from edge_lane_service import get_curvature
        assert get_curvature(0, 1) == 0.0
        print("PASS: 1-lane curvature is 0")

    def test_get_curvature_2_lanes(self):
        """Test curvature for 2-lane pair is [-0.12, +0.12]"""
        import sys
        sys.path.insert(0, '/app/backend')
        from edge_lane_service import get_curvature
        assert get_curvature(0, 2) == -0.12
        assert get_curvature(1, 2) == 0.12
        print("PASS: 2-lane curvature is [-0.12, +0.12]")

    def test_get_curvature_3_lanes(self):
        """Test curvature for 3-lane pair is [-0.12, 0, +0.12]"""
        import sys
        sys.path.insert(0, '/app/backend')
        from edge_lane_service import get_curvature
        assert get_curvature(0, 3) == -0.12
        assert get_curvature(1, 3) == 0.0
        assert get_curvature(2, 3) == 0.12
        print("PASS: 3-lane curvature is [-0.12, 0, +0.12]")

    def test_get_curvature_4_lanes(self):
        """Test curvature for 4-lane pair is [-0.20, -0.12, +0.12, +0.20]"""
        import sys
        sys.path.insert(0, '/app/backend')
        from edge_lane_service import get_curvature
        assert abs(get_curvature(0, 4) - (-0.20)) < 0.01
        assert abs(get_curvature(1, 4) - (-0.12)) < 0.01
        assert abs(get_curvature(2, 4) - 0.12) < 0.01
        assert abs(get_curvature(3, 4) - 0.20) < 0.01
        print("PASS: 4-lane curvature is [-0.20, -0.12, +0.12, +0.20]")

    def test_get_curvature_5_lanes(self):
        """Test curvature for 5-lane pair is [-0.20, -0.12, 0, +0.12, +0.20]"""
        import sys
        sys.path.insert(0, '/app/backend')
        from edge_lane_service import get_curvature
        assert abs(get_curvature(0, 5) - (-0.20)) < 0.01
        assert abs(get_curvature(1, 5) - (-0.12)) < 0.01
        assert abs(get_curvature(2, 5) - 0.0) < 0.01
        assert abs(get_curvature(3, 5) - 0.12) < 0.01
        assert abs(get_curvature(4, 5) - 0.20) < 0.01
        print("PASS: 5-lane curvature is [-0.20, -0.12, 0, +0.12, +0.20]")

    def test_max_lanes_per_pair_constant(self):
        """Test MAX_LANES_PER_PAIR constant is 5"""
        import sys
        sys.path.insert(0, '/app/backend')
        from edge_lane_service import MAX_LANES_PER_PAIR
        assert MAX_LANES_PER_PAIR == 5
        print("PASS: MAX_LANES_PER_PAIR is 5")

    def test_color_constants(self):
        """Test color constants match spec"""
        import sys
        sys.path.insert(0, '/app/backend')
        from edge_lane_service import COLOR_INCOMING, COLOR_OUTGOING, COLOR_NEUTRAL
        assert COLOR_INCOMING == "#34D399", f"COLOR_INCOMING wrong: {COLOR_INCOMING}"
        assert COLOR_OUTGOING == "#ff6b6b", f"COLOR_OUTGOING wrong: {COLOR_OUTGOING}"
        assert COLOR_NEUTRAL == "#8a8a8a", f"COLOR_NEUTRAL wrong: {COLOR_NEUTRAL}"
        print("PASS: Color constants match spec")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
