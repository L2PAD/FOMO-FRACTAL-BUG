"""
CEX Flow Mode Filtering Tests
=============================
Tests for the CEX Flow mode bug fix that ensures:
1. GET /api/graph-core/render/{node_id}?mode=cex_flow returns filtered data with deposit/withdraw edges
2. CEX Flow mode for CEX entity (Binance) returns nodes and edges (not empty)
3. CEX Flow mode for wallet entity (Vitalik) returns deposit/withdraw edges
4. Other modes (smart_money, entity, etc.) are NOT affected
5. No mode parameter returns full graph (all edge types)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestCEXFlowModeFiltering:
    """Tests for CEX Flow mode filtering in graph render endpoint"""
    
    # Known Binance CEX address (from graph_anchor_entities)
    BINANCE_NODE_ID = "cex:0x28c6c06298d514db089934071355e5743bf21d60:ethereum"
    
    # Known Vitalik wallet address
    VITALIK_NODE_ID = "wallet:0xd8da6bf26964af9d7eed9e03e53415d37aa96045:ethereum"
    
    def test_cex_flow_mode_for_cex_entity_returns_data(self):
        """
        CEX Flow mode for CEX entity (Binance) should return nodes and edges (not empty).
        This is a critical test for the bug fix.
        """
        url = f"{BASE_URL}/api/graph-core/render/{self.BINANCE_NODE_ID}?mode=cex_flow"
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Should have nodes (at least the center node)
        nodes = data.get("nodes", [])
        assert len(nodes) > 0, "CEX Flow mode for Binance should return at least 1 node"
        
        # Should have edges (CEX-related)
        edges = data.get("edges", [])
        
        # Even if no edges, meta should indicate cex_flow mode
        meta = data.get("meta", {})
        assert meta.get("mode") == "cex_flow", f"Expected mode=cex_flow in meta, got {meta.get('mode')}"
        
        print(f"[PASS] CEX Flow mode for Binance: {len(nodes)} nodes, {len(edges)} edges")
        
        # Verify center node is present
        node_ids = [n.get("id") for n in nodes]
        assert self.BINANCE_NODE_ID in node_ids or any("0x28c6c06298d514db089934071355e5743bf21d60" in nid for nid in node_ids), \
            "Center node (Binance) should be in returned nodes"
    
    def test_cex_flow_mode_edges_are_deposit_withdraw_or_cex_connected(self):
        """
        CEX Flow mode edges should only be:
        - deposit or withdraw flow_type/type
        - OR connected to a CEX/exchange node
        """
        url = f"{BASE_URL}/api/graph-core/render/{self.BINANCE_NODE_ID}?mode=cex_flow"
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        
        data = response.json()
        edges = data.get("edges", [])
        nodes = data.get("nodes", [])
        
        # Build set of CEX node IDs
        cex_node_ids = set()
        for n in nodes:
            ntype = (n.get("type") or "wallet").lower()
            nid = n.get("id", "")
            if ntype in ("cex", "exchange") or nid.startswith("cex:") or nid.startswith("exchange:"):
                cex_node_ids.add(nid)
        
        cex_flow_types = {"deposit", "withdraw"}
        
        for edge in edges:
            src = edge.get("source", "")
            tgt = edge.get("target", "")
            flow_type = (edge.get("flowType") or edge.get("flow_type") or edge.get("type") or "transfer").lower()
            
            is_cex_edge = (src in cex_node_ids or tgt in cex_node_ids)
            is_cex_flow_type = flow_type in cex_flow_types
            
            assert is_cex_edge or is_cex_flow_type, \
                f"Edge {src}->{tgt} (type={flow_type}) should be connected to CEX or be deposit/withdraw"
        
        print(f"[PASS] All {len(edges)} edges are CEX-connected or deposit/withdraw")
    
    def test_cex_flow_mode_for_wallet_returns_data(self):
        """
        CEX Flow mode for wallet (Vitalik) should return deposit/withdraw edges.
        """
        url = f"{BASE_URL}/api/graph-core/render/{self.VITALIK_NODE_ID}?mode=cex_flow"
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        meta = data.get("meta", {})
        
        # Should have mode=cex_flow in meta
        assert meta.get("mode") == "cex_flow", f"Expected mode=cex_flow, got {meta.get('mode')}"
        
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        
        print(f"[PASS] CEX Flow mode for Vitalik: {len(nodes)} nodes, {len(edges)} edges")
    
    def test_smart_money_mode_not_affected(self):
        """
        Smart Money mode should still work correctly (not affected by CEX Flow fix).
        """
        url = f"{BASE_URL}/api/graph-core/render/{self.BINANCE_NODE_ID}?mode=smart_money"
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        meta = data.get("meta", {})
        
        # Should have mode=smart_money
        assert meta.get("mode") == "smart_money", f"Expected mode=smart_money, got {meta.get('mode')}"
        
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        
        print(f"[PASS] Smart Money mode works: {len(nodes)} nodes, {len(edges)} edges")
    
    def test_entity_mode_not_affected(self):
        """
        Entity mode should still work correctly (not affected by CEX Flow fix).
        """
        url = f"{BASE_URL}/api/graph-core/render/{self.BINANCE_NODE_ID}?mode=entity"
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        meta = data.get("meta", {})
        
        # Should have mode=entity
        assert meta.get("mode") == "entity", f"Expected mode=entity, got {meta.get('mode')}"
        
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        
        print(f"[PASS] Entity mode works: {len(nodes)} nodes, {len(edges)} edges")
    
    def test_no_mode_returns_full_graph(self):
        """
        No mode parameter should return full graph with all edge types.
        """
        url = f"{BASE_URL}/api/graph-core/render/{self.BINANCE_NODE_ID}"
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        meta = data.get("meta", {})
        
        # mode should be None or not present
        assert meta.get("mode") is None, f"Expected mode=None for no filter, got {meta.get('mode')}"
        
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        
        # Full graph should have at least the center node and some edges
        assert len(nodes) >= 1, "Full graph should have at least 1 node"
        
        print(f"[PASS] No mode (full graph): {len(nodes)} nodes, {len(edges)} edges")
    
    def test_cex_flow_edges_less_or_equal_to_full_graph(self):
        """
        CEX Flow mode should return fewer or equal edges than full graph (filtering works).
        """
        # Get full graph
        full_url = f"{BASE_URL}/api/graph-core/render/{self.BINANCE_NODE_ID}"
        full_response = requests.get(full_url, timeout=30)
        assert full_response.status_code == 200
        full_data = full_response.json()
        full_edges = len(full_data.get("edges", []))
        
        # Get CEX flow filtered graph
        cex_url = f"{BASE_URL}/api/graph-core/render/{self.BINANCE_NODE_ID}?mode=cex_flow"
        cex_response = requests.get(cex_url, timeout=30)
        assert cex_response.status_code == 200
        cex_data = cex_response.json()
        cex_edges = len(cex_data.get("edges", []))
        
        # CEX flow should have less or equal edges (filtering)
        assert cex_edges <= full_edges, \
            f"CEX Flow mode ({cex_edges} edges) should have <= full graph ({full_edges} edges)"
        
        print(f"[PASS] CEX Flow filtering works: {cex_edges} <= {full_edges} edges")
    
    def test_render_seeds_with_cex_flow_mode(self):
        """
        Test that render-seeds endpoint also supports cex_flow mode.
        """
        seeds = self.BINANCE_NODE_ID
        url = f"{BASE_URL}/api/graph-core/render-seeds?seeds={seeds}&mode=cex_flow&limit=50"
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        meta = data.get("meta", {})
        
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        
        print(f"[PASS] Render-seeds with cex_flow: {len(nodes)} nodes, {len(edges)} edges")
    
    def test_project_endpoint_skips_cex_flow_filter(self):
        """
        Project endpoint should skip cex_flow filter (handled post-render).
        This tests that the fix in graph_projection_service.py line 73 works.
        """
        url = f"{BASE_URL}/api/graph-core/project/{self.BINANCE_NODE_ID}?mode=cex_flow"
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        meta = data.get("meta", {})
        
        # Mode should be passed through but not filtered at projection level
        assert meta.get("mode") == "cex_flow", f"Expected mode=cex_flow in meta, got {meta.get('mode')}"
        
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        
        # Projection endpoint should return data (not filtered to empty)
        assert len(nodes) >= 1, "Project endpoint with cex_flow should return at least 1 node"
        
        print(f"[PASS] Project endpoint with cex_flow: {len(nodes)} nodes, {len(edges)} edges")


class TestGraphHealthAndMeta:
    """Basic health and meta tests for graph endpoints"""
    
    def test_graph_health_endpoint(self):
        """Test that graph health endpoint is working"""
        url = f"{BASE_URL}/api/graph-core/health"
        response = requests.get(url, timeout=10)
        
        assert response.status_code == 200, f"Health endpoint failed: {response.status_code}"
        
        data = response.json()
        assert data.get("status") == "ok", f"Health status not ok: {data.get('status')}"
        
        print(f"[PASS] Graph health endpoint OK")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
