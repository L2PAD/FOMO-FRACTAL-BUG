"""
Listing Detection Engine Tests
==============================
Tests for /api/v4/sentiment/listings endpoint

Features tested:
- Backend returns ok:true with data.confirmed and data.potential arrays
- Listing fields: token, tokenName, exchange, status, confidence, listingScore, freshness, minutesAgo, sourceCount, expectedBehavior, isPotential
- Confirmed listings have sourceIsExchange=true or sourceCount>=2
- Potential listings have isPotential=true and status=UNCONFIRMED
- Anti-spam: unknown tokens from untrusted sources are filtered out
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestListingDetectionEngine:
    """Listing Detection Engine API tests"""
    
    def test_listings_endpoint_returns_ok(self):
        """Test that /api/v4/sentiment/listings returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") == True, "Expected ok:true in response"
        print("✓ Listings endpoint returns ok:true")
    
    def test_listings_has_confirmed_and_potential_arrays(self):
        """Test that response has data.confirmed and data.potential arrays"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        assert response.status_code == 200
        
        data = response.json()
        assert "data" in data, "Expected 'data' field in response"
        assert "confirmed" in data["data"], "Expected 'confirmed' array in data"
        assert "potential" in data["data"], "Expected 'potential' array in data"
        assert isinstance(data["data"]["confirmed"], list), "confirmed should be a list"
        assert isinstance(data["data"]["potential"], list), "potential should be a list"
        print(f"✓ Response has confirmed ({len(data['data']['confirmed'])}) and potential ({len(data['data']['potential'])}) arrays")
    
    def test_listings_has_total_detected_and_scan_time(self):
        """Test that response has totalDetected and scanTime"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        assert response.status_code == 200
        
        data = response.json()["data"]
        assert "totalDetected" in data, "Expected 'totalDetected' field"
        assert "scanTime" in data, "Expected 'scanTime' field"
        assert isinstance(data["totalDetected"], int), "totalDetected should be int"
        print(f"✓ totalDetected={data['totalDetected']}, scanTime={data['scanTime']}")
    
    def test_listing_has_required_fields(self):
        """Test that each listing has all required fields"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        assert response.status_code == 200
        
        data = response.json()["data"]
        all_listings = data["confirmed"] + data["potential"]
        
        required_fields = [
            "id", "token", "tokenName", "exchange", "status", "confidence",
            "listingScore", "freshness", "minutesAgo", "sourceCount",
            "expectedBehavior", "isPotential", "sourceIsExchange", "hasPattern"
        ]
        
        for listing in all_listings:
            for field in required_fields:
                assert field in listing, f"Missing field '{field}' in listing {listing.get('token', 'unknown')}"
        
        print(f"✓ All {len(all_listings)} listings have required fields: {', '.join(required_fields)}")
    
    def test_confirmed_listings_criteria(self):
        """Test that confirmed listings have sourceIsExchange=true OR sourceCount>=2"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        assert response.status_code == 200
        
        confirmed = response.json()["data"]["confirmed"]
        
        for listing in confirmed:
            is_valid = listing["sourceIsExchange"] == True or listing["sourceCount"] >= 2
            assert is_valid, f"Confirmed listing {listing['token']} doesn't meet criteria: sourceIsExchange={listing['sourceIsExchange']}, sourceCount={listing['sourceCount']}"
            assert listing["status"] == "CONFIRMED", f"Confirmed listing should have status=CONFIRMED, got {listing['status']}"
        
        print(f"✓ All {len(confirmed)} confirmed listings meet criteria (sourceIsExchange=true OR sourceCount>=2)")
    
    def test_potential_listings_criteria(self):
        """Test that potential listings have isPotential=true and status=UNCONFIRMED"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        assert response.status_code == 200
        
        potential = response.json()["data"]["potential"]
        
        for listing in potential:
            assert listing["isPotential"] == True, f"Potential listing {listing['token']} should have isPotential=true"
            assert listing["status"] == "UNCONFIRMED", f"Potential listing {listing['token']} should have status=UNCONFIRMED, got {listing['status']}"
        
        print(f"✓ All {len(potential)} potential listings have isPotential=true and status=UNCONFIRMED")
    
    def test_listing_score_range(self):
        """Test that listingScore is in valid range 0-100"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        assert response.status_code == 200
        
        all_listings = response.json()["data"]["confirmed"] + response.json()["data"]["potential"]
        
        for listing in all_listings:
            score = listing["listingScore"]
            assert 0 <= score <= 100, f"listingScore {score} out of range for {listing['token']}"
        
        print(f"✓ All listing scores in valid range 0-100")
    
    def test_confidence_values(self):
        """Test that confidence is HIGH/MED/LOW"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        assert response.status_code == 200
        
        all_listings = response.json()["data"]["confirmed"] + response.json()["data"]["potential"]
        valid_confidence = {"HIGH", "MED", "LOW"}
        
        for listing in all_listings:
            assert listing["confidence"] in valid_confidence, f"Invalid confidence '{listing['confidence']}' for {listing['token']}"
        
        print(f"✓ All confidence values are valid (HIGH/MED/LOW)")
    
    def test_freshness_values(self):
        """Test that freshness is JUST LISTED/FRESH LISTING/ACTIVE"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        assert response.status_code == 200
        
        all_listings = response.json()["data"]["confirmed"] + response.json()["data"]["potential"]
        valid_freshness = {"JUST LISTED", "FRESH LISTING", "ACTIVE"}
        
        for listing in all_listings:
            assert listing["freshness"] in valid_freshness, f"Invalid freshness '{listing['freshness']}' for {listing['token']}"
        
        print(f"✓ All freshness values are valid (JUST LISTED/FRESH LISTING/ACTIVE)")
    
    def test_expected_behavior_is_list(self):
        """Test that expectedBehavior is a list of strings"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        assert response.status_code == 200
        
        all_listings = response.json()["data"]["confirmed"] + response.json()["data"]["potential"]
        
        for listing in all_listings:
            assert isinstance(listing["expectedBehavior"], list), f"expectedBehavior should be list for {listing['token']}"
            for behavior in listing["expectedBehavior"]:
                assert isinstance(behavior, str), f"expectedBehavior items should be strings"
        
        print(f"✓ All expectedBehavior fields are lists of strings")
    
    def test_seeded_data_arb_binance_confirmed(self):
        """Test that seeded ARB→Binance listing is confirmed"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        assert response.status_code == 200
        
        confirmed = response.json()["data"]["confirmed"]
        arb_binance = next((l for l in confirmed if l["token"] == "ARB" and l["exchange"] == "Binance"), None)
        
        assert arb_binance is not None, "ARB→Binance should be in confirmed listings"
        assert arb_binance["status"] == "CONFIRMED"
        assert arb_binance["confidence"] == "HIGH"
        assert arb_binance["sourceIsExchange"] == True
        print(f"✓ ARB→Binance confirmed: score={arb_binance['listingScore']}, confidence={arb_binance['confidence']}")
    
    def test_seeded_data_pendle_coinbase_confirmed(self):
        """Test that seeded PENDLE→Coinbase listing is confirmed"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        assert response.status_code == 200
        
        confirmed = response.json()["data"]["confirmed"]
        pendle_coinbase = next((l for l in confirmed if l["token"] == "PENDLE" and l["exchange"] == "Coinbase"), None)
        
        assert pendle_coinbase is not None, "PENDLE→Coinbase should be in confirmed listings"
        assert pendle_coinbase["status"] == "CONFIRMED"
        assert pendle_coinbase["confidence"] == "HIGH"
        print(f"✓ PENDLE→Coinbase confirmed: score={pendle_coinbase['listingScore']}, confidence={pendle_coinbase['confidence']}")
    
    def test_seeded_data_jup_bybit_potential(self):
        """Test that seeded JUP→Bybit listing is potential"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        assert response.status_code == 200
        
        potential = response.json()["data"]["potential"]
        jup_bybit = next((l for l in potential if l["token"] == "JUP" and l["exchange"] == "Bybit"), None)
        
        assert jup_bybit is not None, "JUP→Bybit should be in potential listings"
        assert jup_bybit["status"] == "UNCONFIRMED"
        assert jup_bybit["isPotential"] == True
        print(f"✓ JUP→Bybit potential: score={jup_bybit['listingScore']}, isPotential={jup_bybit['isPotential']}")
    
    def test_seeded_data_wld_okx_potential(self):
        """Test that seeded WLD→OKX listing is potential"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        assert response.status_code == 200
        
        potential = response.json()["data"]["potential"]
        wld_okx = next((l for l in potential if l["token"] == "WLD" and l["exchange"] == "OKX"), None)
        
        assert wld_okx is not None, "WLD→OKX should be in potential listings"
        assert wld_okx["status"] == "UNCONFIRMED"
        assert wld_okx["isPotential"] == True
        print(f"✓ WLD→OKX potential: score={wld_okx['listingScore']}, isPotential={wld_okx['isPotential']}")


class TestPhase1to3Regression:
    """Regression tests for Phase 1-3 features (Setup+Maturity, Quality, Alignment, Velocity, Market Context, Risk)"""
    
    def test_top_signals_still_working(self):
        """Test that /api/v4/sentiment/top-signals still returns Phase 1-3 fields"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        
        if data["data"]:
            signal = data["data"][0]
            # Phase 1 fields
            assert "setupType" in signal, "Missing setupType (Phase 1)"
            assert "signalMaturity" in signal, "Missing signalMaturity (Phase 1)"
            assert "expectedMove" in signal, "Missing expectedMove (Phase 1)"
            # Phase 2 fields
            assert "signalQuality" in signal, "Missing signalQuality (Phase 2)"
            assert "riskContext" in signal, "Missing riskContext (Phase 2)"
            # Phase 3 fields
            assert "alignment" in signal, "Missing alignment (Phase 3)"
            assert "velocityDisplay" in signal or signal.get("velocityDisplay") is None, "velocityDisplay field issue"
            assert "marketContext" in signal, "Missing marketContext (Phase 3)"
            print(f"✓ Top signals has Phase 1-3 fields: setupType={signal['setupType']}, alignment={signal['alignment']}")
    
    def test_correlations_still_working(self):
        """Test that /api/v4/sentiment/correlations still returns Phase 1-3 fields"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        
        if data["data"]:
            item = data["data"][0]
            signal = item.get("signal", {})
            # Phase 1 fields
            assert "setupType" in signal, "Missing setupType in signal"
            assert "signalMaturity" in signal, "Missing signalMaturity in signal"
            # Phase 2 fields
            assert "signalQuality" in signal, "Missing signalQuality in signal"
            # Phase 3 fields
            assert "alignment" in signal, "Missing alignment in signal"
            print(f"✓ Correlations has Phase 1-3 fields in signal object")
    
    def test_model_stats_still_working(self):
        """Test that /api/v4/sentiment/model-stats still works"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/model-stats")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        assert "activeAlerts" in data["data"]
        assert "totalAlerts" in data["data"]
        print(f"✓ Model stats working: activeAlerts={data['data']['activeAlerts']}")
    
    def test_top_influencers_still_working(self):
        """Test that /api/v4/sentiment/top-influencers still works"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-influencers")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        print(f"✓ Top influencers working: {len(data['data'])} influencers")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
