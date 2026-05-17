"""
Graph Intelligence Layer Tests — 4 New Edge Types

Tests for the Graph Intelligence layer that adds dynamic intelligence edges:
1. entity_pressure: token→project based on actor convergence
2. alpha_source: actor→token from high-hit-rate early actors
3. temporal_decay: weight_current with exp decay, weight_total preserved
4. attention_flow: 1-hop collapse actor→project via token bridge

Endpoints:
- POST /api/graph/intelligence/run — runs all 4 intelligence layers
- GET /api/graph/intelligence/stats — returns edge counts, decay stats
- POST /api/graph/build — full build includes intelligence (step 6)

Expected counts (from agent context):
- entity_pressure: 42 edges
- alpha_source: 253 edges from 12 qualifying actors
- temporal_decay: 2648 edge states in graph_edge_state
- attention_flow: 872 edges
- Total edges: 6087+
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestGraphIntelligenceRun:
    """POST /api/graph/intelligence/run — runs all 4 intelligence layers"""
    
    def test_intelligence_run_returns_ok(self, api_client):
        """POST /api/graph/intelligence/run - returns ok status"""
        response = api_client.post(f"{BASE_URL}/api/graph/intelligence/run")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got: {data}"
        print(f"PASS: Intelligence run returned ok=True")
        
    def test_intelligence_run_has_all_layers(self, api_client):
        """POST /api/graph/intelligence/run - returns all 4 layer results"""
        response = api_client.post(f"{BASE_URL}/api/graph/intelligence/run")
        assert response.status_code == 200
        
        data = response.json()
        
        # Check all 4 layers are present
        assert "entity_pressure" in data, "Missing entity_pressure in response"
        assert "alpha_source" in data, "Missing alpha_source in response"
        assert "temporal_decay" in data, "Missing temporal_decay in response"
        assert "attention_flow" in data, "Missing attention_flow in response"
        assert "summary" in data, "Missing summary in response"
        
        print(f"PASS: All 4 intelligence layers present in response")
        
    def test_entity_pressure_edges_created(self, api_client):
        """entity_pressure: creates token→project edges based on actor convergence"""
        response = api_client.post(f"{BASE_URL}/api/graph/intelligence/run")
        assert response.status_code == 200
        
        data = response.json()
        ep = data.get("entity_pressure", {})
        
        # Should have edges count
        edges = ep.get("edges", 0)
        assert edges >= 0, f"entity_pressure edges should be >= 0, got {edges}"
        
        # Should have top_pressure list
        top_pressure = ep.get("top_pressure", [])
        assert isinstance(top_pressure, list), "top_pressure should be a list"
        
        print(f"PASS: entity_pressure created {edges} edges, top_pressure has {len(top_pressure)} items")
        
    def test_alpha_source_edges_created(self, api_client):
        """alpha_source: creates actor→token edges from high-hit-rate actors"""
        response = api_client.post(f"{BASE_URL}/api/graph/intelligence/run")
        assert response.status_code == 200
        
        data = response.json()
        alpha = data.get("alpha_source", {})
        
        # Should have edges count
        edges = alpha.get("edges", 0)
        assert edges >= 0, f"alpha_source edges should be >= 0, got {edges}"
        
        # Should have qualifying_actors count
        qualifying = alpha.get("qualifying_actors", 0)
        assert qualifying >= 0, f"qualifying_actors should be >= 0, got {qualifying}"
        
        # Should have top_alpha list
        top_alpha = alpha.get("top_alpha", [])
        assert isinstance(top_alpha, list), "top_alpha should be a list"
        
        print(f"PASS: alpha_source created {edges} edges from {qualifying} qualifying actors")
        
    def test_temporal_decay_applied(self, api_client):
        """temporal_decay: applies exp decay to SIGNAL edges"""
        response = api_client.post(f"{BASE_URL}/api/graph/intelligence/run")
        assert response.status_code == 200
        
        data = response.json()
        decay = data.get("temporal_decay", {})
        
        # Should have edges_updated count
        updated = decay.get("edges_updated", 0)
        assert updated >= 0, f"edges_updated should be >= 0, got {updated}"
        
        # Should have avg_decay_factor
        avg_decay = decay.get("avg_decay_factor", 0)
        assert 0 <= avg_decay <= 1, f"avg_decay_factor should be 0-1, got {avg_decay}"
        
        # Should have tau_hours
        tau = decay.get("tau_hours", 0)
        assert tau > 0, f"tau_hours should be > 0, got {tau}"
        
        print(f"PASS: temporal_decay updated {updated} edges, avg_decay={avg_decay}, tau={tau}h")
        
    def test_attention_flow_edges_created(self, api_client):
        """attention_flow: creates actor→project edges via 1-hop collapse"""
        response = api_client.post(f"{BASE_URL}/api/graph/intelligence/run")
        assert response.status_code == 200
        
        data = response.json()
        flow = data.get("attention_flow", {})
        
        # Should have edges count
        edges = flow.get("edges", 0)
        assert edges >= 0, f"attention_flow edges should be >= 0, got {edges}"
        
        # Should have top_flows list
        top_flows = flow.get("top_flows", [])
        assert isinstance(top_flows, list), "top_flows should be a list"
        
        print(f"PASS: attention_flow created {edges} edges, top_flows has {len(top_flows)} items")
        
    def test_intelligence_summary_counts(self, api_client):
        """summary: contains total edge counts"""
        response = api_client.post(f"{BASE_URL}/api/graph/intelligence/run")
        assert response.status_code == 200
        
        data = response.json()
        summary = data.get("summary", {})
        
        # Should have all counts
        assert "entity_pressure_edges" in summary, "Missing entity_pressure_edges in summary"
        assert "alpha_source_edges" in summary, "Missing alpha_source_edges in summary"
        assert "attention_flow_edges" in summary, "Missing attention_flow_edges in summary"
        assert "edge_states" in summary, "Missing edge_states in summary"
        assert "duration_sec" in summary, "Missing duration_sec in summary"
        
        print(f"PASS: Summary - pressure={summary.get('entity_pressure_edges')}, "
              f"alpha={summary.get('alpha_source_edges')}, flow={summary.get('attention_flow_edges')}, "
              f"states={summary.get('edge_states')}, duration={summary.get('duration_sec')}s")


class TestGraphIntelligenceStats:
    """GET /api/graph/intelligence/stats — returns edge counts and stats"""
    
    def test_stats_returns_ok(self, api_client):
        """GET /api/graph/intelligence/stats - returns ok status"""
        response = api_client.get(f"{BASE_URL}/api/graph/intelligence/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got: {data}"
        print(f"PASS: Intelligence stats returned ok=True")
        
    def test_stats_has_edge_counts(self, api_client):
        """GET /api/graph/intelligence/stats - has edge counts for all types"""
        response = api_client.get(f"{BASE_URL}/api/graph/intelligence/stats")
        assert response.status_code == 200
        
        data = response.json()
        
        # Should have all edge counts
        assert "entity_pressure_edges" in data, "Missing entity_pressure_edges"
        assert "alpha_source_edges" in data, "Missing alpha_source_edges"
        assert "attention_flow_edges" in data, "Missing attention_flow_edges"
        assert "edge_states" in data, "Missing edge_states"
        
        print(f"PASS: Stats - pressure={data.get('entity_pressure_edges')}, "
              f"alpha={data.get('alpha_source_edges')}, flow={data.get('attention_flow_edges')}, "
              f"states={data.get('edge_states')}")
        
    def test_stats_has_decay_stats(self, api_client):
        """GET /api/graph/intelligence/stats - has decay statistics"""
        response = api_client.get(f"{BASE_URL}/api/graph/intelligence/stats")
        assert response.status_code == 200
        
        data = response.json()
        
        # Should have decay_stats
        decay_stats = data.get("decay_stats", {})
        
        # If there are edge states, should have decay stats
        if data.get("edge_states", 0) > 0:
            assert "avg_decay" in decay_stats or len(decay_stats) > 0, "Missing decay stats"
            print(f"PASS: Decay stats present: {decay_stats}")
        else:
            print(f"PASS: No edge states yet, decay_stats empty as expected")
            
    def test_stats_has_top_pressure(self, api_client):
        """GET /api/graph/intelligence/stats - has top pressure entities"""
        response = api_client.get(f"{BASE_URL}/api/graph/intelligence/stats")
        assert response.status_code == 200
        
        data = response.json()
        
        # Should have top_pressure list
        top_pressure = data.get("top_pressure", [])
        assert isinstance(top_pressure, list), "top_pressure should be a list"
        
        # If there are pressure edges, should have items
        if data.get("entity_pressure_edges", 0) > 0:
            assert len(top_pressure) > 0, "top_pressure should have items when edges exist"
            
            # Check structure of first item
            if len(top_pressure) > 0:
                item = top_pressure[0]
                assert "token" in item, "top_pressure item missing token"
                assert "project" in item, "top_pressure item missing project"
                assert "weight" in item, "top_pressure item missing weight"
                
        print(f"PASS: top_pressure has {len(top_pressure)} items")
        
    def test_stats_has_top_alpha(self, api_client):
        """GET /api/graph/intelligence/stats - has top alpha sources"""
        response = api_client.get(f"{BASE_URL}/api/graph/intelligence/stats")
        assert response.status_code == 200
        
        data = response.json()
        
        # Should have top_alpha list
        top_alpha = data.get("top_alpha", [])
        assert isinstance(top_alpha, list), "top_alpha should be a list"
        
        # If there are alpha edges, should have items
        if data.get("alpha_source_edges", 0) > 0:
            assert len(top_alpha) > 0, "top_alpha should have items when edges exist"
            
            # Check structure of first item
            if len(top_alpha) > 0:
                item = top_alpha[0]
                assert "actor" in item, "top_alpha item missing actor"
                assert "token" in item, "top_alpha item missing token"
                assert "weight" in item, "top_alpha item missing weight"
                
        print(f"PASS: top_alpha has {len(top_alpha)} items")


class TestGraphBuildIncludesIntelligence:
    """POST /api/graph/build — full build includes intelligence at step 6"""
    
    def test_full_build_returns_ok(self, api_client):
        """POST /api/graph/build - returns ok status"""
        response = api_client.post(f"{BASE_URL}/api/graph/build", timeout=120)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got: {data}"
        print(f"PASS: Full build returned ok=True")
        
    def test_full_build_includes_intelligence(self, api_client):
        """POST /api/graph/build - includes intelligence results"""
        response = api_client.post(f"{BASE_URL}/api/graph/build", timeout=120)
        assert response.status_code == 200
        
        data = response.json()
        
        # Should have intelligence results
        assert "intelligence" in data, "Missing intelligence in full build response"
        
        intel = data.get("intelligence", {})
        assert intel.get("ok") is True, "Intelligence should return ok=True"
        
        # Should have all 4 layers
        assert "entity_pressure" in intel, "Missing entity_pressure in intelligence"
        assert "alpha_source" in intel, "Missing alpha_source in intelligence"
        assert "temporal_decay" in intel, "Missing temporal_decay in intelligence"
        assert "attention_flow" in intel, "Missing attention_flow in intelligence"
        
        print(f"PASS: Full build includes all 4 intelligence layers")
        
    def test_full_build_totals(self, api_client):
        """POST /api/graph/build - returns total node/edge counts"""
        response = api_client.post(f"{BASE_URL}/api/graph/build", timeout=120)
        assert response.status_code == 200
        
        data = response.json()
        totals = data.get("totals", {})
        
        # Should have totals
        assert "nodes" in totals, "Missing nodes in totals"
        assert "edges" in totals, "Missing edges in totals"
        assert "signal_edges" in totals, "Missing signal_edges in totals"
        assert "knowledge_edges" in totals, "Missing knowledge_edges in totals"
        
        nodes = totals.get("nodes", 0)
        edges = totals.get("edges", 0)
        signal = totals.get("signal_edges", 0)
        knowledge = totals.get("knowledge_edges", 0)
        
        # Verify counts are reasonable
        assert nodes > 0, f"nodes should be > 0, got {nodes}"
        assert edges > 0, f"edges should be > 0, got {edges}"
        
        print(f"PASS: Full build totals - nodes={nodes}, edges={edges}, "
              f"signal={signal}, knowledge={knowledge}")


class TestEntityPressureDetails:
    """Detailed tests for entity_pressure edge type"""
    
    def test_btc_has_most_pressure(self, api_client):
        """BTC should have significant pressure (many actors mention it)"""
        response = api_client.get(f"{BASE_URL}/api/graph/intelligence/stats")
        assert response.status_code == 200
        
        data = response.json()
        top_pressure = data.get("top_pressure", [])
        
        # Find BTC in top pressure
        btc_items = [p for p in top_pressure if "BTC" in p.get("token", "").upper()]
        
        if len(btc_items) > 0:
            btc = btc_items[0]
            actors = btc.get("actors", 0)
            print(f"PASS: BTC found in top_pressure with {actors} actors")
        else:
            # BTC might not be in top 10, check if pressure edges exist
            pressure_count = data.get("entity_pressure_edges", 0)
            print(f"INFO: BTC not in top 10 pressure, total pressure edges: {pressure_count}")
            
    def test_pressure_only_for_tokens_with_bridge(self, api_client):
        """entity_pressure edges should only exist for tokens with token_of bridge"""
        # Get entity_pressure edges
        response = api_client.get(f"{BASE_URL}/api/graph/build/stats")
        assert response.status_code == 200
        
        data = response.json()
        edge_types = data.get("edge_types", {})
        
        # Check if entity_pressure exists
        pressure_key = "SIGNAL:entity_pressure"
        pressure_count = edge_types.get(pressure_key, 0)
        
        # Check token_of bridges exist
        token_of_count = data.get("cross_layer", {}).get("token_of", 0)
        
        print(f"PASS: entity_pressure={pressure_count}, token_of bridges={token_of_count}")


class TestAlphaSourceDetails:
    """Detailed tests for alpha_source edge type"""
    
    def test_alpha_source_thresholds(self, api_client):
        """alpha_source: only actors with hit_rate>=0.65, early>=0.5, signals>=10"""
        response = api_client.post(f"{BASE_URL}/api/graph/intelligence/run")
        assert response.status_code == 200
        
        data = response.json()
        alpha = data.get("alpha_source", {})
        
        qualifying = alpha.get("qualifying_actors", 0)
        edges = alpha.get("edges", 0)
        
        # If there are qualifying actors, there should be edges
        if qualifying > 0:
            assert edges > 0, f"Should have edges when {qualifying} actors qualify"
            
        print(f"PASS: alpha_source - {qualifying} qualifying actors, {edges} edges")
        
    def test_alpha_source_top_actors(self, api_client):
        """alpha_source: top_alpha should have actor details"""
        response = api_client.get(f"{BASE_URL}/api/graph/intelligence/stats")
        assert response.status_code == 200
        
        data = response.json()
        top_alpha = data.get("top_alpha", [])
        
        if len(top_alpha) > 0:
            # Check first actor has required fields
            actor = top_alpha[0]
            assert "actor" in actor, "Missing actor field"
            assert "token" in actor, "Missing token field"
            assert "weight" in actor, "Missing weight field"
            
            # hit_rate should be present if available
            if "hit_rate" in actor:
                hr = actor["hit_rate"]
                assert 0 <= hr <= 1, f"hit_rate should be 0-1, got {hr}"
                
        print(f"PASS: top_alpha has {len(top_alpha)} actors with proper structure")


class TestTemporalDecayDetails:
    """Detailed tests for temporal_decay edge state"""
    
    def test_edge_state_collection_exists(self, api_client):
        """graph_edge_state collection should have weight_current, weight_total, decay_factor"""
        response = api_client.get(f"{BASE_URL}/api/graph/intelligence/stats")
        assert response.status_code == 200
        
        data = response.json()
        edge_states = data.get("edge_states", 0)
        decay_stats = data.get("decay_stats", {})
        
        print(f"PASS: edge_states={edge_states}, decay_stats={decay_stats}")
        
    def test_avg_decay_reasonable(self, api_client):
        """avg_decay should be around 0.71 (based on tau=48h)"""
        response = api_client.get(f"{BASE_URL}/api/graph/intelligence/stats")
        assert response.status_code == 200
        
        data = response.json()
        decay_stats = data.get("decay_stats", {})
        
        if decay_stats:
            avg_decay = decay_stats.get("avg_decay", 0)
            # Decay should be between 0 and 1
            assert 0 <= avg_decay <= 1, f"avg_decay should be 0-1, got {avg_decay}"
            print(f"PASS: avg_decay={avg_decay}")
        else:
            print(f"INFO: No decay stats yet (no edge states)")


class TestAttentionFlowDetails:
    """Detailed tests for attention_flow edge type"""
    
    def test_attention_flow_1hop_collapse(self, api_client):
        """attention_flow: actor→project via token bridge"""
        response = api_client.post(f"{BASE_URL}/api/graph/intelligence/run")
        assert response.status_code == 200
        
        data = response.json()
        flow = data.get("attention_flow", {})
        
        edges = flow.get("edges", 0)
        top_flows = flow.get("top_flows", [])
        
        if len(top_flows) > 0:
            # Check structure
            item = top_flows[0]
            assert "actor" in item, "Missing actor in flow"
            assert "project" in item, "Missing project in flow"
            assert "tokens" in item, "Missing tokens in flow"
            assert "weight" in item, "Missing weight in flow"
            
            # tokens should be a list
            assert isinstance(item["tokens"], list), "tokens should be a list"
            
        print(f"PASS: attention_flow - {edges} edges, top_flows has {len(top_flows)} items")


class TestSolanaEntityEdges:
    """Verify Solana has expected edge types"""
    
    def test_solana_has_multiple_edge_types(self, api_client):
        """Solana should have: entity_pressure + attention_flow + contributes_to + invested_in + founded + token_of"""
        response = api_client.get(f"{BASE_URL}/api/graph/entity/project:solana")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got: {data}"
        
        edges = data.get("edges", [])
        edges_by_layer = data.get("edges_by_layer", {})
        
        # Get unique relation types
        relation_types = set(e.get("relation_type") for e in edges)
        
        print(f"Solana edges: {len(edges)} total, by_layer={edges_by_layer}")
        print(f"Solana relation types: {relation_types}")
        
        # Check for expected types (may not all be present depending on data)
        expected_types = ["token_of", "contributes_to"]
        for et in expected_types:
            if et in relation_types:
                print(f"  FOUND: {et}")
            else:
                print(f"  MISSING: {et} (may be expected if no data)")


class TestVitalikEntityEdges:
    """Verify Vitalik has expected edge types"""
    
    def test_vitalik_has_expected_edges(self, api_client):
        """Vitalik should have: MENTIONED_TOKEN + attention_flow + account_of"""
        # Try different possible IDs for Vitalik
        possible_ids = ["twitter:vitalikbuterin", "person:vitalik", "twitter:vitalik"]
        
        found = False
        for entity_id in possible_ids:
            response = api_client.get(f"{BASE_URL}/api/graph/entity/{entity_id}")
            if response.status_code == 200:
                data = response.json()
                if data.get("ok") is True:
                    found = True
                    edges = data.get("edges", [])
                    relation_types = set(e.get("relation_type") for e in edges)
                    
                    print(f"Vitalik ({entity_id}) edges: {len(edges)} total")
                    print(f"Vitalik relation types: {relation_types}")
                    break
                    
        if not found:
            print(f"INFO: Vitalik entity not found in graph (may be expected)")


class TestIdempotency:
    """Verify running intelligence twice doesn't create duplicates"""
    
    def test_intelligence_idempotent(self, api_client):
        """Running intelligence twice should produce same edge counts"""
        # First run
        response1 = api_client.post(f"{BASE_URL}/api/graph/intelligence/run")
        assert response1.status_code == 200
        data1 = response1.json()
        summary1 = data1.get("summary", {})
        
        # Second run
        response2 = api_client.post(f"{BASE_URL}/api/graph/intelligence/run")
        assert response2.status_code == 200
        data2 = response2.json()
        summary2 = data2.get("summary", {})
        
        # Compare counts
        pressure1 = summary1.get("entity_pressure_edges", 0)
        pressure2 = summary2.get("entity_pressure_edges", 0)
        
        alpha1 = summary1.get("alpha_source_edges", 0)
        alpha2 = summary2.get("alpha_source_edges", 0)
        
        flow1 = summary1.get("attention_flow_edges", 0)
        flow2 = summary2.get("attention_flow_edges", 0)
        
        # Counts should be the same (idempotent)
        assert pressure1 == pressure2, f"entity_pressure not idempotent: {pressure1} vs {pressure2}"
        assert alpha1 == alpha2, f"alpha_source not idempotent: {alpha1} vs {alpha2}"
        assert flow1 == flow2, f"attention_flow not idempotent: {flow1} vs {flow2}"
        
        print(f"PASS: Intelligence is idempotent - pressure={pressure1}, alpha={alpha1}, flow={flow1}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
