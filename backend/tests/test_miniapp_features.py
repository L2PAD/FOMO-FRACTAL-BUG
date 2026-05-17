"""
MiniApp Features Test Suite
============================
Tests for:
- Webhook endpoint (POST /api/miniapp/webhook)
- Home API (GET /api/miniapp/home)
- Bot setup commands verification
- Alert button formatting (free vs PRO users)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestMiniAppWebhook:
    """Test the MiniApp webhook endpoint"""
    
    def test_webhook_returns_200(self):
        """POST /api/miniapp/webhook should return 200 OK"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/webhook",
            json={"message": {"chat": {"id": 123456}, "text": "/start"}},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
    
    def test_webhook_handles_btc_command(self):
        """POST /api/miniapp/webhook with /btc command"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/webhook",
            json={"message": {"chat": {"id": 123456}, "text": "/btc"}},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
    
    def test_webhook_handles_eth_command(self):
        """POST /api/miniapp/webhook with /eth command"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/webhook",
            json={"message": {"chat": {"id": 123456}, "text": "/eth"}},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
    
    def test_webhook_handles_sol_command(self):
        """POST /api/miniapp/webhook with /sol command"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/webhook",
            json={"message": {"chat": {"id": 123456}, "text": "/sol"}},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
    
    def test_webhook_handles_alerts_command(self):
        """POST /api/miniapp/webhook with /alerts command"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/webhook",
            json={"message": {"chat": {"id": 123456}, "text": "/alerts"}},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
    
    def test_webhook_handles_edge_command(self):
        """POST /api/miniapp/webhook with /edge command"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/webhook",
            json={"message": {"chat": {"id": 123456}, "text": "/edge"}},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
    
    def test_webhook_handles_pro_command(self):
        """POST /api/miniapp/webhook with /pro command"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/webhook",
            json={"message": {"chat": {"id": 123456}, "text": "/pro"}},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
    
    def test_webhook_handles_help_command(self):
        """POST /api/miniapp/webhook with /help command"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/webhook",
            json={"message": {"chat": {"id": 123456}, "text": "/help"}},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True


class TestMiniAppHomeAPI:
    """Test the MiniApp home API"""
    
    def test_home_btc_returns_200(self):
        """GET /api/miniapp/home?asset=BTC should return 200 with data"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=BTC")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("asset") == "BTC"
        assert "price" in data
        assert "decision" in data
    
    def test_home_eth_returns_200(self):
        """GET /api/miniapp/home?asset=ETH should return 200 with data"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=ETH")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("asset") == "ETH"
    
    def test_home_sol_returns_200(self):
        """GET /api/miniapp/home?asset=SOL should return 200 with data"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=SOL")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("asset") == "SOL"
    
    def test_home_decision_structure(self):
        """Home API decision should have required fields"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=BTC")
        assert response.status_code == 200
        data = response.json()
        decision = data.get("decision", {})
        assert "action" in decision
        assert "confidence" in decision
        assert decision["action"] in ["BUY", "SELL", "WAIT", "AVOID"]


class TestMiniAppFeedAPI:
    """Test the MiniApp feed API"""
    
    def test_feed_returns_200(self):
        """GET /api/miniapp/feed should return 200"""
        response = requests.get(f"{BASE_URL}/api/miniapp/feed?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True


class TestMiniAppEdgeAPI:
    """Test the MiniApp edge API"""
    
    def test_edge_returns_200(self):
        """GET /api/miniapp/edge should return 200"""
        response = requests.get(f"{BASE_URL}/api/miniapp/edge")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True


class TestMiniAppBillingAPI:
    """Test the MiniApp billing APIs"""
    
    def test_billing_plans_returns_200(self):
        """GET /api/miniapp/billing/plans should return 200"""
        response = requests.get(f"{BASE_URL}/api/miniapp/billing/plans")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
    
    def test_billing_status_returns_200(self):
        """GET /api/miniapp/billing/status should return 200"""
        response = requests.get(f"{BASE_URL}/api/miniapp/billing/status?telegram_id=test123")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True


class TestAlertButtonFormatting:
    """Test alert button formatting for free vs PRO users"""
    
    def test_upgrade_button_has_two_buttons_for_free_users(self):
        """
        Verify _upgrade_button returns two buttons for free users:
        1. 'See Full Edge in App' (or 'Unlock Full Analysis' for variants B/D)
        2. 'Upgrade to PRO'
        """
        # Set MINIAPP_URL env var before importing
        os.environ['MINIAPP_URL'] = 'https://expo-telegram-web.preview.emergentagent.com/miniapp'
        
        # Import the function to test (reload to pick up env var)
        import sys
        sys.path.insert(0, '/app/backend')
        import importlib
        import miniapp.edge_alerts as ea
        importlib.reload(ea)
        
        # Test default variant (should have 'See Full Edge in App')
        result = ea._upgrade_button("")
        assert result is not None, "WEBAPP_URL should be set"
        keyboard = result.get("inline_keyboard", [])
        assert len(keyboard) == 2, "Free user should have 2 buttons"
        
        # First button should be 'See Full Edge in App'
        first_btn = keyboard[0][0]
        assert first_btn["text"] == "See Full Edge in App"
        
        # Second button should be 'Upgrade to PRO'
        second_btn = keyboard[1][0]
        assert second_btn["text"] == "Upgrade to PRO"
    
    def test_upgrade_button_variant_b_has_unlock_text(self):
        """Variant B should have 'Unlock Full Analysis' text"""
        os.environ['MINIAPP_URL'] = 'https://expo-telegram-web.preview.emergentagent.com/miniapp'
        
        import sys
        sys.path.insert(0, '/app/backend')
        import importlib
        import miniapp.edge_alerts as ea
        importlib.reload(ea)
        
        result = ea._upgrade_button("B")
        keyboard = result.get("inline_keyboard", [])
        first_btn = keyboard[0][0]
        assert first_btn["text"] == "Unlock Full Analysis"
    
    def test_edge_open_button_for_pro_users(self):
        """
        Verify _edge_open_button returns single button for PRO users:
        'Open Full {asset} Analysis'
        """
        os.environ['MINIAPP_URL'] = 'https://expo-telegram-web.preview.emergentagent.com/miniapp'
        
        import sys
        sys.path.insert(0, '/app/backend')
        import importlib
        import miniapp.edge_alerts as ea
        importlib.reload(ea)
        
        result = ea._edge_open_button("BTC")
        assert result is not None, "WEBAPP_URL should be set"
        keyboard = result.get("inline_keyboard", [])
        assert len(keyboard) == 1, "PRO user should have 1 button"
        
        btn = keyboard[0][0]
        assert btn["text"] == "Open Full BTC Analysis"
        assert "web_app" in btn
        assert "BTC" in btn["web_app"]["url"]


class TestBotSetupCommands:
    """Verify bot setup has correct 8 commands"""
    
    def test_bot_setup_has_8_commands(self):
        """Bot setup should configure 8 commands"""
        import sys
        sys.path.insert(0, '/app/backend')
        
        # Read the bot_setup.py file to verify commands
        with open('/app/backend/miniapp/bot_setup.py', 'r') as f:
            content = f.read()
        
        # Check for all 8 commands
        commands = [
            '"command": "start"',
            '"command": "btc"',
            '"command": "eth"',
            '"command": "sol"',
            '"command": "alerts"',
            '"command": "edge"',
            '"command": "pro"',
            '"command": "help"',
        ]
        
        for cmd in commands:
            assert cmd in content, f"Command {cmd} not found in bot_setup.py"
        
        print("All 8 bot commands verified in bot_setup.py")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
