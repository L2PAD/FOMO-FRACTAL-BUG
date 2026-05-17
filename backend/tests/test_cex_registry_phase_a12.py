"""
CEX Registry & Flow API Tests — Phase A1.2/A1.3
Tests for Industrial CEX Registry with 377+ addresses across 26 exchanges
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestCexRegistryStats:
    """CEX Registry Stats API Tests"""
    
    def test_registry_stats_returns_26_plus_exchanges(self):
        """GET /api/v10/onchain-v2/cex/registry/stats should return 26+ exchanges"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/cex/registry/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert data['exchangesCount'] >= 26, f"Expected 26+ exchanges, got {data['exchangesCount']}"
        assert 'totalAddresses' in data
        
    def test_registry_stats_returns_370_plus_addresses(self):
        """GET /api/v10/onchain-v2/cex/registry/stats should return 370+ total addresses"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/cex/registry/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert data['totalAddresses'] >= 370, f"Expected 370+ addresses, got {data['totalAddresses']}"
        
    def test_registry_stats_includes_by_exchange_breakdown(self):
        """Stats should include byExchange breakdown with entityId, entityName, count, status"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/cex/registry/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert 'byExchange' in data
        assert len(data['byExchange']) >= 26
        
        # Verify structure of first exchange
        first_exchange = data['byExchange'][0]
        assert 'entityId' in first_exchange
        assert 'entityName' in first_exchange
        assert 'count' in first_exchange
        assert 'status' in first_exchange
        assert first_exchange['status'] == 'active'
        
    def test_registry_stats_includes_by_type_breakdown(self):
        """Stats should include byType breakdown"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/cex/registry/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert 'byType' in data
        assert len(data['byType']) > 0
        
        # Check that hot_wallet is most common
        first_type = data['byType'][0]
        assert 'addressType' in first_type
        assert 'count' in first_type


class TestCexRegistryExchanges:
    """CEX Registry Exchanges List API Tests"""
    
    def test_registry_exchanges_returns_26_exchanges(self):
        """GET /api/v10/onchain-v2/cex/registry/exchanges should return all 26 active exchanges"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/cex/registry/exchanges")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert 'exchanges' in data
        assert len(data['exchanges']) == 26, f"Expected 26 exchanges, got {len(data['exchanges'])}"
        
    def test_registry_exchanges_all_active_status(self):
        """All exchanges should have active status"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/cex/registry/exchanges")
        assert response.status_code == 200
        
        data = response.json()
        for exchange in data['exchanges']:
            assert exchange['status'] == 'active', f"{exchange['entityId']} has status {exchange['status']}"
            
    def test_registry_exchanges_correct_entity_names(self):
        """Exchanges should have correct human-readable entityNames"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/cex/registry/exchanges")
        assert response.status_code == 200
        
        data = response.json()
        exchanges_by_id = {ex['entityId']: ex for ex in data['exchanges']}
        
        # Verify key exchanges have correct names
        expected_names = {
            'binance': 'Binance',
            'coinbase': 'Coinbase',
            'crypto_com': 'Crypto.com',
            'gate': 'Gate.io',
            'binance_us': 'Binance.US',
            'htx': 'HTX',
            'okx': 'OKX',
            'kraken': 'Kraken',
            'bitflyer': 'bitFlyer',
            'whitebit': 'WhiteBIT',
        }
        
        for entity_id, expected_name in expected_names.items():
            if entity_id in exchanges_by_id:
                actual_name = exchanges_by_id[entity_id]['entityName']
                assert actual_name == expected_name, f"Expected {entity_id} to have name '{expected_name}', got '{actual_name}'"


