"""
Graph API Tests - Unified Graph Intelligence System (iteration 300)
Tests /api/graph, /api/graph/stats, /api/graph/health, /api/graph-intelligence/address endpoints
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestGraphAPIEndpoints:
    """Test suite for Graph API endpoints"""
    
    def test_graph_endpoint_returns_valid_json(self):
        """Test /api/graph returns valid JSON with correct structure"""
        response = requests.get(f"{BASE_URL}/api/graph")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "ok" in data, "Response should have 'ok' field"
        assert data["ok"] == True, "ok should be True"
        
        # Validate data structure
        assert "data" in data, "Response should have 'data' field"
        graph_data = data["data"]
        
        assert "nodes" in graph_data, "data should have 'nodes' array"
        assert "edges" in graph_data, "data should have 'edges' array"
        assert isinstance(graph_data["nodes"], list), "nodes should be a list"
        assert isinstance(graph_data["edges"], list), "edges should be a list"
        
    def test_graph_stats_endpoint(self):
        """Test /api/graph/stats returns valid statistics"""
        response = requests.get(f"{BASE_URL}/api/graph/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Validate required fields
        assert "total_nodes" in data, "Stats should have total_nodes"
        assert "total_edges" in data, "Stats should have total_edges"
        assert "nodes_by_type" in data, "Stats should have nodes_by_type"
        assert "edges_by_type" in data, "Stats should have edges_by_type"
        
        # Validate types
        assert isinstance(data["total_nodes"], int), "total_nodes should be int"
        assert isinstance(data["total_edges"], int), "total_edges should be int"
        assert isinstance(data["nodes_by_type"], dict), "nodes_by_type should be dict"
        assert isinstance(data["edges_by_type"], dict), "edges_by_type should be dict"
        
    def test_graph_health_endpoint(self):
        """Test /api/graph/health returns valid health check"""
        response = requests.get(f"{BASE_URL}/api/graph/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Validate required fields
        assert "status" in data, "Health should have status field"
        assert data["status"] == "healthy", f"Status should be 'healthy', got {data['status']}"
        
        # Validate metrics
        assert "metrics" in data, "Health should have metrics"
        metrics = data["metrics"]
        assert "nodes_count" in metrics, "metrics should have nodes_count"
        assert "edges_count" in metrics, "metrics should have edges_count"
        
    def test_graph_intelligence_valid_address(self):
        """Test /api/graph-intelligence/address/:address with valid Ethereum address"""
        # Valid Vitalik address
        address = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
        response = requests.get(f"{BASE_URL}/api/graph-intelligence/address/{address}?network=ethereum")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "ok" in data, "Response should have 'ok' field"
        assert data["ok"] == True, "ok should be True"
        
        # Validate data structure
        assert "data" in data, "Response should have 'data' field"
        graph_data = data["data"]
        
        assert "nodes" in graph_data, "data should have 'nodes' array"
        assert "edges" in graph_data, "data should have 'edges' array"
        assert "riskSummary" in graph_data, "data should have 'riskSummary'"
        
    def test_graph_intelligence_invalid_address(self):
        """Test /api/graph-intelligence/address/:address with invalid address"""
        # Invalid short address
        response = requests.get(f"{BASE_URL}/api/graph-intelligence/address/0x123?network=ethereum")
        
        data = response.json()
        # Should return error for invalid address
        assert "ok" in data, "Response should have 'ok' field"
        assert data["ok"] == False, "ok should be False for invalid address"
        assert "error" in data, "Response should have 'error' field"
        
    def test_graph_search_endpoint(self):
        """Test /api/graph/search returns valid search results"""
        response = requests.get(f"{BASE_URL}/api/graph/search?q=test")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Validate search response structure
        assert "results" in data, "Search should have results array"
        assert "total" in data, "Search should have total count"
        assert isinstance(data["results"], list), "results should be a list"
        assert isinstance(data["total"], int), "total should be an int"


class TestGraphAPIDataIntegrity:
    """Test data integrity of Graph API responses"""
    
    def test_graph_response_metadata(self):
        """Test /api/graph returns proper metadata"""
        response = requests.get(f"{BASE_URL}/api/graph")
        data = response.json()
        
        if "data" in data and "metadata" in data["data"]:
            metadata = data["data"]["metadata"]
            assert "totalNodes" in metadata, "metadata should have totalNodes"
            assert "totalEdges" in metadata, "metadata should have totalEdges"
            
    def test_graph_intelligence_with_network_param(self):
        """Test graph-intelligence endpoint with different network parameter"""
        address = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
        
        # Test with ethereum network
        response = requests.get(f"{BASE_URL}/api/graph-intelligence/address/{address}?network=ethereum")
        assert response.status_code == 200
        data = response.json()
        assert data.get("network") == "ethereum", "Network should be ethereum"
        
    def test_health_check_thresholds(self):
        """Test health endpoint returns threshold configurations"""
        response = requests.get(f"{BASE_URL}/api/graph/health")
        data = response.json()
        
        if "thresholds" in data:
            thresholds = data["thresholds"]
            # Validate threshold structure exists
            assert isinstance(thresholds, dict), "thresholds should be a dict"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
