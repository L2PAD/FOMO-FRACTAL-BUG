"""
Token Endpoints Phase D Testing — D1, D2, D3, D4
==================================================
Tests for the new token-related endpoints:
- D1: /tokens/resolve and /tokens/suggest
- D2: /tokens/profile
- D3: /tokens/series and /tokens/series/status
- D4: /tokens/movers

Known tokens: WETH, LINK, UNI, USDC, AAVE, MKR, WBTC, SNX
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
API_PREFIX = '/api/v10/onchain-v2/market/tokens'

class TestD1TokenResolve:
    """D1: Token resolve endpoint tests - /tokens/resolve"""

    def test_resolve_by_symbol_uni(self):
        """D1: Resolve UNI token by symbol"""
        url = f"{BASE_URL}{API_PREFIX}/resolve?chainId=1&q=UNI"
        resp = requests.get(url, timeout=30)
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data.get('ok') == True, "Response ok should be True"
        
        token = data.get('token')
        assert token is not None, "Token should not be None"
        assert 'address' in token, "Token should have address"
        assert 'symbol' in token, "Token should have symbol"
        assert 'name' in token, "Token should have name"
        assert 'verified' in token, "Token should have verified field"
        assert token['symbol'].upper() == 'UNI', f"Symbol should be UNI, got {token.get('symbol')}"
        print(f"✓ Resolved UNI: {token['address'][:10]}... verified={token['verified']}")

    def test_resolve_by_symbol_usdc(self):
        """D1: Resolve USDC (stablecoin) correctly"""
        url = f"{BASE_URL}{API_PREFIX}/resolve?chainId=1&q=USDC"
        resp = requests.get(url, timeout=30)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('ok') == True
        
        token = data.get('token')
        assert token is not None, "USDC should be resolved"
        assert token['symbol'].upper() == 'USDC', f"Symbol should be USDC, got {token.get('symbol')}"
        print(f"✓ Resolved USDC: {token['address'][:10]}... verified={token['verified']}")

    def test_resolve_by_address_weth(self):
        """D1: Resolve WETH by address"""
        weth_address = '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2'
        url = f"{BASE_URL}{API_PREFIX}/resolve?chainId=1&q={weth_address}"
        resp = requests.get(url, timeout=30)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('ok') == True
        
        token = data.get('token')
        assert token is not None, "Token should be resolved by address"
        assert token['address'].lower() == weth_address.lower(), "Address should match"
        print(f"✓ Resolved by address: {token['symbol']} ({token['name']})")

    def test_resolve_empty_query(self):
        """D1: Empty query returns null token"""
        url = f"{BASE_URL}{API_PREFIX}/resolve?chainId=1&q="
        resp = requests.get(url, timeout=30)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('ok') == True
        assert data.get('token') is None, "Empty query should return null token"
        print("✓ Empty query correctly returns null token")


class TestD1TokenSuggest:
    """D1: Token suggest endpoint tests - /tokens/suggest"""

    def test_suggest_query_un(self):
        """D1: Suggest with 'un' query returns UNI in results"""
        url = f"{BASE_URL}{API_PREFIX}/suggest?chainId=1&q=un"
        resp = requests.get(url, timeout=30)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('ok') == True
        assert 'items' in data, "Response should have items array"
        
        items = data['items']
        assert isinstance(items, list), "Items should be a list"
        
        # Should find UNI in results
        symbols = [item.get('symbol', '').upper() for item in items]
        assert 'UNI' in symbols, f"UNI should be in suggestions, got {symbols}"
        
        # Check item structure
        if len(items) > 0:
            item = items[0]
            assert 'address' in item
            assert 'symbol' in item
            assert 'name' in item
            assert 'verified' in item
        print(f"✓ Suggest 'un' returned {len(items)} items including UNI")

    def test_suggest_empty_query(self):
        """D1: Empty query returns empty items array"""
        url = f"{BASE_URL}{API_PREFIX}/suggest?chainId=1&q="
        resp = requests.get(url, timeout=30)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('ok') == True
        assert 'items' in data
        assert data['items'] == [], "Empty query should return empty items"
        print("✓ Empty suggest query returns empty items")

    def test_suggest_with_limit(self):
        """D1: Suggest respects limit parameter"""
        url = f"{BASE_URL}{API_PREFIX}/suggest?chainId=1&q=a&limit=3"
        resp = requests.get(url, timeout=30)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('ok') == True
        items = data.get('items', [])
        assert len(items) <= 3, f"Should respect limit=3, got {len(items)} items"
        print(f"✓ Suggest with limit=3 returned {len(items)} items")


class TestD2TokenProfile:
    """D2: Token profile endpoint tests - /tokens/profile"""

    def test_profile_weth_full_structure(self):
        """D2: Get WETH profile with full structure"""
        url = f"{BASE_URL}{API_PREFIX}/profile?chainId=1&token=WETH"
        resp = requests.get(url, timeout=30)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('ok') == True, f"Profile should return ok:true, got {data}"
        
        # Check all required fields
        required_fields = [
            'address', 'symbol', 'name', 'decimals', 'verified',
            'priceUsd', 'tvlUsd', 'poolScore', 'poolStatus', 'trades24h'
        ]
        for field in required_fields:
            assert field in data, f"Profile missing field: {field}"
        
        print(f"✓ WETH profile: price={data.get('priceUsd')}, tvl={data.get('tvlUsd')}, "
              f"poolScore={data.get('poolScore')}, poolStatus={data.get('poolStatus')}, "
              f"trades24h={data.get('trades24h')}")

    def test_profile_nonexistent_token(self):
        """D2: Profile for nonexistent token returns ok:false with reason"""
        url = f"{BASE_URL}{API_PREFIX}/profile?chainId=1&token=NONEXISTENT_TOKEN_XYZ123"
        resp = requests.get(url, timeout=30)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('ok') == False, "Nonexistent token should return ok:false"
        assert 'reason' in data, "Should have reason field"
        print(f"✓ Nonexistent token returns ok:false, reason={data.get('reason')}")

    def test_profile_missing_token_param(self):
        """D2: Profile without token param returns error"""
        url = f"{BASE_URL}{API_PREFIX}/profile?chainId=1"
        resp = requests.get(url, timeout=30)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('ok') == False
        assert data.get('reason') == 'MISSING_TOKEN'
        print("✓ Missing token param returns MISSING_TOKEN error")

    def test_profile_link_token(self):
        """D2: LINK token profile"""
        url = f"{BASE_URL}{API_PREFIX}/profile?chainId=1&token=LINK"
        resp = requests.get(url, timeout=30)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('ok') == True, f"LINK profile should return ok:true"
        assert data.get('symbol', '').upper() == 'LINK'
        print(f"✓ LINK profile retrieved: verified={data.get('verified')}")


class TestD3TokenSeries:
    """D3: Token series endpoint tests - /tokens/series"""

    def test_series_weth_7d(self):
        """D3: Get WETH series for 7d window - returns buckets array"""
        url = f"{BASE_URL}{API_PREFIX}/series?chainId=1&token=WETH&window=7d"
        resp = requests.get(url, timeout=30)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('ok') == True, f"Series should return ok:true, got {data}"
        assert 'buckets' in data, "Response should have buckets array"
        assert 'window' in data, "Response should have window"
        
        buckets = data['buckets']
        assert isinstance(buckets, list), "Buckets should be a list"
        
        # Check bucket structure if data exists
        if len(buckets) > 0:
            bucket = buckets[0]
            required_bucket_fields = ['ts', 'inflowUsd', 'outflowUsd', 'netUsd', 'transfers']
            for field in required_bucket_fields:
                assert field in bucket, f"Bucket missing field: {field}"
        
        print(f"✓ WETH series 7d: {len(buckets)} buckets, stale={data.get('stale', False)}")

    def test_series_status(self):
        """D3: Get series job status"""
        url = f"{BASE_URL}{API_PREFIX}/series/status"
        resp = requests.get(url, timeout=30)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('ok') == True
        
        # Check status fields
        assert 'running' in data
        assert 'tickCount' in data
        assert 'successCount' in data
        assert 'errorCount' in data
        print(f"✓ Series job status: running={data.get('running')}, "
              f"tickCount={data.get('tickCount')}, successCount={data.get('successCount')}")

    def test_series_different_windows(self):
        """D3: Series works for 24h, 7d, 30d windows"""
        for window in ['24h', '7d', '30d']:
            url = f"{BASE_URL}{API_PREFIX}/series?chainId=1&token=WETH&window={window}"
            resp = requests.get(url, timeout=30)
            
            assert resp.status_code == 200
            data = resp.json()
            assert data.get('ok') == True, f"Window {window} failed"
            assert data.get('window') == window, f"Window should be {window}"
            print(f"✓ WETH series {window}: {len(data.get('buckets', []))} buckets")

    def test_series_missing_token(self):
        """D3: Series without token returns error"""
        url = f"{BASE_URL}{API_PREFIX}/series?chainId=1&window=7d"
        resp = requests.get(url, timeout=30)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('ok') == False
        assert data.get('reason') == 'MISSING_TOKEN'
        print("✓ Missing token returns MISSING_TOKEN error")


class TestD4TokenMovers:
    """D4: Token movers endpoint tests - /tokens/movers"""

    def test_movers_weth_7d(self):
        """D4: Get WETH movers for 7d - returns topEntities and topWallets"""
        url = f"{BASE_URL}{API_PREFIX}/movers?chainId=1&token=WETH&window=7d"
        resp = requests.get(url, timeout=30)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('ok') == True, f"Movers should return ok:true, got {data}"
        
        # Check required fields
        assert 'topEntities' in data, "Response should have topEntities"
        assert 'topWallets' in data, "Response should have topWallets"
        assert 'tokenAddress' in data
        assert 'symbol' in data
        assert 'window' in data
        
        entities = data['topEntities']
        wallets = data['topWallets']
        
        assert isinstance(entities, list), "topEntities should be a list"
        assert isinstance(wallets, list), "topWallets should be a list"
        
        # Check entity structure if data exists
        if len(entities) > 0:
            entity = entities[0]
            entity_fields = ['entityId', 'label', 'inflowUsd', 'outflowUsd', 'netUsd', 'transfers']
            for field in entity_fields:
                assert field in entity, f"Entity missing field: {field}"
        
        # Check wallet structure if data exists
        if len(wallets) > 0:
            wallet = wallets[0]
            wallet_fields = ['address', 'inflowUsd', 'outflowUsd', 'netUsd', 'transfers']
            for field in wallet_fields:
                assert field in wallet, f"Wallet missing field: {field}"
        
        print(f"✓ WETH movers 7d: {len(entities)} entities, {len(wallets)} wallets")

    def test_movers_wallets_sorted_by_abs_net(self):
        """D4: Verify topWallets sorted by abs(netUsd) descending"""
        url = f"{BASE_URL}{API_PREFIX}/movers?chainId=1&token=WETH&window=7d"
        resp = requests.get(url, timeout=30)
        
        assert resp.status_code == 200
        data = resp.json()
        
        wallets = data.get('topWallets', [])
        if len(wallets) >= 2:
            # Verify sorting by abs(netUsd) descending
            for i in range(len(wallets) - 1):
                current_abs = abs(wallets[i].get('netUsd', 0))
                next_abs = abs(wallets[i + 1].get('netUsd', 0))
                assert current_abs >= next_abs, f"Wallets not sorted: {current_abs} < {next_abs}"
            print(f"✓ Wallets correctly sorted by abs(netUsd) descending")
        else:
            print(f"⚠ Only {len(wallets)} wallets - can't verify sorting")

    def test_movers_missing_token(self):
        """D4: Movers without token returns error"""
        url = f"{BASE_URL}{API_PREFIX}/movers?chainId=1&window=7d"
        resp = requests.get(url, timeout=30)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('ok') == False
        assert data.get('reason') == 'MISSING_TOKEN'
        print("✓ Missing token returns MISSING_TOKEN error")

    def test_movers_nonexistent_token(self):
        """D4: Movers for nonexistent token returns ok:false"""
        url = f"{BASE_URL}{API_PREFIX}/movers?chainId=1&token=NONEXISTENT_TOKEN_XYZ&window=7d"
        resp = requests.get(url, timeout=30)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('ok') == False
        assert 'reason' in data
        print(f"✓ Nonexistent token returns ok:false, reason={data.get('reason')}")


class TestTokenEndpointsCrossValidation:
    """Cross-validation tests across D1-D4 endpoints"""

    def test_resolve_then_profile(self):
        """Resolve UNI then get profile with resolved address"""
        # Step 1: Resolve
        resolve_url = f"{BASE_URL}{API_PREFIX}/resolve?chainId=1&q=UNI"
        resolve_resp = requests.get(resolve_url, timeout=30)
        resolve_data = resolve_resp.json()
        
        assert resolve_data.get('ok') == True
        token = resolve_data.get('token')
        address = token.get('address')
        
        # Step 2: Profile by address
        profile_url = f"{BASE_URL}{API_PREFIX}/profile?chainId=1&token={address}"
        profile_resp = requests.get(profile_url, timeout=30)
        profile_data = profile_resp.json()
        
        assert profile_data.get('ok') == True
        assert profile_data.get('symbol', '').upper() == 'UNI'
        print(f"✓ Resolve → Profile flow works for UNI")

    def test_weth_full_deep_dive_flow(self):
        """Simulate full TokenDeepView data fetch flow for WETH"""
        token = 'WETH'
        window = '7d'
        
        # Profile
        profile_url = f"{BASE_URL}{API_PREFIX}/profile?chainId=1&token={token}&window={window}"
        profile_resp = requests.get(profile_url, timeout=30)
        assert profile_resp.status_code == 200
        profile_data = profile_resp.json()
        assert profile_data.get('ok') == True
        
        # Series
        series_url = f"{BASE_URL}{API_PREFIX}/series?chainId=1&token={token}&window={window}"
        series_resp = requests.get(series_url, timeout=30)
        assert series_resp.status_code == 200
        series_data = series_resp.json()
        assert series_data.get('ok') == True
        
        # Movers
        movers_url = f"{BASE_URL}{API_PREFIX}/movers?chainId=1&token={token}&window={window}"
        movers_resp = requests.get(movers_url, timeout=30)
        assert movers_resp.status_code == 200
        movers_data = movers_resp.json()
        assert movers_data.get('ok') == True
        
        print(f"✓ Full WETH deep dive flow works: profile ok, "
              f"{len(series_data.get('buckets', []))} series buckets, "
              f"{len(movers_data.get('topEntities', []))} entities, "
              f"{len(movers_data.get('topWallets', []))} wallets")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
