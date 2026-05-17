"""
Test Connections Analytics API endpoints for Actor Hub
Tests: smart-followers, paths, timeseries, ai/cached, accounts, trend-adjusted, early-signal, score/mock
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestConnectionsAnalyticsAPI:
    """Test all connections analytics endpoints"""
    
    # Test account ID for vitalikbuterin
    TEST_ACCOUNT = "vitalikbuterin"
    TEST_AUTHOR_ID = "demo_vitalikbuterin"
    
    def test_smart_followers_endpoint(self):
        """Test /api/connections/smart-followers/{account_id} returns ok:true with data"""
        response = requests.get(f"{BASE_URL}/api/connections/smart-followers/{self.TEST_ACCOUNT}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") == True, f"Expected ok:true, got {data}"
        assert "data" in data, "Missing 'data' field"
        
        # Validate data structure
        sf_data = data["data"]
        assert "smart_followers_score_0_1" in sf_data, "Missing smart_followers_score_0_1"
        assert "followers_count" in sf_data, "Missing followers_count"
        assert "breakdown" in sf_data, "Missing breakdown"
        assert "top_followers" in sf_data, "Missing top_followers"
        
        # Validate breakdown structure
        breakdown = sf_data["breakdown"]
        assert "tier_shares" in breakdown, "Missing tier_shares in breakdown"
        assert "tier_counts" in breakdown, "Missing tier_counts in breakdown"
        
        print(f"PASS: smart-followers returns score {int(sf_data['smart_followers_score_0_1']*100)}/100")
    
    def test_network_paths_endpoint(self):
        """Test /api/connections/paths/{account_id} returns ok:true with paths"""
        response = requests.get(f"{BASE_URL}/api/connections/paths/{self.TEST_ACCOUNT}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") == True, f"Expected ok:true, got {data}"
        assert "data" in data, "Missing 'data' field"
        
        # Validate data structure
        paths_data = data["data"]
        assert "paths" in paths_data, "Missing paths"
        assert "exposure" in paths_data, "Missing exposure"
        
        # Validate paths structure
        paths = paths_data["paths"]
        assert "paths" in paths, "Missing paths.paths"
        assert len(paths["paths"]) > 0, "Expected at least one path"
        
        # Validate first path structure
        first_path = paths["paths"][0]
        assert "hops" in first_path, "Missing hops in path"
        assert "nodes" in first_path, "Missing nodes in path"
        assert "kind" in first_path, "Missing kind in path"
        
        # Validate exposure structure
        exposure = paths_data["exposure"]
        assert "exposure_score_0_1" in exposure, "Missing exposure_score_0_1"
        assert "exposure_tier" in exposure, "Missing exposure_tier"
        
        print(f"PASS: paths returns {len(paths['paths'])} paths, exposure score {int(exposure['exposure_score_0_1']*100)}/100")
    
    def test_timeseries_endpoint(self):
        """Test /api/connections/timeseries/{account_id} returns ok:true with 30 data points"""
        response = requests.get(f"{BASE_URL}/api/connections/timeseries/{self.TEST_ACCOUNT}?window=30d")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") == True, f"Expected ok:true, got {data}"
        assert "data" in data, "Missing 'data' field"
        
        # Validate data structure
        ts_data = data["data"]
        assert "followers" in ts_data, "Missing followers"
        assert "engagement" in ts_data, "Missing engagement"
        assert "scores" in ts_data, "Missing scores"
        
        # Validate 30 data points
        assert len(ts_data["followers"]) == 30, f"Expected 30 followers data points, got {len(ts_data['followers'])}"
        assert len(ts_data["engagement"]) == 30, f"Expected 30 engagement data points, got {len(ts_data['engagement'])}"
        assert len(ts_data["scores"]) == 30, f"Expected 30 scores data points, got {len(ts_data['scores'])}"
        
        # Validate first data point structure
        first_follower = ts_data["followers"][0]
        assert "ts" in first_follower, "Missing ts in followers data"
        assert "followers" in first_follower, "Missing followers count"
        
        print(f"PASS: timeseries returns {len(ts_data['followers'])} data points")
    
    def test_timeseries_summary_endpoint(self):
        """Test /api/connections/timeseries/{account_id}/summary returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/connections/timeseries/{self.TEST_ACCOUNT}/summary?window=30d")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") == True, f"Expected ok:true, got {data}"
        assert "data" in data, "Missing 'data' field"
        
        # Validate summary structure
        summary = data["data"]
        assert "followers" in summary, "Missing followers summary"
        assert "engagement" in summary, "Missing engagement summary"
        assert "scores" in summary, "Missing scores summary"
        
        print(f"PASS: timeseries/summary returns followers current: {summary['followers']['current']}")
    
    def test_ai_cached_endpoint(self):
        """Test /api/connections/ai/cached/{account_id} returns ok:true with verdict, headline, key_drivers"""
        response = requests.get(f"{BASE_URL}/api/connections/ai/cached/{self.TEST_ACCOUNT}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") == True, f"Expected ok:true, got {data}"
        assert "data" in data, "Missing 'data' field"
        
        # Validate AI summary structure
        ai_data = data["data"]
        assert "verdict" in ai_data, "Missing verdict"
        assert "headline" in ai_data, "Missing headline"
        assert "key_drivers" in ai_data, "Missing key_drivers"
        assert "risks" in ai_data, "Missing risks"
        assert "recommendations" in ai_data, "Missing recommendations"
        assert "evidence" in ai_data, "Missing evidence"
        
        # Validate verdict is valid
        valid_verdicts = ["STRONG", "GOOD", "MIXED", "RISKY", "INSUFFICIENT_DATA"]
        assert ai_data["verdict"] in valid_verdicts, f"Invalid verdict: {ai_data['verdict']}"
        
        # Validate key_drivers is a list
        assert isinstance(ai_data["key_drivers"], list), "key_drivers should be a list"
        assert len(ai_data["key_drivers"]) > 0, "key_drivers should not be empty"
        
        print(f"PASS: ai/cached returns verdict={ai_data['verdict']}, headline='{ai_data['headline'][:50]}...'")
    
    def test_accounts_endpoint(self):
        """Test /api/connections/accounts/{author_id} returns ok:true with profile data"""
        response = requests.get(f"{BASE_URL}/api/connections/accounts/{self.TEST_AUTHOR_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") == True, f"Expected ok:true, got {data}"
        assert "data" in data, "Missing 'data' field"
        
        # Validate account data structure
        account = data["data"]
        assert "author_id" in account, "Missing author_id"
        assert "scores" in account, "Missing scores"
        assert "activity" in account, "Missing activity"
        assert "trend" in account, "Missing trend"
        
        # Validate scores structure
        scores = account["scores"]
        assert "influence_score" in scores, "Missing influence_score"
        assert "x_score" in scores, "Missing x_score"
        
        print(f"PASS: accounts returns influence_score={scores['influence_score']}, x_score={scores['x_score']}")
    
    def test_trend_adjusted_endpoint(self):
        """Test /api/connections/trend-adjusted POST returns ok:true with adjusted scores"""
        payload = {
            "influence_score": 500,
            "x_score": 300,
            "velocity_norm": 0.3,
            "acceleration_norm": 0.1
        }
        response = requests.post(f"{BASE_URL}/api/connections/trend-adjusted", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") == True, f"Expected ok:true, got {data}"
        assert "data" in data, "Missing 'data' field"
        
        # Validate trend-adjusted structure
        trend_data = data["data"]
        assert "influence" in trend_data, "Missing influence"
        assert "x_score" in trend_data, "Missing x_score"
        
        # Validate influence structure
        influence = trend_data["influence"]
        assert "base_score" in influence, "Missing base_score"
        assert "adjusted_score" in influence, "Missing adjusted_score"
        
        print(f"PASS: trend-adjusted returns base={influence['base_score']}, adjusted={influence['adjusted_score']}")
    
    def test_early_signal_endpoint(self):
        """Test /api/connections/early-signal POST returns ok:true with badge"""
        payload = {
            "influence_base": 500,
            "trend": {"velocity_norm": 0.3, "acceleration_norm": 0.1},
            "signal_noise": 6,
            "risk_level": "low"
        }
        response = requests.post(f"{BASE_URL}/api/connections/early-signal", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") == True, f"Expected ok:true, got {data}"
        assert "data" in data, "Missing 'data' field"
        
        # Validate early signal structure
        signal = data["data"]
        assert "early_signal_score" in signal, "Missing early_signal_score"
        assert "badge" in signal, "Missing badge"
        assert "confidence" in signal, "Missing confidence"
        
        # Validate badge is valid
        valid_badges = ["breakout", "rising", "none"]
        assert signal["badge"] in valid_badges, f"Invalid badge: {signal['badge']}"
        
        print(f"PASS: early-signal returns score={signal['early_signal_score']}, badge={signal['badge']}")
    
    def test_score_mock_endpoint(self):
        """Test /api/connections/score/mock returns ok:true with metrics"""
        response = requests.get(f"{BASE_URL}/api/connections/score/mock")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") == True, f"Expected ok:true, got {data}"
        assert "data" in data, "Missing 'data' field"
        
        # Validate score mock structure
        score_data = data["data"]
        assert "grade" in score_data, "Missing grade"
        assert "influence_score" in score_data, "Missing influence_score"
        assert "metrics" in score_data, "Missing metrics"
        
        # Validate metrics structure
        metrics = score_data["metrics"]
        assert "real_views" in metrics, "Missing real_views"
        assert "engagement_quality" in metrics, "Missing engagement_quality"
        assert "posting_consistency" in metrics, "Missing posting_consistency"
        
        print(f"PASS: score/mock returns grade={score_data['grade']}, influence={score_data['influence_score']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
