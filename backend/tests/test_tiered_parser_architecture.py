"""
Test Tiered Parser Architecture for Decision Intelligence System

Tests:
- POST /api/graph/discovery/run with body {tiers:[0]} - runs only T0 parsers (CryptoRank, Dropstab) + GraphRebuild + KnowledgeSync
- POST /api/graph/discovery/run with body {tiers:[0,1,2]} - runs all 9 parsers + GraphRebuild + KnowledgeSync = 11 items
- GET /api/graph/parsers - returns parser_registry with 9 parsers, each has tier, status, role, last_run, last_duration_sec
- POST /api/graph/bridge/run - still works: builds SIGNAL + KNOWLEDGE edges + node scores
- GET /api/graph/bridge/stats - shows both KNOWLEDGE and SIGNAL layers
- Verify graph has KNOWLEDGE edges (422) and SIGNAL edges (2717)
- Verify parser_registry has correct tier assignments

Tier assignments:
- T0 (Core): CryptoRank, Dropstab
- T1 (Extension): RootData, GitHub
- T2 (Addons): DefiLlama, ICODrops, DropsEarn, AirdropAlert, TokenUnlocks
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Expected tier assignments
EXPECTED_TIERS = {
    "CryptoRank": 0,
    "Dropstab": 0,
    "RootData": 1,
    "GitHub": 1,
    "DefiLlama": 2,
    "ICODrops": 2,
    "DropsEarn": 2,
    "AirdropAlert": 2,
    "TokenUnlocks": 2,
}

T0_PARSERS = ["CryptoRank", "Dropstab"]
T1_PARSERS = ["RootData", "GitHub"]
T2_PARSERS = ["DefiLlama", "ICODrops", "DropsEarn", "AirdropAlert", "TokenUnlocks"]
ALL_PARSERS = T0_PARSERS + T1_PARSERS + T2_PARSERS


class TestParserRegistry:
    """Test GET /api/graph/parsers - parser registry endpoint"""
    
    def test_parser_registry_returns_9_parsers(self):
        """Verify parser registry returns exactly 9 parsers"""
        response = requests.get(f"{BASE_URL}/api/graph/parsers", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") == True, f"Expected ok:true, got {data}"
        
        parsers = data.get("parsers", [])
        print(f"Parser registry returned {len(parsers)} parsers")
        
        # Should have 9 parsers
        assert len(parsers) == 9, f"Expected 9 parsers, got {len(parsers)}: {[p.get('name') for p in parsers]}"
        
    def test_parser_registry_has_required_fields(self):
        """Verify each parser has tier, status, role, last_run, last_duration_sec"""
        response = requests.get(f"{BASE_URL}/api/graph/parsers", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        parsers = data.get("parsers", [])
        
        required_fields = ["name", "tier", "status", "role", "last_run", "last_duration_sec"]
        
        for parser in parsers:
            parser_name = parser.get("name", "UNKNOWN")
            for field in required_fields:
                assert field in parser, f"Parser {parser_name} missing field: {field}"
            print(f"Parser {parser_name}: tier={parser.get('tier')}, status={parser.get('status')}, role={parser.get('role')[:30]}...")
            
    def test_parser_registry_tier_assignments(self):
        """Verify correct tier assignments: T0=CryptoRank,Dropstab; T1=RootData,GitHub; T2=rest"""
        response = requests.get(f"{BASE_URL}/api/graph/parsers", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        parsers = data.get("parsers", [])
        
        parser_tiers = {p.get("name"): p.get("tier") for p in parsers}
        
        # Verify T0 parsers
        for name in T0_PARSERS:
            assert name in parser_tiers, f"T0 parser {name} not found in registry"
            assert parser_tiers[name] == 0, f"Parser {name} should be tier 0, got {parser_tiers[name]}"
            print(f"T0 parser {name}: tier={parser_tiers[name]} ✓")
            
        # Verify T1 parsers
        for name in T1_PARSERS:
            assert name in parser_tiers, f"T1 parser {name} not found in registry"
            assert parser_tiers[name] == 1, f"Parser {name} should be tier 1, got {parser_tiers[name]}"
            print(f"T1 parser {name}: tier={parser_tiers[name]} ✓")
            
        # Verify T2 parsers
        for name in T2_PARSERS:
            assert name in parser_tiers, f"T2 parser {name} not found in registry"
            assert parser_tiers[name] == 2, f"Parser {name} should be tier 2, got {parser_tiers[name]}"
            print(f"T2 parser {name}: tier={parser_tiers[name]} ✓")


class TestDiscoveryRunT0Only:
    """Test POST /api/graph/discovery/run with {tiers:[0]} - T0 parsers only"""
    
    def test_discovery_run_t0_only(self):
        """Run only T0 parsers (CryptoRank, Dropstab) + GraphRebuild + KnowledgeSync"""
        response = requests.post(
            f"{BASE_URL}/api/graph/discovery/run",
            json={"tiers": [0]},
            timeout=120  # T0 only should be fast (~4s)
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") == True, f"Expected ok:true, got {data}"
        
        # Check tiers_run
        tiers_run = data.get("tiers_run", [])
        assert tiers_run == [0], f"Expected tiers_run=[0], got {tiers_run}"
        
        # Check parsers list
        parsers = data.get("parsers", [])
        parser_names = [p.get("name") for p in parsers]
        print(f"T0 run returned {len(parsers)} items: {parser_names}")
        
        # Should have T0 parsers + GraphRebuild + KnowledgeSync = 4 items
        assert len(parsers) == 4, f"Expected 4 items (2 T0 + GraphRebuild + KnowledgeSync), got {len(parsers)}"
        
        # Verify T0 parsers are present
        for name in T0_PARSERS:
            assert name in parser_names, f"T0 parser {name} not in results"
            
        # Verify GraphRebuild and KnowledgeSync
        assert "GraphRebuild" in parser_names, "GraphRebuild not in results"
        assert "KnowledgeSync" in parser_names, "KnowledgeSync not in results"
        
        # Verify T1/T2 parsers are NOT present
        for name in T1_PARSERS + T2_PARSERS:
            assert name not in parser_names, f"T1/T2 parser {name} should not be in T0-only run"
            
        # Check ok_count
        ok_count = data.get("ok_count", 0)
        total = data.get("total", 0)
        print(f"T0 run: {ok_count}/{total} OK, duration={data.get('duration_sec', 0)}s")
        
        # All should be OK
        assert ok_count == total, f"Expected all {total} to be OK, got {ok_count}"


class TestDiscoveryRunAllTiers:
    """Test POST /api/graph/discovery/run with {tiers:[0,1,2]} - all parsers"""
    
    def test_discovery_run_all_tiers(self):
        """Run all 9 parsers + GraphRebuild + KnowledgeSync = 11 items"""
        response = requests.post(
            f"{BASE_URL}/api/graph/discovery/run",
            json={"tiers": [0, 1, 2]},
            timeout=180  # All tiers takes ~30s
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") == True, f"Expected ok:true, got {data}"
        
        # Check tiers_run
        tiers_run = data.get("tiers_run", [])
        assert set(tiers_run) == {0, 1, 2}, f"Expected tiers_run=[0,1,2], got {tiers_run}"
        
        # Check parsers list
        parsers = data.get("parsers", [])
        parser_names = [p.get("name") for p in parsers]
        print(f"All tiers run returned {len(parsers)} items: {parser_names}")
        
        # Should have 9 parsers + GraphRebuild + KnowledgeSync = 11 items
        assert len(parsers) == 11, f"Expected 11 items (9 parsers + GraphRebuild + KnowledgeSync), got {len(parsers)}"
        
        # Verify all parsers are present
        for name in ALL_PARSERS:
            assert name in parser_names, f"Parser {name} not in results"
            
        # Verify GraphRebuild and KnowledgeSync
        assert "GraphRebuild" in parser_names, "GraphRebuild not in results"
        assert "KnowledgeSync" in parser_names, "KnowledgeSync not in results"
        
        # Check ok_count
        ok_count = data.get("ok_count", 0)
        total = data.get("total", 0)
        print(f"All tiers run: {ok_count}/{total} OK, duration={data.get('duration_sec', 0)}s")
        
        # Report individual parser results
        for p in parsers:
            status = "✓" if p.get("ok") else "✗"
            duration = p.get("duration", 0)
            error = p.get("error", "")
            result = str(p.get("result", ""))[:50] if p.get("result") else ""
            print(f"  {status} {p.get('name')}: {duration}s - {result or error}")


class TestGraphBridgeStillWorks:
    """Test POST /api/graph/bridge/run - should still work with new architecture"""
    
    def test_graph_bridge_run(self):
        """Bridge should build SIGNAL + KNOWLEDGE edges + node scores"""
        response = requests.post(
            f"{BASE_URL}/api/graph/bridge/run",
            timeout=120
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") == True, f"Expected ok:true, got {data}"
        
        # Check required result fields
        required_fields = ["knowledge_edges", "mention_edges", "correlation_edges", "alpha_edges", "node_scores", "totals"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
            
        # Log results
        print(f"Bridge run results:")
        print(f"  knowledge_edges: {data.get('knowledge_edges')}")
        print(f"  mention_edges: {data.get('mention_edges')}")
        print(f"  correlation_edges: {data.get('correlation_edges')}")
        print(f"  alpha_edges: {data.get('alpha_edges')}")
        print(f"  node_scores: {data.get('node_scores')}")
        print(f"  totals: {data.get('totals')}")


class TestGraphBridgeStats:
    """Test GET /api/graph/bridge/stats - should show both layers"""
    
    def test_graph_bridge_stats_layers(self):
        """Stats should show both KNOWLEDGE and SIGNAL layers"""
        response = requests.get(f"{BASE_URL}/api/graph/bridge/stats", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") == True, f"Expected ok:true, got {data}"
        
        # Check layers
        layers = data.get("layers", {})
        assert "SIGNAL" in layers, "SIGNAL layer not in stats"
        assert "KNOWLEDGE" in layers, "KNOWLEDGE layer not in stats"
        
        signal_edges = layers.get("SIGNAL", 0)
        knowledge_edges = layers.get("KNOWLEDGE", 0)
        
        print(f"Graph layers:")
        print(f"  SIGNAL: {signal_edges} edges")
        print(f"  KNOWLEDGE: {knowledge_edges} edges")
        print(f"  Total: {data.get('edges_total', 0)} edges")
        print(f"  Nodes: {data.get('nodes', 0)}")
        
        # Verify we have edges in both layers
        assert signal_edges > 0, f"Expected SIGNAL edges > 0, got {signal_edges}"
        assert knowledge_edges > 0, f"Expected KNOWLEDGE edges > 0, got {knowledge_edges}"
        
    def test_graph_bridge_stats_edge_types(self):
        """Stats should show edge types with layer prefix"""
        response = requests.get(f"{BASE_URL}/api/graph/bridge/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        edge_types = data.get("edge_types", {})
        
        print(f"Edge types ({len(edge_types)} types):")
        for edge_type, count in sorted(edge_types.items(), key=lambda x: -x[1]):
            print(f"  {edge_type}: {count}")
            
        # Should have SIGNAL and KNOWLEDGE prefixed edge types
        signal_types = [k for k in edge_types.keys() if k.startswith("SIGNAL:")]
        knowledge_types = [k for k in edge_types.keys() if k.startswith("KNOWLEDGE:")]
        
        assert len(signal_types) > 0, "No SIGNAL edge types found"
        assert len(knowledge_types) > 0, "No KNOWLEDGE edge types found"
        
    def test_graph_bridge_stats_top_scored(self):
        """Stats should include top_scored actors with node_score"""
        response = requests.get(f"{BASE_URL}/api/graph/bridge/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        top_scored = data.get("top_scored", [])
        
        print(f"Top scored actors ({len(top_scored)}):")
        for actor in top_scored[:5]:
            print(f"  {actor.get('actor')}: score={actor.get('node_score')}, role={actor.get('role')}")
            
        # Should have top_scored with node_score field
        if top_scored:
            first = top_scored[0]
            assert "node_score" in first, "top_scored missing node_score field"
            assert "actor" in first, "top_scored missing actor field"


class TestGraphEdgeCounts:
    """Verify graph has expected edge counts"""
    
    def test_knowledge_edges_count(self):
        """Verify KNOWLEDGE layer has ~422 edges"""
        response = requests.get(f"{BASE_URL}/api/graph/bridge/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        layers = data.get("layers", {})
        knowledge_edges = layers.get("KNOWLEDGE", 0)
        
        print(f"KNOWLEDGE edges: {knowledge_edges}")
        
        # Should have around 422 edges (allow some variance)
        assert knowledge_edges >= 400, f"Expected KNOWLEDGE edges >= 400, got {knowledge_edges}"
        
    def test_signal_edges_count(self):
        """Verify SIGNAL layer has ~2717 edges"""
        response = requests.get(f"{BASE_URL}/api/graph/bridge/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        layers = data.get("layers", {})
        signal_edges = layers.get("SIGNAL", 0)
        
        print(f"SIGNAL edges: {signal_edges}")
        
        # Should have around 2717 edges (allow some variance)
        assert signal_edges >= 2500, f"Expected SIGNAL edges >= 2500, got {signal_edges}"


class TestRemovedParsers:
    """Verify CoinGecko, CMC, DappRadar are NOT in parser registry"""
    
    def test_removed_parsers_not_in_registry(self):
        """CoinGecko, CMC, DappRadar should not be in parser registry"""
        response = requests.get(f"{BASE_URL}/api/graph/parsers", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        parsers = data.get("parsers", [])
        parser_names = [p.get("name") for p in parsers]
        
        removed_parsers = ["CoinGecko", "CMC", "CoinMarketCap", "DappRadar"]
        
        for name in removed_parsers:
            assert name not in parser_names, f"Removed parser {name} should not be in registry"
            print(f"Verified {name} is NOT in registry ✓")


class TestDiscoveryRunT1Only:
    """Test POST /api/graph/discovery/run with {tiers:[1]} - T1 parsers only"""
    
    def test_discovery_run_t1_only(self):
        """Run only T1 parsers (RootData, GitHub) + GraphRebuild + KnowledgeSync"""
        response = requests.post(
            f"{BASE_URL}/api/graph/discovery/run",
            json={"tiers": [1]},
            timeout=120
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") == True, f"Expected ok:true, got {data}"
        
        # Check tiers_run
        tiers_run = data.get("tiers_run", [])
        assert tiers_run == [1], f"Expected tiers_run=[1], got {tiers_run}"
        
        # Check parsers list
        parsers = data.get("parsers", [])
        parser_names = [p.get("name") for p in parsers]
        print(f"T1 run returned {len(parsers)} items: {parser_names}")
        
        # Should have T1 parsers + GraphRebuild + KnowledgeSync = 4 items
        assert len(parsers) == 4, f"Expected 4 items (2 T1 + GraphRebuild + KnowledgeSync), got {len(parsers)}"
        
        # Verify T1 parsers are present
        for name in T1_PARSERS:
            assert name in parser_names, f"T1 parser {name} not in results"
            
        # Verify T0/T2 parsers are NOT present
        for name in T0_PARSERS + T2_PARSERS:
            assert name not in parser_names, f"T0/T2 parser {name} should not be in T1-only run"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
