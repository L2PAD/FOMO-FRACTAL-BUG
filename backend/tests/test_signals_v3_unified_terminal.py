"""
Signals V3 Unified Terminal Tests
=================================
Tests for the new Unified Signals Terminal V3 feature.

Endpoints tested:
  - /api/signals — Unified signals stream with filters
  - /api/signals/stats — Signal summary statistics
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# === Tests for /api/signals endpoint ===

class TestSignalsEndpoint:
    """Tests for GET /api/signals - Unified signals stream"""

    def test_signals_returns_ok_true(self):
        """Test 1: /api/signals returns ok:true and signals array"""
        response = requests.get(f"{BASE_URL}/api/signals", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Response should have ok:true"
        assert "signals" in data, "Response should contain signals array"
        assert isinstance(data["signals"], list), "signals should be a list"
        assert "count" in data, "Response should contain count"

    def test_signals_have_required_fields(self):
        """Test 2: Each signal has all required fields"""
        response = requests.get(f"{BASE_URL}/api/signals", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        signals = data.get("signals", [])
        
        required_fields = [
            "id", "asset", "signal_type", "direction", "score", 
            "confidence", "severity", "status", "timeframe", 
            "expected_move", "drivers", "target", "risk", 
            "timestamp", "age_min"
        ]
        
        for signal in signals:
            for field in required_fields:
                assert field in signal, f"Signal missing required field: {field}"
        
        print(f"Verified {len(signals)} signals have all required fields")

    def test_signal_direction_values(self):
        """Test 3: Direction values are BULLISH/BEARISH/NEUTRAL"""
        response = requests.get(f"{BASE_URL}/api/signals", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        signals = data.get("signals", [])
        valid_directions = {"BULLISH", "BEARISH", "NEUTRAL"}
        
        for signal in signals:
            assert signal["direction"] in valid_directions, \
                f"Invalid direction: {signal['direction']}"
        
        print(f"All {len(signals)} signals have valid direction values")

    def test_signal_severity_values(self):
        """Test 4: Severity values are EXTREME/STRONG/WATCH/WEAK"""
        response = requests.get(f"{BASE_URL}/api/signals", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        signals = data.get("signals", [])
        valid_severities = {"EXTREME", "STRONG", "WATCH", "WEAK"}
        
        for signal in signals:
            assert signal["severity"] in valid_severities, \
                f"Invalid severity: {signal['severity']}"
        
        print(f"All {len(signals)} signals have valid severity values")

    def test_signal_status_values(self):
        """Test 5: Status values are valid lifecycle states"""
        response = requests.get(f"{BASE_URL}/api/signals", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        signals = data.get("signals", [])
        valid_statuses = {"confirmed", "forming", "detected", "cooling", "invalidated"}
        
        for signal in signals:
            assert signal["status"] in valid_statuses, \
                f"Invalid status: {signal['status']}"
        
        print(f"All {len(signals)} signals have valid status values")

    def test_signal_score_range(self):
        """Test 6: Score is 0-100"""
        response = requests.get(f"{BASE_URL}/api/signals", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        signals = data.get("signals", [])
        
        for signal in signals:
            assert 0 <= signal["score"] <= 100, \
                f"Score out of range: {signal['score']}"
        
        print(f"All {len(signals)} signals have valid score range 0-100")

    def test_signal_drivers_is_object(self):
        """Test 7: Drivers field is an object"""
        response = requests.get(f"{BASE_URL}/api/signals", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        signals = data.get("signals", [])
        
        for signal in signals:
            assert isinstance(signal["drivers"], dict), \
                f"Drivers should be an object, got: {type(signal['drivers'])}"
        
        print(f"All {len(signals)} signals have drivers as object")


class TestSignalsFilters:
    """Tests for /api/signals filter parameters"""

    def test_severity_filter_watch(self):
        """Test 8: Filter by severity=WATCH returns only WATCH signals"""
        response = requests.get(f"{BASE_URL}/api/signals?severity=WATCH", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        signals = data.get("signals", [])
        
        for signal in signals:
            assert signal["severity"] == "WATCH", \
                f"Expected WATCH severity, got: {signal['severity']}"
        
        print(f"Severity filter WATCH: {len(signals)} signals returned")

    def test_direction_filter_bullish(self):
        """Test 9: Filter by direction=BULLISH returns only BULLISH signals"""
        response = requests.get(f"{BASE_URL}/api/signals?direction=BULLISH", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        signals = data.get("signals", [])
        
        for signal in signals:
            assert signal["direction"] == "BULLISH", \
                f"Expected BULLISH direction, got: {signal['direction']}"
        
        print(f"Direction filter BULLISH: {len(signals)} signals returned")


class TestSignalsStats:
    """Tests for GET /api/signals/stats endpoint"""

    def test_stats_returns_ok_true(self):
        """Test 10: /api/signals/stats returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/signals/stats", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Response should have ok:true"

    def test_stats_has_required_fields(self):
        """Test 11: Stats response has all required fields"""
        response = requests.get(f"{BASE_URL}/api/signals/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        required_fields = [
            "total", "strong", "extreme", "bullish", 
            "bearish", "avg_score", "by_type", "top_signal"
        ]
        
        for field in required_fields:
            assert field in data, f"Stats missing required field: {field}"
        
        print(f"Stats endpoint has all required fields: {required_fields}")

    def test_stats_by_type_is_object(self):
        """Test 12: by_type field is an object with signal_type counts"""
        response = requests.get(f"{BASE_URL}/api/signals/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        by_type = data.get("by_type")
        assert isinstance(by_type, dict), f"by_type should be object, got: {type(by_type)}"
        
        print(f"by_type contains: {by_type}")

    def test_stats_top_signal_structure(self):
        """Test 13: top_signal has signal structure or is null"""
        response = requests.get(f"{BASE_URL}/api/signals/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        top_signal = data.get("top_signal")
        
        if top_signal is not None:
            assert "id" in top_signal, "top_signal should have id"
            assert "score" in top_signal, "top_signal should have score"
            assert "signal_type" in top_signal, "top_signal should have signal_type"
            print(f"top_signal: {top_signal['signal_type']} with score {top_signal['score']}")
        else:
            print("top_signal is null (no signals)")


class TestOSRegression:
    """Regression tests for OS page endpoints to ensure they still work"""

    def test_os_state_endpoint(self):
        """Test 14: /api/os/state still works"""
        response = requests.get(f"{BASE_URL}/api/os/state", timeout=30)
        assert response.status_code == 200, f"OS state failed: {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "OS state should return ok:true"
        print("OS state endpoint working")

    def test_os_regime_timeline(self):
        """Test 15: /api/os/regime-timeline still works"""
        response = requests.get(f"{BASE_URL}/api/os/regime-timeline", timeout=30)
        assert response.status_code == 200, f"Regime timeline failed: {response.status_code}"
        print("OS regime-timeline endpoint working")

    def test_os_actor_radar(self):
        """Test 16: /api/os/actor-radar still works"""
        response = requests.get(f"{BASE_URL}/api/os/actor-radar", timeout=30)
        assert response.status_code == 200, f"Actor radar failed: {response.status_code}"
        print("OS actor-radar endpoint working")

    def test_os_opportunities(self):
        """Test 17: /api/os/opportunities still works"""
        response = requests.get(f"{BASE_URL}/api/os/opportunities", timeout=30)
        assert response.status_code == 200, f"Opportunities failed: {response.status_code}"
        print("OS opportunities endpoint working")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
