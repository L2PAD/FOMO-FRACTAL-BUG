"""
Graph Bridge API Tests - SIGNAL Layer Edge Building

Tests for:
- POST /api/graph/bridge/run - builds SIGNAL layer edges (MENTIONED_TOKEN, signal_correlated, alpha_source)
- GET /api/graph/bridge/stats - returns graph statistics
- Idempotency verification (running twice doesn't duplicate edges)
- graph_edges collection verification (layer=SIGNAL)
- graph_nodes enrichment verification (actor_score, hit_rate, role)
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestGraphBridgeStats:
    """Test GET /api/graph/bridge/stats endpoint"""
    
    def test_graph_bridge_stats_returns_ok(self):
        """Test that stats endpoint returns ok:true with expected fields"""
        response = requests.get(f"{BASE_URL}/api/graph/bridge/stats", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok:true, got {data}"
        
        # Verify required fields exist
        assert "nodes" in data, "Missing 'nodes' field"
        assert "edges_total" in data, "Missing 'edges_total' field"
        assert "edges_signal" in data, "Missing 'edges_signal' field"
        assert "edge_types" in data, "Missing 'edge_types' field"
        assert "node_types" in data, "Missing 'node_types' field"
        assert "top_actors" in data, "Missing 'top_actors' field"
        
        print(f"Graph stats: nodes={data['nodes']}, edges_total={data['edges_total']}, edges_signal={data['edges_signal']}")
        print(f"Edge types: {data['edge_types']}")
        print(f"Node types: {data['node_types']}")
        print(f"Top actors count: {len(data['top_actors'])}")
    
    def test_graph_bridge_stats_has_signal_edges(self):
        """Verify graph_edges collection has 2717+ edges with layer=SIGNAL"""
        response = requests.get(f"{BASE_URL}/api/graph/bridge/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        signal_edges = data.get("edges_signal", 0)
        
        # Per context: bridge already ran with 2648 MENTIONED_TOKEN + 69 signal_correlated = 2717
        # Allow some tolerance for data changes
        assert signal_edges >= 2700, f"Expected >= 2700 SIGNAL edges, got {signal_edges}"
        print(f"SIGNAL layer edges: {signal_edges}")
    
    def test_graph_bridge_stats_edge_types_breakdown(self):
        """Verify edge_types breakdown includes expected relation types"""
        response = requests.get(f"{BASE_URL}/api/graph/bridge/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        edge_types = data.get("edge_types", {})
        
        # Should have MENTIONED_TOKEN edges
        assert "MENTIONED_TOKEN" in edge_types, f"Missing MENTIONED_TOKEN in edge_types: {edge_types}"
        mentioned_count = edge_types.get("MENTIONED_TOKEN", 0)
        assert mentioned_count > 0, f"Expected MENTIONED_TOKEN edges > 0, got {mentioned_count}"
        
        print(f"Edge types breakdown: {edge_types}")
    
    def test_graph_bridge_stats_node_types_breakdown(self):
        """Verify node_types breakdown includes twitter_account and token"""
        response = requests.get(f"{BASE_URL}/api/graph/bridge/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        node_types = data.get("node_types", {})
        
        # Should have twitter_account and token nodes
        assert "twitter_account" in node_types, f"Missing twitter_account in node_types: {node_types}"
        assert "token" in node_types, f"Missing token in node_types: {node_types}"
        
        print(f"Node types breakdown: {node_types}")
    
    def test_graph_bridge_stats_top_actors(self):
        """Verify top_actors list is populated"""
        response = requests.get(f"{BASE_URL}/api/graph/bridge/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        top_actors = data.get("top_actors", [])
        
        assert len(top_actors) > 0, "Expected top_actors to be populated"
        
        # Verify structure of top_actors
        if top_actors:
            actor = top_actors[0]
            assert "actor" in actor, f"Missing 'actor' field in top_actors entry: {actor}"
            assert "tokens_mentioned" in actor, f"Missing 'tokens_mentioned' field: {actor}"
            assert "total_weight" in actor, f"Missing 'total_weight' field: {actor}"
        
        print(f"Top actors (first 3): {top_actors[:3]}")


class TestGraphBridgeRun:
    """Test POST /api/graph/bridge/run endpoint"""
    
    def test_graph_bridge_run_returns_ok(self):
        """Test that bridge/run returns ok:true with expected result fields"""
        response = requests.post(f"{BASE_URL}/api/graph/bridge/run", timeout=120)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok:true, got {data}"
        
        # Verify required result fields
        assert "mention_edges" in data, "Missing 'mention_edges' field"
        assert "correlation_edges" in data, "Missing 'correlation_edges' field"
        assert "alpha_edges" in data, "Missing 'alpha_edges' field"
        assert "actor_enrichment" in data, "Missing 'actor_enrichment' field"
        assert "totals" in data, "Missing 'totals' field"
        
        print(f"Bridge run results:")
        print(f"  mention_edges: {data['mention_edges']}")
        print(f"  correlation_edges: {data['correlation_edges']}")
        print(f"  alpha_edges: {data['alpha_edges']}")
        print(f"  actor_enrichment: {data['actor_enrichment']}")
        print(f"  totals: {data['totals']}")
    
    def test_graph_bridge_run_mention_edges_structure(self):
        """Verify mention_edges result has expected structure"""
        response = requests.post(f"{BASE_URL}/api/graph/bridge/run", timeout=120)
        assert response.status_code == 200
        
        data = response.json()
        mention_edges = data.get("mention_edges", {})
        
        # Should have edges_created field
        assert "edges_created" in mention_edges, f"Missing 'edges_created' in mention_edges: {mention_edges}"
        
        edges_created = mention_edges.get("edges_created", 0)
        print(f"MENTIONED_TOKEN edges created: {edges_created}")
    
    def test_graph_bridge_run_correlation_edges_structure(self):
        """Verify correlation_edges result has expected structure"""
        response = requests.post(f"{BASE_URL}/api/graph/bridge/run", timeout=120)
        assert response.status_code == 200
        
        data = response.json()
        correlation_edges = data.get("correlation_edges", {})
        
        # Should have edges_created field
        assert "edges_created" in correlation_edges, f"Missing 'edges_created' in correlation_edges: {correlation_edges}"
        
        edges_created = correlation_edges.get("edges_created", 0)
        print(f"signal_correlated edges created: {edges_created}")
    
    def test_graph_bridge_run_alpha_edges_structure(self):
        """Verify alpha_edges result has expected structure"""
        response = requests.post(f"{BASE_URL}/api/graph/bridge/run", timeout=120)
        assert response.status_code == 200
        
        data = response.json()
        alpha_edges = data.get("alpha_edges", {})
        
        # Should have edges_created field
        assert "edges_created" in alpha_edges, f"Missing 'edges_created' in alpha_edges: {alpha_edges}"
        
        edges_created = alpha_edges.get("edges_created", 0)
        # Per context: 0 alpha_source expected (no EARLY+GOOD outcomes yet)
        print(f"alpha_source edges created: {edges_created}")
    
    def test_graph_bridge_run_actor_enrichment_structure(self):
        """Verify actor_enrichment result has expected structure"""
        response = requests.post(f"{BASE_URL}/api/graph/bridge/run", timeout=120)
        assert response.status_code == 200
        
        data = response.json()
        actor_enrichment = data.get("actor_enrichment", {})
        
        # Should have actors_enriched field
        assert "actors_enriched" in actor_enrichment, f"Missing 'actors_enriched' in actor_enrichment: {actor_enrichment}"
        
        actors_enriched = actor_enrichment.get("actors_enriched", 0)
        print(f"Actors enriched: {actors_enriched}")
    
    def test_graph_bridge_run_totals_structure(self):
        """Verify totals result has expected structure"""
        response = requests.post(f"{BASE_URL}/api/graph/bridge/run", timeout=120)
        assert response.status_code == 200
        
        data = response.json()
        totals = data.get("totals", {})
        
        # Should have signal_edges and total_nodes
        assert "signal_edges" in totals, f"Missing 'signal_edges' in totals: {totals}"
        assert "total_nodes" in totals, f"Missing 'total_nodes' in totals: {totals}"
        
        print(f"Totals: signal_edges={totals.get('signal_edges')}, total_nodes={totals.get('total_nodes')}")


class TestGraphBridgeIdempotency:
    """Test idempotency - running bridge twice should not duplicate edges"""
    
    def test_bridge_idempotency(self):
        """Run bridge twice and verify edge count stays the same"""
        # First run
        response1 = requests.post(f"{BASE_URL}/api/graph/bridge/run", timeout=120)
        assert response1.status_code == 200, f"First run failed: {response1.text}"
        
        data1 = response1.json()
        assert data1.get("ok") is True
        
        # Get stats after first run
        stats1 = requests.get(f"{BASE_URL}/api/graph/bridge/stats", timeout=30)
        assert stats1.status_code == 200
        edges_after_first = stats1.json().get("edges_signal", 0)
        
        print(f"Edges after first run: {edges_after_first}")
        
        # Small delay
        time.sleep(2)
        
        # Second run
        response2 = requests.post(f"{BASE_URL}/api/graph/bridge/run", timeout=120)
        assert response2.status_code == 200, f"Second run failed: {response2.text}"
        
        data2 = response2.json()
        assert data2.get("ok") is True
        
        # Get stats after second run
        stats2 = requests.get(f"{BASE_URL}/api/graph/bridge/stats", timeout=30)
        assert stats2.status_code == 200
        edges_after_second = stats2.json().get("edges_signal", 0)
        
        print(f"Edges after second run: {edges_after_second}")
        
        # Edge count should be the same (idempotent upserts)
        assert edges_after_second == edges_after_first, \
            f"Idempotency failed: edges changed from {edges_after_first} to {edges_after_second}"
        
        print(f"Idempotency verified: edge count stable at {edges_after_second}")


class TestGraphNodesEnrichment:
    """Test that graph_nodes have enriched metadata for twitter_account nodes"""
    
    def test_enriched_actor_nodes_via_stats(self):
        """Verify actor nodes are enriched by checking stats after bridge run"""
        # Run bridge to ensure enrichment
        response = requests.post(f"{BASE_URL}/api/graph/bridge/run", timeout=120)
        assert response.status_code == 200
        
        data = response.json()
        actors_enriched = data.get("actor_enrichment", {}).get("actors_enriched", 0)
        
        # Per context: 105 actors enriched
        assert actors_enriched > 0, f"Expected actors to be enriched, got {actors_enriched}"
        print(f"Actors enriched with metadata: {actors_enriched}")
    
    def test_top_actors_have_weight(self):
        """Verify top actors have total_weight (indicates enrichment)"""
        response = requests.get(f"{BASE_URL}/api/graph/bridge/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        top_actors = data.get("top_actors", [])
        
        if top_actors:
            for actor in top_actors[:5]:
                assert actor.get("total_weight", 0) > 0, f"Actor {actor.get('actor')} has no weight"
                print(f"Actor {actor.get('actor')}: tokens={actor.get('tokens_mentioned')}, weight={actor.get('total_weight')}")


class TestGraphEdgesCollection:
    """Test graph_edges collection has correct SIGNAL layer edges"""
    
    def test_signal_layer_edges_count(self):
        """Verify graph_edges has 2717+ edges with layer=SIGNAL"""
        response = requests.get(f"{BASE_URL}/api/graph/bridge/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        signal_edges = data.get("edges_signal", 0)
        
        # Per context: 2648 MENTIONED_TOKEN + 69 signal_correlated = 2717
        assert signal_edges >= 2700, f"Expected >= 2700 SIGNAL edges, got {signal_edges}"
        print(f"SIGNAL layer edges verified: {signal_edges}")
    
    def test_mentioned_token_edges_exist(self):
        """Verify MENTIONED_TOKEN edges exist in edge_types"""
        response = requests.get(f"{BASE_URL}/api/graph/bridge/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        edge_types = data.get("edge_types", {})
        
        mentioned_count = edge_types.get("MENTIONED_TOKEN", 0)
        # Per context: 2648 MENTIONED_TOKEN edges
        assert mentioned_count >= 2600, f"Expected >= 2600 MENTIONED_TOKEN edges, got {mentioned_count}"
        print(f"MENTIONED_TOKEN edges: {mentioned_count}")
    
    def test_signal_correlated_edges_exist(self):
        """Verify signal_correlated edges exist in edge_types"""
        response = requests.get(f"{BASE_URL}/api/graph/bridge/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        edge_types = data.get("edge_types", {})
        
        correlated_count = edge_types.get("signal_correlated", 0)
        # Per context: 69 signal_correlated edges
        assert correlated_count >= 60, f"Expected >= 60 signal_correlated edges, got {correlated_count}"
        print(f"signal_correlated edges: {correlated_count}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
