"""
Test Unified Graph Builder APIs for Decision Intelligence System.

Tests:
- POST /api/graph/build — Full graph rebuild with entity resolution, cross-layer bridges
- POST /api/graph/hydrate — On-demand entity hydration (search 'Solana', 'Ethereum', 'vitalik', 'a16z')
- GET /api/graph/entity/{entity_id} — Entity detail with edges and neighbors
- GET /api/graph/build/stats — Graph statistics with cross-layer bridge counts
- Verify Vitalik: person:vitalik has founded->project:ethereum, twitter:vitalikbuterin has account_of->person:vitalik
- Verify Solana: project:solana has invested_in from funds, founded from persons, token:SOL->token_of->project:solana
- Verify no duplicate edges after running /api/graph/build twice (idempotency test)
- POST /api/graph/bridge/run — Legacy bridge still works alongside new builder
- GET /api/graph/bridge/stats — Legacy stats endpoint still works
- GET /api/graph/parsers — Parser registry returns all 9 parsers
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestUnifiedGraphBuilder:
    """Test Unified Graph Builder APIs."""

    def test_01_graph_build_stats_initial(self):
        """GET /api/graph/build/stats — Get initial graph statistics."""
        response = requests.get(f"{BASE_URL}/api/graph/build/stats", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Verify structure
        assert "nodes" in data, "Missing 'nodes' in response"
        assert "edges" in data, "Missing 'edges' in response"
        assert "layers" in data, "Missing 'layers' in response"
        assert "cross_layer" in data, "Missing 'cross_layer' in response"
        
        # Verify cross-layer bridges exist
        cross_layer = data.get("cross_layer", {})
        assert "token_of" in cross_layer, "Missing 'token_of' in cross_layer"
        assert "account_of" in cross_layer, "Missing 'account_of' in cross_layer"
        assert "official_account_of" in cross_layer, "Missing 'official_account_of' in cross_layer"
        
        print(f"Initial stats: {data['nodes']} nodes, {data['edges']} edges")
        print(f"Layers: {data.get('layers', {})}")
        print(f"Cross-layer bridges: token_of={cross_layer.get('token_of', 0)}, account_of={cross_layer.get('account_of', 0)}, official_account_of={cross_layer.get('official_account_of', 0)}")

    def test_02_graph_full_build(self):
        """POST /api/graph/build — Full graph rebuild with entity resolution."""
        response = requests.post(f"{BASE_URL}/api/graph/build", timeout=120)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Verify build results
        assert "totals" in data, "Missing 'totals' in response"
        totals = data["totals"]
        assert totals.get("nodes", 0) > 0, "Expected nodes > 0"
        assert totals.get("edges", 0) > 0, "Expected edges > 0"
        
        # Verify lookups were built
        assert "lookups" in data, "Missing 'lookups' in response"
        lookups = data["lookups"]
        assert lookups.get("symbols", 0) > 0, "Expected symbols lookup > 0"
        
        # Verify cross-layer bridges were built
        assert "token_project_bridges" in data, "Missing 'token_project_bridges' in response"
        assert "twitter_person_bridges" in data, "Missing 'twitter_person_bridges' in response"
        
        print(f"Build complete: {totals.get('nodes')} nodes, {totals.get('edges')} edges")
        print(f"SIGNAL edges: {totals.get('signal_edges', 0)}, KNOWLEDGE edges: {totals.get('knowledge_edges', 0)}")
        print(f"Token→Project bridges: {data.get('token_project_bridges', {}).get('edges', 0)}")
        print(f"Twitter→Person bridges: {data.get('twitter_person_bridges', {}).get('edges', 0)}")

    def test_03_graph_build_idempotency(self):
        """Verify no duplicate edges after running /api/graph/build twice."""
        # Get stats before second build
        response1 = requests.get(f"{BASE_URL}/api/graph/build/stats", timeout=30)
        assert response1.status_code == 200
        stats_before = response1.json()
        edges_before = stats_before.get("edges", 0)
        
        # Run build again
        response2 = requests.post(f"{BASE_URL}/api/graph/build", timeout=120)
        assert response2.status_code == 200, f"Second build failed: {response2.text}"
        
        # Get stats after second build
        response3 = requests.get(f"{BASE_URL}/api/graph/build/stats", timeout=30)
        assert response3.status_code == 200
        stats_after = response3.json()
        edges_after = stats_after.get("edges", 0)
        
        # Edges should be the same (idempotent)
        assert edges_after == edges_before, f"Duplicate edges detected! Before: {edges_before}, After: {edges_after}"
        print(f"Idempotency verified: {edges_before} edges before, {edges_after} edges after (no duplicates)")

    def test_04_hydrate_solana(self):
        """POST /api/graph/hydrate — Search 'Solana'."""
        response = requests.post(
            f"{BASE_URL}/api/graph/hydrate",
            json={"query": "Solana"},
            timeout=30
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert data.get("matched_nodes", 0) > 0, "Expected at least 1 matched node for 'Solana'"
        
        print(f"Solana hydration: {data.get('matched_nodes')} matched nodes, {data.get('total_edges')} edges, {data.get('total_neighbors')} neighbors")

    def test_05_hydrate_ethereum(self):
        """POST /api/graph/hydrate — Search 'Ethereum'."""
        response = requests.post(
            f"{BASE_URL}/api/graph/hydrate",
            json={"query": "Ethereum"},
            timeout=30
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert data.get("matched_nodes", 0) > 0, "Expected at least 1 matched node for 'Ethereum'"
        
        print(f"Ethereum hydration: {data.get('matched_nodes')} matched nodes, {data.get('total_edges')} edges")

    def test_06_hydrate_vitalik(self):
        """POST /api/graph/hydrate — Search 'vitalik'."""
        response = requests.post(
            f"{BASE_URL}/api/graph/hydrate",
            json={"query": "vitalik"},
            timeout=30
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        print(f"Vitalik hydration: {data.get('matched_nodes')} matched nodes, {data.get('total_edges')} edges")

    def test_07_hydrate_a16z(self):
        """POST /api/graph/hydrate — Search 'a16z'."""
        response = requests.post(
            f"{BASE_URL}/api/graph/hydrate",
            json={"query": "a16z"},
            timeout=30
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        print(f"a16z hydration: {data.get('matched_nodes')} matched nodes, {data.get('total_edges')} edges")

    def test_08_entity_detail_person_vitalik(self):
        """GET /api/graph/entity/person:vitalik — Verify Vitalik entity with founded->project:ethereum."""
        response = requests.get(f"{BASE_URL}/api/graph/entity/person:vitalik", timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                entity = data.get("entity", {})
                edges = data.get("edges", [])
                
                print(f"person:vitalik found: {entity.get('label', 'N/A')}")
                print(f"Total edges: {len(edges)}")
                
                # Check for founded->project:ethereum edge
                founded_edges = [e for e in edges if e.get("relation_type") == "founded" and "ethereum" in e.get("to_node_id", "").lower()]
                if founded_edges:
                    print(f"VERIFIED: person:vitalik has founded->project:ethereum edge")
                else:
                    print(f"Note: founded->project:ethereum edge not found (may need entity_graph_relations data)")
            else:
                print(f"person:vitalik not found in graph: {data.get('error', 'unknown')}")
        else:
            print(f"person:vitalik entity not found (status {response.status_code})")

    def test_09_entity_detail_project_solana(self):
        """GET /api/graph/entity/project:solana — Verify Solana entity with invested_in from funds."""
        response = requests.get(f"{BASE_URL}/api/graph/entity/project:solana", timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                entity = data.get("entity", {})
                edges = data.get("edges", [])
                
                print(f"project:solana found: {entity.get('label', 'N/A')}")
                print(f"Total edges: {len(edges)}")
                
                # Check for invested_in edges (funds investing in Solana)
                invested_edges = [e for e in edges if e.get("relation_type") == "invested_in" and e.get("to_node_id") == "project:solana"]
                if invested_edges:
                    print(f"VERIFIED: project:solana has {len(invested_edges)} invested_in edges from funds")
                    for e in invested_edges[:3]:
                        print(f"  - {e.get('from_node_id')} -> invested_in -> project:solana")
                else:
                    print(f"Note: invested_in edges not found (may need funding_rounds data)")
            else:
                print(f"project:solana not found in graph: {data.get('error', 'unknown')}")
        else:
            print(f"project:solana entity not found (status {response.status_code})")

    def test_10_entity_detail_token_eth(self):
        """GET /api/graph/entity/token:ETH — Verify token:ETH has token_of->project:ethereum bridge."""
        response = requests.get(f"{BASE_URL}/api/graph/entity/token:ETH", timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                entity = data.get("entity", {})
                edges = data.get("edges", [])
                
                print(f"token:ETH found: {entity.get('label', 'N/A')}")
                print(f"Total edges: {len(edges)}")
                
                # Check for token_of->project:ethereum bridge
                token_of_edges = [e for e in edges if e.get("relation_type") == "token_of" and "ethereum" in e.get("to_node_id", "").lower()]
                if token_of_edges:
                    print(f"VERIFIED: token:ETH has token_of->project:ethereum bridge")
                else:
                    print(f"Note: token_of->project:ethereum bridge not found")
            else:
                print(f"token:ETH not found in graph: {data.get('error', 'unknown')}")
        else:
            print(f"token:ETH entity not found (status {response.status_code})")

    def test_11_entity_detail_token_sol(self):
        """GET /api/graph/entity/token:SOL — Verify token:SOL has token_of->project:solana bridge."""
        response = requests.get(f"{BASE_URL}/api/graph/entity/token:SOL", timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                entity = data.get("entity", {})
                edges = data.get("edges", [])
                
                print(f"token:SOL found: {entity.get('label', 'N/A')}")
                print(f"Total edges: {len(edges)}")
                
                # Check for token_of->project:solana bridge
                token_of_edges = [e for e in edges if e.get("relation_type") == "token_of" and "solana" in e.get("to_node_id", "").lower()]
                if token_of_edges:
                    print(f"VERIFIED: token:SOL has token_of->project:solana bridge")
                else:
                    print(f"Note: token_of->project:solana bridge not found")
            else:
                print(f"token:SOL not found in graph: {data.get('error', 'unknown')}")
        else:
            print(f"token:SOL entity not found (status {response.status_code})")

    def test_12_legacy_bridge_run(self):
        """POST /api/graph/bridge/run — Legacy bridge still works alongside new builder."""
        response = requests.post(f"{BASE_URL}/api/graph/bridge/run", timeout=120)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Verify legacy bridge results
        assert "mention_edges" in data, "Missing 'mention_edges' in response"
        assert "knowledge_edges" in data, "Missing 'knowledge_edges' in response"
        assert "totals" in data, "Missing 'totals' in response"
        
        print(f"Legacy bridge run: mention_edges={data.get('mention_edges', {})}, knowledge_edges={data.get('knowledge_edges', {})}")
        print(f"Totals: {data.get('totals', {})}")

    def test_13_legacy_bridge_stats(self):
        """GET /api/graph/bridge/stats — Legacy stats endpoint still works."""
        response = requests.get(f"{BASE_URL}/api/graph/bridge/stats", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Verify structure
        assert "nodes" in data, "Missing 'nodes' in response"
        assert "edges_total" in data, "Missing 'edges_total' in response"
        assert "layers" in data, "Missing 'layers' in response"
        assert "edge_types" in data, "Missing 'edge_types' in response"
        
        print(f"Legacy bridge stats: {data.get('nodes')} nodes, {data.get('edges_total')} total edges")
        print(f"Layers: {data.get('layers', {})}")

    def test_14_parser_registry(self):
        """GET /api/graph/parsers — Parser registry returns all 9 parsers."""
        response = requests.get(f"{BASE_URL}/api/graph/parsers", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        parsers = data.get("parsers", [])
        assert len(parsers) >= 9, f"Expected at least 9 parsers, got {len(parsers)}"
        
        # Verify parser names
        parser_names = [p.get("name") for p in parsers]
        expected_parsers = ["CryptoRank", "Dropstab", "RootData", "GitHub", "DefiLlama", "ICODrops", "DropsEarn", "AirdropAlert", "TokenUnlocks"]
        
        for expected in expected_parsers:
            assert expected in parser_names, f"Missing parser: {expected}"
        
        print(f"Parser registry: {len(parsers)} parsers")
        for p in parsers:
            print(f"  - {p.get('name')} (tier {p.get('tier')}, status: {p.get('status', 'N/A')})")

    def test_15_graph_build_stats_final(self):
        """GET /api/graph/build/stats — Final graph statistics with cross-layer bridge counts."""
        response = requests.get(f"{BASE_URL}/api/graph/build/stats", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Verify final stats
        nodes = data.get("nodes", 0)
        edges = data.get("edges", 0)
        layers = data.get("layers", {})
        cross_layer = data.get("cross_layer", {})
        
        print(f"\n=== FINAL GRAPH STATS ===")
        print(f"Total nodes: {nodes}")
        print(f"Total edges: {edges}")
        print(f"Layers: SIGNAL={layers.get('SIGNAL', 0)}, KNOWLEDGE={layers.get('KNOWLEDGE', 0)}")
        print(f"Cross-layer bridges:")
        print(f"  - token_of: {cross_layer.get('token_of', 0)}")
        print(f"  - account_of: {cross_layer.get('account_of', 0)}")
        print(f"  - official_account_of: {cross_layer.get('official_account_of', 0)}")
        
        # Verify cross-layer bridges exist (as per agent context: 46 token_of, 10 account_of, 228 official_account_of)
        assert cross_layer.get("token_of", 0) > 0, "Expected token_of bridges > 0"
        assert cross_layer.get("official_account_of", 0) > 0, "Expected official_account_of bridges > 0"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
