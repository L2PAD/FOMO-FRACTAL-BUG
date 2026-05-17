"""
News Feed v2 API Tests
======================
Tests for Task 4 — News Feed Product Layer:
- Importance scoring v2 (0-100 scale, bands, breaking detection, feedRankScore)
- Updated cluster schema with new fields
- Feed API v2 with new response format
- Filters: asset, eventType, importance band
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestNewsFeedV2:
    """Tests for GET /api/news/feed v2 response format"""

    def test_feed_returns_200(self):
        """GET /api/news/feed returns 200 OK"""
        response = requests.get(f"{BASE_URL}/api/news/feed?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        print("PASS: GET /api/news/feed returns 200")

    def test_feed_has_clusters_and_meta(self):
        """Feed response has clusters array and meta object"""
        response = requests.get(f"{BASE_URL}/api/news/feed?limit=5")
        data = response.json()
        assert 'data' in data
        assert 'clusters' in data['data']
        assert 'meta' in data['data']
        assert isinstance(data['data']['clusters'], list)
        print("PASS: Feed has clusters and meta")

    def test_cluster_has_v2_fields(self):
        """Each cluster has v2 fields: importanceBand, feedRankScore, importance (0-100), isBreaking, representativeUrl, representativeSource"""
        response = requests.get(f"{BASE_URL}/api/news/feed?limit=10")
        data = response.json()
        clusters = data['data']['clusters']
        
        if len(clusters) == 0:
            pytest.skip("No clusters available")
        
        for cluster in clusters:
            # V2 required fields
            assert 'importanceBand' in cluster, f"Missing importanceBand in cluster {cluster.get('clusterId')}"
            assert cluster['importanceBand'] in ['high', 'medium', 'low'], f"Invalid importanceBand: {cluster['importanceBand']}"
            
            assert 'feedRankScore' in cluster, f"Missing feedRankScore in cluster {cluster.get('clusterId')}"
            assert isinstance(cluster['feedRankScore'], (int, float)), f"feedRankScore should be numeric"
            
            assert 'importance' in cluster, f"Missing importance in cluster {cluster.get('clusterId')}"
            assert 0 <= cluster['importance'] <= 100, f"importance should be 0-100, got {cluster['importance']}"
            
            assert 'isBreaking' in cluster, f"Missing isBreaking in cluster {cluster.get('clusterId')}"
            assert isinstance(cluster['isBreaking'], bool), f"isBreaking should be boolean"
            
            assert 'representativeUrl' in cluster, f"Missing representativeUrl in cluster {cluster.get('clusterId')}"
            assert 'representativeSource' in cluster, f"Missing representativeSource in cluster {cluster.get('clusterId')}"
        
        print(f"PASS: All {len(clusters)} clusters have v2 fields")

    def test_importance_score_0_100_scale(self):
        """Importance scores are in 0-100 range (not 0-1)"""
        response = requests.get(f"{BASE_URL}/api/news/feed?limit=20")
        data = response.json()
        clusters = data['data']['clusters']
        
        if len(clusters) == 0:
            pytest.skip("No clusters available")
        
        scores = [c['importance'] for c in clusters]
        max_score = max(scores)
        
        # If max score > 1, it's 0-100 scale (not 0-1)
        assert max_score > 1, f"Importance scores appear to be 0-1 scale, max={max_score}"
        assert all(0 <= s <= 100 for s in scores), "All scores should be 0-100"
        
        print(f"PASS: Importance scores in 0-100 range (max={max_score})")

    def test_importance_band_matches_score(self):
        """importanceBand matches importance score: high>=70, medium>=40, low<40"""
        response = requests.get(f"{BASE_URL}/api/news/feed?limit=30")
        data = response.json()
        clusters = data['data']['clusters']
        
        for cluster in clusters:
            score = cluster['importance']
            band = cluster['importanceBand']
            
            if score >= 70:
                expected = 'high'
            elif score >= 40:
                expected = 'medium'
            else:
                expected = 'low'
            
            assert band == expected, f"Score {score} should be {expected}, got {band}"
        
        print(f"PASS: All {len(clusters)} clusters have correct importance bands")


class TestNewsFeedFilters:
    """Tests for feed filters: asset, eventType, importance"""

    def test_filter_by_asset_btc(self):
        """GET /api/news/feed?asset=BTC returns only BTC clusters"""
        response = requests.get(f"{BASE_URL}/api/news/feed?asset=BTC&limit=20")
        assert response.status_code == 200
        data = response.json()
        clusters = data['data']['clusters']
        
        for cluster in clusters:
            assets = cluster.get('assets', [])
            primary = cluster.get('primaryAsset')
            # Either primaryAsset is BTC or BTC is in assets
            assert primary == 'BTC' or 'BTC' in assets, f"Cluster {cluster['clusterId']} doesn't have BTC"
        
        print(f"PASS: BTC filter returns {len(clusters)} BTC-related clusters")

    def test_filter_by_event_type_regulation(self):
        """GET /api/news/feed?eventType=regulation returns only regulation clusters"""
        response = requests.get(f"{BASE_URL}/api/news/feed?eventType=regulation&limit=20")
        assert response.status_code == 200
        data = response.json()
        clusters = data['data']['clusters']
        
        for cluster in clusters:
            assert cluster['eventType'] == 'regulation', f"Expected regulation, got {cluster['eventType']}"
        
        print(f"PASS: eventType=regulation filter returns {len(clusters)} regulation clusters")

    def test_filter_by_importance_medium(self):
        """GET /api/news/feed?importance=medium returns only medium importance clusters"""
        response = requests.get(f"{BASE_URL}/api/news/feed?importance=medium&limit=20")
        assert response.status_code == 200
        data = response.json()
        clusters = data['data']['clusters']
        
        for cluster in clusters:
            assert cluster['importanceBand'] == 'medium', f"Expected medium, got {cluster['importanceBand']}"
        
        print(f"PASS: importance=medium filter returns {len(clusters)} medium clusters")


class TestNewsStats:
    """Tests for GET /api/news/stats"""

    def test_stats_returns_200(self):
        """GET /api/news/stats returns 200 OK"""
        response = requests.get(f"{BASE_URL}/api/news/stats")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        print("PASS: GET /api/news/stats returns 200")

    def test_stats_has_importance_distribution(self):
        """Stats has importanceDistribution with high/medium/low counts"""
        response = requests.get(f"{BASE_URL}/api/news/stats")
        data = response.json()
        stats = data['data']
        
        assert 'importanceDistribution' in stats
        dist = stats['importanceDistribution']
        assert 'high' in dist
        assert 'medium' in dist
        assert 'low' in dist
        
        # Counts should be non-negative integers
        assert isinstance(dist['high'], int) and dist['high'] >= 0
        assert isinstance(dist['medium'], int) and dist['medium'] >= 0
        assert isinstance(dist['low'], int) and dist['low'] >= 0
        
        # Sum should equal totalClusters
        total = dist['high'] + dist['medium'] + dist['low']
        assert total == stats['totalClusters'], f"Distribution sum {total} != totalClusters {stats['totalClusters']}"
        
        print(f"PASS: importanceDistribution: high={dist['high']}, medium={dist['medium']}, low={dist['low']}")


class TestExistingAdminEndpoints:
    """Tests for existing admin endpoints still working"""

    def test_admin_news_sources(self):
        """GET /api/admin/news/sources still works"""
        response = requests.get(f"{BASE_URL}/api/admin/news/sources")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        assert 'sources' in data['data']
        print(f"PASS: /api/admin/news/sources returns {len(data['data']['sources'])} sources")

    def test_admin_news_health(self):
        """GET /api/admin/news/health still works"""
        response = requests.get(f"{BASE_URL}/api/admin/news/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        assert 'totalSources' in data['data']
        print(f"PASS: /api/admin/news/health returns health snapshot")


class TestMetaFields:
    """Tests for meta fields in feed response"""

    def test_meta_has_required_fields(self):
        """Meta has all required fields"""
        response = requests.get(f"{BASE_URL}/api/news/feed?limit=5")
        data = response.json()
        meta = data['data']['meta']
        
        required_fields = [
            'totalRawEvents', 'totalClusters', 'breakingCount',
            'highCount', 'mediumCount', 'lowCount',
            'timeRangeHours', 'compressionRatio', 'page', 'limit', 'generatedAt'
        ]
        
        for field in required_fields:
            assert field in meta, f"Missing meta field: {field}"
        
        print(f"PASS: Meta has all required fields")

    def test_meta_counts_consistent(self):
        """Meta counts are consistent: high + medium + low = totalClusters"""
        response = requests.get(f"{BASE_URL}/api/news/feed?limit=50")
        data = response.json()
        meta = data['data']['meta']
        
        total = meta['highCount'] + meta['mediumCount'] + meta['lowCount']
        assert total == meta['totalClusters'], f"Counts sum {total} != totalClusters {meta['totalClusters']}"
        
        print(f"PASS: Meta counts consistent (high={meta['highCount']}, medium={meta['mediumCount']}, low={meta['lowCount']})")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
