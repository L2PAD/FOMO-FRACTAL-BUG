"""
Telegram Intel Plugin API Tests
Tests the isolated Telegram Intelligence Module endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com').rstrip('/')
TIMEOUT = 60  # Longer timeout for external URL


class TestTelegramIntelHealth:
    """Health & Version endpoint tests"""
    
    def test_health_returns_ok(self):
        """GET /api/telegram-intel/health should return ok:true"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/health", timeout=TIMEOUT)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("module") == "telegram-intel"
        assert "version" in data
        print(f"PASS: health returns ok:true, module:{data['module']}, version:{data['version']}")
    
    def test_health_has_runtime_info(self):
        """Health endpoint should include runtime info"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/health", timeout=TIMEOUT)
        assert response.status_code == 200
        data = response.json()
        assert "runtime" in data
        assert "mode" in data["runtime"]
        assert data["runtime"]["mode"] in ["mock", "live"]
        print(f"PASS: health has runtime info, mode:{data['runtime']['mode']}")
    
    def test_version_returns_frozen(self):
        """GET /api/telegram-intel/version should return version 1.0.0 and frozen:true"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/version", timeout=TIMEOUT)
        assert response.status_code == 200
        data = response.json()
        assert data.get("version") == "1.0.0"
        assert data.get("frozen") is True
        assert data.get("module") == "telegram-intel"
        print(f"PASS: version returns 1.0.0, frozen:{data['frozen']}")


class TestTelegramIntelFeed:
    """Feed endpoint tests"""
    
    def test_feed_v2_returns_ok(self):
        """GET /api/telegram-intel/feed/v2 should return ok:true with items array"""
        response = requests.get(
            f"{BASE_URL}/api/telegram-intel/feed/v2",
            params={"actorId": "default", "page": 1, "limit": 10},
            timeout=TIMEOUT
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "items" in data
        assert isinstance(data["items"], list)
        assert "total" in data
        assert "page" in data
        print(f"PASS: feed/v2 returns ok:true, total:{data['total']}, page:{data['page']}")
    
    def test_feed_v2_pagination(self):
        """Feed should support pagination parameters"""
        response = requests.get(
            f"{BASE_URL}/api/telegram-intel/feed/v2",
            params={"actorId": "default", "page": 2, "limit": 5, "windowDays": 7},
            timeout=TIMEOUT
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "pages" in data
        print(f"PASS: feed/v2 supports pagination, pages:{data.get('pages')}")


class TestTelegramIntelUtility:
    """Channel/Utility list tests"""
    
    def test_utility_list_returns_ok(self):
        """GET /api/telegram-intel/utility/list should return ok:true with items array"""
        response = requests.get(
            f"{BASE_URL}/api/telegram-intel/utility/list",
            params={"limit": 10, "offset": 0},
            timeout=TIMEOUT
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "items" in data
        assert isinstance(data["items"], list)
        assert "total" in data
        print(f"PASS: utility/list returns ok:true, total:{data['total']}")


class TestTelegramIntelWatchlist:
    """Watchlist CRUD tests"""
    
    def test_watchlist_get_returns_ok(self):
        """GET /api/telegram-intel/watchlist should return ok:true with items array"""
        response = requests.get(
            f"{BASE_URL}/api/telegram-intel/watchlist",
            params={"actorId": "default"},
            timeout=TIMEOUT
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "items" in data
        assert isinstance(data["items"], list)
        print(f"PASS: watchlist returns ok:true, count:{data.get('total', len(data['items']))}")
    
    def test_watchlist_add(self):
        """POST /api/telegram-intel/watchlist should add channel to watchlist"""
        test_username = "TEST_pytest_channel"
        response = requests.post(
            f"{BASE_URL}/api/telegram-intel/watchlist",
            json={"username": test_username, "actorId": "a_public"},
            timeout=TIMEOUT
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("username") == test_username
        print(f"PASS: watchlist add ok:true, username:{test_username}")
        
        # Cleanup: remove the test channel
        cleanup = requests.delete(
            f"{BASE_URL}/api/telegram-intel/watchlist/{test_username}",
            params={"actorId": "a_public"},
            timeout=TIMEOUT
        )
        print(f"Cleanup: delete returned {cleanup.status_code}")


class TestTelegramIntelAlerts:
    """Alerts endpoint tests"""
    
    def test_alerts_returns_ok(self):
        """GET /api/telegram-intel/alerts should return ok:true with alerts array"""
        response = requests.get(
            f"{BASE_URL}/api/telegram-intel/alerts",
            params={"actorId": "default", "limit": 50},
            timeout=TIMEOUT
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "alerts" in data
        assert isinstance(data["alerts"], list)
        print(f"PASS: alerts returns ok:true, count:{data.get('count', len(data['alerts']))}")


class TestTelegramIntelBot:
    """Bot status tests"""
    
    def test_bot_status_returns_ok(self):
        """GET /api/telegram-intel/bot/status should return ok:true"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/bot/status", timeout=TIMEOUT)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        # Bot may not be configured but status should return
        assert "botConfigured" in data
        print(f"PASS: bot/status returns ok:true, configured:{data.get('botConfigured')}")


class TestCoreRegression:
    """Core app regression tests - ensure Telegram plugin doesn't break existing endpoints"""
    
    def test_system_health_still_works(self):
        """GET /api/system/health should still respond after Telegram plugin integration"""
        response = requests.get(f"{BASE_URL}/api/system/health", timeout=TIMEOUT)
        assert response.status_code == 200
        data = response.json()
        # Core system health has different structure but should return
        assert "status" in data or "ok" in data
        print(f"PASS: /api/system/health still works, status:{data.get('status', 'ok')}")
    
    def test_python_gateway_health(self):
        """GET /health should return Python gateway health"""
        response = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)
        assert response.status_code == 200
        data = response.json()
        assert data.get("service") == "python-gateway"
        assert data.get("status") == "ok"
        print(f"PASS: Python gateway health ok, node_backend:{data.get('node_backend')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
