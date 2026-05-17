"""
Connections Module API Tests
Test the OSINT Dashboard endpoints that read from seed data in connections_db.

Endpoints tested:
- GET /api/connections/health
- GET /api/connections/unified
- GET /api/connections/reality/score
- GET /api/connections/clusters
- GET /api/connections/backers
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestConnectionsHealth:
    """Health check endpoint tests - should return ok:true, accountsCount: 10"""
    
    def test_health_endpoint_returns_ok(self):
        """GET /api/connections/health returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/connections/health", timeout=15)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') == True, f"Expected ok=true, got {data}"
        
    def test_health_endpoint_accounts_count(self):
        """GET /api/connections/health returns accountsCount: 10"""
        response = requests.get(f"{BASE_URL}/api/connections/health", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert 'accountsCount' in data, f"Missing accountsCount in response: {data}"
        assert data['accountsCount'] == 10, f"Expected accountsCount=10, got {data['accountsCount']}"
        
    def test_health_endpoint_status_seeded(self):
        """GET /api/connections/health returns status: seeded"""
        response = requests.get(f"{BASE_URL}/api/connections/health", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('status') == 'seeded', f"Expected status=seeded, got {data.get('status')}"


class TestConnectionsUnified:
    """Unified influencers endpoint tests"""
    
    def test_unified_endpoint_returns_influencers(self):
        """GET /api/connections/unified returns list of influencers"""
        response = requests.get(f"{BASE_URL}/api/connections/unified", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True, f"Expected ok=true, got {data}"
        assert 'influencers' in data, f"Missing influencers in response: {data}"
        assert isinstance(data['influencers'], list), f"influencers should be a list"
        
    def test_unified_endpoint_returns_10_influencers(self):
        """GET /api/connections/unified returns 10 seeded influencers"""
        response = requests.get(f"{BASE_URL}/api/connections/unified?limit=50", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        influencers = data.get('influencers', [])
        assert len(influencers) == 10, f"Expected 10 influencers, got {len(influencers)}"
        
    def test_unified_influencer_structure(self):
        """Verify influencer object has required fields"""
        response = requests.get(f"{BASE_URL}/api/connections/unified", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        influencers = data.get('influencers', [])
        assert len(influencers) > 0, "No influencers returned"
        
        first_influencer = influencers[0]
        required_fields = ['handle', 'name', 'influence']
        for field in required_fields:
            assert field in first_influencer, f"Missing field '{field}' in influencer: {first_influencer}"
            
    def test_unified_contains_expected_influencers(self):
        """Verify seed data contains expected influencers (Vitalik, CZ, a16z, etc.)"""
        response = requests.get(f"{BASE_URL}/api/connections/unified?limit=50", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        influencers = data.get('influencers', [])
        handles = [inf.get('handle', '').lower() for inf in influencers]
        
        # Check for some expected influencers from seed data
        expected_handles = ['vitalik', 'cz_binance', 'a16z', 'paradigm', 'cobie']
        found_handles = [h for h in expected_handles if h in handles]
        
        # At least some expected influencers should be present
        assert len(found_handles) >= 3, f"Expected at least 3 of {expected_handles}, found: {found_handles}. All handles: {handles}"


class TestConnectionsRealityScore:
    """Reality score endpoint tests"""
    
    def test_reality_score_requires_symbol(self):
        """GET /api/connections/reality/score without symbol returns 400"""
        response = requests.get(f"{BASE_URL}/api/connections/reality/score", timeout=15)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
    def test_reality_score_with_symbol(self):
        """GET /api/connections/reality/score?symbol=BTC returns realityScore and sample"""
        response = requests.get(f"{BASE_URL}/api/connections/reality/score?symbol=BTC", timeout=15)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') == True, f"Expected ok=true, got {data}"
        assert 'realityScore' in data, f"Missing realityScore in response: {data}"
        assert 'sample' in data, f"Missing sample in response: {data}"
        
    def test_reality_score_data_types(self):
        """Verify realityScore and sample have correct data types"""
        response = requests.get(f"{BASE_URL}/api/connections/reality/score?symbol=BTC", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data.get('realityScore'), (int, float)), f"realityScore should be numeric: {data}"
        assert isinstance(data.get('sample'), int), f"sample should be integer: {data}"
        
    def test_reality_score_contains_confidence(self):
        """Verify realityScore response contains confidence field"""
        response = requests.get(f"{BASE_URL}/api/connections/reality/score?symbol=BTC", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        assert 'confidence' in data, f"Missing confidence in response: {data}"
        assert data['confidence'] in ['low', 'medium', 'high'], f"Invalid confidence value: {data['confidence']}"


class TestConnectionsClusters:
    """Clusters endpoint tests - grouped by categories"""
    
    def test_clusters_endpoint_returns_ok(self):
        """GET /api/connections/clusters returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/connections/clusters", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True, f"Expected ok=true, got {data}"
        
    def test_clusters_endpoint_returns_clusters_array(self):
        """GET /api/connections/clusters returns clusters array"""
        response = requests.get(f"{BASE_URL}/api/connections/clusters", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        assert 'clusters' in data, f"Missing clusters in response: {data}"
        assert isinstance(data['clusters'], list), f"clusters should be a list"
        
    def test_clusters_have_required_fields(self):
        """Verify cluster objects have required fields"""
        response = requests.get(f"{BASE_URL}/api/connections/clusters", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        clusters = data.get('clusters', [])
        
        if len(clusters) > 0:
            first_cluster = clusters[0]
            required_fields = ['symbol', 'memberCount', 'momentum', 'direction']
            for field in required_fields:
                assert field in first_cluster, f"Missing field '{field}' in cluster: {first_cluster}"


class TestConnectionsBackers:
    """Backers (VC) endpoint tests"""
    
    def test_backers_endpoint_returns_ok(self):
        """GET /api/connections/backers returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/connections/backers", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True, f"Expected ok=true, got {data}"
        
    def test_backers_endpoint_returns_backers_array(self):
        """GET /api/connections/backers returns backers array"""
        response = requests.get(f"{BASE_URL}/api/connections/backers", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        assert 'backers' in data, f"Missing backers in response: {data}"
        assert isinstance(data['backers'], list), f"backers should be a list"
        
    def test_backers_have_required_fields(self):
        """Verify backer objects have required fields"""
        response = requests.get(f"{BASE_URL}/api/connections/backers", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        backers = data.get('backers', [])
        
        if len(backers) > 0:
            first_backer = backers[0]
            required_fields = ['name', 'handle', 'type']
            for field in required_fields:
                assert field in first_backer, f"Missing field '{field}' in backer: {first_backer}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
