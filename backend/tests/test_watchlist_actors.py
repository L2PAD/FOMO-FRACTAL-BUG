"""
Watchlist Actors API Tests (P1.1)

Tests for:
- GET /api/watchlist/actors - aggregated actors with intelligence data
- GET /api/watchlist/actors/:id/profile - detailed actor profile
- GET /api/watchlist/actors/suggested - suggested actors
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestWatchlistActorsAPI:
    """Test Watchlist Actors endpoints"""
    
    def test_get_watchlist_actors(self):
        """GET /api/watchlist/actors - returns aggregated actors"""
        response = requests.get(f"{BASE_URL}/api/watchlist/actors")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert data.get('ok') == True
        assert data.get('success') == True
        assert 'total' in data
        assert 'actors' in data
        assert isinstance(data['actors'], list)
        
        print(f"Found {data['total']} actors in watchlist")
        
        # Verify actor data structure if actors exist
        if data['total'] > 0:
            actor = data['actors'][0]
            assert 'watchlistId' in actor
            assert 'actorId' in actor
            assert 'address' in actor
            assert 'confidence' in actor
            assert 'confidenceLevel' in actor
            assert 'patterns' in actor
            assert 'chains' in actor
            assert 'bridgeCount7d' in actor
            assert 'openAlerts' in actor
            assert 'lastActivityAt' in actor
            print(f"Actor structure validated: {actor['actorId']}")
    
    def test_get_actor_profile_by_id(self):
        """GET /api/watchlist/actors/:id/profile - returns detailed profile by actorId"""
        actor_id = "actor_ff8b25f1cdd03142"
        response = requests.get(f"{BASE_URL}/api/watchlist/actors/{actor_id}/profile")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert data.get('ok') == True
        assert data.get('success') == True
        
        # Check actor section
        assert 'actor' in data
        actor = data['actor']
        assert actor['id'] == actor_id
        assert 'address' in actor
        assert 'confidence' in actor
        assert 'confidenceLevel' in actor
        print(f"Actor profile loaded: {actor['id']}, confidence: {actor['confidence']}")
        
        # Check summary section
        assert 'summary' in data
        summary = data['summary']
        assert 'chains' in summary
        assert 'dominantRoutes' in summary
        assert 'totalMigrations' in summary
        assert 'totalVolumeUsd' in summary
        assert 'patterns' in summary
        print(f"Summary: {summary['totalMigrations']} migrations, ${summary['totalVolumeUsd']} volume")
        
        # Check patterns
        if summary['patterns']:
            pattern = summary['patterns'][0]
            assert 'type' in pattern
            assert 'confidence' in pattern
            print(f"Patterns found: {[p['type'] for p in summary['patterns']]}")
        
        # Check recent events
        assert 'recentEvents' in data
        if data['recentEvents']:
            event = data['recentEvents'][0]
            assert 'eventId' in event
            assert 'type' in event
            assert 'severity' in event
            assert 'title' in event
            print(f"Recent events: {len(data['recentEvents'])}")
        
        # Check related alerts
        assert 'relatedAlerts' in data
        if data['relatedAlerts']:
            alert = data['relatedAlerts'][0]
            assert 'alertId' in alert
            assert 'type' in alert
            assert 'severity' in alert
            assert 'status' in alert
            print(f"Related alerts: {len(data['relatedAlerts'])}")
        
        # Check recent migrations
        assert 'recentMigrations' in data
        if data['recentMigrations']:
            migration = data['recentMigrations'][0]
            assert 'migrationId' in migration
            assert 'fromChain' in migration
            assert 'toChain' in migration
            print(f"Recent migrations: {len(data['recentMigrations'])}")
    
    def test_get_actor_profile_by_address(self):
        """GET /api/watchlist/actors/:address/profile - returns profile by address"""
        address = "0x742d35cc6634c0532925a3b844bc454e4438f44e"
        response = requests.get(f"{BASE_URL}/api/watchlist/actors/{address}/profile")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') == True
        assert data.get('success') == True
        assert 'actor' in data
        assert data['actor']['address'].lower() == address.lower()
        print(f"Profile loaded by address: {data['actor']['address']}")
    
    def test_get_actor_profile_not_found(self):
        """GET /api/watchlist/actors/:id/profile - returns 404 for non-existent actor"""
        response = requests.get(f"{BASE_URL}/api/watchlist/actors/nonexistent_actor_123/profile")
        
        assert response.status_code == 404
        data = response.json()
        
        assert data.get('ok') == False
        assert 'error' in data
        print(f"404 response for non-existent actor: {data['error']}")
    
    def test_get_suggested_actors(self):
        """GET /api/watchlist/actors/suggested - returns suggested actors"""
        response = requests.get(f"{BASE_URL}/api/watchlist/actors/suggested")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') == True
        assert data.get('success') == True
        assert 'count' in data
        assert 'actors' in data
        assert isinstance(data['actors'], list)
        print(f"Suggested actors: {data['count']}")
        
        # Verify suggested actor structure if any exist
        if data['count'] > 0:
            actor = data['actors'][0]
            assert 'actorId' in actor
            assert 'address' in actor
            assert 'confidence' in actor
            assert 'confidenceLevel' in actor
    
    def test_get_suggested_actors_with_limit(self):
        """GET /api/watchlist/actors/suggested?limit=3 - respects limit parameter"""
        response = requests.get(f"{BASE_URL}/api/watchlist/actors/suggested", params={'limit': 3})
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') == True
        assert len(data['actors']) <= 3
        print(f"Suggested actors with limit=3: {len(data['actors'])}")


class TestWatchlistActorsDataValidation:
    """Test data validation for actor responses"""
    
    def test_actor_confidence_range(self):
        """Verify confidence scores are in valid range (0-1)"""
        response = requests.get(f"{BASE_URL}/api/watchlist/actors")
        data = response.json()
        
        for actor in data.get('actors', []):
            confidence = actor.get('confidence', 0)
            assert 0 <= confidence <= 1, f"Invalid confidence: {confidence}"
            
            # Verify confidence level matches score
            level = actor.get('confidenceLevel', 'LOW')
            if confidence >= 0.7:
                assert level in ['HIGH', 'MEDIUM'], f"Mismatch: {confidence} -> {level}"
            elif confidence >= 0.4:
                assert level in ['MEDIUM', 'LOW'], f"Mismatch: {confidence} -> {level}"
        
        print("All actor confidence scores validated")
    
    def test_actor_patterns_structure(self):
        """Verify pattern data structure"""
        response = requests.get(f"{BASE_URL}/api/watchlist/actors")
        data = response.json()
        
        valid_patterns = [
            'REPEAT_BRIDGE_PATTERN',
            'ROUTE_DOMINANCE', 
            'LIQUIDITY_ESCALATION',
            'MULTI_CHAIN_PRESENCE',
            'STRATEGIC_TIMING',
            'NEW_STRATEGIC_ACTOR'
        ]
        
        for actor in data.get('actors', []):
            for pattern in actor.get('patterns', []):
                assert 'type' in pattern
                assert 'confidence' in pattern
                assert pattern['type'] in valid_patterns, f"Unknown pattern: {pattern['type']}"
                assert 0 <= pattern['confidence'] <= 1
        
        print("All actor patterns validated")
    
    def test_actor_profile_sections(self):
        """Verify all profile sections are present"""
        actor_id = "actor_ff8b25f1cdd03142"
        response = requests.get(f"{BASE_URL}/api/watchlist/actors/{actor_id}/profile")
        data = response.json()
        
        # Required sections
        required_sections = ['actor', 'summary', 'recentEvents', 'relatedAlerts', 'recentMigrations']
        for section in required_sections:
            assert section in data, f"Missing section: {section}"
        
        # Summary subsections
        summary = data['summary']
        summary_fields = ['chains', 'dominantRoutes', 'totalMigrations', 'totalVolumeUsd', 'patterns']
        for field in summary_fields:
            assert field in summary, f"Missing summary field: {field}"
        
        print("All profile sections validated")


class TestWatchlistActorsIntegration:
    """Integration tests for watchlist actors"""
    
    def test_actors_match_watchlist_items(self):
        """Verify actors endpoint returns items from watchlist"""
        # Get watchlist items of type 'actor'
        watchlist_response = requests.get(f"{BASE_URL}/api/watchlist", params={'type': 'actor'})
        watchlist_data = watchlist_response.json()
        
        # Get actors endpoint
        actors_response = requests.get(f"{BASE_URL}/api/watchlist/actors")
        actors_data = actors_response.json()
        
        # Count should match
        watchlist_count = len(watchlist_data.get('data', []))
        actors_count = actors_data.get('total', 0)
        
        assert watchlist_count == actors_count, f"Count mismatch: watchlist={watchlist_count}, actors={actors_count}"
        print(f"Actor counts match: {actors_count}")
    
    def test_profile_has_watchlist_id(self):
        """Verify profile includes watchlistId for tracked actors"""
        actor_id = "actor_ff8b25f1cdd03142"
        response = requests.get(f"{BASE_URL}/api/watchlist/actors/{actor_id}/profile")
        data = response.json()
        
        # Actor is in watchlist, should have watchlistId
        assert 'watchlistId' in data, "Missing watchlistId for tracked actor"
        assert data['watchlistId'], "watchlistId should not be empty"
        print(f"Profile has watchlistId: {data['watchlistId']}")
    
    def test_alerts_count_matches_profile(self):
        """Verify openAlerts count matches related alerts"""
        # Get actors list
        actors_response = requests.get(f"{BASE_URL}/api/watchlist/actors")
        actors_data = actors_response.json()
        
        # Find actor with alerts
        actor_with_alerts = None
        for actor in actors_data.get('actors', []):
            if actor.get('openAlerts', 0) > 0:
                actor_with_alerts = actor
                break
        
        if actor_with_alerts:
            # Get profile
            profile_response = requests.get(
                f"{BASE_URL}/api/watchlist/actors/{actor_with_alerts['actorId']}/profile"
            )
            profile_data = profile_response.json()
            
            # Count OPEN alerts
            open_alerts = [a for a in profile_data.get('relatedAlerts', []) if a.get('status') == 'OPEN']
            
            assert actor_with_alerts['openAlerts'] == len(open_alerts), \
                f"Alert count mismatch: list={actor_with_alerts['openAlerts']}, profile={len(open_alerts)}"
            print(f"Alert counts match: {len(open_alerts)}")
        else:
            print("No actors with alerts found - skipping test")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
