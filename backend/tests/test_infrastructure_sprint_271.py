"""
Sprint 271 — Infrastructure Completion Tests
=============================================
Tests for:
1. /api/os/liquidity-evolution — dynamics with trend
2. /api/os/state — liquidity_evolution field
3. /api/os/opportunities — move_confidence + liquidity_alignment
4. /api/engine/monitoring/events — intensity + clusters + cluster_size
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestLiquidityEvolution:
    """Test /api/os/liquidity-evolution endpoint"""
    
    def test_liquidity_evolution_returns_ok(self):
        """Endpoint returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/os/liquidity-evolution")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
    
    def test_liquidity_evolution_has_dynamics_array(self):
        """Response has dynamics array"""
        response = requests.get(f"{BASE_URL}/api/os/liquidity-evolution")
        assert response.status_code == 200
        data = response.json()
        assert "dynamics" in data
        assert isinstance(data["dynamics"], list)
    
    def test_liquidity_evolution_dynamics_structure(self):
        """Each dynamics entry has required fields: type, direction, confidence, trend"""
        response = requests.get(f"{BASE_URL}/api/os/liquidity-evolution")
        assert response.status_code == 200
        data = response.json()
        dynamics = data.get("dynamics", [])
        
        # If dynamics exist, check structure
        if dynamics:
            for d in dynamics:
                assert "type" in d, f"Missing 'type' field in dynamics entry: {d}"
                assert "direction" in d, f"Missing 'direction' field in dynamics entry: {d}"
                assert "confidence" in d, f"Missing 'confidence' field in dynamics entry: {d}"
                assert "trend" in d, f"Missing 'trend' field in dynamics entry: {d}"
                # trend must be one of: strengthening, weakening, stable, new
                assert d["trend"] in ["strengthening", "weakening", "stable", "new"], \
                    f"Invalid trend value: {d['trend']}"
            print(f"PASS: {len(dynamics)} dynamics entries validated with trend fields")
        else:
            print("INFO: No dynamics entries yet (tracking just started)")


class TestOSState:
    """Test /api/os/state endpoint — must include liquidity_evolution"""
    
    def test_os_state_returns_ok(self):
        """Endpoint returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/os/state")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
    
    def test_os_state_has_liquidity_evolution(self):
        """Response includes liquidity_evolution field"""
        response = requests.get(f"{BASE_URL}/api/os/state")
        assert response.status_code == 200
        data = response.json()
        assert "liquidity_evolution" in data, "Missing liquidity_evolution in /api/os/state"
        assert isinstance(data["liquidity_evolution"], list)
        print(f"PASS: liquidity_evolution field present with {len(data['liquidity_evolution'])} entries")
    
    def test_os_state_has_all_required_fields(self):
        """Verify all expected fields are present"""
        response = requests.get(f"{BASE_URL}/api/os/state")
        assert response.status_code == 200
        data = response.json()
        
        required_fields = [
            "market_state", "market_risk", "market_pulse",
            "regime_timeline", "actor_radar", "liquidity_evolution",
            "opportunities", "actor_pressure", "liquidity_targets", "alerts"
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        print(f"PASS: All {len(required_fields)} required fields present in /api/os/state")


class TestOSOpportunities:
    """Test /api/os/opportunities — move_confidence + liquidity_alignment"""
    
    def test_opportunities_returns_ok(self):
        """Endpoint returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/os/opportunities")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
    
    def test_opportunities_have_new_fields(self):
        """Each opportunity has move_confidence and liquidity_alignment"""
        response = requests.get(f"{BASE_URL}/api/os/opportunities")
        assert response.status_code == 200
        data = response.json()
        opportunities = data.get("opportunities", [])
        
        if opportunities:
            for opp in opportunities:
                assert "move_confidence" in opp, f"Missing 'move_confidence' in opportunity: {opp.get('setup')}"
                assert "liquidity_alignment" in opp, f"Missing 'liquidity_alignment' in opportunity: {opp.get('setup')}"
                
                # Validate types and ranges
                assert isinstance(opp["move_confidence"], (int, float)), "move_confidence must be numeric"
                assert isinstance(opp["liquidity_alignment"], (int, float)), "liquidity_alignment must be numeric"
                assert 0 <= opp["move_confidence"] <= 1, f"move_confidence out of range: {opp['move_confidence']}"
                assert 0 <= opp["liquidity_alignment"] <= 1, f"liquidity_alignment out of range: {opp['liquidity_alignment']}"
            
            print(f"PASS: {len(opportunities)} opportunities validated with move_confidence and liquidity_alignment")
        else:
            print("INFO: No opportunities available")


