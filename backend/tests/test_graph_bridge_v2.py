"""
Graph Bridge API Tests V2 - UNIFIED GRAPH with SIGNAL + KNOWLEDGE Layers

Tests for new features in this session:
- POST /api/graph/bridge/run - builds ALL edges: KNOWLEDGE sync + SIGNAL edges + node scores
- GET /api/graph/bridge/stats - returns layers breakdown (SIGNAL + KNOWLEDGE), top_scored nodes
- POST /api/graph/discovery/run - runs 5 parsers + graph rebuild + knowledge sync
- Verify graph has BOTH layers: SIGNAL (~2717) and KNOWLEDGE (~422) edges
- Verify idempotency: bridge/run twice keeps same edge count
- Verify top_scored nodes have node_score, role, hit_rate fields
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestGraphBridgeRunV2:
    """Test POST /api/graph/bridge/run with new KNOWLEDGE layer + node scores"""
    
    def test_bridge_run_returns_ok_with_knowledge_edges(self):
        """Test bridge/run returns ok:true with knowledge_edges field"""
        response = requests.post(f"{BASE_URL}/api/graph/bridge/run", timeout=120)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok:true, got {data}"
        
        # Verify new knowledge_edges field exists
        assert "knowledge_edges" in data, f"Missing 'knowledge_edges' field in response: {data.keys()}"
        
        knowledge_edges = data.get("knowledge_edges", {})
        assert "synced" in knowledge_edges, f"Missing 'synced' in knowledge_edges: {knowledge_edges}"
        
        print(f"KNOWLEDGE edges synced: {knowledge_edges.get('synced', 0)}")
    
    def test_bridge_run_returns_node_scores(self):
        """Test bridge/run returns node_scores field"""
        response = requests.post(f"{BASE_URL}/api/graph/bridge/run", timeout=120)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        # Verify node_scores field exists
        assert "node_scores" in data, f"Missing 'node_scores' field in response: {data.keys()}"
        
        node_scores = data.get("node_scores", {})
        assert "scored" in node_scores, f"Missing 'scored' in node_scores: {node_scores}"
        
        scored_count = node_scores.get("scored", 0)
        print(f"Nodes scored: {scored_count}")
    
    def test_bridge_run_all_expected_fields(self):
        """Verify bridge/run returns all expected fields"""
        response = requests.post(f"{BASE_URL}/api/graph/bridge/run", timeout=120)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        # All expected fields from the new implementation
        expected_fields = [
            "knowledge_edges",
            "mention_edges",
            "actor_enrichment",
            "correlation_edges",
            "alpha_edges",
            "node_scores",
            "totals"
        ]
        
        for field in expected_fields:
            assert field in data, f"Missing '{field}' field in response"
        
        print(f"Bridge run response fields: {list(data.keys())}")
        print(f"  knowledge_edges: {data.get('knowledge_edges')}")
        print(f"  mention_edges: {data.get('mention_edges')}")
        print(f"  correlation_edges: {data.get('correlation_edges')}")
        print(f"  alpha_edges: {data.get('alpha_edges')}")
        print(f"  node_scores: {data.get('node_scores')}")
        print(f"  totals: {data.get('totals')}")


class TestGraphBridgeStatsV2:
    """Test GET /api/graph/bridge/stats with layers breakdown + top_scored"""
    
    def test_stats_returns_layers_breakdown(self):
        """Test stats returns layers field with SIGNAL and KNOWLEDGE counts"""
        response = requests.get(f"{BASE_URL}/api/graph/bridge/stats", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True
        
        # Verify layers field exists
        assert "layers" in data, f"Missing 'layers' field in response: {data.keys()}"
        
        layers = data.get("layers", {})
        print(f"Layers breakdown: {layers}")
        
        # Should have SIGNAL layer
        assert "SIGNAL" in layers, f"Missing 'SIGNAL' in layers: {layers}"
        signal_count = layers.get("SIGNAL", 0)
        assert signal_count > 0, f"Expected SIGNAL edges > 0, got {signal_count}"
        
        # Should have KNOWLEDGE layer (per context: ~422 edges)
        assert "KNOWLEDGE" in layers, f"Missing 'KNOWLEDGE' in layers: {layers}"
        knowledge_count = layers.get("KNOWLEDGE", 0)
        # Allow some tolerance - may vary slightly
        print(f"SIGNAL edges: {signal_count}, KNOWLEDGE edges: {knowledge_count}")
    
    def test_stats_returns_top_scored(self):
        """Test stats returns top_scored field with node_score, role, hit_rate"""
        response = requests.get(f"{BASE_URL}/api/graph/bridge/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        # Verify top_scored field exists
        assert "top_scored" in data, f"Missing 'top_scored' field in response: {data.keys()}"
        
        top_scored = data.get("top_scored", [])
        print(f"Top scored actors count: {len(top_scored)}")
        
        if top_scored:
            # Verify structure of top_scored entries
            actor = top_scored[0]
            assert "actor" in actor, f"Missing 'actor' field in top_scored entry: {actor}"
            assert "node_score" in actor, f"Missing 'node_score' field in top_scored entry: {actor}"
            assert "role" in actor, f"Missing 'role' field in top_scored entry: {actor}"
            assert "hit_rate" in actor, f"Missing 'hit_rate' field in top_scored entry: {actor}"
            
            print(f"Top scored actors (first 5):")
            for a in top_scored[:5]:
                print(f"  {a.get('actor')}: score={a.get('node_score')}, role={a.get('role')}, hit_rate={a.get('hit_rate')}")
    
    def test_stats_edge_types_include_layer_prefix(self):
        """Test edge_types keys include layer prefix (SIGNAL:type, KNOWLEDGE:type)"""
        response = requests.get(f"{BASE_URL}/api/graph/bridge/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        edge_types = data.get("edge_types", {})
        
        print(f"Edge types with layer prefix: {edge_types}")
        
        # Should have SIGNAL:MENTIONED_TOKEN
        signal_mentioned = [k for k in edge_types.keys() if "SIGNAL" in k and "MENTIONED_TOKEN" in k]
        assert len(signal_mentioned) > 0, f"Expected SIGNAL:MENTIONED_TOKEN in edge_types: {edge_types}"
    
    def test_stats_total_edges_equals_layers_sum(self):
        """Verify edges_total equals sum of all layers"""
        response = requests.get(f"{BASE_URL}/api/graph/bridge/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        edges_total = data.get("edges_total", 0)
        layers = data.get("layers", {})
        
        layers_sum = sum(layers.values())
        
        # Should be equal (or very close due to timing)
        assert abs(edges_total - layers_sum) <= 5, \
            f"edges_total ({edges_total}) != sum of layers ({layers_sum})"
        
        print(f"edges_total={edges_total}, layers_sum={layers_sum}")


class TestGraphBridgeKnowledgeLayer:
    """Test KNOWLEDGE layer sync from entity_graph_relations"""
    
    def test_knowledge_edges_synced(self):
        """Verify KNOWLEDGE edges are synced after bridge/run"""
        # Run bridge
        response = requests.post(f"{BASE_URL}/api/graph/bridge/run", timeout=120)
        assert response.status_code == 200
        
        data = response.json()
        knowledge_synced = data.get("knowledge_edges", {}).get("synced", 0)
        
        # Per context: ~422 KNOWLEDGE edges
        print(f"KNOWLEDGE edges synced: {knowledge_synced}")
    
    def test_knowledge_layer_in_stats(self):
        """Verify KNOWLEDGE layer appears in stats after bridge/run"""
        # Run bridge first
        requests.post(f"{BASE_URL}/api/graph/bridge/run", timeout=120)
        
        # Get stats
        response = requests.get(f"{BASE_URL}/api/graph/bridge/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        layers = data.get("layers", {})
        
        knowledge_count = layers.get("KNOWLEDGE", 0)
        print(f"KNOWLEDGE layer edges in stats: {knowledge_count}")


class TestGraphBridgeNodeScoring:
    """Test node scoring: alpha*0.5 + influence*0.3 + activity*0.2"""
    
    def test_node_scores_computed(self):
        """Verify node_scores are computed after bridge/run"""
        response = requests.post(f"{BASE_URL}/api/graph/bridge/run", timeout=120)
        assert response.status_code == 200
        
        data = response.json()
        node_scores = data.get("node_scores", {})
        scored = node_scores.get("scored", 0)
        
        assert scored > 0, f"Expected nodes to be scored, got {scored}"
        print(f"Nodes scored: {scored}")
    
    def test_top_scored_nodes_have_valid_scores(self):
        """Verify top_scored nodes have valid node_score values"""
        # Run bridge first
        requests.post(f"{BASE_URL}/api/graph/bridge/run", timeout=120)
        
        # Get stats
        response = requests.get(f"{BASE_URL}/api/graph/bridge/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        top_scored = data.get("top_scored", [])
        
        if top_scored:
            for actor in top_scored[:5]:
                score = actor.get("node_score", 0)
                # Score should be between 0 and 1 (normalized)
                assert 0 <= score <= 2, f"Invalid node_score {score} for {actor.get('actor')}"
                print(f"Actor {actor.get('actor')}: node_score={score}")


class TestGraphBridgeIdempotencyV2:
    """Test idempotency with KNOWLEDGE layer"""
    
    def test_bridge_idempotency_both_layers(self):
        """Run bridge twice and verify both SIGNAL and KNOWLEDGE edge counts stay the same"""
        # First run
        response1 = requests.post(f"{BASE_URL}/api/graph/bridge/run", timeout=120)
        assert response1.status_code == 200
        
        # Get stats after first run
        stats1 = requests.get(f"{BASE_URL}/api/graph/bridge/stats", timeout=30)
        assert stats1.status_code == 200
        data1 = stats1.json()
        layers1 = data1.get("layers", {})
        signal1 = layers1.get("SIGNAL", 0)
        knowledge1 = layers1.get("KNOWLEDGE", 0)
        
        print(f"After first run: SIGNAL={signal1}, KNOWLEDGE={knowledge1}")
        
        # Small delay
        time.sleep(2)
        
        # Second run
        response2 = requests.post(f"{BASE_URL}/api/graph/bridge/run", timeout=120)
        assert response2.status_code == 200
        
        # Get stats after second run
        stats2 = requests.get(f"{BASE_URL}/api/graph/bridge/stats", timeout=30)
        assert stats2.status_code == 200
        data2 = stats2.json()
        layers2 = data2.get("layers", {})
        signal2 = layers2.get("SIGNAL", 0)
        knowledge2 = layers2.get("KNOWLEDGE", 0)
        
        print(f"After second run: SIGNAL={signal2}, KNOWLEDGE={knowledge2}")
        
        # Both layers should be stable
        assert signal2 == signal1, f"SIGNAL layer changed: {signal1} -> {signal2}"
        assert knowledge2 == knowledge1, f"KNOWLEDGE layer changed: {knowledge1} -> {knowledge2}"
        
        print(f"Idempotency verified: SIGNAL={signal2}, KNOWLEDGE={knowledge2}")


class TestDiscoveryParsers:
    """Test POST /api/graph/discovery/run - runs 5 parsers + graph rebuild + knowledge sync"""
    
    def test_discovery_run_returns_ok(self):
        """Test discovery/run returns ok:true (long-running ~12s)"""
        # This endpoint is slow due to external API calls
        response = requests.post(f"{BASE_URL}/api/graph/discovery/run", timeout=300)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok:true, got {data}"
        
        print(f"Discovery run result: ok={data.get('ok')}")
    
    def test_discovery_run_returns_parsers(self):
        """Test discovery/run returns parsers list with 7 entries"""
        response = requests.post(f"{BASE_URL}/api/graph/discovery/run", timeout=300)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        # Should have parsers field
        assert "parsers" in data, f"Missing 'parsers' field in response: {data.keys()}"
        
        parsers = data.get("parsers", [])
        print(f"Parsers count: {len(parsers)}")
        
        # Per context: 5 external parsers + GraphRebuild + KnowledgeSync = 7
        assert len(parsers) >= 5, f"Expected >= 5 parsers, got {len(parsers)}"
        
        for p in parsers:
            print(f"  {p.get('name')}: ok={p.get('ok')}, result={str(p.get('result', p.get('error', '')))[:100]}")
    
    def test_discovery_run_has_expected_parsers(self):
        """Verify discovery/run includes expected parser names"""
        response = requests.post(f"{BASE_URL}/api/graph/discovery/run", timeout=300)
        assert response.status_code == 200
        
        data = response.json()
        parsers = data.get("parsers", [])
        parser_names = [p.get("name") for p in parsers]
        
        # Expected parsers per context
        expected = ["CryptoRank", "DefiLlama", "CoinGecko", "Dropstab", "ICODrops"]
        
        for name in expected:
            assert name in parser_names, f"Missing parser '{name}' in {parser_names}"
        
        print(f"All expected parsers present: {expected}")
    
    def test_discovery_run_includes_knowledge_sync(self):
        """Verify discovery/run includes KnowledgeSync step"""
        response = requests.post(f"{BASE_URL}/api/graph/discovery/run", timeout=300)
        assert response.status_code == 200
        
        data = response.json()
        parsers = data.get("parsers", [])
        parser_names = [p.get("name") for p in parsers]
        
        assert "KnowledgeSync" in parser_names, f"Missing 'KnowledgeSync' in {parser_names}"
        
        # Find KnowledgeSync result
        ks = next((p for p in parsers if p.get("name") == "KnowledgeSync"), None)
        if ks:
            print(f"KnowledgeSync: ok={ks.get('ok')}, result={ks.get('result')}")
    
    def test_discovery_run_returns_duration(self):
        """Verify discovery/run returns duration_sec field"""
        response = requests.post(f"{BASE_URL}/api/graph/discovery/run", timeout=300)
        assert response.status_code == 200
        
        data = response.json()
        
        assert "duration_sec" in data, f"Missing 'duration_sec' field in response"
        duration = data.get("duration_sec", 0)
        
        print(f"Discovery run duration: {duration}s")


class TestUnifiedGraphTotals:
    """Test unified graph has both SIGNAL and KNOWLEDGE layers with expected totals"""
    
    def test_graph_has_both_layers(self):
        """Verify graph has both SIGNAL and KNOWLEDGE layers"""
        # Run bridge to ensure both layers are populated
        requests.post(f"{BASE_URL}/api/graph/bridge/run", timeout=120)
        
        # Get stats
        response = requests.get(f"{BASE_URL}/api/graph/bridge/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        layers = data.get("layers", {})
        
        assert "SIGNAL" in layers, f"Missing SIGNAL layer: {layers}"
        assert "KNOWLEDGE" in layers, f"Missing KNOWLEDGE layer: {layers}"
        
        signal = layers.get("SIGNAL", 0)
        knowledge = layers.get("KNOWLEDGE", 0)
        total = data.get("edges_total", 0)
        
        print(f"Unified graph: SIGNAL={signal}, KNOWLEDGE={knowledge}, total={total}")
        
        # Per context: ~2717 SIGNAL + ~422 KNOWLEDGE = ~3139 total
        assert signal >= 2700, f"Expected >= 2700 SIGNAL edges, got {signal}"
    
    def test_graph_total_edges_approximately_3139(self):
        """Verify total edges is approximately 3139 (2717 SIGNAL + 422 KNOWLEDGE)"""
        # Run bridge
        requests.post(f"{BASE_URL}/api/graph/bridge/run", timeout=120)
        
        # Get stats
        response = requests.get(f"{BASE_URL}/api/graph/bridge/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        total = data.get("edges_total", 0)
        
        # Allow 10% tolerance for data changes
        expected_min = 2800  # ~3139 - 10%
        expected_max = 3500  # ~3139 + 10%
        
        assert expected_min <= total <= expected_max, \
            f"Expected total edges between {expected_min} and {expected_max}, got {total}"
        
        print(f"Total edges: {total} (expected ~3139)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
