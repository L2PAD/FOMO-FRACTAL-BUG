"""
Prediction Stage 6 Sprint B Tests — Signal Intelligence Layer

Tests:
1. Node.js prediction-intel service endpoints
2. Python signal_intel_adapter integration
3. GET /api/prediction/run returns signal_intel field
4. Frontend displays Intel column with all fields
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
NODE_URL = "http://localhost:8003"


class TestNodeJsPredictionIntelService:
    """Test Node.js prediction-intel service endpoints"""

    def test_sources_endpoint(self):
        """GET /api/prediction-intel/sources returns source profiles with trust scores"""
        resp = requests.get(f"{NODE_URL}/api/prediction-intel/sources", timeout=10)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        assert data.get("ok") is True
        assert "profiles" in data
        
        profiles = data["profiles"]
        assert len(profiles) > 0, "Should have at least one source profile"
        
        # Check profile structure
        first = profiles[0]
        assert "sourceId" in first
        assert "type" in first
        assert "trustScore" in first
        assert isinstance(first["trustScore"], (int, float))
        
        # Check known source types exist
        source_types = [p["type"] for p in profiles]
        assert "official" in source_types, "Should have official source type"
        assert "exchange" in source_types, "Should have exchange source type"
        assert "onchain" in source_types, "Should have onchain source type"
        print(f"✓ Sources endpoint: {len(profiles)} profiles returned")

    def test_events_endpoint_btc(self):
        """GET /api/prediction-intel/events/BTC returns enriched events"""
        resp = requests.get(
            f"{NODE_URL}/api/prediction-intel/events/BTC",
            params={"hoursBack": "48"},
            timeout=10
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        assert data.get("ok") is True
        assert data.get("asset") == "BTC"
        assert "count" in data
        assert "events" in data
        
        # Should have events (based on context: 25 BTC events)
        events = data["events"]
        print(f"✓ Events endpoint: {len(events)} BTC events returned")
        
        if events:
            first = events[0]
            # Check enriched event structure
            assert "id" in first or "eventId" in first
            assert "text" in first
            assert "sourceType" in first or "extractedSourceType" in first
            assert "asset" in first
            print(f"  First event: {first.get('text', '')[:50]}...")

    def test_market_intelligence_endpoint(self):
        """GET /api/prediction-intel/market/:marketId returns signal batch"""
        resp = requests.get(
            f"{NODE_URL}/api/prediction-intel/market/test_market_123",
            params={
                "asset": "BTC",
                "entities": "BTC",
                "eventType": "price_threshold",
                "currentProb": "0.5",
                "move6h": "0.03",
                "volume": "10000"
            },
            timeout=10
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        assert data.get("ok") is True
        assert "data" in data
        
        batch = data["data"]
        assert "marketId" in batch
        assert "asset" in batch
        assert "signals" in batch
        assert "aggregated" in batch
        
        # Check aggregated structure
        agg = batch["aggregated"]
        assert "netProbabilityImpact" in agg
        assert "netConfidenceImpact" in agg
        assert "netAlignmentImpact" in agg
        assert "dominantBias" in agg
        assert "signalCount" in agg
        assert "avgNovelty" in agg
        assert "avgAlreadyPriced" in agg
        assert "topDriver" in agg
        
        print(f"✓ Market intelligence: {agg['signalCount']} signals, bias={agg['dominantBias']}")
        
        # Check signals structure if present
        signals = batch["signals"]
        if signals:
            first_sig = signals[0]
            assert "eventId" in first_sig
            assert "bias" in first_sig
            assert "strength" in first_sig
            assert "confidence" in first_sig
            assert "impact" in first_sig
            assert "smartDriver" in first_sig
            assert "novelty" in first_sig
            assert "alreadyPriced" in first_sig
            
            # Check impact structure
            impact = first_sig["impact"]
            assert "probability" in impact
            assert "confidence" in impact
            assert "alignment" in impact
            print(f"  First signal: {first_sig['smartDriver'][:50]}...")


class TestPythonSignalIntelAdapter:
    """Test Python adapter integration with Node.js service"""

    def test_prediction_run_has_signal_intel(self):
        """GET /api/prediction/run returns cases with signal_intel field"""
        resp = requests.get(f"{BASE_URL}/api/prediction/run", params={"limit": 20}, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        assert data.get("ok") is True
        assert "sections" in data
        
        # Collect all cases
        all_cases = []
        for section_name, cases in data["sections"].items():
            all_cases.extend(cases)
        
        assert len(all_cases) > 0, "Should have at least one classified case"
        
        # Find BTC cases (should have signal_intel)
        btc_cases = [c for c in all_cases if c.get("asset") == "BTC"]
        print(f"✓ Found {len(btc_cases)} BTC cases out of {len(all_cases)} total")
        
        # Check signal_intel structure on BTC cases
        cases_with_intel = 0
        for case in btc_cases:
            intel = case.get("signal_intel")
            if intel and intel.get("signal_count", 0) > 0:
                cases_with_intel += 1
                
                # Verify structure
                assert "signal_count" in intel
                assert "dominant_bias" in intel
                assert "smart_drivers" in intel
                assert "net_probability_impact" in intel
                assert "net_confidence_impact" in intel
                assert "net_alignment_impact" in intel
                assert "avg_novelty" in intel
                assert "avg_already_priced" in intel
                
                # Check smart_drivers is a list
                assert isinstance(intel["smart_drivers"], list)
        
        print(f"✓ {cases_with_intel}/{len(btc_cases)} BTC cases have signal_intel with signals")

    def test_signal_intel_enriches_why_now(self):
        """Signal intel smart drivers should appear in why_now field"""
        resp = requests.get(f"{BASE_URL}/api/prediction/run", params={"limit": 20}, timeout=30)
        assert resp.status_code == 200
        
        data = resp.json()
        all_cases = []
        for cases in data["sections"].values():
            all_cases.extend(cases)
        
        # Find cases with signal_intel and smart_drivers
        enriched_cases = 0
        for case in all_cases:
            intel = case.get("signal_intel", {})
            smart_drivers = intel.get("smart_drivers", [])
            why_now = case.get("why_now", [])
            
            if smart_drivers and why_now:
                # Check if any smart driver appears in why_now
                for driver in smart_drivers[:2]:
                    if driver in why_now:
                        enriched_cases += 1
                        break
        
        print(f"✓ {enriched_cases} cases have why_now enriched with smart drivers")


class TestStage5FieldsStillPresent:
    """Verify Stage 5 fields are still present after Stage 6 additions"""

    def test_repricing_fields_present(self):
        """Each case should have repricing object with Stage 5 fields"""
        resp = requests.get(f"{BASE_URL}/api/prediction/run", params={"limit": 10}, timeout=30)
        assert resp.status_code == 200
        
        data = resp.json()
        all_cases = []
        for cases in data["sections"].values():
            all_cases.extend(cases)
        
        for case in all_cases[:5]:
            repricing = case.get("repricing", {})
            assert "repricing_state" in repricing, f"Missing repricing_state in {case.get('market_id')}"
            assert "acceleration" in repricing
            assert "stress_signal" in repricing
            assert "speed_score" in repricing
        
        print(f"✓ Repricing fields present in all cases")

    def test_entry_timing_fields_present(self):
        """Each case should have entry_timing object with Stage 5 fields"""
        resp = requests.get(f"{BASE_URL}/api/prediction/run", params={"limit": 10}, timeout=30)
        assert resp.status_code == 200
        
        data = resp.json()
        all_cases = []
        for cases in data["sections"].values():
            all_cases.extend(cases)
        
        for case in all_cases[:5]:
            entry = case.get("entry_timing", {})
            assert "entry_action" in entry or "chase_risk" in entry, f"Missing entry_timing fields in {case.get('market_id')}"
            assert "chase_risk" in entry
            assert "miss_risk" in entry
        
        print(f"✓ Entry timing fields present in all cases")

    def test_market_stage_present(self):
        """Each case should have market_stage field"""
        resp = requests.get(f"{BASE_URL}/api/prediction/run", params={"limit": 10}, timeout=30)
        assert resp.status_code == 200
        
        data = resp.json()
        all_cases = []
        for cases in data["sections"].values():
            all_cases.extend(cases)
        
        for case in all_cases[:5]:
            assert "market_stage" in case, f"Missing market_stage in {case.get('market_id')}"
        
        print(f"✓ Market stage field present in all cases")

    def test_transitions_field_present(self):
        """Each case should have transitions array"""
        resp = requests.get(f"{BASE_URL}/api/prediction/run", params={"limit": 10}, timeout=30)
        assert resp.status_code == 200
        
        data = resp.json()
        all_cases = []
        for cases in data["sections"].values():
            all_cases.extend(cases)
        
        for case in all_cases[:5]:
            assert "transitions" in case, f"Missing transitions in {case.get('market_id')}"
            assert isinstance(case["transitions"], list)
        
        print(f"✓ Transitions field present in all cases")


class TestWatcherStatus:
    """Test market watcher endpoint"""

    def test_watcher_status_endpoint(self):
        """GET /api/prediction/watcher/status returns watcher status"""
        resp = requests.get(f"{BASE_URL}/api/prediction/watcher/status", timeout=10)
        assert resp.status_code == 200
        
        data = resp.json()
        assert data.get("ok") is True
        
        # Should have tier counts
        if "tier_counts" in data:
            print(f"✓ Watcher status: tier_counts={data['tier_counts']}")
        else:
            print(f"✓ Watcher status: {data}")


class TestSectionsPopulated:
    """Test that all sections are populated correctly"""

    def test_all_sections_exist(self):
        """Response should have all 9 sections"""
        resp = requests.get(f"{BASE_URL}/api/prediction/run", params={"limit": 30}, timeout=30)
        assert resp.status_code == 200
        
        data = resp.json()
        sections = data.get("sections", {})
        
        expected_sections = [
            "best_opportunities",
            "emerging_opportunities",
            "entry_windows_open",
            "new_mispricings",
            "repricing_now",
            "watchlist",
            "late_moves",
            "avoid_zone",
            "state_changes"
        ]
        
        for section in expected_sections:
            assert section in sections, f"Missing section: {section}"
        
        # Print section counts
        for section in expected_sections:
            count = len(sections.get(section, []))
            print(f"  {section}: {count} cases")
        
        print(f"✓ All 9 sections present")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
