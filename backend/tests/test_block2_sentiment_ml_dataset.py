"""
Sentiment ML BLOCK 2: Dataset & Labels Testing
===============================================

Tests for Block 2 implementation:
- Dataset finalize job creates samples with labelVersion: 1
- Quality field (OK, LOW_VOLUME) is correctly assigned based on eventsCount
- Label thresholds work correctly: 24H ±0.35%, 7D ±1.8%, 30D ±4.5%
- Backfill mode processes historical aggregates without lookahead bias
- API endpoint GET /api/admin/sentiment-ml/dataset/stats
- API endpoint POST /api/admin/sentiment-ml/dataset/trigger
- API endpoint GET /api/admin/sentiment-ml/dataset/samples
- Unique index on {symbol, window, asOf, labelVersion}
- OPS status endpoint /api/admin/sentiment-ml/ops/status

Author: T1 Testing Agent
Date: 2026-02-16
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Label thresholds from sentiment-dataset-labels.ts (BLOCK 2 spec)
LABEL_THRESHOLDS = {
    '24H': {'up': 0.0035, 'down': -0.0035},   # ±0.35%
    '7D': {'up': 0.018, 'down': -0.018},       # ±1.8%
    '30D': {'up': 0.045, 'down': -0.045},      # ±4.5%
}

# Current label version
SENTIMENT_LABEL_VERSION = 1


class TestDatasetStatsEndpoint:
    """Tests for GET /api/admin/sentiment-ml/dataset/stats"""
    
    def test_stats_endpoint_returns_ok(self):
        """Test that stats endpoint returns ok: true"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/dataset/stats")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        print(f"Stats endpoint: ok={data.get('ok')}")
    
    def test_stats_contains_total_samples(self):
        """Test that stats contains total count of samples"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/dataset/stats")
        assert response.status_code == 200
        data = response.json()
        
        assert 'data' in data
        assert 'total' in data['data']
        assert isinstance(data['data']['total'], int)
        assert data['data']['total'] >= 0
        print(f"Total samples: {data['data']['total']}")
    
    def test_stats_contains_bywindow_breakdown(self):
        """Test that stats contains window breakdown with label distribution"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/dataset/stats")
        assert response.status_code == 200
        data = response.json()
        
        assert 'byWindow' in data['data']
        assert isinstance(data['data']['byWindow'], list)
        
        for window_stat in data['data']['byWindow']:
            assert 'window' in window_stat
            assert window_stat['window'] in ['24H', '7D', '30D']
            assert 'count' in window_stat
            assert 'labels' in window_stat
            
            labels = window_stat['labels']
            assert 'UP' in labels or 'DOWN' in labels or 'NEUTRAL' in labels
            
            print(f"Window {window_stat['window']}: count={window_stat['count']}, labels={labels}")
    
    def test_stats_contains_coverage_dates(self):
        """Test that stats contains coverage date range"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/dataset/stats")
        assert response.status_code == 200
        data = response.json()
        
        assert 'coverage' in data['data']
        assert 'from' in data['data']['coverage']
        assert 'to' in data['data']['coverage']
        print(f"Coverage: {data['data']['coverage']['from']} to {data['data']['coverage']['to']}")
    
    def test_stats_contains_job_status(self):
        """Test that stats contains job status information"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/dataset/stats")
        assert response.status_code == 200
        data = response.json()
        
        assert 'job' in data
        assert 'enabled' in data['job']
        assert 'running' in data['job']
        assert isinstance(data['job']['enabled'], bool)
        assert isinstance(data['job']['running'], bool)
        print(f"Job status: enabled={data['job']['enabled']}, running={data['job']['running']}")


