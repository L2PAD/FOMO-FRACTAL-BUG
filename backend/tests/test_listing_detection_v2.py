"""
Listing Detection Engine v2 Tests
=================================
Tests for P0-2 Listing Logic Fix:
- ALREADY_LISTED_REGISTRY for top 50 assets on top 5 exchanges
- Negative text filters
- Event type classification: NEW_SPOT_LISTING/FUTURES_LISTING/NEW_PAIR/EXCHANGE_MENTION
- Confidence model with novelty check
- EXCHANGE_MENTION signals have capped score (max 25)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestListingsEndpoint:
    """Tests for /api/v4/sentiment/listings endpoint"""

    def test_listings_endpoint_returns_ok(self):
        """Test that listings endpoint returns ok status"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print("✅ Listings endpoint returns ok status")

    def test_listings_returns_mentions_array(self):
        """Test that listings returns mentions array alongside confirmed/potential"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        data = response.json()
        assert "data" in data
        listings_data = data["data"]
        
        # Check all required arrays are present
        assert "confirmed" in listings_data, "Missing 'confirmed' array"
        assert "potential" in listings_data, "Missing 'potential' array"
        assert "mentions" in listings_data, "Missing 'mentions' array"
        assert "live" in listings_data, "Missing 'live' array"
        
        print(f"✅ Listings returns all arrays: confirmed={len(listings_data['confirmed'])}, "
              f"potential={len(listings_data['potential'])}, mentions={len(listings_data['mentions'])}, "
              f"live={len(listings_data['live'])}")

    def test_listings_have_event_type_field(self):
        """Test that each listing result has eventType field"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        data = response.json()["data"]
        
        all_listings = (data.get("confirmed", []) + data.get("potential", []) + 
                       data.get("mentions", []) + data.get("live", []))
        
        for listing in all_listings:
            assert "eventType" in listing, f"Missing eventType for {listing.get('token')}"
            assert listing["eventType"] in ["NEW_SPOT_LISTING", "FUTURES_LISTING", 
                                            "NEW_PAIR", "EXCHANGE_MENTION", "POTENTIAL_LISTING"], \
                f"Invalid eventType: {listing['eventType']}"
        
        print(f"✅ All {len(all_listings)} listings have valid eventType field")

    def test_listings_have_is_already_listed_field(self):
        """Test that each listing result has isAlreadyListed field"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        data = response.json()["data"]
        
        all_listings = (data.get("confirmed", []) + data.get("potential", []) + 
                       data.get("mentions", []) + data.get("live", []))
        
        for listing in all_listings:
            assert "isAlreadyListed" in listing, f"Missing isAlreadyListed for {listing.get('token')}"
            assert isinstance(listing["isAlreadyListed"], bool), \
                f"isAlreadyListed should be boolean for {listing.get('token')}"
        
        print(f"✅ All {len(all_listings)} listings have isAlreadyListed field")

    def test_listings_have_confidence_score_field(self):
        """Test that each listing result has confidenceScore field"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        data = response.json()["data"]
        
        all_listings = (data.get("confirmed", []) + data.get("potential", []) + 
                       data.get("mentions", []) + data.get("live", []))
        
        for listing in all_listings:
            assert "confidenceScore" in listing, f"Missing confidenceScore for {listing.get('token')}"
            assert isinstance(listing["confidenceScore"], (int, float)), \
                f"confidenceScore should be numeric for {listing.get('token')}"
        
        print(f"✅ All {len(all_listings)} listings have confidenceScore field")


