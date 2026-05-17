"""
News Tab v2 - Border Cleanup & Full Article Feature Tests
Tests for:
- POST /api/ai-news/expand - generates full deep-dive article
- GET /api/news/feed - news clusters feed
- GET /api/news/digest - market brief digest
- GET /api/news/velocity - market velocity
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestNewsExpandEndpoint:
    """Tests for POST /api/ai-news/expand - Full Article generation"""
    
    def test_expand_endpoint_exists(self):
        """Test that expand endpoint responds"""
        response = requests.post(
            f"{BASE_URL}/api/ai-news/expand",
            json={
                "title": "test",
                "summary": "test",
                "sentiment": "bullish",
                "eventType": "regulation",
                "assets": ["BTC"],
                "sourcesCount": 2,
                "events": [],
                "lang": "en"
            },
            timeout=60
        )
        # Should return 200 with ok field
        assert response.status_code == 200
        data = response.json()
        assert "ok" in data
    
    def test_expand_returns_article_structure(self):
        """Test that expand returns proper article structure"""
        response = requests.post(
            f"{BASE_URL}/api/ai-news/expand",
            json={
                "title": "Bitcoin ETF approval expected",
                "summary": "SEC likely to approve Bitcoin ETF",
                "sentiment": "bullish",
                "eventType": "etf",
                "assets": ["BTC"],
                "sourcesCount": 3,
                "events": [],
                "lang": "en"
            },
            timeout=90
        )
        assert response.status_code == 200
        data = response.json()
        
        if data.get("ok"):
            article = data.get("article", {})
            # Check article has required fields
            assert "title" in article, "Article should have title"
            assert "body" in article, "Article should have body"
            assert "sentiment" in article, "Article should have sentiment"
            # Optional fields
            if "conclusions" in article:
                assert isinstance(article["conclusions"], list)
            if "forecast" in article:
                assert isinstance(article["forecast"], str)
    
    def test_expand_with_russian_language(self):
        """Test expand with Russian language"""
        response = requests.post(
            f"{BASE_URL}/api/ai-news/expand",
            json={
                "title": "Регуляция криптовалют",
                "summary": "Новые правила для криптовалют",
                "sentiment": "neutral",
                "eventType": "regulation",
                "assets": ["BTC", "ETH"],
                "sourcesCount": 2,
                "events": [],
                "lang": "ru"
            },
            timeout=90
        )
        assert response.status_code == 200
        data = response.json()
        assert "ok" in data


class TestNewsFeedEndpoint:
    """Tests for GET /api/news/feed"""
    
    def test_news_feed_returns_clusters(self):
        """Test news feed returns clusters array"""
        response = requests.get(f"{BASE_URL}/api/news/feed?limit=10&hours=48", timeout=15)
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") == True
        assert "data" in data
        assert "clusters" in data["data"]
        assert isinstance(data["data"]["clusters"], list)
    
    def test_news_feed_cluster_structure(self):
        """Test cluster has required fields"""
        response = requests.get(f"{BASE_URL}/api/news/feed?limit=5&hours=48", timeout=15)
        assert response.status_code == 200
        data = response.json()
        
        clusters = data.get("data", {}).get("clusters", [])
        if len(clusters) > 0:
            cluster = clusters[0]
            # Required fields for cluster
            assert "clusterId" in cluster
            assert "title" in cluster
            assert "eventType" in cluster
            assert "importance" in cluster
            assert "importanceBand" in cluster
            assert "sentimentHint" in cluster
            assert "sourcesCount" in cluster


class TestMarketBriefEndpoints:
    """Tests for Market Brief related endpoints"""
    
    def test_digest_endpoint(self):
        """Test GET /api/news/digest"""
        response = requests.get(f"{BASE_URL}/api/news/digest", timeout=15)
        assert response.status_code == 200
        data = response.json()
        
        if data.get("ok"):
            digest = data.get("data", {})
            # Check for expected fields
            if digest:
                assert "totalEvents" in digest or "sentiment" in digest
    
    def test_velocity_endpoint(self):
        """Test GET /api/news/velocity"""
        response = requests.get(f"{BASE_URL}/api/news/velocity", timeout=15)
        assert response.status_code == 200
        data = response.json()
        
        if data.get("ok"):
            velocity = data.get("data", {})
            if velocity:
                # Velocity should have level and message
                assert "level" in velocity or "message" in velocity


class TestAINewsEndpoints:
    """Tests for AI News generation endpoints"""
    
    def test_latest_article(self):
        """Test GET /api/ai-news/latest"""
        response = requests.get(f"{BASE_URL}/api/ai-news/latest", timeout=15)
        assert response.status_code == 200
        data = response.json()
        assert "ok" in data
    
    def test_articles_list(self):
        """Test GET /api/ai-news/articles"""
        response = requests.get(f"{BASE_URL}/api/ai-news/articles?limit=5", timeout=15)
        assert response.status_code == 200
        data = response.json()
        assert "ok" in data
        if data.get("ok"):
            assert "articles" in data
            assert isinstance(data["articles"], list)
    
    def test_image_endpoint_404_for_invalid(self):
        """Test GET /api/ai-news/image/{id} returns 404 for invalid ID"""
        response = requests.get(f"{BASE_URL}/api/ai-news/image/nonexistent123", timeout=10)
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
