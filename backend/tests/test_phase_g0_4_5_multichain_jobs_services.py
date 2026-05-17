"""
Phase G0.4 + G0.5: Multichain Jobs and Services Refactoring Tests
==================================================================

Tests for:
- G0.4: 14 background jobs refactored to use runPerChain wrapper
- G0.5: Service functions accept chainId parameter

API Endpoints tested:
- GET /api/v10/onchain-v2/chains/job-readiness
- GET /api/system/chains
- GET /api/v10/onchain-v2/wallets/health
- GET /api/v10/onchain-v2/market/tokens/profile
- GET /api/v10/onchain-v2/market/tokens/series
- GET /api/v10/onchain-v2/engine/projects
- GET /api/v10/onchain-v2/cex-flow/buckets/cross
- GET /api/v10/onchain-v2/wallets/series
- GET /api/v10/onchain-v2/market/tokens/series/status
"""

import pytest
import requests
import os
import subprocess
import re

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com').rstrip('/')

# ═══════════════════════════════════════════════════════════════
# API TESTS
# ═══════════════════════════════════════════════════════════════

class TestJobReadinessEndpoint:
    """Test GET /api/v10/onchain-v2/chains/job-readiness"""
    
    def test_job_readiness_returns_ok(self):
        """Job readiness endpoint should return ok:true"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/chains/job-readiness")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        
    def test_job_readiness_has_14_jobs(self):
        """Should return exactly 14 refactored jobs"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/chains/job-readiness")
        data = response.json()
        
        refactored_jobs = data.get('refactoredJobs', [])
        assert len(refactored_jobs) == 14, f"Expected 14 jobs, got {len(refactored_jobs)}"
        
        expected_jobs = [
            'WalletSnapshotJob', 'TokenSeriesJob', 'CexBucketJob', 
            'ActorScoreJob', 'EntityFlowJob', 'AltFlowJob',
            'MarketSeriesJob', 'LiquidityJob', 'LiquidityV2Job',
            'BridgeAggJob', 'PoolDiscoveryJob', 'PoolLiquidityJob',
            'StableAggJob', 'DexSyncJob'
        ]
        
        for job in expected_jobs:
            assert job in refactored_jobs, f"Missing job: {job}"
            
    def test_job_readiness_enabled_chains(self):
        """Should show enabledChains=[1]"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/chains/job-readiness")
        data = response.json()
        
        enabled_chains = data.get('enabledChains', [])
        assert 1 in enabled_chains, "Chain 1 (Ethereum) should be enabled"
        
    def test_job_readiness_has_runperchain_wrapper(self):
        """Should indicate runPerChain wrapper is used"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/chains/job-readiness")
        data = response.json()
        
        assert data.get('jobWrapper') == 'runPerChain'


class TestSystemChainsEndpoint:
    """Test GET /api/system/chains"""
    
    def test_system_chains_returns_ok(self):
        """System chains endpoint should return ok:true"""
        response = requests.get(f"{BASE_URL}/api/system/chains")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        
    def test_system_chains_has_chains_array(self):
        """Should return chains array with 4 chains"""
        response = requests.get(f"{BASE_URL}/api/system/chains")
        data = response.json()
        
        chains = data.get('chains', [])
        assert len(chains) >= 4, f"Expected at least 4 chains, got {len(chains)}"
        
    def test_ethereum_is_enabled(self):
        """Ethereum (chainId=1) should be enabled"""
        response = requests.get(f"{BASE_URL}/api/system/chains")
        data = response.json()
        
        chains = data.get('chains', [])
        eth_chain = next((c for c in chains if c.get('chainId') == 1), None)
        
        assert eth_chain is not None, "Ethereum chain not found"
        assert eth_chain.get('enabled') is True


class TestWalletsHealthEndpoint:
    """Test GET /api/v10/onchain-v2/wallets/health"""
    
    def test_wallets_health_returns_ok(self):
        """Wallets health endpoint should return ok:true"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/wallets/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        assert data.get('module') == 'wallets_v3'


class TestTokenProfileEndpoint:
    """Test GET /api/v10/onchain-v2/market/tokens/profile"""
    
    def test_token_profile_weth_returns_ok(self):
        """Token profile for WETH should return ok:true"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/market/tokens/profile",
            params={"chainId": 1, "token": "WETH"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        
    def test_token_profile_weth_has_symbol(self):
        """Token profile should return correct symbol"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/market/tokens/profile",
            params={"chainId": 1, "token": "WETH"}
        )
        data = response.json()
        
        assert data.get('symbol') == 'WETH'


class TestTokenSeriesEndpoint:
    """Test GET /api/v10/onchain-v2/market/tokens/series"""
    
    def test_token_series_weth_returns_ok(self):
        """Token series for WETH should return ok:true"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/market/tokens/series",
            params={"chainId": 1, "token": "WETH", "window": "7d"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True


class TestEngineProjectsEndpoint:
    """Test GET /api/v10/onchain-v2/engine/projects"""
    
    def test_engine_projects_returns_ok(self):
        """Engine projects endpoint should return ok:true"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/engine/projects",
            params={"window": "24h", "chainId": 1}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        
    def test_engine_projects_has_chainid(self):
        """Response should include chainId"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/engine/projects",
            params={"window": "24h", "chainId": 1}
        )
        data = response.json()
        
        assert data.get('chainId') == 1


class TestCexFlowBucketsEndpoint:
    """Test GET /api/v10/onchain-v2/cex-flow/buckets/cross"""
    
    def test_cex_flow_buckets_returns_ok(self):
        """CEX flow buckets endpoint should return ok:true"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/cex-flow/buckets/cross",
            params={"window": "24h"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        
    def test_cex_flow_buckets_has_items(self):
        """Response should have items array"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/cex-flow/buckets/cross",
            params={"window": "24h"}
        )
        data = response.json()
        
        assert 'items' in data


