"""
Test Suite for Prediction OS Stage 5 Sprint A
Live Decision Machine: Repricing Detection, Entry Timing, State Transitions, Market Watcher

Tests:
- GET /api/prediction/run returns Stage 5 fields (repricing, entry_timing, market_stage, transitions)
- Sections: emerging_opportunities, repricing_now, watchlist, avoid_zone populated
- Repricing fields: repricing_state, speed_score, acceleration, stress_signal, volume_confirmation
- Entry timing fields: entry_action, entry_score, chase_risk, miss_risk, urgency
- market_stage computed correctly
- GET /api/prediction/watcher/status returns watcher status with tier counts
- POST /api/prediction/watcher/cycle triggers manual watcher cycle
- GET /api/prediction/alerts returns alert list
- Event classifier: direction_bet, token_launch, generic_crypto, price_threshold
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestPredictionRunEndpoint:
    """Tests for GET /api/prediction/run - main prediction pipeline"""

    def test_prediction_run_returns_200(self):
        """Basic health check - endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=10", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") is True
        print(f"PASS: /api/prediction/run returns 200 with {data.get('classified', 0)} classified markets")

    def test_prediction_run_has_stage5_sections(self):
        """Verify Stage 5 sections exist in response"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=20", timeout=30)
        assert response.status_code == 200
        data = response.json()
        sections = data.get("sections", {})
        
        # Stage 5 sections
        required_sections = [
            "best_opportunities", "emerging_opportunities", "entry_windows_open",
            "new_mispricings", "repricing_now", "watchlist", "late_moves",
            "avoid_zone", "state_changes"
        ]
        for sec in required_sections:
            assert sec in sections, f"Missing section: {sec}"
        print(f"PASS: All 9 Stage 5 sections present: {list(sections.keys())}")

    def test_prediction_run_has_signal_availability_flags(self):
        """Verify exchange/onchain/sentiment availability flags"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=5", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        assert "exchange_available" in data
        assert "onchain_available" in data
        assert "sentiment_available" in data
        
        # BTC and ETH should be available
        assert data["exchange_available"].get("BTC") is True
        assert data["onchain_available"].get("BTC") is True
        assert data["sentiment_available"].get("BTC") is True
        print(f"PASS: Signal availability flags present - Exchange: {data['exchange_available']}")

    def test_case_has_repricing_fields(self):
        """Verify each case has repricing object with Stage 5 fields"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=20", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        # Find a case from any section
        all_cases = []
        for sec_name, sec_cases in data.get("sections", {}).items():
            all_cases.extend(sec_cases)
        
        assert len(all_cases) > 0, "No cases returned"
        
        case = all_cases[0]
        repricing = case.get("repricing", {})
        
        # Required repricing fields
        required_fields = [
            "repricing_state", "speed_score", "acceleration", 
            "stress_signal", "volume_confirmation", "pricing_penalty"
        ]
        for field in required_fields:
            assert field in repricing, f"Missing repricing field: {field}"
        
        # Validate repricing_state is one of expected values
        valid_states = [
            "fresh_mispricing", "early_repricing", "active_repricing",
            "late_repricing", "overheated", "fair_value", "stalled", "panic_move"
        ]
        assert repricing["repricing_state"] in valid_states, f"Invalid repricing_state: {repricing['repricing_state']}"
        
        print(f"PASS: Case has repricing fields - state: {repricing['repricing_state']}, speed: {repricing['speed_score']}")

    def test_case_has_entry_timing_fields(self):
        """Verify each case has entry_timing object with Stage 5 fields"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=20", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        all_cases = []
        for sec_name, sec_cases in data.get("sections", {}).items():
            all_cases.extend(sec_cases)
        
        assert len(all_cases) > 0, "No cases returned"
        
        case = all_cases[0]
        entry = case.get("entry_timing", {})
        
        # Required entry timing fields
        required_fields = [
            "entry_action", "entry_score", "chase_risk", 
            "miss_risk", "urgency", "order_type"
        ]
        for field in required_fields:
            assert field in entry, f"Missing entry_timing field: {field}"
        
        # Validate entry_action is one of expected values
        valid_actions = [
            "enter_now", "enter_limit", "wait_retrace", 
            "wait_confirmation", "too_late", "do_not_enter"
        ]
        assert entry["entry_action"] in valid_actions, f"Invalid entry_action: {entry['entry_action']}"
        
        print(f"PASS: Case has entry_timing fields - action: {entry['entry_action']}, chase_risk: {entry['chase_risk']}")

    def test_case_has_market_stage(self):
        """Verify each case has market_stage field"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=20", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        all_cases = []
        for sec_name, sec_cases in data.get("sections", {}).items():
            all_cases.extend(sec_cases)
        
        assert len(all_cases) > 0, "No cases returned"
        
        case = all_cases[0]
        stage = case.get("market_stage")
        
        valid_stages = [
            "new", "forming", "triggered", "repricing", 
            "crowded", "exhausted", "invalidated"
        ]
        assert stage in valid_stages, f"Invalid market_stage: {stage}"
        
        print(f"PASS: Case has market_stage: {stage}")

    def test_case_has_transitions_field(self):
        """Verify each case has transitions array"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=20", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        all_cases = []
        for sec_name, sec_cases in data.get("sections", {}).items():
            all_cases.extend(sec_cases)
        
        assert len(all_cases) > 0, "No cases returned"
        
        case = all_cases[0]
        transitions = case.get("transitions")
        
        assert transitions is not None, "Missing transitions field"
        assert isinstance(transitions, list), "transitions should be a list"
        
        # If there are transitions, verify structure
        if len(transitions) > 0:
            t = transitions[0]
            assert "field" in t, "Transition missing 'field'"
            assert "priority" in t, "Transition missing 'priority'"
            print(f"PASS: Case has transitions: {len(transitions)} transitions found")
        else:
            print(f"PASS: Case has transitions field (empty list - no state changes)")


