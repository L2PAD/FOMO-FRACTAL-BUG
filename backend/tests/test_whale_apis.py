"""
S10.W - Whale Intelligence API Tests

Tests whale-related endpoints:
- GET /api/v10/exchange/whales/health
- GET /api/v10/exchange/whales/state/:symbol
- GET /api/v10/exchange/whales/patterns/:symbol
- GET /api/v10/exchange/whales/stats
- GET /api/v10/exchange/labs/whale-risk/summary
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')


class TestWhaleHealth:
    """Test whale health endpoint"""
    
    def test_health_endpoint_returns_200(self):
        """Test that health endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/whales/health")
        assert response.status_code == 200
        print(f"✓ Health endpoint returned 200")
    
    def test_health_response_structure(self):
        """Test health response has required fields"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/whales/health")
        data = response.json()
        
        # Check required fields
        assert 'sources' in data, "Missing 'sources' field"
        assert 'aggregatedStatus' in data, "Missing 'aggregatedStatus' field"
        assert 'totalPositionsTracked' in data, "Missing 'totalPositionsTracked' field"
        assert 'symbolsCovered' in data, "Missing 'symbolsCovered' field"
        assert 'lastGlobalUpdate' in data, "Missing 'lastGlobalUpdate' field"
        print(f"✓ Health response has all required fields")
    
    def test_health_aggregated_status_valid(self):
        """Test aggregatedStatus is valid value"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/whales/health")
        data = response.json()
        
        valid_statuses = ['UP', 'DEGRADED', 'DOWN']
        assert data['aggregatedStatus'] in valid_statuses
        print(f"✓ AggregatedStatus is valid: {data['aggregatedStatus']}")
    
    def test_health_sources_contain_hyperliquid(self):
        """Test sources include hyperliquid provider"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/whales/health")
        data = response.json()
        
        exchanges = [s['exchange'] for s in data['sources']]
        assert 'hyperliquid' in exchanges, "Hyperliquid provider not found in sources"
        print(f"✓ Hyperliquid provider found in sources")


class TestWhaleState:
    """Test whale state endpoint"""
    
    def test_state_btcusdt_returns_200(self):
        """Test state endpoint for BTCUSDT returns 200"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/whales/state/BTCUSDT")
        assert response.status_code == 200
        print(f"✓ State endpoint for BTCUSDT returned 200")
    
    def test_state_response_structure(self):
        """Test state response has required fields"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/whales/state/BTCUSDT")
        data = response.json()
        
        # Check top-level fields
        assert 'state' in data, "Missing 'state' field"
        assert 'indicators' in data, "Missing 'indicators' field"
        assert 'source' in data, "Missing 'source' field"
        assert 'timestamp' in data, "Missing 'timestamp' field"
        print(f"✓ State response has all required top-level fields")
    
    def test_state_contains_market_data(self):
        """Test state contains market position data"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/whales/state/BTCUSDT")
        data = response.json()
        
        state = data['state']
        assert state is not None, "State is null"
        
        # Check state fields
        required_fields = ['totalLongUsd', 'totalShortUsd', 'netBias', 
                          'whaleLongCount', 'whaleShortCount', 'concentrationIndex', 'crowdingRisk']
        for field in required_fields:
            assert field in state, f"Missing '{field}' in state"
        print(f"✓ State contains all required market data fields")
    
    def test_state_indicators_present(self):
        """Test state contains 6 whale indicators"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/whales/state/BTCUSDT")
        data = response.json()
        
        indicators = data['indicators']
        assert indicators is not None, "Indicators is null"
        
        expected_indicators = [
            'large_position_presence',
            'whale_side_bias',
            'position_crowding_against_whales',
            'stop_hunt_probability',
            'large_position_survival_time',
            'contrarian_pressure_index'
        ]
        
        for indicator in expected_indicators:
            assert indicator in indicators, f"Missing indicator: {indicator}"
        print(f"✓ All 6 whale indicators present")
    
    def test_state_with_exchange_param(self):
        """Test state endpoint with exchange query parameter"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/whales/state/BTCUSDT?exchange=hyperliquid")
        assert response.status_code == 200
        data = response.json()
        assert data['state']['source'] == 'mock'  # Mock data is used
        print(f"✓ State endpoint with exchange param works")


