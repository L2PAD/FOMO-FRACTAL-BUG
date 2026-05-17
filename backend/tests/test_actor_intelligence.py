"""
Actor Intelligence API Tests (BLOCK 3)
Tests for Actor-Level Cross-Chain Intelligence backend

Endpoints tested:
- GET /api/actors - list actor profiles
- GET /api/actors/stats - actor statistics with byLevel breakdown
- GET /api/actors/events - list actor events
- GET /api/actors/alerts - list actor-related system alerts
- GET /api/actors/:id - get actor profile by ID
- POST /api/actors/analyze - analyze specific actor
- POST /api/actors/scan - scan all actors with recent migrations
- POST /api/actors/sync-alerts - sync actor events to system alerts
- GET /api/system-alerts?source=actor_intelligence - filter alerts by actor source
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestActorIntelligenceAPIs:
    """Actor Intelligence endpoint tests"""
    
    def test_health_check(self):
        """Verify backend is healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
    
    def test_get_actors_list(self):
        """GET /api/actors - list actor profiles"""
        response = requests.get(f"{BASE_URL}/api/actors")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert data.get('success') == True
        assert 'count' in data
        assert 'actors' in data
        assert isinstance(data['actors'], list)
        
        # Verify actor structure if actors exist
        if data['count'] > 0:
            actor = data['actors'][0]
            assert 'actorId' in actor
            assert 'address' in actor
            assert 'chainsUsed' in actor
            assert 'confidenceScore' in actor
            assert 'confidenceLevel' in actor
            assert 'patternScores' in actor
    
    def test_get_actors_stats(self):
        """GET /api/actors/stats - actor statistics with byLevel breakdown"""
        response = requests.get(f"{BASE_URL}/api/actors/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert data.get('success') == True
        assert 'total' in data
        assert 'byLevel' in data
        assert 'topActors' in data
        
        # Verify byLevel is a dict
        assert isinstance(data['byLevel'], dict)
        
        # Verify topActors structure
        assert isinstance(data['topActors'], list)
        if len(data['topActors']) > 0:
            top_actor = data['topActors'][0]
            assert 'actorId' in top_actor
            assert 'address' in top_actor
            assert 'confidence' in top_actor
            assert 'chains' in top_actor
            assert 'migrations' in top_actor
    
    def test_get_actor_events(self):
        """GET /api/actors/events - list actor events"""
        response = requests.get(f"{BASE_URL}/api/actors/events")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert data.get('success') == True
        assert 'count' in data
        assert 'events' in data
        assert isinstance(data['events'], list)
        
        # Verify event structure if events exist
        if data['count'] > 0:
            event = data['events'][0]
            assert 'eventId' in event
            assert 'actorId' in event
            assert 'actorAddress' in event
            assert 'type' in event
            assert 'severity' in event
            assert 'confidence' in event
            
            # Verify event type is valid
            valid_types = [
                'REPEAT_BRIDGE_PATTERN',
                'ROUTE_DOMINANCE',
                'LIQUIDITY_ESCALATION',
                'MULTI_CHAIN_PRESENCE',
                'STRATEGIC_TIMING',
                'NEW_STRATEGIC_ACTOR'
            ]
            assert event['type'] in valid_types
    
    def test_get_actor_alerts(self):
        """GET /api/actors/alerts - list actor-related system alerts"""
        response = requests.get(f"{BASE_URL}/api/actors/alerts")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert data.get('success') == True
        assert 'count' in data
        assert 'alerts' in data
        assert isinstance(data['alerts'], list)
        
        # Verify alert structure if alerts exist
        if data['count'] > 0:
            alert = data['alerts'][0]
            assert 'alertId' in alert
            assert 'type' in alert
            assert 'severity' in alert
            assert 'title' in alert
            assert 'message' in alert
            assert 'metadata' in alert
            
            # Verify actor metadata
            assert 'actorId' in alert['metadata']
            assert 'actorAddress' in alert['metadata']
    
    def test_get_actor_by_id(self):
        """GET /api/actors/:id - get actor profile by ID"""
        # First get list to find an actor ID
        list_response = requests.get(f"{BASE_URL}/api/actors")
        assert list_response.status_code == 200
        
        actors = list_response.json().get('actors', [])
        if len(actors) == 0:
            pytest.skip("No actors available for testing")
        
        actor_id = actors[0]['actorId']
        
        # Get actor by ID
        response = requests.get(f"{BASE_URL}/api/actors/{actor_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert data.get('success') == True
        assert 'actor' in data
        
        actor = data['actor']
        assert actor['actorId'] == actor_id
        assert 'address' in actor
        assert 'chainsUsed' in actor
        assert 'dominantRoutes' in actor
        assert 'patternScores' in actor
        assert 'confidenceScore' in actor
        assert 'confidenceLevel' in actor
        
        # Verify recentEvents if present
        if 'recentEvents' in data:
            assert isinstance(data['recentEvents'], list)
    
    def test_get_actor_not_found(self):
        """GET /api/actors/:id - returns 404 for non-existent actor"""
        response = requests.get(f"{BASE_URL}/api/actors/actor_nonexistent123")
        assert response.status_code == 404
        
        data = response.json()
        assert data.get('ok') == False or data.get('success') == False
    
    def test_post_analyze_actor(self):
        """POST /api/actors/analyze - analyze specific actor"""
        # Use existing test address
        payload = {
            "address": "0x742d35cc6634c0532925a3b844bc454e4438f44e",
            "emitEvents": False  # Don't create duplicate events
        }
        
        response = requests.post(
            f"{BASE_URL}/api/actors/analyze",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert data.get('success') == True
        assert 'actorId' in data
        assert 'confidenceScore' in data
        assert 'confidenceLevel' in data
        assert 'patternScores' in data
        
        # Verify pattern scores structure
        scores = data['patternScores']
        assert 'repeatBridge' in scores
        assert 'routeDominance' in scores
        assert 'sizeEscalation' in scores
        assert 'multiChainPresence' in scores
        assert 'temporalPattern' in scores
    
    def test_post_scan_actors(self):
        """POST /api/actors/scan - scan all actors with recent migrations"""
        payload = {
            "windowDays": 7,
            "limit": 10
        }
        
        response = requests.post(
            f"{BASE_URL}/api/actors/scan",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert data.get('success') == True
        assert 'scanned' in data
        assert 'updated' in data
        assert 'events' in data
        assert 'message' in data
    
    def test_post_sync_alerts(self):
        """POST /api/actors/sync-alerts - sync actor events to system alerts"""
        payload = {
            "windowHours": 24
        }
        
        response = requests.post(
            f"{BASE_URL}/api/actors/sync-alerts",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert data.get('success') == True
        assert 'synced' in data
        assert 'skipped' in data
        assert 'message' in data
    
    def test_system_alerts_actor_source_filter(self):
        """GET /api/system-alerts?source=actor_intelligence - filter alerts by actor source"""
        response = requests.get(f"{BASE_URL}/api/system-alerts?source=actor_intelligence")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('success') == True
        assert 'alerts' in data
        assert isinstance(data['alerts'], list)
        
        # Verify all alerts have actor_intelligence source
        for alert in data['alerts']:
            assert alert.get('source') == 'actor_intelligence'
            assert alert.get('category') == 'ACTOR'
            
            # Verify actor metadata
            metadata = alert.get('metadata', {})
            assert 'actorId' in metadata
            assert 'actorAddress' in metadata
            assert 'eventType' in metadata


class TestActorPatternDetection:
    """Tests for pattern detection logic"""
    
    def test_pattern_types_in_events(self):
        """Verify all pattern types are detected"""
        response = requests.get(f"{BASE_URL}/api/actors/events")
        assert response.status_code == 200
        
        data = response.json()
        events = data.get('events', [])
        
        if len(events) == 0:
            pytest.skip("No events available for testing")
        
        # Collect all event types
        event_types = set(e['type'] for e in events)
        
        # At least some patterns should be detected
        expected_patterns = {
            'REPEAT_BRIDGE_PATTERN',
            'ROUTE_DOMINANCE',
            'LIQUIDITY_ESCALATION',
            'STRATEGIC_TIMING'
        }
        
        # Check that at least one expected pattern is present
        assert len(event_types.intersection(expected_patterns)) > 0, \
            f"Expected at least one of {expected_patterns}, got {event_types}"
    
    def test_confidence_scores_valid(self):
        """Verify confidence scores are in valid range"""
        response = requests.get(f"{BASE_URL}/api/actors")
        assert response.status_code == 200
        
        actors = response.json().get('actors', [])
        
        for actor in actors:
            score = actor.get('confidenceScore', 0)
            assert 0 <= score <= 1, f"Invalid confidence score: {score}"
            
            level = actor.get('confidenceLevel')
            assert level in ['IGNORED', 'LOW', 'MEDIUM', 'HIGH'], \
                f"Invalid confidence level: {level}"
            
            # Verify level matches score
            if score < 0.4:
                assert level == 'IGNORED'
            elif score < 0.6:
                assert level == 'LOW'
            elif score < 0.8:
                assert level == 'MEDIUM'
            else:
                assert level == 'HIGH'


class TestActorAlertsIntegration:
    """Tests for actor events → system alerts integration"""
    
    def test_actor_alerts_have_correct_types(self):
        """Verify actor alerts have correct ACTOR_ prefixed types"""
        response = requests.get(f"{BASE_URL}/api/actors/alerts")
        assert response.status_code == 200
        
        alerts = response.json().get('alerts', [])
        
        valid_alert_types = [
            'ACTOR_REPEAT_BRIDGE',
            'ACTOR_ROUTE_DOMINANCE',
            'ACTOR_LIQUIDITY_ESCALATION',
            'ACTOR_MULTI_CHAIN',
            'ACTOR_STRATEGIC_TIMING',
            'ACTOR_NEW_STRATEGIC'
        ]
        
        for alert in alerts:
            assert alert['type'] in valid_alert_types, \
                f"Invalid alert type: {alert['type']}"
    
    def test_actor_alerts_have_entity_ref(self):
        """Verify actor alerts have entityRef with ACTOR type"""
        response = requests.get(f"{BASE_URL}/api/actors/alerts")
        assert response.status_code == 200
        
        alerts = response.json().get('alerts', [])
        
        for alert in alerts:
            entity_ref = alert.get('entityRef', {})
            if entity_ref:
                assert entity_ref.get('entityType') == 'ACTOR'
                assert 'entityId' in entity_ref
                assert 'address' in entity_ref


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
