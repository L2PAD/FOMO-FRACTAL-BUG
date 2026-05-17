"""
Prediction Telegram Delivery Module Tests

Tests for the Prediction Telegram Delivery system (separate from notification engine):
- POST /api/telegram-delivery/connect — creates prefs with defaults
- GET /api/telegram-delivery/stats — returns delivery stats
- POST /api/telegram-delivery/preferences — updates chatId preferences
- GET /api/telegram-delivery/subscribers — returns enabled subscribers
- POST /api/telegram-delivery/test — sends test alert
- POST /api/telegram-delivery/deliver — delivers alert to all subscribers
- POST /api/telegram-delivery/deliver-weekly — delivers weekly digest
- POST /api/telegram-delivery/flush-batch — flushes batch queue
- POST /api/telegram-delivery/disconnect — disables chatId
- POST /api/telegram-delivery/webhook — handles bot commands
- Python proxy routes via /api/prediction/telegram-delivery/*

Note: Actual Telegram message delivery will fail with 'chat not found' 
because test chatIds are not real Telegram chats. This is EXPECTED.
We test API structure, preferences CRUD, and endpoint responses.

MongoDB collection: intelligence_engine.prediction_telegram_prefs
"""

import pytest
import requests
import os
import time

# Use public URL for testing
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://expo-telegram-web.preview.emergentagent.com").rstrip("/")
TEST_CHAT_ID = f"TEST_pred_chat_{int(time.time())}"  # Unique test chatId


