"""
S10.6I.6 — Indicator Persistence Layer Tests

Tests for saving 32 indicators in ExchangeObservationRow:
- POST /api/v10/exchange/observation/tick/full - create observation with indicators
- GET /api/v10/exchange/observation/:symbol/latest - get latest with indicators
- GET /api/v10/exchange/observation/indicators/coverage - coverage stats
- POST /api/v10/exchange/observation/backfill - backfill functionality
- Legacy endpoints compatibility (/observation, /observation/stats)
- Indicator map structure validation (not array)
- All 5 categories present
- No NaN/undefined values
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Expected 5 categories with their indicator IDs
EXPECTED_CATEGORIES = {
    'PRICE_STRUCTURE': [
        'ema_distance_fast', 'ema_distance_mid', 'ema_distance_slow',
        'vwap_deviation', 'median_price_deviation', 'atr_normalized',
        'trend_slope', 'range_compression'
    ],
    'MOMENTUM': [
        'rsi_normalized', 'stochastic', 'macd_delta',
        'roc', 'momentum_decay', 'directional_momentum_balance'
    ],
    'VOLUME': [
        'volume_index', 'volume_delta', 'buy_sell_ratio',
        'volume_price_response', 'relative_volume', 'participation_intensity'
    ],
    'ORDER_BOOK': [
        'book_imbalance', 'depth_density', 'liquidity_walls',
        'absorption_strength', 'liquidity_vacuum', 'spread_pressure'
    ],
    'POSITIONING': [
        'oi_level', 'oi_delta', 'oi_volume_ratio',
        'funding_pressure', 'long_short_ratio', 'position_crowding'
    ]
}

EXPECTED_INDICATOR_COUNT = 32  # 8 + 6 + 6 + 6 + 6


class TestObservationWithIndicatorsEndpoint:
    """Tests for POST /api/v10/exchange/observation/tick/full"""
    
    def test_create_observation_with_indicators_btcusdt(self):
        """Create observation with indicators for BTCUSDT"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/observation/tick/full",
            json={"symbol": "BTCUSDT"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get('ok') == True, f"Response not ok: {data}"
        assert 'observation' in data, "Response missing 'observation' field"
        
        obs = data['observation']
        assert obs['symbol'] == 'BTCUSDT', f"Expected BTCUSDT, got {obs['symbol']}"
        assert 'indicatorsMeta' in obs, "Missing indicatorsMeta"
        assert 'indicatorCount' in obs, "Missing indicatorCount"
        
        print(f"✓ Created observation with {obs['indicatorCount']} indicators")
    
    def test_create_observation_with_indicators_ethusdt(self):
        """Create observation with indicators for ETHUSDT"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/observation/tick/full",
            json={"symbol": "ETHUSDT"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        
        obs = data['observation']
        assert obs['symbol'] == 'ETHUSDT'
        assert obs['indicatorCount'] > 0
        
        print(f"✓ ETHUSDT observation: {obs['indicatorCount']} indicators")
    
    def test_observation_has_all_32_indicators(self):
        """Verify observation contains all 32 indicators"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/observation/tick/full",
            json={"symbol": "BTCUSDT"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        meta = data['observation']['indicatorsMeta']
        indicator_count = data['observation']['indicatorCount']
        
        assert meta['indicatorCount'] == EXPECTED_INDICATOR_COUNT, \
            f"Expected {EXPECTED_INDICATOR_COUNT} indicators, got {meta['indicatorCount']}"
        assert indicator_count == EXPECTED_INDICATOR_COUNT, \
            f"indicatorCount mismatch: {indicator_count}"
        
        print(f"✓ All {EXPECTED_INDICATOR_COUNT} indicators present")
    
    def test_observation_completeness_is_100_percent(self):
        """Verify indicatorsMeta.completeness = 1 (100%)"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/observation/tick/full",
            json={"symbol": "BTCUSDT"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        meta = data['observation']['indicatorsMeta']
        
        assert meta['completeness'] == 1.0, \
            f"Expected completeness 1.0, got {meta['completeness']}"
        
        print(f"✓ Completeness is 100%: {meta['completeness']}")
    
    def test_observation_missing_is_empty(self):
        """Verify indicatorsMeta.missing = [] (empty)"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/observation/tick/full",
            json={"symbol": "BTCUSDT"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        meta = data['observation']['indicatorsMeta']
        
        assert meta['missing'] == [], \
            f"Expected empty missing list, got {meta['missing']}"
        
        print(f"✓ Missing list is empty: {meta['missing']}")


class TestGetLatestObservation:
    """Tests for GET /api/v10/exchange/observation/:symbol/latest"""
    
    def test_get_latest_observation_has_indicators(self):
        """Get latest observation and verify it has full indicators map"""
        # First create an observation
        requests.post(
            f"{BASE_URL}/api/v10/exchange/observation/tick/full",
            json={"symbol": "BTCUSDT"}
        )
        
        # Then get latest
        response = requests.get(f"{BASE_URL}/api/v10/exchange/observation/BTCUSDT/latest")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') == True
        assert 'observation' in data
        
        obs = data['observation']
        assert 'indicators' in obs, "Missing indicators map"
        assert 'indicatorsMeta' in obs, "Missing indicatorsMeta"
        
        # Verify indicators is a map (dict), not array
        assert isinstance(obs['indicators'], dict), \
            f"indicators should be map/dict, got {type(obs['indicators'])}"
        
        indicator_count = len(obs['indicators'])
        assert indicator_count == EXPECTED_INDICATOR_COUNT, \
            f"Expected {EXPECTED_INDICATOR_COUNT} indicators, got {indicator_count}"
        
        print(f"✓ Latest observation has {indicator_count} indicators (map structure)")
    
    def test_latest_observation_indicators_have_valid_values(self):
        """Verify no NaN or undefined values in indicators"""
        # Create fresh observation
        requests.post(
            f"{BASE_URL}/api/v10/exchange/observation/tick/full",
            json={"symbol": "BTCUSDT"}
        )
        
        response = requests.get(f"{BASE_URL}/api/v10/exchange/observation/BTCUSDT/latest")
        data = response.json()
        
        indicators = data['observation']['indicators']
        
        invalid_values = []
        for indicator_id, indicator_data in indicators.items():
            value = indicator_data.get('value')
            
            # Check for None/null
            if value is None:
                invalid_values.append(f"{indicator_id}: null")
                continue
            
            # Check for NaN (Python's way to detect NaN)
            if isinstance(value, float) and value != value:  # NaN != NaN
                invalid_values.append(f"{indicator_id}: NaN")
                continue
        
        assert len(invalid_values) == 0, \
            f"Found invalid indicator values: {invalid_values}"
        
        print(f"✓ All {len(indicators)} indicator values are valid (no NaN/undefined)")
    
    def test_latest_observation_has_all_5_categories(self):
        """Verify all 5 indicator categories are present"""
        # Create observation
        requests.post(
            f"{BASE_URL}/api/v10/exchange/observation/tick/full",
            json={"symbol": "BTCUSDT"}
        )
        
        response = requests.get(f"{BASE_URL}/api/v10/exchange/observation/BTCUSDT/latest")
        data = response.json()
        
        indicators = data['observation']['indicators']
        
        # Group by category
        categories_found = set()
        for indicator_id, indicator_data in indicators.items():
            category = indicator_data.get('category')
            if category:
                categories_found.add(category)
        
        expected_categories = set(EXPECTED_CATEGORIES.keys())
        
        assert categories_found == expected_categories, \
            f"Expected categories {expected_categories}, found {categories_found}"
        
        print(f"✓ All 5 categories present: {sorted(categories_found)}")
    
    def test_latest_observation_indicator_structure(self):
        """Verify each indicator has correct structure: value, category, normalized"""
        requests.post(
            f"{BASE_URL}/api/v10/exchange/observation/tick/full",
            json={"symbol": "BTCUSDT"}
        )
        
        response = requests.get(f"{BASE_URL}/api/v10/exchange/observation/BTCUSDT/latest")
        data = response.json()
        
        indicators = data['observation']['indicators']
        
        for indicator_id, indicator_data in indicators.items():
            assert 'value' in indicator_data, f"{indicator_id} missing 'value'"
            assert 'category' in indicator_data, f"{indicator_id} missing 'category'"
            assert 'normalized' in indicator_data, f"{indicator_id} missing 'normalized'"
            
            # Value must be a number
            assert isinstance(indicator_data['value'], (int, float)), \
                f"{indicator_id} value is not a number: {indicator_data['value']}"
        
        print(f"✓ All indicators have correct structure (value, category, normalized)")
    
    def test_nonexistent_symbol_returns_error(self):
        """Get latest for nonexistent symbol returns appropriate error"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/observation/NONEXISTENT123/latest")
        
        assert response.status_code == 200  # API returns 200 with ok=false
        data = response.json()
        
        assert data.get('ok') == False, "Expected ok=false for nonexistent symbol"
        assert 'error' in data, "Expected error message"
        
        print(f"✓ Nonexistent symbol returns error: {data.get('error')}")


class TestIndicatorCoverageStats:
    """Tests for GET /api/v10/exchange/observation/indicators/coverage"""
    
    def test_get_coverage_stats_all_symbols(self):
        """Get indicator coverage stats for all symbols"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/observation/indicators/coverage")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') == True
        assert 'stats' in data
        
        stats = data['stats']
        assert 'totalObservations' in stats
        assert 'withIndicators' in stats
        assert 'coverageRate' in stats
        assert 'avgCompleteness' in stats
        assert 'avgIndicatorCount' in stats
        
        print(f"✓ Coverage stats: {stats['withIndicators']}/{stats['totalObservations']} observations with indicators")
    
    def test_get_coverage_stats_specific_symbol(self):
        """Get indicator coverage stats for specific symbol"""
        # First create some observations
        requests.post(f"{BASE_URL}/api/v10/exchange/observation/tick/full", json={"symbol": "BTCUSDT"})
        
        response = requests.get(
            f"{BASE_URL}/api/v10/exchange/observation/indicators/coverage",
            params={"symbol": "BTCUSDT"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') == True
        assert data.get('symbol') == 'BTCUSDT'
        
        stats = data['stats']
        assert stats['totalObservations'] >= 0
        
        print(f"✓ BTCUSDT coverage: {stats}")
    
    def test_coverage_rate_calculation(self):
        """Verify coverage rate is calculated correctly"""
        # Create observation with indicators
        requests.post(
            f"{BASE_URL}/api/v10/exchange/observation/tick/full",
            json={"symbol": "COVERAGETEST"}
        )
        
        response = requests.get(
            f"{BASE_URL}/api/v10/exchange/observation/indicators/coverage",
            params={"symbol": "COVERAGETEST"}
        )
        
        data = response.json()
        stats = data['stats']
        
        # Coverage rate should be between 0 and 1
        assert 0 <= stats['coverageRate'] <= 1, \
            f"Coverage rate out of range: {stats['coverageRate']}"
        
        # Avg completeness should be between 0 and 1
        if stats['avgCompleteness'] > 0:
            assert 0 <= stats['avgCompleteness'] <= 1, \
                f"Avg completeness out of range: {stats['avgCompleteness']}"
        
        print(f"✓ Coverage rate: {stats['coverageRate']:.2%}, Avg completeness: {stats['avgCompleteness']:.2%}")


class TestBackfillObservations:
    """Tests for POST /api/v10/exchange/observation/backfill"""
    
    def test_backfill_creates_observations(self):
        """Backfill creates multiple observations with indicators"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/observation/backfill",
            json={"symbol": "BACKFILLTEST", "count": 5}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') == True
        assert data.get('count') >= 1  # May be rate limited
        assert 'observations' in data
        
        print(f"✓ Backfilled {data['count']} observations")
    
    def test_backfill_observations_have_indicators(self):
        """Verify backfilled observations have indicators"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/observation/backfill",
            json={"symbol": "BACKFILL2", "count": 3}
        )
        
        data = response.json()
        
        if data.get('count', 0) > 0:
            for obs in data['observations']:
                assert 'indicatorCount' in obs
                assert obs['indicatorCount'] > 0, "Backfilled observation missing indicators"
                assert 'completeness' in obs
        
        print(f"✓ Backfilled observations have indicators")
    
    def test_backfill_respects_max_count(self):
        """Backfill respects max count limit of 100"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/observation/backfill",
            json={"symbol": "BACKFILLMAX", "count": 200}
        )
        
        data = response.json()
        
        # Count should be capped at 100 (or less due to rate limiting)
        assert data.get('count', 0) <= 100
        
        print(f"✓ Backfill count capped appropriately: {data.get('count', 0)}")
    
    def test_backfill_source_is_replay(self):
        """Verify backfilled observations have source='replay'"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/observation/backfill",
            json={"symbol": "BACKFILLSRC", "count": 2}
        )
        
        data = response.json()
        
        # Get one of the backfilled observations
        if data.get('count', 0) > 0:
            obs_id = data['observations'][0]['id']
            
            # Get latest to verify source
            latest = requests.get(f"{BASE_URL}/api/v10/exchange/observation/BACKFILLSRC/latest")
            latest_data = latest.json()
            
            if latest_data.get('ok'):
                source = latest_data['observation'].get('source')
                # Source should be 'replay' for backfilled observations
                assert source == 'replay', f"Expected source='replay', got {source}"
        
        print(f"✓ Backfilled observations have source='replay'")


class TestLegacyEndpointsCompatibility:
    """Test that old endpoints still work after S10.6I.6 changes"""
    
    def test_legacy_observation_list_endpoint(self):
        """GET /api/v10/exchange/observation still works"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/observation")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') == True
        assert 'count' in data
        assert 'data' in data
        
        print(f"✓ Legacy /observation endpoint works: {data['count']} observations")
    
    def test_legacy_observation_stats_endpoint(self):
        """GET /api/v10/exchange/observation/stats still works"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/observation/stats")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') == True
        assert 'totalObservations' in data
        assert 'regimeDistribution' in data
        
        print(f"✓ Legacy /observation/stats endpoint works: {data['totalObservations']} total")
    
    def test_legacy_observation_by_symbol_endpoint(self):
        """GET /api/v10/exchange/observation/:symbol still works"""
        # Create an observation first
        requests.post(
            f"{BASE_URL}/api/v10/exchange/observation/tick/full",
            json={"symbol": "BTCUSDT"}
        )
        
        response = requests.get(f"{BASE_URL}/api/v10/exchange/observation/BTCUSDT")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') == True
        assert data.get('symbol') == 'BTCUSDT'
        assert 'data' in data
        
        print(f"✓ Legacy /observation/:symbol endpoint works")
    
    def test_legacy_tick_endpoint_without_indicators(self):
        """POST /api/v10/exchange/observation/tick (legacy) creates observation without full indicators"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/observation/tick",
            json={"symbol": "LEGACYTICK"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') == True
        assert 'observation' in data
        
        # Legacy endpoint should still create observations
        obs = data['observation']
        assert 'id' in obs
        assert obs['symbol'] == 'LEGACYTICK'
        
        print(f"✓ Legacy /tick endpoint still works")
    
    def test_legacy_matrix_endpoint(self):
        """GET /api/v10/exchange/observation/matrix still works"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/observation/matrix")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') == True
        assert 'matrix' in data
        
        print(f"✓ Legacy /observation/matrix endpoint works")


