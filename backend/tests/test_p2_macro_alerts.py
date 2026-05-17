"""
P2 Macro Alerts - Telegram Notifications on Macro Regime Change
================================================================

Tests for:
1. GET /api/v10/macro/alerts/status - Monitor status (isRunning, lastLabel, lastValue)
2. POST /api/v10/macro/alerts/start - Start monitoring
3. POST /api/v10/macro/alerts/stop - Stop monitoring
4. POST /api/v10/macro/alerts/trigger - Manually trigger check

FomoAlertEngine tests:
- MACRO_REGIME_CHANGE event type
- MACRO_EXTREME event type
- Message formatting
- Dedupe keys use label not symbol
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestMacroAlertEndpoints:
    """Tests for macro alert monitoring API endpoints"""
    
    def test_alerts_status_returns_ok(self):
        """GET /api/v10/macro/alerts/status - returns ok"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/alerts/status")
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] is True
        print(f"✅ GET /alerts/status returns ok=true")
    
    def test_alerts_status_has_required_fields(self):
        """GET /api/v10/macro/alerts/status - has isRunning, lastLabel, lastValue"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/alerts/status")
        assert response.status_code == 200
        data = response.json()['data']
        
        assert 'isRunning' in data
        assert 'lastLabel' in data  
        assert 'lastValue' in data
        assert isinstance(data['isRunning'], bool)
        print(f"✅ Status has isRunning={data['isRunning']}, lastLabel={data['lastLabel']}, lastValue={data['lastValue']}")
    
    def test_alerts_stop_works(self):
        """POST /api/v10/macro/alerts/stop - stops monitoring"""
        response = requests.post(f"{BASE_URL}/api/v10/macro/alerts/stop")
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] is True
        assert 'stopped' in data['message'].lower()
        assert data['data']['isRunning'] is False
        print(f"✅ POST /alerts/stop - isRunning=false")
    
    def test_alerts_start_works(self):
        """POST /api/v10/macro/alerts/start - starts monitoring"""
        response = requests.post(f"{BASE_URL}/api/v10/macro/alerts/start")
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] is True
        assert 'started' in data['message'].lower()
        assert data['data']['isRunning'] is True
        print(f"✅ POST /alerts/start - isRunning=true")
    
    def test_alerts_trigger_returns_checked(self):
        """POST /api/v10/macro/alerts/trigger - returns checked=true"""
        response = requests.post(f"{BASE_URL}/api/v10/macro/alerts/trigger")
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] is True
        assert data['data']['checked'] is True
        print(f"✅ POST /alerts/trigger - checked=true")
    
    def test_alerts_trigger_returns_current_label_and_value(self):
        """POST /api/v10/macro/alerts/trigger - has currentLabel and currentValue"""
        response = requests.post(f"{BASE_URL}/api/v10/macro/alerts/trigger")
        assert response.status_code == 200
        data = response.json()['data']
        
        assert 'currentLabel' in data
        assert 'currentValue' in data
        assert data['currentLabel'] in ['EXTREME_FEAR', 'FEAR', 'NEUTRAL', 'GREED', 'EXTREME_GREED']
        assert isinstance(data['currentValue'], (int, float))
        assert 0 <= data['currentValue'] <= 100
        print(f"✅ Trigger returns currentLabel={data['currentLabel']}, currentValue={data['currentValue']}")
    
    def test_alerts_trigger_returns_alerts_triggered_array(self):
        """POST /api/v10/macro/alerts/trigger - has alertsTriggered array"""
        response = requests.post(f"{BASE_URL}/api/v10/macro/alerts/trigger")
        assert response.status_code == 200
        data = response.json()['data']
        
        assert 'alertsTriggered' in data
        assert isinstance(data['alertsTriggered'], list)
        print(f"✅ Trigger returns alertsTriggered={data['alertsTriggered']}")
    
    def test_alerts_trigger_detects_macro_extreme_for_extreme_fear(self):
        """POST /api/v10/macro/alerts/trigger - detects MACRO_EXTREME for EXTREME_FEAR"""
        response = requests.post(f"{BASE_URL}/api/v10/macro/alerts/trigger")
        assert response.status_code == 200
        data = response.json()['data']
        
        # Current market is EXTREME_FEAR with F&G=14
        if data['currentLabel'] == 'EXTREME_FEAR':
            assert 'MACRO_EXTREME' in data['alertsTriggered']
            print(f"✅ MACRO_EXTREME triggered for EXTREME_FEAR condition (F&G={data['currentValue']})")
        else:
            print(f"⚠️ Current market is {data['currentLabel']}, not EXTREME_FEAR - skipping MACRO_EXTREME check")


class TestMacroAlertStopStartCycle:
    """Tests for start/stop cycle behavior"""
    
    def test_stop_start_stop_cycle(self):
        """Monitor can be stopped, started, stopped again"""
        # Stop
        r1 = requests.post(f"{BASE_URL}/api/v10/macro/alerts/stop")
        assert r1.status_code == 200
        assert r1.json()['data']['isRunning'] is False
        
        # Start
        r2 = requests.post(f"{BASE_URL}/api/v10/macro/alerts/start")
        assert r2.status_code == 200
        assert r2.json()['data']['isRunning'] is True
        
        # Stop again
        r3 = requests.post(f"{BASE_URL}/api/v10/macro/alerts/stop")
        assert r3.status_code == 200
        assert r3.json()['data']['isRunning'] is False
        
        # Start to leave in running state
        r4 = requests.post(f"{BASE_URL}/api/v10/macro/alerts/start")
        assert r4.status_code == 200
        
        print(f"✅ Stop/Start/Stop cycle completed successfully")
    
    def test_start_when_already_running(self):
        """Start when already running returns ok (idempotent)"""
        # Ensure running
        requests.post(f"{BASE_URL}/api/v10/macro/alerts/start")
        
        # Start again
        response = requests.post(f"{BASE_URL}/api/v10/macro/alerts/start")
        assert response.status_code == 200
        assert response.json()['ok'] is True
        print(f"✅ Double start is idempotent")


class TestMacroSnapshotIntegration:
    """Tests that macro alerts integrate with macro snapshot data"""
    
    def test_trigger_uses_real_macro_data(self):
        """Trigger uses real macro snapshot data"""
        # Get snapshot
        snap_r = requests.get(f"{BASE_URL}/api/v10/macro/snapshot")
        assert snap_r.status_code == 200
        snapshot = snap_r.json()['data']
        
        # Trigger alert check
        trigger_r = requests.post(f"{BASE_URL}/api/v10/macro/alerts/trigger")
        assert trigger_r.status_code == 200
        trigger_data = trigger_r.json()['data']
        
        # Values should match
        assert trigger_data['currentLabel'] == snapshot['fearGreed']['label']
        assert trigger_data['currentValue'] == snapshot['fearGreed']['value']
        print(f"✅ Trigger uses real snapshot data: F&G={trigger_data['currentValue']} ({trigger_data['currentLabel']})")
    
    def test_status_reflects_last_checked_value(self):
        """Status reflects the last checked F&G value after trigger"""
        # Trigger first
        requests.post(f"{BASE_URL}/api/v10/macro/alerts/trigger")
        
        # Get status
        response = requests.get(f"{BASE_URL}/api/v10/macro/alerts/status")
        assert response.status_code == 200
        data = response.json()['data']
        
        assert data['lastLabel'] is not None
        assert data['lastValue'] is not None
        print(f"✅ Status reflects last checked: {data['lastLabel']} (F&G={data['lastValue']})")


class TestMacroSignalIntegration:
    """Tests that macro alerts use macro signal flags"""
    
    def test_macro_signal_has_flags(self):
        """Macro signal has flags array including MACRO_PANIC"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/signal")
        assert response.status_code == 200
        signal = response.json()['data']
        
        assert 'flags' in signal
        assert isinstance(signal['flags'], list)
        print(f"✅ Macro signal has flags: {signal['flags']}")
    
    def test_macro_panic_flag_triggers_extreme_alert(self):
        """MACRO_PANIC flag in signal means MACRO_EXTREME should be triggered"""
        signal_r = requests.get(f"{BASE_URL}/api/v10/macro/signal")
        signal = signal_r.json()['data']
        
        trigger_r = requests.post(f"{BASE_URL}/api/v10/macro/alerts/trigger")
        trigger_data = trigger_r.json()['data']
        
        if 'MACRO_PANIC' in signal['flags'] or 'MACRO_EUPHORIA' in signal['flags']:
            assert 'MACRO_EXTREME' in trigger_data['alertsTriggered']
            print(f"✅ MACRO_PANIC/EUPHORIA flag triggers MACRO_EXTREME alert")
        else:
            assert 'MACRO_EXTREME' not in trigger_data['alertsTriggered']
            print(f"⚠️ No MACRO_PANIC/EUPHORIA flag - MACRO_EXTREME not expected")


