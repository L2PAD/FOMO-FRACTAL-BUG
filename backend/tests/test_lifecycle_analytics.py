"""
Lifecycle Analytics API Tests
Tests for /api/connections/lifecycle, /api/connections/cluster-lifecycle, /api/connections/early-rotation/active
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestLifecycleAssets:
    """Tests for GET /api/connections/lifecycle - Asset-level lifecycle states"""
    
    def test_lifecycle_returns_ok(self):
        """Verify endpoint returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/connections/lifecycle")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"PASS: Lifecycle endpoint returns ok:true")
    
    def test_lifecycle_returns_data_array(self):
        """Verify data is an array"""
        response = requests.get(f"{BASE_URL}/api/connections/lifecycle")
        data = response.json()
        assert "data" in data
        assert isinstance(data["data"], list)
        print(f"PASS: Lifecycle returns data array with {len(data['data'])} items")
    
    def test_lifecycle_asset_count_minimum(self):
        """Verify at least 116 assets are tracked"""
        response = requests.get(f"{BASE_URL}/api/connections/lifecycle")
        data = response.json()
        assert len(data["data"]) >= 116
        print(f"PASS: {len(data['data'])} assets tracked (>= 116)")
    
    def test_lifecycle_asset_structure(self):
        """Verify each asset has required fields"""
        response = requests.get(f"{BASE_URL}/api/connections/lifecycle")
        data = response.json()
        required_fields = ["asset", "state", "confidence", "scores", "window"]
        
        for asset in data["data"][:5]:  # Check first 5
            for field in required_fields:
                assert field in asset, f"Missing field: {field}"
        print(f"PASS: Asset structure has all required fields")
    
    def test_lifecycle_state_values(self):
        """Verify state is one of 4 valid phases"""
        response = requests.get(f"{BASE_URL}/api/connections/lifecycle")
        data = response.json()
        valid_states = {"ACCUMULATION", "IGNITION", "EXPANSION", "DISTRIBUTION"}
        
        states_found = set()
        for asset in data["data"]:
            assert asset["state"] in valid_states, f"Invalid state: {asset['state']}"
            states_found.add(asset["state"])
        
        print(f"PASS: All states valid. Found: {states_found}")
    
    def test_lifecycle_confidence_range(self):
        """Verify confidence is between 0 and 1"""
        response = requests.get(f"{BASE_URL}/api/connections/lifecycle")
        data = response.json()
        
        for asset in data["data"]:
            assert 0 <= asset["confidence"] <= 1, f"Invalid confidence: {asset['confidence']}"
        print(f"PASS: All confidence values in 0-1 range")
    
    def test_lifecycle_scores_structure(self):
        """Verify scores has all 4 phase scores"""
        response = requests.get(f"{BASE_URL}/api/connections/lifecycle")
        data = response.json()
        score_keys = {"accumulation", "ignition", "expansion", "distribution"}
        
        for asset in data["data"][:5]:
            assert set(asset["scores"].keys()) == score_keys
            for key, val in asset["scores"].items():
                assert 0 <= val <= 1, f"Invalid score {key}: {val}"
        print(f"PASS: Scores structure correct with all 4 phases")
    
    def test_lifecycle_has_price_change(self):
        """Verify priceChange24h is present"""
        response = requests.get(f"{BASE_URL}/api/connections/lifecycle")
        data = response.json()
        
        assets_with_price = sum(1 for a in data["data"] if "priceChange24h" in a)
        assert assets_with_price > 0
        print(f"PASS: {assets_with_price} assets have priceChange24h")
    
    def test_lifecycle_igniting_count(self):
        """Verify igniting assets count"""
        response = requests.get(f"{BASE_URL}/api/connections/lifecycle")
        data = response.json()
        
        igniting = sum(1 for a in data["data"] if a["state"] == "IGNITION")
        print(f"INFO: {igniting} assets in IGNITION phase")
        assert igniting > 0
        print(f"PASS: Found {igniting} igniting assets")
    
    def test_lifecycle_distributing_count(self):
        """Verify distributing assets count"""
        response = requests.get(f"{BASE_URL}/api/connections/lifecycle")
        data = response.json()
        
        distributing = sum(1 for a in data["data"] if a["state"] == "DISTRIBUTION")
        print(f"INFO: {distributing} assets in DISTRIBUTION phase")
        assert distributing > 0
        print(f"PASS: Found {distributing} distributing assets")


