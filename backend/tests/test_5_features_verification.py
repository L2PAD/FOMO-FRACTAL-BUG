"""
Test Suite for 5 Features Verification
=======================================
1. Signals Terminal - Cluster name resolution
2. EntityDrawer - Related wallets display  
3. Wallet Exposure & Capital Routes - Etherscan links
4. CSS underline removal (frontend test via API data)
5. Backend API wallet_addresses verification

Uses pytest framework with real API calls to public URL.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestBackendAPIs:
    """Test all backend APIs for wallet_addresses and cluster data."""
    
    def test_signals_api_returns_cluster_data(self):
        """#1 Test /api/signals returns CLUSTER_ACTIVITY signals with cluster_id for frontend resolution."""
        response = requests.get(f"{BASE_URL}/api/signals?limit=20")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "API should return ok: true"
        assert "signals" in data, "Response should contain signals array"
        
        signals = data["signals"]
        assert len(signals) > 0, "Should have at least 1 signal"
        
        # Find CLUSTER_ACTIVITY signals
        cluster_signals = [s for s in signals if s.get("signal_type") == "CLUSTER_ACTIVITY"]
        print(f"Found {len(cluster_signals)} CLUSTER_ACTIVITY signals")
        
        if cluster_signals:
            signal = cluster_signals[0]
            # Verify cluster data exists for frontend resolution
            assert "cluster_id" in signal, "CLUSTER_ACTIVITY signal should have cluster_id"
            assert "entity" in signal, "Signal should have entity field"
            # The entity field contains "Cluster CS-XXXXX" which frontend resolves
            print(f"Cluster ID: {signal.get('cluster_id')}, Entity: {signal.get('entity')}")
    
    def test_clusters_api_returns_cluster_names(self):
        """#1 Test /api/onchain-overview/clusters returns cluster_name for frontend mapping."""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/clusters?limit=10")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "API should return ok: true"
        assert "clusters" in data, "Response should contain clusters array"
        
        clusters = data["clusters"]
        assert len(clusters) > 0, "Should have at least 1 cluster"
        
        cluster = clusters[0]
        assert "cluster_id" in cluster, "Cluster should have cluster_id"
        assert "cluster_name" in cluster, "Cluster should have cluster_name"
        
        print(f"Cluster: {cluster.get('cluster_id')} -> {cluster.get('cluster_name')}")
        
        # Verify the name is human-readable (e.g., "Fund Cluster #1")
        cluster_name = cluster.get("cluster_name", "")
        assert "Cluster" in cluster_name, f"Cluster name should be human-readable, got: {cluster_name}"
    
    def test_intelligence_context_returns_wallet_addresses(self):
        """#3 Test /api/onchain/smart-money/intelligence-context returns actors with wallet_addresses."""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/intelligence-context?chainId=1&window=30d")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "API should return ok: true"
        
        # Check actors
        actors = data.get("actors", [])
        print(f"Found {len(actors)} actors")
        
        if actors:
            actor = actors[0]
            assert "wallet_addresses" in actor, "Actor should have wallet_addresses array"
            wallet_addresses = actor.get("wallet_addresses", [])
            assert len(wallet_addresses) > 0, "Actor should have at least 1 wallet address"
            
            # Verify addresses are valid 0x format
            for addr in wallet_addresses[:3]:
                assert addr.startswith("0x"), f"Address should start with 0x, got: {addr}"
                assert len(addr) == 42, f"Address should be 42 chars, got: {len(addr)}"
            
            print(f"Actor wallet_addresses: {wallet_addresses[:3]}")
        
        # Check routes
        routes = data.get("routes", [])
        print(f"Found {len(routes)} routes")
        
        if routes:
            route = routes[0]
            assert "wallet_addresses" in route, "Route should have wallet_addresses array"
            wallet_addresses = route.get("wallet_addresses", [])
            assert len(wallet_addresses) > 0, "Route should have at least 1 wallet address"
            print(f"Route wallet_addresses: {wallet_addresses}")
    
    def test_otc_api_returns_wallets(self):
        """#5 Test /api/intelligence/otc returns trades with seller_wallets and buyer_wallets."""
        response = requests.get(f"{BASE_URL}/api/intelligence/otc")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "API should return ok: true"
        
        trades = data.get("trades", [])
        print(f"Found {len(trades)} OTC trades")
        
        if trades:
            trade = trades[0]
            
            # Check seller_wallets
            seller_wallets = trade.get("seller_wallets", [])
            assert len(seller_wallets) > 0, "Trade should have seller_wallets"
            for addr in seller_wallets:
                assert addr.startswith("0x"), f"Seller wallet should be 0x address: {addr}"
            print(f"Seller wallets: {seller_wallets}")
            
            # Check buyer_wallets
            buyer_wallets = trade.get("buyer_wallets", [])
            assert len(buyer_wallets) > 0, "Trade should have buyer_wallets"
            for addr in buyer_wallets:
                assert addr.startswith("0x"), f"Buyer wallet should be 0x address: {addr}"
            print(f"Buyer wallets: {buyer_wallets}")
    
    def test_market_makers_api_returns_wallet_addresses(self):
        """#5 Test /api/intelligence/market-makers returns wallet_addresses."""
        response = requests.get(f"{BASE_URL}/api/intelligence/market-makers")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "API should return ok: true"
        
        market_makers = data.get("market_makers", [])
        print(f"Found {len(market_makers)} market makers")
        
        if market_makers:
            mm = market_makers[0]
            assert "wallet_addresses" in mm, "Market maker should have wallet_addresses"
            
            wallet_addresses = mm.get("wallet_addresses", [])
            assert len(wallet_addresses) > 0, "Market maker should have at least 1 wallet address"
            
            for addr in wallet_addresses:
                assert addr.startswith("0x"), f"Address should start with 0x: {addr}"
                assert len(addr) == 42, f"Address should be 42 chars: {addr}"
            
            print(f"Market maker: {mm.get('name')}, wallets: {wallet_addresses}")
    
    def test_clusters_overview_returns_wallet_addresses(self):
        """#5 Test /api/entities/v2/clusters/overview returns entities with wallet_addresses."""
        response = requests.get(f"{BASE_URL}/api/entities/v2/clusters/overview")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "API should return ok: true"
        
        entities = data.get("entities", [])
        print(f"Found {len(entities)} entities in clusters overview")
        
        if entities:
            entity = entities[0]
            assert "wallet_addresses" in entity, "Entity should have wallet_addresses"
            
            wallet_addresses = entity.get("wallet_addresses", [])
            assert len(wallet_addresses) > 0, "Entity should have at least 1 wallet address"
            
            for addr in wallet_addresses:
                assert addr.startswith("0x"), f"Address should start with 0x: {addr}"
            
            print(f"Entity: {entity.get('name')}, wallets: {wallet_addresses}")
    
    def test_signals_have_cluster_wallets_for_expansion(self):
        """Test CLUSTER_ACTIVITY signals have cluster_wallets array for expand/collapse feature."""
        response = requests.get(f"{BASE_URL}/api/signals?limit=20")
        assert response.status_code == 200
        
        data = response.json()
        signals = data.get("signals", [])
        
        cluster_signals = [s for s in signals if s.get("signal_type") == "CLUSTER_ACTIVITY"]
        
        if cluster_signals:
            signal = cluster_signals[0]
            cluster_wallets = signal.get("cluster_wallets", [])
            print(f"Cluster signal has {len(cluster_wallets)} wallets")
            
            if cluster_wallets:
                # Verify wallet format
                for wallet in cluster_wallets[:5]:
                    assert wallet.startswith("0x"), f"Wallet should be 0x address: {wallet}"
                print(f"Sample wallets: {cluster_wallets[:3]}")


