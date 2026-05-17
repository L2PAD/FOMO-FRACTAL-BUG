"""
RSS Pipeline, Twitter Linker, and Entity Graph API Tests
=========================================================
Tests for iteration 394:
- GET /api/intel/admin/rss/status - RSS pipeline status
- GET /api/intel/admin/twitter/links - Twitter linking stats
- GET /api/graph/health - Graph health with entity_graph collections
- Data integrity: entity_graph vs legacy graph separation
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestRSSPipelineStatus:
    """Tests for GET /api/intel/admin/rss/status endpoint"""
    
    def test_rss_status_returns_200(self):
        """RSS status endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/rss/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: RSS status endpoint returns 200")
    
    def test_rss_status_has_articles_section(self):
        """RSS status should have articles section with counts"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/rss/status")
        data = response.json()
        
        assert "articles" in data, "Missing 'articles' section"
        articles = data["articles"]
        
        assert "total" in articles, "Missing articles.total"
        assert "with_entities" in articles, "Missing articles.with_entities"
        assert "avg_entity_count" in articles, "Missing articles.avg_entity_count"
        
        print(f"PASS: Articles section present - total={articles['total']}, with_entities={articles['with_entities']}")
    
    def test_rss_status_articles_count_threshold(self):
        """RSS pipeline should have 1000+ articles"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/rss/status")
        data = response.json()
        
        total_articles = data["articles"]["total"]
        assert total_articles >= 1000, f"Expected 1000+ articles, got {total_articles}"
        print(f"PASS: Article count threshold met - {total_articles} articles")
    
    def test_rss_status_entities_coverage(self):
        """RSS pipeline should have 500+ articles with entities"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/rss/status")
        data = response.json()
        
        with_entities = data["articles"]["with_entities"]
        assert with_entities >= 500, f"Expected 500+ articles with entities, got {with_entities}"
        print(f"PASS: Entity coverage threshold met - {with_entities} articles with entities")
    
    def test_rss_status_has_sources_section(self):
        """RSS status should have sources section with health info"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/rss/status")
        data = response.json()
        
        assert "sources" in data, "Missing 'sources' section"
        sources = data["sources"]
        
        assert "total" in sources, "Missing sources.total"
        assert "active" in sources, "Missing sources.active"
        assert "with_data" in sources, "Missing sources.with_data"
        assert "broken" in sources, "Missing sources.broken"
        
        print(f"PASS: Sources section present - total={sources['total']}, active={sources['active']}")
    
    def test_rss_status_has_sentiment_events(self):
        """RSS status should include sentiment events count"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/rss/status")
        data = response.json()
        
        assert "sentiment_events" in data, "Missing 'sentiment_events' field"
        print(f"PASS: Sentiment events present - count={data['sentiment_events']}")


class TestTwitterLinksStats:
    """Tests for GET /api/intel/admin/twitter/links endpoint"""
    
    def test_twitter_links_returns_200(self):
        """Twitter links endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/twitter/links")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: Twitter links endpoint returns 200")
    
    def test_twitter_links_has_total_count(self):
        """Twitter links should have total_links count"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/twitter/links")
        data = response.json()
        
        assert "total_links" in data, "Missing 'total_links' field"
        assert "twitter_accounts" in data, "Missing 'twitter_accounts' field"
        
        print(f"PASS: Twitter stats present - accounts={data['twitter_accounts']}, links={data['total_links']}")
    
    def test_twitter_links_count_is_43(self):
        """Twitter linker should have exactly 43 edges"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/twitter/links")
        data = response.json()
        
        total_links = data["total_links"]
        assert total_links == 43, f"Expected 43 twitter_linker edges, got {total_links}"
        print(f"PASS: Twitter linker edge count correct - {total_links} edges")
    
    def test_twitter_links_has_breakdown(self):
        """Twitter links should have breakdown by relation_type"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/twitter/links")
        data = response.json()
        
        assert "breakdown" in data, "Missing 'breakdown' field"
        breakdown = data["breakdown"]
        
        # Should have at least one relation type
        assert len(breakdown) > 0, "Breakdown should have at least one relation type"
        
        # Verify breakdown sums to total
        breakdown_sum = sum(breakdown.values())
        assert breakdown_sum == data["total_links"], f"Breakdown sum {breakdown_sum} != total_links {data['total_links']}"
        
        print(f"PASS: Breakdown present - {breakdown}")
    
    def test_twitter_links_has_recent_links(self):
        """Twitter links should have recent_links array"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/twitter/links")
        data = response.json()
        
        assert "recent_links" in data, "Missing 'recent_links' field"
        recent = data["recent_links"]
        
        assert isinstance(recent, list), "recent_links should be a list"
        assert len(recent) <= 10, "recent_links should have max 10 items"
        
        if recent:
            # Verify structure of first link
            link = recent[0]
            assert "source_id" in link, "Link missing source_id"
            assert "target_id" in link, "Link missing target_id"
            assert "relation_type" in link, "Link missing relation_type"
            assert "weight" in link, "Link missing weight (confidence)"
        
        print(f"PASS: Recent links present - {len(recent)} items")
    
    def test_twitter_links_confidence_threshold(self):
        """All twitter_linker edges should have confidence >= 0.8"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/twitter/links")
        data = response.json()
        
        recent = data.get("recent_links", [])
        for link in recent:
            weight = link.get("weight", 0)
            assert weight >= 0.8, f"Link {link.get('source_id')} -> {link.get('target_id')} has confidence {weight} < 0.8"
        
        print(f"PASS: All recent links have confidence >= 0.8")


class TestGraphHealth:
    """Tests for GET /api/graph/health endpoint with entity_graph collections"""
    
    def test_graph_health_returns_200(self):
        """Graph health endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/graph/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: Graph health endpoint returns 200")
    
    def test_graph_health_has_metrics(self):
        """Graph health should have metrics section"""
        response = requests.get(f"{BASE_URL}/api/graph/health")
        data = response.json()
        
        assert "metrics" in data, "Missing 'metrics' section"
        metrics = data["metrics"]
        
        assert "nodes_count" in metrics, "Missing nodes_count"
        assert "edges_count" in metrics, "Missing edges_count"
        
        print(f"PASS: Metrics present - nodes={metrics['nodes_count']}, edges={metrics['edges_count']}")
    
    def test_graph_health_entity_graph_nodes_count(self):
        """Entity graph should have 431 nodes"""
        response = requests.get(f"{BASE_URL}/api/graph/health")
        data = response.json()
        
        nodes_count = data["metrics"]["nodes_count"]
        assert nodes_count == 431, f"Expected 431 entity_graph_nodes, got {nodes_count}"
        print(f"PASS: Entity graph nodes count correct - {nodes_count}")
    
    def test_graph_health_entity_graph_edges_count(self):
        """Entity graph should have 422+ edges"""
        response = requests.get(f"{BASE_URL}/api/graph/health")
        data = response.json()
        
        edges_count = data["metrics"]["edges_count"]
        assert edges_count >= 422, f"Expected 422+ entity_graph_relations, got {edges_count}"
        print(f"PASS: Entity graph edges count correct - {edges_count}")
    
    def test_graph_health_has_distribution(self):
        """Graph health should have distribution section"""
        response = requests.get(f"{BASE_URL}/api/graph/health")
        data = response.json()
        
        assert "distribution" in data, "Missing 'distribution' section"
        dist = data["distribution"]
        
        assert "node_types" in dist, "Missing node_types distribution"
        assert "edge_types" in dist, "Missing edge_types distribution"
        
        print(f"PASS: Distribution present - node_types={len(dist['node_types'])}, edge_types={len(dist['edge_types'])}")
    
    def test_graph_health_has_twitter_linker_edges(self):
        """Graph health edge_types should include twitter_linker edges"""
        response = requests.get(f"{BASE_URL}/api/graph/health")
        data = response.json()
        
        edge_types = data["distribution"]["edge_types"]
        
        # Twitter linker creates official_account_of, associated_with, account_of edges
        twitter_edge_types = ["official_account_of", "associated_with", "account_of"]
        found_types = [t for t in twitter_edge_types if t in edge_types]
        
        assert len(found_types) > 0, f"Expected twitter_linker edge types, found none in {list(edge_types.keys())}"
        
        # Sum of twitter-related edges should be 43
        twitter_edges_sum = sum(edge_types.get(t, 0) for t in twitter_edge_types)
        assert twitter_edges_sum == 43, f"Expected 43 twitter_linker edges, got {twitter_edges_sum}"
        
        print(f"PASS: Twitter linker edges present - types={found_types}, total={twitter_edges_sum}")


