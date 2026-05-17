"""
P1 Core Registry Integration Tests
====================================
Tests for:
1. Graph4 rolling curve endpoint (7D, 30D)
2. Fractal module TypeScript Core endpoints
3. Prediction audit endpoint
4. Bootstrap status endpoint
5. Freeze guard functionality
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com').rstrip('/')


class TestGraph4RollingCurve:
    """Test /api/prediction/exchange/graph4 endpoint for rolling expectation curve."""

    def test_graph4_7d_returns_ok(self):
        """Graph4 with horizon=7D returns ok:true with rollingForecasts data."""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph4", params={
            "asset": "BTC",
            "horizon": "7D"
        })
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "rollingForecasts" in data
        assert isinstance(data["rollingForecasts"], list)
        assert "priceSeries" in data
        assert data["asset"] == "BTC"
        assert data["horizon"] == "7D"
        assert data["nowPrice"] > 0

    def test_graph4_30d_returns_ok(self):
        """Graph4 with horizon=30D returns ok:true with rollingForecasts and band data."""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph4", params={
            "asset": "BTC",
            "horizon": "30D"
        })
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "rollingForecasts" in data
        assert isinstance(data["rollingForecasts"], list)
        assert len(data["rollingForecasts"]) > 0
        assert data["horizon"] == "30D"
        
        # 30D should have band data
        assert "band" in data
        if data["band"]:
            assert "medianTarget" in data["band"]
            assert "bandCore" in data["band"]
            assert "bandWide" in data["band"]

    def test_graph4_forecast_has_required_fields(self):
        """Verify rollingForecasts entries have all required fields for NOW stitch point."""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph4", params={
            "asset": "BTC",
            "horizon": "7D"
        })
        data = response.json()
        
        if data["rollingForecasts"]:
            forecast = data["rollingForecasts"][0]
            required_fields = ["madeAtTs", "horizonDays", "entryPrice", "targetPrice", 
                              "expectedMovePct", "direction", "confidence"]
            for field in required_fields:
                assert field in forecast, f"Missing field: {field}"
            
            assert isinstance(forecast["madeAtTs"], int)
            assert forecast["horizonDays"] == 7
            assert forecast["entryPrice"] > 0
            assert forecast["targetPrice"] > 0


class TestFractalCoreEndpoints:
    """Test TypeScript Core /api/v10/fractal/* endpoints."""

    def test_fractal_health_returns_ok(self):
        """GET /api/v10/fractal/health returns ok:true with module:'fractal' and status:HEALTHY."""
        response = requests.get(f"{BASE_URL}/api/v10/fractal/health")
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert data["module"] == "fractal"
        assert data["status"] in ["HEALTHY", "DEGRADED", "DOWN"]
        assert "forecasts" in data
        assert data["forecasts"]["total"] > 0

    def test_fractal_config_returns_version(self):
        """GET /api/v10/fractal/config returns ok:true with version 4.0.0."""
        response = requests.get(f"{BASE_URL}/api/v10/fractal/config")
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert data["version"] == "4.0.0"
        assert "config" in data
        assert data["config"]["horizons"] == [7, 30]
        assert "thresholds" in data["config"]
        assert data["config"]["thresholds"]["driftMax"] == 0.25
        assert data["config"]["thresholds"]["calibrationMax"] == 0.20

    def test_fractal_jobs_returns_daily_job(self):
        """GET /api/v10/fractal/jobs returns ok:true with fractal:daily job."""
        response = requests.get(f"{BASE_URL}/api/v10/fractal/jobs")
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "jobs" in data
        assert len(data["jobs"]) >= 1
        
        # Find fractal:daily job
        daily_job = next((j for j in data["jobs"] if j["name"] == "fractal:daily"), None)
        assert daily_job is not None, "fractal:daily job not found"
        assert daily_job["schedule"] == "10 0 * * *"
        assert daily_job["runOnStartup"] is True

    def test_fractal_dashboard_returns_full_dto(self):
        """GET /api/v10/fractal/dashboard returns moduleName:'fractal' with health and jobs."""
        response = requests.get(f"{BASE_URL}/api/v10/fractal/dashboard")
        assert response.status_code == 200
        data = response.json()
        
        assert data["moduleName"] == "fractal"
        assert data["version"] == "4.0.0"
        assert "health" in data
        assert data["health"]["ok"] is True
        assert data["health"]["module"] == "fractal"
        assert "jobs" in data
        assert "config" in data


class TestPredictionAudit:
    """Test /api/prediction/audit endpoint."""

    def test_audit_returns_horizons_7d_and_30d(self):
        """GET /api/prediction/audit?asset=BTC returns ok:true with horizons 7D and 30D."""
        response = requests.get(f"{BASE_URL}/api/prediction/audit", params={"asset": "BTC"})
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "horizons" in data
        assert "7D" in data["horizons"]
        assert "30D" in data["horizons"]
        
        # Verify 7D data
        h7d = data["horizons"]["7D"]
        assert "total" in h7d
        assert "winRate" in h7d
        assert "calibration" in h7d
        
        # Verify 30D data
        h30d = data["horizons"]["30D"]
        assert "total" in h30d
        assert "winRate" in h30d


class TestBootstrapStatus:
    """Test /api/system/bootstrap/status endpoint."""

    def test_bootstrap_status_returns_forecasts(self):
        """GET /api/system/bootstrap/status returns total forecasts > 0."""
        response = requests.get(f"{BASE_URL}/api/system/bootstrap/status", params={"asset": "BTC"})
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert data["total"] > 0
        assert data["evaluated"] > 0
        assert "horizons" in data
        assert "7D" in data["horizons"]
        assert "30D" in data["horizons"]


class TestFreezeGuard:
    """Test freeze guard functionality (read-only verification)."""

    def test_config_shows_freeze_status(self):
        """Verify fractal config shows freeze status."""
        response = requests.get(f"{BASE_URL}/api/v10/fractal/config")
        data = response.json()
        
        assert "config" in data
        assert "freezeEnabled" in data["config"]
        # Currently should be false
        assert data["config"]["freezeEnabled"] is False

    def test_health_shows_freeze_status(self):
        """Verify fractal health shows freeze status."""
        response = requests.get(f"{BASE_URL}/api/v10/fractal/health")
        data = response.json()
        
        assert "freeze" in data
        # Currently should be false
        assert data["freeze"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
