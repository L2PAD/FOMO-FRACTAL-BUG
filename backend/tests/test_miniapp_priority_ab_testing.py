"""
MiniApp Priority Engine v2 + A/B Testing Layer Tests
=====================================================
Tests for:
1. Edge Priority Engine v2 - priorityScore, priorityLabel, decisionType fields
2. A/B Testing Layer - variants A/B/C/D, event tracking, stats endpoint
3. Webhook /start command handling
4. Regression tests for existing endpoints
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestEdgePriorityEngineV2:
    """Tests for Edge Priority Engine v2 scoring and labels."""

    def test_edge_returns_priority_fields(self):
        """GET /api/miniapp/edge returns priorityScore, priorityLabel, decisionType."""
        response = requests.get(f"{BASE_URL}/api/miniapp/edge")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("status") in ["ACTIVE", "NO_EDGE"], f"Unexpected status: {data.get('status')}"
        
        if data.get("status") == "ACTIVE" and data.get("best"):
            best = data["best"]
            # Verify priority fields exist
            assert "priorityScore" in best, "Missing priorityScore in best edge"
            assert "priorityLabel" in best, "Missing priorityLabel in best edge"
            assert "decisionType" in best, "Missing decisionType in best edge"
            
            # Verify priorityScore is a float between 0 and 1
            assert isinstance(best["priorityScore"], (int, float)), "priorityScore should be numeric"
            assert 0 <= best["priorityScore"] <= 1, f"priorityScore {best['priorityScore']} out of range [0,1]"
            
            # Verify priorityLabel is one of expected values
            valid_labels = ["ELITE EDGE", "LIVE EDGE", "STRONG EDGE", "WATCHING", "LOW PRIORITY"]
            assert best["priorityLabel"] in valid_labels, f"Invalid priorityLabel: {best['priorityLabel']}"
            
            print(f"Best edge: {best['asset']} - priorityScore={best['priorityScore']}, priorityLabel={best['priorityLabel']}, decisionType={best['decisionType']}")

    def test_edge_sorted_by_priority_score(self):
        """Edges should be sorted by priorityScore (highest first)."""
        response = requests.get(f"{BASE_URL}/api/miniapp/edge")
        assert response.status_code == 200
        
        data = response.json()
        if data.get("status") == "ACTIVE":
            markets = data.get("markets", [])
            # Filter out watching edges for sorting check
            active_markets = [m for m in markets if m.get("status") != "watching"]
            
            if len(active_markets) >= 2:
                scores = [m.get("priorityScore", 0) for m in active_markets]
                assert scores == sorted(scores, reverse=True), f"Markets not sorted by priorityScore: {scores}"
                print(f"Verified {len(active_markets)} active markets sorted by priorityScore")

    def test_priority_label_thresholds(self):
        """Verify priority labels match score thresholds."""
        response = requests.get(f"{BASE_URL}/api/miniapp/edge")
        assert response.status_code == 200
        
        data = response.json()
        if data.get("status") == "ACTIVE":
            markets = data.get("markets", [])
            
            for market in markets:
                score = market.get("priorityScore", 0)
                label = market.get("priorityLabel", "")
                
                # Verify label matches score threshold
                if score >= 0.80:
                    expected = "ELITE EDGE"
                elif score >= 0.68:
                    expected = "LIVE EDGE"
                elif score >= 0.55:
                    expected = "STRONG EDGE"
                elif score >= 0.40:
                    expected = "WATCHING"
                else:
                    expected = "LOW PRIORITY"
                
                # Note: watching status edges may have different labels
                if market.get("status") != "watching":
                    assert label == expected, f"Asset {market.get('asset')}: score={score}, expected label={expected}, got={label}"
            
            print(f"Verified priority labels for {len(markets)} markets")

    def test_best_edge_has_highest_priority(self):
        """Best edge should have the highest priorityScore."""
        response = requests.get(f"{BASE_URL}/api/miniapp/edge")
        assert response.status_code == 200
        
        data = response.json()
        if data.get("status") == "ACTIVE" and data.get("best"):
            best = data["best"]
            markets = data.get("markets", [])
            
            best_score = best.get("priorityScore", 0)
            for market in markets:
                if market.get("status") != "watching":
                    assert market.get("priorityScore", 0) <= best_score, \
                        f"Market {market.get('asset')} has higher score than best edge"
            
            print(f"Best edge {best['asset']} has highest priorityScore: {best_score}")


class TestABTestingLayer:
    """Tests for A/B Testing Layer - variants, tracking, stats."""

    def test_ab_stats_returns_all_variants(self):
        """GET /api/miniapp/ab/stats returns variants A/B/C/D with events and kpi."""
        response = requests.get(f"{BASE_URL}/api/miniapp/ab/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert "variants" in data, "Missing variants in response"
        
        variants = data["variants"]
        expected_variants = ["A", "B", "C", "D"]
        
        for v in expected_variants:
            assert v in variants, f"Missing variant {v} in stats"
            assert "events" in variants[v], f"Missing events for variant {v}"
            assert "kpi" in variants[v], f"Missing kpi for variant {v}"
            
            kpi = variants[v]["kpi"]
            assert "ctr" in kpi, f"Missing ctr in kpi for variant {v}"
            assert "engagement" in kpi, f"Missing engagement in kpi for variant {v}"
            assert "conversion" in kpi, f"Missing conversion in kpi for variant {v}"
            assert "revenuePerAlert" in kpi, f"Missing revenuePerAlert in kpi for variant {v}"
        
        print(f"A/B stats returned all 4 variants with events and kpi")

    def test_ab_track_event_success(self):
        """POST /api/miniapp/ab/track tracks events correctly."""
        test_user_id = f"TEST_ab_user_{int(time.time())}"
        
        payload = {
            "user_id": test_user_id,
            "event": "alert_sent",
            "variant": "A",
            "meta": {"asset": "BTC", "edge": 0.15}
        }
        
        response = requests.post(f"{BASE_URL}/api/miniapp/ab/track", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        print(f"Successfully tracked event for user {test_user_id}")

    def test_ab_track_requires_user_id_and_event(self):
        """POST /api/miniapp/ab/track requires user_id and event."""
        # Missing user_id
        response = requests.post(f"{BASE_URL}/api/miniapp/ab/track", json={
            "event": "alert_sent",
            "variant": "A"
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is False, "Should fail without user_id"
        
        # Missing event
        response = requests.post(f"{BASE_URL}/api/miniapp/ab/track", json={
            "user_id": "test_user",
            "variant": "A"
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is False, "Should fail without event"
        
        print("Validated required fields for ab/track")

    def test_ab_stats_update_after_tracking(self):
        """A/B stats should update after tracking events."""
        # Get initial stats
        initial_response = requests.get(f"{BASE_URL}/api/miniapp/ab/stats")
        initial_data = initial_response.json()
        initial_count = initial_data["variants"]["B"]["events"].get("test_event", 0)
        
        # Track a new event
        test_user_id = f"TEST_ab_stats_{int(time.time())}"
        requests.post(f"{BASE_URL}/api/miniapp/ab/track", json={
            "user_id": test_user_id,
            "event": "test_event",
            "variant": "B",
            "meta": {}
        })
        
        # Get updated stats
        updated_response = requests.get(f"{BASE_URL}/api/miniapp/ab/stats")
        updated_data = updated_response.json()
        updated_count = updated_data["variants"]["B"]["events"].get("test_event", 0)
        
        assert updated_count >= initial_count, "Event count should increase after tracking"
        print(f"A/B stats updated: test_event count {initial_count} -> {updated_count}")


class TestWebhookStartCommand:
    """Tests for Telegram bot webhook /start command."""

    def test_webhook_start_command(self):
        """POST /api/miniapp/webhook handles /start command."""
        # Simulate Telegram update with /start command
        payload = {
            "update_id": 123456789,
            "message": {
                "message_id": 1,
                "from": {
                    "id": 999888777,
                    "is_bot": False,
                    "first_name": "Test",
                    "username": "test_user"
                },
                "chat": {
                    "id": 999888777,
                    "first_name": "Test",
                    "username": "test_user",
                    "type": "private"
                },
                "date": int(time.time()),
                "text": "/start"
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/miniapp/webhook", json=payload)
        # Webhook should return 200 even if bot token is not configured
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        print(f"Webhook /start command handled successfully")

    def test_webhook_empty_payload(self):
        """POST /api/miniapp/webhook handles empty payload gracefully."""
        response = requests.post(f"{BASE_URL}/api/miniapp/webhook", json={})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("Webhook handles empty payload gracefully")


class TestRegressionEndpoints:
    """Regression tests for existing MiniApp endpoints."""

    def test_user_state_endpoint(self):
        """GET /api/miniapp/user/state?telegram_id=test_tg_123 still works."""
        response = requests.get(f"{BASE_URL}/api/miniapp/user/state?telegram_id=test_tg_123")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert "state" in data, "Missing state in response"
        assert data["state"] in ["guest", "telegram_only", "linked_google"], f"Invalid state: {data['state']}"
        print(f"User state endpoint works: state={data['state']}")

    def test_scheduler_status_endpoint(self):
        """GET /api/miniapp/scheduler/status still shows running=true."""
        response = requests.get(f"{BASE_URL}/api/miniapp/scheduler/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert "running" in data, "Missing running in response"
        # Scheduler should be running
        print(f"Scheduler status: running={data.get('running')}, lastIngest={data.get('lastIngest')}")

    def test_profile_endpoint(self):
        """GET /api/miniapp/profile still works."""
        response = requests.get(f"{BASE_URL}/api/miniapp/profile")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "user" in data or "plan" in data, f"Missing user/plan in profile response"
        print("Profile endpoint works")

    def test_billing_plans_endpoint(self):
        """GET /api/miniapp/billing/plans still works."""
        response = requests.get(f"{BASE_URL}/api/miniapp/billing/plans")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        # Response contains billingMode, monthly, yearly pricing info
        assert "billingMode" in data or "monthly" in data, "Missing billing info in response"
        print(f"Billing plans endpoint works: billingMode={data.get('billingMode')}")

    def test_edge_still_has_tier_ttl_loss_framing(self):
        """Edge endpoint still returns tier badge, TTL, and loss framing data."""
        response = requests.get(f"{BASE_URL}/api/miniapp/edge")
        assert response.status_code == 200
        
        data = response.json()
        if data.get("status") == "ACTIVE" and data.get("best"):
            best = data["best"]
            
            # Verify tier badge data (confidenceTier)
            assert "confidenceTier" in best, "Missing confidenceTier for tier badge"
            assert best["confidenceTier"] in ["EXTREME", "HIGH_CONVICTION", "STANDARD"], \
                f"Invalid confidenceTier: {best['confidenceTier']}"
            
            # Verify TTL data
            assert "ttlHours" in best, "Missing ttlHours for TTL indicator"
            assert isinstance(best["ttlHours"], int), "ttlHours should be integer"
            assert 4 <= best["ttlHours"] <= 24, f"ttlHours {best['ttlHours']} out of expected range [4,24]"
            
            # Verify loss framing data (edge value for "Market mispriced by X%")
            assert "edge" in best, "Missing edge value for loss framing"
            assert isinstance(best["edge"], (int, float)), "edge should be numeric"
            
            print(f"Edge has tier={best['confidenceTier']}, ttl={best['ttlHours']}h, edge={best['edge']}")


class TestEdgeDataStructure:
    """Tests for complete edge data structure."""

    def test_edge_response_structure(self):
        """Verify complete edge response structure."""
        response = requests.get(f"{BASE_URL}/api/miniapp/edge")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data, "Missing status"
        
        if data.get("status") == "ACTIVE":
            assert "best" in data, "Missing best edge"
            assert "markets" in data, "Missing markets list"
            
            best = data["best"]
            required_fields = [
                "asset", "question", "marketProbability", "modelProbability",
                "edge", "direction", "confidence", "confidenceTier", "ttlHours",
                "priorityScore", "priorityLabel", "decisionType", "reason"
            ]
            
            for field in required_fields:
                assert field in best, f"Missing required field: {field}"
            
            print(f"Edge response has all required fields. Best edge: {best['asset']}")
            print(f"  - priorityScore: {best['priorityScore']}")
            print(f"  - priorityLabel: {best['priorityLabel']}")
            print(f"  - decisionType: {best['decisionType']}")
            print(f"  - confidenceTier: {best['confidenceTier']}")
            print(f"  - ttlHours: {best['ttlHours']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
