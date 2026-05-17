"""
Intel Admin Health Monitor & Discovery System API Tests
========================================================
Tests for:
- GET /api/intel/admin/health/sources - Source health with real data
- GET /api/graph/health - Graph metrics (nodes, edges, types)
- GET /api/intel/admin/discovery/dashboard - Tier-based discovery data
- GET /api/intel/admin/sources-registry - News sources registry
- GET /api/admin/news/health - News admin health
- GET /api/admin/news/sources - News sources list
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com')


class TestHealthMonitorSources:
    """Health Monitor - /api/intel/admin/health/sources"""
    
    def test_health_sources_returns_200(self):
        """Health sources endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/health/sources")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Health sources endpoint returns 200")
    
    def test_health_sources_has_sources_array(self):
        """Health sources returns sources array"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/health/sources")
        data = response.json()
        assert "sources" in data, "Response missing 'sources' key"
        assert isinstance(data["sources"], list), "sources should be a list"
        print(f"✓ Health sources returns {len(data['sources'])} sources")
    
    def test_health_sources_has_summary(self):
        """Health sources returns summary with stats"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/health/sources")
        data = response.json()
        assert "summary" in data, "Response missing 'summary' key"
        summary = data["summary"]
        assert "total_sources" in summary, "Summary missing total_sources"
        assert "active" in summary, "Summary missing active count"
        assert "degraded" in summary, "Summary missing degraded count"
        assert "paused" in summary, "Summary missing paused count"
        assert "avg_health_score" in summary, "Summary missing avg_health_score"
        print(f"✓ Summary: total={summary['total_sources']}, active={summary['active']}, degraded={summary['degraded']}")
    
    def test_health_sources_source_structure(self):
        """Each source has required fields"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/health/sources")
        data = response.json()
        if data["sources"]:
            source = data["sources"][0]
            required_fields = ["source_id", "source_name", "status", "health_score"]
            for field in required_fields:
                assert field in source, f"Source missing required field: {field}"
            print(f"✓ Source structure valid: {source['source_name']} (status={source['status']})")


class TestGraphHealth:
    """Graph Health - /api/graph/health"""
    
    def test_graph_health_returns_200(self):
        """Graph health endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/graph/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Graph health endpoint returns 200")
    
    def test_graph_health_has_metrics(self):
        """Graph health returns metrics with node/edge counts"""
        response = requests.get(f"{BASE_URL}/api/graph/health")
        data = response.json()
        assert "metrics" in data, "Response missing 'metrics' key"
        metrics = data["metrics"]
        assert "nodes_count" in metrics, "Metrics missing nodes_count"
        assert "edges_count" in metrics, "Metrics missing edges_count"
        print(f"✓ Graph metrics: nodes={metrics['nodes_count']}, edges={metrics['edges_count']}")
    
    def test_graph_health_expected_counts(self):
        """Graph has expected node/edge counts (2601 nodes, 12446 edges)"""
        response = requests.get(f"{BASE_URL}/api/graph/health")
        data = response.json()
        metrics = data["metrics"]
        # Allow some variance but should be close to expected
        assert metrics["nodes_count"] >= 2500, f"Expected ~2601 nodes, got {metrics['nodes_count']}"
        assert metrics["edges_count"] >= 12000, f"Expected ~12446 edges, got {metrics['edges_count']}"
        print(f"✓ Graph counts match expected: nodes={metrics['nodes_count']}, edges={metrics['edges_count']}")
    
    def test_graph_health_has_distribution(self):
        """Graph health returns node_types and edge_types distribution"""
        response = requests.get(f"{BASE_URL}/api/graph/health")
        data = response.json()
        assert "distribution" in data, "Response missing 'distribution' key"
        dist = data["distribution"]
        assert "node_types" in dist, "Distribution missing node_types"
        assert "edge_types" in dist, "Distribution missing edge_types"
        # Check for expected node types
        node_types = dist["node_types"]
        assert "wallet" in node_types, "Missing 'wallet' node type"
        assert "project" in node_types, "Missing 'project' node type"
        print(f"✓ Node types: {list(node_types.keys())[:5]}...")
        print(f"✓ Edge types: {list(dist['edge_types'].keys())[:5]}...")
    
    def test_graph_health_has_duplicate_check(self):
        """Graph health returns duplicate check info"""
        response = requests.get(f"{BASE_URL}/api/graph/health")
        data = response.json()
        assert "duplicate_check" in data, "Response missing 'duplicate_check' key"
        dup = data["duplicate_check"]
        assert "potential_duplicates" in dup, "Missing potential_duplicates count"
        print(f"✓ Duplicate check: {dup['potential_duplicates']} potential duplicates")


