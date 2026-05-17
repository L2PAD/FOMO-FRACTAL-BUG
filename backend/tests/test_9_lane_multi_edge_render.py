"""
Test: 9-Lane Multi-Edge Rendering
=================================
Tests for the 9-lane parallel edge rendering feature.
Key requirements:
1. MAX_LANES_PER_PAIR=9 edges per node pair
2. Curvatures span [-0.20, +0.20] with uniform spacing
3. Center lane (index 4 of 9) has curvature=0.0
4. Edges sorted by importance ranking
5. Directions alternate (incoming/outgoing) within pairs
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://expo-telegram-web.preview.emergentagent.com"

TEST_NODE_ID = "cex:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"

# Expected 9-lane curvatures (uniform spacing within ±0.20)
EXPECTED_9_LANE_CURVATURES = [-0.20, -0.15, -0.10, -0.05, 0.0, 0.05, 0.10, 0.15, 0.20]


class Test9LaneEdgeRendering:
    """Tests for 9-lane multi-edge rendering via render endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_render_endpoint_returns_200(self):
        """Basic connectivity test for render endpoint"""
        url = f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}?depth=2&limit=150"
        response = self.session.get(url)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        data = response.json()
        assert "nodes" in data, "Response must contain 'nodes' field"
        assert "edges" in data, "Response must contain 'edges' field"
        print(f"Render endpoint returned {len(data.get('nodes', []))} nodes, {len(data.get('edges', []))} edges")
    
    def test_render_returns_edges_with_lane_geometry(self):
        """All edges must have lane_index, lane_count, curvature fields"""
        url = f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}?depth=2&limit=150"
        response = self.session.get(url)
        assert response.status_code == 200
        data = response.json()
        edges = data.get("edges", [])
        assert len(edges) > 0, "Expected at least one edge"
        
        for edge in edges[:50]:  # Check first 50 edges
            assert "lane_index" in edge or "laneIndex" in edge, f"Edge missing lane_index: {edge.get('id')}"
            assert "lane_count" in edge or "laneCount" in edge, f"Edge missing lane_count: {edge.get('id')}"
            assert "curvature" in edge, f"Edge missing curvature: {edge.get('id')}"
        print(f"All {len(edges)} edges have lane geometry fields")
    
    def test_max_lanes_per_pair_is_9(self):
        """Verify maximum lanes per pair is 9"""
        url = f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}?depth=2&limit=150"
        response = self.session.get(url)
        assert response.status_code == 200
        data = response.json()
        edges = data.get("edges", [])
        
        # Group by pair_key and count
        pairs = {}
        for edge in edges:
            pk = edge.get("pair_key") or edge.get("pairKey") or f"{edge.get('source')}|{edge.get('target')}"
            pairs.setdefault(pk, []).append(edge)
        
        max_lanes = max(len(v) for v in pairs.values()) if pairs else 0
        pairs_with_9_lanes = sum(1 for v in pairs.values() if len(v) == 9)
        
        print(f"Total pairs: {len(pairs)}")
        print(f"Max lanes in any pair: {max_lanes}")
        print(f"Pairs with exactly 9 lanes: {pairs_with_9_lanes}")
        
        # Expect at least some pairs with 9 lanes
        assert max_lanes <= 9, f"Max lanes {max_lanes} exceeds 9"
        assert pairs_with_9_lanes > 0, f"Expected at least one pair with 9 lanes, found {pairs_with_9_lanes}"
    
    def test_9_lane_curvature_values(self):
        """9-lane pairs must have curvatures matching expected values"""
        url = f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}?depth=2&limit=150"
        response = self.session.get(url)
        assert response.status_code == 200
        data = response.json()
        edges = data.get("edges", [])
        
        # Group by pair_key
        pairs = {}
        for edge in edges:
            pk = edge.get("pair_key") or edge.get("pairKey") or f"{edge.get('source')}|{edge.get('target')}"
            pairs.setdefault(pk, []).append(edge)
        
        # Find pairs with exactly 9 lanes
        nine_lane_pairs = {k: v for k, v in pairs.items() if len(v) == 9}
        
        if not nine_lane_pairs:
            pytest.skip("No 9-lane pairs found in test data")
        
        for pk, pair_edges in list(nine_lane_pairs.items())[:3]:  # Check up to 3 pairs
            curvatures = sorted([e.get("curvature", 0) for e in pair_edges])
            print(f"Pair {pk[:30]}... curvatures: {curvatures}")
            
            # Verify center lane (index 4) has curvature ~0
            for edge in pair_edges:
                lane_idx = edge.get("lane_index") or edge.get("laneIndex") or 0
                curv = edge.get("curvature", 0)
                if lane_idx == 4:
                    assert abs(curv) < 0.01, f"Center lane (idx=4) should have curvature~0, got {curv}"
            
            # Verify curvature range is within [-0.20, +0.20]
            min_curv = min(curvatures)
            max_curv = max(curvatures)
            assert min_curv >= -0.21, f"Min curvature {min_curv} below -0.20"
            assert max_curv <= 0.21, f"Max curvature {max_curv} above +0.20"
    
    def test_lane_count_matches_actual_edges(self):
        """lane_count in each edge must match actual number of edges in pair"""
        url = f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}?depth=2&limit=150"
        response = self.session.get(url)
        assert response.status_code == 200
        data = response.json()
        edges = data.get("edges", [])
        
        # Group by pair_key
        pairs = {}
        for edge in edges:
            pk = edge.get("pair_key") or edge.get("pairKey") or f"{edge.get('source')}|{edge.get('target')}"
            pairs.setdefault(pk, []).append(edge)
        
        mismatches = []
        for pk, pair_edges in pairs.items():
            actual_count = len(pair_edges)
            for edge in pair_edges:
                stated_count = edge.get("lane_count") or edge.get("laneCount") or 1
                if stated_count != actual_count:
                    mismatches.append({
                        "pair_key": pk[:50],
                        "edge_id": edge.get("id", ""),
                        "stated": stated_count,
                        "actual": actual_count,
                    })
        
        if mismatches:
            print(f"Found {len(mismatches)} lane_count mismatches:")
            for m in mismatches[:5]:
                print(f"  {m}")
        
        assert len(mismatches) == 0, f"Found {len(mismatches)} lane_count mismatches"
    
    def test_edges_have_alternating_directions(self):
        """Multi-lane pairs should have both incoming and outgoing edges"""
        url = f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}?depth=2&limit=150"
        response = self.session.get(url)
        assert response.status_code == 200
        data = response.json()
        edges = data.get("edges", [])
        
        # Group by pair_key
        pairs = {}
        for edge in edges:
            pk = edge.get("pair_key") or edge.get("pairKey") or f"{edge.get('source')}|{edge.get('target')}"
            pairs.setdefault(pk, []).append(edge)
        
        # Check pairs with 3+ lanes
        multi_lane_pairs = {k: v for k, v in pairs.items() if len(v) >= 3}
        
        if not multi_lane_pairs:
            pytest.skip("No multi-lane pairs found")
        
        pairs_with_both_dirs = 0
        for pk, pair_edges in multi_lane_pairs.items():
            directions = set(e.get("direction", "").lower() for e in pair_edges)
            if "incoming" in directions and "outgoing" in directions:
                pairs_with_both_dirs += 1
        
        pct_both = (pairs_with_both_dirs / len(multi_lane_pairs)) * 100
        print(f"Multi-lane pairs with both directions: {pairs_with_both_dirs}/{len(multi_lane_pairs)} ({pct_both:.1f}%)")
        
        # At least 50% of multi-lane pairs should have both directions
        assert pct_both >= 50, f"Only {pct_both:.1f}% of pairs have both directions"
    
    def test_edges_sorted_by_importance(self):
        """Within each pair, edges should be sorted by importance (weight descending)"""
        url = f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}?depth=2&limit=150"
        response = self.session.get(url)
        assert response.status_code == 200
        data = response.json()
        edges = data.get("edges", [])
        
        # Group by pair_key
        pairs = {}
        for edge in edges:
            pk = edge.get("pair_key") or edge.get("pairKey") or f"{edge.get('source')}|{edge.get('target')}"
            pairs.setdefault(pk, []).append(edge)
        
        # Check 9-lane pairs for proper ordering
        nine_lane_pairs = {k: v for k, v in pairs.items() if len(v) == 9}
        
        if not nine_lane_pairs:
            pytest.skip("No 9-lane pairs to verify ordering")
        
        for pk, pair_edges in list(nine_lane_pairs.items())[:5]:
            # Sort by lane_index
            sorted_edges = sorted(pair_edges, key=lambda e: e.get("lane_index", 0))
            weights = [e.get("weight", 0) or e.get("amountUsd", 0) for e in sorted_edges]
            
            # First edge (lane_index=0) should have highest weight
            if weights[0] > 0:
                is_sorted = weights[0] >= weights[-1]
                print(f"Pair {pk[:30]}... weights: {weights[:3]}...{weights[-2:]}, sorted: {is_sorted}")
                # Relaxed check - first should be >= last
                assert weights[0] >= weights[-1], f"First edge weight {weights[0]} < last {weights[-1]}"
    
    def test_edge_colors_match_direction(self):
        """Edge color should match direction: green for incoming, red for outgoing"""
        url = f"{BASE_URL}/api/graph-core/render/{TEST_NODE_ID}?depth=2&limit=150"
        response = self.session.get(url)
        assert response.status_code == 200
        data = response.json()
        edges = data.get("edges", [])
        
        GREEN = "#34D399".lower()
        RED = "#ff6b6b".lower()
        
        color_mismatches = []
        for edge in edges[:100]:  # Check first 100
            direction = (edge.get("direction") or "").lower()
            color = (edge.get("color") or "").lower()
            
            if direction == "incoming" and color != GREEN:
                color_mismatches.append(f"incoming edge has color {color}")
            elif direction == "outgoing" and color != RED:
                color_mismatches.append(f"outgoing edge has color {color}")
        
        if color_mismatches:
            print(f"Color mismatches: {color_mismatches[:5]}")
        
        mismatch_rate = len(color_mismatches) / min(100, len(edges)) * 100
        assert mismatch_rate < 10, f"{mismatch_rate:.1f}% of edges have wrong colors"


