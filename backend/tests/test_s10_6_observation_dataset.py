"""
S10.6 Exchange Observation Dataset API Tests

Tests the Observation Dataset API endpoints for Intelligence Engine v3.0.
This module captures raw observation data (market state + patterns + regime)
for future ML training. NO signals, NO predictions.

API Endpoints Tested:
- GET /api/v10/exchange/observation - list observations with filters
- GET /api/v10/exchange/observation/:symbol - observations for specific symbol
- GET /api/v10/exchange/observation/stats - dataset statistics
- GET /api/v10/exchange/observation/matrix - regime × pattern matrix
- POST /api/v10/exchange/observation/tick - create new observation
- POST /api/admin/exchange/observation/seed - seed test data
- POST /api/admin/exchange/observation/clear - clear observations
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestObservationDatasetAPIs:
    """S10.6 Observation Dataset API tests"""
    
    # ─────────────────────────────────────────────────────────────
    # Stats Endpoint
    # ─────────────────────────────────────────────────────────────
    def test_get_observation_stats(self):
        """GET /api/v10/exchange/observation/stats - returns dataset statistics"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/observation/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') is True, "Response should have ok=true"
        
        # Validate structure
        assert 'totalObservations' in data, "Should have totalObservations"
        assert 'observationsBySymbol' in data, "Should have observationsBySymbol"
        assert 'patternFrequency' in data, "Should have patternFrequency"
        assert 'categoryFrequency' in data, "Should have categoryFrequency"
        assert 'regimeDistribution' in data, "Should have regimeDistribution"
        assert 'conflictRate' in data, "Should have conflictRate"
        assert 'observationsPerHour' in data, "Should have observationsPerHour"
        
        # Validate regime distribution has all 7 types
        regimes = data['regimeDistribution']
        expected_regimes = ['ACCUMULATION', 'DISTRIBUTION', 'LONG_SQUEEZE', 
                           'SHORT_SQUEEZE', 'EXPANSION', 'EXHAUSTION', 'NEUTRAL']
        for regime in expected_regimes:
            assert regime in regimes, f"Regime {regime} should be in distribution"
        
        print(f"Stats: total={data['totalObservations']}, conflict_rate={data['conflictRate']:.2f}")
    
    # ─────────────────────────────────────────────────────────────
    # List Observations Endpoint
    # ─────────────────────────────────────────────────────────────
    def test_get_observations_list(self):
        """GET /api/v10/exchange/observation - returns list of observations"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/observation?limit=10")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') is True, "Response should have ok=true"
        assert 'count' in data, "Should have count field"
        assert 'data' in data, "Should have data array"
        
        if data['count'] > 0:
            obs = data['data'][0]
            # Validate observation structure
            assert 'id' in obs, "Observation should have id"
            assert 'symbol' in obs, "Observation should have symbol"
            assert 'timestamp' in obs, "Observation should have timestamp"
            assert 'regime' in obs, "Observation should have regime"
            assert 'patternCount' in obs, "Observation should have patternCount"
            assert 'hasConflict' in obs, "Observation should have hasConflict"
            assert 'patterns' in obs, "Observation should have patterns array"
            
            print(f"First observation: {obs['symbol']}, regime={obs['regime']}, patterns={obs['patternCount']}")
    
    def test_get_observations_with_symbol_filter(self):
        """GET /api/v10/exchange/observation?symbol=BTCUSDT - filter by symbol"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/observation?symbol=BTCUSDT&limit=5")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') is True, "Response should have ok=true"
        
        # All observations should be for BTCUSDT
        for obs in data.get('data', []):
            assert obs['symbol'] == 'BTCUSDT', f"Expected BTCUSDT, got {obs['symbol']}"
        
        print(f"BTCUSDT observations count: {data['count']}")
    
    def test_get_observations_with_hasConflict_filter(self):
        """GET /api/v10/exchange/observation?hasConflict=true - filter by conflict"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/observation?hasConflict=true&limit=10")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') is True, "Response should have ok=true"
        
        # All observations should have conflict
        for obs in data.get('data', []):
            assert obs['hasConflict'] is True, "All observations should have conflict"
        
        print(f"Observations with conflict: {data['count']}")
    
    # ─────────────────────────────────────────────────────────────
    # Symbol-specific Endpoint
    # ─────────────────────────────────────────────────────────────
    def test_get_observations_by_symbol(self):
        """GET /api/v10/exchange/observation/:symbol - returns observations for symbol"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/observation/BTCUSDT?limit=5")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') is True, "Response should have ok=true"
        assert data.get('symbol') == 'BTCUSDT', "Should return BTCUSDT"
        assert 'count' in data, "Should have count field"
        assert 'data' in data, "Should have data array"
        
        if data['count'] > 0:
            obs = data['data'][0]
            # Full observation data (not summary)
            assert 'market' in obs, "Should have market object"
            assert 'volume' in obs, "Should have volume object"
            assert 'openInterest' in obs, "Should have openInterest object"
            assert 'orderFlow' in obs, "Should have orderFlow object"
            assert 'liquidations' in obs, "Should have liquidations object"
            
            print(f"BTCUSDT full data: price={obs['market']['price']:.2f}")
    
    # ─────────────────────────────────────────────────────────────
    # Matrix Endpoint
    # ─────────────────────────────────────────────────────────────
    def test_get_regime_pattern_matrix(self):
        """GET /api/v10/exchange/observation/matrix - returns regime × pattern matrix"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/observation/matrix")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') is True, "Response should have ok=true"
        assert 'matrix' in data, "Should have matrix object"
        assert 'totalSamples' in data, "Should have totalSamples"
        
        # Matrix should have all 7 regime types
        matrix = data['matrix']
        expected_regimes = ['ACCUMULATION', 'DISTRIBUTION', 'LONG_SQUEEZE', 
                           'SHORT_SQUEEZE', 'EXPANSION', 'EXHAUSTION', 'NEUTRAL']
        for regime in expected_regimes:
            assert regime in matrix, f"Matrix should have {regime} regime"
        
        print(f"Matrix total samples: {data['totalSamples']}")
    
    # ─────────────────────────────────────────────────────────────
    # Create Tick Endpoint
    # ─────────────────────────────────────────────────────────────
    def test_create_tick_observation(self):
        """POST /api/v10/exchange/observation/tick - creates new observation"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/observation/tick",
            json={"symbol": "BTCUSDT"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') is True, "Response should have ok=true"
        assert data.get('message') == 'Observation created', "Should confirm creation"
        
        obs = data.get('observation', {})
        assert 'id' in obs, "Should return observation id"
        assert obs.get('symbol') == 'BTCUSDT', "Should be BTCUSDT"
        assert 'regime' in obs, "Should have regime"
        assert 'patternCount' in obs, "Should have patternCount"
        assert 'hasConflict' in obs, "Should have hasConflict"
        assert 'patterns' in obs, "Should have patterns array"
        
        print(f"Created tick: id={obs['id']}, regime={obs['regime']}, patterns={obs['patternCount']}")
    
    def test_create_tick_default_symbol(self):
        """POST /api/v10/exchange/observation/tick - defaults to BTCUSDT"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/observation/tick",
            json={}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') is True, "Response should have ok=true"
        assert data['observation']['symbol'] == 'BTCUSDT', "Should default to BTCUSDT"
    
    def test_create_tick_different_symbol(self):
        """POST /api/v10/exchange/observation/tick - with different symbol"""
        response = requests.post(
            f"{BASE_URL}/api/v10/exchange/observation/tick",
            json={"symbol": "ETHUSDT"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') is True, "Response should have ok=true"
        assert data['observation']['symbol'] == 'ETHUSDT', "Should be ETHUSDT"
    
    # ─────────────────────────────────────────────────────────────
    # Admin Seed Endpoint
    # ─────────────────────────────────────────────────────────────
    def test_admin_seed_observations(self):
        """POST /api/admin/exchange/observation/seed - seeds test data"""
        response = requests.post(
            f"{BASE_URL}/api/admin/exchange/observation/seed",
            json={"symbol": "XRPUSDT", "count": 3}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') is True, "Response should have ok=true"
        assert 'Created 3 observations' in data.get('message', ''), "Should confirm count"
        assert data.get('count') == 3, "Should have created 3"
        assert 'ids' in data, "Should return created ids"
        
        print(f"Seeded: {data['count']} observations, ids: {data['ids'][:2]}")
    
    def test_admin_seed_default_values(self):
        """POST /api/admin/exchange/observation/seed - with defaults"""
        response = requests.post(
            f"{BASE_URL}/api/admin/exchange/observation/seed",
            json={}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') is True, "Response should have ok=true"
        # Default is 10 observations for BTCUSDT
        assert data.get('count') == 10, "Default count should be 10"
    
    # ─────────────────────────────────────────────────────────────
    # Admin Clear Endpoint
    # ─────────────────────────────────────────────────────────────
    def test_admin_clear_symbol_observations(self):
        """POST /api/admin/exchange/observation/clear - clears symbol observations"""
        # First seed some test data for XRPUSDT
        requests.post(
            f"{BASE_URL}/api/admin/exchange/observation/seed",
            json={"symbol": "BNBUSDT", "count": 2}
        )
        
        # Then clear
        response = requests.post(
            f"{BASE_URL}/api/admin/exchange/observation/clear",
            json={"symbol": "BNBUSDT"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') is True, "Response should have ok=true"
        assert 'deletedCount' in data, "Should have deletedCount"
        assert 'BNBUSDT' in data.get('message', ''), "Message should mention symbol"
        
        print(f"Cleared: {data['deletedCount']} BNBUSDT observations")
    
    # ─────────────────────────────────────────────────────────────
    # Data Persistence Test
    # ─────────────────────────────────────────────────────────────
    def test_create_and_verify_persistence(self):
        """Create observation and verify it persists in database"""
        # Get current count
        stats_before = requests.get(f"{BASE_URL}/api/v10/exchange/observation/stats").json()
        count_before = stats_before.get('totalObservations', 0)
        
        # Create new observation
        create_response = requests.post(
            f"{BASE_URL}/api/v10/exchange/observation/tick",
            json={"symbol": "BTCUSDT"}
        )
        assert create_response.status_code == 200
        created_id = create_response.json()['observation']['id']
        
        # Verify count increased
        stats_after = requests.get(f"{BASE_URL}/api/v10/exchange/observation/stats").json()
        count_after = stats_after.get('totalObservations', 0)
        
        assert count_after > count_before, f"Count should increase from {count_before} to {count_after}"
        
        # Verify we can fetch the observation
        obs_response = requests.get(f"{BASE_URL}/api/v10/exchange/observation?limit=50")
        obs_data = obs_response.json()
        
        ids = [o['id'] for o in obs_data.get('data', [])]
        assert created_id in ids, f"Created observation {created_id} should be in list"
        
        print(f"Persistence verified: count {count_before} -> {count_after}")
    
    # ─────────────────────────────────────────────────────────────
    # Validation Tests
    # ─────────────────────────────────────────────────────────────
    def test_observation_data_structure(self):
        """Verify observation data has all required fields"""
        response = requests.get(f"{BASE_URL}/api/v10/exchange/observation/BTCUSDT?limit=1")
        assert response.status_code == 200
        
        data = response.json()
        if data['count'] > 0:
            obs = data['data'][0]
            
            # Market data
            market = obs.get('market', {})
            assert 'price' in market, "Market should have price"
            assert 'priceChange5m' in market, "Market should have priceChange5m"
            assert 'volatility' in market, "Market should have volatility"
            
            # Volume data
            volume = obs.get('volume', {})
            assert 'total' in volume, "Volume should have total"
            assert 'delta' in volume, "Volume should have delta"
            
            # Open Interest
            oi = obs.get('openInterest', {})
            assert 'value' in oi, "OI should have value"
            assert 'delta' in oi, "OI should have delta"
            
            # Order Flow
            flow = obs.get('orderFlow', {})
            assert 'aggressorBias' in flow, "OrderFlow should have aggressorBias"
            assert flow['aggressorBias'] in ['BUY', 'SELL', 'NEUTRAL'], "Invalid aggressorBias"
            
            # Liquidations
            liqs = obs.get('liquidations', {})
            assert 'longVolume' in liqs, "Liquidations should have longVolume"
            assert 'shortVolume' in liqs, "Liquidations should have shortVolume"
            assert 'cascadeActive' in liqs, "Liquidations should have cascadeActive"
            
            # Regime
            regime = obs.get('regime', {})
            assert 'type' in regime, "Regime should have type"
            assert 'confidence' in regime, "Regime should have confidence"
            
            # Patterns
            patterns = obs.get('patterns', [])
            if len(patterns) > 0:
                p = patterns[0]
                assert 'patternId' in p, "Pattern should have patternId"
                assert 'name' in p, "Pattern should have name"
                assert 'category' in p, "Pattern should have category"
                assert 'direction' in p, "Pattern should have direction"
                assert p['direction'] in ['BULLISH', 'BEARISH', 'NEUTRAL'], "Invalid direction"
            
            print(f"Structure validated: market.price={market['price']:.2f}, regime={regime['type']}")


class TestObservationAdminHealth:
    """Admin health and diagnostics tests"""
    
    def test_admin_health_endpoint(self):
        """GET /api/admin/exchange/observation/health - storage health"""
        response = requests.get(f"{BASE_URL}/api/admin/exchange/observation/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') is True, "Response should have ok=true"
        
        health = data.get('health', {})
        assert 'totalObservations' in health, "Should have totalObservations"
        assert 'symbolCount' in health, "Should have symbolCount"
        
        storage = data.get('storage', {})
        assert storage.get('type') == 'mongodb', "Storage type should be mongodb"
        assert storage.get('collection') == 'exchange_observations', "Collection should be exchange_observations"
        
        print(f"Health: total={health['totalObservations']}, symbols={health['symbolCount']}")
    
    def test_admin_diagnostics_endpoint(self):
        """GET /api/admin/exchange/observation/diagnostics - full diagnostics"""
        response = requests.get(f"{BASE_URL}/api/admin/exchange/observation/diagnostics")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') is True, "Response should have ok=true"
        assert 'stats' in data, "Should have stats"
        assert 'matrix' in data, "Should have matrix"
        assert 'diagnostics' in data, "Should have diagnostics"
        
        diag = data.get('diagnostics', {})
        assert 'indexesCreated' in diag, "Should list indexes"
        
        print(f"Diagnostics: indexes={diag.get('indexesCreated', [])}")


# Cleanup fixture
@pytest.fixture(scope="class", autouse=True)
def cleanup_test_data():
    """Cleanup TEST_ prefixed data and XRPUSDT test data after tests"""
    yield
    # Cleanup XRPUSDT and BNBUSDT test data
    requests.post(
        f"{BASE_URL}/api/admin/exchange/observation/clear",
        json={"symbol": "XRPUSDT"}
    )
    requests.post(
        f"{BASE_URL}/api/admin/exchange/observation/clear",
        json={"symbol": "BNBUSDT"}
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
