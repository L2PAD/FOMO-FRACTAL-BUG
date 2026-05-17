"""
DashboardPack V1 - Decision Intelligence Dashboard API Tests
Tests all 6 dashboard endpoints with various filter combinations
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com')

class TestDashboardOverview:
    """Tests for /api/dashboard/overview endpoint"""
    
    def test_overview_default_params(self):
        """Test overview with default params (horizon=all, period=7d)"""
        response = requests.get(f"{BASE_URL}/api/dashboard/overview?horizon=all&period=7d")
        assert response.status_code == 200
        data = response.json()
        
        # Verify all required fields exist
        assert "total_forecasts" in data
        assert "evaluated" in data
        assert "evaluated_pct" in data
        assert "hit_rate" in data
        assert "fp_rate" in data
        assert "avg_error" in data
        assert "sample_size" in data
        assert "active_layers" in data
        
        # Verify data types
        assert isinstance(data["total_forecasts"], int)
        assert isinstance(data["evaluated"], int)
        assert isinstance(data["evaluated_pct"], (int, float))
        assert isinstance(data["hit_rate"], (int, float))
        assert isinstance(data["fp_rate"], (int, float))
        assert isinstance(data["avg_error"], (int, float))
        assert isinstance(data["sample_size"], int)
        assert isinstance(data["active_layers"], dict)
    
    def test_overview_horizon_24h(self):
        """Test overview with horizon=24H filter"""
        response = requests.get(f"{BASE_URL}/api/dashboard/overview?horizon=24H&period=7d")
        assert response.status_code == 200
        data = response.json()
        assert "total_forecasts" in data
        assert data["total_forecasts"] >= 0
    
    def test_overview_horizon_7d(self):
        """Test overview with horizon=7D filter"""
        response = requests.get(f"{BASE_URL}/api/dashboard/overview?horizon=7D&period=7d")
        assert response.status_code == 200
        data = response.json()
        assert "total_forecasts" in data
    
    def test_overview_horizon_30d(self):
        """Test overview with horizon=30D filter"""
        response = requests.get(f"{BASE_URL}/api/dashboard/overview?horizon=30D&period=all")
        assert response.status_code == 200
        data = response.json()
        assert "total_forecasts" in data
    
    def test_overview_period_24h(self):
        """Test overview with period=24h filter"""
        response = requests.get(f"{BASE_URL}/api/dashboard/overview?horizon=all&period=24h")
        assert response.status_code == 200
        data = response.json()
        assert "total_forecasts" in data
    
    def test_overview_period_30d(self):
        """Test overview with period=30d filter"""
        response = requests.get(f"{BASE_URL}/api/dashboard/overview?horizon=all&period=30d")
        assert response.status_code == 200
        data = response.json()
        assert "total_forecasts" in data
    
    def test_overview_period_all(self):
        """Test overview with period=all filter"""
        response = requests.get(f"{BASE_URL}/api/dashboard/overview?horizon=all&period=all")
        assert response.status_code == 200
        data = response.json()
        assert "total_forecasts" in data


class TestDashboardCalibration:
    """Tests for /api/dashboard/calibration endpoint"""
    
    def test_calibration_default_params(self):
        """Test calibration with default params"""
        response = requests.get(f"{BASE_URL}/api/dashboard/calibration?horizon=all&period=7d")
        assert response.status_code == 200
        data = response.json()
        
        # Verify all required fields exist
        assert "ece" in data
        assert "brier" in data
        assert "sharpness" in data
        assert "sample_size" in data
        assert "buckets" in data
        
        # Verify data types
        assert isinstance(data["sample_size"], int)
        assert isinstance(data["buckets"], list)
        
        # Verify bucket structure if buckets exist
        if data["buckets"]:
            bucket = data["buckets"][0]
            assert "conf" in bucket
            assert "actual" in bucket
            assert "count" in bucket
    
    def test_calibration_with_horizon_filter(self):
        """Test calibration with horizon filter"""
        response = requests.get(f"{BASE_URL}/api/dashboard/calibration?horizon=24H&period=7d")
        assert response.status_code == 200
        data = response.json()
        assert "ece" in data
        assert "buckets" in data


class TestDashboardInteraction:
    """Tests for /api/dashboard/interaction endpoint"""
    
    def test_interaction_default_params(self):
        """Test interaction with default params"""
        response = requests.get(f"{BASE_URL}/api/dashboard/interaction?horizon=all&period=7d")
        assert response.status_code == 200
        data = response.json()
        
        # Verify all required fields exist
        assert "sample_size" in data
        assert "state_distribution" in data
        assert "performance_by_state" in data
        assert "confidence_delta" in data
        assert "confidence_flow" in data
        
        # Verify data types
        assert isinstance(data["sample_size"], int)
        assert isinstance(data["state_distribution"], dict)
        assert isinstance(data["performance_by_state"], list)
        assert isinstance(data["confidence_delta"], dict)
        assert isinstance(data["confidence_flow"], dict)
        
        # Verify confidence_flow structure
        flow = data["confidence_flow"]
        assert "avg_before" in flow
        assert "avg_after" in flow
        assert "avg_delta" in flow
    
    def test_interaction_with_filters(self):
        """Test interaction with various filters"""
        response = requests.get(f"{BASE_URL}/api/dashboard/interaction?horizon=30D&period=30d")
        assert response.status_code == 200
        data = response.json()
        assert "sample_size" in data


class TestDashboardDecision:
    """Tests for /api/dashboard/decision endpoint"""
    
    def test_decision_default_params(self):
        """Test decision with default params"""
        response = requests.get(f"{BASE_URL}/api/dashboard/decision?horizon=all&period=7d")
        assert response.status_code == 200
        data = response.json()
        
        # Verify all required fields exist
        assert "sample_size" in data
        assert "direction_distribution" in data
        assert "by_horizon" in data
        
        # Verify data types
        assert isinstance(data["sample_size"], int)
        assert isinstance(data["direction_distribution"], dict)
        assert isinstance(data["by_horizon"], list)
        
        # Verify direction_distribution contains expected keys if data exists
        if data["direction_distribution"]:
            # Should contain LONG, SHORT, NEUTRAL
            for key in data["direction_distribution"].keys():
                assert key in ["LONG", "SHORT", "NEUTRAL"]
    
    def test_decision_by_horizon_structure(self):
        """Test decision by_horizon array structure"""
        response = requests.get(f"{BASE_URL}/api/dashboard/decision?horizon=all&period=7d")
        assert response.status_code == 200
        data = response.json()
        
        if data["by_horizon"]:
            entry = data["by_horizon"][0]
            assert "horizon" in entry
            assert "long" in entry
            assert "short" in entry
            assert "neutral" in entry


class TestDashboardDistribution:
    """Tests for /api/dashboard/distribution endpoint"""
    
    def test_distribution_default_params(self):
        """Test distribution with default params"""
        response = requests.get(f"{BASE_URL}/api/dashboard/distribution?horizon=all&period=7d")
        assert response.status_code == 200
        data = response.json()
        
        # Verify required field exists
        assert "confidence_histogram" in data
        assert isinstance(data["confidence_histogram"], list)
        
        # Verify histogram structure
        if data["confidence_histogram"]:
            bucket = data["confidence_histogram"][0]
            assert "bucket" in bucket
            assert "count" in bucket
    
    def test_distribution_has_5_buckets(self):
        """Test distribution returns 5 confidence buckets"""
        response = requests.get(f"{BASE_URL}/api/dashboard/distribution?horizon=all&period=7d")
        assert response.status_code == 200
        data = response.json()
        
        # Should have 5 buckets: 0.0-0.2, 0.2-0.4, 0.4-0.6, 0.6-0.8, 0.8-1.0
        assert len(data["confidence_histogram"]) == 5


class TestDashboardAlerts:
    """Tests for /api/dashboard/alerts endpoint"""
    
    def test_alerts_default_params(self):
        """Test alerts with default params"""
        response = requests.get(f"{BASE_URL}/api/dashboard/alerts?horizon=all&period=7d")
        assert response.status_code == 200
        data = response.json()
        
        # Verify required field exists
        assert "alerts" in data
        assert isinstance(data["alerts"], list)
        
        # Verify alert structure if alerts exist
        if data["alerts"]:
            alert = data["alerts"][0]
            assert "type" in alert
            assert "message" in alert
            assert "severity" in alert
    
    def test_alerts_severity_values(self):
        """Test alerts have valid severity values"""
        response = requests.get(f"{BASE_URL}/api/dashboard/alerts?horizon=all&period=7d")
        assert response.status_code == 200
        data = response.json()
        
        valid_severities = ["high", "medium", "low"]
        for alert in data["alerts"]:
            assert alert["severity"] in valid_severities


class TestDashboardFilterCombinations:
    """Tests for various filter combinations across all endpoints"""
    
    @pytest.mark.parametrize("horizon", ["all", "24H", "7D", "30D"])
    @pytest.mark.parametrize("period", ["24h", "7d", "30d", "all"])
    def test_overview_all_filter_combinations(self, horizon, period):
        """Test overview endpoint with all filter combinations"""
        response = requests.get(f"{BASE_URL}/api/dashboard/overview?horizon={horizon}&period={period}")
        assert response.status_code == 200
        data = response.json()
        assert "total_forecasts" in data
    
    @pytest.mark.parametrize("endpoint", ["overview", "calibration", "interaction", "decision", "distribution", "alerts"])
    def test_all_endpoints_respond(self, endpoint):
        """Test all 6 endpoints respond with 200"""
        response = requests.get(f"{BASE_URL}/api/dashboard/{endpoint}?horizon=all&period=7d")
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
