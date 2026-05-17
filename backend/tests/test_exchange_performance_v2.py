"""
Exchange Performance Table V2 API Tests
Tests the /api/market/exchange/performance-v2 endpoint
Verifies: data structure, Win Rate formula, fields, outcomes, and directions
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestExchangePerformanceV2API:
    """Test suite for Exchange Performance V2 API endpoint"""
    
    @pytest.fixture
    def api_response(self):
        """Fetch API response once for multiple tests"""
        url = f"{BASE_URL}/api/market/exchange/performance-v2?symbol=BTC&horizon=7D&limit=30"
        response = requests.get(url, timeout=30)
        return response
    
    def test_api_returns_200(self, api_response):
        """API should return 200 status code"""
        assert api_response.status_code == 200, f"Expected 200, got {api_response.status_code}"
        print("PASS: API returns 200 status code")
    
    def test_response_has_ok_true(self, api_response):
        """Response should have ok: true"""
        data = api_response.json()
        assert data.get('ok') == True, f"Expected ok=true, got {data.get('ok')}"
        print("PASS: Response has ok=true")
    
    def test_response_has_rows_array(self, api_response):
        """Response should have rows array"""
        data = api_response.json()
        assert 'rows' in data, "Response missing 'rows' field"
        assert isinstance(data['rows'], list), f"rows should be list, got {type(data['rows'])}"
        print(f"PASS: Response has rows array with {len(data['rows'])} items")
    
    def test_response_has_summary_object(self, api_response):
        """Response should have summary object"""
        data = api_response.json()
        assert 'summary' in data, "Response missing 'summary' field"
        assert isinstance(data['summary'], dict), f"summary should be dict, got {type(data['summary'])}"
        print("PASS: Response has summary object")
    
    def test_summary_fields(self, api_response):
        """Summary should have required fields: total, evaluated, wins, losses, weak, winRate, avgReturn"""
        data = api_response.json()
        summary = data['summary']
        required_fields = ['total', 'evaluated', 'wins', 'losses', 'weak', 'winRate', 'avgReturn']
        for field in required_fields:
            assert field in summary, f"Summary missing required field: {field}"
        print(f"PASS: Summary has all required fields: {required_fields}")
        print(f"  - total={summary['total']}, evaluated={summary['evaluated']}")
        print(f"  - wins={summary['wins']}, losses={summary['losses']}, weak={summary['weak']}")
        print(f"  - winRate={summary['winRate']:.4f}, avgReturn={summary['avgReturn']:.4f}")


class TestWinRateFormula:
    """Test Win Rate formula: TP / (TP + FP + WEAK)"""
    
    def test_win_rate_formula_is_correct(self):
        """Verify Win Rate = TP / (TP + FP + WEAK) excluding PENDING"""
        url = f"{BASE_URL}/api/market/exchange/performance-v2?symbol=BTC&horizon=7D&limit=30"
        response = requests.get(url, timeout=30)
        data = response.json()
        
        summary = data['summary']
        wins = summary['wins']  # TP count
        losses = summary['losses']  # FP count
        weak = summary['weak']  # WEAK count
        reported_win_rate = summary['winRate']
        
        # Calculate expected win rate
        denominator = wins + losses + weak
        expected_win_rate = wins / denominator if denominator > 0 else 0
        
        # Allow small floating point tolerance
        assert abs(reported_win_rate - expected_win_rate) < 0.0001, \
            f"Win Rate mismatch: reported={reported_win_rate}, expected={expected_win_rate}"
        
        print(f"PASS: Win Rate formula verified")
        print(f"  - TP={wins}, FP={losses}, WEAK={weak}")
        print(f"  - Formula: {wins}/({wins}+{losses}+{weak}) = {expected_win_rate:.4f}")
        print(f"  - Reported: {reported_win_rate:.4f}")


class TestRowStructure:
    """Test individual row fields"""
    
    @pytest.fixture
    def sample_row(self):
        """Get a sample row from API"""
        url = f"{BASE_URL}/api/market/exchange/performance-v2?symbol=BTC&horizon=7D&limit=10"
        response = requests.get(url, timeout=30)
        data = response.json()
        if data['rows']:
            return data['rows'][0]
        pytest.skip("No rows returned by API")
    
    def test_row_has_raw_and_final_target(self, sample_row):
        """Row should have rawTarget and finalTarget fields"""
        assert 'rawTarget' in sample_row, "Row missing rawTarget field"
        assert 'finalTarget' in sample_row, "Row missing finalTarget field"
        print(f"PASS: Row has rawTarget={sample_row['rawTarget']:.2f} and finalTarget={sample_row['finalTarget']:.2f}")
    
    def test_row_has_raw_and_final_confidence(self, sample_row):
        """Row should have rawConfidence and finalConfidence fields"""
        assert 'rawConfidence' in sample_row, "Row missing rawConfidence field"
        assert 'finalConfidence' in sample_row, "Row missing finalConfidence field"
        print(f"PASS: Row has rawConfidence={sample_row['rawConfidence']:.4f} and finalConfidence={sample_row['finalConfidence']:.4f}")
    
    def test_row_has_direction_field(self, sample_row):
        """Row should have direction field with valid value"""
        assert 'direction' in sample_row, "Row missing direction field"
        valid_directions = ['LONG', 'SHORT', 'NEUTRAL']
        assert sample_row['direction'] in valid_directions, \
            f"Invalid direction: {sample_row['direction']}, expected one of {valid_directions}"
        print(f"PASS: Row has valid direction={sample_row['direction']}")
    
    def test_row_has_outcome_field(self, sample_row):
        """Row should have outcome field with valid value"""
        assert 'outcome' in sample_row, "Row missing outcome field"
        valid_outcomes = ['TP', 'WEAK', 'FP', 'FN', 'PENDING', 'VOIDED']
        assert sample_row['outcome'] in valid_outcomes, \
            f"Invalid outcome: {sample_row['outcome']}, expected one of {valid_outcomes}"
        print(f"PASS: Row has valid outcome={sample_row['outcome']}")
    
    def test_row_has_entry_and_actual(self, sample_row):
        """Row should have entry and actual fields"""
        assert 'entry' in sample_row, "Row missing entry field"
        assert 'actual' in sample_row, "Row missing actual field"
        print(f"PASS: Row has entry={sample_row['entry']:.2f} and actual={sample_row.get('actual') or 'null'}")
    
    def test_row_has_asof_timestamp(self, sample_row):
        """Row should have asOf timestamp"""
        assert 'asOf' in sample_row, "Row missing asOf field"
        print(f"PASS: Row has asOf={sample_row['asOf']}")


class TestOutcomeDistribution:
    """Test outcome types are present in data"""
    
    def test_outcome_types_in_response(self):
        """Verify different outcome types exist in response"""
        url = f"{BASE_URL}/api/market/exchange/performance-v2?symbol=BTC&horizon=7D&limit=50"
        response = requests.get(url, timeout=30)
        data = response.json()
        
        outcomes_found = set()
        for row in data['rows']:
            outcomes_found.add(row['outcome'])
        
        print(f"PASS: Found outcome types: {outcomes_found}")
        # At minimum, we expect PENDING to exist for recent rows
        assert len(outcomes_found) > 0, "No outcomes found in data"


class TestDirectionTypes:
    """Test direction types are present in data"""
    
    def test_direction_types_in_response(self):
        """Verify different direction types exist in response"""
        url = f"{BASE_URL}/api/market/exchange/performance-v2?symbol=BTC&horizon=7D&limit=50"
        response = requests.get(url, timeout=30)
        data = response.json()
        
        directions_found = set()
        for row in data['rows']:
            directions_found.add(row['direction'])
        
        print(f"PASS: Found direction types: {directions_found}")
        assert len(directions_found) > 0, "No directions found in data"


class TestHorizonParameter:
    """Test different horizon parameters"""
    
    @pytest.mark.parametrize("horizon", ["24H", "7D", "30D"])
    def test_horizon_parameter(self, horizon):
        """API should accept different horizon values"""
        url = f"{BASE_URL}/api/market/exchange/performance-v2?symbol=BTC&horizon={horizon}&limit=5"
        response = requests.get(url, timeout=30)
        assert response.status_code == 200, f"Horizon {horizon} failed with status {response.status_code}"
        data = response.json()
        assert data.get('ok') == True, f"Horizon {horizon} returned ok=false"
        assert data.get('horizon') == horizon, f"Response horizon mismatch: expected {horizon}"
        print(f"PASS: Horizon {horizon} works correctly")


class TestSymbolParameter:
    """Test symbol parameter"""
    
    def test_symbol_parameter(self):
        """API should use provided symbol"""
        url = f"{BASE_URL}/api/market/exchange/performance-v2?symbol=BTC&horizon=7D&limit=5"
        response = requests.get(url, timeout=30)
        data = response.json()
        assert data.get('symbol') == 'BTC', f"Symbol mismatch: expected BTC, got {data.get('symbol')}"
        print("PASS: Symbol parameter works correctly")


class TestLimitParameter:
    """Test limit parameter"""
    
    def test_limit_parameter(self):
        """API should respect limit parameter"""
        limit = 5
        url = f"{BASE_URL}/api/market/exchange/performance-v2?symbol=BTC&horizon=7D&limit={limit}"
        response = requests.get(url, timeout=30)
        data = response.json()
        assert len(data['rows']) <= limit, f"Got {len(data['rows'])} rows, expected <= {limit}"
        print(f"PASS: Limit parameter works correctly (got {len(data['rows'])} rows for limit={limit})")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
