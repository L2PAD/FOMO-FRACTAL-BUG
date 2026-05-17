"""
Phase 2 Data Pipeline Stabilization Tests
==========================================
Testing Block 2.1-2.5 features:
- Block 2.1: Enhanced scheduler with heartbeat (tickCount, successCount, errorCount, lastError, health)
- Block 2.2: Data Quality Flags (unified flag enum, quality/evidence in AltFlow)
- Block 2.3: Pricing Hardening (priceAgeMs, stale detection)
- Block 2.4: Pool Scoring (reasons array)
- Block 2.5: AltFlow Integrity Gate (NaN/Inf guard, min evidence policy, strong-only gate)
"""

import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestBlock21JobSchedulerHeartbeat:
    """Block 2.1: Enhanced scheduler with heartbeat data"""

    def test_system_jobs_status_returns_jobs_array(self):
        """Verify /api/system/jobs/status returns jobs array"""
        response = requests.get(f"{BASE_URL}/api/system/jobs/status", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert "jobs" in data, "Response should have 'jobs' array"
        assert isinstance(data["jobs"], list), "jobs should be an array"
        assert len(data["jobs"]) > 0, "Should have at least one job registered"

    def test_jobs_have_tick_count(self):
        """Verify jobs have tickCount field"""
        response = requests.get(f"{BASE_URL}/api/system/jobs/status", timeout=30)
        data = response.json()
        
        for job in data["jobs"]:
            assert "tickCount" in job, f"Job {job.get('name')} missing tickCount"
            assert isinstance(job["tickCount"], int), f"tickCount should be integer"

    def test_jobs_have_success_count(self):
        """Verify jobs have successCount field"""
        response = requests.get(f"{BASE_URL}/api/system/jobs/status", timeout=30)
        data = response.json()
        
        for job in data["jobs"]:
            assert "successCount" in job, f"Job {job.get('name')} missing successCount"
            assert isinstance(job["successCount"], int), f"successCount should be integer"

    def test_jobs_have_error_count(self):
        """Verify jobs have errorCount field"""
        response = requests.get(f"{BASE_URL}/api/system/jobs/status", timeout=30)
        data = response.json()
        
        for job in data["jobs"]:
            assert "errorCount" in job, f"Job {job.get('name')} missing errorCount"
            assert isinstance(job["errorCount"], int), f"errorCount should be integer"

    def test_jobs_have_last_error(self):
        """Verify jobs have lastError field (nullable)"""
        response = requests.get(f"{BASE_URL}/api/system/jobs/status", timeout=30)
        data = response.json()
        
        for job in data["jobs"]:
            assert "lastError" in job, f"Job {job.get('name')} missing lastError"
            # lastError can be null or string

    def test_jobs_have_health_status(self):
        """Verify jobs have health field with valid status"""
        response = requests.get(f"{BASE_URL}/api/system/jobs/status", timeout=30)
        data = response.json()
        
        valid_health_values = ['ok', 'degraded', 'critical', 'idle']
        for job in data["jobs"]:
            assert "health" in job, f"Job {job.get('name')} missing health"
            assert job["health"] in valid_health_values, f"Invalid health value: {job['health']}"

    def test_jobs_status_has_summary(self):
        """Verify response has summary with counts"""
        response = requests.get(f"{BASE_URL}/api/system/jobs/status", timeout=30)
        data = response.json()
        
        assert "summary" in data
        assert "total" in data["summary"]
        assert "healthy" in data["summary"]
        assert "degraded" in data["summary"]
        assert "critical" in data["summary"]
        assert "idle" in data["summary"]


class TestBlock21HealthOnchain:
    """Block 2.1: Health/onchain endpoint with subsystems"""

    def test_health_onchain_returns_ok(self):
        """Verify /api/health/onchain returns valid response"""
        response = requests.get(f"{BASE_URL}/api/health/onchain", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert "ok" in data
        assert "status" in data
        assert "mongo" in data
        assert "timestamp" in data
        assert "subsystems" in data

    def test_health_onchain_has_subsystems(self):
        """Verify subsystems structure"""
        response = requests.get(f"{BASE_URL}/api/health/onchain", timeout=30)
        data = response.json()
        
        expected_subsystems = ['ingestion', 'signals', 'actors', 'scoring', 'snapshots']
        for subsystem in expected_subsystems:
            assert subsystem in data["subsystems"], f"Missing subsystem: {subsystem}"

    def test_subsystem_jobs_have_health_status(self):
        """Verify each subsystem job has health status"""
        response = requests.get(f"{BASE_URL}/api/health/onchain", timeout=30)
        data = response.json()
        
        for subsystem_name, subsystem in data["subsystems"].items():
            for job_name, job in subsystem.items():
                assert "status" in job, f"Job {job_name} missing status"
                assert "running" in job, f"Job {job_name} missing running"


class TestBlock22AltFlowQualityEvidence:
    """Block 2.2: Data Quality Flags - quality/evidence/flags in AltFlow"""

    def test_altflow_returns_data(self):
        """Verify AltFlow endpoint returns data"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/market/altflow",
            params={"window": "24h", "network": "ethereum"},
            timeout=30
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True

    def test_altflow_items_have_quality(self):
        """Verify AltFlow items have quality object"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/market/altflow",
            params={"window": "24h", "network": "ethereum"},
            timeout=30
        )
        data = response.json()
        
        # Check topAccumulation items
        for item in data.get("topAccumulation", []):
            assert "quality" in item, f"Item {item.get('symbol')} missing quality"
            assert "priceSource" in item["quality"]
            assert "poolStatus" in item["quality"]
            assert "poolScore" in item["quality"]

    def test_altflow_items_have_evidence(self):
        """Verify AltFlow items have evidence object"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/market/altflow",
            params={"window": "24h", "network": "ethereum"},
            timeout=30
        )
        data = response.json()
        
        for item in data.get("topAccumulation", []):
            assert "evidence" in item, f"Item {item.get('symbol')} missing evidence"
            assert "trades" in item["evidence"]
            assert "uniquePools" in item["evidence"]
            assert "spanHours" in item["evidence"]
            assert "pricedShare" in item["evidence"]

    def test_altflow_flags_are_structured(self):
        """Verify flags are structured objects with code and severity"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/market/altflow",
            params={"window": "24h", "network": "ethereum"},
            timeout=30
        )
        data = response.json()
        
        all_items = data.get("topAccumulation", []) + data.get("topDistribution", [])
        for item in all_items:
            assert "flags" in item
            for flag in item["flags"]:
                assert isinstance(flag, dict), f"Flag should be object, got {type(flag)}"
                assert "code" in flag, f"Flag missing 'code'"
                assert "severity" in flag, f"Flag missing 'severity'"

    def test_altflow_items_have_components(self):
        """Verify AltFlow items have components object"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/market/altflow",
            params={"window": "24h", "network": "ethereum"},
            timeout=30
        )
        data = response.json()
        
        for item in data.get("topAccumulation", []):
            assert "components" in item, f"Item {item.get('symbol')} missing components"
            assert "dexNetUsd" in item["components"]
            assert "cexNetUsd" in item["components"]


class TestBlock22DataQualityFlagCodes:
    """Block 2.2: Unified flag enum validation"""

    def test_flags_have_valid_severity(self):
        """Verify flags use valid severity values"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/market/altflow",
            params={"window": "24h", "network": "ethereum"},
            timeout=30
        )
        data = response.json()
        
        valid_severities = ['INFO', 'WARN', 'CRITICAL']
        all_items = data.get("topAccumulation", []) + data.get("topDistribution", [])
        for item in all_items:
            for flag in item.get("flags", []):
                assert flag["severity"] in valid_severities, f"Invalid severity: {flag['severity']}"


