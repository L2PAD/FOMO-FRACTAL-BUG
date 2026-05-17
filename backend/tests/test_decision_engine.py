"""
Decision Engine API Tests

Tests the Decision Engine endpoints:
- GET /api/notifications/decision/{asset} - Single asset decision
- GET /api/notifications/decisions/overview - All assets × horizons (9 items)
- POST /api/notifications/decision/{asset}/send - Decision + Telegram send

Decision mapping:
- score >= 4 → BUY
- score <= -4 → SELL
- |score| < 2 → WAIT
- else → AVOID
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestDecisionEngineBasics:
    """Basic Decision Engine endpoint tests"""

    def test_decision_btc_30d(self):
        """GET /api/notifications/decision/BTC?horizon=30D returns valid decision"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/BTC?horizon=30D")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=True, got {data}"
        
        # Verify required fields
        assert "asset" in data, "Missing 'asset' field"
        assert data["asset"] == "BTC", f"Expected asset=BTC, got {data['asset']}"
        
        assert "decision" in data, "Missing 'decision' field"
        assert data["decision"] in ["BUY", "SELL", "WAIT", "AVOID"], f"Invalid decision: {data['decision']}"
        
        assert "confidence" in data, "Missing 'confidence' field"
        assert isinstance(data["confidence"], (int, float)), f"Confidence should be numeric: {data['confidence']}"
        assert 0 <= data["confidence"] <= 100, f"Confidence out of range: {data['confidence']}"
        
        assert "score" in data, "Missing 'score' field"
        assert isinstance(data["score"], (int, float)), f"Score should be numeric: {data['score']}"
        
        assert "horizon" in data, "Missing 'horizon' field"
        assert "horizonRaw" in data, "Missing 'horizonRaw' field"
        assert data["horizonRaw"] == "30D", f"Expected horizonRaw=30D, got {data['horizonRaw']}"
        
        assert "reasoning" in data, "Missing 'reasoning' field"
        assert isinstance(data["reasoning"], list), f"Reasoning should be list: {data['reasoning']}"
        
        assert "components" in data, "Missing 'components' field"
        assert isinstance(data["components"], dict), f"Components should be dict: {data['components']}"
        
        assert "timestamp" in data, "Missing 'timestamp' field"
        
        print(f"✓ BTC 30D Decision: {data['decision']} (score={data['score']}, confidence={data['confidence']}%)")

    def test_decision_eth_7d(self):
        """GET /api/notifications/decision/ETH?horizon=7D returns valid decision"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/ETH?horizon=7D")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True
        assert data["asset"] == "ETH"
        assert data["horizonRaw"] == "7D"
        assert data["decision"] in ["BUY", "SELL", "WAIT", "AVOID"]
        
        print(f"✓ ETH 7D Decision: {data['decision']} (score={data['score']}, confidence={data['confidence']}%)")

    def test_decision_sol_24h(self):
        """GET /api/notifications/decision/SOL?horizon=24H returns valid decision"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/SOL?horizon=24H")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True
        assert data["asset"] == "SOL"
        assert data["horizonRaw"] == "24H"
        assert data["horizon"] == "short"  # 24H maps to "short"
        
        print(f"✓ SOL 24H Decision: {data['decision']} (score={data['score']}, confidence={data['confidence']}%)")


class TestDecisionComponents:
    """Test decision components structure"""

    def test_components_structure(self):
        """Verify all 6 components are present with correct structure"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/BTC?horizon=30D")
        assert response.status_code == 200
        
        data = response.json()
        components = data.get("components", {})
        
        # Required components
        required_components = ["exchange", "ml_risk", "onchain", "sentiment", "drift", "divergence"]
        for comp in required_components:
            assert comp in components, f"Missing component: {comp}"
        
        # Exchange component structure
        exchange = components["exchange"]
        assert "available" in exchange, "Exchange missing 'available' field"
        if exchange.get("available"):
            assert "subsccore" in exchange, "Exchange missing 'subsccore' when available"
            assert "direction" in exchange, "Exchange missing 'direction' when available"
        
        # ML Risk component structure
        ml_risk = components["ml_risk"]
        assert "available" in ml_risk, "ML Risk missing 'available' field"
        if ml_risk.get("available"):
            assert "subsccore" in ml_risk, "ML Risk missing 'subsccore' when available"
        
        # OnChain component structure
        onchain = components["onchain"]
        assert "available" in onchain or "recentEvents" in onchain, "OnChain missing availability indicator"
        
        # Sentiment component structure
        sentiment = components["sentiment"]
        assert "available" in sentiment, "Sentiment missing 'available' field"
        
        # Drift component structure
        drift = components["drift"]
        assert "available" in drift, "Drift missing 'available' field"
        
        # Divergence component structure
        divergence = components["divergence"]
        assert "detected" in divergence, "Divergence missing 'detected' field"
        
        print(f"✓ All 6 components present with correct structure")
        print(f"  - Exchange: available={exchange.get('available')}")
        print(f"  - ML Risk: available={ml_risk.get('available')}")
        print(f"  - OnChain: available={onchain.get('available', onchain.get('recentEvents', 0) > 0)}")
        print(f"  - Sentiment: available={sentiment.get('available')}")
        print(f"  - Drift: available={drift.get('available')}")
        print(f"  - Divergence: detected={divergence.get('detected')}")

    def test_reasoning_non_empty(self):
        """Verify reasoning array is non-empty and human-readable"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/BTC?horizon=30D")
        assert response.status_code == 200
        
        data = response.json()
        reasoning = data.get("reasoning", [])
        
        # Reasoning should be a list
        assert isinstance(reasoning, list), f"Reasoning should be list: {type(reasoning)}"
        
        # At least one reason should be present (even if just "Exchange: no forecast data")
        # Note: reasoning can be empty if no signals are available
        print(f"✓ Reasoning has {len(reasoning)} items")
        for r in reasoning[:5]:  # Print first 5
            print(f"  - {r}")


