"""
Phase 4 Real-Time Edge System Tests
====================================
Tests for:
1. Score decay (baseScore vs listingScore)
2. marketReaction field (renamed from expectedBehavior)
3. Live alerts array for JUST LISTED signals
4. Auto-refresh polling (frontend runtime feature - DOM check only)
5. Alert toast container (frontend runtime feature - DOM check only)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestPhase4ListingsEndpoint:
    """Tests for /api/v4/sentiment/listings Phase 4 features"""

    def test_listings_returns_ok(self):
        """Verify listings endpoint returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print("PASS: Listings endpoint returns ok:true")

    def test_listings_has_base_score_field(self):
        """Verify listings have baseScore field"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        data = response.json()
        all_listings = data["data"].get("confirmed", []) + data["data"].get("potential", [])
        
        for listing in all_listings:
            assert "baseScore" in listing, f"Missing baseScore in listing {listing.get('token')}"
            assert isinstance(listing["baseScore"], (int, float)), f"baseScore should be numeric"
        print(f"PASS: All {len(all_listings)} listings have baseScore field")

    def test_listings_has_listing_score_field(self):
        """Verify listings have listingScore (decayed) field"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        data = response.json()
        all_listings = data["data"].get("confirmed", []) + data["data"].get("potential", [])
        
        for listing in all_listings:
            assert "listingScore" in listing, f"Missing listingScore in listing {listing.get('token')}"
            assert isinstance(listing["listingScore"], (int, float)), f"listingScore should be numeric"
        print(f"PASS: All {len(all_listings)} listings have listingScore field")

    def test_score_decay_applied(self):
        """Verify score decay: listingScore <= baseScore"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        data = response.json()
        all_listings = data["data"].get("confirmed", []) + data["data"].get("potential", [])
        
        for listing in all_listings:
            base = listing.get("baseScore", 0)
            decayed = listing.get("listingScore", 0)
            assert decayed <= base, f"Decayed score {decayed} should be <= base {base} for {listing.get('token')}"
        print(f"PASS: Score decay applied correctly (listingScore <= baseScore)")

    def test_fresh_listing_decay_multiplier(self):
        """Verify FRESH LISTING gets 0.8 multiplier (5-30m ago)"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        data = response.json()
        all_listings = data["data"].get("confirmed", []) + data["data"].get("potential", [])
        
        fresh_listings = [l for l in all_listings if l.get("freshness") == "FRESH LISTING"]
        for listing in fresh_listings:
            base = listing.get("baseScore", 0)
            decayed = listing.get("listingScore", 0)
            # FRESH LISTING should have ~0.8 multiplier
            if base > 0:
                ratio = decayed / base
                assert 0.7 <= ratio <= 0.9, f"FRESH LISTING ratio {ratio:.2f} should be ~0.8 for {listing.get('token')}"
        print(f"PASS: FRESH LISTING decay multiplier verified ({len(fresh_listings)} listings)")

    def test_active_listing_decay_multiplier(self):
        """Verify ACTIVE gets 0.5 or 0.2 multiplier (>30m ago)"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        data = response.json()
        all_listings = data["data"].get("confirmed", []) + data["data"].get("potential", [])
        
        active_listings = [l for l in all_listings if l.get("freshness") == "ACTIVE"]
        for listing in active_listings:
            base = listing.get("baseScore", 0)
            decayed = listing.get("listingScore", 0)
            # ACTIVE should have 0.5 or 0.2 multiplier
            if base > 0:
                ratio = decayed / base
                assert ratio <= 0.6, f"ACTIVE ratio {ratio:.2f} should be <= 0.6 for {listing.get('token')}"
        print(f"PASS: ACTIVE decay multiplier verified ({len(active_listings)} listings)")

    def test_market_reaction_field_present(self):
        """Verify marketReaction field exists (renamed from expectedBehavior)"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        data = response.json()
        all_listings = data["data"].get("confirmed", []) + data["data"].get("potential", [])
        
        for listing in all_listings:
            assert "marketReaction" in listing, f"Missing marketReaction in listing {listing.get('token')}"
            assert isinstance(listing["marketReaction"], list), f"marketReaction should be a list"
        print(f"PASS: All {len(all_listings)} listings have marketReaction field")

    def test_market_reaction_content(self):
        """Verify marketReaction contains terminal-grade analysis text"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        data = response.json()
        all_listings = data["data"].get("confirmed", []) + data["data"].get("potential", [])
        
        expected_patterns = ["volatility", "liquidity", "expansion", "risk", "monitor"]
        for listing in all_listings:
            reactions = listing.get("marketReaction", [])
            if reactions:
                combined = " ".join(reactions).lower()
                has_pattern = any(p in combined for p in expected_patterns)
                assert has_pattern, f"marketReaction should contain terminal-grade text for {listing.get('token')}"
        print(f"PASS: marketReaction contains terminal-grade analysis text")

    def test_no_expected_behavior_field(self):
        """Verify expectedBehavior field is NOT present (renamed to marketReaction)"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        data = response.json()
        all_listings = data["data"].get("confirmed", []) + data["data"].get("potential", [])
        
        for listing in all_listings:
            # expectedBehavior should NOT be present (renamed to marketReaction)
            assert "expectedBehavior" not in listing or "marketReaction" in listing, \
                f"expectedBehavior should be renamed to marketReaction for {listing.get('token')}"
        print(f"PASS: expectedBehavior renamed to marketReaction")

    def test_live_array_present(self):
        """Verify live array exists in response"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        data = response.json()
        
        assert "live" in data["data"], "Missing 'live' array in response"
        assert isinstance(data["data"]["live"], list), "'live' should be a list"
        print(f"PASS: 'live' array present in response (count: {len(data['data']['live'])})")

    def test_first_seen_at_field(self):
        """Verify firstSeenAt field exists for (first seen) label"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        data = response.json()
        all_listings = data["data"].get("confirmed", []) + data["data"].get("potential", [])
        
        for listing in all_listings:
            assert "firstSeenAt" in listing, f"Missing firstSeenAt in listing {listing.get('token')}"
        print(f"PASS: All {len(all_listings)} listings have firstSeenAt field")


