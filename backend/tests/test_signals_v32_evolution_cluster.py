"""
Signals Terminal V3.2 Backend Tests
- Tests for cluster_score field in signals
- Tests for evolution endpoint (phase history)
- Tests for phase_history collection population
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')


class TestSignalsClusterScore:
    """Tests for cluster_score enhancement in signals"""

    def test_signals_return_cluster_score_field(self):
        """Verify signals contain cluster_score field"""
        response = requests.get(f"{BASE_URL}/api/signals")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "signals" in data
        assert len(data["signals"]) > 0
        
        # Check cluster_score field exists on all signals
        for sig in data["signals"]:
            assert "cluster_score" in sig, f"Signal {sig['id']} missing cluster_score"
            assert isinstance(sig["cluster_score"], (int, float))
            assert 0 <= sig["cluster_score"] <= 100

    def test_signals_return_cluster_count_field(self):
        """Verify signals contain cluster_count field"""
        response = requests.get(f"{BASE_URL}/api/signals")
        assert response.status_code == 200
        data = response.json()
        
        for sig in data["signals"]:
            assert "cluster_count" in sig, f"Signal {sig['id']} missing cluster_count"
            assert isinstance(sig["cluster_count"], int)
            assert sig["cluster_count"] >= 1

    def test_cluster_score_reflects_grouping(self):
        """Verify cluster_score is higher when multiple signals are clustered"""
        response = requests.get(f"{BASE_URL}/api/signals")
        assert response.status_code == 200
        data = response.json()
        
        clustered_signals = [s for s in data["signals"] if s.get("cluster_id")]
        if clustered_signals:
            for sig in clustered_signals:
                # cluster_score should be >= signal's base score
                assert sig["cluster_score"] >= sig["score"] - 5, \
                    f"cluster_score {sig['cluster_score']} too low vs score {sig['score']}"

    def test_stats_return_max_cluster_score(self):
        """Verify /api/signals/stats returns max_cluster_score"""
        response = requests.get(f"{BASE_URL}/api/signals/stats")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "max_cluster_score" in data
        assert isinstance(data["max_cluster_score"], (int, float))


class TestSignalEvolutionEndpoint:
    """Tests for GET /api/signals/{signal_id}/evolution endpoint"""

    def test_evolution_endpoint_exists(self):
        """Verify evolution endpoint returns 200"""
        # First get a valid signal ID
        sig_response = requests.get(f"{BASE_URL}/api/signals")
        assert sig_response.status_code == 200
        signals = sig_response.json().get("signals", [])
        assert len(signals) > 0
        
        signal_id = signals[0]["id"]
        response = requests.get(f"{BASE_URL}/api/signals/{signal_id}/evolution")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True

    def test_evolution_returns_phases_array(self):
        """Verify evolution endpoint returns phases array"""
        sig_response = requests.get(f"{BASE_URL}/api/signals")
        signals = sig_response.json().get("signals", [])
        signal_id = signals[0]["id"]
        
        response = requests.get(f"{BASE_URL}/api/signals/{signal_id}/evolution")
        data = response.json()
        
        assert "phases" in data
        assert isinstance(data["phases"], list)
        assert "count" in data

    def test_evolution_phase_structure(self):
        """Verify phase entries have correct structure"""
        sig_response = requests.get(f"{BASE_URL}/api/signals")
        signals = sig_response.json().get("signals", [])
        signal_id = signals[0]["id"]
        
        response = requests.get(f"{BASE_URL}/api/signals/{signal_id}/evolution")
        data = response.json()
        
        if data["phases"]:
            phase = data["phases"][0]
            # Verify required fields
            assert "signal_id" in phase
            assert "phase" in phase
            assert "timestamp" in phase
            assert "score" in phase
            # Verify phase is valid lifecycle stage
            valid_phases = ["detected", "forming", "confirmed", "cooling", "invalidated"]
            assert phase["phase"] in valid_phases, f"Invalid phase: {phase['phase']}"

    def test_evolution_phases_have_timestamps(self):
        """Verify phase entries have timestamps for timeline display"""
        sig_response = requests.get(f"{BASE_URL}/api/signals")
        signals = sig_response.json().get("signals", [])
        signal_id = signals[0]["id"]
        
        response = requests.get(f"{BASE_URL}/api/signals/{signal_id}/evolution")
        data = response.json()
        
        if data["phases"]:
            for phase in data["phases"]:
                assert "timestamp" in phase
                assert phase["timestamp"]  # Not empty

    def test_evolution_invalid_signal_id(self):
        """Verify evolution endpoint handles invalid signal IDs gracefully"""
        response = requests.get(f"{BASE_URL}/api/signals/invalid_signal_123/evolution")
        # Should still return 200 with empty phases or ok: true
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("count", 0) == 0


class TestSignalPhaseHistoryPopulation:
    """Tests to verify signal_phase_history collection is populated"""

    def test_phase_history_recorded_for_signals(self):
        """Verify that signals have their phase history recorded"""
        # Get all signals
        sig_response = requests.get(f"{BASE_URL}/api/signals")
        signals = sig_response.json().get("signals", [])
        
        # At least one signal should have evolution history
        has_history = False
        for sig in signals[:3]:  # Check first 3 signals
            evo_response = requests.get(f"{BASE_URL}/api/signals/{sig['id']}/evolution")
            evo_data = evo_response.json()
            if evo_data.get("count", 0) > 0:
                has_history = True
                break
        
        assert has_history, "No signals have phase history recorded"


class TestDirectionFilter:
    """Tests for direction filter functionality"""

    def test_direction_filter_bullish(self):
        """Verify direction=BULLISH filter works"""
        response = requests.get(f"{BASE_URL}/api/signals?direction=BULLISH")
        assert response.status_code == 200
        data = response.json()
        
        for sig in data["signals"]:
            assert sig["direction"] == "BULLISH"

    def test_direction_filter_bearish(self):
        """Verify direction=BEARISH filter works"""
        response = requests.get(f"{BASE_URL}/api/signals?direction=BEARISH")
        assert response.status_code == 200
        data = response.json()
        # All returned signals should be BEARISH (could be 0 if none exist)
        for sig in data["signals"]:
            assert sig["direction"] == "BEARISH"


class TestStatsEndpoint:
    """Tests for /api/signals/stats endpoint"""

    def test_stats_returns_all_fields(self):
        """Verify stats endpoint returns all required fields"""
        response = requests.get(f"{BASE_URL}/api/signals/stats")
        assert response.status_code == 200
        data = response.json()
        
        required_fields = [
            "ok", "total", "strong", "extreme", "bullish", "bearish",
            "avg_score", "by_type", "has_cluster", "cluster_count", "max_cluster_score"
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_stats_cluster_info(self):
        """Verify stats includes cluster information"""
        response = requests.get(f"{BASE_URL}/api/signals/stats")
        data = response.json()
        
        assert "has_cluster" in data
        assert isinstance(data["has_cluster"], bool)
        assert "cluster_count" in data
        assert isinstance(data["cluster_count"], int)


class TestSignalStructure:
    """Tests for signal data structure completeness"""

    def test_signal_has_age_field(self):
        """Verify signals have age_min field"""
        response = requests.get(f"{BASE_URL}/api/signals")
        data = response.json()
        
        for sig in data["signals"]:
            assert "age_min" in sig
            assert isinstance(sig["age_min"], int)

    def test_signal_has_expected_move_and_timeframe(self):
        """Verify signals have expected_move and timeframe fields"""
        response = requests.get(f"{BASE_URL}/api/signals")
        data = response.json()
        
        for sig in data["signals"]:
            assert "expected_move" in sig
            assert "timeframe" in sig
