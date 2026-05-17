"""
OTC Detection and Market Maker Detection API Tests
Tests for /api/intelligence/otc and /api/intelligence/market-makers endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestOTCDetection:
    """OTC Detection endpoint tests - /api/intelligence/otc"""

    def test_otc_endpoint_returns_200(self):
        """OTC endpoint returns 200 status code"""
        response = requests.get(f"{BASE_URL}/api/intelligence/otc", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: OTC endpoint returns 200")

    def test_otc_response_has_correct_structure(self):
        """OTC response has required fields: ok, trades, count, threshold_usd"""
        response = requests.get(f"{BASE_URL}/api/intelligence/otc", timeout=30)
        data = response.json()
        
        assert "ok" in data, "Response missing 'ok' field"
        assert data["ok"] is True, f"Expected ok=True, got {data['ok']}"
        assert "trades" in data, "Response missing 'trades' field"
        assert "count" in data, "Response missing 'count' field"
        assert "threshold_usd" in data, "Response missing 'threshold_usd' field"
        assert isinstance(data["trades"], list), "trades should be a list"
        assert isinstance(data["count"], int), "count should be an integer"
        assert data["threshold_usd"] == 1000000, f"Expected threshold_usd=1000000, got {data['threshold_usd']}"
        print(f"PASS: OTC response structure correct - {data['count']} trades detected")

    def test_otc_trades_have_required_fields(self):
        """Each OTC trade has required fields"""
        response = requests.get(f"{BASE_URL}/api/intelligence/otc", timeout=30)
        data = response.json()
        
        if data["count"] > 0:
            trade = data["trades"][0]
            required_fields = [
                "trade_id", "asset", "stablecoin", "seller_entity", "buyer_entity",
                "usd_value", "usd_value_fmt", "confidence", "signals", "source_entity"
            ]
            for field in required_fields:
                assert field in trade, f"Trade missing required field: {field}"
            
            # Validate signals structure
            assert "signals" in trade, "Trade missing signals"
            signals = trade["signals"]
            signal_keys = ["value_match", "time_proximity", "cluster_distance", "liquidity"]
            for key in signal_keys:
                assert key in signals, f"Signals missing {key}"
            
            print(f"PASS: OTC trade structure correct - {trade['asset']} <-> {trade['stablecoin']}")
        else:
            print("INFO: No OTC trades to validate structure")

    def test_otc_filtered_by_entity(self):
        """OTC endpoint returns filtered trades for specific entity"""
        response = requests.get(f"{BASE_URL}/api/intelligence/otc?entity=binance", timeout=30)
        data = response.json()
        
        assert response.status_code == 200
        assert data["ok"] is True
        assert "entity_filter" in data, "Response missing 'entity_filter' field"
        assert data["entity_filter"] == "binance", f"Expected entity_filter='binance', got {data['entity_filter']}"
        
        # If trades exist, verify they are for binance entity
        if data["count"] > 0:
            for trade in data["trades"]:
                assert trade["source_entity"] == "binance", f"Trade source_entity should be 'binance', got {trade['source_entity']}"
        
        print(f"PASS: OTC entity filter works - binance filter returned {data['count']} trades")

    def test_otc_nonexistent_entity_returns_empty(self):
        """OTC endpoint returns empty trades for nonexistent entity"""
        response = requests.get(f"{BASE_URL}/api/intelligence/otc?entity=nonexistent_entity_xyz", timeout=30)
        data = response.json()
        
        assert response.status_code == 200
        assert data["ok"] is True
        assert data["count"] == 0, f"Expected count=0 for nonexistent entity, got {data['count']}"
        print("PASS: OTC nonexistent entity returns empty trades")


class TestMarketMakerDetection:
    """Market Maker Detection endpoint tests - /api/intelligence/market-makers"""

    def test_market_makers_endpoint_returns_200(self):
        """Market Makers endpoint returns 200 status code"""
        response = requests.get(f"{BASE_URL}/api/intelligence/market-makers", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: Market Makers endpoint returns 200")

    def test_market_makers_response_has_correct_structure(self):
        """Market Makers response has required fields: ok, market_makers, count, threshold"""
        response = requests.get(f"{BASE_URL}/api/intelligence/market-makers", timeout=30)
        data = response.json()
        
        assert "ok" in data, "Response missing 'ok' field"
        assert data["ok"] is True, f"Expected ok=True, got {data['ok']}"
        assert "market_makers" in data, "Response missing 'market_makers' field"
        assert "count" in data, "Response missing 'count' field"
        assert "threshold" in data, "Response missing 'threshold' field"
        assert "total_entities_scanned" in data, "Response missing 'total_entities_scanned' field"
        assert isinstance(data["market_makers"], list), "market_makers should be a list"
        assert isinstance(data["count"], int), "count should be an integer"
        assert data["threshold"] == 0.5, f"Expected threshold=0.5, got {data['threshold']}"
        print(f"PASS: Market Makers response structure correct - {data['count']} MMs detected out of {data['total_entities_scanned']} scanned")

    def test_market_makers_have_required_fields(self):
        """Each market maker detection has required fields"""
        response = requests.get(f"{BASE_URL}/api/intelligence/market-makers", timeout=30)
        data = response.json()
        
        if data["count"] > 0:
            mm = data["market_makers"][0]
            required_fields = [
                "entity", "name", "entity_type", "type", "score", "signals", "details"
            ]
            for field in required_fields:
                assert field in mm, f"Market maker missing required field: {field}"
            
            # Validate type is one of expected values
            valid_types = ["market_maker", "probable_mm", "unlikely"]
            assert mm["type"] in valid_types, f"MM type should be one of {valid_types}, got {mm['type']}"
            
            # Validate score is between 0 and 1
            assert 0 <= mm["score"] <= 1, f"MM score should be 0-1, got {mm['score']}"
            
            # Validate signals structure
            signals = mm["signals"]
            signal_keys = ["bidirectional_flow", "exchange_density", "stablecoin_recycling", "velocity"]
            for key in signal_keys:
                assert key in signals, f"MM signals missing {key}"
            
            # Validate details structure
            details = mm["details"]
            detail_keys = ["volume_usd", "inflow_outflow_ratio", "venue_count", "stablecoin_dependency"]
            for key in detail_keys:
                assert key in details, f"MM details missing {key}"
            
            print(f"PASS: Market Maker structure correct - {mm['name']} ({mm['type']}) score={mm['score']}")
        else:
            print("INFO: No market makers to validate structure")

    def test_market_makers_sorted_by_score_descending(self):
        """Market makers are sorted by score in descending order"""
        response = requests.get(f"{BASE_URL}/api/intelligence/market-makers", timeout=30)
        data = response.json()
        
        if data["count"] > 1:
            scores = [mm["score"] for mm in data["market_makers"]]
            assert scores == sorted(scores, reverse=True), "Market makers should be sorted by score descending"
            print(f"PASS: Market Makers sorted by score - scores: {scores}")
        else:
            print("INFO: Not enough market makers to test sorting")

    def test_market_makers_above_threshold(self):
        """All returned market makers have score >= threshold"""
        response = requests.get(f"{BASE_URL}/api/intelligence/market-makers", timeout=30)
        data = response.json()
        
        threshold = data["threshold"]
        for mm in data["market_makers"]:
            assert mm["score"] >= threshold, f"MM {mm['entity']} has score {mm['score']} below threshold {threshold}"
        
        print(f"PASS: All {data['count']} market makers have score >= {threshold}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