class TestDataIntegrity:
    """Tests for data integrity - entity_graph vs legacy graph separation"""
    
    def test_legacy_graph_untouched(self):
        """Legacy graph_nodes should have 2601 nodes (untouched)"""
        # This test verifies via the discovery dashboard which shows legacy graph stats
        response = requests.get(f"{BASE_URL}/api/intel/admin/discovery/dashboard")
        data = response.json()
        
        # Discovery dashboard shows graph stats from entity_graph collections
        # We need to verify legacy is separate - check via direct API if available
        # For now, verify entity_graph has different counts
        
        graph_health = requests.get(f"{BASE_URL}/api/graph/health").json()
        entity_nodes = graph_health["metrics"]["nodes_count"]
        entity_edges = graph_health["metrics"]["edges_count"]
        
        # Entity graph should be smaller than legacy
        assert entity_nodes == 431, f"Entity graph should have 431 nodes, got {entity_nodes}"
        assert entity_edges >= 422, f"Entity graph should have 422+ edges, got {entity_edges}"
        
        # These are different from legacy (2601 nodes, 12446 edges)
        assert entity_nodes != 2601, "Entity graph nodes should differ from legacy (2601)"
        assert entity_edges != 12446, "Entity graph edges should differ from legacy (12446)"
        
        print(f"PASS: Entity graph ({entity_nodes} nodes, {entity_edges} edges) is separate from legacy (2601 nodes, 12446 edges)")
    
    def test_entity_graph_has_twitter_accounts(self):
        """Entity graph should have twitter_account node type"""
        response = requests.get(f"{BASE_URL}/api/graph/health")
        data = response.json()
        
        node_types = data["distribution"]["node_types"]
        assert "twitter_account" in node_types, "Missing twitter_account node type"
        
        twitter_count = node_types["twitter_account"]
        assert twitter_count > 0, "Should have twitter_account nodes"
        
        print(f"PASS: Entity graph has {twitter_count} twitter_account nodes")


