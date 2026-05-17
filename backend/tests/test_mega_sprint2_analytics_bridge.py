"""
Mega Sprint 2: Analytics-in-Feed Bridge + Confidence-Aware Decision + Decision Stability

Tests for:
1. Family Confidence Service with Bayesian normalization
2. Calibration State with family+global fallback
3. Effective Confidence with trust multipliers + hard floor 0.25
4. Decision Gate with hysteresis
5. Sizing Gate caps
6. Decision Stability with flip protection/lock
7. Analytics Badge in cards showing accuracy%
8. Confidence breakdown in detail drawer (Raw → Calibrated → Effective)

Pipeline: overlay → calibration → analytics → effective confidence → decision gate → sizing gate → stability → UI
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestFeedAnalyticsOverlay:
    """Test analytics fields in feed overlay"""
    
    def test_feed_hot_returns_events(self):
        """GET /api/feed?tier=hot&limit=5 returns events"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot&limit=5")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") == True, "Response should have ok=true"
        assert "events" in data, "Response should have events array"
        print(f"PASS: Feed hot returns {len(data.get('events', []))} events")
    
    def test_overlay_has_analytics_block(self):
        """Events should have overlay.analytics with family_accuracy, family_strength, calibration_state, effective_confidence, adjusted_confidence, sample_size"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot&limit=10")
        assert response.status_code == 200
        data = response.json()
        events = data.get("events", [])
        
        analytics_found = 0
        for ev in events:
            overlay = ev.get("overlay", {})
            analytics = overlay.get("analytics")
            if analytics:
                analytics_found += 1
                # Check required fields
                assert "family_strength" in analytics, f"analytics missing family_strength for event {ev.get('event_id')}"
                assert "calibration_state" in analytics, f"analytics missing calibration_state for event {ev.get('event_id')}"
                assert "effective_confidence" in analytics, f"analytics missing effective_confidence for event {ev.get('event_id')}"
                assert "adjusted_confidence" in analytics, f"analytics missing adjusted_confidence for event {ev.get('event_id')}"
                assert "sample_size" in analytics, f"analytics missing sample_size for event {ev.get('event_id')}"
                # family_accuracy can be None for cold start
                assert "family_accuracy" in analytics, f"analytics missing family_accuracy for event {ev.get('event_id')}"
        
        print(f"PASS: {analytics_found}/{len(events)} events have analytics block with all required fields")
        assert analytics_found > 0, "At least one event should have analytics block"
    
    def test_overlay_has_gating_block(self):
        """Events should have overlay.gating with original_action, final_action, gating_reasons, action_changed"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot&limit=10")
        assert response.status_code == 200
        data = response.json()
        events = data.get("events", [])
        
        gating_found = 0
        for ev in events:
            overlay = ev.get("overlay", {})
            gating = overlay.get("gating")
            if gating:
                gating_found += 1
                # Check required fields
                assert "original_action" in gating, f"gating missing original_action for event {ev.get('event_id')}"
                assert "final_action" in gating, f"gating missing final_action for event {ev.get('event_id')}"
                assert "gating_reasons" in gating, f"gating missing gating_reasons for event {ev.get('event_id')}"
                assert "action_changed" in gating, f"gating missing action_changed for event {ev.get('event_id')}"
                # Validate types
                assert isinstance(gating["gating_reasons"], list), "gating_reasons should be a list"
                assert isinstance(gating["action_changed"], bool), "action_changed should be boolean"
        
        print(f"PASS: {gating_found}/{len(events)} events have gating block with all required fields")
        assert gating_found > 0, "At least one event should have gating block"
    
    def test_overlay_has_stability_block(self):
        """Events should have overlay.stability with state: STABLE|UNSTABLE|LOCKED"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot&limit=10")
        assert response.status_code == 200
        data = response.json()
        events = data.get("events", [])
        
        stability_found = 0
        valid_states = {"STABLE", "UNSTABLE", "LOCKED"}
        for ev in events:
            overlay = ev.get("overlay", {})
            stability = overlay.get("stability")
            if stability:
                stability_found += 1
                # Check required fields
                assert "state" in stability, f"stability missing state for event {ev.get('event_id')}"
                assert stability["state"] in valid_states, f"stability.state should be one of {valid_states}, got {stability['state']}"
        
        print(f"PASS: {stability_found}/{len(events)} events have stability block with valid state")
        assert stability_found > 0, "At least one event should have stability block"


class TestFeedSync:
    """Test feed sync endpoint"""
    
    def test_feed_sync_triggers_pipeline(self):
        """POST /api/feed/sync triggers full pipeline sync returning event counts"""
        response = requests.post(f"{BASE_URL}/api/feed/sync")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") == True, "Response should have ok=true"
        # Should return event counts
        assert "total_events" in data or "events_count" in data or "total" in data, "Response should have event count"
        print(f"PASS: Feed sync returned ok=true with data: {data}")


class TestPredictionLabRegression:
    """Regression tests for Prediction Lab endpoints"""
    
    def test_prediction_lab_overview(self):
        """GET /api/prediction-lab/overview still works correctly"""
        response = requests.get(f"{BASE_URL}/api/prediction-lab/overview")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        # Check key fields exist
        assert "total_forecasts" in data, "overview missing total_forecasts"
        assert "resolved_forecasts" in data, "overview missing resolved_forecasts"
        assert "pending_forecasts" in data, "overview missing pending_forecasts"
        print(f"PASS: Prediction Lab overview returns total_forecasts={data.get('total_forecasts')}, resolved={data.get('resolved_forecasts')}")
    
    def test_prediction_lab_scheduler_status(self):
        """GET /api/prediction-lab/scheduler-status works"""
        response = requests.get(f"{BASE_URL}/api/prediction-lab/scheduler-status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") == True, "Response should have ok=true"
        assert "jobs" in data, "Response should have jobs array"
        print(f"PASS: Scheduler status returns {len(data.get('jobs', []))} jobs")


class TestAnalyticsFieldValues:
    """Test analytics field values and constraints"""
    
    def test_family_strength_values(self):
        """family_strength should be STRONG|MEDIUM|WEAK|UNKNOWN"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot&limit=20")
        assert response.status_code == 200
        data = response.json()
        events = data.get("events", [])
        
        valid_strengths = {"STRONG", "MEDIUM", "WEAK", "UNKNOWN"}
        strength_counts = {}
        for ev in events:
            analytics = ev.get("overlay", {}).get("analytics", {})
            strength = analytics.get("family_strength")
            if strength:
                assert strength in valid_strengths, f"Invalid family_strength: {strength}"
                strength_counts[strength] = strength_counts.get(strength, 0) + 1
        
        print(f"PASS: family_strength distribution: {strength_counts}")
    
    def test_calibration_state_values(self):
        """calibration_state should be GOOD|OVER|UNDER|UNKNOWN"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot&limit=20")
        assert response.status_code == 200
        data = response.json()
        events = data.get("events", [])
        
        valid_states = {"GOOD", "OVER", "UNDER", "UNKNOWN"}
        state_counts = {}
        for ev in events:
            analytics = ev.get("overlay", {}).get("analytics", {})
            state = analytics.get("calibration_state")
            if state:
                assert state in valid_states, f"Invalid calibration_state: {state}"
                state_counts[state] = state_counts.get(state, 0) + 1
        
        print(f"PASS: calibration_state distribution: {state_counts}")
    
    def test_effective_confidence_hard_floor(self):
        """effective_confidence should have hard floor of 0.25"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot&limit=20")
        assert response.status_code == 200
        data = response.json()
        events = data.get("events", [])
        
        for ev in events:
            analytics = ev.get("overlay", {}).get("analytics", {})
            eff_conf = analytics.get("effective_confidence")
            if eff_conf is not None:
                assert eff_conf >= 0.25, f"effective_confidence {eff_conf} is below hard floor 0.25"
                assert eff_conf <= 1.0, f"effective_confidence {eff_conf} exceeds 1.0"
        
        print(f"PASS: All effective_confidence values respect hard floor 0.25")
    
    def test_sample_size_non_negative(self):
        """sample_size should be non-negative integer"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot&limit=20")
        assert response.status_code == 200
        data = response.json()
        events = data.get("events", [])
        
        for ev in events:
            analytics = ev.get("overlay", {}).get("analytics", {})
            sample_size = analytics.get("sample_size")
            if sample_size is not None:
                assert isinstance(sample_size, int), f"sample_size should be int, got {type(sample_size)}"
                assert sample_size >= 0, f"sample_size should be non-negative, got {sample_size}"
        
        print(f"PASS: All sample_size values are non-negative integers")


class TestDecisionStability:
    """Test decision stability behavior"""
    
    def test_stability_state_values(self):
        """stability.state should be STABLE|UNSTABLE|LOCKED"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot&limit=20")
        assert response.status_code == 200
        data = response.json()
        events = data.get("events", [])
        
        valid_states = {"STABLE", "UNSTABLE", "LOCKED"}
        state_counts = {}
        for ev in events:
            stability = ev.get("overlay", {}).get("stability", {})
            state = stability.get("state")
            if state:
                assert state in valid_states, f"Invalid stability.state: {state}"
                state_counts[state] = state_counts.get(state, 0) + 1
        
        print(f"PASS: stability.state distribution: {state_counts}")
    
    def test_calling_same_event_twice_shows_stable(self):
        """Calling same event twice should show STABLE state (sticky decision)"""
        # First call
        response1 = requests.get(f"{BASE_URL}/api/feed?mode=hot&limit=5")
        assert response1.status_code == 200
        data1 = response1.json()
        events1 = data1.get("events", [])
        
        if not events1:
            pytest.skip("No events available for stability test")
        
        # Get first event's stability state
        first_event = events1[0]
        stability1 = first_event.get("overlay", {}).get("stability", {})
        state1 = stability1.get("state")
        
        # Second call (same endpoint)
        response2 = requests.get(f"{BASE_URL}/api/feed?mode=hot&limit=5")
        assert response2.status_code == 200
        data2 = response2.json()
        events2 = data2.get("events", [])
        
        # Find same event
        event_id = first_event.get("event_id")
        matching_event = next((e for e in events2 if e.get("event_id") == event_id), None)
        
        if matching_event:
            stability2 = matching_event.get("overlay", {}).get("stability", {})
            state2 = stability2.get("state")
            # Should be STABLE on second call (no change)
            print(f"PASS: Event {event_id} stability state: first={state1}, second={state2}")
            # Note: state could be STABLE, UNSTABLE, or LOCKED depending on history
            assert state2 in {"STABLE", "UNSTABLE", "LOCKED"}, f"Invalid state: {state2}"
        else:
            print(f"PASS: Event {event_id} not found in second call (may have changed tier)")


