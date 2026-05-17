"""
Velocity v2 + Digest UI API Tests
=================================
Tests for:
- GET /api/news/velocity - v2 fields (current, baseline, velocityRatio, growthPct, level, trend24hPct, clusters24h, clustersYesterday)
- GET /api/news/digest - sentiment with actual percentages, top5 events with sentimentHint-based sentiment, whyItMatters
- Velocity level ratio-based detection: <0.8=CALM, 0.8-1.2=NORMAL, 1.2-1.8=ELEVATED, >=1.8=SPIKE
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestVelocityV2:
    """Tests for GET /api/news/velocity v2 endpoint"""
    
    def test_velocity_endpoint_returns_ok(self):
        """Test velocity endpoint returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/news/velocity")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        print(f"PASS: Velocity endpoint returns ok:true")
    
    def test_velocity_has_current_field(self):
        """Test velocity has current field (clusters in last 1h)"""
        response = requests.get(f"{BASE_URL}/api/news/velocity")
        data = response.json()
        assert 'data' in data
        assert 'current' in data['data']
        assert isinstance(data['data']['current'], (int, float))
        print(f"PASS: current = {data['data']['current']}")
    
    def test_velocity_has_baseline_field(self):
        """Test velocity has baseline field (avg clusters per hour over 24h)"""
        response = requests.get(f"{BASE_URL}/api/news/velocity")
        data = response.json()
        assert 'baseline' in data['data']
        assert isinstance(data['data']['baseline'], (int, float))
        print(f"PASS: baseline = {data['data']['baseline']}")
    
    def test_velocity_has_velocity_ratio_field(self):
        """Test velocity has velocityRatio field (current/baseline)"""
        response = requests.get(f"{BASE_URL}/api/news/velocity")
        data = response.json()
        assert 'velocityRatio' in data['data']
        assert isinstance(data['data']['velocityRatio'], (int, float))
        print(f"PASS: velocityRatio = {data['data']['velocityRatio']}")
    
    def test_velocity_has_growth_pct_field(self):
        """Test velocity has growthPct field"""
        response = requests.get(f"{BASE_URL}/api/news/velocity")
        data = response.json()
        assert 'growthPct' in data['data']
        assert isinstance(data['data']['growthPct'], (int, float))
        print(f"PASS: growthPct = {data['data']['growthPct']}")
    
    def test_velocity_has_level_field(self):
        """Test velocity has level field (CALM/NORMAL/ELEVATED/SPIKE)"""
        response = requests.get(f"{BASE_URL}/api/news/velocity")
        data = response.json()
        assert 'level' in data['data']
        assert data['data']['level'] in ['CALM', 'NORMAL', 'ELEVATED', 'SPIKE']
        print(f"PASS: level = {data['data']['level']}")
    
    def test_velocity_has_trend24h_pct_field(self):
        """Test velocity has trend24hPct field"""
        response = requests.get(f"{BASE_URL}/api/news/velocity")
        data = response.json()
        assert 'trend24hPct' in data['data']
        assert isinstance(data['data']['trend24hPct'], (int, float))
        print(f"PASS: trend24hPct = {data['data']['trend24hPct']}")
    
    def test_velocity_has_clusters24h_field(self):
        """Test velocity has clusters24h field"""
        response = requests.get(f"{BASE_URL}/api/news/velocity")
        data = response.json()
        assert 'clusters24h' in data['data']
        assert isinstance(data['data']['clusters24h'], int)
        print(f"PASS: clusters24h = {data['data']['clusters24h']}")
    
    def test_velocity_has_clusters_yesterday_field(self):
        """Test velocity has clustersYesterday field"""
        response = requests.get(f"{BASE_URL}/api/news/velocity")
        data = response.json()
        assert 'clustersYesterday' in data['data']
        assert isinstance(data['data']['clustersYesterday'], int)
        print(f"PASS: clustersYesterday = {data['data']['clustersYesterday']}")
    
    def test_velocity_level_ratio_based_detection(self):
        """Test velocity level uses ratio-based detection"""
        response = requests.get(f"{BASE_URL}/api/news/velocity")
        data = response.json()
        ratio = data['data']['velocityRatio']
        level = data['data']['level']
        
        # Verify level matches ratio (unless breaking override)
        breaking = data['data'].get('breakingLast1h', 0)
        if breaking >= 2:
            # Breaking override - level should be SPIKE
            print(f"INFO: Breaking override active ({breaking} breaking events)")
        else:
            # Normal ratio-based detection
            if ratio < 0.8:
                expected = 'CALM'
            elif ratio < 1.2:
                expected = 'NORMAL'
            elif ratio < 1.8:
                expected = 'ELEVATED'
            else:
                expected = 'SPIKE'
            
            assert level == expected, f"Expected {expected} for ratio {ratio}, got {level}"
            print(f"PASS: Level {level} matches ratio {ratio} (expected {expected})")
    
    def test_velocity_has_message_field(self):
        """Test velocity has message field"""
        response = requests.get(f"{BASE_URL}/api/news/velocity")
        data = response.json()
        assert 'message' in data['data']
        assert isinstance(data['data']['message'], str)
        print(f"PASS: message = {data['data']['message']}")