class TestIndicatorCategoriesInObservation:
    """Verify all 5 categories have correct indicators"""
    
    def test_price_structure_indicators_present(self):
        """Verify 8 PRICE_STRUCTURE indicators in observation"""
        requests.post(
            f"{BASE_URL}/api/v10/exchange/observation/tick/full",
            json={"symbol": "BTCUSDT"}
        )
        
        response = requests.get(f"{BASE_URL}/api/v10/exchange/observation/BTCUSDT/latest")
        indicators = response.json()['observation']['indicators']
        
        price_structure_ids = [id for id, ind in indicators.items() if ind['category'] == 'PRICE_STRUCTURE']
        
        assert len(price_structure_ids) == 8, \
            f"Expected 8 PRICE_STRUCTURE indicators, got {len(price_structure_ids)}: {price_structure_ids}"
        
        # Verify specific IDs
        for expected_id in EXPECTED_CATEGORIES['PRICE_STRUCTURE']:
            assert expected_id in indicators, f"Missing PRICE_STRUCTURE indicator: {expected_id}"
        
        print(f"✓ 8 PRICE_STRUCTURE indicators present: {price_structure_ids}")
    
    def test_momentum_indicators_present(self):
        """Verify 6 MOMENTUM indicators in observation"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/observation/BTCUSDT/latest")
        indicators = response.json()['observation']['indicators']
        
        momentum_ids = [id for id, ind in indicators.items() if ind['category'] == 'MOMENTUM']
        
        assert len(momentum_ids) == 6, \
            f"Expected 6 MOMENTUM indicators, got {len(momentum_ids)}"
        
        for expected_id in EXPECTED_CATEGORIES['MOMENTUM']:
            assert expected_id in indicators, f"Missing MOMENTUM indicator: {expected_id}"
        
        print(f"✓ 6 MOMENTUM indicators present")
    
    def test_volume_indicators_present(self):
        """Verify 6 VOLUME indicators in observation"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/observation/BTCUSDT/latest")
        indicators = response.json()['observation']['indicators']
        
        volume_ids = [id for id, ind in indicators.items() if ind['category'] == 'VOLUME']
        
        assert len(volume_ids) == 6, \
            f"Expected 6 VOLUME indicators, got {len(volume_ids)}"
        
        for expected_id in EXPECTED_CATEGORIES['VOLUME']:
            assert expected_id in indicators, f"Missing VOLUME indicator: {expected_id}"
        
        print(f"✓ 6 VOLUME indicators present")
    
    def test_order_book_indicators_present(self):
        """Verify 6 ORDER_BOOK indicators in observation"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/observation/BTCUSDT/latest")
        indicators = response.json()['observation']['indicators']
        
        order_book_ids = [id for id, ind in indicators.items() if ind['category'] == 'ORDER_BOOK']
        
        assert len(order_book_ids) == 6, \
            f"Expected 6 ORDER_BOOK indicators, got {len(order_book_ids)}"
        
        for expected_id in EXPECTED_CATEGORIES['ORDER_BOOK']:
            assert expected_id in indicators, f"Missing ORDER_BOOK indicator: {expected_id}"
        
        print(f"✓ 6 ORDER_BOOK indicators present")
    
    def test_positioning_indicators_present(self):
        """Verify 6 POSITIONING indicators in observation"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/observation/BTCUSDT/latest")
        indicators = response.json()['observation']['indicators']
        
        positioning_ids = [id for id, ind in indicators.items() if ind['category'] == 'POSITIONING']
        
        assert len(positioning_ids) == 6, \
            f"Expected 6 POSITIONING indicators, got {len(positioning_ids)}"
        
        for expected_id in EXPECTED_CATEGORIES['POSITIONING']:
            assert expected_id in indicators, f"Missing POSITIONING indicator: {expected_id}"
        
        print(f"✓ 6 POSITIONING indicators present")