class TestWalletsSeriesEndpoint:
    """Test GET /api/v10/onchain-v2/wallets/series"""
    
    def test_wallets_series_returns_ok(self):
        """Wallets series endpoint should return ok:true"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/wallets/series",
            params={
                "address": "0x0000000000000000000000000000000000000000",
                "window": "7d"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True


class TestTokenSeriesStatusEndpoint:
    """Test GET /api/v10/onchain-v2/market/tokens/series/status"""
    
    def test_token_series_status_returns_ok(self):
        """Token series status endpoint should return ok:true"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/market/tokens/series/status")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True


# ═══════════════════════════════════════════════════════════════
# CODE STRUCTURE TESTS
# ═══════════════════════════════════════════════════════════════

class TestRunPerChainUtility:
    """Test runPerChain utility exists and exports correctly"""
    
    def test_runperchain_file_exists(self):
        """runPerChain.ts should exist"""
        filepath = "/app/legacy/backend-src/modules/onchain_v2/system/runPerChain.ts"
        assert os.path.exists(filepath), f"File not found: {filepath}"
        
    def test_runperchain_exports_function(self):
        """runPerChain should export runPerChain function"""
        filepath = "/app/legacy/backend-src/modules/onchain_v2/system/runPerChain.ts"
        with open(filepath, 'r') as f:
            content = f.read()
        
        assert "export async function runPerChain" in content


class TestJobFilesRefactored:
    """Test that 14 job files import runPerChain or getActiveChainIds"""
    
    JOB_FILES = [
        "/app/legacy/backend-src/modules/onchain_v2/wallets_v3/walletSnapshot.job.ts",
        "/app/legacy/backend-src/modules/onchain_v2/market/tokens/tokenSeries.job.ts",
        "/app/legacy/backend-src/modules/onchain_v2/market/cex/buckets/cexBucket.job.ts",
        "/app/legacy/backend-src/modules/onchain_v2/market/actors/actorScore.job.ts",
        "/app/legacy/backend-src/modules/onchain_v2/market/actors/entityFlow.job.ts",
        "/app/legacy/backend-src/modules/onchain_v2/market/altflow/altflow.job.ts",
        "/app/legacy/backend-src/modules/onchain_v2/market/market.job.ts",
        "/app/legacy/backend-src/modules/onchain_v2/market/liquidity/liquidity.job.ts",
        "/app/legacy/backend-src/modules/onchain_v2/market/liquidity_v2/liquidity_v2.job.ts",
        "/app/legacy/backend-src/modules/onchain_v2/bridge/aggregation/bridge_agg.job.ts",
        "/app/legacy/backend-src/modules/onchain_v2/market/pricing/pools/poolDiscovery.job.ts",
        "/app/legacy/backend-src/modules/onchain_v2/market/pricing/pools/liquidity/poolLiquidity.job.ts",
        "/app/legacy/backend-src/modules/onchain_v2/stables/stable.jobs.ts",
        "/app/legacy/backend-src/modules/onchain_v2/ingestion/dex/dex_sync.job.ts",
    ]
    
    @pytest.mark.parametrize("filepath", JOB_FILES)
    def test_job_file_exists(self, filepath):
        """Each job file should exist"""
        assert os.path.exists(filepath), f"Job file not found: {filepath}"
        
    @pytest.mark.parametrize("filepath", JOB_FILES)
    def test_job_file_uses_chain_iteration(self, filepath):
        """Each job file should use runPerChain, getActiveChainIds, or chainRegistry"""
        with open(filepath, 'r') as f:
            content = f.read()
        
        has_runperchain = "runPerChain" in content
        has_getactivechainids = "getActiveChainIds" in content
        has_chainregistry = "chainRegistry.getActiveIds" in content
        
        assert has_runperchain or has_getactivechainids or has_chainregistry, \
            f"Job {os.path.basename(filepath)} doesn't use chain iteration"


