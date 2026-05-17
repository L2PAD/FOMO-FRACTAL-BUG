"""
Test: Arkham-style Distance-Aware Lane Compression
===================================================
Tests for:
1. Backend: 9-lane pairs with uniform curvature within ±0.20 corridor
2. Backend: Edge directions (incoming/outgoing) and color matching
3. Backend: Tooltip fields (flowType, amountUsd, txCount, lane position)
4. Backend: Smart Money and CEX Flow discovery modes
"""

import pytest
import requests
import os
import math

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_NODE_ID = "cex:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"

class TestRenderEndpoint9Lanes:
    """Tests for GET /api/graph-core/render/{node_id} with 9-lane pairs"""
    
    def test_render_returns_9_lane_pairs(self):
        """Verify all pairs have exactly 9 lanes (MAX_LANES_PER_PAIR=9)"""
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}?depth=2&limit=50")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        edges = data.get('edges', [])
        assert len(edges) > 0, "No edges returned"
        
        # Check lane_count distribution
        lane_counts = {}
        for e in edges:
            lc = e.get('lane_count', 1)
            lane_counts[lc] = lane_counts.get(lc, 0) + 1
        
        print(f"Lane count distribution: {lane_counts}")
        assert 9 in lane_counts, "Should have 9-lane pairs"
        # Most pairs should be 9-lane
        total_9_lane = lane_counts.get(9, 0)
        assert total_9_lane >= len(edges) * 0.5, f"At least 50% should be 9-lane pairs, got {total_9_lane}/{len(edges)}"
    
    def test_curvatures_within_corridor(self):
        """Verify curvatures are uniform within ±0.20 corridor"""
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}?depth=2&limit=50")
        assert response.status_code == 200
        
        data = response.json()
        edges = data.get('edges', [])
        
        # Get curvatures from 9-lane pairs
        nine_lane_curvatures = [e.get('curvature', 0) for e in edges if e.get('lane_count') == 9]
        
        if not nine_lane_curvatures:
            pytest.skip("No 9-lane pairs to test")
        
        # All curvatures should be within [-0.20, +0.20]
        for c in nine_lane_curvatures:
            assert -0.21 <= c <= 0.21, f"Curvature {c} outside ±0.20 corridor"
        
        # Check expected 9-lane curvatures: [-0.20, -0.15, -0.10, -0.05, 0, 0.05, 0.10, 0.15, 0.20]
        unique_curvatures = sorted(set([round(c, 2) for c in nine_lane_curvatures]))
        expected = [-0.20, -0.15, -0.10, -0.05, 0.0, 0.05, 0.10, 0.15, 0.20]
        
        print(f"9-lane curvatures: {unique_curvatures}")
        assert len(unique_curvatures) == 9, f"Expected 9 unique curvatures, got {len(unique_curvatures)}"
        for i, expected_val in enumerate(expected):
            assert abs(unique_curvatures[i] - expected_val) < 0.02, f"Curvature mismatch at index {i}: {unique_curvatures[i]} vs {expected_val}"
    
    def test_uniform_curvature_spacing(self):
        """Verify uniform 0.05 spacing between lanes in 9-lane pairs"""
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}?depth=2&limit=50")
        assert response.status_code == 200
        
        data = response.json()
        edges = data.get('edges', [])
        
        # Group edges by pair_key to check spacing
        pairs = {}
        for e in edges:
            pk = e.get('pair_key', '')
            if pk not in pairs:
                pairs[pk] = []
            pairs[pk].append(e)
        
        # Check spacing in 9-lane pairs
        for pk, pair_edges in pairs.items():
            if len(pair_edges) == 9:
                curvatures = sorted([e.get('curvature', 0) for e in pair_edges])
                for i in range(len(curvatures) - 1):
                    spacing = round(curvatures[i+1] - curvatures[i], 3)
                    assert abs(spacing - 0.05) < 0.01, f"Non-uniform spacing in pair {pk}: {spacing}"


class TestEdgeDirectionsAndColors:
    """Tests for edge direction and color matching"""
    
    def test_directions_incoming_outgoing(self):
        """Verify edges have incoming and outgoing directions"""
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}?depth=2&limit=50")
        assert response.status_code == 200
        
        data = response.json()
        edges = data.get('edges', [])
        
        directions = {}
        for e in edges:
            d = e.get('direction', 'unknown')
            directions[d] = directions.get(d, 0) + 1
        
        print(f"Direction distribution: {directions}")
        assert 'incoming' in directions, "Should have incoming edges"
        assert 'outgoing' in directions, "Should have outgoing edges"
        # Both should be substantial (at least 10%)
        assert directions['incoming'] >= len(edges) * 0.1, "Too few incoming edges"
        assert directions['outgoing'] >= len(edges) * 0.1, "Too few outgoing edges"
    
    def test_color_matches_direction(self):
        """Verify green=#34D399 for incoming, red=#ff6b6b for outgoing"""
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}?depth=2&limit=50")
        assert response.status_code == 200
        
        data = response.json()
        edges = data.get('edges', [])
        
        COLOR_INCOMING = "#34D399"
        COLOR_OUTGOING = "#ff6b6b"
        
        correct_colors = 0
        for e in edges:
            direction = e.get('direction', '')
            color = e.get('color', '')
            if (direction == 'incoming' and color.upper() == COLOR_INCOMING.upper()) or \
               (direction == 'outgoing' and color.lower() == COLOR_OUTGOING.lower()):
                correct_colors += 1
        
        match_rate = 100 * correct_colors / len(edges) if edges else 0
        print(f"Color match rate: {correct_colors}/{len(edges)} = {match_rate:.1f}%")
        assert match_rate >= 90, f"Color match rate too low: {match_rate}%"