class TestDatasetSamplesEndpoint:
    """Tests for GET /api/admin/sentiment-ml/dataset/samples"""
    
    def test_samples_endpoint_returns_ok(self):
        """Test that samples endpoint returns ok: true"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/dataset/samples?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        print(f"Samples endpoint: ok={data.get('ok')}")
    
    def test_samples_returns_expected_count(self):
        """Test that samples returns expected count of records"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/dataset/samples?limit=5")
        assert response.status_code == 200
        data = response.json()
        
        assert 'count' in data
        assert 'samples' in data
        assert len(data['samples']) <= 5
        print(f"Returned {data['count']} samples")
    
    def test_samples_contain_required_schema_fields(self):
        """Test that samples contain all BLOCK 2 required schema fields"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/dataset/samples?limit=5")
        assert response.status_code == 200
        data = response.json()
        
        assert len(data['samples']) > 0, "Expected at least one sample"
        
        sample = data['samples'][0]
        
        # Keys
        assert 'symbol' in sample
        assert 'window' in sample
        assert 'asOf' in sample
        
        # INPUT snapshot fields
        assert 'bias' in sample
        assert 'score' in sample
        assert 'confidence' in sample
        assert 'volume' in sample
        assert 'connectionsWeight' in sample
        assert 'eventsCount' in sample
        
        # OUTCOME fields
        assert 'priceAtAsOf' in sample
        assert 'priceAtHorizonClose' in sample
        assert 'forwardReturnPct' in sample
        assert 'label' in sample
        
        # Metadata fields (BLOCK 2 new fields)
        assert 'labelVersion' in sample
        assert 'finalizedAt' in sample
        assert 'quality' in sample
        
        print(f"Sample schema validated: symbol={sample['symbol']}, window={sample['window']}")
    
    def test_samples_have_label_version_1(self):
        """Test that all samples have labelVersion: 1 (BLOCK 2 spec)"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/dataset/samples?limit=20")
        assert response.status_code == 200
        data = response.json()
        
        for sample in data['samples']:
            assert sample.get('labelVersion') == SENTIMENT_LABEL_VERSION, \
                f"Expected labelVersion={SENTIMENT_LABEL_VERSION}, got {sample.get('labelVersion')}"
        
        print(f"All {len(data['samples'])} samples have labelVersion={SENTIMENT_LABEL_VERSION}")
    
    def test_samples_have_valid_quality_field(self):
        """Test that quality field is correctly assigned (OK or LOW_VOLUME)"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/dataset/samples?limit=50")
        assert response.status_code == 200
        data = response.json()
        
        valid_qualities = ['OK', 'LOW_VOLUME', 'MISSING_PRICE', 'MISSING_AGG']
        
        ok_count = 0
        low_volume_count = 0
        
        for sample in data['samples']:
            quality = sample.get('quality')
            assert quality in valid_qualities, \
                f"Invalid quality '{quality}', expected one of {valid_qualities}"
            
            events_count = sample.get('eventsCount', 0)
            
            # Verify quality logic: LOW_VOLUME if eventsCount < 3
            if events_count < 3:
                assert quality == 'LOW_VOLUME', \
                    f"Expected LOW_VOLUME for eventsCount={events_count}, got {quality}"
                low_volume_count += 1
            else:
                assert quality == 'OK', \
                    f"Expected OK for eventsCount={events_count}, got {quality}"
                ok_count += 1
        
        print(f"Quality validation: OK={ok_count}, LOW_VOLUME={low_volume_count}")
    
    def test_samples_have_valid_labels(self):
        """Test that all samples have valid UP/DOWN/NEUTRAL labels"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/dataset/samples?limit=30")
        assert response.status_code == 200
        data = response.json()
        
        valid_labels = ['UP', 'DOWN', 'NEUTRAL']
        label_counts = {'UP': 0, 'DOWN': 0, 'NEUTRAL': 0}
        
        for sample in data['samples']:
            label = sample.get('label')
            assert label in valid_labels, \
                f"Invalid label '{label}', expected one of {valid_labels}"
            label_counts[label] += 1
        
        print(f"Label distribution: {label_counts}")
    
    def test_samples_have_valid_window_values(self):
        """Test that all samples have valid window values (24H, 7D, 30D)"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/dataset/samples?limit=30")
        assert response.status_code == 200
        data = response.json()
        
        valid_windows = ['24H', '7D', '30D']
        
        for sample in data['samples']:
            window = sample.get('window')
            assert window in valid_windows, \
                f"Invalid window '{window}', expected one of {valid_windows}"
        
        print(f"All samples have valid window values")


class TestLabelThresholds:
    """Tests for label threshold logic: 24H ±0.35%, 7D ±1.8%, 30D ±4.5%"""
    
    def test_24h_label_thresholds(self):
        """Test 24H label thresholds: ±0.35%"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/dataset/samples?limit=100")
        assert response.status_code == 200
        data = response.json()
        
        threshold = LABEL_THRESHOLDS['24H']
        
        for sample in data['samples']:
            if sample.get('window') != '24H':
                continue
                
            return_pct = sample.get('forwardReturnPct', 0)
            label = sample.get('label')
            
            # Verify label assignment based on return
            if return_pct >= threshold['up']:
                expected = 'UP'
            elif return_pct <= threshold['down']:
                expected = 'DOWN'
            else:
                expected = 'NEUTRAL'
            
            assert label == expected, \
                f"24H: return={return_pct:.4f}, expected {expected}, got {label}"
        
        print(f"24H threshold validation passed (±0.35%)")
    
    def test_7d_label_thresholds(self):
        """Test 7D label thresholds: ±1.8%"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/dataset/samples?limit=100")
        assert response.status_code == 200
        data = response.json()
        
        threshold = LABEL_THRESHOLDS['7D']
        
        for sample in data['samples']:
            if sample.get('window') != '7D':
                continue
                
            return_pct = sample.get('forwardReturnPct', 0)
            label = sample.get('label')
            
            if return_pct >= threshold['up']:
                expected = 'UP'
            elif return_pct <= threshold['down']:
                expected = 'DOWN'
            else:
                expected = 'NEUTRAL'
            
            assert label == expected, \
                f"7D: return={return_pct:.4f}, expected {expected}, got {label}"
        
        print(f"7D threshold validation passed (±1.8%)")
    
    def test_30d_label_thresholds_if_samples_exist(self):
        """Test 30D label thresholds: ±4.5% (if samples exist)"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/dataset/samples?limit=200")
        assert response.status_code == 200
        data = response.json()
        
        threshold = LABEL_THRESHOLDS['30D']
        found_30d = False
        
        for sample in data['samples']:
            if sample.get('window') != '30D':
                continue
            
            found_30d = True
            return_pct = sample.get('forwardReturnPct', 0)
            label = sample.get('label')
            
            if return_pct >= threshold['up']:
                expected = 'UP'
            elif return_pct <= threshold['down']:
                expected = 'DOWN'
            else:
                expected = 'NEUTRAL'
            
            assert label == expected, \
                f"30D: return={return_pct:.4f}, expected {expected}, got {label}"
        
        if not found_30d:
            print("30D: No samples found yet (will appear when aggregates mature ~7 days)")
            pytest.skip("No 30D samples available yet")
        else:
            print(f"30D threshold validation passed (±4.5%)")


