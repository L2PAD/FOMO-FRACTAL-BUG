"""
Cosmic Radar API Tests
Tests for /api/connections/radar/cosmic endpoint
Features: velocity_norm, quality, zone classification, radar_score, insights, zone_counts
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestCosmicRadarAPI:
    """Tests for the Cosmic Radar endpoint"""

    def test_cosmic_radar_endpoint_returns_200(self):
        """Test that the cosmic radar endpoint returns 200 OK"""
        response = requests.get(f"{BASE_URL}/api/connections/radar/cosmic?limit=100")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: Cosmic radar endpoint returns 200")

    def test_cosmic_radar_response_structure(self):
        """Test that response has correct top-level structure"""
        response = requests.get(f"{BASE_URL}/api/connections/radar/cosmic?limit=100")
        data = response.json()
        
        assert data.get("ok") == True, "Response should have ok=True"
        assert "data" in data, "Response should have 'data' field"
        assert "accounts" in data["data"], "Data should have 'accounts' array"
        assert "zone_counts" in data["data"], "Data should have 'zone_counts' object"
        assert "insights" in data["data"], "Data should have 'insights' array"
        assert "total" in data["data"], "Data should have 'total' count"
        print("PASS: Response structure is correct")

    def test_actor_has_required_fields(self):
        """Test that each actor has all required fields"""
        response = requests.get(f"{BASE_URL}/api/connections/radar/cosmic?limit=100")
        data = response.json()
        accounts = data["data"]["accounts"]
        
        required_fields = [
            "author_id", "username", "display_name", "avatar", "followers",
            "velocity_norm", "quality", "zone", "radar_score", "size_norm",
            "signal_type", "trail", "history_confidence"
        ]
        
        assert len(accounts) > 0, "Should have at least one actor"
        
        for actor in accounts:
            for field in required_fields:
                assert field in actor, f"Actor missing required field: {field}"
        
        print(f"PASS: All {len(accounts)} actors have required fields")

    def test_zone_classification_alpha(self):
        """Test alpha zone classification: vel > 0.3 AND qual > 0.6"""
        response = requests.get(f"{BASE_URL}/api/connections/radar/cosmic?limit=100")
        data = response.json()
        accounts = data["data"]["accounts"]
        
        alpha_actors = [a for a in accounts if a["zone"] == "alpha"]
        
        for actor in alpha_actors:
            assert actor["velocity_norm"] > 0.3, f"Alpha actor {actor['username']} should have velocity > 0.3, got {actor['velocity_norm']}"
            assert actor["quality"] > 0.6, f"Alpha actor {actor['username']} should have quality > 0.6, got {actor['quality']}"
        
        print(f"PASS: {len(alpha_actors)} alpha actors correctly classified")

    def test_zone_classification_opportunity(self):
        """Test opportunity zone classification: vel > 0.3 AND qual <= 0.6"""
        response = requests.get(f"{BASE_URL}/api/connections/radar/cosmic?limit=100")
        data = response.json()
        accounts = data["data"]["accounts"]
        
        opp_actors = [a for a in accounts if a["zone"] == "opportunity"]
        
        for actor in opp_actors:
            assert actor["velocity_norm"] > 0.3, f"Opportunity actor {actor['username']} should have velocity > 0.3"
            assert actor["quality"] <= 0.6, f"Opportunity actor {actor['username']} should have quality <= 0.6"
        
        print(f"PASS: {len(opp_actors)} opportunity actors correctly classified")

    def test_zone_classification_stable(self):
        """Test stable zone classification: vel <= 0.3 AND qual > 0.6"""
        response = requests.get(f"{BASE_URL}/api/connections/radar/cosmic?limit=100")
        data = response.json()
        accounts = data["data"]["accounts"]
        
        stable_actors = [a for a in accounts if a["zone"] == "stable"]
        
        for actor in stable_actors:
            assert actor["velocity_norm"] <= 0.3, f"Stable actor {actor['username']} should have velocity <= 0.3"
            assert actor["quality"] > 0.6, f"Stable actor {actor['username']} should have quality > 0.6"
        
        print(f"PASS: {len(stable_actors)} stable actors correctly classified")

    def test_zone_classification_noise(self):
        """Test noise zone classification: vel <= 0.3 AND qual <= 0.6"""
        response = requests.get(f"{BASE_URL}/api/connections/radar/cosmic?limit=100")
        data = response.json()
        accounts = data["data"]["accounts"]
        
        noise_actors = [a for a in accounts if a["zone"] == "noise"]
        
        for actor in noise_actors:
            assert actor["velocity_norm"] <= 0.3, f"Noise actor {actor['username']} should have velocity <= 0.3"
            assert actor["quality"] <= 0.6, f"Noise actor {actor['username']} should have quality <= 0.6"
        
        print(f"PASS: {len(noise_actors)} noise actors correctly classified")

    def test_zone_counts_match_actors(self):
        """Test that zone_counts matches actual actor counts"""
        response = requests.get(f"{BASE_URL}/api/connections/radar/cosmic?limit=100")
        data = response.json()
        accounts = data["data"]["accounts"]
        zone_counts = data["data"]["zone_counts"]
        
        actual_counts = {"alpha": 0, "opportunity": 0, "stable": 0, "noise": 0}
        for actor in accounts:
            actual_counts[actor["zone"]] += 1
        
        for zone in ["alpha", "opportunity", "stable", "noise"]:
            assert zone_counts.get(zone, 0) == actual_counts[zone], \
                f"Zone count mismatch for {zone}: expected {actual_counts[zone]}, got {zone_counts.get(zone, 0)}"
        
        print(f"PASS: Zone counts match: {zone_counts}")

    def test_insights_structure(self):
        """Test that insights array has correct structure (max 2 items)"""
        response = requests.get(f"{BASE_URL}/api/connections/radar/cosmic?limit=100")
        data = response.json()
        insights = data["data"]["insights"]
        
        assert isinstance(insights, list), "Insights should be a list"
        assert len(insights) <= 2, f"Insights should have max 2 items, got {len(insights)}"
        
        for insight in insights:
            assert "type" in insight, "Insight should have 'type' field"
            assert "text" in insight, "Insight should have 'text' field"
        
        print(f"PASS: Insights structure correct, {len(insights)} insights returned")

    def test_actors_sorted_by_radar_score(self):
        """Test that actors are sorted by radar_score descending"""
        response = requests.get(f"{BASE_URL}/api/connections/radar/cosmic?limit=100")
        data = response.json()
        accounts = data["data"]["accounts"]
        
        if len(accounts) > 1:
            scores = [a["radar_score"] for a in accounts]
            assert scores == sorted(scores, reverse=True), "Actors should be sorted by radar_score descending"
        
        print(f"PASS: Actors sorted by radar_score (top: {accounts[0]['radar_score'] if accounts else 'N/A'})")

    def test_velocity_norm_range(self):
        """Test that velocity_norm is within valid range [-1, 1]"""
        response = requests.get(f"{BASE_URL}/api/connections/radar/cosmic?limit=100")
        data = response.json()
        accounts = data["data"]["accounts"]
        
        for actor in accounts:
            assert -1 <= actor["velocity_norm"] <= 1, \
                f"Actor {actor['username']} velocity_norm {actor['velocity_norm']} out of range [-1, 1]"
        
        print("PASS: All velocity_norm values in valid range")

    def test_quality_range(self):
        """Test that quality is within valid range [0, 1]"""
        response = requests.get(f"{BASE_URL}/api/connections/radar/cosmic?limit=100")
        data = response.json()
        accounts = data["data"]["accounts"]
        
        for actor in accounts:
            assert 0 <= actor["quality"] <= 1, \
                f"Actor {actor['username']} quality {actor['quality']} out of range [0, 1]"
        
        print("PASS: All quality values in valid range")

    def test_size_norm_range(self):
        """Test that size_norm is within valid range [4, 20]"""
        response = requests.get(f"{BASE_URL}/api/connections/radar/cosmic?limit=100")
        data = response.json()
        accounts = data["data"]["accounts"]
        
        for actor in accounts:
            assert 4 <= actor["size_norm"] <= 20, \
                f"Actor {actor['username']} size_norm {actor['size_norm']} out of range [4, 20]"
        
        print("PASS: All size_norm values in valid range")

    def test_signal_type_values(self):
        """Test that signal_type has valid values"""
        response = requests.get(f"{BASE_URL}/api/connections/radar/cosmic?limit=100")
        data = response.json()
        accounts = data["data"]["accounts"]
        
        valid_types = {"breakout", "early", "stable", "noise"}
        
        for actor in accounts:
            assert actor["signal_type"] in valid_types, \
                f"Actor {actor['username']} has invalid signal_type: {actor['signal_type']}"
        
        print("PASS: All signal_type values are valid")

    def test_history_confidence_values(self):
        """Test that history_confidence has valid values"""
        response = requests.get(f"{BASE_URL}/api/connections/radar/cosmic?limit=100")
        data = response.json()
        accounts = data["data"]["accounts"]
        
        valid_confidence = {"none", "low", "medium", "high"}
        
        for actor in accounts:
            assert actor["history_confidence"] in valid_confidence, \
                f"Actor {actor['username']} has invalid history_confidence: {actor['history_confidence']}"
        
        print("PASS: All history_confidence values are valid")

    def test_trail_structure(self):
        """Test that trail array has correct structure"""
        response = requests.get(f"{BASE_URL}/api/connections/radar/cosmic?limit=100")
        data = response.json()
        accounts = data["data"]["accounts"]
        
        for actor in accounts:
            assert isinstance(actor["trail"], list), f"Actor {actor['username']} trail should be a list"
            for point in actor["trail"]:
                assert "x" in point, "Trail point should have 'x' (velocity)"
                assert "y" in point, "Trail point should have 'y' (quality)"
                assert "t" in point, "Trail point should have 't' (timestamp)"
        
        print("PASS: All trail structures are valid")

    def test_limit_parameter(self):
        """Test that limit parameter works correctly"""
        response = requests.get(f"{BASE_URL}/api/connections/radar/cosmic?limit=5")
        data = response.json()
        accounts = data["data"]["accounts"]
        
        # Should return at most 5 actors (or fewer if less data available)
        assert len(accounts) <= 5, f"Expected at most 5 actors, got {len(accounts)}"
        print(f"PASS: Limit parameter works, returned {len(accounts)} actors")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
