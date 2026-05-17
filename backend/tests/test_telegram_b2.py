"""
B.2 - Telegram UX Polish Tests
Tests for Telegram notification settings endpoints:
- GET /api/v4/twitter/telegram/status
- POST /api/v4/twitter/telegram/disconnect
- GET /api/v4/twitter/telegram/events
- PUT /api/v4/twitter/telegram/events
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestTelegramStatus:
    """GET /api/v4/twitter/telegram/status tests"""
    
    def test_status_returns_ok(self):
        """Status endpoint returns ok: true"""
        response = requests.get(f"{BASE_URL}/api/v4/twitter/telegram/status")
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] == True
        assert 'data' in data
    
    def test_status_contains_connected_field(self):
        """Status contains connected boolean"""
        response = requests.get(f"{BASE_URL}/api/v4/twitter/telegram/status")
        data = response.json()
        assert 'connected' in data['data']
        assert isinstance(data['data']['connected'], bool)
    
    def test_status_contains_username_when_connected(self):
        """Status contains username when connected"""
        response = requests.get(f"{BASE_URL}/api/v4/twitter/telegram/status")
        data = response.json()
        if data['data']['connected']:
            assert 'username' in data['data']
    
    def test_status_contains_event_preferences(self):
        """Status contains eventPreferences object"""
        response = requests.get(f"{BASE_URL}/api/v4/twitter/telegram/status")
        data = response.json()
        if data['data']['connected']:
            assert 'eventPreferences' in data['data']
            prefs = data['data']['eventPreferences']
            # Check all 7 event types
            expected_keys = ['sessionOk', 'sessionStale', 'sessionInvalid', 
                           'parseCompleted', 'parseAborted', 'cooldown', 'highRisk']
            for key in expected_keys:
                assert key in prefs, f"Missing key: {key}"
                assert isinstance(prefs[key], bool), f"{key} should be boolean"
    
    def test_status_chatid_is_masked(self):
        """ChatId is masked for security (shows ***XXXX)"""
        response = requests.get(f"{BASE_URL}/api/v4/twitter/telegram/status")
        data = response.json()
        if data['data'].get('chatId'):
            assert data['data']['chatId'].startswith('***')


class TestTelegramEvents:
    """GET/PUT /api/v4/twitter/telegram/events tests"""
    
    def test_get_events_returns_preferences(self):
        """GET events returns current preferences"""
        response = requests.get(f"{BASE_URL}/api/v4/twitter/telegram/events")
        # May return 400 if not connected
        if response.status_code == 200:
            data = response.json()
            assert data['ok'] == True
            assert 'data' in data
            # Check all 7 event types
            expected_keys = ['sessionOk', 'sessionStale', 'sessionInvalid', 
                           'parseCompleted', 'parseAborted', 'cooldown', 'highRisk']
            for key in expected_keys:
                assert key in data['data']
        elif response.status_code == 400:
            data = response.json()
            assert data['error'] == 'NO_CONNECTION'
    
    def test_put_events_updates_single_preference(self):
        """PUT events updates a single preference"""
        # First get current state
        status_resp = requests.get(f"{BASE_URL}/api/v4/twitter/telegram/status")
        if not status_resp.json()['data'].get('connected'):
            pytest.skip("Telegram not connected")
        
        # Get current parseCompleted value
        events_resp = requests.get(f"{BASE_URL}/api/v4/twitter/telegram/events")
        current_value = events_resp.json()['data']['parseCompleted']
        
        # Toggle it
        new_value = not current_value
        update_resp = requests.put(
            f"{BASE_URL}/api/v4/twitter/telegram/events",
            json={'parseCompleted': new_value}
        )
        assert update_resp.status_code == 200
        data = update_resp.json()
        assert data['ok'] == True
        assert data['data']['parseCompleted'] == new_value
        
        # Verify persistence with GET
        verify_resp = requests.get(f"{BASE_URL}/api/v4/twitter/telegram/events")
        assert verify_resp.json()['data']['parseCompleted'] == new_value
        
        # Restore original value
        requests.put(
            f"{BASE_URL}/api/v4/twitter/telegram/events",
            json={'parseCompleted': current_value}
        )
    
    def test_put_events_updates_multiple_preferences(self):
        """PUT events can update multiple preferences at once"""
        status_resp = requests.get(f"{BASE_URL}/api/v4/twitter/telegram/status")
        if not status_resp.json()['data'].get('connected'):
            pytest.skip("Telegram not connected")
        
        # Update multiple
        update_resp = requests.put(
            f"{BASE_URL}/api/v4/twitter/telegram/events",
            json={
                'sessionOk': True,
                'sessionStale': True,
                'highRisk': True
            }
        )
        assert update_resp.status_code == 200
        data = update_resp.json()
        assert data['ok'] == True
        assert data['data']['sessionOk'] == True
        assert data['data']['sessionStale'] == True
        assert data['data']['highRisk'] == True
    
    def test_put_events_ignores_invalid_keys(self):
        """PUT events ignores invalid preference keys"""
        status_resp = requests.get(f"{BASE_URL}/api/v4/twitter/telegram/status")
        if not status_resp.json()['data'].get('connected'):
            pytest.skip("Telegram not connected")
        
        # Try to update with invalid key
        update_resp = requests.put(
            f"{BASE_URL}/api/v4/twitter/telegram/events",
            json={
                'invalidKey': True,
                'sessionOk': True
            }
        )
        assert update_resp.status_code == 200
        # Should still update valid key
        assert update_resp.json()['data']['sessionOk'] == True
    
    def test_put_events_empty_body_returns_failure(self):
        """PUT events with empty body returns update failed"""
        status_resp = requests.get(f"{BASE_URL}/api/v4/twitter/telegram/status")
        if not status_resp.json()['data'].get('connected'):
            pytest.skip("Telegram not connected")
        
        update_resp = requests.put(
            f"{BASE_URL}/api/v4/twitter/telegram/events",
            json={}
        )
        assert update_resp.status_code == 200
        assert update_resp.json()['ok'] == False


class TestTelegramDisconnect:
    """POST /api/v4/twitter/telegram/disconnect tests"""
    
    def test_disconnect_when_connected(self):
        """Disconnect returns success when connected"""
        # First check if connected
        status_resp = requests.get(f"{BASE_URL}/api/v4/twitter/telegram/status")
        was_connected = status_resp.json()['data'].get('connected', False)
        
        if not was_connected:
            pytest.skip("Telegram not connected - cannot test disconnect")
        
        # Disconnect
        disconnect_resp = requests.post(f"{BASE_URL}/api/v4/twitter/telegram/disconnect")
        assert disconnect_resp.status_code == 200
        data = disconnect_resp.json()
        assert data['ok'] == True
        assert 'message' in data
        
        # Verify disconnected
        verify_resp = requests.get(f"{BASE_URL}/api/v4/twitter/telegram/status")
        assert verify_resp.json()['data']['connected'] == False
    
    def test_events_fail_after_disconnect(self):
        """GET events returns error after disconnect"""
        # Check if disconnected
        status_resp = requests.get(f"{BASE_URL}/api/v4/twitter/telegram/status")
        if status_resp.json()['data'].get('connected'):
            # Disconnect first
            requests.post(f"{BASE_URL}/api/v4/twitter/telegram/disconnect")
        
        # Try to get events
        events_resp = requests.get(f"{BASE_URL}/api/v4/twitter/telegram/events")
        assert events_resp.status_code == 400
        assert events_resp.json()['error'] == 'NO_CONNECTION'
    
    def test_put_events_fail_after_disconnect(self):
        """PUT events returns error after disconnect"""
        # Check if disconnected
        status_resp = requests.get(f"{BASE_URL}/api/v4/twitter/telegram/status")
        if status_resp.json()['data'].get('connected'):
            # Disconnect first
            requests.post(f"{BASE_URL}/api/v4/twitter/telegram/disconnect")
        
        # Try to update events
        update_resp = requests.put(
            f"{BASE_URL}/api/v4/twitter/telegram/events",
            json={'sessionOk': True}
        )
        assert update_resp.status_code == 200
        assert update_resp.json()['ok'] == False
        assert update_resp.json()['error'] == 'UPDATE_FAILED'


class TestTelegramTestMessage:
    """POST /api/v4/twitter/telegram/test tests"""
    
    def test_test_message_when_not_connected(self):
        """Test message returns error when not connected"""
        # Check if disconnected
        status_resp = requests.get(f"{BASE_URL}/api/v4/twitter/telegram/status")
        if status_resp.json()['data'].get('connected'):
            pytest.skip("Telegram is connected - cannot test not-connected case")
        
        test_resp = requests.post(f"{BASE_URL}/api/v4/twitter/telegram/test")
        assert test_resp.status_code == 400
        assert test_resp.json()['error'] == 'NO_TELEGRAM_CONNECTION'


# Fixture to reconnect Telegram after tests
@pytest.fixture(scope="module", autouse=True)
def reconnect_telegram_after_tests():
    """Reconnect Telegram after all tests complete"""
    yield
    # Reconnect via MongoDB (test cleanup)
    try:
        from pymongo import MongoClient
        client = MongoClient("mongodb://localhost:27017")
        db = client["test"]
        db.telegram_connections.update_one(
            {"userId": "dev-user"},
            {"$set": {"isActive": True}}
        )
        client.close()
        print("\n[Cleanup] Reconnected Telegram for dev-user")
    except Exception as e:
        print(f"\n[Cleanup] Failed to reconnect: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
