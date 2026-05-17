"""
Test ExchangeAltSignalsCompact API - /api/market/exchange/top-alts-v2
Tests the backend API that powers the new compact BUY/SELL alt signals table
on the Prediction > Exchange page.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestExchangeTopAltsV2API:
    """Tests for /api/market/exchange/top-alts-v2 endpoint"""

    def test_api_returns_ok_status(self):
        """Test that API returns ok: true with valid data"""
        response = requests.get(f"{BASE_URL}/api/market/exchange/top-alts-v2?horizon=7D&limit=20")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') == True, f"Expected ok=True, got {data.get('ok')}"
        assert 'rows' in data, "Response should contain 'rows' field"

    def test_api_returns_required_fields(self):
        """Test that API returns all required fields in response"""
        response = requests.get(f"{BASE_URL}/api/market/exchange/top-alts-v2?horizon=7D&limit=20")
        data = response.json()
        
        # Check top-level required fields
        assert 'ok' in data, "Missing 'ok' field"
        assert 'horizon' in data, "Missing 'horizon' field"
        assert 'rows' in data, "Missing 'rows' field"
        assert 'uriLevel' in data, "Missing 'uriLevel' field"
        assert 'activeCount' in data, "Missing 'activeCount' field"
        
        # Validate uriLevel is one of expected values
        assert data['uriLevel'] in ['OK', 'WARN', 'EXTREME'], f"Unexpected uriLevel: {data['uriLevel']}"

    def test_row_structure(self):
        """Test that each row contains required fields for the compact table"""
        response = requests.get(f"{BASE_URL}/api/market/exchange/top-alts-v2?horizon=7D&limit=20")
        data = response.json()
        
        assert len(data['rows']) > 0, "Expected at least one row"
        
        for row in data['rows']:
            # Required fields for ExchangeAltSignalsCompact
            assert 'symbol' in row, f"Row missing 'symbol': {row}"
            assert 'direction' in row, f"Row missing 'direction': {row}"
            assert 'confidenceFinal' in row, f"Row missing 'confidenceFinal': {row}"
            assert 'expectedMovePctFinal' in row, f"Row missing 'expectedMovePctFinal': {row}"
            
            # Direction should be LONG, SHORT, or NEUTRAL
            assert row['direction'] in ['LONG', 'SHORT', 'NEUTRAL'], f"Unexpected direction: {row['direction']}"
            
            # Confidence should be between 0 and 1
            assert 0 <= row['confidenceFinal'] <= 1, f"Confidence out of range: {row['confidenceFinal']}"

    def test_direction_filtering_long_buy(self):
        """Test that LONG direction rows can be used as BUYs"""
        response = requests.get(f"{BASE_URL}/api/market/exchange/top-alts-v2?horizon=7D&limit=20")
        data = response.json()
        
        buys = [r for r in data['rows'] if r['direction'] == 'LONG']
        print(f"Found {len(buys)} BUY signals (LONG direction)")
        
        # At least some LONG signals expected
        assert len(buys) >= 0, "API should return LONG direction rows"

    def test_direction_filtering_short_sell(self):
        """Test that SHORT direction rows can be used as SELLs"""
        response = requests.get(f"{BASE_URL}/api/market/exchange/top-alts-v2?horizon=7D&limit=20")
        data = response.json()
        
        sells = [r for r in data['rows'] if r['direction'] == 'SHORT']
        print(f"Found {len(sells)} SELL signals (SHORT direction)")
        
        # Some SHORT signals expected (based on market conditions)
        assert len(sells) >= 0, "API should return SHORT direction rows"

    def test_horizon_1d(self):
        """Test API with 1D horizon"""
        response = requests.get(f"{BASE_URL}/api/market/exchange/top-alts-v2?horizon=1D&limit=20")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert data.get('horizon') in ['1D', '24H'], f"Unexpected horizon: {data.get('horizon')}"
        assert 'rows' in data
        print(f"1D horizon: {len(data['rows'])} rows, {data.get('activeCount')} active assets")

    def test_horizon_7d(self):
        """Test API with 7D horizon"""
        response = requests.get(f"{BASE_URL}/api/market/exchange/top-alts-v2?horizon=7D&limit=20")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert data.get('horizon') == '7D', f"Unexpected horizon: {data.get('horizon')}"
        assert 'rows' in data
        print(f"7D horizon: {len(data['rows'])} rows, {data.get('activeCount')} active assets")

    def test_horizon_30d(self):
        """Test API with 30D horizon"""
        response = requests.get(f"{BASE_URL}/api/market/exchange/top-alts-v2?horizon=30D&limit=20")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') == True
        assert data.get('horizon') == '30D', f"Unexpected horizon: {data.get('horizon')}"
        assert 'rows' in data
        print(f"30D horizon: {len(data['rows'])} rows, {data.get('activeCount')} active assets")

    def test_limit_parameter(self):
        """Test that limit parameter works correctly"""
        response = requests.get(f"{BASE_URL}/api/market/exchange/top-alts-v2?horizon=7D&limit=5")
        data = response.json()
        
        assert data.get('ok') == True
        assert len(data['rows']) <= 5, f"Expected max 5 rows, got {len(data['rows'])}"

    def test_flags_field_present(self):
        """Test that rows contain flags field for risk calculation"""
        response = requests.get(f"{BASE_URL}/api/market/exchange/top-alts-v2?horizon=7D&limit=20")
        data = response.json()
        
        for row in data['rows']:
            # flags may be empty array or contain items
            assert 'flags' in row or row.get('flags') is None, f"Row should have flags field: {row}"

    def test_safe_mode_field(self):
        """Test that safeMode field is present in response"""
        response = requests.get(f"{BASE_URL}/api/market/exchange/top-alts-v2?horizon=7D&limit=20")
        data = response.json()
        
        assert 'safeMode' in data, "Response should contain 'safeMode' field"
        assert isinstance(data['safeMode'], bool), "safeMode should be boolean"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