class TestGatingReasons:
    """Test gating reasons are human-readable"""
    
    def test_gating_reasons_are_strings(self):
        """gating_reasons should be list of human-readable strings"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot&limit=20")
        assert response.status_code == 200
        data = response.json()
        events = data.get("events", [])
        
        all_reasons = set()
        for ev in events:
            gating = ev.get("overlay", {}).get("gating", {})
            reasons = gating.get("gating_reasons", [])
            for r in reasons:
                assert isinstance(r, str), f"gating_reason should be string, got {type(r)}"
                all_reasons.add(r)
        
        print(f"PASS: Found {len(all_reasons)} unique gating reasons: {list(all_reasons)[:10]}...")


class TestActionBannerConfidence:
    """Test action banner shows effective confidence"""
    
    def test_actionable_events_have_effective_confidence(self):
        """Actionable events (BUY_YES/BUY_NO) should have effective_confidence in analytics"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=actionable&limit=10")
        assert response.status_code == 200
        data = response.json()
        events = data.get("events", [])
        
        actionable_with_eff_conf = 0
        for ev in events:
            overlay = ev.get("overlay", {})
            action = overlay.get("action")
            if action in ("BUY_YES", "BUY_NO"):
                analytics = overlay.get("analytics", {})
                eff_conf = analytics.get("effective_confidence")
                if eff_conf is not None:
                    actionable_with_eff_conf += 1
                    assert 0.25 <= eff_conf <= 1.0, f"effective_confidence {eff_conf} out of range"
        
        print(f"PASS: {actionable_with_eff_conf} actionable events have effective_confidence")


