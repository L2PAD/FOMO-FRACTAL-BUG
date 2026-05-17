"""
News Intelligence Layer API Tests
=================================
Tests for Task 3 - News Intelligence Layer (minimal)
- Clustering, scoring, breaking detection, and public API
- Pure algorithmic approach: entity extraction + Jaccard similarity clustering
- Importance scoring (tier * sources * recency * eventType)
- Breaking detection (3+ sources AND age < 30min)

Endpoints tested:
- GET /api/news/feed - Clustered, ranked news feed with meta
- GET /api/news/feed?asset=BTC - Filter by asset
- GET /api/news/feed?eventType=etf - Filter by event type
- GET /api/news/breaking - Breaking news only (2h window)
- GET /api/news/asset/:symbol - Asset-specific clusters
- GET /api/news/trends - Event type distribution, importance distribution
- GET /api/news/stats - Admin clustering stats
- GET /api/news/event/:id - Single cluster detail
- GET /api/admin/news/sources - Existing admin endpoint
- GET /api/admin/news/health - Existing admin endpoint
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestNewsFeedEndpoint:
    """Tests for GET /api/news/feed - main clustered news feed"""
    
    def test_feed_returns_200(self):
        """Feed endpoint returns 200 OK"""
        response = requests.get(f"{BASE_URL}/api/news/feed")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: GET /api/news/feed returns 200")
    
    def test_feed_response_structure(self):
        """Feed response has correct top-level structure"""
        response = requests.get(f"{BASE_URL}/api/news/feed")
        data = response.json()
        
        assert data.get('ok') == True, "Response should have ok=true"
        assert 'data' in data, "Response should have data field"
        assert 'clusters' in data['data'], "Data should have clusters array"
        assert 'meta' in data['data'], "Data should have meta object"
        print("PASS: Feed response has correct structure (ok, data, clusters, meta)")
    
    def test_feed_meta_fields(self):
        """Feed meta contains required fields"""
        response = requests.get(f"{BASE_URL}/api/news/feed")
        meta = response.json()['data']['meta']
        
        required_fields = ['totalRawEvents', 'totalClusters', 'breakingCount', 'timeRangeHours', 'generatedAt']
        for field in required_fields:
            assert field in meta, f"Meta should have {field}"
        
        assert isinstance(meta['totalRawEvents'], int), "totalRawEvents should be int"
        assert isinstance(meta['totalClusters'], int), "totalClusters should be int"
        assert isinstance(meta['breakingCount'], int), "breakingCount should be int"
        print(f"PASS: Feed meta has all required fields - totalRawEvents={meta['totalRawEvents']}, totalClusters={meta['totalClusters']}, breakingCount={meta['breakingCount']}")
    
    def test_cluster_structure(self):
        """Each cluster has correct structure"""
        response = requests.get(f"{BASE_URL}/api/news/feed")
        clusters = response.json()['data']['clusters']
        
        if len(clusters) == 0:
            pytest.skip("No clusters available to test structure")
        
        cluster = clusters[0]
        required_fields = [
            'clusterId', 'title', 'eventType', 'primaryAsset', 'assets',
            'importance', 'isBreaking', 'sourcesCount', 'sources',
            'firstSeenAt', 'lastSeenAt', 'events', 'sentimentHint'
        ]
        
        for field in required_fields:
            assert field in cluster, f"Cluster should have {field}"
        
        # Type checks
        assert isinstance(cluster['clusterId'], str), "clusterId should be string"
        assert isinstance(cluster['title'], str), "title should be string"
        assert isinstance(cluster['eventType'], str), "eventType should be string"
        assert isinstance(cluster['assets'], list), "assets should be list"
        assert isinstance(cluster['importance'], (int, float)), "importance should be number"
        assert isinstance(cluster['isBreaking'], bool), "isBreaking should be boolean"
        assert isinstance(cluster['sourcesCount'], int), "sourcesCount should be int"
        assert isinstance(cluster['sources'], list), "sources should be list"
        assert isinstance(cluster['events'], list), "events should be list"
        
        print(f"PASS: Cluster structure is correct - clusterId={cluster['clusterId'][:8]}..., eventType={cluster['eventType']}")
    
    def test_cluster_event_structure(self):
        """Each event within a cluster has correct structure"""
        response = requests.get(f"{BASE_URL}/api/news/feed")
        clusters = response.json()['data']['clusters']
        
        if len(clusters) == 0:
            pytest.skip("No clusters available")
        
        # Find a cluster with events
        cluster = clusters[0]
        if len(cluster['events']) == 0:
            pytest.skip("No events in cluster")
        
        event = cluster['events'][0]
        required_fields = ['externalId', 'title', 'publisher', 'tier', 'publishedAt']
        
        for field in required_fields:
            assert field in event, f"Event should have {field}"
        
        print(f"PASS: Event structure is correct - publisher={event['publisher']}, tier={event['tier']}")
    
    def test_importance_scores_in_range(self):
        """All importance scores are between 0 and 1"""
        response = requests.get(f"{BASE_URL}/api/news/feed")
        clusters = response.json()['data']['clusters']
        
        for cluster in clusters:
            importance = cluster['importance']
            assert 0 <= importance <= 1, f"Importance {importance} should be between 0 and 1"
        
        print(f"PASS: All {len(clusters)} clusters have importance scores in [0, 1] range")


class TestNewsFeedFilters:
    """Tests for feed filtering by asset and eventType"""
    
    def test_filter_by_asset_btc(self):
        """Filter feed by asset=BTC"""
        response = requests.get(f"{BASE_URL}/api/news/feed?asset=BTC")
        assert response.status_code == 200
        
        data = response.json()['data']
        clusters = data['clusters']
        
        # All clusters should have BTC in assets or primaryAsset
        for cluster in clusters:
            has_btc = 'BTC' in cluster['assets'] or cluster['primaryAsset'] == 'BTC'
            assert has_btc, f"Cluster {cluster['clusterId']} should have BTC"
        
        print(f"PASS: GET /api/news/feed?asset=BTC returns {len(clusters)} BTC clusters")
    
    def test_filter_by_asset_eth(self):
        """Filter feed by asset=ETH"""
        response = requests.get(f"{BASE_URL}/api/news/feed?asset=ETH")
        assert response.status_code == 200
        
        data = response.json()['data']
        clusters = data['clusters']
        
        for cluster in clusters:
            has_eth = 'ETH' in cluster['assets'] or cluster['primaryAsset'] == 'ETH'
            assert has_eth, f"Cluster {cluster['clusterId']} should have ETH"
        
        print(f"PASS: GET /api/news/feed?asset=ETH returns {len(clusters)} ETH clusters")
    
    def test_filter_by_event_type_etf(self):
        """Filter feed by eventType=etf"""
        response = requests.get(f"{BASE_URL}/api/news/feed?eventType=etf")
        assert response.status_code == 200
        
        data = response.json()['data']
        clusters = data['clusters']
        
        for cluster in clusters:
            assert cluster['eventType'] == 'etf', f"Cluster should have eventType=etf, got {cluster['eventType']}"
        
        print(f"PASS: GET /api/news/feed?eventType=etf returns {len(clusters)} ETF clusters")
    
    def test_filter_by_event_type_regulation(self):
        """Filter feed by eventType=regulation"""
        response = requests.get(f"{BASE_URL}/api/news/feed?eventType=regulation")
        assert response.status_code == 200
        
        data = response.json()['data']
        clusters = data['clusters']
        
        for cluster in clusters:
            assert cluster['eventType'] == 'regulation', f"Cluster should have eventType=regulation"
        
        print(f"PASS: GET /api/news/feed?eventType=regulation returns {len(clusters)} regulation clusters")


class TestBreakingNewsEndpoint:
    """Tests for GET /api/news/breaking - breaking news only"""
    
    def test_breaking_returns_200(self):
        """Breaking endpoint returns 200 OK"""
        response = requests.get(f"{BASE_URL}/api/news/breaking")
        assert response.status_code == 200
        print("PASS: GET /api/news/breaking returns 200")
    
    def test_breaking_response_structure(self):
        """Breaking response has correct structure"""
        response = requests.get(f"{BASE_URL}/api/news/breaking")
        data = response.json()
        
        assert data.get('ok') == True
        assert 'data' in data
        assert 'clusters' in data['data']
        assert 'meta' in data['data']
        print("PASS: Breaking response has correct structure")
    
    def test_breaking_uses_2h_window(self):
        """Breaking endpoint uses 2h time window"""
        response = requests.get(f"{BASE_URL}/api/news/breaking")
        meta = response.json()['data']['meta']
        
        assert meta['timeRangeHours'] == 2, f"Breaking should use 2h window, got {meta['timeRangeHours']}"
        print("PASS: Breaking endpoint uses 2h time window")
    
    def test_breaking_clusters_are_breaking(self):
        """All clusters from breaking endpoint should have isBreaking=true"""
        response = requests.get(f"{BASE_URL}/api/news/breaking")
        clusters = response.json()['data']['clusters']
        
        # Note: May return 0 clusters if no breaking news
        for cluster in clusters:
            assert cluster['isBreaking'] == True, f"Cluster {cluster['clusterId']} should be breaking"
        
        print(f"PASS: All {len(clusters)} breaking clusters have isBreaking=true (may be 0 if no recent multi-source news)")


class TestAssetEndpoints:
    """Tests for GET /api/news/asset/:symbol"""
    
    def test_asset_btc_returns_200(self):
        """Asset BTC endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/news/asset/BTC")
        assert response.status_code == 200
        print("PASS: GET /api/news/asset/BTC returns 200")
    
    def test_asset_btc_filters_correctly(self):
        """Asset BTC endpoint returns only BTC clusters"""
        response = requests.get(f"{BASE_URL}/api/news/asset/BTC")
        data = response.json()['data']
        clusters = data['clusters']
        
        for cluster in clusters:
            has_btc = 'BTC' in cluster['assets'] or cluster['primaryAsset'] == 'BTC'
            assert has_btc, f"Cluster should have BTC"
        
        print(f"PASS: GET /api/news/asset/BTC returns {len(clusters)} BTC-specific clusters")
    
    def test_asset_eth_returns_200(self):
        """Asset ETH endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/news/asset/ETH")
        assert response.status_code == 200
        print("PASS: GET /api/news/asset/ETH returns 200")
    
    def test_asset_eth_filters_correctly(self):
        """Asset ETH endpoint returns only ETH clusters"""
        response = requests.get(f"{BASE_URL}/api/news/asset/ETH")
        data = response.json()['data']
        clusters = data['clusters']
        
        for cluster in clusters:
            has_eth = 'ETH' in cluster['assets'] or cluster['primaryAsset'] == 'ETH'
            assert has_eth, f"Cluster should have ETH"
        
        print(f"PASS: GET /api/news/asset/ETH returns {len(clusters)} ETH-specific clusters")
    
    def test_asset_case_insensitive(self):
        """Asset endpoint is case insensitive"""
        response_upper = requests.get(f"{BASE_URL}/api/news/asset/BTC")
        response_lower = requests.get(f"{BASE_URL}/api/news/asset/btc")
        
        assert response_upper.status_code == 200
        assert response_lower.status_code == 200
        
        # Both should return same number of clusters
        clusters_upper = response_upper.json()['data']['clusters']
        clusters_lower = response_lower.json()['data']['clusters']
        
        assert len(clusters_upper) == len(clusters_lower), "Case should not affect results"
        print("PASS: Asset endpoint is case insensitive")


class TestTrendsEndpoint:
    """Tests for GET /api/news/trends"""
    
    def test_trends_returns_200(self):
        """Trends endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/news/trends")
        assert response.status_code == 200
        print("PASS: GET /api/news/trends returns 200")
    
    def test_trends_response_structure(self):
        """Trends response has correct structure"""
        response = requests.get(f"{BASE_URL}/api/news/trends")
        data = response.json()
        
        assert data.get('ok') == True
        assert 'data' in data
        
        trends = data['data']
        required_fields = ['eventTypes', 'importance', 'clustering', 'breaking']
        
        for field in required_fields:
            assert field in trends, f"Trends should have {field}"
        
        print("PASS: Trends response has correct structure")
    
    def test_trends_event_types_distribution(self):
        """Trends contains event type distribution"""
        response = requests.get(f"{BASE_URL}/api/news/trends")
        event_types = response.json()['data']['eventTypes']
        
        assert isinstance(event_types, dict), "eventTypes should be dict"
        
        # Should have some event types
        print(f"PASS: Event type distribution: {event_types}")
    
    def test_trends_importance_distribution(self):
        """Trends contains importance distribution"""
        response = requests.get(f"{BASE_URL}/api/news/trends")
        importance = response.json()['data']['importance']
        
        assert 'high' in importance, "Should have high importance count"
        assert 'medium' in importance, "Should have medium importance count"
        assert 'low' in importance, "Should have low importance count"
        
        print(f"PASS: Importance distribution: high={importance['high']}, medium={importance['medium']}, low={importance['low']}")
    
    def test_trends_clustering_stats(self):
        """Trends contains clustering stats"""
        response = requests.get(f"{BASE_URL}/api/news/trends")
        clustering = response.json()['data']['clustering']
        
        required_fields = ['totalRaw', 'totalClusters', 'avgClusterSize', 'singleSource', 'multiSource']
        for field in required_fields:
            assert field in clustering, f"Clustering should have {field}"
        
        print(f"PASS: Clustering stats: totalRaw={clustering['totalRaw']}, totalClusters={clustering['totalClusters']}, multiSource={clustering['multiSource']}")