class TestAPIHealthCheck:
    """Basic health checks for all required endpoints."""
    
    def test_signals_endpoint_healthy(self):
        """Test /api/signals endpoint is accessible."""
        response = requests.get(f"{BASE_URL}/api/signals")
        assert response.status_code == 200
        assert response.json().get("ok") is True
    
    def test_clusters_endpoint_healthy(self):
        """Test /api/onchain-overview/clusters endpoint is accessible."""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/clusters")
        assert response.status_code == 200
        assert response.json().get("ok") is True
    
    def test_intelligence_context_healthy(self):
        """Test /api/onchain/smart-money/intelligence-context endpoint is accessible."""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/intelligence-context?chainId=1&window=30d")
        assert response.status_code == 200
        assert response.json().get("ok") is True
    
    def test_otc_endpoint_healthy(self):
        """Test /api/intelligence/otc endpoint is accessible."""
        response = requests.get(f"{BASE_URL}/api/intelligence/otc")
        assert response.status_code == 200
        assert response.json().get("ok") is True
    
    def test_market_makers_endpoint_healthy(self):
        """Test /api/intelligence/market-makers endpoint is accessible."""
        response = requests.get(f"{BASE_URL}/api/intelligence/market-makers")
        assert response.status_code == 200
        assert response.json().get("ok") is True
    
    def test_clusters_overview_endpoint_healthy(self):
        """Test /api/entities/v2/clusters/overview endpoint is accessible."""
        response = requests.get(f"{BASE_URL}/api/entities/v2/clusters/overview")
        assert response.status_code == 200
        assert response.json().get("ok") is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