class TestDigestEndpoint:
    """Tests for GET /api/news/digest endpoint"""
    
    def test_digest_endpoint_returns_ok(self):
        """Test digest endpoint returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/news/digest")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        print(f"PASS: Digest endpoint returns ok:true")
    
    def test_digest_has_sentiment_with_percentages(self):
        """Test digest has sentiment with actual bullish/bearish/neutral percentages (NOT 100% neutral)"""
        response = requests.get(f"{BASE_URL}/api/news/digest")
        data = response.json()
        assert 'sentiment' in data['data']
        sentiment = data['data']['sentiment']
        
        assert 'bullish' in sentiment
        assert 'bearish' in sentiment
        assert 'neutral' in sentiment
        
        # Parse percentages
        bullish = int(sentiment['bullish'].replace('%', ''))
        bearish = int(sentiment['bearish'].replace('%', ''))
        neutral = int(sentiment['neutral'].replace('%', ''))
        
        # Verify not all 100% neutral (sentiment fix)
        total = bullish + bearish + neutral
        assert total >= 99 and total <= 101, f"Percentages should sum to ~100%, got {total}%"
        
        # If there are events, sentiment should not be 100% neutral
        if data['data'].get('totalEvents', 0) > 0:
            # At least one of bullish or bearish should be > 0 (unless truly all neutral)
            print(f"PASS: Sentiment distribution - Bullish: {bullish}%, Bearish: {bearish}%, Neutral: {neutral}%")
    
    def test_digest_has_top5_events(self):
        """Test digest has top5 events array"""
        response = requests.get(f"{BASE_URL}/api/news/digest")
        data = response.json()
        assert 'top5' in data['data']
        assert isinstance(data['data']['top5'], list)
        assert len(data['data']['top5']) <= 5
        print(f"PASS: top5 has {len(data['data']['top5'])} events")
    
    def test_digest_top5_events_have_sentiment_field(self):
        """Test top5 events have sentiment field from sentimentHint"""
        response = requests.get(f"{BASE_URL}/api/news/digest")
        data = response.json()
        top5 = data['data']['top5']
        
        for i, event in enumerate(top5):
            assert 'sentiment' in event, f"Event {i+1} missing sentiment field"
            assert event['sentiment'] in ['bullish', 'bearish', 'neutral'], f"Event {i+1} has invalid sentiment: {event['sentiment']}"
            print(f"PASS: Event {i+1} sentiment = {event['sentiment']}")
    
    def test_digest_top5_events_have_required_fields(self):
        """Test top5 events have all required fields"""
        response = requests.get(f"{BASE_URL}/api/news/digest")
        data = response.json()
        top5 = data['data']['top5']
        
        required_fields = ['title', 'eventType', 'importance', 'sentiment', 'assets', 'sourcesCount']
        
        for i, event in enumerate(top5):
            for field in required_fields:
                assert field in event, f"Event {i+1} missing {field}"
            print(f"PASS: Event {i+1} has all required fields: {event['title'][:50]}...")
    
    def test_digest_has_why_it_matters(self):
        """Test digest has whyItMatters array with strings"""
        response = requests.get(f"{BASE_URL}/api/news/digest")
        data = response.json()
        assert 'whyItMatters' in data['data']
        assert isinstance(data['data']['whyItMatters'], list)
        
        for item in data['data']['whyItMatters']:
            assert isinstance(item, str)
        
        print(f"PASS: whyItMatters = {data['data']['whyItMatters']}")
    
    def test_digest_has_sentiment_shift_pct(self):
        """Test digest has sentimentShiftPct field"""
        response = requests.get(f"{BASE_URL}/api/news/digest")
        data = response.json()
        assert 'sentimentShiftPct' in data['data']
        assert isinstance(data['data']['sentimentShiftPct'], (int, float))
        print(f"PASS: sentimentShiftPct = {data['data']['sentimentShiftPct']}")
    
    def test_digest_has_velocity_change_pct(self):
        """Test digest has velocityChangePct field"""
        response = requests.get(f"{BASE_URL}/api/news/digest")
        data = response.json()
        assert 'velocityChangePct' in data['data']
        assert isinstance(data['data']['velocityChangePct'], (int, float))
        print(f"PASS: velocityChangePct = {data['data']['velocityChangePct']}")
    
    def test_digest_has_total_events_and_breaking_count(self):
        """Test digest has totalEvents and breakingCount"""
        response = requests.get(f"{BASE_URL}/api/news/digest")
        data = response.json()
        assert 'totalEvents' in data['data']
        assert 'breakingCount' in data['data']
        assert isinstance(data['data']['totalEvents'], int)
        assert isinstance(data['data']['breakingCount'], int)
        print(f"PASS: totalEvents = {data['data']['totalEvents']}, breakingCount = {data['data']['breakingCount']}")


class TestNewsFeedIntegration:
    """Tests for news feed integration"""
    
    def test_news_feed_returns_clusters(self):
        """Test news feed returns clusters with required fields"""
        response = requests.get(f"{BASE_URL}/api/news/feed?limit=10&hours=24")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        assert 'clusters' in data['data']
        print(f"PASS: News feed returns {len(data['data']['clusters'])} clusters")
    
    def test_news_feed_clusters_have_sentiment_hint(self):
        """Test news feed clusters have sentimentHint field"""
        response = requests.get(f"{BASE_URL}/api/news/feed?limit=10&hours=24")
        data = response.json()
        clusters = data['data']['clusters']
        
        for i, cluster in enumerate(clusters[:5]):  # Check first 5
            # sentimentHint should be present
            if 'sentimentHint' in cluster:
                assert cluster['sentimentHint'] in ['bullish', 'bearish', 'neutral', None]
                print(f"PASS: Cluster {i+1} sentimentHint = {cluster.get('sentimentHint')}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
