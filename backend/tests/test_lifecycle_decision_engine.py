"""
Lifecycle Decision Engine Tests
Tests for the new decision scoring layer: score, action, entry, marketState, pumpSignals
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestLifecycleDecisionEngine:
    """Tests for GET /api/connections/lifecycle with decision engine fields"""
    
    def test_lifecycle_returns_ok(self):
        """Verify lifecycle endpoint returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/connections/lifecycle")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
    
    def test_lifecycle_has_market_state(self):
        """Verify marketState is present in response"""
        response = requests.get(f"{BASE_URL}/api/connections/lifecycle")
        data = response.json()
        assert "marketState" in data
        ms = data["marketState"]
        assert ms is not None
    
    def test_market_state_structure(self):
        """Verify marketState has required fields: dominant, dominantCount, action, phaseCounts"""
        response = requests.get(f"{BASE_URL}/api/connections/lifecycle")
        data = response.json()
        ms = data["marketState"]
        
        assert "dominant" in ms
        assert "dominantCount" in ms
        assert "action" in ms
        assert "phaseCounts" in ms
        
        # Verify dominant is a valid phase
        assert ms["dominant"] in ["ACCUMULATION", "IGNITION", "EXPANSION", "DISTRIBUTION"]
        
        # Verify dominantCount is positive
        assert isinstance(ms["dominantCount"], int)
        assert ms["dominantCount"] > 0
    
    def test_market_state_action_structure(self):
        """Verify marketState.action has headline, do[], dont[]"""
        response = requests.get(f"{BASE_URL}/api/connections/lifecycle")
        data = response.json()
        action = data["marketState"]["action"]
        
        assert "headline" in action
        assert "do" in action
        assert "dont" in action
        
        assert isinstance(action["headline"], str)
        assert isinstance(action["do"], list)
        assert isinstance(action["dont"], list)
        assert len(action["do"]) > 0
        assert len(action["dont"]) > 0
    
    def test_market_state_phase_counts(self):
        """Verify phaseCounts has all 4 phases"""
        response = requests.get(f"{BASE_URL}/api/connections/lifecycle")
        data = response.json()
        counts = data["marketState"]["phaseCounts"]
        
        assert "ACCUMULATION" in counts
        assert "IGNITION" in counts
        assert "EXPANSION" in counts
        assert "DISTRIBUTION" in counts
        
        # Verify counts are non-negative integers
        for phase, count in counts.items():
            assert isinstance(count, int)
            assert count >= 0
    
    def test_lifecycle_has_pump_signals(self):
        """Verify pumpSignals is present in response"""
        response = requests.get(f"{BASE_URL}/api/connections/lifecycle")
        data = response.json()
        assert "pumpSignals" in data
        assert isinstance(data["pumpSignals"], list)
    
    def test_pump_signal_structure(self):
        """Verify pump signals have required fields"""
        response = requests.get(f"{BASE_URL}/api/connections/lifecycle")
        data = response.json()
        signals = data["pumpSignals"]
        
        if len(signals) > 0:
            signal = signals[0]
            assert "symbol" in signal
            assert "score" in signal
            assert "label" in signal
            assert "window" in signal
            assert "phase" in signal
            assert "drivers" in signal
            
            # Verify score is 0-1
            assert 0 <= signal["score"] <= 1
            
            # Verify label is valid
            assert signal["label"] in ["EARLY PUMP", "BREAKOUT FORMING", "MOMENTUM BUILDING"]
            
            # Verify window is valid
            assert signal["window"] in ["EARLY", "OPEN", "CLOSING", "LATE"]
            
            # Verify drivers is a list
            assert isinstance(signal["drivers"], list)
    
    def test_asset_has_score(self):
        """Verify assets have score field (0-1)"""
        response = requests.get(f"{BASE_URL}/api/connections/lifecycle")
        data = response.json()
        assets = data["data"]
        
        assert len(assets) > 0
        for asset in assets[:10]:  # Check first 10
            assert "score" in asset
            assert isinstance(asset["score"], (int, float))
            assert 0 <= asset["score"] <= 1
    
    def test_asset_has_action(self):
        """Verify assets have action field (STRONG BUY/BUY/HOLD/AVOID/EXIT)"""
        response = requests.get(f"{BASE_URL}/api/connections/lifecycle")
        data = response.json()
        assets = data["data"]
        
        valid_actions = ["STRONG BUY", "BUY", "HOLD", "AVOID", "EXIT"]
        for asset in assets[:10]:
            assert "action" in asset
            assert asset["action"] in valid_actions
    
    def test_asset_has_entry(self):
        """Verify assets have entry field (EARLY/BREAKOUT/LATE/NO ENTRY)"""
        response = requests.get(f"{BASE_URL}/api/connections/lifecycle")
        data = response.json()
        assets = data["data"]
        
        valid_entries = ["EARLY", "BREAKOUT", "LATE", "NO ENTRY", "NEUTRAL"]
        for asset in assets[:10]:
            assert "entry" in asset
            assert asset["entry"] in valid_entries
    
    def test_asset_sorted_by_score(self):
        """Verify assets are sorted by score (descending)"""
        response = requests.get(f"{BASE_URL}/api/connections/lifecycle")
        data = response.json()
        assets = data["data"]
        
        scores = [a["score"] for a in assets]
        assert scores == sorted(scores, reverse=True)
    
    def test_action_distribution(self):
        """Verify action distribution includes multiple types"""
        response = requests.get(f"{BASE_URL}/api/connections/lifecycle")
        data = response.json()
        assets = data["data"]
        
        actions = set(a["action"] for a in assets)
        # Should have at least 2 different action types
        assert len(actions) >= 2
    
    def test_entry_distribution(self):
        """Verify entry distribution includes multiple types"""
        response = requests.get(f"{BASE_URL}/api/connections/lifecycle")
        data = response.json()
        assets = data["data"]
        
        entries = set(a["entry"] for a in assets)
        # Should have at least 2 different entry types
        assert len(entries) >= 2


