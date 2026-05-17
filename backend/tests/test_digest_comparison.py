"""
Digest Comparison View (Phase 1.5 of Weekly Digest) Tests

Tests the comparison functionality that answers 'did the system improve or degrade this week?'
Features tested:
- POST /api/prediction/weekly-digest/generate — comparison object structure
- GET /api/prediction/weekly-digest/latest — comparison field presence
- Comparison fields: systemState, overallChangeScore, metricDeltas, regimeComparison,
  executionDeltas, biggestImprovement, biggestDegradation, drivers, confidenceDrift
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestDigestComparisonBackend:
    """Test Digest Comparison API endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})
    
    def test_generate_first_digest(self):
        """Generate first digest (may not have comparison if no previous digest)"""
        response = self.session.post(f"{BASE_URL}/api/prediction/weekly-digest/generate", json={})
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Basic structure check
        assert 'digest' in data or 'ok' in data, f"Response should have digest or ok field: {data}"
        
        if 'digest' in data:
            digest = data['digest']
            assert 'period' in digest, "Digest should have period"
            assert 'performance' in digest, "Digest should have performance"
            assert 'generatedAt' in digest, "Digest should have generatedAt"
            print(f"First digest generated at: {digest.get('generatedAt')}")
            print(f"Has comparison: {'comparison' in digest and digest['comparison'] is not None}")
    
    def test_generate_second_digest_with_comparison(self):
        """Generate second digest which should have comparison data"""
        # Generate first digest
        response1 = self.session.post(f"{BASE_URL}/api/prediction/weekly-digest/generate", json={})
        assert response1.status_code == 200, f"First digest failed: {response1.text}"
        
        # Small delay to ensure different timestamp
        time.sleep(1)
        
        # Generate second digest - this should have comparison
        response2 = self.session.post(f"{BASE_URL}/api/prediction/weekly-digest/generate", json={})
        assert response2.status_code == 200, f"Second digest failed: {response2.text}"
        
        data = response2.json()
        digest = data.get('digest', data)
        
        print(f"Second digest has comparison: {'comparison' in digest and digest.get('comparison') is not None}")
        
        # If comparison exists, validate its structure
        if 'comparison' in digest and digest['comparison'] is not None:
            self._validate_comparison_structure(digest['comparison'])
    
    def test_latest_digest_structure(self):
        """Test GET /api/prediction/weekly-digest/latest returns proper structure"""
        response = self.session.get(f"{BASE_URL}/api/prediction/weekly-digest/latest")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Check if digest exists
        if 'digest' in data and data['digest'] is not None:
            digest = data['digest']
            
            # Required fields
            assert 'period' in digest, "Digest should have period"
            assert 'performance' in digest, "Digest should have performance"
            assert 'timing' in digest, "Digest should have timing"
            
            # Check comparison if present
            if 'comparison' in digest and digest['comparison'] is not None:
                self._validate_comparison_structure(digest['comparison'])
                print("Latest digest has valid comparison structure")
            else:
                print("Latest digest does not have comparison (expected if only one digest exists)")
    
    def test_comparison_system_state_values(self):
        """Test that systemState has valid values"""
        response = self.session.get(f"{BASE_URL}/api/prediction/weekly-digest/latest")
        assert response.status_code == 200
        
        data = response.json()
        digest = data.get('digest')
        
        if digest and 'comparison' in digest and digest['comparison']:
            comparison = digest['comparison']
            valid_states = ['IMPROVING', 'STABLE', 'DEGRADING', 'UNSTABLE']
            assert comparison['systemState'] in valid_states, \
                f"systemState should be one of {valid_states}, got {comparison['systemState']}"
            print(f"System state: {comparison['systemState']}")
    
    def test_comparison_metric_deltas_structure(self):
        """Test metricDeltas array structure"""
        response = self.session.get(f"{BASE_URL}/api/prediction/weekly-digest/latest")
        assert response.status_code == 200
        
        data = response.json()
        digest = data.get('digest')
        
        if digest and 'comparison' in digest and digest['comparison']:
            comparison = digest['comparison']
            
            assert 'metricDeltas' in comparison, "comparison should have metricDeltas"
            assert isinstance(comparison['metricDeltas'], list), "metricDeltas should be a list"
            
            for delta in comparison['metricDeltas']:
                # Required fields for each metric delta
                assert 'metric' in delta, "Each delta should have metric name"
                assert 'prev' in delta, "Each delta should have prev value"
                assert 'current' in delta, "Each delta should have current value"
                assert 'delta' in delta, "Each delta should have delta value"
                assert 'deltaPercent' in delta, "Each delta should have deltaPercent"
                assert 'direction' in delta, "Each delta should have direction"
                assert 'impact' in delta, "Each delta should have impact"
                
                # Validate direction values
                assert delta['direction'] in ['UP', 'DOWN', 'STABLE'], \
                    f"direction should be UP/DOWN/STABLE, got {delta['direction']}"
                
                # Validate impact values
                assert delta['impact'] in ['HIGH', 'MEDIUM', 'LOW'], \
                    f"impact should be HIGH/MEDIUM/LOW, got {delta['impact']}"
            
            print(f"metricDeltas count: {len(comparison['metricDeltas'])}")
            for d in comparison['metricDeltas'][:3]:
                print(f"  - {d['metric']}: {d['direction']} ({d['delta']:.1f})")
    
    def test_comparison_regime_comparison_structure(self):
        """Test regimeComparison array structure"""
        response = self.session.get(f"{BASE_URL}/api/prediction/weekly-digest/latest")
        assert response.status_code == 200
        
        data = response.json()
        digest = data.get('digest')
        
        if digest and 'comparison' in digest and digest['comparison']:
            comparison = digest['comparison']
            
            assert 'regimeComparison' in comparison, "comparison should have regimeComparison"
            
            if comparison['regimeComparison']:
                for regime in comparison['regimeComparison']:
                    assert 'regime' in regime, "Each regime should have regime name"
                    assert 'prevAccuracy' in regime, "Each regime should have prevAccuracy"
                    assert 'currentAccuracy' in regime, "Each regime should have currentAccuracy"
                    assert 'delta' in regime, "Each regime should have delta"
                    assert 'direction' in regime, "Each regime should have direction"
                    
                    # Validate direction
                    assert regime['direction'] in ['UP', 'DOWN', 'STABLE'], \
                        f"direction should be UP/DOWN/STABLE, got {regime['direction']}"
                
                print(f"regimeComparison count: {len(comparison['regimeComparison'])}")
                for r in comparison['regimeComparison']:
                    print(f"  - {r['regime']}: {r['direction']} ({r['delta']:.1f}%)")
    
    def test_comparison_execution_deltas_structure(self):
        """Test executionDeltas array structure"""
        response = self.session.get(f"{BASE_URL}/api/prediction/weekly-digest/latest")
        assert response.status_code == 200
        
        data = response.json()
        digest = data.get('digest')
        
        if digest and 'comparison' in digest and digest['comparison']:
            comparison = digest['comparison']
            
            assert 'executionDeltas' in comparison, "comparison should have executionDeltas"
            
            if comparison['executionDeltas']:
                for exec_delta in comparison['executionDeltas']:
                    assert 'style' in exec_delta, "Each executionDelta should have style"
                    assert 'prevScore' in exec_delta, "Each executionDelta should have prevScore"
                    assert 'currentScore' in exec_delta, "Each executionDelta should have currentScore"
                    assert 'delta' in exec_delta, "Each executionDelta should have delta"
                    assert 'direction' in exec_delta, "Each executionDelta should have direction"
                    assert 'note' in exec_delta, "Each executionDelta should have note"
                    
                    # Validate direction
                    assert exec_delta['direction'] in ['UP', 'DOWN', 'STABLE'], \
                        f"direction should be UP/DOWN/STABLE, got {exec_delta['direction']}"
                
                print(f"executionDeltas count: {len(comparison['executionDeltas'])}")
    
    def test_comparison_confidence_drift_structure(self):
        """Test confidenceDrift object structure"""
        response = self.session.get(f"{BASE_URL}/api/prediction/weekly-digest/latest")
        assert response.status_code == 200
        
        data = response.json()
        digest = data.get('digest')
        
        if digest and 'comparison' in digest and digest['comparison']:
            comparison = digest['comparison']
            
            assert 'confidenceDrift' in comparison, "comparison should have confidenceDrift"
            drift = comparison['confidenceDrift']
            
            assert 'direction' in drift, "confidenceDrift should have direction"
            assert 'delta' in drift, "confidenceDrift should have delta"
            assert 'interpretation' in drift, "confidenceDrift should have interpretation"
            
            # Validate direction
            assert drift['direction'] in ['UP', 'DOWN', 'STABLE'], \
                f"direction should be UP/DOWN/STABLE, got {drift['direction']}"
            
            # Validate interpretation
            valid_interpretations = [
                'System becoming more aggressive',
                'System becoming more conservative',
                'Confidence stable'
            ]
            assert drift['interpretation'] in valid_interpretations, \
                f"interpretation should be one of {valid_interpretations}, got {drift['interpretation']}"
            
            print(f"Confidence drift: {drift['direction']} ({drift['delta']:.1f}%) - {drift['interpretation']}")
    
    def test_comparison_biggest_changes(self):
        """Test biggestImprovement and biggestDegradation fields"""
        response = self.session.get(f"{BASE_URL}/api/prediction/weekly-digest/latest")
        assert response.status_code == 200
        
        data = response.json()
        digest = data.get('digest')
        
        if digest and 'comparison' in digest and digest['comparison']:
            comparison = digest['comparison']
            
            assert 'biggestImprovement' in comparison, "comparison should have biggestImprovement"
            assert 'biggestDegradation' in comparison, "comparison should have biggestDegradation"
            
            assert isinstance(comparison['biggestImprovement'], str), "biggestImprovement should be string"
            assert isinstance(comparison['biggestDegradation'], str), "biggestDegradation should be string"
            
            print(f"Biggest improvement: {comparison['biggestImprovement']}")
            print(f"Biggest degradation: {comparison['biggestDegradation']}")
    
    def test_comparison_drivers(self):
        """Test drivers array"""
        response = self.session.get(f"{BASE_URL}/api/prediction/weekly-digest/latest")
        assert response.status_code == 200
        
        data = response.json()
        digest = data.get('digest')
        
        if digest and 'comparison' in digest and digest['comparison']:
            comparison = digest['comparison']
            
            assert 'drivers' in comparison, "comparison should have drivers"
            assert isinstance(comparison['drivers'], list), "drivers should be a list"
            
            for driver in comparison['drivers']:
                assert isinstance(driver, str), "Each driver should be a string"
            
            print(f"Drivers count: {len(comparison['drivers'])}")
            for d in comparison['drivers'][:3]:
                print(f"  - {d}")
    
    def test_comparison_overall_change_score(self):
        """Test overallChangeScore field"""
        response = self.session.get(f"{BASE_URL}/api/prediction/weekly-digest/latest")
        assert response.status_code == 200
        
        data = response.json()
        digest = data.get('digest')
        
        if digest and 'comparison' in digest and digest['comparison']:
            comparison = digest['comparison']
            
            assert 'overallChangeScore' in comparison, "comparison should have overallChangeScore"
            assert isinstance(comparison['overallChangeScore'], (int, float)), \
                "overallChangeScore should be a number"
            
            print(f"Overall change score: {comparison['overallChangeScore']:.2f}")
    
    def _validate_comparison_structure(self, comparison):
        """Helper to validate full comparison structure"""
        required_fields = [
            'systemState',
            'overallChangeScore',
            'metricDeltas',
            'regimeComparison',
            'executionDeltas',
            'biggestImprovement',
            'biggestDegradation',
            'drivers',
            'confidenceDrift'
        ]
        
        for field in required_fields:
            assert field in comparison, f"comparison should have {field}"
        
        # Validate systemState
        valid_states = ['IMPROVING', 'STABLE', 'DEGRADING', 'UNSTABLE']
        assert comparison['systemState'] in valid_states, \
            f"systemState should be one of {valid_states}"
        
        # Validate metricDeltas is array
        assert isinstance(comparison['metricDeltas'], list), "metricDeltas should be list"
        
        # Validate confidenceDrift structure
        drift = comparison['confidenceDrift']
        assert 'direction' in drift, "confidenceDrift should have direction"
        assert 'delta' in drift, "confidenceDrift should have delta"
        assert 'interpretation' in drift, "confidenceDrift should have interpretation"
        
        print("Comparison structure validated successfully")


