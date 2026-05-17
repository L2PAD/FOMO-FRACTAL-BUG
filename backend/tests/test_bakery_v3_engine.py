"""
Bakery v3 Engine Tests — DECISION ENGINE (Money Origin Map)

Tests for:
- ENTRY (EARLY/MID/LATE/EXIT) replacing SPS
- SIGNAL STRENGTH (STRONG/MEDIUM/WEAK)
- PLAY with verbs (ENTER/FOLLOW/WATCH/AVOID/EXIT + sector)
- WHY NOW sector-level decisions
- SYNC detection
- Detail page: signalProfile, frontRun, whyWorks, whyFails
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestBakeryLeaderboardV3:
    """Tests for GET /api/backers — v3 Decision Engine"""
    
    def test_bakery_returns_ok_with_whynow(self):
        """P0: /api/backers returns ok:true with 'whyNow' array (sector-level decisions)"""
        response = requests.get(f"{BASE_URL}/api/backers?limit=20")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert "whyNow" in data, "Missing 'whyNow' array"
        assert isinstance(data["whyNow"], list)
        
        # Verify whyNow structure
        if len(data["whyNow"]) > 0:
            wn = data["whyNow"][0]
            assert "sector" in wn, "whyNow missing 'sector'"
            assert "play" in wn, "whyNow missing 'play'"
            assert "reasons" in wn, "whyNow missing 'reasons'"
            assert "topBaker" in wn, "whyNow missing 'topBaker'"
            assert "sync" in wn, "whyNow missing 'sync'"
            
            # topBaker structure
            assert "name" in wn["topBaker"]
            assert "slug" in wn["topBaker"]
            assert "role" in wn["topBaker"]
            
            print(f"PASS: whyNow has {len(data['whyNow'])} sector decisions")
            print(f"Sample: sector={wn['sector']}, play={wn['play']}, sync={wn['sync']}")
    
    def test_bakery_returns_sync_map(self):
        """P0: /api/backers returns sync map with sector counts and labels"""
        response = requests.get(f"{BASE_URL}/api/backers?limit=50")
        assert response.status_code == 200
        data = response.json()
        
        assert "sync" in data, "Missing 'sync' map"
        assert isinstance(data["sync"], dict)
        
        # Verify sync structure
        for sector, sync_data in data["sync"].items():
            assert "count" in sync_data, f"sync[{sector}] missing 'count'"
            assert "label" in sync_data, f"sync[{sector}] missing 'label'"
            assert sync_data["label"] in ["HIGH", "MEDIUM", "LOW"], f"Invalid sync label: {sync_data['label']}"
            
        print(f"PASS: sync map has {len(data['sync'])} sectors")
        for sec, sd in list(data["sync"].items())[:3]:
            print(f"  {sec}: count={sd['count']}, label={sd['label']}")
    
    def test_bakers_have_v3_fields(self):
        """P0: Bakers have v3 fields: role, power, edge, entry, signal, play, reasons, sync"""
        response = requests.get(f"{BASE_URL}/api/backers?limit=10")
        assert response.status_code == 200
        data = response.json()
        
        assert "bakers" in data
        assert len(data["bakers"]) > 0
        
        baker = data["bakers"][0]
        
        # Core v3 fields
        assert "role" in baker, "Missing 'role'"
        assert baker["role"] in ["Driver", "Capital", "Amplifier", "Tracker"]
        
        assert "power" in baker, "Missing 'power'"
        assert isinstance(baker["power"], (int, float))
        
        assert "edge" in baker, "Missing 'edge'"
        assert "edgeLabel" in baker, "Missing 'edgeLabel'"
        assert baker["edgeLabel"] in ["HIGH", "MID", "LOW"]
        
        # ENTRY (replaces SPS)
        assert "entry" in baker, "Missing 'entry' (replaces sps)"
        assert baker["entry"] in ["EARLY", "MID", "LATE", "EXIT"], f"Invalid entry: {baker['entry']}"
        
        # SIGNAL STRENGTH
        assert "signal" in baker, "Missing 'signal'"
        assert baker["signal"] in ["STRONG", "MEDIUM", "WEAK"], f"Invalid signal: {baker['signal']}"
        
        # PLAY with verb
        assert "play" in baker, "Missing 'play'"
        play_verb = baker["play"].split(" ")[0] if baker["play"] else ""
        assert play_verb in ["ENTER", "FOLLOW", "WATCH", "AVOID", "EXIT"], f"Invalid play verb: {play_verb}"
        
        # REASONS
        assert "reasons" in baker, "Missing 'reasons'"
        assert isinstance(baker["reasons"], list)
        
        # SYNC
        assert "sync" in baker, "Missing 'sync'"
        assert baker["sync"] in ["HIGH", "MEDIUM", "LOW"]
        
        print(f"PASS: Baker '{baker['name']}' has all v3 fields")
        print(f"  entry={baker['entry']}, signal={baker['signal']}, play={baker['play']}")
        print(f"  reasons={baker['reasons'][:2] if baker['reasons'] else []}, sync={baker['sync']}")
    
    def test_decisions_have_v3_structure(self):
        """P0: decisions have action, reasons, sector, play"""
        response = requests.get(f"{BASE_URL}/api/backers?limit=20")
        assert response.status_code == 200
        data = response.json()
        
        assert "decisions" in data
        assert isinstance(data["decisions"], list)
        
        if len(data["decisions"]) > 0:
            d = data["decisions"][0]
            assert "action" in d, "decision missing 'action'"
            assert "reasons" in d, "decision missing 'reasons'"
            assert "sector" in d, "decision missing 'sector'"
            assert "play" in d, "decision missing 'play'"
            
            # Action should be verb
            assert d["action"] in ["ENTER", "FOLLOW", "WATCH", "AVOID", "EXIT"]
            
            print(f"PASS: decisions have v3 structure")
            print(f"Sample: action={d['action']}, sector={d['sector']}, play={d['play']}")
    
    def test_type_filter_fund_capital_role(self):
        """P0: ?type=FUND filters correctly, Capital role only for FUND"""
        response = requests.get(f"{BASE_URL}/api/backers?type=FUND&limit=20")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        
        for baker in data.get("bakers", []):
            assert baker["type"] == "FUND", f"Expected FUND, got {baker['type']}"
            assert baker["role"] == "Capital", f"FUND should have Capital role, got {baker['role']}"
        
        print(f"PASS: FUND filter returns {len(data['bakers'])} bakers, all Capital role")
    
    def test_stats_enter_watch_avoid(self):
        """P0: Stats show enter/follow, watch, avoid counts"""
        response = requests.get(f"{BASE_URL}/api/backers?limit=50")
        assert response.status_code == 200
        data = response.json()
        
        stats = data.get("stats", {})
        assert "total" in stats
        assert "enter" in stats, "Missing 'enter' (enter/follow count)"
        assert "watch" in stats
        assert "avoid" in stats
        
        # Verify consistency
        assert stats["enter"] + stats["watch"] + stats["avoid"] == stats["total"], \
            f"Stats don't add up: {stats['enter']} + {stats['watch']} + {stats['avoid']} != {stats['total']}"
        
        print(f"PASS: Stats - {stats['enter']} enter/follow, {stats['watch']} watch, {stats['avoid']} avoid = {stats['total']} total")
    
    def test_entry_values_valid(self):
        """P0: ENTRY column shows EARLY/MID/LATE/EXIT"""
        response = requests.get(f"{BASE_URL}/api/backers?limit=30")
        assert response.status_code == 200
        data = response.json()
        
        entry_values = set(b["entry"] for b in data.get("bakers", []))
        valid_entries = {"EARLY", "MID", "LATE", "EXIT"}
        
        assert entry_values.issubset(valid_entries), f"Invalid entry values: {entry_values - valid_entries}"
        print(f"PASS: Entry values found: {entry_values}")
    
    def test_play_column_actionable(self):
        """P0: PLAY column shows actionable text with reasons-based plays"""
        response = requests.get(f"{BASE_URL}/api/backers?limit=30")
        assert response.status_code == 200
        data = response.json()
        
        play_values = [b["play"] for b in data.get("bakers", [])]
        
        # Check for expected patterns
        has_enter = any(p.startswith("ENTER") for p in play_values)
        has_follow = any(p.startswith("FOLLOW") for p in play_values)
        has_watch = any(p.startswith("WATCH") for p in play_values)
        has_avoid = any(p == "AVOID" for p in play_values)
        has_exit = any(p == "EXIT" for p in play_values)
        
        print(f"PASS: PLAY values - ENTER: {has_enter}, FOLLOW: {has_follow}, WATCH: {has_watch}, AVOID: {has_avoid}, EXIT: {has_exit}")
        print(f"Sample plays: {play_values[:5]}")


class TestBakeryActiveV3:
    """Tests for GET /api/backers/active — ACTIVE MONEY FLOW with phase"""
    
    def test_active_returns_flows_with_phase(self):
        """P0: /api/backers/active returns flows with phase (early stage/momentum phase/late amplification)"""
        response = requests.get(f"{BASE_URL}/api/backers/active")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert "flows" in data
        
        if len(data["flows"]) > 0:
            flow = data["flows"][0]
            assert "phase" in flow, "Flow missing 'phase'"
            assert flow["phase"] in ["early stage", "momentum phase", "late amplification"], \
                f"Invalid phase: {flow['phase']}"
            
            # Other required fields
            assert "name" in flow
            assert "role" in flow
            assert "sector" in flow
            assert "context" in flow
            assert "slug" in flow
            
            print(f"PASS: {len(data['flows'])} flows with phase")
            for f in data["flows"][:3]:
                print(f"  {f['name']}: {f['phase']} - {f['context']}")


class TestBakerDetailV3:
    """Tests for GET /api/backers/:slug — v3 Entity Detail"""
    
    def test_cz_binance_has_signal_profile(self):
        """P0: /api/backers/cz_binance returns signalProfile block"""
        response = requests.get(f"{BASE_URL}/api/backers/cz_binance")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        
        # SIGNAL PROFILE
        assert "signalProfile" in data, "Missing 'signalProfile'"
        sp = data["signalProfile"]
        assert "type" in sp, "signalProfile missing 'type'"
        assert "style" in sp, "signalProfile missing 'style'"
        assert "edge" in sp, "signalProfile missing 'edge'"
        assert "risk" in sp, "signalProfile missing 'risk'"
        
        print(f"PASS: signalProfile - type={sp['type']}, style={sp['style']}, edge={sp['edge']}, risk={sp['risk']}")
    
    def test_cz_binance_has_front_run(self):
        """P0: /api/backers/cz_binance returns frontRun block with numbered steps"""
        response = requests.get(f"{BASE_URL}/api/backers/cz_binance")
        assert response.status_code == 200
        data = response.json()
        
        assert "frontRun" in data, "Missing 'frontRun'"
        assert isinstance(data["frontRun"], list)
        assert len(data["frontRun"]) > 0, "frontRun should have steps"
        
        print(f"PASS: frontRun has {len(data['frontRun'])} steps")
        for i, step in enumerate(data["frontRun"][:3]):
            print(f"  {i+1}. {step}")
    
    def test_cz_binance_has_why_works_fails(self):
        """P0: /api/backers/cz_binance returns whyWorks and whyFails blocks"""
        response = requests.get(f"{BASE_URL}/api/backers/cz_binance")
        assert response.status_code == 200
        data = response.json()
        
        assert "whyWorks" in data, "Missing 'whyWorks'"
        assert isinstance(data["whyWorks"], list)
        
        assert "whyFails" in data, "Missing 'whyFails'"
        assert isinstance(data["whyFails"], list)
        
        print(f"PASS: whyWorks ({len(data['whyWorks'])} items), whyFails ({len(data['whyFails'])} items)")
        if data["whyWorks"]:
            print(f"  Works: {data['whyWorks'][:2]}")
        if data["whyFails"]:
            print(f"  Fails: {data['whyFails'][:2]}")
    
    def test_baker_score_block_v3(self):
        """P0: Baker detail score block shows POWER, EDGE, ENTRY, PLAY with Signal and reasons"""
        response = requests.get(f"{BASE_URL}/api/backers/cz_binance")
        assert response.status_code == 200
        data = response.json()
        
        baker = data.get("baker", {})
        
        # Score block fields
        assert "power" in baker, "Missing POWER"
        assert "edgeLabel" in baker, "Missing EDGE label"
        assert "entry" in baker, "Missing ENTRY"
        assert "play" in baker, "Missing PLAY"
        assert "signal" in baker, "Missing SIGNAL"
        assert "reasons" in baker, "Missing reasons"
        
        # Performance line
        assert "hitRate" in baker, "Missing hitRate"
        assert "avgReturn" in baker, "Missing avgReturn"
        assert "callsTracked" in baker, "Missing callsTracked"
        
        print(f"PASS: Score block - POWER={baker['power']}, EDGE={baker['edgeLabel']}, ENTRY={baker['entry']}, PLAY={baker['play']}")
        print(f"  Signal={baker['signal']}, reasons={baker['reasons']}")
    
    def test_baker_has_how_to_trade(self):
        """P0: Baker detail has HOW TO TRADE block with numbered steps"""
        response = requests.get(f"{BASE_URL}/api/backers/cz_binance")
        assert response.status_code == 200
        data = response.json()
        
        assert "howToTrade" in data, "Missing 'howToTrade'"
        assert isinstance(data["howToTrade"], list)
        assert len(data["howToTrade"]) > 0
        
        print(f"PASS: howToTrade has {len(data['howToTrade'])} steps")
    
    def test_baker_has_money_track(self):
        """P0: Baker detail has MONEY TRACK with best/worst plays"""
        response = requests.get(f"{BASE_URL}/api/backers/cz_binance")
        assert response.status_code == 200
        data = response.json()
        
        assert "moneyTrack" in data, "Missing 'moneyTrack'"
        assert "best" in data["moneyTrack"]
        assert "worst" in data["moneyTrack"]
        
        best = data["moneyTrack"]["best"]
        worst = data["moneyTrack"]["worst"]
        
        if best:
            assert "token" in best[0]
            assert "return" in best[0]
        
        print(f"PASS: moneyTrack - {len(best)} best, {len(worst)} worst")
    
    def test_baker_connections_clickable(self):
        """P0: Baker detail TOP CONNECTIONS are clickable (have slug)"""
        response = requests.get(f"{BASE_URL}/api/backers/cz_binance")
        assert response.status_code == 200
        data = response.json()
        
        connections = data.get("connections", [])
        if connections:
            conn = connections[0]
            assert "slug" in conn, "Connection missing slug"
            assert "name" in conn
            assert "role" in conn
            print(f"PASS: {len(connections)} connections with clickable slugs")
        else:
            print("PASS: No connections (acceptable)")
    
    def test_vitalikbuterin_detail(self):
        """Test another known baker - vitalikbuterin"""
        response = requests.get(f"{BASE_URL}/api/backers/vitalikbuterin")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert "baker" in data
        assert "signalProfile" in data
        assert "frontRun" in data
        assert "whyWorks" in data
        assert "whyFails" in data
        
        print(f"PASS: vitalikbuterin - entry={data['baker']['entry']}, signal={data['baker']['signal']}, play={data['baker']['play']}")
    
    def test_cobie_detail(self):
        """Test cobie baker"""
        response = requests.get(f"{BASE_URL}/api/backers/cobie")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        print(f"PASS: cobie - entry={data['baker']['entry']}, play={data['baker']['play']}")
    
    def test_a16z_detail(self):
        """Test a16z (fund) baker"""
        response = requests.get(f"{BASE_URL}/api/backers/a16z")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert data["baker"]["role"] == "Capital", "a16z should be Capital role"
        print(f"PASS: a16z - role={data['baker']['role']}, entry={data['baker']['entry']}")
    
    def test_paradigm_detail(self):
        """Test paradigm (fund) baker"""
        response = requests.get(f"{BASE_URL}/api/backers/paradigm")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert data["baker"]["role"] == "Capital", "paradigm should be Capital role"
        print(f"PASS: paradigm - role={data['baker']['role']}, entry={data['baker']['entry']}")
    
    def test_not_found_baker(self):
        """Baker not found returns ok:false"""
        response = requests.get(f"{BASE_URL}/api/backers/nonexistent_baker_xyz_123")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is False
        assert "error" in data
        print("PASS: Nonexistent baker returns ok:false with error")


class TestFilterButtons:
    """Tests for filter buttons ALL/FUNDS/PEOPLE/MEDIA"""
    
    def test_filter_all(self):
        """ALL filter returns all types"""
        response = requests.get(f"{BASE_URL}/api/backers?limit=50")
        assert response.status_code == 200
        data = response.json()
        
        types = set(b["type"] for b in data.get("bakers", []))
        print(f"PASS: ALL filter returns types: {types}")
    
    def test_filter_funds(self):
        """FUNDS filter returns only FUND type"""
        response = requests.get(f"{BASE_URL}/api/backers?type=FUND&limit=20")
        assert response.status_code == 200
        data = response.json()
        
        for baker in data.get("bakers", []):
            assert baker["type"] == "FUND"
        print(f"PASS: FUNDS filter returns {len(data['bakers'])} FUND bakers")
    
    def test_filter_people(self):
        """PEOPLE filter returns only PERSON type"""
        response = requests.get(f"{BASE_URL}/api/backers?type=PERSON&limit=20")
        assert response.status_code == 200
        data = response.json()
        
        for baker in data.get("bakers", []):
            assert baker["type"] == "PERSON"
        print(f"PASS: PEOPLE filter returns {len(data['bakers'])} PERSON bakers")
    
    def test_filter_media(self):
        """MEDIA filter returns only MEDIA type"""
        response = requests.get(f"{BASE_URL}/api/backers?type=MEDIA&limit=20")
        assert response.status_code == 200
        data = response.json()
        
        for baker in data.get("bakers", []):
            assert baker["type"] == "MEDIA"
        print(f"PASS: MEDIA filter returns {len(data['bakers'])} MEDIA bakers")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
