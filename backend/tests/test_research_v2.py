"""
Research V2 (Macro Interpretation Engine) Tests
Tests for R1 — Research endpoint that builds structured ResearchReport from Labs, Radar, Market, Health data.

Endpoints tested:
- GET /api/v11/exchange/research/report
- GET /api/v11/exchange/research/debug
- Previous feature: GET /api/v11/exchange/radar/selfcheck
- Previous feature: GET /api/v11/exchange/market/board
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestResearchReportEndpoint:
    """Tests for GET /api/v11/exchange/research/report"""

    def test_research_report_btcusdt_basic_structure(self):
        """Test research report returns valid JSON with required fields"""
        response = requests.get(
            f"{BASE_URL}/api/v11/exchange/research/report",
            params={"symbol": "BTCUSDT", "timeframe": "15m", "force": "true"},
            timeout=30
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Basic structure
        assert data.get("ok") is True, "Response should have ok=true"
        assert "ts" in data, "Response should have ts"
        assert "marketState" in data, "Response should have marketState"
        assert "riskPressure" in data, "Response should have riskPressure"
        assert "horizonBias" in data, "Response should have horizonBias"
        assert "dominantForces" in data, "Response should have dominantForces"
        assert "executionImplications" in data, "Response should have executionImplications"
        assert "meta" in data, "Response should have meta"
        assert "latencyMs" in data, "Response should have latencyMs"

    def test_research_report_ethusdt(self):
        """Test research report for ETHUSDT returns data"""
        response = requests.get(
            f"{BASE_URL}/api/v11/exchange/research/report",
            params={"symbol": "ETHUSDT", "force": "true"},
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("symbol") == "ETHUSDT"
        assert "marketState" in data

    def test_market_state_five_domains(self):
        """Test marketState has 5 domains: regime, volatility, liquidity, flow, stress"""
        response = requests.get(
            f"{BASE_URL}/api/v11/exchange/research/report",
            params={"symbol": "BTCUSDT", "timeframe": "15m"},
            timeout=30
        )
        data = response.json()
        market_state = data.get("marketState", {})
        
        # Check all 5 domains present
        required_domains = ["regime", "volatility", "liquidity", "flow", "stress"]
        for domain in required_domains:
            assert domain in market_state, f"marketState should have {domain}"
            # Each domain should have state and confidence
            assert "state" in market_state[domain], f"{domain} should have state"
            assert "confidence" in market_state[domain], f"{domain} should have confidence"
            # Confidence should be a float 0-1
            conf = market_state[domain]["confidence"]
            assert isinstance(conf, (int, float)), f"{domain}.confidence should be a number"
            assert 0 <= conf <= 1, f"{domain}.confidence should be 0-1"

    def test_risk_pressure_structure(self):
        """Test riskPressure has score (0-1), level (LOW/MID/HIGH), drivers (array)"""
        response = requests.get(
            f"{BASE_URL}/api/v11/exchange/research/report",
            params={"symbol": "BTCUSDT", "timeframe": "15m"},
            timeout=30
        )
        data = response.json()
        risk = data.get("riskPressure", {})
        
        # Score
        assert "score" in risk, "riskPressure should have score"
        assert isinstance(risk["score"], (int, float)), "score should be float"
        assert 0 <= risk["score"] <= 1, "score should be 0-1"
        
        # Level
        assert "level" in risk, "riskPressure should have level"
        assert risk["level"] in ["LOW", "MID", "HIGH"], f"level should be LOW/MID/HIGH, got {risk['level']}"
        
        # Drivers
        assert "drivers" in risk, "riskPressure should have drivers"
        assert isinstance(risk["drivers"], list), "drivers should be an array"

    def test_horizon_bias_structure(self):
        """Test horizonBias has short, mid, swing with bias and confidence"""
        response = requests.get(
            f"{BASE_URL}/api/v11/exchange/research/report",
            params={"symbol": "BTCUSDT", "timeframe": "15m"},
            timeout=30
        )
        data = response.json()
        horizon = data.get("horizonBias", {})
        
        for h in ["short", "mid", "swing"]:
            assert h in horizon, f"horizonBias should have {h}"
            assert "bias" in horizon[h], f"{h} should have bias"
            assert "confidence" in horizon[h], f"{h} should have confidence"
            assert isinstance(horizon[h]["bias"], str), f"{h}.bias should be string"
            assert isinstance(horizon[h]["confidence"], (int, float)), f"{h}.confidence should be float"

    def test_dominant_forces_structure(self):
        """Test dominantForces is array of objects with name, state, impactScore, explanation"""
        response = requests.get(
            f"{BASE_URL}/api/v11/exchange/research/report",
            params={"symbol": "BTCUSDT", "timeframe": "15m"},
            timeout=30
        )
        data = response.json()
        forces = data.get("dominantForces", [])
        
        assert isinstance(forces, list), "dominantForces should be an array"
        assert len(forces) > 0, "dominantForces should have at least one entry"
        assert len(forces) <= 5, "dominantForces should have at most 5 entries"
        
        for force in forces:
            assert "name" in force, "force should have name"
            assert "state" in force, "force should have state"
            assert "impactScore" in force, "force should have impactScore"
            assert "explanation" in force, "force should have explanation"

    def test_execution_implications_structure(self):
        """Test executionImplications has style, avoid, preferredInstruments, riskControls"""
        response = requests.get(
            f"{BASE_URL}/api/v11/exchange/research/report",
            params={"symbol": "BTCUSDT", "timeframe": "15m"},
            timeout=30
        )
        data = response.json()
        exec_impl = data.get("executionImplications", {})
        
        assert "style" in exec_impl, "executionImplications should have style"
        assert "avoid" in exec_impl, "executionImplications should have avoid"
        assert "preferredInstruments" in exec_impl, "executionImplications should have preferredInstruments"
        assert "riskControls" in exec_impl, "executionImplications should have riskControls"
        
        assert isinstance(exec_impl["style"], str), "style should be string"
        assert isinstance(exec_impl["avoid"], list), "avoid should be array"
        assert isinstance(exec_impl["preferredInstruments"], list), "preferredInstruments should be array"
        assert isinstance(exec_impl["riskControls"], list), "riskControls should be array"

    def test_latency_under_5000ms(self):
        """Test latencyMs is present and under 5000ms"""
        response = requests.get(
            f"{BASE_URL}/api/v11/exchange/research/report",
            params={"symbol": "BTCUSDT", "timeframe": "15m", "force": "true"},
            timeout=30
        )
        data = response.json()
        
        assert "latencyMs" in data, "Response should have latencyMs"
        assert data["latencyMs"] < 5000, f"latencyMs should be < 5000, got {data['latencyMs']}"


class TestResearchCache:
    """Tests for cache functionality"""

    def test_cache_returns_faster_on_second_call(self):
        """Test that cache works: second call returns faster with fromCache=true"""
        # Force a fresh call
        response1 = requests.get(
            f"{BASE_URL}/api/v11/exchange/research/report",
            params={"symbol": "BTCUSDT", "timeframe": "15m", "force": "true"},
            timeout=30
        )
        data1 = response1.json()
        assert data1.get("fromCache") is False, "First call with force=true should not be from cache"
        
        # Give cache time to settle
        time.sleep(1)
        
        # Second call should be from cache
        response2 = requests.get(
            f"{BASE_URL}/api/v11/exchange/research/report",
            params={"symbol": "BTCUSDT", "timeframe": "15m"},
            timeout=30
        )
        data2 = response2.json()
        assert data2.get("fromCache") is True, "Second call should be from cache"


class TestResearchDebugEndpoint:
    """Tests for GET /api/v11/exchange/research/debug"""

    def test_debug_returns_snapshot(self):
        """Test debug endpoint returns snapshot with labs, radar, pulse, health"""
        response = requests.get(
            f"{BASE_URL}/api/v11/exchange/research/debug",
            params={"symbol": "BTCUSDT", "timeframe": "15m"},
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True, "Response should have ok=true"
        assert "snapshot" in data, "Response should have snapshot"
        
        snapshot = data["snapshot"]
        assert "labs" in snapshot, "snapshot should have labs"
        assert "radar" in snapshot, "snapshot should have radar"
        assert "pulse" in snapshot, "snapshot should have pulse"
        assert "health" in snapshot, "snapshot should have health"


class TestPreviousFeatures:
    """Tests for previous features (Radar, Market Board) to ensure they still work"""

    def test_radar_selfcheck_still_works(self):
        """Test GET /api/v11/exchange/radar/selfcheck returns valid data"""
        response = requests.get(
            f"{BASE_URL}/api/v11/exchange/radar/selfcheck",
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True, "selfcheck should return ok=true"
        assert "coverage" in data, "selfcheck should have coverage"
        assert "spot" in data, "selfcheck should have spot"
        assert "divergence" in data, "selfcheck should have divergence"

    def test_market_board_still_works(self):
        """Test GET /api/v11/exchange/market/board returns valid data"""
        response = requests.get(
            f"{BASE_URL}/api/v11/exchange/market/board",
            params={"universe": "alpha"},
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "ts" in data, "market board should have ts"
        assert "pulse" in data, "market board should have pulse"
        assert "summary" in data, "market board should have summary"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
