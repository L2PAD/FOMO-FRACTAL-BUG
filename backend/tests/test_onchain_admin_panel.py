"""
On-Chain Admin Panel API Tests
==============================
Tests for the restored on-chain admin panel with 6 tabs:
- Overview, Engine, Infrastructure, Governance, Research, Validation

On-chain data endpoints:
- /api/onchain/summary, /api/onchain/flows, /api/onchain/whales, /api/onchain/activity

Admin indexer control:
- /api/admin/indexer/status, /api/admin/indexer/mode, /api/admin/indexer/pause, /api/admin/indexer/resume

Admin V2 routes:
- /api/v10/onchain-v2/admin/runtime, /api/v10/onchain-v2/admin/governance/state
- /api/v10/onchain-v2/admin/rpc, /api/v6/observation/*, /api/v7/validation/*
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


# ═══════════════════════════════════════════════════════════════
# On-Chain Data Endpoints (Real data from Infura RPC + DefiLlama)
# ═══════════════════════════════════════════════════════════════

class TestOnchainDataEndpoints:
    """Tests for /api/onchain/* endpoints - real on-chain data"""

    def test_onchain_summary(self):
        """GET /api/onchain/summary returns network health with real block number"""
        response = requests.get(f"{BASE_URL}/api/onchain/summary")
        assert response.status_code == 200, f"Status: {response.status_code}"
        data = response.json()
        assert data.get("ok") is True
        assert "data" in data
        assert "mode" in data
        
        # Verify real block data
        summary = data["data"]
        assert "blockHeight" in summary
        assert summary["blockHeight"] > 20000000, "Block should be > 20M for Ethereum mainnet"
        assert "gasPrice" in summary
        assert "tps" in summary
        assert summary.get("provider") == "infura-lite"

    def test_onchain_flows(self):
        """GET /api/onchain/flows returns exchange and stablecoin flows"""
        response = requests.get(f"{BASE_URL}/api/onchain/flows")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "data" in data
        
        flows = data["data"]
        assert "exchangeInflow24h" in flows
        assert "exchangeOutflow24h" in flows
        assert "stablecoinInflow24h" in flows
        assert "stablecoinOutflow24h" in flows
        assert flows.get("provider") in ["infura-lite+defillama", "paused"]

    def test_onchain_whales(self):
        """GET /api/onchain/whales returns large transfers with explorer links"""
        response = requests.get(f"{BASE_URL}/api/onchain/whales")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "data" in data
        
        whales = data["data"]
        assert "largeTransfers24h" in whales
        assert "topTransfers" in whales
        assert "totalWhaleVolume24h" in whales
        # topTransfers should be a list
        assert isinstance(whales["topTransfers"], list)

    def test_onchain_activity(self):
        """GET /api/onchain/activity returns DEX volumes, TVL, top pairs"""
        response = requests.get(f"{BASE_URL}/api/onchain/activity")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "data" in data
        
        activity = data["data"]
        assert "dexVolume24h" in activity
        assert "totalValueLocked" in activity
        assert "topPairs" in activity
        assert activity.get("provider") == "defillama"


# ═══════════════════════════════════════════════════════════════
# Admin Indexer Control Endpoints
# ═══════════════════════════════════════════════════════════════

class TestAdminIndexerControl:
    """Tests for /api/admin/indexer/* endpoints - indexer mode management"""

    def test_indexer_status(self):
        """GET /api/admin/indexer/status returns full indexer status"""
        response = requests.get(f"{BASE_URL}/api/admin/indexer/status")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        # Indexer state
        assert "indexer" in data
        indexer = data["indexer"]
        assert "mode" in indexer
        assert "runtimeStatus" in indexer
        assert indexer["runtimeStatus"] in ["RUNNING", "PAUSED"]
        
        # RPC pools
        assert "rpcPools" in data
        pools = data["rpcPools"]
        assert len(pools) > 0, "Should have at least one RPC pool"

    def test_indexer_mode_change(self):
        """POST /api/admin/indexer/mode changes indexer mode"""
        # Set to LIMITED
        response = requests.post(
            f"{BASE_URL}/api/admin/indexer/mode",
            json={"mode": "LIMITED"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("mode") == "LIMITED"

        # Set to STANDARD
        response2 = requests.post(
            f"{BASE_URL}/api/admin/indexer/mode",
            json={"mode": "STANDARD"},
            headers={"Content-Type": "application/json"}
        )
        assert response2.status_code == 200
        assert response2.json().get("mode") == "STANDARD"

    def test_indexer_pause_resume(self):
        """POST /api/admin/indexer/pause and /resume work correctly"""
        # Pause
        pause_response = requests.post(f"{BASE_URL}/api/admin/indexer/pause")
        assert pause_response.status_code == 200
        assert pause_response.json().get("paused") is True

        # Resume
        resume_response = requests.post(f"{BASE_URL}/api/admin/indexer/resume")
        assert resume_response.status_code == 200
        assert resume_response.json().get("paused") is False

    def test_indexer_invalid_mode(self):
        """POST /api/admin/indexer/mode with invalid mode returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/admin/indexer/mode",
            json={"mode": "INVALID_MODE"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400


# ═══════════════════════════════════════════════════════════════
# Admin V2 Routes (v10) - Overview/Engine/Governance tabs
# ═══════════════════════════════════════════════════════════════

class TestAdminV2RuntimeGovernance:
    """Tests for /api/v10/onchain-v2/admin/* endpoints"""

    def test_runtime_status(self):
        """GET /api/v10/onchain-v2/admin/runtime returns runtime status"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/admin/runtime")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        # Runtime fields
        assert "enabled" in data
        assert "provider" in data
        assert "rpcHealthy" in data
        assert "latestBlock" in data
        assert data["latestBlock"] > 20000000, "Block should be > 20M"
        assert data["rpcConfigured"] is True

    def test_governance_state(self):
        """GET /api/v10/onchain-v2/admin/governance/state returns governance"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/admin/governance/state")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        # Active policy
        assert "activePolicy" in data
        policy = data["activePolicy"]
        assert "name" in policy
        assert "version" in policy
        assert "weights" in policy
        
        # Guardrails
        assert "guardrails" in data
        guardrails = data["guardrails"]
        assert "allPassed" in guardrails
        assert "driftPsi30d" in guardrails


# ═══════════════════════════════════════════════════════════════
# Admin Infrastructure Tab (RPC Pool)
# ═══════════════════════════════════════════════════════════════

class TestAdminInfrastructure:
    """Tests for Infrastructure tab endpoints"""

    def test_rpc_config(self):
        """GET /api/v10/onchain-v2/admin/rpc returns RPC pool with health"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/admin/rpc")
        assert response.status_code == 200
        data = response.json()
        
        # Config
        assert "config" in data
        assert "endpoints" in data["config"]
        endpoints = data["config"]["endpoints"]
        assert len(endpoints) == 5, "Should have 5 RPC providers"
        
        # Verify providers
        provider_names = [ep["provider"] for ep in endpoints]
        assert "Infura" in provider_names
        assert "LlamaRPC" in provider_names
        
        # Health
        assert "health" in data
        health = data["health"]
        assert "healthyCount" in health
        assert "totalCount" in health
        assert "avgLatencyMs" in health
        assert health["healthyCount"] >= 1, "At least 1 healthy provider"

    def test_snapshot_backfill_metrics(self):
        """GET /api/v10/onchain-v2/admin/snapshot/backfill-metrics returns metrics"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/admin/snapshot/backfill-metrics")
        assert response.status_code == 200
        data = response.json()
        
        assert "totalSnapshots" in data
        assert "backfillStatus" in data

    def test_force_snapshot_tick(self):
        """POST /api/v10/onchain-v2/admin/snapshot/tick forces snapshot"""
        response = requests.post(f"{BASE_URL}/api/v10/onchain-v2/admin/snapshot/tick")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True


# ═══════════════════════════════════════════════════════════════
# Admin Governance Tab
# ═══════════════════════════════════════════════════════════════

class TestAdminGovernance:
    """Tests for Governance tab endpoints"""

    def test_governance_audit(self):
        """GET /api/v10/onchain-v2/admin/governance/audit returns audit trail"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/admin/governance/audit?limit=30")
        assert response.status_code == 200
        data = response.json()
        assert "entries" in data
        assert isinstance(data["entries"], list)

    def test_active_policy(self):
        """GET /api/v10/onchain-v2/admin/governance/policy/active returns policy"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/admin/governance/policy/active")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "policy" in data
        
        policy = data["policy"]
        assert policy.get("name") == "default"
        assert "weights" in policy
        weights = policy["weights"]
        assert "networkWeight" in weights
        assert "flowWeight" in weights

    def test_rolling_stats(self):
        """GET /api/v10/onchain-v2/admin/rolling/{asset} returns rolling stats"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/admin/rolling/ETH?window=30d")
        assert response.status_code == 200
        data = response.json()
        assert "asset" in data
        assert "score" in data

    def test_drift_data(self):
        """GET /api/v10/onchain-v2/admin/drift/{asset} returns drift"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/admin/drift/ETH")
        assert response.status_code == 200
        data = response.json()
        assert "psi" in data
        assert "threshold" in data

    def test_policy_dry_run(self):
        """POST /api/v10/onchain-v2/admin/governance/policy/dry-run"""
        response = requests.post(
            f"{BASE_URL}/api/v10/onchain-v2/admin/governance/policy/dry-run",
            json={"weights": {}, "thresholds": {}}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True


# ═══════════════════════════════════════════════════════════════
# Research Tab (v6 observation) - MOCKED endpoints
# ═══════════════════════════════════════════════════════════════

class TestResearchTab:
    """Tests for Research tab endpoints - ML/Observation (MOCKED)"""

    def test_observation_stats(self):
        """GET /api/v6/observation/stats returns observation stats"""
        response = requests.get(f"{BASE_URL}/api/v6/observation/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "byDecision" in data

    def test_observation_metrics(self):
        """GET /api/v6/observation/metrics/summary returns metrics"""
        response = requests.get(f"{BASE_URL}/api/v6/observation/metrics/summary")
        assert response.status_code == 200
        data = response.json()
        assert "falseConfidenceRate" in data

    def test_ml_status_mocked(self):
        """GET /api/v6/observation/ml/status returns empty ML status (MOCKED)"""
        response = requests.get(f"{BASE_URL}/api/v6/observation/ml/status")
        assert response.status_code == 200
        data = response.json()
        # MOCKED - returns empty data
        assert data.get("loaded") is False
        assert data.get("version") == "0.0.0"

    def test_ml_train_mocked(self):
        """POST /api/v6/observation/ml/train returns not available (MOCKED)"""
        response = requests.post(f"{BASE_URL}/api/v6/observation/ml/train")
        assert response.status_code == 200
        data = response.json()
        assert "not available" in data.get("message", "").lower()


# ═══════════════════════════════════════════════════════════════
# Validation Tab (v7 validation) - MOCKED endpoints
# ═══════════════════════════════════════════════════════════════

class TestValidationTab:
    """Tests for Validation tab endpoints - (MOCKED)"""

    def test_validation_stats(self):
        """GET /api/v7/validation/stats returns validation stats"""
        response = requests.get(f"{BASE_URL}/api/v7/validation/stats")
        assert response.status_code == 200
        data = response.json()
        assert "validation" in data
        assert "kpis" in data
        assert "use_confirm_rate" in data["kpis"]
        assert "use_contradict_rate" in data["kpis"]

    def test_validation_contradictions(self):
        """GET /api/v7/validation/contradictions returns list"""
        response = requests.get(f"{BASE_URL}/api/v7/validation/contradictions?limit=20")
        assert response.status_code == 200
        data = response.json()
        assert "contradictions" in data
        assert isinstance(data["contradictions"], list)

    def test_validation_batch_mocked(self):
        """POST /api/v7/validation/batch returns not available (MOCKED)"""
        response = requests.post(f"{BASE_URL}/api/v7/validation/batch")
        assert response.status_code == 200
        data = response.json()
        assert "not available" in data.get("message", "").lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
