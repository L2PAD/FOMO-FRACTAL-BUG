"""
S10.5 Exchange Patterns API Tests
Tests for 14 exchange patterns across 5 categories (FLOW, OI, LIQUIDATION, VOLUME, STRUCTURE)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPatternEndpoints:
    """Test pattern API endpoints"""

    def test_get_patterns_for_btcusdt(self):
        """GET /api/v10/exchange/patterns/:symbol - returns detected patterns for BTCUSDT"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/patterns/BTCUSDT")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert data['symbol'] == 'BTCUSDT'
        assert 'patternCount' in data
        assert 'hasConflict' in data
        assert 'summary' in data
        assert 'bullish' in data['summary']
        assert 'bearish' in data['summary']
        assert 'neutral' in data['summary']
        assert 'patterns' in data
        assert 'lastUpdated' in data
        print(f"✓ BTCUSDT patterns: {data['patternCount']} detected")

    def test_get_patterns_for_ethusdt(self):
        """GET /api/v10/exchange/patterns/:symbol - returns detected patterns for ETHUSDT"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/patterns/ETHUSDT")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert data['symbol'] == 'ETHUSDT'
        print(f"✓ ETHUSDT patterns: {data['patternCount']} detected")

    def test_get_all_patterns(self):
        """GET /api/v10/exchange/patterns - returns all pattern states"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/patterns")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert 'count' in data
        assert 'data' in data
        assert isinstance(data['data'], list)
        print(f"✓ All patterns: {data['count']} symbol states")

    def test_get_active_patterns(self):
        """GET /api/v10/exchange/patterns/active - returns active patterns across symbols"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/patterns/active")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert 'totalCount' in data
        assert 'symbolCount' in data
        assert 'bySymbol' in data
        print(f"✓ Active patterns: {data['totalCount']} across {data['symbolCount']} symbols")

    def test_get_pattern_library(self):
        """GET /api/v10/exchange/patterns/library - returns 14 pattern definitions"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/patterns/library")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert data['totalPatterns'] == 14
        assert 'byCategory' in data
        assert data['byCategory']['FLOW'] == 4
        assert data['byCategory']['OI'] == 3
        assert data['byCategory']['LIQUIDATION'] == 3
        assert data['byCategory']['VOLUME'] == 2
        assert data['byCategory']['STRUCTURE'] == 2
        assert 'patterns' in data
        assert len(data['patterns']) == 14
        print(f"✓ Pattern library: {data['totalPatterns']} patterns in 5 categories")

    def test_get_pattern_history(self):
        """GET /api/v10/exchange/patterns/history/:symbol - returns pattern history"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/patterns/history/BTCUSDT")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert data['symbol'] == 'BTCUSDT'
        assert 'count' in data
        assert 'data' in data
        assert isinstance(data['data'], list)
        print(f"✓ BTCUSDT history: {data['count']} entries")

    def test_pattern_detail_structure(self):
        """Validate pattern detail structure for symbol"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/patterns/BTCUSDT")
        assert response.status_code == 200
        
        data = response.json()
        if data['patterns'] and len(data['patterns']) > 0:
            pattern = data['patterns'][0]
            # Required fields
            assert 'id' in pattern
            assert 'name' in pattern
            assert 'category' in pattern
            assert 'categoryLabel' in pattern
            assert 'categoryIcon' in pattern
            assert 'direction' in pattern
            assert 'strength' in pattern
            assert 'confidence' in pattern
            assert 'conditions' in pattern
            assert 'metrics' in pattern
            assert 'timeframe' in pattern
            assert 'detectedAt' in pattern
            
            # Direction values
            assert pattern['direction'] in ['BULLISH', 'BEARISH', 'NEUTRAL']
            # Strength values
            assert pattern['strength'] in ['WEAK', 'MEDIUM', 'STRONG']
            # Category values
            assert pattern['category'] in ['FLOW', 'OI', 'LIQUIDATION', 'VOLUME', 'STRUCTURE']
            # Confidence range
            assert 0 <= pattern['confidence'] <= 1
            print(f"✓ Pattern detail structure validated: {pattern['name']}")
        else:
            pytest.skip("No patterns detected to validate structure")

    def test_pattern_library_definitions(self):
        """Validate all 14 pattern definitions in library"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/patterns/library")
        assert response.status_code == 200
        
        data = response.json()
        patterns = data['patterns']
        
        expected_patterns = [
            # FLOW (4)
            'FLOW_AGGRESSIVE_BUY_ABSORPTION',
            'FLOW_AGGRESSIVE_SELL_ABSORPTION',
            'FLOW_BUYER_EXHAUSTION',
            'FLOW_SELLER_EXHAUSTION',
            # OI (3)
            'OI_EXPANSION_FLAT_PRICE',
            'OI_COLLAPSE_AFTER_EXPANSION',
            'OI_DIVERGENCE_PRICE',
            # LIQUIDATION (3)
            'LIQ_LONG_SQUEEZE_CONTINUATION',
            'LIQ_SHORT_SQUEEZE_EXHAUSTION',
            'LIQ_CASCADE_EXHAUSTION_ZONE',
            # VOLUME (2)
            'VOL_SPIKE_NO_FOLLOWTHROUGH',
            'VOL_COMPRESSION',
            # STRUCTURE (2)
            'STRUCT_RANGE_TRAP',
            'STRUCT_TREND_ACCEPTANCE',
        ]
        
        pattern_ids = [p['id'] for p in patterns]
        for expected_id in expected_patterns:
            assert expected_id in pattern_ids, f"Missing pattern: {expected_id}"
        
        print(f"✓ All 14 pattern definitions present")

    def test_conflict_detection_logic(self):
        """Test that conflict detection works (hasConflict = bullish + bearish > 0)"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/patterns/BTCUSDT")
        assert response.status_code == 200
        
        data = response.json()
        summary = data['summary']
        has_conflict = data['hasConflict']
        
        # Conflict = both bullish and bearish present
        expected_conflict = summary['bullish'] > 0 and summary['bearish'] > 0
        assert has_conflict == expected_conflict
        print(f"✓ Conflict detection: hasConflict={has_conflict} (bullish={summary['bullish']}, bearish={summary['bearish']})")

    def test_detection_duration_metric(self):
        """Test that detection duration metric is provided"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/patterns/BTCUSDT")
        assert response.status_code == 200
        
        data = response.json()
        assert 'detectionDurationMs' in data
        assert isinstance(data['detectionDurationMs'], (int, float))
        print(f"✓ Detection duration: {data['detectionDurationMs']}ms")


class TestSymbolSupport:
    """Test all supported symbols"""

    @pytest.mark.parametrize("symbol", ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"])
    def test_all_symbols_supported(self, symbol):
        """Test pattern detection for all supported symbols"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/patterns/{symbol}")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert data['symbol'] == symbol
        print(f"✓ {symbol} patterns: ok")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
