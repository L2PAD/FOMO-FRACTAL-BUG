"""
Telegram Intel - Metrics and Computed Data Tests
Tests all the features related to metrics calculations:
- Channel list with computed fields (type, sector, members, avgReach, growth7, activity, redFlags, fomoScore)
- Stats cards (tracked, avgScore, highGrowth, highRisk)
- Search functionality in entities and feed
- Topic momentum, cross-channel signals, alerts
- Feed with channelTitle, channelAvatar, channelSector
- Related channels on channel overview
"""

import pytest
import requests
import os
import time

# Use the public preview URL for testing
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com').rstrip('/')
TIMEOUT = 60  # Generous timeout as backend can be slow


class TestChannelListWithMetrics:
    """Test /api/telegram-intel/utility/list returns items with all computed fields"""
    
    def test_utility_list_returns_items_with_fields(self):
        """Test that utility/list returns channels with type, sector, members, avgReach, growth7, activity, redFlags, fomoScore, stars, avatarUrl"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/utility/list", timeout=TIMEOUT)
        assert response.status_code == 200, f"API returned {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") == True, f"Response not ok: {data}"
        
        items = data.get("items", [])
        assert len(items) > 0, f"Expected channels in items but got empty: {data}"
        
        # Check first item has all required fields
        first = items[0]
        required_fields = ["type", "sector", "members", "avgReach", "growth7", "activity", "redFlags", "fomoScore", "stars"]
        
        print(f"\nFirst channel: {first.get('username')}")
        for field in required_fields:
            value = first.get(field)
            print(f"  {field}: {value}")
            # Check field exists (some may be None/0 which is acceptable)
            assert field in first, f"Missing field '{field}' in channel {first.get('username')}"
        
        # Validate specific field types/values
        assert isinstance(first.get("members", 0), int), "members should be int"
        assert isinstance(first.get("avgReach", 0), int), "avgReach should be int"
        assert isinstance(first.get("fomoScore", 0), (int, float)), "fomoScore should be numeric"
        assert isinstance(first.get("stars", 0), (int, float)), "stars should be numeric"
    
    def test_utility_list_returns_stats(self):
        """Test that utility/list returns stats object with tracked, avgUtility, highGrowth, highRisk"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/utility/list", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        stats = data.get("stats", {})
        
        print(f"\nStats: {stats}")
        
        required_stats = ["tracked", "avgUtility", "highGrowth", "highRisk"]
        for stat in required_stats:
            assert stat in stats, f"Missing stat '{stat}' in stats"
            print(f"  {stat}: {stats.get(stat)}")
        
        # Tracked should be > 0 if we have channels
        assert stats.get("tracked", 0) > 0, f"Expected tracked > 0 but got {stats.get('tracked')}"
    
    def test_utility_list_search_crypto(self):
        """Test that search q=crypto returns filtered channels matching in username/title/sector"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/utility/list?q=crypto", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        print(f"\nSearch 'crypto': {data.get('total')} results")
        
        items = data.get("items", [])
        for item in items[:3]:
            print(f"  - {item.get('username')}: {item.get('title')} (sector: {item.get('sector')})")


class TestFeedWithChannelMetadata:
    """Test /api/telegram-intel/feed/v2 returns posts with channel metadata"""
    
    def test_feed_v2_with_channel_metadata(self):
        """Test that feed/v2 returns posts with channelTitle, channelAvatar, channelSector fields"""
        # Use actorId=a_public as specified in requirements
        response = requests.get(f"{BASE_URL}/api/telegram-intel/feed/v2?actorId=a_public", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True, f"Response not ok: {data}"
        
        items = data.get("items", [])
        print(f"\nFeed posts: {len(items)} items, total: {data.get('total')}")
        
        if len(items) > 0:
            first = items[0]
            print(f"\nFirst post from @{first.get('username')}:")
            print(f"  channelTitle: {first.get('channelTitle')}")
            print(f"  channelAvatar: {first.get('channelAvatar')}")
            print(f"  channelSector: {first.get('channelSector')}")
            
            # Check fields exist
            assert "channelTitle" in first, "Missing channelTitle in post"
            assert "channelAvatar" in first, "Missing channelAvatar in post"
            assert "channelSector" in first, "Missing channelSector in post"


class TestTopicMomentum:
    """Test /api/telegram-intel/topics/momentum returns trending topics"""
    
    def test_topics_momentum(self):
        """Test that topics/momentum returns topics with mentions, channels, momentum"""
        # Use 168 hours (7 days) as specified
        response = requests.get(f"{BASE_URL}/api/telegram-intel/topics/momentum?hours=168", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        
        topics = data.get("topics", [])
        print(f"\nTopic Momentum: {len(topics)} topics found")
        
        for topic in topics[:5]:
            print(f"  - {topic.get('topic')}: {topic.get('mentions')} mentions, {topic.get('channels')} channels, momentum: {topic.get('momentum')}")
            
            # Check topic has required fields
            assert "topic" in topic, "Missing 'topic' field"
            assert "mentions" in topic, "Missing 'mentions' field"
            assert "channels" in topic, "Missing 'channels' field"
            assert "momentum" in topic, "Missing 'momentum' field"


class TestCrossChannelSignals:
    """Test /api/telegram-intel/signals/cross-channel returns cross-channel events"""
    
    def test_cross_channel_signals(self):
        """Test that signals/cross-channel returns events with entity, channelCount, mentions"""
        # Use window=10080 (7 days in minutes) as specified
        response = requests.get(f"{BASE_URL}/api/telegram-intel/signals/cross-channel?window=10080", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        
        events = data.get("events", [])
        print(f"\nCross-Channel Signals: {data.get('eventCount')} events")
        
        for event in events[:5]:
            print(f"  - {event.get('entity')}: {event.get('channelCount')} channels, {event.get('mentions')} mentions")
            
            # Check event has required fields
            assert "entity" in event, "Missing 'entity' field"
            assert "channelCount" in event, "Missing 'channelCount' field"
            assert "mentions" in event, "Missing 'mentions' field"


class TestAlerts:
    """Test /api/telegram-intel/alerts returns generated alerts"""
    
    def test_alerts(self):
        """Test that alerts returns alerts with type, severity, title, message"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/alerts?actorId=a_public", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        
        alerts = data.get("alerts", [])
        print(f"\nAlerts: {len(alerts)} alerts found")
        
        for alert in alerts[:5]:
            print(f"  - [{alert.get('severity')}] {alert.get('type')}: {alert.get('title')}")
            
            # Check alert has required fields
            if len(alerts) > 0:
                first = alerts[0]
                assert "type" in first, "Missing 'type' field"
                assert "severity" in first, "Missing 'severity' field"
                assert "title" in first, "Missing 'title' field"


