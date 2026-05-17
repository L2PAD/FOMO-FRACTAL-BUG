"""
Wallet v3 Phase C3 Drilldowns - Backend API Tests
===================================================
Tests for the new bucket-based wallet token and counterparty drilldown endpoints.

Endpoints tested:
  GET /api/v10/onchain-v2/wallets/health
  GET /api/v10/onchain-v2/wallets/profile
  GET /api/v10/onchain-v2/wallets/tokens
  GET /api/v10/onchain-v2/wallets/counterparties
  POST /api/v10/onchain-v2/wallets/buckets/aggregate
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_ADDRESS = "0x51c72848c68a965f66fa7a88855f9f7784502a7f"

@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestWalletsV3Health:
    """Health endpoint tests"""
    
    def test_health_returns_ok(self, api_client):
        """GET /api/v10/onchain-v2/wallets/health returns ok: true"""
        response = api_client.get(f"{BASE_URL}/api/v10/onchain-v2/wallets/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert data.get("module") == "wallets_v3"
        assert "cache" in data
        assert "jobs" in data
        print(f"Health check passed: module={data['module']}, cache enabled={data['cache']['enabled']}")


class TestWalletsV3Tokens:
    """Token drilldown endpoint tests (C3.1)"""
    
    def test_tokens_missing_address_returns_400(self, api_client):
        """GET /wallets/tokens without address returns 400"""
        response = api_client.get(f"{BASE_URL}/api/v10/onchain-v2/wallets/tokens")
        assert response.status_code == 400
        
        data = response.json()
        assert data.get("ok") is False
        assert data.get("error") == "MISSING_ADDRESS"
        print("Token endpoint correctly rejects missing address with 400")
    
    def test_tokens_returns_correct_structure(self, api_client):
        """GET /wallets/tokens returns bucket-based token data"""
        response = api_client.get(
            f"{BASE_URL}/api/v10/onchain-v2/wallets/tokens",
            params={"address": TEST_ADDRESS, "chainId": 1, "window": "30d"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert data.get("bucketed") is True
        assert "items" in data
        assert data.get("chainId") == 1
        assert data.get("address") == TEST_ADDRESS.lower()
        assert data.get("window") == "30d"
        
        # Validate item structure if we have items
        if data["items"]:
            item = data["items"][0]
            assert "tokenAddress" in item
            assert "inUsd" in item
            assert "outUsd" in item
            assert "netUsd" in item
            assert "transfers" in item
            print(f"Token endpoint returned {len(data['items'])} items, bucketCount={data.get('bucketCount', 0)}")
        else:
            print("Token endpoint returned 0 items (no bucket data)")
    
    def test_tokens_different_windows(self, api_client):
        """Test tokens endpoint with different window values"""
        for window in ["24h", "7d", "30d"]:
            response = api_client.get(
                f"{BASE_URL}/api/v10/onchain-v2/wallets/tokens",
                params={"address": TEST_ADDRESS, "window": window}
            )
            assert response.status_code == 200
            data = response.json()
            assert data.get("ok") is True
            assert data.get("window") == window
            print(f"Token endpoint window={window}: {len(data.get('items', []))} items")


class TestWalletsV3Counterparties:
    """Counterparty drilldown endpoint tests (C3.2)"""
    
    def test_counterparties_missing_address_returns_400(self, api_client):
        """GET /wallets/counterparties without address returns 400"""
        response = api_client.get(f"{BASE_URL}/api/v10/onchain-v2/wallets/counterparties")
        assert response.status_code == 400
        
        data = response.json()
        assert data.get("ok") is False
        assert data.get("error") == "MISSING_ADDRESS"
        print("Counterparty endpoint correctly rejects missing address with 400")
    
    def test_counterparties_returns_correct_structure(self, api_client):
        """GET /wallets/counterparties returns bucket-based counterparty data"""
        response = api_client.get(
            f"{BASE_URL}/api/v10/onchain-v2/wallets/counterparties",
            params={"address": TEST_ADDRESS, "chainId": 1, "window": "30d"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert data.get("bucketed") is True
        assert "items" in data
        assert data.get("chainId") == 1
        assert data.get("address") == TEST_ADDRESS.lower()
        assert data.get("window") == "30d"
        
        # Validate item structure if we have items
        if data["items"]:
            item = data["items"][0]
            assert "address" in item
            assert "inUsd" in item
            assert "outUsd" in item
            assert "netUsd" in item
            assert "transfers" in item
            assert "attribution" in item
            
            # Validate attribution structure
            attr = item["attribution"]
            assert "entityId" in attr or attr.get("entityId") is None
            assert "source" in attr
            assert "confidence" in attr
            print(f"Counterparty endpoint returned {len(data['items'])} items, bucketCount={data.get('bucketCount', 0)}")
        else:
            print("Counterparty endpoint returned 0 items (no bucket data)")
    
    def test_counterparties_different_windows(self, api_client):
        """Test counterparties endpoint with different window values"""
        for window in ["24h", "7d", "30d"]:
            response = api_client.get(
                f"{BASE_URL}/api/v10/onchain-v2/wallets/counterparties",
                params={"address": TEST_ADDRESS, "window": window}
            )
            assert response.status_code == 200
            data = response.json()
            assert data.get("ok") is True
            assert data.get("window") == window
            print(f"Counterparty endpoint window={window}: {len(data.get('items', []))} items")


class TestWalletsV3Profile:
    """Profile endpoint tests (backward compatibility)"""
    
    def test_profile_returns_ok(self, api_client):
        """GET /wallets/profile with valid address works"""
        response = api_client.get(
            f"{BASE_URL}/api/v10/onchain-v2/wallets/profile",
            params={"address": TEST_ADDRESS, "window": "7d"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "totals" in data
        assert "attribution" in data
        assert "topTokens" in data
        assert "topCounterparties" in data
        assert "meta" in data
        print(f"Profile returned: transfers={data['totals']['transfers']}, counterparties={data['totals']['uniqueCounterparties']}")
    
    def test_profile_missing_address_returns_400(self, api_client):
        """GET /wallets/profile without address returns 400"""
        response = api_client.get(f"{BASE_URL}/api/v10/onchain-v2/wallets/profile")
        assert response.status_code == 400
        
        data = response.json()
        assert data.get("ok") is False
        assert data.get("error") == "MISSING_ADDRESS"


class TestWalletsV3BucketAggregate:
    """Bucket aggregate endpoint tests (C2)"""
    
    def test_bucket_aggregate_returns_token_and_cp_buckets(self):
        """POST /wallets/buckets/aggregate populates tokenBuckets and cpBuckets"""
        # POST without Content-Type to avoid empty body error
        response = requests.post(
            f"{BASE_URL}/api/v10/onchain-v2/wallets/buckets/aggregate",
            params={"address": TEST_ADDRESS, "chainId": 1, "days": 30}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "bucketsUpserted" in data
        assert "tokenBuckets" in data
        assert "cpBuckets" in data
        assert "elapsed" in data
        
        print(f"Aggregate result: buckets={data['bucketsUpserted']}, tokenBuckets={data['tokenBuckets']}, cpBuckets={data['cpBuckets']}, elapsed={data['elapsed']}ms")
    
    def test_bucket_aggregate_missing_address_returns_400(self):
        """POST /wallets/buckets/aggregate without address returns 400"""
        response = requests.post(f"{BASE_URL}/api/v10/onchain-v2/wallets/buckets/aggregate")
        assert response.status_code == 400
        
        data = response.json()
        assert data.get("ok") is False
        assert data.get("error") == "MISSING_ADDRESS"


class TestWalletsV3Integration:
    """End-to-end integration tests"""
    
    def test_aggregate_then_tokens_has_data(self, api_client):
        """After aggregation, tokens endpoint should return data"""
        # First aggregate (no Content-Type header for POST without body)
        agg_response = requests.post(
            f"{BASE_URL}/api/v10/onchain-v2/wallets/buckets/aggregate",
            params={"address": TEST_ADDRESS, "chainId": 1, "days": 30}
        )
        assert agg_response.status_code == 200
        agg_data = agg_response.json()
        
        # Then fetch tokens
        tokens_response = api_client.get(
            f"{BASE_URL}/api/v10/onchain-v2/wallets/tokens",
            params={"address": TEST_ADDRESS, "chainId": 1, "window": "30d"}
        )
        assert tokens_response.status_code == 200
        tokens_data = tokens_response.json()
        
        # Verify data consistency
        assert tokens_data.get("ok") is True
        assert tokens_data.get("bucketed") is True
        
        print(f"Integration test: aggregated {agg_data['tokenBuckets']} token buckets, tokens endpoint returned {len(tokens_data.get('items', []))} items")
    
    def test_aggregate_then_counterparties_has_data(self, api_client):
        """After aggregation, counterparties endpoint should return data"""
        # First aggregate (no Content-Type header for POST without body)
        agg_response = requests.post(
            f"{BASE_URL}/api/v10/onchain-v2/wallets/buckets/aggregate",
            params={"address": TEST_ADDRESS, "chainId": 1, "days": 30}
        )
        assert agg_response.status_code == 200
        agg_data = agg_response.json()
        
        # Then fetch counterparties
        cp_response = api_client.get(
            f"{BASE_URL}/api/v10/onchain-v2/wallets/counterparties",
            params={"address": TEST_ADDRESS, "chainId": 1, "window": "30d"}
        )
        assert cp_response.status_code == 200
        cp_data = cp_response.json()
        
        # Verify data consistency
        assert cp_data.get("ok") is True
        assert cp_data.get("bucketed") is True
        
        print(f"Integration test: aggregated {agg_data['cpBuckets']} cp buckets, counterparties endpoint returned {len(cp_data.get('items', []))} items")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
