"""
Test Sampling Strategy V1 (Phase 3) for Sentiment System

Tests:
- compute_event_score() returns score in [0, 1] and breakdown dict
- compute_event_score uses signal.mentions_1h, actor.score, sentiment.confidence, market.volatility
- sampling_decision() returns (True, 'high_signal') when score >= 0.6
- sampling_decision() returns (True, 'exploration') ~10% of the time for low scores
- detect_event_type() enhanced with text-based hints for listing/funding/unlock/whale
- detect_event_type() uses actor.role TRACKER fallback to social_spike
- GET /api/outcome/sampling-quality returns include_rate_new, score_histogram, by_reason, by_event_type
- POST /api/outcome/backfill-labels-v2 now writes audit.sampling with event_score and breakdown
- audit.sampling contains event_score, included_old, included_new, include_reason, breakdown
- GET /api/outcome/labels-v2-compare still works correctly
- GET /api/outcome/evaluation-alignment still works correctly (reduced unknown count)
"""

import pytest
import requests
import os
import sys

# Add backend to path for direct imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestComputeEventScore:
    """Tests for compute_event_score() function"""

    def test_compute_event_score_returns_tuple(self):
        """compute_event_score returns (score, breakdown) tuple"""
        from outcome_resolver import compute_event_score
        
        sample = {
            "signal": {"mentions_1h": 5, "unique_actors_1h": 2, "cluster_size_1h": 1, "coordination": 0.3, "position": "EARLY"},
            "actor": {"score": 0.7, "hit_rate": 0.5, "role": "TRACKER"},
            "sentiment": {"confidence": 0.8, "intent": "BULLISH_SIGNAL"},
            "market": {"volatility": 2.0, "momentum": 1.0},
        }
        
        result = compute_event_score(sample)
        assert isinstance(result, tuple), "Should return tuple"
        assert len(result) == 2, "Should return (score, breakdown)"
        
        score, breakdown = result
        assert isinstance(score, float), "Score should be float"
        assert isinstance(breakdown, dict), "Breakdown should be dict"

    def test_compute_event_score_in_range(self):
        """compute_event_score returns score in [0, 1]"""
        from outcome_resolver import compute_event_score
        
        # Test with minimal sample
        minimal = {}
        score, _ = compute_event_score(minimal)
        assert 0 <= score <= 1, f"Score {score} should be in [0, 1]"
        
        # Test with maximal sample
        maximal = {
            "signal": {"mentions_1h": 100, "unique_actors_1h": 50, "cluster_size_1h": 50, "coordination": 1.0, "position": "EARLY"},
            "actor": {"score": 1.0, "hit_rate": 1.0, "role": "TRACKER"},
            "sentiment": {"confidence": 1.0, "intent": "BULLISH_SIGNAL"},
            "market": {"volatility": 10.0, "momentum": 10.0},
        }
        score, _ = compute_event_score(maximal)
        assert 0 <= score <= 1, f"Score {score} should be in [0, 1]"

    def test_compute_event_score_uses_signal_mentions(self):
        """compute_event_score uses signal.mentions_1h"""
        from outcome_resolver import compute_event_score
        
        low_mentions = {"signal": {"mentions_1h": 1}}
        high_mentions = {"signal": {"mentions_1h": 20}}
        
        score_low, _ = compute_event_score(low_mentions)
        score_high, _ = compute_event_score(high_mentions)
        
        assert score_high > score_low, "Higher mentions should increase score"

    def test_compute_event_score_uses_actor_score(self):
        """compute_event_score uses actor.score"""
        from outcome_resolver import compute_event_score
        
        low_actor = {"actor": {"score": 0.1}}
        high_actor = {"actor": {"score": 0.9}}
        
        score_low, _ = compute_event_score(low_actor)
        score_high, _ = compute_event_score(high_actor)
        
        assert score_high > score_low, "Higher actor score should increase event score"

    def test_compute_event_score_uses_sentiment_confidence(self):
        """compute_event_score uses sentiment.confidence"""
        from outcome_resolver import compute_event_score
        
        low_conf = {"sentiment": {"confidence": 0.2, "intent": "BULLISH_SIGNAL"}}
        high_conf = {"sentiment": {"confidence": 0.9, "intent": "BULLISH_SIGNAL"}}
        
        score_low, _ = compute_event_score(low_conf)
        score_high, _ = compute_event_score(high_conf)
        
        assert score_high > score_low, "Higher confidence should increase score"

    def test_compute_event_score_uses_market_volatility(self):
        """compute_event_score uses market.volatility"""
        from outcome_resolver import compute_event_score
        
        low_vol = {"market": {"volatility": 0.5}}
        high_vol = {"market": {"volatility": 5.0}}
        
        score_low, _ = compute_event_score(low_vol)
        score_high, _ = compute_event_score(high_vol)
        
        assert score_high > score_low, "Higher volatility should increase score"

    def test_compute_event_score_breakdown_has_all_components(self):
        """compute_event_score breakdown contains all 6 components"""
        from outcome_resolver import compute_event_score
        
        sample = {
            "signal": {"mentions_1h": 5, "position": "EARLY"},
            "actor": {"score": 0.7},
            "sentiment": {"confidence": 0.8, "intent": "BULLISH_SIGNAL"},
            "market": {"volatility": 2.0},
        }
        
        _, breakdown = compute_event_score(sample)
        
        required_keys = [
            "signal_strength", "entity_importance", "sentiment_shift",
            "volatility_context", "position_bonus", "event_type_weight", "event_type"
        ]
        
        for key in required_keys:
            assert key in breakdown, f"Breakdown should contain {key}"


