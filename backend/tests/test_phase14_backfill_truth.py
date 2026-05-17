"""
Phase 1.4 — Backfill & Historical Truth Layer Tests
=====================================================

Tests for backfill job management and truth evaluation APIs.

Endpoints:
  POST /api/v10/market/backfill/start - Start backfill job
  GET  /api/v10/market/backfill/status/:runId - Get backfill status
  GET  /api/v10/market/backfill/runs - Get recent runs
  GET  /api/v10/market/history/:symbol - Get price history
  GET  /api/v10/market/truth/:symbol - Get truth records
  GET  /api/v10/market/truth/stats/:symbol - Get truth statistics
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBackfillRuns:
    """Tests for backfill run management endpoints"""
    
    def test_get_backfill_runs_btcusdt(self):
        """GET /backfill/runs returns list of runs for BTCUSDT"""
        response = requests.get(f"{BASE_URL}/api/v10/market/backfill/runs?symbol=BTCUSDT&limit=5")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') == True
        assert 'runs' in data
        assert isinstance(data['runs'], list)
        
        if len(data['runs']) > 0:
            run = data['runs'][0]
            # Verify run structure
            assert 'runId' in run
            assert 'symbol' in run
            assert run['symbol'] == 'BTCUSDT'
            assert 'status' in run
            assert run['status'] in ['PENDING', 'RUNNING', 'COMPLETED', 'FAILED']
            assert 'progress' in run
            assert 'barsSaved' in run['progress']
            assert 'truthRecordsSaved' in run['progress']
            print(f"Found {len(data['runs'])} runs, latest status: {run['status']}")
    
    def test_get_backfill_runs_all(self):
        """GET /backfill/runs without symbol returns all runs"""
        response = requests.get(f"{BASE_URL}/api/v10/market/backfill/runs?limit=10")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') == True
        assert 'runs' in data
        print(f"Total runs found: {len(data['runs'])}")
    
    def test_get_backfill_status_existing_run(self):
        """GET /backfill/status/:runId returns run status"""
        # First get a run ID
        runs_response = requests.get(f"{BASE_URL}/api/v10/market/backfill/runs?symbol=BTCUSDT&limit=1")
        assert runs_response.status_code == 200
        runs_data = runs_response.json()
        
        if not runs_data.get('runs') or len(runs_data['runs']) == 0:
            pytest.skip("No existing backfill runs to test status")
        
        run_id = runs_data['runs'][0]['runId']
        
        response = requests.get(f"{BASE_URL}/api/v10/market/backfill/status/{run_id}")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') == True
        assert 'run' in data
        assert data['run']['runId'] == run_id
        print(f"Run {run_id} status: {data['run']['status']}")
    
    def test_get_backfill_status_nonexistent(self):
        """GET /backfill/status/:runId returns 404 for nonexistent run"""
        response = requests.get(f"{BASE_URL}/api/v10/market/backfill/status/nonexistent_run_id")
        assert response.status_code == 404
        data = response.json()
        
        assert data.get('ok') == False
        assert 'error' in data


class TestPriceHistory:
    """Tests for price history endpoint"""
    
    def test_get_price_history_btcusdt(self):
        """GET /history/:symbol returns price bars"""
        response = requests.get(f"{BASE_URL}/api/v10/market/history/BTCUSDT?tf=1h")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') == True
        assert data['symbol'] == 'BTCUSDT'
        assert data['tf'] == '1h'
        assert 'bars' in data
        assert 'count' in data
        assert 'totalInDb' in data
        
        if len(data['bars']) > 0:
            bar = data['bars'][0]
            # Verify OHLCV structure
            assert 'ts' in bar
            assert 'o' in bar
            assert 'h' in bar
            assert 'l' in bar
            assert 'c' in bar
            assert 'v' in bar
            assert 'source' in bar
            print(f"Found {data['count']} bars (total in DB: {data['totalInDb']})")
    
    def test_get_price_history_lowercase_symbol(self):
        """GET /history/:symbol normalizes lowercase to uppercase"""
        response = requests.get(f"{BASE_URL}/api/v10/market/history/btcusdt?tf=1h")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') == True
        assert data['symbol'] == 'BTCUSDT'
    
    def test_get_price_history_with_range(self):
        """GET /history/:symbol with from/to returns filtered bars"""
        now = int(time.time() * 1000)
        day_ago = now - 24 * 60 * 60 * 1000
        
        response = requests.get(
            f"{BASE_URL}/api/v10/market/history/BTCUSDT?tf=1h&from={day_ago}&to={now}"
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') == True
        print(f"Bars in last 24h: {data['count']}")


class TestTruthRecords:
    """Tests for truth records endpoints"""
    
    def test_get_truth_records_btcusdt(self):
        """GET /truth/:symbol returns truth records"""
        response = requests.get(f"{BASE_URL}/api/v10/market/truth/BTCUSDT?limit=10")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') == True
        assert data['symbol'] == 'BTCUSDT'
        assert 'records' in data
        assert 'count' in data
        
        if len(data['records']) > 0:
            record = data['records'][0]
            # Verify truth record structure
            assert 'verdictTs' in record
            assert 'verdict' in record
            assert record['verdict'] in ['BULLISH', 'BEARISH', 'NEUTRAL', 'INCONCLUSIVE', 'NO_DATA']
            assert 'confidence' in record
            assert 'outcome' in record
            assert record['outcome'] in ['CONFIRMED', 'DIVERGED', 'NO_DATA']
            assert 'reason' in record
            assert 'priceChangePct' in record
            assert 'priceDirection' in record
            assert record['priceDirection'] in ['UP', 'DOWN', 'FLAT']
            assert 'horizonBars' in record
            assert 'threshold' in record
            print(f"Found {data['count']} truth records")
    
    def test_get_truth_records_filter_by_outcome(self):
        """GET /truth/:symbol with outcome filter works"""
        response = requests.get(f"{BASE_URL}/api/v10/market/truth/BTCUSDT?outcome=CONFIRMED&limit=10")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') == True
        
        for record in data['records']:
            assert record['outcome'] == 'CONFIRMED'
        
        print(f"Found {data['count']} CONFIRMED records")
    
    def test_get_truth_records_filter_by_timeframe(self):
        """GET /truth/:symbol with tf filter works"""
        response = requests.get(f"{BASE_URL}/api/v10/market/truth/BTCUSDT?tf=1h&limit=10")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') == True
        
        for record in data['records']:
            assert record['tf'] == '1h'
        
        print(f"Found {data['count']} records for 1h timeframe")


class TestTruthStats:
    """Tests for truth statistics endpoint"""
    
    def test_get_truth_stats_btcusdt(self):
        """GET /truth/stats/:symbol returns statistics"""
        response = requests.get(f"{BASE_URL}/api/v10/market/truth/stats/BTCUSDT")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') == True
        assert 'stats' in data
        
        stats = data['stats']
        assert stats['symbol'] == 'BTCUSDT'
        
        # Verify stats structure
        assert 'total' in stats
        assert 'confirmed' in stats
        assert 'diverged' in stats
        assert 'noData' in stats
        assert 'confirmRate' in stats
        assert 'divergeRate' in stats
        assert 'avgConfidence' in stats
        assert 'byVerdict' in stats
        
        # Verify byVerdict structure
        assert 'BULLISH' in stats['byVerdict']
        assert 'BEARISH' in stats['byVerdict']
        assert 'NEUTRAL' in stats['byVerdict']
        
        for verdict in ['BULLISH', 'BEARISH', 'NEUTRAL']:
            assert 'total' in stats['byVerdict'][verdict]
            assert 'confirmed' in stats['byVerdict'][verdict]
            assert 'diverged' in stats['byVerdict'][verdict]
        
        # Verify rates are valid percentages
        assert 0 <= stats['confirmRate'] <= 1
        assert 0 <= stats['divergeRate'] <= 1
        
        # Verify totals add up
        assert stats['total'] == stats['confirmed'] + stats['diverged'] + stats['noData']
        
        print(f"Stats: {stats['total']} total, {stats['confirmed']} confirmed ({stats['confirmRate']*100:.1f}%), {stats['diverged']} diverged ({stats['divergeRate']*100:.1f}%)")
        print(f"By Verdict: BULLISH {stats['byVerdict']['BULLISH']['total']}, BEARISH {stats['byVerdict']['BEARISH']['total']}, NEUTRAL {stats['byVerdict']['NEUTRAL']['total']}")
    
    def test_get_truth_stats_lowercase(self):
        """GET /truth/stats/:symbol normalizes lowercase"""
        response = requests.get(f"{BASE_URL}/api/v10/market/truth/stats/btcusdt")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') == True
        assert data['stats']['symbol'] == 'BTCUSDT'
    
    def test_get_truth_stats_with_timeframe(self):
        """GET /truth/stats/:symbol with tf filter works"""
        response = requests.get(f"{BASE_URL}/api/v10/market/truth/stats/BTCUSDT?tf=1h")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') == True
        assert data['stats']['tf'] == '1h'


class TestBackfillStart:
    """Tests for starting new backfill jobs"""
    
    def test_start_backfill_requires_symbol(self):
        """POST /backfill/start returns 400 without symbol"""
        response = requests.post(
            f"{BASE_URL}/api/v10/market/backfill/start",
            json={}
        )
        assert response.status_code == 400
        data = response.json()
        
        assert data.get('ok') == False
        assert 'error' in data
    
    def test_start_backfill_valid_request(self):
        """POST /backfill/start creates new backfill run"""
        response = requests.post(
            f"{BASE_URL}/api/v10/market/backfill/start",
            json={
                "symbol": "ETHUSDT",
                "tf": "1h",
                "days": 1
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') == True
        assert 'runId' in data
        assert data['symbol'] == 'ETHUSDT'
        assert data['tf'] == '1h'
        assert data['status'] in ['PENDING', 'RUNNING']
        
        run_id = data['runId']
        print(f"Started backfill run: {run_id}")
        
        # Wait a bit and check status
        time.sleep(3)
        
        status_response = requests.get(f"{BASE_URL}/api/v10/market/backfill/status/{run_id}")
        assert status_response.status_code == 200
        status_data = status_response.json()
        
        print(f"Run status after 3s: {status_data['run']['status']}")
        print(f"Progress: {status_data['run']['progress']['barsSaved']} bars, {status_data['run']['progress']['truthRecordsSaved']} truth records")


class TestDataIntegrity:
    """Tests for data integrity across endpoints"""
    
    def test_stats_matches_records_count(self):
        """Truth stats total should match records count"""
        # Get stats
        stats_response = requests.get(f"{BASE_URL}/api/v10/market/truth/stats/BTCUSDT")
        assert stats_response.status_code == 200
        stats_data = stats_response.json()
        
        # Get all records
        records_response = requests.get(f"{BASE_URL}/api/v10/market/truth/BTCUSDT?limit=500")
        assert records_response.status_code == 200
        records_data = records_response.json()
        
        stats_total = stats_data['stats']['total']
        records_count = records_data['count']
        
        # They should match or be close (records may be limited)
        if records_count <= 500:
            assert stats_total == records_count, f"Stats total {stats_total} != records count {records_count}"
        
        print(f"Stats total: {stats_total}, Records count: {records_count}")
    
    def test_history_bars_present_after_backfill(self):
        """After backfill, history endpoint should return bars"""
        # Get latest run for BTCUSDT
        runs_response = requests.get(f"{BASE_URL}/api/v10/market/backfill/runs?symbol=BTCUSDT&limit=1")
        assert runs_response.status_code == 200
        runs_data = runs_response.json()
        
        if runs_data['runs'] and runs_data['runs'][0]['status'] == 'COMPLETED':
            bars_saved = runs_data['runs'][0]['progress']['barsSaved']
            
            # Get history
            history_response = requests.get(f"{BASE_URL}/api/v10/market/history/BTCUSDT?tf=1h")
            assert history_response.status_code == 200
            history_data = history_response.json()
            
            assert history_data['totalInDb'] >= bars_saved
            print(f"Backfill saved {bars_saved} bars, history shows {history_data['totalInDb']} in DB")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
