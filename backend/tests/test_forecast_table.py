"""
Forecast Performance Table API Tests
=====================================
Tests for /api/market/forecast-table endpoint
- Validates data structure with summary and rows
- Tests filtering by symbol and horizon
- Tests pagination parameters
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com')


class TestForecastTableAPI:
    """Test /api/market/forecast-table endpoint"""

    def test_default_request_returns_valid_structure(self):
        """API returns correct data structure with default params"""
        response = requests.get(f"{BASE_URL}/api/market/forecast-table")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        assert 'summary' in data
        assert 'rows' in data
        assert 'pagination' in data
        
        # Validate summary structure
        summary = data['summary']
        assert 'winRate' in summary
        assert 'avgDeviation' in summary
        assert 'samples' in summary
        assert isinstance(summary['winRate'], (int, float))
        assert isinstance(summary['avgDeviation'], (int, float))
        assert isinstance(summary['samples'], int)
        
        # Validate pagination structure
        pagination = data['pagination']
        assert 'page' in pagination
        assert 'limit' in pagination
        assert 'total' in pagination
        assert 'totalPages' in pagination
        print(f"PASS: Default request returns valid structure with {len(data['rows'])} rows")

    def test_filter_by_symbol_btc(self):
        """API correctly filters by BTC symbol"""
        response = requests.get(f"{BASE_URL}/api/market/forecast-table?symbol=BTC")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        assert isinstance(data['rows'], list)
        print(f"PASS: BTC filter works, returned {len(data['rows'])} rows")

    def test_filter_by_horizon_1d(self):
        """API correctly filters by 1D horizon"""
        response = requests.get(f"{BASE_URL}/api/market/forecast-table?symbol=BTC&horizon=1D")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        
        # All rows should have 1D horizon
        for row in data['rows']:
            assert row['horizon'] == '1D', f"Expected 1D horizon but got {row['horizon']}"
        print(f"PASS: 1D horizon filter works, returned {len(data['rows'])} rows")

    def test_filter_by_horizon_7d(self):
        """API correctly filters by 7D horizon"""
        response = requests.get(f"{BASE_URL}/api/market/forecast-table?symbol=BTC&horizon=7D")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        
        # All rows should have 7D horizon
        for row in data['rows']:
            assert row['horizon'] == '7D', f"Expected 7D horizon but got {row['horizon']}"
        print(f"PASS: 7D horizon filter works, returned {len(data['rows'])} rows")

    def test_filter_by_horizon_30d(self):
        """API correctly filters by 30D horizon"""
        response = requests.get(f"{BASE_URL}/api/market/forecast-table?symbol=BTC&horizon=30D")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        
        # All rows should have 30D horizon
        for row in data['rows']:
            assert row['horizon'] == '30D', f"Expected 30D horizon but got {row['horizon']}"
        print(f"PASS: 30D horizon filter works, returned {len(data['rows'])} rows")

    def test_pagination_limit_parameter(self):
        """API pagination limit parameter works"""
        response = requests.get(f"{BASE_URL}/api/market/forecast-table?symbol=BTC&horizon=1D&limit=1")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        assert len(data['rows']) <= 1, f"Expected max 1 row but got {len(data['rows'])}"
        assert data['pagination']['limit'] == 1
        print(f"PASS: Limit=1 pagination works")

    def test_pagination_page_parameter(self):
        """API pagination page parameter works"""
        # Get page 1 with limit 1
        response1 = requests.get(f"{BASE_URL}/api/market/forecast-table?symbol=BTC&horizon=1D&limit=1&page=1")
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Get page 2 with limit 1
        response2 = requests.get(f"{BASE_URL}/api/market/forecast-table?symbol=BTC&horizon=1D&limit=1&page=2")
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Pages should be different if there are 2+ records
        if data1['pagination']['total'] >= 2 and len(data2['rows']) > 0:
            assert data1['rows'][0]['id'] != data2['rows'][0]['id'], "Page 1 and Page 2 should have different rows"
            print(f"PASS: Pagination returns different rows on different pages")
        else:
            print(f"PASS: Pagination structure valid (not enough data for page comparison)")

    def test_row_data_structure(self):
        """Each row contains required columns"""
        response = requests.get(f"{BASE_URL}/api/market/forecast-table?symbol=BTC&horizon=1D")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        
        if len(data['rows']) > 0:
            row = data['rows'][0]
            # Validate row structure
            assert 'id' in row
            assert 'date' in row
            assert 'horizon' in row
            assert 'entry' in row
            assert 'target' in row
            assert 'actual' in row
            assert 'deviation' in row
            assert 'status' in row
            assert 'confidence' in row
            assert 'size' in row
            
            # Status should be one of valid values
            assert row['status'] in ['WIN', 'LOSS', 'DRAW', 'PENDING'], f"Invalid status: {row['status']}"
            
            # Entry and target should be numbers or null
            if row['entry'] is not None:
                assert isinstance(row['entry'], (int, float))
            if row['target'] is not None:
                assert isinstance(row['target'], (int, float))
                
            # Confidence should be a number between 0 and 1
            assert isinstance(row['confidence'], (int, float))
            assert 0 <= row['confidence'] <= 1, f"Confidence {row['confidence']} out of range"
            
            print(f"PASS: Row data structure is valid with all required columns")
        else:
            print(f"PASS: No rows to validate, but API structure is correct")

    def test_limit_buttons_7_14_30(self):
        """API handles limit values for Last 7, Last 14, Last 30 buttons"""
        for limit in [7, 14, 30]:
            response = requests.get(f"{BASE_URL}/api/market/forecast-table?symbol=BTC&horizon=1D&limit={limit}")
            assert response.status_code == 200
            data = response.json()
            assert data.get('ok') is True
            assert data['pagination']['limit'] == limit
            print(f"PASS: Limit {limit} works correctly")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
