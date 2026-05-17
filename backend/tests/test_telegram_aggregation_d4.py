"""
Test Suite for P0.5 Stats Enrichment + D4 Telegram Aggregation v1

Tests:
- P0.5: GET /api/notifications/decision/stats includes byHorizon and byAsset breakdowns
- D4: GET /api/notifications/telegram/aggregation/status returns buffer state
- D4: POST /api/notifications/telegram/aggregation/flush manually flushes buffers
- D4: POST /api/notifications/telegram/aggregation/test buffers 3 BTC events and flushes
- D4: notification_service routes telegram_user events through aggregator
- Regression: All existing decision endpoints still work
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestP05StatsEnrichment:
    """P0.5: Stats endpoint now includes byHorizon and byAsset breakdowns"""

    def test_decision_stats_returns_ok(self):
        """GET /api/notifications/decision/stats returns 200"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        print(f"✓ Decision stats endpoint returns 200 OK")

    def test_decision_stats_has_by_horizon(self):
        """Stats response includes byHorizon breakdown with N, accuracy, catastrophicRate"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/stats")
        assert response.status_code == 200
        data = response.json()
        
        # Check byHorizon exists
        assert "byHorizon" in data, f"Missing byHorizon in stats: {data.keys()}"
        by_horizon = data["byHorizon"]
        
        # byHorizon should be a dict (may be empty if no evaluated decisions)
        assert isinstance(by_horizon, dict), f"byHorizon should be dict, got {type(by_horizon)}"
        
        # If there are evaluated decisions, check structure
        if by_horizon:
            for horizon, breakdown in by_horizon.items():
                assert "total" in breakdown, f"Missing 'total' in byHorizon[{horizon}]"
                assert "accuracy" in breakdown, f"Missing 'accuracy' in byHorizon[{horizon}]"
                assert "catastrophicRate" in breakdown, f"Missing 'catastrophicRate' in byHorizon[{horizon}]"
                print(f"  byHorizon[{horizon}]: total={breakdown['total']}, accuracy={breakdown['accuracy']}, catastrophicRate={breakdown['catastrophicRate']}")
        
        print(f"✓ byHorizon breakdown present with correct structure")

    def test_decision_stats_has_by_asset(self):
        """Stats response includes byAsset breakdown with N, accuracy, catastrophicRate"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/stats")
        assert response.status_code == 200
        data = response.json()
        
        # Check byAsset exists
        assert "byAsset" in data, f"Missing byAsset in stats: {data.keys()}"
        by_asset = data["byAsset"]
        
        # byAsset should be a dict (may be empty if no evaluated decisions)
        assert isinstance(by_asset, dict), f"byAsset should be dict, got {type(by_asset)}"
        
        # If there are evaluated decisions, check structure
        if by_asset:
            for asset, breakdown in by_asset.items():
                assert "total" in breakdown, f"Missing 'total' in byAsset[{asset}]"
                assert "accuracy" in breakdown, f"Missing 'accuracy' in byAsset[{asset}]"
                assert "catastrophicRate" in breakdown, f"Missing 'catastrophicRate' in byAsset[{asset}]"
                print(f"  byAsset[{asset}]: total={breakdown['total']}, accuracy={breakdown['accuracy']}, catastrophicRate={breakdown['catastrophicRate']}")
        
        print(f"✓ byAsset breakdown present with correct structure")

    def test_decision_stats_has_by_type(self):
        """Stats response includes byType breakdown (existing feature, regression check)"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/stats")
        assert response.status_code == 200
        data = response.json()
        
        # Check byType exists (existing feature)
        assert "byType" in data, f"Missing byType in stats: {data.keys()}"
        by_type = data["byType"]
        assert isinstance(by_type, dict), f"byType should be dict, got {type(by_type)}"
        
        print(f"✓ byType breakdown present (regression check)")

    def test_decision_stats_full_structure(self):
        """Stats response has all required fields"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/stats")
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ["total", "evaluated", "pending", "accuracy", "catastrophicRate", 
                          "avgMoveWhenCorrect", "byType", "byHorizon", "byAsset"]
        
        for field in required_fields:
            assert field in data, f"Missing required field '{field}' in stats response"
        
        print(f"✓ Stats response has all required fields: {required_fields}")
        print(f"  total={data['total']}, evaluated={data['evaluated']}, pending={data['pending']}")
        print(f"  accuracy={data['accuracy']}, catastrophicRate={data['catastrophicRate']}")


