"""
P0 Multichain V2 APIs + P1.3 Exchange Pressure Tests

Tests for:
- GET /api/v2/transfers (network REQUIRED)
- GET /api/v2/bridges (network REQUIRED)
- GET /api/v2/wallet/summary (multi-network)
- GET /api/v2/wallet/timeline (network REQUIRED)
- GET /api/v2/wallet/counterparties (network REQUIRED)
- GET /api/market/exchange-pressure (P1.3)
- GET /api/market/cex-addresses (P1.3)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test wallet address (Uniswap V2 Router)
TEST_ADDRESS = "0x7a250d5630b4cf539739df2c5dacb4c659f2488d"


class TestTransfersV2:
    """P0.2 - Transfers V2 API with network parameter"""
    
    def test_transfers_with_network_returns_200(self):
        """GET /api/v2/transfers?network=ethereum should return transfers"""
        response = requests.get(f"{BASE_URL}/api/v2/transfers?network=ethereum&limit=5")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "data" in data
        assert "transfers" in data["data"]
        assert "pagination" in data["data"]
        assert "meta" in data["data"]
        
        # Verify pagination structure
        pagination = data["data"]["pagination"]
        assert "total" in pagination
        assert "limit" in pagination
        assert "hasMore" in pagination
        
        # Verify meta structure
        meta = data["data"]["meta"]
        assert meta["network"] == "ethereum"
        assert "window" in meta
        assert "since" in meta
    
    def test_transfers_without_network_returns_400(self):
        """GET /api/v2/transfers without network should return 400 NETWORK_REQUIRED"""
        response = requests.get(f"{BASE_URL}/api/v2/transfers")
        assert response.status_code == 400
        
        data = response.json()
        assert data["ok"] is False
        assert data["error"] == "NETWORK_REQUIRED"
        assert "ethereum" in data["message"]  # Should list supported networks
    
    def test_transfers_with_invalid_network_returns_400(self):
        """GET /api/v2/transfers?network=invalid should return 400"""
        response = requests.get(f"{BASE_URL}/api/v2/transfers?network=invalid_network")
        assert response.status_code == 400
        
        data = response.json()
        assert data["ok"] is False
        assert data["error"] == "NETWORK_INVALID"
    
    def test_transfers_with_address_filter(self):
        """GET /api/v2/transfers with address filter should work"""
        response = requests.get(
            f"{BASE_URL}/api/v2/transfers?network=ethereum&address={TEST_ADDRESS}&limit=5"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        
        # If transfers exist, verify they involve the address
        transfers = data["data"]["transfers"]
        if len(transfers) > 0:
            for t in transfers:
                assert t["from"].lower() == TEST_ADDRESS.lower() or t["to"].lower() == TEST_ADDRESS.lower()


class TestBridgesV2:
    """P0.3 - Bridges V2 API"""
    
    def test_bridges_with_network_returns_200(self):
        """GET /api/v2/bridges?network=ethereum should return bridge events"""
        response = requests.get(f"{BASE_URL}/api/v2/bridges?network=ethereum&limit=5")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "data" in data
        assert "bridges" in data["data"]
        assert "pagination" in data["data"]
        assert "meta" in data["data"]
        
        # Verify meta
        assert data["data"]["meta"]["network"] == "ethereum"
    
    def test_bridges_without_network_returns_400(self):
        """GET /api/v2/bridges without network should return 400"""
        response = requests.get(f"{BASE_URL}/api/v2/bridges")
        assert response.status_code == 400
        
        data = response.json()
        assert data["ok"] is False
        assert data["error"] == "NETWORK_REQUIRED"
    
    def test_bridges_registry_returns_200(self):
        """GET /api/v2/bridges/registry should return known bridges"""
        response = requests.get(f"{BASE_URL}/api/v2/bridges/registry")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "bridges" in data["data"]
        assert "networks" in data["data"]
        
        # Should have known bridges
        bridges = data["data"]["bridges"]
        assert len(bridges) > 0
        
        # Verify bridge structure
        bridge = bridges[0]
        assert "name" in bridge
        assert "addresses" in bridge
        assert "targetNetworks" in bridge


class TestWalletV2:
    """P0.4 - Wallet V2 API (multi-network)"""
    
    def test_wallet_summary_returns_200(self):
        """GET /api/v2/wallet/summary should return multi-network summary"""
        response = requests.get(f"{BASE_URL}/api/v2/wallet/summary?address={TEST_ADDRESS}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "data" in data
        
        wallet_data = data["data"]
        assert wallet_data["address"] == TEST_ADDRESS.lower()
        assert "window" in wallet_data
        assert "networks" in wallet_data
        assert "totals" in wallet_data
        assert "activeNetworks" in wallet_data
        
        # Verify totals structure
        totals = wallet_data["totals"]
        assert "transfersIn" in totals
        assert "transfersOut" in totals
        assert "netFlow" in totals
        assert "bridgesIn" in totals
        assert "bridgesOut" in totals
    
    def test_wallet_summary_without_address_returns_400(self):
        """GET /api/v2/wallet/summary without address should return 400"""
        response = requests.get(f"{BASE_URL}/api/v2/wallet/summary")
        assert response.status_code == 400
        
        data = response.json()
        assert data["ok"] is False
        assert data["error"] == "ADDRESS_REQUIRED"
    
    def test_wallet_timeline_returns_200(self):
        """GET /api/v2/wallet/timeline should return activity timeline"""
        response = requests.get(
            f"{BASE_URL}/api/v2/wallet/timeline?network=ethereum&address={TEST_ADDRESS}&limit=5"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        
        timeline_data = data["data"]
        assert timeline_data["address"] == TEST_ADDRESS.lower()
        assert timeline_data["network"] == "ethereum"
        assert "timeline" in timeline_data
        assert "counts" in timeline_data
        
        # Verify timeline item structure if exists
        timeline = timeline_data["timeline"]
        if len(timeline) > 0:
            item = timeline[0]
            assert "type" in item  # TRANSFER or BRIDGE
            assert "timestamp" in item
            assert "txHash" in item
            assert "direction" in item  # IN or OUT
            assert "counterparty" in item
    
    def test_wallet_timeline_without_network_returns_400(self):
        """GET /api/v2/wallet/timeline without network should return 400"""
        response = requests.get(f"{BASE_URL}/api/v2/wallet/timeline?address={TEST_ADDRESS}")
        assert response.status_code == 400
        
        data = response.json()
        assert data["ok"] is False
        assert data["error"] == "NETWORK_REQUIRED"
    
    def test_wallet_counterparties_returns_200(self):
        """GET /api/v2/wallet/counterparties should return top counterparties"""
        response = requests.get(
            f"{BASE_URL}/api/v2/wallet/counterparties?network=ethereum&address={TEST_ADDRESS}&limit=5"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        
        cp_data = data["data"]
        assert cp_data["address"] == TEST_ADDRESS.lower()
        assert cp_data["network"] == "ethereum"
        assert "counterparties" in cp_data
        
        # Verify counterparty structure if exists
        counterparties = cp_data["counterparties"]
        if len(counterparties) > 0:
            cp = counterparties[0]
            assert "address" in cp
            assert "txCount" in cp
            assert "direction" in cp
            assert "firstSeen" in cp
            assert "lastSeen" in cp
    
    def test_wallet_counterparties_without_network_returns_400(self):
        """GET /api/v2/wallet/counterparties without network should return 400"""
        response = requests.get(f"{BASE_URL}/api/v2/wallet/counterparties?address={TEST_ADDRESS}")
        assert response.status_code == 400
        
        data = response.json()
        assert data["ok"] is False
        assert data["error"] == "NETWORK_REQUIRED"


class TestExchangePressure:
    """P1.3 - Exchange Pressure API (Market & Flow Analytics)"""
    
    def test_exchange_pressure_returns_200(self):
        """GET /api/market/exchange-pressure?network=ethereum should return pressure data"""
        response = requests.get(f"{BASE_URL}/api/market/exchange-pressure?network=ethereum")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "data" in data
        
        pressure_data = data["data"]
        assert pressure_data["network"] == "ethereum"
        assert "window" in pressure_data
        assert "since" in pressure_data
        assert "exchanges" in pressure_data
        assert "aggregate" in pressure_data
        
        # Verify aggregate structure
        aggregate = pressure_data["aggregate"]
        assert "totalInflow" in aggregate
        assert "totalOutflow" in aggregate
        assert "netFlow" in aggregate
        assert "pressure" in aggregate
        assert "signal" in aggregate
        
        # Signal should be one of valid values
        valid_signals = ["STRONG_BUY", "BUY", "NEUTRAL", "SELL", "STRONG_SELL"]
        assert aggregate["signal"] in valid_signals
        
        # Pressure should be between -1 and 1
        assert -1 <= aggregate["pressure"] <= 1
    
    def test_exchange_pressure_without_network_returns_400(self):
        """GET /api/market/exchange-pressure without network should return 400"""
        response = requests.get(f"{BASE_URL}/api/market/exchange-pressure")
        assert response.status_code == 400
        
        data = response.json()
        assert data["ok"] is False
        assert data["error"] == "NETWORK_REQUIRED"
    
    def test_exchange_pressure_exchanges_structure(self):
        """Verify exchange-level pressure data structure"""
        response = requests.get(f"{BASE_URL}/api/market/exchange-pressure?network=ethereum")
        assert response.status_code == 200
        
        data = response.json()
        exchanges = data["data"]["exchanges"]
        
        # Should have multiple exchanges
        assert len(exchanges) > 0
        
        # Verify exchange structure
        for ex in exchanges:
            assert "exchange" in ex
            assert "inflow" in ex
            assert "outflow" in ex
            assert "inflowTxCount" in ex
            assert "outflowTxCount" in ex
            assert "pressure" in ex
            assert "signal" in ex
    
    def test_exchange_pressure_with_window(self):
        """GET /api/market/exchange-pressure with different windows"""
        for window in ["1h", "4h", "24h", "7d"]:
            response = requests.get(
                f"{BASE_URL}/api/market/exchange-pressure?network=ethereum&window={window}"
            )
            assert response.status_code == 200
            
            data = response.json()
            assert data["ok"] is True
            assert data["data"]["window"] == window
    
    def test_cex_addresses_returns_200(self):
        """GET /api/market/cex-addresses should return known CEX addresses"""
        response = requests.get(f"{BASE_URL}/api/market/cex-addresses?network=ethereum")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "data" in data
        
        cex_data = data["data"]
        assert cex_data["network"] == "ethereum"
        assert "exchanges" in cex_data
        assert "totalAddresses" in cex_data
        
        # Should have multiple exchanges
        exchanges = cex_data["exchanges"]
        assert len(exchanges) > 0
        
        # Verify exchange structure
        for ex in exchanges:
            assert "exchange" in ex
            assert "name" in ex
            assert "addresses" in ex
            assert len(ex["addresses"]) > 0
        
        # Total addresses should match sum
        total = sum(len(ex["addresses"]) for ex in exchanges)
        assert cex_data["totalAddresses"] == total
    
    def test_cex_addresses_all_networks(self):
        """GET /api/market/cex-addresses without network returns all"""
        response = requests.get(f"{BASE_URL}/api/market/cex-addresses")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert data["data"]["network"] == "all"


class TestNetworkValidation:
    """Test network parameter validation across all V2 endpoints"""
    
    @pytest.mark.parametrize("network", ["ethereum", "arbitrum", "optimism", "base", "polygon"])
    def test_transfers_supported_networks(self, network):
        """Transfers V2 should accept all supported networks"""
        response = requests.get(f"{BASE_URL}/api/v2/transfers?network={network}&limit=1")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert data["data"]["meta"]["network"] == network
    
    @pytest.mark.parametrize("network", ["ethereum", "arbitrum", "optimism", "base", "polygon"])
    def test_exchange_pressure_supported_networks(self, network):
        """Exchange pressure should accept all supported networks"""
        response = requests.get(f"{BASE_URL}/api/market/exchange-pressure?network={network}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert data["data"]["network"] == network


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
