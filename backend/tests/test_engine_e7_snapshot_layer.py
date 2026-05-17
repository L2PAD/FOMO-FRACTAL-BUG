"""
E7: Snapshot Intelligence Layer Tests
======================================
Tests for background snapshot workers, snapshot-served API responses,
history endpoints, and collection verification.
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestEngineContextSnapshot:
    """Tests for GET /api/engine/context served from snapshot"""

    def test_context_returns_ok(self):
        """API returns ok=true"""
        response = requests.get(f"{BASE_URL}/api/engine/context")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True

    def test_snapshot_meta_present(self):
        """snapshot_meta field exists in response"""
        response = requests.get(f"{BASE_URL}/api/engine/context")
        data = response.json()
        assert "snapshot_meta" in data
        assert data["snapshot_meta"] is not None

    def test_snapshot_meta_age_seconds(self):
        """snapshot_meta contains age_seconds field"""
        response = requests.get(f"{BASE_URL}/api/engine/context")
        data = response.json()
        snap = data.get("snapshot_meta", {})
        assert "age_seconds" in snap
        assert isinstance(snap["age_seconds"], (int, float))
        # Age should be less than 180s (stale threshold)
        assert snap["age_seconds"] <= 180

    def test_snapshot_meta_build_latency_ms(self):
        """snapshot_meta contains build_latency_ms field"""
        response = requests.get(f"{BASE_URL}/api/engine/context")
        data = response.json()
        snap = data.get("snapshot_meta", {})
        assert "build_latency_ms" in snap
        assert isinstance(snap["build_latency_ms"], int)
        # Build latency should be positive
        assert snap["build_latency_ms"] > 0

    def test_snapshot_meta_engine_version_45(self):
        """snapshot_meta.engine_version is '4.5'"""
        response = requests.get(f"{BASE_URL}/api/engine/context")
        data = response.json()
        snap = data.get("snapshot_meta", {})
        assert snap.get("engine_version") == "4.5"

    def test_snapshot_meta_served_from_snapshot(self):
        """snapshot_meta.served_from is 'snapshot' (not 'live')"""
        response = requests.get(f"{BASE_URL}/api/engine/context")
        data = response.json()
        snap = data.get("snapshot_meta", {})
        assert "served_from" in snap
        assert snap["served_from"] in ["snapshot", "live"]
        # If snapshot exists and is fresh, should be served from snapshot
        if snap.get("age_seconds", 999) <= 180:
            assert snap["served_from"] == "snapshot"

    def test_meta_version_45(self):
        """meta.version is '4.5'"""
        response = requests.get(f"{BASE_URL}/api/engine/context")
        data = response.json()
        meta = data.get("meta", {})
        assert meta.get("version") == "4.5"

    def test_narrative_version_45(self):
        """narrative.version is '4.5'"""
        response = requests.get(f"{BASE_URL}/api/engine/context")
        data = response.json()
        narrative = data.get("narrative", {})
        assert narrative.get("version") == "4.5"

    def test_api_response_time_faster_than_build(self):
        """API response time should be much faster than build_latency_ms"""
        start = time.time()
        response = requests.get(f"{BASE_URL}/api/engine/context")
        response_time_ms = (time.time() - start) * 1000
        
        data = response.json()
        build_latency = data.get("snapshot_meta", {}).get("build_latency_ms", 0)
        
        # Response should be at least 2x faster than build time
        # (unless build time is very small)
        if build_latency > 100:
            assert response_time_ms < build_latency * 0.8, \
                f"Response time {response_time_ms:.0f}ms should be faster than build {build_latency}ms"


class TestEngineAlerts:
    """Tests for GET /api/engine/alerts (E6 still working)"""

    def test_alerts_returns_ok(self):
        """Alerts endpoint returns ok=true"""
        response = requests.get(f"{BASE_URL}/api/engine/alerts")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True

    def test_alerts_returns_array(self):
        """Alerts endpoint returns alerts array"""
        response = requests.get(f"{BASE_URL}/api/engine/alerts")
        data = response.json()
        assert "alerts" in data
        assert isinstance(data["alerts"], list)

    def test_alerts_count_matches(self):
        """count field matches alerts array length"""
        response = requests.get(f"{BASE_URL}/api/engine/alerts")
        data = response.json()
        assert data.get("count") == len(data.get("alerts", []))


class TestSetupHistory:
    """Tests for GET /api/engine/history/setups (E7 new endpoint)"""

    def test_setup_history_returns_ok(self):
        """Setup history endpoint returns ok=true"""
        response = requests.get(f"{BASE_URL}/api/engine/history/setups")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True

    def test_setup_history_returns_array(self):
        """Setup history returns history array"""
        response = requests.get(f"{BASE_URL}/api/engine/history/setups")
        data = response.json()
        assert "history" in data
        assert isinstance(data["history"], list)

    def test_setup_history_count_matches(self):
        """count field matches history array length"""
        response = requests.get(f"{BASE_URL}/api/engine/history/setups")
        data = response.json()
        assert data.get("count") == len(data.get("history", []))

    def test_setup_history_entry_structure(self):
        """Setup history entries have required fields"""
        response = requests.get(f"{BASE_URL}/api/engine/history/setups")
        data = response.json()
        history = data.get("history", [])
        if len(history) > 0:
            entry = history[0]
            assert "timestamp" in entry
            assert "setup" in entry
            assert "status" in entry
            assert "confidence" in entry

    def test_setup_history_has_data(self):
        """Setup history collection has at least 1 document"""
        response = requests.get(f"{BASE_URL}/api/engine/history/setups")
        data = response.json()
        assert data.get("count", 0) >= 1, "engine_setup_history should have documents"


class TestMicroSnapshots:
    """Tests for GET /api/engine/history/micro (E7 new endpoint)"""

    def test_micro_snapshots_returns_ok(self):
        """Micro snapshots endpoint returns ok=true"""
        response = requests.get(f"{BASE_URL}/api/engine/history/micro")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True

    def test_micro_snapshots_returns_array(self):
        """Micro snapshots returns snapshots array"""
        response = requests.get(f"{BASE_URL}/api/engine/history/micro")
        data = response.json()
        assert "snapshots" in data
        assert isinstance(data["snapshots"], list)

    def test_micro_snapshots_count_matches(self):
        """count field matches snapshots array length"""
        response = requests.get(f"{BASE_URL}/api/engine/history/micro")
        data = response.json()
        assert data.get("count") == len(data.get("snapshots", []))

    def test_micro_snapshot_entry_structure(self):
        """Micro snapshot entries have required fields"""
        response = requests.get(f"{BASE_URL}/api/engine/history/micro")
        data = response.json()
        snapshots = data.get("snapshots", [])
        if len(snapshots) > 0:
            entry = snapshots[0]
            # Core fields
            assert "timestamp" in entry
            assert "decision" in entry
            assert "composite" in entry
            # Regime fields
            assert "regime" in entry
            assert "regime_status" in entry
            assert "regime_confidence" in entry
            # Setup fields
            assert "setup" in entry
            assert "setup_status" in entry
            assert "setup_confidence" in entry
            # Probability fields
            assert "probability_continuation" in entry
            assert "probability_failure" in entry
            assert "probability_upgrade" in entry
            # Flow fields
            assert "flow_state" in entry
            assert "flow_strength" in entry

    def test_micro_snapshots_has_data(self):
        """Micro snapshots collection has at least 1 document"""
        response = requests.get(f"{BASE_URL}/api/engine/history/micro")
        data = response.json()
        assert data.get("count", 0) >= 1, "engine_micro_snapshots should have documents"


class TestEngineDataIntegrity:
    """Tests for E7 data integrity - existing engine blocks still work"""

    def test_regime_engine_present(self):
        """regime_engine block still present in response"""
        response = requests.get(f"{BASE_URL}/api/engine/context")
        data = response.json()
        assert "regime_engine" in data
        assert data["regime_engine"] is not None

    def test_setup_engine_present(self):
        """setup_engine block still present in response"""
        response = requests.get(f"{BASE_URL}/api/engine/context")
        data = response.json()
        assert "setup_engine" in data
        assert data["setup_engine"] is not None

    def test_probability_layer_present(self):
        """probability_layer block still present in response"""
        response = requests.get(f"{BASE_URL}/api/engine/context")
        data = response.json()
        assert "probability_layer" in data
        assert data["probability_layer"] is not None

    def test_flow_engine_present(self):
        """flow_engine block still present in response"""
        response = requests.get(f"{BASE_URL}/api/engine/context")
        data = response.json()
        assert "flow_engine" in data
        assert data["flow_engine"] is not None

    def test_liquidity_map_present(self):
        """liquidity_map block still present in response"""
        response = requests.get(f"{BASE_URL}/api/engine/context")
        data = response.json()
        assert "liquidity_map" in data
        assert data["liquidity_map"] is not None

    def test_narrative_present(self):
        """narrative block still present (E4)"""
        response = requests.get(f"{BASE_URL}/api/engine/context")
        data = response.json()
        assert "narrative" in data
        assert data["narrative"] is not None

    def test_decision_present(self):
        """decision field still present"""
        response = requests.get(f"{BASE_URL}/api/engine/context")
        data = response.json()
        assert "decision" in data
        assert data["decision"] in ["BUY", "SELL", "NEUTRAL", "STRONG_BUY", "WATCH", "AVOID"]

    def test_confidence_present(self):
        """confidence block still present"""
        response = requests.get(f"{BASE_URL}/api/engine/context")
        data = response.json()
        assert "confidence" in data
        conf = data["confidence"]
        assert "score" in conf
        assert "level" in conf
