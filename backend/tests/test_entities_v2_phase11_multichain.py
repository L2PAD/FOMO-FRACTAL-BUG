"""
Entities V2 Phase 11: Multichain Expansion Tests
=================================================
Tests for multichain intelligence across Ethereum, Optimism, Arbitrum, Base.
- GET /api/entities/v2/{slug}/chains - entity chain distribution
- GET /api/entities/v2/chains/overview - cross-entity chain coverage
- POST /api/entities/v2/chains/build-all - build all entity chains
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestMultichainEntityChains:
    """Tests for GET /api/entities/v2/{slug}/chains"""

    def test_binance_chains_returns_200(self):
        """GET /api/entities/v2/binance/chains returns valid chain data"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/chains")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get('ok') is True
        print(f"PASS: binance/chains returned 200 OK")
        
    def test_binance_chains_structure(self):
        """Validate binance chains response structure"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/chains")
        data = response.json()
        
        # Entity metadata
        assert 'entity' in data, "Missing 'entity' field"
        assert data['entity']['slug'] == 'binance'
        assert 'name' in data['entity']
        assert 'type' in data['entity']
        assert 'category' in data['entity']
        
        # Chain metrics
        assert 'total_addresses' in data, "Missing total_addresses"
        assert 'total_chains_active' in data, "Missing total_chains_active"
        assert 'total_transfers' in data, "Missing total_transfers"
        assert 'has_multichain_activity' in data, "Missing has_multichain_activity"
        assert 'dominant_chain' in data, "Missing dominant_chain"
        assert 'chains' in data, "Missing chains array"
        assert 'cross_chain_addresses' in data, "Missing cross_chain_addresses"
        assert 'cross_chain_count' in data, "Missing cross_chain_count"
        assert 'bridge_summary' in data, "Missing bridge_summary"
        assert 'computed_at' in data, "Missing computed_at"
        
        print(f"PASS: binance chains structure valid - {data['total_chains_active']} chains active")

    def test_binance_chains_ethereum_activity(self):
        """Validate Binance has Ethereum chain activity"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/chains")
        data = response.json()
        chains = data.get('chains', [])
        
        # Find Ethereum chain
        eth_chain = next((c for c in chains if c['chain_name'] == 'Ethereum'), None)
        assert eth_chain is not None, "Binance should have Ethereum activity"
        
        # Validate chain structure
        assert eth_chain['chain_id'] == 1
        assert eth_chain['chain_short'] == 'ETH'
        assert eth_chain['chain_type'] == 'L1'
        assert eth_chain['total_transfers'] > 0
        print(f"PASS: Binance Ethereum activity - {eth_chain['total_transfers']} transfers")

    def test_chain_structure_fields(self):
        """Validate each chain has required fields"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/chains")
        data = response.json()
        chains = data.get('chains', [])
        
        if len(chains) == 0:
            pytest.skip("No chain data available")
            
        required_fields = [
            'chain_id', 'chain_name', 'chain_short', 'chain_type',
            'active_addresses', 'outbound_transfers', 'inbound_transfers', 'total_transfers',
            'direction', 'unique_tokens', 'unique_counterparties', 'activity_score',
            'bridge_interactions', 'has_bridge_activity', 'distribution_share'
        ]
        
        for chain in chains:
            for field in required_fields:
                assert field in chain, f"Chain {chain.get('chain_name')} missing field: {field}"
        
        print(f"PASS: All {len(chains)} chains have required fields")

    def test_distribution_share_sums_to_one(self):
        """Validate distribution_share sums to 1.0 for entity"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/chains")
        data = response.json()
        chains = data.get('chains', [])
        
        if len(chains) == 0:
            pytest.skip("No chain data to sum")
            
        total_share = sum(c['distribution_share'] for c in chains)
        assert 0.99 <= total_share <= 1.01, f"distribution_share sum {total_share} should be ~1.0"
        print(f"PASS: distribution_share sums to {total_share:.4f}")

    def test_activity_score_range(self):
        """Validate activity_score is 0-100 integer"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/chains")
        data = response.json()
        chains = data.get('chains', [])
        
        for chain in chains:
            score = chain['activity_score']
            assert isinstance(score, int), f"activity_score should be int, got {type(score)}"
            assert 0 <= score <= 100, f"activity_score {score} out of range 0-100"
        
        print(f"PASS: All activity_score values in 0-100 range")

    def test_has_multichain_activity_boolean(self):
        """Validate has_multichain_activity is boolean"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/chains")
        data = response.json()
        
        assert isinstance(data['has_multichain_activity'], bool), "has_multichain_activity should be boolean"
        print(f"PASS: has_multichain_activity is boolean ({data['has_multichain_activity']})")

    def test_dominant_chain_structure(self):
        """Validate dominant_chain has required fields"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/chains")
        data = response.json()
        dom = data.get('dominant_chain')
        
        if dom is None:
            pytest.skip("No dominant chain")
            
        assert 'chain_name' in dom, "Missing chain_name in dominant_chain"
        assert 'chain_id' in dom, "Missing chain_id in dominant_chain"
        assert 'distribution_share' in dom, "Missing distribution_share in dominant_chain"
        assert 'transfers' in dom, "Missing transfers in dominant_chain"
        
        print(f"PASS: dominant_chain is {dom['chain_name']} with {dom['transfers']} transfers")


class TestMultichainOtherEntities:
    """Tests for gate-io and coinbase chain endpoints"""

    def test_gate_io_chains_returns_200(self):
        """GET /api/entities/v2/gate-io/chains returns valid data"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/gate-io/chains")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        assert 'chains' in data
        print(f"PASS: gate-io/chains returned 200 - {data.get('total_chains_active', 0)} chains")

    def test_coinbase_chains_returns_200(self):
        """GET /api/entities/v2/coinbase/chains returns valid data"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/coinbase/chains")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        assert 'chains' in data
        print(f"PASS: coinbase/chains returned 200 - {data.get('total_chains_active', 0)} chains")

    def test_nonexistent_entity_returns_404(self):
        """GET /api/entities/v2/nonexistent/chains returns 404"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/nonexistent/chains")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        data = response.json()
        assert data.get('ok') is False
        assert 'error' in data
        print(f"PASS: nonexistent entity returns 404")


