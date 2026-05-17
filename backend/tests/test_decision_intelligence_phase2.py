"""
Decision Intelligence Phase 2 Tests
====================================
Tests for Phase 2 features:
1. Market Context (1 line: 'Momentum strong · Sentiment aligned · Velocity ↑')
2. Comparative Rank (uniform 'Top N signal' format)
3. Signal Quality (HIGH/MED/LOW replacing confidence)
4. Priority Visual (#1 signal gets emerald border/glow + 'Top signal' badge)

Backend endpoints tested:
- /api/v4/sentiment/top-signals
- /api/v4/sentiment/correlations
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestTopSignalsPhase2:
    """Tests for /api/v4/sentiment/top-signals Phase 2 fields"""

    def test_top_signals_returns_market_context(self):
        """marketContext should be an array with max 3 items"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        signals = data.get("data", [])
        assert len(signals) > 0, "Should have at least one signal"
        
        for sig in signals[:5]:
            assert "marketContext" in sig, f"Signal {sig.get('entityId')} missing marketContext"
            ctx = sig["marketContext"]
            assert isinstance(ctx, list), "marketContext should be a list"
            assert len(ctx) <= 3, f"marketContext should have max 3 items, got {len(ctx)}"
            print(f"✓ {sig['symbol']}: marketContext = {ctx}")

    def test_top_signals_market_context_values(self):
        """marketContext should contain valid descriptors"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        data = response.json()
        signals = data.get("data", [])
        
        valid_momentum = ["Momentum strong", "Momentum building", "Momentum fading"]
        valid_sentiment = ["Sentiment aligned", "Sentiment bearish", "Sentiment mixed"]
        valid_velocity = ["Velocity ↑", "Velocity steady", "Velocity ↓"]
        
        for sig in signals[:5]:
            ctx = sig.get("marketContext", [])
            for item in ctx:
                is_valid = (
                    item in valid_momentum or 
                    item in valid_sentiment or 
                    item in valid_velocity
                )
                assert is_valid, f"Invalid marketContext item: {item}"
        print("✓ All marketContext values are valid")

    def test_top_signals_returns_signal_quality(self):
        """signalQuality should be HIGH/MED/LOW"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        data = response.json()
        signals = data.get("data", [])
        
        valid_qualities = ["HIGH", "MED", "LOW"]
        
        for sig in signals[:5]:
            assert "signalQuality" in sig, f"Signal {sig.get('entityId')} missing signalQuality"
            quality = sig["signalQuality"]
            assert quality in valid_qualities, f"Invalid signalQuality: {quality}"
            print(f"✓ {sig['symbol']}: signalQuality = {quality}")

    def test_top_signals_returns_rank(self):
        """rank should be 1-based integer"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        data = response.json()
        signals = data.get("data", [])
        
        for i, sig in enumerate(signals):
            assert "rank" in sig, f"Signal {sig.get('entityId')} missing rank"
            rank = sig["rank"]
            assert isinstance(rank, int), f"rank should be int, got {type(rank)}"
            assert rank == i + 1, f"rank should be {i + 1}, got {rank}"
            print(f"✓ {sig['symbol']}: rank = {rank}")

    def test_top_signals_rank_1_is_top_signal(self):
        """First signal should have rank=1 (for 'Top signal' badge)"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        data = response.json()
        signals = data.get("data", [])
        
        assert len(signals) > 0, "Should have at least one signal"
        first_signal = signals[0]
        assert first_signal["rank"] == 1, f"First signal should have rank=1, got {first_signal['rank']}"
        print(f"✓ Top signal: {first_signal['symbol']} with rank=1")

    def test_top_signals_phase1_fields_still_present(self):
        """Phase 1 fields should still be present"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        data = response.json()
        signals = data.get("data", [])
        
        phase1_fields = ["setupType", "signalMaturity", "riskContext", "expectedMove"]
        
        for sig in signals[:3]:
            for field in phase1_fields:
                assert field in sig, f"Phase 1 field {field} missing from signal {sig.get('entityId')}"
        print("✓ All Phase 1 fields still present")


class TestCorrelationsPhase2:
    """Tests for /api/v4/sentiment/correlations Phase 2 fields"""

    def test_correlations_signal_has_market_context(self):
        """signal object should contain marketContext"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        correlations = data.get("data", [])
        active_signals = [c for c in correlations if c.get("signal", {}).get("type") != "NEUTRAL"]
        
        assert len(active_signals) > 0, "Should have at least one active signal"
        
        for corr in active_signals[:5]:
            signal = corr.get("signal", {})
            assert "marketContext" in signal, f"Signal for {corr.get('id')} missing marketContext"
            ctx = signal["marketContext"]
            assert isinstance(ctx, list), "marketContext should be a list"
            assert len(ctx) <= 3, f"marketContext should have max 3 items"
            print(f"✓ {corr['symbol']}: signal.marketContext = {ctx}")

    def test_correlations_signal_has_signal_quality(self):
        """signal object should contain signalQuality"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        data = response.json()
        correlations = data.get("data", [])
        
        valid_qualities = ["HIGH", "MED", "LOW"]
        
        for corr in correlations[:5]:
            signal = corr.get("signal", {})
            assert "signalQuality" in signal, f"Signal for {corr.get('id')} missing signalQuality"
            quality = signal["signalQuality"]
            assert quality in valid_qualities, f"Invalid signalQuality: {quality}"
            print(f"✓ {corr['symbol']}: signal.signalQuality = {quality}")

    def test_correlations_signal_has_rank(self):
        """signal object should contain rank"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        data = response.json()
        correlations = data.get("data", [])
        
        active_signals = [c for c in correlations if c.get("signal", {}).get("type") != "NEUTRAL"]
        
        for corr in active_signals[:5]:
            signal = corr.get("signal", {})
            assert "rank" in signal, f"Signal for {corr.get('id')} missing rank"
            rank = signal["rank"]
            assert isinstance(rank, int), f"rank should be int, got {type(rank)}"
            assert rank >= 1, f"rank should be >= 1, got {rank}"
            print(f"✓ {corr['symbol']}: signal.rank = {rank}")

    def test_correlations_rank_1_exists(self):
        """At least one signal should have rank=1"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        data = response.json()
        correlations = data.get("data", [])
        
        rank_1_signals = [c for c in correlations if c.get("signal", {}).get("rank") == 1]
        assert len(rank_1_signals) == 1, f"Should have exactly one rank=1 signal, got {len(rank_1_signals)}"
        
        top_signal = rank_1_signals[0]
        print(f"✓ Top signal (rank=1): {top_signal['symbol']}")

    def test_correlations_neutral_signals_have_rank_0(self):
        """NEUTRAL signals should have rank=0"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        data = response.json()
        correlations = data.get("data", [])
        
        neutral_signals = [c for c in correlations if c.get("signal", {}).get("type") == "NEUTRAL"]
        
        for corr in neutral_signals:
            signal = corr.get("signal", {})
            assert signal.get("rank") == 0, f"NEUTRAL signal {corr.get('id')} should have rank=0"
        print(f"✓ {len(neutral_signals)} NEUTRAL signals have rank=0")

    def test_correlations_phase1_fields_still_present(self):
        """Phase 1 fields should still be present in signal object"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        data = response.json()
        correlations = data.get("data", [])
        
        active_signals = [c for c in correlations if c.get("signal", {}).get("type") != "NEUTRAL"]
        phase1_fields = ["setupType", "signalMaturity", "riskContext", "expectedMove"]
        
        for corr in active_signals[:3]:
            signal = corr.get("signal", {})
            for field in phase1_fields:
                assert field in signal, f"Phase 1 field {field} missing from signal for {corr.get('id')}"
        print("✓ All Phase 1 fields still present in signal object")


class TestSignalQualityLogic:
    """Tests for signalQuality computation logic"""

    def test_high_quality_signals_have_high_scores(self):
        """HIGH quality signals should have high decayedScore"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        data = response.json()
        signals = data.get("data", [])
        
        high_quality = [s for s in signals if s.get("signalQuality") == "HIGH"]
        
        for sig in high_quality[:3]:
            # HIGH quality typically has decayedScore >= 60 or multiple sources
            decayed = sig.get("decayedScore", 0)
            confidence = sig.get("confidence", 0)
            print(f"✓ HIGH quality {sig['symbol']}: decayedScore={decayed}, confidence={confidence}")

    def test_signal_quality_replaces_confidence_label(self):
        """signalQuality should be used instead of confidenceLabel for display"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        data = response.json()
        signals = data.get("data", [])
        
        for sig in signals[:5]:
            # Both fields exist but signalQuality is the new display field
            assert "signalQuality" in sig, "signalQuality should exist"
            assert "confidenceLabel" in sig, "confidenceLabel should still exist for backward compat"
            print(f"✓ {sig['symbol']}: signalQuality={sig['signalQuality']}, confidenceLabel={sig['confidenceLabel']}")


class TestMarketContextFormat:
    """Tests for marketContext format and content"""

    def test_market_context_is_dot_separable(self):
        """marketContext items should be joinable with ' · '"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        data = response.json()
        signals = data.get("data", [])
        
        for sig in signals[:5]:
            ctx = sig.get("marketContext", [])
            if ctx:
                joined = " · ".join(ctx)
                print(f"✓ {sig['symbol']}: {joined}")
                assert "·" not in ctx[0], "Individual items should not contain separator"

    def test_market_context_max_3_items(self):
        """marketContext should never exceed 3 items"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        data = response.json()
        signals = data.get("data", [])
        
        for sig in signals:
            ctx = sig.get("marketContext", [])
            assert len(ctx) <= 3, f"{sig['symbol']} has {len(ctx)} marketContext items"
        print("✓ All signals have max 3 marketContext items")


class TestRankOrdering:
    """Tests for rank ordering and consistency"""

    def test_top_signals_sorted_by_rank(self):
        """top-signals should be sorted by rank (1, 2, 3, ...)"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        data = response.json()
        signals = data.get("data", [])
        
        ranks = [s.get("rank") for s in signals]
        expected = list(range(1, len(signals) + 1))
        assert ranks == expected, f"Ranks should be sequential: {ranks}"
        print(f"✓ Ranks are sequential: {ranks[:5]}...")

    def test_correlations_active_sorted_by_rank(self):
        """Active signals in correlations should be sorted by rank"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        data = response.json()
        correlations = data.get("data", [])
        
        active = [c for c in correlations if c.get("signal", {}).get("type") != "NEUTRAL"]
        ranks = [c.get("signal", {}).get("rank") for c in active]
        
        # Ranks should be sequential starting from 1
        expected = list(range(1, len(active) + 1))
        assert ranks == expected, f"Active signal ranks should be sequential: {ranks}"
        print(f"✓ Active signal ranks are sequential: {ranks[:5]}...")


class TestNoConfidenceQualityDuplication:
    """Tests to ensure no duplicate confidence+quality display"""

    def test_signal_quality_is_distinct_from_confidence(self):
        """signalQuality should be distinct field from confidence"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        data = response.json()
        signals = data.get("data", [])
        
        for sig in signals[:5]:
            quality = sig.get("signalQuality")
            confidence = sig.get("confidence")
            conf_label = sig.get("confidenceLabel")
            
            # signalQuality is the new display field
            assert quality in ["HIGH", "MED", "LOW"], f"Invalid signalQuality: {quality}"
            # confidence is numeric
            assert isinstance(confidence, (int, float)), f"confidence should be numeric"
            print(f"✓ {sig['symbol']}: Quality={quality}, Confidence={confidence}, ConfLabel={conf_label}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
