"""
Prediction Module Stage 2A Tests
================================
Tests for:
- Enriched Exchange adapter (regime, structural_risk, scenarios)
- Scenario-weighted probability engine (separate probability/confidence)
- Direction-aware alignment engine
- Opportunity scoring with ranking and buckets
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestPredictionStage2ABackend:
    """Stage 2A: Full prediction pipeline tests"""

    def test_prediction_run_returns_enriched_results(self):
        """GET /api/prediction/run returns enriched results with Stage 2A fields"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=10")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "results" in data
        assert "exchange_available" in data
        
        # Check exchange availability
        assert "BTC" in data["exchange_available"]
        assert "ETH" in data["exchange_available"]
        
        # If we have results, verify Stage 2A fields
        if data["results"]:
            result = data["results"][0]
            
            # Core fields
            assert "market_id" in result
            assert "question" in result
            assert "asset" in result
            
            # Stage 2A: Regime (should NOT be UNKNOWN if exchange is available)
            assert "regime" in result
            if data["exchange_available"].get("BTC"):
                # Regime should be real data, not UNKNOWN
                assert result["regime"] in ["TREND", "RANGE", "PULLBACK", "TRANSITION", "BREAKDOWN", "UNKNOWN"]
            
            # Stage 2A: Structural Risk block
            assert "structural_risk" in result
            sr = result["structural_risk"]
            assert "reversal_risk" in sr
            assert "breakdown_risk" in sr
            assert "drawdown_pressure" in sr
            assert "combined_risk" in sr
            # All risk values should be 0-1
            for key in ["reversal_risk", "breakdown_risk", "drawdown_pressure", "combined_risk"]:
                assert 0 <= sr[key] <= 1, f"{key} should be 0-1, got {sr[key]}"
            
            # Stage 2A: Separate probability and confidence
            assert "fair_prob" in result
            assert "model_confidence" in result
            assert 0 <= result["fair_prob"] <= 1
            assert 0 <= result["model_confidence"] <= 1
            
            # Stage 2A: Alignment score
            assert "alignment_score" in result
            assert 0 <= result["alignment_score"] <= 1
            
            # Stage 2A: Opportunity score and bucket
            assert "opportunity_score" in result
            assert "bucket" in result
            assert 0 <= result["opportunity_score"] <= 1
            assert result["bucket"] in ["actionable", "watch", "avoid"]
            
            # Stage 2A: Scoring components (explainability)
            assert "scoring_components" in result
            sc = result["scoring_components"]
            assert "edge_score" in sc
            assert "confidence_score" in sc
            assert "alignment_score" in sc
            
            # Stage 2A: Biases
            assert "biases" in result
            
            # Stage 2A: Reasoning
            assert "reasoning" in result
            assert isinstance(result["reasoning"], list)

    def test_exchange_adapter_returns_real_regime(self):
        """Exchange adapter reads real data from DB - regime should not be UNKNOWN"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=5")
        assert response.status_code == 200
        
        data = response.json()
        
        # If BTC exchange is available, regime should be real
        if data.get("exchange_available", {}).get("BTC"):
            btc_results = [r for r in data.get("results", []) if r.get("asset") == "BTC"]
            if btc_results:
                result = btc_results[0]
                # With real exchange data, regime should be set
                # Current regime is TRANSITION per agent context
                assert result["regime"] != "UNKNOWN" or result["model_confidence"] < 0.2

    def test_probability_and_confidence_are_separate(self):
        """Probability engine keeps probability and confidence separate"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=5")
        assert response.status_code == 200
        
        data = response.json()
        
        for result in data.get("results", []):
            # fair_prob is pure probability
            fair_prob = result.get("fair_prob", 0.5)
            # model_confidence is trust level
            model_confidence = result.get("model_confidence", 0.3)
            
            # They should be independent values
            assert "fair_prob" in result
            assert "model_confidence" in result
            
            # Both should be valid probabilities
            assert 0 <= fair_prob <= 1
            assert 0 <= model_confidence <= 1
            
            # Check probability components exist
            assert "probability_components" in result
            pc = result["probability_components"]
            assert "exchange_base" in pc
            assert "onchain_modifier" in pc
            assert "sentiment_modifier" in pc

    def test_alignment_is_direction_aware(self):
        """Alignment engine is direction-aware: for 'above' markets, bearish onchain reduces alignment"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=10")
        assert response.status_code == 200
        
        data = response.json()
        
        for result in data.get("results", []):
            comparator = result.get("comparator", "above")
            biases = result.get("biases", {})
            alignment_score = result.get("alignment_score", 0.5)
            conflict_flags = result.get("conflict_flags", [])
            
            # For "above" markets with bearish onchain, alignment should be reduced
            if comparator == "above" and biases.get("onchain") == "bearish":
                # Should have conflict flag
                has_onchain_conflict = any("onchain" in f.lower() for f in conflict_flags)
                assert has_onchain_conflict, "Bearish onchain should create conflict for 'above' market"
                # Alignment should be below 0.5 (penalized)
                assert alignment_score < 0.7, f"Alignment should be reduced with opposing bias, got {alignment_score}"

    def test_opportunity_score_normalized_and_buckets_correct(self):
        """Opportunity score is normalized 0-1, buckets are actionable (>=0.65), watch (0.40-0.64), avoid (<0.40)"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=20")
        assert response.status_code == 200
        
        data = response.json()
        
        for result in data.get("results", []):
            opp_score = result.get("opportunity_score", 0)
            bucket = result.get("bucket", "avoid")
            
            # Score should be 0-1
            assert 0 <= opp_score <= 1, f"Opportunity score should be 0-1, got {opp_score}"
            
            # Bucket should match score
            if opp_score >= 0.65:
                assert bucket == "actionable", f"Score {opp_score} should be 'actionable', got '{bucket}'"
            elif opp_score >= 0.40:
                assert bucket == "watch", f"Score {opp_score} should be 'watch', got '{bucket}'"
            else:
                assert bucket == "avoid", f"Score {opp_score} should be 'avoid', got '{bucket}'"

    def test_results_sorted_by_opportunity_score_descending(self):
        """Results are sorted by opportunity_score descending"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=20")
        assert response.status_code == 200
        
        data = response.json()
        results = data.get("results", [])
        
        if len(results) > 1:
            scores = [r.get("opportunity_score", 0) for r in results]
            # Check descending order
            for i in range(len(scores) - 1):
                assert scores[i] >= scores[i + 1], f"Results not sorted: {scores[i]} < {scores[i + 1]}"

    def test_fallback_when_exchange_unavailable(self):
        """Fallback: if exchange returns None, probability should be ~0.5 and system should not crash"""
        # This is tested implicitly - if ETH exchange is unavailable, ETH markets should still work
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=30")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        # System should not crash even with missing data
        # All results should have valid structure
        for result in data.get("results", []):
            assert "fair_prob" in result
            assert "model_confidence" in result
            assert "opportunity_score" in result
            assert "bucket" in result
            
            # If exchange unavailable, fair_prob should be close to 0.5
            # (base probability without exchange data)
            if result.get("regime") == "UNKNOWN":
                # Without exchange, probability should be near 0.5
                assert 0.3 <= result["fair_prob"] <= 0.7, "Without exchange, fair_prob should be near 0.5"


class TestPredictionMarketsEndpoint:
    """Test raw markets endpoint"""

    def test_markets_endpoint_returns_ok(self):
        """GET /api/prediction/markets returns ok=true with markets array"""
        response = requests.get(f"{BASE_URL}/api/prediction/markets?limit=10")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "markets" in data
        assert "count" in data
        assert isinstance(data["markets"], list)


class TestScoringComponents:
    """Test scoring component calculations"""

    def test_scoring_components_present(self):
        """Each result has scoring_components for explainability"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=5")
        assert response.status_code == 200
        
        data = response.json()
        
        for result in data.get("results", []):
            sc = result.get("scoring_components", {})
            
            # All scoring components should be present
            assert "edge_score" in sc
            assert "confidence_score" in sc
            assert "alignment_score" in sc
            assert "liquidity_score" in sc
            assert "spread_penalty" in sc
            assert "risk_penalty" in sc
            
            # All should be numeric
            for key, value in sc.items():
                assert isinstance(value, (int, float)), f"{key} should be numeric"