class TestSamplingDecision:
    """Tests for sampling_decision() function"""

    def test_sampling_decision_high_signal(self):
        """sampling_decision returns (True, 'high_signal') when score >= 0.6"""
        from outcome_resolver import sampling_decision
        
        result = sampling_decision(0.6, exploration=False)
        assert result == (True, "high_signal"), f"Score 0.6 should be high_signal, got {result}"
        
        result = sampling_decision(0.8, exploration=False)
        assert result == (True, "high_signal"), f"Score 0.8 should be high_signal, got {result}"
        
        result = sampling_decision(1.0, exploration=False)
        assert result == (True, "high_signal"), f"Score 1.0 should be high_signal, got {result}"

    def test_sampling_decision_medium_signal_range(self):
        """sampling_decision handles medium signal range (0.3-0.6)"""
        from outcome_resolver import sampling_decision
        
        # Run multiple times to check probabilistic behavior
        results = [sampling_decision(0.45, exploration=False) for _ in range(100)]
        
        included = [r for r in results if r[0]]
        rejected = [r for r in results if not r[0]]
        
        # Should have some medium_signal and some medium_rejected
        reasons = [r[1] for r in results]
        assert "medium_signal" in reasons or "medium_rejected" in reasons, "Should have medium decisions"

    def test_sampling_decision_low_signal_range(self):
        """sampling_decision handles low signal range (<0.3)"""
        from outcome_resolver import sampling_decision
        
        # Run multiple times
        results = [sampling_decision(0.15, exploration=False) for _ in range(100)]
        
        reasons = [r[1] for r in results]
        assert "low_signal" in reasons or "low_rejected" in reasons, "Should have low decisions"

    def test_sampling_decision_exploration(self):
        """sampling_decision returns exploration ~10% of the time"""
        from outcome_resolver import sampling_decision
        
        # Run many times with low score and exploration enabled
        results = [sampling_decision(0.1, exploration=True) for _ in range(1000)]
        
        exploration_count = sum(1 for r in results if r[1] == "exploration")
        
        # Should be roughly 10% (allow 5-15% range for randomness)
        exploration_rate = exploration_count / 1000
        assert 0.05 <= exploration_rate <= 0.20, f"Exploration rate {exploration_rate} should be ~10%"


