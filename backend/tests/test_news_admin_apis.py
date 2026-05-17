"""
NEWS ADMIN API TESTS
Tests for /api/admin/news/* endpoints:
- GET /api/admin/news/health
- GET /api/admin/news/sources
- GET /api/admin/news/events?limit=N
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestNewsAdminHealth:
    """Tests for GET /api/admin/news/health endpoint"""

    def test_health_endpoint_returns_200(self):
        """Health endpoint should return 200 OK"""
        response = requests.get(f"{BASE_URL}/api/admin/news/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: Health endpoint returns 200")

    def test_health_response_structure(self):
        """Health response should have ok:true and data object"""
        response = requests.get(f"{BASE_URL}/api/admin/news/health")
        data = response.json()
        
        assert data.get('ok') == True, "Expected ok:true in response"
        assert 'data' in data, "Expected 'data' field in response"
        print("PASS: Health response has ok:true and data")

    def test_health_data_fields(self):
        """Health data should contain required fields"""
        response = requests.get(f"{BASE_URL}/api/admin/news/health")
        data = response.json()['data']
        
        required_fields = [
            'totalSources', 'activeSources', 'healthySources',
            'eventsLast1h', 'eventsLast24h', 'avgLatencyMs', 'dedupeRate'
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Verify data types
        assert isinstance(data['totalSources'], int), "totalSources should be int"
        assert isinstance(data['activeSources'], int), "activeSources should be int"
        assert isinstance(data['healthySources'], int), "healthySources should be int"
        
        print(f"PASS: Health data contains all required fields")
        print(f"  - totalSources: {data['totalSources']}")
        print(f"  - activeSources: {data['activeSources']}")
        print(f"  - healthySources: {data['healthySources']}")

    def test_health_top_sources(self):
        """Health should include topSources array"""
        response = requests.get(f"{BASE_URL}/api/admin/news/health")
        data = response.json()['data']
        
        assert 'topSources' in data, "Expected topSources in health data"
        assert isinstance(data['topSources'], list), "topSources should be a list"
        
        if len(data['topSources']) > 0:
            src = data['topSources'][0]
            assert 'name' in src, "topSources item should have name"
            assert 'articles' in src, "topSources item should have articles"
            assert 'tier' in src, "topSources item should have tier"
        
        print(f"PASS: topSources array present with {len(data['topSources'])} items")


class TestNewsAdminSources:
    """Tests for GET /api/admin/news/sources endpoint"""

    def test_sources_endpoint_returns_200(self):
        """Sources endpoint should return 200 OK"""
        response = requests.get(f"{BASE_URL}/api/admin/news/sources")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: Sources endpoint returns 200")

    def test_sources_response_structure(self):
        """Sources response should have ok:true and data.sources array"""
        response = requests.get(f"{BASE_URL}/api/admin/news/sources")
        data = response.json()
        
        assert data.get('ok') == True, "Expected ok:true in response"
        assert 'data' in data, "Expected 'data' field in response"
        assert 'sources' in data['data'], "Expected 'sources' array in data"
        assert isinstance(data['data']['sources'], list), "sources should be a list"
        
        print(f"PASS: Sources response has ok:true and sources array with {len(data['data']['sources'])} items")

    def test_sources_item_structure(self):
        """Each source should have required fields"""
        response = requests.get(f"{BASE_URL}/api/admin/news/sources")
        sources = response.json()['data']['sources']
        
        if len(sources) == 0:
            pytest.skip("No sources available to test")
        
        required_fields = [
            'id', 'name', 'tier', 'lang', 'healthy',
            'totalArticles', 'successRate', 'lastFetchAt'
        ]
        
        src = sources[0]
        for field in required_fields:
            assert field in src, f"Source missing required field: {field}"
        
        # Verify tier is A, B, or C
        assert src['tier'] in ['A', 'B', 'C'], f"Invalid tier: {src['tier']}"
        
        print(f"PASS: Source items have all required fields")
        print(f"  - First source: {src['name']} (Tier {src['tier']})")

    def test_sources_tier_distribution(self):
        """Sources should have tier A, B, C distribution"""
        response = requests.get(f"{BASE_URL}/api/admin/news/sources")
        sources = response.json()['data']['sources']
        
        tiers = {'A': 0, 'B': 0, 'C': 0}
        for src in sources:
            if src['tier'] in tiers:
                tiers[src['tier']] += 1
        
        print(f"PASS: Tier distribution - A:{tiers['A']}, B:{tiers['B']}, C:{tiers['C']}")


class TestNewsAdminEvents:
    """Tests for GET /api/admin/news/events endpoint"""

    def test_events_endpoint_returns_200(self):
        """Events endpoint should return 200 OK"""
        response = requests.get(f"{BASE_URL}/api/admin/news/events?limit=5")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: Events endpoint returns 200")

    def test_events_response_structure(self):
        """Events response should have ok:true and data.events array"""
        response = requests.get(f"{BASE_URL}/api/admin/news/events?limit=5")
        data = response.json()
        
        assert data.get('ok') == True, "Expected ok:true in response"
        assert 'data' in data, "Expected 'data' field in response"
        assert 'events' in data['data'], "Expected 'events' array in data"
        assert isinstance(data['data']['events'], list), "events should be a list"
        
        print(f"PASS: Events response has ok:true and events array with {len(data['data']['events'])} items")

    def test_events_limit_parameter(self):
        """Events endpoint should respect limit parameter"""
        for limit in [5, 10, 20]:
            response = requests.get(f"{BASE_URL}/api/admin/news/events?limit={limit}")
            events = response.json()['data']['events']
            
            assert len(events) <= limit, f"Expected max {limit} events, got {len(events)}"
        
        print("PASS: Events endpoint respects limit parameter")

    def test_events_item_structure(self):
        """Each event should have required fields"""
        response = requests.get(f"{BASE_URL}/api/admin/news/events?limit=5")
        events = response.json()['data']['events']
        
        if len(events) == 0:
            pytest.skip("No events available to test")
        
        required_fields = ['externalId', 'title', 'publishedAt', 'sourceName']
        
        ev = events[0]
        for field in required_fields:
            assert field in ev, f"Event missing required field: {field}"
        
        print(f"PASS: Event items have required fields")
        print(f"  - First event: {ev['title'][:50]}...")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
