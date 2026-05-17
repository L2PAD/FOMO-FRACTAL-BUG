"""
Test On-Chain Overview Dashboard APIs
=====================================
Testing 7 overview endpoints:
1. GET /api/onchain-overview/summary - Network activity stats
2. GET /api/onchain-overview/entities - Top entities by tx_count
3. GET /api/onchain-overview/exchange-flows - Per-exchange inflow/outflow/net
4. GET /api/onchain-overview/smart-money - Scored wallets with labels
5. GET /api/onchain-overview/token-flows - ERC20 and native flows
6. GET /api/onchain-overview/clusters - Cluster data with scores
7. GET /api/onchain-overview/signals - Discovery signals
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestOnchainOverviewSummary:
    """Test /api/onchain-overview/summary endpoint - Network Activity stats"""
    
    def test_summary_returns_ok(self):
        """Summary endpoint returns ok=true with required fields"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/summary")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true"
        assert "active_wallets" in data, "Missing active_wallets field"
        assert "clusters_detected" in data, "Missing clusters_detected field"
        assert "smart_money_wallets" in data, "Missing smart_money_wallets field"
        assert "large_transfers" in data, "Missing large_transfers field"
    
    def test_summary_data_types(self):
        """Summary endpoint returns correct data types"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/summary")
        data = response.json()
        
        assert isinstance(data["active_wallets"], int), "active_wallets should be int"
        assert isinstance(data["clusters_detected"], int), "clusters_detected should be int"
        assert isinstance(data["smart_money_wallets"], int), "smart_money_wallets should be int"
        assert isinstance(data["large_transfers"], int), "large_transfers should be int"
        assert data["active_wallets"] > 0, "Should have at least 1 active wallet"
    
    def test_summary_wallet_types(self):
        """Summary includes wallet_types breakdown"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/summary")
        data = response.json()
        
        assert "wallet_types" in data, "Missing wallet_types field"
        assert isinstance(data["wallet_types"], dict), "wallet_types should be dict"
        # Check for exchange wallets (from seed data)
        assert "exchange" in data["wallet_types"], "Should have exchange wallet type"


class TestOnchainOverviewEntities:
    """Test /api/onchain-overview/entities endpoint - Top Entities Active"""
    
    def test_entities_returns_list(self):
        """Entities endpoint returns ok with entities array"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/entities")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "entities" in data
        assert isinstance(data["entities"], list)
    
    def test_entities_sorted_by_tx_count(self):
        """Entities are sorted by tx_count descending"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/entities?limit=10")
        data = response.json()
        entities = data["entities"]
        
        if len(entities) >= 2:
            for i in range(len(entities) - 1):
                assert entities[i]["tx_count"] >= entities[i + 1]["tx_count"], \
                    f"Entities not sorted: {entities[i]['tx_count']} < {entities[i + 1]['tx_count']}"
    
    def test_entities_have_required_fields(self):
        """Each entity has required fields"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/entities?limit=5")
        data = response.json()
        
        for entity in data["entities"]:
            assert "entity" in entity, "Missing entity name"
            assert "tx_count" in entity, "Missing tx_count"
            assert "total_value_eth" in entity, "Missing total_value_eth"
            assert "entity_type" in entity, "Missing entity_type"
    
    def test_entities_limit_param(self):
        """Limit parameter works correctly"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/entities?limit=3")
        data = response.json()
        
        assert len(data["entities"]) <= 3, "Limit not respected"


