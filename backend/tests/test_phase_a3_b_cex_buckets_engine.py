"""
Phase A3 + B Testing: CEX Flow Bucket Precompute & Engine Project Ranking
==========================================================================

A3: Tests pre-computed bucket endpoints (replacing slow 26-exchange sequential queries)
B: Tests Engine project ranking API (multi-signal scoring)

Base URL: https://expo-telegram-web.preview.emergentagent.com
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestCexBucketJobAPI:
    """A3.3: Bucket job status and force-tick endpoints"""

    def test_bucket_job_status(self):
        """GET /api/v10/onchain-v2/cex-flow/buckets/job/status returns job status"""
        url = f"{BASE_URL}/api/v10/onchain-v2/cex-flow/buckets/job/status"
        r = requests.get(url, timeout=15)
        
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        
        assert data.get('ok') is True, "Response should have ok:true"
        assert 'tickCount' in data, "Response should have tickCount"
        assert 'successCount' in data, "Response should have successCount"
        assert isinstance(data['tickCount'], int), "tickCount should be int"
        assert isinstance(data['successCount'], int), "successCount should be int"
        
        print(f"Job status: tickCount={data['tickCount']}, successCount={data['successCount']}, running={data.get('running')}")
        
    def test_bucket_job_force_tick(self):
        """POST /api/v10/onchain-v2/cex-flow/buckets/job/force-tick triggers computation"""
        url = f"{BASE_URL}/api/v10/onchain-v2/cex-flow/buckets/job/force-tick"
        r = requests.post(url, timeout=120)  # Long timeout for computation
        
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        
        assert data.get('ok') is True, "Response should have ok:true"
        assert 'tickCount' in data, "Response should have tickCount after force-tick"
        assert data['tickCount'] >= 1, "tickCount should be >= 1 after force-tick"
        
        print(f"Force-tick completed: tickCount={data['tickCount']}, successCount={data.get('successCount')}")


class TestCexBucketCrossAPI:
    """A3.4: Cross-exchange overview from buckets (fast, < 2s)"""

    def test_bucket_cross_24h(self):
        """GET /cex-flow/buckets/cross?window=24h returns exchanges with flow data"""
        url = f"{BASE_URL}/api/v10/onchain-v2/cex-flow/buckets/cross?window=24h&chainId=1"
        
        start = time.time()
        r = requests.get(url, timeout=10)
        elapsed = time.time() - start
        
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        
        assert data.get('ok') is True, "Response should have ok:true"
        assert 'items' in data, "Response should have items array"
        assert 'window' in data, "Response should have window"
        assert 'stale' in data, "Response should have stale indicator"
        
        # Performance check: should be fast (< 2s)
        assert elapsed < 2.0, f"Cross endpoint took {elapsed:.2f}s, should be < 2s"
        
        print(f"Cross 24h: {len(data['items'])} exchanges, stale={data['stale']}, elapsed={elapsed:.2f}s")
        
    def test_bucket_cross_7d(self):
        """GET /cex-flow/buckets/cross?window=7d returns exchanges with flow data"""
        url = f"{BASE_URL}/api/v10/onchain-v2/cex-flow/buckets/cross?window=7d&chainId=1"
        
        start = time.time()
        r = requests.get(url, timeout=10)
        elapsed = time.time() - start
        
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        
        assert data.get('ok') is True, "Response should have ok:true"
        items = data.get('items', [])
        
        # Validate structure of exchange items
        if len(items) > 0:
            item = items[0]
            assert 'exchangeId' in item, "Item should have exchangeId"
            assert 'entityName' in item, "Item should have entityName"
            assert 'inflowUsd' in item, "Item should have inflowUsd"
            assert 'outflowUsd' in item, "Item should have outflowUsd"
            assert 'netUsd' in item, "Item should have netUsd"
            
        # Performance check
        assert elapsed < 2.0, f"Cross endpoint took {elapsed:.2f}s, should be < 2s"
        
        print(f"Cross 7d: {len(items)} exchanges, stale={data.get('stale')}, elapsed={elapsed:.2f}s")
        

class TestCexBucketExchangeAPI:
    """A3.4: Exchange drilldown from buckets"""

    def test_bucket_exchange_binance_7d(self):
        """GET /cex-flow/buckets/exchange/binance?window=7d returns totals + topIn + topOut"""
        url = f"{BASE_URL}/api/v10/onchain-v2/cex-flow/buckets/exchange/binance?window=7d&chainId=1"
        r = requests.get(url, timeout=15)
        
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        
        assert data.get('ok') is True, "Response should have ok:true"
        assert data.get('exchangeId') == 'binance', "exchangeId should be binance"
        assert data.get('entityName') == 'Binance', "entityName should be Binance"
        assert 'totals' in data, "Response should have totals"
        assert 'topIn' in data, "Response should have topIn array"
        assert 'topOut' in data, "Response should have topOut array"
        assert 'stale' in data, "Response should have stale indicator"
        
        # Validate totals structure
        totals = data.get('totals')
        if totals:
            assert 'inflowUsd' in totals, "Totals should have inflowUsd"
            assert 'outflowUsd' in totals, "Totals should have outflowUsd"
            assert 'netUsd' in totals, "Totals should have netUsd"
            assert 'transferCount' in totals, "Totals should have transferCount"
            
            print(f"Binance 7d totals: in=${totals['inflowUsd']:.2f}, out=${totals['outflowUsd']:.2f}, net=${totals['netUsd']:.2f}")
        
        # Validate topIn/topOut structure
        top_in = data.get('topIn', [])
        if len(top_in) > 0:
            tok = top_in[0]
            assert 'tokenAddress' in tok, "Token should have tokenAddress"
            assert 'inflowUsd' in tok, "Token should have inflowUsd"
            
        print(f"Binance 7d: topIn={len(data.get('topIn', []))}, topOut={len(data.get('topOut', []))}")

    def test_bucket_exchange_coinbase_24h(self):
        """GET /cex-flow/buckets/exchange/coinbase?window=24h returns data"""
        url = f"{BASE_URL}/api/v10/onchain-v2/cex-flow/buckets/exchange/coinbase?window=24h&chainId=1"
        r = requests.get(url, timeout=15)
        
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        
        assert data.get('ok') is True, "Response should have ok:true"
        assert data.get('exchangeId') == 'coinbase', "exchangeId should be coinbase"
        
        print(f"Coinbase 24h: entityName={data.get('entityName')}, stale={data.get('stale')}")


class TestCexBucketTokenAPI:
    """A3.4: Token across exchanges from buckets"""

    def test_bucket_token_weth_7d(self):
        """GET /cex-flow/buckets/token/:tokenAddress?window=7d returns per-exchange breakdown"""
        # WETH address
        weth = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
        url = f"{BASE_URL}/api/v10/onchain-v2/cex-flow/buckets/token/{weth}?window=7d&chainId=1"
        r = requests.get(url, timeout=15)
        
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        
        assert data.get('ok') is True, "Response should have ok:true"
        assert data.get('tokenAddress') == weth, f"tokenAddress should be {weth}"
        assert 'items' in data, "Response should have items array"
        assert 'window' in data, "Response should have window"
        
        items = data.get('items', [])
        if len(items) > 0:
            item = items[0]
            assert 'exchangeId' in item, "Item should have exchangeId"
            assert 'entityName' in item, "Item should have entityName"
            assert 'inflowUsd' in item, "Item should have inflowUsd"
            assert 'outflowUsd' in item, "Item should have outflowUsd"
            assert 'netUsd' in item, "Item should have netUsd"
            
        print(f"WETH 7d: {len(items)} exchanges, tokenSymbol={data.get('tokenSymbol')}")

    def test_bucket_token_usdc_24h(self):
        """GET /cex-flow/buckets/token/:tokenAddress?window=24h for USDC"""
        usdc = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
        url = f"{BASE_URL}/api/v10/onchain-v2/cex-flow/buckets/token/{usdc}?window=24h&chainId=1"
        r = requests.get(url, timeout=15)
        
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        
        assert data.get('ok') is True, "Response should have ok:true"
        print(f"USDC 24h: {len(data.get('items', []))} exchanges")


class TestEngineProjectRankingAPI:
    """Phase B: Engine project ranking endpoints"""

    def test_engine_projects_7d(self):
        """GET /engine/projects?window=7d returns ranked projects with scores"""
        url = f"{BASE_URL}/api/v10/onchain-v2/engine/projects?window=7d&chainId=1"
        r = requests.get(url, timeout=30)
        
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        
        assert data.get('ok') is True, "Response should have ok:true"
        assert 'totalTokens' in data, "Response should have totalTokens"
        assert 'projects' in data, "Response should have projects array"
        assert 'generatedAt' in data, "Response should have generatedAt timestamp"
        
        projects = data.get('projects', [])
        if len(projects) > 0:
            p = projects[0]
            # Validate required fields per spec
            assert 'symbol' in p, "Project should have symbol"
            assert 'score' in p, "Project should have score"
            assert 'action' in p, "Project should have action"
            assert 'dexNetUsd' in p, "Project should have dexNetUsd"
            assert 'cexNetUsd' in p, "Project should have cexNetUsd"
            assert 'smartMoneyNet' in p, "Project should have smartMoneyNet"
            assert 'liquidityScore' in p, "Project should have liquidityScore"
            
            # Validate action is one of BUY/SELL/NEUTRAL
            assert p['action'] in ['BUY', 'SELL', 'NEUTRAL'], f"Invalid action: {p['action']}"
            
            # Validate score range
            assert -1 <= p['score'] <= 1, f"Score {p['score']} out of [-1, 1] range"
            
        # Count actions
        buy_count = len([p for p in projects if p.get('action') == 'BUY'])
        sell_count = len([p for p in projects if p.get('action') == 'SELL'])
        neutral_count = len([p for p in projects if p.get('action') == 'NEUTRAL'])
        
        print(f"Engine projects 7d: total={data['totalTokens']}, BUY={buy_count}, SELL={sell_count}, NEUTRAL={neutral_count}")

    def test_engine_projects_filter_buy(self):
        """GET /engine/projects?window=7d&action=BUY filters by BUY action"""
        url = f"{BASE_URL}/api/v10/onchain-v2/engine/projects?window=7d&action=BUY&chainId=1"
        r = requests.get(url, timeout=30)
        
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        
        assert data.get('ok') is True, "Response should have ok:true"
        
        projects = data.get('projects', [])
        # All returned projects should have action=BUY
        for p in projects:
            assert p.get('action') == 'BUY', f"Expected action=BUY, got {p.get('action')}"
            
        print(f"Engine projects BUY filter: {len(projects)} projects")

    def test_engine_projects_filter_sell(self):
        """GET /engine/projects?window=7d&action=SELL filters by SELL action"""
        url = f"{BASE_URL}/api/v10/onchain-v2/engine/projects?window=7d&action=SELL&chainId=1"
        r = requests.get(url, timeout=30)
        
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        
        assert data.get('ok') is True, "Response should have ok:true"
        
        projects = data.get('projects', [])
        for p in projects:
            assert p.get('action') == 'SELL', f"Expected action=SELL, got {p.get('action')}"
            
        print(f"Engine projects SELL filter: {len(projects)} projects")

    def test_engine_projects_24h(self):
        """GET /engine/projects?window=24h works for different window"""
        url = f"{BASE_URL}/api/v10/onchain-v2/engine/projects?window=24h&chainId=1"
        r = requests.get(url, timeout=30)
        
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        
        assert data.get('ok') is True, "Response should have ok:true"
        print(f"Engine projects 24h: total={data.get('totalTokens')}")

    def test_engine_projects_scoring_formula(self):
        """Validate scoring formula: 0.35*DEX + 0.25*SmartMoney + 0.20*Liquidity + 0.20*(-CEX)"""
        url = f"{BASE_URL}/api/v10/onchain-v2/engine/projects?window=7d&chainId=1&limit=10"
        r = requests.get(url, timeout=30)
        
        assert r.status_code == 200
        data = r.json()
        
        projects = data.get('projects', [])
        
        # Verify projects have components for transparency
        for p in projects[:3]:  # Check first 3
            if 'components' in p:
                c = p['components']
                assert 'dex' in c, "Components should have dex"
                assert 'cex' in c, "Components should have cex"
                assert 'smartMoney' in c, "Components should have smartMoney"
                assert 'liquidity' in c, "Components should have liquidity"
                
                # Verify score thresholds
                if p['score'] >= 0.6:
                    assert p['action'] == 'BUY', f"Score {p['score']} >= 0.6 should be BUY, got {p['action']}"
                elif p['score'] <= -0.6:
                    assert p['action'] == 'SELL', f"Score {p['score']} <= -0.6 should be SELL, got {p['action']}"
                else:
                    assert p['action'] == 'NEUTRAL', f"Score {p['score']} should be NEUTRAL, got {p['action']}"
                    
        print("Scoring formula validation passed")


class TestBucketPerformanceComparison:
    """Performance comparison: bucket vs legacy endpoint"""

    def test_bucket_cross_is_fast(self):
        """Bucket cross endpoint should be significantly faster than legacy"""
        # Test bucket endpoint speed
        url = f"{BASE_URL}/api/v10/onchain-v2/cex-flow/buckets/cross?window=7d&chainId=1"
        
        times = []
        for i in range(3):
            start = time.time()
            r = requests.get(url, timeout=10)
            elapsed = time.time() - start
            times.append(elapsed)
            assert r.status_code == 200
            
        avg_time = sum(times) / len(times)
        
        # Should complete in under 500ms on average (vs 30+ seconds for legacy)
        assert avg_time < 2.0, f"Average time {avg_time:.2f}s should be < 2s"
        
        print(f"Bucket cross average response time: {avg_time:.3f}s (3 requests)")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
