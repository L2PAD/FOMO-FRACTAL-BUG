"""
P1 Production-Ready System API Tests
Tests for Risk, Warmth, ProxyQuality, and Worker endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com').rstrip('/')

class TestRiskEndpoints:
    """Test Risk Service endpoints"""
    
    def test_get_risk_report(self):
        """GET /api/admin/twitter-parser/risk/report - should return risk report"""
        response = requests.get(f"{BASE_URL}/api/admin/twitter-parser/risk/report")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] == True
        assert "data" in data
        
        report = data["data"]
        assert "total" in report
        assert "byStatus" in report
        assert "byRisk" in report
        assert "sessions" in report
        
        # Verify byStatus structure
        assert "OK" in report["byStatus"]
        assert "STALE" in report["byStatus"]
        assert "INVALID" in report["byStatus"]
        assert "EXPIRED" in report["byStatus"]
        
        # Verify byRisk structure
        assert "healthy" in report["byRisk"]
        assert "warning" in report["byRisk"]
        assert "critical" in report["byRisk"]
        
        print(f"Risk report: {report['total']} sessions, {report['byRisk']['healthy']} healthy, {report['byRisk']['warning']} warning, {report['byRisk']['critical']} critical")
    
    def test_get_risk_session_detail(self):
        """GET /api/admin/twitter-parser/risk/session/:sessionId - should return detailed risk for session"""
        # First get a session ID from the report
        report_response = requests.get(f"{BASE_URL}/api/admin/twitter-parser/risk/report")
        report = report_response.json()["data"]
        
        if report["total"] == 0:
            pytest.skip("No sessions available for testing")
        
        session_id = report["sessions"][0]["sessionId"]
        
        response = requests.get(f"{BASE_URL}/api/admin/twitter-parser/risk/session/{session_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] == True
        assert "data" in data
        
        detail = data["data"]
        assert detail["sessionId"] == session_id
        assert "status" in detail
        assert "riskScore" in detail
        assert "factors" in detail
        assert "breakdown" in detail
        assert "lifetime" in detail
        
        # Verify factors structure
        factors = detail["factors"]
        assert "cookieAgeHours" in factors
        assert "warmthFailureRate" in factors
        assert "parserErrorRate" in factors
        assert "rateLimitPressure" in factors
        assert "idleHours" in factors
        assert "hasRequiredCookies" in factors
        
        # Verify breakdown structure
        breakdown = detail["breakdown"]
        assert "cookieAge" in breakdown
        assert "warmth" in breakdown
        assert "parserErrors" in breakdown
        
        print(f"Session {session_id}: risk={detail['riskScore']}, status={detail['status']}, lifetime={detail['lifetime']['days']}d")
    
    def test_get_risk_session_not_found(self):
        """GET /api/admin/twitter-parser/risk/session/:sessionId - should return 404 for non-existent session"""
        response = requests.get(f"{BASE_URL}/api/admin/twitter-parser/risk/session/non_existent_session_12345")
        assert response.status_code == 404
        
        data = response.json()
        assert data["ok"] == False
        assert "error" in data
    
    def test_post_risk_recalculate(self):
        """POST /api/admin/twitter-parser/risk/recalculate - should recalculate risk for all sessions"""
        response = requests.post(f"{BASE_URL}/api/admin/twitter-parser/risk/recalculate")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] == True
        assert "checked" in data
        assert "changed" in data
        
        print(f"Risk recalculated: {data['checked']} checked, {data['changed']} changed")


class TestWarmthEndpoints:
    """Test Warmth Service endpoints"""
    
    def test_get_warmth_status(self):
        """GET /api/admin/twitter-parser/warmth/status - should return warmth status"""
        response = requests.get(f"{BASE_URL}/api/admin/twitter-parser/warmth/status")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] == True
        assert "needingWarmth" in data
        assert "sessions" in data
        
        print(f"Warmth status: {data['needingWarmth']} sessions needing warmth")
    
    def test_post_warmth_run(self):
        """POST /api/admin/twitter-parser/warmth/run - should run warmth on all sessions"""
        response = requests.post(f"{BASE_URL}/api/admin/twitter-parser/warmth/run")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] == True
        assert "checked" in data
        assert "success" in data
        assert "failed" in data
        
        print(f"Warmth run: {data['checked']} checked, {data['success']} success, {data['failed']} failed")


class TestProxyQualityEndpoints:
    """Test Proxy Quality Service endpoints"""
    
    def test_get_proxy_quality(self):
        """GET /api/admin/twitter-parser/proxy/quality - should return proxy quality report"""
        response = requests.get(f"{BASE_URL}/api/admin/twitter-parser/proxy/quality")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] == True
        assert "data" in data
        
        report = data["data"]
        assert "total" in report
        assert "healthy" in report
        assert "degraded" in report
        assert "critical" in report
        assert "avgScore" in report
        assert "proxies" in report
        
        print(f"Proxy quality: {report['total']} proxies, avg score={report['avgScore']}, {report['healthy']} healthy")


class TestWorkerEndpoints:
    """Test Session Health Worker endpoints"""
    
    def test_get_worker_status(self):
        """GET /api/admin/twitter-parser/worker/status - should return worker status"""
        response = requests.get(f"{BASE_URL}/api/admin/twitter-parser/worker/status")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] == True
        assert "data" in data
        
        status = data["data"]
        assert "isRunning" in status
        assert "config" in status
        
        config = status["config"]
        assert "warmthIntervalMs" in config
        assert "riskIntervalMs" in config
        assert "dailySummaryHour" in config
        
        print(f"Worker status: running={status['isRunning']}, warmth interval={config['warmthIntervalMs']}ms, risk interval={config['riskIntervalMs']}ms")
    
    def test_post_worker_run_now(self):
        """POST /api/admin/twitter-parser/worker/run-now - should trigger manual health check"""
        response = requests.post(f"{BASE_URL}/api/admin/twitter-parser/worker/run-now")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] == True
        assert "message" in data
        
        print(f"Worker run-now: {data['message']}")


class TestSessionsWithP1Fields:
    """Test that sessions have P1 fields"""
    
    def test_sessions_have_risk_fields(self):
        """GET /api/admin/twitter-parser/sessions - should return sessions with P1 fields"""
        response = requests.get(f"{BASE_URL}/api/admin/twitter-parser/sessions")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] == True
        assert "data" in data
        
        sessions = data["data"]
        if len(sessions) == 0:
            pytest.skip("No sessions available for testing")
        
        # Check that sessions have P1 fields
        for session in sessions:
            # riskScore should be present (may be 0 or higher)
            assert "riskScore" in session or session.get("riskScore") is not None or session.get("riskScore") == 0
            
            # Check for other P1 fields (may be null/undefined for new sessions)
            # These fields should exist in the schema
            print(f"Session {session['sessionId']}: riskScore={session.get('riskScore')}, expectedLifetimeDays={session.get('expectedLifetimeDays')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