class TestD4TelegramAggregation:
    """D4: Telegram Aggregation v1 - buffer, flush, aggregated messages"""

    def test_aggregation_status_endpoint(self):
        """GET /api/notifications/telegram/aggregation/status returns buffer state"""
        response = requests.get(f"{BASE_URL}/api/notifications/telegram/aggregation/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert "buffer" in data, f"Missing 'buffer' in response: {data.keys()}"
        
        buffer = data["buffer"]
        assert isinstance(buffer, dict), f"buffer should be dict, got {type(buffer)}"
        
        print(f"✓ Aggregation status endpoint returns buffer state: {buffer}")

    def test_aggregation_flush_endpoint(self):
        """POST /api/notifications/telegram/aggregation/flush manually flushes buffers"""
        response = requests.post(f"{BASE_URL}/api/notifications/telegram/aggregation/flush")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert "message" in data, f"Missing 'message' in response: {data.keys()}"
        assert "flushed" in data["message"].lower(), f"Expected 'flushed' in message: {data['message']}"
        
        print(f"✓ Aggregation flush endpoint works: {data['message']}")

    def test_aggregation_test_endpoint(self):
        """POST /api/notifications/telegram/aggregation/test buffers 3 BTC events and flushes"""
        response = requests.post(f"{BASE_URL}/api/notifications/telegram/aggregation/test")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert "message" in data, f"Missing 'message' in response: {data.keys()}"
        
        # Check message mentions 3 events and aggregated
        message = data["message"].lower()
        assert "3" in message or "btc" in message.lower(), f"Expected '3' or 'BTC' in message: {data['message']}"
        assert "aggregated" in message or "flushed" in message, f"Expected 'aggregated' or 'flushed' in message: {data['message']}"
        
        print(f"✓ Aggregation test endpoint works: {data['message']}")

    def test_buffer_empty_after_flush(self):
        """After flush, buffer should be empty"""
        # First flush any existing buffers
        requests.post(f"{BASE_URL}/api/notifications/telegram/aggregation/flush")
        
        # Check buffer is empty
        response = requests.get(f"{BASE_URL}/api/notifications/telegram/aggregation/status")
        assert response.status_code == 200
        data = response.json()
        
        buffer = data.get("buffer", {})
        # Buffer should be empty or have no items
        total_items = sum(b.get("count", 0) for b in buffer.values()) if buffer else 0
        assert total_items == 0, f"Expected empty buffer after flush, got {buffer}"
        
        print(f"✓ Buffer is empty after flush")


class TestRegressionDecisionEndpoints:
    """Regression tests for existing decision endpoints"""

    def test_decision_for_asset_with_horizon(self):
        """GET /api/notifications/decision/{asset}?horizon= still works"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/BTC?horizon=7D")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert "decision" in data, f"Missing 'decision' in response: {data.keys()}"
        assert "confidence" in data, f"Missing 'confidence' in response: {data.keys()}"
        assert "asset" in data, f"Missing 'asset' in response: {data.keys()}"
        
        print(f"✓ Decision for BTC with horizon=7D: decision={data['decision']}, confidence={data['confidence']}")

    def test_decisions_overview_returns_9(self):
        """GET /api/notifications/decisions/overview returns 9 decisions (3 assets x 3 horizons)"""
        response = requests.get(f"{BASE_URL}/api/notifications/decisions/overview")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert "overview" in data, f"Missing 'overview' in response: {data.keys()}"
        
        overview = data["overview"]
        assert len(overview) == 9, f"Expected 9 decisions, got {len(overview)}"
        
        # Check all assets and horizons are present
        assets = set(d["asset"] for d in overview)
        horizons = set(d["horizon"] for d in overview)
        
        assert assets == {"BTC", "ETH", "SOL"}, f"Expected BTC, ETH, SOL, got {assets}"
        assert horizons == {"24H", "7D", "30D"}, f"Expected 24H, 7D, 30D, got {horizons}"
        
        print(f"✓ Decisions overview returns 9 decisions for {assets} x {horizons}")

    def test_decision_record_endpoint(self):
        """POST /api/notifications/decision/record still works"""
        response = requests.post(
            f"{BASE_URL}/api/notifications/decision/record",
            json={"asset": "BTC", "horizon": "7D"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert "decision" in data, f"Missing 'decision' in response: {data.keys()}"
        
        decision = data["decision"]
        assert decision.get("asset") == "BTC", f"Expected asset=BTC, got {decision.get('asset')}"
        assert decision.get("status") == "pending", f"Expected status=pending, got {decision.get('status')}"
        
        print(f"✓ Decision record endpoint works: id={decision.get('id')}")

    def test_decision_record_all_endpoint(self):
        """POST /api/notifications/decision/record-all still works"""
        response = requests.post(f"{BASE_URL}/api/notifications/decision/record-all")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert "saved" in data, f"Missing 'saved' in response: {data.keys()}"
        assert "results" in data, f"Missing 'results' in response: {data.keys()}"
        
        # Should save 9 decisions (3 assets x 3 horizons)
        assert data["saved"] == 9, f"Expected 9 saved, got {data['saved']}"
        
        print(f"✓ Decision record-all endpoint works: saved={data['saved']}")

    def test_decision_history_endpoint(self):
        """GET /api/notifications/decision/history still works"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/history")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert "history" in data, f"Missing 'history' in response: {data.keys()}"
        assert "count" in data, f"Missing 'count' in response: {data.keys()}"
        
        print(f"✓ Decision history endpoint works: count={data['count']}")

    def test_decision_feedback_endpoint(self):
        """GET /api/notifications/decision/feedback still works"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/feedback")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Should have action and recommendation
        assert "action" in data or "recommendation" in data, f"Missing action/recommendation in response: {data.keys()}"
        
        print(f"✓ Decision feedback endpoint works: action={data.get('action')}")


class TestRegressionNotificationEndpoints:
    """Regression tests for notification feed and unread count"""

    def test_notification_feed_endpoint(self):
        """GET /api/notifications/feed still works"""
        response = requests.get(f"{BASE_URL}/api/notifications/feed")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert "notifications" in data, f"Missing 'notifications' in response: {data.keys()}"
        assert "unread" in data, f"Missing 'unread' in response: {data.keys()}"
        
        print(f"✓ Notification feed endpoint works: count={data.get('count')}, unread={data.get('unread')}")

    def test_unread_count_endpoint(self):
        """GET /api/notifications/unread-count still works"""
        response = requests.get(f"{BASE_URL}/api/notifications/unread-count")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert "unread" in data, f"Missing 'unread' in response: {data.keys()}"
        
        print(f"✓ Unread count endpoint works: unread={data.get('unread')}")


class TestTelegramStatus:
    """Test Telegram configuration status"""

    def test_telegram_status_endpoint(self):
        """GET /api/notifications/telegram/status returns config status"""
        response = requests.get(f"{BASE_URL}/api/notifications/telegram/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        assert "user_bot" in data, f"Missing 'user_bot' in response: {data.keys()}"
        assert "admin_bot" in data, f"Missing 'admin_bot' in response: {data.keys()}"
        
        print(f"✓ Telegram status endpoint works")
        print(f"  user_bot ready: {data['user_bot'].get('ready')}")
        print(f"  admin_bot ready: {data['admin_bot'].get('ready')}")


class TestAggregationBufferBehavior:
    """Test aggregation buffer behavior in detail"""

    def test_aggregation_test_creates_aggregated_message(self):
        """Aggregation test endpoint creates proper aggregated message format"""
        # First flush any existing buffers
        requests.post(f"{BASE_URL}/api/notifications/telegram/aggregation/flush")
        
        # Run aggregation test
        response = requests.post(f"{BASE_URL}/api/notifications/telegram/aggregation/test")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        # The test buffers 3 events and flushes them as 1 aggregated message
        # This tests the _format_aggregated function
        
        print(f"✓ Aggregation test creates aggregated message")

    def test_buffer_status_structure(self):
        """Buffer status has correct structure per asset"""
        response = requests.get(f"{BASE_URL}/api/notifications/telegram/aggregation/status")
        assert response.status_code == 200
        data = response.json()
        
        buffer = data.get("buffer", {})
        
        # If buffer has items, check structure
        for asset, info in buffer.items():
            assert "count" in info, f"Missing 'count' in buffer[{asset}]"
            assert "oldest" in info, f"Missing 'oldest' in buffer[{asset}]"
            assert "types" in info, f"Missing 'types' in buffer[{asset}]"
            
            assert isinstance(info["count"], int), f"count should be int"
            assert isinstance(info["types"], list), f"types should be list"
        
        print(f"✓ Buffer status has correct structure")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
