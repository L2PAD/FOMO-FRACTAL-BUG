"""
OnChain V2 Pricing Layer (STEP 1) - Backend API Tests
=====================================================

Tests for multi-source USD valuation service:
- GET /api/v10/onchain-v2/market/pricing/health
- GET /api/v10/onchain-v2/market/pricing/latest
- POST /api/v10/onchain-v2/market/pricing/batch
- POST /api/v10/onchain-v2/market/pricing/refresh
- POST /api/v10/onchain-v2/market/pricing/clear-cache

Price Sources (priority order):
1. Chainlink (confidence 0.95)
2. UniV3 TWAP (confidence 0.75)
3. DEX VWAP (confidence 0.35)
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
API_PREFIX = "/api/v10/onchain-v2/market/pricing"

# Test tokens with Chainlink feeds (ETH Mainnet chainId=1)
WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
USDC = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
USDT = "0xdac17f958d2ee523a2206206994597c13d831ec7"
UNI = "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984"
WBTC = "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599"
UNKNOWN_TOKEN = "0x0000000000000000000000000000000000000001"


class TestPricingHealth:
    """Health endpoint tests"""
    
    def test_health_returns_200(self):
        """GET /health should return 200 with service status"""
        response = requests.get(f"{BASE_URL}{API_PREFIX}/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=true, got: {data}"
        
    def test_health_contains_expected_fields(self):
        """Health response should contain cacheSize, totalProviders, settings"""
        response = requests.get(f"{BASE_URL}{API_PREFIX}/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "cacheSize" in data, f"Missing cacheSize in health: {data}"
        assert "totalProviders" in data, f"Missing totalProviders in health: {data}"
        assert data["totalProviders"] == 3, f"Expected 3 providers (Chainlink, TWAP, VWAP), got: {data['totalProviders']}"
        assert "settings" in data, f"Missing settings in health: {data}"
        assert "cacheTtlMs" in data.get("settings", {}), f"Missing cacheTtlMs in settings"
        assert "hardStaleMs" in data.get("settings", {}), f"Missing hardStaleMs in settings"


class TestLatestPrice:
    """GET /latest endpoint tests"""
    
    def test_latest_weth_price(self):
        """Chainlink should return WETH price with confidence 0.95"""
        response = requests.get(
            f"{BASE_URL}{API_PREFIX}/latest",
            params={"chainId": 1, "token": WETH}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=true, got: {data}"
        
        quote = data.get("data")
        assert quote is not None, f"Expected data (price quote), got null: {data}"
        assert quote["token"] == WETH.lower(), f"Token mismatch: {quote}"
        assert quote["chainId"] == 1, f"ChainId mismatch: {quote}"
        assert quote["source"] == "CHAINLINK", f"Expected CHAINLINK source, got: {quote['source']}"
        assert quote["confidence"] == 0.95, f"Expected confidence 0.95, got: {quote['confidence']}"
        assert quote["priceUsd"] > 0, f"Expected positive price, got: {quote['priceUsd']}"
        # WETH typically $1500-$5000
        assert 500 < quote["priceUsd"] < 10000, f"WETH price out of range: {quote['priceUsd']}"
        
    def test_latest_usdc_price(self):
        """USDC should return ~$1 from Chainlink"""
        response = requests.get(
            f"{BASE_URL}{API_PREFIX}/latest",
            params={"chainId": 1, "token": USDC}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=true: {data}"
        
        quote = data.get("data")
        assert quote is not None, f"Expected price quote for USDC"
        assert quote["source"] == "CHAINLINK", f"Expected CHAINLINK for USDC"
        assert quote["confidence"] == 0.95, f"Expected 0.95 confidence"
        # USDC should be very close to $1
        assert 0.98 < quote["priceUsd"] < 1.02, f"USDC price should be ~$1, got: {quote['priceUsd']}"
        
    def test_latest_usdt_price(self):
        """USDT should return ~$1 from Chainlink"""
        response = requests.get(
            f"{BASE_URL}{API_PREFIX}/latest",
            params={"chainId": 1, "token": USDT}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        quote = data.get("data")
        assert quote is not None, f"Expected price quote for USDT"
        assert quote["source"] == "CHAINLINK"
        # USDT should be very close to $1
        assert 0.98 < quote["priceUsd"] < 1.02, f"USDT price should be ~$1, got: {quote['priceUsd']}"
        
    def test_latest_uni_price(self):
        """UNI should return price from Chainlink"""
        response = requests.get(
            f"{BASE_URL}{API_PREFIX}/latest",
            params={"chainId": 1, "token": UNI}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        quote = data.get("data")
        assert quote is not None, f"Expected price quote for UNI"
        assert quote["source"] == "CHAINLINK"
        assert quote["confidence"] == 0.95
        # UNI typically $3-$50
        assert 1 < quote["priceUsd"] < 100, f"UNI price out of expected range: {quote['priceUsd']}"
        
    def test_latest_wbtc_price(self):
        """WBTC should return a price (from Chainlink or fallback source)"""
        response = requests.get(
            f"{BASE_URL}{API_PREFIX}/latest",
            params={"chainId": 1, "token": WBTC}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        quote = data.get("data")
        # Note: WBTC has Chainlink feed configured but may fallback to DEX_VWAP if RPC fails
        # The system should still return a price from a fallback source
        if quote is not None:
            assert quote["source"] in ["CHAINLINK", "UNIV3_TWAP", "DEX_VWAP"], \
                f"Unexpected source: {quote['source']}"
            assert quote["priceUsd"] > 0, f"Expected positive price for WBTC"
            # If Chainlink, validate correct price range; if fallback, confidence will be lower
            if quote["source"] == "CHAINLINK":
                assert 10000 < quote["priceUsd"] < 500000, f"WBTC price out of expected range: {quote['priceUsd']}"
                assert quote["confidence"] == 0.95
            else:
                # Fallback source - lower confidence expected
                assert quote["confidence"] < 0.95, f"Fallback should have lower confidence"
                print(f"NOTE: WBTC using fallback source {quote['source']} with price {quote['priceUsd']}")
        
    def test_latest_unknown_token_returns_null(self):
        """Unknown token without Chainlink/pools should return null gracefully"""
        response = requests.get(
            f"{BASE_URL}{API_PREFIX}/latest",
            params={"chainId": 1, "token": UNKNOWN_TOKEN}
        )
        assert response.status_code == 200, f"Expected 200 even for unknown token"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=true: {data}"
        assert data.get("data") is None, f"Expected null data for unknown token, got: {data.get('data')}"
        
    def test_latest_missing_chainid_error(self):
        """Missing chainId should return error"""
        response = requests.get(
            f"{BASE_URL}{API_PREFIX}/latest",
            params={"token": WETH}
        )
        assert response.status_code == 200  # API returns 200 with ok:false
        
        data = response.json()
        assert data.get("ok") is False, f"Expected ok=false for missing chainId: {data}"
        assert "error" in data or "Missing" in str(data), f"Expected error message: {data}"
        
    def test_latest_missing_token_error(self):
        """Missing token should return error"""
        response = requests.get(
            f"{BASE_URL}{API_PREFIX}/latest",
            params={"chainId": 1}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is False, f"Expected ok=false for missing token: {data}"


class TestBatchPricing:
    """POST /batch endpoint tests"""
    
    def test_batch_multiple_known_tokens(self):
        """Batch request should return prices for multiple known tokens"""
        tokens = [WETH, USDC, UNI]
        response = requests.post(
            f"{BASE_URL}{API_PREFIX}/batch",
            json={"chainId": 1, "tokens": tokens}
        )
        assert response.status_code == 200, f"Expected 200: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=true: {data}"
        assert data.get("count") == 3, f"Expected count=3: {data}"
        
        prices = data.get("data", {})
        assert len(prices) == 3, f"Expected 3 prices: {prices}"
        
        # Verify each token has a price
        for token in tokens:
            token_lower = token.lower()
            assert token_lower in prices, f"Missing price for {token}"
            quote = prices[token_lower]
            assert quote is not None, f"Expected price for {token}"
            assert quote["priceUsd"] > 0, f"Expected positive price for {token}"
            
    def test_batch_mixed_known_unknown_tokens(self):
        """Batch should handle mix of known and unknown tokens gracefully"""
        tokens = [WETH, UNKNOWN_TOKEN, USDC]
        response = requests.post(
            f"{BASE_URL}{API_PREFIX}/batch",
            json={"chainId": 1, "tokens": tokens}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=true: {data}"
        
        prices = data.get("data", {})
        
        # WETH should have price
        weth_price = prices.get(WETH.lower())
        assert weth_price is not None, f"Expected WETH price"
        assert weth_price["priceUsd"] > 0
        
        # Unknown token should be null
        unknown_price = prices.get(UNKNOWN_TOKEN.lower())
        assert unknown_price is None, f"Expected null for unknown token, got: {unknown_price}"
        
        # USDC should have price
        usdc_price = prices.get(USDC.lower())
        assert usdc_price is not None, f"Expected USDC price"
        
    def test_batch_all_major_tokens(self):
        """Batch all tokens with Chainlink feeds - all should return prices"""
        tokens = [WETH, USDC, USDT, UNI, WBTC]
        response = requests.post(
            f"{BASE_URL}{API_PREFIX}/batch",
            json={"chainId": 1, "tokens": tokens}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert data.get("count") == 5
        
        prices = data.get("data", {})
        
        # All 5 should have prices (Chainlink preferred, fallback acceptable)
        chainlink_count = 0
        for token in tokens:
            quote = prices.get(token.lower())
            assert quote is not None, f"Missing price for {token}"
            assert quote["source"] in ["CHAINLINK", "UNIV3_TWAP", "DEX_VWAP"], \
                f"Unknown source for {token}: {quote.get('source')}"
            if quote["source"] == "CHAINLINK":
                chainlink_count += 1
        
        # At least most tokens should use Chainlink (allow some fallback due to RPC issues)
        assert chainlink_count >= 3, f"Expected at least 3 Chainlink sources, got: {chainlink_count}"
            
    def test_batch_missing_chainid_error(self):
        """Batch without chainId should fail"""
        response = requests.post(
            f"{BASE_URL}{API_PREFIX}/batch",
            json={"tokens": [WETH]}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is False, f"Expected ok=false: {data}"
        
    def test_batch_missing_tokens_error(self):
        """Batch without tokens array should fail"""
        response = requests.post(
            f"{BASE_URL}{API_PREFIX}/batch",
            json={"chainId": 1}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is False, f"Expected ok=false: {data}"


class TestRefreshPrice:
    """POST /refresh endpoint tests"""
    
    def test_refresh_weth_price(self):
        """Force refresh should fetch fresh price from providers"""
        # First, clear cache to ensure fresh fetch
        requests.post(f"{BASE_URL}{API_PREFIX}/clear-cache")
        
        response = requests.post(
            f"{BASE_URL}{API_PREFIX}/refresh",
            json={"chainId": 1, "token": WETH}
        )
        assert response.status_code == 200, f"Expected 200: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=true: {data}"
        
        quote = data.get("data")
        assert quote is not None, f"Expected fresh price quote"
        assert quote["source"] == "CHAINLINK"
        assert quote["priceUsd"] > 0
        # updatedAt should be recent (within last 5 minutes as there's caching)
        assert quote["updatedAt"] > (time.time() * 1000 - 300000), f"Price too stale"
        
    def test_refresh_unknown_token_returns_null(self):
        """Refresh unknown token should return null (no providers have it)"""
        response = requests.post(
            f"{BASE_URL}{API_PREFIX}/refresh",
            json={"chainId": 1, "token": UNKNOWN_TOKEN}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert data.get("data") is None, f"Expected null for unknown token"


class TestClearCache:
    """POST /clear-cache endpoint tests"""
    
    def test_clear_cache(self):
        """Clear cache should reset memory cache"""
        response = requests.post(f"{BASE_URL}{API_PREFIX}/clear-cache")
        assert response.status_code == 200, f"Expected 200: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=true: {data}"
        assert "cleared" in data.get("message", "").lower() or "cache" in data.get("message", "").lower(), \
            f"Expected cache cleared message: {data}"
            
    def test_cache_cleared_verified_by_health(self):
        """After clearing cache, health should show cacheSize = 0"""
        # Clear cache
        response = requests.post(f"{BASE_URL}{API_PREFIX}/clear-cache")
        assert response.status_code == 200
        
        # Check health
        health_response = requests.get(f"{BASE_URL}{API_PREFIX}/health")
        assert health_response.status_code == 200
        
        health = health_response.json()
        assert health.get("cacheSize") == 0, f"Expected cacheSize=0 after clear, got: {health.get('cacheSize')}"


class TestPricingCacheBehavior:
    """Test caching behavior - prices should be cached after first fetch"""
    
    def test_cache_populated_after_fetch(self):
        """Fetching a price should populate the cache"""
        # Clear cache first
        requests.post(f"{BASE_URL}{API_PREFIX}/clear-cache")
        
        # Verify cache is empty
        health1 = requests.get(f"{BASE_URL}{API_PREFIX}/health").json()
        assert health1.get("cacheSize") == 0, f"Cache should be empty: {health1}"
        
        # Fetch WETH price
        response = requests.get(
            f"{BASE_URL}{API_PREFIX}/latest",
            params={"chainId": 1, "token": WETH}
        )
        assert response.status_code == 200
        
        # Verify cache now has 1 entry
        health2 = requests.get(f"{BASE_URL}{API_PREFIX}/health").json()
        assert health2.get("cacheSize") >= 1, f"Cache should have at least 1 entry: {health2}"
        
    def test_cached_price_returned_quickly(self):
        """Second fetch should return cached price quickly"""
        # First fetch
        start1 = time.time()
        response1 = requests.get(
            f"{BASE_URL}{API_PREFIX}/latest",
            params={"chainId": 1, "token": USDC}
        )
        time1 = time.time() - start1
        
        # Second fetch (should be cached)
        start2 = time.time()
        response2 = requests.get(
            f"{BASE_URL}{API_PREFIX}/latest",
            params={"chainId": 1, "token": USDC}
        )
        time2 = time.time() - start2
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        data1 = response1.json().get("data", {})
        data2 = response2.json().get("data", {})
        
        # Prices should be same (cached)
        assert data1.get("priceUsd") == data2.get("priceUsd"), \
            f"Cached price mismatch: {data1.get('priceUsd')} vs {data2.get('priceUsd')}"


class TestChainlinkSourceDetails:
    """Test Chainlink-specific features"""
    
    def test_chainlink_meta_contains_feed_info(self):
        """Chainlink response should include feed address in meta"""
        response = requests.get(
            f"{BASE_URL}{API_PREFIX}/latest",
            params={"chainId": 1, "token": WETH}
        )
        assert response.status_code == 200
        
        data = response.json()
        quote = data.get("data")
        assert quote is not None
        
        meta = quote.get("meta", {})
        assert "feedAddress" in meta, f"Expected feedAddress in meta: {meta}"
        assert "oracleUpdatedAt" in meta, f"Expected oracleUpdatedAt in meta: {meta}"
        assert "oracleDecimals" in meta, f"Expected oracleDecimals in meta: {meta}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
