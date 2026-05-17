"""
Test Suite for Price vs Expectation V2 - Blocks 20-27
======================================================

Tests:
- Block 20: Model Health Panel metrics
- Block 21: Multi-Horizon Engine (1D, 7D, 30D)
- Block 22 & 25: Layer Drivers with adaptive weighting
- Block 23: Outcome markers (TP/FP/FN/WEAK)
- Block 26: Errors layer support
- Block 27: Forecast projection (futurePoint, futureBand)
- 24H Forecast card data (target, confidence, band, evaluate time)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBlock20ModelHealthPanel:
    """Block 20: Model Health Panel - verify all metrics are returned correctly"""
    
    def test_api_returns_metrics(self):
        """API should return metrics object with all required fields"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d&horizon=1D")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        
        metrics = data.get('metrics')
        assert metrics is not None, "Metrics should be present in response"
        
        # Verify all required metrics fields
        required_fields = [
            'horizon', 'sampleCount', 'evaluatedCount', 
            'directionMatchPct', 'hitRatePct', 'avgDeviationPct',
            'calibrationScore', 'expectedCalibration', 'modelScore', 'breakdown'
        ]
        for field in required_fields:
            assert field in metrics, f"Missing required field: {field}"
    
    def test_metrics_values_in_valid_range(self):
        """Metrics percentage values should be between 0-100"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d&horizon=1D")
        data = response.json()
        metrics = data.get('metrics', {})
        
        if metrics.get('evaluatedCount', 0) > 0:
            # Percentage fields should be 0-100
            pct_fields = ['directionMatchPct', 'hitRatePct', 'calibrationScore', 'modelScore']
            for field in pct_fields:
                value = metrics.get(field, 0)
                assert 0 <= value <= 100, f"{field} should be between 0-100, got {value}"
    
    def test_breakdown_structure(self):
        """Breakdown should contain TP, FP, FN, WEAK counts"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d&horizon=1D")
        data = response.json()
        breakdown = data.get('metrics', {}).get('breakdown', {})
        
        for label in ['tp', 'fp', 'fn', 'weak']:
            assert label in breakdown, f"Missing breakdown label: {label}"
            assert isinstance(breakdown[label], int), f"Breakdown {label} should be integer"


class TestBlock21MultiHorizonEngine:
    """Block 21: Multi-Horizon Engine - test horizon selector changes data"""
    
    @pytest.mark.parametrize("horizon", ["1D", "7D", "30D"])
    def test_horizon_parameter_accepted(self, horizon):
        """API should accept all three horizon values"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d&horizon={horizon}")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert data.get('horizon') == horizon
    
    def test_horizon_changes_metrics(self):
        """Different horizons should return different metrics.horizon"""
        horizons = ["1D", "7D", "30D"]
        responses = {}
        
        for h in horizons:
            response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d&horizon={h}")
            data = response.json()
            responses[h] = data.get('metrics', {}).get('horizon')
        
        # Each horizon should match its metrics.horizon
        for h in horizons:
            assert responses[h] == h, f"metrics.horizon should be {h}, got {responses[h]}"


class TestBlock22And25LayerDrivers:
    """Block 22 & 25: Layer Drivers with adaptive weighting"""
    
    def test_drivers_structure(self):
        """Drivers should have exchange, onchain, sentiment, directionBias"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d&horizon=1D")
        data = response.json()
        drivers = data.get('drivers')
        
        assert drivers is not None, "Drivers should be present"
        
        required_fields = ['exchange', 'onchain', 'sentiment', 'directionBias']
        for field in required_fields:
            assert field in drivers, f"Missing driver field: {field}"
    
    def test_direction_bias_valid_values(self):
        """directionBias should be UP, DOWN, or FLAT"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d&horizon=1D")
        data = response.json()
        direction = data.get('drivers', {}).get('directionBias')
        
        assert direction in ['UP', 'DOWN', 'FLAT'], f"Invalid directionBias: {direction}"


class TestBlock23OutcomeMarkers:
    """Block 23: Outcome markers on chart (TP/FP/FN/WEAK)"""
    
    def test_outcome_markers_structure(self):
        """outcomeMarkers should be an array with proper structure"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d&horizon=1D")
        data = response.json()
        markers = data.get('outcomeMarkers', [])
        
        assert isinstance(markers, list), "outcomeMarkers should be a list"
        
        if len(markers) > 0:
            marker = markers[0]
            required_fields = ['ts', 'label', 'direction', 'expectedMovePct', 'actualMovePct', 'confidence']
            for field in required_fields:
                assert field in marker, f"Missing marker field: {field}"
    
    def test_outcome_marker_labels_valid(self):
        """Outcome labels should be TP, FP, FN, or WEAK"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d&horizon=1D")
        data = response.json()
        markers = data.get('outcomeMarkers', [])
        
        valid_labels = ['TP', 'FP', 'FN', 'WEAK']
        for marker in markers:
            label = marker.get('label')
            assert label in valid_labels, f"Invalid outcome label: {label}"


class TestBlock26ErrorsLayer:
    """Block 26: Errors layer - FP and FN markers should have error data"""
    
    def test_error_markers_have_deviation_data(self):
        """Error markers (FP/FN) should have expected and actual move percentages"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d&horizon=1D")
        data = response.json()
        markers = data.get('outcomeMarkers', [])
        
        error_markers = [m for m in markers if m.get('label') in ['FP', 'FN']]
        
        for marker in error_markers:
            assert 'expectedMovePct' in marker, "Error marker should have expectedMovePct"
            assert 'actualMovePct' in marker, "Error marker should have actualMovePct"
            assert isinstance(marker['expectedMovePct'], (int, float))
            assert isinstance(marker['actualMovePct'], (int, float))