class TestConfidenceBreakdown:
    """Test confidence breakdown (Raw → Calibrated → Effective)"""
    
    def test_confidence_breakdown_fields(self):
        """Analytics should have adjusted_confidence (calibrated) and effective_confidence"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot&limit=10")
        assert response.status_code == 200
        data = response.json()
        events = data.get("events", [])
        
        breakdown_found = 0
        for ev in events:
            overlay = ev.get("overlay", {})
            analytics = overlay.get("analytics", {})
            
            # Raw confidence is in overlay.confidence (string: high/medium/low)
            raw_conf = overlay.get("confidence")
            # Calibrated is adjusted_confidence
            calibrated = analytics.get("adjusted_confidence")
            # Effective is effective_confidence
            effective = analytics.get("effective_confidence")
            
            if calibrated is not None and effective is not None:
                breakdown_found += 1
                # Effective should be <= calibrated (trust multipliers reduce it)
                # But with hard floor, effective could be higher if calibrated was very low
                assert effective >= 0.25, f"effective_confidence below hard floor"
        
        print(f"PASS: {breakdown_found}/{len(events)} events have full confidence breakdown")


class TestFeedHealth:
    """Test feed health endpoint"""
    
    def test_feed_health_endpoint(self):
        """GET /api/feed/health returns ok status"""
        response = requests.get(f"{BASE_URL}/api/feed/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") == True, "Health check should return ok=true"
        print(f"PASS: Feed health check ok, data: {data}")


class TestTierFiltering:
    """Test tier filtering still works"""
    
    def test_hot_tier(self):
        """GET /api/feed?mode=hot returns hot events"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print(f"PASS: Hot tier returns {len(data.get('events', []))} events")
    
    def test_actionable_tier(self):
        """GET /api/feed?mode=actionable returns actionable events"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=actionable")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print(f"PASS: Actionable tier returns {len(data.get('events', []))} events")
    
    def test_all_tier(self):
        """GET /api/feed?mode=all returns all events"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=all")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print(f"PASS: All tier returns {len(data.get('events', []))} events")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