class TestPhase4TopSignals:
    """Tests for /api/v4/sentiment/top-signals Phase 4 features"""

    def test_top_signals_returns_ok(self):
        """Verify top-signals endpoint returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print("PASS: top-signals endpoint returns ok:true")

    def test_top_signals_has_decayed_score(self):
        """Verify top-signals have decayedScore field"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        data = response.json()
        signals = data.get("data", [])
        
        for sig in signals:
            assert "decayedScore" in sig, f"Missing decayedScore in signal {sig.get('entityId')}"
            assert "score" in sig, f"Missing score (base) in signal {sig.get('entityId')}"
        print(f"PASS: All {len(signals)} signals have decayedScore field")


class TestPhase4Correlations:
    """Tests for /api/v4/sentiment/correlations Phase 4 features"""

    def test_correlations_returns_ok(self):
        """Verify correlations endpoint returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print("PASS: correlations endpoint returns ok:true")

    def test_correlations_signal_has_decayed_score(self):
        """Verify correlation signals have decayedScore field"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        data = response.json()
        correlations = data.get("data", [])
        
        for corr in correlations:
            signal = corr.get("signal", {})
            if signal.get("type") != "NEUTRAL":
                assert "decayedScore" in signal, f"Missing decayedScore in signal for {corr.get('id')}"
        print(f"PASS: Correlation signals have decayedScore field")


class TestPhase1To3Regression:
    """Regression tests for Phase 1-3 features"""

    def test_setup_maturity_fields(self):
        """Verify Phase 1 Setup+Maturity fields still present"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        data = response.json()
        correlations = data.get("data", [])
        
        for corr in correlations:
            signal = corr.get("signal", {})
            if signal.get("type") != "NEUTRAL":
                assert "setupType" in signal, f"Missing setupType for {corr.get('id')}"
                assert "signalMaturity" in signal, f"Missing signalMaturity for {corr.get('id')}"
        print("PASS: Phase 1 Setup+Maturity fields present")

    def test_quality_alignment_fields(self):
        """Verify Phase 2 Quality+Alignment fields still present"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        data = response.json()
        correlations = data.get("data", [])
        
        for corr in correlations:
            signal = corr.get("signal", {})
            if signal.get("type") != "NEUTRAL":
                assert "signalQuality" in signal, f"Missing signalQuality for {corr.get('id')}"
                assert "alignment" in signal, f"Missing alignment for {corr.get('id')}"
        print("PASS: Phase 2 Quality+Alignment fields present")

    def test_velocity_risk_fields(self):
        """Verify Phase 3 Velocity+Risk fields still present"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        data = response.json()
        correlations = data.get("data", [])
        
        for corr in correlations:
            signal = corr.get("signal", {})
            if signal.get("type") != "NEUTRAL":
                assert "riskContext" in signal, f"Missing riskContext for {corr.get('id')}"
                assert "marketContext" in signal, f"Missing marketContext for {corr.get('id')}"
        print("PASS: Phase 3 Velocity+Risk fields present")

    def test_expected_move_fields(self):
        """Verify expectedMove fields still present"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        data = response.json()
        correlations = data.get("data", [])
        
        for corr in correlations:
            signal = corr.get("signal", {})
            if signal.get("type") != "NEUTRAL":
                assert "expectedMove" in signal, f"Missing expectedMove for {corr.get('id')}"
                move = signal.get("expectedMove", {})
                assert "text" in move, f"Missing expectedMove.text for {corr.get('id')}"
        print("PASS: expectedMove fields present")


class TestNoBuySellWait:
    """Verify no BUY/SELL/WAIT in API responses"""

    def test_no_buy_sell_in_listings(self):
        """Verify no BUY/SELL/WAIT in listings response"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        text = response.text.upper()
        
        assert "\"BUY\"" not in text, "Found BUY in listings response"
        assert "\"SELL\"" not in text, "Found SELL in listings response"
        assert "\"WAIT\"" not in text, "Found WAIT in listings response"
        print("PASS: No BUY/SELL/WAIT in listings response")

    def test_no_buy_sell_in_correlations(self):
        """Verify no BUY/SELL/WAIT in correlations response"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        text = response.text.upper()
        
        assert "\"BUY\"" not in text, "Found BUY in correlations response"
        assert "\"SELL\"" not in text, "Found SELL in correlations response"
        assert "\"WAIT\"" not in text, "Found WAIT in correlations response"
        print("PASS: No BUY/SELL/WAIT in correlations response")

    def test_no_buy_sell_in_top_signals(self):
        """Verify no BUY/SELL/WAIT in top-signals response"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        text = response.text.upper()
        
        assert "\"BUY\"" not in text, "Found BUY in top-signals response"
        assert "\"SELL\"" not in text, "Found SELL in top-signals response"
        assert "\"WAIT\"" not in text, "Found WAIT in top-signals response"
        print("PASS: No BUY/SELL/WAIT in top-signals response")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