class TestPredictionTelegramConnect:
    """Tests for POST /api/telegram-delivery/connect"""

    def test_connect_creates_prefs_with_defaults(self):
        """Connect should create preferences with default values"""
        response = requests.post(
            f"{BASE_URL}/api/telegram-delivery/connect",
            json={"chatId": TEST_CHAT_ID},
            timeout=15
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Verify prefs object returned
        prefs = data.get("prefs", {})
        assert prefs.get("chatId") == TEST_CHAT_ID
        assert prefs.get("enabled") is True
        assert prefs.get("instantHighAlerts") is True
        assert prefs.get("batchDigest30m") is True
        assert prefs.get("weeklyDigest") is True
        assert prefs.get("highOnly") is False
        assert prefs.get("muteUntil") is None
        assert prefs.get("maxMessagesPerHour") == 10
        assert "createdAt" in prefs
        assert "updatedAt" in prefs
        print(f"✓ Connect created prefs with defaults for {TEST_CHAT_ID}")

    def test_connect_requires_chatid(self):
        """Connect should require chatId"""
        response = requests.post(
            f"{BASE_URL}/api/telegram-delivery/connect",
            json={},
            timeout=15
        )
        assert response.status_code == 200  # Returns ok=false, not 400
        data = response.json()
        assert data.get("ok") is False
        assert "chatid" in data.get("error", "").lower()  # Case-insensitive check
        print("✓ Connect requires chatId")

    def test_connect_idempotent(self):
        """Connect should be idempotent - same chatId returns same prefs"""
        # First connect
        resp1 = requests.post(
            f"{BASE_URL}/api/telegram-delivery/connect",
            json={"chatId": TEST_CHAT_ID},
            timeout=15
        )
        prefs1 = resp1.json().get("prefs", {})
        
        # Second connect
        resp2 = requests.post(
            f"{BASE_URL}/api/telegram-delivery/connect",
            json={"chatId": TEST_CHAT_ID},
            timeout=15
        )
        prefs2 = resp2.json().get("prefs", {})
        
        assert prefs1.get("chatId") == prefs2.get("chatId")
        assert prefs1.get("createdAt") == prefs2.get("createdAt")
        print("✓ Connect is idempotent")


class TestPredictionTelegramStats:
    """Tests for GET /api/telegram-delivery/stats"""

    def test_stats_returns_structure(self):
        """Stats should return total, last24h, subscribers, batchQueueSize"""
        response = requests.get(
            f"{BASE_URL}/api/telegram-delivery/stats",
            timeout=15
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True
        
        stats = data.get("stats", {})
        assert "total" in stats, "Missing 'total' in stats"
        assert "last24h" in stats, "Missing 'last24h' in stats"
        assert "subscribers" in stats, "Missing 'subscribers' in stats"
        assert "batchQueueSize" in stats, "Missing 'batchQueueSize' in stats"
        
        # All should be integers
        assert isinstance(stats["total"], int)
        assert isinstance(stats["last24h"], int)
        assert isinstance(stats["subscribers"], int)
        assert isinstance(stats["batchQueueSize"], int)
        
        print(f"✓ Stats returned: total={stats['total']}, last24h={stats['last24h']}, subscribers={stats['subscribers']}, batchQueueSize={stats['batchQueueSize']}")


class TestPredictionTelegramPreferences:
    """Tests for POST /api/telegram-delivery/preferences"""

    def test_update_highonly(self):
        """Should update highOnly preference"""
        response = requests.post(
            f"{BASE_URL}/api/telegram-delivery/preferences",
            json={"chatId": TEST_CHAT_ID, "highOnly": True},
            timeout=15
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        prefs = data.get("prefs", {})
        assert prefs.get("highOnly") is True
        print("✓ Updated highOnly to True")

    def test_update_batchdigest(self):
        """Should update batchDigest30m preference"""
        response = requests.post(
            f"{BASE_URL}/api/telegram-delivery/preferences",
            json={"chatId": TEST_CHAT_ID, "batchDigest30m": False},
            timeout=15
        )
        assert response.status_code == 200
        
        data = response.json()
        prefs = data.get("prefs", {})
        assert prefs.get("batchDigest30m") is False
        print("✓ Updated batchDigest30m to False")

    def test_update_weeklydigest(self):
        """Should update weeklyDigest preference"""
        response = requests.post(
            f"{BASE_URL}/api/telegram-delivery/preferences",
            json={"chatId": TEST_CHAT_ID, "weeklyDigest": False},
            timeout=15
        )
        assert response.status_code == 200
        
        data = response.json()
        prefs = data.get("prefs", {})
        assert prefs.get("weeklyDigest") is False
        print("✓ Updated weeklyDigest to False")

    def test_update_mute(self):
        """Should update muteUntil preference"""
        mute_until = int(time.time() * 1000) + 3600000  # 1 hour from now
        response = requests.post(
            f"{BASE_URL}/api/telegram-delivery/preferences",
            json={"chatId": TEST_CHAT_ID, "muteUntil": mute_until},
            timeout=15
        )
        assert response.status_code == 200
        
        data = response.json()
        prefs = data.get("prefs", {})
        assert prefs.get("muteUntil") == mute_until
        print(f"✓ Updated muteUntil to {mute_until}")

    def test_update_requires_chatid(self):
        """Should require chatId"""
        response = requests.post(
            f"{BASE_URL}/api/telegram-delivery/preferences",
            json={"highOnly": True},
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is False
        print("✓ Preferences update requires chatId")


class TestPredictionTelegramSubscribers:
    """Tests for GET /api/telegram-delivery/subscribers"""

    def test_subscribers_returns_list(self):
        """Should return list of enabled subscribers"""
        # First ensure our test subscriber is connected and enabled
        requests.post(
            f"{BASE_URL}/api/telegram-delivery/connect",
            json={"chatId": TEST_CHAT_ID},
            timeout=15
        )
        requests.post(
            f"{BASE_URL}/api/telegram-delivery/preferences",
            json={"chatId": TEST_CHAT_ID, "enabled": True},
            timeout=15
        )
        
        response = requests.get(
            f"{BASE_URL}/api/telegram-delivery/subscribers",
            timeout=15
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "count" in data
        assert "subscribers" in data
        assert isinstance(data["subscribers"], list)
        
        # Our test subscriber should be in the list
        chat_ids = [s.get("chatId") for s in data["subscribers"]]
        assert TEST_CHAT_ID in chat_ids, f"Test chatId {TEST_CHAT_ID} not in subscribers"
        print(f"✓ Subscribers returned: count={data['count']}")


class TestPredictionTelegramTest:
    """Tests for POST /api/telegram-delivery/test"""

    def test_send_test_alert(self):
        """Should attempt to send test alert (will fail with chat not found - expected)"""
        response = requests.post(
            f"{BASE_URL}/api/telegram-delivery/test",
            json={"chatId": TEST_CHAT_ID, "type": "ENTRY_ALERT"},
            timeout=15
        )
        assert response.status_code == 200
        
        data = response.json()
        # ok can be True or False depending on Telegram API response
        # With fake chatId, it will be False (chat not found) - this is expected
        assert "ok" in data
        assert "message" in data or "error" in data
        print(f"✓ Test alert endpoint responded: ok={data.get('ok')}, message={data.get('message', data.get('error', 'N/A'))}")

    def test_test_requires_chatid(self):
        """Should require chatId"""
        response = requests.post(
            f"{BASE_URL}/api/telegram-delivery/test",
            json={"type": "ENTRY_ALERT"},
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is False
        print("✓ Test alert requires chatId")


class TestPredictionTelegramDeliver:
    """Tests for POST /api/telegram-delivery/deliver"""

    def test_deliver_alert(self):
        """Should attempt to deliver alert to all subscribers"""
        payload = {
            "type": "ENTRY_ALERT",
            "priority": "HIGH",
            "title": "Test Entry Alert",
            "body": "This is a test entry alert",
            "asset": "BTC",
            "marketId": "test_market_123",
            "meta": {
                "asset": "BTC",
                "question": "Will BTC reach 100k?",
                "action": "YES_NOW",
                "edge": 0.11,
                "confidence": 0.68,
                "conviction": "HIGH"
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/telegram-delivery/deliver",
            json=payload,
            timeout=15
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "sent" in data
        assert "suppressed" in data
        assert isinstance(data["sent"], int)
        assert isinstance(data["suppressed"], int)
        print(f"✓ Deliver alert: sent={data['sent']}, suppressed={data['suppressed']}")

    def test_deliver_requires_type(self):
        """Should require type in payload"""
        response = requests.post(
            f"{BASE_URL}/api/telegram-delivery/deliver",
            json={"priority": "HIGH", "title": "Test"},
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is False
        assert "type" in data.get("error", "").lower()
        print("✓ Deliver requires type")


class TestPredictionTelegramWeekly:
    """Tests for POST /api/telegram-delivery/deliver-weekly"""

    def test_deliver_weekly_digest(self):
        """Should attempt to deliver weekly digest"""
        digest_data = {
            "period": {"from": "2025-01-01", "to": "2025-01-07"},
            "summary": {
                "totalCases": 50,
                "accuracy": 0.72,
                "avgEdge": 0.08
            },
            "topWins": [
                {"asset": "BTC", "edge": 0.15, "outcome": "WIN"}
            ],
            "lessons": ["Lesson 1", "Lesson 2"]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/telegram-delivery/deliver-weekly",
            json=digest_data,
            timeout=15
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "sent" in data
        assert isinstance(data["sent"], int)
        print(f"✓ Weekly digest delivery: sent={data['sent']}")


class TestPredictionTelegramFlushBatch:
    """Tests for POST /api/telegram-delivery/flush-batch"""

    def test_flush_batch(self):
        """Should flush batch queue"""
        response = requests.post(
            f"{BASE_URL}/api/telegram-delivery/flush-batch",
            timeout=15
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "sent" in data
        assert isinstance(data["sent"], int)
        print(f"✓ Batch flush: sent={data['sent']}")


class TestPredictionTelegramWebhook:
    """Tests for POST /api/telegram-delivery/webhook"""

    def test_webhook_predictions_command(self):
        """Should handle /predictions command"""
        update = {
            "message": {
                "chat": {"id": 123456789},
                "text": "/predictions"
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/telegram-delivery/webhook",
            json=update,
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print("✓ Webhook handled /predictions command")

    def test_webhook_pred_status_command(self):
        """Should handle /pred_status command"""
        update = {
            "message": {
                "chat": {"id": 123456789},
                "text": "/pred_status"
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/telegram-delivery/webhook",
            json=update,
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print("✓ Webhook handled /pred_status command")

    def test_webhook_high_only_command(self):
        """Should handle /high_only command"""
        update = {
            "message": {
                "chat": {"id": 123456789},
                "text": "/high_only"
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/telegram-delivery/webhook",
            json=update,
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print("✓ Webhook handled /high_only command")

    def test_webhook_mute_command(self):
        """Should handle /mute_1h command"""
        update = {
            "message": {
                "chat": {"id": 123456789},
                "text": "/mute_1h"
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/telegram-delivery/webhook",
            json=update,
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print("✓ Webhook handled /mute_1h command")

    def test_webhook_empty_message(self):
        """Should handle empty/invalid webhook gracefully"""
        response = requests.post(
            f"{BASE_URL}/api/telegram-delivery/webhook",
            json={},
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print("✓ Webhook handled empty message gracefully")


class TestPredictionTelegramDisconnect:
    """Tests for POST /api/telegram-delivery/disconnect"""

    def test_disconnect_disables_subscriber(self):
        """Should set enabled=false for chatId"""
        response = requests.post(
            f"{BASE_URL}/api/telegram-delivery/disconnect",
            json={"chatId": TEST_CHAT_ID},
            timeout=15
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "Disconnected" in data.get("message", "")
        print(f"✓ Disconnected {TEST_CHAT_ID}")

    def test_disconnect_removes_from_subscribers(self):
        """After disconnect, chatId should not be in enabled subscribers"""
        # First disconnect
        requests.post(
            f"{BASE_URL}/api/telegram-delivery/disconnect",
            json={"chatId": TEST_CHAT_ID},
            timeout=15
        )
        
        # Check subscribers
        response = requests.get(
            f"{BASE_URL}/api/telegram-delivery/subscribers",
            timeout=15
        )
        data = response.json()
        chat_ids = [s.get("chatId") for s in data.get("subscribers", [])]
        assert TEST_CHAT_ID not in chat_ids, f"Disconnected chatId {TEST_CHAT_ID} still in subscribers"
        print("✓ Disconnected chatId not in subscribers list")


class TestPythonProxyRoutes:
    """Tests for Python proxy routes at /api/prediction/telegram-delivery/*"""

    def test_proxy_connect(self):
        """Python proxy: POST /api/prediction/telegram-delivery/connect"""
        proxy_chat_id = f"TEST_proxy_{int(time.time())}"
        response = requests.post(
            f"{BASE_URL}/api/prediction/telegram-delivery/connect",
            json={"chatId": proxy_chat_id},
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("prefs", {}).get("chatId") == proxy_chat_id
        print(f"✓ Python proxy connect works for {proxy_chat_id}")

    def test_proxy_stats(self):
        """Python proxy: GET /api/prediction/telegram-delivery/stats"""
        response = requests.get(
            f"{BASE_URL}/api/prediction/telegram-delivery/stats",
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "stats" in data
        print("✓ Python proxy stats works")

    def test_proxy_subscribers(self):
        """Python proxy: GET /api/prediction/telegram-delivery/subscribers"""
        response = requests.get(
            f"{BASE_URL}/api/prediction/telegram-delivery/subscribers",
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "subscribers" in data
        print("✓ Python proxy subscribers works")

    def test_proxy_test_alert(self):
        """Python proxy: POST /api/prediction/telegram-delivery/test"""
        response = requests.post(
            f"{BASE_URL}/api/prediction/telegram-delivery/test",
            json={"chatId": "test_proxy_123", "type": "ENTRY_ALERT"},
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        assert "ok" in data
        print("✓ Python proxy test alert works")

    def test_proxy_preferences(self):
        """Python proxy: POST /api/prediction/telegram-delivery/preferences"""
        response = requests.post(
            f"{BASE_URL}/api/prediction/telegram-delivery/preferences",
            json={"chatId": "test_proxy_123", "highOnly": True},
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print("✓ Python proxy preferences works")

    def test_proxy_deliver(self):
        """Python proxy: POST /api/prediction/telegram-delivery/deliver"""
        payload = {
            "type": "ENTRY_ALERT",
            "priority": "HIGH",
            "title": "Proxy Test",
            "body": "Test via proxy"
        }
        response = requests.post(
            f"{BASE_URL}/api/prediction/telegram-delivery/deliver",
            json=payload,
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print("✓ Python proxy deliver works")

    def test_proxy_deliver_weekly(self):
        """Python proxy: POST /api/prediction/telegram-delivery/deliver-weekly"""
        digest_data = {
            "period": {"from": "2025-01-01", "to": "2025-01-07"},
            "summary": {"totalCases": 10}
        }
        response = requests.post(
            f"{BASE_URL}/api/prediction/telegram-delivery/deliver-weekly",
            json=digest_data,
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print("✓ Python proxy deliver-weekly works")


class TestPreferencesSystem:
    """Tests for the preferences system behavior"""

    def test_connect_creates_defaults_then_update_modifies(self):
        """Connect creates defaults, update modifies specific fields"""
        unique_chat = f"TEST_prefs_{int(time.time())}"
        
        # Connect creates defaults
        resp1 = requests.post(
            f"{BASE_URL}/api/telegram-delivery/connect",
            json={"chatId": unique_chat},
            timeout=15
        )
        prefs1 = resp1.json().get("prefs", {})
        assert prefs1.get("highOnly") is False
        assert prefs1.get("weeklyDigest") is True
        
        # Update only highOnly
        resp2 = requests.post(
            f"{BASE_URL}/api/telegram-delivery/preferences",
            json={"chatId": unique_chat, "highOnly": True},
            timeout=15
        )
        prefs2 = resp2.json().get("prefs", {})
        assert prefs2.get("highOnly") is True
        assert prefs2.get("weeklyDigest") is True  # Unchanged
        
        # Update only weeklyDigest
        resp3 = requests.post(
            f"{BASE_URL}/api/telegram-delivery/preferences",
            json={"chatId": unique_chat, "weeklyDigest": False},
            timeout=15
        )
        prefs3 = resp3.json().get("prefs", {})
        assert prefs3.get("highOnly") is True  # Still True
        assert prefs3.get("weeklyDigest") is False  # Now False
        
        print("✓ Preferences system: connect creates defaults, update modifies specific fields")

    def test_mute_works_with_muteuntil_timestamp(self):
        """Mute works with muteUntil timestamp"""
        unique_chat = f"TEST_mute_{int(time.time())}"
        
        # Connect
        requests.post(
            f"{BASE_URL}/api/telegram-delivery/connect",
            json={"chatId": unique_chat},
            timeout=15
        )
        
        # Set mute
        mute_until = int(time.time() * 1000) + 7200000  # 2 hours from now
        resp = requests.post(
            f"{BASE_URL}/api/telegram-delivery/preferences",
            json={"chatId": unique_chat, "muteUntil": mute_until},
            timeout=15
        )
        prefs = resp.json().get("prefs", {})
        assert prefs.get("muteUntil") == mute_until
        
        # Clear mute
        resp2 = requests.post(
            f"{BASE_URL}/api/telegram-delivery/preferences",
            json={"chatId": unique_chat, "muteUntil": None},
            timeout=15
        )
        prefs2 = resp2.json().get("prefs", {})
        assert prefs2.get("muteUntil") is None
        
        print("✓ Mute works with muteUntil timestamp")


class TestGetPreferences:
    """Tests for GET /api/telegram-delivery/preferences/:chatId"""

    def test_get_preferences_existing(self):
        """Should return preferences for existing chatId"""
        # First create
        unique_chat = f"TEST_getprefs_{int(time.time())}"
        requests.post(
            f"{BASE_URL}/api/telegram-delivery/connect",
            json={"chatId": unique_chat},
            timeout=15
        )
        
        # Then get
        response = requests.get(
            f"{BASE_URL}/api/telegram-delivery/preferences/{unique_chat}",
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        prefs = data.get("prefs", {})
        assert prefs.get("chatId") == unique_chat
        print(f"✓ GET preferences works for {unique_chat}")

    def test_get_preferences_nonexistent(self):
        """Should return null prefs for non-existent chatId"""
        response = requests.get(
            f"{BASE_URL}/api/telegram-delivery/preferences/nonexistent_chat_xyz",
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("prefs") is None
        print("✓ GET preferences returns null for non-existent chatId")


# Cleanup fixture
@pytest.fixture(scope="module", autouse=True)
def cleanup_test_data():
    """Cleanup TEST_ prefixed data after tests"""
    yield
    # Note: In production, we'd delete test data here
    # For now, test data with TEST_ prefix remains for inspection
    print(f"\n[Cleanup] Test data with prefix TEST_ created during testing")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