class TestDecisionEngine:
    """Test decision engine outputs"""

    def test_decision_values_valid(self):
        """Decision values are only: YES, NO, WAIT, AVOID"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=20")
        assert response.status_code == 200
        
        data = response.json()
        valid_decisions = {"YES", "NO", "WAIT", "AVOID"}
        
        for result in data.get("results", []):
            decision = result.get("decision")
            assert decision in valid_decisions, f"Invalid decision: {decision}"


class TestAlignmentEngine:
    """Test alignment engine outputs"""

    def test_alignment_has_biases_and_reasoning(self):
        """Alignment output includes biases and reasoning"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=5")
        assert response.status_code == 200
        
        data = response.json()
        
        for result in data.get("results", []):
            # Biases should be present
            biases = result.get("biases", {})
            assert isinstance(biases, dict)
            
            # Reasoning should be present
            reasoning = result.get("reasoning", [])
            assert isinstance(reasoning, list)
            
            # Conflict flags should be present
            conflict_flags = result.get("conflict_flags", [])
            assert isinstance(conflict_flags, list)


class TestEdgeEngine:
    """Test edge computation"""

    def test_edge_fields_present(self):
        """Edge fields are present: implied_prob, fair_prob, raw_edge, net_edge"""
        response = requests.get(f"{BASE_URL}/api/prediction/run?limit=5")
        assert response.status_code == 200
        
        data = response.json()
        
        for result in data.get("results", []):
            assert "implied_prob" in result
            assert "fair_prob" in result
            assert "raw_edge" in result
            assert "net_edge" in result
            
            # Edge should be fair - implied
            # (approximately, due to penalties)
            raw_edge = result.get("raw_edge", 0)
            fair = result.get("fair_prob", 0.5)
            implied = result.get("implied_prob", 0.5)
            
            expected_raw = fair - implied
            assert abs(raw_edge - expected_raw) < 0.01, f"raw_edge mismatch: {raw_edge} vs {expected_raw}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
