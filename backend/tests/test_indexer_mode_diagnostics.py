"""
Test: Indexer Mode & Diagnostics APIs
=====================================
Tests for:
- POST /api/admin/indexer/mode (FULL/LIMITED switching)
- GET /api/admin/indexer/diagnostics (chain sync data)
- POST /api/admin/indexer/restart
- GET /api/admin/indexer/status
- Existing onchain data endpoints
"""

import os
import pytest
import requests
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestIndexerModeControl:
    """Test indexer mode switching APIs"""
    
    def test_set_mode_full_indexer(self):
        """POST /api/admin/indexer/mode with mode=FULL switches to indexer mode"""
        response = requests.post(
            f"{BASE_URL}/api/admin/indexer/mode",
            json={"mode": "FULL"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("mode") == "FULL"
        assert data.get("internal") == "indexer"
    
    def test_set_mode_limited_lite(self):
        """POST /api/admin/indexer/mode with mode=LIMITED switches to lite mode"""
        response = requests.post(
            f"{BASE_URL}/api/admin/indexer/mode",
            json={"mode": "LIMITED"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("mode") == "LIMITED"
        assert data.get("internal") == "preview"
        
        # Restore to FULL mode
        requests.post(f"{BASE_URL}/api/admin/indexer/mode", json={"mode": "FULL"})
    
    def test_set_mode_invalid(self):
        """POST /api/admin/indexer/mode with invalid mode returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/admin/indexer/mode",
            json={"mode": "INVALID"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400
        data = response.json()
        assert data.get("ok") is False


class TestIndexerDiagnostics:
    """Test indexer diagnostics API"""
    
    def test_diagnostics_endpoint(self):
        """GET /api/admin/indexer/diagnostics returns real chain sync data"""
        response = requests.get(f"{BASE_URL}/api/admin/indexer/diagnostics")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        # Verify mode is present
        assert "mode" in data
        assert data["mode"] in ("indexer", "preview", "lite", "paused", "boost")
    
    def test_diagnostics_has_all_4_chains(self):
        """Diagnostics shows all 4 chains: ethereum, arbitrum, optimism, base"""
        response = requests.get(f"{BASE_URL}/api/admin/indexer/diagnostics")
        assert response.status_code == 200
        data = response.json()
        
        # Check RPC status for all chains
        rpc_chains = data.get("rpc", {}).get("chains", {})
        expected_chains = {"ethereum", "arbitrum", "optimism", "base"}
        assert set(rpc_chains.keys()) == expected_chains
        
        # Each chain should have status
        for chain in expected_chains:
            assert "status" in rpc_chains.get(chain, {})
            assert "head_block" in rpc_chains.get(chain, {})
    
    def test_diagnostics_chain_sync_data(self):
        """Diagnostics returns chain sync with blocks, transactions, events"""
        response = requests.get(f"{BASE_URL}/api/admin/indexer/diagnostics")
        assert response.status_code == 200
        data = response.json()
        
        # Check chains sync state
        chains = data.get("chains", {})
        for chain_name, chain_data in chains.items():
            assert "last_block" in chain_data
            assert "head_block" in chain_data
            assert "lag" in chain_data
            assert "status" in chain_data
    
    def test_diagnostics_ingestion_totals(self):
        """Diagnostics shows ingestion totals (blocks, transactions, events)"""
        response = requests.get(f"{BASE_URL}/api/admin/indexer/diagnostics")
        assert response.status_code == 200
        data = response.json()
        
        ingestion = data.get("ingestion", {})
        totals = ingestion.get("totals", {})
        
        # Verify totals keys exist
        assert "blocks" in totals
        assert "transactions" in totals
        assert "events" in totals
        
        # Verify they are integers
        assert isinstance(totals["blocks"], int)
        assert isinstance(totals["transactions"], int)
        assert isinstance(totals["events"], int)
    
    def test_diagnostics_health_statuses(self):
        """Diagnostics health shows rpc, sync, ingestion, signals statuses"""
        response = requests.get(f"{BASE_URL}/api/admin/indexer/diagnostics")
        assert response.status_code == 200
        data = response.json()
        
        health = data.get("health", {})
        expected_keys = {"rpc", "sync", "ingestion", "signals"}
        assert set(health.keys()) == expected_keys
        
        # Each should have a status value
        valid_statuses = {"ok", "error", "idle", "degraded"}
        for key in expected_keys:
            assert health[key] in valid_statuses


class TestIndexerRestart:
    """Test indexer restart API"""
    
    def test_restart_indexer(self):
        """POST /api/admin/indexer/restart restarts the indexer worker"""
        response = requests.post(f"{BASE_URL}/api/admin/indexer/restart")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "message" in data


class TestIndexerStatus:
    """Test indexer status API"""
    
    def test_indexer_status(self):
        """GET /api/admin/indexer/status returns full status"""
        response = requests.get(f"{BASE_URL}/api/admin/indexer/status")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        # Verify indexer object
        indexer = data.get("indexer", {})
        assert "mode" in indexer
        assert "runtimeStatus" in indexer
        
        # Verify rpcPools
        rpc_pools = data.get("rpcPools", {})
        expected_chains = {"ethereum", "arbitrum", "optimism", "base"}
        assert set(rpc_pools.keys()) == expected_chains
        
        # Verify summary
        summary = data.get("summary", {})
        assert "activeProviders" in summary
        assert "networks" in summary


class TestOnchainDataEndpoints:
    """Test existing onchain data endpoints still work"""
    
    def test_onchain_summary(self):
        """GET /api/onchain/summary returns valid data"""
        response = requests.get(f"{BASE_URL}/api/onchain/summary")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "data" in data
        assert "blockHeight" in data["data"]
        assert data["data"]["blockHeight"] > 0
    
    def test_onchain_flows(self):
        """GET /api/onchain/flows returns valid data"""
        response = requests.get(f"{BASE_URL}/api/onchain/flows")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "data" in data
    
    def test_onchain_whales(self):
        """GET /api/onchain/whales returns valid data"""
        response = requests.get(f"{BASE_URL}/api/onchain/whales")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "data" in data
    
    def test_onchain_activity(self):
        """GET /api/onchain/activity returns valid data"""
        response = requests.get(f"{BASE_URL}/api/onchain/activity")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "data" in data
    
    def test_onchain_status(self):
        """GET /api/onchain/status returns valid data"""
        response = requests.get(f"{BASE_URL}/api/onchain/status")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "mode" in data
        assert "chains" in data


class TestPlannedModuleEndpoints:
    """Test Research and Validation tabs' planned module endpoints (MOCKED)"""
    
    def test_observation_stats(self):
        """GET /api/v6/observation/stats - placeholder data"""
        response = requests.get(f"{BASE_URL}/api/v6/observation/stats")
        assert response.status_code == 200
    
    def test_observation_ml_status(self):
        """GET /api/v6/observation/ml/status - placeholder data"""
        response = requests.get(f"{BASE_URL}/api/v6/observation/ml/status")
        assert response.status_code == 200
    
    def test_validation_stats(self):
        """GET /api/v7/validation/stats - placeholder data"""
        response = requests.get(f"{BASE_URL}/api/v7/validation/stats")
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
