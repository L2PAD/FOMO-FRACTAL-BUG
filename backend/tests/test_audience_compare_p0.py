"""
Audience Compare P0 Tests - Testing ANY handle comparison feature
Tests: actors-list with all 417 actors, on-the-fly analysis, status badges, error handling
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com')


class TestActorsList:
    """Test /api/connections/network/actors-list endpoint"""

    def test_actors_list_returns_all_actors(self):
        """Should return 417 total actors (21 analyzed + 396 unanalyzed/targets)"""
        resp = requests.get(f"{BASE_URL}/api/connections/network/actors-list")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["totalCount"] >= 400  # Should be ~417
        assert data["analyzedCount"] == 21
        assert len(data["actors"]) == data["totalCount"]

    def test_actors_list_has_correct_levels(self):
        """Should have ELITE, GOOD, MODERATE, UNANALYZED, TARGET levels"""
        resp = requests.get(f"{BASE_URL}/api/connections/network/actors-list")
        data = resp.json()
        levels = set(a["level"] for a in data["actors"])
        assert "ELITE" in levels
        assert "GOOD" in levels or "MODERATE" in levels
        assert "UNANALYZED" in levels
        assert "TARGET" in levels

    def test_actors_list_sorted_by_aqi(self):
        """Analyzed actors should be sorted by AQI descending"""
        resp = requests.get(f"{BASE_URL}/api/connections/network/actors-list")
        data = resp.json()
        analyzed = [a for a in data["actors"] if a["level"] in ["ELITE", "GOOD", "MODERATE", "RISKY"]]
        aqis = [a["aqi"] for a in analyzed]
        assert aqis == sorted(aqis, reverse=True), "Analyzed actors should be sorted by AQI descending"

    def test_actors_list_search_filter(self):
        """Should filter actors by search query"""
        resp = requests.get(f"{BASE_URL}/api/connections/network/actors-list?q=crypto")
        data = resp.json()
        assert data["ok"] is True
        assert len(data["actors"]) > 0
        for actor in data["actors"]:
            assert "crypto" in actor["actorId"].lower()

    def test_actors_list_has_required_fields(self):
        """Each actor should have actorId, aqi, level, category, followers"""
        resp = requests.get(f"{BASE_URL}/api/connections/network/actors-list")
        data = resp.json()
        for actor in data["actors"][:10]:  # Check first 10
            assert "actorId" in actor
            assert "aqi" in actor
            assert "level" in actor
            assert "category" in actor
            assert "followers" in actor

    def test_unanalyzed_actors_have_tweet_count(self):
        """UNANALYZED actors should have tweetCount field"""
        resp = requests.get(f"{BASE_URL}/api/connections/network/actors-list")
        data = resp.json()
        unanalyzed = [a for a in data["actors"] if a["level"] == "UNANALYZED"]
        assert len(unanalyzed) > 0
        for actor in unanalyzed[:5]:
            assert "tweetCount" in actor
            assert actor["tweetCount"] >= 1


class TestCompareAnalyzedActors:
    """Test compare endpoint with pre-analyzed actors"""

    def test_compare_elite_actors(self):
        """Compare two ELITE analyzed actors"""
        resp = requests.get(f"{BASE_URL}/api/connections/network/compare?a=cryptocapo_&b=cz_binance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["actorA"]["dataStatus"] == "analyzed"
        assert data["actorB"]["dataStatus"] == "analyzed"
        assert "classification" in data
        assert "risk" in data
        assert "overlap" in data
        assert "interpretation" in data

    def test_compare_returns_overlap_metrics(self):
        """Should return all overlap metrics"""
        resp = requests.get(f"{BASE_URL}/api/connections/network/compare?a=cryptocapo_&b=cz_binance")
        data = resp.json()
        overlap = data["overlap"]
        assert "estimated" in overlap
        assert "uniqueA" in overlap
        assert "uniqueB" in overlap
        assert "behaviorSimilarity" in overlap
        assert "timeSimilarity" in overlap
        assert "tokenSimilarity" in overlap
        assert "sharedTokens" in overlap

    def test_compare_returns_quality_metrics(self):
        """Should return quality metrics"""
        resp = requests.get(f"{BASE_URL}/api/connections/network/compare?a=cryptocapo_&b=cz_binance")
        data = resp.json()
        quality = data["quality"]
        assert "overlapBotRatio" in quality
        assert "relationshipScore" in quality

    def test_compare_returns_actor_details(self):
        """Should return actor details with pctBot, aqi, level"""
        resp = requests.get(f"{BASE_URL}/api/connections/network/compare?a=cryptocapo_&b=cz_binance")
        data = resp.json()
        for actor_key in ["actorA", "actorB"]:
            actor = data[actor_key]
            assert "id" in actor
            assert "pctBot" in actor
            assert "aqi" in actor
            assert "level" in actor
            assert "dataStatus" in actor


class TestCompareOnTheFly:
    """Test on-the-fly analysis for UNANALYZED actors"""

    def test_compare_unanalyzed_actor(self):
        """UNANALYZED actor should be computed on-the-fly"""
        resp = requests.get(f"{BASE_URL}/api/connections/network/compare?a=dutch_defi&b=cryptocapo_")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["actorA"]["dataStatus"] == "computed"
        assert data["actorB"]["dataStatus"] == "analyzed"

    def test_computed_actor_has_data_notes(self):
        """On-the-fly computed actors should have dataNotes"""
        resp = requests.get(f"{BASE_URL}/api/connections/network/compare?a=dutch_defi&b=cryptocapo_")
        data = resp.json()
        assert "dataNotes" in data
        assert len(data["dataNotes"]) > 0
        assert "on-the-fly" in data["dataNotes"][0].lower()

    def test_compare_target_actor_metadata_only(self):
        """TARGET actor should return metadata_only status"""
        resp = requests.get(f"{BASE_URL}/api/connections/network/compare?a=vitalikbuterin&b=cryptocapo_")
        data = resp.json()
        assert data["ok"] is True
        assert data["actorA"]["dataStatus"] == "metadata_only"
        assert "limited data" in data["dataNotes"][0].lower()


class TestCompareHandleNormalization:
    """Test @ prefix stripping and case insensitivity"""

    def test_compare_strips_at_prefix(self):
        """Should strip @ prefix from handles"""
        resp = requests.get(f"{BASE_URL}/api/connections/network/compare?a=@cryptocapo_&b=@cz_binance")
        data = resp.json()
        assert data["ok"] is True
        assert data["actorA"]["id"] == "cryptocapo_"
        assert data["actorB"]["id"] == "cz_binance"

    def test_compare_case_insensitive(self):
        """Should be case insensitive"""
        resp = requests.get(f"{BASE_URL}/api/connections/network/compare?a=CRYPTOCAPO_&b=CZ_BINANCE")
        data = resp.json()
        assert data["ok"] is True
        assert data["actorA"]["id"] == "cryptocapo_"
        assert data["actorB"]["id"] == "cz_binance"


class TestCompareErrorHandling:
    """Test error handling for invalid comparisons"""

    def test_compare_same_actor_error(self):
        """Should error when comparing actor with itself"""
        resp = requests.get(f"{BASE_URL}/api/connections/network/compare?a=cryptocapo_&b=cryptocapo_")
        data = resp.json()
        assert data["ok"] is False
        assert "Cannot compare actor with itself" in data["error"]

    def test_compare_unknown_actor_error(self):
        """Should error with missingActors for unknown handles"""
        resp = requests.get(f"{BASE_URL}/api/connections/network/compare?a=totally_unknown_xyz_123&b=cryptocapo_")
        data = resp.json()
        assert data["ok"] is False
        assert "No data found" in data["error"]
        assert "missingActors" in data
        assert "totally_unknown_xyz_123" in data["missingActors"]
        assert "suggestion" in data

    def test_compare_both_unknown_actors(self):
        """Should list both missing actors"""
        resp = requests.get(f"{BASE_URL}/api/connections/network/compare?a=unknown_a_xyz&b=unknown_b_xyz")
        data = resp.json()
        assert data["ok"] is False
        assert len(data["missingActors"]) == 2


class TestIntelligenceEndpoint:
    """Test /api/connections/network/intelligence endpoint"""

    def test_intelligence_returns_clusters(self):
        """Should return clusters with howToUse and metricExplanations"""
        resp = requests.get(f"{BASE_URL}/api/connections/network/intelligence")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        if data["clusters"]:
            cluster = data["clusters"][0]
            assert "howToUse" in cluster
            assert "metricExplanations" in cluster
            assert len(cluster["howToUse"]) >= 1

    def test_intelligence_returns_signals(self):
        """Should return active signals"""
        resp = requests.get(f"{BASE_URL}/api/connections/network/intelligence")
        data = resp.json()
        if data["signals"]:
            signal = data["signals"][0]
            assert "type" in signal
            assert "severity" in signal
            assert "title" in signal
            assert "action" in signal


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