class TestStatsEndpoint:
    """Tests for GET /api/news/stats - admin clustering stats"""
    
    def test_stats_returns_200(self):
        """Stats endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/news/stats")
        assert response.status_code == 200
        print("PASS: GET /api/news/stats returns 200")
    
    def test_stats_response_structure(self):
        """Stats response has correct structure"""
        response = requests.get(f"{BASE_URL}/api/news/stats")
        data = response.json()
        
        assert data.get('ok') == True
        assert 'data' in data
        
        stats = data['data']
        required_fields = [
            'totalRawNews', 'totalClusters', 'avgClusterSize',
            'singleSourceClusters', 'multiSourceClusters', 'breakingCount',
            'eventTypeDistribution', 'importanceDistribution'
        ]
        
        for field in required_fields:
            assert field in stats, f"Stats should have {field}"
        
        print("PASS: Stats response has all required fields")
    
    def test_stats_values_consistent(self):
        """Stats values are internally consistent"""
        response = requests.get(f"{BASE_URL}/api/news/stats")
        stats = response.json()['data']
        
        # Single + multi should equal total
        total = stats['singleSourceClusters'] + stats['multiSourceClusters']
        assert total == stats['totalClusters'], f"Single({stats['singleSourceClusters']}) + Multi({stats['multiSourceClusters']}) should equal Total({stats['totalClusters']})"
        
        # Importance distribution should sum to total clusters
        imp = stats['importanceDistribution']
        imp_total = imp['high'] + imp['medium'] + imp['low']
        assert imp_total == stats['totalClusters'], f"Importance distribution sum should equal total clusters"
        
        print(f"PASS: Stats values are consistent - {stats['totalClusters']} clusters ({stats['singleSourceClusters']} single, {stats['multiSourceClusters']} multi)")


class TestEventDetailEndpoint:
    """Tests for GET /api/news/event/:id - single cluster detail"""
    
    def test_event_with_valid_id(self):
        """Event endpoint returns cluster for valid ID"""
        # First get a valid cluster ID from feed
        feed_response = requests.get(f"{BASE_URL}/api/news/feed")
        clusters = feed_response.json()['data']['clusters']
        
        if len(clusters) == 0:
            pytest.skip("No clusters available to test")
        
        cluster_id = clusters[0]['clusterId']
        
        response = requests.get(f"{BASE_URL}/api/news/event/{cluster_id}")
        assert response.status_code == 200, f"Expected 200 for valid cluster ID, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') == True
        assert 'data' in data
        assert data['data']['clusterId'] == cluster_id
        
        print(f"PASS: GET /api/news/event/{cluster_id} returns correct cluster")
    
    def test_event_with_invalid_id(self):
        """Event endpoint returns 404 for invalid ID"""
        response = requests.get(f"{BASE_URL}/api/news/event/invalid_cluster_id_12345")
        assert response.status_code == 404, f"Expected 404 for invalid ID, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') == False
        assert 'error' in data
        
        print("PASS: GET /api/news/event/invalid_id returns 404")


class TestMultiSourceClusters:
    """Tests for multi-source clustering"""
    
    def test_multi_source_clusters_exist(self):
        """At least 2 clusters have sourcesCount >= 2"""
        response = requests.get(f"{BASE_URL}/api/news/feed?limit=50")
        clusters = response.json()['data']['clusters']
        
        multi_source = [c for c in clusters if c['sourcesCount'] >= 2]
        
        assert len(multi_source) >= 2, f"Expected at least 2 multi-source clusters, got {len(multi_source)}"
        
        print(f"PASS: Found {len(multi_source)} multi-source clusters")
        for c in multi_source[:3]:
            print(f"  - {c['title'][:50]}... ({c['sourcesCount']} sources: {', '.join(c['sources'])})")
    
    def test_multi_source_cluster_has_multiple_events(self):
        """Multi-source clusters have multiple events"""
        response = requests.get(f"{BASE_URL}/api/news/feed?limit=50")
        clusters = response.json()['data']['clusters']
        
        multi_source = [c for c in clusters if c['sourcesCount'] >= 2]
        
        if len(multi_source) == 0:
            pytest.skip("No multi-source clusters available")
        
        for cluster in multi_source:
            assert len(cluster['events']) >= cluster['sourcesCount'], \
                f"Cluster should have at least {cluster['sourcesCount']} events, got {len(cluster['events'])}"
        
        print(f"PASS: All {len(multi_source)} multi-source clusters have correct event counts")


class TestEventTypes:
    """Tests for event type detection"""
    
    def test_event_types_variety(self):
        """Feed contains variety of event types"""
        response = requests.get(f"{BASE_URL}/api/news/feed?limit=50")
        clusters = response.json()['data']['clusters']
        
        event_types = set(c['eventType'] for c in clusters)
        
        # Should have at least 3 different event types
        assert len(event_types) >= 3, f"Expected at least 3 event types, got {event_types}"
        
        print(f"PASS: Found {len(event_types)} event types: {event_types}")
    
    def test_expected_event_types_present(self):
        """Expected event types are present in feed"""
        response = requests.get(f"{BASE_URL}/api/news/feed?limit=50")
        clusters = response.json()['data']['clusters']
        
        event_types = set(c['eventType'] for c in clusters)
        
        # At least some of these should be present
        expected_types = {'regulation', 'funding', 'etf', 'macro', 'price', 'whale', 'market', 'upgrade'}
        found_expected = event_types.intersection(expected_types)
        
        assert len(found_expected) >= 2, f"Expected at least 2 of {expected_types}, found {found_expected}"
        
        print(f"PASS: Found expected event types: {found_expected}")


class TestExistingAdminEndpoints:
    """Tests for existing admin endpoints still working"""
    
    def test_admin_news_sources(self):
        """GET /api/admin/news/sources still works"""
        response = requests.get(f"{BASE_URL}/api/admin/news/sources")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') == True
        assert 'data' in data
        
        print(f"PASS: GET /api/admin/news/sources returns {len(data['data'])} sources")
    
    def test_admin_news_health(self):
        """GET /api/admin/news/health still works"""
        response = requests.get(f"{BASE_URL}/api/admin/news/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') == True
        assert 'data' in data
        
        print("PASS: GET /api/admin/news/health returns health snapshot")


class TestBreakingDetectionLogic:
    """Tests for breaking detection logic (3+ sources AND age < 30min)"""
    
    def test_breaking_requires_3_sources(self):
        """Breaking clusters must have sourcesCount >= 3"""
        response = requests.get(f"{BASE_URL}/api/news/feed?limit=50")
        clusters = response.json()['data']['clusters']
        
        breaking_clusters = [c for c in clusters if c['isBreaking']]
        
        for cluster in breaking_clusters:
            assert cluster['sourcesCount'] >= 3, \
                f"Breaking cluster should have 3+ sources, got {cluster['sourcesCount']}"
        
        print(f"PASS: All {len(breaking_clusters)} breaking clusters have 3+ sources (may be 0 if no recent breaking news)")
    
    def test_non_breaking_with_few_sources(self):
        """Clusters with < 3 sources should not be breaking"""
        response = requests.get(f"{BASE_URL}/api/news/feed?limit=50")
        clusters = response.json()['data']['clusters']
        
        few_source_clusters = [c for c in clusters if c['sourcesCount'] < 3]
        
        for cluster in few_source_clusters:
            assert cluster['isBreaking'] == False, \
                f"Cluster with {cluster['sourcesCount']} sources should not be breaking"
        
        print(f"PASS: All {len(few_source_clusters)} clusters with <3 sources are not breaking")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