class TestOnchainOverviewExchangeFlows:
    """Test /api/onchain-overview/exchange-flows endpoint - Exchange Inflow/Outflow"""
    
    def test_exchange_flows_returns_ok(self):
        """Exchange flows returns ok with flows and totals"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/exchange-flows")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "flows" in data
        assert "totals" in data
    
    def test_exchange_flows_totals_structure(self):
        """Totals have inflow/outflow/net fields"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/exchange-flows")
        data = response.json()
        totals = data["totals"]
        
        assert "inflow_eth" in totals, "Missing inflow_eth in totals"
        assert "outflow_eth" in totals, "Missing outflow_eth in totals"
        assert "net_flow_eth" in totals, "Missing net_flow_eth in totals"
        
        # Verify net = inflow - outflow
        expected_net = round(totals["inflow_eth"] - totals["outflow_eth"], 2)
        actual_net = round(totals["net_flow_eth"], 2)
        assert abs(expected_net - actual_net) < 0.1, \
            f"Net flow calculation incorrect: {expected_net} != {actual_net}"
    
    def test_exchange_flows_per_exchange_structure(self):
        """Per-exchange flows have required fields"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/exchange-flows")
        data = response.json()
        
        for flow in data["flows"]:
            assert "entity" in flow, "Missing entity name"
            assert "inflow_eth" in flow, "Missing inflow_eth"
            assert "outflow_eth" in flow, "Missing outflow_eth"
            assert "net_flow_eth" in flow, "Missing net_flow_eth"


class TestOnchainOverviewSmartMoney:
    """Test /api/onchain-overview/smart-money endpoint - Smart Money Wallets"""
    
    def test_smart_money_returns_ok(self):
        """Smart money endpoint returns ok with wallets"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/smart-money")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "wallets" in data
        assert "count" in data
    
    def test_smart_money_sorted_by_score(self):
        """Wallets sorted by smart_money_score descending"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/smart-money?limit=15")
        data = response.json()
        wallets = data["wallets"]
        
        if len(wallets) >= 2:
            for i in range(len(wallets) - 1):
                assert wallets[i]["smart_money_score"] >= wallets[i + 1]["smart_money_score"], \
                    "Wallets not sorted by smart_money_score"
    
    def test_smart_money_wallet_fields(self):
        """Each wallet has required score fields"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/smart-money?limit=5")
        data = response.json()
        
        for wallet in data["wallets"]:
            assert "wallet" in wallet, "Missing wallet address"
            assert "smart_money_score" in wallet, "Missing smart_money_score"
            # Score should be between 0 and 1
            assert 0 <= wallet["smart_money_score"] <= 1, \
                f"Score out of range: {wallet['smart_money_score']}"


class TestOnchainOverviewTokenFlows:
    """Test /api/onchain-overview/token-flows endpoint - Token Flow Distribution"""
    
    def test_token_flows_returns_ok(self):
        """Token flows returns ok with erc20 and native flows"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/token-flows")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "erc20_flows" in data, "Missing erc20_flows"
        assert "native_flows" in data, "Missing native_flows"
    
    def test_token_flows_structure(self):
        """Token flows have required fields"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/token-flows")
        data = response.json()
        
        for token in data["erc20_flows"]:
            assert "token" in token, "Missing token symbol"
            assert "transfer_count" in token, "Missing transfer_count"
            assert "total_amount" in token, "Missing total_amount"


class TestOnchainOverviewClusters:
    """Test /api/onchain-overview/clusters endpoint - Cluster Activity"""
    
    def test_clusters_returns_ok(self):
        """Clusters endpoint returns ok with clusters list"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/clusters")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "clusters" in data
        assert "count" in data
    
    def test_clusters_sorted_by_score(self):
        """Clusters sorted by cluster_score descending"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/clusters?limit=10")
        data = response.json()
        clusters = data["clusters"]
        
        if len(clusters) >= 2:
            for i in range(len(clusters) - 1):
                assert clusters[i]["cluster_score"] >= clusters[i + 1]["cluster_score"], \
                    "Clusters not sorted by score"
    
    def test_clusters_have_required_fields(self):
        """Each cluster has required fields"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/clusters?limit=5")
        data = response.json()
        
        for cluster in data["clusters"]:
            assert "cluster_id" in cluster, "Missing cluster_id"
            assert "cluster_type" in cluster, "Missing cluster_type"
            assert "cluster_score" in cluster, "Missing cluster_score"
            assert "wallet_count" in cluster, "Missing wallet_count"


class TestOnchainOverviewSignals:
    """Test /api/onchain-overview/signals endpoint - Recent On-Chain Signals"""
    
    def test_signals_returns_ok(self):
        """Signals endpoint returns ok with signals list"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/signals")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "signals" in data
        assert "count" in data
    
    def test_signals_sorted_by_score(self):
        """Signals sorted by score descending"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/signals?limit=15")
        data = response.json()
        signals = data["signals"]
        
        if len(signals) >= 2:
            for i in range(len(signals) - 1):
                assert signals[i].get("score", 0) >= signals[i + 1].get("score", 0), \
                    "Signals not sorted by score"
    
    def test_signals_have_required_fields(self):
        """Each signal has required fields"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/signals?limit=5")
        data = response.json()
        
        for signal in data["signals"]:
            assert "signal_type" in signal, "Missing signal_type"
            assert "score" in signal, "Missing score"


# Run all tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