class TestClusterLifecycle:
    """Tests for GET /api/connections/cluster-lifecycle"""
    
    def test_cluster_lifecycle_returns_ok(self):
        """Verify cluster-lifecycle endpoint returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/connections/cluster-lifecycle")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
    
    def test_cluster_has_required_fields(self):
        """Verify clusters have state, scores, assetCount"""
        response = requests.get(f"{BASE_URL}/api/connections/cluster-lifecycle")
        data = response.json()
        clusters = data["data"]
        
        assert len(clusters) > 0
        for cluster in clusters:
            assert "cluster" in cluster
            assert "state" in cluster
            assert "scores" in cluster
            assert "assetCount" in cluster
            assert "confidence" in cluster
    
    def test_cluster_state_valid(self):
        """Verify cluster state is a valid phase"""
        response = requests.get(f"{BASE_URL}/api/connections/cluster-lifecycle")
        data = response.json()
        clusters = data["data"]
        
        valid_states = ["ACCUMULATION", "IGNITION", "EXPANSION", "DISTRIBUTION"]
        for cluster in clusters:
            assert cluster["state"] in valid_states
    
    def test_cluster_scores_normalized(self):
        """Verify cluster scores sum to approximately 1"""
        response = requests.get(f"{BASE_URL}/api/connections/cluster-lifecycle")
        data = response.json()
        clusters = data["data"]
        
        for cluster in clusters:
            scores = cluster["scores"]
            total = sum(scores.values())
            assert 0.99 <= total <= 1.01  # Allow small floating point error


class TestEarlyRotation:
    """Tests for GET /api/connections/early-rotation/active"""
    
    def test_early_rotation_returns_ok(self):
        """Verify early-rotation endpoint returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/connections/early-rotation/active")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
    
    def test_rotation_has_required_fields(self):
        """Verify rotations have erp, class, notes"""
        response = requests.get(f"{BASE_URL}/api/connections/early-rotation/active")
        data = response.json()
        rotations = data["data"]
        
        if len(rotations) > 0:
            rotation = rotations[0]
            assert "fromCluster" in rotation
            assert "toCluster" in rotation
            assert "erp" in rotation
            assert "class" in rotation
            assert "notes" in rotation
    
    def test_rotation_erp_range(self):
        """Verify ERP is between 0 and 1"""
        response = requests.get(f"{BASE_URL}/api/connections/early-rotation/active")
        data = response.json()
        rotations = data["data"]
        
        for rotation in rotations:
            assert 0 <= rotation["erp"] <= 1
    
    def test_rotation_class_valid(self):
        """Verify rotation class is valid"""
        response = requests.get(f"{BASE_URL}/api/connections/early-rotation/active")
        data = response.json()
        rotations = data["data"]
        
        valid_classes = ["IMMINENT", "BUILDING", "WATCH"]
        for rotation in rotations:
            assert rotation["class"] in valid_classes


class TestDataConsistency:
    """Tests for data consistency across endpoints"""
    
    def test_asset_count_matches_phase_counts(self):
        """Verify total assets equals sum of phase counts"""
        response = requests.get(f"{BASE_URL}/api/connections/lifecycle")
        data = response.json()
        
        total_assets = len(data["data"])
        phase_counts = data["marketState"]["phaseCounts"]
        sum_phases = sum(phase_counts.values())
        
        assert total_assets == sum_phases
    
    def test_dominant_phase_has_highest_count(self):
        """Verify dominant phase has the highest count"""
        response = requests.get(f"{BASE_URL}/api/connections/lifecycle")
        data = response.json()
        
        ms = data["marketState"]
        dominant = ms["dominant"]
        dominant_count = ms["dominantCount"]
        phase_counts = ms["phaseCounts"]
        
        assert phase_counts[dominant] == dominant_count
        assert dominant_count == max(phase_counts.values())
    
    def test_cluster_asset_count_matches_total(self):
        """Verify sum of cluster asset counts equals total assets"""
        lc_response = requests.get(f"{BASE_URL}/api/connections/lifecycle")
        cl_response = requests.get(f"{BASE_URL}/api/connections/cluster-lifecycle")
        
        total_assets = len(lc_response.json()["data"])
        cluster_sum = sum(c["assetCount"] for c in cl_response.json()["data"])
        
        assert total_assets == cluster_sum


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
