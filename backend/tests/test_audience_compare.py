"""
Audience Compare API Tests - Bot Detection Audience Overlap Intelligence
Tests the new /compare and /actors-list endpoints for the AOI feature.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestActorsList:
    """Tests for /api/connections/network/actors-list endpoint"""
    
    def test_actors_list_returns_200(self):
        """Verify actors-list endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/connections/network/actors-list")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        print(f"PASS: actors-list returns 200 with {len(data.get('actors', []))} actors")
    
    def test_actors_list_has_required_fields(self):
        """Verify each actor has actorId, aqi, level fields"""
        response = requests.get(f"{BASE_URL}/api/connections/network/actors-list")
        data = response.json()
        actors = data.get("actors", [])
        assert len(actors) > 0, "Should have at least one actor"
        
        for actor in actors[:5]:  # Check first 5
            assert "actorId" in actor, f"Actor missing actorId: {actor}"
            assert "aqi" in actor, f"Actor missing aqi: {actor}"
            assert "level" in actor, f"Actor missing level: {actor}"
        print(f"PASS: actors have required fields (actorId, aqi, level)")
    
    def test_actors_list_sorted_by_aqi(self):
        """Verify actors are sorted by AQI descending"""
        response = requests.get(f"{BASE_URL}/api/connections/network/actors-list")
        data = response.json()
        actors = data.get("actors", [])
        
        if len(actors) >= 2:
            aqis = [a.get("aqi", 0) for a in actors]
            assert aqis == sorted(aqis, reverse=True), "Actors should be sorted by AQI descending"
        print(f"PASS: actors sorted by AQI descending")
    
    def test_actors_list_count(self):
        """Verify actors-list returns expected count (21 actors)"""
        response = requests.get(f"{BASE_URL}/api/connections/network/actors-list")
        data = response.json()
        actors = data.get("actors", [])
        assert len(actors) == 21, f"Expected 21 actors, got {len(actors)}"
        print(f"PASS: actors-list returns 21 actors")