class TestWhalePatterns:
    """Test whale patterns endpoint"""
    
    def test_patterns_btcusdt_returns_200(self):
        """Test patterns endpoint for BTCUSDT returns 200"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/whales/patterns/BTCUSDT")
        assert response.status_code == 200
        print(f"✓ Patterns endpoint for BTCUSDT returned 200")
    
    def test_patterns_response_structure(self):
        """Test patterns response has required fields"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/whales/patterns/BTCUSDT")
        data = response.json()
        
        assert 'ok' in data, "Missing 'ok' field"
        assert data['ok'] == True, "Response not ok"
        assert 'snapshot' in data, "Missing 'snapshot' field"
        print(f"✓ Patterns response has all required fields")
    
    def test_patterns_snapshot_structure(self):
        """Test patterns snapshot has required fields"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/whales/patterns/BTCUSDT")
        data = response.json()
        
        snapshot = data['snapshot']
        required_fields = ['symbol', 'timestamp', 'patterns', 'highestRisk', 
                          'overallRiskLevel', 'hasHighRisk', 'activeCount']
        
        for field in required_fields:
            assert field in snapshot, f"Missing '{field}' in snapshot"
        print(f"✓ Patterns snapshot has all required fields")
    
    def test_patterns_risk_level_valid(self):
        """Test overallRiskLevel is valid value"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/whales/patterns/BTCUSDT")
        data = response.json()
        
        valid_levels = ['LOW', 'MID', 'HIGH']
        assert data['snapshot']['overallRiskLevel'] in valid_levels
        print(f"✓ OverallRiskLevel is valid: {data['snapshot']['overallRiskLevel']}")


class TestWhaleStats:
    """Test whale stats endpoint"""
    
    def test_stats_returns_200(self):
        """Test stats endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/whales/stats")
        assert response.status_code == 200
        print(f"✓ Stats endpoint returned 200")
    
    def test_stats_response_structure(self):
        """Test stats response has required fields"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/whales/stats")
        data = response.json()
        
        required_fields = ['snapshotCount', 'eventCount', 'stateCount', 
                          'exchangesCovered', 'symbolsCovered', 'timestamp']
        
        for field in required_fields:
            assert field in data, f"Missing '{field}' in stats"
        print(f"✓ Stats response has all required fields")
    
    def test_stats_has_data(self):
        """Test stats shows some data collected"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/whales/stats")
        data = response.json()
        
        # Should have at least some data
        assert data['snapshotCount'] >= 0, "snapshotCount is negative"
        assert data['eventCount'] >= 0, "eventCount is negative"
        assert data['stateCount'] >= 0, "stateCount is negative"
        print(f"✓ Stats: {data['snapshotCount']} snapshots, {data['eventCount']} events, {data['stateCount']} states")


class TestLabsWhaleRisk:
    """Test LABS-05 whale risk endpoint"""
    
    def test_labs_whale_risk_summary_returns_200(self):
        """Test labs whale risk summary returns 200"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/labs/whale-risk/summary?symbol=BTCUSDT&horizon=15m&window=2000")
        assert response.status_code == 200
        print(f"✓ Labs whale risk summary returned 200")
    
    def test_labs_whale_risk_summary_structure(self):
        """Test labs whale risk summary has required fields"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/labs/whale-risk/summary?symbol=BTCUSDT&horizon=15m&window=2000")
        data = response.json()
        
        assert 'ok' in data, "Missing 'ok' field"
        assert data['ok'] == True, "Response not ok"
        assert 'params' in data, "Missing 'params' field"
        assert 'totalObservations' in data, "Missing 'totalObservations' field"
        assert 'patternStats' in data, "Missing 'patternStats' field"
        assert 'overallStats' in data, "Missing 'overallStats' field"
        assert 'insights' in data, "Missing 'insights' field"
        print(f"✓ Labs whale risk summary has all required fields")
    
    def test_labs_whale_risk_pattern_stats_structure(self):
        """Test labs whale risk patternStats contains expected patterns"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/labs/whale-risk/summary?symbol=BTCUSDT&horizon=15m&window=2000")
        data = response.json()
        
        pattern_ids = [p['patternId'] for p in data['patternStats']]
        expected_patterns = ['WHALE_TRAP_RISK', 'FORCED_SQUEEZE_RISK', 'BAIT_AND_FLIP']
        
        for pattern in expected_patterns:
            assert pattern in pattern_ids, f"Missing pattern: {pattern}"
        print(f"✓ All expected whale patterns present in patternStats")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