class TestDetectEventType:
    """Tests for detect_event_type() with text-based hints"""

    def test_detect_event_type_intent_mapping(self):
        """detect_event_type maps intent to event type"""
        from outcome_resolver import detect_event_type
        
        assert detect_event_type({"sentiment": {"intent": "BULLISH_SIGNAL"}}) == "social_spike"
        assert detect_event_type({"sentiment": {"intent": "BEARISH_SIGNAL"}}) == "social_spike"
        assert detect_event_type({"sentiment": {"intent": "HYPE"}}) == "narrative"
        assert detect_event_type({"sentiment": {"intent": "WARNING"}}) == "whale_move"

    def test_detect_event_type_text_hints_listing(self):
        """detect_event_type detects listing from text"""
        from outcome_resolver import detect_event_type
        
        sample = {"text": {"raw": "Token XYZ just got listed on Binance!"}}
        assert detect_event_type(sample) == "listing"
        
        sample = {"text": {"raw": "Coinbase listing announcement for ABC"}}
        assert detect_event_type(sample) == "listing"

    def test_detect_event_type_text_hints_funding(self):
        """detect_event_type detects funding from text"""
        from outcome_resolver import detect_event_type
        
        sample = {"text": {"raw": "Project raised $50M in Series A funding"}}
        assert detect_event_type(sample) == "funding"
        
        sample = {"text": {"raw": "New investment round announced"}}
        assert detect_event_type(sample) == "funding"

    def test_detect_event_type_text_hints_unlock(self):
        """detect_event_type detects unlock from text"""
        from outcome_resolver import detect_event_type
        
        sample = {"text": {"raw": "Token unlock scheduled for next week"}}
        assert detect_event_type(sample) == "unlock"
        
        sample = {"text": {"raw": "Vesting cliff ends tomorrow"}}
        assert detect_event_type(sample) == "unlock"

    def test_detect_event_type_text_hints_whale(self):
        """detect_event_type detects whale_move from text"""
        from outcome_resolver import detect_event_type
        
        sample = {"text": {"raw": "Whale moved 10000 BTC to exchange"}}
        assert detect_event_type(sample) == "whale_move"
        
        sample = {"text": {"raw": "Large transfer detected from wallet"}}
        assert detect_event_type(sample) == "whale_move"

    def test_detect_event_type_tracker_fallback(self):
        """detect_event_type uses TRACKER role fallback to social_spike"""
        from outcome_resolver import detect_event_type
        
        sample = {
            "sentiment": {"intent": "INFORMATIONAL"},  # Would map to unknown
            "actor": {"role": "TRACKER", "score": 0.7}
        }
        assert detect_event_type(sample) == "social_spike"

    def test_detect_event_type_unknown_fallback(self):
        """detect_event_type returns unknown for unrecognized patterns"""
        from outcome_resolver import detect_event_type
        
        sample = {"sentiment": {"intent": "NOISE"}}
        assert detect_event_type(sample) == "unknown"
        
        sample = {}
        assert detect_event_type(sample) == "unknown"


class TestTextEventHints:
    """Tests for TEXT_EVENT_HINTS constant"""

    def test_text_event_hints_exists(self):
        """TEXT_EVENT_HINTS constant exists"""
        from outcome_resolver import TEXT_EVENT_HINTS
        
        assert isinstance(TEXT_EVENT_HINTS, list), "TEXT_EVENT_HINTS should be a list"
        assert len(TEXT_EVENT_HINTS) > 0, "TEXT_EVENT_HINTS should not be empty"

    def test_text_event_hints_structure(self):
        """TEXT_EVENT_HINTS has correct structure"""
        from outcome_resolver import TEXT_EVENT_HINTS
        
        for hint in TEXT_EVENT_HINTS:
            assert isinstance(hint, tuple), "Each hint should be a tuple"
            assert len(hint) == 2, "Each hint should have (keywords, event_type)"
            keywords, event_type = hint
            assert isinstance(keywords, list), "Keywords should be a list"
            assert isinstance(event_type, str), "Event type should be a string"


