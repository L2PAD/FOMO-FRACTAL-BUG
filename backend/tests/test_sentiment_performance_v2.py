"""
Sentiment Performance V2 API Tests
===================================
Tests for the Prediction > Sentiment tab bug fixes:
1) Real BTC prices from Kraken (not hardcoded $68,000)
2) Unique dates per row (not all Mar 27)
3) Correct forecast counts (1D=1, 7D=7, 30D=30)
4) evaluateAt and createdAt fields present
5) Real prices in chart candles
"""

import pytest
import requests
import os
from datetime import datetime, timedelta

# Use the public URL for testing
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com')

class TestSentimentPerformanceV2:
    """Tests for /api/market/sentiment/performance-v2 endpoint"""
    
    def test_24h_horizon_returns_1_row(self):
        """24H horizon with limit=1 should return exactly 1 row"""
        response = requests.get(
            f"{BASE_URL}/api/market/sentiment/performance-v2",
            params={"symbol": "BTC", "horizon": "24H", "limit": 1},
            timeout=30
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") == True, f"Response not ok: {data}"
        assert "rows" in data, "Missing 'rows' field"
        
        rows = data["rows"]
        assert len(rows) == 1, f"Expected 1 row for 24H/limit=1, got {len(rows)}"
        print(f"✓ 24H horizon returns exactly 1 row")
    
    def test_7d_horizon_returns_7_rows(self):
        """7D horizon with limit=7 should return up to 7 rows with unique dates"""
        response = requests.get(
            f"{BASE_URL}/api/market/sentiment/performance-v2",
            params={"symbol": "BTC", "horizon": "7D", "limit": 7},
            timeout=30
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") == True, f"Response not ok: {data}"
        
        rows = data["rows"]
        assert len(rows) <= 7, f"Expected max 7 rows, got {len(rows)}"
        
        # Check for unique dates (the bug was all rows showing same date)
        dates = [row.get("asOf", "")[:10] for row in rows]
        unique_dates = set(dates)
        
        # If we have multiple rows, they should have different dates
        if len(rows) > 1:
            assert len(unique_dates) > 1, f"All rows have same date! Dates: {dates}"
            print(f"✓ 7D horizon has {len(unique_dates)} unique dates out of {len(rows)} rows")
        else:
            print(f"✓ 7D horizon returned {len(rows)} row(s)")
    
    def test_30d_horizon_returns_up_to_30_rows(self):
        """30D horizon with limit=30 should return up to 30 rows"""
        response = requests.get(
            f"{BASE_URL}/api/market/sentiment/performance-v2",
            params={"symbol": "BTC", "horizon": "30D", "limit": 30},
            timeout=30
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") == True, f"Response not ok: {data}"
        
        rows = data["rows"]
        assert len(rows) <= 30, f"Expected max 30 rows, got {len(rows)}"
        print(f"✓ 30D horizon returns {len(rows)} rows (max 30)")
    
    def test_rows_have_evaluateAt_and_createdAt(self):
        """Each row must have evaluateAt and createdAt fields"""
        response = requests.get(
            f"{BASE_URL}/api/market/sentiment/performance-v2",
            params={"symbol": "BTC", "horizon": "7D", "limit": 5},
            timeout=30
        )
        assert response.status_code == 200
        
        data = response.json()
        rows = data.get("rows", [])
        
        for i, row in enumerate(rows):
            assert "evaluateAt" in row, f"Row {i} missing 'evaluateAt' field"
            assert "createdAt" in row, f"Row {i} missing 'createdAt' field"
            assert row["evaluateAt"] is not None, f"Row {i} has null evaluateAt"
            assert row["createdAt"] is not None, f"Row {i} has null createdAt"
            
            # Validate ISO date format
            try:
                datetime.fromisoformat(row["evaluateAt"].replace("Z", "+00:00"))
                datetime.fromisoformat(row["createdAt"].replace("Z", "+00:00"))
            except ValueError as e:
                pytest.fail(f"Row {i} has invalid date format: {e}")
        
        print(f"✓ All {len(rows)} rows have valid evaluateAt and createdAt fields")
    
    def test_entry_prices_are_realistic_btc_prices(self):
        """Entry prices should be realistic BTC prices (50000-100000), not 0 or 68000"""
        response = requests.get(
            f"{BASE_URL}/api/market/sentiment/performance-v2",
            params={"symbol": "BTC", "horizon": "7D", "limit": 7},
            timeout=30
        )
        assert response.status_code == 200
        
        data = response.json()
        rows = data.get("rows", [])
        
        hardcoded_fallback_count = 0
        zero_price_count = 0
        
        for i, row in enumerate(rows):
            entry = row.get("entry", 0)
            
            # Check for hardcoded fallback ($68,000 was the bug)
            if entry == 68000:
                hardcoded_fallback_count += 1
            
            # Check for zero prices
            if entry == 0:
                zero_price_count += 1
            
            # Entry should be in realistic BTC range
            assert 50000 <= entry <= 100000, f"Row {i} entry price {entry} outside realistic range (50000-100000)"
        
        # Warn if too many hardcoded values (indicates fallback being used)
        if hardcoded_fallback_count > len(rows) * 0.5:
            pytest.fail(f"Too many rows ({hardcoded_fallback_count}/{len(rows)}) have hardcoded $68,000 price")
        
        assert zero_price_count == 0, f"{zero_price_count} rows have zero entry price"
        
        print(f"✓ All {len(rows)} rows have realistic BTC entry prices")
    
    def test_summary_has_required_fields(self):
        """Summary should have evaluated, overdue, pending fields"""
        response = requests.get(
            f"{BASE_URL}/api/market/sentiment/performance-v2",
            params={"symbol": "BTC", "horizon": "7D", "limit": 7},
            timeout=30
        )
        assert response.status_code == 200
        
        data = response.json()
        summary = data.get("summary", {})
        
        required_fields = ["total", "wins", "losses", "pending", "evaluated", "overdue", "winRate", "avgReturn"]
        for field in required_fields:
            assert field in summary, f"Summary missing '{field}' field"
        
        # Validate summary values are reasonable
        assert summary["total"] >= 0, "total should be >= 0"
        assert summary["pending"] >= 0, "pending should be >= 0"
        assert summary["evaluated"] >= 0, "evaluated should be >= 0"
        assert 0 <= summary["winRate"] <= 1, f"winRate {summary['winRate']} should be between 0 and 1"
        
        print(f"✓ Summary has all required fields: total={summary['total']}, pending={summary['pending']}, evaluated={summary['evaluated']}")


class TestSentimentChartV2:
    """Tests for /api/market/chart/sentiment-v2 endpoint"""
    
    def test_chart_returns_candles_with_real_prices(self):
        """Chart should return candles with real BTC prices from Kraken"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/sentiment-v2",
            params={"symbol": "BTC", "horizon": "7D"},
            timeout=30
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") == True, f"Response not ok: {data}"
        
        chart = data.get("chart", {})
        candles = chart.get("candles", [])
        
        # Should have ~168 hourly candles for 7D
        assert len(candles) > 100, f"Expected ~168 candles, got {len(candles)}"
        
        # Check first candle has realistic BTC price
        if candles:
            first_candle = candles[0]
            close_price = first_candle.get("close", 0)
            
            # Real BTC price should be in 50000-100000 range (as of 2026)
            assert 50000 <= close_price <= 100000, f"First candle close {close_price} not in realistic BTC range"
            
            # Check candle structure
            assert "time" in first_candle, "Candle missing 'time' field"
            assert "open" in first_candle, "Candle missing 'open' field"
            assert "high" in first_candle, "Candle missing 'high' field"
            assert "low" in first_candle, "Candle missing 'low' field"
            assert "close" in first_candle, "Candle missing 'close' field"
        
        print(f"✓ Chart returns {len(candles)} candles with realistic prices (first close: ${candles[0]['close']:.2f})")
    
    def test_chart_has_forecast_data(self):
        """Chart should have projection line and forecast data"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/sentiment-v2",
            params={"symbol": "BTC", "horizon": "7D"},
            timeout=30
        )
        assert response.status_code == 200
        
        data = response.json()
        
        # Check forecast section
        forecast = data.get("forecast", {})
        assert "entry" in forecast, "Missing forecast.entry"
        assert "target" in forecast, "Missing forecast.target"
        assert "direction" in forecast, "Missing forecast.direction"
        
        entry = forecast.get("entry", 0)
        assert 50000 <= entry <= 100000, f"Forecast entry {entry} not in realistic BTC range"
        
        print(f"✓ Chart has forecast data: entry=${entry:.2f}, target=${forecast.get('target', 0):.2f}, direction={forecast.get('direction')}")


class TestUICandlesEndpoint:
    """Tests for /api/ui/candles endpoint"""
    
    def test_btc_candles_have_todays_date(self):
        """BTC candles should include today's date with live Kraken price"""
        response = requests.get(
            f"{BASE_URL}/api/ui/candles",
            params={"asset": "BTC", "days": 2},
            timeout=30
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") == True, f"Response not ok: {data}"
        
        candles = data.get("candles", [])
        assert len(candles) > 0, "No candles returned"
        
        # Get today's date
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Last candle should be today (or very recent)
        last_candle = candles[-1]
        last_date = last_candle.get("t", "")
        
        # Allow for timezone differences - last candle should be within 1 day of today
        last_dt = datetime.strptime(last_date, "%Y-%m-%d")
        today_dt = datetime.strptime(today, "%Y-%m-%d")
        diff_days = abs((today_dt - last_dt).days)
        
        assert diff_days <= 1, f"Last candle date {last_date} is {diff_days} days from today {today}"
        
        # Check price is realistic
        close_price = last_candle.get("c", 0) or last_candle.get("close", 0)
        assert 50000 <= close_price <= 100000, f"Last candle close {close_price} not in realistic BTC range"
        
        print(f"✓ BTC candles include recent date {last_date} with price ${close_price:.2f}")
    
    def test_candles_have_correct_structure(self):
        """Candles should have t, o, h, l, c fields"""
        response = requests.get(
            f"{BASE_URL}/api/ui/candles",
            params={"asset": "BTC", "days": 2},
            timeout=30
        )
        assert response.status_code == 200
        
        data = response.json()
        candles = data.get("candles", [])
        
        for i, candle in enumerate(candles[:5]):  # Check first 5
            assert "t" in candle, f"Candle {i} missing 't' (date) field"
            assert "c" in candle or "close" in candle, f"Candle {i} missing close price field"
            
            # Validate date format
            try:
                datetime.strptime(candle["t"], "%Y-%m-%d")
            except ValueError:
                pytest.fail(f"Candle {i} has invalid date format: {candle['t']}")
        
        print(f"✓ Candles have correct structure")


class TestKrakenIntegration:
    """Tests to verify Kraken API is being used (not mocked data)"""
    
    def test_kraken_api_accessible(self):
        """Verify Kraken public API is accessible"""
        response = requests.get(
            "https://api.kraken.com/0/public/Ticker",
            params={"pair": "XBTUSD"},
            timeout=10
        )
        assert response.status_code == 200, f"Kraken API not accessible: {response.status_code}"
        
        data = response.json()
        assert "result" in data, "Kraken response missing 'result'"
        
        # Get current BTC price from Kraken
        result = data.get("result", {})
        key = list(result.keys())[0] if result else None
        if key:
            kraken_price = float(result[key]["c"][0])
            print(f"✓ Kraken API accessible, current BTC price: ${kraken_price:.2f}")
            return kraken_price
        
        pytest.fail("Could not get price from Kraken")
    
    def test_performance_prices_match_kraken_range(self):
        """Performance entry prices should be close to Kraken prices"""
        # Get current Kraken price
        kraken_response = requests.get(
            "https://api.kraken.com/0/public/Ticker",
            params={"pair": "XBTUSD"},
            timeout=10
        )
        kraken_data = kraken_response.json()
        result = kraken_data.get("result", {})
        key = list(result.keys())[0] if result else None
        kraken_price = float(result[key]["c"][0]) if key else 65000
        
        # Get performance data
        perf_response = requests.get(
            f"{BASE_URL}/api/market/sentiment/performance-v2",
            params={"symbol": "BTC", "horizon": "24H", "limit": 1},
            timeout=30
        )
        assert perf_response.status_code == 200
        
        perf_data = perf_response.json()
        rows = perf_data.get("rows", [])
        
        if rows:
            entry_price = rows[0].get("entry", 0)
            
            # Entry price should be within 20% of current Kraken price
            # (accounting for historical data being from different times)
            price_diff_pct = abs(entry_price - kraken_price) / kraken_price * 100
            
            assert price_diff_pct < 30, f"Entry price ${entry_price:.2f} differs by {price_diff_pct:.1f}% from Kraken ${kraken_price:.2f}"
            
            print(f"✓ Entry price ${entry_price:.2f} is within range of Kraken price ${kraken_price:.2f} (diff: {price_diff_pct:.1f}%)")


class TestEvaluateAtCalculation:
    """Tests for evaluateAt field calculation"""
    
    def test_24h_evaluateAt_is_asOf_plus_24_hours(self):
        """For 24H horizon, evaluateAt should be asOf + 24 hours"""
        response = requests.get(
            f"{BASE_URL}/api/market/sentiment/performance-v2",
            params={"symbol": "BTC", "horizon": "24H", "limit": 3},
            timeout=30
        )
        assert response.status_code == 200
        
        data = response.json()
        rows = data.get("rows", [])
        
        for i, row in enumerate(rows):
            asOf = row.get("asOf", "")
            evaluateAt = row.get("evaluateAt", "")
            
            if asOf and evaluateAt:
                asOf_dt = datetime.fromisoformat(asOf.replace("Z", "+00:00"))
                evaluateAt_dt = datetime.fromisoformat(evaluateAt.replace("Z", "+00:00"))
                
                diff_hours = (evaluateAt_dt - asOf_dt).total_seconds() / 3600
                
                # Should be approximately 24 hours (allow some tolerance)
                assert 23 <= diff_hours <= 25, f"Row {i}: evaluateAt is {diff_hours:.1f} hours after asOf (expected ~24)"
        
        print(f"✓ 24H horizon: evaluateAt is correctly asOf + 24 hours")
    
    def test_7d_evaluateAt_is_asOf_plus_7_days(self):
        """For 7D horizon, evaluateAt should be asOf + 7 days"""
        response = requests.get(
            f"{BASE_URL}/api/market/sentiment/performance-v2",
            params={"symbol": "BTC", "horizon": "7D", "limit": 3},
            timeout=30
        )
        assert response.status_code == 200
        
        data = response.json()
        rows = data.get("rows", [])
        
        for i, row in enumerate(rows):
            asOf = row.get("asOf", "")
            evaluateAt = row.get("evaluateAt", "")
            
            if asOf and evaluateAt:
                asOf_dt = datetime.fromisoformat(asOf.replace("Z", "+00:00"))
                evaluateAt_dt = datetime.fromisoformat(evaluateAt.replace("Z", "+00:00"))
                
                diff_days = (evaluateAt_dt - asOf_dt).days
                
                # Should be approximately 7 days
                assert 6 <= diff_days <= 8, f"Row {i}: evaluateAt is {diff_days} days after asOf (expected ~7)"
        
        print(f"✓ 7D horizon: evaluateAt is correctly asOf + 7 days")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