class TestMonitoringEvents:
    """Test /api/engine/monitoring/events — intensity + clusters + cluster_size"""
    
    def test_monitoring_events_returns_ok(self):
        """Endpoint returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/engine/monitoring/events?limit=100")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
    
    def test_monitoring_events_has_intensity(self):
        """Response includes intensity object"""
        response = requests.get(f"{BASE_URL}/api/engine/monitoring/events?limit=100")
        assert response.status_code == 200
        data = response.json()
        
        assert "intensity" in data, "Missing 'intensity' in monitoring/events response"
        intensity = data["intensity"]
        assert isinstance(intensity, dict)
        
        # Verify intensity levels are valid
        valid_levels = ["extreme", "high", "moderate", "low"]
        for cat, level in intensity.items():
            assert level in valid_levels, f"Invalid intensity level '{level}' for category '{cat}'"
        
        print(f"PASS: intensity object present with {len(intensity)} categories")
        print(f"  Categories: {intensity}")
    
    def test_monitoring_events_has_clusters(self):
        """Response includes clusters object"""
        response = requests.get(f"{BASE_URL}/api/engine/monitoring/events?limit=100")
        assert response.status_code == 200
        data = response.json()
        
        assert "clusters" in data, "Missing 'clusters' in monitoring/events response"
        clusters = data["clusters"]
        assert isinstance(clusters, dict)
        
        # Verify cluster counts are > 1
        for event_type, count in clusters.items():
            assert count > 1, f"Cluster count must be > 1, got {count} for {event_type}"
        
        print(f"PASS: clusters object present with {len(clusters)} clustered event types")
        if clusters:
            print(f"  Clusters: {clusters}")
    
    def test_monitoring_events_have_cluster_size(self):
        """Each event in timeline has cluster_size field"""
        response = requests.get(f"{BASE_URL}/api/engine/monitoring/events?limit=100")
        assert response.status_code == 200
        data = response.json()
        
        timeline = data.get("timeline", [])
        if timeline:
            for event in timeline:
                assert "cluster_size" in event, f"Missing 'cluster_size' in event: {event.get('type')}"
                assert isinstance(event["cluster_size"], int)
                assert event["cluster_size"] >= 1
            
            print(f"PASS: {len(timeline)} timeline events validated with cluster_size")
        else:
            print("INFO: No timeline events available")
    
    def test_monitoring_events_structure(self):
        """Verify overall response structure"""
        response = requests.get(f"{BASE_URL}/api/engine/monitoring/events?limit=100")
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ["ok", "events", "timeline", "total", "intensity", "clusters"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # events should be categorized
        events = data.get("events", {})
        expected_categories = ["critical", "liquidity", "actor", "setup", "flow"]
        for cat in expected_categories:
            assert cat in events, f"Missing category '{cat}' in events"
        
        print(f"PASS: All required fields and categories present")


class TestRegressionPreviousFeatures:
    """Regression tests for previous features"""
    
    def test_market_pulse_endpoint(self):
        """Market pulse should still work"""
        response = requests.get(f"{BASE_URL}/api/os/market-pulse")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "pulse" in data
        assert "score" in data
    
    def test_regime_timeline_endpoint(self):
        """Regime timeline should still work"""
        response = requests.get(f"{BASE_URL}/api/os/regime-timeline")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "timeline" in data
    
    def test_actor_radar_endpoint(self):
        """Actor radar should still work"""
        response = requests.get(f"{BASE_URL}/api/os/actor-radar")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "actors" in data
        assert "summary" in data
    
    def test_engine_alerts_endpoint(self):
        """Engine alerts should still work"""
        response = requests.get(f"{BASE_URL}/api/engine/alerts")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "alerts" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
