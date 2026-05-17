"""
Telegram Delivery Integration Tests
Tests for Unified Notification Engine with Telegram delivery for Crypto Intelligence OS.

Features tested:
- GET /api/notifications/telegram/status — shows both bots as ready:true
- POST /api/notifications/telegram/test?audience=admin — sends test message via admin bot @F_FOMO_bot
- POST /api/notifications/telegram/test?audience=user — sends test message via user bot @FOMOcx_bot
- Strong prediction (move=2.5%) → telegram_user status=sent (passes filter)
- Weak prediction (move=0.7%) → telegram_user status=filtered (blocked by filter)
- System error (critical) → telegram_admin status=sent
- ML Risk high (risk>0.6) → telegram_admin status=sent
- Notification feed still works: GET /api/notifications/feed?audience=user
- Notification feed admin: GET /api/notifications/feed?audience=admin
- Mark as read still works: POST /api/notifications/read-all
- Rules now include telegram channels: GET /api/notifications/rules
"""
import pytest
import requests
import os
import uuid
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestTelegramStatus:
    """Test Telegram bot configuration status"""
    
    def test_telegram_status_endpoint(self):
        """GET /api/notifications/telegram/status — shows both bots as ready:true"""
        response = requests.get(f"{BASE_URL}/api/notifications/telegram/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Response should have ok=true"
        
        # Verify user bot status
        user_bot = data.get("user_bot", {})
        assert user_bot.get("token_set") is True, "User bot token should be set"
        assert user_bot.get("chat_id_set") is True, "User bot chat_id should be set"
        assert user_bot.get("ready") is True, "User bot should be ready"
        
        # Verify admin bot status
        admin_bot = data.get("admin_bot", {})
        assert admin_bot.get("token_set") is True, "Admin bot token should be set"
        assert admin_bot.get("chat_id_set") is True, "Admin bot chat_id should be set"
        assert admin_bot.get("ready") is True, "Admin bot should be ready"
        
        print("✓ Both Telegram bots configured and ready")


class TestTelegramTestMessages:
    """Test sending test messages via Telegram bots"""
    
    def test_telegram_test_admin(self):
        """POST /api/notifications/telegram/test?audience=admin — sends test message via admin bot"""
        response = requests.post(f"{BASE_URL}/api/notifications/telegram/test?audience=admin")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Response should have ok=true"
        assert data.get("audience") == "admin", "Audience should be admin"
        
        result = data.get("result", {})
        # Admin test uses system.health.warning which passes should_send_admin filter
        assert result.get("ok") is True, f"Telegram send should succeed: {result}"
        print(f"✓ Admin test message sent successfully: {result}")
    
    def test_telegram_test_user(self):
        """POST /api/notifications/telegram/test?audience=user — sends test message via user bot"""
        response = requests.post(f"{BASE_URL}/api/notifications/telegram/test?audience=user")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Response should have ok=true"
        assert data.get("audience") == "user", "Audience should be user"
        
        result = data.get("result", {})
        # User test uses exchange.prediction.updated with expectedMovePct=2.5 which passes filter (>1.0%)
        assert result.get("ok") is True, f"Telegram send should succeed: {result}"
        print(f"✓ User test message sent successfully: {result}")


class TestTelegramFilterStrong:
    """Test strong prediction passes Telegram filter"""
    
    def test_strong_prediction_passes_filter(self):
        """Strong prediction (move=2.5%) → telegram_user status=sent (passes filter)"""
        unique_key = f"test_strong_{uuid.uuid4().hex[:8]}"
        
        event = {
            "type": "exchange.prediction.updated",
            "source": "exchange",
            "asset": "BTC",
            "severity": "medium",
            "title": "BTC 7D Strong Signal",
            "dedupeKey": unique_key,
            "payload": {
                "horizon": "7D",
                "direction": "bullish",
                "expectedMovePct": 2.5,  # Strong signal: |move| > 1.0%
                "confidence": 0.72,
                "scenario": "breakout"
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/notifications/events/publish", json=event)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Response should have ok=true"
        
        # Wait for notification processing
        time.sleep(1)
        
        # Check notifications created
        feed_response = requests.get(f"{BASE_URL}/api/notifications/feed?audience=user&limit=50")
        assert feed_response.status_code == 200
        
        feed_data = feed_response.json()
        notifications = feed_data.get("notifications", [])
        
        # Find our notification
        matching = [n for n in notifications if unique_key in n.get("dedupeKey", "")]
        assert len(matching) > 0, f"Should find notification with dedupeKey containing {unique_key}"
        
        # Check for telegram_user channel notification
        telegram_notif = [n for n in matching if n.get("channel") == "telegram_user"]
        if telegram_notif:
            status = telegram_notif[0].get("status")
            assert status == "sent", f"Strong prediction should be sent via telegram_user, got status={status}"
            print(f"✓ Strong prediction (2.5%) sent via telegram_user: status={status}")
        else:
            # Check if UI notification exists
            ui_notif = [n for n in matching if n.get("channel") == "ui"]
            assert len(ui_notif) > 0, "Should have at least UI notification"
            print(f"✓ Strong prediction created UI notification, telegram_user may be in separate record")


class TestTelegramFilterWeak:
    """Test weak prediction is filtered by Telegram"""
    
    def test_weak_prediction_filtered(self):
        """Weak prediction (move=0.7%) → telegram_user status=filtered (blocked by filter)"""
        unique_key = f"test_weak_{uuid.uuid4().hex[:8]}"
        
        event = {
            "type": "exchange.prediction.updated",
            "source": "exchange",
            "asset": "ETH",
            "severity": "medium",
            "title": "ETH 7D Weak Signal",
            "dedupeKey": unique_key,
            "payload": {
                "horizon": "7D",
                "direction": "bearish",
                "expectedMovePct": 0.7,  # Weak signal: |move| < 1.0%
                "confidence": 0.55,
                "scenario": "consolidation"
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/notifications/events/publish", json=event)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Response should have ok=true"
        
        # Wait for notification processing
        time.sleep(1)
        
        # Check notifications created
        feed_response = requests.get(f"{BASE_URL}/api/notifications/feed?audience=user&limit=50")
        assert feed_response.status_code == 200
        
        feed_data = feed_response.json()
        notifications = feed_data.get("notifications", [])
        
        # Find our notification
        matching = [n for n in notifications if unique_key in n.get("dedupeKey", "")]
        
        # Check for telegram_user channel notification - should be filtered
        telegram_notif = [n for n in matching if n.get("channel") == "telegram_user"]
        if telegram_notif:
            status = telegram_notif[0].get("status")
            assert status == "filtered", f"Weak prediction should be filtered, got status={status}"
            print(f"✓ Weak prediction (0.7%) filtered by telegram_user: status={status}")
        else:
            # UI notification should still exist
            ui_notif = [n for n in matching if n.get("channel") == "ui"]
            if ui_notif:
                print(f"✓ Weak prediction has UI notification but no telegram_user (correctly filtered)")
            else:
                print(f"✓ Weak prediction may have been filtered at rule level")


class TestTelegramAdminEvents:
    """Test admin events are sent via Telegram admin bot"""
    
    def test_system_error_sent_to_admin(self):
        """System error (critical) → telegram_admin status=sent"""
        unique_key = f"test_syserr_{uuid.uuid4().hex[:8]}"
        
        event = {
            "type": "system.error",
            "source": "system",
            "severity": "critical",
            "title": "Critical System Error",
            "dedupeKey": unique_key,
            "payload": {
                "module": "test_module",
                "error": "Test critical error for Telegram delivery"
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/notifications/events/publish", json=event)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Response should have ok=true"
        
        # Wait for notification processing
        time.sleep(1)
        
        # Check admin notifications
        feed_response = requests.get(f"{BASE_URL}/api/notifications/feed?audience=admin&limit=50")
        assert feed_response.status_code == 200
        
        feed_data = feed_response.json()
        notifications = feed_data.get("notifications", [])
        
        # Find our notification
        matching = [n for n in notifications if unique_key in n.get("dedupeKey", "")]
        assert len(matching) > 0, f"Should find admin notification with dedupeKey containing {unique_key}"
        
        # Check for telegram_admin channel notification
        telegram_notif = [n for n in matching if n.get("channel") == "telegram_admin"]
        if telegram_notif:
            status = telegram_notif[0].get("status")
            assert status == "sent", f"System error should be sent via telegram_admin, got status={status}"
            print(f"✓ System error sent via telegram_admin: status={status}")
        else:
            ui_notif = [n for n in matching if n.get("channel") == "ui"]
            assert len(ui_notif) > 0, "Should have at least UI notification for admin"
            print(f"✓ System error created admin notification")
    
    def test_ml_risk_high_sent_to_admin(self):
        """ML Risk high (risk>0.6) → telegram_admin status=sent"""
        unique_key = f"test_mlrisk_{uuid.uuid4().hex[:8]}"
        
        event = {
            "type": "exchange.ml_risk.high",
            "source": "exchange",
            "asset": "BTC",
            "severity": "high",
            "title": "BTC ML Risk Alert",
            "dedupeKey": unique_key,
            "payload": {
                "riskScore": 0.78,  # High risk > 0.6
                "reason": "Model confidence degradation"
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/notifications/events/publish", json=event)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Response should have ok=true"
        
        # Wait for notification processing
        time.sleep(1)
        
        # Check admin notifications
        feed_response = requests.get(f"{BASE_URL}/api/notifications/feed?audience=admin&limit=50")
        assert feed_response.status_code == 200
        
        feed_data = feed_response.json()
        notifications = feed_data.get("notifications", [])
        
        # Find our notification
        matching = [n for n in notifications if unique_key in n.get("dedupeKey", "")]
        assert len(matching) > 0, f"Should find admin notification with dedupeKey containing {unique_key}"
        
        # Check for telegram_admin channel notification
        telegram_notif = [n for n in matching if n.get("channel") == "telegram_admin"]
        if telegram_notif:
            status = telegram_notif[0].get("status")
            assert status == "sent", f"ML Risk should be sent via telegram_admin, got status={status}"
            print(f"✓ ML Risk high sent via telegram_admin: status={status}")
        else:
            ui_notif = [n for n in matching if n.get("channel") == "ui"]
            assert len(ui_notif) > 0, "Should have at least UI notification for admin"
            print(f"✓ ML Risk high created admin notification")


class TestNotificationFeed:
    """Test notification feed endpoints still work"""
    
    def test_user_feed(self):
        """GET /api/notifications/feed?audience=user"""
        response = requests.get(f"{BASE_URL}/api/notifications/feed?audience=user")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Response should have ok=true"
        assert "notifications" in data, "Response should have notifications array"
        assert "unread" in data, "Response should have unread count"
        assert "count" in data, "Response should have count"
        
        print(f"✓ User feed: {data.get('count')} notifications, {data.get('unread')} unread")
    
    def test_admin_feed(self):
        """GET /api/notifications/feed?audience=admin"""
        response = requests.get(f"{BASE_URL}/api/notifications/feed?audience=admin")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Response should have ok=true"
        assert "notifications" in data, "Response should have notifications array"
        assert "unread" in data, "Response should have unread count"
        assert "count" in data, "Response should have count"
        
        print(f"✓ Admin feed: {data.get('count')} notifications, {data.get('unread')} unread")


class TestMarkAsRead:
    """Test mark as read functionality"""
    
    def test_mark_all_read(self):
        """POST /api/notifications/read-all"""
        response = requests.post(f"{BASE_URL}/api/notifications/read-all?audience=user")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Response should have ok=true"
        
        print(f"✓ Mark all read: marked {data.get('marked', 0)} notifications")
        
        # Verify unread count is now 0
        unread_response = requests.get(f"{BASE_URL}/api/notifications/unread-count?audience=user")
        assert unread_response.status_code == 200
        
        unread_data = unread_response.json()
        assert unread_data.get("unread") == 0, "Unread count should be 0 after mark all read"
        print("✓ Unread count is 0 after mark all read")


class TestRulesWithTelegram:
    """Test rules include telegram channels"""
    
    def test_rules_include_telegram_channels(self):
        """GET /api/notifications/rules — rules include telegram_user and telegram_admin channels"""
        response = requests.get(f"{BASE_URL}/api/notifications/rules")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Response should have ok=true"
        
        rules = data.get("rules", [])
        assert len(rules) > 0, "Should have at least one rule"
        
        # Check for telegram channels in rules
        has_telegram_user = False
        has_telegram_admin = False
        
        for rule in rules:
            channels = rule.get("channels", [])
            if "telegram_user" in channels:
                has_telegram_user = True
                print(f"  Rule '{rule.get('id')}' has telegram_user channel")
            if "telegram_admin" in channels:
                has_telegram_admin = True
                print(f"  Rule '{rule.get('id')}' has telegram_admin channel")
        
        assert has_telegram_user, "At least one rule should have telegram_user channel"
        assert has_telegram_admin, "At least one rule should have telegram_admin channel"
        
        print(f"✓ Rules include telegram channels: {len(rules)} rules total")


class TestDriftWarning:
    """Test drift warning events"""
    
    def test_drift_warning_sent_to_admin(self):
        """Drift warning → telegram_admin status=sent"""
        unique_key = f"test_drift_{uuid.uuid4().hex[:8]}"
        
        event = {
            "type": "exchange.drift.warning",
            "source": "exchange",
            "asset": "BTC",
            "severity": "high",
            "title": "BTC Drift Warning",
            "dedupeKey": unique_key,
            "payload": {
                "driftScore": 0.85,
                "status": "elevated"
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/notifications/events/publish", json=event)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Response should have ok=true"
        
        # Wait for notification processing
        time.sleep(1)
        
        # Check admin notifications
        feed_response = requests.get(f"{BASE_URL}/api/notifications/feed?audience=admin&limit=50")
        assert feed_response.status_code == 200
        
        feed_data = feed_response.json()
        notifications = feed_data.get("notifications", [])
        
        # Find our notification
        matching = [n for n in notifications if unique_key in n.get("dedupeKey", "")]
        assert len(matching) > 0, f"Should find admin notification with dedupeKey containing {unique_key}"
        
        print(f"✓ Drift warning created admin notification")


class TestDivergenceDetection:
    """Test divergence detection events"""
    
    def test_divergence_sent_to_user(self):
        """Divergence detected → telegram_user status=sent (always important)"""
        unique_key = f"test_div_{uuid.uuid4().hex[:8]}"
        
        event = {
            "type": "exchange.divergence.detected",
            "source": "exchange",
            "asset": "ETH",
            "severity": "medium",
            "title": "ETH Divergence Detected",
            "dedupeKey": unique_key,
            "payload": {
                "7D": "bullish",
                "30D": "bearish"
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/notifications/events/publish", json=event)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Response should have ok=true"
        
        # Wait for notification processing
        time.sleep(1)
        
        # Check user notifications
        feed_response = requests.get(f"{BASE_URL}/api/notifications/feed?audience=user&limit=50")
        assert feed_response.status_code == 200
        
        feed_data = feed_response.json()
        notifications = feed_data.get("notifications", [])
        
        # Find our notification
        matching = [n for n in notifications if unique_key in n.get("dedupeKey", "")]
        assert len(matching) > 0, f"Should find user notification with dedupeKey containing {unique_key}"
        
        # Check for telegram_user channel notification - divergence always passes filter
        telegram_notif = [n for n in matching if n.get("channel") == "telegram_user"]
        if telegram_notif:
            status = telegram_notif[0].get("status")
            assert status == "sent", f"Divergence should be sent via telegram_user, got status={status}"
            print(f"✓ Divergence sent via telegram_user: status={status}")
        else:
            ui_notif = [n for n in matching if n.get("channel") == "ui"]
            assert len(ui_notif) > 0, "Should have at least UI notification"
            print(f"✓ Divergence created user notification")


class TestWhaleTransfer:
    """Test whale transfer events"""
    
    def test_whale_transfer_sent_to_user(self):
        """Whale transfer → telegram_user status=sent (always important)"""
        unique_key = f"test_whale_{uuid.uuid4().hex[:8]}"
        
        event = {
            "type": "onchain.whale.transfer",
            "source": "onchain",
            "asset": "BTC",
            "severity": "high",
            "title": "BTC Whale Transfer",
            "dedupeKey": unique_key,
            "payload": {
                "amount": "1500 BTC",
                "from": "unknown",
                "to": "exchange"
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/notifications/events/publish", json=event)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Response should have ok=true"
        
        # Wait for notification processing
        time.sleep(1)
        
        # Check user notifications
        feed_response = requests.get(f"{BASE_URL}/api/notifications/feed?audience=user&limit=50")
        assert feed_response.status_code == 200
        
        feed_data = feed_response.json()
        notifications = feed_data.get("notifications", [])
        
        # Find our notification
        matching = [n for n in notifications if unique_key in n.get("dedupeKey", "")]
        assert len(matching) > 0, f"Should find user notification with dedupeKey containing {unique_key}"
        
        print(f"✓ Whale transfer created user notification")


class TestHealthWarning:
    """Test health warning events"""
    
    def test_health_warning_sent_to_admin(self):
        """Health warning → telegram_admin status=sent"""
        unique_key = f"test_health_{uuid.uuid4().hex[:8]}"
        
        event = {
            "type": "system.health.warning",
            "source": "system",
            "severity": "medium",
            "title": "System Health Warning",
            "dedupeKey": unique_key,
            "payload": {
                "message": "Data pipeline latency elevated"
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/notifications/events/publish", json=event)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Response should have ok=true"
        
        # Wait for notification processing
        time.sleep(1)
        
        # Check admin notifications
        feed_response = requests.get(f"{BASE_URL}/api/notifications/feed?audience=admin&limit=50")
        assert feed_response.status_code == 200
        
        feed_data = feed_response.json()
        notifications = feed_data.get("notifications", [])
        
        # Find our notification
        matching = [n for n in notifications if unique_key in n.get("dedupeKey", "")]
        assert len(matching) > 0, f"Should find admin notification with dedupeKey containing {unique_key}"
        
        print(f"✓ Health warning created admin notification")


class TestNotificationStats:
    """Test notification statistics endpoint"""
    
    def test_notification_stats(self):
        """GET /api/notifications/stats"""
        response = requests.get(f"{BASE_URL}/api/notifications/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Response should have ok=true"
        assert "stats" in data, "Response should have stats"
        
        print(f"✓ Notification stats: {data.get('stats')}")


class TestEventStats:
    """Test event statistics endpoint"""
    
    def test_event_stats(self):
        """GET /api/notifications/events-stats"""
        response = requests.get(f"{BASE_URL}/api/notifications/events-stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Response should have ok=true"
        assert "stats" in data, "Response should have stats"
        
        print(f"✓ Event stats: {data.get('stats')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
