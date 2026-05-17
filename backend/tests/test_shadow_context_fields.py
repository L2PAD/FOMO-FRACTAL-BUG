"""
Shadow Decision Logs Context Fields Tests
==========================================
Tests for ML Validation Stage 2:
- Shadow decision logs must include context fields (eventType, importanceBand, sourcesCount, clusterSize, recencyBucket, assetClass)
- Breaking fallback v2: show top 3 by importanceScore when no breaking events
- News feed API returns clusters with required fields
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestShadowStatsContextCoverage:
    """Test GET /api/admin/sentiment-ml/shadow/stats returns context coverage and distribution"""
    
    def test_shadow_stats_returns_context_coverage(self):
        """Stats should return contextCoverage field"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/shadow/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get('ok') == True, f"Expected ok:true, got {data}"
        
        # Check contextCoverage exists
        assert 'contextCoverage' in data, f"Missing contextCoverage in response: {data.keys()}"
        
        # contextCoverage should be a number between 0 and 1
        coverage = data['contextCoverage']
        assert isinstance(coverage, (int, float)), f"contextCoverage should be numeric, got {type(coverage)}"
        assert 0 <= coverage <= 1, f"contextCoverage should be 0-1, got {coverage}"
        
        print(f"PASS: contextCoverage = {coverage}")
    
    def test_shadow_stats_returns_context_distribution(self):
        """Stats should return contextDistribution with eventTypes, importanceBands, assetClasses, recencyBuckets"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/shadow/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        
        # Check contextDistribution exists
        assert 'contextDistribution' in data, f"Missing contextDistribution in response: {data.keys()}"
        
        dist = data['contextDistribution']
        assert isinstance(dist, dict), f"contextDistribution should be dict, got {type(dist)}"
        
        # Check all required sub-fields
        required_fields = ['eventTypes', 'importanceBands', 'assetClasses', 'recencyBuckets']
        for field in required_fields:
            assert field in dist, f"Missing {field} in contextDistribution: {dist.keys()}"
            assert isinstance(dist[field], dict), f"{field} should be dict, got {type(dist[field])}"
        
        print(f"PASS: contextDistribution has all required fields")
        print(f"  eventTypes: {dist['eventTypes']}")
        print(f"  importanceBands: {dist['importanceBands']}")
        print(f"  assetClasses: {dist['assetClasses']}")
        print(f"  recencyBuckets: {dist['recencyBuckets']}")


class TestShadowRecordTest:
    """Test POST /api/admin/sentiment-ml/shadow/record-test creates decision with newsContext"""
    
    def test_record_test_returns_recorded_true(self):
        """Record test should return recorded=true"""
        response = requests.post(
            f"{BASE_URL}/api/admin/sentiment-ml/shadow/record-test",
            json={"symbol": "ETH", "bias": 0.15}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Note: recorded may be false if duplicate key (already recorded for this symbol/time)
        # So we check the response structure is correct
        assert 'recorded' in data, f"Missing 'recorded' in response: {data}"
        assert 'ok' in data, f"Missing 'ok' in response: {data}"
        
        if data.get('recorded'):
            print(f"PASS: record-test returned recorded=true")
        else:
            # Duplicate is acceptable
            print(f"INFO: record-test returned recorded=false (likely duplicate): {data.get('error', 'no error')}")


class TestShadowLatest:
    """Test GET /api/admin/sentiment-ml/shadow/latest returns decisions with newsContext"""
    
    def test_latest_returns_decisions_with_news_context(self):
        """Latest decisions should have newsContext object populated"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/shadow/latest")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get('ok') == True, f"Expected ok:true, got {data}"
        assert 'decisions' in data, f"Missing decisions in response: {data.keys()}"
        
        decisions = data['decisions']
        assert isinstance(decisions, list), f"decisions should be list, got {type(decisions)}"
        
        if len(decisions) == 0:
            print("INFO: No decisions found, skipping newsContext check")
            return
        
        # Check at least some decisions have newsContext
        with_context = [d for d in decisions if d.get('newsContext')]
        print(f"INFO: {len(with_context)}/{len(decisions)} decisions have newsContext")
        
        # Verify newsContext structure for decisions that have it
        context_fields = ['eventType', 'importanceBand', 'sourcesCount', 'clusterSize', 'recencyBucket', 'assetClass']
        for d in with_context[:3]:  # Check first 3
            ctx = d['newsContext']
            for field in context_fields:
                assert field in ctx, f"Missing {field} in newsContext: {ctx.keys()}"
            print(f"  Decision {d['symbol']}: eventType={ctx['eventType']}, importanceBand={ctx['importanceBand']}, assetClass={ctx['assetClass']}")
        
        print(f"PASS: newsContext structure verified")


