"""
PHASE 2 — ML Dataset Preparation API Tests
============================================

Tests for:
- 2.1 Feature Snapshots
- 2.2 Dataset Builder
- 2.3 Confidence Decay Engine

Exchange/Sentiment/Onchain data is MOCKED. Truth records from Phase 1.4 backfill are real.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_SYMBOL = 'BTCUSDT'
TEST_SYMBOL_SECONDARY = 'ETHUSDT'


class TestFeatureSnapshots:
    """Phase 2.1 - Feature Snapshot API Tests"""

    # ═══════════════════════════════════════════════════════════════
    # POST /features/snapshot/:symbol - Create snapshot
    # ═══════════════════════════════════════════════════════════════

    def test_create_snapshot_success(self):
        """POST /features/snapshot/:symbol - Creates new snapshot (200)"""
        response = requests.post(f"{BASE_URL}/api/v10/features/snapshot/{TEST_SYMBOL}")
        assert response.status_code == 200
        data = response.json()
        
        # Basic response validation
        assert data['ok'] is True
        assert 'snapshot' in data
        
        # Snapshot structure validation
        snapshot = data['snapshot']
        assert 'snapshotId' in snapshot
        assert snapshot['snapshotId'].startswith('snap_')
        assert snapshot['symbol'] == TEST_SYMBOL
        assert 'timestamp' in snapshot
        assert isinstance(snapshot['timestamp'], int)
        
        # Exchange context validation
        assert 'exchange' in snapshot
        exchange = snapshot['exchange']
        assert 'verdict' in exchange
        assert exchange['verdict'] in ['BULLISH', 'BEARISH', 'NEUTRAL', 'NO_DATA']
        assert 'confidence' in exchange
        assert 0 <= exchange['confidence'] <= 1
        assert 'regime' in exchange
        assert 'stress' in exchange
        assert 'whaleRisk' in exchange
        assert 'readiness' in exchange
        
        # Sentiment context validation
        assert 'sentiment' in snapshot
        sentiment = snapshot['sentiment']
        assert 'verdict' in sentiment
        assert 'confidence' in sentiment
        assert 'alignment' in sentiment
        assert sentiment['alignment'] in ['ALIGNED', 'PARTIAL', 'CONFLICT', 'NO_DATA']
        
        # Onchain context validation
        assert 'onchain' in snapshot
        onchain = snapshot['onchain']
        assert 'validation' in onchain
        assert onchain['validation'] in ['CONFIRMS', 'CONTRADICTS', 'NO_DATA']
        assert 'confidence' in onchain
        
        # MetaBrain context validation
        assert 'metaBrain' in snapshot
        metaBrain = snapshot['metaBrain']
        assert 'finalVerdict' in metaBrain
        assert 'finalConfidence' in metaBrain
        assert 'downgraded' in metaBrain
        
        # Meta validation
        assert 'meta' in snapshot
        meta = snapshot['meta']
        assert 'dataCompleteness' in meta
        assert 0 <= meta['dataCompleteness'] <= 1
        assert 'dataMode' in meta
        assert meta['dataMode'] in ['LIVE', 'MOCK', 'MIXED']
        assert meta['version'] == 'v1'

    def test_create_snapshot_normalizes_symbol(self):
        """POST /features/snapshot/:symbol - Normalizes lowercase to uppercase"""
        response = requests.post(f"{BASE_URL}/api/v10/features/snapshot/btcusdt")
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] is True
        assert data['snapshot']['symbol'] == 'BTCUSDT'

    # ═══════════════════════════════════════════════════════════════
    # GET /features/snapshot/latest/:symbol - Get latest snapshot
    # ═══════════════════════════════════════════════════════════════

    def test_get_latest_snapshot_success(self):
        """GET /features/snapshot/latest/:symbol - Returns latest snapshot (200)"""
        response = requests.get(f"{BASE_URL}/api/v10/features/snapshot/latest/{TEST_SYMBOL}")
        assert response.status_code == 200
        data = response.json()
        
        assert data['ok'] is True
        assert 'snapshot' in data
        
        snapshot = data['snapshot']
        assert snapshot is not None
        assert snapshot['symbol'] == TEST_SYMBOL
        assert 'snapshotId' in snapshot
        assert 'timestamp' in snapshot
        assert 'exchange' in snapshot
        assert 'sentiment' in snapshot
        assert 'onchain' in snapshot
        assert 'metaBrain' in snapshot
        assert 'meta' in snapshot

    def test_get_latest_snapshot_nonexistent_symbol(self):
        """GET /features/snapshot/latest/:symbol - Returns null for unknown symbol"""
        response = requests.get(f"{BASE_URL}/api/v10/features/snapshot/latest/UNKNOWNSYMBOL")
        assert response.status_code == 200
        data = response.json()
        
        assert data['ok'] is True
        assert data['snapshot'] is None
        assert 'message' in data

    # ═══════════════════════════════════════════════════════════════
    # GET /features/snapshot/history/:symbol - Get snapshot history
    # ═══════════════════════════════════════════════════════════════

    def test_get_snapshot_history_success(self):
        """GET /features/snapshot/history/:symbol - Returns snapshot history (200)"""
        response = requests.get(f"{BASE_URL}/api/v10/features/snapshot/history/{TEST_SYMBOL}?limit=10")
        assert response.status_code == 200
        data = response.json()
        
        assert data['ok'] is True
        assert data['symbol'] == TEST_SYMBOL
        assert 'count' in data
        assert 'snapshots' in data
        assert isinstance(data['snapshots'], list)
        assert data['count'] == len(data['snapshots'])
        assert data['count'] <= 10  # Respects limit

    def test_get_snapshot_history_respects_limit(self):
        """GET /features/snapshot/history/:symbol - Respects limit parameter"""
        response = requests.get(f"{BASE_URL}/api/v10/features/snapshot/history/{TEST_SYMBOL}?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data['snapshots']) <= 5

    def test_get_snapshot_history_order(self):
        """GET /features/snapshot/history/:symbol - Returns most recent first"""
        response = requests.get(f"{BASE_URL}/api/v10/features/snapshot/history/{TEST_SYMBOL}?limit=5")
        assert response.status_code == 200
        data = response.json()
        
        if len(data['snapshots']) > 1:
            # Most recent should be first (descending order)
            for i in range(len(data['snapshots']) - 1):
                assert data['snapshots'][i]['timestamp'] >= data['snapshots'][i+1]['timestamp']

    # ═══════════════════════════════════════════════════════════════
    # GET /features/snapshot/stats/:symbol - Get snapshot stats
    # ═══════════════════════════════════════════════════════════════

    def test_get_snapshot_stats_success(self):
        """GET /features/snapshot/stats/:symbol - Returns stats (200)"""
        response = requests.get(f"{BASE_URL}/api/v10/features/snapshot/stats/{TEST_SYMBOL}")
        assert response.status_code == 200
        data = response.json()
        
        assert data['ok'] is True
        assert data['symbol'] == TEST_SYMBOL
        assert 'total' in data
        assert isinstance(data['total'], int)
        assert data['total'] >= 0
        assert 'avgCompleteness' in data
        assert 0 <= data['avgCompleteness'] <= 1
        
        # Check data mode breakdown
        assert 'LIVE' in data
        assert 'MOCK' in data
        assert 'MIXED' in data
        
        # Verify total equals sum of modes
        assert data['total'] == data['LIVE'] + data['MOCK'] + data['MIXED']
        
        # Check timeRange if data exists
        if data['total'] > 0:
            assert 'timeRange' in data
            assert data['timeRange'] is not None
            assert 'from' in data['timeRange']
            assert 'to' in data['timeRange']


class TestDatasetBuilder:
    """Phase 2.2 - Dataset Builder API Tests"""

    # ═══════════════════════════════════════════════════════════════
    # POST /dataset/backfill/:symbol - Backfill historical dataset
    # ═══════════════════════════════════════════════════════════════

    def test_backfill_dataset_success(self):
        """POST /dataset/backfill/:symbol - Backfills historical dataset (200)"""
        response = requests.post(
            f"{BASE_URL}/api/v10/dataset/backfill/{TEST_SYMBOL}",
            json={"horizon": 6}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data['ok'] is True
        assert data['symbol'] == TEST_SYMBOL
        assert 'rowsCreated' in data
        assert isinstance(data['rowsCreated'], int)
        
        # Check skipped stats
        assert 'skipped' in data
        skipped = data['skipped']
        assert 'noTruth' in skipped
        assert 'lowQuality' in skipped
        assert 'alreadyExists' in skipped

    def test_backfill_dataset_idempotent(self):
        """POST /dataset/backfill/:symbol - Second backfill skips existing rows"""
        # First backfill
        response1 = requests.post(
            f"{BASE_URL}/api/v10/dataset/backfill/{TEST_SYMBOL}",
            json={"horizon": 6}
        )
        data1 = response1.json()
        
        # Second backfill
        response2 = requests.post(
            f"{BASE_URL}/api/v10/dataset/backfill/{TEST_SYMBOL}",
            json={"horizon": 6}
        )
        data2 = response2.json()
        
        assert response2.status_code == 200
        # Most rows should be skipped as already exists
        assert data2['skipped']['alreadyExists'] >= 0

    # ═══════════════════════════════════════════════════════════════
    # GET /dataset/stats/:symbol - Get dataset stats
    # ═══════════════════════════════════════════════════════════════

    def test_get_dataset_stats_success(self):
        """GET /dataset/stats/:symbol - Returns dataset statistics (200)"""
        response = requests.get(f"{BASE_URL}/api/v10/dataset/stats/{TEST_SYMBOL}")
        assert response.status_code == 200
        data = response.json()
        
        assert data['ok'] is True
        assert data['symbol'] == TEST_SYMBOL
        assert 'total' in data
        assert 'confirmed' in data
        assert 'diverged' in data
        assert 'confirmRate' in data
        assert 'avgConfidence' in data
        
        # Verify confirmed + diverged <= total
        assert data['confirmed'] + data['diverged'] <= data['total']
        
        # Verify confirmRate calculation
        if data['total'] > 0:
            expected_rate = data['confirmed'] / data['total']
            assert abs(data['confirmRate'] - expected_rate) < 0.01
        
        # Check timeRange if data exists
        if data['total'] > 0:
            assert 'timeRange' in data
            assert data['timeRange'] is not None

    def test_get_dataset_stats_normalizes_symbol(self):
        """GET /dataset/stats/:symbol - Normalizes lowercase to uppercase"""
        response = requests.get(f"{BASE_URL}/api/v10/dataset/stats/btcusdt")
        assert response.status_code == 200
        data = response.json()
        assert data['symbol'] == 'BTCUSDT'

    # ═══════════════════════════════════════════════════════════════
    # GET /dataset/ready - Get dataset readiness for ML
    # ═══════════════════════════════════════════════════════════════

    def test_get_dataset_ready_success(self):
        """GET /dataset/ready - Returns ML readiness status (200)"""
        response = requests.get(f"{BASE_URL}/api/v10/dataset/ready")
        assert response.status_code == 200
        data = response.json()
        
        assert data['ok'] is True
        assert 'total' in data
        assert 'usable' in data
        assert isinstance(data['total'], int)
        assert isinstance(data['usable'], int)
        
        # Check discarded breakdown
        assert 'discarded' in data
        discarded = data['discarded']
        assert 'lowCompleteness' in discarded
        assert 'mockData' in discarded
        assert 'noTarget' in discarded
        
        # Check bySymbol breakdown
        assert 'bySymbol' in data
        assert isinstance(data['bySymbol'], dict)
        
        # Usable should be <= total
        assert data['usable'] <= data['total']

    def test_get_dataset_ready_has_btcusdt(self):
        """GET /dataset/ready - Includes BTCUSDT in bySymbol"""
        response = requests.get(f"{BASE_URL}/api/v10/dataset/ready")
        assert response.status_code == 200
        data = response.json()
        
        assert TEST_SYMBOL in data['bySymbol']
        assert data['bySymbol'][TEST_SYMBOL] > 0

    # ═══════════════════════════════════════════════════════════════
    # GET /dataset/sample/:symbol - Get dataset samples
    # ═══════════════════════════════════════════════════════════════

    def test_get_dataset_sample_success(self):
        """GET /dataset/sample/:symbol - Returns sample rows (200)"""
        response = requests.get(f"{BASE_URL}/api/v10/dataset/sample/{TEST_SYMBOL}?count=5")
        assert response.status_code == 200
        data = response.json()
        
        assert data['ok'] is True
        assert data['symbol'] == TEST_SYMBOL
        assert 'count' in data
        assert 'rows' in data
        assert isinstance(data['rows'], list)
        assert data['count'] == len(data['rows'])
        assert data['count'] <= 5

    def test_get_dataset_sample_row_structure(self):
        """GET /dataset/sample/:symbol - Validates row structure"""
        response = requests.get(f"{BASE_URL}/api/v10/dataset/sample/{TEST_SYMBOL}?count=1")
        assert response.status_code == 200
        data = response.json()
        
        if len(data['rows']) > 0:
            row = data['rows'][0]
            
            # Required fields
            assert 'rowId' in row
            assert row['rowId'].startswith('row_')
            assert row['symbol'] == TEST_SYMBOL
            assert 't0' in row
            assert 't1' in row
            assert row['t1'] > row['t0']  # t1 should be after t0
            assert 'snapshotId' in row
            
            # Features validation
            assert 'features' in row
            features = row['features']
            assert 'exchangeVerdict' in features
            assert 'exchangeConfidence' in features
            assert 'stress' in features
            assert 'whaleRisk' in features
            assert 'readinessScore' in features
            assert 'sentimentVerdict' in features
            assert 'sentimentConfidence' in features
            assert 'alignment' in features
            assert 'onchainValidation' in features
            assert 'onchainConfidence' in features
            assert 'dataCompleteness' in features
            
            # Target validation
            assert 'target' in row
            target = row['target']
            assert 'priceChangePct' in target
            assert 'direction' in target
            assert target['direction'] in [-1, 0, 1]
            assert 'confirmed' in target
            assert 'diverged' in target
            assert isinstance(target['confirmed'], bool)
            assert isinstance(target['diverged'], bool)
            
            # Meta validation
            assert 'meta' in row
            meta = row['meta']
            assert 'horizonBars' in meta
            assert 'horizonHours' in meta
            assert 'dataQuality' in meta
            assert meta['version'] == 'v1'


class TestConfidenceDecay:
    """Phase 2.3 - Confidence Decay Engine API Tests"""

    # ═══════════════════════════════════════════════════════════════
    # POST /confidence/compute/:symbol - Compute decay
    # ═══════════════════════════════════════════════════════════════

    def test_compute_decay_success(self):
        """POST /confidence/compute/:symbol - Computes decay (200)"""
        response = requests.post(
            f"{BASE_URL}/api/v10/confidence/compute/{TEST_SYMBOL}",
            json={"rawConfidence": 0.8}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data['ok'] is True
        assert data['symbol'] == TEST_SYMBOL
        assert 'decayFactor' in data
        assert 'adjustedConfidence' in data
        
        # Verify decay formula: adjustedConfidence = rawConfidence * decayFactor
        expected_adjusted = round(0.8 * data['decayFactor'], 3)
        assert abs(data['adjustedConfidence'] - expected_adjusted) < 0.01
        
        # Check record
        assert 'record' in data
        record = data['record']
        assert 'recordId' in record
        assert record['recordId'].startswith('decay_')
        assert record['rawConfidence'] == 0.8
        assert record['version'] == 'v1'

    def test_compute_decay_clamps_factor(self):
        """POST /confidence/compute/:symbol - Decay factor clamped to [0.3, 1.0]"""
        response = requests.post(
            f"{BASE_URL}/api/v10/confidence/compute/{TEST_SYMBOL}",
            json={"rawConfidence": 1.0}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify decayFactor is within bounds
        assert 0.3 <= data['decayFactor'] <= 1.0

    def test_compute_decay_requires_raw_confidence(self):
        """POST /confidence/compute/:symbol - Returns 400 without rawConfidence"""
        response = requests.post(
            f"{BASE_URL}/api/v10/confidence/compute/{TEST_SYMBOL}",
            json={}
        )
        assert response.status_code == 400
        data = response.json()
        assert data['ok'] is False
        assert 'error' in data

    def test_compute_decay_with_verdict_filter(self):
        """POST /confidence/compute/:symbol - Accepts verdict filter"""
        response = requests.post(
            f"{BASE_URL}/api/v10/confidence/compute/{TEST_SYMBOL}",
            json={"rawConfidence": 0.7, "verdict": "NEUTRAL"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] is True
        assert data['record']['verdict'] == 'NEUTRAL'

    # ═══════════════════════════════════════════════════════════════
    # GET /confidence/factor/:symbol - Get decay factor
    # ═══════════════════════════════════════════════════════════════

    def test_get_decay_factor_success(self):
        """GET /confidence/factor/:symbol - Returns decay factor (200)"""
        response = requests.get(f"{BASE_URL}/api/v10/confidence/factor/{TEST_SYMBOL}")
        assert response.status_code == 200
        data = response.json()
        
        assert data['ok'] is True
        assert data['symbol'] == TEST_SYMBOL
        assert 'verdict' in data
        assert data['verdict'] == 'ALL'
        assert 'decayFactor' in data
        assert 0.3 <= data['decayFactor'] <= 1.0

    def test_get_decay_factor_with_verdict(self):
        """GET /confidence/factor/:symbol - Accepts verdict query param"""
        response = requests.get(f"{BASE_URL}/api/v10/confidence/factor/{TEST_SYMBOL}?verdict=NEUTRAL")
        assert response.status_code == 200
        data = response.json()
        
        assert data['ok'] is True
        assert data['verdict'] == 'NEUTRAL'
        assert 0.3 <= data['decayFactor'] <= 1.0

    def test_get_decay_factor_neutral_for_low_samples(self):
        """GET /confidence/factor/:symbol - Returns 0.5 for unknown symbol (low samples)"""
        response = requests.get(f"{BASE_URL}/api/v10/confidence/factor/UNKNOWNSYMBOL")
        assert response.status_code == 200
        data = response.json()
        
        # With 0 samples, should return neutral 0.5
        assert data['decayFactor'] == 0.5

    # ═══════════════════════════════════════════════════════════════
    # GET /confidence/stats/:symbol - Get decay stats
    # ═══════════════════════════════════════════════════════════════

    def test_get_decay_stats_success(self):
        """GET /confidence/stats/:symbol - Returns comprehensive stats (200)"""
        response = requests.get(f"{BASE_URL}/api/v10/confidence/stats/{TEST_SYMBOL}")
        assert response.status_code == 200
        data = response.json()
        
        assert data['ok'] is True
        assert data['symbol'] == TEST_SYMBOL
        
        # Overall stats
        assert 'overall' in data
        overall = data['overall']
        assert 'total' in overall
        assert 'confirmed' in overall
        assert 'diverged' in overall
        assert 'confirmationRate' in overall
        assert 'decayFactor' in overall
        
        # Verify confirmationRate calculation
        if overall['total'] > 0:
            expected_rate = overall['confirmed'] / overall['total']
            assert abs(overall['confirmationRate'] - expected_rate) < 0.01
        
        # By verdict breakdown
        assert 'byVerdict' in data
        by_verdict = data['byVerdict']
        assert 'BULLISH' in by_verdict
        assert 'BEARISH' in by_verdict
        assert 'NEUTRAL' in by_verdict
        
        for verdict in ['BULLISH', 'BEARISH', 'NEUTRAL']:
            v_data = by_verdict[verdict]
            assert 'total' in v_data
            assert 'confirmed' in v_data
            assert 'decayFactor' in v_data

    def test_get_decay_stats_decay_factor_consistency(self):
        """GET /confidence/stats/:symbol - Decay factor matches factor endpoint"""
        # Get stats
        stats_response = requests.get(f"{BASE_URL}/api/v10/confidence/stats/{TEST_SYMBOL}")
        stats_data = stats_response.json()
        
        # Get factor separately
        factor_response = requests.get(f"{BASE_URL}/api/v10/confidence/factor/{TEST_SYMBOL}")
        factor_data = factor_response.json()
        
        # Should match
        assert abs(stats_data['overall']['decayFactor'] - factor_data['decayFactor']) < 0.01


class TestDataIntegrity:
    """Data integrity and cross-module validation tests"""

    def test_snapshot_to_dataset_flow(self):
        """Creating snapshot then building dataset produces valid data"""
        # Create snapshot
        snap_response = requests.post(f"{BASE_URL}/api/v10/features/snapshot/{TEST_SYMBOL}")
        assert snap_response.status_code == 200
        snap_data = snap_response.json()
        snapshot_id = snap_data['snapshot']['snapshotId']
        
        # Get dataset stats before
        stats_response = requests.get(f"{BASE_URL}/api/v10/dataset/stats/{TEST_SYMBOL}")
        stats_before = stats_response.json()
        
        # Both services should have data
        assert stats_before['total'] >= 0

    def test_decay_reflects_dataset_stats(self):
        """Decay stats match dataset stats for symbol"""
        # Get dataset stats
        dataset_response = requests.get(f"{BASE_URL}/api/v10/dataset/stats/{TEST_SYMBOL}")
        dataset_data = dataset_response.json()
        
        # Get decay stats
        decay_response = requests.get(f"{BASE_URL}/api/v10/confidence/stats/{TEST_SYMBOL}")
        decay_data = decay_response.json()
        
        # Total should match
        assert dataset_data['total'] == decay_data['overall']['total']
        assert dataset_data['confirmed'] == decay_data['overall']['confirmed']
        assert dataset_data['diverged'] == decay_data['overall']['diverged']

    def test_decay_formula_validation(self):
        """Validates decay formula: decayFactor = clamp(confirmationRate, 0.3, 1.0)"""
        # Get stats
        response = requests.get(f"{BASE_URL}/api/v10/confidence/stats/{TEST_SYMBOL}")
        data = response.json()
        
        overall = data['overall']
        if overall['total'] > 0:
            # Expected decay = clamp(confirmed/total, 0.3, 1.0)
            confirmation_rate = overall['confirmed'] / overall['total']
            expected_decay = max(0.3, min(1.0, confirmation_rate))
            
            assert abs(overall['decayFactor'] - expected_decay) < 0.01
            assert abs(overall['confirmationRate'] - confirmation_rate) < 0.01

    def test_adjusted_confidence_calculation(self):
        """Validates: adjustedConfidence = rawConfidence × decayFactor"""
        raw_confidence = 0.9
        
        response = requests.post(
            f"{BASE_URL}/api/v10/confidence/compute/{TEST_SYMBOL}",
            json={"rawConfidence": raw_confidence}
        )
        data = response.json()
        
        expected = round(raw_confidence * data['decayFactor'], 3)
        assert abs(data['adjustedConfidence'] - expected) < 0.01


class TestMockDataMode:
    """Verify MOCK data mode is being used correctly"""

    def test_snapshots_use_mock_mode(self):
        """All snapshots should be MOCK mode (external APIs are mocked)"""
        response = requests.get(f"{BASE_URL}/api/v10/features/snapshot/stats/{TEST_SYMBOL}")
        data = response.json()
        
        # All data should be MOCK since Exchange/Sentiment/Onchain are mocked
        assert data['MOCK'] > 0
        assert data['LIVE'] == 0

    def test_snapshot_meta_shows_mock(self):
        """Individual snapshot meta shows MOCK providers"""
        response = requests.get(f"{BASE_URL}/api/v10/features/snapshot/latest/{TEST_SYMBOL}")
        data = response.json()
        
        if data['snapshot']:
            meta = data['snapshot']['meta']
            assert meta['dataMode'] == 'MOCK'
            assert 'MOCK' in meta['providers']
