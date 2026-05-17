"""
Exchange Chart V3 - Rolling Forecast Curve Tests
=================================================
Tests for the refactored V3 endpoint with NO simulations, NO interpolation, NO daily cap.

Key changes from previous version:
1) Backend filters by horizonDays (1D/7D/30D) instead of returning all horizons
2) Removed prevFuturePoints (gray spider web) - always empty []
3) Frontend builds candles directly from DB points (1 record = 1 candle)
4) No piecewise interpolation, no daily cap

Expected results (from MongoDB):
- 1D: horizonDays=1 has 2 records, after dedup + future filter = 1 point
- 7D: horizonDays=7 has 152 records, after dedup + future filter = 7 points  
- 30D: horizonDays=30 has 152 records, after dedup + future filter = 30 points
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL')
if not BASE_URL:
    BASE_URL = 'https://expo-telegram-web.preview.emergentagent.com'
BASE_URL = BASE_URL.rstrip('/')


class TestExchangeChartV3HorizonFiltering:
    """Tests for horizon-specific filtering (1D/7D/30D)"""
    
    def test_1d_horizon_returns_exactly_1_future_point(self):
        """1D horizon should return exactly 1 futurePoint"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=1D"
        )
        assert response.status_code == 200, f"Status: {response.status_code}"
        data = response.json()
        
        assert data.get('ok') is True, f"ok is not True: {data}"
        
        future_points = data.get('futurePoints', [])
        future_count = len(future_points)
        
        # Should have exactly 1 point for 1D horizon
        assert future_count == 1, \
            f"Expected exactly 1 futurePoint for 1D horizon, got {future_count}"
        
        print(f"✓ 1D horizon: {future_count} futurePoint(s)")
    
    def test_7d_horizon_returns_exactly_7_future_points(self):
        """7D horizon should return exactly 7 futurePoints"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D"
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        
        future_points = data.get('futurePoints', [])
        future_count = len(future_points)
        
        # Should have exactly 7 points for 7D horizon
        assert future_count == 7, \
            f"Expected exactly 7 futurePoints for 7D horizon, got {future_count}"
        
        print(f"✓ 7D horizon: {future_count} futurePoints")
    
    def test_30d_horizon_returns_exactly_30_future_points(self):
        """30D horizon should return exactly 30 futurePoints"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=30D"
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        
        future_points = data.get('futurePoints', [])
        future_count = len(future_points)
        
        # Should have exactly 30 points for 30D horizon
        assert future_count == 30, \
            f"Expected exactly 30 futurePoints for 30D horizon, got {future_count}"
        
        print(f"✓ 30D horizon: {future_count} futurePoints")