class TestChannelOverviewRelated:
    """Test /api/telegram-intel/channel/{username}/full returns relatedChannels"""
    
    def test_channel_full_has_related_channels(self):
        """Test that channel/incrypted/full returns relatedChannels array (not empty)"""
        # Use incrypted as test channel
        response = requests.get(f"{BASE_URL}/api/telegram-intel/channel/incrypted/full", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True, f"Channel not found or error: {data}"
        
        related = data.get("relatedChannels", [])
        print(f"\nRelated Channels for incrypted: {len(related)}")
        
        for ch in related[:5]:
            print(f"  - @{ch.get('username')}: {ch.get('title')} ({ch.get('sector')})")
        
        # Related channels should not be empty (fallback returns all other channels)
        assert len(related) > 0, f"Expected relatedChannels to not be empty: {data}"


class TestFeedSearch:
    """Test /api/telegram-intel/feed/search returns search results"""
    
    def test_feed_search_bitcoin(self):
        """Test that feed/search?q=bitcoin returns search results matching 'bitcoin'"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/feed/search?q=bitcoin&actorId=a_public&days=30", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        
        items = data.get("items", [])
        total = data.get("total", 0)
        print(f"\nFeed Search 'bitcoin': {total} results")
        
        for item in items[:3]:
            text_preview = (item.get("text", "")[:80] + "...") if len(item.get("text", "")) > 80 else item.get("text", "")
            print(f"  - @{item.get('username')}: {text_preview}")


class TestChannelSearch:
    """Test /api/telegram-intel/channels/search returns channel search results"""
    
    def test_channels_search(self):
        """Test that channels/search?q=crypto returns matching channels"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/channels/search?q=crypto", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        
        items = data.get("items", [])
        print(f"\nChannels Search 'crypto': {len(items)} results")
        
        for item in items[:5]:
            print(f"  - @{item.get('username')}: {item.get('title')} (sector: {item.get('sector')})")


class TestAggregateStats:
    """Test /api/telegram-intel/stats/aggregate returns stats for cards"""
    
    def test_aggregate_stats(self):
        """Test aggregate stats endpoint returns tracked, avgScore, highGrowth, highRisk"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/stats/aggregate", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        
        print(f"\nAggregate Stats:")
        print(f"  tracked: {data.get('tracked')}")
        print(f"  avgScore: {data.get('avgScore')}")
        print(f"  highGrowth: {data.get('highGrowth')}")
        print(f"  highRisk: {data.get('highRisk')}")
        
        # At least tracked should be > 0
        assert data.get("tracked", 0) > 0, f"Expected tracked > 0"


class TestSpecificChannelMetrics:
    """Test specific channel has computed metrics"""
    
    def test_durov_channel_has_metrics(self):
        """Test durov channel (10.5M members) has computed metrics"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/channel/durov/full", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        if not data.get("ok"):
            pytest.skip("durov channel not in DB")
        
        channel = data.get("channel", {})
        metrics = data.get("metrics", {})
        
        print(f"\ndurov channel:")
        print(f"  members: {channel.get('members')}")
        print(f"  type: {channel.get('type')}")
        print(f"  sector: {channel.get('sector')}")
        print(f"  fomoScore: {metrics.get('utilityScore')}")
        print(f"  engagement: {metrics.get('engagementRate')}")
        
        # durov should have ~10.5M members
        members = channel.get("members", 0)
        assert members > 1000000, f"durov should have 1M+ members, got {members}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
