"""
P1.7 - Graph Intelligence Layer Tests

Tests for the explainability graph generation API.
Endpoints:
- GET /api/graph-intelligence/health - Health check
- GET /api/graph-intelligence/stats - Statistics
- GET /api/graph-intelligence/address/:address - Build graph for address
- GET /api/graph-intelligence/route/:routeId - Build graph for route
- GET /api/graph-intelligence/cached/:snapshotId - Get cached snapshot
- DELETE /api/graph-intelligence/cache/clear - Clear expired cache
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
API_PREFIX = f"{BASE_URL}/api/graph-intelligence"

# Test addresses
BINANCE_HOT_WALLET = "0x28c6c06298d514db089934071355e5743bf21d60"
TEST_ROUTE_ID = "test-route-p17-001"
RANDOM_ADDRESS = "0xabcdef1234567890abcdef1234567890abcdef12"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestGraphIntelligenceHealth:
    """Health check endpoint tests"""
    
    def test_health_returns_ok(self, api_client):
        """GET /health - returns operational status"""
        response = api_client.get(f"{API_PREFIX}/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert data["module"] == "graph_intelligence"
        assert data["version"] == "P1.7"
        assert data["status"] == "operational"
        
    def test_health_includes_stats(self, api_client):
        """GET /health - includes snapshot stats"""
        response = api_client.get(f"{API_PREFIX}/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "stats" in data
        assert "totalSnapshots" in data["stats"]
        assert "avgBuildTimeMs" in data["stats"]


class TestGraphIntelligenceStats:
    """Statistics endpoint tests"""
    
    def test_stats_returns_ok(self, api_client):
        """GET /stats - returns statistics"""
        response = api_client.get(f"{API_PREFIX}/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "stats" in data
        
    def test_stats_structure(self, api_client):
        """GET /stats - correct structure"""
        response = api_client.get(f"{API_PREFIX}/stats")
        assert response.status_code == 200
        
        stats = response.json()["stats"]
        assert "total" in stats
        assert "byKind" in stats
        assert "avgBuildTimeMs" in stats
        assert "expired" in stats
        
        # byKind should be a dict
        assert isinstance(stats["byKind"], dict)


class TestGraphIntelligenceAddress:
    """Address graph building tests"""
    
    def test_address_graph_returns_ok(self, api_client):
        """GET /address/:address - returns graph for address"""
        response = api_client.get(f"{API_PREFIX}/address/{BINANCE_HOT_WALLET}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "data" in data
        
    def test_address_graph_structure(self, api_client):
        """GET /address/:address - correct response structure"""
        response = api_client.get(f"{API_PREFIX}/address/{BINANCE_HOT_WALLET}")
        assert response.status_code == 200
        
        graph = response.json()["data"]
        
        # Required fields
        assert "snapshotId" in graph
        assert "kind" in graph
        assert graph["kind"] == "ADDRESS"
        assert "address" in graph
        assert graph["address"] == BINANCE_HOT_WALLET.lower()
        
        # Graph data
        assert "nodes" in graph
        assert "edges" in graph
        assert "highlightedPath" in graph
        
        # Risk analysis
        assert "riskSummary" in graph
        assert "explain" in graph
        
        # Metadata
        assert "generatedAt" in graph
        assert "expiresAt" in graph
        assert "buildTimeMs" in graph
        
    def test_address_graph_nodes_structure(self, api_client):
        """GET /address/:address - nodes have correct structure"""
        response = api_client.get(f"{API_PREFIX}/address/{BINANCE_HOT_WALLET}")
        assert response.status_code == 200
        
        nodes = response.json()["data"]["nodes"]
        
        # Should have at least one node
        if len(nodes) > 0:
            node = nodes[0]
            assert "id" in node
            assert "type" in node
            assert "address" in node
            assert "chain" in node
            assert "displayName" in node
            assert "labels" in node
            
            # Type should be valid
            valid_types = ["WALLET", "TOKEN", "BRIDGE", "DEX", "CEX", "CONTRACT"]
            assert node["type"] in valid_types
            
    def test_address_graph_edges_structure(self, api_client):
        """GET /address/:address - edges have correct structure"""
        response = api_client.get(f"{API_PREFIX}/address/{BINANCE_HOT_WALLET}")
        assert response.status_code == 200
        
        edges = response.json()["data"]["edges"]
        
        if len(edges) > 0:
            edge = edges[0]
            assert "id" in edge
            assert "type" in edge
            assert "fromNodeId" in edge
            assert "toNodeId" in edge
            assert "chain" in edge
            assert "timestamp" in edge
            
            # Type should be valid
            valid_types = ["TRANSFER", "SWAP", "BRIDGE", "DEPOSIT", "WITHDRAW", "CONTRACT_CALL"]
            assert edge["type"] in valid_types
            
    def test_address_graph_risk_summary_structure(self, api_client):
        """GET /address/:address - riskSummary has correct structure"""
        response = api_client.get(f"{API_PREFIX}/address/{BINANCE_HOT_WALLET}")
        assert response.status_code == 200
        
        risk = response.json()["data"]["riskSummary"]
        
        # P0.5 fields
        assert "exitProbability" in risk
        assert "dumpRiskScore" in risk
        assert "pathEntropy" in risk
        
        # P1.6 fields
        assert "contextualRiskScore" in risk
        assert "marketAmplifier" in risk
        assert "confidenceImpact" in risk
        assert "contextTags" in risk
        
        # Values should be in valid ranges
        assert 0 <= risk["exitProbability"] <= 1
        assert 0 <= risk["dumpRiskScore"] <= 100
        assert 0 <= risk["pathEntropy"] <= 1
        
    def test_address_graph_explain_structure(self, api_client):
        """GET /address/:address - explain block has correct structure"""
        response = api_client.get(f"{API_PREFIX}/address/{BINANCE_HOT_WALLET}")
        assert response.status_code == 200
        
        explain = response.json()["data"]["explain"]
        
        assert "reasons" in explain
        assert "amplifiers" in explain
        assert "suppressors" in explain
        
        # All should be arrays
        assert isinstance(explain["reasons"], list)
        assert isinstance(explain["amplifiers"], list)
        assert isinstance(explain["suppressors"], list)
        
    def test_address_graph_explain_reasons_structure(self, api_client):
        """GET /address/:address - explain reasons have correct structure"""
        response = api_client.get(f"{API_PREFIX}/address/{BINANCE_HOT_WALLET}")
        assert response.status_code == 200
        
        reasons = response.json()["data"]["explain"]["reasons"]
        
        if len(reasons) > 0:
            reason = reasons[0]
            assert "code" in reason
            assert "title" in reason
            assert "description" in reason
            assert "severity" in reason
            
            # Severity should be valid
            valid_severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
            assert reason["severity"] in valid_severities
            
    def test_address_graph_highlighted_path_structure(self, api_client):
        """GET /address/:address - highlightedPath has correct structure"""
        response = api_client.get(f"{API_PREFIX}/address/{BINANCE_HOT_WALLET}")
        assert response.status_code == 200
        
        path = response.json()["data"]["highlightedPath"]
        
        if len(path) > 0:
            step = path[0]
            assert "edgeId" in step
            assert "reason" in step
            assert "riskContribution" in step
            assert "order" in step
            
            # riskContribution should be 0-1
            assert 0 <= step["riskContribution"] <= 1
            
    def test_address_invalid_returns_400(self, api_client):
        """GET /address/:address - invalid address returns 400"""
        response = api_client.get(f"{API_PREFIX}/address/invalid")
        assert response.status_code == 400
        
        data = response.json()
        assert data["ok"] is False
        assert "error" in data
        
    def test_address_with_query_params(self, api_client):
        """GET /address/:address - accepts query parameters"""
        response = api_client.get(
            f"{API_PREFIX}/address/{BINANCE_HOT_WALLET}",
            params={
                "maxRoutes": "5",
                "maxEdges": "100",
                "timeWindowHours": "48"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        
    def test_address_binance_recognized_as_cex(self, api_client):
        """GET /address/:address - Binance hot wallet recognized as CEX"""
        response = api_client.get(f"{API_PREFIX}/address/{BINANCE_HOT_WALLET}")
        assert response.status_code == 200
        
        nodes = response.json()["data"]["nodes"]
        
        # Find the Binance node
        binance_nodes = [n for n in nodes if n["address"].lower() == BINANCE_HOT_WALLET.lower()]
        
        if len(binance_nodes) > 0:
            binance_node = binance_nodes[0]
            assert binance_node["type"] == "CEX"
            assert "Binance" in binance_node["displayName"]


class TestGraphIntelligenceRoute:
    """Route graph building tests"""
    
    def test_route_graph_returns_ok(self, api_client):
        """GET /route/:routeId - returns graph for route"""
        response = api_client.get(f"{API_PREFIX}/route/{TEST_ROUTE_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "data" in data
        
    def test_route_graph_structure(self, api_client):
        """GET /route/:routeId - correct response structure"""
        response = api_client.get(f"{API_PREFIX}/route/{TEST_ROUTE_ID}")
        assert response.status_code == 200
        
        graph = response.json()["data"]
        
        # Required fields
        assert "snapshotId" in graph
        assert "kind" in graph
        assert graph["kind"] == "ROUTE"
        assert "routeId" in graph
        assert graph["routeId"] == TEST_ROUTE_ID
        
        # Graph data
        assert "nodes" in graph
        assert "edges" in graph
        assert "highlightedPath" in graph
        
        # Risk analysis
        assert "riskSummary" in graph
        assert "explain" in graph
        
    def test_route_graph_risk_summary(self, api_client):
        """GET /route/:routeId - riskSummary has correct values"""
        response = api_client.get(f"{API_PREFIX}/route/{TEST_ROUTE_ID}")
        assert response.status_code == 200
        
        risk = response.json()["data"]["riskSummary"]
        
        # Should have market regime
        if "marketRegime" in risk:
            valid_regimes = ["STABLE", "VOLATILE", "STRESSED"]
            assert risk["marketRegime"] in valid_regimes
            
    def test_route_empty_returns_400(self, api_client):
        """GET /route/ - empty routeId returns 404 (route not found)"""
        # This will match a different route or return 404
        response = api_client.get(f"{API_PREFIX}/route/")
        # Empty route should be handled
        assert response.status_code in [400, 404]


class TestGraphIntelligenceCached:
    """Cached snapshot retrieval tests"""
    
    def test_cached_nonexistent_returns_404(self, api_client):
        """GET /cached/:snapshotId - non-existent returns 404"""
        response = api_client.get(f"{API_PREFIX}/cached/nonexistent-snapshot-id")
        assert response.status_code == 404
        
        data = response.json()
        assert data["ok"] is False
        assert "error" in data
        
    def test_cached_retrieves_valid_snapshot(self, api_client):
        """GET /cached/:snapshotId - retrieves valid snapshot"""
        # First create a snapshot
        create_response = api_client.get(f"{API_PREFIX}/address/{RANDOM_ADDRESS}")
        assert create_response.status_code == 200
        
        snapshot_id = create_response.json()["data"]["snapshotId"]
        
        # Try to retrieve it (may be expired due to 60s TTL)
        cached_response = api_client.get(f"{API_PREFIX}/cached/{snapshot_id}")
        
        # Should be 200 (found) or 410 (expired)
        assert cached_response.status_code in [200, 410]
        
        if cached_response.status_code == 200:
            data = cached_response.json()
            assert data["ok"] is True
            assert data["data"]["snapshotId"] == snapshot_id


class TestGraphIntelligenceCacheClear:
    """Cache clearing tests"""
    
    def test_cache_clear_returns_ok(self, api_client):
        """DELETE /cache/clear - clears expired cache"""
        response = api_client.delete(f"{API_PREFIX}/cache/clear")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "deletedCount" in data
        assert isinstance(data["deletedCount"], int)
        assert data["deletedCount"] >= 0


class TestGraphIntelligenceCaching:
    """Caching mechanism tests"""
    
    def test_same_request_returns_cached(self, api_client):
        """Same address request should return cached data (same snapshotId)"""
        # First request
        response1 = api_client.get(f"{API_PREFIX}/address/{BINANCE_HOT_WALLET}")
        assert response1.status_code == 200
        snapshot_id1 = response1.json()["data"]["snapshotId"]
        
        # Second request (should be cached)
        response2 = api_client.get(f"{API_PREFIX}/address/{BINANCE_HOT_WALLET}")
        assert response2.status_code == 200
        snapshot_id2 = response2.json()["data"]["snapshotId"]
        
        # Should be same snapshot (cached)
        assert snapshot_id1 == snapshot_id2
        
    def test_build_time_reasonable(self, api_client):
        """Build time should be reasonable (< 5000ms)"""
        response = api_client.get(f"{API_PREFIX}/address/{RANDOM_ADDRESS}")
        assert response.status_code == 200
        
        build_time = response.json()["data"]["buildTimeMs"]
        assert build_time < 5000  # Should build in under 5 seconds


class TestGraphIntelligenceExplainRules:
    """Risk explanation rule tests"""
    
    def test_explain_reasons_sorted_by_severity(self, api_client):
        """Explain reasons should be sorted by severity (CRITICAL first)"""
        response = api_client.get(f"{API_PREFIX}/address/{BINANCE_HOT_WALLET}")
        assert response.status_code == 200
        
        reasons = response.json()["data"]["explain"]["reasons"]
        
        if len(reasons) > 1:
            severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
            
            for i in range(len(reasons) - 1):
                current_severity = severity_order.get(reasons[i]["severity"], 4)
                next_severity = severity_order.get(reasons[i + 1]["severity"], 4)
                assert current_severity <= next_severity, "Reasons not sorted by severity"
                
    def test_amplifiers_have_correct_structure(self, api_client):
        """Amplifiers should have tag, multiplier, source"""
        response = api_client.get(f"{API_PREFIX}/address/{BINANCE_HOT_WALLET}")
        assert response.status_code == 200
        
        amplifiers = response.json()["data"]["explain"]["amplifiers"]
        
        for amp in amplifiers:
            assert "tag" in amp
            assert "multiplier" in amp
            assert "source" in amp
            
            # Source should be valid
            valid_sources = ["MARKET", "ROUTE", "ACTOR"]
            assert amp["source"] in valid_sources
            
            # Multiplier should be > 1 for amplifiers
            assert amp["multiplier"] >= 1.0


class TestGraphIntelligenceEdgeCases:
    """Edge case tests"""
    
    def test_lowercase_address_handling(self, api_client):
        """Address should be normalized to lowercase"""
        upper_address = BINANCE_HOT_WALLET.upper()
        response = api_client.get(f"{API_PREFIX}/address/{upper_address}")
        assert response.status_code == 200
        
        # Returned address should be lowercase
        returned_address = response.json()["data"]["address"]
        assert returned_address == BINANCE_HOT_WALLET.lower()
        
    def test_chains_filter_parameter(self, api_client):
        """chains query parameter should be accepted"""
        response = api_client.get(
            f"{API_PREFIX}/address/{BINANCE_HOT_WALLET}",
            params={"chains": "eth,arb,bsc"}
        )
        assert response.status_code == 200
        
    def test_max_edges_parameter(self, api_client):
        """maxEdges query parameter should limit edges"""
        response = api_client.get(
            f"{API_PREFIX}/address/{BINANCE_HOT_WALLET}",
            params={"maxEdges": "10"}
        )
        assert response.status_code == 200
        
        edges = response.json()["data"]["edges"]
        assert len(edges) <= 10


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
