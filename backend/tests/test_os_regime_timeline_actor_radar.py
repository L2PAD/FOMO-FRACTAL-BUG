"""
OS Market Timeline & Actor Radar Backend Tests
================================================
Tests for Sprint 270 new features:
1. /api/os/regime-timeline - Regime change timeline
2. /api/os/actor-radar - Actor radar with 5 actors
3. /api/os/state - Extended with regime_timeline and actor_radar fields
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")

# Expected actor IDs
EXPECTED_ACTOR_IDS = ["smart_money", "exchanges", "market_makers", "funds", "whales"]


class TestRegimeTimeline:
    """Tests for /api/os/regime-timeline endpoint"""

    def test_regime_timeline_returns_ok(self):
        """Test that regime-timeline endpoint returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/os/regime-timeline")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True, f"Expected ok:true, got {data}"
        print(f"PASS: /api/os/regime-timeline returns ok:true")

    def test_regime_timeline_has_timeline_array(self):
        """Test that response contains timeline array"""
        response = requests.get(f"{BASE_URL}/api/os/regime-timeline")
        data = response.json()
        assert "timeline" in data, "Response should contain 'timeline' field"
        assert isinstance(data["timeline"], list), "timeline should be an array"
        print(f"PASS: timeline is an array with {len(data['timeline'])} entries")

    def test_regime_timeline_entry_structure(self):
        """Test that timeline entries have required fields: regime, previous_regime, confidence, driver, timestamp"""
        response = requests.get(f"{BASE_URL}/api/os/regime-timeline")
        data = response.json()
        timeline = data.get("timeline", [])
        
        if len(timeline) == 0:
            pytest.skip("No regime history entries - tracking may have just started")
        
        entry = timeline[0]
        # Required fields
        assert "regime" in entry, "Entry should have 'regime' field"
        assert "confidence" in entry, "Entry should have 'confidence' field"
        assert "timestamp" in entry, "Entry should have 'timestamp' field"
        assert "driver" in entry, "Entry should have 'driver' field"
        # previous_regime can be null for first entry
        assert "previous_regime" in entry, "Entry should have 'previous_regime' field (can be null)"
        
        # Validate confidence is 0-1 range (normalized)
        assert 0 <= entry["confidence"] <= 1, f"Confidence should be 0-1, got {entry['confidence']}"
        
        print(f"PASS: Timeline entry has all required fields")
        print(f"  - regime: {entry['regime']}")
        print(f"  - previous_regime: {entry['previous_regime']}")
        print(f"  - confidence: {entry['confidence']}")
        print(f"  - driver: {entry['driver']}")
        print(f"  - timestamp: {entry['timestamp']}")


