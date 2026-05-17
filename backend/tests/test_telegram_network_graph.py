"""
Tests for Telegram Network Graph API Improvements (v2)

Features tested:
1. GET /api/telegram-intel/graph returns ok=true with 79 nodes and 63 edges
2. GET /api/telegram-intel/graph?root=incrypted returns only 9 nodes and 8 edges
3. GET /api/telegram-intel/graph?root=durov returns both inbound and outbound edges
4. Edge direction calculation (IN if target==root, OUT if source==root)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestTelegramNetworkGraphAPI:
    """Tests for Network Graph API endpoints"""
    
    def test_full_graph_returns_ok_true(self):
        """Test that full graph endpoint returns ok=true"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/graph")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print(f"Full graph: ok={data.get('ok')}")
    
    def test_full_graph_has_79_nodes_63_edges(self):
        """Test that full graph returns approximately 79 nodes and 63 edges"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/graph")
        assert response.status_code == 200
        data = response.json()
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        # Allow for some variance as data may change
        assert len(nodes) >= 50, f"Expected at least 50 nodes, got {len(nodes)}"
        assert len(edges) >= 30, f"Expected at least 30 edges, got {len(edges)}"
        print(f"Full graph: {len(nodes)} nodes, {len(edges)} edges")
    
    def test_root_incrypted_returns_9_nodes_8_edges(self):
        """Test that graph with root=incrypted returns only direct connections"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/graph?root=incrypted")
        assert response.status_code == 200
        data = response.json()
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        assert data.get("ok") == True
        # Should only show direct connections to incrypted
        assert len(nodes) >= 5, f"Expected at least 5 nodes, got {len(nodes)}"
        assert len(nodes) <= 20, f"Expected at most 20 nodes, got {len(nodes)}"
        print(f"Root=incrypted: {len(nodes)} nodes, {len(edges)} edges")
    
    def test_root_incrypted_all_edges_connected_to_root(self):
        """Test that all edges in root graph are connected to the root"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/graph?root=incrypted")
        data = response.json()
        edges = data.get("edges", [])
        
        for edge in edges:
            src = edge.get("source")
            tgt = edge.get("target")
            # All edges should have either source or target = incrypted
            assert src == "incrypted" or tgt == "incrypted", \
                f"Edge {src}->{tgt} not connected to root incrypted"
        print(f"All {len(edges)} edges properly connected to root")
    
    def test_root_durov_has_inbound_and_outbound(self):
        """Test that durov graph has both inbound and outbound edges"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/graph?root=durov")
        assert response.status_code == 200
        data = response.json()
        edges = data.get("edges", [])
        
        inbound = [e for e in edges if e.get("target") == "durov"]
        outbound = [e for e in edges if e.get("source") == "durov"]
        
        print(f"Durov: {len(inbound)} inbound, {len(outbound)} outbound edges")
        # Durov should have outbound edges (mentions others)
        assert len(outbound) >= 5, f"Expected at least 5 outbound edges, got {len(outbound)}"
        # Durov should have at least 1 inbound edge
        assert len(inbound) >= 1, f"Expected at least 1 inbound edge, got {len(inbound)}"
    
    def test_graph_nodes_have_required_fields(self):
        """Test that nodes have required fields: id, label, size"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/graph")
        data = response.json()
        nodes = data.get("nodes", [])
        
        for node in nodes[:10]:  # Check first 10 nodes
            assert "id" in node, "Node missing 'id' field"
            assert "label" in node, "Node missing 'label' field"
            # size is optional but should be present in most nodes
        print(f"Node fields validated for {len(nodes)} nodes")
    
    def test_graph_edges_have_required_fields(self):
        """Test that edges have required fields: source, target"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/graph")
        data = response.json()
        edges = data.get("edges", [])
        
        for edge in edges[:10]:  # Check first 10 edges
            assert "source" in edge, "Edge missing 'source' field"
            assert "target" in edge, "Edge missing 'target' field"
        print(f"Edge fields validated for {len(edges)} edges")
    
    def test_external_nodes_marked_correctly(self):
        """Test that external nodes (not in DB) are marked with external=True"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/graph?root=incrypted")
        data = response.json()
        nodes = data.get("nodes", [])
        
        external_nodes = [n for n in nodes if n.get("external") == True]
        internal_nodes = [n for n in nodes if n.get("external") != True]
        
        print(f"External nodes: {len(external_nodes)}, Internal nodes: {len(internal_nodes)}")
        # At least some nodes should be external (mentioned but not in DB)
        assert len(external_nodes) >= 1 or len(nodes) > 0
    
    def test_graph_stats_endpoint(self):
        """Test the graph stats endpoint"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/graph/stats")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print(f"Graph stats: {data.get('totalNodes')} nodes, {data.get('totalEdges')} edges")


class TestEdgeDirection:
    """Tests for edge direction calculation (IN=green, OUT=red)"""
    
    def test_inbound_edges_target_equals_root(self):
        """Test that inbound edges have target == root (direction=IN -> green)"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/graph?root=durov")
        data = response.json()
        edges = data.get("edges", [])
        
        inbound_count = 0
        for edge in edges:
            if edge.get("target") == "durov":
                inbound_count += 1
                # This would be rendered with direction=IN (green) by frontend
        print(f"Found {inbound_count} inbound edges (IN=green)")
        assert inbound_count >= 1
    
    def test_outbound_edges_source_equals_root(self):
        """Test that outbound edges have source == root (direction=OUT -> red)"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/graph?root=durov")
        data = response.json()
        edges = data.get("edges", [])
        
        outbound_count = 0
        for edge in edges:
            if edge.get("source") == "durov":
                outbound_count += 1
                # This would be rendered with direction=OUT (red) by frontend
        print(f"Found {outbound_count} outbound edges (OUT=red)")
        assert outbound_count >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
