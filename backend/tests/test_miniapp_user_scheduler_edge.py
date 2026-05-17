"""
MiniApp User State Machine, Scheduler, and Edge Alerts v2 Tests
================================================================
Tests for:
1. User State Machine (guest → telegram → linked_google → active_sub → expired_sub)
2. Automated Scheduler (Polymarket ingestion + daily digest)
3. Edge Alert improvements (confidence tiers, TTL, loss framing)
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestUserStateMachine:
    """User State Machine endpoint tests"""
    
    def test_user_state_unknown_telegram_id_returns_guest(self):
        """GET /api/miniapp/user/state with unknown telegram_id returns guest state"""
        response = requests.get(f"{BASE_URL}/api/miniapp/user/state", params={"telegram_id": "TEST_unknown_12345"})
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("state") == "guest"
        assert data.get("telegram_id") == "TEST_unknown_12345"
        print(f"✓ Unknown telegram_id returns guest state: {data}")
    
    def test_user_state_empty_telegram_id_returns_guest(self):
        """GET /api/miniapp/user/state with empty telegram_id returns guest state"""
        response = requests.get(f"{BASE_URL}/api/miniapp/user/state", params={"telegram_id": ""})
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("state") == "guest"
        print(f"✓ Empty telegram_id returns guest state: {data}")
    
    def test_link_google_account_creates_linked_state(self):
        """POST /api/miniapp/user/link-google links accounts and returns linked_google state"""
        test_telegram_id = f"TEST_tg_{int(time.time())}"
        test_email = f"test_{int(time.time())}@example.com"
        
        response = requests.post(f"{BASE_URL}/api/miniapp/user/link-google", json={
            "telegram_id": test_telegram_id,
            "email": test_email,
            "name": "Test User"
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("success") == True
        assert data.get("state") == "linked_google"
        assert "Linked" in data.get("message", "")
        print(f"✓ Link Google account returns linked_google state: {data}")
        
        # Verify state via GET
        state_response = requests.get(f"{BASE_URL}/api/miniapp/user/state", params={"telegram_id": test_telegram_id})
        assert state_response.status_code == 200
        state_data = state_response.json()
        assert state_data.get("state") == "linked_google"
        assert state_data.get("google_email") == test_email
        assert state_data.get("linked", {}).get("google") == True
        print(f"✓ GET state confirms linked_google: {state_data}")
        
        return test_telegram_id
    
    def test_unlink_google_account_reverts_to_telegram_only(self):
        """POST /api/miniapp/user/unlink-google unlinks and state reverts to telegram_only"""
        # First link an account
        test_telegram_id = f"TEST_tg_unlink_{int(time.time())}"
        test_email = f"test_unlink_{int(time.time())}@example.com"
        
        link_response = requests.post(f"{BASE_URL}/api/miniapp/user/link-google", json={
            "telegram_id": test_telegram_id,
            "email": test_email,
            "name": "Test Unlink User"
        })
        assert link_response.status_code == 200
        
        # Now unlink
        unlink_response = requests.post(f"{BASE_URL}/api/miniapp/user/unlink-google", json={
            "telegram_id": test_telegram_id
        })
        assert unlink_response.status_code == 200
        unlink_data = unlink_response.json()
        assert unlink_data.get("ok") == True
        assert unlink_data.get("success") == True
        print(f"✓ Unlink Google account successful: {unlink_data}")
        
        # Verify state reverted to telegram_only
        state_response = requests.get(f"{BASE_URL}/api/miniapp/user/state", params={"telegram_id": test_telegram_id})
        assert state_response.status_code == 200
        state_data = state_response.json()
        assert state_data.get("state") == "telegram_only"
        assert state_data.get("google_email") is None
        assert state_data.get("linked", {}).get("google") == False
        print(f"✓ State reverted to telegram_only after unlink: {state_data}")
    
    def test_link_google_missing_params_returns_error(self):
        """POST /api/miniapp/user/link-google with missing params returns error"""
        response = requests.post(f"{BASE_URL}/api/miniapp/user/link-google", json={
            "telegram_id": "",
            "email": ""
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == False
        assert "required" in data.get("message", "").lower()
        print(f"✓ Missing params returns error: {data}")


class TestScheduler:
    """Scheduler endpoint tests"""
    
    def test_scheduler_status_returns_running_info(self):
        """GET /api/miniapp/scheduler/status returns running status with metrics"""
        response = requests.get(f"{BASE_URL}/api/miniapp/scheduler/status")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "running" in data
        assert "lastIngest" in data
        assert "ingestCount" in data
        assert "ingestIntervalMinutes" in data
        assert "digestHourUtc" in data
        print(f"✓ Scheduler status: running={data.get('running')}, ingestCount={data.get('ingestCount')}, lastIngest={data.get('lastIngest')}")
    
    def test_scheduler_stop_stops_scheduler(self):
        """POST /api/miniapp/scheduler/stop stops the scheduler"""
        response = requests.post(f"{BASE_URL}/api/miniapp/scheduler/stop")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("status") == "stopped"
        print(f"✓ Scheduler stopped: {data}")
        
        # Verify status shows not running
        status_response = requests.get(f"{BASE_URL}/api/miniapp/scheduler/status")
        status_data = status_response.json()
        assert status_data.get("running") == False
        print(f"✓ Scheduler status confirms stopped: running={status_data.get('running')}")
    
    def test_scheduler_start_starts_scheduler(self):
        """POST /api/miniapp/scheduler/start starts the scheduler"""
        # First ensure it's stopped
        requests.post(f"{BASE_URL}/api/miniapp/scheduler/stop")
        
        # Now start
        response = requests.post(f"{BASE_URL}/api/miniapp/scheduler/start")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("status") in ("started", "already_running")
        print(f"✓ Scheduler started: {data}")
        
        # Verify status shows running
        status_response = requests.get(f"{BASE_URL}/api/miniapp/scheduler/status")
        status_data = status_response.json()
        assert status_data.get("running") == True
        print(f"✓ Scheduler status confirms running: running={status_data.get('running')}")
    
    def test_scheduler_start_when_already_running(self):
        """POST /api/miniapp/scheduler/start when already running returns already_running"""
        # Ensure running
        requests.post(f"{BASE_URL}/api/miniapp/scheduler/start")
        
        # Try to start again
        response = requests.post(f"{BASE_URL}/api/miniapp/scheduler/start")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("status") == "already_running"
        print(f"✓ Scheduler already running: {data}")


class TestEdgeAlerts:
    """Edge Alert improvements tests - confidence tiers, TTL, loss framing"""
    
    def test_edge_returns_confidence_tier_and_ttl(self):
        """GET /api/miniapp/edge returns edges with confidenceTier and ttlHours fields"""
        response = requests.get(f"{BASE_URL}/api/miniapp/edge")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        
        markets = data.get("markets", [])
        if len(markets) > 0:
            # Check first market has new fields
            market = markets[0]
            if market.get("status") != "watching":
                assert "confidenceTier" in market, f"Missing confidenceTier in market: {market}"
                assert "ttlHours" in market, f"Missing ttlHours in market: {market}"
                assert market["confidenceTier"] in ("EXTREME", "HIGH_CONVICTION", "STANDARD")
                assert isinstance(market["ttlHours"], int)
                assert market["ttlHours"] >= 4 and market["ttlHours"] <= 24
                print(f"✓ Edge market has confidenceTier={market['confidenceTier']}, ttlHours={market['ttlHours']}")
        
        # Check best edge if present
        best = data.get("best")
        if best:
            assert "confidenceTier" in best, f"Missing confidenceTier in best edge: {best}"
            assert "ttlHours" in best, f"Missing ttlHours in best edge: {best}"
            print(f"✓ Best edge: asset={best.get('asset')}, tier={best.get('confidenceTier')}, ttl={best.get('ttlHours')}h")
        
        print(f"✓ Edge response has {len(markets)} markets, status={data.get('status')}")
    
    def test_edge_confidence_tier_thresholds(self):
        """Verify confidence tier thresholds: EXTREME (>=0.80), HIGH_CONVICTION (>=0.65), STANDARD (<0.65)"""
        response = requests.get(f"{BASE_URL}/api/miniapp/edge")
        assert response.status_code == 200
        data = response.json()
        
        markets = data.get("markets", [])
        for market in markets:
            if market.get("status") == "watching":
                continue
            
            confidence = market.get("confidence", 0)
            tier = market.get("confidenceTier", "")
            
            if confidence >= 0.80:
                assert tier == "EXTREME", f"Confidence {confidence} should be EXTREME, got {tier}"
            elif confidence >= 0.65:
                assert tier == "HIGH_CONVICTION", f"Confidence {confidence} should be HIGH_CONVICTION, got {tier}"
            else:
                assert tier == "STANDARD", f"Confidence {confidence} should be STANDARD, got {tier}"
            
            print(f"  ✓ {market.get('asset')}: confidence={confidence:.2f} → tier={tier}")
        
        print(f"✓ All {len(markets)} markets have correct confidence tier mapping")
    
    def test_edge_has_direction_and_edge_value(self):
        """GET /api/miniapp/edge returns edges with direction and edge value"""
        response = requests.get(f"{BASE_URL}/api/miniapp/edge")
        assert response.status_code == 200
        data = response.json()
        
        markets = data.get("markets", [])
        for market in markets:
            assert "direction" in market
            assert "edge" in market
            assert "confidence" in market
            assert "marketProbability" in market
            assert "modelProbability" in market
            
            if market.get("status") != "watching":
                assert market["direction"] in ("BUY", "SELL", "WAIT")
                assert isinstance(market["edge"], (int, float))
        
        print(f"✓ All markets have required fields (direction, edge, confidence, probabilities)")


class TestRegressionEndpoints:
    """Regression tests for existing endpoints"""
    
    def test_miniapp_profile_endpoint(self):
        """GET /api/miniapp/profile still works"""
        response = requests.get(f"{BASE_URL}/api/miniapp/profile")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print(f"✓ Profile endpoint works: {list(data.keys())[:5]}...")
    
    def test_miniapp_home_endpoint(self):
        """GET /api/miniapp/home?asset=BTC still works"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home", params={"asset": "BTC"})
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "price" in data or "decision" in data
        print(f"✓ Home endpoint works: price={data.get('price')}, decision={data.get('decision')}")
    
    def test_miniapp_billing_plans_endpoint(self):
        """GET /api/miniapp/billing/plans still works"""
        response = requests.get(f"{BASE_URL}/api/miniapp/billing/plans")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "billingMode" in data
        print(f"✓ Billing plans endpoint works: billingMode={data.get('billingMode')}")
    
    def test_miniapp_feed_endpoint(self):
        """GET /api/miniapp/feed still works"""
        response = requests.get(f"{BASE_URL}/api/miniapp/feed")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print(f"✓ Feed endpoint works: {list(data.keys())[:5]}...")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
