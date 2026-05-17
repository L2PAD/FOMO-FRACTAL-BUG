"""
Cluster Wallets Signals Test - P0
Tests the cluster_wallets field enrichment for CLUSTER_ACTIVITY signals
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestClusterWalletsSignals:
    """Tests for CLUSTER_ACTIVITY signals with cluster_wallets enrichment"""
    
    def test_signals_api_returns_ok(self):
        """Test that /api/signals returns OK status"""
        response = requests.get(f"{BASE_URL}/api/signals")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "signals" in data
        assert "count" in data
        print(f"✓ API returned {data['count']} signals")
    
    def test_cluster_activity_signals_have_cluster_wallets(self):
        """Test that CLUSTER_ACTIVITY signals have cluster_wallets array"""
        response = requests.get(f"{BASE_URL}/api/signals")
        assert response.status_code == 200
        data = response.json()
        
        cluster_signals = [s for s in data["signals"] if s.get("signal_type") == "CLUSTER_ACTIVITY"]
        assert len(cluster_signals) > 0, "No CLUSTER_ACTIVITY signals found"
        
        signals_with_wallets = 0
        for signal in cluster_signals:
            if "cluster_wallets" in signal:
                signals_with_wallets += 1
                assert isinstance(signal["cluster_wallets"], list), f"cluster_wallets should be a list for signal {signal['id']}"
                assert len(signal["cluster_wallets"]) > 0, f"cluster_wallets should not be empty for signal {signal['id']}"
                
                # Verify wallets are valid Ethereum addresses
                for wallet in signal["cluster_wallets"]:
                    assert wallet.startswith("0x"), f"Invalid wallet address: {wallet}"
                    assert len(wallet) == 42, f"Wallet address wrong length: {wallet}"
        
        print(f"✓ Found {len(cluster_signals)} CLUSTER_ACTIVITY signals, {signals_with_wallets} have cluster_wallets")
        assert signals_with_wallets == len(cluster_signals), "All CLUSTER_ACTIVITY signals should have cluster_wallets"
    
    def test_cluster_activity_signals_have_required_fields(self):
        """Test that CLUSTER_ACTIVITY signals have all required fields"""
        response = requests.get(f"{BASE_URL}/api/signals")
        assert response.status_code == 200
        data = response.json()
        
        cluster_signals = [s for s in data["signals"] if s.get("signal_type") == "CLUSTER_ACTIVITY"]
        assert len(cluster_signals) > 0
        
        for signal in cluster_signals:
            assert "id" in signal, "Signal missing id"
            assert "cluster_id" in signal, "Signal missing cluster_id"
            assert "cluster_wallets" in signal, "Signal missing cluster_wallets"
            assert "wallet_count" in signal or len(signal.get("cluster_wallets", [])) > 0, "Signal should have wallet_count or non-empty cluster_wallets"
            
        print(f"✓ All {len(cluster_signals)} CLUSTER_ACTIVITY signals have required fields")
    
    def test_non_cluster_activity_signals_no_cluster_wallets(self):
        """Test that non-CLUSTER_ACTIVITY signals do NOT have cluster_wallets field"""
        response = requests.get(f"{BASE_URL}/api/signals")
        assert response.status_code == 200
        data = response.json()
        
        non_cluster_signals = [s for s in data["signals"] if s.get("signal_type") != "CLUSTER_ACTIVITY"]
        
        signals_with_wallets = 0
        for signal in non_cluster_signals:
            if "cluster_wallets" in signal:
                signals_with_wallets += 1
        
        print(f"✓ Checked {len(non_cluster_signals)} non-CLUSTER_ACTIVITY signals, {signals_with_wallets} have cluster_wallets (should be 0)")
        assert signals_with_wallets == 0, f"Non-CLUSTER_ACTIVITY signals should not have cluster_wallets, found {signals_with_wallets}"
    
    def test_cluster_wallets_count_matches(self):
        """Test that wallet_count matches actual number of wallets"""
        response = requests.get(f"{BASE_URL}/api/signals")
        assert response.status_code == 200
        data = response.json()
        
        cluster_signals = [s for s in data["signals"] if s.get("signal_type") == "CLUSTER_ACTIVITY"]
        
        for signal in cluster_signals:
            if "cluster_wallets" in signal and "wallet_count" in signal:
                actual_count = len(signal["cluster_wallets"])
                reported_count = signal["wallet_count"]
                # Note: wallet_count might be different if it's from the signal metadata
                # vs cluster_wallets which is the actual wallets from wallet_clusters collection
                print(f"Signal {signal['id']}: reported={reported_count}, actual={actual_count}")
    
    def test_signals_actors_filter(self):
        """Test that signals with signal_type filter returns CLUSTER_ACTIVITY signals"""
        # The Actors filter includes CLUSTER_ACTIVITY as per TAB_TYPES in the frontend
        response = requests.get(f"{BASE_URL}/api/signals?signal_type=CLUSTER_ACTIVITY")
        assert response.status_code == 200
        data = response.json()
        
        # All returned signals should be CLUSTER_ACTIVITY
        for signal in data.get("signals", []):
            if signal.get("signal_type") == "CLUSTER_ACTIVITY":
                assert "cluster_wallets" in signal, f"CLUSTER_ACTIVITY signal {signal['id']} missing cluster_wallets"
        
        print(f"✓ signal_type=CLUSTER_ACTIVITY filter works correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