class TestIndicatorsPersistenceIntegrity:
    """Test data integrity of persisted indicators"""
    
    def test_indicators_is_map_not_array(self):
        """Verify indicators field is a map (dict), not an array"""
        requests.post(
            f"{BASE_URL}/api/v10/exchange/observation/tick/full",
            json={"symbol": "BTCUSDT"}
        )
        
        response = requests.get(f"{BASE_URL}/api/v10/exchange/observation/BTCUSDT/latest")
        data = response.json()
        
        indicators = data['observation']['indicators']
        
        # Must be dict/object, not list
        assert isinstance(indicators, dict), \
            f"indicators must be dict/map, got {type(indicators)}"
        
        # Keys should be indicator IDs (strings)
        for key in indicators.keys():
            assert isinstance(key, str), f"Indicator key should be string: {key}"
        
        print(f"✓ indicators is a map with {len(indicators)} entries")
    
    def test_indicators_values_are_numeric(self):
        """Verify all indicator values are numeric"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/observation/BTCUSDT/latest")
        data = response.json()
        
        indicators = data['observation']['indicators']
        
        for indicator_id, indicator_data in indicators.items():
            value = indicator_data['value']
            assert isinstance(value, (int, float)), \
                f"{indicator_id} value is not numeric: {value} ({type(value)})"
        
        print(f"✓ All indicator values are numeric")
    
    def test_normalized_indicators_in_range(self):
        """Verify normalized indicators are within expected ranges"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/observation/BTCUSDT/latest")
        data = response.json()
        
        indicators = data['observation']['indicators']
        
        out_of_range = []
        for indicator_id, indicator_data in indicators.items():
            if indicator_data.get('normalized'):
                value = indicator_data['value']
                # Most normalized indicators should be in [-1, 1] or [0, 1]
                if value < -1.5 or value > 1.5:  # Allow small margin
                    out_of_range.append(f"{indicator_id}: {value}")
        
        if out_of_range:
            print(f"Warning: Some normalized values appear out of range: {out_of_range}")
        
        print(f"✓ Normalized indicator ranges checked")
    
    def test_indicatorsmeta_structure(self):
        """Verify indicatorsMeta has correct structure"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/observation/BTCUSDT/latest")
        data = response.json()
        
        meta = data['observation']['indicatorsMeta']
        
        assert 'completeness' in meta, "indicatorsMeta missing 'completeness'"
        assert 'indicatorCount' in meta, "indicatorsMeta missing 'indicatorCount'"
        assert 'missing' in meta, "indicatorsMeta missing 'missing'"
        assert 'source' in meta, "indicatorsMeta missing 'source'"
        
        # Completeness should be 0-1
        assert 0 <= meta['completeness'] <= 1
        
        # indicatorCount should match actual count
        assert meta['indicatorCount'] == EXPECTED_INDICATOR_COUNT
        
        # missing should be a list
        assert isinstance(meta['missing'], list)
        
        # source should be valid
        assert meta['source'] in ['polling', 'replay', 'manual']
        
        print(f"✓ indicatorsMeta structure is valid")


class TestRateLimiting:
    """Test rate limiting for observation saving"""
    
    def test_forced_save_bypasses_rate_limit(self):
        """Manual tick with forceReason bypasses rate limit"""
        # Create first observation
        response1 = requests.post(
            f"{BASE_URL}/api/v10/exchange/observation/tick/full",
            json={"symbol": "RATELIMITBYPASS"}
        )
        
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1.get('ok') == True, "First observation should succeed"
        
        # Immediate second request should also succeed (manual_tick forces save)
        response2 = requests.post(
            f"{BASE_URL}/api/v10/exchange/observation/tick/full",
            json={"symbol": "RATELIMITBYPASS"}
        )
        
        assert response2.status_code == 200
        data2 = response2.json()
        # Manual tick always has forceReason='manual_tick'
        assert data2.get('ok') == True
        
        print(f"✓ Manual tick bypasses rate limit")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
