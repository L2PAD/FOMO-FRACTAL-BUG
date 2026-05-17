"""
Exchange Chart V3 Forecast Window & Stability Tests
=====================================================
Tests for:
1. Forecast Window filtering (7D=7d, 30D=21d)
2. Target Normalization (expectedMovePct)
3. Forecast Stability Indicator (stable/moderate/unstable)
4. Response structure validation
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestExchangeChartV3ForecastWindow:
    """Verify forecast window filtering returns fewer forecasts due to age filter"""

    def test_7d_returns_7_or_fewer_future_points(self):
        """7D horizon should return 7 or fewer futurePoints (max 7 days old forecasts)"""
        response = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert len(data["futurePoints"]) <= 7, f"7D should have ≤7 futurePoints, got {len(data['futurePoints'])}"

    def test_30d_returns_30_or_fewer_future_points(self):
        """30D horizon should return ≤30 futurePoints (filtered by 21-day window)"""
        response = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=30D")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert len(data["futurePoints"]) <= 30, f"30D should have ≤30 futurePoints, got {len(data['futurePoints'])}"

    def test_1d_returns_1_or_fewer_future_points(self):
        """1D horizon should return 1 or fewer futurePoints (max 2 days old forecasts)"""
        response = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=1D")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert len(data["futurePoints"]) <= 1, f"1D should have ≤1 futurePoints, got {len(data['futurePoints'])}"


class TestExchangeChartV3TargetNormalization:
    """Verify normalized target prices are close to current price (no wild jumps)"""

    def test_7d_normalized_targets_near_current_price(self):
        """7D normalized targets should be within 20% of current price"""
        response = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D")
        assert response.status_code == 200
        data = response.json()
        current_price = data["entryPrice"]
        
        for point in data["futurePoints"]:
            target = point["targetPrice"]
            deviation_pct = abs(target - current_price) / current_price * 100
            assert deviation_pct <= 20, f"Target {target} deviates {deviation_pct:.1f}% from current {current_price}"

    def test_30d_normalized_targets_near_current_price(self):
        """30D normalized targets should be within 20% of current price"""
        response = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=30D")
        assert response.status_code == 200
        data = response.json()
        current_price = data["entryPrice"]
        
        for point in data["futurePoints"]:
            target = point["targetPrice"]
            deviation_pct = abs(target - current_price) / current_price * 100
            assert deviation_pct <= 20, f"Target {target} deviates {deviation_pct:.1f}% from current {current_price}"

    def test_target_field_is_normalized(self):
        """Main target field should also be normalized (close to current price)"""
        response = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D")
        assert response.status_code == 200
        data = response.json()
        current_price = data["entryPrice"]
        target = data["target"]
        
        deviation_pct = abs(target - current_price) / current_price * 100
        assert deviation_pct <= 20, f"Main target {target} should be near current price {current_price}"


class TestExchangeChartV3StabilityIndicator:
    """Test Forecast Stability indicator (stddev of last 7 expectedMovePct values)"""

    def test_7d_stability_field_present(self):
        """meta.stability field should be present and valid"""
        response = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D")
        assert response.status_code == 200
        data = response.json()
        
        assert "meta" in data
        assert "stability" in data["meta"]
        assert data["meta"]["stability"] in ["stable", "moderate", "unstable", "unknown"]

    def test_30d_stability_field_present(self):
        """meta.stability field should be present for 30D horizon"""
        response = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=30D")
        assert response.status_code == 200
        data = response.json()
        
        assert "meta" in data
        assert "stability" in data["meta"]
        assert data["meta"]["stability"] in ["stable", "moderate", "unstable", "unknown"]

    def test_stability_stddev_is_number(self):
        """meta.stabilityStddev should be a number"""
        response = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D")
        assert response.status_code == 200
        data = response.json()
        
        assert "stabilityStddev" in data["meta"]
        assert isinstance(data["meta"]["stabilityStddev"], (int, float))
        assert data["meta"]["stabilityStddev"] >= 0, "stabilityStddev should be non-negative"

    def test_stability_label_matches_stddev_thresholds(self):
        """Stability label should match stddev thresholds: stable<1.5, moderate<3, unstable>=3"""
        response = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D")
        assert response.status_code == 200
        data = response.json()
        
        stddev = data["meta"]["stabilityStddev"]
        label = data["meta"]["stability"]
        
        if label == "stable":
            assert stddev < 1.5, f"stable label but stddev={stddev}"
        elif label == "moderate":
            assert 1.5 <= stddev < 3, f"moderate label but stddev={stddev}"
        elif label == "unstable":
            assert stddev >= 3, f"unstable label but stddev={stddev}"
        # 'unknown' is valid when not enough data


class TestExchangeChartV3Volatility:
    """Test volatility field from real candles"""

    def test_volatility_field_present(self):
        """volatility field should be present in response"""
        response = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D")
        assert response.status_code == 200
        data = response.json()
        
        assert "volatility" in data
        assert isinstance(data["volatility"], (int, float))

    def test_volatility_is_positive(self):
        """volatility should be a positive number"""
        response = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D")
        assert response.status_code == 200
        data = response.json()
        
        assert data["volatility"] > 0, f"volatility should be > 0, got {data['volatility']}"

    def test_volatility_reasonable_range(self):
        """volatility should be in reasonable range (0.001 to 0.5 for daily)"""
        response = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D")
        assert response.status_code == 200
        data = response.json()
        
        vol = data["volatility"]
        assert 0.001 <= vol <= 0.5, f"volatility {vol} outside reasonable range [0.001, 0.5]"


class TestExchangeChartV3FuturePointsSorting:
    """Test futurePoints are sorted ascending by targetDateTs"""

    def test_7d_future_points_sorted_ascending(self):
        """futurePoints should be sorted ascending by targetDateTs"""
        response = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D")
        assert response.status_code == 200
        data = response.json()
        
        points = data["futurePoints"]
        if len(points) > 1:
            for i in range(1, len(points)):
                assert points[i]["targetDateTs"] >= points[i-1]["targetDateTs"], \
                    f"futurePoints not sorted: {points[i-1]['targetDateTs']} > {points[i]['targetDateTs']}"

    def test_30d_future_points_sorted_ascending(self):
        """30D futurePoints should be sorted ascending by targetDateTs"""
        response = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=30D")
        assert response.status_code == 200
        data = response.json()
        
        points = data["futurePoints"]
        if len(points) > 1:
            for i in range(1, len(points)):
                assert points[i]["targetDateTs"] >= points[i-1]["targetDateTs"], \
                    f"futurePoints not sorted: {points[i-1]['targetDateTs']} > {points[i]['targetDateTs']}"


class TestExchangeChartV3ResponseStructure:
    """Test complete response structure"""

    def test_all_required_fields_present(self):
        """Response should contain all required fields"""
        response = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D")
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ["ok", "symbol", "nowTs", "entryPrice", "realCandles", 
                          "futurePoints", "prevFuturePoints", "target", "confidence",
                          "direction", "source", "volatility", "meta"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

    def test_meta_contains_stability_fields(self):
        """meta should contain stability and stabilityStddev fields"""
        response = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D")
        assert response.status_code == 200
        data = response.json()
        
        meta_fields = ["regime", "totalForecasts", "uniqueTargetDates", 
                      "anomaliesFiltered", "stability", "stabilityStddev"]
        for field in meta_fields:
            assert field in data["meta"], f"Missing meta field: {field}"

    def test_future_point_structure(self):
        """Each futurePoint should have required fields"""
        response = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D")
        assert response.status_code == 200
        data = response.json()
        
        if data["futurePoints"]:
            point = data["futurePoints"][0]
            required = ["targetDateTs", "targetPrice", "madeAtTs", "confidence", "direction"]
            for field in required:
                assert field in point, f"Missing futurePoint field: {field}"


class TestExchangeChartV3HorizonDifferences:
    """Test that different horizons return different data"""

    def test_7d_and_30d_return_different_future_points_count(self):
        """7D and 30D should return different number of futurePoints"""
        resp_7d = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D")
        resp_30d = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=30D")
        
        assert resp_7d.status_code == 200
        assert resp_30d.status_code == 200
        
        data_7d = resp_7d.json()
        data_30d = resp_30d.json()
        
        # 30D should generally have more or equal points due to longer window
        assert data_30d["meta"]["uniqueTargetDates"] >= data_7d["meta"]["uniqueTargetDates"] or \
               data_30d["meta"]["totalForecasts"] >= data_7d["meta"]["totalForecasts"], \
               "30D should have >= forecasts than 7D"

    def test_different_horizons_return_same_current_price(self):
        """All horizons should return approximately the same current price"""
        resp_7d = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D")
        resp_30d = requests.get(f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=30D")
        
        assert resp_7d.status_code == 200
        assert resp_30d.status_code == 200
        
        data_7d = resp_7d.json()
        data_30d = resp_30d.json()
        
        # Entry prices should be very close (within 1% due to market movement during requests)
        deviation = abs(data_7d["entryPrice"] - data_30d["entryPrice"]) / data_7d["entryPrice"] * 100
        assert deviation < 1, f"Entry prices differ by {deviation:.2f}%"