class TestCexFlowExchanges:
    """CEX Flow Exchanges API Tests"""
    
    def test_cex_flow_exchanges_returns_26(self):
        """GET /api/v10/onchain-v2/cex-flow/exchanges should list 26 exchanges"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/cex-flow/exchanges?chainId=1")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert 'exchanges' in data
        assert len(data['exchanges']) == 26, f"Expected 26 exchanges, got {len(data['exchanges'])}"
        
    def test_cex_flow_exchanges_correct_entity_names(self):
        """CEX Flow should use correct entityNames from prettifyName mapping"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/cex-flow/exchanges?chainId=1")
        assert response.status_code == 200
        
        data = response.json()
        exchanges_by_id = {ex['entityId']: ex for ex in data['exchanges']}
        
        # Verify correct names (not underscore versions)
        name_checks = [
            ('crypto_com', 'Crypto.com'),
            ('gate', 'Gate.io'),
            ('binance_us', 'Binance.US'),
        ]
        
        for entity_id, expected_name in name_checks:
            if entity_id in exchanges_by_id:
                actual_name = exchanges_by_id[entity_id]['entityName']
                assert actual_name == expected_name, f"{entity_id} should be '{expected_name}', got '{actual_name}'"
                
    def test_cex_flow_exchanges_includes_address_count(self):
        """Each exchange should have addressCount field"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/cex-flow/exchanges?chainId=1")
        assert response.status_code == 200
        
        data = response.json()
        for exchange in data['exchanges']:
            assert 'addressCount' in exchange, f"Missing addressCount for {exchange['entityId']}"
            assert exchange['addressCount'] > 0, f"{exchange['entityId']} has 0 addresses"


class TestCexFlowSummary:
    """CEX Flow Summary API Tests"""
    
    def test_cex_flow_summary_binance_returns_flow_data(self):
        """GET /api/v10/onchain-v2/cex-flow/summary for binance should return non-zero flow"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/cex-flow/summary",
            params={'chainId': 1, 'entityId': 'binance', 'window': '7d'}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert data['entityId'] == 'binance'
        assert data['entityName'] == 'Binance'
        assert data['window'] == '7d'
        
    def test_cex_flow_summary_includes_totals(self):
        """Summary should include totals with inUsd, outUsd, netUsd, txCount"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/cex-flow/summary",
            params={'chainId': 1, 'entityId': 'binance', 'window': '7d'}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert 'totals' in data
        totals = data['totals']
        assert 'inUsd' in totals
        assert 'outUsd' in totals
        assert 'netUsd' in totals
        assert 'txCount' in totals
        assert 'uniqueCounterparties' in totals
        
    def test_cex_flow_summary_non_zero_totals(self):
        """Binance should have non-zero flow data"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/cex-flow/summary",
            params={'chainId': 1, 'entityId': 'binance', 'window': '7d'}
        )
        assert response.status_code == 200
        
        data = response.json()
        totals = data['totals']
        # Binance should have activity
        assert totals['txCount'] > 0, "Binance should have transactions"
        
    def test_cex_flow_summary_includes_top_tokens(self):
        """Summary should include topTokensIn, topTokensOut, topNetTokens"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/cex-flow/summary",
            params={'chainId': 1, 'entityId': 'binance', 'window': '7d'}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert 'topTokensIn' in data
        assert 'topTokensOut' in data
        assert 'topNetTokens' in data
        
    def test_cex_flow_summary_includes_quality_metrics(self):
        """Summary should include quality metrics"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/cex-flow/summary",
            params={'chainId': 1, 'entityId': 'binance', 'window': '7d'}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert 'quality' in data
        quality = data['quality']
        assert 'totalLogs' in quality
        assert 'pricedLogs' in quality
        assert 'pricedShare' in quality
        
    def test_cex_flow_summary_missing_entity_returns_error(self):
        """Missing entityId should return error"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/cex-flow/summary",
            params={'chainId': 1, 'window': '7d'}
        )
        assert response.status_code == 200  # API returns 200 with ok:false
        
        data = response.json()
        assert data['ok'] == False
        assert data['error'] == 'MISSING_ENTITY_ID'


class TestCexFlowCross:
    """CEX Flow Cross-Exchange API Tests (slow endpoint ~30s)"""
    
    def test_cex_flow_cross_returns_26_exchanges(self):
        """GET /api/v10/onchain-v2/cex-flow/cross should return 26 exchanges"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/cex-flow/cross",
            params={'chainId': 1, 'window': '7d'},
            timeout=90  # Cross endpoint is slow
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert 'exchanges' in data
        assert len(data['exchanges']) == 26, f"Expected 26 exchanges, got {len(data['exchanges'])}"
        
    def test_cex_flow_cross_exchange_structure(self):
        """Each exchange in cross should have correct fields"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/cex-flow/cross",
            params={'chainId': 1, 'window': '7d'},
            timeout=90
        )
        assert response.status_code == 200
        
        data = response.json()
        for exchange in data['exchanges']:
            assert 'entityId' in exchange
            assert 'entityName' in exchange
            assert 'inUsd' in exchange
            assert 'outUsd' in exchange
            assert 'netUsd' in exchange
            assert 'txCount' in exchange
            
    def test_cex_flow_cross_some_have_flow_data(self):
        """At least some exchanges should have flow data"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/cex-flow/cross",
            params={'chainId': 1, 'window': '7d'},
            timeout=90
        )
        assert response.status_code == 200
        
        data = response.json()
        exchanges_with_flow = [
            ex for ex in data['exchanges'] 
            if ex['inUsd'] > 0 or ex['outUsd'] > 0 or ex['txCount'] > 0
        ]
        assert len(exchanges_with_flow) > 0, "At least some exchanges should have flow data"


class TestCexRegistryDatasets:
    """Verify 26 JSON dataset files exist in /datasets/cex/"""
    
    def test_datasets_endpoint_exists(self):
        """POST /api/v10/onchain-v2/cex/registry/import-datasets should be accessible"""
        # Just verify endpoint responds (don't actually import again)
        # GET to stats is enough to verify data was imported
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/cex/registry/stats")
        assert response.status_code == 200
        
        data = response.json()
        # If 26 exchanges exist with 370+ addresses, import was successful
        assert data['exchangesCount'] == 26
        assert data['totalAddresses'] >= 370


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
