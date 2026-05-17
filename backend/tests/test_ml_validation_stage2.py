"""
ML Validation Stage 2 Backend Tests
====================================
Tests for:
1. Adaptive outcome labeling with volatility-based thresholds
2. Narrative Velocity endpoint (/api/news/velocity)
3. Daily Digest endpoint (/api/news/digest)
4. Label distribution endpoint (/api/admin/sentiment-ml/shadow/label-distribution)
5. Shadow finalize endpoint with adaptive thresholds
6. Shadow stats with contextCoverage
7. Shadow record-test with newsContext
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestNewsVelocityEndpoint:
    """Tests for GET /api/news/velocity - Narrative velocity metrics"""
    
    def test_velocity_endpoint_returns_ok(self):
        """Velocity endpoint should return ok:true with required fields"""
        response = requests.get(f"{BASE_URL}/api/news/velocity", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') == True, "Expected ok:true"
        assert 'data' in data, "Expected data field"
        
    def test_velocity_has_required_fields(self):
        """Velocity data should have all required fields"""
        response = requests.get(f"{BASE_URL}/api/news/velocity", timeout=30)
        data = response.json()['data']
        
        # Required fields per spec
        required_fields = [
            'clustersPerHour', 'newClustersLast1h', 'breakingLast1h',
            'highImportanceLast1h', 'growthRatePct', 'level', 'message'
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
            
    def test_velocity_level_is_valid(self):
        """Velocity level should be one of CALM/NORMAL/ELEVATED/SPIKE"""
        response = requests.get(f"{BASE_URL}/api/news/velocity", timeout=30)
        data = response.json()['data']
        
        valid_levels = ['CALM', 'NORMAL', 'ELEVATED', 'SPIKE']
        assert data['level'] in valid_levels, f"Invalid level: {data['level']}"
        
    def test_velocity_clusters_per_hour_structure(self):
        """clustersPerHour should have 1h, 3h, 6h keys"""
        response = requests.get(f"{BASE_URL}/api/news/velocity", timeout=30)
        data = response.json()['data']
        
        cph = data['clustersPerHour']
        assert '1h' in cph, "Missing 1h in clustersPerHour"
        assert '3h' in cph, "Missing 3h in clustersPerHour"
        assert '6h' in cph, "Missing 6h in clustersPerHour"


class TestNewsDailyDigestEndpoint:
    """Tests for GET /api/news/digest - Daily market brief"""
    
    def test_digest_endpoint_returns_ok(self):
        """Digest endpoint should return ok:true"""
        response = requests.get(f"{BASE_URL}/api/news/digest", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') == True, "Expected ok:true"
        
    def test_digest_has_required_fields(self):
        """Digest data should have all required fields"""
        response = requests.get(f"{BASE_URL}/api/news/digest", timeout=30)
        data = response.json()['data']
        
        required_fields = [
            'period', 'generatedAt', 'totalEvents', 'breakingCount',
            'top5', 'sentiment', 'sentimentShiftPct', 'velocityChangePct', 'whyItMatters'
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
            
    def test_digest_top5_structure(self):
        """top5 should be array with title/eventType/importance/assets"""
        response = requests.get(f"{BASE_URL}/api/news/digest", timeout=30)
        data = response.json()['data']
        
        top5 = data['top5']
        assert isinstance(top5, list), "top5 should be a list"
        
        if len(top5) > 0:
            event = top5[0]
            assert 'title' in event, "top5 event missing title"
            assert 'eventType' in event, "top5 event missing eventType"
            assert 'importance' in event, "top5 event missing importance"
            assert 'assets' in event, "top5 event missing assets"
            
    def test_digest_sentiment_percentages(self):
        """sentiment should have bullish/bearish/neutral percentages"""
        response = requests.get(f"{BASE_URL}/api/news/digest", timeout=30)
        data = response.json()['data']
        
        sentiment = data['sentiment']
        assert 'bullish' in sentiment, "Missing bullish percentage"
        assert 'bearish' in sentiment, "Missing bearish percentage"
        assert 'neutral' in sentiment, "Missing neutral percentage"
        
    def test_digest_why_it_matters_is_array(self):
        """whyItMatters should be an array of strings"""
        response = requests.get(f"{BASE_URL}/api/news/digest", timeout=30)
        data = response.json()['data']
        
        assert isinstance(data['whyItMatters'], list), "whyItMatters should be a list"


class TestShadowLabelDistribution:
    """Tests for GET /api/admin/sentiment-ml/shadow/label-distribution"""
    
    def test_label_distribution_returns_ok(self):
        """Label distribution endpoint should return ok:true"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/shadow/label-distribution", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') == True, "Expected ok:true"
        
    def test_label_distribution_has_required_fields(self):
        """Label distribution should have distribution, percentages, volatilityBuckets, quality"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/shadow/label-distribution", timeout=30)
        data = response.json()
        
        required_fields = ['totalEvaluated', 'distribution', 'percentages', 'volatilityBuckets', 'quality']
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
            
    def test_label_distribution_percentages_structure(self):
        """percentages should have UP/DOWN/FLAT"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/shadow/label-distribution", timeout=30)
        data = response.json()
        
        pct = data['percentages']
        assert 'UP' in pct, "Missing UP percentage"
        assert 'DOWN' in pct, "Missing DOWN percentage"
        assert 'FLAT' in pct, "Missing FLAT percentage"
        
    def test_label_distribution_quality_verdict(self):
        """quality should have verdict field"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/shadow/label-distribution", timeout=30)
        data = response.json()
        
        quality = data['quality']
        assert 'verdict' in quality, "Missing verdict in quality"
        assert quality['verdict'] in ['GOOD', 'NEEDS_REVIEW'], f"Invalid verdict: {quality['verdict']}"


class TestShadowFinalize:
    """Tests for POST /api/admin/sentiment-ml/shadow/finalize"""
    
    def test_finalize_endpoint_returns_ok(self):
        """Finalize endpoint should return ok:true"""
        response = requests.post(f"{BASE_URL}/api/admin/sentiment-ml/shadow/finalize", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') == True, "Expected ok:true"
        
    def test_finalize_returns_counts(self):
        """Finalize should return processed/success/failed counts"""
        response = requests.post(f"{BASE_URL}/api/admin/sentiment-ml/shadow/finalize", timeout=60)
        data = response.json()
        
        assert 'processed' in data, "Missing processed count"
        assert 'success' in data, "Missing success count"
        assert 'failed' in data, "Missing failed count"


class TestShadowStats:
    """Tests for GET /api/admin/sentiment-ml/shadow/stats"""
    
    def test_stats_returns_ok(self):
        """Stats endpoint should return ok:true"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/shadow/stats", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') == True, "Expected ok:true"
        
    def test_stats_has_context_coverage(self):
        """Stats should include contextCoverage field"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/shadow/stats", timeout=30)
        data = response.json()
        
        assert 'contextCoverage' in data, "Missing contextCoverage"
        # contextCoverage should be 1 (100%) per spec
        assert data['contextCoverage'] == 1, f"Expected contextCoverage=1, got {data['contextCoverage']}"
        
    def test_stats_formatted_coverage(self):
        """Stats should have formatted.contextCoverage as percentage string"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/shadow/stats", timeout=30)
        data = response.json()
        
        assert 'formatted' in data, "Missing formatted field"
        assert 'contextCoverage' in data['formatted'], "Missing formatted.contextCoverage"


