"""
MiniApp Welcome Screen, Profile Sync, and Webhook Tests
=========================================================
Tests for iteration 5 changes:
1. Welcome screen is single page (no slider/steps), has 'Open Intelligence Dashboard' button
2. POST /api/miniapp/sync-telegram-user accepts telegram_id, first_name, last_name, username, photo_url
3. GET /api/miniapp/profile?telegram_id=577782582 returns synced data
4. POST /api/miniapp/webhook responds to /start command
5. POST /api/miniapp/ab/track event tracking still works
6. All 4 tabs still work (Home, Feed, Edge, Profile)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestSyncTelegramUser:
    """Tests for POST /api/miniapp/sync-telegram-user endpoint"""
    
    def test_sync_telegram_user_success(self):
        """Test syncing telegram user data"""
        response = requests.post(f"{BASE_URL}/api/miniapp/sync-telegram-user", json={
            "telegram_id": "577782582",
            "first_name": "Pavel",
            "last_name": "D",
            "username": "pavelcrypto",
            "photo_url": "https://example.com/photo.jpg"
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print("PASS: sync-telegram-user returns ok:true")
    
    def test_sync_telegram_user_requires_telegram_id(self):
        """Test that telegram_id is required"""
        response = requests.post(f"{BASE_URL}/api/miniapp/sync-telegram-user", json={
            "first_name": "Test",
            "last_name": "User"
        })
        assert response.status_code == 400
        data = response.json()
        assert data.get("ok") == False
        assert "telegram_id" in data.get("error", "").lower()
        print("PASS: sync-telegram-user requires telegram_id")
    
    def test_sync_telegram_user_partial_data(self):
        """Test syncing with partial data (only first_name)"""
        response = requests.post(f"{BASE_URL}/api/miniapp/sync-telegram-user", json={
            "telegram_id": "TEST_123456",
            "first_name": "TestUser"
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print("PASS: sync-telegram-user accepts partial data")


class TestProfileWithSyncedData:
    """Tests for GET /api/miniapp/profile with synced telegram data"""
    
    def test_profile_returns_synced_name(self):
        """Test that profile returns the synced name"""
        # First sync the user
        requests.post(f"{BASE_URL}/api/miniapp/sync-telegram-user", json={
            "telegram_id": "577782582",
            "first_name": "Pavel",
            "last_name": "D",
            "username": "pavelcrypto",
            "photo_url": "https://example.com/photo.jpg"
        })
        
        # Then get profile
        response = requests.get(f"{BASE_URL}/api/miniapp/profile?telegram_id=577782582")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        
        user = data.get("user", {})
        # Name should be "Pavel D" (first_name + last_name)
        assert "Pavel" in user.get("name", ""), f"Expected 'Pavel' in name, got: {user.get('name')}"
        print(f"PASS: profile returns synced name: {user.get('name')}")
    
    def test_profile_returns_synced_username(self):
        """Test that profile returns the synced username"""
        response = requests.get(f"{BASE_URL}/api/miniapp/profile?telegram_id=577782582")
        assert response.status_code == 200
        data = response.json()
        
        user = data.get("user", {})
        assert user.get("username") == "pavelcrypto", f"Expected 'pavelcrypto', got: {user.get('username')}"
        print(f"PASS: profile returns synced username: {user.get('username')}")
    
    def test_profile_returns_photo_url(self):
        """Test that profile returns photo_url"""
        response = requests.get(f"{BASE_URL}/api/miniapp/profile?telegram_id=577782582")
        assert response.status_code == 200
        data = response.json()
        
        user = data.get("user", {})
        # photoUrl should be set
        assert user.get("photoUrl") is not None, "photoUrl should be set"
        print(f"PASS: profile returns photoUrl: {user.get('photoUrl')}")
    
    def test_profile_has_all_sections(self):
        """Test that profile has all required sections"""
        response = requests.get(f"{BASE_URL}/api/miniapp/profile?telegram_id=577782582")
        assert response.status_code == 200
        data = response.json()
        
        assert "user" in data
        assert "performance" in data
        assert "favorites" in data
        assert "referral" in data
        assert "settings" in data
        print("PASS: profile has all required sections")


class TestWebhook:
    """Tests for POST /api/miniapp/webhook endpoint"""
    
    def test_webhook_responds_to_start_command(self):
        """Test webhook handles /start command"""
        response = requests.post(f"{BASE_URL}/api/miniapp/webhook", json={
            "message": {
                "text": "/start",
                "chat": {"id": 577782582},
                "from": {
                    "id": 577782582,
                    "first_name": "Pavel",
                    "last_name": "D",
                    "username": "pavelcrypto"
                }
            }
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print("PASS: webhook responds to /start command")
    
    def test_webhook_handles_btc_command(self):
        """Test webhook handles /btc command"""
        response = requests.post(f"{BASE_URL}/api/miniapp/webhook", json={
            "message": {
                "text": "/btc",
                "chat": {"id": 577782582},
                "from": {"id": 577782582, "first_name": "Test"}
            }
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print("PASS: webhook responds to /btc command")
    
    def test_webhook_handles_help_command(self):
        """Test webhook handles /help command"""
        response = requests.post(f"{BASE_URL}/api/miniapp/webhook", json={
            "message": {
                "text": "/help",
                "chat": {"id": 577782582},
                "from": {"id": 577782582, "first_name": "Test"}
            }
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print("PASS: webhook responds to /help command")
    
    def test_webhook_handles_empty_update(self):
        """Test webhook handles empty update gracefully"""
        response = requests.post(f"{BASE_URL}/api/miniapp/webhook", json={})
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print("PASS: webhook handles empty update")


class TestEventTracking:
    """Tests for POST /api/miniapp/ab/track endpoint"""
    
    def test_track_event_works(self):
        """Test event tracking still works"""
        response = requests.post(f"{BASE_URL}/api/miniapp/ab/track", json={
            "user_id": "test_user_iteration5",
            "event": "welcome_completed",
            "variant": "A",
            "meta": {"source": "test"}
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print("PASS: event tracking works")


class TestAllTabs:
    """Tests for all 4 tabs (Home, Feed, Edge, Profile)"""
    
    def test_home_tab_btc(self):
        """Test Home tab with BTC"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=BTC")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "decision" in data
        print("PASS: Home tab (BTC) works")
    
    def test_home_tab_eth(self):
        """Test Home tab with ETH"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=ETH")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print("PASS: Home tab (ETH) works")
    
    def test_home_tab_sol(self):
        """Test Home tab with SOL"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=SOL")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print("PASS: Home tab (SOL) works")
    
    def test_feed_tab(self):
        """Test Feed tab"""
        response = requests.get(f"{BASE_URL}/api/miniapp/feed?limit=30")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "sections" in data
        print("PASS: Feed tab works")
    
    def test_edge_tab(self):
        """Test Edge tab"""
        response = requests.get(f"{BASE_URL}/api/miniapp/edge")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "markets" in data
        print("PASS: Edge tab works")
    
    def test_profile_tab(self):
        """Test Profile tab"""
        response = requests.get(f"{BASE_URL}/api/miniapp/profile?telegram_id=577782582")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "user" in data
        print("PASS: Profile tab works")


class TestPolymarket:
    """Tests for Polymarket endpoint"""
    
    def test_polymarket_endpoint(self):
        """Test Polymarket endpoint"""
        response = requests.get(f"{BASE_URL}/api/miniapp/polymarket")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print("PASS: Polymarket endpoint works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