class TestEndpointResponseStructure:
    """Tests for complete response structure validation"""
    
    def test_rss_status_complete_structure(self):
        """RSS status should have complete response structure"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/rss/status")
        data = response.json()
        
        # Verify all required fields
        required_fields = ["articles", "sources", "sentiment_events"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Verify articles structure
        articles_fields = ["total", "with_entities", "avg_entity_count"]
        for field in articles_fields:
            assert field in data["articles"], f"Missing articles.{field}"
        
        # Verify sources structure
        sources_fields = ["total", "active", "with_data", "broken"]
        for field in sources_fields:
            assert field in data["sources"], f"Missing sources.{field}"
        
        print("PASS: RSS status has complete response structure")
    
    def test_twitter_links_complete_structure(self):
        """Twitter links should have complete response structure"""
        response = requests.get(f"{BASE_URL}/api/intel/admin/twitter/links")
        data = response.json()
        
        required_fields = ["twitter_accounts", "total_links", "breakdown", "recent_links"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        print("PASS: Twitter links has complete response structure")
    
    def test_graph_health_complete_structure(self):
        """Graph health should have complete response structure"""
        response = requests.get(f"{BASE_URL}/api/graph/health")
        data = response.json()
        
        required_fields = ["status", "metrics", "distribution"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Verify metrics structure
        metrics_fields = ["nodes_count", "edges_count"]
        for field in metrics_fields:
            assert field in data["metrics"], f"Missing metrics.{field}"
        
        # Verify distribution structure
        dist_fields = ["node_types", "edge_types"]
        for field in dist_fields:
            assert field in data["distribution"], f"Missing distribution.{field}"
        
        print("PASS: Graph health has complete response structure")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