class TestCompareEndpoint:
    """Tests for /api/connections/network/compare endpoint"""
    
    def test_compare_valid_actors(self):
        """Compare two valid actors: thecryptodog vs cryptowendyo"""
        response = requests.get(f"{BASE_URL}/api/connections/network/compare?a=thecryptodog&b=cryptowendyo")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        print(f"PASS: compare returns 200 for valid actors")
    
    def test_compare_returns_overlap_metrics(self):
        """Verify compare returns overlap metrics"""
        response = requests.get(f"{BASE_URL}/api/connections/network/compare?a=thecryptodog&b=cryptowendyo")
        data = response.json()
        
        assert "overlap" in data, "Response missing overlap"
        overlap = data["overlap"]
        assert "estimated" in overlap, "Overlap missing estimated"
        assert "uniqueA" in overlap, "Overlap missing uniqueA"
        assert "uniqueB" in overlap, "Overlap missing uniqueB"
        assert "behaviorSimilarity" in overlap, "Overlap missing behaviorSimilarity"
        assert "timeSimilarity" in overlap, "Overlap missing timeSimilarity"
        assert "tokenSimilarity" in overlap, "Overlap missing tokenSimilarity"
        assert "sharedTokens" in overlap, "Overlap missing sharedTokens"
        print(f"PASS: compare returns overlap metrics (estimated={overlap['estimated']:.2%})")
    
    def test_compare_returns_classification(self):
        """Verify compare returns classification and risk"""
        response = requests.get(f"{BASE_URL}/api/connections/network/compare?a=thecryptodog&b=cryptowendyo")
        data = response.json()
        
        assert "classification" in data, "Response missing classification"
        assert "risk" in data, "Response missing risk"
        assert data["classification"] in ["Bot Amplification Network", "Coordinated Audience", "Weak Connection", "Independent Audiences"]
        assert data["risk"] in ["HIGH", "MEDIUM", "LOW", "NONE"]
        print(f"PASS: classification={data['classification']}, risk={data['risk']}")
    
    def test_compare_returns_interpretation(self):
        """Verify compare returns interpretation array"""
        response = requests.get(f"{BASE_URL}/api/connections/network/compare?a=thecryptodog&b=cryptowendyo")
        data = response.json()
        
        assert "interpretation" in data, "Response missing interpretation"
        assert isinstance(data["interpretation"], list), "Interpretation should be a list"
        assert len(data["interpretation"]) > 0, "Interpretation should not be empty"
        print(f"PASS: interpretation has {len(data['interpretation'])} lines")
    
    def test_compare_returns_howToUse(self):
        """Verify compare returns howToUse guidance"""
        response = requests.get(f"{BASE_URL}/api/connections/network/compare?a=thecryptodog&b=cryptowendyo")
        data = response.json()
        
        assert "howToUse" in data, "Response missing howToUse"
        assert isinstance(data["howToUse"], str), "howToUse should be a string"
        assert len(data["howToUse"]) > 0, "howToUse should not be empty"
        print(f"PASS: howToUse present")
    
    def test_compare_returns_quality_metrics(self):
        """Verify compare returns quality metrics"""
        response = requests.get(f"{BASE_URL}/api/connections/network/compare?a=thecryptodog&b=cryptowendyo")
        data = response.json()
        
        assert "quality" in data, "Response missing quality"
        quality = data["quality"]
        assert "overlapBotRatio" in quality, "Quality missing overlapBotRatio"
        assert "relationshipScore" in quality, "Quality missing relationshipScore"
        print(f"PASS: quality metrics present (botRatio={quality['overlapBotRatio']:.2%})")
    
    def test_compare_returns_actor_details(self):
        """Verify compare returns actorA and actorB details"""
        response = requests.get(f"{BASE_URL}/api/connections/network/compare?a=thecryptodog&b=cryptowendyo")
        data = response.json()
        
        assert "actorA" in data, "Response missing actorA"
        assert "actorB" in data, "Response missing actorB"
        
        for actor_key in ["actorA", "actorB"]:
            actor = data[actor_key]
            assert "id" in actor, f"{actor_key} missing id"
            assert "pctBot" in actor, f"{actor_key} missing pctBot"
            assert "aqi" in actor, f"{actor_key} missing aqi"
            assert "level" in actor, f"{actor_key} missing level"
        print(f"PASS: actorA and actorB details present")
    
    def test_compare_returns_shared_cluster(self):
        """Verify compare returns sharedCluster when both actors in same cluster"""
        response = requests.get(f"{BASE_URL}/api/connections/network/compare?a=thecryptodog&b=cryptowendyo")
        data = response.json()
        
        # sharedCluster can be null or object
        assert "sharedCluster" in data, "Response missing sharedCluster"
        if data["sharedCluster"]:
            cluster = data["sharedCluster"]
            assert "farmId" in cluster, "sharedCluster missing farmId"
            assert "name" in cluster, "sharedCluster missing name"
            assert "riskLevel" in cluster, "sharedCluster missing riskLevel"
            print(f"PASS: sharedCluster present: {cluster['name']}")
        else:
            print(f"PASS: sharedCluster is null (actors not in same cluster)")
    
    def test_compare_same_actor_error(self):
        """Verify compare returns error when comparing actor with itself"""
        response = requests.get(f"{BASE_URL}/api/connections/network/compare?a=thecryptodog&b=thecryptodog")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is False
        assert "error" in data
        assert "itself" in data["error"].lower()
        print(f"PASS: same actor comparison returns error: {data['error']}")
    
    def test_compare_unknown_actor_error(self):
        """Verify compare returns error for unknown actor"""
        response = requests.get(f"{BASE_URL}/api/connections/network/compare?a=unknownactor123xyz&b=cryptowendyo")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is False
        assert "error" in data
        assert "no data" in data["error"].lower() or "unknownactor123xyz" in data["error"].lower()
        print(f"PASS: unknown actor returns error: {data['error']}")
    
    def test_compare_case_insensitive(self):
        """Verify compare is case-insensitive"""
        response1 = requests.get(f"{BASE_URL}/api/connections/network/compare?a=TheCryptoDog&b=CryptoWendyO")
        response2 = requests.get(f"{BASE_URL}/api/connections/network/compare?a=thecryptodog&b=cryptowendyo")
        
        data1 = response1.json()
        data2 = response2.json()
        
        # Both should succeed or both should fail
        assert data1["ok"] == data2["ok"], "Case sensitivity mismatch"
        if data1["ok"]:
            assert data1["classification"] == data2["classification"], "Classification should match regardless of case"
        print(f"PASS: compare is case-insensitive")


class TestIntelligenceEndpoint:
    """Tests for /api/connections/network/intelligence endpoint"""
    
    def test_intelligence_returns_howToUse(self):
        """Verify intelligence returns howToUse in clusters"""
        response = requests.get(f"{BASE_URL}/api/connections/network/intelligence")
        data = response.json()
        
        assert data["ok"] is True
        clusters = data.get("clusters", [])
        if clusters:
            cluster = clusters[0]
            assert "howToUse" in cluster, "Cluster missing howToUse"
            assert isinstance(cluster["howToUse"], list), "howToUse should be a list"
            print(f"PASS: intelligence returns howToUse with {len(cluster['howToUse'])} items")
    
    def test_intelligence_returns_metricExplanations(self):
        """Verify intelligence returns metricExplanations in clusters"""
        response = requests.get(f"{BASE_URL}/api/connections/network/intelligence")
        data = response.json()
        
        clusters = data.get("clusters", [])
        if clusters:
            cluster = clusters[0]
            assert "metricExplanations" in cluster, "Cluster missing metricExplanations"
            explanations = cluster["metricExplanations"]
            assert "botScore" in explanations, "Missing botScore explanation"
            assert "density" in explanations, "Missing density explanation"
            assert "confidence" in explanations, "Missing confidence explanation"
            print(f"PASS: intelligence returns metricExplanations")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
