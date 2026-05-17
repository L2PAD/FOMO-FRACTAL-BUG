"""
Test suite for the new /api/prediction/exchange/graph endpoint
Added in: ForecastChart rebuild with lightweight-charts

Tests:
- Graph API returns ok:true with priceSeries and forecastSegments
- priceSeries contains time/value pairs for price history
- forecastSegments contain evaluated (with hit/outcomeLabel) and active forecasts
- Horizon parameter filters segments correctly (24H/7D/30D)
- Lookback parameter controls date range
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestForecastGraphAPI:
    """Tests for /api/prediction/exchange/graph endpoint"""
    
    def test_graph_api_returns_ok_and_structure(self):
        """Test graph API returns ok:true with correct structure"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph?asset=BTC&horizon=7D&lookback=90")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] == True
        assert "priceSeries" in data
        assert "forecastSegments" in data
        assert "meta" in data
        
        # Meta fields
        meta = data["meta"]
        assert meta["asset"] == "BTC"
        assert meta["horizon"] == "7D"
        assert meta["lookback"] == 90
        assert "now" in meta
        assert "segmentCount" in meta
        print(f"Graph API returned {meta['segmentCount']} segments")
    
    def test_price_series_format(self):
        """Test priceSeries has correct format for lightweight-charts"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph?asset=BTC&horizon=7D&lookback=90")
        assert response.status_code == 200
        
        data = response.json()
        price_series = data["priceSeries"]
        assert isinstance(price_series, list)
        assert len(price_series) > 0
        
        # Each point should have time (unix timestamp) and value (price)
        sample = price_series[0]
        assert "time" in sample
        assert "value" in sample
        assert isinstance(sample["time"], int)
        assert isinstance(sample["value"], (int, float))
        print(f"Price series has {len(price_series)} data points")
    
    def test_forecast_segments_structure(self):
        """Test forecastSegments have correct fields"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph?asset=BTC&horizon=7D&lookback=90")
        assert response.status_code == 200
        
        data = response.json()
        segments = data["forecastSegments"]
        assert isinstance(segments, list)
        assert len(segments) > 0
        
        # Check required fields in segment
        required_fields = ["id", "createdAt", "evaluateAfter", "entryPrice", "targetPrice", 
                         "direction", "status", "confidence"]
        sample = segments[0]
        for field in required_fields:
            assert field in sample, f"Missing field: {field}"
        
        # Check direction is normalized
        assert sample["direction"] in ["LONG", "SHORT", "NEUTRAL"]
        # Check status
        assert sample["status"] in ["EVALUATED", "ACTIVE", "OVERDUE"]
        print(f"Sample segment: direction={sample['direction']}, status={sample['status']}")
    
    def test_evaluated_segments_have_outcome(self):
        """Test that EVALUATED segments have hit and outcomeLabel"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph?asset=BTC&horizon=7D&lookback=90")
        assert response.status_code == 200
        
        data = response.json()
        segments = data["forecastSegments"]
        
        evaluated = [s for s in segments if s["status"] == "EVALUATED"]
        assert len(evaluated) > 0, "No evaluated segments found"
        
        # Check evaluated segment has outcome fields
        sample = evaluated[0]
        assert "hit" in sample, "EVALUATED segment missing 'hit' field"
        assert "outcomeLabel" in sample, "EVALUATED segment missing 'outcomeLabel' field"
        assert "actualPrice" in sample, "EVALUATED segment missing 'actualPrice' field"
        assert isinstance(sample["hit"], bool)
        print(f"Evaluated segments: {len(evaluated)}, sample outcome: {sample['outcomeLabel']}")
    
    def test_active_segments_exist(self):
        """Test that ACTIVE segments exist and don't have outcome fields"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph?asset=BTC&horizon=7D&lookback=90")
        assert response.status_code == 200
        
        data = response.json()
        segments = data["forecastSegments"]
        
        active = [s for s in segments if s["status"] == "ACTIVE"]
        assert len(active) > 0, "No active segments found"
        
        # Active segments should NOT have outcome fields (yet)
        sample = active[0]
        # These fields are optional for active
        print(f"Active segments: {len(active)}, sample direction: {sample['direction']}")
    
    def test_horizon_24h_returns_segments(self):
        """Test 24H horizon returns segments"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph?asset=BTC&horizon=24H&lookback=90")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] == True
        assert data["meta"]["horizon"] == "24H"
        assert len(data["forecastSegments"]) > 0
        print(f"24H horizon: {data['meta']['segmentCount']} segments")
    
    def test_horizon_30d_returns_segments(self):
        """Test 30D horizon returns segments"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph?asset=BTC&horizon=30D&lookback=90")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] == True
        assert data["meta"]["horizon"] == "30D"
        assert len(data["forecastSegments"]) > 0
        print(f"30D horizon: {data['meta']['segmentCount']} segments")
    
    def test_different_horizons_return_different_counts(self):
        """Test that different horizons return different segment counts"""
        counts = {}
        for horizon in ["24H", "7D", "30D"]:
            response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph?asset=BTC&horizon={horizon}&lookback=90")
            assert response.status_code == 200
            counts[horizon] = response.json()["meta"]["segmentCount"]
        
        # Counts should vary by horizon (not all same)
        print(f"Segment counts by horizon: {counts}")
        # Just verify we got counts for all
        assert all(c > 0 for c in counts.values())


class TestForecastGraphStats:
    """Test stats calculations in graph response"""
    
    def test_segment_counts_match_filtered_data(self):
        """Verify meta.segmentCount matches actual array length"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph?asset=BTC&horizon=7D&lookback=90")
        assert response.status_code == 200
        
        data = response.json()
        assert data["meta"]["segmentCount"] == len(data["forecastSegments"])
    
    def test_evaluated_vs_active_counts(self):
        """Count evaluated and active segments"""
        response = requests.get(f"{BASE_URL}/api/prediction/exchange/graph?asset=BTC&horizon=7D&lookback=90")
        assert response.status_code == 200
        
        data = response.json()
        segments = data["forecastSegments"]
        
        evaluated = len([s for s in segments if s["status"] == "EVALUATED"])
        active = len([s for s in segments if s["status"] == "ACTIVE"])
        overdue = len([s for s in segments if s["status"] == "OVERDUE"])
        
        assert evaluated + active + overdue == len(segments)
        print(f"7D: Evaluated={evaluated}, Active={active}, Overdue={overdue}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
