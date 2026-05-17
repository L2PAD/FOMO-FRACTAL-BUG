"""
Test Suite for Price vs Expectation V2 - Part 2 (Blocks 28-35)
- Block 28: Multi-Layer Alignment
- Block 29 & 30: Model Credibility + Capital Efficiency
- Block 31: Position Sizing (Kelly-based)
- Block 34: Error Cluster Analysis
- Block 35: V3 Contract Freeze
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBlock28LayerAlignment:
    """Block 28: Multi-Layer Alignment Panel tests"""
    
    def test_alignment_object_exists(self):
        """API should return alignment object"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d")
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] == True
        assert 'alignment' in data
        
    def test_alignment_has_required_fields(self):
        """Alignment object should have score, consensus, layerSignals, activeLayerCount"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d")
        data = response.json()
        alignment = data['alignment']
        
        assert 'score' in alignment
        assert 'consensus' in alignment
        assert 'layerSignals' in alignment
        assert 'activeLayerCount' in alignment
        
    def test_alignment_consensus_values(self):
        """Consensus should be one of expected values"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d")
        data = response.json()
        
        valid_consensus = ['STRONG_BULL', 'BULL', 'MIXED', 'NEUTRAL', 'BEAR', 'STRONG_BEAR']
        assert data['alignment']['consensus'] in valid_consensus
        print(f"  Consensus: {data['alignment']['consensus']}")
        
    def test_alignment_layer_signals(self):
        """Layer signals should include exchange, onchain, sentiment"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d")
        data = response.json()
        signals = data['alignment']['layerSignals']
        
        assert 'exchange' in signals
        assert 'onchain' in signals
        assert 'sentiment' in signals
        print(f"  Layer signals: {signals}")
        
    def test_alignment_score_range(self):
        """Alignment score should be between -1 and 1"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d")
        data = response.json()
        score = data['alignment']['score']
        
        assert -1 <= score <= 1
        print(f"  Alignment score: {score}")


class TestBlock29And30Performance:
    """Block 29 & 30: Model Credibility + Capital Efficiency tests"""
    
    def test_metrics_for_credibility_calculation(self):
        """Metrics should provide data for credibility calculation"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d")
        data = response.json()
        metrics = data['metrics']
        
        # Required for credibility calculation: directionMatchPct, hitRatePct, calibrationScore
        assert 'directionMatchPct' in metrics
        assert 'hitRatePct' in metrics
        assert 'calibrationScore' in metrics
        
        print(f"  Direction Match: {metrics['directionMatchPct']}%")
        print(f"  Hit Rate: {metrics['hitRatePct']}%")
        print(f"  Calibration: {metrics['calibrationScore']}%")
        
    def test_breakdown_for_return_simulation(self):
        """Breakdown should exist for simulated return calculation"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d")
        data = response.json()
        metrics = data['metrics']
        
        assert 'breakdown' in metrics
        breakdown = metrics['breakdown']
        assert 'tp' in breakdown
        assert 'fp' in breakdown
        assert 'fn' in breakdown
        assert 'weak' in breakdown
        
        print(f"  Breakdown: TP={breakdown['tp']}, FP={breakdown['fp']}, FN={breakdown['fn']}, WEAK={breakdown['weak']}")
        
    def test_avg_deviation_for_sharpe(self):
        """avgDeviationPct needed for Sharpe estimate"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d")
        data = response.json()
        
        assert 'avgDeviationPct' in data['metrics']
        print(f"  Avg Deviation: {data['metrics']['avgDeviationPct']}%")


class TestBlock31PositionSizing:
    """Block 31: Position Sizing (Kelly-based) tests"""
    
    def test_future_point_has_confidence(self):
        """Future point needs confidence for Kelly calculation"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d")
        data = response.json()
        
        future_point = data['layers']['meta']['futurePoint']
        assert future_point is not None
        assert 'confidence' in future_point
        assert 0 <= future_point['confidence'] <= 1
        
        print(f"  Confidence: {future_point['confidence']}")
        
    def test_future_point_has_expected_move(self):
        """Future point needs expectedMovePct for Kelly calculation"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d")
        data = response.json()
        
        future_point = data['layers']['meta']['futurePoint']
        assert 'expectedMovePct' in future_point
        
        print(f"  Expected Move: {future_point['expectedMovePct']}%")
        
    def test_kelly_formula_inputs_valid(self):
        """Verify Kelly formula can be calculated from data"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d")
        data = response.json()
        
        fp = data['layers']['meta']['futurePoint']
        confidence = fp['confidence']
        expected_move = abs(fp['expectedMovePct'])
        
        # Kelly: f = (p * b - q) / b where p=win rate, b=reward/risk, q=1-p
        # Using 2:1 R/R assumption like frontend
        reward_risk = expected_move / 2
        kelly_fraction = max(0, (confidence * reward_risk - (1 - confidence)) / reward_risk) if reward_risk > 0 else 0
        suggested_size = min(25, round(kelly_fraction * 100 * 0.5))  # Half-Kelly, max 25%
        
        print(f"  Kelly calculation: confidence={confidence}, expectedMove={expected_move}%")
        print(f"  Calculated position size: {suggested_size}%")
        
        assert 0 <= suggested_size <= 25


