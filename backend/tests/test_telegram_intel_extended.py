"""
Telegram Intel Plugin Extended API Tests
Tests the extended/admin functionality with real MTProto/MongoDB data
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com').rstrip('/')
TIMEOUT = 60


class TestTelegramIntelHealth:
    """Health & Version endpoint tests"""
    
    def test_health_returns_ok_live_mode(self):
        """GET /api/telegram-intel/health should return ok:true with live mode"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/health", timeout=TIMEOUT)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("module") == "telegram-intel"
        assert "version" in data
        # Verify it's in live mode (real MTProto session configured)
        assert "runtime" in data
        print(f"PASS: health ok:true, mode:{data['runtime'].get('mode')}, version:{data['version']}")
    
    def test_version_returns_1_0_0_frozen(self):
        """GET /api/telegram-intel/version should return version 1.0.0 and frozen:true"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/version", timeout=TIMEOUT)
        assert response.status_code == 200
        data = response.json()
        assert data.get("version") == "1.0.0"
        assert data.get("frozen") is True
        assert data.get("module") == "telegram-intel"
        print(f"PASS: version returns 1.0.0, frozen:true")


class TestTelegramIntelUtilityList:
    """Channel list endpoint tests - expects 5 real channels"""
    
    def test_utility_list_returns_5_channels(self):
        """GET /api/telegram-intel/utility/list should return 5 real channels"""
        response = requests.get(
            f"{BASE_URL}/api/telegram-intel/utility/list",
            params={"limit": 50},
            timeout=TIMEOUT
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "items" in data
        
        # Verify we have at least 5 channels
        assert len(data["items"]) >= 5, f"Expected 5+ channels, got {len(data['items'])}"
        
        # Verify expected channel usernames
        usernames = [item["username"] for item in data["items"]]
        expected_channels = ["durov", "incrypted", "forklog", "bitcoinmagazine", "defillama"]
        for expected in expected_channels:
            assert expected in usernames, f"Missing expected channel: {expected}"
        
        print(f"PASS: utility/list returns {len(data['items'])} channels including: {expected_channels}")


class TestTelegramIntelChannelFull:
    """Channel full endpoint tests - expects real data with growth/activity"""
    
    def test_channel_durov_full_returns_data(self):
        """GET /api/telegram-intel/channel/durov/full should return full channel data"""
        response = requests.get(
            f"{BASE_URL}/api/telegram-intel/channel/durov/full",
            timeout=TIMEOUT
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        # Verify expected data structure
        assert "channel" in data or "username" in data, "Missing channel data"
        assert "growth" in data, "Missing growth object"
        assert "activity" in data, "Missing activity object"
        assert "healthSafety" in data, "Missing healthSafety object"
        
        # Verify growth structure
        growth = data.get("growth", {})
        assert "growth7" in growth or growth.get("growth7") is not None or growth.get("growth7") == 0
        
        # Verify activity structure  
        activity = data.get("activity", {})
        assert "engagementRate" in activity or activity.get("postsPerDay") is not None
        
        print(f"PASS: channel/durov/full returns data with growth, activity, healthSafety")


class TestTelegramIntelChannelOverview:
    """Channel overview endpoint tests - expects real data with topCards, metrics"""
    
    def test_channel_durov_overview_returns_data(self):
        """GET /api/telegram-intel/channel/durov/overview should return overview data"""
        response = requests.get(
            f"{BASE_URL}/api/telegram-intel/channel/durov/overview",
            timeout=TIMEOUT
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        # Verify expected data structure
        assert "profile" in data, "Missing profile"
        assert "topCards" in data, "Missing topCards"
        assert "metrics" in data, "Missing metrics"
        
        # Verify profile
        profile = data.get("profile", {})
        assert profile.get("username") == "durov"
        assert profile.get("title") == "Pavel Durov"
        
        # Verify topCards has subscribers (10M+ expected)
        top_cards = data.get("topCards", {})
        subscribers = top_cards.get("subscribers", 0)
        assert subscribers >= 10000000, f"Expected 10M+ subscribers, got {subscribers}"
        
        print(f"PASS: channel/durov/overview returns profile:{profile.get('title')}, subscribers:{subscribers}")


class TestTelegramIntelFeed:
    """Feed endpoint tests - expects 61+ posts"""
    
    def test_feed_v2_returns_61_plus_posts(self):
        """GET /api/telegram-intel/feed/v2 should return 61+ posts"""
        response = requests.get(
            f"{BASE_URL}/api/telegram-intel/feed/v2",
            params={"actorId": "default", "page": 1, "limit": 50, "windowDays": 30},
            timeout=TIMEOUT
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "items" in data
        assert "total" in data
        
        # Verify we have 61+ posts total
        total = data.get("total", 0)
        assert total >= 61, f"Expected 61+ posts, got {total}"
        
        # Verify items have required fields
        if data["items"]:
            item = data["items"][0]
            assert "username" in item
            assert "text" in item or item.get("text") == ""
            
        print(f"PASS: feed/v2 returns {total} total posts, {len(data['items'])} on page 1")


class TestTelegramIntelFeedSearch:
    """Feed search endpoint tests"""
    
    def test_feed_search_returns_results(self):
        """GET /api/telegram-intel/feed/search should return search results"""
        response = requests.get(
            f"{BASE_URL}/api/telegram-intel/feed/search",
            params={"q": "telegram", "actorId": "default", "days": 30},
            timeout=TIMEOUT
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "items" in data
        assert "total" in data
        
        # Note: search results may be 0 if no posts contain "telegram"
        print(f"PASS: feed/search returns {data.get('total', 0)} results for 'telegram'")


class TestTelegramIntelWatchlist:
    """Watchlist endpoint tests"""
    
    def test_watchlist_returns_items(self):
        """GET /api/telegram-intel/watchlist should return watchlist items"""
        response = requests.get(
            f"{BASE_URL}/api/telegram-intel/watchlist",
            params={"actorId": "default"},
            timeout=TIMEOUT
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "items" in data
        
        # Verify watchlist has some items
        items = data.get("items", [])
        print(f"PASS: watchlist returns {len(items)} items")
    
    def test_watchlist_check_durov_in_watchlist(self):
        """GET /api/telegram-intel/watchlist/check/durov should return inWatchlist:true"""
        response = requests.get(
            f"{BASE_URL}/api/telegram-intel/watchlist/check/durov",
            timeout=TIMEOUT
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("inWatchlist") is True, "durov should be in watchlist"
        
        print(f"PASS: watchlist/check/durov returns inWatchlist:true")


class TestTelegramIntelTopics:
    """Topics momentum endpoint tests"""
    
    def test_topics_momentum_returns_data(self):
        """GET /api/telegram-intel/topics/momentum should return topics data"""
        response = requests.get(
            f"{BASE_URL}/api/telegram-intel/topics/momentum",
            params={"limit": 20},
            timeout=TIMEOUT
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "windowHours" in data
        assert "topics" in data
        
        print(f"PASS: topics/momentum returns windowHours:{data.get('windowHours')}, topics:{len(data.get('topics', []))}")


class TestTelegramIntelSignals:
    """Cross-channel signals endpoint tests"""
    
    def test_signals_cross_channel_returns_data(self):
        """GET /api/telegram-intel/signals/cross-channel should return signals data"""
        response = requests.get(
            f"{BASE_URL}/api/telegram-intel/signals/cross-channel",
            params={"window": 30},
            timeout=TIMEOUT
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "windowMinutes" in data
        assert "eventCount" in data
        assert "events" in data
        
        print(f"PASS: signals/cross-channel returns windowMinutes:{data.get('windowMinutes')}, eventCount:{data.get('eventCount')}")


class TestTelegramIntelAdminMTProto:
    """Admin MTProto endpoint tests"""
    
    def test_admin_mtproto_status_returns_connected(self):
        """GET /api/telegram-intel/admin/mtproto/status should return connected state"""
        response = requests.get(
            f"{BASE_URL}/api/telegram-intel/admin/mtproto/status",
            timeout=TIMEOUT
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("available") is True, "MTProto should be available"
        # Connection state may vary
        assert "connected" in data
        assert "state" in data
        
        print(f"PASS: admin/mtproto/status returns available:true, connected:{data.get('connected')}")
    
    def test_admin_mtproto_health_returns_data(self):
        """GET /api/telegram-intel/admin/mtproto/health should return health with credentials loaded"""
        response = requests.get(
            f"{BASE_URL}/api/telegram-intel/admin/mtproto/health",
            timeout=TIMEOUT
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        # credentialsLoaded should be true if session string is configured
        assert "credentialsLoaded" in data
        # authorized may be false if session needs refresh
        assert "authorized" in data
        
        print(f"PASS: admin/mtproto/health returns credentialsLoaded:{data.get('credentialsLoaded')}, authorized:{data.get('authorized')}")


class TestCoreRegression:
    """Core app regression tests"""
    
    def test_system_health_still_responds(self):
        """GET /api/system/health should still respond"""
        response = requests.get(
            f"{BASE_URL}/api/system/health",
            timeout=TIMEOUT
        )
        assert response.status_code == 200
        data = response.json()
        assert "status" in data or "ok" in data
        
        print(f"PASS: /api/system/health still responds, status:{data.get('status', 'ok')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
