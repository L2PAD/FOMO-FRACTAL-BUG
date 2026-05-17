"""
Test Suite: BLOCK A (Multi-Layer Influence Bars) and BLOCK B (Multi-Asset Ranking)

Tests for:
- V4 endpoint /api/market/chart/price-vs-expectation-v4 with 'explain' object
- Rankings endpoint /api/market/rankings/top

Requirements:
- BLOCK A: V4 endpoint should return 'explain' object with horizon, final, drivers
- BLOCK B: Rankings endpoint should return ok, items[], buys[], sells[], convictionScore
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBlockAExplainEndpoint:
    """BLOCK A: Test V4 endpoint returns explain object for model transparency"""
    
    def test_v4_endpoint_returns_ok(self):
        """V4 endpoint should return ok: true"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v4?asset=BTC&horizon=1D")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
    
    def test_v4_endpoint_returns_explain_object(self):
        """V4 endpoint should return 'explain' object"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v4?asset=BTC&horizon=1D")
        assert response.status_code == 200
        data = response.json()
        
        # Verify explain object exists
        assert "explain" in data, "explain object should be present in response"
        explain = data["explain"]
        
        # Verify explain structure
        assert "horizon" in explain, "explain should have horizon"
        assert "final" in explain, "explain should have final"
        assert "drivers" in explain, "explain should have drivers"
    
    def test_explain_horizon_matches_request(self):
        """Explain horizon should match the requested horizon"""
        for horizon in ['1D', '7D', '30D']:
            response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v4?asset=BTC&horizon={horizon}")
            data = response.json()
            explain = data.get("explain", {})
            assert explain.get("horizon") == horizon, f"explain.horizon should be {horizon}"
    
    def test_explain_final_structure(self):
        """Explain.final should contain action, confidence_raw, confidence_adj, expectedMovePct"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v4?asset=BTC&horizon=1D")
        data = response.json()
        final = data.get("explain", {}).get("final", {})
        
        assert "action" in final, "final should have action"
        assert final["action"] in ["BUY", "SELL", "HOLD", "AVOID"], "action should be BUY/SELL/HOLD/AVOID"
        
        assert "confidence_raw" in final, "final should have confidence_raw"
        assert 0 <= final["confidence_raw"] <= 1, "confidence_raw should be 0-1"
        
        assert "confidence_adj" in final, "final should have confidence_adj"
        assert 0 <= final["confidence_adj"] <= 1, "confidence_adj should be 0-1"
        
        assert "expectedMovePct" in final, "final should have expectedMovePct"
        assert isinstance(final["expectedMovePct"], (int, float)), "expectedMovePct should be numeric"
    
    def test_explain_drivers_layers(self):
        """Explain.drivers.layers should contain exchange, onchain, sentiment"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v4?asset=BTC&horizon=1D")
        data = response.json()
        drivers = data.get("explain", {}).get("drivers", {})
        
        assert "layers" in drivers, "drivers should have layers"
        layers = drivers["layers"]
        
        assert isinstance(layers, list), "layers should be a list"
        layer_keys = [l["key"] for l in layers]
        
        assert "exchange" in layer_keys, "layers should include exchange"
        assert "onchain" in layer_keys, "layers should include onchain"
        assert "sentiment" in layer_keys, "layers should include sentiment"
        
        # Check layer structure
        for layer in layers:
            assert "key" in layer, "layer should have key"
            assert "weight" in layer, "layer should have weight"
            assert 0 <= layer["weight"] <= 1, f"layer weight should be 0-1, got {layer['weight']}"
            
            # Check frozen layers have note
            if layer["weight"] == 0:
                assert layer.get("note") == "frozen", "frozen layers should have note='frozen'"
    
    def test_explain_drivers_overlays(self):
        """Explain.drivers.overlays should contain macro, funding, health adjustments"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v4?asset=BTC&horizon=1D")
        data = response.json()
        drivers = data.get("explain", {}).get("drivers", {})
        
        assert "overlays" in drivers, "drivers should have overlays"
        overlays = drivers["overlays"]
        
        assert isinstance(overlays, list), "overlays should be a list"
        overlay_keys = [o["key"] for o in overlays]
        
        # At least macro overlay should be present
        assert "macro" in overlay_keys, "overlays should include macro"
        
        # Check overlay structure
        for overlay in overlays:
            assert "key" in overlay, "overlay should have key"
            assert "delta" in overlay, "overlay should have delta"
            assert isinstance(overlay["delta"], (int, float)), "overlay delta should be numeric"
    
    def test_explain_drivers_top_signals(self):
        """Explain.drivers.topSignals should be present (may be empty)"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v4?asset=BTC&horizon=1D")
        data = response.json()
        drivers = data.get("explain", {}).get("drivers", {})
        
        assert "topSignals" in drivers, "drivers should have topSignals"
        top_signals = drivers["topSignals"]
        
        assert isinstance(top_signals, list), "topSignals should be a list"
        
        # If there are signals, check structure
        for signal in top_signals:
            assert "key" in signal, "signal should have key"
            assert "impact" in signal, "signal should have impact"
            assert isinstance(signal["impact"], (int, float)), "signal impact should be numeric"
    
    def test_v4_endpoint_different_assets(self):
        """V4 endpoint should work for different assets (BTC, ETH, SOL, BNB)"""
        for asset in ['BTC', 'ETH', 'SOL', 'BNB']:
            response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v4?asset={asset}&horizon=1D")
            assert response.status_code == 200, f"V4 endpoint failed for {asset}"
            data = response.json()
            assert data.get("ok") is True, f"V4 endpoint returned ok=false for {asset}"
            assert "explain" in data, f"explain object missing for {asset}"


class TestBlockBRankingsEndpoint:
    """BLOCK B: Test Rankings endpoint for multi-asset ranking"""
    
    def test_rankings_endpoint_returns_ok(self):
        """Rankings endpoint should return ok: true"""
        response = requests.get(f"{BASE_URL}/api/market/rankings/top?horizon=1D")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
    
    def test_rankings_endpoint_structure(self):
        """Rankings endpoint should return required fields"""
        response = requests.get(f"{BASE_URL}/api/market/rankings/top?horizon=1D")
        assert response.status_code == 200
        data = response.json()
        
        # Required fields per BLOCK B spec
        assert "ok" in data
        assert "items" in data
        assert "buys" in data
        assert "sells" in data
        
        # Additional metadata
        assert "generatedAt" in data
        assert "horizon" in data
        assert "universe" in data
        assert "count" in data
    
    def test_rankings_items_structure(self):
        """Rankings items should contain convictionScore and required fields"""
        response = requests.get(f"{BASE_URL}/api/market/rankings/top?horizon=1D")
        data = response.json()
        items = data.get("items", [])
        
        assert len(items) > 0, "items should not be empty"
        
        for item in items:
            assert "symbol" in item, "item should have symbol"
            assert "action" in item, "item should have action"
            assert item["action"] in ["BUY", "SELL", "HOLD", "AVOID"], "action should be valid"
            assert "convictionScore" in item, "item should have convictionScore"
            assert isinstance(item["convictionScore"], (int, float)), "convictionScore should be numeric"
            assert "adjustedConfidence" in item, "item should have adjustedConfidence"
            assert "expectedMovePct" in item, "item should have expectedMovePct"
            assert "risk" in item, "item should have risk"
            assert item["risk"] in ["LOW", "MEDIUM", "HIGH", "EXTREME"], "risk should be valid"
    
    def test_rankings_buys_and_sells_are_lists(self):
        """Buys and sells should be lists (may be empty)"""
        response = requests.get(f"{BASE_URL}/api/market/rankings/top?horizon=1D")
        data = response.json()
        
        assert isinstance(data.get("buys"), list), "buys should be a list"
        assert isinstance(data.get("sells"), list), "sells should be a list"
    
    def test_rankings_buys_only_contain_buy_actions(self):
        """Buys list should only contain BUY actions"""
        response = requests.get(f"{BASE_URL}/api/market/rankings/top?horizon=1D")
        data = response.json()
        buys = data.get("buys", [])
        
        for item in buys:
            assert item.get("action") == "BUY", f"buys list should only contain BUY, got {item.get('action')}"
    
    def test_rankings_sells_only_contain_sell_actions(self):
        """Sells list should only contain SELL actions"""
        response = requests.get(f"{BASE_URL}/api/market/rankings/top?horizon=1D")
        data = response.json()
        sells = data.get("sells", [])
        
        for item in sells:
            assert item.get("action") == "SELL", f"sells list should only contain SELL, got {item.get('action')}"
    
    def test_rankings_items_sorted_by_conviction(self):
        """Items should be sorted by convictionScore (descending)"""
        response = requests.get(f"{BASE_URL}/api/market/rankings/top?horizon=1D")
        data = response.json()
        items = data.get("items", [])
        
        if len(items) > 1:
            for i in range(len(items) - 1):
                assert items[i]["convictionScore"] >= items[i + 1]["convictionScore"], \
                    f"items not sorted by convictionScore: {items[i]['convictionScore']} < {items[i + 1]['convictionScore']}"
    
    def test_rankings_different_horizons(self):
        """Rankings endpoint should work for different horizons (1D, 7D, 30D)"""
        for horizon in ['1D', '7D', '30D']:
            response = requests.get(f"{BASE_URL}/api/market/rankings/top?horizon={horizon}")
            assert response.status_code == 200, f"Rankings endpoint failed for horizon={horizon}"
            data = response.json()
            assert data.get("ok") is True
            assert data.get("horizon") == horizon
    
    def test_rankings_invalid_horizon_returns_400(self):
        """Rankings endpoint should return 400 for invalid horizon"""
        response = requests.get(f"{BASE_URL}/api/market/rankings/top?horizon=INVALID")
        assert response.status_code == 400
        data = response.json()
        assert data.get("ok") is False
    
    def test_rankings_limit_parameter(self):
        """Rankings endpoint should respect limit parameter"""
        response = requests.get(f"{BASE_URL}/api/market/rankings/top?horizon=1D&limit=2")
        data = response.json()
        assert len(data.get("items", [])) <= 2, "limit parameter not respected"
    
    def test_rankings_type_filter_buy(self):
        """Rankings endpoint should filter by type=BUY"""
        response = requests.get(f"{BASE_URL}/api/market/rankings/top?horizon=1D&type=BUY")
        data = response.json()
        items = data.get("items", [])
        
        for item in items:
            assert item.get("action") == "BUY", f"type=BUY filter not working, got {item.get('action')}"
    
    def test_rankings_type_filter_sell(self):
        """Rankings endpoint should filter by type=SELL"""
        response = requests.get(f"{BASE_URL}/api/market/rankings/top?horizon=1D&type=SELL")
        data = response.json()
        items = data.get("items", [])
        
        for item in items:
            assert item.get("action") == "SELL", f"type=SELL filter not working, got {item.get('action')}"


class TestBlockABIntegration:
    """Integration tests for BLOCK A and BLOCK B working together"""
    
    def test_v4_and_rankings_return_same_assets(self):
        """V4 and Rankings endpoints should return data for the same universe of assets"""
        # Get rankings to see available assets
        rankings_response = requests.get(f"{BASE_URL}/api/market/rankings/top?horizon=1D")
        rankings_data = rankings_response.json()
        rankings_assets = [item["symbol"] for item in rankings_data.get("items", [])]
        
        # Verify V4 works for each asset
        for asset in rankings_assets:
            v4_response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v4?asset={asset}&horizon=1D")
            assert v4_response.status_code == 200, f"V4 failed for asset {asset}"
            v4_data = v4_response.json()
            assert v4_data.get("ok") is True
            assert "explain" in v4_data
    
    def test_confidence_values_consistent(self):
        """Confidence values in V4 explain and Rankings should be consistent for same asset"""
        # Get rankings for reference
        rankings_response = requests.get(f"{BASE_URL}/api/market/rankings/top?horizon=1D")
        rankings_data = rankings_response.json()
        
        for item in rankings_data.get("items", []):
            asset = item["symbol"]
            rankings_confidence = item["adjustedConfidence"]
            
            # Get V4 explain confidence
            v4_response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v4?asset={asset}&horizon=1D")
            v4_data = v4_response.json()
            v4_confidence = v4_data.get("explain", {}).get("final", {}).get("confidence_adj", 0)
            
            # Allow small tolerance for floating point differences
            assert abs(rankings_confidence - v4_confidence) < 0.01, \
                f"Confidence mismatch for {asset}: rankings={rankings_confidence}, v4={v4_confidence}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