class TestEventClassifier:
    """Tests for event classifier - direction_bet, token_launch, generic_crypto, price_threshold"""

    def test_direction_bet_classification(self):
        """Verify direction_bet markets are classified correctly"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=50", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        all_cases = []
        for sec_name, sec_cases in data.get("sections", {}).items():
            all_cases.extend(sec_cases)
        
        direction_bets = [c for c in all_cases if c.get("event_type") == "direction_bet"]
        
        if len(direction_bets) > 0:
            case = direction_bets[0]
            assert case["market_type"] == "quant"
            assert case["comparator"] == "direction"
            print(f"PASS: Found {len(direction_bets)} direction_bet markets - {case['question'][:50]}...")
        else:
            print(f"INFO: No direction_bet markets currently available on Polymarket")

    def test_token_launch_classification(self):
        """Verify token_launch markets are classified correctly"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=50", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        all_cases = []
        for sec_name, sec_cases in data.get("sections", {}).items():
            all_cases.extend(sec_cases)
        
        token_launches = [c for c in all_cases if c.get("event_type") == "token_launch"]
        
        if len(token_launches) > 0:
            case = token_launches[0]
            assert case["market_type"] == "catalyst"
            assert "entities" in case
            print(f"PASS: Found {len(token_launches)} token_launch markets - {case['question'][:50]}...")
        else:
            print(f"INFO: No token_launch markets currently available on Polymarket")

    def test_generic_crypto_classification(self):
        """Verify generic_crypto markets are classified correctly"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=50", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        all_cases = []
        for sec_name, sec_cases in data.get("sections", {}).items():
            all_cases.extend(sec_cases)
        
        generic_crypto = [c for c in all_cases if c.get("event_type") == "generic_crypto"]
        
        if len(generic_crypto) > 0:
            case = generic_crypto[0]
            assert case["market_type"] == "quant"
            print(f"PASS: Found {len(generic_crypto)} generic_crypto markets - {case['question'][:50]}...")
        else:
            print(f"INFO: No generic_crypto markets currently available on Polymarket")

    def test_price_threshold_classification(self):
        """Verify price_threshold markets are classified correctly"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=50", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        all_cases = []
        for sec_name, sec_cases in data.get("sections", {}).items():
            all_cases.extend(sec_cases)
        
        price_thresholds = [c for c in all_cases if c.get("event_type") == "price_threshold"]
        
        if len(price_thresholds) > 0:
            case = price_thresholds[0]
            assert case["market_type"] == "quant"
            assert case.get("threshold") is not None
            assert case.get("comparator") in ("above", "below")
            print(f"PASS: Found {len(price_thresholds)} price_threshold markets - {case['question'][:50]}...")
        else:
            print(f"INFO: No price_threshold markets currently available on Polymarket")