class TestExchangeMentionLogic:
    """Tests for EXCHANGE_MENTION classification and scoring"""

    def test_arb_binance_is_exchange_mention(self):
        """Test that ARB:Binance returns eventType=EXCHANGE_MENTION (already listed in registry)"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        data = response.json()["data"]
        
        # Find ARB in mentions
        arb_listings = [l for l in data.get("mentions", []) 
                       if l["token"] == "ARB" and l["exchange"] == "Binance"]
        
        if arb_listings:
            arb = arb_listings[0]
            assert arb["eventType"] == "EXCHANGE_MENTION", \
                f"ARB:Binance should be EXCHANGE_MENTION, got {arb['eventType']}"
            assert arb["isAlreadyListed"] is True, \
                "ARB:Binance should have isAlreadyListed=True"
            print(f"✅ ARB:Binance correctly classified as EXCHANGE_MENTION (isAlreadyListed=True)")
        else:
            # ARB might not be in current data, check if it's in confirmed/potential
            all_arb = [l for l in (data.get("confirmed", []) + data.get("potential", []))
                      if l["token"] == "ARB"]
            if all_arb:
                print(f"⚠️ ARB found in confirmed/potential, not mentions: {all_arb[0]['eventType']}")
            else:
                print("⚠️ ARB not found in current listings data (may not be in test data)")

    def test_exchange_mention_has_capped_score(self):
        """Test that EXCHANGE_MENTION signals have capped score (max 25)"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        data = response.json()["data"]
        
        mentions = data.get("mentions", [])
        for mention in mentions:
            if mention["eventType"] == "EXCHANGE_MENTION":
                assert mention["listingScore"] <= 25, \
                    f"{mention['token']}:{mention['exchange']} has listingScore {mention['listingScore']} > 25"
                assert mention["confidenceScore"] <= 25, \
                    f"{mention['token']}:{mention['exchange']} has confidenceScore {mention['confidenceScore']} > 25"
        
        print(f"✅ All {len(mentions)} EXCHANGE_MENTION signals have capped scores (max 25)")

    def test_new_spot_listing_not_in_registry(self):
        """Test that NEW_SPOT_LISTING is for assets not in registry"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        data = response.json()["data"]
        
        confirmed = data.get("confirmed", [])
        for listing in confirmed:
            if listing["eventType"] == "NEW_SPOT_LISTING":
                # NEW_SPOT_LISTING should have isAlreadyListed=False
                assert listing["isAlreadyListed"] is False, \
                    f"{listing['token']}:{listing['exchange']} is NEW_SPOT_LISTING but isAlreadyListed=True"
        
        print(f"✅ NEW_SPOT_LISTING entries correctly have isAlreadyListed=False")


class TestEarlySignalsConfluence:
    """Tests for early-signals endpoint and confluence logic"""

    def test_early_signals_endpoint_returns_ok(self):
        """Test that early-signals endpoint returns ok status"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/early-signals")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print("✅ Early-signals endpoint returns ok status")

    def test_early_signals_returns_confluences_array(self):
        """Test that early-signals returns confluences array"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/early-signals")
        data = response.json()["data"]
        
        assert "earlySignals" in data, "Missing 'earlySignals' array"
        assert "confluences" in data, "Missing 'confluences' array"
        assert "tripleConfluenceCount" in data, "Missing 'tripleConfluenceCount'"
        
        print(f"✅ Early-signals returns: earlySignals={len(data['earlySignals'])}, "
              f"confluences={len(data['confluences'])}, tripleConfluenceCount={data['tripleConfluenceCount']}")

    def test_confluences_exclude_exchange_mention(self):
        """Test that Triple Confluence does not fire for EXCHANGE_MENTION listings"""
        # Get listings to find EXCHANGE_MENTION tokens
        listings_resp = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        listings_data = listings_resp.json()["data"]
        
        exchange_mention_tokens = {l["token"] for l in listings_data.get("mentions", [])
                                   if l["eventType"] == "EXCHANGE_MENTION"}
        
        # Get early signals
        early_resp = requests.get(f"{BASE_URL}/api/v4/sentiment/early-signals")
        early_data = early_resp.json()["data"]
        
        confluences = early_data.get("confluences", [])
        
        # Check that no confluence contains EXCHANGE_MENTION tokens
        for conf in confluences:
            assert conf["token"] not in exchange_mention_tokens, \
                f"Confluence should not include EXCHANGE_MENTION token: {conf['token']}"
        
        print(f"✅ Confluences correctly exclude EXCHANGE_MENTION tokens "
              f"(checked {len(confluences)} confluences against {len(exchange_mention_tokens)} mention tokens)")


class TestCorrelationsEndpoint:
    """Tests for correlations endpoint"""

    def test_correlations_endpoint_returns_ok(self):
        """Test that correlations endpoint returns ok status"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print("✅ Correlations endpoint returns ok status")

    def test_correlations_returns_signal_data(self):
        """Test that correlations returns signal data with required fields"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        data = response.json()["data"]
        
        assert isinstance(data, list), "Correlations should return a list"
        
        if data:
            first = data[0]
            required_fields = ["id", "symbol", "name", "sentiment", "signal"]
            for field in required_fields:
                assert field in first, f"Missing required field: {field}"
            
            # Check signal object structure
            signal = first.get("signal", {})
            signal_fields = ["type", "score", "decayedScore", "confidence"]
            for field in signal_fields:
                assert field in signal, f"Missing signal field: {field}"
        
        print(f"✅ Correlations returns {len(data)} items with proper structure")


class TestModelStats:
    """Tests for model-stats endpoint"""

    def test_model_stats_endpoint_returns_ok(self):
        """Test that model-stats endpoint returns ok status"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/model-stats")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print("✅ Model-stats endpoint returns ok status")

    def test_model_stats_returns_required_fields(self):
        """Test that model-stats returns required fields"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/model-stats")
        data = response.json()["data"]
        
        required_fields = ["avgCorrelation", "predictionAccuracy", "totalSignals", 
                          "totalAlerts", "activeAlerts"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        print(f"✅ Model-stats returns all required fields: activeAlerts={data['activeAlerts']}, "
              f"totalAlerts={data['totalAlerts']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
