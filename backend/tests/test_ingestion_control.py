"""
Ingestion Control API Tests (P0.1)

Tests for:
- Health endpoints (GET /api/health/ingestion, GET /api/health/ingestion/simple)
- Status endpoints (GET /api/ingestion/status, GET /api/ingestion/chains, GET /api/ingestion/chains/:chain)
- Alert endpoints (GET /api/ingestion/alerts, GET /api/ingestion/alerts/stats)
- Replay guard endpoints (GET /api/ingestion/replay/stats, GET /api/ingestion/replay/failed)
- Admin endpoints (POST /api/admin/ingestion/init, pause, resume)
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

SUPPORTED_CHAINS = ['ETH', 'ARB', 'OP', 'BASE', 'POLY', 'BNB', 'AVAX', 'ZKSYNC', 'SCROLL', 'LINEA']


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestHealthEndpoints:
    """Health endpoint tests"""
    
    def test_health_ingestion_main(self, api_client):
        """GET /api/health/ingestion - main health endpoint"""
        response = api_client.get(f"{BASE_URL}/api/health/ingestion")
        assert response.status_code in [200, 503], f"Unexpected status: {response.status_code}"
        
        data = response.json()
        assert "ok" in data
        assert "status" in data
        assert data["status"] in ["HEALTHY", "WARNING", "CRITICAL", "UNKNOWN"]
        assert "timestamp" in data
        assert "chains" in data
        assert "summary" in data
        assert "alerts" in data
        
        # Verify summary structure
        summary = data["summary"]
        assert "healthy" in summary
        assert "warning" in summary
        assert "critical" in summary
        assert "unknown" in summary
        assert "totalLag" in summary
        assert "avgLag" in summary
        
        # Verify chains structure
        chains = data["chains"]
        for chain in SUPPORTED_CHAINS:
            assert chain in chains, f"Chain {chain} missing from health response"
            chain_health = chains[chain]
            assert "status" in chain_health
            assert "lag" in chain_health
            assert "minutesSinceSync" in chain_health
            assert "errorRate" in chain_health
            assert "issues" in chain_health
    
    def test_health_ingestion_simple(self, api_client):
        """GET /api/health/ingestion/simple - simplified health check"""
        response = api_client.get(f"{BASE_URL}/api/health/ingestion/simple")
        assert response.status_code in [200, 503]
        
        data = response.json()
        assert "ok" in data
        assert isinstance(data["ok"], bool)
        # reason is optional, only present when not healthy


class TestIngestionStatusEndpoints:
    """Ingestion status endpoint tests"""
    
    def test_ingestion_status_full(self, api_client):
        """GET /api/ingestion/status - full ingestion status"""
        response = api_client.get(f"{BASE_URL}/api/ingestion/status")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "data" in data
        
        status_data = data["data"]
        assert "chains" in status_data
        assert "summary" in status_data
        assert "replayStats" in status_data
        assert "rpcBudget" in status_data
        
        # Verify chains array
        chains = status_data["chains"]
        assert len(chains) == 10, f"Expected 10 chains, got {len(chains)}"
        for chain in chains:
            assert "chain" in chain
            assert "status" in chain
            assert "lastSyncedBlock" in chain
            assert "lastHeadBlock" in chain
            assert "lag" in chain
            assert "totalEvents" in chain
        
        # Verify summary
        summary = status_data["summary"]
        assert summary["totalChains"] == 10
        assert "activeChains" in summary
        assert "pausedChains" in summary
        assert "totalLag" in summary
        assert "totalEvents" in summary
        
        # Verify replay stats
        replay = status_data["replayStats"]
        assert "done" in replay
        assert "inProgress" in replay
        assert "failed" in replay
        assert "failedRangesUnresolved" in replay
        
        # Verify RPC budget
        rpc_budget = status_data["rpcBudget"]
        assert len(rpc_budget) == 10
        for budget in rpc_budget:
            assert "chain" in budget
            assert "requestsThisMinute" in budget
            assert "maxRequestsPerMinute" in budget
            assert "currentConcurrent" in budget
            assert "maxConcurrent" in budget
            assert "consecutiveErrors" in budget
            assert "isPaused" in budget
    
    def test_ingestion_chains_list(self, api_client):
        """GET /api/ingestion/chains - list all chain states"""
        response = api_client.get(f"{BASE_URL}/api/ingestion/chains")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "data" in data
        
        chains_data = data["data"]
        assert "chains" in chains_data
        assert "supported" in chains_data
        
        # Verify supported chains
        assert chains_data["supported"] == SUPPORTED_CHAINS
        
        # Verify chain states
        chains = chains_data["chains"]
        assert len(chains) == 10
        for chain in chains:
            assert "chain" in chain
            assert "chainId" in chain
            assert "lastSyncedBlock" in chain
            assert "lastHeadBlock" in chain
            assert "status" in chain
            assert chain["status"] in ["OK", "DEGRADED", "PAUSED", "ERROR"]
            assert "errorCount" in chain
            assert "consecutiveErrors" in chain
            assert "totalEventsIngested" in chain
    
    def test_ingestion_chain_specific_eth(self, api_client):
        """GET /api/ingestion/chains/ETH - get specific chain state"""
        response = api_client.get(f"{BASE_URL}/api/ingestion/chains/ETH")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "data" in data
        
        chain_data = data["data"]
        assert "state" in chain_data
        assert "rpcBudget" in chain_data
        assert "lag" in chain_data
        
        # Verify state
        state = chain_data["state"]
        assert state["chain"] == "ETH"
        assert state["chainId"] == 1
        
        # Verify RPC budget
        budget = chain_data["rpcBudget"]
        assert budget["chain"] == "ETH"
        assert budget["maxRequestsPerMinute"] == 60  # ETH has lower limit
        assert budget["maxConcurrent"] == 3
    
    def test_ingestion_chain_specific_arb(self, api_client):
        """GET /api/ingestion/chains/ARB - get Arbitrum chain state"""
        response = api_client.get(f"{BASE_URL}/api/ingestion/chains/ARB")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        
        chain_data = data["data"]
        state = chain_data["state"]
        assert state["chain"] == "ARB"
        assert state["chainId"] == 42161
        
        budget = chain_data["rpcBudget"]
        assert budget["maxRequestsPerMinute"] == 120  # ARB has higher limit
        assert budget["maxConcurrent"] == 5
    
    def test_ingestion_chain_case_insensitive(self, api_client):
        """GET /api/ingestion/chains/:chain - case insensitive"""
        response = api_client.get(f"{BASE_URL}/api/ingestion/chains/eth")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert data["data"]["state"]["chain"] == "ETH"
    
    def test_ingestion_chain_not_found(self, api_client):
        """GET /api/ingestion/chains/:chain - 404 for unknown chain"""
        response = api_client.get(f"{BASE_URL}/api/ingestion/chains/UNKNOWN")
        assert response.status_code == 404
        
        data = response.json()
        assert data["ok"] is False
        assert data["error"] == "CHAIN_NOT_FOUND"


class TestAlertEndpoints:
    """Alert endpoint tests"""
    
    def test_alerts_list(self, api_client):
        """GET /api/ingestion/alerts - get active alerts"""
        response = api_client.get(f"{BASE_URL}/api/ingestion/alerts")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "data" in data
        
        alerts_data = data["data"]
        assert "alerts" in alerts_data
        assert "count" in alerts_data
        assert isinstance(alerts_data["alerts"], list)
        assert alerts_data["count"] == len(alerts_data["alerts"])
    
    def test_alerts_filter_by_chain(self, api_client):
        """GET /api/ingestion/alerts?chain=ETH - filter by chain"""
        response = api_client.get(f"{BASE_URL}/api/ingestion/alerts?chain=ETH")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        # All returned alerts should be for ETH chain
        for alert in data["data"]["alerts"]:
            assert alert["chain"] == "ETH"
    
    def test_alerts_filter_by_severity(self, api_client):
        """GET /api/ingestion/alerts?severity=CRITICAL - filter by severity"""
        response = api_client.get(f"{BASE_URL}/api/ingestion/alerts?severity=CRITICAL")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        # All returned alerts should be CRITICAL
        for alert in data["data"]["alerts"]:
            assert alert["severity"] == "CRITICAL"
    
    def test_alerts_stats(self, api_client):
        """GET /api/ingestion/alerts/stats - alert statistics"""
        response = api_client.get(f"{BASE_URL}/api/ingestion/alerts/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "data" in data
        
        stats = data["data"]
        assert "active" in stats
        assert "resolved" in stats
        assert "last24h" in stats
        
        active = stats["active"]
        assert "total" in active
        assert "critical" in active
        assert "warning" in active


class TestReplayGuardEndpoints:
    """Replay guard endpoint tests"""
    
    def test_replay_stats(self, api_client):
        """GET /api/ingestion/replay/stats - replay guard statistics"""
        response = api_client.get(f"{BASE_URL}/api/ingestion/replay/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "data" in data
        
        stats = data["data"]
        assert "total" in stats
        assert "done" in stats
        assert "inProgress" in stats
        assert "failed" in stats
        assert "partial" in stats
        assert "failedRangesUnresolved" in stats
        
        # All values should be non-negative integers
        for key, value in stats.items():
            assert isinstance(value, int)
            assert value >= 0
    
    def test_replay_failed_ranges(self, api_client):
        """GET /api/ingestion/replay/failed - failed ranges"""
        response = api_client.get(f"{BASE_URL}/api/ingestion/replay/failed")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "data" in data
        
        failed_data = data["data"]
        assert "ranges" in failed_data
        assert "count" in failed_data
        assert isinstance(failed_data["ranges"], list)
        assert failed_data["count"] == len(failed_data["ranges"])
    
    def test_replay_failed_filter_by_chain(self, api_client):
        """GET /api/ingestion/replay/failed?chain=ETH - filter by chain"""
        response = api_client.get(f"{BASE_URL}/api/ingestion/replay/failed?chain=ETH")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        # All returned ranges should be for ETH chain
        for range_entry in data["data"]["ranges"]:
            assert range_entry["chain"] == "ETH"


class TestAdminEndpoints:
    """Admin endpoint tests"""
    
    def test_admin_init_chains(self, api_client):
        """POST /api/admin/ingestion/init - initialize chains (idempotent)"""
        response = api_client.post(f"{BASE_URL}/api/admin/ingestion/init", json={})
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "message" in data
        assert "10 chains" in data["message"]
    
    def test_admin_pause_chain(self, api_client):
        """POST /api/admin/ingestion/pause/:chain - pause chain"""
        response = api_client.post(
            f"{BASE_URL}/api/admin/ingestion/pause/ARB",
            json={"reason": "Test pause from pytest"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert data["data"]["status"] == "PAUSED"
        assert data["data"]["pauseReason"] == "Test pause from pytest"
        assert "Chain ARB paused" in data["message"]
        
        # Verify chain is paused
        verify_response = api_client.get(f"{BASE_URL}/api/ingestion/chains/ARB")
        verify_data = verify_response.json()
        assert verify_data["data"]["state"]["status"] == "PAUSED"
        assert verify_data["data"]["rpcBudget"]["isPaused"] is True
    
    def test_admin_resume_chain(self, api_client):
        """POST /api/admin/ingestion/resume/:chain - resume chain"""
        # First ensure chain is paused
        api_client.post(
            f"{BASE_URL}/api/admin/ingestion/pause/ARB",
            json={"reason": "Pause before resume test"}
        )
        
        # Now resume (must send empty json body for Fastify)
        response = api_client.post(f"{BASE_URL}/api/admin/ingestion/resume/ARB", json={})
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert data["data"]["status"] == "OK"
        assert "Chain ARB resumed" in data["message"]
        
        # Verify chain is resumed
        verify_response = api_client.get(f"{BASE_URL}/api/ingestion/chains/ARB")
        verify_data = verify_response.json()
        assert verify_data["data"]["state"]["status"] == "OK"
        assert verify_data["data"]["rpcBudget"]["isPaused"] is False
    
    def test_admin_pause_unknown_chain(self, api_client):
        """POST /api/admin/ingestion/pause/:chain - error for unknown chain"""
        response = api_client.post(
            f"{BASE_URL}/api/admin/ingestion/pause/UNKNOWN",
            json={"reason": "Test"}
        )
        # Can be 500 or 520 (cloudflare error) depending on how error is handled
        assert response.status_code in [500, 520]
        
        data = response.json()
        assert data["ok"] is False
    
    def test_admin_pause_without_reason(self, api_client):
        """POST /api/admin/ingestion/pause/:chain - default reason when not provided"""
        response = api_client.post(
            f"{BASE_URL}/api/admin/ingestion/pause/OP",
            json={}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert data["data"]["pauseReason"] == "Manual pause via API"
        
        # Resume for cleanup
        api_client.post(f"{BASE_URL}/api/admin/ingestion/resume/OP", json={})


class TestChainConfigValidation:
    """Validate chain configuration"""
    
    def test_all_chains_have_correct_chain_ids(self, api_client):
        """Verify all chains have correct chainId"""
        expected_chain_ids = {
            "ETH": 1,
            "ARB": 42161,
            "OP": 10,
            "BASE": 8453,
            "POLY": 137,
            "BNB": 56,
            "AVAX": 43114,
            "ZKSYNC": 324,
            "SCROLL": 534352,
            "LINEA": 59144
        }
        
        response = api_client.get(f"{BASE_URL}/api/ingestion/chains")
        data = response.json()
        
        for chain_state in data["data"]["chains"]:
            chain = chain_state["chain"]
            expected_id = expected_chain_ids.get(chain)
            assert chain_state["chainId"] == expected_id, f"Chain {chain} has wrong chainId"
    
    def test_rpc_budget_limits_per_chain(self, api_client):
        """Verify RPC budget limits are correctly configured per chain"""
        expected_limits = {
            "ETH": {"maxRequestsPerMinute": 60, "maxConcurrent": 3},
            "ARB": {"maxRequestsPerMinute": 120, "maxConcurrent": 5},
            "OP": {"maxRequestsPerMinute": 120, "maxConcurrent": 5},
            "BASE": {"maxRequestsPerMinute": 120, "maxConcurrent": 5},
            "POLY": {"maxRequestsPerMinute": 100, "maxConcurrent": 5},
            "BNB": {"maxRequestsPerMinute": 100, "maxConcurrent": 5},
            "AVAX": {"maxRequestsPerMinute": 100, "maxConcurrent": 5},
            "ZKSYNC": {"maxRequestsPerMinute": 60, "maxConcurrent": 3},
            "SCROLL": {"maxRequestsPerMinute": 60, "maxConcurrent": 3},
            "LINEA": {"maxRequestsPerMinute": 60, "maxConcurrent": 3}
        }
        
        response = api_client.get(f"{BASE_URL}/api/ingestion/status")
        data = response.json()
        
        for budget in data["data"]["rpcBudget"]:
            chain = budget["chain"]
            expected = expected_limits.get(chain)
            assert budget["maxRequestsPerMinute"] == expected["maxRequestsPerMinute"], \
                f"Chain {chain} has wrong maxRequestsPerMinute"
            assert budget["maxConcurrent"] == expected["maxConcurrent"], \
                f"Chain {chain} has wrong maxConcurrent"


class TestHealthStatusCalculation:
    """Test health status calculation logic"""
    
    def test_health_summary_counts_match(self, api_client):
        """Verify health summary counts match chain statuses"""
        response = api_client.get(f"{BASE_URL}/api/health/ingestion")
        data = response.json()
        
        chains = data["chains"]
        summary = data["summary"]
        
        # Count statuses manually
        healthy_count = sum(1 for c in chains.values() if c["status"] == "HEALTHY")
        warning_count = sum(1 for c in chains.values() if c["status"] == "WARNING")
        critical_count = sum(1 for c in chains.values() if c["status"] == "CRITICAL")
        unknown_count = sum(1 for c in chains.values() if c["status"] == "UNKNOWN")
        
        assert summary["healthy"] == healthy_count
        assert summary["warning"] == warning_count
        assert summary["critical"] == critical_count
        assert summary["unknown"] == unknown_count
    
    def test_overall_status_reflects_worst_chain(self, api_client):
        """Verify overall status reflects worst chain status"""
        response = api_client.get(f"{BASE_URL}/api/health/ingestion")
        data = response.json()
        
        chains = data["chains"]
        overall = data["status"]
        
        has_critical = any(c["status"] == "CRITICAL" for c in chains.values())
        has_warning = any(c["status"] == "WARNING" for c in chains.values())
        
        if has_critical:
            assert overall == "CRITICAL"
        elif has_warning:
            assert overall == "WARNING"
        else:
            assert overall in ["HEALTHY", "UNKNOWN"]


class TestPauseResumeWorkflow:
    """Test complete pause/resume workflow"""
    
    def test_pause_resume_cycle(self, api_client):
        """Test complete pause -> verify -> resume -> verify cycle"""
        chain = "BASE"
        
        # 1. Pause chain
        pause_response = api_client.post(
            f"{BASE_URL}/api/admin/ingestion/pause/{chain}",
            json={"reason": "Workflow test"}
        )
        assert pause_response.status_code == 200
        
        # 2. Verify paused state
        state_response = api_client.get(f"{BASE_URL}/api/ingestion/chains/{chain}")
        state_data = state_response.json()
        assert state_data["data"]["state"]["status"] == "PAUSED"
        assert state_data["data"]["rpcBudget"]["isPaused"] is True
        
        # 3. Verify health shows warning for paused chain
        health_response = api_client.get(f"{BASE_URL}/api/health/ingestion")
        health_data = health_response.json()
        assert health_data["chains"][chain]["status"] == "WARNING"
        assert any("paused" in issue.lower() for issue in health_data["chains"][chain]["issues"])
        
        # 4. Resume chain (must send empty json body for Fastify)
        resume_response = api_client.post(f"{BASE_URL}/api/admin/ingestion/resume/{chain}", json={})
        assert resume_response.status_code == 200
        
        # 5. Verify resumed state
        state_response = api_client.get(f"{BASE_URL}/api/ingestion/chains/{chain}")
        state_data = state_response.json()
        assert state_data["data"]["state"]["status"] == "OK"
        assert state_data["data"]["rpcBudget"]["isPaused"] is False
        
        # 6. Verify health shows healthy
        health_response = api_client.get(f"{BASE_URL}/api/health/ingestion")
        health_data = health_response.json()
        assert health_data["chains"][chain]["status"] == "HEALTHY"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
