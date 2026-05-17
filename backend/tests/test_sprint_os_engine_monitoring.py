"""
Sprint Test: OS Tab + Engine Zones + Monitoring Radar Features
==============================================================
Tests for:
1. /api/os/state - market_pulse, opportunities with expanded fields, alerts
2. /api/os/market-pulse - dedicated endpoint
3. /api/os/opportunities - ranked list with expected_move, timeframe, rank_score
4. /api/engine/monitoring/events - categorized events with timeline
5. /api/engine/context - market_memory, playbook objects
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

class TestOSStateEndpoint:
    """Test /api/os/state with market_pulse and expanded opportunity fields"""
    
    def test_os_state_returns_ok(self):
        """OS state endpoint returns ok=true"""
        r = requests.get(f"{BASE_URL}/api/os/state", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True
        print(f"PASS: /api/os/state returns ok=true")
    
    def test_os_state_has_market_pulse(self):
        """OS state includes market_pulse with pulse, score, drivers"""
        r = requests.get(f"{BASE_URL}/api/os/state", timeout=30)
        data = r.json()
        
        assert "market_pulse" in data, "Missing market_pulse in OS state"
        pulse = data["market_pulse"]
        
        assert "pulse" in pulse, "market_pulse missing 'pulse' field"
        assert "score" in pulse, "market_pulse missing 'score' field"
        assert "drivers" in pulse, "market_pulse missing 'drivers' field"
        
        # Validate pulse level
        valid_levels = ["LOW", "NORMAL", "HIGH", "EXTREME"]
        assert pulse["pulse"] in valid_levels, f"Invalid pulse level: {pulse['pulse']}"
        
        # Score should be 0-100
        assert 0 <= pulse["score"] <= 100, f"Score out of range: {pulse['score']}"
        
        # Drivers should be an array
        assert isinstance(pulse["drivers"], list), "drivers should be an array"
        
        print(f"PASS: market_pulse = {pulse['pulse']}, score = {pulse['score']}, drivers = {pulse['drivers']}")
    
    def test_os_state_has_market_risk(self):
        """OS state includes market_risk"""
        r = requests.get(f"{BASE_URL}/api/os/state", timeout=30)
        data = r.json()
        
        assert "market_risk" in data, "Missing market_risk"
        risk = data["market_risk"]
        print(f"PASS: market_risk present with risk_score={risk.get('risk_score')}, risk_level={risk.get('risk_level')}")
    
    def test_os_state_has_market_state(self):
        """OS state includes market_state"""
        r = requests.get(f"{BASE_URL}/api/os/state", timeout=30)
        data = r.json()
        
        assert "market_state" in data, "Missing market_state"
        print(f"PASS: market_state present")
    
    def test_os_state_has_alerts(self):
        """OS state includes alerts array"""
        r = requests.get(f"{BASE_URL}/api/os/state", timeout=30)
        data = r.json()
        
        assert "alerts" in data, "Missing alerts"
        assert isinstance(data["alerts"], list), "alerts should be an array"
        print(f"PASS: alerts present with {len(data['alerts'])} items")
    
    def test_os_state_opportunities_have_expanded_fields(self):
        """Opportunities have expected_move, timeframe, status fields"""
        r = requests.get(f"{BASE_URL}/api/os/state", timeout=30)
        data = r.json()
        
        assert "opportunities" in data, "Missing opportunities"
        opps = data["opportunities"]
        
        if len(opps) == 0:
            pytest.skip("No opportunities available to test")
        
        opp = opps[0]
        
        # Check expanded fields
        assert "expected_move" in opp, "Missing expected_move field"
        assert "timeframe" in opp, "Missing timeframe field"
        assert "status" in opp, "Missing status field"
        assert "rank_score" in opp, "Missing rank_score field"
        
        # Validate status values
        valid_statuses = ["confirmed", "active", "forming", "weakening", "weak"]
        assert opp["status"] in valid_statuses, f"Invalid status: {opp['status']}"
        
        print(f"PASS: First opportunity - setup={opp['setup']}, status={opp['status']}, expected_move={opp['expected_move']}, timeframe={opp['timeframe']}, rank_score={opp['rank_score']}")


class TestOSMarketPulseEndpoint:
    """Test dedicated /api/os/market-pulse endpoint"""
    
    def test_market_pulse_endpoint_returns_ok(self):
        """Market pulse endpoint returns ok=true"""
        r = requests.get(f"{BASE_URL}/api/os/market-pulse", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True
        print(f"PASS: /api/os/market-pulse returns ok=true")
    
    def test_market_pulse_has_required_fields(self):
        """Market pulse has pulse level, score, drivers"""
        r = requests.get(f"{BASE_URL}/api/os/market-pulse", timeout=30)
        data = r.json()
        
        assert "pulse" in data, "Missing pulse level"
        assert "score" in data, "Missing score"
        assert "drivers" in data, "Missing drivers"
        
        valid_levels = ["LOW", "NORMAL", "HIGH", "EXTREME"]
        assert data["pulse"] in valid_levels, f"Invalid pulse: {data['pulse']}"
        assert 0 <= data["score"] <= 100, f"Score out of range: {data['score']}"
        assert isinstance(data["drivers"], list), "drivers should be array"
        
        print(f"PASS: pulse={data['pulse']}, score={data['score']}, drivers count={len(data['drivers'])}")


class TestOSOpportunitiesEndpoint:
    """Test /api/os/opportunities with ranking"""
    
    def test_opportunities_endpoint_returns_ok(self):
        """Opportunities endpoint returns ok=true"""
        r = requests.get(f"{BASE_URL}/api/os/opportunities", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True
        print(f"PASS: /api/os/opportunities returns ok=true")
    
    def test_opportunities_have_new_fields(self):
        """Each opportunity has expected_move, timeframe, rank_score"""
        r = requests.get(f"{BASE_URL}/api/os/opportunities", timeout=30)
        data = r.json()
        
        opps = data.get("opportunities", [])
        if len(opps) == 0:
            pytest.skip("No opportunities to test")
        
        for i, opp in enumerate(opps):
            assert "expected_move" in opp, f"Opportunity {i} missing expected_move"
            assert "timeframe" in opp, f"Opportunity {i} missing timeframe"
            assert "rank_score" in opp, f"Opportunity {i} missing rank_score"
            assert "status" in opp, f"Opportunity {i} missing status"
            print(f"  Opportunity {i+1}: {opp['setup']} | status={opp['status']} | move={opp['expected_move']} | time={opp['timeframe']} | rank={opp['rank_score']}")
        
        print(f"PASS: All {len(opps)} opportunities have required fields")
    
    def test_opportunities_sorted_by_rank_score(self):
        """Opportunities are sorted by rank_score descending"""
        r = requests.get(f"{BASE_URL}/api/os/opportunities", timeout=30)
        data = r.json()
        
        opps = data.get("opportunities", [])
        if len(opps) < 2:
            pytest.skip("Need at least 2 opportunities to test sorting")
        
        scores = [o["rank_score"] for o in opps]
        assert scores == sorted(scores, reverse=True), f"Not sorted descending: {scores}"
        print(f"PASS: Sorted by rank_score descending: {scores}")


class TestMonitoringEventsEndpoint:
    """Test /api/engine/monitoring/events with categorized events"""
    
    def test_monitoring_events_returns_ok(self):
        """Monitoring events endpoint returns ok=true"""
        r = requests.get(f"{BASE_URL}/api/engine/monitoring/events", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True
        print(f"PASS: /api/engine/monitoring/events returns ok=true")
    
    def test_monitoring_events_has_categories(self):
        """Events are grouped by category: critical, liquidity, actor, setup, flow"""
        r = requests.get(f"{BASE_URL}/api/engine/monitoring/events", timeout=30)
        data = r.json()
        
        assert "events" in data, "Missing events field"
        events = data["events"]
        
        expected_cats = ["critical", "liquidity", "actor", "setup", "flow"]
        for cat in expected_cats:
            assert cat in events, f"Missing category: {cat}"
            assert isinstance(events[cat], list), f"{cat} should be array"
        
        cat_counts = {cat: len(events[cat]) for cat in expected_cats}
        print(f"PASS: Categories present - {cat_counts}")
    
    def test_monitoring_events_has_timeline(self):
        """Response includes timeline array"""
        r = requests.get(f"{BASE_URL}/api/engine/monitoring/events", timeout=30)
        data = r.json()
        
        assert "timeline" in data, "Missing timeline"
        assert isinstance(data["timeline"], list), "timeline should be array"
        print(f"PASS: timeline present with {len(data['timeline'])} items")
    
    def test_monitoring_events_has_total(self):
        """Response includes total count"""
        r = requests.get(f"{BASE_URL}/api/engine/monitoring/events", timeout=30)
        data = r.json()
        
        assert "total" in data, "Missing total"
        assert isinstance(data["total"], int), "total should be int"
        print(f"PASS: total = {data['total']}")
    
    def test_events_have_event_category_and_impact_score(self):
        """Each event has event_category and impact_score fields"""
        r = requests.get(f"{BASE_URL}/api/engine/monitoring/events", timeout=30)
        data = r.json()
        
        events = data.get("events", {})
        all_events = []
        for cat, items in events.items():
            all_events.extend(items)
        
        if len(all_events) == 0:
            pytest.skip("No events to test")
        
        for ev in all_events[:5]:  # Check first 5
            assert "event_category" in ev, f"Event missing event_category: {ev.get('type')}"
            assert "impact_score" in ev, f"Event missing impact_score: {ev.get('type')}"
            
            # Validate impact_score
            valid_impacts = ["HIGH", "MEDIUM", "LOW"]
            assert ev["impact_score"] in valid_impacts, f"Invalid impact_score: {ev['impact_score']}"
        
        print(f"PASS: Events have event_category and impact_score (checked {min(5, len(all_events))} events)")


class TestEngineContextEndpoint:
    """Test /api/engine/context for market_memory and playbook"""
    
    def test_engine_context_returns_ok(self):
        """Engine context returns ok=true"""
        r = requests.get(f"{BASE_URL}/api/engine/context", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True
        print(f"PASS: /api/engine/context returns ok=true")
    
    def test_engine_context_has_market_memory(self):
        """Engine context includes market_memory object"""
        r = requests.get(f"{BASE_URL}/api/engine/context", timeout=30)
        data = r.json()
        
        assert "market_memory" in data, "Missing market_memory"
        memory = data["market_memory"]
        
        # Check expected fields
        expected_fields = ["setup", "sample_size"]
        for field in expected_fields:
            assert field in memory, f"market_memory missing {field}"
        
        print(f"PASS: market_memory present - setup={memory.get('setup')}, sample_size={memory.get('sample_size')}")
    
    def test_engine_context_has_playbook(self):
        """Engine context includes playbook object"""
        r = requests.get(f"{BASE_URL}/api/engine/context", timeout=30)
        data = r.json()
        
        assert "playbook" in data, "Missing playbook"
        playbook = data["playbook"]
        
        # Check expected fields
        expected_fields = ["bias", "confirmation", "invalidation", "targets", "risk_note"]
        for field in expected_fields:
            assert field in playbook, f"playbook missing {field}"
        
        print(f"PASS: playbook present - bias={playbook.get('bias')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