class TestBlock27ForecastProjection:
    """Block 27: Forecast projection line with target price label"""
    
    def test_future_point_structure(self):
        """futurePoint should have direction, targetPrice, confidence"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d&horizon=1D")
        data = response.json()
        fp = data.get('layers', {}).get('meta', {}).get('futurePoint')
        
        if fp is not None:
            required_fields = ['direction', 'targetPrice', 'confidence', 'ts']
            for field in required_fields:
                assert field in fp, f"Missing futurePoint field: {field}"
            
            assert fp['direction'] in ['UP', 'DOWN', 'FLAT']
            assert isinstance(fp['targetPrice'], (int, float))
            assert 0 <= fp['confidence'] <= 1
    
    def test_future_band_structure(self):
        """futureBand should have ts, upper, lower"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d&horizon=1D")
        data = response.json()
        fb = data.get('layers', {}).get('meta', {}).get('futureBand')
        
        if fb is not None:
            required_fields = ['ts', 'upper', 'lower']
            for field in required_fields:
                assert field in fb, f"Missing futureBand field: {field}"
            
            assert fb['upper'] > fb['lower'], "Upper band should be greater than lower band"


class Test24HForecastCard:
    """24H Forecast Card - target, confidence, band, evaluate time"""
    
    def test_forecast_card_data_available(self):
        """API should return data needed for 24H Forecast card"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d&horizon=1D")
        data = response.json()
        
        meta = data.get('layers', {}).get('meta', {})
        fp = meta.get('futurePoint')
        fb = meta.get('futureBand')
        
        # If there's a pending forecast, verify all card fields are available
        if fp is not None:
            # Target price
            assert 'targetPrice' in fp
            # Confidence
            assert 'confidence' in fp
            # Expected move percentage (for display)
            assert 'expectedMovePct' in fp
            # Direction
            assert 'direction' in fp
        
        if fb is not None:
            # Band values for confidence corridor
            assert 'upper' in fb
            assert 'lower' in fb
            # Evaluation time
            assert 'ts' in fb


class TestAssetSelector:
    """Test asset selector works with different assets"""
    
    @pytest.mark.parametrize("asset", ["BTC", "ETH", "SOL", "BNB"])
    def test_different_assets(self, asset):
        """API should accept all supported assets"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset={asset}&range=7d&horizon=1D")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert data.get('asset') == asset


class TestRangeSelector:
    """Test range selector works with different ranges"""
    
    @pytest.mark.parametrize("range_val", ["24h", "7d", "30d", "90d"])
    def test_different_ranges(self, range_val):
        """API should accept all supported ranges"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range={range_val}&horizon=1D")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert data.get('range') == range_val


class TestForecastStats:
    """Test forecast stats endpoint"""
    
    def test_forecast_stats_endpoint(self):
        """GET /api/market/chart/forecast/stats should return stats"""
        response = requests.get(f"{BASE_URL}/api/market/chart/forecast/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        
        # Should have count fields
        assert 'total' in data
        assert 'pending' in data
        assert 'evaluated' in data


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