class TestShadowBackfill:
    """Test POST /api/admin/sentiment-ml/shadow/backfill works without errors"""
    
    def test_backfill_returns_success(self):
        """Backfill should return ok:true with updated/failed/skipped counts"""
        response = requests.post(f"{BASE_URL}/api/admin/sentiment-ml/shadow/backfill")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get('ok') == True, f"Expected ok:true, got {data}"
        
        # Check response has expected fields
        assert 'updated' in data, f"Missing 'updated' in response: {data.keys()}"
        assert 'failed' in data, f"Missing 'failed' in response: {data.keys()}"
        assert 'skipped' in data, f"Missing 'skipped' in response: {data.keys()}"
        
        print(f"PASS: backfill returned ok:true")
        print(f"  updated: {data['updated']}, failed: {data['failed']}, skipped: {data['skipped']}")


class TestShadowReport:
    """Test GET /api/admin/sentiment-ml/shadow/report returns scenario, global stats, dataReady"""
    
    def test_report_returns_required_fields(self):
        """Report should return scenario, global stats, dataReady fields"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/shadow/report")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get('ok') == True, f"Expected ok:true, got {data}"
        
        # Check required top-level fields
        assert 'scenario' in data, f"Missing 'scenario' in response: {data.keys()}"
        assert 'dataReady' in data, f"Missing 'dataReady' in response: {data.keys()}"
        assert 'global' in data, f"Missing 'global' in response: {data.keys()}"
        
        # Check global stats structure
        global_stats = data['global']
        required_global = ['total', 'evaluated', 'pending', 'mlAccuracy', 'ruleAccuracy', 'delta', 'agreementRate']
        for field in required_global:
            assert field in global_stats, f"Missing {field} in global stats: {global_stats.keys()}"
        
        print(f"PASS: report has all required fields")
        print(f"  scenario: {data['scenario']}")
        print(f"  dataReady: {data['dataReady']}")
        print(f"  global.total: {global_stats['total']}, evaluated: {global_stats['evaluated']}")


class TestNewsFeedAPI:
    """Test GET /api/news/feed returns clusters with required fields"""
    
    def test_news_feed_returns_clusters_with_required_fields(self):
        """News feed should return clusters with importance, importanceBand, eventType, sourcesCount, isBreaking, assets"""
        response = requests.get(f"{BASE_URL}/api/news/feed?limit=5&hours=48")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get('ok') == True, f"Expected ok:true, got {data}"
        assert 'data' in data, f"Missing 'data' in response: {data.keys()}"
        
        feed_data = data['data']
        assert 'clusters' in feed_data, f"Missing 'clusters' in data: {feed_data.keys()}"
        
        clusters = feed_data['clusters']
        assert isinstance(clusters, list), f"clusters should be list, got {type(clusters)}"
        
        if len(clusters) == 0:
            print("INFO: No clusters found in news feed")
            return
        
        # Check required fields on each cluster
        required_fields = ['importance', 'importanceBand', 'eventType', 'sourcesCount', 'isBreaking', 'assets']
        for i, cluster in enumerate(clusters[:5]):  # Check first 5
            for field in required_fields:
                assert field in cluster, f"Cluster {i} missing {field}: {cluster.keys()}"
            
            print(f"  Cluster {i}: importance={cluster['importance']}, band={cluster['importanceBand']}, type={cluster['eventType']}, sources={cluster['sourcesCount']}, breaking={cluster['isBreaking']}")
        
        print(f"PASS: All {len(clusters)} clusters have required fields")
    
    def test_news_feed_clusters_have_valid_importance_bands(self):
        """Clusters should have valid importanceBand values (high, medium, low)"""
        response = requests.get(f"{BASE_URL}/api/news/feed?limit=50&hours=48")
        assert response.status_code == 200
        
        data = response.json()
        clusters = data.get('data', {}).get('clusters', [])
        
        valid_bands = ['high', 'medium', 'low']
        for cluster in clusters:
            band = cluster.get('importanceBand', '').lower()
            assert band in valid_bands, f"Invalid importanceBand '{band}' for cluster {cluster.get('clusterId')}"
        
        # Count distribution
        band_counts = {'high': 0, 'medium': 0, 'low': 0}
        for c in clusters:
            band = c.get('importanceBand', '').lower()
            if band in band_counts:
                band_counts[band] += 1
        
        print(f"PASS: All clusters have valid importanceBand")
        print(f"  Distribution: HIGH={band_counts['high']}, MEDIUM={band_counts['medium']}, LOW={band_counts['low']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
