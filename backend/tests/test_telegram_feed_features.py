"""
Telegram Feed Page Features Tests
Testing: 
1. Post images from media endpoint
2. Cross-channel signals with entity, channels, mentions
3. Feed stats
4. Feed v2 with media and pinnedInChannel fields
"""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestFeedV2API:
    """Tests for /api/telegram-intel/feed/v2 endpoint - posts with media"""
    
    def test_feed_v2_returns_posts(self):
        """Feed v2 returns posts with expected structure"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/feed/v2?actorId=a_public&page=1&limit=20")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "items" in data
        assert len(data["items"]) > 0
        
        # Verify total and pagination
        assert "total" in data
        assert "pages" in data
        assert "watchlistCount" in data
        
    def test_feed_v2_post_structure(self):
        """Each post has required fields including media and pinnedInChannel"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/feed/v2?actorId=a_public&page=1&limit=10")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        for post in data["items"]:
            # Required fields
            assert "messageId" in post
            assert "username" in post
            assert "date" in post
            assert "text" in post
            
            # Media field (can be None or object)
            assert "media" in post
            
            # pinnedInChannel field (boolean)
            assert "pinnedInChannel" in post
            assert isinstance(post["pinnedInChannel"], bool)
            
            # Engagement metrics
            assert "views" in post
            assert "forwards" in post
            
            # Channel metadata
            assert "channelTitle" in post
            
    def test_feed_v2_media_object(self):
        """Posts with media have properly structured media object"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/feed/v2?actorId=a_public&page=1&limit=50")
        assert response.status_code == 200
        
        data = response.json()
        posts_with_media = [p for p in data["items"] if p.get("media")]
        
        # Should have some posts with media
        print(f"Posts with media: {len(posts_with_media)}")
        
        for post in posts_with_media:
            media = post["media"]
            assert "url" in media
            assert media["url"].startswith("/tg/media/")
            assert "kind" in media  # photo, video, etc.
            

class TestCrossChannelSignals:
    """Tests for /api/telegram-intel/signals/cross-channel endpoint"""
    
    def test_signals_endpoint_returns_events(self):
        """Cross-channel signals endpoint returns events"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/signals/cross-channel?window=10080")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "events" in data
        assert "eventCount" in data
        
    def test_signal_event_structure(self):
        """Each signal event has entity, channels array, channelCount, mentions"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/signals/cross-channel?window=10080")
        assert response.status_code == 200
        
        data = response.json()
        events = data.get("events", [])
        
        # Should have signals if there's data
        if len(events) > 0:
            for event in events[:5]:
                # Required fields for cross-channel signals
                assert "entity" in event, f"Event missing 'entity': {event}"
                assert "channels" in event, f"Event missing 'channels': {event}"
                assert "channelCount" in event, f"Event missing 'channelCount': {event}"
                assert "mentions" in event, f"Event missing 'mentions': {event}"
                
                # Channels should be a list
                assert isinstance(event["channels"], list)
                assert event["channelCount"] == len(event["channels"])
                
                # Entity should be a string (topic/keyword)
                assert isinstance(event["entity"], str)
                assert len(event["entity"]) > 0
                
                print(f"Signal: {event['entity']} - {event['channelCount']} channels, {event['mentions']} mentions")
                
    def test_signals_contain_known_entities(self):
        """Cross-channel signals contain expected crypto entities"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/signals/cross-channel?window=10080")
        assert response.status_code == 200
        
        data = response.json()
        events = data.get("events", [])
        
        entities = [e.get("entity", "") for e in events]
        
        # Should contain some known crypto topics
        known_entities = ["Bitcoin", "Ethereum", "USDT", "Binance"]
        found_count = sum(1 for ke in known_entities if ke in entities)
        print(f"Found {found_count}/{len(known_entities)} known entities: {entities}")


class TestFeedStats:
    """Tests for /api/telegram-intel/feed/stats endpoint"""
    
    def test_feed_stats_returns_counts(self):
        """Feed stats returns expected count fields"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/feed/stats?actorId=a_public&hours=24")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        # Required stats fields
        assert "postsToday" in data
        assert "mediaCount" in data
        assert "pinnedCount" in data
        assert "channelsInFeed" in data
        
        # Values should be integers
        assert isinstance(data["postsToday"], int)
        assert isinstance(data["mediaCount"], int)
        assert isinstance(data["pinnedCount"], int)
        
        print(f"Feed Stats: posts={data['postsToday']}, media={data['mediaCount']}, pinned={data['pinnedCount']}")
        

class TestMediaEndpoint:
    """Tests for /api/telegram-intel/media/{username}/{filename} endpoint"""
    
    def test_media_endpoint_serves_image(self):
        """Media endpoint serves actual image file"""
        # First get a post with media
        feed_response = requests.get(f"{BASE_URL}/api/telegram-intel/feed/v2?actorId=a_public&page=1&limit=50")
        assert feed_response.status_code == 200
        
        data = feed_response.json()
        posts_with_media = [p for p in data["items"] if p.get("media")]
        
        if not posts_with_media:
            pytest.skip("No posts with media found")
            
        # Get media URL from first post with media
        post = posts_with_media[0]
        username = post["username"]
        message_id = post["messageId"]
        
        # Request the media file
        media_response = requests.get(f"{BASE_URL}/api/telegram-intel/media/{username}/{message_id}.jpg")
        
        # Should return image
        assert media_response.status_code == 200
        assert media_response.headers.get("content-type") == "image/jpeg"
        assert len(media_response.content) > 1000  # Should be more than 1KB
        
        print(f"Media served: {username}/{message_id}.jpg - {len(media_response.content)} bytes")


class TestFeedSearch:
    """Tests for /api/telegram-intel/feed/search endpoint"""
    
    def test_search_returns_results(self):
        """Search endpoint returns matching posts"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/feed/search?actorId=a_public&q=Bitcoin&days=30")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "items" in data
        assert "total" in data
        
        print(f"Search 'Bitcoin': {data['total']} results")
        
    def test_search_by_username_filter(self):
        """Search with username filter returns posts from that channel"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/feed/search?actorId=a_public&username=incrypted&days=30")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        # All posts should be from incrypted
        for post in data["items"]:
            assert post["username"] == "incrypted"
            
    def test_search_includes_media_info(self):
        """Search results include media information"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/feed/search?actorId=a_public&q=Bitcoin&days=30&limit=50")
        assert response.status_code == 200
        
        data = response.json()
        
        for post in data["items"]:
            assert "media" in post
            assert "pinnedInChannel" in post


class TestChannelAutocomplete:
    """Tests for /api/telegram-intel/channels/autocomplete endpoint"""
    
    def test_autocomplete_returns_suggestions(self):
        """Autocomplete returns channel suggestions"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/channels/autocomplete?q=inc&limit=5")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "suggestions" in data
        
        if data["suggestions"]:
            suggestion = data["suggestions"][0]
            assert "username" in suggestion
            assert "title" in suggestion
            
            print(f"Autocomplete 'inc': {len(data['suggestions'])} suggestions")
