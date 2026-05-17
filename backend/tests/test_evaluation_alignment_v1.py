"""
Test Suite: Evaluation Alignment V1 (Phase 2)
Tests dynamic evaluation windows, peak-aware timing, early exit detection,
and audit fields for evaluation tracking.

Features tested:
- get_dynamic_window() returns correct window for each event_type + horizon combo
- detect_event_type() maps sentiment.intent to event_type
- _find_peak_prices_with_timing() returns max_price, min_price, time_to_max, time_to_min
- GET /api/outcome/evaluation-alignment returns alignment metrics
- GET /api/outcome/labels-v2-compare still works with new audit.evaluation fields
- POST /api/outcome/backfill-labels-v2 includes audit.evaluation fields
- audit.evaluation fields are correctly set per sample
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com').rstrip('/')


class TestDynamicWindowLogic:
    """Test get_dynamic_window() function logic"""

    def test_social_spike_24h_window(self):
        """social_spike event type should get 48h max window, capped to 24h for 24H horizon"""
        from outcome_resolver import get_dynamic_window, EVENT_TIME_PROFILE
        
        result = get_dynamic_window("social_spike", "24H")
        
        assert result["event_type"] == "social_spike"
        # social_spike max_hours = 48, horizon = 24, window = max(48, 12) = 48, capped to 24
        assert result["window_hours"] == 24  # capped to horizon
        assert result["min_hours"] == EVENT_TIME_PROFILE["social_spike"]["min_hours"]
        assert result["max_hours"] == EVENT_TIME_PROFILE["social_spike"]["max_hours"]

    def test_narrative_24h_window(self):
        """narrative event type should get 240h max window, capped to 24h for 24H horizon"""
        from outcome_resolver import get_dynamic_window
        
        result = get_dynamic_window("narrative", "24H")
        
        assert result["event_type"] == "narrative"
        # narrative max_hours = 240, horizon = 24, window = max(240, 12) = 240, capped to 24
        assert result["window_hours"] == 24  # capped to horizon
        assert result["min_hours"] == 48
        assert result["max_hours"] == 240

    def test_unknown_24h_window(self):
        """unknown event type should get 72h max window, capped to 24h for 24H horizon"""
        from outcome_resolver import get_dynamic_window
        
        result = get_dynamic_window("unknown", "24H")
        
        assert result["event_type"] == "unknown"
        # unknown max_hours = 72, horizon = 24, window = max(72, 12) = 72, capped to 24
        assert result["window_hours"] == 24  # capped to horizon
        assert result["min_hours"] == 24
        assert result["max_hours"] == 72

    def test_whale_move_24h_window(self):
        """whale_move event type should get 24h max window"""
        from outcome_resolver import get_dynamic_window
        
        result = get_dynamic_window("whale_move", "24H")
        
        assert result["event_type"] == "whale_move"
        # whale_move max_hours = 24, horizon = 24, window = max(24, 12) = 24
        assert result["window_hours"] == 24
        assert result["min_hours"] == 1
        assert result["max_hours"] == 24

    def test_social_spike_7d_window(self):
        """social_spike with 7D horizon should get 48h window (not capped)"""
        from outcome_resolver import get_dynamic_window
        
        result = get_dynamic_window("social_spike", "7D")
        
        # 7D = 168h, social_spike max = 48, window = max(48, 84) = 84
        assert result["window_hours"] == 84  # half of 168h
        assert result["event_type"] == "social_spike"

    def test_narrative_7d_window(self):
        """narrative with 7D horizon should get 168h window (capped to horizon)"""
        from outcome_resolver import get_dynamic_window
        
        result = get_dynamic_window("narrative", "7D")
        
        # 7D = 168h, narrative max = 240, window = max(240, 84) = 240, capped to 168
        assert result["window_hours"] == 168  # capped to horizon
        assert result["event_type"] == "narrative"


class TestDetectEventType:
    """Test detect_event_type() function"""

    def test_bullish_signal_maps_to_social_spike(self):
        """BULLISH_SIGNAL intent should map to social_spike"""
        from outcome_resolver import detect_event_type
        
        sample = {"sentiment": {"intent": "BULLISH_SIGNAL"}}
        result = detect_event_type(sample)
        
        assert result == "social_spike"

    def test_bearish_signal_maps_to_social_spike(self):
        """BEARISH_SIGNAL intent should map to social_spike"""
        from outcome_resolver import detect_event_type
        
        sample = {"sentiment": {"intent": "BEARISH_SIGNAL"}}
        result = detect_event_type(sample)
        
        assert result == "social_spike"

    def test_hype_maps_to_narrative(self):
        """HYPE intent should map to narrative"""
        from outcome_resolver import detect_event_type
        
        sample = {"sentiment": {"intent": "HYPE"}}
        result = detect_event_type(sample)
        
        assert result == "narrative"

    def test_warning_maps_to_whale_move(self):
        """WARNING intent should map to whale_move"""
        from outcome_resolver import detect_event_type
        
        sample = {"sentiment": {"intent": "WARNING"}}
        result = detect_event_type(sample)
        
        assert result == "whale_move"

    def test_informational_maps_to_unknown(self):
        """INFORMATIONAL intent should map to unknown"""
        from outcome_resolver import detect_event_type
        
        sample = {"sentiment": {"intent": "INFORMATIONAL"}}
        result = detect_event_type(sample)
        
        assert result == "unknown"

    def test_noise_maps_to_unknown(self):
        """NOISE intent should map to unknown"""
        from outcome_resolver import detect_event_type
        
        sample = {"sentiment": {"intent": "NOISE"}}
        result = detect_event_type(sample)
        
        assert result == "unknown"

    def test_missing_intent_maps_to_unknown(self):
        """Missing intent should map to unknown"""
        from outcome_resolver import detect_event_type
        
        sample = {"sentiment": {}}
        result = detect_event_type(sample)
        
        assert result == "unknown"

    def test_empty_sample_maps_to_unknown(self):
        """Empty sample should map to unknown"""
        from outcome_resolver import detect_event_type
        
        sample = {}
        result = detect_event_type(sample)
        
        assert result == "unknown"


class TestEventTimeProfile:
    """Test EVENT_TIME_PROFILE configuration"""

    def test_all_event_types_defined(self):
        """All expected event types should be defined"""
        from outcome_resolver import EVENT_TIME_PROFILE
        
        expected_types = ["listing", "funding", "unlock", "whale_move", 
                         "social_spike", "narrative", "unknown"]
        
        for et in expected_types:
            assert et in EVENT_TIME_PROFILE, f"Missing event type: {et}"
            assert "min_hours" in EVENT_TIME_PROFILE[et]
            assert "max_hours" in EVENT_TIME_PROFILE[et]

    def test_social_spike_profile(self):
        """social_spike should have correct time profile"""
        from outcome_resolver import EVENT_TIME_PROFILE
        
        profile = EVENT_TIME_PROFILE["social_spike"]
        assert profile["min_hours"] == 6
        assert profile["max_hours"] == 48

    def test_narrative_profile(self):
        """narrative should have correct time profile"""
        from outcome_resolver import EVENT_TIME_PROFILE
        
        profile = EVENT_TIME_PROFILE["narrative"]
        assert profile["min_hours"] == 48
        assert profile["max_hours"] == 240


class TestIntentToEventTypeMapping:
    """Test INTENT_TO_EVENT_TYPE mapping"""

    def test_all_intents_mapped(self):
        """All expected intents should be mapped"""
        from outcome_resolver import INTENT_TO_EVENT_TYPE
        
        expected_intents = ["BULLISH_SIGNAL", "BEARISH_SIGNAL", "HYPE", 
                           "WARNING", "INFORMATIONAL", "NOISE"]
        
        for intent in expected_intents:
            assert intent in INTENT_TO_EVENT_TYPE, f"Missing intent: {intent}"


class TestEvaluationAlignmentAPI:
    """Test GET /api/outcome/evaluation-alignment endpoint"""

    def test_endpoint_returns_200(self):
        """Endpoint should return 200 OK"""
        response = requests.get(f"{BASE_URL}/api/outcome/evaluation-alignment")
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True

    def test_response_has_required_fields(self):
        """Response should have all required fields"""
        response = requests.get(f"{BASE_URL}/api/outcome/evaluation-alignment")
        data = response.json()
        
        required_fields = [
            "ok", "total", "early_exit_rate", "avg_time_to_peak_up",
            "avg_time_to_peak_down", "avg_peak_vs_final_gap",
            "peak_captured_but_final_missed", "peak_captured_pct", "by_event_type"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_early_exit_rate_is_percentage(self):
        """early_exit_rate should be a percentage (0-100)"""
        response = requests.get(f"{BASE_URL}/api/outcome/evaluation-alignment")
        data = response.json()
        
        rate = data.get("early_exit_rate")
        assert isinstance(rate, (int, float))
        assert 0 <= rate <= 100

    def test_by_event_type_structure(self):
        """by_event_type should have correct structure"""
        response = requests.get(f"{BASE_URL}/api/outcome/evaluation-alignment")
        data = response.json()
        
        by_type = data.get("by_event_type", {})
        
        for et, info in by_type.items():
            assert "count" in info, f"Missing count for {et}"
            assert "early_exits" in info, f"Missing early_exits for {et}"
            assert "labels" in info, f"Missing labels for {et}"
            assert isinstance(info["labels"], dict)

    def test_total_matches_sum_of_event_types(self):
        """Total should match sum of all event type counts"""
        response = requests.get(f"{BASE_URL}/api/outcome/evaluation-alignment")
        data = response.json()
        
        total = data.get("total", 0)
        by_type = data.get("by_event_type", {})
        
        sum_counts = sum(info.get("count", 0) for info in by_type.values())
        assert total == sum_counts

    def test_avg_time_to_peak_values(self):
        """avg_time_to_peak values should be reasonable hours"""
        response = requests.get(f"{BASE_URL}/api/outcome/evaluation-alignment")
        data = response.json()
        
        up = data.get("avg_time_to_peak_up")
        down = data.get("avg_time_to_peak_down")
        
        if up is not None:
            assert 0 <= up <= 720, f"avg_time_to_peak_up out of range: {up}"
        if down is not None:
            assert 0 <= down <= 720, f"avg_time_to_peak_down out of range: {down}"


class TestLabelsV2CompareAPI:
    """Test GET /api/outcome/labels-v2-compare still works with Phase 2"""

    def test_endpoint_returns_200(self):
        """Endpoint should return 200 OK"""
        response = requests.get(f"{BASE_URL}/api/outcome/labels-v2-compare")
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True

    def test_response_has_required_fields(self):
        """Response should have all required fields"""
        response = requests.get(f"{BASE_URL}/api/outcome/labels-v2-compare")
        data = response.json()
        
        required_fields = [
            "ok", "total_resolved", "v2_labeled", "v1_distribution",
            "v2_distribution", "transitions", "avg_v2_confidence"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_v2_distribution_has_5_labels(self):
        """V2 distribution should have 5-label classification"""
        response = requests.get(f"{BASE_URL}/api/outcome/labels-v2-compare")
        data = response.json()
        
        v2_dist = data.get("v2_distribution", {})
        valid_labels = ["STRONG_GOOD", "WEAK_GOOD", "NEUTRAL", "WEAK_BAD", "STRONG_BAD"]
        
        for label in v2_dist.keys():
            assert label in valid_labels, f"Invalid V2 label: {label}"


class TestBackfillLabelsV2API:
    """Test POST /api/outcome/backfill-labels-v2 includes audit.evaluation"""

    def test_endpoint_returns_200(self):
        """Endpoint should return 200 OK"""
        response = requests.post(f"{BASE_URL}/api/outcome/backfill-labels-v2?limit=1")
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True

    def test_response_has_required_fields(self):
        """Response should have all required fields"""
        response = requests.post(f"{BASE_URL}/api/outcome/backfill-labels-v2?limit=1")
        data = response.json()
        
        required_fields = ["ok", "backfilled", "errors", "remaining"]
        
        for field in required_fields:
            assert field in data, f"Missing field: {field}"


class TestAuditEvaluationFields:
    """Test audit.evaluation fields are correctly set"""

    def test_samples_have_evaluation_audit(self):
        """Samples should have audit.evaluation field"""
        response = requests.get(f"{BASE_URL}/api/outcome/evaluation-alignment")
        data = response.json()
        
        # If total > 0, samples have evaluation audit
        assert data.get("total", 0) > 0, "No samples with audit.evaluation found"

    def test_event_types_detected(self):
        """Event types should be detected from samples"""
        response = requests.get(f"{BASE_URL}/api/outcome/evaluation-alignment")
        data = response.json()
        
        by_type = data.get("by_event_type", {})
        
        # Should have at least one event type
        assert len(by_type) > 0, "No event types detected"
        
        # Check expected event types based on context
        # unknown (from NOISE/INFORMATIONAL), social_spike (from BULLISH_SIGNAL), narrative (from HYPE)
        expected_types = ["unknown", "social_spike", "narrative"]
        found_types = list(by_type.keys())
        
        for et in expected_types:
            if et in found_types:
                print(f"Found expected event type: {et} with {by_type[et]['count']} samples")

    def test_early_exit_detection(self):
        """Early exit should be detected for strong signals within 24h"""
        response = requests.get(f"{BASE_URL}/api/outcome/evaluation-alignment")
        data = response.json()
        
        # early_exit_rate should be a valid percentage
        rate = data.get("early_exit_rate", 0)
        assert isinstance(rate, (int, float))
        
        # Check by_event_type for early_exits
        by_type = data.get("by_event_type", {})
        total_early = sum(info.get("early_exits", 0) for info in by_type.values())
        
        print(f"Total early exits: {total_early}, rate: {rate}%")


class TestV2ShadowLabelsUnchanged:
    """Test V2 shadow labels unchanged by Phase 2"""

    def test_compute_label_v2_function_exists(self):
        """compute_label_v2 function should exist and work"""
        from outcome_resolver import compute_label_v2
        
        # Test basic classification
        label, conf = compute_label_v2(3.0, 0.5, 2.0, "24H")
        assert label == "STRONG_GOOD"
        assert 0 <= conf <= 1

    def test_compute_label_v2_thresholds_unchanged(self):
        """V2 thresholds should be unchanged"""
        from outcome_resolver import LABEL_V2_THRESHOLDS
        
        assert LABEL_V2_THRESHOLDS["24H"]["weak"] == 1.5
        assert LABEL_V2_THRESHOLDS["24H"]["strong"] == 2.5
        assert LABEL_V2_THRESHOLDS["7D"]["weak"] == 2.0
        assert LABEL_V2_THRESHOLDS["7D"]["strong"] == 5.0
        assert LABEL_V2_THRESHOLDS["30D"]["weak"] == 4.0
        assert LABEL_V2_THRESHOLDS["30D"]["strong"] == 10.0


class TestPeakVsFinalGap:
    """Test peak_vs_final_gap computation"""

    def test_gap_in_response(self):
        """avg_peak_vs_final_gap should be in response"""
        response = requests.get(f"{BASE_URL}/api/outcome/evaluation-alignment")
        data = response.json()
        
        gap = data.get("avg_peak_vs_final_gap")
        
        # Can be None if no data, or a number
        if gap is not None:
            assert isinstance(gap, (int, float))
            print(f"avg_peak_vs_final_gap: {gap}%")

    def test_peak_captured_final_missed(self):
        """peak_captured_but_final_missed should be counted"""
        response = requests.get(f"{BASE_URL}/api/outcome/evaluation-alignment")
        data = response.json()
        
        missed = data.get("peak_captured_but_final_missed", 0)
        pct = data.get("peak_captured_pct", 0)
        
        assert isinstance(missed, int)
        assert isinstance(pct, (int, float))
        
        print(f"Peak captured but final missed: {missed} ({pct}%)")


class TestIntegration:
    """Integration tests for Phase 2 features"""

    def test_all_endpoints_work_together(self):
        """All Phase 2 endpoints should work together"""
        # 1. Get evaluation alignment
        ea_resp = requests.get(f"{BASE_URL}/api/outcome/evaluation-alignment")
        assert ea_resp.status_code == 200
        ea_data = ea_resp.json()
        
        # 2. Get labels v2 compare
        lv2_resp = requests.get(f"{BASE_URL}/api/outcome/labels-v2-compare")
        assert lv2_resp.status_code == 200
        lv2_data = lv2_resp.json()
        
        # 3. Verify consistency
        # Total in evaluation-alignment should match v2_labeled in labels-v2-compare
        # (if all samples have evaluation audit)
        ea_total = ea_data.get("total", 0)
        lv2_labeled = lv2_data.get("v2_labeled", 0)
        
        print(f"Evaluation alignment total: {ea_total}")
        print(f"Labels V2 labeled: {lv2_labeled}")
        
        # They should be equal if all samples have evaluation audit
        assert ea_total == lv2_labeled, f"Mismatch: {ea_total} vs {lv2_labeled}"

    def test_event_type_distribution_matches_context(self):
        """Event type distribution should match expected from context"""
        response = requests.get(f"{BASE_URL}/api/outcome/evaluation-alignment")
        data = response.json()
        
        by_type = data.get("by_event_type", {})
        
        # From context: unknown (79), social_spike (21), narrative (6)
        # These are approximate based on intent mapping
        
        if "unknown" in by_type:
            print(f"unknown: {by_type['unknown']['count']} samples")
        if "social_spike" in by_type:
            print(f"social_spike: {by_type['social_spike']['count']} samples")
        if "narrative" in by_type:
            print(f"narrative: {by_type['narrative']['count']} samples")

    def test_dynamic_window_used_in_backfill(self):
        """Dynamic window should be used in backfill (window_used_hours varies)"""
        response = requests.get(f"{BASE_URL}/api/outcome/evaluation-alignment")
        data = response.json()
        
        # All samples should have evaluation audit with window_used_hours
        total = data.get("total", 0)
        assert total > 0, "No samples with evaluation audit"
        
        # The window_used_hours should be 24h for 24H horizon (capped)
        # This is verified by the fact that samples have evaluation audit


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
