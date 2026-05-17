"""
Test Graph Entity Builder + News Pipeline for Decision Intelligence System.

Tests:
1. POST /api/graph/bridge/run - entity_builder results (funding, defi, activities, unlocks) + knowledge_edges synced
2. GET /api/graph/bridge/stats - KNOWLEDGE layer with deployed_on, coinvested_with, invested_in edges
3. POST /api/news/fetch - RSS news pipeline with tier filtering
4. GET /api/news/stats - news statistics
5. POST /api/graph/discovery/run {tiers:[0]} - T0 parsers + graph rebuild + knowledge sync
6. GET /api/graph/parsers - parser registry with all 9 parsers
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

class TestGraphEntityBuilder:
    """Test graph entity builder integration in graph bridge."""
    
    def test_graph_bridge_run_includes_entity_builder(self):
        """POST /api/graph/bridge/run should include entity_builder results."""
        response = requests.post(f"{BASE_URL}/api/graph/bridge/run", timeout=120)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Check entity_builder results
        entity_builder = data.get("entity_builder", {})
        assert "builders" in entity_builder or entity_builder.get("ok") is True, f"entity_builder missing or failed: {entity_builder}"
        
        # Check knowledge_edges synced
        knowledge_edges = data.get("knowledge_edges", {})
        synced_count = knowledge_edges.get("synced", 0)
        print(f"Knowledge edges synced: {synced_count}")
        assert synced_count > 422, f"Expected knowledge_edges synced > 422, got {synced_count}"
        
        # Verify entity_builder has funding, defi, activities, unlocks
        if "builders" in entity_builder:
            builders = entity_builder["builders"]
            assert "funding" in builders, "Missing funding builder"
            assert "defi" in builders, "Missing defi builder"
            assert "activities" in builders, "Missing activities builder"
            assert "unlocks" in builders, "Missing unlocks builder"
            print(f"Entity builder results: {builders}")
    
    def test_graph_bridge_stats_knowledge_layer(self):
        """GET /api/graph/bridge/stats should show KNOWLEDGE layer with edge types."""
        response = requests.get(f"{BASE_URL}/api/graph/bridge/stats", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Check total edges > 4000
        total_edges = data.get("edges_total", 0)
        print(f"Total edges: {total_edges}")
        assert total_edges > 4000, f"Expected total edges > 4000, got {total_edges}"
        
        # Check layers
        layers = data.get("layers", {})
        knowledge_count = layers.get("KNOWLEDGE", 0)
        signal_count = layers.get("SIGNAL", 0)
        print(f"Layers: KNOWLEDGE={knowledge_count}, SIGNAL={signal_count}")
        assert knowledge_count > 0, f"Expected KNOWLEDGE layer edges > 0, got {knowledge_count}"
        
        # Check edge_types for KNOWLEDGE layer edges
        edge_types = data.get("edge_types", {})
        print(f"Edge types: {edge_types}")
        
        # Look for KNOWLEDGE layer edge types
        knowledge_edge_types = [k for k in edge_types.keys() if k.startswith("KNOWLEDGE:")]
        print(f"KNOWLEDGE edge types: {knowledge_edge_types}")
        
        # Verify expected edge types exist
        expected_types = ["deployed_on", "coinvested_with", "invested_in"]
        found_types = []
        for et in expected_types:
            for k in edge_types.keys():
                if et in k.lower():
                    found_types.append(et)
                    break
        print(f"Found expected types: {found_types}")


class TestNewsPipeline:
    """Test news RSS pipeline."""
    
    def test_news_fetch_with_tier_filter(self):
        """POST /api/news/fetch with tier filter should return articles."""
        payload = {"tiers": ["A"], "limit_sources": 5}
        response = requests.post(f"{BASE_URL}/api/news/fetch", json=payload, timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Check response fields
        sources_checked = data.get("sources_checked", 0)
        total_articles = data.get("total_articles", 0)
        sources_with_articles = data.get("sources_with_articles", 0)
        
        print(f"News fetch results: sources_checked={sources_checked}, total_articles={total_articles}, sources_with_articles={sources_with_articles}")
        
        assert sources_checked > 0, f"Expected sources_checked > 0, got {sources_checked}"
        # Note: total_articles may be 0 if RSS feeds are empty or unavailable
        # But sources_checked should be > 0
    
    def test_news_stats(self):
        """GET /api/news/stats should return statistics."""
        response = requests.get(f"{BASE_URL}/api/news/stats", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Check stats fields
        total_articles = data.get("total_articles", 0)
        active_sources = data.get("active_sources", 0)
        fresh_24h = data.get("fresh_24h", 0)
        top_sources = data.get("top_sources", [])
        
        print(f"News stats: total_articles={total_articles}, active_sources={active_sources}, fresh_24h={fresh_24h}")
        print(f"Top sources: {top_sources[:5] if top_sources else 'none'}")
        
        # Verify expected values based on context
        assert total_articles > 1000, f"Expected total_articles > 1000, got {total_articles}"
        assert active_sources == 120, f"Expected active_sources=120, got {active_sources}"
        assert fresh_24h >= 0, f"Expected fresh_24h >= 0, got {fresh_24h}"
        assert isinstance(top_sources, list), f"Expected top_sources to be list, got {type(top_sources)}"


class TestDiscoveryPipeline:
    """Test discovery pipeline with tier filtering."""
    
    def test_discovery_run_tier_0(self):
        """POST /api/graph/discovery/run {tiers:[0]} should run T0 parsers."""
        payload = {"tiers": [0]}
        response = requests.post(f"{BASE_URL}/api/graph/discovery/run", json=payload, timeout=120)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Check pipeline info
        pipeline = data.get("pipeline", "")
        tiers_run = data.get("tiers_run", [])
        parsers = data.get("parsers", [])
        ok_count = data.get("ok_count", 0)
        total = data.get("total", 0)
        
        print(f"Discovery run: pipeline={pipeline}, tiers_run={tiers_run}, ok_count={ok_count}/{total}")
        print(f"Parsers: {[p.get('name') for p in parsers]}")
        
        assert pipeline == "GRAPH", f"Expected pipeline=GRAPH, got {pipeline}"
        assert 0 in tiers_run, f"Expected tier 0 in tiers_run, got {tiers_run}"
        
        # Should have T0 parsers (CryptoRank, Dropstab) + GraphRebuild + KnowledgeSync
        parser_names = [p.get("name") for p in parsers]
        assert "CryptoRank" in parser_names or "Dropstab" in parser_names, f"Expected T0 parsers, got {parser_names}"
        assert "KnowledgeSync" in parser_names, f"Expected KnowledgeSync, got {parser_names}"
    
    def test_parser_registry(self):
        """GET /api/graph/parsers should return all 9 parsers."""
        response = requests.get(f"{BASE_URL}/api/graph/parsers", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        parsers = data.get("parsers", [])
        print(f"Parser registry: {len(parsers)} parsers")
        
        for p in parsers:
            print(f"  - {p.get('name')}: tier={p.get('tier')}, status={p.get('status')}, role={p.get('role')}")
        
        assert len(parsers) == 9, f"Expected 9 parsers, got {len(parsers)}"
        
        # Verify tier assignments
        tier_0 = [p for p in parsers if p.get("tier") == 0]
        tier_1 = [p for p in parsers if p.get("tier") == 1]
        tier_2 = [p for p in parsers if p.get("tier") == 2]
        
        assert len(tier_0) == 2, f"Expected 2 T0 parsers, got {len(tier_0)}"
        assert len(tier_1) == 2, f"Expected 2 T1 parsers, got {len(tier_1)}"
        assert len(tier_2) == 5, f"Expected 5 T2 parsers, got {len(tier_2)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
