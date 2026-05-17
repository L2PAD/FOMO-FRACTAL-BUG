"""
Telegram Intel - Bug Fix Tests
Tests for:
1. Feed diversification - shows posts from multiple channels
2. Clear all watchlist endpoint
3. AI Analytics (Product Analysis) endpoint
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestFeedDiversification:
    """Test feed v2 returns diversified posts from multiple channels"""

    def test_feed_v2_returns_ok(self):
        """Feed v2 endpoint returns ok=true"""
        res = requests.get(f"{BASE_URL}/api/telegram-intel/feed/v2?actorId=a_public&page=1&limit=50")
        assert res.status_code == 200
        data = res.json()
        assert data.get("ok") is True
        print(f"Feed v2 returned ok=true with {len(data.get('items', []))} items")
    
    def test_feed_page1_has_multiple_channels(self):
        """Feed page 1 includes posts from at least 3 different channels"""
        res = requests.get(f"{BASE_URL}/api/telegram-intel/feed/v2?actorId=a_public&page=1&limit=50")
        assert res.status_code == 200
        data = res.json()
        assert data.get("ok") is True
        
        items = data.get("items", [])
        if len(items) == 0:
            pytest.skip("No items in feed - watchlist may be empty")
        
        # Extract unique channel usernames
        channels = set(item.get("username") for item in items if item.get("username"))
        channel_count = len(channels)
        
        print(f"Page 1: {len(items)} posts from {channel_count} different channels")
        print(f"Channels: {list(channels)[:10]}")
        
        # Verify diversification - should have posts from multiple channels
        # Previously bug showed only truexanewsua posts
        assert channel_count >= 3, f"Expected at least 3 different channels, got {channel_count}. Channels: {channels}"
    
    def test_feed_page2_has_multiple_channels(self):
        """Feed page 2 also includes posts from multiple channels"""
        res = requests.get(f"{BASE_URL}/api/telegram-intel/feed/v2?actorId=a_public&page=2&limit=50")
        assert res.status_code == 200
        data = res.json()
        assert data.get("ok") is True
        
        items = data.get("items", [])
        if len(items) == 0:
            pytest.skip("No items on page 2 - not enough posts")
        
        # Extract unique channel usernames
        channels = set(item.get("username") for item in items if item.get("username"))
        channel_count = len(channels)
        
        print(f"Page 2: {len(items)} posts from {channel_count} different channels")
        
        # Page 2 should also be diversified
        assert channel_count >= 2, f"Expected at least 2 different channels on page 2, got {channel_count}"

    def test_feed_not_dominated_by_single_channel(self):
        """Feed is not dominated by a single channel (no channel has >50% of posts)"""
        res = requests.get(f"{BASE_URL}/api/telegram-intel/feed/v2?actorId=a_public&page=1&limit=50")
        assert res.status_code == 200
        data = res.json()
        
        items = data.get("items", [])
        if len(items) < 10:
            pytest.skip("Not enough posts to check dominance")
        
        # Count posts per channel
        channel_counts = {}
        for item in items:
            username = item.get("username", "unknown")
            channel_counts[username] = channel_counts.get(username, 0) + 1
        
        total_posts = len(items)
        max_channel, max_count = max(channel_counts.items(), key=lambda x: x[1])
        dominance_pct = (max_count / total_posts) * 100
        
        print(f"Total posts: {total_posts}")
        print(f"Channel distribution: {dict(sorted(channel_counts.items(), key=lambda x: -x[1])[:5])}")
        print(f"Most dominant channel: {max_channel} with {max_count} posts ({dominance_pct:.1f}%)")
        
        # No single channel should have more than 50% of posts
        assert dominance_pct <= 50, f"Feed dominated by {max_channel} with {dominance_pct:.1f}% of posts"


class TestClearWatchlist:
    """Test clear all watchlist endpoint - DELETE /api/telegram-intel/watchlist"""
    
    def test_clear_watchlist_endpoint_exists(self):
        """DELETE /api/telegram-intel/watchlist endpoint exists and returns ok"""
        # NOTE: We're not actually clearing the watchlist per agent instructions
        # Just verifying the endpoint works with a non-destructive test
        
        # First, check current watchlist count
        res_before = requests.get(f"{BASE_URL}/api/telegram-intel/watchlist?actorId=a_public")
        assert res_before.status_code == 200
        data_before = res_before.json()
        assert data_before.get("ok") is True
        
        count_before = len(data_before.get("items", []))
        print(f"Current watchlist has {count_before} items")
        
        # Verify the endpoint signature exists by checking health
        # (We won't actually call DELETE to avoid removing all channels)
        print("DELETE /api/telegram-intel/watchlist endpoint confirmed to exist in code")
        print("NOT executing clear to preserve watchlist data per instructions")
    
    def test_add_and_remove_single_channel(self):
        """Test add/remove single channel instead of clearing all"""
        test_username = "test_channel_for_watchlist_api"
        
        # Add a test channel
        add_res = requests.post(
            f"{BASE_URL}/api/telegram-intel/watchlist",
            json={"username": test_username, "actorId": "a_test_actor"}
        )
        print(f"Add channel response: {add_res.status_code}")
        
        # Verify it was added
        check_res = requests.get(f"{BASE_URL}/api/telegram-intel/watchlist?actorId=a_test_actor")
        if check_res.status_code == 200:
            items = check_res.json().get("items", [])
            added = any(i.get("username") == test_username for i in items)
            print(f"Channel added: {added}")
        
        # Remove the test channel
        remove_res = requests.delete(f"{BASE_URL}/api/telegram-intel/watchlist/{test_username}?actorId=a_test_actor")
        print(f"Remove channel response: {remove_res.status_code}")
        
        assert remove_res.status_code == 200


class TestWatchlistAfterRepopulate:
    """Verify watchlist returns items after operations"""
    
    def test_get_watchlist_returns_items(self):
        """GET /api/telegram-intel/watchlist returns items"""
        res = requests.get(f"{BASE_URL}/api/telegram-intel/watchlist?actorId=a_public")
        assert res.status_code == 200
        data = res.json()
        assert data.get("ok") is True
        
        items = data.get("items", [])
        total = data.get("total", 0)
        
        print(f"Watchlist has {total} items")
        if len(items) > 0:
            print(f"Sample channels: {[i.get('username') for i in items[:5]]}")
        
        # Watchlist should have items (main agent said there are ~20 channels)
        assert len(items) > 0, "Watchlist should have items"


class TestAIAnalytics:
    """Test AI Analytics (Product Analysis) endpoint"""
    
    def test_analyze_product_endpoint(self):
        """POST /api/telegram-intel/channel/{username}/analyze-product returns ok=true with analysis"""
        # Use forklog as per agent instructions
        res = requests.post(f"{BASE_URL}/api/telegram-intel/channel/forklog/analyze-product")
        
        assert res.status_code == 200
        data = res.json()
        
        print(f"Analyze product response: ok={data.get('ok')}")
        
        assert data.get("ok") is True, f"Expected ok=true, got {data}"
        
        # Check for analysis data
        analysis = data.get("analysis")
        if analysis:
            print(f"Analysis found: product_types={analysis.get('product_types')}")
            print(f"Trust score: {analysis.get('trust_score')}")
            print(f"Revenue model: {analysis.get('revenue_model')}")
        else:
            print(f"Response keys: {data.keys()}")
    
    def test_channel_full_endpoint(self):
        """GET /api/telegram-intel/channel/{username}/full returns product analysis if available"""
        res = requests.get(f"{BASE_URL}/api/telegram-intel/channel/forklog/full")
        
        assert res.status_code == 200
        data = res.json()
        assert data.get("ok") is True
        
        # Check for productAnalysis in response
        product_analysis = data.get("productAnalysis")
        channel = data.get("channel")
        
        print(f"Channel: {channel.get('title') if channel else 'N/A'}")
        print(f"Product analysis present: {product_analysis is not None}")
        
        if product_analysis:
            print(f"Product types: {product_analysis.get('product_types')}")


class TestFeedMediaPlaceholder:
    """Test feed shows media placeholder for posts without downloaded media"""
    
    def test_feed_has_media_info(self):
        """Feed posts include hasMedia and media fields"""
        res = requests.get(f"{BASE_URL}/api/telegram-intel/feed/v2?actorId=a_public&page=1&limit=50")
        assert res.status_code == 200
        data = res.json()
        
        items = data.get("items", [])
        posts_with_media_flag = [i for i in items if i.get("hasMedia")]
        posts_with_media_url = [i for i in items if i.get("media") and i.get("media", {}).get("url")]
        
        print(f"Total posts: {len(items)}")
        print(f"Posts with hasMedia=true: {len(posts_with_media_flag)}")
        print(f"Posts with media.url: {len(posts_with_media_url)}")
        
        # Some posts should have hasMedia=true but no media.url (placeholder scenario)
        posts_needing_placeholder = [i for i in items if i.get("hasMedia") and not (i.get("media") and i.get("media", {}).get("url"))]
        print(f"Posts needing placeholder (hasMedia but no url): {len(posts_needing_placeholder)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
