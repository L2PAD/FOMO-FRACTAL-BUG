"""
Y1 - Exchange Admin Control Plane API Tests
============================================

Testing all provider admin operations (enable/disable/priority/test/reset)
and job operations (start/stop/config/run-once).

Endpoints tested:
- GET    /api/v10/exchange/admin/providers
- GET    /api/v10/exchange/admin/providers/:id
- PATCH  /api/v10/exchange/admin/providers/:id
- POST   /api/v10/exchange/admin/providers/:id/test
- POST   /api/v10/exchange/admin/providers/:id/reset
- GET    /api/v10/exchange/admin/jobs
- GET    /api/v10/exchange/admin/jobs/:id
- POST   /api/v10/exchange/admin/jobs/:id/start
- POST   /api/v10/exchange/admin/jobs/:id/stop
- PATCH  /api/v10/exchange/admin/jobs/:id/config
- POST   /api/v10/exchange/admin/jobs/:id/run-once
- GET    /api/v10/exchange/admin/health
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
ADMIN_BASE = f"{BASE_URL}/api/v10/exchange/admin"

# Known job IDs from jobs.registry.ts
JOB_IDS = [
    'exchangeTick',
    'whaleIngest',
    'indicatorCalculation',
    'regimeDetection',
    'patternDetection',
    'observationPersist'
]


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    # Don't set Content-Type globally - set it per request when needed
    return session


def post_json(session, url, json_data=None):
    """Helper to send POST with proper headers"""
    if json_data is None:
        # POST without body - don't set Content-Type
        return session.post(url)
    else:
        return session.post(url, json=json_data)


def patch_json(session, url, json_data):
    """Helper to send PATCH with JSON"""
    return session.patch(url, json=json_data)


# ═══════════════════════════════════════════════════════════════
# PROVIDER ADMIN TESTS
# ═══════════════════════════════════════════════════════════════

class TestProviderList:
    """GET /api/v10/exchange/admin/providers - list all providers"""
    
    def test_list_providers_returns_ok(self, api_client):
        """List providers endpoint returns ok response"""
        response = api_client.get(f"{ADMIN_BASE}/providers")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "providers" in data
        assert isinstance(data["providers"], list)
        print(f"Found {len(data['providers'])} providers")
    
    def test_list_providers_have_required_fields(self, api_client):
        """Each provider has required admin fields"""
        response = api_client.get(f"{ADMIN_BASE}/providers")
        assert response.status_code == 200
        
        data = response.json()
        providers = data["providers"]
        
        for provider in providers:
            assert "id" in provider, f"Provider missing 'id': {provider}"
            assert "enabled" in provider, f"Provider missing 'enabled': {provider}"
            assert "priority" in provider, f"Provider missing 'priority': {provider}"
            assert "health" in provider, f"Provider missing 'health': {provider}"
            
            # Health sub-fields
            health = provider["health"]
            assert "status" in health, f"Health missing 'status': {health}"
            assert "errorCount" in health, f"Health missing 'errorCount': {health}"
            
            print(f"Provider {provider['id']}: enabled={provider['enabled']}, priority={provider['priority']}, status={health['status']}")


class TestProviderGet:
    """GET /api/v10/exchange/admin/providers/:id - get provider details"""
    
    def test_get_mock_provider_returns_details(self, api_client):
        """Get MOCK provider details"""
        response = api_client.get(f"{ADMIN_BASE}/providers/MOCK")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "provider" in data
        
        provider = data["provider"]
        assert provider["id"] == "MOCK"
        assert isinstance(provider["enabled"], bool)
        assert isinstance(provider["priority"], int)
        assert "health" in provider
        print(f"MOCK provider details: enabled={provider['enabled']}, priority={provider['priority']}")
    
    def test_get_binance_provider_returns_details(self, api_client):
        """Get BINANCE_USDM provider details"""
        response = api_client.get(f"{ADMIN_BASE}/providers/BINANCE_USDM")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        provider = data["provider"]
        assert provider["id"] == "BINANCE_USDM"
        print(f"BINANCE_USDM provider details: enabled={provider['enabled']}, priority={provider['priority']}")
    
    def test_get_unknown_provider_returns_404(self, api_client):
        """Unknown provider returns 404"""
        response = api_client.get(f"{ADMIN_BASE}/providers/UNKNOWN_PROVIDER")
        assert response.status_code == 404
        
        data = response.json()
        assert data.get("ok") is False
        assert "error" in data
        print(f"Unknown provider error: {data['error']}")


class TestProviderPatch:
    """PATCH /api/v10/exchange/admin/providers/:id - update provider config"""
    
    def test_patch_provider_priority(self, api_client):
        """Update provider priority"""
        # First get current state
        current = api_client.get(f"{ADMIN_BASE}/providers/MOCK").json()
        original_priority = current["provider"]["priority"]
        
        # Update priority
        new_priority = original_priority + 5
        response = api_client.patch(
            f"{ADMIN_BASE}/providers/MOCK",
            json={"priority": new_priority}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert data["provider"]["priority"] == new_priority
        print(f"Priority updated: {original_priority} -> {new_priority}")
        
        # Restore original
        api_client.patch(f"{ADMIN_BASE}/providers/MOCK", json={"priority": original_priority})
    
    def test_patch_provider_enabled(self, api_client):
        """Enable/disable provider"""
        # Make sure MOCK is enabled first
        api_client.patch(f"{ADMIN_BASE}/providers/MOCK", json={"enabled": True})
        
        # Disable MOCK (BINANCE_USDM should still be enabled)
        response = api_client.patch(
            f"{ADMIN_BASE}/providers/MOCK",
            json={"enabled": False}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert data["provider"]["enabled"] is False
        print("MOCK provider disabled")
        
        # Re-enable
        response = api_client.patch(
            f"{ADMIN_BASE}/providers/MOCK",
            json={"enabled": True}
        )
        assert response.status_code == 200
        assert response.json()["provider"]["enabled"] is True
        print("MOCK provider re-enabled")
    
    def test_patch_provider_negative_priority_rejected(self, api_client):
        """Negative priority is rejected"""
        response = api_client.patch(
            f"{ADMIN_BASE}/providers/MOCK",
            json={"priority": -5}
        )
        assert response.status_code == 400
        
        data = response.json()
        assert data.get("ok") is False
        assert "priority" in data.get("message", "").lower() or "negative" in data.get("message", "").lower()
        print(f"Negative priority rejected: {data['message']}")
    
    def test_patch_unknown_provider_returns_error(self, api_client):
        """Patch unknown provider returns error"""
        response = api_client.patch(
            f"{ADMIN_BASE}/providers/UNKNOWN",
            json={"priority": 10}
        )
        # Should return 400 or 404
        assert response.status_code in [400, 404]
        
        data = response.json()
        assert data.get("ok") is False
        print(f"Unknown provider patch error: {data['message']}")


class TestProviderTest:
    """POST /api/v10/exchange/admin/providers/:id/test - test provider connectivity"""
    
    def test_test_mock_provider_connectivity(self, api_client):
        """Test MOCK provider returns successful result"""
        response = api_client.post(
            f"{ADMIN_BASE}/providers/MOCK/test",
            json={"symbol": "BTCUSDT"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert data["providerId"] == "MOCK"
        assert data["symbol"] == "BTCUSDT"
        assert "latencyMs" in data
        assert data["latencyMs"] >= 0
        
        # Should have sample data
        if "sample" in data:
            sample = data["sample"]
            assert "mid" in sample or "bid" in sample or "ask" in sample
            print(f"MOCK test result: latency={data['latencyMs']}ms, sample={sample}")
        else:
            print(f"MOCK test result: latency={data['latencyMs']}ms")
    
    def test_test_binance_provider(self, api_client):
        """Test BINANCE_USDM provider (may return error due to regional restrictions)"""
        response = api_client.post(
            f"{ADMIN_BASE}/providers/BINANCE_USDM/test",
            json={"symbol": "BTCUSDT"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "providerId" in data
        assert data["providerId"] == "BINANCE_USDM"
        assert "latencyMs" in data
        
        if data.get("ok"):
            print(f"Binance test succeeded: latency={data['latencyMs']}ms")
        else:
            print(f"Binance test failed (expected due to 451): {data.get('error')}")
    
    def test_test_provider_default_symbol(self, api_client):
        """Test without symbol uses default BTCUSDT"""
        response = api_client.post(
            f"{ADMIN_BASE}/providers/MOCK/test",
            json={}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["symbol"] == "BTCUSDT"  # Default
        print(f"Default symbol test: {data['symbol']}")
    
    def test_test_unknown_provider_returns_error(self, api_client):
        """Test unknown provider returns error"""
        response = api_client.post(
            f"{ADMIN_BASE}/providers/UNKNOWN/test",
            json={}
        )
        assert response.status_code == 200  # Returns 200 with ok:false
        
        data = response.json()
        assert data.get("ok") is False
        assert "error" in data
        print(f"Unknown provider test error: {data['error']}")


class TestProviderReset:
    """POST /api/v10/exchange/admin/providers/:id/reset - reset circuit breaker"""
    
    def test_reset_mock_provider(self, api_client):
        """Reset MOCK provider circuit breaker"""
        response = post_json(api_client, f"{ADMIN_BASE}/providers/MOCK/reset")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "message" in data
        print(f"MOCK reset: {data['message']}")
    
    def test_reset_binance_provider(self, api_client):
        """Reset BINANCE_USDM provider circuit breaker"""
        response = post_json(api_client, f"{ADMIN_BASE}/providers/BINANCE_USDM/reset")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        print(f"BINANCE_USDM reset: {data['message']}")
    
    def test_reset_unknown_provider_returns_404(self, api_client):
        """Reset unknown provider returns 404"""
        response = post_json(api_client, f"{ADMIN_BASE}/providers/UNKNOWN/reset")
        assert response.status_code == 404
        
        data = response.json()
        assert data.get("ok") is False
        print(f"Unknown provider reset error: {data['message']}")


# ═══════════════════════════════════════════════════════════════
# JOB ADMIN TESTS
# ═══════════════════════════════════════════════════════════════

class TestJobList:
    """GET /api/v10/exchange/admin/jobs - list all jobs"""
    
    def test_list_jobs_returns_ok(self, api_client):
        """List jobs endpoint returns ok response"""
        response = api_client.get(f"{ADMIN_BASE}/jobs")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "jobs" in data
        assert isinstance(data["jobs"], list)
        
        # Should have 6 jobs defined
        assert len(data["jobs"]) >= 6
        print(f"Found {len(data['jobs'])} jobs")
    
    def test_list_jobs_have_required_fields(self, api_client):
        """Each job has required admin fields"""
        response = api_client.get(f"{ADMIN_BASE}/jobs")
        assert response.status_code == 200
        
        data = response.json()
        jobs = data["jobs"]
        
        for job in jobs:
            assert "id" in job, f"Job missing 'id': {job}"
            assert "displayName" in job, f"Job missing 'displayName': {job}"
            assert "enabled" in job, f"Job missing 'enabled': {job}"
            assert "running" in job, f"Job missing 'running': {job}"
            assert "status" in job, f"Job missing 'status': {job}"
            assert "scheduleMs" in job, f"Job missing 'scheduleMs': {job}"
            assert "config" in job, f"Job missing 'config': {job}"
            
            print(f"Job {job['id']}: enabled={job['enabled']}, running={job['running']}, status={job['status']}, scheduleMs={job['scheduleMs']}")
    
    def test_list_jobs_contains_expected_jobs(self, api_client):
        """Jobs list contains all expected job IDs"""
        response = api_client.get(f"{ADMIN_BASE}/jobs")
        assert response.status_code == 200
        
        data = response.json()
        job_ids = [j["id"] for j in data["jobs"]]
        
        for expected_id in JOB_IDS:
            assert expected_id in job_ids, f"Missing job: {expected_id}"
        print(f"All expected jobs present: {JOB_IDS}")


class TestJobGet:
    """GET /api/v10/exchange/admin/jobs/:id - get job details"""
    
    @pytest.mark.parametrize("job_id", JOB_IDS)
    def test_get_job_by_id(self, api_client, job_id):
        """Get each job by ID returns details"""
        response = api_client.get(f"{ADMIN_BASE}/jobs/{job_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "job" in data
        
        job = data["job"]
        assert job["id"] == job_id
        assert "displayName" in job
        assert "enabled" in job
        assert "running" in job
        assert "status" in job
        assert "config" in job
        
        # Config should have scheduleMs and trackedSymbols
        config = job["config"]
        assert "scheduleMs" in config
        assert "trackedSymbols" in config
        
        print(f"Job {job_id}: scheduleMs={config['scheduleMs']}, symbols={len(config['trackedSymbols'])}")
    
    def test_get_unknown_job_returns_404(self, api_client):
        """Unknown job returns 404"""
        response = api_client.get(f"{ADMIN_BASE}/jobs/unknownJob")
        assert response.status_code == 404
        
        data = response.json()
        assert data.get("ok") is False
        assert "error" in data
        print(f"Unknown job error: {data['error']}")


class TestJobStartStop:
    """POST /api/v10/exchange/admin/jobs/:id/start|stop - job lifecycle"""
    
    def test_start_job(self, api_client):
        """Start a job"""
        job_id = "exchangeTick"
        
        # First ensure job is stopped
        post_json(api_client, f"{ADMIN_BASE}/jobs/{job_id}/stop")
        
        # Start job
        response = post_json(api_client, f"{ADMIN_BASE}/jobs/{job_id}/start")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "message" in data
        print(f"Start job result: {data['message']}")
        
        # Verify running
        job_response = api_client.get(f"{ADMIN_BASE}/jobs/{job_id}")
        job = job_response.json()["job"]
        assert job["running"] is True
        assert job["status"] == "RUNNING"
    
    def test_stop_job(self, api_client):
        """Stop a running job"""
        job_id = "exchangeTick"
        
        # Ensure job is started first
        post_json(api_client, f"{ADMIN_BASE}/jobs/{job_id}/start")
        
        # Stop job
        response = post_json(api_client, f"{ADMIN_BASE}/jobs/{job_id}/stop")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        print(f"Stop job result: {data['message']}")
        
        # Verify stopped
        job_response = api_client.get(f"{ADMIN_BASE}/jobs/{job_id}")
        job = job_response.json()["job"]
        assert job["running"] is False
        assert job["status"] in ["STOPPED", "IDLE"]
    
    def test_start_already_running_job_returns_error(self, api_client):
        """Starting already running job returns error"""
        job_id = "whaleIngest"
        
        # Start job first
        post_json(api_client, f"{ADMIN_BASE}/jobs/{job_id}/start")
        
        # Try to start again
        response = post_json(api_client, f"{ADMIN_BASE}/jobs/{job_id}/start")
        assert response.status_code == 400
        
        data = response.json()
        assert data.get("ok") is False
        assert "already running" in data.get("message", "").lower()
        print(f"Already running error: {data['message']}")
        
        # Cleanup
        post_json(api_client, f"{ADMIN_BASE}/jobs/{job_id}/stop")
    
    def test_stop_not_running_job_returns_error(self, api_client):
        """Stopping non-running job returns error"""
        job_id = "indicatorCalculation"
        
        # Ensure job is stopped
        post_json(api_client, f"{ADMIN_BASE}/jobs/{job_id}/stop")
        
        # Try to stop again
        response = post_json(api_client, f"{ADMIN_BASE}/jobs/{job_id}/stop")
        assert response.status_code == 400
        
        data = response.json()
        assert data.get("ok") is False
        assert "not running" in data.get("message", "").lower()
        print(f"Not running error: {data['message']}")
    
    def test_start_unknown_job_returns_error(self, api_client):
        """Start unknown job returns error"""
        response = post_json(api_client, f"{ADMIN_BASE}/jobs/unknownJob/start")
        assert response.status_code == 400
        
        data = response.json()
        assert data.get("ok") is False
        print(f"Unknown job start error: {data['message']}")
    
    def test_stop_unknown_job_returns_error(self, api_client):
        """Stop unknown job returns error"""
        response = post_json(api_client, f"{ADMIN_BASE}/jobs/unknownJob/stop")
        assert response.status_code == 400
        
        data = response.json()
        assert data.get("ok") is False
        print(f"Unknown job stop error: {data['message']}")


class TestJobConfig:
    """PATCH /api/v10/exchange/admin/jobs/:id/config - update job config"""
    
    def test_patch_job_schedule_ms(self, api_client):
        """Update job scheduleMs"""
        job_id = "regimeDetection"
        
        # Get original config
        original = api_client.get(f"{ADMIN_BASE}/jobs/{job_id}").json()["job"]["config"]
        original_schedule = original["scheduleMs"]
        
        # Update
        new_schedule = 45000
        response = api_client.patch(
            f"{ADMIN_BASE}/jobs/{job_id}/config",
            json={"scheduleMs": new_schedule}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert data["config"]["scheduleMs"] == new_schedule
        print(f"Schedule updated: {original_schedule} -> {new_schedule}")
        
        # Restore original
        api_client.patch(
            f"{ADMIN_BASE}/jobs/{job_id}/config",
            json={"scheduleMs": original_schedule}
        )
    
    def test_patch_job_tracked_symbols(self, api_client):
        """Update job trackedSymbols"""
        job_id = "patternDetection"
        
        # Get original config
        original = api_client.get(f"{ADMIN_BASE}/jobs/{job_id}").json()["job"]["config"]
        original_symbols = original["trackedSymbols"]
        
        # Update
        new_symbols = ["BTCUSDT", "ETHUSDT"]
        response = api_client.patch(
            f"{ADMIN_BASE}/jobs/{job_id}/config",
            json={"trackedSymbols": new_symbols}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert data["config"]["trackedSymbols"] == new_symbols
        print(f"Symbols updated: {original_symbols} -> {new_symbols}")
        
        # Restore original
        api_client.patch(
            f"{ADMIN_BASE}/jobs/{job_id}/config",
            json={"trackedSymbols": original_symbols}
        )
    
    def test_patch_job_enabled(self, api_client):
        """Disable job via config patch"""
        job_id = "observationPersist"
        
        # Disable
        response = api_client.patch(
            f"{ADMIN_BASE}/jobs/{job_id}/config",
            json={"enabled": False}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        print(f"Job disabled: {data['config']['enabled']}")
        
        # Re-enable
        response = api_client.patch(
            f"{ADMIN_BASE}/jobs/{job_id}/config",
            json={"enabled": True}
        )
        assert response.status_code == 200
        assert response.json()["config"]["enabled"] is True
        print("Job re-enabled")
    
    def test_patch_unknown_job_returns_error(self, api_client):
        """Patch unknown job returns error"""
        response = api_client.patch(
            f"{ADMIN_BASE}/jobs/unknownJob/config",
            json={"scheduleMs": 30000}
        )
        assert response.status_code == 400
        
        data = response.json()
        assert data.get("ok") is False
        print(f"Unknown job config error: {data['message']}")


class TestJobRunOnce:
    """POST /api/v10/exchange/admin/jobs/:id/run-once - run job once (diagnostic)"""
    
    def test_run_once_exchange_tick(self, api_client):
        """Run exchangeTick job once"""
        response = api_client.post(
            f"{ADMIN_BASE}/jobs/exchangeTick/run-once",
            json={"symbol": "BTCUSDT"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "ok" in data
        assert data["jobId"] == "exchangeTick"
        assert "executionMs" in data
        assert data["executionMs"] >= 0
        print(f"exchangeTick run-once: ok={data['ok']}, executionMs={data['executionMs']}")
    
    def test_run_once_indicator_calculation(self, api_client):
        """Run indicatorCalculation job once"""
        response = api_client.post(
            f"{ADMIN_BASE}/jobs/indicatorCalculation/run-once",
            json={}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "ok" in data
        assert data["jobId"] == "indicatorCalculation"
        print(f"indicatorCalculation run-once: ok={data['ok']}, executionMs={data['executionMs']}")
    
    def test_run_once_with_custom_symbol(self, api_client):
        """Run job once with custom symbol"""
        response = api_client.post(
            f"{ADMIN_BASE}/jobs/regimeDetection/run-once",
            json={"symbol": "ETHUSDT"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["jobId"] == "regimeDetection"
        print(f"regimeDetection run-once (ETHUSDT): ok={data['ok']}")
    
    def test_run_once_unknown_job(self, api_client):
        """Run-once unknown job returns error in response"""
        response = api_client.post(
            f"{ADMIN_BASE}/jobs/unknownJob/run-once",
            json={}
        )
        assert response.status_code == 200  # Returns 200 with ok:false
        
        data = response.json()
        assert data.get("ok") is False
        assert "error" in data
        print(f"Unknown job run-once error: {data['error']}")


# ═══════════════════════════════════════════════════════════════
# HEALTH OVERVIEW TESTS
# ═══════════════════════════════════════════════════════════════

class TestHealthOverview:
    """GET /api/v10/exchange/admin/health - health overview with alerts"""
    
    def test_health_returns_overview(self, api_client):
        """Health endpoint returns complete overview"""
        response = api_client.get(f"{ADMIN_BASE}/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        # Check providers stats
        assert "providers" in data
        providers = data["providers"]
        assert "total" in providers
        assert "enabled" in providers
        assert "up" in providers
        assert "degraded" in providers
        assert "down" in providers
        print(f"Providers: total={providers['total']}, enabled={providers['enabled']}, up={providers['up']}")
    
    def test_health_has_jobs_stats(self, api_client):
        """Health endpoint includes jobs statistics"""
        response = api_client.get(f"{ADMIN_BASE}/health")
        assert response.status_code == 200
        
        data = response.json()
        
        assert "jobs" in data
        jobs = data["jobs"]
        assert "total" in jobs
        assert "running" in jobs
        assert "stopped" in jobs
        assert "error" in jobs
        print(f"Jobs: total={jobs['total']}, running={jobs['running']}, stopped={jobs['stopped']}, error={jobs['error']}")
    
    def test_health_has_data_status(self, api_client):
        """Health endpoint includes data status"""
        response = api_client.get(f"{ADMIN_BASE}/health")
        assert response.status_code == 200
        
        data = response.json()
        
        assert "dataStatus" in data
        status = data["dataStatus"]
        assert "mode" in status
        assert status["mode"] in ["LIVE", "MOCK", "MIXED"]
        assert "activeSymbols" in status
        print(f"Data status: mode={status['mode']}, activeSymbols={status['activeSymbols']}")
    
    def test_health_has_alerts(self, api_client):
        """Health endpoint includes alerts array"""
        response = api_client.get(f"{ADMIN_BASE}/health")
        assert response.status_code == 200
        
        data = response.json()
        
        assert "alerts" in data
        assert isinstance(data["alerts"], list)
        
        for alert in data["alerts"]:
            assert "level" in alert
            assert alert["level"] in ["INFO", "WARN", "ERROR"]
            assert "code" in alert
            assert "message" in alert
            assert "timestamp" in alert
            print(f"Alert: [{alert['level']}] {alert['code']}: {alert['message']}")
        
        if not data["alerts"]:
            print("No alerts (system healthy)")


# ═══════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════

class TestIntegrationFlows:
    """Test complete admin workflows"""
    
    def test_provider_disable_enable_flow(self, api_client):
        """Complete provider disable/enable cycle"""
        provider_id = "MOCK"
        
        # 1. Get initial state
        initial = api_client.get(f"{ADMIN_BASE}/providers/{provider_id}").json()["provider"]
        print(f"Initial: enabled={initial['enabled']}")
        
        # 2. Disable
        disable_resp = patch_json(
            api_client,
            f"{ADMIN_BASE}/providers/{provider_id}",
            {"enabled": False}
        )
        assert disable_resp.json()["ok"] is True
        print("Disabled MOCK provider")
        
        # 3. Verify disabled
        disabled = api_client.get(f"{ADMIN_BASE}/providers/{provider_id}").json()["provider"]
        assert disabled["enabled"] is False
        
        # 4. Re-enable
        enable_resp = patch_json(
            api_client,
            f"{ADMIN_BASE}/providers/{provider_id}",
            {"enabled": True}
        )
        assert enable_resp.json()["ok"] is True
        print("Re-enabled MOCK provider")
        
        # 5. Verify enabled
        enabled = api_client.get(f"{ADMIN_BASE}/providers/{provider_id}").json()["provider"]
        assert enabled["enabled"] is True
    
    def test_job_lifecycle_flow(self, api_client):
        """Complete job start/stop/config cycle"""
        job_id = "whaleIngest"
        
        # 1. Ensure stopped
        post_json(api_client, f"{ADMIN_BASE}/jobs/{job_id}/stop")
        
        # 2. Update config
        config_resp = patch_json(
            api_client,
            f"{ADMIN_BASE}/jobs/{job_id}/config",
            {"scheduleMs": 45000}
        )
        assert config_resp.json()["ok"] is True
        print(f"Config updated: scheduleMs=45000")
        
        # 3. Start job
        start_resp = post_json(api_client, f"{ADMIN_BASE}/jobs/{job_id}/start")
        assert start_resp.json()["ok"] is True
        print("Job started")
        
        # 4. Verify running
        job = api_client.get(f"{ADMIN_BASE}/jobs/{job_id}").json()["job"]
        assert job["running"] is True
        assert job["status"] == "RUNNING"
        
        # 5. Run once while running
        run_resp = post_json(
            api_client,
            f"{ADMIN_BASE}/jobs/{job_id}/run-once",
            {"symbol": "BTCUSDT"}
        )
        print(f"Run-once result: ok={run_resp.json().get('ok')}")
        
        # 6. Stop job
        stop_resp = post_json(api_client, f"{ADMIN_BASE}/jobs/{job_id}/stop")
        assert stop_resp.json()["ok"] is True
        print("Job stopped")
        
        # 7. Restore config
        patch_json(
            api_client,
            f"{ADMIN_BASE}/jobs/{job_id}/config",
            {"scheduleMs": 60000}
        )


# Cleanup fixture to stop any running jobs after tests
@pytest.fixture(scope="module", autouse=True)
def cleanup_jobs(api_client):
    """Stop all jobs after test module completes"""
    yield
    # Cleanup: stop all jobs
    for job_id in JOB_IDS:
        try:
            post_json(api_client, f"{ADMIN_BASE}/jobs/{job_id}/stop")
        except:
            pass
    print("Cleanup: All jobs stopped")