class TestClusterLifecycle:
    """Tests for GET /api/connections/cluster-lifecycle - Cluster-level lifecycle states"""
    
    def test_cluster_lifecycle_returns_ok(self):
        """Verify endpoint returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/connections/cluster-lifecycle")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"PASS: Cluster lifecycle endpoint returns ok:true")
    
    def test_cluster_lifecycle_count(self):
        """Verify 4 clusters are returned"""
        response = requests.get(f"{BASE_URL}/api/connections/cluster-lifecycle")
        data = response.json()
        assert len(data["data"]) == 4
        print(f"PASS: {len(data['data'])} clusters returned")
    
    def test_cluster_lifecycle_structure(self):
        """Verify cluster structure has required fields"""
        response = requests.get(f"{BASE_URL}/api/connections/cluster-lifecycle")
        data = response.json()
        required_fields = ["cluster", "state", "confidence", "scores", "assetCount", "window"]
        
        for cluster in data["data"]:
            for field in required_fields:
                assert field in cluster, f"Missing field: {field}"
        print(f"PASS: Cluster structure has all required fields")
    
    def test_cluster_names(self):
        """Verify expected cluster names"""
        response = requests.get(f"{BASE_URL}/api/connections/cluster-lifecycle")
        data = response.json()
        
        cluster_names = {c["cluster"] for c in data["data"]}
        expected = {"Layer 1", "Layer 2", "Meme", "Alt"}
        
        # At least some expected clusters should be present
        assert len(cluster_names & expected) >= 3
        print(f"PASS: Found clusters: {cluster_names}")
    
    def test_cluster_asset_count(self):
        """Verify assetCount is positive"""
        response = requests.get(f"{BASE_URL}/api/connections/cluster-lifecycle")
        data = response.json()
        
        for cluster in data["data"]:
            assert cluster["assetCount"] > 0
        print(f"PASS: All clusters have positive asset counts")
    
    def test_cluster_scores_sum(self):
        """Verify cluster scores are normalized"""
        response = requests.get(f"{BASE_URL}/api/connections/cluster-lifecycle")
        data = response.json()
        
        for cluster in data["data"]:
            total = sum(cluster["scores"].values())
            assert 0.99 <= total <= 1.01, f"Scores don't sum to 1: {total}"
        print(f"PASS: Cluster scores are normalized")


class TestEarlyRotation:
    """Tests for GET /api/connections/early-rotation/active - Rotation signals"""
    
    def test_rotation_returns_ok(self):
        """Verify endpoint returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/connections/early-rotation/active")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"PASS: Early rotation endpoint returns ok:true")
    
    def test_rotation_returns_data_array(self):
        """Verify data is an array"""
        response = requests.get(f"{BASE_URL}/api/connections/early-rotation/active")
        data = response.json()
        assert "data" in data
        assert isinstance(data["data"], list)
        print(f"PASS: Rotation returns data array with {len(data['data'])} items")
    
    def test_rotation_structure(self):
        """Verify rotation structure has required fields"""
        response = requests.get(f"{BASE_URL}/api/connections/early-rotation/active")
        data = response.json()
        
        if len(data["data"]) > 0:
            required_fields = ["fromCluster", "toCluster", "erp", "class"]
            for rotation in data["data"]:
                for field in required_fields:
                    assert field in rotation, f"Missing field: {field}"
            print(f"PASS: Rotation structure has all required fields")
        else:
            print(f"INFO: No rotations detected (may be normal)")
    
    def test_rotation_erp_range(self):
        """Verify ERP is between 0 and 1"""
        response = requests.get(f"{BASE_URL}/api/connections/early-rotation/active")
        data = response.json()
        
        for rotation in data["data"]:
            assert 0 <= rotation["erp"] <= 1, f"Invalid ERP: {rotation['erp']}"
        print(f"PASS: All ERP values in 0-1 range")
    
    def test_rotation_class_values(self):
        """Verify class is one of valid values"""
        response = requests.get(f"{BASE_URL}/api/connections/early-rotation/active")
        data = response.json()
        valid_classes = {"IMMINENT", "BUILDING", "WATCH"}
        
        for rotation in data["data"]:
            assert rotation["class"] in valid_classes, f"Invalid class: {rotation['class']}"
        print(f"PASS: All rotation classes are valid")
    
    def test_rotation_has_notes(self):
        """Verify rotations have notes with details"""
        response = requests.get(f"{BASE_URL}/api/connections/early-rotation/active")
        data = response.json()
        
        for rotation in data["data"]:
            if "notes" in rotation:
                assert "volatility" in rotation["notes"]
                assert "funding" in rotation["notes"]
        print(f"PASS: Rotations have notes with volatility and funding")


class TestLifecycleIntegration:
    """Integration tests across lifecycle endpoints"""
    
    def test_asset_cluster_consistency(self):
        """Verify asset counts match cluster totals"""
        assets_resp = requests.get(f"{BASE_URL}/api/connections/lifecycle")
        clusters_resp = requests.get(f"{BASE_URL}/api/connections/cluster-lifecycle")
        
        assets = assets_resp.json()["data"]
        clusters = clusters_resp.json()["data"]
        
        total_from_clusters = sum(c["assetCount"] for c in clusters)
        assert total_from_clusters == len(assets)
        print(f"PASS: Asset count ({len(assets)}) matches cluster totals ({total_from_clusters})")
    
    def test_all_endpoints_respond(self):
        """Verify all 3 endpoints respond successfully"""
        endpoints = [
            "/api/connections/lifecycle",
            "/api/connections/cluster-lifecycle",
            "/api/connections/early-rotation/active"
        ]
        
        for endpoint in endpoints:
            response = requests.get(f"{BASE_URL}{endpoint}")
            assert response.status_code == 200
            assert response.json().get("ok") is True
        print(f"PASS: All 3 lifecycle endpoints respond successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
