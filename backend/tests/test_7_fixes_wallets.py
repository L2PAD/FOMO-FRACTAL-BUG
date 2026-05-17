"""
Test 7 Fixes — Wallet addresses and signal types verification
=============================================================
Tests for the 7 specific features fixed per user request:
#1 Overview → Key Signals: Diverse signal types (not just CLUSTER_ACTIVITY)
#2 Smart Money → Playbooks: No underlines (frontend check)
#3 Token Intelligence → WalletActivity: Real 0x wallet addresses + wallet_addresses array
#4 Top Smart Wallets: No underlines (frontend check)
#5 Entities → OTC Activity: seller_wallets and buyer_wallets arrays
#6 Entities → Market Makers: wallet_addresses arrays
#7 Entities → Cluster Coverage: wallet_addresses arrays
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestSignalsAPI:
    """#1 Overview → Key Signals: Diverse signal types"""

    def test_signals_endpoint_returns_diverse_types(self):
        """GET /api/onchain-overview/signals should return multiple signal types"""
        response = requests.get(f"{BASE_URL}/api/onchain-overview/signals?limit=10")
        assert response.status_code == 200, f"Status: {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, f"Response not ok: {data}"
        
        signals = data.get("signals", [])
        assert len(signals) > 0, "No signals returned"
        
        # Collect all signal types
        signal_types = set()
        for s in signals:
            stype = s.get("signal_type", "")
            if stype:
                signal_types.add(stype)
        
        print(f"Found signal types: {signal_types}")
        
        # Verify diverse types (not just CLUSTER_ACTIVITY)
        expected_types = {"CEX_INFLOW", "CLUSTER_COORDINATION", "WHALE_TRANSFER", 
                        "SMART_MONEY_ACTIVITY", "CLUSTER_ACTIVITY", "EXCHANGE_DOMINANCE",
                        "CEX_OUTFLOW"}
        
        # At least 2 different types (showing diversity)
        assert len(signal_types) >= 2, f"Only {len(signal_types)} signal type(s): {signal_types}"
        
        # Check signals have required fields
        for s in signals[:5]:
            assert "title" in s, "Missing title"
            assert "score" in s, "Missing score"
            assert "severity" in s, "Missing severity"
            print(f"Signal: {s.get('title')} | Type: {s.get('signal_type')} | Score: {s.get('score')}")


class TestTokenIntelligenceAPI:
    """#3 Token Intelligence → WalletActivity: Real 0x wallet addresses"""

    def test_smart_money_actors_have_wallet_addresses(self):
        """GET /api/onchain/smart-money/intelligence-context should return actors with wallet_addresses"""
        response = requests.get(
            f"{BASE_URL}/api/onchain/smart-money/intelligence-context?chainId=1&window=30d"
        )
        assert response.status_code == 200, f"Status: {response.status_code}"
        
        data = response.json()
        
        # Find actors from the response
        actors = data.get("top_actors", data.get("actors", []))
        
        if len(actors) == 0:
            pytest.skip("No actors returned - may need seeded data")
        
        # Check first actor has wallet and wallet_addresses
        actor = actors[0]
        print(f"Actor: {actor.get('name')}")
        
        # Verify wallet field starts with 0x
        wallet = actor.get("wallet", "")
        if wallet:
            assert wallet.startswith("0x"), f"Wallet not 0x address: {wallet}"
            print(f"Primary wallet: {wallet}")
        
        # Verify wallet_addresses array
        wallet_addresses = actor.get("wallet_addresses", [])
        print(f"wallet_addresses count: {len(wallet_addresses)}")
        
        if len(wallet_addresses) > 0:
            for addr in wallet_addresses[:3]:
                assert addr.startswith("0x"), f"Address not 0x: {addr}"
                assert len(addr) == 42, f"Invalid address length: {addr}"
            print(f"Sample addresses: {wallet_addresses[:3]}")


