"""
Backer Detail Page API Tests
Tests the backer detail endpoints: /backers/:slug, /network, /coinvestors, /investments, /influence
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBackerDetailEndpoints:
    """Test backer detail page API endpoints"""
    
    def test_backer_detail_returns_ok(self):
        """GET /api/connections/backers/a16z returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/connections/backers/a16z")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get('ok') == True, f"Expected ok:true, got {data}"
        print("PASS: /api/connections/backers/a16z returns ok:true")
    
    def test_backer_detail_has_required_fields(self):
        """GET /api/connections/backers/a16z returns seedAuthority, confidence, type fields"""
        response = requests.get(f"{BASE_URL}/api/connections/backers/a16z")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        
        backer = data.get('backer', {})
        # Check required fields
        assert 'seedAuthority' in backer, f"Missing seedAuthority in backer: {backer}"
        assert 'confidence' in backer, f"Missing confidence in backer: {backer}"
        assert 'type' in backer, f"Missing type in backer: {backer}"
        assert 'description' in backer, f"Missing description in backer: {backer}"
        
        # Validate types
        assert isinstance(backer['seedAuthority'], (int, float)), f"seedAuthority should be numeric: {backer['seedAuthority']}"
        assert isinstance(backer['confidence'], (int, float)), f"confidence should be numeric: {backer['confidence']}"
        assert isinstance(backer['type'], str), f"type should be string: {backer['type']}"
        
        print(f"PASS: Backer has required fields - seedAuthority={backer['seedAuthority']}, confidence={backer['confidence']}, type={backer['type']}")
    
    def test_backer_network_returns_ok(self):
        """GET /api/connections/backers/a16z/network returns ok:true with nodes and edges"""
        response = requests.get(f"{BASE_URL}/api/connections/backers/a16z/network")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get('ok') == True, f"Expected ok:true, got {data}"
        
        # Check data structure
        network_data = data.get('data', {})
        assert 'nodes' in network_data, f"Missing nodes in network data: {network_data}"
        assert 'edges' in network_data, f"Missing edges in network data: {network_data}"
        assert isinstance(network_data['nodes'], list), f"nodes should be array"
        assert isinstance(network_data['edges'], list), f"edges should be array"
        
        print(f"PASS: /network returns ok:true with {len(network_data['nodes'])} nodes and {len(network_data['edges'])} edges")
    
    def test_backer_coinvestors_returns_ok(self):
        """GET /api/connections/backers/a16z/coinvestors returns ok:true with coinvestors array"""
        response = requests.get(f"{BASE_URL}/api/connections/backers/a16z/coinvestors?limit=20")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get('ok') == True, f"Expected ok:true, got {data}"
        
        # Check coinvestors array
        coinvestors = data.get('coinvestors', [])
        assert isinstance(coinvestors, list), f"coinvestors should be array"
        
        # If there are coinvestors, check structure
        if len(coinvestors) > 0:
            first = coinvestors[0]
            assert 'name' in first or 'backerId' in first, f"Coinvestor missing name/backerId: {first}"
            assert 'sharedCount' in first or 'shared' in first, f"Coinvestor missing sharedCount/shared: {first}"
        
        print(f"PASS: /coinvestors returns ok:true with {len(coinvestors)} coinvestors")
    
    def test_backer_investments_returns_ok(self):
        """GET /api/connections/backers/a16z/investments returns ok:true with investments array"""
        response = requests.get(f"{BASE_URL}/api/connections/backers/a16z/investments?limit=50")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get('ok') == True, f"Expected ok:true, got {data}"
        
        # Check investments array
        investments = data.get('investments', [])
        assert isinstance(investments, list), f"investments should be array"
        
        # If there are investments, check structure
        if len(investments) > 0:
            first = investments[0]
            assert 'projectId' in first or 'project' in first, f"Investment missing projectId/project: {first}"
        
        print(f"PASS: /investments returns ok:true with {len(investments)} investments")
    
    def test_backer_influence_returns_ok(self):
        """GET /api/connections/backers/a16z/influence returns ok:true with data containing summary, graph, projectImpact"""
        response = requests.get(f"{BASE_URL}/api/connections/backers/a16z/influence")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get('ok') == True, f"Expected ok:true, got {data}"
        
        # Check data structure
        influence_data = data.get('data', {})
        assert 'summary' in influence_data, f"Missing summary in influence data: {influence_data}"
        assert 'graph' in influence_data, f"Missing graph in influence data: {influence_data}"
        assert 'projectImpact' in influence_data, f"Missing projectImpact in influence data: {influence_data}"
        
        # Check summary structure
        summary = influence_data.get('summary', {})
        assert 'impactScore' in summary, f"Missing impactScore in summary: {summary}"
        assert 'networkRank' in summary, f"Missing networkRank in summary: {summary}"
        
        # Check graph structure
        graph = influence_data.get('graph', {})
        assert 'nodes' in graph, f"Missing nodes in graph: {graph}"
        assert 'edges' in graph, f"Missing edges in graph: {graph}"
        
        print(f"PASS: /influence returns ok:true with summary (impactScore={summary.get('impactScore')}), graph ({len(graph.get('nodes', []))} nodes), projectImpact ({len(influence_data.get('projectImpact', []))} items)")
    
    def test_other_backer_slugs(self):
        """Test other available backer slugs: paradigm, vitalikbuterin, cz_binance"""
        slugs = ['paradigm', 'vitalikbuterin', 'cz_binance']
        
        for slug in slugs:
            response = requests.get(f"{BASE_URL}/api/connections/backers/{slug}")
            # These may or may not exist in DB, so we just check for valid response
            assert response.status_code in [200, 404], f"Unexpected status for {slug}: {response.status_code}"
            data = response.json()
            # If ok:true, check structure
            if data.get('ok') == True:
                backer = data.get('backer', {})
                assert 'name' in backer or 'handle' in backer, f"Backer {slug} missing name/handle"
                print(f"PASS: /{slug} returns ok:true with backer data")
            else:
                print(f"INFO: /{slug} returns ok:false (backer may not exist in DB)")
    
    def test_connections_health(self):
        """Test connections health endpoint"""
        response = requests.get(f"{BASE_URL}/api/connections/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get('ok') == True, f"Expected ok:true, got {data}"
        print(f"PASS: /api/connections/health returns ok:true")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