class TestActorRadar:
    """Tests for /api/os/actor-radar endpoint"""

    def test_actor_radar_returns_ok(self):
        """Test that actor-radar endpoint returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/os/actor-radar")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True, f"Expected ok:true, got {data}"
        print(f"PASS: /api/os/actor-radar returns ok:true")

    def test_actor_radar_has_actors_array(self):
        """Test that response contains actors array"""
        response = requests.get(f"{BASE_URL}/api/os/actor-radar")
        data = response.json()
        assert "actors" in data, "Response should contain 'actors' field"
        assert isinstance(data["actors"], list), "actors should be an array"
        print(f"PASS: actors is an array with {len(data['actors'])} actors")

    def test_actor_radar_has_5_actors(self):
        """Test that actor radar contains exactly 5 actors"""
        response = requests.get(f"{BASE_URL}/api/os/actor-radar")
        data = response.json()
        actors = data.get("actors", [])
        assert len(actors) == 5, f"Expected 5 actors, got {len(actors)}"
        print(f"PASS: Actor radar has exactly 5 actors")

    def test_actor_radar_has_correct_actor_ids(self):
        """Test that all 5 expected actor IDs are present"""
        response = requests.get(f"{BASE_URL}/api/os/actor-radar")
        data = response.json()
        actors = data.get("actors", [])
        
        actor_ids = [a.get("id") for a in actors]
        for expected_id in EXPECTED_ACTOR_IDS:
            assert expected_id in actor_ids, f"Missing actor ID: {expected_id}"
        
        print(f"PASS: All 5 actor IDs present: {actor_ids}")

    def test_actor_radar_actor_structure(self):
        """Test that each actor has: id, name, action, direction, strength"""
        response = requests.get(f"{BASE_URL}/api/os/actor-radar")
        data = response.json()
        actors = data.get("actors", [])
        
        for actor in actors:
            assert "id" in actor, f"Actor should have 'id' field"
            assert "name" in actor, f"Actor should have 'name' field"
            assert "action" in actor, f"Actor should have 'action' field"
            assert "direction" in actor, f"Actor should have 'direction' field"
            assert "strength" in actor, f"Actor should have 'strength' field"
            
            # Validate direction values
            assert actor["direction"] in ["up", "down", "neutral"], f"Direction should be up/down/neutral, got {actor['direction']}"
            
            # Validate strength is 0-100
            assert 0 <= actor["strength"] <= 100, f"Strength should be 0-100, got {actor['strength']}"
        
        print(f"PASS: All actors have correct structure with id, name, action, direction, strength")

    def test_actor_radar_has_summary(self):
        """Test that actor radar has summary field with valid value"""
        response = requests.get(f"{BASE_URL}/api/os/actor-radar")
        data = response.json()
        
        assert "summary" in data, "Response should have 'summary' field"
        valid_summaries = ["Net Bullish", "Net Bearish", "Mixed"]
        assert data["summary"] in valid_summaries, f"Summary should be one of {valid_summaries}, got {data['summary']}"
        
        print(f"PASS: Actor radar summary: {data['summary']}")


class TestOSStateExtended:
    """Tests for /api/os/state endpoint with new regime_timeline and actor_radar fields"""

    def test_os_state_returns_ok(self):
        """Test that /api/os/state returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/os/state")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True, f"Expected ok:true, got {data}"
        print(f"PASS: /api/os/state returns ok:true")

    def test_os_state_has_regime_timeline(self):
        """Test that /api/os/state includes regime_timeline field"""
        response = requests.get(f"{BASE_URL}/api/os/state")
        data = response.json()
        
        assert "regime_timeline" in data, "OS state should include 'regime_timeline' field"
        assert isinstance(data["regime_timeline"], list), "regime_timeline should be an array"
        
        print(f"PASS: /api/os/state has regime_timeline with {len(data['regime_timeline'])} entries")

    def test_os_state_has_actor_radar(self):
        """Test that /api/os/state includes actor_radar field"""
        response = requests.get(f"{BASE_URL}/api/os/state")
        data = response.json()
        
        assert "actor_radar" in data, "OS state should include 'actor_radar' field"
        assert isinstance(data["actor_radar"], dict), "actor_radar should be an object"
        assert "actors" in data["actor_radar"], "actor_radar should have 'actors' array"
        
        print(f"PASS: /api/os/state has actor_radar with {len(data['actor_radar'].get('actors', []))} actors")

    def test_os_state_has_all_legacy_fields(self):
        """Test that /api/os/state still has all legacy fields"""
        response = requests.get(f"{BASE_URL}/api/os/state")
        data = response.json()
        
        legacy_fields = [
            "market_state",
            "market_risk", 
            "market_pulse",
            "opportunities",
            "actor_pressure",
            "liquidity_targets",
            "alerts"
        ]
        
        for field in legacy_fields:
            assert field in data, f"OS state should include legacy field '{field}'"
        
        print(f"PASS: All legacy fields present: {legacy_fields}")

    def test_os_state_actor_radar_structure(self):
        """Test that actor_radar in os/state has correct structure"""
        response = requests.get(f"{BASE_URL}/api/os/state")
        data = response.json()
        
        actor_radar = data.get("actor_radar", {})
        actors = actor_radar.get("actors", [])
        
        assert len(actors) == 5, f"Expected 5 actors in actor_radar, got {len(actors)}"
        
        actor_ids = [a.get("id") for a in actors]
        for expected_id in EXPECTED_ACTOR_IDS:
            assert expected_id in actor_ids, f"Missing actor ID: {expected_id}"
        
        print(f"PASS: actor_radar in os/state has 5 correct actors")

    def test_os_state_market_pulse_present(self):
        """Test that market_pulse is present with required fields (regression)"""
        response = requests.get(f"{BASE_URL}/api/os/state")
        data = response.json()
        
        pulse = data.get("market_pulse", {})
        assert "pulse" in pulse, "market_pulse should have 'pulse' level"
        assert "score" in pulse, "market_pulse should have 'score'"
        
        valid_levels = ["LOW", "NORMAL", "HIGH", "EXTREME"]
        assert pulse["pulse"] in valid_levels, f"Pulse level should be one of {valid_levels}"
        
        print(f"PASS: market_pulse present - level={pulse['pulse']}, score={pulse['score']}")

    def test_os_state_opportunities_structure(self):
        """Test that opportunities have required fields (regression)"""
        response = requests.get(f"{BASE_URL}/api/os/state")
        data = response.json()
        
        opportunities = data.get("opportunities", [])
        if len(opportunities) > 0:
            opp = opportunities[0]
            required_fields = ["setup", "status", "confidence", "probability", "expected_move", "timeframe"]
            for field in required_fields:
                assert field in opp, f"Opportunity should have '{field}' field"
            
            print(f"PASS: Opportunities have required fields including expected_move and timeframe")
        else:
            print("INFO: No opportunities present, skipping structure check")


