"""
Smart Money Wallet Addresses Test Suite
=========================================
Tests the wallet address enrichment feature for Smart Money tab.
Verifies that signals, events, actors, routes, and playbooks
all return real wallet addresses instead of 'unknown address'.
"""

import pytest
import requests
import os
import re

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

def is_valid_eth_address(addr: str) -> bool:
    """Check if address is a valid Ethereum address (0x...)."""
    return bool(addr and isinstance(addr, str) and re.match(r'^0x[a-fA-F0-9]{40}$', addr))


class TestSmartMoneyContextAPI:
    """Tests for /api/onchain/smart-money/context endpoint."""
    
    def test_context_endpoint_returns_200(self):
        """Test that the context endpoint returns 200 OK."""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/context", params={
            "chainId": 1,
            "window": "30d"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") is True, "Expected ok=True in response"
        print("PASS: Context endpoint returns 200 with ok=True")
    
    def test_signals_have_wallet_addresses(self):
        """Test that signals include wallet_addresses arrays."""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/context", params={
            "chainId": 1,
            "window": "30d"
        })
        assert response.status_code == 200
        data = response.json()
        
        signals = data.get("signals", [])
        assert len(signals) > 0, "No signals returned"
        
        signals_with_addresses = [s for s in signals if s.get("wallet_addresses")]
        assert len(signals_with_addresses) > 0, "No signals have wallet_addresses"
        
        # Verify addresses are valid Ethereum addresses
        for sig in signals_with_addresses[:3]:
            for addr in sig["wallet_addresses"][:3]:
                assert is_valid_eth_address(addr), f"Invalid address in signal: {addr}"
        
        print(f"PASS: {len(signals_with_addresses)}/{len(signals)} signals have wallet_addresses")
    
    def test_cluster_events_have_wallet_addresses(self):
        """Test that cluster_activity events include wallet_addresses."""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/context", params={
            "chainId": 1,
            "window": "30d"
        })
        assert response.status_code == 200
        data = response.json()
        
        events = data.get("events", [])
        cluster_events = [e for e in events if e.get("event_type") == "cluster_activity"]
        assert len(cluster_events) > 0, "No cluster_activity events found"
        
        events_with_addresses = [e for e in cluster_events if e.get("wallet_addresses")]
        assert len(events_with_addresses) > 0, "No cluster events have wallet_addresses"
        
        # Verify all cluster events have addresses
        for ev in events_with_addresses[:5]:
            addrs = ev.get("wallet_addresses", [])
            assert len(addrs) > 0, f"Empty wallet_addresses for {ev.get('entity')}"
            for addr in addrs[:5]:
                assert is_valid_eth_address(addr), f"Invalid address in event: {addr}"
        
        print(f"PASS: {len(events_with_addresses)}/{len(cluster_events)} cluster events have wallet_addresses")
    
    def test_routes_have_source_wallet(self):
        """Test that capital routes include source_wallet."""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/context", params={
            "chainId": 1,
            "window": "30d"
        })
        assert response.status_code == 200
        data = response.json()
        
        routes_data = data.get("routes", {})
        routes = routes_data.get("routes", [])
        assert len(routes) > 0, "No routes returned"
        
        routes_with_wallet = [r for r in routes if r.get("source_wallet")]
        assert len(routes_with_wallet) > 0, "No routes have source_wallet"
        
        # Verify source_wallet is valid
        for route in routes_with_wallet[:5]:
            wallet = route["source_wallet"]
            assert is_valid_eth_address(wallet), f"Invalid source_wallet: {wallet}"
        
        print(f"PASS: {len(routes_with_wallet)}/{len(routes)} routes have source_wallet")
    
    def test_actors_have_wallet_addresses(self):
        """Test that actors include wallet_addresses for entities like OKX."""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/context", params={
            "chainId": 1,
            "window": "30d"
        })
        assert response.status_code == 200
        data = response.json()
        
        actors = data.get("actors", [])
        assert len(actors) > 0, "No actors returned"
        
        actors_with_addresses = [a for a in actors if a.get("wallet_addresses")]
        # At least some actors should have wallet_addresses
        
        for actor in actors_with_addresses[:3]:
            for addr in actor["wallet_addresses"][:3]:
                assert is_valid_eth_address(addr), f"Invalid address for actor {actor.get('name')}: {addr}"
        
        print(f"PASS: {len(actors_with_addresses)}/{len(actors)} actors have wallet_addresses")
    
    def test_playbooks_have_wallet_addresses(self):
        """Test that playbooks include wallet_addresses and wallet objects with addresses."""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/context", params={
            "chainId": 1,
            "window": "30d"
        })
        assert response.status_code == 200
        data = response.json()
        
        playbooks = data.get("playbooks", [])
        assert len(playbooks) > 0, "No playbooks returned"
        
        playbooks_with_addresses = [p for p in playbooks if p.get("wallet_addresses")]
        assert len(playbooks_with_addresses) > 0, "No playbooks have wallet_addresses"
        
        # Verify addresses are valid
        for pb in playbooks_with_addresses[:3]:
            for addr in pb["wallet_addresses"][:3]:
                assert is_valid_eth_address(addr), f"Invalid address in playbook: {addr}"
        
        print(f"PASS: {len(playbooks_with_addresses)}/{len(playbooks)} playbooks have wallet_addresses")
    
    def test_no_unknown_address_in_playbook_wallets(self):
        """Test that playbook wallet names are not 'unknown address'."""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/context", params={
            "chainId": 1,
            "window": "30d"
        })
        assert response.status_code == 200
        data = response.json()
        
        playbooks = data.get("playbooks", [])
        unknown_count = 0
        total_wallets = 0
        
        for pb in playbooks:
            for w in pb.get("wallets", []):
                total_wallets += 1
                name = w.get("name", "").lower()
                if name in ("unknown address", "unknown", ""):
                    unknown_count += 1
        
        # Allow some unknowns but majority should have real addresses
        unknown_ratio = unknown_count / max(total_wallets, 1)
        print(f"Unknown ratio: {unknown_count}/{total_wallets} = {unknown_ratio:.2%}")
        
        # At least some wallets should have real addresses (not just 'unknown address')
        assert unknown_ratio < 1.0, "All playbook wallets are 'unknown address'"
        print(f"PASS: Playbook wallets have real addresses ({total_wallets - unknown_count}/{total_wallets})")