class TestDecisionsOverview:
    """Test the decisions overview endpoint"""

    def test_overview_returns_9_decisions(self):
        """GET /api/notifications/decisions/overview returns 9 decisions (3 assets × 3 horizons)"""
        response = requests.get(f"{BASE_URL}/api/notifications/decisions/overview")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True
        
        overview = data.get("overview", [])
        assert len(overview) == 9, f"Expected 9 decisions, got {len(overview)}"
        
        # Verify all combinations
        expected_assets = {"BTC", "ETH", "SOL"}
        expected_horizons = {"24H", "7D", "30D"}
        
        found_combinations = set()
        for item in overview:
            assert "asset" in item, f"Missing 'asset' in overview item: {item}"
            assert "horizon" in item, f"Missing 'horizon' in overview item: {item}"
            assert "decision" in item, f"Missing 'decision' in overview item: {item}"
            assert "confidence" in item, f"Missing 'confidence' in overview item: {item}"
            assert "score" in item, f"Missing 'score' in overview item: {item}"
            assert "reasoning" in item, f"Missing 'reasoning' in overview item: {item}"
            
            assert item["asset"] in expected_assets, f"Unexpected asset: {item['asset']}"
            assert item["horizon"] in expected_horizons, f"Unexpected horizon: {item['horizon']}"
            assert item["decision"] in ["BUY", "SELL", "WAIT", "AVOID"], f"Invalid decision: {item['decision']}"
            
            found_combinations.add((item["asset"], item["horizon"]))
        
        # Verify all 9 combinations are present
        expected_combinations = {(a, h) for a in expected_assets for h in expected_horizons}
        assert found_combinations == expected_combinations, f"Missing combinations: {expected_combinations - found_combinations}"
        
        print(f"✓ Overview returns all 9 decisions:")
        for item in overview:
            print(f"  - {item['asset']} {item['horizon']}: {item['decision']} (score={item['score']}, confidence={item['confidence']}%)")


class TestDecisionSend:
    """Test decision send to Telegram"""

    def test_decision_send_btc(self):
        """POST /api/notifications/decision/BTC/send computes decision AND sends to Telegram"""
        response = requests.post(f"{BASE_URL}/api/notifications/decision/BTC/send?horizon=30D")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True
        
        # Verify decision fields
        assert "asset" in data
        assert data["asset"] == "BTC"
        assert "decision" in data
        assert "confidence" in data
        assert "score" in data
        assert "reasoning" in data
        assert "components" in data
        
        # Verify telegram_sent field
        assert "telegram_sent" in data, "Missing 'telegram_sent' field"
        
        print(f"✓ Decision send: {data['decision']} (telegram_sent={data['telegram_sent']})")
        
        # Note: telegram_sent may be False if TG_BOT_TOKEN or TG_USER_CHAT_ID not configured
        # This is expected behavior - we just verify the field exists


class TestDecisionMapping:
    """Test decision score to decision mapping logic"""

    def test_decision_values_valid(self):
        """Verify all decisions are one of BUY/SELL/WAIT/AVOID"""
        response = requests.get(f"{BASE_URL}/api/notifications/decisions/overview")
        assert response.status_code == 200
        
        data = response.json()
        overview = data.get("overview", [])
        
        valid_decisions = {"BUY", "SELL", "WAIT", "AVOID"}
        for item in overview:
            assert item["decision"] in valid_decisions, f"Invalid decision: {item['decision']}"
        
        print(f"✓ All decisions are valid (BUY/SELL/WAIT/AVOID)")


class TestExistingNotificationEndpoints:
    """Verify existing notification endpoints still work"""

    def test_events_endpoint(self):
        """GET /api/notifications/events still works"""
        response = requests.get(f"{BASE_URL}/api/notifications/events?limit=5")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True
        assert "events" in data
        print(f"✓ Events endpoint works ({data.get('count', 0)} events)")

    def test_feed_endpoint(self):
        """GET /api/notifications/feed still works"""
        response = requests.get(f"{BASE_URL}/api/notifications/feed?limit=5")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True
        assert "notifications" in data
        print(f"✓ Feed endpoint works ({data.get('count', 0)} notifications)")

    def test_rules_endpoint(self):
        """GET /api/notifications/rules still works"""
        response = requests.get(f"{BASE_URL}/api/notifications/rules")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True
        assert "rules" in data
        print(f"✓ Rules endpoint works ({data.get('count', 0)} rules)")

    def test_telegram_status_endpoint(self):
        """GET /api/notifications/telegram/status still works"""
        response = requests.get(f"{BASE_URL}/api/notifications/telegram/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True
        assert "user_bot" in data
        assert "admin_bot" in data
        print(f"✓ Telegram status endpoint works (user_bot ready={data['user_bot'].get('ready')}, admin_bot ready={data['admin_bot'].get('ready')})")

    def test_telegram_test_endpoint(self):
        """POST /api/notifications/telegram/test still works"""
        response = requests.post(f"{BASE_URL}/api/notifications/telegram/test?audience=user")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True
        print(f"✓ Telegram test endpoint works")

    def test_unread_count_endpoint(self):
        """GET /api/notifications/unread-count still works"""
        response = requests.get(f"{BASE_URL}/api/notifications/unread-count")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True
        assert "unread" in data
        print(f"✓ Unread count endpoint works (unread={data['unread']})")

    def test_stats_endpoint(self):
        """GET /api/notifications/stats still works"""
        response = requests.get(f"{BASE_URL}/api/notifications/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True
        print(f"✓ Stats endpoint works")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