class TestChainsOverview:
    """Tests for GET /api/entities/v2/chains/overview"""

    def test_chains_overview_returns_200(self):
        """GET /api/entities/v2/chains/overview returns 200"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/chains/overview")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        print(f"PASS: chains/overview returned 200")

    def test_chains_overview_structure(self):
        """Validate chains overview response structure"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/chains/overview")
        data = response.json()
        
        assert 'total_entities' in data, "Missing total_entities"
        assert 'multichain_entities' in data, "Missing multichain_entities"
        assert 'chain_coverage' in data, "Missing chain_coverage"
        assert 'entities' in data, "Missing entities list"
        
        print(f"PASS: overview has {data['total_entities']} entities, {data['multichain_entities']} multichain")

    def test_chains_overview_chain_coverage_list(self):
        """Validate chain_coverage is a list with chain stats"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/chains/overview")
        data = response.json()
        coverage = data.get('chain_coverage', [])
        
        assert isinstance(coverage, list), "chain_coverage should be list"
        
        if len(coverage) > 0:
            for ch in coverage:
                assert 'chain_name' in ch, "chain_coverage item missing chain_name"
                assert 'entities' in ch, "chain_coverage item missing entities count"
                assert 'total_transfers' in ch, "chain_coverage item missing total_transfers"
        
        print(f"PASS: chain_coverage has {len(coverage)} chains")

    def test_chains_overview_entities_sorted_by_transfers(self):
        """Validate entities are sorted by total_transfers descending"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/chains/overview")
        data = response.json()
        entities = data.get('entities', [])
        
        if len(entities) < 2:
            pytest.skip("Not enough entities to test sorting")
            
        for i in range(len(entities) - 1):
            curr = entities[i].get('total_transfers', 0)
            next_ = entities[i + 1].get('total_transfers', 0)
            assert curr >= next_, f"Entities not sorted: {curr} < {next_}"
        
        print(f"PASS: {len(entities)} entities sorted by transfers")