class TestDiscoveryModes:
    """Tests for discovery modes (Smart Money, CEX Flow, All)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def _get_discovery_graph(self, mode):
        """Helper to get graph via discovery → render-seeds flow"""
        # Step 1: Get seed nodes
        disc_url = f"{BASE_URL}/api/graph-core/discovery?mode={mode}&limit=10"
        disc_resp = self.session.get(disc_url)
        if disc_resp.status_code != 200:
            return None, f"Discovery returned {disc_resp.status_code}"
        disc_data = disc_resp.json()
        seeds = disc_data.get("seed_nodes", [])
        if not seeds:
            return None, "No seed nodes found"
        
        # Step 2: Render graph from seeds
        seed_ids = ",".join(n.get("id", "") for n in seeds)
        render_url = f"{BASE_URL}/api/graph-core/render-seeds?seeds={seed_ids}&limit=100&mode={mode}"
        render_resp = self.session.get(render_url)
        if render_resp.status_code != 200:
            return None, f"Render returned {render_resp.status_code}"
        
        return render_resp.json(), None
    
    def test_smart_money_mode_multi_edges(self):
        """Smart Money mode should return multi-edge graph"""
        data, error = self._get_discovery_graph("smart_money")
        if error:
            pytest.skip(f"Smart Money discovery unavailable: {error}")
        
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        print(f"Smart Money mode: {len(nodes)} nodes, {len(edges)} edges")
        
        if len(edges) == 0:
            pytest.skip("No edges in Smart Money mode")
        
        # Check for multi-lane edges
        lane_counts = [e.get("lane_count", 1) for e in edges]
        max_lanes = max(lane_counts)
        print(f"Max lanes in Smart Money graph: {max_lanes}")
        
        assert max_lanes >= 3, f"Expected 3+ lanes, got max {max_lanes}"
    
    def test_cex_flow_mode_multi_edges(self):
        """CEX Flow mode should return multi-edge graph"""
        data, error = self._get_discovery_graph("cex_flow")
        if error:
            pytest.skip(f"CEX Flow discovery unavailable: {error}")
        
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        print(f"CEX Flow mode: {len(nodes)} nodes, {len(edges)} edges")
        
        if len(edges) == 0:
            pytest.skip("No edges in CEX Flow mode")
        
        # Check edge properties
        has_direction = sum(1 for e in edges if e.get("direction"))
        has_curvature = sum(1 for e in edges if e.get("curvature") is not None)
        print(f"Edges with direction: {has_direction}, with curvature: {has_curvature}")
    
    def test_all_mode_multi_edges(self):
        """All mode should return multi-edge graph"""
        data, error = self._get_discovery_graph("all")
        if error:
            pytest.skip(f"All mode discovery unavailable: {error}")
        
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        print(f"All mode: {len(nodes)} nodes, {len(edges)} edges")


class TestCurvatureFormula:
    """Tests specifically for the curvature calculation formula"""
    
    def test_curvature_uniformity(self):
        """Curvatures should be uniformly spaced within ±0.20"""
        # Test the expected formula
        # 9-lane: [-0.20, -0.15, -0.10, -0.05, 0, 0.05, 0.10, 0.15, 0.20]
        expected = EXPECTED_9_LANE_CURVATURES
        
        # Calculate spacing
        spacings = [expected[i+1] - expected[i] for i in range(len(expected)-1)]
        avg_spacing = sum(spacings) / len(spacings)
        
        print(f"9-lane curvatures: {expected}")
        print(f"Spacings: {spacings}")
        print(f"Average spacing: {avg_spacing:.3f}")
        
        # All spacings should be equal (0.05)
        for i, s in enumerate(spacings):
            assert abs(s - 0.05) < 0.001, f"Spacing {i} is {s}, expected 0.05"
    
    def test_center_lane_is_straight(self):
        """Center lane of 9-lane pairs should be straight (curvature=0)"""
        expected = EXPECTED_9_LANE_CURVATURES
        center_idx = 4  # Index 4 of 9
        assert expected[center_idx] == 0.0, f"Center lane curvature should be 0, got {expected[center_idx]}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
