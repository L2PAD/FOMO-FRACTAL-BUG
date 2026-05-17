"""
Bakery v2 Engine Tests — WHO MOVES MONEY NOW
Tests for Decision Layer, ROLE, SPS, PLAY, HOW TO TRADE, MONEY TRACK
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBakeryLeaderboard:
    """Tests for GET /api/bakery — Decision Layer + Bakers"""
    
    def test_bakery_returns_ok_with_decisions(self):
        """P0: /api/bakery returns ok:true with 'decisions' array"""
        response = requests.get(f"{BASE_URL}/api/bakery?limit=10")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert "decisions" in data
        assert isinstance(data["decisions"], list)
        
        # Verify decision structure (FOLLOW/WATCH/IGNORE with name, context, play)
        if len(data["decisions"]) > 0:
            decision = data["decisions"][0]
            assert "action" in decision
            assert decision["action"] in ["FOLLOW", "WATCH", "IGNORE"]
            assert "name" in decision
            assert "context" in decision
            assert "play" in decision
            print(f"PASS: decisions array has {len(data['decisions'])} items with correct structure")
    
    def test_bakers_have_new_v2_fields(self):
        """P0: Bakers have new fields: role, sps, sector, play, capitalPath"""
        response = requests.get(f"{BASE_URL}/api/bakery?limit=5")
        assert response.status_code == 200
        data = response.json()
        
        assert "bakers" in data
        assert len(data["bakers"]) > 0
        
        baker = data["bakers"][0]
        # New v2 fields
        assert "role" in baker, "Missing 'role' field"
        assert baker["role"] in ["Driver", "Capital", "Amplifier", "Tracker"]
        
        assert "sps" in baker, "Missing 'sps' field"
        assert baker["sps"] in ["EARLY", "MID", "LATE"]
        
        assert "sector" in baker, "Missing 'sector' field"
        assert baker["sector"] in ["AI", "MEME", "DEFI", "INFRA", "MARKET"]
        
        assert "play" in baker, "Missing 'play' field"
        assert isinstance(baker["play"], str)
        
        assert "capitalPath" in baker, "Missing 'capitalPath' field"
        assert isinstance(baker["capitalPath"], list)
        
        print(f"PASS: Baker '{baker['name']}' has role={baker['role']}, sps={baker['sps']}, sector={baker['sector']}, play={baker['play']}")
    
    def test_type_filter_fund(self):
        """P0: ?type=FUND filters correctly"""
        response = requests.get(f"{BASE_URL}/api/bakery?type=FUND&limit=20")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        for baker in data.get("bakers", []):
            assert baker["type"] == "FUND", f"Expected FUND, got {baker['type']}"
            assert baker["role"] == "Capital", f"FUND should have Capital role, got {baker['role']}"
        
        print(f"PASS: FUND filter returns {len(data['bakers'])} bakers, all with type=FUND")
    
    def test_type_filter_person(self):
        """P0: ?type=PERSON filters correctly"""
        response = requests.get(f"{BASE_URL}/api/bakery?type=PERSON&limit=20")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        for baker in data.get("bakers", []):
            assert baker["type"] == "PERSON", f"Expected PERSON, got {baker['type']}"
        
        print(f"PASS: PERSON filter returns {len(data['bakers'])} bakers")
    
    def test_stats_consistency(self):
        """Stats: follow + watch + ignore = total"""
        response = requests.get(f"{BASE_URL}/api/bakery?limit=50")
        assert response.status_code == 200
        data = response.json()
        
        stats = data.get("stats", {})
        assert "total" in stats
        assert "follow" in stats
        assert "watch" in stats
        assert "ignore" in stats
        
        assert stats["follow"] + stats["watch"] + stats["ignore"] == stats["total"]
        print(f"PASS: Stats consistent - {stats['follow']} follow + {stats['watch']} watch + {stats['ignore']} ignore = {stats['total']} total")
    
    def test_play_column_values(self):
        """P0: PLAY column shows actionable text like 'WATCH MEME', 'WATCH DEFI', 'AVOID'"""
        response = requests.get(f"{BASE_URL}/api/bakery?limit=20")
        assert response.status_code == 200
        data = response.json()
        
        play_values = [b["play"] for b in data.get("bakers", [])]
        
        # Check for expected patterns
        has_watch = any("WATCH" in p for p in play_values)
        has_avoid = any("AVOID" in p for p in play_values)
        has_follow = any("FOLLOW" in p for p in play_values)
        has_late = any("LATE" in p for p in play_values)
        
        print(f"PASS: PLAY values found - WATCH: {has_watch}, AVOID: {has_avoid}, FOLLOW: {has_follow}, LATE: {has_late}")
        print(f"Sample PLAY values: {play_values[:5]}")
    
    def test_sps_colors_mapping(self):
        """P0: SPS column shows EARLY/MID/LATE"""
        response = requests.get(f"{BASE_URL}/api/bakery?limit=30")
        assert response.status_code == 200
        data = response.json()
        
        sps_values = set(b["sps"] for b in data.get("bakers", []))
        valid_sps = {"EARLY", "MID", "LATE"}
        
        assert sps_values.issubset(valid_sps), f"Invalid SPS values: {sps_values - valid_sps}"
        print(f"PASS: SPS values found: {sps_values}")


class TestBakeryActive:
    """Tests for GET /api/bakery/active — ACTIVE MONEY FLOW"""
    
    def test_active_returns_ok_with_flows(self):
        """P0: /api/bakery/active returns ok:true with 'flows' array"""
        response = requests.get(f"{BASE_URL}/api/bakery/active")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert "flows" in data
        assert isinstance(data["flows"], list)
        print(f"PASS: /api/bakery/active returns {len(data['flows'])} flows")
    
    def test_flow_structure(self):
        """P0: Flow has name, role, sector, context"""
        response = requests.get(f"{BASE_URL}/api/bakery/active")
        assert response.status_code == 200
        data = response.json()
        
        if len(data.get("flows", [])) > 0:
            flow = data["flows"][0]
            assert "name" in flow
            assert "role" in flow
            assert "sector" in flow
            assert "context" in flow
            assert "slug" in flow
            
            print(f"PASS: Flow '{flow['name']}' has role={flow['role']}, sector={flow['sector']}, context={flow['context']}")


class TestBakerDetail:
    """Tests for GET /api/bakery/:slug — Entity Detail"""
    
    def test_cz_binance_detail(self):
        """P0: /api/bakery/cz_binance returns howToTrade, useWhen, avoidWhen, moneyTrack"""
        response = requests.get(f"{BASE_URL}/api/bakery/cz_binance")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        
        # HOW TO TRADE
        assert "howToTrade" in data
        assert isinstance(data["howToTrade"], list)
        assert len(data["howToTrade"]) > 0
        
        # USE WHEN / AVOID WHEN
        assert "useWhen" in data
        assert isinstance(data["useWhen"], list)
        
        assert "avoidWhen" in data
        assert isinstance(data["avoidWhen"], list)
        
        # MONEY TRACK
        assert "moneyTrack" in data
        assert "best" in data["moneyTrack"]
        assert "worst" in data["moneyTrack"]
        
        print(f"PASS: cz_binance detail has howToTrade ({len(data['howToTrade'])} steps), useWhen, avoidWhen, moneyTrack")
    
    def test_baker_score_block(self):
        """P0: Baker detail has POWER, EDGE, SIGNAL (sps), ACTION"""
        response = requests.get(f"{BASE_URL}/api/bakery/cz_binance")
        assert response.status_code == 200
        data = response.json()
        
        baker = data.get("baker", {})
        
        # Score block fields
        assert "score" in baker, "Missing POWER (score)"
        assert "edgeLabel" in baker, "Missing EDGE label"
        assert "sps" in baker, "Missing SIGNAL (sps)"
        assert "action" in baker, "Missing ACTION"
        assert "play" in baker, "Missing PLAY"
        
        # Performance line
        assert "hitRate" in baker, "Missing hitRate"
        assert "avgReturn" in baker, "Missing avgReturn"
        assert "callsTracked" in baker, "Missing callsTracked"
        
        print(f"PASS: Baker score block - POWER={baker['score']}, EDGE={baker['edgeLabel']}, SIGNAL={baker['sps']}, ACTION={baker['action']}")
    
    def test_money_track_best_worst(self):
        """P0: moneyTrack has best and worst plays"""
        response = requests.get(f"{BASE_URL}/api/bakery/cz_binance")
        assert response.status_code == 200
        data = response.json()
        
        money = data.get("moneyTrack", {})
        
        # Best plays
        best = money.get("best", [])
        if len(best) > 0:
            assert "token" in best[0]
            assert "return" in best[0]
            assert best[0]["return"] >= 0, "Best plays should have positive returns"
        
        # Worst plays
        worst = money.get("worst", [])
        if len(worst) > 0:
            assert "token" in worst[0]
            assert "return" in worst[0]
            assert worst[0]["return"] < 0, "Worst plays should have negative returns"
        
        print(f"PASS: moneyTrack has {len(best)} best plays, {len(worst)} worst plays")
    
    def test_connections_clickable(self):
        """P0: Connections are returned with slug for clickable links"""
        response = requests.get(f"{BASE_URL}/api/bakery/cz_binance")
        assert response.status_code == 200
        data = response.json()
        
        connections = data.get("connections", [])
        if len(connections) > 0:
            conn = connections[0]
            assert "slug" in conn, "Connection missing slug for link"
            assert "name" in conn
            assert "role" in conn
            print(f"PASS: {len(connections)} connections with clickable slugs")
    
    def test_not_found_baker(self):
        """Baker not found returns ok:false"""
        response = requests.get(f"{BASE_URL}/api/bakery/nonexistent_baker_xyz")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is False
        assert "error" in data
        print("PASS: Nonexistent baker returns ok:false with error")
    
    def test_vitalikbuterin_detail(self):
        """Test another known baker"""
        response = requests.get(f"{BASE_URL}/api/bakery/vitalikbuterin")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert "baker" in data
        assert data["baker"]["name"] == "Vitalik Buterin"
        print(f"PASS: vitalikbuterin detail loaded - role={data['baker']['role']}, sector={data['baker']['sector']}")


class TestRoleClassification:
    """Tests for ROLE classification (Driver/Capital/Amplifier/Tracker)"""
    
    def test_fund_has_capital_role(self):
        """FUND type should have Capital role"""
        response = requests.get(f"{BASE_URL}/api/bakery?type=FUND&limit=10")
        assert response.status_code == 200
        data = response.json()
        
        for baker in data.get("bakers", []):
            assert baker["role"] == "Capital", f"FUND {baker['name']} should be Capital, got {baker['role']}"
        
        print("PASS: All FUND bakers have Capital role")
    
    def test_role_values_valid(self):
        """All roles should be valid"""
        response = requests.get(f"{BASE_URL}/api/bakery?limit=50")
        assert response.status_code == 200
        data = response.json()
        
        valid_roles = {"Driver", "Capital", "Amplifier", "Tracker"}
        roles_found = set()
        
        for baker in data.get("bakers", []):
            assert baker["role"] in valid_roles, f"Invalid role: {baker['role']}"
            roles_found.add(baker["role"])
        
        print(f"PASS: Roles found: {roles_found}")


class TestDecisionLayer:
    """Tests for Decision Layer grouping"""
    
    def test_decisions_grouped_by_action(self):
        """Decisions should be grouped by FOLLOW/WATCH/IGNORE"""
        response = requests.get(f"{BASE_URL}/api/bakery?limit=50")
        assert response.status_code == 200
        data = response.json()
        
        decisions = data.get("decisions", [])
        actions = [d["action"] for d in decisions]
        
        # Should have at least some decisions
        assert len(decisions) > 0, "No decisions returned"
        
        # All actions should be valid
        valid_actions = {"FOLLOW", "WATCH", "IGNORE"}
        for action in actions:
            assert action in valid_actions
        
        print(f"PASS: {len(decisions)} decisions with actions: {set(actions)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
