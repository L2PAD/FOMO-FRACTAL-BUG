"""
LARE v2 Block 8 API Tests
=========================

Tests for LARE v2.0.0 backend APIs (frozen):
- GET /api/v10/onchain-v2/lare-v2/health
- GET /api/v10/onchain-v2/lare-v2/latest?window=24h|7d
- GET /api/v10/onchain-v2/lare-v2/gate
- GET /api/v10/onchain-v2/lare-v2/series?window=24h|7d&range=30d
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestLareV2Health:
    """Tests for /api/v10/onchain-v2/lare-v2/health endpoint"""
    
    def test_health_returns_ok(self):
        """Health endpoint should return ok:true"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/lare-v2/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
    
    def test_health_returns_version(self):
        """Health endpoint should return version v2.0.0"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/lare-v2/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("version") == "v2.0.0"
    
    def test_health_has_windows(self):
        """Health endpoint should have windows object"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/lare-v2/health")
        assert response.status_code == 200
        data = response.json()
        assert "windows" in data
        assert "24h" in data["windows"]
        assert "7d" in data["windows"]
    
    def test_health_windows_have_required_fields(self):
        """Each window should have score, confidence, regime"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/lare-v2/health")
        assert response.status_code == 200
        data = response.json()
        
        for window_key in ["24h", "7d"]:
            window = data["windows"][window_key]
            assert "score" in window
            assert "confidence" in window
            assert "regime" in window
            assert isinstance(window["score"], (int, float))
            assert isinstance(window["confidence"], (int, float))


class TestLareV2Latest:
    """Tests for /api/v10/onchain-v2/lare-v2/latest endpoint"""
    
    def test_latest_24h_returns_ok(self):
        """Latest endpoint with window=24h should return ok:true"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/lare-v2/latest?window=24h")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
    
    def test_latest_7d_returns_ok(self):
        """Latest endpoint with window=7d should return ok:true"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/lare-v2/latest?window=7d")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
    
    def test_latest_has_data_object(self):
        """Latest endpoint should have data object with required fields"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/lare-v2/latest?window=24h")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        
        lare_data = data["data"]
        assert "score" in lare_data
        assert "confidence" in lare_data
        assert "regime" in lare_data
        assert "version" in lare_data
    
    def test_latest_data_version_v2(self):
        """Latest endpoint data should have version v2.0.0"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/lare-v2/latest?window=24h")
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["version"] == "v2.0.0"
    
    def test_latest_has_gate_object(self):
        """Latest endpoint data should have gate object with riskCap"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/lare-v2/latest?window=24h")
        assert response.status_code == 200
        data = response.json()
        
        gate = data["data"].get("gate")
        assert gate is not None
        assert "riskCap" in gate
        assert "blockNewPositions" in gate
        assert isinstance(gate["riskCap"], (int, float))
    
    def test_latest_has_components(self):
        """Latest endpoint data should have components array (Market, Flow, Bridge, Stables)"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/lare-v2/latest?window=24h")
        assert response.status_code == 200
        data = response.json()
        
        components = data["data"].get("components")
        assert components is not None
        assert isinstance(components, list)
        assert len(components) == 4  # Market, Flow, Bridge, Stables
        
        component_keys = [c["key"] for c in components]
        assert "market" in component_keys
        assert "flow" in component_keys
        assert "bridge" in component_keys
        assert "stables" in component_keys
    
    def test_latest_component_structure(self):
        """Each component should have score, direction, strength, confidence, drivers"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/lare-v2/latest?window=24h")
        assert response.status_code == 200
        data = response.json()
        
        for component in data["data"]["components"]:
            assert "key" in component
            assert "score" in component
            assert "direction" in component
            assert "confidence" in component
            assert "drivers" in component
            assert isinstance(component["drivers"], list)
    
    def test_latest_has_drivers(self):
        """Latest endpoint data should have drivers array"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/lare-v2/latest?window=24h")
        assert response.status_code == 200
        data = response.json()
        
        drivers = data["data"].get("drivers")
        assert drivers is not None
        assert isinstance(drivers, list)
    
    def test_latest_has_flags(self):
        """Latest endpoint data should have flags array"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/lare-v2/latest?window=24h")
        assert response.status_code == 200
        data = response.json()
        
        flags = data["data"].get("flags")
        assert flags is not None
        assert isinstance(flags, list)
    
    def test_latest_regime_valid_value(self):
        """Regime should be one of valid values"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/lare-v2/latest?window=24h")
        assert response.status_code == 200
        data = response.json()
        
        valid_regimes = ['RISK_ON_ALTS', 'MODERATE_RISK_ON', 'NEUTRAL', 'MODERATE_RISK_OFF', 'RISK_OFF']
        assert data["data"]["regime"] in valid_regimes


class TestLareV2Gate:
    """Tests for /api/v10/onchain-v2/lare-v2/gate endpoint"""
    
    def test_gate_returns_ok(self):
        """Gate endpoint should return ok:true"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/lare-v2/gate")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
    
    def test_gate_has_gate_object(self):
        """Gate endpoint should have gate object with riskCap"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/lare-v2/gate")
        assert response.status_code == 200
        data = response.json()
        
        gate = data.get("gate")
        assert gate is not None
        assert "riskCap" in gate
        assert "blockNewPositions" in gate
    
    def test_gate_has_confidence_regime_score(self):
        """Gate endpoint should have confidence, regime, score"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/lare-v2/gate")
        assert response.status_code == 200
        data = response.json()
        
        assert "confidence" in data
        assert "regime" in data
        assert "score" in data
    
    def test_gate_risk_cap_in_valid_range(self):
        """Risk cap should be between 0 and 1"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/lare-v2/gate")
        assert response.status_code == 200
        data = response.json()
        
        risk_cap = data["gate"]["riskCap"]
        assert 0 <= risk_cap <= 1


class TestLareV2Series:
    """Tests for /api/v10/onchain-v2/lare-v2/series endpoint"""
    
    def test_series_returns_ok(self):
        """Series endpoint should return ok:true"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/lare-v2/series?window=24h&range=30d")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
    
    def test_series_has_series_array(self):
        """Series endpoint should have series array"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/lare-v2/series?window=24h&range=30d")
        assert response.status_code == 200
        data = response.json()
        
        series = data.get("series")
        assert series is not None
        assert isinstance(series, list)
    
    def test_series_has_count(self):
        """Series endpoint should have count field"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/lare-v2/series?window=24h&range=30d")
        assert response.status_code == 200
        data = response.json()
        
        assert "count" in data
        assert data["count"] == len(data["series"])
    
    def test_series_point_structure(self):
        """Each series point should have t, score, confidence, regime, riskCap"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/lare-v2/series?window=24h&range=30d")
        assert response.status_code == 200
        data = response.json()
        
        if len(data["series"]) > 0:
            point = data["series"][0]
            assert "t" in point
            assert "score" in point
            assert "confidence" in point
            assert "regime" in point
            assert "riskCap" in point
    
    def test_series_7d_window(self):
        """Series endpoint should work with window=7d"""
        response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/lare-v2/series?window=7d&range=30d")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "series" in data


class TestLareV2DataConsistency:
    """Cross-endpoint consistency tests"""
    
    def test_health_and_latest_score_match(self):
        """Score in health endpoint should match latest endpoint"""
        health_response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/lare-v2/health")
        latest_response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/lare-v2/latest?window=24h")
        
        health_data = health_response.json()
        latest_data = latest_response.json()
        
        # Allow small delta for timing differences
        health_score = health_data["windows"]["24h"]["score"]
        latest_score = latest_data["data"]["score"]
        assert abs(health_score - latest_score) < 0.1  # Within 0.1 delta
    
    def test_gate_and_latest_gate_match(self):
        """Gate endpoint should match gate in latest endpoint"""
        gate_response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/lare-v2/gate")
        latest_response = requests.get(f"{BASE_URL}/api/v10/onchain-v2/lare-v2/latest?window=24h")
        
        gate_data = gate_response.json()
        latest_data = latest_response.json()
        
        # Risk cap should match
        assert gate_data["gate"]["riskCap"] == latest_data["data"]["gate"]["riskCap"]
        assert gate_data["gate"]["blockNewPositions"] == latest_data["data"]["gate"]["blockNewPositions"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