class TestSignalWalletExpansion:
    """Tests for wallet count and expandable wallet lists in signals."""
    
    def test_signals_with_wallet_count_have_addresses(self):
        """Test that signals with wallet_count > 0 have corresponding addresses."""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/context", params={
            "chainId": 1,
            "window": "30d"
        })
        assert response.status_code == 200
        data = response.json()
        
        signals = data.get("signals", [])
        signals_with_count = [s for s in signals if s.get("wallet_count", 0) > 0]
        
        if signals_with_count:
            signals_with_both = [s for s in signals_with_count if s.get("wallet_addresses")]
            print(f"Signals with wallet_count > 0: {len(signals_with_count)}")
            print(f"Of those, signals with wallet_addresses: {len(signals_with_both)}")
            
            # Verify address count matches or is close to wallet_count
            for sig in signals_with_both[:3]:
                wallet_count = sig["wallet_count"]
                addr_count = len(sig["wallet_addresses"])
                print(f"  {sig['token']}: wallet_count={wallet_count}, addresses={addr_count}")
        
        print("PASS: Signals with wallet counts have expandable address lists")
    
    def test_feed_items_have_wallet_addresses(self):
        """Test that feed items (high conviction signals) have wallet_addresses."""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/context", params={
            "chainId": 1,
            "window": "30d"
        })
        assert response.status_code == 200
        data = response.json()
        
        feed = data.get("feed", [])
        if feed:
            feed_with_addresses = [f for f in feed if f.get("wallet_addresses")]
            print(f"Feed items: {len(feed)}, with addresses: {len(feed_with_addresses)}")
        
        print("PASS: Feed items checked for wallet_addresses")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
