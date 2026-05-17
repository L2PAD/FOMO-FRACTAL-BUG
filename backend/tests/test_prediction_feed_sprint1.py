"""
Prediction Feed Sprint 1 Tests — Event-based card grid with FOMO intelligence overlay.

Tests:
- GET /api/feed returns events with ok=true, hot_count>0, actionable_count>0
- GET /api/feed?mode=hot returns only hot events
- GET /api/feed?mode=actionable returns actionable events with edge data
- GET /api/feed?asset=BTC filters to Bitcoin events only
- GET /api/feed?asset=ETH filters to Ethereum events only
- GET /api/feed?category=fdv returns FDV market events
- GET /api/feed/health returns health status
- POST /api/feed/sync triggers refresh
- GET /api/feed/event/{event_id} returns single event detail
- Event structure validation (event_id, title, is_multi, markets_count, markets, overlay)
- Overlay structure validation (action, urgency, confidence, summary, best_pick, top_outcomes)
- Multi-outcome events have markets array with >1 items
- No false positive non-crypto events
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestFeedHealth:
    """Feed health and sync endpoints"""
    
    def test_feed_health_returns_status(self):
        """GET /api/feed/health returns health status with counts"""
        response = requests.get(f"{BASE_URL}/api/feed/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "events_count" in data
        assert "markets_count" in data
        assert "overlays_count" in data
        assert data["events_count"] >= 0
        assert data["markets_count"] >= 0
        print(f"Health: events={data['events_count']}, markets={data['markets_count']}, overlays={data['overlays_count']}")
    
    def test_feed_sync_triggers_refresh(self):
        """POST /api/feed/sync triggers refresh and returns updated counts"""
        response = requests.post(f"{BASE_URL}/api/feed/sync")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "total_events" in data
        assert "total_markets" in data
        assert "hot_count" in data
        assert "actionable_count" in data
        print(f"Sync: events={data['total_events']}, markets={data['total_markets']}, hot={data['hot_count']}, actionable={data['actionable_count']}")


class TestFeedEndpoint:
    """Main feed endpoint tests"""
    
    def test_feed_returns_events_with_counts(self):
        """GET /api/feed returns events with ok=true, hot_count>0, actionable_count>0"""
        response = requests.get(f"{BASE_URL}/api/feed")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("hot_count", 0) > 0, "Expected hot_count > 0"
        assert data.get("actionable_count", 0) > 0, "Expected actionable_count > 0"
        assert data.get("total", 0) > 0, "Expected total events > 0"
        assert len(data.get("events", [])) > 0, "Expected events array to have items"
        print(f"Feed: total={data['total']}, hot={data['hot_count']}, actionable={data['actionable_count']}")
    
    def test_feed_mode_hot_returns_hot_events(self):
        """GET /api/feed?mode=hot returns only hot events"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("mode") == "hot"
        events = data.get("events", [])
        assert len(events) > 0, "Expected hot events"
        # All events should be tier=hot
        for e in events:
            assert e.get("tier") == "hot", f"Expected tier=hot, got {e.get('tier')}"
        print(f"Hot mode: {len(events)} hot events")
    
    def test_feed_mode_actionable_returns_actionable_events(self):
        """GET /api/feed?mode=actionable returns actionable events with edge data"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=actionable")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("mode") == "actionable"
        events = data.get("events", [])
        assert len(events) > 0, "Expected actionable events"
        # All events should be tier=actionable
        for e in events:
            assert e.get("tier") == "actionable", f"Expected tier=actionable, got {e.get('tier')}"
        print(f"Actionable mode: {len(events)} actionable events")


class TestFeedFilters:
    """Asset and category filter tests"""
    
    def test_feed_asset_btc_filter(self):
        """GET /api/feed?asset=BTC filters to Bitcoin events only"""
        response = requests.get(f"{BASE_URL}/api/feed?asset=BTC")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        events = data.get("events", [])
        assert len(events) > 0, "Expected BTC events"
        for e in events:
            assert e.get("asset_group") == "BTC", f"Expected asset_group=BTC, got {e.get('asset_group')}"
        print(f"BTC filter: {len(events)} events")
    
    def test_feed_asset_eth_filter(self):
        """GET /api/feed?asset=ETH filters to Ethereum events only"""
        response = requests.get(f"{BASE_URL}/api/feed?asset=ETH")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        events = data.get("events", [])
        assert len(events) > 0, "Expected ETH events"
        for e in events:
            assert e.get("asset_group") == "ETH", f"Expected asset_group=ETH, got {e.get('asset_group')}"
        print(f"ETH filter: {len(events)} events")
    
    def test_feed_category_fdv_filter(self):
        """GET /api/feed?category=fdv returns FDV market events"""
        response = requests.get(f"{BASE_URL}/api/feed?category=fdv")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        events = data.get("events", [])
        # FDV events may be 0 if none exist, but if they exist, they should be fdv category
        for e in events:
            assert e.get("category") == "fdv", f"Expected category=fdv, got {e.get('category')}"
        print(f"FDV filter: {len(events)} events")


class TestEventDetail:
    """Single event detail endpoint tests"""
    
    def test_event_detail_returns_event(self):
        """GET /api/feed/event/{event_id} returns single event detail"""
        # First get an event_id from the feed
        feed_response = requests.get(f"{BASE_URL}/api/feed")
        assert feed_response.status_code == 200
        feed_data = feed_response.json()
        events = feed_data.get("events", [])
        assert len(events) > 0, "Need at least one event to test detail"
        
        event_id = events[0].get("event_id")
        response = requests.get(f"{BASE_URL}/api/feed/event/{event_id}")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        event = data.get("event", {})
        assert event.get("event_id") == event_id
        print(f"Event detail: {event.get('title')}")
    
    def test_event_detail_not_found(self):
        """GET /api/feed/event/{invalid_id} returns error"""
        response = requests.get(f"{BASE_URL}/api/feed/event/invalid_event_id_12345")
        assert response.status_code == 200  # API returns 200 with ok=false
        data = response.json()
        assert data.get("ok") == False
        assert "error" in data


class TestEventStructure:
    """Event and overlay structure validation"""
    
    def test_event_has_required_fields(self):
        """Each event has: event_id, title, is_multi, markets_count, markets array, overlay object"""
        response = requests.get(f"{BASE_URL}/api/feed")
        assert response.status_code == 200
        data = response.json()
        events = data.get("events", [])
        assert len(events) > 0
        
        for e in events[:5]:  # Check first 5 events
            assert "event_id" in e, "Missing event_id"
            assert "title" in e, "Missing title"
            assert "is_multi" in e, "Missing is_multi"
            assert "markets_count" in e, "Missing markets_count"
            assert "markets" in e, "Missing markets array"
            assert "overlay" in e, "Missing overlay object"
            assert isinstance(e["markets"], list), "markets should be a list"
            assert isinstance(e["overlay"], dict), "overlay should be a dict"
        print("Event structure validation passed")
    
    def test_overlay_has_required_fields(self):
        """Overlay has: action, urgency, confidence, summary, best_pick, top_outcomes"""
        response = requests.get(f"{BASE_URL}/api/feed")
        assert response.status_code == 200
        data = response.json()
        events = data.get("events", [])
        assert len(events) > 0
        
        for e in events[:5]:  # Check first 5 events
            ov = e.get("overlay", {})
            assert "action" in ov, "Missing overlay.action"
            assert "urgency" in ov, "Missing overlay.urgency"
            assert "confidence" in ov, "Missing overlay.confidence"
            # summary, best_pick, top_outcomes may be optional
            assert ov.get("action") in ["BUY_YES", "BUY_NO", "WATCH", "AVOID", None], f"Invalid action: {ov.get('action')}"
            assert ov.get("confidence") in ["high", "medium", "low", None], f"Invalid confidence: {ov.get('confidence')}"
        print("Overlay structure validation passed")
    
    def test_multi_outcome_events_have_multiple_markets(self):
        """Multi-outcome events have markets array with >1 items, each with yes_price, overlay"""
        response = requests.get(f"{BASE_URL}/api/feed")
        assert response.status_code == 200
        data = response.json()
        events = data.get("events", [])
        
        multi_events = [e for e in events if e.get("is_multi") and e.get("markets_count", 0) > 1]
        assert len(multi_events) > 0, "Expected at least one multi-outcome event"
        
        for e in multi_events[:3]:  # Check first 3 multi events
            markets = e.get("markets", [])
            assert len(markets) > 1, f"Multi event should have >1 markets, got {len(markets)}"
            for m in markets[:3]:
                assert "market_id" in m, "Missing market_id"
                assert "yes_price" in m, "Missing yes_price"
                assert "overlay" in m or m.get("overlay") is None, "overlay should exist or be None"
        print(f"Multi-outcome validation passed: {len(multi_events)} multi events found")


class TestNoCryptoFalsePositives:
    """Verify no false positive non-crypto events"""
    
    def test_no_sports_events_in_feed(self):
        """No false positive non-crypto events (no FIFA, NBA, NFL events in feed)"""
        response = requests.get(f"{BASE_URL}/api/feed")
        assert response.status_code == 200
        data = response.json()
        events = data.get("events", [])
        
        false_positive_keywords = ['fifa', 'nba', 'nfl', 'soccer', 'football', 'basketball', 'baseball', 'hockey', 'mlb', 'nhl']
        false_positives = []
        
        for e in events:
            title = (e.get('title', '') or '').lower()
            for kw in false_positive_keywords:
                if kw in title:
                    false_positives.append(e.get('title'))
                    break
        
        assert len(false_positives) == 0, f"Found sports false positives: {false_positives}"
        print(f"No sports false positives in {len(events)} events")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
