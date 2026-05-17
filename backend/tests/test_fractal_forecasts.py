"""
Fractal Forecast API Tests
===========================
Tests for the fractal_forecast pipeline endpoints:
- GET /api/fractal/forecasts (with scope, horizon filters)
- POST /api/fractal/forecasts/run (pipeline trigger)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Required fields for each forecast row
REQUIRED_ROW_FIELDS = [
    'scope', 'createdAt', 'evaluateAt', 'horizon', 'entryPrice',
    'targetPrice', 'expectedReturn', 'direction', 'confidence', 'status'
]

# Required fields for summary object
REQUIRED_SUMMARY_FIELDS = [
    'winRate', 'avgError', 'evaluated', 'total', 'pending', 'overdue'
]


class TestFractalForecastsAPI:
    """Tests for GET /api/fractal/forecasts endpoint"""

    def test_get_forecasts_returns_valid_json(self):
        """GET /api/fractal/forecasts?scope=BTC returns valid JSON with ok:true, rows array, summary object"""
        response = requests.get(f"{BASE_URL}/api/fractal/forecasts?scope=BTC")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check ok:true
        assert data.get('ok') is True, "Response should have ok:true"
        
        # Check rows is array
        assert 'rows' in data, "Response should have rows field"
        assert isinstance(data['rows'], list), "rows should be a list"
        
        # Check summary is object
        assert 'summary' in data, "Response should have summary field"
        assert isinstance(data['summary'], dict), "summary should be a dict"
        
        print(f"✓ GET /api/fractal/forecasts?scope=BTC returned {len(data['rows'])} rows")

    def test_forecasts_filter_by_horizon_7d(self):
        """GET /api/fractal/forecasts?scope=BTC&horizon=7D returns only 7D horizon rows"""
        response = requests.get(f"{BASE_URL}/api/fractal/forecasts?scope=BTC&horizon=7D")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        
        # All rows should have horizon=7D
        for row in data['rows']:
            assert row.get('horizon') == '7D', f"Expected horizon 7D, got {row.get('horizon')}"
        
        print(f"✓ GET /api/fractal/forecasts?scope=BTC&horizon=7D returned {len(data['rows'])} rows (all 7D)")

    def test_forecasts_filter_by_horizon_30d(self):
        """GET /api/fractal/forecasts?scope=BTC&horizon=30D returns only 30D horizon rows"""
        response = requests.get(f"{BASE_URL}/api/fractal/forecasts?scope=BTC&horizon=30D")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        
        # All rows should have horizon=30D
        for row in data['rows']:
            assert row.get('horizon') == '30D', f"Expected horizon 30D, got {row.get('horizon')}"
        
        print(f"✓ GET /api/fractal/forecasts?scope=BTC&horizon=30D returned {len(data['rows'])} rows (all 30D)")

    def test_row_has_required_fields(self):
        """Each row has required fields: scope, createdAt, evaluateAt, horizon, entryPrice, targetPrice, expectedReturn, direction, confidence, status"""
        response = requests.get(f"{BASE_URL}/api/fractal/forecasts?scope=BTC")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data['rows']) > 0, "Should have at least one row to test"
        
        for i, row in enumerate(data['rows']):
            for field in REQUIRED_ROW_FIELDS:
                assert field in row, f"Row {i} missing required field: {field}"
        
        print(f"✓ All {len(data['rows'])} rows have all required fields: {REQUIRED_ROW_FIELDS}")

    def test_summary_has_required_fields(self):
        """Summary object contains winRate, avgError, evaluated, total, pending, overdue fields"""
        response = requests.get(f"{BASE_URL}/api/fractal/forecasts?scope=BTC")
        
        assert response.status_code == 200
        data = response.json()
        
        summary = data['summary']
        
        for field in REQUIRED_SUMMARY_FIELDS:
            assert field in summary, f"Summary missing required field: {field}"
        
        # Type checks
        assert isinstance(summary['winRate'], (int, float)), "winRate should be numeric"
        assert isinstance(summary['avgError'], (int, float)), "avgError should be numeric"
        assert isinstance(summary['evaluated'], int), "evaluated should be int"
        assert isinstance(summary['total'], int), "total should be int"
        assert isinstance(summary['pending'], int), "pending should be int"
        assert isinstance(summary['overdue'], int), "overdue should be int"
        
        print(f"✓ Summary has all required fields: {REQUIRED_SUMMARY_FIELDS}")
        print(f"  - total: {summary['total']}, pending: {summary['pending']}, evaluated: {summary['evaluated']}")

    def test_row_field_types(self):
        """Verify row field types are correct"""
        response = requests.get(f"{BASE_URL}/api/fractal/forecasts?scope=BTC")
        
        assert response.status_code == 200
        data = response.json()
        
        if len(data['rows']) == 0:
            pytest.skip("No rows to verify field types")
        
        row = data['rows'][0]
        
        # String fields
        assert isinstance(row['scope'], str), "scope should be string"
        assert isinstance(row['createdAt'], str), "createdAt should be string (ISO date)"
        assert isinstance(row['evaluateAt'], str), "evaluateAt should be string (ISO date)"
        assert isinstance(row['horizon'], str), "horizon should be string"
        assert isinstance(row['direction'], str), "direction should be string"
        assert isinstance(row['status'], str), "status should be string"
        
        # Numeric fields
        assert isinstance(row['entryPrice'], (int, float)), "entryPrice should be numeric"
        assert isinstance(row['targetPrice'], (int, float)), "targetPrice should be numeric"
        assert isinstance(row['expectedReturn'], (int, float)), "expectedReturn should be numeric"
        assert isinstance(row['confidence'], (int, float)), "confidence should be numeric"
        
        print(f"✓ Row field types verified correctly")


class TestFractalForecastsPipeline:
    """Tests for POST /api/fractal/forecasts/run endpoint"""

    def test_pipeline_trigger_returns_ok(self):
        """POST /api/fractal/forecasts/run triggers pipeline and returns ok:true with resolved/generated counts"""
        response = requests.post(f"{BASE_URL}/api/fractal/forecasts/run")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check ok:true
        assert data.get('ok') is True, "Response should have ok:true"
        
        # Check resolved and generated counts
        assert 'resolved' in data, "Response should have resolved field"
        assert 'generated' in data, "Response should have generated field"
        
        assert isinstance(data['resolved'], int), "resolved should be int"
        assert isinstance(data['generated'], int), "generated should be int"
        
        print(f"✓ POST /api/fractal/forecasts/run returned ok:true, resolved={data['resolved']}, generated={data['generated']}")


class TestFractalForecastsValidation:
    """Data validation tests"""

    def test_direction_values(self):
        """Direction field should be UP, DOWN, or NEUTRAL"""
        response = requests.get(f"{BASE_URL}/api/fractal/forecasts?scope=BTC")
        
        assert response.status_code == 200
        data = response.json()
        
        valid_directions = {'UP', 'DOWN', 'NEUTRAL'}
        
        for row in data['rows']:
            assert row['direction'] in valid_directions, f"Invalid direction: {row['direction']}"
        
        print(f"✓ All rows have valid direction values (UP/DOWN/NEUTRAL)")

    def test_status_values(self):
        """Status field should be pending or resolved"""
        response = requests.get(f"{BASE_URL}/api/fractal/forecasts?scope=BTC")
        
        assert response.status_code == 200
        data = response.json()
        
        valid_statuses = {'pending', 'resolved'}
        
        for row in data['rows']:
            assert row['status'] in valid_statuses, f"Invalid status: {row['status']}"
        
        print(f"✓ All rows have valid status values (pending/resolved)")

    def test_horizon_values(self):
        """Horizon field should be valid (7D, 30D, 90D, 180D, 365D)"""
        response = requests.get(f"{BASE_URL}/api/fractal/forecasts?scope=BTC")
        
        assert response.status_code == 200
        data = response.json()
        
        valid_horizons = {'7D', '30D', '90D', '180D', '365D'}
        
        for row in data['rows']:
            assert row['horizon'] in valid_horizons, f"Invalid horizon: {row['horizon']}"
        
        print(f"✓ All rows have valid horizon values")

    def test_confidence_in_range(self):
        """Confidence should be between 0 and 1"""
        response = requests.get(f"{BASE_URL}/api/fractal/forecasts?scope=BTC")
        
        assert response.status_code == 200
        data = response.json()
        
        for row in data['rows']:
            conf = row['confidence']
            assert 0 <= conf <= 1, f"Confidence out of range: {conf}"
        
        print(f"✓ All confidence values are in valid range [0, 1]")

    def test_prices_are_positive(self):
        """Entry and target prices should be positive"""
        response = requests.get(f"{BASE_URL}/api/fractal/forecasts?scope=BTC")
        
        assert response.status_code == 200
        data = response.json()
        
        for row in data['rows']:
            assert row['entryPrice'] > 0, f"Entry price should be positive: {row['entryPrice']}"
            assert row['targetPrice'] > 0, f"Target price should be positive: {row['targetPrice']}"
        
        print(f"✓ All prices are positive")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
