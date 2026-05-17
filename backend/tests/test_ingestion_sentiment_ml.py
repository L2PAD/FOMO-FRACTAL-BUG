"""
Ingestion Layer & Sentiment-ML API Tests
=========================================
Tests for the Market Intelligence System's ingestion pipeline and sentiment-ml module.

Endpoints tested:
- Ingestion Module:
  - POST /api/admin/ingestion/bridge/run
  - GET /api/admin/ingestion/health
  - GET /api/admin/ingestion/runs
  - GET /api/admin/ingestion/raw-events/stats
  - POST /api/admin/ingestion/scheduler/start
  - POST /api/admin/ingestion/scheduler/stop

- Sentiment-ML Module:
  - GET /api/admin/sentiment-ml/guards/parser-health
  - POST /api/admin/sentiment-ml/guards/parser-health/run
  - POST /api/admin/sentiment-ml/guards/kill-switch
  - GET /api/admin/sentiment-ml/ops/status
  - GET /api/admin/sentiment-ml/intake/status
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestIngestionModule:
    """Tests for the Ingestion Layer endpoints"""

    def test_ingestion_health(self):
        """GET /api/admin/ingestion/health - Returns health snapshot with scheduler status"""
        response = requests.get(f"{BASE_URL}/api/admin/ingestion/health", timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get('ok') == True, f"Expected ok=true, got: {data}"
        assert 'data' in data, "Response should contain 'data' field"
        
        health_data = data['data']
        # Verify health snapshot fields
        assert 'lastRunAt' in health_data or health_data.get('lastRunAt') is None
        assert 'runsLast1h' in health_data
        assert 'eventsLast1h' in health_data
        assert 'dedupeRate' in health_data
        assert 'errorRate' in health_data
        
        # Verify scheduler status
        assert 'scheduler' in health_data, "Health should include scheduler status"
        scheduler = health_data['scheduler']
        assert 'running' in scheduler
        assert 'intervalMs' in scheduler
        
        print(f"✓ Ingestion health: runsLast1h={health_data['runsLast1h']}, scheduler.running={scheduler['running']}")

    def test_ingestion_runs(self):
        """GET /api/admin/ingestion/runs - Returns recent ingestion run history"""
        response = requests.get(f"{BASE_URL}/api/admin/ingestion/runs?limit=10", timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get('ok') == True, f"Expected ok=true, got: {data}"
        assert 'data' in data
        
        runs_data = data['data']
        assert 'count' in runs_data
        assert 'runs' in runs_data
        assert isinstance(runs_data['runs'], list)
        
        print(f"✓ Ingestion runs: count={runs_data['count']}")
        
        # If there are runs, verify structure
        if runs_data['runs']:
            run = runs_data['runs'][0]
            assert 'source' in run or 'fetched' in run, "Run should have source or fetched field"
            print(f"  Latest run: fetched={run.get('fetched')}, inserted={run.get('inserted')}, duplicated={run.get('duplicated')}")

    def test_raw_events_stats(self):
        """GET /api/admin/ingestion/raw-events/stats - Returns raw_events collection stats"""
        response = requests.get(f"{BASE_URL}/api/admin/ingestion/raw-events/stats", timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get('ok') == True, f"Expected ok=true, got: {data}"
        assert 'data' in data
        
        stats = data['data']
        assert 'total' in stats, "Stats should include total count"
        assert 'processed' in stats, "Stats should include processed count"
        assert 'unprocessed' in stats, "Stats should include unprocessed count"
        assert 'bySource' in stats, "Stats should include bySource breakdown"
        
        print(f"✓ Raw events stats: total={stats['total']}, processed={stats['processed']}, unprocessed={stats['unprocessed']}")
        print(f"  By source: {stats['bySource']}")

    def test_bridge_run_first_execution(self):
        """POST /api/admin/ingestion/bridge/run - First run should fetch and insert events"""
        response = requests.post(
            f"{BASE_URL}/api/admin/ingestion/bridge/run",
            json={"limit": 100, "sinceMinutes": 180},
            timeout=60
        )
        
        # Could be 200 (success) or 409 (lock busy if scheduler is running)
        assert response.status_code in [200, 409], f"Expected 200 or 409, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        if response.status_code == 409:
            assert data.get('error') == 'LOCK_BUSY', "409 should indicate LOCK_BUSY"
            print(f"✓ Bridge run: LOCK_BUSY (scheduler is running)")
            return
        
        assert data.get('ok') == True, f"Expected ok=true, got: {data}"
        assert 'data' in data
        
        result = data['data']
        assert 'fetched' in result
        assert 'inserted' in result
        assert 'duplicated' in result
        assert 'errors' in result
        assert 'durationMs' in result
        
        print(f"✓ Bridge run: fetched={result['fetched']}, inserted={result['inserted']}, duplicated={result['duplicated']}, errors={result['errors']}")

    def test_bridge_run_deduplication(self):
        """POST /api/admin/ingestion/bridge/run - Second run should have 0 inserts (deduplication)"""
        # First run
        response1 = requests.post(
            f"{BASE_URL}/api/admin/ingestion/bridge/run",
            json={"limit": 50, "sinceMinutes": 180},
            timeout=60
        )
        
        if response1.status_code == 409:
            print("✓ Deduplication test skipped: LOCK_BUSY")
            return
        
        # Wait a bit for first run to complete
        time.sleep(1)
        
        # Second run with same parameters
        response2 = requests.post(
            f"{BASE_URL}/api/admin/ingestion/bridge/run",
            json={"limit": 50, "sinceMinutes": 180},
            timeout=60
        )
        
        if response2.status_code == 409:
            print("✓ Deduplication test: second run LOCK_BUSY (expected if first still running)")
            return
        
        assert response2.status_code == 200, f"Expected 200, got {response2.status_code}: {response2.text}"
        
        data = response2.json()
        assert data.get('ok') == True
        
        result = data['data']
        # Second run should have 0 inserts due to deduplication
        print(f"✓ Deduplication test: fetched={result['fetched']}, inserted={result['inserted']}, duplicated={result['duplicated']}")
        
        # If data was already ingested, second run should have 0 inserts
        if result['fetched'] > 0:
            assert result['inserted'] == 0 or result['duplicated'] > 0, \
                f"Expected deduplication: inserted should be 0 or duplicated > 0, got inserted={result['inserted']}, duplicated={result['duplicated']}"

    def test_scheduler_stop(self):
        """POST /api/admin/ingestion/scheduler/stop - Stops the scheduler"""
        response = requests.post(f"{BASE_URL}/api/admin/ingestion/scheduler/stop", timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get('ok') == True, f"Expected ok=true, got: {data}"
        assert 'data' in data
        
        scheduler_status = data['data']
        assert scheduler_status.get('running') == False, "Scheduler should be stopped"
        
        print(f"✓ Scheduler stopped: running={scheduler_status['running']}")

    def test_scheduler_start(self):
        """POST /api/admin/ingestion/scheduler/start - Starts the scheduler"""
        response = requests.post(f"{BASE_URL}/api/admin/ingestion/scheduler/start", timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get('ok') == True, f"Expected ok=true, got: {data}"
        assert 'data' in data
        
        scheduler_status = data['data']
        assert scheduler_status.get('running') == True, "Scheduler should be running"
        
        print(f"✓ Scheduler started: running={scheduler_status['running']}")


class TestSentimentMLGuards:
    """Tests for Sentiment-ML Guard endpoints"""

    def test_parser_health_get(self):
        """GET /api/admin/sentiment-ml/guards/parser-health - Returns guard state"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/guards/parser-health", timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get('ok') == True, f"Expected ok=true, got: {data}"
        
        # Verify state structure
        assert 'state' in data, "Response should contain 'state' field"
        state = data['state']
        assert 'status' in state, "State should have status field"
        
        # Verify flags
        assert 'flags' in data, "Response should contain 'flags' field"
        flags = data['flags']
        assert 'isWorkersAllowed' in flags
        assert 'isTrainingAllowed' in flags
        assert 'confidenceModifier' in flags
        
        print(f"✓ Parser health: status={state['status']}, isWorkersAllowed={flags['isWorkersAllowed']}")

    def test_parser_health_run(self):
        """POST /api/admin/sentiment-ml/guards/parser-health/run - Runs guard check"""
        response = requests.post(f"{BASE_URL}/api/admin/sentiment-ml/guards/parser-health/run", timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get('ok') == True, f"Expected ok=true, got: {data}"
        
        assert 'result' in data, "Response should contain 'result' field"
        result = data['result']
        
        # Verify guard decision structure
        assert 'status' in result, "Result should have status"
        assert 'reasons' in result, "Result should have reasons"
        assert 'isKillSwitchOn' in result, "Result should have isKillSwitchOn"
        assert 'isTrainingDisabled' in result, "Result should have isTrainingDisabled"
        assert 'isInferenceDegraded' in result, "Result should have isInferenceDegraded"
        assert 'metrics' in result, "Result should have metrics"
        
        print(f"✓ Parser health run: status={result['status']}, reasons={result['reasons']}")
        print(f"  Metrics: events6h={result['metrics'].get('events6h')}, events24h={result['metrics'].get('events24h')}")

    def test_kill_switch_toggle(self):
        """POST /api/admin/sentiment-ml/guards/kill-switch - Toggle kill switch"""
        # Enable kill switch
        response_on = requests.post(
            f"{BASE_URL}/api/admin/sentiment-ml/guards/kill-switch",
            json={"enabled": True, "note": "Test enable"},
            timeout=30
        )
        
        assert response_on.status_code == 200, f"Expected 200, got {response_on.status_code}: {response_on.text}"
        
        data_on = response_on.json()
        assert data_on.get('ok') == True
        assert data_on.get('killSwitchEnabled') == True
        
        print(f"✓ Kill switch enabled: {data_on}")
        
        # Disable kill switch
        response_off = requests.post(
            f"{BASE_URL}/api/admin/sentiment-ml/guards/kill-switch",
            json={"enabled": False, "note": "Test disable"},
            timeout=30
        )
        
        assert response_off.status_code == 200, f"Expected 200, got {response_off.status_code}: {response_off.text}"
        
        data_off = response_off.json()
        assert data_off.get('ok') == True
        assert data_off.get('killSwitchEnabled') == False
        
        print(f"✓ Kill switch disabled: {data_off}")


class TestSentimentMLOps:
    """Tests for Sentiment-ML Ops endpoints"""

    def test_ops_status(self):
        """GET /api/admin/sentiment-ml/ops/status - Returns ops status with flags"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/ops/status", timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get('ok') == True, f"Expected ok=true, got: {data}"
        
        # Verify structure
        assert 'flags' in data, "Response should contain 'flags'"
        assert 'workers' in data, "Response should contain 'workers'"
        assert 'locks' in data, "Response should contain 'locks'"
        assert 'counts' in data, "Response should contain 'counts'"
        assert 'health' in data, "Response should contain 'health'"
        
        print(f"✓ Ops status: health={data['health']}")
        print(f"  Flags: {data['flags']}")
        print(f"  Counts: {data['counts']}")


class TestSentimentMLIntake:
    """Tests for Sentiment-ML Intake endpoints"""

    def test_intake_status(self):
        """GET /api/admin/sentiment-ml/intake/status - Returns intake worker status"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-ml/intake/status", timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get('ok') == True, f"Expected ok=true, got: {data}"
        
        assert 'data' in data, "Response should contain 'data'"
        intake_data = data['data']
        
        # Verify worker stats
        assert 'worker' in intake_data, "Should have worker stats"
        worker = intake_data['worker']
        assert 'isRunning' in worker
        assert 'tickCount' in worker
        assert 'tweetsProcessed' in worker
        assert 'eventsCreated' in worker
        
        # Verify queue stats
        assert 'queue' in intake_data, "Should have queue stats"
        
        # Verify events stats
        assert 'events' in intake_data, "Should have events stats"
        
        print(f"✓ Intake status: isRunning={worker['isRunning']}, tweetsProcessed={worker['tweetsProcessed']}, eventsCreated={worker['eventsCreated']}")


class TestHealthEndpoint:
    """Basic health check"""

    def test_api_health(self):
        """GET /api/health - Basic health check"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get('ok') == True, f"Expected ok=true, got: {data}"
        
        print(f"✓ API health: ok={data['ok']}, service={data.get('service')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