class TestDiscoveryDashboard:
    """Discovery System - /api/intel/admin/discovery/dashboard"""
    
    def test_discovery_dashboard_returns_200(self):
        """Discovery dashboard endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/discovery/dashboard")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Discovery dashboard endpoint returns 200")
    
    def test_discovery_dashboard_has_tiers(self):
        """Discovery dashboard returns T1/T2/T3 tiers"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/discovery/dashboard")
        data = response.json()
        assert "tiers" in data, "Response missing 'tiers' key"
        tiers = data["tiers"]
        assert "T1" in tiers, "Missing T1 tier"
        assert "T2" in tiers, "Missing T2 tier"
        assert "T3" in tiers, "Missing T3 tier"
        print(f"✓ Tiers present: T1, T2, T3")
    
    def test_discovery_t1_sources(self):
        """T1 tier has expected sources (CryptoRank, DefiLlama, RootData, Dropstab, ICO Drops)"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/discovery/dashboard")
        data = response.json()
        t1 = data["tiers"]["T1"]
        assert "sources" in t1, "T1 missing sources"
        source_ids = [s["id"] for s in t1["sources"]]
        expected_t1 = ["cryptorank", "defillama", "rootdata", "dropstab", "ico_drops"]
        for expected in expected_t1:
            assert expected in source_ids, f"T1 missing expected source: {expected}"
        print(f"✓ T1 sources: {source_ids}")
    
    def test_discovery_t2_sources(self):
        """T2 tier has expected sources (CoinGecko, CMC, TokenUnlocks, Messari)"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/discovery/dashboard")
        data = response.json()
        t2 = data["tiers"]["T2"]
        source_ids = [s["id"] for s in t2["sources"]]
        expected_t2 = ["coingecko", "coinmarketcap", "token_unlocks", "messari"]
        for expected in expected_t2:
            assert expected in source_ids, f"T2 missing expected source: {expected}"
        print(f"✓ T2 sources: {source_ids}")
    
    def test_discovery_t3_sources(self):
        """T3 tier has expected sources (Twitter, RSS, Funding Rounds)"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/discovery/dashboard")
        data = response.json()
        t3 = data["tiers"]["T3"]
        source_ids = [s["id"] for s in t3["sources"]]
        expected_t3 = ["twitter", "rss_news", "funding_rounds"]
        for expected in expected_t3:
            assert expected in source_ids, f"T3 missing expected source: {expected}"
        print(f"✓ T3 sources: {source_ids}")
    
    def test_discovery_has_graph_stats(self):
        """Discovery dashboard includes graph stats"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/discovery/dashboard")
        data = response.json()
        assert "graph" in data, "Response missing 'graph' key"
        graph = data["graph"]
        assert "nodes" in graph, "Graph missing nodes count"
        assert "edges" in graph, "Graph missing edges count"
        assert "node_types" in graph, "Graph missing node_types"
        assert "edge_types" in graph, "Graph missing edge_types"
        print(f"✓ Graph stats: nodes={graph['nodes']}, edges={graph['edges']}")
    
    def test_discovery_has_scheduler_info(self):
        """Discovery dashboard includes scheduler info"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/discovery/dashboard")
        data = response.json()
        assert "scheduler" in data, "Response missing 'scheduler' key"
        scheduler = data["scheduler"]
        assert "running" in scheduler, "Scheduler missing running status"
        assert "jobs" in scheduler, "Scheduler missing jobs list"
        print(f"✓ Scheduler: running={scheduler['running']}, jobs={len(scheduler['jobs'])}")
    
    def test_discovery_tier_records(self):
        """Each tier has real record counts"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/discovery/dashboard")
        data = response.json()
        for tier_id in ["T1", "T2", "T3"]:
            tier = data["tiers"][tier_id]
            assert "total_records" in tier, f"{tier_id} missing total_records"
            for source in tier["sources"]:
                assert "records" in source, f"Source {source['id']} missing records count"
        print(f"✓ T1 records: {data['tiers']['T1']['total_records']}")
        print(f"✓ T2 records: {data['tiers']['T2']['total_records']}")
        print(f"✓ T3 records: {data['tiers']['T3']['total_records']}")


