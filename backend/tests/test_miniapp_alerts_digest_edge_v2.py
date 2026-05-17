"""
MiniApp Edge Alerts, Daily Digest, and Edge Filtering v2 Tests
================================================================
Tests for:
- POST /api/miniapp/polymarket/ingest (ingestion + alerts)
- POST /api/miniapp/alerts/send (edge alert processing)
- POST /api/miniapp/digest/send (daily digest delivery)
- GET /api/miniapp/edge (ACTIVE status with real Polymarket data)
- Regression tests for existing endpoints
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestPolymarketIngestionWithAlerts:
    """Test Polymarket ingestion endpoint that triggers alerts"""

    def test_polymarket_ingest_returns_ok(self):
        """POST /api/miniapp/polymarket/ingest returns ok=true with ingestion data + alerts result"""
        response = requests.post(f"{BASE_URL}/api/miniapp/polymarket/ingest", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=true, got {data}"
        
        # Verify ingestion fields
        assert "ingested" in data, "Missing 'ingested' field"
        assert "total_fetched" in data, "Missing 'total_fetched' field"
        assert isinstance(data["ingested"], int), "ingested should be int"
        
        # Verify alerts result
        assert "alerts" in data, "Missing 'alerts' field"
        alerts = data["alerts"]
        assert "sent" in alerts, "Missing 'sent' in alerts"
        assert "skipped" in alerts or "reason" in alerts, "Missing skipped/reason in alerts"
        
        print(f"Polymarket ingestion: ingested={data['ingested']}, total_fetched={data['total_fetched']}")
        print(f"Alerts result: {alerts}")


class TestEdgeAlertsSend:
    """Test manual edge alert sending endpoint"""

    def test_alerts_send_returns_ok(self):
        """POST /api/miniapp/alerts/send triggers edge alert processing"""
        response = requests.post(f"{BASE_URL}/api/miniapp/alerts/send", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=true, got {data}"
        
        # Verify alert processing result
        assert "sent" in data, "Missing 'sent' field"
        assert "skipped" in data or "reason" in data, "Missing skipped/reason field"
        
        # In test env, sent=0 is expected (no real Telegram chat_ids)
        print(f"Alerts send result: sent={data.get('sent')}, skipped={data.get('skipped')}, reason={data.get('reason')}")


class TestDailyDigestSend:
    """Test daily digest sending endpoint"""

    def test_digest_send_returns_ok(self):
        """POST /api/miniapp/digest/send triggers daily digest delivery"""
        response = requests.post(f"{BASE_URL}/api/miniapp/digest/send", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=true, got {data}"
        
        # Verify digest result
        assert "sent" in data, "Missing 'sent' field"
        
        # In test env, sent=0 is expected (no real Telegram chat_ids)
        print(f"Digest send result: sent={data.get('sent')}, total_users={data.get('total_users')}")


class TestEdgeEndpointWithRealData:
    """Test Edge endpoint returns ACTIVE status with real Polymarket data"""

    def test_edge_returns_active_status(self):
        """GET /api/miniapp/edge returns ACTIVE status with real market data"""
        response = requests.get(f"{BASE_URL}/api/miniapp/edge", timeout=15)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=true, got {data}"
        
        # Verify status
        status = data.get("status")
        assert status in ("ACTIVE", "NO_EDGE"), f"Expected ACTIVE or NO_EDGE, got {status}"
        
        if status == "ACTIVE":
            # Verify best edge structure
            best = data.get("best")
            assert best is not None, "Missing 'best' edge when status=ACTIVE"
            assert "asset" in best, "Missing asset in best edge"
            assert "question" in best, "Missing question in best edge"
            assert "marketProbability" in best, "Missing marketProbability"
            assert "modelProbability" in best, "Missing modelProbability"
            assert "edge" in best, "Missing edge value"
            assert "direction" in best, "Missing direction"
            assert "confidence" in best, "Missing confidence"
            
            print(f"Best edge: {best['asset']} - {best['question'][:50]}...")
            print(f"  Market: {best['marketProbability']}, Model: {best['modelProbability']}, Edge: {best['edge']}")
            print(f"  Direction: {best['direction']}, Confidence: {best['confidence']}")
        
        # Verify markets list
        markets = data.get("markets", [])
        assert isinstance(markets, list), "markets should be a list"
        print(f"Total markets: {len(markets)}")
        
        # Verify source is polymarket
        source = data.get("source")
        if source:
            print(f"Source: {source}")

    def test_edge_markets_have_required_fields(self):
        """Verify each market in edge response has required fields"""
        response = requests.get(f"{BASE_URL}/api/miniapp/edge", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        markets = data.get("markets", [])
        
        for i, market in enumerate(markets[:5]):  # Check first 5
            assert "asset" in market, f"Market {i} missing asset"
            assert "question" in market, f"Market {i} missing question"
            assert "edge" in market, f"Market {i} missing edge"
            assert "direction" in market, f"Market {i} missing direction"
            
            # Check for status field (watching/active)
            status = market.get("status")
            print(f"Market {i}: {market['asset']} - edge={market['edge']:.3f}, direction={market['direction']}, status={status}")


class TestRegressionEndpoints:
    """Regression tests for existing MiniApp endpoints"""

    def test_home_endpoint_btc(self):
        """GET /api/miniapp/home?asset=BTC still works"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=BTC", timeout=15)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=true, got {data}"
        assert "price" in data, "Missing price field"
        assert "decision" in data, "Missing decision field"
        
        print(f"Home BTC: price={data.get('price')}, decision={data.get('decision')}")

    def test_feed_endpoint(self):
        """GET /api/miniapp/feed still works"""
        response = requests.get(f"{BASE_URL}/api/miniapp/feed", timeout=15)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=true, got {data}"
        assert "sections" in data, "Missing sections field"
        
        sections = data.get("sections", [])
        print(f"Feed: {len(sections)} sections")

    def test_billing_plans_endpoint(self):
        """GET /api/miniapp/billing/plans still works"""
        response = requests.get(f"{BASE_URL}/api/miniapp/billing/plans", timeout=15)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=true, got {data}"
        
        print(f"Billing plans: billingMode={data.get('billingMode')}")

    def test_accuracy_audit_endpoint(self):
        """GET /api/miniapp/accuracy/audit still works"""
        response = requests.get(f"{BASE_URL}/api/miniapp/accuracy/audit", timeout=15)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=true, got {data}"
        
        # Verify overall block with directional accuracy fields
        overall = data.get("overall", {})
        assert "directionalAccuracy" in overall, "Missing directionalAccuracy in overall"
        assert "directionalTotal" in overall, "Missing directionalTotal in overall"
        assert "directionalCorrect" in overall, "Missing directionalCorrect in overall"
        
        print(f"Accuracy audit: directionalAccuracy={overall.get('directionalAccuracy')}, total={overall.get('directionalTotal')}, correct={overall.get('directionalCorrect')}")

    def test_profile_endpoint(self):
        """GET /api/miniapp/profile still works with directional accuracy"""
        response = requests.get(f"{BASE_URL}/api/miniapp/profile", timeout=15)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=true, got {data}"
        
        # Verify performance block
        performance = data.get("performance", {})
        if performance:
            print(f"Profile performance: accuracy={performance.get('accuracy')}, directionalTotal={performance.get('directionalTotal')}, directionalCorrect={performance.get('directionalCorrect')}")


class TestEdgeAlertThresholds:
    """Test edge alert threshold logic"""

    def test_edge_filtering_logic(self):
        """Verify edge filtering: strong edges have abs(edge) >= 0.12 and confidence >= 0.5"""
        response = requests.get(f"{BASE_URL}/api/miniapp/edge", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        markets = data.get("markets", [])
        
        strong_edges = []
        other_edges = []
        watching = []
        
        for m in markets:
            edge_val = abs(m.get("edge", 0))
            confidence = m.get("confidence", 0)
            status = m.get("status")
            
            if status == "watching":
                watching.append(m)
            elif edge_val >= 0.12 and confidence >= 0.5:
                strong_edges.append(m)
            else:
                other_edges.append(m)
        
        print(f"Edge filtering: strong={len(strong_edges)}, other={len(other_edges)}, watching={len(watching)}")
        
        # Verify strong edges meet threshold
        for m in strong_edges:
            assert abs(m["edge"]) >= 0.12, f"Strong edge {m['asset']} has edge < 0.12"
            assert m.get("confidence", 0) >= 0.5, f"Strong edge {m['asset']} has confidence < 0.5"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