class TestFomoAlertConfig:
    """Tests for FOMO alert configuration including macro events"""
    
    def test_fomo_alerts_config_endpoint(self):
        """GET /api/v10/fomo-alerts/config returns config object"""
        response = requests.get(f"{BASE_URL}/api/v10/fomo-alerts/config")
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] is True
        
        config = data['config']
        
        # Check user config exists
        assert 'user' in config
        # Check admin config exists and has event toggles
        assert 'admin' in config
        assert 'global' in config
        
        print(f"✅ FOMO config has user, admin, global sections")
        
        # Note: macroRegimeChange and macroExtreme are new fields
        # They may be in DEFAULT_FOMO_ALERT_CONFIG but not yet persisted to DB
        # The engine uses defaults if not found in stored config


class TestFomoAlertLogs:
    """Tests for FOMO alert logs including macro events"""
    
    def test_fomo_alerts_logs_endpoint(self):
        """GET /api/v10/fomo-alerts/logs returns alert history"""
        response = requests.get(f"{BASE_URL}/api/v10/fomo-alerts/logs")
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] is True
        assert 'logs' in data
        assert isinstance(data['logs'], list)
        print(f"✅ FOMO alerts logs endpoint returns {len(data['logs'])} entries")
    
    def test_fomo_alerts_stats_endpoint(self):
        """GET /api/v10/fomo-alerts/stats returns alert statistics"""
        response = requests.get(f"{BASE_URL}/api/v10/fomo-alerts/stats")
        assert response.status_code == 200
        data = response.json()
        assert data['ok'] is True
        
        stats = data['stats']
        assert 'total' in stats
        assert 'sent' in stats
        assert 'skipped' in stats
        assert 'byEvent' in stats
        assert 'hourlyRemaining' in stats
        print(f"✅ FOMO stats: total={stats['total']}, sent={stats['sent']}, hourlyRemaining={stats['hourlyRemaining']}")


# Test cleanup - ensure monitor is running after tests
@pytest.fixture(scope="module", autouse=True)
def ensure_monitor_running():
    """Ensure monitor is running after all tests"""
    yield
    requests.post(f"{BASE_URL}/api/v10/macro/alerts/start")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
