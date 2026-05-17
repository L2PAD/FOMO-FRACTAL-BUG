"""
Phase G0.7 + G1.0 Multichain UI Network Selector Tests
=======================================================

Tests for:
- UI Network Selector visible but disabled in header
- ARB in chain registry but disabled
- Feature flags added
- All API endpoints return correct chain data
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestSystemChainsEndpoint:
    """GET /api/system/chains — should return 4 chains with ETH enabled and ARB/OP/BASE disabled"""
    
    def test_chains_endpoint_returns_ok(self):
        """Test that /api/system/chains returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/system/chains")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        print(f"✓ /api/system/chains returns ok:true")
    
    def test_chains_returns_4_chains(self):
        """Test that exactly 4 chains are returned"""
        response = requests.get(f"{BASE_URL}/api/system/chains")
        data = response.json()
        chains = data.get('chains', [])
        assert len(chains) == 4, f"Expected 4 chains, got {len(chains)}"
        print(f"✓ Returns exactly 4 chains")
    
    def test_ethereum_chain_enabled(self):
        """Test that Ethereum (chainId=1) is enabled"""
        response = requests.get(f"{BASE_URL}/api/system/chains")
        data = response.json()
        chains = {c['chainId']: c for c in data.get('chains', [])}
        
        eth_chain = chains.get(1)
        assert eth_chain is not None, "Ethereum chain (chainId=1) not found"
        assert eth_chain.get('enabled') == True, "Ethereum should be enabled"
        assert eth_chain.get('key') == 'eth'
        assert eth_chain.get('name') == 'Ethereum'
        print(f"✓ Ethereum (chainId=1) is enabled")
    
    def test_arbitrum_chain_disabled(self):
        """Test that Arbitrum (chainId=42161) exists but is disabled"""
        response = requests.get(f"{BASE_URL}/api/system/chains")
        data = response.json()
        chains = {c['chainId']: c for c in data.get('chains', [])}
        
        arb_chain = chains.get(42161)
        assert arb_chain is not None, "Arbitrum chain (chainId=42161) not found"
        assert arb_chain.get('enabled') == False, "Arbitrum should be disabled"
        assert arb_chain.get('key') == 'arb'
        assert arb_chain.get('name') == 'Arbitrum'
        print(f"✓ Arbitrum (chainId=42161) exists but is disabled")
    
    def test_optimism_chain_disabled(self):
        """Test that Optimism (chainId=10) exists but is disabled"""
        response = requests.get(f"{BASE_URL}/api/system/chains")
        data = response.json()
        chains = {c['chainId']: c for c in data.get('chains', [])}
        
        op_chain = chains.get(10)
        assert op_chain is not None, "Optimism chain (chainId=10) not found"
        assert op_chain.get('enabled') == False, "Optimism should be disabled"
        assert op_chain.get('key') == 'op'
        assert op_chain.get('name') == 'Optimism'
        print(f"✓ Optimism (chainId=10) exists but is disabled")
    
    def test_base_chain_disabled(self):
        """Test that Base (chainId=8453) exists but is disabled"""
        response = requests.get(f"{BASE_URL}/api/system/chains")
        data = response.json()
        chains = {c['chainId']: c for c in data.get('chains', [])}
        
        base_chain = chains.get(8453)
        assert base_chain is not None, "Base chain (chainId=8453) not found"
        assert base_chain.get('enabled') == False, "Base should be disabled"
        assert base_chain.get('key') == 'base'
        assert base_chain.get('name') == 'Base'
        print(f"✓ Base (chainId=8453) exists but is disabled")


class TestJobReadinessEndpoint:
    """GET /api/v10/onchain-v2/chains/job-readiness — check enabledChains, availableChains, featureFlags"""
    
    def test_job_readiness_returns_ok(self):
        """Test that job-readiness endpoint returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/chains/job-readiness")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        print(f"✓ /api/v10/onchain-v2/chains/job-readiness returns ok:true")
    
    def test_enabled_chains_only_ethereum(self):
        """Test that enabledChains contains only Ethereum (chainId=1)"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/chains/job-readiness")
        data = response.json()
        
        enabled_chains = data.get('enabledChains', [])
        assert enabled_chains == [1], f"Expected enabledChains=[1], got {enabled_chains}"
        print(f"✓ enabledChains=[1] (Ethereum only)")
    
    def test_available_chains_all_four(self):
        """Test that availableChains contains all 4 chain IDs"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/chains/job-readiness")
        data = response.json()
        
        available_chains = set(data.get('availableChains', []))
        expected = {1, 42161, 10, 8453}
        assert available_chains == expected, f"Expected availableChains={expected}, got {available_chains}"
        print(f"✓ availableChains=[1, 42161, 10, 8453] (all 4 chains)")
    
    def test_feature_flags_all_false(self):
        """Test that all feature flags are false"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/chains/job-readiness")
        data = response.json()
        
        feature_flags = data.get('featureFlags', {})
        assert feature_flags.get('MULTICHAIN_ENABLED') == False, "MULTICHAIN_ENABLED should be false"
        assert feature_flags.get('ENABLE_ARB_INGESTION') == False, "ENABLE_ARB_INGESTION should be false"
        assert feature_flags.get('ENABLE_ARB_ALTFLOW') == False, "ENABLE_ARB_ALTFLOW should be false"
        assert feature_flags.get('ENABLE_ARB_ENGINE') == False, "ENABLE_ARB_ENGINE should be false"
        print(f"✓ All feature flags are false: {feature_flags}")