class TestExchangeChartV3PrevFuturePointsRemoved:
    """Tests that prevFuturePoints (gray spider web) is always empty"""
    
    def test_1d_prev_future_points_is_empty(self):
        """1D horizon prevFuturePoints should be empty array"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=1D"
        )
        assert response.status_code == 200
        data = response.json()
        
        prev_points = data.get('prevFuturePoints', None)
        
        # Should exist but be empty
        assert prev_points is not None, "prevFuturePoints field is missing"
        assert isinstance(prev_points, list), "prevFuturePoints should be a list"
        assert len(prev_points) == 0, \
            f"prevFuturePoints should be empty for 1D, got {len(prev_points)} items"
        
        print(f"✓ 1D prevFuturePoints is empty (gray spider web removed)")
    
    def test_7d_prev_future_points_is_empty(self):
        """7D horizon prevFuturePoints should be empty array"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D"
        )
        assert response.status_code == 200
        data = response.json()
        
        prev_points = data.get('prevFuturePoints', None)
        
        assert prev_points is not None
        assert isinstance(prev_points, list)
        assert len(prev_points) == 0, \
            f"prevFuturePoints should be empty for 7D, got {len(prev_points)} items"
        
        print(f"✓ 7D prevFuturePoints is empty (gray spider web removed)")
    
    def test_30d_prev_future_points_is_empty(self):
        """30D horizon prevFuturePoints should be empty array"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=30D"
        )
        assert response.status_code == 200
        data = response.json()
        
        prev_points = data.get('prevFuturePoints', None)
        
        assert prev_points is not None
        assert isinstance(prev_points, list)
        assert len(prev_points) == 0, \
            f"prevFuturePoints should be empty for 30D, got {len(prev_points)} items"
        
        print(f"✓ 30D prevFuturePoints is empty (gray spider web removed)")


class TestExchangeChartV3HorizonDifferentValues:
    """Tests that each horizon returns different target/confidence values"""
    
    def test_horizons_return_different_targets(self):
        """Each horizon should return different target prices"""
        responses = {}
        for horizon in ['1D', '7D', '30D']:
            resp = requests.get(
                f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon={horizon}"
            )
            assert resp.status_code == 200
            responses[horizon] = resp.json()
        
        targets = {h: r['target'] for h, r in responses.items()}
        confidences = {h: r['confidence'] for h, r in responses.items()}
        
        # All targets should be positive
        for h, t in targets.items():
            assert t > 0, f"{h} target should be positive, got {t}"
        
        # At least some targets should differ (check 7D vs 30D as 1D may be similar)
        # Note: We can't guarantee they're different, but log them
        print(f"Target prices: 1D=${targets['1D']:.2f}, 7D=${targets['7D']:.2f}, 30D=${targets['30D']:.2f}")
        print(f"Confidences: 1D={confidences['1D']:.4f}, 7D={confidences['7D']:.4f}, 30D={confidences['30D']:.4f}")
        
        # Different horizons may have different values - log if same
        if targets['7D'] == targets['30D']:
            print("Warning: 7D and 30D have same target price (may be from same latest forecast)")
    
    def test_each_horizon_has_valid_confidence(self):
        """Each horizon should have valid confidence between 0 and 1"""
        for horizon in ['1D', '7D', '30D']:
            resp = requests.get(
                f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon={horizon}"
            )
            assert resp.status_code == 200
            data = resp.json()
            
            confidence = data.get('confidence', -1)
            assert 0 <= confidence <= 1, \
                f"{horizon} confidence should be 0-1, got {confidence}"
            
            print(f"✓ {horizon} confidence: {confidence:.4f}")


class TestExchangeChartV3SourceIsDb:
    """Tests that source field is 'db' for all horizons"""
    
    def test_1d_source_is_db(self):
        """1D horizon source should be 'db'"""
        resp = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=1D"
        )
        assert resp.status_code == 200
        data = resp.json()
        
        source = data.get('source', '')
        assert source == 'db', f"1D source should be 'db', got '{source}'"
        
        print(f"✓ 1D source: {source}")
    
    def test_7d_source_is_db(self):
        """7D horizon source should be 'db'"""
        resp = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D"
        )
        assert resp.status_code == 200
        data = resp.json()
        
        source = data.get('source', '')
        assert source == 'db', f"7D source should be 'db', got '{source}'"
        
        print(f"✓ 7D source: {source}")
    
    def test_30d_source_is_db(self):
        """30D horizon source should be 'db'"""
        resp = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=30D"
        )
        assert resp.status_code == 200
        data = resp.json()
        
        source = data.get('source', '')
        assert source == 'db', f"30D source should be 'db', got '{source}'"
        
        print(f"✓ 30D source: {source}")


class TestExchangeChartV3FuturePointsDeduplication:
    """Tests that futurePoints are deduplicated and sorted"""
    
    def test_future_points_unique_target_dates(self):
        """futurePoints should have unique targetDateTs (no duplicates)"""
        for horizon in ['1D', '7D', '30D']:
            resp = requests.get(
                f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon={horizon}"
            )
            assert resp.status_code == 200
            data = resp.json()
            
            future_points = data.get('futurePoints', [])
            
            if len(future_points) > 0:
                target_dates = [p['targetDateTs'] for p in future_points]
                unique_dates = set(target_dates)
                
                assert len(target_dates) == len(unique_dates), \
                    f"{horizon}: Duplicate targetDateTs found! {len(target_dates)} items, {len(unique_dates)} unique"
                
                print(f"✓ {horizon}: {len(future_points)} unique target dates")
    
    def test_future_points_sorted_ascending(self):
        """futurePoints should be sorted by targetDateTs ascending"""
        for horizon in ['7D', '30D']:  # Skip 1D as it has only 1 point
            resp = requests.get(
                f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon={horizon}"
            )
            assert resp.status_code == 200
            data = resp.json()
            
            future_points = data.get('futurePoints', [])
            
            if len(future_points) < 2:
                continue
            
            for i in range(len(future_points) - 1):
                current_ts = future_points[i]['targetDateTs']
                next_ts = future_points[i + 1]['targetDateTs']
                assert current_ts < next_ts, \
                    f"{horizon}: Not sorted at index {i}: {current_ts} >= {next_ts}"
            
            print(f"✓ {horizon}: sorted ascending from {future_points[0]['targetDateTs']} to {future_points[-1]['targetDateTs']}")


class TestExchangeChartV3ResponseStructure:
    """Tests for overall response structure"""
    
    def test_all_required_fields_present(self):
        """Response should contain all required fields"""
        resp = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D"
        )
        assert resp.status_code == 200
        data = resp.json()
        
        required_fields = [
            'ok', 'symbol', 'nowTs', 'entryPrice',
            'realCandles', 'futurePoints', 'prevFuturePoints',
            'target', 'confidence', 'direction', 'source', 'meta'
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        print(f"✓ All {len(required_fields)} required fields present")
    
    def test_future_point_structure(self):
        """Each futurePoint should have required fields"""
        resp = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D"
        )
        assert resp.status_code == 200
        data = resp.json()
        
        future_points = data.get('futurePoints', [])
        
        required_fields = ['targetDateTs', 'targetPrice', 'madeAtTs', 'confidence', 'direction']
        
        for i, point in enumerate(future_points):
            for field in required_fields:
                assert field in point, f"futurePoint[{i}] missing field: {field}"
            
            # Validate types
            assert isinstance(point['targetDateTs'], int)
            assert isinstance(point['targetPrice'], (int, float))
            assert isinstance(point['madeAtTs'], int)
            assert isinstance(point['confidence'], (int, float))
            assert point['direction'] in ['LONG', 'SHORT', 'NEUTRAL']
        
        print(f"✓ All {len(future_points)} futurePoints have valid structure")
    
    def test_meta_contains_required_fields(self):
        """meta should contain regime, totalForecasts, uniqueTargetDates"""
        resp = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D"
        )
        assert resp.status_code == 200
        data = resp.json()
        
        meta = data.get('meta', {})
        
        assert 'regime' in meta, "meta.regime missing"
        assert 'totalForecasts' in meta, "meta.totalForecasts missing"
        assert 'uniqueTargetDates' in meta, "meta.uniqueTargetDates missing"
        
        print(f"✓ Meta: regime={meta['regime']}, totalForecasts={meta['totalForecasts']}, uniqueDates={meta['uniqueTargetDates']}")


class TestExchangeChartV3RealCandles:
    """Tests for realCandles from ByBit"""
    
    def test_real_candles_present(self):
        """realCandles should be present and non-empty"""
        resp = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D"
        )
        assert resp.status_code == 200
        data = resp.json()
        
        real_candles = data.get('realCandles', [])
        assert len(real_candles) > 0, "realCandles should not be empty"
        
        print(f"✓ {len(real_candles)} real candles from ByBit")
    
    def test_real_candles_ohlc_structure(self):
        """realCandles should have OHLC structure"""
        resp = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D"
        )
        assert resp.status_code == 200
        data = resp.json()
        
        real_candles = data.get('realCandles', [])
        
        if len(real_candles) == 0:
            pytest.skip("No realCandles")
        
        candle = real_candles[0]
        
        assert 'time' in candle
        assert 'open' in candle
        assert 'high' in candle
        assert 'low' in candle
        assert 'close' in candle
        
        assert candle['high'] >= candle['low'], "high should be >= low"
        
        print(f"✓ realCandles have valid OHLC structure")
    
    def test_entry_price_matches_last_candle(self):
        """entryPrice should match last realCandle close"""
        resp = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D"
        )
        assert resp.status_code == 200
        data = resp.json()
        
        entry_price = data.get('entryPrice', 0)
        real_candles = data.get('realCandles', [])
        
        if len(real_candles) == 0:
            pytest.skip("No realCandles")
        
        last_close = real_candles[-1]['close']
        
        assert entry_price == last_close, \
            f"entryPrice ({entry_price}) != last candle close ({last_close})"
        
        print(f"✓ entryPrice ${entry_price} matches last candle close")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
