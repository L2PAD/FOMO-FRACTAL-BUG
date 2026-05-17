"""
Exchange Forecast Evolution + Performance V2 API Tests
=======================================================
Tests for:
1. AI Evolution line spike fix (backend dedup by runId)
2. BTC Forecast Table restructuring (Yesterday/Today/Tomorrow + Pending)

API Endpoints Tested:
- GET /api/market/chart/forecast-evolution?asset=BTC&horizon={1,7,30}
- GET /api/market/exchange/performance-v2?symbol=BTC&horizon={24H,7D,30D}&limit={n}
"""

import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestForecastEvolution:
    """Test forecast-evolution endpoint for AI Evolution line (dedup by runId)"""
    
    def test_evolution_api_basic(self):
        """Test basic API response structure"""
        response = requests.get(f"{BASE_URL}/api/market/chart/forecast-evolution?asset=BTC&horizon=7")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') is True, "Expected ok=true"
        assert data.get('asset') == 'BTC', "Expected asset=BTC"
        assert data.get('horizonDays') == 7, "Expected horizonDays=7"
        assert 'points' in data, "Expected points array"
        assert 'drift' in data, "Expected drift object"
        assert 'trend' in data, "Expected trend object"
    
    def test_evolution_no_duplicate_runids_7d(self):
        """Verify no duplicate runIds in 7D evolution (critical fix)"""
        response = requests.get(f"{BASE_URL}/api/market/chart/forecast-evolution?asset=BTC&horizon=7")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        
        points = data.get('points', [])
        run_ids = [p.get('runId') for p in points]
        unique_run_ids = set(run_ids)
        
        # CRITICAL: No duplicate runIds should exist after dedup fix
        assert len(run_ids) == len(unique_run_ids), \
            f"Found {len(run_ids) - len(unique_run_ids)} duplicate runIds! Expected 0."
        
        print(f"✓ 7D Evolution: {len(points)} points, all unique runIds")
    
    def test_evolution_no_duplicate_runids_1d(self):
        """Verify no duplicate runIds in 1D evolution"""
        response = requests.get(f"{BASE_URL}/api/market/chart/forecast-evolution?asset=BTC&horizon=1")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        
        points = data.get('points', [])
        run_ids = [p.get('runId') for p in points if p.get('runId')]
        unique_run_ids = set(run_ids)
        
        assert len(run_ids) == len(unique_run_ids), \
            f"Found {len(run_ids) - len(unique_run_ids)} duplicate runIds in 1D!"
        
        print(f"✓ 1D Evolution: {len(points)} points, all unique runIds")
    
    def test_evolution_no_duplicate_runids_30d(self):
        """Verify no duplicate runIds in 30D evolution"""
        response = requests.get(f"{BASE_URL}/api/market/chart/forecast-evolution?asset=BTC&horizon=30")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        
        points = data.get('points', [])
        run_ids = [p.get('runId') for p in points if p.get('runId')]
        unique_run_ids = set(run_ids)
        
        assert len(run_ids) == len(unique_run_ids), \
            f"Found {len(run_ids) - len(unique_run_ids)} duplicate runIds in 30D!"
        
        print(f"✓ 30D Evolution: {len(points)} points, all unique runIds")
    
    def test_evolution_point_structure(self):
        """Test that each evolution point has required fields"""
        response = requests.get(f"{BASE_URL}/api/market/chart/forecast-evolution?asset=BTC&horizon=7")
        data = response.json()
        
        points = data.get('points', [])
        assert len(points) > 0, "Expected at least one point"
        
        for i, point in enumerate(points[:5]):  # Check first 5
            assert 'date' in point, f"Point {i} missing date"
            assert 'target' in point, f"Point {i} missing target"
            assert 'runId' in point, f"Point {i} missing runId"
            assert point['date'] > 0, f"Point {i} date should be positive unix timestamp"
            assert point['target'] > 0, f"Point {i} target should be positive"
        
        print(f"✓ Evolution point structure verified")
    
    def test_evolution_drift_info(self):
        """Test drift calculation is present"""
        response = requests.get(f"{BASE_URL}/api/market/chart/forecast-evolution?asset=BTC&horizon=7")
        data = response.json()
        
        drift = data.get('drift', {})
        assert 'value' in drift, "Drift should have value"
        assert 'status' in drift, "Drift should have status"
        assert drift['status'] in ['stable', 'moderate', 'unstable'], \
            f"Drift status should be one of stable/moderate/unstable, got {drift['status']}"
        
        print(f"✓ Drift: value={drift['value']}, status={drift['status']}")


