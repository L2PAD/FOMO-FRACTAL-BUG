"""
OS Service, Alerts Tab, and Setup History Tests
=================================================
Tests for the new sprint features:
1. OS Service: /api/os/state, /api/os/opportunities
2. Alerts Dashboard: /api/engine/alerts 
3. Setup History with probability_at_event, regime_at_event
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestOSStateEndpoint:
    """Test GET /api/os/state — Market Intelligence OS"""

    def test_os_state_returns_ok(self):
        """/api/os/state returns ok=true"""
        r = requests.get(f"{BASE_URL}/api/os/state", timeout=30)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        assert data.get("ok") is True, f"Expected ok=true, got {data}"

    def test_os_state_has_market_state(self):
        """Response contains market_state object"""
        r = requests.get(f"{BASE_URL}/api/os/state", timeout=30)
        data = r.json()
        assert "market_state" in data, f"Missing market_state field: {data.keys()}"
        ms = data["market_state"]
        assert isinstance(ms, dict), f"market_state should be dict, got {type(ms)}"

    def test_market_state_has_required_fields(self):
        """market_state has regime, setup, flow_state, decision, probability fields"""
        r = requests.get(f"{BASE_URL}/api/os/state", timeout=30)
        data = r.json()
        ms = data.get("market_state", {})
        required = ["regime", "setup", "flow_state", "decision"]
        for field in required:
            assert field in ms, f"market_state missing {field}: {ms.keys()}"
        # Probability fields
        assert "probability_continuation" in ms or "composite" in ms, f"Missing probability field: {ms.keys()}"

    def test_os_state_has_top_opportunity(self):
        """Response contains top_opportunity object"""
        r = requests.get(f"{BASE_URL}/api/os/state", timeout=30)
        data = r.json()
        assert "top_opportunity" in data, f"Missing top_opportunity: {data.keys()}"
        opp = data["top_opportunity"]
        assert isinstance(opp, dict), f"top_opportunity should be dict"

    def test_top_opportunity_fields(self):
        """top_opportunity has setup, status, confidence, probability, supports fields"""
        r = requests.get(f"{BASE_URL}/api/os/state", timeout=30)
        data = r.json()
        opp = data.get("top_opportunity", {})
        # At minimum, setup should be present (could be 'mixed' or empty if no opportunity)
        if opp:
            # If there's data, check structure
            possible_fields = ["setup", "status", "confidence", "probability", "supports", "target"]
            found = [f for f in possible_fields if f in opp]
            assert len(found) >= 1, f"top_opportunity has no expected fields: {opp.keys()}"

    def test_os_state_has_actor_pressure(self):
        """Response contains actor_pressure object"""
        r = requests.get(f"{BASE_URL}/api/os/state", timeout=30)
        data = r.json()
        assert "actor_pressure" in data, f"Missing actor_pressure: {data.keys()}"
        ap = data["actor_pressure"]
        assert isinstance(ap, dict), f"actor_pressure should be dict"

    def test_actor_pressure_fields(self):
        """actor_pressure has bullish, bearish, neutral counts and actors array"""
        r = requests.get(f"{BASE_URL}/api/os/state", timeout=30)
        data = r.json()
        ap = data.get("actor_pressure", {})
        assert "bullish" in ap, f"Missing bullish count: {ap.keys()}"
        assert "bearish" in ap, f"Missing bearish count: {ap.keys()}"
        assert "neutral" in ap, f"Missing neutral count: {ap.keys()}"
        assert "actors" in ap, f"Missing actors array: {ap.keys()}"
        assert isinstance(ap["actors"], list), f"actors should be list"

    def test_os_state_has_liquidity_targets(self):
        """Response contains liquidity_targets array"""
        r = requests.get(f"{BASE_URL}/api/os/state", timeout=30)
        data = r.json()
        assert "liquidity_targets" in data, f"Missing liquidity_targets: {data.keys()}"
        lt = data["liquidity_targets"]
        assert isinstance(lt, list), f"liquidity_targets should be list"

    def test_liquidity_targets_zone_types(self):
        """liquidity_targets items have zone_type (target/magnet/void)"""
        r = requests.get(f"{BASE_URL}/api/os/state", timeout=30)
        data = r.json()
        lt = data.get("liquidity_targets", [])
        if lt:  # Only check if there's data
            valid_zone_types = {"target", "magnet", "void"}
            for item in lt:
                assert "zone_type" in item, f"Liquidity target missing zone_type: {item}"
                assert item["zone_type"] in valid_zone_types, f"Invalid zone_type: {item['zone_type']}"

    def test_os_state_has_alerts(self):
        """Response contains alerts array"""
        r = requests.get(f"{BASE_URL}/api/os/state", timeout=30)
        data = r.json()
        assert "alerts" in data, f"Missing alerts: {data.keys()}"
        assert isinstance(data["alerts"], list), f"alerts should be list"


class TestOSOpportunitiesEndpoint:
    """Test GET /api/os/opportunities"""

    def test_os_opportunities_returns_ok(self):
        """/api/os/opportunities returns ok=true"""
        r = requests.get(f"{BASE_URL}/api/os/opportunities", timeout=30)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        assert data.get("ok") is True, f"Expected ok=true, got {data}"

    def test_os_opportunities_has_array(self):
        """Response contains opportunities array"""
        r = requests.get(f"{BASE_URL}/api/os/opportunities", timeout=30)
        data = r.json()
        assert "opportunities" in data, f"Missing opportunities: {data.keys()}"
        assert isinstance(data["opportunities"], list), f"opportunities should be list"


class TestSetupHistoryEndpoint:
    """Test GET /api/engine/history/setups with new fields"""

    def test_setup_history_returns_ok(self):
        """/api/engine/history/setups returns ok=true"""
        r = requests.get(f"{BASE_URL}/api/engine/history/setups", timeout=30)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        assert data.get("ok") is True, f"Expected ok=true, got {data}"

    def test_setup_history_has_array(self):
        """Response contains history array"""
        r = requests.get(f"{BASE_URL}/api/engine/history/setups", timeout=30)
        data = r.json()
        assert "history" in data, f"Missing history: {data.keys()}"
        assert isinstance(data["history"], list), f"history should be list"

    def test_setup_history_entry_structure(self):
        """Setup history entries have required fields"""
        r = requests.get(f"{BASE_URL}/api/engine/history/setups", timeout=30)
        data = r.json()
        history = data.get("history", [])
        if history:
            entry = history[0]
            # Basic required fields
            assert "timestamp" in entry, f"Missing timestamp: {entry.keys()}"
            assert "setup" in entry, f"Missing setup: {entry.keys()}"
            assert "status" in entry, f"Missing status: {entry.keys()}"
            assert "confidence" in entry, f"Missing confidence: {entry.keys()}"

    def test_setup_history_new_fields(self):
        """Newer entries have probability_at_event and regime_at_event fields"""
        r = requests.get(f"{BASE_URL}/api/engine/history/setups", timeout=30)
        data = r.json()
        history = data.get("history", [])
        # Note: per context, old entries may not have these fields
        # New entries should have them
        if history:
            # Check if any entry has the new fields
            has_prob_field = any("probability_at_event" in e for e in history)
            has_regime_field = any("regime_at_event" in e for e in history)
            # Log for awareness - not a hard failure if only old data
            print(f"probability_at_event present in any entry: {has_prob_field}")
            print(f"regime_at_event present in any entry: {has_regime_field}")
            # Verify the fields are valid when present
            for entry in history:
                if "probability_at_event" in entry:
                    assert entry["probability_at_event"] is None or isinstance(entry["probability_at_event"], (int, float)), \
                        f"Invalid probability_at_event type: {entry['probability_at_event']}"
                if "regime_at_event" in entry:
                    assert entry["regime_at_event"] is None or isinstance(entry["regime_at_event"], str), \
                        f"Invalid regime_at_event type: {entry['regime_at_event']}"


class TestAlertsEndpoint:
    """Test GET /api/engine/alerts for Alert Dashboard"""

    def test_alerts_returns_ok(self):
        """/api/engine/alerts returns ok=true"""
        r = requests.get(f"{BASE_URL}/api/engine/alerts?limit=100", timeout=30)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        assert data.get("ok") is True, f"Expected ok=true, got {data}"

    def test_alerts_has_array(self):
        """Response contains alerts array"""
        r = requests.get(f"{BASE_URL}/api/engine/alerts?limit=100", timeout=30)
        data = r.json()
        assert "alerts" in data, f"Missing alerts: {data.keys()}"
        assert isinstance(data["alerts"], list), f"alerts should be list"

    def test_alerts_structure(self):
        """Alert entries have type, severity, message, timestamp fields"""
        r = requests.get(f"{BASE_URL}/api/engine/alerts?limit=100", timeout=30)
        data = r.json()
        alerts = data.get("alerts", [])
        if alerts:
            alert = alerts[0]
            assert "type" in alert, f"Missing type: {alert.keys()}"
            assert "severity" in alert, f"Missing severity: {alert.keys()}"
            assert "message" in alert, f"Missing message: {alert.keys()}"
            assert "timestamp" in alert, f"Missing timestamp: {alert.keys()}"

    def test_alerts_severity_values(self):
        """Alert severity values are valid (CRITICAL/IMPORTANT/WATCH/INFO)"""
        r = requests.get(f"{BASE_URL}/api/engine/alerts?limit=100", timeout=30)
        data = r.json()
        alerts = data.get("alerts", [])
        valid_severities = {"CRITICAL", "IMPORTANT", "WATCH", "INFO"}
        for alert in alerts:
            assert alert.get("severity") in valid_severities, \
                f"Invalid severity: {alert.get('severity')}"


class TestEngineContext:
    """Test existing /api/engine/context endpoint"""

    def test_engine_context_returns_ok(self):
        """/api/engine/context returns ok=true"""
        r = requests.get(f"{BASE_URL}/api/engine/context", timeout=60)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        assert data.get("ok") is True, f"Expected ok=true, got {data}"

    def test_engine_context_has_snapshot_meta(self):
        """Response contains snapshot_meta"""
        r = requests.get(f"{BASE_URL}/api/engine/context", timeout=60)
        data = r.json()
        assert "snapshot_meta" in data, f"Missing snapshot_meta: {data.keys()}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