class TestSourcesRegistry:
    """Sources Registry - /api/intel/admin/sources-registry"""
    
    def test_sources_registry_returns_200(self):
        """Sources registry endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/sources-registry")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Sources registry endpoint returns 200")
    
    def test_sources_registry_has_sources(self):
        """Sources registry returns sources list"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/sources-registry")
        data = response.json()
        assert "sources" in data, "Response missing 'sources' key"
        assert isinstance(data["sources"], list), "sources should be a list"
        print(f"✓ Sources registry returns {len(data['sources'])} sources")
    
    def test_sources_registry_count_210(self):
        """Sources registry has ~210 news sources"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/sources-registry")
        data = response.json()
        # Allow some variance
        assert len(data["sources"]) >= 200, f"Expected ~210 sources, got {len(data['sources'])}"
        print(f"✓ Sources count: {len(data['sources'])} (expected ~210)")
    
    def test_sources_registry_has_stats(self):
        """Sources registry returns stats"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/sources-registry")
        data = response.json()
        assert "stats" in data, "Response missing 'stats' key"
        stats = data["stats"]
        assert "total" in stats, "Stats missing total"
        assert "active" in stats, "Stats missing active"
        print(f"✓ Stats: total={stats['total']}, active={stats['active']}")
    
    def test_sources_registry_filter_by_tier(self):
        """Sources registry supports tier filter"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/sources-registry?tier=A")
        assert response.status_code == 200
        data = response.json()
        # All returned sources should be tier A
        for source in data["sources"]:
            assert source.get("tier") == "A", f"Source {source.get('id')} has tier {source.get('tier')}, expected A"
        print(f"✓ Tier A filter returns {len(data['sources'])} sources")


class TestNewsAdminHealth:
    """News Admin Health - /api/admin/news/health"""
    
    def test_news_health_returns_200(self):
        """News health endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/admin/news/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ News health endpoint returns 200")
    
    def test_news_health_has_data(self):
        """News health returns data object"""
        response = requests.get(f"{BASE_URL}/api/admin/news/health")
        data = response.json()
        assert data.get("ok") == True, "Response ok should be True"
        assert "data" in data, "Response missing 'data' key"
        print("✓ News health returns data object")
    
    def test_news_health_total_sources_210(self):
        """News health shows totalSources=210"""
        response = requests.get(f"{BASE_URL}/api/admin/news/health")
        data = response.json()
        health = data["data"]
        assert "totalSources" in health, "Health missing totalSources"
        assert health["totalSources"] >= 200, f"Expected ~210 sources, got {health['totalSources']}"
        print(f"✓ Total sources: {health['totalSources']} (expected ~210)")
    
    def test_news_health_has_metrics(self):
        """News health has required metrics"""
        response = requests.get(f"{BASE_URL}/api/admin/news/health")
        data = response.json()
        health = data["data"]
        required = ["totalSources", "activeSources", "healthySources", "eventsLast1h", "eventsLast24h"]
        for field in required:
            assert field in health, f"Health missing {field}"
        print(f"✓ Health metrics: active={health['activeSources']}, healthy={health['healthySources']}")
        print(f"✓ Events: 1h={health['eventsLast1h']}, 24h={health['eventsLast24h']}")
    
    def test_news_health_has_top_sources(self):
        """News health includes top sources"""
        response = requests.get(f"{BASE_URL}/api/admin/news/health")
        data = response.json()
        health = data["data"]
        assert "topSources" in health, "Health missing topSources"
        assert isinstance(health["topSources"], list), "topSources should be a list"
        if health["topSources"]:
            top = health["topSources"][0]
            assert "name" in top, "Top source missing name"
            assert "articles" in top, "Top source missing articles count"
        print(f"✓ Top sources: {[s['name'] for s in health['topSources'][:3]]}")


class TestNewsAdminSources:
    """News Admin Sources - /api/admin/news/sources"""
    
    def test_news_sources_returns_200(self):
        """News sources endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/admin/news/sources")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ News sources endpoint returns 200")
    
    def test_news_sources_has_data(self):
        """News sources returns data object"""
        response = requests.get(f"{BASE_URL}/api/admin/news/sources")
        data = response.json()
        assert data.get("ok") == True, "Response ok should be True"
        assert "data" in data, "Response missing 'data' key"
        print("✓ News sources returns data object")
    
    def test_news_sources_has_sources_list(self):
        """News sources returns sources list"""
        response = requests.get(f"{BASE_URL}/api/admin/news/sources")
        data = response.json()
        sources_data = data["data"]
        assert "sources" in sources_data, "Data missing sources"
        assert isinstance(sources_data["sources"], list), "sources should be a list"
        print(f"✓ News sources returns {len(sources_data['sources'])} sources")
    
    def test_news_sources_source_structure(self):
        """Each news source has required fields"""
        response = requests.get(f"{BASE_URL}/api/admin/news/sources")
        data = response.json()
        sources = data["data"]["sources"]
        if sources:
            source = sources[0]
            required = ["id", "name", "tier", "healthy"]
            for field in required:
                assert field in source, f"Source missing required field: {field}"
            print(f"✓ Source structure valid: {source['name']} (tier={source['tier']}, healthy={source['healthy']})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
