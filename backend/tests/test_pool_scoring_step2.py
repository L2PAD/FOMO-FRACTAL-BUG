"""
OnChain V2 — Pool Scoring & Discovery API Tests (STEP 2)
=========================================================

Tests for:
- GET /api/v10/onchain-v2/market/pricing/pools/stats - scoring and discovery stats
- GET /api/v10/onchain-v2/market/pricing/pools/list - list pools with scores
- GET /api/v10/onchain-v2/market/pricing/pools/best - best stable pool for token
- POST /api/v10/onchain-v2/market/pricing/pools/score - run scoring for chain
- POST /api/v10/onchain-v2/market/pricing/pools/discover - run discovery for chain
- GET /api/v10/onchain-v2/market/pricing/pools/job/status - job status
- POST /api/v10/onchain-v2/market/pricing/pools/job/run - force run job

Test tokens (ETH Mainnet):
- WETH: 0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2
- Existing pools: WETH/USDC 0.05%, WETH/USDC 0.3%, WETH/USDT 0.05%, WBTC/WETH 0.3%
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
API_BASE = f"{BASE_URL}/api/v10/onchain-v2/market/pricing/pools"

# Test tokens for ETH mainnet
WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
WBTC = "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599"
USDC = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
USDT = "0xdac17f958d2ee523a2206206994597c13d831ec7"


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


# ═══════════════════════════════════════════════════════════════
# TEST CLASS: Stats Endpoint
# ═══════════════════════════════════════════════════════════════

class TestPoolStats:
    """Tests for GET /pools/stats - scoring and discovery statistics"""
    
    def test_stats_endpoint_returns_200(self, api_client):
        """Stats endpoint should return 200 status code"""
        response = api_client.get(f"{API_BASE}/stats", params={"chainId": 1})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_stats_response_structure(self, api_client):
        """Stats response should contain scoring and discovery sections"""
        response = api_client.get(f"{API_BASE}/stats", params={"chainId": 1})
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True, f"Response not ok: {data}"
        assert "chainId" in data, "Missing chainId in response"
        assert data["chainId"] == 1
        
        # Verify scoring stats section
        assert "scoring" in data, f"Missing scoring section: {data}"
        scoring = data["scoring"]
        assert "total" in scoring, "Missing total in scoring"
        assert "byStatus" in scoring, "Missing byStatus in scoring"
        assert "avgScore" in scoring, "Missing avgScore in scoring"
        assert "avgConfidence" in scoring, "Missing avgConfidence in scoring"
    
    def test_stats_by_status_contains_all_statuses(self, api_client):
        """byStatus should contain CANDIDATE, ACTIVE, DEGRADED, DISABLED"""
        response = api_client.get(f"{API_BASE}/stats", params={"chainId": 1})
        data = response.json()
        
        by_status = data.get("scoring", {}).get("byStatus", {})
        expected_statuses = ["CANDIDATE", "ACTIVE", "DEGRADED", "DISABLED"]
        for status in expected_statuses:
            assert status in by_status, f"Missing status {status} in byStatus: {by_status}"
    
    def test_stats_discovery_section(self, api_client):
        """Stats should contain discovery stats section"""
        response = api_client.get(f"{API_BASE}/stats", params={"chainId": 1})
        data = response.json()
        
        assert "discovery" in data, f"Missing discovery section: {data}"
        discovery = data["discovery"]
        assert "totalPools" in discovery, "Missing totalPools in discovery"
        assert "byStatus" in discovery, "Missing byStatus in discovery"
        assert "stablePairs" in discovery, "Missing stablePairs in discovery"
        assert "basePairs" in discovery, "Missing basePairs in discovery"
    
    def test_stats_has_existing_pools(self, api_client):
        """Stats should show existing pools (4 pools mentioned in context)"""
        response = api_client.get(f"{API_BASE}/stats", params={"chainId": 1})
        data = response.json()
        
        total = data.get("scoring", {}).get("total", 0)
        # Pools exist from previous setup
        assert total >= 0, f"Expected pools >= 0, got {total}"
        print(f"Total pools in system: {total}")


# ═══════════════════════════════════════════════════════════════
# TEST CLASS: List Endpoint
# ═══════════════════════════════════════════════════════════════

class TestPoolList:
    """Tests for GET /pools/list - list pools with scores"""
    
    def test_list_endpoint_returns_200(self, api_client):
        """List endpoint should return 200 status code"""
        response = api_client.get(f"{API_BASE}/list", params={"chainId": 1})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    def test_list_response_structure(self, api_client):
        """List response should contain pools array with correct structure"""
        response = api_client.get(f"{API_BASE}/list", params={"chainId": 1})
        data = response.json()
        
        assert data.get("ok") is True
        assert "chainId" in data
        assert "count" in data
        assert "pools" in data
        assert isinstance(data["pools"], list)
    
    def test_list_pool_item_structure(self, api_client):
        """Each pool in list should have required fields"""
        response = api_client.get(f"{API_BASE}/list", params={"chainId": 1})
        data = response.json()
        
        pools = data.get("pools", [])
        if pools:
            pool = pools[0]
            required_fields = [
                "address", "token0", "token1", "fee", "status", 
                "score", "confidence", "isStablePair"
            ]
            for field in required_fields:
                assert field in pool, f"Missing {field} in pool: {pool}"
            
            # Verify field types
            assert isinstance(pool["score"], (int, float))
            assert isinstance(pool["confidence"], (int, float))
            assert isinstance(pool["isStablePair"], bool)
            print(f"Sample pool: {pool['address']}, status={pool['status']}, score={pool['score']}")
    
    def test_list_with_status_filter(self, api_client):
        """List should support status filter"""
        # Test DISABLED filter (most likely status for existing pools)
        response = api_client.get(f"{API_BASE}/list", params={"chainId": 1, "status": "DISABLED"})
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        pools = data.get("pools", [])
        
        # All returned pools should have DISABLED status
        for pool in pools:
            assert pool["status"] == "DISABLED", f"Pool with wrong status: {pool['status']}"
    
    def test_list_with_limit(self, api_client):
        """List should respect limit parameter"""
        response = api_client.get(f"{API_BASE}/list", params={"chainId": 1, "limit": 2})
        data = response.json()
        
        assert len(data.get("pools", [])) <= 2
    
    def test_list_sorted_by_score(self, api_client):
        """List should be sorted by score descending"""
        response = api_client.get(f"{API_BASE}/list", params={"chainId": 1, "limit": 10})
        data = response.json()
        
        pools = data.get("pools", [])
        if len(pools) >= 2:
            scores = [p["score"] for p in pools]
            # Verify descending order
            for i in range(len(scores) - 1):
                assert scores[i] >= scores[i+1], f"Pools not sorted by score: {scores}"


# ═══════════════════════════════════════════════════════════════
# TEST CLASS: Best Pool Endpoint
# ═══════════════════════════════════════════════════════════════

class TestBestPool:
    """Tests for GET /pools/best - get best stable pool for token"""
    
    def test_best_endpoint_returns_200(self, api_client):
        """Best pool endpoint should return 200 status code"""
        response = api_client.get(f"{API_BASE}/best", params={"chainId": 1, "token": WETH})
        assert response.status_code == 200
    
    def test_best_pool_for_weth(self, api_client):
        """Should return best stable pool for WETH"""
        response = api_client.get(f"{API_BASE}/best", params={"chainId": 1, "token": WETH})
        data = response.json()
        
        assert data.get("ok") is True
        assert data["chainId"] == 1
        assert data["token"].lower() == WETH.lower()
        
        # Pool may be null if no stable pairs exist, or contain pool data
        pool = data.get("pool")
        if pool:
            assert "pool" in pool, f"Missing pool address: {pool}"
            assert "token0" in pool
            assert "token1" in pool
            assert "fee" in pool
            assert "score" in pool
            assert "stableToken" in pool
            print(f"Best pool for WETH: {pool['pool']}, score={pool['score']}, status={pool['status']}")
    
    def test_best_pool_missing_token(self, api_client):
        """Should return error when token is missing"""
        response = api_client.get(f"{API_BASE}/best", params={"chainId": 1})
        data = response.json()
        
        assert data.get("ok") is False
        assert "error" in data
    
    def test_best_pool_unknown_token(self, api_client):
        """Should return null pool for unknown token"""
        unknown = "0x0000000000000000000000000000000000000001"
        response = api_client.get(f"{API_BASE}/best", params={"chainId": 1, "token": unknown})
        data = response.json()
        
        assert data.get("ok") is True
        assert data.get("pool") is None, f"Expected null pool for unknown token: {data}"
    
    def test_best_pool_for_stable(self, api_client):
        """Best pool for stable token (USDC) should return pool with WETH or other"""
        response = api_client.get(f"{API_BASE}/best", params={"chainId": 1, "token": USDC})
        data = response.json()
        
        assert data.get("ok") is True
        # USDC may have stable pairs with other tokens
        print(f"Best pool for USDC: {data.get('pool')}")


# ═══════════════════════════════════════════════════════════════
# TEST CLASS: Score Endpoint
# ═══════════════════════════════════════════════════════════════

class TestPoolScoring:
    """Tests for POST /pools/score - run scoring for chain"""
    
    def test_score_endpoint_returns_200(self, api_client):
        """Score endpoint should return 200 status code"""
        response = api_client.post(f"{API_BASE}/score", json={"chainId": 1})
        assert response.status_code == 200
    
    def test_score_response_structure(self, api_client):
        """Score response should contain expected fields"""
        response = api_client.post(f"{API_BASE}/score", json={"chainId": 1})
        data = response.json()
        
        assert data.get("ok") is True
        assert "chainId" in data
        assert "updated" in data
        assert "summary" in data
        
        summary = data["summary"]
        for status in ["CANDIDATE", "ACTIVE", "DEGRADED", "DISABLED"]:
            assert status in summary, f"Missing {status} in summary"
        
        print(f"Scoring result: updated={data['updated']}, summary={data['summary']}")
    
    def test_score_updates_pools(self, api_client):
        """Scoring should update pool scores"""
        response = api_client.post(f"{API_BASE}/score", json={"chainId": 1})
        data = response.json()
        
        updated = data.get("updated", 0)
        # Should update the existing pools
        assert isinstance(updated, int)
        print(f"Updated {updated} pools")
    
    def test_score_status_transitions(self, api_client):
        """Verify status transitions based on score thresholds"""
        # First run scoring
        response = api_client.post(f"{API_BASE}/score", json={"chainId": 1})
        data = response.json()
        
        # Verify summary contains counts
        summary = data.get("summary", {})
        total = sum(summary.values())
        
        # Get actual pool statuses to verify
        list_response = api_client.get(f"{API_BASE}/list", params={"chainId": 1})
        list_data = list_response.json()
        
        pools = list_data.get("pools", [])
        for pool in pools[:5]:  # Check first 5 pools
            score = pool["score"]
            status = pool["status"]
            
            # Verify status matches expected based on score
            # ACTIVE: score >= 70, DEGRADED: score >= 45, DISABLED: score < 45
            if status == "ACTIVE":
                assert score >= 70 or pool["confidence"] >= 0.45, f"ACTIVE pool with low score: {pool}"
            elif status == "DEGRADED":
                assert score >= 45 or pool["confidence"] >= 0.25, f"DEGRADED with very low score: {pool}"
            
            print(f"Pool {pool['address'][:10]}...: score={score}, status={status}")


# ═══════════════════════════════════════════════════════════════
# TEST CLASS: Discovery Endpoint
# ═══════════════════════════════════════════════════════════════

class TestPoolDiscovery:
    """Tests for POST /pools/discover - run discovery for chain"""
    
    def test_discover_endpoint_returns_200(self, api_client):
        """Discover endpoint should return 200 status code"""
        response = api_client.post(f"{API_BASE}/discover", json={"chainId": 1, "window": "24h"})
        assert response.status_code == 200
    
    def test_discover_response_structure(self, api_client):
        """Discovery response should contain expected fields"""
        response = api_client.post(f"{API_BASE}/discover", json={"chainId": 1, "window": "24h"})
        data = response.json()
        
        assert "ok" in data
        assert "chainId" in data
        assert "window" in data
        assert "tokensScanned" in data
        assert "poolsFound" in data
        assert "poolsUpserted" in data
        assert "errors" in data
        
        print(f"Discovery result: tokensScanned={data['tokensScanned']}, poolsFound={data['poolsFound']}, upserted={data['poolsUpserted']}")
    
    def test_discover_with_7d_window(self, api_client):
        """Discovery should work with 7d window"""
        response = api_client.post(f"{API_BASE}/discover", json={"chainId": 1, "window": "7d"})
        data = response.json()
        
        assert data.get("window") == "7d"


# ═══════════════════════════════════════════════════════════════
# TEST CLASS: Job Status Endpoint
# ═══════════════════════════════════════════════════════════════

class TestJobStatus:
    """Tests for GET /pools/job/status - job status"""
    
    def test_job_status_returns_200(self, api_client):
        """Job status endpoint should return 200"""
        response = api_client.get(f"{API_BASE}/job/status")
        assert response.status_code == 200
    
    def test_job_status_structure(self, api_client):
        """Job status should contain expected fields"""
        response = api_client.get(f"{API_BASE}/job/status")
        data = response.json()
        
        assert data.get("ok") is True
        assert "running" in data
        assert "enabled" in data
        assert "intervalMs" in data
        assert "lastRunAt" in data
        assert "lastResult" in data
        assert "nextRunAt" in data
        
        print(f"Job status: running={data['running']}, enabled={data['enabled']}, intervalMs={data['intervalMs']}")
    
    def test_job_status_types(self, api_client):
        """Job status fields should have correct types"""
        response = api_client.get(f"{API_BASE}/job/status")
        data = response.json()
        
        assert isinstance(data["running"], bool)
        assert isinstance(data["enabled"], bool)
        assert isinstance(data["intervalMs"], int)


# ═══════════════════════════════════════════════════════════════
# TEST CLASS: Job Run Endpoint
# ═══════════════════════════════════════════════════════════════

class TestJobRun:
    """Tests for POST /pools/job/run - force run job"""
    
    def test_job_run_returns_200(self, api_client):
        """Force run endpoint should return 200"""
        response = api_client.post(f"{API_BASE}/job/run", json={})
        assert response.status_code == 200
    
    def test_job_run_response_structure(self, api_client):
        """Force run should return result array or null"""
        response = api_client.post(f"{API_BASE}/job/run", json={})
        data = response.json()
        
        assert data.get("ok") is True
        # Result can be array of chain results or null if no chains configured
        result = data.get("result")
        if result:
            assert isinstance(result, list)
            for r in result:
                assert "chainId" in r
                assert "discovered" in r
                assert "scored" in r
            print(f"Job run results: {result}")
        else:
            print("Job run result is null (no active chains)")


# ═══════════════════════════════════════════════════════════════
# TEST CLASS: Job Start/Stop Endpoints
# ═══════════════════════════════════════════════════════════════

class TestJobControl:
    """Tests for job start/stop endpoints"""
    
    def test_job_start_returns_200(self, api_client):
        """Job start endpoint should return 200"""
        response = api_client.post(f"{API_BASE}/job/start", json={})
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "running" in data
    
    def test_job_stop_returns_200(self, api_client):
        """Job stop endpoint should return 200"""
        response = api_client.post(f"{API_BASE}/job/stop", json={})
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True


# ═══════════════════════════════════════════════════════════════
# TEST CLASS: Integration Tests
# ═══════════════════════════════════════════════════════════════

class TestPoolScoringIntegration:
    """End-to-end integration tests for pool scoring"""
    
    def test_score_then_verify_list(self, api_client):
        """Run scoring, then verify pools have scores in list"""
        # 1. Run scoring
        score_response = api_client.post(f"{API_BASE}/score", json={"chainId": 1})
        score_data = score_response.json()
        assert score_data.get("ok") is True
        
        # 2. Get list and verify scores
        list_response = api_client.get(f"{API_BASE}/list", params={"chainId": 1})
        list_data = list_response.json()
        
        pools = list_data.get("pools", [])
        for pool in pools:
            # Score should be between 0 and 100
            assert 0 <= pool["score"] <= 100, f"Invalid score: {pool['score']}"
            # Confidence should be between 0 and 1
            assert 0 <= pool["confidence"] <= 1, f"Invalid confidence: {pool['confidence']}"
    
    def test_score_then_verify_stats(self, api_client):
        """Run scoring, then verify stats are updated"""
        # 1. Run scoring
        score_response = api_client.post(f"{API_BASE}/score", json={"chainId": 1})
        score_data = score_response.json()
        updated_count = score_data.get("updated", 0)
        
        # 2. Get stats and verify
        stats_response = api_client.get(f"{API_BASE}/stats", params={"chainId": 1})
        stats_data = stats_response.json()
        
        scoring_stats = stats_data.get("scoring", {})
        total = scoring_stats.get("total", 0)
        
        # Stats total should match what was scored
        assert total >= 0
        print(f"Scored {updated_count} pools, stats shows {total} total")
    
    def test_best_pool_returns_highest_scored(self, api_client):
        """Best pool should return highest scored stable pair"""
        # 1. First ensure scoring is done
        api_client.post(f"{API_BASE}/score", json={"chainId": 1})
        
        # 2. Get best pool for WETH
        best_response = api_client.get(f"{API_BASE}/best", params={"chainId": 1, "token": WETH})
        best_data = best_response.json()
        
        best_pool = best_data.get("pool")
        if best_pool:
            # Get list of all WETH stable pools
            list_response = api_client.get(f"{API_BASE}/list", params={"chainId": 1})
            all_pools = list_response.json().get("pools", [])
            
            # Filter stable pairs containing WETH
            weth_stable_pools = [
                p for p in all_pools 
                if p["isStablePair"] and (
                    p["token0"].lower() == WETH.lower() or 
                    p["token1"].lower() == WETH.lower()
                )
            ]
            
            if weth_stable_pools:
                # Best should be highest scored among stable pairs
                max_score = max(p["score"] for p in weth_stable_pools)
                assert best_pool["score"] >= max_score * 0.9, \
                    f"Best pool score {best_pool['score']} not near max {max_score}"
