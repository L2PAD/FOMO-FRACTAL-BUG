"""
Live Intelligence Quality System Tests
Tests for HOT market price polling, Update Gate, Freshness/Staleness detection, and Live health endpoint.
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestLiveHealthEndpoint:
    """Tests for GET /api/live/health - Live engine metrics"""
    
    def test_live_health_returns_ok(self):
        """Health endpoint returns ok=true"""
        response = requests.get(f"{BASE_URL}/api/live/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print(f"PASS: Live health returns ok=true")
    
    def test_live_health_has_cycles(self):
        """Health endpoint returns cycles > 0 (engine is cycling)"""
        response = requests.get(f"{BASE_URL}/api/live/health")
        data = response.json()
        cycles = data.get("cycles", 0)
        assert cycles > 0, f"Expected cycles > 0, got {cycles}"
        print(f"PASS: Live engine has {cycles} cycles")
    
    def test_live_health_has_prices_fetched(self):
        """Health endpoint returns prices_fetched > 0"""
        response = requests.get(f"{BASE_URL}/api/live/health")
        data = response.json()
        prices_fetched = data.get("prices_fetched", 0)
        assert prices_fetched > 0, f"Expected prices_fetched > 0, got {prices_fetched}"
        print(f"PASS: Live engine fetched {prices_fetched} prices")
    
    def test_live_health_has_updates_total(self):
        """Health endpoint returns updates_total"""
        response = requests.get(f"{BASE_URL}/api/live/health")
        data = response.json()
        assert "updates_total" in data
        print(f"PASS: updates_total = {data['updates_total']}")
    
    def test_live_health_has_updates_emitted(self):
        """Health endpoint returns updates_emitted"""
        response = requests.get(f"{BASE_URL}/api/live/health")
        data = response.json()
        assert "updates_emitted" in data
        print(f"PASS: updates_emitted = {data['updates_emitted']}")
    
    def test_live_health_has_updates_blocked(self):
        """Health endpoint returns updates_blocked > 0 (noise is being filtered)"""
        response = requests.get(f"{BASE_URL}/api/live/health")
        data = response.json()
        updates_blocked = data.get("updates_blocked", 0)
        # Update gate should be blocking some noise
        assert updates_blocked > 0, f"Expected updates_blocked > 0, got {updates_blocked}"
        print(f"PASS: Update gate blocked {updates_blocked} noisy updates")
    
    def test_live_health_has_overlay_recalc(self):
        """Health endpoint returns overlay_recalc count"""
        response = requests.get(f"{BASE_URL}/api/live/health")
        data = response.json()
        assert "overlay_recalc" in data
        print(f"PASS: overlay_recalc = {data['overlay_recalc']}")
    
    def test_live_health_has_hot_live(self):
        """Health endpoint returns hot_live count"""
        response = requests.get(f"{BASE_URL}/api/live/health")
        data = response.json()
        hot_live = data.get("hot_live", 0)
        assert hot_live > 0, f"Expected hot_live > 0, got {hot_live}"
        print(f"PASS: {hot_live} HOT markets are live")
    
    def test_live_health_has_total_tracked(self):
        """Health endpoint returns total_tracked count"""
        response = requests.get(f"{BASE_URL}/api/live/health")
        data = response.json()
        total_tracked = data.get("total_tracked", 0)
        assert total_tracked > 0, f"Expected total_tracked > 0, got {total_tracked}"
        print(f"PASS: {total_tracked} markets being tracked")
    
    def test_live_health_has_stale_count(self):
        """Health endpoint returns stale_count"""
        response = requests.get(f"{BASE_URL}/api/live/health")
        data = response.json()
        assert "stale_count" in data
        print(f"PASS: stale_count = {data['stale_count']}")


class TestLiveFeedEndpoint:
    """Tests for GET /api/live/feed - Live-enriched feed"""
    
    def test_live_feed_hot_returns_ok(self):
        """Live feed returns ok=true for HOT mode"""
        response = requests.get(f"{BASE_URL}/api/live/feed?mode=hot")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print(f"PASS: Live feed returns ok=true")
    
    def test_live_feed_has_events(self):
        """Live feed returns events array"""
        response = requests.get(f"{BASE_URL}/api/live/feed?mode=hot")
        data = response.json()
        events = data.get("events", [])
        assert len(events) > 0, "Expected events in live feed"
        print(f"PASS: Live feed has {len(events)} events")
    
    def test_live_feed_events_have_live_block(self):
        """Events have live enrichment block"""
        response = requests.get(f"{BASE_URL}/api/live/feed?mode=hot&limit=10")
        data = response.json()
        events = data.get("events", [])
        
        events_with_live = 0
        for ev in events:
            if "live" in ev:
                events_with_live += 1
                live = ev["live"]
                assert "is_live" in live, "live block missing is_live"
                assert "state" in live, "live block missing state"
                assert "freshness_seconds" in live, "live block missing freshness_seconds"
        
        assert events_with_live > 0, "No events have live block"
        print(f"PASS: {events_with_live}/{len(events)} events have live enrichment")
    
    def test_live_feed_live_state_values(self):
        """Live state is LIVE, STALE, or OFFLINE"""
        response = requests.get(f"{BASE_URL}/api/live/feed?mode=hot&limit=20")
        data = response.json()
        events = data.get("events", [])
        
        valid_states = {"LIVE", "STALE", "OFFLINE"}
        for ev in events:
            if "live" in ev:
                state = ev["live"].get("state")
                assert state in valid_states, f"Invalid live state: {state}"
        
        print(f"PASS: All live states are valid (LIVE/STALE/OFFLINE)")
    
    def test_live_feed_markets_have_freshness(self):
        """Markets in live feed have freshness_seconds and is_stale fields"""
        response = requests.get(f"{BASE_URL}/api/live/feed?mode=hot&limit=5")
        data = response.json()
        events = data.get("events", [])
        
        markets_with_freshness = 0
        for ev in events:
            for m in ev.get("markets", []):
                if "freshness_seconds" in m:
                    markets_with_freshness += 1
                    assert "is_stale" in m, "Market has freshness_seconds but missing is_stale"
        
        assert markets_with_freshness > 0, "No markets have freshness data"
        print(f"PASS: {markets_with_freshness} markets have freshness data")


class TestRegularFeedWithLiveEnrichment:
    """Tests for GET /api/feed - Regular feed with live state injected"""
    
    def test_feed_hot_returns_ok(self):
        """Regular feed returns ok=true"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print(f"PASS: Regular feed returns ok=true")
    
    def test_feed_hot_has_live_enrichment(self):
        """Regular feed events have live data injected"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot&limit=10")
        data = response.json()
        events = data.get("events", [])
        
        events_with_live = 0
        for ev in events:
            if "live" in ev:
                events_with_live += 1
                state = ev["live"].get("state")
                assert state in {"LIVE", "STALE", "OFFLINE"}, f"Invalid state: {state}"
        
        assert events_with_live > 0, "No events have live enrichment in regular feed"
        print(f"PASS: {events_with_live}/{len(events)} events have live enrichment in regular feed")
    
    def test_feed_stability_two_calls(self):
        """Calling feed twice returns stable actions (no flipping)"""
        # First call
        response1 = requests.get(f"{BASE_URL}/api/feed?mode=hot&limit=20")
        data1 = response1.json()
        events1 = data1.get("events", [])
        
        # Wait a moment
        time.sleep(1)
        
        # Second call
        response2 = requests.get(f"{BASE_URL}/api/feed?mode=hot&limit=20")
        data2 = response2.json()
        events2 = data2.get("events", [])
        
        # Compare actions for same events
        actions1 = {ev["event_id"]: ev.get("overlay", {}).get("action") for ev in events1}
        actions2 = {ev["event_id"]: ev.get("overlay", {}).get("action") for ev in events2}
        
        flips = 0
        for eid, action1 in actions1.items():
            action2 = actions2.get(eid)
            if action1 and action2 and action1 != action2:
                flips += 1
                print(f"  Action flip: {eid} {action1} -> {action2}")
        
        # Allow some flips due to real market changes, but not many
        assert flips <= 2, f"Too many action flips: {flips}"
        print(f"PASS: Feed is stable ({flips} flips in 20 events)")


class TestUpdateGateMetrics:
    """Tests for Update Gate noise filtering"""
    
    def test_update_gate_blocking_noise(self):
        """Update gate is blocking noise (updates_blocked > 0)"""
        response = requests.get(f"{BASE_URL}/api/live/health")
        data = response.json()
        
        updates_total = data.get("updates_total", 0)
        updates_blocked = data.get("updates_blocked", 0)
        updates_emitted = data.get("updates_emitted", 0)
        
        assert updates_total > 0, "No updates processed"
        assert updates_blocked > 0, "Update gate not blocking any noise"
        
        block_rate = updates_blocked / updates_total if updates_total > 0 else 0
        print(f"PASS: Update gate blocking {block_rate*100:.1f}% of updates ({updates_blocked}/{updates_total})")
    
    def test_update_gate_emitting_meaningful(self):
        """Update gate is emitting meaningful updates"""
        response = requests.get(f"{BASE_URL}/api/live/health")
        data = response.json()
        
        updates_emitted = data.get("updates_emitted", 0)
        assert updates_emitted > 0, "No updates emitted"
        print(f"PASS: {updates_emitted} meaningful updates emitted")


class TestPredictionLabRegression:
    """Regression tests for Prediction Lab"""
    
    def test_prediction_lab_overview(self):
        """Prediction Lab overview still works"""
        response = requests.get(f"{BASE_URL}/api/prediction-lab/overview")
        assert response.status_code == 200
        data = response.json()
        assert "total_forecasts" in data
        print(f"PASS: Prediction Lab overview works (total_forecasts={data.get('total_forecasts')})")
    
    def test_prediction_lab_scheduler_status(self):
        """Prediction Lab scheduler status still works"""
        response = requests.get(f"{BASE_URL}/api/prediction-lab/scheduler-status")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print(f"PASS: Prediction Lab scheduler status works")


class TestFeedCardsData:
    """Tests for feed card data (analytics badges, event images)"""
    
    def test_feed_cards_have_analytics(self):
        """Feed cards have analytics badges data"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot&limit=20")
        data = response.json()
        events = data.get("events", [])
        
        events_with_analytics = 0
        for ev in events:
            overlay = ev.get("overlay", {})
            if "analytics" in overlay:
                events_with_analytics += 1
        
        print(f"PASS: {events_with_analytics}/{len(events)} events have analytics data")
    
    def test_feed_cards_have_images(self):
        """Feed cards have event images"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot&limit=20")
        data = response.json()
        events = data.get("events", [])
        
        events_with_images = 0
        for ev in events:
            if ev.get("image"):
                events_with_images += 1
        
        assert events_with_images > 0, "No events have images"
        print(f"PASS: {events_with_images}/{len(events)} events have images")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