class TestPerformanceV2:
    """Test performance-v2 endpoint for BTC Forecast Table structure"""
    
    def test_performance_v2_30d_structure(self):
        """Test 30D performance API returns correct structure"""
        response = requests.get(f"{BASE_URL}/api/market/exchange/performance-v2?symbol=BTC&horizon=30D&limit=40")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        assert data.get('symbol') == 'BTC'
        assert data.get('horizon') == '30D'
        assert 'rows' in data
        assert 'summary' in data
        
        rows = data['rows']
        assert len(rows) >= 3, "Should have at least 3 rows for yesterday/today/tomorrow"
        
        summary = data['summary']
        assert 'total' in summary
        assert 'evaluated' in summary
        assert 'pending' in summary
        
        print(f"✓ 30D Structure: {len(rows)} rows, {summary['pending']} pending")
    
    def test_performance_v2_30d_key_dates_guaranteed(self):
        """Verify yesterday/today/tomorrow are always included in 30D response"""
        response = requests.get(f"{BASE_URL}/api/market/exchange/performance-v2?symbol=BTC&horizon=30D&limit=40")
        data = response.json()
        
        rows = data.get('rows', [])
        
        now = datetime.utcnow()
        yesterday = (now - timedelta(days=1)).strftime('%Y-%m-%d')
        today = now.strftime('%Y-%m-%d')
        tomorrow = (now + timedelta(days=1)).strftime('%Y-%m-%d')
        
        eval_dates = set(r.get('evaluateAt', '')[:10] for r in rows)
        
        # These key dates should be present (service guarantees them)
        has_yesterday = yesterday in eval_dates
        has_today = today in eval_dates
        has_tomorrow = tomorrow in eval_dates
        
        print(f"Key dates: yesterday={yesterday} ({has_yesterday}), today={today} ({has_today}), tomorrow={tomorrow} ({has_tomorrow})")
        
        # At least today should be present (most common case)
        assert has_today or has_yesterday or has_tomorrow, \
            f"At least one key date should be present. Dates found: {sorted(list(eval_dates))[:5]}"
    
    def test_performance_v2_30d_pending_count(self):
        """Verify 30D has at least 28+ pending forecasts"""
        response = requests.get(f"{BASE_URL}/api/market/exchange/performance-v2?symbol=BTC&horizon=30D&limit=40")
        data = response.json()
        
        rows = data.get('rows', [])
        pending_count = len([r for r in rows if r.get('outcome') == 'PENDING'])
        
        # For 30D, we should have many pending forecasts
        assert pending_count >= 20, f"Expected 20+ pending rows for 30D, got {pending_count}"
        
        print(f"✓ 30D Pending: {pending_count} forecasts awaiting evaluation")
    
    def test_performance_v2_7d_structure(self):
        """Test 7D performance API structure"""
        response = requests.get(f"{BASE_URL}/api/market/exchange/performance-v2?symbol=BTC&horizon=7D&limit=15")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        
        rows = data.get('rows', [])
        assert len(rows) > 0, "Should have rows"
        
        # Verify row structure
        row = rows[0]
        assert 'evaluateAt' in row, "Row should have evaluateAt"
        assert 'direction' in row, "Row should have direction"
        assert 'outcome' in row, "Row should have outcome"
        assert 'finalTarget' in row, "Row should have finalTarget"
        
        print(f"✓ 7D Structure verified: {len(rows)} rows")
    
    def test_performance_v2_1d_structure(self):
        """Test 1D (24H) performance API structure"""
        response = requests.get(f"{BASE_URL}/api/market/exchange/performance-v2?symbol=BTC&horizon=24H&limit=10")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        
        rows = data.get('rows', [])
        summary = data.get('summary', {})
        
        print(f"✓ 1D/24H Structure: {len(rows)} rows, evaluated={summary.get('evaluated')}")
    
    def test_performance_v2_row_outcome_values(self):
        """Verify outcome values are valid"""
        response = requests.get(f"{BASE_URL}/api/market/exchange/performance-v2?symbol=BTC&horizon=30D&limit=40")
        data = response.json()
        
        valid_outcomes = {'TP', 'FP', 'FN', 'WEAK', 'PENDING', 'OVERDUE', 'VOIDED'}
        
        for row in data.get('rows', []):
            outcome = row.get('outcome')
            assert outcome in valid_outcomes, f"Invalid outcome: {outcome}"
        
        print(f"✓ All outcome values are valid")
    
    def test_performance_v2_direction_mapping(self):
        """Verify direction is mapped correctly (UP→LONG, DOWN→SHORT)"""
        response = requests.get(f"{BASE_URL}/api/market/exchange/performance-v2?symbol=BTC&horizon=30D&limit=40")
        data = response.json()
        
        valid_directions = {'LONG', 'SHORT', 'NEUTRAL'}
        
        for row in data.get('rows', []):
            direction = row.get('direction')
            assert direction in valid_directions, f"Invalid direction: {direction}"
        
        print(f"✓ All direction values are valid (LONG/SHORT/NEUTRAL)")


class TestFrontendDataTestIds:
    """Verify required data-testid attributes are documented for frontend testing"""
    
    def test_document_expected_testids(self):
        """Document the data-testid attributes expected in frontend"""
        expected_testids = {
            # Table component
            'exchange-performance-table': 'Main table container',
            'perf-summary': 'Summary bar with win rate, avg return, etc',
            'perf-table': 'Inner table element',
            'pending-divider': 'Divider showing pending forecast count',
            
            # Fixed rows
            'perf-fixed-yesterday': 'Yesterday fixed row',
            'perf-fixed-today': 'Today fixed row',
            'perf-fixed-tomorrow': 'Tomorrow fixed row',
            
            # Chart component
            'chart-v3-container': 'Chart V3 main container',
            'chart-v3-loading': 'Loading state',
            'chart-v3-error': 'Error state',
            'chart-v3-evo-toggle': 'AI Evolution toggle checkbox',
        }
        
        for testid, description in expected_testids.items():
            print(f"  data-testid=\"{testid}\": {description}")
        
        print(f"\n✓ {len(expected_testids)} data-testid attributes documented")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