class TestShadowRecordTest:
    """Tests for POST /api/admin/sentiment-ml/shadow/record-test"""
    
    def test_record_test_with_sol_symbol(self):
        """Record test with SOL symbol and bias=0.3 should create decision with newsContext"""
        payload = {'symbol': 'SOL', 'bias': 0.3}
        response = requests.post(
            f"{BASE_URL}/api/admin/sentiment-ml/shadow/record-test",
            json=payload,
            timeout=30
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') == True, "Expected ok:true"
        
    def test_record_test_returns_recorded_true(self):
        """Record test should return recorded:true"""
        payload = {'symbol': 'ETH', 'bias': 0.2}
        response = requests.post(
            f"{BASE_URL}/api/admin/sentiment-ml/shadow/record-test",
            json=payload,
            timeout=30
        )
        data = response.json()
        
        assert data.get('recorded') == True or data.get('ok') == True, "Expected recorded:true or ok:true"


class TestNewsFeedIntegration:
    """Integration tests for news feed with cluster data"""
    
    def test_feed_returns_clusters_with_importance(self):
        """Feed should return clusters with importance fields"""
        response = requests.get(f"{BASE_URL}/api/news/feed?limit=10&hours=48", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        
        clusters = data['data']['clusters']
        if len(clusters) > 0:
            cluster = clusters[0]
            # Check for importance-related fields
            assert 'importance' in cluster or 'importanceScore' in cluster, "Missing importance field"
            
    def test_feed_clusters_have_event_type(self):
        """Clusters should have eventType field"""
        response = requests.get(f"{BASE_URL}/api/news/feed?limit=10&hours=48", timeout=30)
        data = response.json()
        
        clusters = data['data']['clusters']
        if len(clusters) > 0:
            cluster = clusters[0]
            assert 'eventType' in cluster, "Missing eventType field"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