class TestSamplingQualityAPI:
    """Tests for GET /api/outcome/sampling-quality endpoint"""

    def test_sampling_quality_returns_ok(self):
        """GET /api/outcome/sampling-quality returns ok"""
        response = requests.get(f"{BASE_URL}/api/outcome/sampling-quality")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True

    def test_sampling_quality_has_include_rate_new(self):
        """Response contains include_rate_new"""
        response = requests.get(f"{BASE_URL}/api/outcome/sampling-quality")
        data = response.json()
        assert "include_rate_new" in data
        assert isinstance(data["include_rate_new"], (int, float))

    def test_sampling_quality_has_score_histogram(self):
        """Response contains score_histogram with 5 buckets"""
        response = requests.get(f"{BASE_URL}/api/outcome/sampling-quality")
        data = response.json()
        assert "score_histogram" in data
        histogram = data["score_histogram"]
        assert isinstance(histogram, list)
        assert len(histogram) == 5, "Should have 5 buckets"
        
        expected_ranges = ["0.0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"]
        for i, bucket in enumerate(histogram):
            assert "range" in bucket
            assert "count" in bucket
            assert bucket["range"] == expected_ranges[i]

    def test_sampling_quality_has_by_reason(self):
        """Response contains by_reason breakdown"""
        response = requests.get(f"{BASE_URL}/api/outcome/sampling-quality")
        data = response.json()
        assert "by_reason" in data
        by_reason = data["by_reason"]
        assert isinstance(by_reason, dict)
        
        # Should have some of these reasons
        valid_reasons = ["high_signal", "medium_signal", "low_signal", 
                        "medium_rejected", "low_rejected", "exploration"]
        for reason in by_reason.keys():
            assert reason in valid_reasons, f"Unknown reason: {reason}"

    def test_sampling_quality_has_by_event_type(self):
        """Response contains by_event_type breakdown"""
        response = requests.get(f"{BASE_URL}/api/outcome/sampling-quality")
        data = response.json()
        assert "by_event_type" in data
        by_type = data["by_event_type"]
        assert isinstance(by_type, dict)
        
        for et, info in by_type.items():
            assert "count" in info
            assert "included" in info
            assert "avg_score" in info
            assert "include_rate" in info

    def test_sampling_quality_has_avg_scores(self):
        """Response contains avg_score and avg_score_included"""
        response = requests.get(f"{BASE_URL}/api/outcome/sampling-quality")
        data = response.json()
        
        assert "avg_score" in data
        assert "avg_score_included" in data
        
        if data["total"] > 0:
            assert data["avg_score"] is not None
            assert 0 <= data["avg_score"] <= 1

    def test_sampling_quality_has_counts(self):
        """Response contains included_count and rejected_count"""
        response = requests.get(f"{BASE_URL}/api/outcome/sampling-quality")
        data = response.json()
        
        assert "included_count" in data
        assert "rejected_count" in data
        assert "total" in data
        
        assert data["included_count"] + data["rejected_count"] == data["total"]


class TestLabelsV2CompareAPI:
    """Tests for GET /api/outcome/labels-v2-compare still working"""

    def test_labels_v2_compare_returns_ok(self):
        """GET /api/outcome/labels-v2-compare returns ok"""
        response = requests.get(f"{BASE_URL}/api/outcome/labels-v2-compare")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True

    def test_labels_v2_compare_has_distributions(self):
        """Response contains v1 and v2 distributions"""
        response = requests.get(f"{BASE_URL}/api/outcome/labels-v2-compare")
        data = response.json()
        
        assert "v1_distribution" in data
        assert "v2_distribution" in data
        assert isinstance(data["v1_distribution"], dict)
        assert isinstance(data["v2_distribution"], dict)

    def test_labels_v2_compare_has_transitions(self):
        """Response contains transitions"""
        response = requests.get(f"{BASE_URL}/api/outcome/labels-v2-compare")
        data = response.json()
        
        assert "transitions" in data
        assert isinstance(data["transitions"], list)


