"""
Cluster Intelligence Engine Tests
Tests /api/connections/clusters/intelligence endpoint
Features: cluster types, status, members, tokens, metrics, insights
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestClusterIntelligenceEndpoint:
    """Tests for /api/connections/clusters/intelligence"""
    
    def test_endpoint_returns_200(self):
        """Endpoint should return 200 OK"""
        response = requests.get(f"{BASE_URL}/api/connections/clusters/intelligence")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: Endpoint returns 200")
    
    def test_response_structure(self):
        """Response should have ok, data with clusters, insights, token_clusters, total"""
        response = requests.get(f"{BASE_URL}/api/connections/clusters/intelligence")
        data = response.json()
        
        assert data.get("ok") == True, "Response should have ok=True"
        assert "data" in data, "Response should have data field"
        assert "clusters" in data["data"], "Data should have clusters array"
        assert "insights" in data["data"], "Data should have insights array"
        assert "token_clusters" in data["data"], "Data should have token_clusters dict"
        assert "total" in data["data"], "Data should have total count"
        print(f"PASS: Response structure correct - {data['data']['total']} clusters")
    
    def test_clusters_have_required_fields(self):
        """Each cluster should have: id, name, type, status, members, tokens, metrics, signal"""
        response = requests.get(f"{BASE_URL}/api/connections/clusters/intelligence")
        clusters = response.json()["data"]["clusters"]
        
        required_fields = ["id", "name", "type", "status", "members", "member_count", "tokens", "metrics", "signal", "total_followers"]
        
        for cluster in clusters:
            for field in required_fields:
                assert field in cluster, f"Cluster {cluster.get('name', 'unknown')} missing field: {field}"
        
        print(f"PASS: All {len(clusters)} clusters have required fields")
    
    def test_cluster_types_valid(self):
        """Cluster types should be: smart_money, narrative_drivers, retail_noise, coordinated_pump"""
        response = requests.get(f"{BASE_URL}/api/connections/clusters/intelligence")
        clusters = response.json()["data"]["clusters"]
        
        valid_types = {"smart_money", "narrative_drivers", "retail_noise", "coordinated_pump"}
        
        for cluster in clusters:
            assert cluster["type"] in valid_types, f"Invalid type '{cluster['type']}' for cluster {cluster['name']}"
        
        types_found = set(c["type"] for c in clusters)
        print(f"PASS: All cluster types valid. Types found: {types_found}")
    
    def test_cluster_status_valid(self):
        """Cluster status should be: emerging, active, saturated, dead"""
        response = requests.get(f"{BASE_URL}/api/connections/clusters/intelligence")
        clusters = response.json()["data"]["clusters"]
        
        valid_statuses = {"emerging", "active", "saturated", "dead"}
        
        for cluster in clusters:
            assert cluster["status"] in valid_statuses, f"Invalid status '{cluster['status']}' for cluster {cluster['name']}"
        
        statuses_found = set(c["status"] for c in clusters)
        print(f"PASS: All cluster statuses valid. Statuses found: {statuses_found}")
    
    def test_members_have_avatars(self):
        """Each member should have username, avatar, authority"""
        response = requests.get(f"{BASE_URL}/api/connections/clusters/intelligence")
        clusters = response.json()["data"]["clusters"]
        
        for cluster in clusters:
            assert len(cluster["members"]) > 0, f"Cluster {cluster['name']} has no members"
            for member in cluster["members"]:
                assert "username" in member, f"Member missing username in {cluster['name']}"
                assert "avatar" in member, f"Member {member.get('username')} missing avatar"
                assert "authority" in member, f"Member {member.get('username')} missing authority"
        
        total_members = sum(len(c["members"]) for c in clusters)
        print(f"PASS: All {total_members} members have required fields (username, avatar, authority)")
    
    def test_tokens_have_required_fields(self):
        """Each token should have: symbol, mentions, score, price_return, verdict"""
        response = requests.get(f"{BASE_URL}/api/connections/clusters/intelligence")
        clusters = response.json()["data"]["clusters"]
        
        token_fields = ["symbol", "mentions", "score", "price_return", "verdict"]
        
        for cluster in clusters:
            for token in cluster["tokens"]:
                for field in token_fields:
                    assert field in token, f"Token {token.get('symbol', 'unknown')} missing field: {field}"
        
        total_tokens = sum(len(c["tokens"]) for c in clusters)
        print(f"PASS: All {total_tokens} tokens have required fields")
    
    def test_metrics_have_required_fields(self):
        """Metrics should have: cohesion, authority, trust, cluster_score, direction"""
        response = requests.get(f"{BASE_URL}/api/connections/clusters/intelligence")
        clusters = response.json()["data"]["clusters"]
        
        metric_fields = ["cohesion", "authority", "trust", "cluster_score", "direction"]
        
        for cluster in clusters:
            for field in metric_fields:
                assert field in cluster["metrics"], f"Cluster {cluster['name']} metrics missing: {field}"
        
        print("PASS: All clusters have required metric fields")
    
    def test_direction_values_valid(self):
        """Direction should be: bullish, mixed, dump_risk"""
        response = requests.get(f"{BASE_URL}/api/connections/clusters/intelligence")
        clusters = response.json()["data"]["clusters"]
        
        valid_directions = {"bullish", "mixed", "dump_risk"}
        
        for cluster in clusters:
            direction = cluster["metrics"]["direction"]
            assert direction in valid_directions, f"Invalid direction '{direction}' for cluster {cluster['name']}"
        
        directions_found = set(c["metrics"]["direction"] for c in clusters)
        print(f"PASS: All directions valid. Directions found: {directions_found}")
    
    def test_cluster_score_range(self):
        """Cluster score should be between 0 and 1"""
        response = requests.get(f"{BASE_URL}/api/connections/clusters/intelligence")
        clusters = response.json()["data"]["clusters"]
        
        for cluster in clusters:
            score = cluster["metrics"]["cluster_score"]
            assert 0 <= score <= 1, f"Cluster {cluster['name']} has invalid score: {score}"
        
        scores = [c["metrics"]["cluster_score"] for c in clusters]
        print(f"PASS: All cluster scores in valid range [0,1]. Scores: {scores}")
    
    def test_clusters_sorted_by_score(self):
        """Clusters should be sorted by cluster_score descending"""
        response = requests.get(f"{BASE_URL}/api/connections/clusters/intelligence")
        clusters = response.json()["data"]["clusters"]
        
        scores = [c["metrics"]["cluster_score"] for c in clusters]
        assert scores == sorted(scores, reverse=True), "Clusters not sorted by score descending"
        
        print(f"PASS: Clusters sorted by score descending: {scores}")
    
    def test_signal_text_present(self):
        """Each cluster should have a non-empty signal text"""
        response = requests.get(f"{BASE_URL}/api/connections/clusters/intelligence")
        clusters = response.json()["data"]["clusters"]
        
        for cluster in clusters:
            assert cluster["signal"], f"Cluster {cluster['name']} has empty signal"
            assert len(cluster["signal"]) > 5, f"Cluster {cluster['name']} signal too short"
        
        signals = [c["signal"] for c in clusters]
        print(f"PASS: All clusters have signal text: {signals}")
    
    def test_insights_structure(self):
        """Insights should have type, text, severity"""
        response = requests.get(f"{BASE_URL}/api/connections/clusters/intelligence")
        insights = response.json()["data"]["insights"]
        
        for insight in insights:
            assert "type" in insight, "Insight missing type"
            assert "text" in insight, "Insight missing text"
            assert "severity" in insight, "Insight missing severity"
        
        print(f"PASS: {len(insights)} insights have correct structure")
    
    def test_token_clusters_multi_cluster_confirmation(self):
        """token_clusters should show tokens mentioned by multiple clusters"""
        response = requests.get(f"{BASE_URL}/api/connections/clusters/intelligence")
        token_clusters = response.json()["data"]["token_clusters"]
        
        for token, clusters_list in token_clusters.items():
            assert len(clusters_list) >= 2, f"Token {token} should be in at least 2 clusters"
        
        print(f"PASS: token_clusters shows multi-cluster tokens: {list(token_clusters.keys())}")
    
    def test_smart_money_cluster_exists(self):
        """At least one smart_money cluster should exist"""
        response = requests.get(f"{BASE_URL}/api/connections/clusters/intelligence")
        clusters = response.json()["data"]["clusters"]
        
        smart_money = [c for c in clusters if c["type"] == "smart_money"]
        assert len(smart_money) >= 1, "No smart_money cluster found"
        
        print(f"PASS: Found {len(smart_money)} smart_money cluster(s): {[c['name'] for c in smart_money]}")
    
    def test_tokens_differentiated_per_cluster(self):
        """Different clusters should have different token sets (not all identical)"""
        response = requests.get(f"{BASE_URL}/api/connections/clusters/intelligence")
        clusters = response.json()["data"]["clusters"]
        
        token_sets = []
        for cluster in clusters:
            tokens = frozenset(t["symbol"] for t in cluster["tokens"])
            token_sets.append(tokens)
        
        # Check that not all clusters have identical token sets
        unique_sets = set(token_sets)
        assert len(unique_sets) > 1, "All clusters have identical token sets"
        
        print(f"PASS: Clusters have {len(unique_sets)} unique token sets")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
