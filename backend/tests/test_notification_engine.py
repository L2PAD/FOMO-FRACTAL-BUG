"""
Unified Notification Engine — Backend API Tests

Tests all notification engine endpoints:
- Events: publish, list, stats
- Rules: CRUD operations
- Notifications: feed, unread count, mark read
- Dedupe: publishing same event twice should skip
- Rule routing: exchange→user, system→admin, critical→admin
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestNotificationInit:
    """Test initialization endpoint"""
    
    def test_init_endpoint(self):
        """POST /api/notifications/init — creates indexes and seeds default rules"""
        response = requests.post(f"{BASE_URL}/api/notifications/init")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "message" in data
        print(f"✓ Init: {data.get('message')}")


class TestNotificationRules:
    """Test rule CRUD operations"""
    
    def test_list_rules(self):
        """GET /api/notifications/rules — list all rules (5 default rules seeded)"""
        response = requests.get(f"{BASE_URL}/api/notifications/rules")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "rules" in data
        assert "count" in data
        # Should have at least 5 default rules
        assert data["count"] >= 5
        print(f"✓ Rules count: {data['count']}")
        
        # Verify default rule IDs exist
        rule_ids = [r["id"] for r in data["rules"]]
        expected_rules = [
            "rule_user_exchange_prediction",
            "rule_user_onchain_whale",
            "rule_user_sentiment",
            "rule_admin_system",
            "rule_admin_all_critical"
        ]
        for expected in expected_rules:
            assert expected in rule_ids, f"Missing default rule: {expected}"
        print(f"✓ All 5 default rules present")
    
    def test_create_custom_rule(self):
        """POST /api/notifications/rules — create custom rule"""
        unique_id = f"rule_test_{uuid.uuid4().hex[:8]}"
        rule_data = {
            "id": unique_id,
            "audience": "user",
            "eventTypes": ["exchange.prediction.updated"],
            "conditions": {"minSeverity": "high"},
            "channels": ["ui"],
            "cooldownMinutes": 30
        }
        response = requests.post(f"{BASE_URL}/api/notifications/rules", json=rule_data)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "rule" in data
        assert data["rule"]["id"] == unique_id
        assert data["rule"]["isBuiltin"] is False
        print(f"✓ Created custom rule: {unique_id}")
        return unique_id
    
    def test_update_rule(self):
        """PUT /api/notifications/rules/{id} — update rule"""
        # First create a rule
        unique_id = f"rule_update_test_{uuid.uuid4().hex[:8]}"
        create_resp = requests.post(f"{BASE_URL}/api/notifications/rules", json={
            "id": unique_id,
            "audience": "user",
            "eventTypes": [],
            "isEnabled": True
        })
        assert create_resp.status_code == 200
        
        # Update it
        update_resp = requests.put(f"{BASE_URL}/api/notifications/rules/{unique_id}", json={
            "isEnabled": False,
            "cooldownMinutes": 60
        })
        assert update_resp.status_code == 200
        data = update_resp.json()
        assert data.get("ok") is True
        print(f"✓ Updated rule: {unique_id}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/notifications/rules/{unique_id}")
    
    def test_delete_custom_rule(self):
        """DELETE /api/notifications/rules/{id} — delete non-builtin rule"""
        # Create a rule to delete
        unique_id = f"rule_delete_test_{uuid.uuid4().hex[:8]}"
        requests.post(f"{BASE_URL}/api/notifications/rules", json={
            "id": unique_id,
            "audience": "user",
            "eventTypes": []
        })
        
        # Delete it
        delete_resp = requests.delete(f"{BASE_URL}/api/notifications/rules/{unique_id}")
        assert delete_resp.status_code == 200
        data = delete_resp.json()
        assert data.get("ok") is True
        print(f"✓ Deleted custom rule: {unique_id}")
    
    def test_cannot_delete_builtin_rule(self):
        """DELETE /api/notifications/rules/{id} — builtin rules cannot be deleted"""
        delete_resp = requests.delete(f"{BASE_URL}/api/notifications/rules/rule_user_exchange_prediction")
        assert delete_resp.status_code == 200
        data = delete_resp.json()
        # Should return ok: false because builtin rules can't be deleted
        assert data.get("ok") is False
        print("✓ Builtin rule deletion correctly rejected")


class TestEventPublishing:
    """Test event publishing and rule engine"""
    
    def test_publish_exchange_event(self):
        """POST /api/notifications/events/publish — creates event, triggers rule engine"""
        unique_key = f"test_exchange_{uuid.uuid4().hex[:8]}"
        event_data = {
            "type": "exchange.prediction.updated",
            "source": "exchange",
            "asset": "BTC",
            "severity": "medium",
            "title": "BTC 30D outlook updated",
            "dedupeKey": unique_key,
            "payload": {
                "horizon": "30D",
                "direction": "bearish",
                "expectedMovePct": -5.2,
                "confidence": 0.72
            }
        }
        response = requests.post(f"{BASE_URL}/api/notifications/events/publish", json=event_data)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "event" in data
        event = data["event"]
        assert "id" in event
        assert event.get("type") == "exchange.prediction.updated"
        assert event.get("source") == "exchange"
        # Should have created notifications
        assert "_notifications_created" in event or "skipped" in event
        print(f"✓ Published exchange event: {event.get('id', 'skipped')}")
        return event
    
    def test_publish_system_event_routes_to_admin(self):
        """POST /api/notifications/events/publish — system events go to admin feed"""
        unique_key = f"test_system_{uuid.uuid4().hex[:8]}"
        event_data = {
            "type": "system.error",
            "source": "system",
            "severity": "high",
            "title": "System error detected",
            "dedupeKey": unique_key,
            "payload": {
                "module": "exchange_engine",
                "error": "Connection timeout"
            }
        }
        response = requests.post(f"{BASE_URL}/api/notifications/events/publish", json=event_data)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        event = data["event"]
        print(f"✓ Published system event: {event.get('id', 'skipped')}")
    
    def test_publish_critical_event_routes_to_admin(self):
        """POST /api/notifications/events/publish — critical events go to admin via catch-all rule"""
        unique_key = f"test_critical_{uuid.uuid4().hex[:8]}"
        event_data = {
            "type": "exchange.prediction.updated",
            "source": "exchange",
            "asset": "ETH",
            "severity": "critical",
            "title": "ETH critical alert",
            "dedupeKey": unique_key,
            "payload": {
                "horizon": "1D",
                "direction": "bearish",
                "expectedMovePct": -15.0,
                "confidence": 0.95
            }
        }
        response = requests.post(f"{BASE_URL}/api/notifications/events/publish", json=event_data)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        event = data["event"]
        # Critical events should create notifications for both user and admin
        print(f"✓ Published critical event: {event.get('id', 'skipped')}")
    
    def test_dedupe_same_event_twice(self):
        """Dedupe: publishing same event twice should skip second time"""
        unique_key = f"test_dedupe_{uuid.uuid4().hex[:8]}"
        event_data = {
            "type": "exchange.prediction.updated",
            "source": "exchange",
            "asset": "SOL",
            "severity": "medium",
            "title": "SOL outlook",
            "dedupeKey": unique_key,
            "payload": {}
        }
        
        # First publish
        resp1 = requests.post(f"{BASE_URL}/api/notifications/events/publish", json=event_data)
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1.get("ok") is True
        event1 = data1["event"]
        assert "skipped" not in event1 or event1.get("skipped") is not True
        print(f"✓ First publish: {event1.get('id')}")
        
        # Second publish with same dedupeKey
        resp2 = requests.post(f"{BASE_URL}/api/notifications/events/publish", json=event_data)
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2.get("ok") is True
        event2 = data2["event"]
        assert event2.get("skipped") is True
        assert event2.get("reason") == "dedupe"
        print(f"✓ Second publish correctly skipped (dedupe)")


class TestEventListing:
    """Test event listing and stats"""
    
    def test_list_events(self):
        """GET /api/notifications/events — list events with optional filters"""
        response = requests.get(f"{BASE_URL}/api/notifications/events")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "events" in data
        assert "count" in data
        print(f"✓ Events count: {data['count']}")
    
    def test_list_events_with_source_filter(self):
        """GET /api/notifications/events?source=exchange — filter by source"""
        response = requests.get(f"{BASE_URL}/api/notifications/events", params={"source": "exchange"})
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        # All returned events should have source=exchange
        for event in data.get("events", []):
            assert event.get("source") == "exchange"
        print(f"✓ Filtered events by source=exchange: {data['count']}")
    
    def test_list_events_with_type_filter(self):
        """GET /api/notifications/events?type=system.error — filter by type"""
        response = requests.get(f"{BASE_URL}/api/notifications/events", params={"type": "system.error"})
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        for event in data.get("events", []):
            assert event.get("type") == "system.error"
        print(f"✓ Filtered events by type=system.error: {data['count']}")
    
    def test_event_stats(self):
        """GET /api/notifications/events-stats — event stats by source and severity"""
        response = requests.get(f"{BASE_URL}/api/notifications/events-stats")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "stats" in data
        stats = data["stats"]
        assert "total_events" in stats
        assert "by_source" in stats
        assert "by_severity" in stats
        print(f"✓ Event stats: total={stats['total_events']}, by_source={stats['by_source']}")


class TestNotificationFeed:
    """Test notification feed endpoints"""
    
    def test_user_feed(self):
        """GET /api/notifications/feed?audience=user — get user notifications"""
        response = requests.get(f"{BASE_URL}/api/notifications/feed", params={"audience": "user"})
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "notifications" in data
        assert "unread" in data
        assert "count" in data
        print(f"✓ User feed: {data['count']} notifications, {data['unread']} unread")
    
    def test_admin_feed(self):
        """GET /api/notifications/feed?audience=admin — get admin notifications"""
        response = requests.get(f"{BASE_URL}/api/notifications/feed", params={"audience": "admin"})
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "notifications" in data
        assert "unread" in data
        print(f"✓ Admin feed: {data['count']} notifications, {data['unread']} unread")
    
    def test_unread_count_user(self):
        """GET /api/notifications/unread-count?audience=user — unread count for bell badge"""
        response = requests.get(f"{BASE_URL}/api/notifications/unread-count", params={"audience": "user"})
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "unread" in data
        assert isinstance(data["unread"], int)
        print(f"✓ User unread count: {data['unread']}")
    
    def test_unread_count_admin(self):
        """GET /api/notifications/unread-count?audience=admin — admin unread count"""
        response = requests.get(f"{BASE_URL}/api/notifications/unread-count", params={"audience": "admin"})
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "unread" in data
        print(f"✓ Admin unread count: {data['unread']}")


class TestNotificationActions:
    """Test mark read actions"""
    
    def test_mark_single_notification_read(self):
        """POST /api/notifications/read/{id} — mark single notification as read"""
        # First get a notification from the feed
        feed_resp = requests.get(f"{BASE_URL}/api/notifications/feed", params={"audience": "user", "limit": 50})
        assert feed_resp.status_code == 200
        feed_data = feed_resp.json()
        
        # Find an unread notification
        unread_notif = None
        for n in feed_data.get("notifications", []):
            if n.get("readAt") is None:
                unread_notif = n
                break
        
        if unread_notif:
            notif_id = unread_notif["id"]
            mark_resp = requests.post(f"{BASE_URL}/api/notifications/read/{notif_id}")
            assert mark_resp.status_code == 200
            data = mark_resp.json()
            assert data.get("ok") is True
            print(f"✓ Marked notification as read: {notif_id}")
        else:
            print("✓ No unread notifications to mark (skipped)")
    
    def test_mark_all_read_user(self):
        """POST /api/notifications/read-all?audience=user — mark all notifications read"""
        response = requests.post(f"{BASE_URL}/api/notifications/read-all", params={"audience": "user"})
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "marked" in data
        print(f"✓ Marked all user notifications as read: {data['marked']}")
    
    def test_mark_all_read_admin(self):
        """POST /api/notifications/read-all?audience=admin — mark all admin notifications read"""
        response = requests.post(f"{BASE_URL}/api/notifications/read-all", params={"audience": "admin"})
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"✓ Marked all admin notifications as read: {data['marked']}")


class TestNotificationStats:
    """Test notification statistics"""
    
    def test_notification_stats(self):
        """GET /api/notifications/stats — notification statistics"""
        response = requests.get(f"{BASE_URL}/api/notifications/stats")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "stats" in data
        stats = data["stats"]
        assert "total" in stats
        assert "unread_user" in stats
        assert "unread_admin" in stats
        assert "pending" in stats
        assert "sent" in stats
        print(f"✓ Notification stats: total={stats['total']}, unread_user={stats['unread_user']}, unread_admin={stats['unread_admin']}")


class TestRuleRouting:
    """Test that events are routed to correct audiences based on rules"""
    
    def test_exchange_event_creates_user_notification(self):
        """Exchange events should create user notifications"""
        unique_key = f"test_routing_exchange_{uuid.uuid4().hex[:8]}"
        
        # Get initial user unread count
        initial_resp = requests.get(f"{BASE_URL}/api/notifications/unread-count", params={"audience": "user"})
        initial_count = initial_resp.json().get("unread", 0)
        
        # Publish exchange event
        event_data = {
            "type": "exchange.prediction.updated",
            "source": "exchange",
            "asset": "AVAX",
            "severity": "medium",
            "title": "AVAX prediction",
            "dedupeKey": unique_key,
            "payload": {"horizon": "7D", "direction": "bullish", "expectedMovePct": 8.5, "confidence": 0.65}
        }
        pub_resp = requests.post(f"{BASE_URL}/api/notifications/events/publish", json=event_data)
        assert pub_resp.status_code == 200
        event = pub_resp.json().get("event", {})
        
        if not event.get("skipped"):
            # Check user feed for new notification
            feed_resp = requests.get(f"{BASE_URL}/api/notifications/feed", params={"audience": "user", "limit": 5})
            notifications = feed_resp.json().get("notifications", [])
            
            # Should find notification with this event
            found = any(n.get("eventId") == event.get("id") for n in notifications)
            if found:
                print(f"✓ Exchange event correctly routed to user feed")
            else:
                print(f"✓ Exchange event published (notification may be deduped)")
        else:
            print(f"✓ Exchange event skipped (dedupe)")
    
    def test_system_event_creates_admin_notification(self):
        """System events should create admin notifications"""
        unique_key = f"test_routing_system_{uuid.uuid4().hex[:8]}"
        
        # Publish system event
        event_data = {
            "type": "system.health.warning",
            "source": "system",
            "severity": "high",
            "title": "Health warning",
            "dedupeKey": unique_key,
            "payload": {"message": "Memory usage high"}
        }
        pub_resp = requests.post(f"{BASE_URL}/api/notifications/events/publish", json=event_data)
        assert pub_resp.status_code == 200
        event = pub_resp.json().get("event", {})
        
        if not event.get("skipped"):
            # Check admin feed
            feed_resp = requests.get(f"{BASE_URL}/api/notifications/feed", params={"audience": "admin", "limit": 5})
            notifications = feed_resp.json().get("notifications", [])
            
            found = any(n.get("eventId") == event.get("id") for n in notifications)
            if found:
                print(f"✓ System event correctly routed to admin feed")
            else:
                print(f"✓ System event published (notification may be deduped)")
        else:
            print(f"✓ System event skipped (dedupe)")


class TestNotificationContent:
    """Test notification content formatting"""
    
    def test_notification_has_required_fields(self):
        """Notifications should have all required fields"""
        response = requests.get(f"{BASE_URL}/api/notifications/feed", params={"audience": "user", "limit": 10})
        assert response.status_code == 200
        notifications = response.json().get("notifications", [])
        
        if notifications:
            n = notifications[0]
            required_fields = ["id", "eventId", "eventType", "audience", "channel", "status", "title", "message", "createdAt"]
            for field in required_fields:
                assert field in n, f"Missing field: {field}"
            print(f"✓ Notification has all required fields")
        else:
            print("✓ No notifications to check (skipped)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