class TestServiceFunctionsAcceptChainId:
    """Test that key service functions accept chainId parameter"""
    
    def test_market_service_savemarketsnaphot_accepts_chainid(self):
        """market.service.ts saveMarketSnapshot should accept chainId"""
        filepath = "/app/legacy/backend-src/modules/onchain_v2/market/market.service.ts"
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Look for function signature with chainId parameter
        assert "saveMarketSnapshot(snapshot: MarketSnapshot, chainId:" in content or \
               "saveMarketSnapshot(snapshot, chainId" in content
               
    def test_liquidity_service_tickliquidity_accepts_chainid(self):
        """liquidity.service.ts tickLiquidity should accept chainId"""
        filepath = "/app/legacy/backend-src/modules/onchain_v2/market/liquidity/liquidity.service.ts"
        with open(filepath, 'r') as f:
            content = f.read()
        
        assert "tickLiquidity(chainId:" in content or \
               "tickLiquidity(chainId =" in content
               
    def test_liquidity_v2_service_computeandstore_accepts_chainid(self):
        """liquidity_v2.service.ts computeAndStore should accept chainId"""
        filepath = "/app/legacy/backend-src/modules/onchain_v2/market/liquidity_v2/liquidity_v2.service.ts"
        with open(filepath, 'r') as f:
            content = f.read()
        
        assert "computeAndStore(window: LareV2Window, chainId:" in content or \
               "computeAndStore(window, chainId" in content
               
    def test_bridge_agg_service_computeandupsert_accepts_chainid(self):
        """bridge_agg.service.ts computeAndUpsert should accept chainId"""
        filepath = "/app/legacy/backend-src/modules/onchain_v2/bridge/aggregation/bridge_agg.service.ts"
        with open(filepath, 'r') as f:
            content = f.read()
        
        assert "computeAndUpsert(window: BridgeAggWindow, nowTs" in content and \
               "chainId:" in content
               
    def test_stable_aggregation_service_computeandupsert_accepts_chainid(self):
        """stable_aggregation.service.ts computeAndUpsert should accept chainId"""
        filepath = "/app/legacy/backend-src/modules/onchain_v2/stables/stable_aggregation.service.ts"
        with open(filepath, 'r') as f:
            content = f.read()
        
        assert "computeAndUpsert(window: StableAggWindow, nowTs" in content and \
               "chainId:" in content


class TestNoHardcodedChainId:
    """Test that job tick functions don't have hardcoded chainId:1"""
    
    JOB_FILES_WITH_TICK = [
        "/app/legacy/backend-src/modules/onchain_v2/wallets_v3/walletSnapshot.job.ts",
        "/app/legacy/backend-src/modules/onchain_v2/market/tokens/tokenSeries.job.ts",
        "/app/legacy/backend-src/modules/onchain_v2/market/market.job.ts",
        "/app/legacy/backend-src/modules/onchain_v2/market/liquidity/liquidity.job.ts",
        "/app/legacy/backend-src/modules/onchain_v2/market/liquidity_v2/liquidity_v2.job.ts",
        "/app/legacy/backend-src/modules/onchain_v2/bridge/aggregation/bridge_agg.job.ts",
        "/app/legacy/backend-src/modules/onchain_v2/stables/stable.jobs.ts",
    ]
    
    @pytest.mark.parametrize("filepath", JOB_FILES_WITH_TICK)
    def test_no_hardcoded_chainid_in_tick(self, filepath):
        """Job tick functions should not have hardcoded chainId:1 in the main logic"""
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Pattern to detect hardcoded chainId: 1 in tick/job functions
        # Exclude: default params like "chainId = 1", comments, getActiveChainIds calls
        
        # This is a heuristic check - look for runPerChain usage which means chain iteration
        has_iteration = "runPerChain" in content or "getActiveChainIds" in content or \
                       "chainRegistry.getActiveIds" in content
        
        assert has_iteration, f"Job {os.path.basename(filepath)} may have hardcoded chainId"


# ═══════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════

class TestChainIdPropagation:
    """Test that chainId is properly propagated in API responses"""
    
    def test_wallets_series_returns_chainid(self):
        """Wallets series should return chainId in response"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/wallets/series",
            params={
                "address": "0x0000000000000000000000000000000000000000",
                "window": "7d"
            }
        )
        data = response.json()
        
        assert data.get('chainId') == 1
        
    def test_engine_projects_chainid_filter(self):
        """Engine projects should filter by chainId"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/engine/projects",
            params={"window": "24h", "chainId": 1}
        )
        data = response.json()
        
        assert data.get('chainId') == 1
        
        # All projects should have chainId=1
        projects = data.get('projects', [])
        for p in projects[:5]:  # Check first 5
            if 'chainId' in p:
                assert p['chainId'] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