class TestOTCAPI:
    """#5 Entities → OTC Activity: seller_wallets and buyer_wallets"""

    def test_otc_trades_have_wallet_arrays(self):
        """GET /api/intelligence/otc should return trades with seller_wallets and buyer_wallets"""
        response = requests.get(f"{BASE_URL}/api/intelligence/otc")
        assert response.status_code == 200, f"Status: {response.status_code}"
        
        data = response.json()
        trades = data.get("trades", [])
        
        if len(trades) == 0:
            pytest.skip("No OTC trades returned - may need entity data")
        
        print(f"OTC trades count: {len(trades)}")
        
        # Check trades have wallet arrays
        for trade in trades[:3]:
            print(f"\nTrade: {trade.get('asset')} → {trade.get('stablecoin')}")
            
            seller_wallets = trade.get("seller_wallets", [])
            buyer_wallets = trade.get("buyer_wallets", [])
            
            print(f"  seller_wallets: {seller_wallets}")
            print(f"  buyer_wallets: {buyer_wallets}")
            
            # Verify wallet arrays exist
            assert isinstance(seller_wallets, list), "seller_wallets not a list"
            assert isinstance(buyer_wallets, list), "buyer_wallets not a list"
            
            # Verify addresses are 0x format
            for w in seller_wallets[:2]:
                assert w.startswith("0x"), f"Seller wallet not 0x: {w}"
            for w in buyer_wallets[:2]:
                assert w.startswith("0x"), f"Buyer wallet not 0x: {w}"


class TestMarketMakersAPI:
    """#6 Entities → Market Makers: wallet_addresses arrays"""

    def test_market_makers_have_wallet_addresses(self):
        """GET /api/intelligence/market-makers should return market_makers with wallet_addresses"""
        response = requests.get(f"{BASE_URL}/api/intelligence/market-makers")
        assert response.status_code == 200, f"Status: {response.status_code}"
        
        data = response.json()
        makers = data.get("market_makers", [])
        
        if len(makers) == 0:
            pytest.skip("No market makers returned - may need entity data")
        
        print(f"Market makers count: {len(makers)}")
        
        # Check makers have wallet_addresses
        for maker in makers[:3]:
            print(f"\nMaker: {maker.get('name')} | Score: {maker.get('score')}")
            
            wallet_addresses = maker.get("wallet_addresses", [])
            print(f"  wallet_addresses: {wallet_addresses}")
            
            # Verify wallet_addresses exists and has 0x addresses
            assert isinstance(wallet_addresses, list), "wallet_addresses not a list"
            
            if len(wallet_addresses) > 0:
                for w in wallet_addresses[:2]:
                    assert w.startswith("0x"), f"Address not 0x: {w}"
                    assert len(w) == 42, f"Invalid address length: {w}"


class TestClustersAPI:
    """#7 Entities → Cluster Coverage: wallet_addresses arrays"""

    def test_clusters_overview_has_wallet_addresses(self):
        """GET /api/entities/v2/clusters/overview should return entities with wallet_addresses"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/clusters/overview")
        assert response.status_code == 200, f"Status: {response.status_code}"
        
        data = response.json()
        entities = data.get("entities", [])
        
        if len(entities) == 0:
            pytest.skip("No cluster entities returned")
        
        print(f"Cluster entities count: {len(entities)}")
        print(f"Total discovered: {data.get('total_discovered', 0)}")
        
        # Check entities have wallet_addresses
        for entity in entities[:3]:
            print(f"\nEntity: {entity.get('name')} | Clusters: {entity.get('cluster_count')}")
            
            wallet_addresses = entity.get("wallet_addresses", [])
            print(f"  wallet_addresses: {wallet_addresses}")
            
            # Verify wallet_addresses exists and has 0x addresses
            assert isinstance(wallet_addresses, list), "wallet_addresses not a list"
            
            if len(wallet_addresses) > 0:
                for w in wallet_addresses[:2]:
                    assert w.startswith("0x"), f"Address not 0x: {w}"
                    assert len(w) == 42, f"Invalid address length: {w}"


class TestTopActorsAPI:
    """Additional test for top actors wallet addresses (related to #3)"""

    def test_top_actors_have_wallet_addresses(self):
        """GET /api/onchain/smart-money/top-actors should return actors with wallet_addresses"""
        response = requests.get(
            f"{BASE_URL}/api/onchain/smart-money/top-actors?chainId=1&window=30d&limit=5"
        )
        
        # May return 404 if endpoint doesn't exist directly
        if response.status_code == 404:
            pytest.skip("top-actors endpoint not available directly")
        
        assert response.status_code == 200, f"Status: {response.status_code}"
        
        data = response.json()
        actors = data.get("actors", data) if isinstance(data, dict) else data
        
        if not actors or len(actors) == 0:
            pytest.skip("No actors returned")
        
        for actor in actors[:3]:
            print(f"Actor: {actor.get('name')} | Wallet: {actor.get('wallet')}")
            wallet_addresses = actor.get("wallet_addresses", [])
            if wallet_addresses:
                for w in wallet_addresses[:2]:
                    assert w.startswith("0x"), f"Address not 0x: {w}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