class TestTriggerEndpoint:
    """Tests for POST /api/admin/sentiment-ml/dataset/trigger"""
    
    def test_trigger_live_mode_returns_ok(self):
        """Test that trigger endpoint works with 'live' mode"""
        response = requests.post(
            f"{BASE_URL}/api/admin/sentiment-ml/dataset/trigger",
            json={"mode": "live"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        assert data.get('mode') == 'live'
        assert 'result' in data
        print(f"Trigger live mode: ok={data.get('ok')}, result={data.get('result')}")
    
    def test_trigger_backfill_mode_returns_ok(self):
        """Test that trigger endpoint works with 'backfill' mode"""
        response = requests.post(
            f"{BASE_URL}/api/admin/sentiment-ml/dataset/trigger",
            json={"mode": "backfill"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        assert data.get('mode') == 'backfill'
        assert 'result' in data
        print(f"Trigger backfill mode: ok={data.get('ok')}, result={data.get('result')}")
    
    def test_trigger_returns_processing_counters(self):
        """Test that trigger returns proper processing counters"""
        response = requests.post(
            f"{BASE_URL}/api/admin/sentiment-ml/dataset/trigger",
            json={"mode": "live"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        
        result = data.get('result', {})
        
        assert 'processed' in result
        assert 'counters' in result
        
        counters = result['counters']
        assert 'CREATED' in counters
        assert 'SKIPPED' in counters
        assert 'RETRY' in counters
        assert 'FAILED' in counters
        
        # Counters should be non-negative integers
        for key, value in counters.items():
            assert isinstance(value, int)
            assert value >= 0
        
        print(f"Processing counters: {counters}")
    
    def test_trigger_returns_skip_reasons(self):
        """Test that trigger returns skip reasons"""
        response = requests.post(
            f"{BASE_URL}/api/admin/sentiment-ml/dataset/trigger",
            json={"mode": "live"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        
        result = data.get('result', {})
        assert 'reasons' in result
        
        # If there are skipped samples, there should be reasons
        skipped = result['counters'].get('SKIPPED', 0)
        if skipped > 0:
            assert len(result['reasons']) > 0
            print(f"Skip reasons: {result['reasons']}")
        else:
            print("No samples skipped")


class TestJobEndpoint:
    """Tests for GET /api/admin/sentiment-ml/dataset/job"""
    
    def test_job_endpoint_returns_ok(self):
        """Test that job status endpoint returns ok: true"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/dataset/job")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        print(f"Job endpoint: ok={data.get('ok')}")
    
    def test_job_status_contains_config(self):
        """Test that job status contains configuration"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/dataset/job")
        assert response.status_code == 200
        data = response.json()
        
        status = data.get('status', {})
        
        assert 'enabled' in status
        assert 'running' in status
        assert 'intervalMs' in status
        assert 'graceMs' in status
        assert 'maxBatch' in status
        
        print(f"Job config: intervalMs={status.get('intervalMs')}, "
              f"graceMs={status.get('graceMs')}, maxBatch={status.get('maxBatch')}")
    
    def test_job_last_run_stats_structure(self):
        """Test that job contains lastRunStats with proper structure"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/dataset/job")
        assert response.status_code == 200
        data = response.json()
        
        status = data.get('status', {})
        last_run = status.get('lastRunStats')
        
        if last_run:
            assert 'startedAt' in last_run
            assert 'finishedAt' in last_run
            assert 'processed' in last_run
            assert 'counters' in last_run
            print(f"Last run: processed={last_run.get('processed')}, counters={last_run.get('counters')}")
        else:
            print("No lastRunStats yet (job hasn't run)")


class TestOpsStatusEndpoint:
    """Tests for GET /api/admin/sentiment-ml/ops/status"""
    
    def test_ops_status_returns_ok(self):
        """Test that OPS status endpoint returns ok: true"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/ops/status")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        print(f"OPS status: ok={data.get('ok')}")
    
    def test_ops_status_contains_flags(self):
        """Test that OPS status contains feature flags"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/ops/status")
        assert response.status_code == 200
        data = response.json()
        
        assert 'flags' in data
        flags = data['flags']
        
        assert 'SENTIMENT_ENABLED' in flags
        assert 'SENTIMENT_WORKERS_ENABLED' in flags
        assert 'SENTIMENT_DATASET_ENABLED' in flags
        assert 'SENTIMENT_SHADOW_ENABLED' in flags
        
        # BLOCK 2 requires dataset to be enabled
        assert flags['SENTIMENT_DATASET_ENABLED'] is True
        
        print(f"Feature flags: {flags}")
    
    def test_ops_status_contains_worker_statuses(self):
        """Test that OPS status contains worker status information"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/ops/status")
        assert response.status_code == 200
        data = response.json()
        
        assert 'workers' in data
        workers = data['workers']
        
        # Required workers for BLOCK 2
        expected_workers = ['intake', 'aggregate', 'dataset_finalize', 'shadow_finalize']
        
        for worker in expected_workers:
            assert worker in workers, f"Missing worker: {worker}"
            worker_status = workers[worker]
            
            assert 'enabled' in worker_status
            assert 'paused' in worker_status
            assert 'runCount' in worker_status
            assert 'errorCount' in worker_status
        
        print(f"Workers: {list(workers.keys())}")
    
    def test_ops_status_contains_lock_states(self):
        """Test that OPS status contains lock state information"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/ops/status")
        assert response.status_code == 200
        data = response.json()
        
        assert 'locks' in data
        locks = data['locks']
        
        # Expected lock keys
        expected_locks = ['INTAKE', 'AGGREGATE', 'DATASET_FINALIZE', 'SHADOW_FINALIZE']
        
        for lock in expected_locks:
            assert lock in locks, f"Missing lock: {lock}"
            # Lock value should be boolean (true=locked, false=not locked)
            assert isinstance(locks[lock], bool)
        
        print(f"Lock states: {locks}")
    
    def test_ops_status_contains_db_counts(self):
        """Test that OPS status contains database count metrics"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/ops/status")
        assert response.status_code == 200
        data = response.json()
        
        assert 'counts' in data
        counts = data['counts']
        
        assert 'events24h' in counts
        assert 'aggregates24h' in counts
        assert 'samples24h' in counts
        assert 'shadowPending' in counts
        
        # Counts should be non-negative integers
        for key, value in counts.items():
            assert isinstance(value, int)
            assert value >= 0
        
        print(f"DB counts: {counts}")
    
    def test_ops_status_contains_health(self):
        """Test that OPS status contains health indicator"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/ops/status")
        assert response.status_code == 200
        data = response.json()
        
        assert 'health' in data
        valid_health = ['HEALTHY', 'DEGRADED', 'CRITICAL', 'DISABLED']
        
        assert data['health'] in valid_health, \
            f"Invalid health '{data['health']}', expected one of {valid_health}"
        
        print(f"System health: {data['health']}")


class TestDataIntegrity:
    """Tests for data integrity and BLOCK 2 spec compliance"""
    
    def test_samples_match_stats_total(self):
        """Test that samples count matches stats total"""
        # Get stats total
        stats_response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/dataset/stats")
        assert stats_response.status_code == 200
        stats_data = stats_response.json()
        
        total_from_stats = stats_data['data']['total']
        
        # Get window breakdown totals
        window_totals = sum(w['count'] for w in stats_data['data']['byWindow'])
        
        assert total_from_stats == window_totals, \
            f"Stats total ({total_from_stats}) doesn't match window totals ({window_totals})"
        
        print(f"Data integrity verified: total={total_from_stats}, window_sum={window_totals}")
    
    def test_samples_have_no_future_leak(self):
        """Test that samples don't have future leak (asOf + window < finalizedAt)"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/dataset/samples?limit=50")
        assert response.status_code == 200
        data = response.json()
        
        from datetime import datetime
        
        horizon_days = {'24H': 1, '7D': 7, '30D': 30}
        
        for sample in data['samples']:
            window = sample.get('window')
            as_of_str = sample.get('asOf')
            finalized_str = sample.get('finalizedAt')
            
            # Parse dates
            as_of = datetime.fromisoformat(as_of_str.replace('Z', '+00:00'))
            finalized = datetime.fromisoformat(finalized_str.replace('Z', '+00:00'))
            
            # Calculate expected close time
            from datetime import timedelta
            days = horizon_days.get(window, 7)
            expected_close = as_of + timedelta(days=days)
            
            # Verify no future leak: finalized should be after expected close
            assert finalized >= expected_close, \
                f"Future leak detected: finalized={finalized} before window close={expected_close}"
        
        print("No future leak detected in samples")
    
    def test_samples_have_positive_prices(self):
        """Test that all price values are positive"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/dataset/samples?limit=50")
        assert response.status_code == 200
        data = response.json()
        
        for sample in data['samples']:
            price_at_as_of = sample.get('priceAtAsOf', 0)
            price_at_horizon = sample.get('priceAtHorizonClose', 0)
            
            assert price_at_as_of > 0, \
                f"Invalid priceAtAsOf: {price_at_as_of}"
            assert price_at_horizon > 0, \
                f"Invalid priceAtHorizonClose: {price_at_horizon}"
        
        print("All samples have positive price values")
    
    def test_forward_return_calculated_correctly(self):
        """Test that forwardReturnPct is calculated correctly"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/dataset/samples?limit=20")
        assert response.status_code == 200
        data = response.json()
        
        for sample in data['samples']:
            p0 = sample.get('priceAtAsOf', 0)
            p1 = sample.get('priceAtHorizonClose', 0)
            stored_return = sample.get('forwardReturnPct', 0)
            
            if p0 > 0:
                calculated_return = (p1 - p0) / p0
                # Allow small floating point tolerance
                assert abs(calculated_return - stored_return) < 0.0001, \
                    f"Return mismatch: calculated={calculated_return:.6f}, stored={stored_return:.6f}"
        
        print("Forward return calculations verified")


class TestBlockTwoSpecificFeatures:
    """Tests specific to BLOCK 2 implementation requirements"""
    
    def test_400_samples_exist_as_per_spec(self):
        """Test that ~400 samples exist (200 for 24H, 200 for 7D)"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/dataset/stats")
        assert response.status_code == 200
        data = response.json()
        
        total = data['data']['total']
        
        # Per spec: 400 samples exist (200 for 24H, 200 for 7D)
        # Allow some tolerance since samples may be added
        assert total >= 400, f"Expected at least 400 samples, got {total}"
        
        print(f"BLOCK 2 spec verified: {total} samples exist (target: 400)")
    
    def test_24h_window_has_200_samples(self):
        """Test that 24H window has ~200 samples"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/dataset/stats")
        assert response.status_code == 200
        data = response.json()
        
        for window_stat in data['data']['byWindow']:
            if window_stat['window'] == '24H':
                count = window_stat['count']
                assert count >= 200, f"Expected 200+ samples for 24H, got {count}"
                print(f"24H window: {count} samples (target: 200)")
                return
        
        pytest.fail("No 24H window data found in stats")
    
    def test_7d_window_has_200_samples(self):
        """Test that 7D window has ~200 samples"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/dataset/stats")
        assert response.status_code == 200
        data = response.json()
        
        for window_stat in data['data']['byWindow']:
            if window_stat['window'] == '7D':
                count = window_stat['count']
                assert count >= 200, f"Expected 200+ samples for 7D, got {count}"
                print(f"7D window: {count} samples (target: 200)")
                return
        
        pytest.fail("No 7D window data found in stats")
    
    def test_label_distribution_per_window(self):
        """Test that each window has UP/DOWN/NEUTRAL distribution"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/dataset/stats")
        assert response.status_code == 200
        data = response.json()
        
        for window_stat in data['data']['byWindow']:
            window = window_stat['window']
            labels = window_stat['labels']
            
            up = labels.get('UP', 0)
            down = labels.get('DOWN', 0)
            neutral = labels.get('NEUTRAL', 0)
            total = up + down + neutral
            
            print(f"{window}: UP={up} ({up/total*100:.1f}%), "
                  f"DOWN={down} ({down/total*100:.1f}%), "
                  f"NEUTRAL={neutral} ({neutral/total*100:.1f}%)")


# Run tests if executed directly
if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