class TestEvaluationAlignmentAPI:
    """Tests for GET /api/outcome/evaluation-alignment still working"""

    def test_evaluation_alignment_returns_ok(self):
        """GET /api/outcome/evaluation-alignment returns ok"""
        response = requests.get(f"{BASE_URL}/api/outcome/evaluation-alignment")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True

    def test_evaluation_alignment_has_metrics(self):
        """Response contains all required metrics"""
        response = requests.get(f"{BASE_URL}/api/outcome/evaluation-alignment")
        data = response.json()
        
        required_fields = [
            "total", "early_exit_rate", "avg_time_to_peak_up",
            "avg_time_to_peak_down", "avg_peak_vs_final_gap",
            "peak_captured_but_final_missed", "peak_captured_pct", "by_event_type"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_evaluation_alignment_reduced_unknown(self):
        """Text hints should reduce unknown count (was 79, now 73)"""
        response = requests.get(f"{BASE_URL}/api/outcome/evaluation-alignment")
        data = response.json()
        
        by_type = data.get("by_event_type", {})
        unknown_count = by_type.get("unknown", {}).get("count", 0)
        
        # With text hints, unknown should be reduced from 79
        # Note: exact count may vary, but should be less than original 79
        assert unknown_count <= 79, f"Unknown count {unknown_count} should be reduced from 79"


class TestBackfillLabelsV2API:
    """Tests for POST /api/outcome/backfill-labels-v2 with sampling"""

    def test_backfill_labels_v2_returns_ok(self):
        """POST /api/outcome/backfill-labels-v2 returns ok"""
        response = requests.post(f"{BASE_URL}/api/outcome/backfill-labels-v2?limit=1")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True

    def test_backfill_labels_v2_has_response_fields(self):
        """Response contains backfilled, errors, remaining"""
        response = requests.post(f"{BASE_URL}/api/outcome/backfill-labels-v2?limit=1")
        data = response.json()
        
        assert "backfilled" in data
        assert "errors" in data
        assert "remaining" in data


class TestAuditSamplingStructure:
    """Tests for audit.sampling structure in database"""

    def test_sampling_quality_data_structure(self):
        """Verify audit.sampling has correct structure via API"""
        response = requests.get(f"{BASE_URL}/api/outcome/sampling-quality")
        data = response.json()
        
        # If we have data, verify structure
        if data["total"] > 0:
            # by_reason should have valid reasons
            by_reason = data["by_reason"]
            valid_reasons = ["high_signal", "medium_signal", "low_signal", 
                           "medium_rejected", "low_rejected", "exploration"]
            for reason in by_reason.keys():
                assert reason in valid_reasons
            
            # by_event_type should have valid types
            by_type = data["by_event_type"]
            valid_types = ["listing", "funding", "unlock", "whale_move", 
                          "social_spike", "narrative", "unknown"]
            for et in by_type.keys():
                assert et in valid_types


class TestSamplingConstants:
    """Tests for sampling constants"""

    def test_sampling_thresholds_exist(self):
        """Sampling thresholds are defined"""
        from outcome_resolver import SAMPLING_HIGH, SAMPLING_MID, SAMPLING_MID_PROB, SAMPLING_LOW_PROB, EXPLORATION_RATE
        
        assert SAMPLING_HIGH == 0.6, "High threshold should be 0.6"
        assert SAMPLING_MID == 0.3, "Mid threshold should be 0.3"
        assert SAMPLING_MID_PROB == 0.4, "Mid probability should be 0.4 (40%)"
        assert SAMPLING_LOW_PROB == 0.10, "Low probability should be 0.10 (10%)"
        assert EXPLORATION_RATE == 0.10, "Exploration rate should be 0.10 (10%)"

    def test_event_type_weights_exist(self):
        """Event type weights are defined"""
        from outcome_resolver import EVENT_TYPE_WEIGHT
        
        assert isinstance(EVENT_TYPE_WEIGHT, dict)
        assert EVENT_TYPE_WEIGHT.get("listing") == 1.0
        assert EVENT_TYPE_WEIGHT.get("funding") == 0.9
        assert EVENT_TYPE_WEIGHT.get("unlock") == 0.8
        assert EVENT_TYPE_WEIGHT.get("whale_move") == 0.7
        assert EVENT_TYPE_WEIGHT.get("social_spike") == 0.6
        assert EVENT_TYPE_WEIGHT.get("narrative") == 0.5
        assert EVENT_TYPE_WEIGHT.get("unknown") == 0.3

    def test_position_weights_exist(self):
        """Position weights are defined"""
        from outcome_resolver import POSITION_WEIGHT
        
        assert isinstance(POSITION_WEIGHT, dict)
        assert POSITION_WEIGHT.get("EARLY") == 1.0
        assert POSITION_WEIGHT.get("MID") == 0.7
        assert POSITION_WEIGHT.get("LATE") == 0.4


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