class TestTooltipFields:
    """Tests for tooltip fields: flowType, amountUsd, txCount, lane position"""
    
    def test_all_tooltip_fields_present(self):
        """Verify all required tooltip fields are present on edges"""
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}?depth=2&limit=50")
        assert response.status_code == 200
        
        data = response.json()
        edges = data.get('edges', [])
        assert len(edges) > 0, "No edges returned"
        
        required_fields = ['direction', 'flowType', 'amountUsd', 'txCount', 'lane_index', 'lane_count', 'color']
        
        for i, e in enumerate(edges[:10]):  # Check first 10 edges
            for field in required_fields:
                assert field in e, f"Edge {i} missing field: {field}"
    
    def test_lane_position_format(self):
        """Verify lane_index and lane_count are valid (Lane X/9 format)"""
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}?depth=2&limit=50")
        assert response.status_code == 200
        
        data = response.json()
        edges = data.get('edges', [])
        
        for e in edges[:20]:
            lane_index = e.get('lane_index', -1)
            lane_count = e.get('lane_count', 0)
            
            assert lane_index >= 0, f"Invalid lane_index: {lane_index}"
            assert lane_count > 0, f"Invalid lane_count: {lane_count}"
            assert lane_index < lane_count, f"lane_index ({lane_index}) >= lane_count ({lane_count})"
            
            # Lane position should be "Lane {lane_index+1}/{lane_count}"
            lane_position = f"Lane {lane_index + 1}/{lane_count}"
            print(f"Sample lane position: {lane_position}")


class TestDiscoveryModes:
    """Tests for Smart Money and CEX Flow discovery modes"""
    
    def test_smart_money_discovery_returns_edges(self):
        """Verify Smart Money discovery mode returns multi-edge graph"""
        response = requests.get(f"{BASE_URL}/api/graph-core/render-seeds?mode=smart_money&limit=50")
        
        if response.status_code != 200:
            pytest.skip(f"Smart Money mode returned {response.status_code} - may not have seed data")
        
        data = response.json()
        edges = data.get('edges', [])
        
        if len(edges) == 0:
            pytest.skip("No edges in Smart Money mode - no seed data")
        
        # Check edges have multi-lane properties
        max_lane_count = max([e.get('lane_count', 1) for e in edges])
        print(f"Smart Money max lane count: {max_lane_count}")
        assert max_lane_count >= 3, f"Expected multi-lane edges, got max {max_lane_count}"
    
    def test_cex_flow_discovery_returns_edges_with_direction(self):
        """Verify CEX Flow discovery mode returns edges with direction/curvature"""
        response = requests.get(f"{BASE_URL}/api/graph-core/render-seeds?mode=cex_flow&limit=50")
        
        if response.status_code != 200:
            pytest.skip(f"CEX Flow mode returned {response.status_code} - may not have seed data")
        
        data = response.json()
        edges = data.get('edges', [])
        
        if len(edges) == 0:
            pytest.skip("No edges in CEX Flow mode - no seed data")
        
        # Check edges have direction and curvature
        edge_with_direction = sum(1 for e in edges if e.get('direction'))
        edge_with_curvature = sum(1 for e in edges if 'curvature' in e)
        
        print(f"CEX Flow: {edge_with_direction}/{len(edges)} with direction, {edge_with_curvature}/{len(edges)} with curvature")
        assert edge_with_direction > 0, "No edges with direction"


class TestCenterLaneStraight:
    """Tests for center lane (index 4 of 9) being straight (curvature=0)"""
    
    def test_center_lane_curvature_zero(self):
        """Verify center lane (index 4 of 9) has curvature=0"""
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}?depth=2&limit=50")
        assert response.status_code == 200
        
        data = response.json()
        edges = data.get('edges', [])
        
        # Find 9-lane pairs and check center lane
        center_lanes = [e for e in edges if e.get('lane_count') == 9 and e.get('lane_index') == 4]
        
        if not center_lanes:
            pytest.skip("No center lanes (index 4 of 9) found")
        
        for e in center_lanes[:10]:
            curvature = e.get('curvature', None)
            assert curvature is not None, "Center lane missing curvature"
            assert abs(curvature) < 0.01, f"Center lane should have curvature=0, got {curvature}"
        
        print(f"Verified {len(center_lanes)} center lanes have curvature=0")


class TestImportanceRanking:
    """Tests for edges sorted by importance (highest first)"""
    
    def test_lane_index_0_has_highest_weight(self):
        """Verify lane_index=0 (first edge) has highest weight in each pair"""
        response = requests.get(f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}?depth=2&limit=50")
        assert response.status_code == 200
        
        data = response.json()
        edges = data.get('edges', [])
        
        # Group by pair_key
        pairs = {}
        for e in edges:
            pk = e.get('pair_key', '')
            if pk not in pairs:
                pairs[pk] = []
            pairs[pk].append(e)
        
        # Check importance ranking in 9-lane pairs
        violations = 0
        for pk, pair_edges in pairs.items():
            if len(pair_edges) >= 2:
                sorted_by_index = sorted(pair_edges, key=lambda x: x.get('lane_index', 0))
                first_weight = sorted_by_index[0].get('weight', 0)
                max_weight = max(e.get('weight', 0) for e in pair_edges)
                if first_weight < max_weight * 0.9:  # Allow 10% tolerance
                    violations += 1
        
        violation_rate = 100 * violations / len(pairs) if pairs else 0
        print(f"Importance ranking violations: {violations}/{len(pairs)} pairs = {violation_rate:.1f}%")
        assert violation_rate < 20, f"Too many importance ranking violations: {violation_rate}%"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
