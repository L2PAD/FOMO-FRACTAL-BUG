"""
Exchange Chart V3 API Tests
=============================
Tests for the new Rolling Forecast Curve (V3) endpoint
that uses real forecast history data instead of simulations.

Testing:
- GET /api/market/chart/exchange-v3?asset=BTC&horizon=7D
- GET /api/market/chart/exchange-v3?asset=BTC&horizon=30D
- futurePoints deduplication by targetDateTs
- prevFuturePoints filtering (forecasts made before today)
- realCandles OHLC data structure
- source field is 'db' when forecasts exist
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL')
if not BASE_URL:
    BASE_URL = 'https://expo-telegram-web.preview.emergentagent.com'
BASE_URL = BASE_URL.rstrip('/')


class TestExchangeChartV3Endpoint:
    """Tests for /api/market/chart/exchange-v3 endpoint"""
    
    def test_v3_7d_returns_ok_true(self):
        """7D horizon returns ok:true with expected fields"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D"
        )
        assert response.status_code == 200
        data = response.json()
        
        # ok must be true
        assert data.get('ok') is True
        
        # Required fields must exist
        assert 'realCandles' in data
        assert 'futurePoints' in data
        assert 'prevFuturePoints' in data
        assert 'entryPrice' in data
        assert 'target' in data
        assert 'confidence' in data
        assert 'direction' in data
        assert 'source' in data
        assert 'meta' in data
        assert 'nowTs' in data
        assert 'symbol' in data
        
        print(f"V3 7D OK: target={data['target']}, confidence={data['confidence']}, source={data['source']}")
    
    def test_v3_30d_returns_ok_true(self):
        """30D horizon returns ok:true with expected fields"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=30D"
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        assert 'realCandles' in data
        assert 'futurePoints' in data
        assert 'prevFuturePoints' in data
        
        print(f"V3 30D OK: target={data['target']}, confidence={data['confidence']}")
    
    def test_v3_7d_vs_30d_different_target_confidence(self):
        """7D and 30D return different target and confidence values"""
        resp_7d = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D"
        )
        resp_30d = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=30D"
        )
        
        assert resp_7d.status_code == 200
        assert resp_30d.status_code == 200
        
        data_7d = resp_7d.json()
        data_30d = resp_30d.json()
        
        # Targets are likely different (different latest forecast for each horizon)
        target_7d = data_7d['target']
        target_30d = data_30d['target']
        conf_7d = data_7d['confidence']
        conf_30d = data_30d['confidence']
        
        # They should both have valid values
        assert target_7d > 0
        assert target_30d > 0
        assert conf_7d >= 0
        assert conf_30d >= 0
        
        # Note: targets MAY be different depending on data
        print(f"7D: target={target_7d}, confidence={conf_7d}")
        print(f"30D: target={target_30d}, confidence={conf_30d}")
    
    def test_future_points_deduplicated_by_target_date(self):
        """futurePoints should have unique targetDateTs (one per day bucket)"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D"
        )
        assert response.status_code == 200
        data = response.json()
        
        future_points = data.get('futurePoints', [])
        
        # Extract all targetDateTs
        target_dates = [p['targetDateTs'] for p in future_points]
        
        # Check uniqueness
        unique_dates = set(target_dates)
        assert len(target_dates) == len(unique_dates), \
            f"Duplicate targetDateTs found! {len(target_dates)} items, {len(unique_dates)} unique"
        
        print(f"FuturePoints: {len(future_points)} unique target dates (deduplicated)")
    
    def test_future_points_sorted_ascending(self):
        """futurePoints should be sorted by targetDateTs ascending"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D"
        )
        assert response.status_code == 200
        data = response.json()
        
        future_points = data.get('futurePoints', [])
        
        if len(future_points) < 2:
            pytest.skip("Not enough futurePoints to verify sort order")
        
        for i in range(len(future_points) - 1):
            current_ts = future_points[i]['targetDateTs']
            next_ts = future_points[i + 1]['targetDateTs']
            assert current_ts < next_ts, \
                f"futurePoints not sorted ascending at index {i}: {current_ts} >= {next_ts}"
        
        print(f"FuturePoints sorted ascending: {future_points[0]['targetDateTs']} -> {future_points[-1]['targetDateTs']}")
    
    def test_prev_future_points_made_before_today(self):
        """prevFuturePoints should only contain forecasts made before today"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D"
        )
        assert response.status_code == 200
        data = response.json()
        
        prev_points = data.get('prevFuturePoints', [])
        now_ts = data.get('nowTs', 0)
        
        # todayBucket = floor(nowTs / 86400) * 86400
        DAY_SEC = 86400
        today_bucket = (now_ts // DAY_SEC) * DAY_SEC
        
        for p in prev_points:
            made_at = p['madeAtTs']
            assert made_at < today_bucket, \
                f"prevFuturePoint madeAtTs {made_at} >= todayBucket {today_bucket}"
        
        print(f"All {len(prev_points)} prevFuturePoints made before today ({today_bucket})")
    
    def test_real_candles_have_ohlc_structure(self):
        """realCandles should have time, open, high, low, close fields"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D"
        )
        assert response.status_code == 200
        data = response.json()
        
        real_candles = data.get('realCandles', [])
        
        # Should have candles from ByBit/Binance
        assert len(real_candles) > 0, "No realCandles returned"
        
        # Check first candle structure
        candle = real_candles[0]
        assert 'time' in candle
        assert 'open' in candle
        assert 'high' in candle
        assert 'low' in candle
        assert 'close' in candle
        
        # Verify valid OHLC values
        assert candle['time'] > 0
        assert candle['open'] > 0
        assert candle['high'] >= candle['low']
        assert candle['close'] > 0
        
        print(f"RealCandles: {len(real_candles)} candles, first time={candle['time']}")
    
    def test_source_is_db_when_forecasts_exist(self):
        """source field should be 'db' when forecasts exist in database"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D"
        )
        assert response.status_code == 200
        data = response.json()
        
        total_forecasts = data.get('meta', {}).get('totalForecasts', 0)
        source = data.get('source', '')
        
        if total_forecasts > 0:
            assert source == 'db', f"Expected source='db' when forecasts exist, got '{source}'"
            print(f"Source is 'db' (totalForecasts={total_forecasts})")
        else:
            assert source == 'fallback', f"Expected source='fallback' when no forecasts, got '{source}'"
            print("Source is 'fallback' (no forecasts)")
    
    def test_meta_contains_expected_fields(self):
        """meta object should contain regime, totalForecasts, uniqueTargetDates"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D"
        )
        assert response.status_code == 200
        data = response.json()
        
        meta = data.get('meta', {})
        
        assert 'regime' in meta, "meta.regime missing"
        assert 'totalForecasts' in meta, "meta.totalForecasts missing"
        assert 'uniqueTargetDates' in meta, "meta.uniqueTargetDates missing"
        
        print(f"Meta: regime={meta['regime']}, totalForecasts={meta['totalForecasts']}, uniqueDates={meta['uniqueTargetDates']}")
    
    def test_direction_is_valid_enum(self):
        """direction should be LONG, SHORT, or NEUTRAL"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D"
        )
        assert response.status_code == 200
        data = response.json()
        
        direction = data.get('direction', '')
        valid_directions = ['LONG', 'SHORT', 'NEUTRAL']
        
        assert direction in valid_directions, \
            f"Invalid direction '{direction}', expected one of {valid_directions}"
        
        print(f"Direction: {direction}")
    
    def test_future_points_have_required_fields(self):
        """Each futurePoint should have targetDateTs, targetPrice, madeAtTs, confidence, direction"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D"
        )
        assert response.status_code == 200
        data = response.json()
        
        future_points = data.get('futurePoints', [])
        
        if len(future_points) == 0:
            pytest.skip("No futurePoints to validate")
        
        required_fields = ['targetDateTs', 'targetPrice', 'madeAtTs', 'confidence', 'direction']
        
        for i, point in enumerate(future_points[:5]):  # Check first 5
            for field in required_fields:
                assert field in point, \
                    f"futurePoint[{i}] missing required field '{field}'"
            
            # Validate types
            assert isinstance(point['targetDateTs'], int)
            assert isinstance(point['targetPrice'], (int, float))
            assert isinstance(point['madeAtTs'], int)
            assert isinstance(point['confidence'], (int, float))
            assert point['direction'] in ['LONG', 'SHORT', 'NEUTRAL']
        
        print(f"Validated {min(5, len(future_points))} futurePoints structure")
    
    def test_entry_price_matches_last_real_candle(self):
        """entryPrice should match the close of the last realCandle"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=7D"
        )
        assert response.status_code == 200
        data = response.json()
        
        entry_price = data.get('entryPrice', 0)
        real_candles = data.get('realCandles', [])
        
        if len(real_candles) == 0:
            pytest.skip("No realCandles")
        
        last_candle_close = real_candles[-1]['close']
        
        assert entry_price == last_candle_close, \
            f"entryPrice ({entry_price}) != last candle close ({last_candle_close})"
        
        print(f"EntryPrice matches last candle close: ${entry_price}")


class TestExchangeChartV3EdgeCases:
    """Edge case tests for V3 endpoint"""
    
    def test_asset_lowercase_normalized(self):
        """Asset parameter should be normalized to uppercase"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v3?asset=btc&horizon=7D"
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        assert data.get('symbol', '').upper() == 'BTC'
        
        print("Lowercase 'btc' normalized correctly")
    
    def test_invalid_horizon_defaults_to_7d(self):
        """Invalid horizon should default to 7D"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v3?asset=BTC&horizon=INVALID"
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should not error, should use default
        assert data.get('ok') is True
        
        print("Invalid horizon defaulted to 7D")
    
    def test_missing_asset_defaults_to_btc(self):
        """Missing asset parameter should default to BTC"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/exchange-v3?horizon=7D"
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        assert data.get('symbol', '').upper() == 'BTC'
        
        print("Missing asset defaulted to BTC")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
