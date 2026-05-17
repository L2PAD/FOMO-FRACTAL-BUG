"""
Test: Momentum Endpoint + System Health Verification
=====================================================
Focus: 
- NEW /api/momentum/entity/{type}/{id}/history endpoint
- Admin backtest endpoint
- ML overlay status and predict
- Playback events (regression)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"


class TestMomentumEndpoint:
    """Tests for the new /api/momentum/entity/{type}/{id}/history endpoint"""
    
    def test_momentum_wallet_history_30d(self):
        """Test momentum for wallet with 30 days (default)"""
        # Using zero address as test wallet
        response = requests.get(
            f"{BASE_URL}/api/momentum/entity/wallet/0x0000000000000000000000000000000000000000/history",
            params={"days": 30}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Validate response structure
        assert "history" in data, "Response must contain 'history' array"
        assert "entity" in data, "Response must contain 'entity' string"
        assert "days" in data, "Response must contain 'days' integer"
        
        # Entity should match the node prefix
        assert data["entity"] == "wallet:0x0000000000000000000000000000000000000000", \
            f"Entity should be 'wallet:0x000...' but got '{data['entity']}'"
        assert data["days"] == 30, f"Days should be 30 but got {data['days']}"
        
        # History should be a list (can be empty if no data)
        assert isinstance(data["history"], list), "History must be a list"
        
        print(f"PASS: Momentum wallet history - got {len(data['history'])} days of history")
    
    def test_momentum_cex_history_7d(self):
        """Test momentum for CEX (Binance) with 7 days"""
        # Binance hot wallet address
        response = requests.get(
            f"{BASE_URL}/api/momentum/entity/cex/0x28c6c06298d514db089934071355e5743bf21d60/history",
            params={"days": 7}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "history" in data
        assert "entity" in data
        assert "days" in data
        
        # Entity should use lowercase
        assert data["entity"] == "cex:0x28c6c06298d514db089934071355e5743bf21d60"
        assert data["days"] == 7
        assert isinstance(data["history"], list)
        
        # If there's history, validate structure
        if data["history"]:
            first = data["history"][0]
            assert "date" in first, "History entry must have 'date'"
            assert "momentum_score" in first, "History entry must have 'momentum_score'"
            assert "volume_usd" in first, "History entry must have 'volume_usd'"
            assert "tx_count" in first, "History entry must have 'tx_count'"
            assert "inflow_usd" in first, "History entry must have 'inflow_usd'"
            assert "outflow_usd" in first, "History entry must have 'outflow_usd'"
            assert "net_flow_usd" in first, "History entry must have 'net_flow_usd'"
        
        print(f"PASS: Momentum CEX history - got {len(data['history'])} days of history")
    
    def test_momentum_unknown_entity_graceful_empty(self):
        """Test momentum for unknown entity returns empty history gracefully (no 500)"""
        response = requests.get(
            f"{BASE_URL}/api/momentum/entity/wallet/0xDEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF/history",
            params={"days": 30}
        )
        assert response.status_code == 200, f"Expected 200 (graceful empty), got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "history" in data
        assert "entity" in data
        assert "days" in data
        
        # Unknown entity should return empty history
        assert isinstance(data["history"], list)
        # History will likely be empty for non-existent entity
        print(f"PASS: Unknown entity returns gracefully - history length: {len(data['history'])}")
    
    def test_momentum_default_days(self):
        """Test momentum endpoint uses default days=30"""
        response = requests.get(
            f"{BASE_URL}/api/momentum/entity/wallet/0x0000000000000000000000000000000000000000/history"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["days"] == 30, f"Default days should be 30, got {data['days']}"
        print("PASS: Momentum default days is 30")


class TestAdminBacktest:
    """Tests for admin backtest endpoint (requires auth)"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(
            f"{BASE_URL}/api/admin/auth/login",
            json={"username": "admin", "password": "admin12345"}
        )
        if response.status_code != 200:
            pytest.skip("Admin auth not available - skipping authenticated tests")
        return response.json().get("token")
    
    def test_backtest_market_without_auth(self):
        """Test backtest market endpoint without auth"""
        response = requests.get(
            f"{BASE_URL}/api/admin/backtest/market",
            params={"network": "ethereum", "windowDays": 30}
        )
        # Should either return 401/403 (auth required) or 200 if no auth required
        assert response.status_code in [200, 401, 403], \
            f"Expected 200/401/403, got {response.status_code}: {response.text}"
        print(f"Backtest without auth: status={response.status_code}")
    
    def test_backtest_market_with_admin_auth(self, admin_token):
        """Test backtest market endpoint with admin auth"""
        headers = {"Authorization": f"Bearer {admin_token}"} if admin_token else {}
        response = requests.get(
            f"{BASE_URL}/api/admin/backtest/market",
            params={"network": "ethereum", "windowDays": 30},
            headers=headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "ok" in data, "Response must contain 'ok' field"
        assert data["ok"] is True, f"Expected ok:true, got {data}"
        print(f"PASS: Backtest market with auth - ok: {data.get('ok')}")


class TestMLOverlay:
    """Tests for ML overlay endpoints"""
    
    def test_ml_overlay_status(self):
        """Test ML overlay status endpoint"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "ok" in data, "Response must contain 'ok' field"
        assert data["ok"] is True, f"Expected ok:true, got {data}"
        
        # Should have trained_models info
        if "trained_models" in data:
            print(f"PASS: ML overlay status - trained_models: {data['trained_models']}")
        else:
            print(f"PASS: ML overlay status - ok: {data.get('ok')}, keys: {list(data.keys())}")
    
    def test_ml_overlay_predict(self):
        """Test ML overlay predict endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/ml-overlay/predict",
            params={"symbol": "BTCUSDT", "horizon": "7D"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Prediction response should have some structure
        print(f"PASS: ML overlay predict - response keys: {list(data.keys())}")


class TestPlaybackEvents:
    """Regression test: Verify playback events still work"""
    
    def test_playback_events_default(self):
        """Test playback events returns valid structure"""
        response = requests.get(f"{BASE_URL}/api/graph-core/playback/events")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "events" in data, "Response must contain 'events'"
        assert "total_events" in data, "Response must contain 'total_events'"
        assert "time_range" in data, "Response must contain 'time_range'"
        assert "resolution" in data, "Response must contain 'resolution'"
        assert "bucket_seconds" in data, "Response must contain 'bucket_seconds'"
        
        assert isinstance(data["events"], list)
        assert isinstance(data["total_events"], int)
        assert "start" in data["time_range"]
        assert "end" in data["time_range"]
        
        print(f"PASS: Playback events - {data['total_events']} events, resolution: {data['resolution']}")
    
    def test_playback_events_1h_resolution(self):
        """Test playback events with 1h resolution"""
        response = requests.get(
            f"{BASE_URL}/api/graph-core/playback/events",
            params={"resolution": "1h"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["bucket_seconds"] == 3600, f"Expected 3600 for 1h, got {data['bucket_seconds']}"
        print(f"PASS: Playback 1h resolution - bucket_seconds: {data['bucket_seconds']}")


class TestGraphCoreHealth:
    """Test graph-core health endpoint"""
    
    def test_graph_health(self):
        """Test graph-core health returns ok"""
        response = requests.get(f"{BASE_URL}/api/graph-core/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "status" in data, "Response must contain 'status'"
        assert data["status"] == "ok", f"Expected status:ok, got {data['status']}"
        
        print(f"PASS: Graph-core health - status: {data['status']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