class TestDigestComparisonNodeJS:
    """Test Node.js direct endpoints for Digest Comparison"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})
    
    def test_nodejs_generate_endpoint(self):
        """Test Node.js POST /api/weekly-digest/generate"""
        response = self.session.post(f"{BASE_URL}/api/weekly-digest/generate", json={})
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert 'ok' in data or 'digest' in data, f"Response should have ok or digest: {data}"
        print(f"Node.js generate endpoint working: {response.status_code}")
    
    def test_nodejs_latest_endpoint(self):
        """Test Node.js GET /api/weekly-digest/latest"""
        response = self.session.get(f"{BASE_URL}/api/weekly-digest/latest")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        if 'digest' in data and data['digest']:
            digest = data['digest']
            print(f"Node.js latest endpoint working, has comparison: {'comparison' in digest and digest['comparison'] is not None}")
    
    def test_nodejs_history_endpoint(self):
        """Test Node.js GET /api/weekly-digest/history"""
        response = self.session.get(f"{BASE_URL}/api/weekly-digest/history?limit=5")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert 'digests' in data, "Response should have digests array"
        assert isinstance(data['digests'], list), "digests should be a list"
        
        print(f"Node.js history endpoint working, count: {len(data['digests'])}")
        
        # Check if any digest has comparison
        for i, digest in enumerate(data['digests'][:3]):
            has_comparison = 'comparison' in digest and digest['comparison'] is not None
            print(f"  Digest {i}: has comparison = {has_comparison}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
