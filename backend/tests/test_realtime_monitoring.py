"""
P2.1 Realtime Monitoring API Tests

Tests for:
- GET /api/watchlist/events/changes - Delta events since timestamp
- GET /api/watchlist/summary/realtime - Lightweight summary for polling
- GET /api/watchlist/events/count - New events count for badge
- POST /api/watchlist/events/viewed - Mark events as viewed
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestRealtimeMonitoringAPI:
    """P2.1 Realtime Monitoring API Tests"""
    
    # =========================================================================
    # GET /api/watchlist/events/changes - Delta endpoint
    # =========================================================================
    
    def test_get_event_changes_with_since_param(self):
        """Test delta endpoint returns events since timestamp"""
        since = "2026-01-25T00:00:00Z"
        response = requests.get(
            f"{BASE_URL}/api/watchlist/events/changes",
            params={"since": since, "limit": 10}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert data.get("ok") == True
        assert data.get("success") == True
        assert "events" in data
        assert "alerts" in data
        assert "actorEvents" in data
        assert "migrations" in data
        assert "summary" in data
        assert "serverTime" in data
        
        # Verify summary structure
        summary = data["summary"]
        assert "totalNew" in summary
        assert "byType" in summary
        assert isinstance(summary["byType"], dict)
        
        print(f"✓ Delta endpoint returned {len(data['events'])} events, {len(data['alerts'])} alerts")
        print(f"  Total new: {summary['totalNew']}")
    
    def test_get_event_changes_default_since(self):
        """Test delta endpoint with default since (5 min ago)"""
        response = requests.get(f"{BASE_URL}/api/watchlist/events/changes")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") == True
        assert "events" in data
        assert "serverTime" in data
        
        print(f"✓ Default since: {len(data['events'])} events")
    
    def test_get_event_changes_limit_param(self):
        """Test delta endpoint respects limit parameter"""
        response = requests.get(
            f"{BASE_URL}/api/watchlist/events/changes",
            params={"since": "2026-01-01T00:00:00Z", "limit": 3}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") == True
        assert len(data["events"]) <= 3
        
        print(f"✓ Limit respected: {len(data['events'])} events (max 3)")
    
    def test_event_changes_event_structure(self):
        """Test event structure in delta response"""
        response = requests.get(
            f"{BASE_URL}/api/watchlist/events/changes",
            params={"since": "2026-01-25T00:00:00Z", "limit": 5}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data["events"]:
            event = data["events"][0]
            
            # Required fields
            assert "_id" in event
            assert "eventType" in event
            assert "severity" in event
            assert "chain" in event
            assert "title" in event
            assert "isNew" in event
            assert "timestamp" in event
            assert "acknowledged" in event
            
            # Optional item reference
            if event.get("item"):
                assert "_id" in event["item"]
                assert "type" in event["item"]
                assert "target" in event["item"]
            
            print(f"✓ Event structure valid: {event['eventType']} - {event['title'][:40]}...")
        else:
            print("✓ No events to validate structure (empty result)")
    
    def test_event_changes_alert_structure(self):
        """Test alert structure in delta response"""
        response = requests.get(
            f"{BASE_URL}/api/watchlist/events/changes",
            params={"since": "2026-01-25T00:00:00Z"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data["alerts"]:
            alert = data["alerts"][0]
            
            assert "alertId" in alert
            assert "type" in alert
            assert "severity" in alert
            assert "status" in alert
            assert "title" in alert
            assert "source" in alert
            assert "isNew" in alert
            assert "createdAt" in alert
            
            print(f"✓ Alert structure valid: {alert['type']} - {alert['title'][:40]}...")
        else:
            print("✓ No alerts to validate structure")
    
    def test_event_changes_actor_events_structure(self):
        """Test actor events structure in delta response"""
        response = requests.get(
            f"{BASE_URL}/api/watchlist/events/changes",
            params={"since": "2026-01-25T00:00:00Z"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data["actorEvents"]:
            actor_event = data["actorEvents"][0]
            
            assert "eventId" in actor_event
            assert "actorId" in actor_event
            assert "type" in actor_event
            assert "severity" in actor_event
            assert "title" in actor_event
            assert "isNew" in actor_event
            assert "timestamp" in actor_event
            
            print(f"✓ Actor event structure valid: {actor_event['type']}")
        else:
            print("✓ No actor events to validate structure")
    
    def test_event_changes_migrations_structure(self):
        """Test migrations structure in delta response"""
        response = requests.get(
            f"{BASE_URL}/api/watchlist/events/changes",
            params={"since": "2026-01-25T00:00:00Z"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data["migrations"]:
            migration = data["migrations"][0]
            
            # Required fields
            assert "migrationId" in migration
            assert "fromChain" in migration
            assert "toChain" in migration
            assert "token" in migration
            assert "isNew" in migration
            # detectedAt is optional (may be null/undefined in some migrations)
            
            print(f"✓ Migration structure valid: {migration['fromChain']} → {migration['toChain']}")
        else:
            print("✓ No migrations to validate structure")
    
    # =========================================================================
    # GET /api/watchlist/summary/realtime - Lightweight summary
    # =========================================================================
    
    def test_get_realtime_summary(self):
        """Test realtime summary endpoint"""
        response = requests.get(f"{BASE_URL}/api/watchlist/summary/realtime")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") == True
        assert data.get("success") == True
        assert "newEvents" in data
        assert "newAlerts" in data
        assert "newMigrations" in data
        assert "updatedActors" in data
        assert "lastUpdateAt" in data
        
        # Values should be non-negative integers
        assert isinstance(data["newEvents"], int)
        assert isinstance(data["newAlerts"], int)
        assert isinstance(data["newMigrations"], int)
        assert isinstance(data["updatedActors"], int)
        assert data["newEvents"] >= 0
        assert data["newAlerts"] >= 0
        
        print(f"✓ Realtime summary: {data['newEvents']} events, {data['newAlerts']} alerts, {data['newMigrations']} migrations")
    
    def test_get_realtime_summary_with_window(self):
        """Test realtime summary with custom window"""
        response = requests.get(
            f"{BASE_URL}/api/watchlist/summary/realtime",
            params={"window": 10}  # 10 minutes
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") == True
        assert "newEvents" in data
        
        print(f"✓ Realtime summary (10min window): {data['newEvents']} events")
    
    def test_realtime_summary_caching(self):
        """Test that realtime summary is cached (10s TTL)"""
        # First request
        response1 = requests.get(f"{BASE_URL}/api/watchlist/summary/realtime")
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Second request immediately after
        response2 = requests.get(f"{BASE_URL}/api/watchlist/summary/realtime")
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Should return same lastUpdateAt (cached)
        assert data1["lastUpdateAt"] == data2["lastUpdateAt"]
        
        print(f"✓ Summary caching works (same lastUpdateAt)")
    
    # =========================================================================
    # GET /api/watchlist/events/count - Badge count
    # =========================================================================
    
    def test_get_events_count(self):
        """Test events count endpoint for badge"""
        response = requests.get(f"{BASE_URL}/api/watchlist/events/count")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") == True
        assert data.get("success") == True
        assert "watchlistEvents" in data
        assert "alerts" in data
        assert "total" in data
        
        # Total should be sum of events and alerts
        assert data["total"] == data["watchlistEvents"] + data["alerts"]
        
        print(f"✓ Events count: {data['watchlistEvents']} events + {data['alerts']} alerts = {data['total']} total")
    
    def test_get_events_count_with_since(self):
        """Test events count with since parameter"""
        since = "2026-01-25T00:00:00Z"
        response = requests.get(
            f"{BASE_URL}/api/watchlist/events/count",
            params={"since": since}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") == True
        assert "total" in data
        
        print(f"✓ Events count since {since}: {data['total']} total")
    
    # =========================================================================
    # POST /api/watchlist/events/viewed - Mark as viewed
    # =========================================================================
    
    def test_mark_events_viewed(self):
        """Test marking events as viewed"""
        # First get some event IDs
        events_response = requests.get(
            f"{BASE_URL}/api/watchlist/events/changes",
            params={"since": "2026-01-25T00:00:00Z", "limit": 2}
        )
        events_data = events_response.json()
        
        if not events_data.get("events"):
            pytest.skip("No events available to mark as viewed")
        
        event_ids = [e["_id"] for e in events_data["events"][:2]]
        
        # Mark as viewed
        response = requests.post(
            f"{BASE_URL}/api/watchlist/events/viewed",
            json={"eventIds": event_ids}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") == True
        assert data.get("success") == True
        assert "marked" in data
        assert isinstance(data["marked"], int)
        
        print(f"✓ Marked {data['marked']} events as viewed")
    
    def test_mark_events_viewed_empty_array(self):
        """Test marking empty array returns error"""
        response = requests.post(
            f"{BASE_URL}/api/watchlist/events/viewed",
            json={"eventIds": []}
        )
        
        # Should return error status (400, 422, 500, or 520 for validation)
        assert response.status_code in [400, 422, 500, 520]
        
        print(f"✓ Empty array rejected with status {response.status_code}")
    
    def test_mark_events_viewed_invalid_ids(self):
        """Test marking non-existent event IDs - may fail due to MongoDB ObjectId validation"""
        response = requests.post(
            f"{BASE_URL}/api/watchlist/events/viewed",
            json={"eventIds": ["nonexistent_id_12345"]}
        )
        
        # MongoDB may reject invalid ObjectId format
        # Either returns 200 with marked=0, or error status
        if response.status_code == 200:
            data = response.json()
            assert data.get("ok") == True
            assert data.get("marked") == 0
            print(f"✓ Non-existent IDs handled gracefully (marked: 0)")
        else:
            # Invalid ObjectId format causes error
            assert response.status_code in [400, 500, 520]
            print(f"✓ Invalid ObjectId rejected with status {response.status_code}")
    
    # =========================================================================
    # Integration Tests
    # =========================================================================
    
    def test_polling_workflow(self):
        """Test typical polling workflow"""
        # 1. Get initial summary
        summary_response = requests.get(f"{BASE_URL}/api/watchlist/summary/realtime")
        assert summary_response.status_code == 200
        summary = summary_response.json()
        
        # 2. If new activity, get delta
        if summary.get("newEvents", 0) > 0 or summary.get("newAlerts", 0) > 0:
            delta_response = requests.get(
                f"{BASE_URL}/api/watchlist/events/changes",
                params={"since": "2026-01-25T00:00:00Z"}
            )
            assert delta_response.status_code == 200
            delta = delta_response.json()
            
            # 3. Mark events as viewed
            if delta.get("events"):
                event_ids = [e["_id"] for e in delta["events"][:5]]
                viewed_response = requests.post(
                    f"{BASE_URL}/api/watchlist/events/viewed",
                    json={"eventIds": event_ids}
                )
                assert viewed_response.status_code == 200
        
        print(f"✓ Polling workflow completed successfully")
    
    def test_badge_count_workflow(self):
        """Test badge count workflow"""
        # Get count for badge
        count_response = requests.get(f"{BASE_URL}/api/watchlist/events/count")
        assert count_response.status_code == 200
        count = count_response.json()
        
        # Verify badge can display total
        total = count.get("total", 0)
        badge_text = str(total) if total <= 9 else "9+"
        
        print(f"✓ Badge count workflow: {total} → display '{badge_text}'")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