class TestChainsBuildAll:
    """Tests for POST /api/entities/v2/chains/build-all"""

    def test_build_all_chains_returns_200(self):
        """POST /api/entities/v2/chains/build-all returns 200"""
        response = requests.post(f"{BASE_URL}/api/entities/v2/chains/build-all")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        print(f"PASS: chains/build-all returned 200")

    def test_build_all_chains_structure(self):
        """Validate build-all response structure"""
        response = requests.post(f"{BASE_URL}/api/entities/v2/chains/build-all")
        data = response.json()
        
        assert 'total_entities' in data, "Missing total_entities"
        assert 'computed' in data, "Missing computed count"
        assert 'multichain_entities' in data, "Missing multichain_entities"
        assert 'chain_coverage' in data, "Missing chain_coverage"
        assert 'errors' in data, "Missing errors count"
        assert 'built_at' in data, "Missing built_at timestamp"
        
        print(f"PASS: built {data['computed']}/{data['total_entities']} entities, {data['multichain_entities']} multichain")

    def test_build_all_chains_entity_count(self):
        """Build-all should process 15 entities"""
        response = requests.post(f"{BASE_URL}/api/entities/v2/chains/build-all")
        data = response.json()
        
        total = data.get('total_entities', 0)
        computed = data.get('computed', 0)
        
        assert total >= 15, f"Expected 15 entities, got {total}"
        assert computed > 0, "No entities were computed"
        assert data.get('errors', 0) == 0, f"Build had {data.get('errors')} errors"
        
        print(f"PASS: Built {computed}/{total} entities with 0 errors")


class TestEmptyEntityChains:
    """Test entities with no addresses return empty chains"""

    def test_entity_no_addresses_empty_chains(self):
        """Entity with no addresses should return empty chains list"""
        # Check an entity that might have no addresses (e.g., one without chain activity)
        response = requests.get(f"{BASE_URL}/api/entities/v2/kraken/chains")
        
        if response.status_code == 404:
            pytest.skip("Kraken entity not found")
            
        assert response.status_code == 200
        data = response.json()
        
        # Kraken may have 0 chains if no activity
        chains = data.get('chains', [])
        if len(chains) == 0:
            assert data.get('total_chains_active', 0) == 0
            assert data.get('total_transfers', 0) == 0
            print(f"PASS: Entity with no chain activity returns empty chains list")
        else:
            print(f"PASS: Kraken has {len(chains)} chains with activity")


class TestChainDirection:
    """Test chain direction classification"""

    def test_direction_values(self):
        """Direction should be inflow_dominant, outflow_dominant, or balanced"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/chains")
        data = response.json()
        chains = data.get('chains', [])
        
        valid_directions = ['inflow_dominant', 'outflow_dominant', 'balanced']
        
        for chain in chains:
            direction = chain.get('direction')
            assert direction in valid_directions, f"Invalid direction: {direction}"
        
        print(f"PASS: All chain directions are valid")


class TestCrossChainAddresses:
    """Test cross-chain address detection"""

    def test_cross_chain_addresses_structure(self):
        """Validate cross_chain_addresses structure"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/chains")
        data = response.json()
        cross = data.get('cross_chain_addresses', [])
        
        assert isinstance(cross, list), "cross_chain_addresses should be list"
        
        if len(cross) > 0:
            for cc in cross:
                assert 'address' in cc, "Missing address field"
                assert 'chains' in cc, "Missing chains field"
                assert 'chain_count' in cc, "Missing chain_count field"
                assert len(cc['chains']) >= 2, "Cross-chain address should be on 2+ chains"
        
        count = data.get('cross_chain_count', 0)
        assert count == len(cross), f"cross_chain_count mismatch: {count} vs {len(cross)}"
        
        print(f"PASS: {count} cross-chain addresses detected")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
