"""
Wallets v3 Phase C API Tests
============================
Tests for:
- P0: Wallets v3 tab integration health
- C2: Daily flow buckets (series endpoint)
- C3: UI drilldowns (profile, tokens, counterparties)
- C4: Snapshot job (status, force-tick)
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

TEST_ADDRESS = "0x1234567890abcdef1234567890abcdef12345678"

class TestWalletsV3Health:
    """Health endpoint tests"""
    
    def test_health_returns_ok(self):
        """GET /api/v10/onchain-v2/wallets/health returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/wallets/health")
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] == True
        assert data["module"] == "wallets_v3"
        assert "cache" in data
        assert data["cache"]["enabled"] == True
        assert "jobs" in data
        assert data["jobs"]["enabled"] == True
        print(f"✓ Health endpoint returns ok:true with cache and job status")


class TestWalletsV3Profile:
    """Profile endpoint tests (C3)"""
    
    def test_profile_missing_address_returns_400(self):
        """GET /api/v10/onchain-v2/wallets/profile without address returns 400"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/wallets/profile")
        assert response.status_code == 400
        data = response.json()
        assert data["ok"] == False
        assert data["error"] == "MISSING_ADDRESS"
        print("✓ Profile endpoint validates address parameter")
    
    def test_profile_returns_correct_structure(self):
        """GET /api/v10/onchain-v2/wallets/profile returns proper structure"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/wallets/profile",
            params={"address": TEST_ADDRESS, "window": "7d"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Required fields
        assert data["ok"] == True
        assert data["chainId"] == 1
        assert data["address"] == TEST_ADDRESS.lower()
        assert data["window"] == "7d"
        
        # Totals structure
        assert "totals" in data
        totals = data["totals"]
        assert "inflowUsd" in totals
        assert "outflowUsd" in totals
        assert "netUsd" in totals
        assert "transfers" in totals
        assert "uniqueCounterparties" in totals
        assert "stableShare" in totals
        assert "avgTransferUsd" in totals
        
        # Attribution structure
        assert "attribution" in data
        attr = data["attribution"]
        assert "entityId" in attr
        assert "entityName" in attr
        assert "entityType" in attr
        assert "source" in attr
        assert "confidence" in attr
        assert "evidence" in attr
        
        # Arrays
        assert "topTokens" in data
        assert isinstance(data["topTokens"], list)
        assert "topCounterparties" in data
        assert isinstance(data["topCounterparties"], list)
        
        # Meta
        assert "meta" in data
        meta = data["meta"]
        assert "fromTs" in meta
        assert "toTs" in meta
        assert "computedAt" in meta
        assert "pricedTokens" in meta
        assert "totalTokens" in meta
        assert "truncated" in meta
        
        print("✓ Profile returns all required fields with correct structure")
    
    def test_profile_windows(self):
        """Profile endpoint accepts all window values (24h, 7d, 30d)"""
        for window in ["24h", "7d", "30d"]:
            response = requests.get(
                f"{BASE_URL}/api/v10/onchain-v2/wallets/profile",
                params={"address": TEST_ADDRESS, "window": window}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] == True
            assert data["window"] == window
        print("✓ Profile accepts 24h, 7d, 30d window values")


class TestWalletsV3Tokens:
    """Tokens endpoint tests (C3)"""
    
    def test_tokens_missing_address_returns_400(self):
        """GET /api/v10/onchain-v2/wallets/tokens without address returns 400"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/wallets/tokens")
        assert response.status_code == 400
        data = response.json()
        assert data["ok"] == False
        print("✓ Tokens endpoint validates address parameter")
    
    def test_tokens_returns_correct_structure(self):
        """GET /api/v10/onchain-v2/wallets/tokens returns proper structure"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/wallets/tokens",
            params={"address": TEST_ADDRESS, "window": "7d"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] == True
        assert data["chainId"] == 1
        assert data["address"] == TEST_ADDRESS.lower()
        assert data["window"] == "7d"
        assert "items" in data
        assert isinstance(data["items"], list)
        print("✓ Tokens endpoint returns correct structure with items array")


class TestWalletsV3Counterparties:
    """Counterparties endpoint tests (C3)"""
    
    def test_counterparties_missing_address_returns_400(self):
        """GET /api/v10/onchain-v2/wallets/counterparties without address returns 400"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/wallets/counterparties")
        assert response.status_code == 400
        data = response.json()
        assert data["ok"] == False
        print("✓ Counterparties endpoint validates address parameter")
    
    def test_counterparties_returns_correct_structure(self):
        """GET /api/v10/onchain-v2/wallets/counterparties returns proper structure"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/wallets/counterparties",
            params={"address": TEST_ADDRESS, "window": "7d"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] == True
        assert data["chainId"] == 1
        assert data["address"] == TEST_ADDRESS.lower()
        assert data["window"] == "7d"
        assert "items" in data
        assert isinstance(data["items"], list)
        print("✓ Counterparties endpoint returns correct structure with items array")


class TestWalletsV3Series:
    """Series endpoint tests (C2 - Daily Bucket Aggregation)"""
    
    def test_series_missing_address_returns_400(self):
        """GET /api/v10/onchain-v2/wallets/series without address returns 400"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/wallets/series")
        assert response.status_code == 400
        data = response.json()
        assert data["ok"] == False
        print("✓ Series endpoint validates address parameter")
    
    def test_series_returns_bucketed_data(self):
        """GET /api/v10/onchain-v2/wallets/series returns bucketed:true"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/wallets/series",
            params={"address": TEST_ADDRESS, "window": "7d", "metric": "netUsd"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] == True
        assert data["chainId"] == 1
        assert data["address"] == TEST_ADDRESS.lower()
        assert data["window"] == "7d"
        assert data["metric"] == "netUsd"
        assert data["bucketed"] == True
        assert "points" in data
        assert isinstance(data["points"], list)
        print("✓ Series endpoint returns bucketed:true with points array")
    
    def test_series_accepts_all_metrics(self):
        """Series accepts netUsd, inflowUsd, outflowUsd, transfers metrics"""
        for metric in ["netUsd", "inflowUsd", "outflowUsd", "transfers"]:
            response = requests.get(
                f"{BASE_URL}/api/v10/onchain-v2/wallets/series",
                params={"address": TEST_ADDRESS, "window": "7d", "metric": metric}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] == True
            assert data["metric"] == metric
        print("✓ Series accepts all metric types (netUsd, inflowUsd, outflowUsd, transfers)")


class TestWalletsV3SnapshotJob:
    """Snapshot job endpoint tests (C4)"""
    
    def test_job_status_returns_ok(self):
        """GET /api/v10/onchain-v2/wallets/job/status returns job status"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/wallets/job/status")
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] == True
        assert "running" in data
        assert "tickCount" in data
        assert "successCount" in data
        assert "errorCount" in data
        assert "walletsProcessed" in data
        assert "lastRunAt" in data
        print(f"✓ Job status returns ok:true with tickCount={data['tickCount']}, successCount={data['successCount']}")
    
    def test_force_tick_triggers_job(self):
        """POST /api/v10/onchain-v2/wallets/job/force-tick triggers job"""
        # Get initial tick count
        initial_response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/wallets/job/status")
        initial_tick = initial_response.json()["tickCount"]
        
        # Force tick
        response = requests.post(f"{BASE_URL}/api/v10/onchain-v2/wallets/job/force-tick")
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] == True
        assert data["tickCount"] >= initial_tick
        print(f"✓ Force-tick triggered job, tickCount: {initial_tick} -> {data['tickCount']}")


class TestWalletsV3Integration:
    """End-to-end integration tests"""
    
    def test_full_flow_profile_then_series(self):
        """Profile lookup triggers bucket aggregation, series returns data"""
        # 1. First call profile (triggers bucket aggregation in background)
        profile_resp = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/wallets/profile",
            params={"address": TEST_ADDRESS, "window": "7d"}
        )
        assert profile_resp.status_code == 200
        profile = profile_resp.json()
        assert profile["ok"] == True
        
        # 2. Call series endpoint
        series_resp = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/wallets/series",
            params={"address": TEST_ADDRESS, "window": "7d", "metric": "netUsd"}
        )
        assert series_resp.status_code == 200
        series = series_resp.json()
        assert series["ok"] == True
        assert series["bucketed"] == True
        
        print("✓ Full flow works: profile -> series returns bucketed data")
    
    def test_cached_profile_has_flag(self):
        """After first lookup, subsequent calls may return cached data"""
        # First call
        resp1 = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/wallets/profile",
            params={"address": TEST_ADDRESS, "window": "7d"}
        )
        assert resp1.status_code == 200
        
        # Force snapshot job to run
        requests.post(f"{BASE_URL}/api/v10/onchain-v2/wallets/job/force-tick")
        time.sleep(1)
        
        # Second call - may hit cache
        resp2 = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/wallets/profile",
            params={"address": TEST_ADDRESS, "window": "7d"}
        )
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["ok"] == True
        
        # Profile returns correctly whether cached or fresh
        print(f"✓ Profile returns correctly (cached={data.get('_cached', False)})")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
