"""
Bakery Engine API Tests — WHO MOVES THE MARKET

Tests for the unified decision engine replacing Backers/Credibility pages.
Endpoints: /api/bakery, /api/bakery/active, /api/bakery/:slug
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestBakeryLeaderboard:
    """Tests for GET /api/bakery — main leaderboard endpoint"""

    def test_bakery_returns_ok(self):
        """GET /api/bakery returns ok:true with bakers array and stats"""
        response = requests.get(f"{BASE_URL}/api/bakery")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert "bakers" in data
        assert isinstance(data["bakers"], list)
        assert len(data["bakers"]) > 0
        
        # Verify stats structure
        assert "stats" in data
        stats = data["stats"]
        assert "total" in stats
        assert "follow" in stats
        assert "watch" in stats
        assert "ignore" in stats

    def test_bakery_baker_structure(self):
        """Each baker has required fields: slug, name, type, score, edge, action, lastSignal"""
        response = requests.get(f"{BASE_URL}/api/bakery")
        data = response.json()
        
        baker = data["bakers"][0]
        required_fields = ["slug", "name", "type", "score", "edge", "edgeLabel", 
                          "marketImpact", "timingAccuracy", "narrativeInfluence", 
                          "consistency", "action", "behavior"]
        
        for field in required_fields:
            assert field in baker, f"Missing field: {field}"
        
        # Verify action is one of FOLLOW/WATCH/IGNORE
        assert baker["action"] in ["FOLLOW", "WATCH", "IGNORE"]
        
        # Verify type is one of FUND/PERSON/MEDIA/PROJECT
        assert baker["type"] in ["FUND", "PERSON", "MEDIA", "PROJECT"]

    def test_bakery_filter_by_fund(self):
        """GET /api/bakery?type=FUND returns only FUND type bakers"""
        response = requests.get(f"{BASE_URL}/api/bakery?type=FUND")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        for baker in data["bakers"]:
            assert baker["type"] == "FUND", f"Expected FUND, got {baker['type']}"

    def test_bakery_filter_by_person(self):
        """GET /api/bakery?type=PERSON returns only PERSON type bakers"""
        response = requests.get(f"{BASE_URL}/api/bakery?type=PERSON")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        for baker in data["bakers"]:
            assert baker["type"] == "PERSON", f"Expected PERSON, got {baker['type']}"

    def test_bakery_stats_consistency(self):
        """Stats follow + watch + ignore = total"""
        response = requests.get(f"{BASE_URL}/api/bakery")
        data = response.json()
        stats = data["stats"]
        
        assert stats["follow"] + stats["watch"] + stats["ignore"] == stats["total"]


class TestBakeryActive:
    """Tests for GET /api/bakery/active — who is driving the market NOW"""

    def test_active_returns_ok(self):
        """GET /api/bakery/active returns ok:true with active bakers array"""
        response = requests.get(f"{BASE_URL}/api/bakery/active")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert "active" in data
        assert isinstance(data["active"], list)

    def test_active_baker_structure(self):
        """Active bakers have slug, name, type, context, tokens, activity"""
        response = requests.get(f"{BASE_URL}/api/bakery/active")
        data = response.json()
        
        if len(data["active"]) > 0:
            active = data["active"][0]
            assert "slug" in active
            assert "name" in active
            assert "type" in active
            assert "context" in active
            assert "tokens" in active
            assert "activity" in active


class TestBakerDetail:
    """Tests for GET /api/bakery/:slug — entity detail page"""

    def test_cz_binance_detail(self):
        """GET /api/bakery/cz_binance returns ok:true with baker detail"""
        response = requests.get(f"{BASE_URL}/api/bakery/cz_binance")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert "baker" in data
        assert "recentImpact" in data
        assert "connections" in data
        
        baker = data["baker"]
        assert baker["slug"] == "cz_binance"
        assert baker["name"] == "CZ"
        assert baker["type"] == "PERSON"

    def test_vitalikbuterin_detail(self):
        """GET /api/bakery/vitalikbuterin returns baker with strengths and weaknesses"""
        response = requests.get(f"{BASE_URL}/api/bakery/vitalikbuterin")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        baker = data["baker"]
        
        assert "strengths" in baker
        assert "weaknesses" in baker
        assert isinstance(baker["strengths"], list)
        assert isinstance(baker["weaknesses"], list)

    def test_baker_detail_score_breakdown(self):
        """Baker detail includes score breakdown: marketImpact, timingAccuracy, narrativeInfluence, consistency"""
        response = requests.get(f"{BASE_URL}/api/bakery/cz_binance")
        data = response.json()
        baker = data["baker"]
        
        breakdown_fields = ["marketImpact", "timingAccuracy", "narrativeInfluence", "consistency"]
        for field in breakdown_fields:
            assert field in baker, f"Missing breakdown field: {field}"
            assert isinstance(baker[field], (int, float))

    def test_baker_detail_performance(self):
        """Baker detail includes performance: hitRate, callsTracked, avgReturn"""
        response = requests.get(f"{BASE_URL}/api/bakery/cz_binance")
        data = response.json()
        baker = data["baker"]
        
        assert "hitRate" in baker
        assert "callsTracked" in baker
        assert "avgReturn" in baker

    def test_baker_detail_recent_impact(self):
        """Baker detail includes recentImpact array with token, return, strength"""
        response = requests.get(f"{BASE_URL}/api/bakery/cz_binance")
        data = response.json()
        
        assert len(data["recentImpact"]) > 0
        impact = data["recentImpact"][0]
        assert "token" in impact
        assert "return" in impact
        assert "strength" in impact

    def test_baker_detail_connections(self):
        """Baker detail includes connections array with slug, name, type"""
        response = requests.get(f"{BASE_URL}/api/bakery/cz_binance")
        data = response.json()
        
        assert len(data["connections"]) > 0
        conn = data["connections"][0]
        assert "slug" in conn
        assert "name" in conn
        assert "type" in conn

    def test_baker_not_found(self):
        """GET /api/bakery/nonexistent returns ok:false with error"""
        response = requests.get(f"{BASE_URL}/api/bakery/nonexistent_baker_xyz")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is False
        assert "error" in data

    def test_a16z_fund_detail(self):
        """GET /api/bakery/a16z returns FUND type baker"""
        response = requests.get(f"{BASE_URL}/api/bakery/a16z")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert data["baker"]["type"] == "FUND"
        assert data["baker"]["slug"] == "a16z"


class TestBakeryScoring:
    """Tests for unified scoring formula validation"""

    def test_score_within_range(self):
        """All scores are within 0-100 range"""
        response = requests.get(f"{BASE_URL}/api/bakery")
        data = response.json()
        
        for baker in data["bakers"]:
            assert 0 <= baker["score"] <= 100
            assert 0 <= baker["edge"] <= 100
            assert 0 <= baker["marketImpact"] <= 100
            assert 0 <= baker["timingAccuracy"] <= 100
            assert 0 <= baker["narrativeInfluence"] <= 100
            assert 0 <= baker["consistency"] <= 100

    def test_action_thresholds(self):
        """FOLLOW >= 85, WATCH >= 65, IGNORE < 65"""
        response = requests.get(f"{BASE_URL}/api/bakery")
        data = response.json()
        
        for baker in data["bakers"]:
            if baker["action"] == "FOLLOW":
                assert baker["score"] >= 85
            elif baker["action"] == "WATCH":
                assert 65 <= baker["score"] < 85
            else:  # IGNORE
                assert baker["score"] < 65

    def test_edge_label_thresholds(self):
        """HIGH >= 75, MID >= 50, LOW < 50"""
        response = requests.get(f"{BASE_URL}/api/bakery")
        data = response.json()
        
        for baker in data["bakers"]:
            if baker["edgeLabel"] == "HIGH":
                assert baker["edge"] >= 75
            elif baker["edgeLabel"] == "MID":
                assert 50 <= baker["edge"] < 75
            else:  # LOW
                assert baker["edge"] < 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
