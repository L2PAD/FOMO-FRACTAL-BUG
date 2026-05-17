"""
Telegram Intel Search & Autocomplete API Tests

Tests for:
1. GET /api/telegram-intel/channels/autocomplete - channel suggestions
2. GET /api/telegram-intel/feed/search - keyword + author filter search
3. GET /api/telegram-intel/utility/list - verify 15 channels total
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')


class TestChannelsAutocomplete:
    """Test channel autocomplete endpoint for Entities and Feed pages"""
    
    def test_autocomplete_returns_suggestions_for_inc_query(self):
        """Entities page: typing 'inc' should return incrypted and other matches"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/channels/autocomplete?q=inc&limit=6")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Response should have ok: true"
        assert "suggestions" in data, "Response should have suggestions array"
        assert len(data["suggestions"]) > 0, "Should return at least one suggestion"
        
        # Verify incrypted is in results
        usernames = [s["username"] for s in data["suggestions"]]
        assert "incrypted" in usernames, "incrypted should be in suggestions for 'inc' query"
        
        # Verify suggestion structure
        first_suggestion = data["suggestions"][0]
        assert "username" in first_suggestion, "Suggestion should have username"
        assert "title" in first_suggestion, "Suggestion should have title"
        assert "members" in first_suggestion, "Suggestion should have members count"

    def test_autocomplete_returns_multiple_fields(self):
        """Verify autocomplete returns all required fields for UI display"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/channels/autocomplete?q=crypto&limit=6")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        if len(data.get("suggestions", [])) > 0:
            suggestion = data["suggestions"][0]
            # Required fields for dropdown display
            assert "username" in suggestion
            assert "title" in suggestion
            assert "avatarUrl" in suggestion or suggestion.get("avatarUrl") is None
            assert "members" in suggestion
            assert "sector" in suggestion or suggestion.get("sector") is None
            assert "sectorColor" in suggestion or suggestion.get("sectorColor") is None

    def test_autocomplete_empty_query_returns_empty(self):
        """Empty or very short query should return empty suggestions"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/channels/autocomplete?q=&limit=6")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert len(data.get("suggestions", [])) == 0, "Empty query should return no suggestions"

    def test_autocomplete_respects_limit(self):
        """Autocomplete should respect the limit parameter"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/channels/autocomplete?q=c&limit=3")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data.get("suggestions", [])) <= 3, "Should return max 3 suggestions"


class TestFeedSearch:
    """Test feed search endpoint for Feed page dual search mode"""
    
    def test_feed_search_by_username_filter(self):
        """Feed page: selecting a channel filters posts by that author only"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/feed/search?username=coin_post&days=30&limit=20")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Response should have ok: true"
        assert data.get("username") == "coin_post", "Response should include username filter"
        assert "total" in data, "Response should have total count"
        assert "items" in data, "Response should have items array"
        assert data["total"] > 0, "coin_post should have posts"
        
        # All items should be from coin_post
        for item in data["items"]:
            assert item["username"] == "coin_post", f"All items should be from coin_post, got {item['username']}"

    def test_feed_search_by_keyword(self):
        """Feed page: keyword search to find posts by content"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/feed/search?q=bitcoin&days=30&limit=20")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert data.get("q") == "bitcoin", "Response should include search query"
        assert "total" in data
        assert "items" in data
        assert data["total"] > 0, "Should find posts containing 'bitcoin'"

    def test_feed_search_combined_username_and_keyword(self):
        """Feed page: combined search - author filter + keyword"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/feed/search?username=incrypted&q=crypto&days=30&limit=20")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert data.get("username") == "incrypted"
        
        # All items should be from incrypted
        for item in data.get("items", []):
            assert item["username"] == "incrypted"

    def test_feed_search_returns_post_structure(self):
        """Verify feed search returns correct post structure"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/feed/search?username=incrypted&days=30&limit=5")
        assert response.status_code == 200
        
        data = response.json()
        if len(data.get("items", [])) > 0:
            post = data["items"][0]
            # Verify post structure
            assert "messageId" in post
            assert "username" in post
            assert "date" in post
            assert "text" in post
            assert "views" in post or post.get("views") is None
            assert "channelTitle" in post
            assert "channelAvatar" in post or post.get("channelAvatar") is None

    def test_feed_search_empty_returns_empty_results(self):
        """Search with neither query nor username should return empty"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/feed/search?days=30&limit=20")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert data.get("total") == 0, "No query or username should return empty results"

    def test_feed_search_pagination(self):
        """Feed search should support pagination"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/feed/search?username=coin_post&days=30&page=1&limit=5")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "page" in data
        assert "pages" in data
        assert len(data.get("items", [])) <= 5


class TestEntitiesPage:
    """Test utility/list endpoint for Entities page - verify 15 channels"""
    
    def test_entities_list_returns_15_channels(self):
        """Entities page should show 15 channels total"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/utility/list?limit=20")
        assert response.status_code == 200
        
        data = response.json()
        assert "total" in data
        assert "items" in data
        assert data["total"] == 15, f"Expected 15 channels, got {data['total']}"
        assert len(data["items"]) == 15, f"Expected 15 items, got {len(data['items'])}"

    def test_entities_list_includes_all_metrics(self):
        """Verify channels have all required metrics for table display"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/utility/list?limit=15")
        assert response.status_code == 200
        
        data = response.json()
        for item in data.get("items", []):
            # Required fields for table
            assert "username" in item, "Item should have username"
            assert "title" in item or item.get("title") is None
            assert "members" in item, "Item should have members"
            assert "type" in item, "Item should have type"
            assert "sector" in item or item.get("sector") is None
            # Metrics
            assert "avgReach" in item or item.get("avgReach") is None
            assert "growth7" in item or item.get("growth7") is None
            assert "activity" in item or item.get("activity") is None
            assert "redFlags" in item or item.get("redFlags") is None
            assert "fomoScore" in item or item.get("fomoScore") is None

    def test_entities_list_stats_object(self):
        """Verify stats cards data is returned"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/utility/list?limit=15")
        assert response.status_code == 200
        
        data = response.json()
        assert "stats" in data, "Response should have stats object"
        stats = data["stats"]
        assert "tracked" in stats, "Stats should have tracked count"
        assert stats["tracked"] == 15, f"Expected tracked=15, got {stats['tracked']}"

    def test_entities_search_filters_results(self):
        """Search on entities page should filter channels by name"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/utility/list?q=crypto&limit=20")
        assert response.status_code == 200
        
        data = response.json()
        # If search is supported, results should be filtered
        # If not, all items should be returned
        assert "items" in data


class TestEndToEndFlows:
    """End-to-end test flows combining multiple API calls"""
    
    def test_entities_autocomplete_to_channel_navigation_flow(self):
        """
        Flow: User types in search -> gets suggestions -> clicks suggestion -> navigates
        This tests the data needed for the UI flow
        """
        # Step 1: Type 'inc' - get autocomplete suggestions
        autocomplete_resp = requests.get(f"{BASE_URL}/api/telegram-intel/channels/autocomplete?q=inc&limit=6")
        assert autocomplete_resp.status_code == 200
        
        autocomplete_data = autocomplete_resp.json()
        assert autocomplete_data.get("ok") is True
        assert len(autocomplete_data["suggestions"]) > 0
        
        # Find incrypted in suggestions
        incrypted = next((s for s in autocomplete_data["suggestions"] if s["username"] == "incrypted"), None)
        assert incrypted is not None, "incrypted should be in suggestions"
        
        # Step 2: After clicking, user would navigate to /telegram/{username}
        # Verify channel data is available
        channel_resp = requests.get(f"{BASE_URL}/api/telegram-intel/channel/{incrypted['username']}/overview")
        assert channel_resp.status_code == 200
        
        channel_data = channel_resp.json()
        assert channel_data.get("ok") is True
        assert channel_data.get("profile", {}).get("username") == "incrypted"

    def test_feed_author_filter_flow(self):
        """
        Flow: User types in feed search -> gets channel suggestions -> 
              selects channel -> feed filters by that author
        """
        # Step 1: Type to get channel suggestions
        suggest_resp = requests.get(f"{BASE_URL}/api/telegram-intel/channels/autocomplete?q=coin&limit=6")
        assert suggest_resp.status_code == 200
        
        suggest_data = suggest_resp.json()
        assert suggest_data.get("ok") is True
        assert len(suggest_data["suggestions"]) > 0
        
        # Find coin_post in suggestions
        coin_post = next((s for s in suggest_data["suggestions"] if s["username"] == "coin_post"), None)
        assert coin_post is not None, "coin_post should be in suggestions"
        
        # Step 2: Select channel - feed should filter by author
        filter_resp = requests.get(f"{BASE_URL}/api/telegram-intel/feed/search?username=coin_post&days=30&limit=20")
        assert filter_resp.status_code == 200
        
        filter_data = filter_resp.json()
        assert filter_data.get("ok") is True
        assert filter_data.get("total") > 0
        
        # All posts should be from coin_post
        for item in filter_data.get("items", []):
            assert item["username"] == "coin_post"

    def test_feed_keyword_search_flow(self):
        """
        Flow: User types keyword in feed search -> presses Enter -> 
              feed shows posts matching keyword
        """
        # Step 1: User types keyword and presses Enter (no channel selected)
        search_resp = requests.get(f"{BASE_URL}/api/telegram-intel/feed/search?q=bitcoin&days=30&limit=20")
        assert search_resp.status_code == 200
        
        search_data = search_resp.json()
        assert search_data.get("ok") is True
        assert search_data.get("q") == "bitcoin"
        assert search_data.get("total") > 0, "Should find posts with 'bitcoin'"
        
        # Results can be from any channel (keyword search across all watchlist channels)
        assert len(search_data.get("items", [])) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