class TestMarketWatcher:
    """Tests for market watcher endpoints"""

    def test_watcher_status_returns_200(self):
        """GET /api/prediction/watcher/status returns watcher status"""
        response = requests.get(f"{BASE_URL}/api/prediction/watcher/status", timeout=10)
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert "running" in data
        assert "cycle_count" in data
        assert "last_cycle_at" in data
        assert "market_tiers" in data
        
        print(f"PASS: Watcher status - running: {data['running']}, cycles: {data['cycle_count']}")

    def test_watcher_cycle_trigger(self):
        """POST /api/prediction/watcher/cycle triggers manual cycle"""
        response = requests.post(f"{BASE_URL}/api/prediction/watcher/cycle", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert "summary" in data
        assert "alerts_count" in data
        assert "cases_count" in data
        
        summary = data.get("summary", {})
        assert "cycle" in summary
        assert "tiers" in summary
        
        print(f"PASS: Watcher cycle triggered - cases: {data['cases_count']}, alerts: {data['alerts_count']}")
        print(f"      Tier distribution: {summary.get('tiers', {})}")


class TestAlerts:
    """Tests for alerts endpoint"""

    def test_alerts_returns_200(self):
        """GET /api/prediction/alerts returns alert list"""
        response = requests.get(f"{BASE_URL}/api/prediction/alerts?limit=20", timeout=10)
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert "count" in data
        assert "alerts" in data
        assert isinstance(data["alerts"], list)
        
        print(f"PASS: Alerts endpoint returns {data['count']} alerts")


class TestRepricingDetector:
    """Tests for repricing detector logic via API"""

    def test_repricing_states_distribution(self):
        """Verify repricing states are being computed"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=30", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        all_cases = []
        for sec_name, sec_cases in data.get("sections", {}).items():
            all_cases.extend(sec_cases)
        
        state_counts = {}
        for case in all_cases:
            state = case.get("repricing", {}).get("repricing_state", "unknown")
            state_counts[state] = state_counts.get(state, 0) + 1
        
        print(f"PASS: Repricing state distribution: {state_counts}")
        assert len(state_counts) > 0, "No repricing states computed"

    def test_repricing_numeric_fields_valid(self):
        """Verify repricing numeric fields are in valid ranges"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=20", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        all_cases = []
        for sec_name, sec_cases in data.get("sections", {}).items():
            all_cases.extend(sec_cases)
        
        for case in all_cases[:5]:
            repr = case.get("repricing", {})
            
            # speed_score should be 0-1
            assert 0 <= repr.get("speed_score", 0) <= 1, f"Invalid speed_score: {repr.get('speed_score')}"
            
            # acceleration should be 0-1
            assert 0 <= repr.get("acceleration", 0) <= 1, f"Invalid acceleration: {repr.get('acceleration')}"
            
            # stress_signal should be 0-1
            assert 0 <= repr.get("stress_signal", 0) <= 1, f"Invalid stress_signal: {repr.get('stress_signal')}"
            
            # volume_confirmation should be 0-1
            assert 0 <= repr.get("volume_confirmation", 0) <= 1, f"Invalid volume_confirmation: {repr.get('volume_confirmation')}"
        
        print(f"PASS: Repricing numeric fields are in valid ranges [0, 1]")


class TestEntryTiming:
    """Tests for entry timing engine logic via API"""

    def test_entry_timing_distribution(self):
        """Verify entry actions are being computed"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=30", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        all_cases = []
        for sec_name, sec_cases in data.get("sections", {}).items():
            all_cases.extend(sec_cases)
        
        action_counts = {}
        for case in all_cases:
            action = case.get("entry_timing", {}).get("entry_action", "unknown")
            action_counts[action] = action_counts.get(action, 0) + 1
        
        print(f"PASS: Entry action distribution: {action_counts}")
        assert len(action_counts) > 0, "No entry actions computed"

    def test_chase_miss_risk_valid(self):
        """Verify chase_risk and miss_risk are in valid ranges"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=20", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        all_cases = []
        for sec_name, sec_cases in data.get("sections", {}).items():
            all_cases.extend(sec_cases)
        
        for case in all_cases[:5]:
            entry = case.get("entry_timing", {})
            
            # chase_risk should be 0-1
            assert 0 <= entry.get("chase_risk", 0) <= 1, f"Invalid chase_risk: {entry.get('chase_risk')}"
            
            # miss_risk should be 0-1
            assert 0 <= entry.get("miss_risk", 0) <= 1, f"Invalid miss_risk: {entry.get('miss_risk')}"
            
            # entry_score should be 0-1
            assert 0 <= entry.get("entry_score", 0) <= 1, f"Invalid entry_score: {entry.get('entry_score')}"
        
        print(f"PASS: Entry timing risk fields are in valid ranges [0, 1]")


class TestMarketStage:
    """Tests for market stage engine logic via API"""

    def test_market_stage_distribution(self):
        """Verify market stages are being computed"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=30", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        all_cases = []
        for sec_name, sec_cases in data.get("sections", {}).items():
            all_cases.extend(sec_cases)
        
        stage_counts = {}
        for case in all_cases:
            stage = case.get("market_stage", "unknown")
            stage_counts[stage] = stage_counts.get(stage, 0) + 1
        
        print(f"PASS: Market stage distribution: {stage_counts}")
        assert len(stage_counts) > 0, "No market stages computed"


class TestSectionPopulation:
    """Tests for section population logic"""

    def test_sections_have_cases(self):
        """Verify at least some sections have cases"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=50", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        sections = data.get("sections", {})
        total_cases = sum(len(cases) for cases in sections.values())
        
        assert total_cases > 0, "No cases in any section"
        
        populated = {k: len(v) for k, v in sections.items() if len(v) > 0}
        print(f"PASS: {total_cases} total cases across sections: {populated}")

    def test_emerging_opportunities_have_fresh_mispricing(self):
        """Verify emerging_opportunities section has fresh_mispricing cases"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=50", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        emerging = data.get("sections", {}).get("emerging_opportunities", [])
        
        if len(emerging) > 0:
            for case in emerging:
                rstate = case.get("repricing", {}).get("repricing_state")
                assert rstate == "fresh_mispricing", f"Expected fresh_mispricing in emerging, got {rstate}"
            print(f"PASS: {len(emerging)} emerging opportunities all have fresh_mispricing state")
        else:
            print(f"INFO: No emerging opportunities currently (depends on market conditions)")

    def test_repricing_now_has_active_repricing(self):
        """Verify repricing_now section has active/early repricing cases"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=50", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        repricing_now = data.get("sections", {}).get("repricing_now", [])
        
        if len(repricing_now) > 0:
            for case in repricing_now:
                rstate = case.get("repricing", {}).get("repricing_state")
                assert rstate in ("active_repricing", "early_repricing"), f"Expected active/early repricing, got {rstate}"
            print(f"PASS: {len(repricing_now)} repricing_now cases have active/early repricing state")
        else:
            print(f"INFO: No repricing_now cases currently (depends on market conditions)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