class TestBlock34ErrorClusters:
    """Block 34: Error Cluster Analysis tests"""
    
    def test_error_clusters_object_exists(self):
        """API should return errorClusters object"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d")
        data = response.json()
        
        assert 'errorClusters' in data
        
    def test_error_clusters_has_by_direction(self):
        """Error clusters should have byDirection breakdown"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d")
        data = response.json()
        ec = data['errorClusters']
        
        assert 'byDirection' in ec
        assert 'upErrors' in ec['byDirection']
        assert 'downErrors' in ec['byDirection']
        
        print(f"  UP errors: {ec['byDirection']['upErrors']}")
        print(f"  DOWN errors: {ec['byDirection']['downErrors']}")
        
    def test_error_clusters_has_by_confidence(self):
        """Error clusters should have byConfidence breakdown"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d")
        data = response.json()
        ec = data['errorClusters']
        
        assert 'byConfidence' in ec
        assert 'highConfErrors' in ec['byConfidence']
        assert 'medConfErrors' in ec['byConfidence']
        assert 'lowConfErrors' in ec['byConfidence']
        
    def test_error_clusters_has_by_deviation(self):
        """Error clusters should have byDeviation breakdown"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d")
        data = response.json()
        ec = data['errorClusters']
        
        assert 'byDeviation' in ec
        assert 'overshot' in ec['byDeviation']
        assert 'undershot' in ec['byDeviation']
        
        print(f"  Overshot: {ec['byDeviation']['overshot']}")
        print(f"  Undershot: {ec['byDeviation']['undershot']}")
        
    def test_error_clusters_has_summary_stats(self):
        """Error clusters should have totalErrors and failureRate"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d")
        data = response.json()
        ec = data['errorClusters']
        
        assert 'totalErrors' in ec
        assert 'failureRate' in ec
        assert isinstance(ec['failureRate'], (int, float))
        assert ec['failureRate'] >= 0
        
        print(f"  Total errors: {ec['totalErrors']}")
        print(f"  Failure rate: {ec['failureRate']}%")


class TestBlock35V3Contract:
    """Block 35: V3 Contract Freeze tests"""
    
    def test_v3_contract_exists(self):
        """API should return v3Contract object"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d")
        data = response.json()
        
        assert 'v3Contract' in data
        
    def test_v3_contract_version(self):
        """v3Contract should have version 3.0.0"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d")
        data = response.json()
        
        assert data['v3Contract']['version'] == '3.0.0'
        print(f"  Version: {data['v3Contract']['version']}")
        
    def test_v3_contract_frozen(self):
        """v3Contract should be frozen (frozen: true)"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d")
        data = response.json()
        
        assert data['v3Contract']['frozen'] == True
        print(f"  Frozen: {data['v3Contract']['frozen']}")
        
    def test_v3_contract_frozen_at(self):
        """v3Contract should have frozenAt timestamp"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d")
        data = response.json()
        
        assert 'frozenAt' in data['v3Contract']
        assert data['v3Contract']['frozenAt'] is not None
        print(f"  Frozen at: {data['v3Contract']['frozenAt']}")
        
    def test_v3_contract_exchange_layer_stable(self):
        """v3Contract should indicate exchange layer is stable"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d")
        data = response.json()
        
        assert 'exchangeLayerStable' in data['v3Contract']
        assert data['v3Contract']['exchangeLayerStable'] == True
        
    def test_v3_contract_changelog(self):
        """v3Contract should have changelog"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d")
        data = response.json()
        
        assert 'changeLog' in data['v3Contract']
        assert isinstance(data['v3Contract']['changeLog'], list)
        assert len(data['v3Contract']['changeLog']) > 0
        
        print(f"  Changelog entries: {len(data['v3Contract']['changeLog'])}")


class TestIntegrationBlocks28To35:
    """Integration tests for all Part 2 blocks"""
    
    def test_all_blocks_present_in_response(self):
        """Verify all Part 2 blocks data is present in API response"""
        response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset=BTC&range=7d")
        data = response.json()
        
        # Block 28: alignment
        assert 'alignment' in data
        
        # Block 29/30: metrics with performance data
        assert 'metrics' in data
        assert 'breakdown' in data['metrics']
        
        # Block 31: futurePoint with confidence
        assert 'layers' in data
        assert 'meta' in data['layers']
        assert 'futurePoint' in data['layers']['meta']
        
        # Block 34: errorClusters
        assert 'errorClusters' in data
        
        # Block 35: v3Contract
        assert 'v3Contract' in data
        
        print("✓ All Part 2 blocks (28-35) present in API response")
        
    def test_different_assets(self):
        """Test API with different assets"""
        assets = ['BTC', 'ETH', 'SOL']
        
        for asset in assets:
            response = requests.get(f"{BASE_URL}/api/market/chart/price-vs-expectation-v2?asset={asset}&range=7d")
            assert response.status_code == 200
            data = response.json()
            assert data['ok'] == True
            assert data['asset'] == asset
            # All blocks should be present regardless of asset
            assert 'alignment' in data
            assert 'errorClusters' in data
            assert 'v3Contract' in data
            print(f"✓ {asset}: alignment={data['alignment']['consensus']}")