class TestBlock23PricingHardening:
    """Block 2.3: Pricing hardening - priceAgeMs, isStale"""

    def test_altflow_quality_has_price_source(self):
        """Verify quality.priceSource is present"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/market/altflow",
            params={"window": "24h", "network": "ethereum"},
            timeout=30
        )
        data = response.json()
        
        valid_price_sources = ['CHAINLINK', 'TWAP', 'DEX_VWAP', 'NONE']
        for item in data.get("topAccumulation", []):
            assert item["quality"]["priceSource"] in valid_price_sources


class TestBlock24PoolScoring:
    """Block 2.4: Pool Scoring with reasons array"""

    def test_altflow_quality_has_pool_score(self):
        """Verify quality.poolScore is numeric"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/market/altflow",
            params={"window": "24h", "network": "ethereum"},
            timeout=30
        )
        data = response.json()
        
        for item in data.get("topAccumulation", []):
            pool_score = item["quality"]["poolScore"]
            assert isinstance(pool_score, (int, float)), f"poolScore should be numeric"
            assert 0 <= pool_score <= 100, f"poolScore out of range: {pool_score}"


class TestBlock25IntegrityGate:
    """Block 2.5: AltFlow Integrity Gate - confidence and strong-only"""

    def test_altflow_items_have_confidence(self):
        """Verify confidence is present and valid"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/market/altflow",
            params={"window": "24h", "network": "ethereum"},
            timeout=30
        )
        data = response.json()
        
        for item in data.get("topAccumulation", []):
            assert "confidence" in item
            assert 0 <= item["confidence"] <= 1, f"Confidence out of range: {item['confidence']}"

    def test_low_confidence_has_warning_flag(self):
        """Verify items with low confidence have LOW_CONFIDENCE flag"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/market/altflow",
            params={"window": "24h", "network": "ethereum"},
            timeout=30
        )
        data = response.json()
        
        all_items = data.get("topAccumulation", []) + data.get("topDistribution", [])
        for item in all_items:
            if item["confidence"] < 0.25:
                flag_codes = [f["code"] for f in item.get("flags", [])]
                assert "LOW_CONFIDENCE" in flag_codes, f"Item with confidence {item['confidence']} missing LOW_CONFIDENCE flag"


class TestAltFlowMeta:
    """Test AltFlow metadata fields"""

    def test_altflow_has_meta(self):
        """Verify response has meta object"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/market/altflow",
            params={"window": "24h", "network": "ethereum"},
            timeout=30
        )
        data = response.json()
        
        assert "meta" in data
        assert "tokenCount" in data["meta"]
        assert "avgConfidence" in data["meta"]

    def test_altflow_7d_window(self):
        """Verify 7d window also works"""
        response = requests.get(
            f"{BASE_URL}/api/v10/onchain-v2/market/altflow",
            params={"window": "7d", "network": "ethereum"},
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("window") == "7d"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
