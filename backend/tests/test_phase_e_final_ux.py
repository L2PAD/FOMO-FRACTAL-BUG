"""
Phase E: Final UX Cleanup - Backend API Tests
==============================================

Testing:
- E0: TradingView-style chart endpoints (series data for lightweight-charts)
- E1: Wallets v3 endpoint (profile, series)
- E4: Unified search router (token suggest, exchange, wallet)
- D1-D4 Regression: Token resolve, suggest, profile, series, movers

All endpoints tested via localhost:8003 (Node.js backend)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8003').rstrip('/')

# Use localhost for reliable testing (external gateway often times out)
LOCAL_BASE_URL = "http://localhost:8003"


class TestWalletsV3Health:
    """E1: Wallets v3 health endpoint"""
    
    def test_wallets_health(self):
        response = requests.get(f"{LOCAL_BASE_URL}/api/v10/onchain-v2/wallets/health", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert data["module"] == "wallets_v3"
        assert "cache" in data
        assert "jobs" in data
        print(f"Wallets health: {data}")


class TestTokenD1Resolve:
    """D1: Token resolve and suggest endpoints"""
    
    def test_resolve_by_symbol(self):
        """Resolve token by symbol"""
        response = requests.get(f"{LOCAL_BASE_URL}/api/v10/onchain-v2/market/tokens/resolve?chainId=1&q=WETH", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert data.get("token") is not None
        assert data["token"]["symbol"] == "WETH"
        print(f"Resolved WETH: {data['token']['address'][:10]}...")
    
    def test_resolve_by_address(self):
        """Resolve token by address"""
        response = requests.get(
            f"{LOCAL_BASE_URL}/api/v10/onchain-v2/market/tokens/resolve?chainId=1&q=0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
            timeout=10
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert data.get("token") is not None
        assert data["token"]["symbol"] == "WETH"
    
    def test_suggest_tokens(self):
        """Token autocomplete/suggest"""
        response = requests.get(f"{LOCAL_BASE_URL}/api/v10/onchain-v2/market/tokens/suggest?chainId=1&q=LINK&limit=5", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "items" in data
        assert len(data["items"]) > 0
        
        # Check LINK is in results
        symbols = [item["symbol"] for item in data["items"]]
        assert "LINK" in symbols
        print(f"Suggest 'LINK': found {len(data['items'])} items: {symbols}")
    
    def test_suggest_empty_query(self):
        """Empty query returns empty items"""
        response = requests.get(f"{LOCAL_BASE_URL}/api/v10/onchain-v2/market/tokens/suggest?chainId=1&q=&limit=5", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert data.get("items", []) == []


class TestTokenD2Profile:
    """D2: Token profile endpoint"""
    
    def test_weth_profile(self):
        """Get WETH token profile"""
        response = requests.get(f"{LOCAL_BASE_URL}/api/v10/onchain-v2/market/tokens/profile?chainId=1&token=WETH&window=7d", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert data["symbol"] == "WETH"
        
        # Check profile structure
        assert "priceUsd" in data  # May be null for wrapped tokens
        assert "tvlUsd" in data
        assert "poolScore" in data
        assert "poolStatus" in data
        assert "activePools" in data
        assert "trades24h" in data
        assert "pricedShare" in data
        print(f"WETH profile: TVL=${data['tvlUsd']:,.0f}, pools={data['activePools']}, trades={data['trades24h']}")
    
    def test_nonexistent_token_profile(self):
        """Non-existent token returns ok:false"""
        response = requests.get(f"{LOCAL_BASE_URL}/api/v10/onchain-v2/market/tokens/profile?chainId=1&token=NONEXISTENTTOKEN&window=7d", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is False
        assert "reason" in data or "error" in data


class TestTokenD3Series:
    """D3: Token series endpoint for TradingView chart (E0)"""
    
    def test_weth_series_7d(self):
        """Get WETH 7d series for TradingView chart"""
        response = requests.get(f"{LOCAL_BASE_URL}/api/v10/onchain-v2/market/tokens/series?chainId=1&token=WETH&window=7d", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "buckets" in data
        
        # Each bucket should have: ts, inflowUsd, outflowUsd, netUsd, transfers, uniqueWallets
        if len(data["buckets"]) > 0:
            bucket = data["buckets"][0]
            assert "ts" in bucket
            assert "inflowUsd" in bucket
            assert "outflowUsd" in bucket
            assert "netUsd" in bucket
            assert "transfers" in bucket
            print(f"WETH series: {len(data['buckets'])} buckets, stale={data.get('stale', False)}")
    
    def test_series_windows(self):
        """Test all window sizes"""
        for window in ["24h", "7d", "30d"]:
            response = requests.get(f"{LOCAL_BASE_URL}/api/v10/onchain-v2/market/tokens/series?chainId=1&token=WETH&window={window}", timeout=15)
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            print(f"  {window}: {len(data.get('buckets', []))} buckets")


class TestTokenD4Movers:
    """D4: Token movers endpoint"""
    
    def test_weth_movers(self):
        """Get WETH top movers"""
        response = requests.get(f"{LOCAL_BASE_URL}/api/v10/onchain-v2/market/tokens/movers?chainId=1&token=WETH&window=7d", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "topEntities" in data
        assert "topWallets" in data
        
        # Check structure
        if len(data["topEntities"]) > 0:
            entity = data["topEntities"][0]
            assert "entityId" in entity
            assert "label" in entity
            assert "inflowUsd" in entity
            assert "netUsd" in entity
        
        if len(data["topWallets"]) > 0:
            wallet = data["topWallets"][0]
            assert "address" in wallet
            assert "netUsd" in wallet
        
        print(f"WETH movers: {len(data['topEntities'])} entities, {len(data['topWallets'])} wallets")


class TestWalletsV3Profile:
    """Wallets v3 profile endpoint"""
    
    def test_wallet_profile(self):
        """Get wallet profile by address"""
        # Use a known active wallet address
        test_address = "0x51c72848c68a965f66fa7a88855f9f7784502a7f"
        response = requests.get(f"{LOCAL_BASE_URL}/api/v10/onchain-v2/wallets/profile?address={test_address}&window=7d", timeout=20)
        assert response.status_code == 200
        
        data = response.json()
        # Wallet might not be in cache, so just check structure
        if data["ok"]:
            assert "address" in data
            assert "totals" in data
            assert "attribution" in data
            print(f"Wallet profile loaded: {data.get('totals', {}).get('transfers', 0)} transfers")
        else:
            print(f"Wallet profile not cached: {data.get('error', 'unknown')}")


class TestWalletsV3Series:
    """Wallets v3 series endpoint for TradingView chart"""
    
    def test_wallet_series(self):
        """Get wallet flow series"""
        test_address = "0x51c72848c68a965f66fa7a88855f9f7784502a7f"
        response = requests.get(f"{LOCAL_BASE_URL}/api/v10/onchain-v2/wallets/series?address={test_address}&window=7d&metric=netUsd", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        if data["ok"]:
            assert "points" in data
            print(f"Wallet series: {len(data.get('points', []))} points")
        else:
            print(f"Wallet series not available: {data.get('error', 'unknown')}")


class TestUnifiedSearchE4:
    """E4: Unified search router functionality"""
    
    def test_token_suggest_for_search(self):
        """Token suggest API works for unified search"""
        # Search for 'uni' - should return UNI token
        response = requests.get(f"{LOCAL_BASE_URL}/api/v10/onchain-v2/market/tokens/suggest?chainId=1&q=uni&limit=5", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "items" in data
        
        symbols = [item["symbol"].upper() for item in data["items"]]
        assert "UNI" in symbols
        print(f"Unified search 'uni': found UNI token")
    
    def test_link_token_suggest(self):
        """LINK token in suggest results"""
        response = requests.get(f"{LOCAL_BASE_URL}/api/v10/onchain-v2/market/tokens/suggest?chainId=1&q=link&limit=5", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        symbols = [item["symbol"].upper() for item in data["items"]]
        assert "LINK" in symbols
        print(f"Unified search 'link': found LINK token")


class TestSeriesJobStatus:
    """D3: Series job status endpoint"""
    
    def test_series_status(self):
        """Check series aggregation job status"""
        response = requests.get(f"{LOCAL_BASE_URL}/api/v10/onchain-v2/market/tokens/series/status", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        
        # Check job status fields
        assert "running" in data or "status" in data
        print(f"Series job status: {data}")


# Run specific test classes
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