class TestWalletsHealthEndpoint:
    """GET /api/v10/onchain-v2/wallets/health — check ok:true"""
    
    def test_wallets_health_returns_ok(self):
        """Test that wallets health endpoint returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/wallets/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        assert data.get('module') == 'wallets_v3'
        print(f"✓ /api/v10/onchain-v2/wallets/health returns ok:true, module:wallets_v3")


class TestEngineProjectsEndpoint:
    """GET /api/v10/onchain-v2/engine/projects — check ok:true with projects"""
    
    def test_engine_projects_returns_ok(self):
        """Test that engine projects endpoint returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/engine/projects?window=24h&chainId=1")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        print(f"✓ /api/v10/onchain-v2/engine/projects returns ok:true")
    
    def test_engine_projects_returns_chainid_1(self):
        """Test that engine projects returns chainId=1"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/engine/projects?window=24h&chainId=1")
        data = response.json()
        assert data.get('chainId') == 1, f"Expected chainId=1, got {data.get('chainId')}"
        print(f"✓ Engine projects returns chainId=1")
    
    def test_engine_projects_has_projects_array(self):
        """Test that engine projects returns projects array"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/engine/projects?window=24h&chainId=1")
        data = response.json()
        projects = data.get('projects')
        assert isinstance(projects, list), "Expected projects to be a list"
        print(f"✓ Engine projects returns projects array with {len(projects)} items")


class TestMarketTokensProfileEndpoint:
    """GET /api/v10/onchain-v2/market/tokens/profile — check ok:true"""
    
    def test_tokens_profile_returns_ok(self):
        """Test that tokens profile endpoint returns ok:true for WETH"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/market/tokens/profile?chainId=1&token=WETH")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        print(f"✓ /api/v10/onchain-v2/market/tokens/profile returns ok:true")
    
    def test_tokens_profile_returns_weth_data(self):
        """Test that tokens profile returns WETH data"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/market/tokens/profile?chainId=1&token=WETH")
        data = response.json()
        
        assert data.get('symbol') == 'WETH', f"Expected symbol=WETH, got {data.get('symbol')}"
        assert 'address' in data, "Expected address field in response"
        assert 'decimals' in data, "Expected decimals field in response"
        print(f"✓ Token profile returns WETH data: symbol={data.get('symbol')}, decimals={data.get('decimals')}")


class TestChainDataIntegrity:
    """Cross-validate chain data across multiple endpoints"""
    
    def test_chain_count_consistency(self):
        """Test that chain counts are consistent across endpoints"""
        # Get chains from /api/system/chains
        system_response = requests.get(f"{BASE_URL}/api/system/chains")
        system_chains = system_response.json().get('chains', [])
        
        # Get chains from /api/v10/onchain-v2/chains/job-readiness
        job_response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/chains/job-readiness")
        job_data = job_response.json()
        available_chains = job_data.get('availableChains', [])
        
        assert len(system_chains) == len(available_chains), \
            f"Chain count mismatch: system={len(system_chains)}, job-readiness={len(available_chains)}"
        print(f"✓ Chain count consistent: {len(system_chains)} chains in both endpoints")
    
    def test_enabled_chain_matches(self):
        """Test that enabled chain is consistent across endpoints"""
        # Get enabled chains from /api/system/chains
        system_response = requests.get(f"{BASE_URL}/api/system/chains")
        system_chains = system_response.json().get('chains', [])
        system_enabled = [c['chainId'] for c in system_chains if c.get('enabled')]
        
        # Get enabled chains from job-readiness
        job_response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/chains/job-readiness")
        job_enabled = job_response.json().get('enabledChains', [])
        
        assert set(system_enabled) == set(job_enabled), \
            f"Enabled chains mismatch: system={system_enabled}, job-readiness={job_enabled}"
        print(f"✓ Enabled chains consistent: {system_enabled}")


# Run all tests
if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