class TestActorRadarDetails:
    """Detailed tests for actor radar data quality"""

    def test_actor_smart_money(self):
        """Test smart_money actor data"""
        response = requests.get(f"{BASE_URL}/api/os/actor-radar")
        data = response.json()
        actors = {a["id"]: a for a in data.get("actors", [])}
        
        assert "smart_money" in actors, "smart_money actor should exist"
        sm = actors["smart_money"]
        assert sm["name"] == "Smart Money", f"Name should be 'Smart Money', got {sm['name']}"
        print(f"PASS: smart_money - action={sm['action']}, direction={sm['direction']}, strength={sm['strength']}")

    def test_actor_exchanges(self):
        """Test exchanges actor data"""
        response = requests.get(f"{BASE_URL}/api/os/actor-radar")
        data = response.json()
        actors = {a["id"]: a for a in data.get("actors", [])}
        
        assert "exchanges" in actors, "exchanges actor should exist"
        ex = actors["exchanges"]
        assert ex["name"] == "Exchanges", f"Name should be 'Exchanges', got {ex['name']}"
        print(f"PASS: exchanges - action={ex['action']}, direction={ex['direction']}, strength={ex['strength']}")

    def test_actor_market_makers(self):
        """Test market_makers actor data"""
        response = requests.get(f"{BASE_URL}/api/os/actor-radar")
        data = response.json()
        actors = {a["id"]: a for a in data.get("actors", [])}
        
        assert "market_makers" in actors, "market_makers actor should exist"
        mm = actors["market_makers"]
        assert mm["name"] == "Market Makers", f"Name should be 'Market Makers', got {mm['name']}"
        print(f"PASS: market_makers - action={mm['action']}, direction={mm['direction']}, strength={mm['strength']}")

    def test_actor_funds(self):
        """Test funds actor data"""
        response = requests.get(f"{BASE_URL}/api/os/actor-radar")
        data = response.json()
        actors = {a["id"]: a for a in data.get("actors", [])}
        
        assert "funds" in actors, "funds actor should exist"
        f = actors["funds"]
        assert f["name"] == "Funds", f"Name should be 'Funds', got {f['name']}"
        print(f"PASS: funds - action={f['action']}, direction={f['direction']}, strength={f['strength']}")

    def test_actor_whales(self):
        """Test whales actor data"""
        response = requests.get(f"{BASE_URL}/api/os/actor-radar")
        data = response.json()
        actors = {a["id"]: a for a in data.get("actors", [])}
        
        assert "whales" in actors, "whales actor should exist"
        w = actors["whales"]
        assert w["name"] == "Whales", f"Name should be 'Whales', got {w['name']}"
        print(f"PASS: whales - action={w['action']}, direction={w['direction']}, strength={w['strength']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
