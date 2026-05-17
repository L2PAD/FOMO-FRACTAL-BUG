"""
MiniApp Core API Tests
======================
Tests for the Telegram MiniApp Decision Delivery Layer endpoints.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestMiniAppCoreAPI:
    """Tests for /api/miniapp/core endpoint"""

    def test_btc_core_returns_valid_json(self):
        """GET /api/miniapp/core?asset=BTC returns valid JSON with all required fields"""
        response = requests.get(f"{BASE_URL}/api/miniapp/core?asset=BTC")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        assert data.get("asset") == "BTC"
        
        # Check decision structure
        decision = data.get("decision")
        assert decision is not None
        assert "action" in decision
        assert decision["action"] in ["BUY", "SELL", "WAIT", "AVOID"]
        assert "strength" in decision
        assert "confidence" in decision
        assert isinstance(decision["confidence"], (int, float))
        
        # Check market structure
        market = data.get("market")
        assert market is not None
        assert "current_price" in market
        assert "horizon" in market
        assert "story" in market
        assert "scenario" in market
        
        # Check signals structure
        signals = data.get("signals")
        assert signals is not None
        assert "exchange" in signals
        assert "onchain" in signals
        assert "sentiment" in signals
        assert "twitter" in signals
        assert "ml_risk" in signals
        
        # Check polymarket structure
        polymarket = data.get("polymarket")
        assert polymarket is not None
        assert "market" in polymarket
        assert "edge" in polymarket
        assert "action" in polymarket
        
        # Check alerts structure
        alerts = data.get("alerts")
        assert alerts is not None
        assert isinstance(alerts, list)
        
        # Check generated_at timestamp
        assert "generated_at" in data

    def test_eth_core_returns_valid_data(self):
        """GET /api/miniapp/core?asset=ETH returns valid data for ETH"""
        response = requests.get(f"{BASE_URL}/api/miniapp/core?asset=ETH")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        assert data.get("asset") == "ETH"
        
        # Verify decision exists
        decision = data.get("decision")
        assert decision is not None
        assert decision["action"] in ["BUY", "SELL", "WAIT", "AVOID"]
        
        # Verify market data
        market = data.get("market")
        assert market is not None
        assert market.get("current_price", 0) > 0

    def test_sol_core_returns_valid_data(self):
        """GET /api/miniapp/core?asset=SOL returns valid data for SOL"""
        response = requests.get(f"{BASE_URL}/api/miniapp/core?asset=SOL")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        assert data.get("asset") == "SOL"
        
        # Verify decision exists
        decision = data.get("decision")
        assert decision is not None
        assert decision["action"] in ["BUY", "SELL", "WAIT", "AVOID"]
        
        # Verify market data
        market = data.get("market")
        assert market is not None
        assert market.get("current_price", 0) > 0

    def test_default_asset_is_btc(self):
        """GET /api/miniapp/core without asset param defaults to BTC"""
        response = requests.get(f"{BASE_URL}/api/miniapp/core")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("asset") == "BTC"

    def test_case_insensitive_asset(self):
        """Asset parameter should be case-insensitive"""
        response = requests.get(f"{BASE_URL}/api/miniapp/core?asset=btc")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("asset") == "BTC"

    def test_decision_confidence_range(self):
        """Decision confidence should be between 0 and 100"""
        response = requests.get(f"{BASE_URL}/api/miniapp/core?asset=BTC")
        assert response.status_code == 200
        
        data = response.json()
        confidence = data.get("decision", {}).get("confidence", -1)
        assert 0 <= confidence <= 100

    def test_market_scenario_structure(self):
        """Market scenario should have required fields"""
        response = requests.get(f"{BASE_URL}/api/miniapp/core?asset=BTC")
        assert response.status_code == 200
        
        data = response.json()
        scenario = data.get("market", {}).get("scenario", {})
        
        assert "type" in scenario
        assert "probability" in scenario
        assert "range_low" in scenario
        assert "range_high" in scenario

    def test_signals_exchange_structure(self):
        """Exchange signal should have direction and strength"""
        response = requests.get(f"{BASE_URL}/api/miniapp/core?asset=BTC")
        assert response.status_code == 200
        
        data = response.json()
        exchange = data.get("signals", {}).get("exchange", {})
        
        assert "direction" in exchange
        assert exchange["direction"] in ["bullish", "bearish", "neutral"]
        assert "strength" in exchange

    def test_signals_ml_risk_structure(self):
        """ML Risk signal should have level and score"""
        response = requests.get(f"{BASE_URL}/api/miniapp/core?asset=BTC")
        assert response.status_code == 200
        
        data = response.json()
        ml_risk = data.get("signals", {}).get("ml_risk", {})
        
        assert "level" in ml_risk
        assert ml_risk["level"] in ["low", "medium", "high", "unknown"]
        assert "score" in ml_risk

    def test_alerts_structure(self):
        """Alerts should have required fields"""
        response = requests.get(f"{BASE_URL}/api/miniapp/core?asset=BTC")
        assert response.status_code == 200
        
        data = response.json()
        alerts = data.get("alerts", [])
        
        if len(alerts) > 0:
            alert = alerts[0]
            assert "type" in alert
            assert "message" in alert
            assert "impact" in alert
            assert alert["impact"] in ["bullish", "bearish", "neutral"]


class TestMiniAppWebhook:
    """Tests for /api/miniapp/webhook endpoint"""

    def test_webhook_start_command(self):
        """POST /api/miniapp/webhook handles /start command"""
        payload = {
            "message": {
                "chat": {"id": 123456789},
                "text": "/start"
            }
        }
        response = requests.post(
            f"{BASE_URL}/api/miniapp/webhook",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True

    def test_webhook_btc_command(self):
        """POST /api/miniapp/webhook handles /btc command"""
        payload = {
            "message": {
                "chat": {"id": 123456789},
                "text": "/btc"
            }
        }
        response = requests.post(
            f"{BASE_URL}/api/miniapp/webhook",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True

    def test_webhook_eth_command(self):
        """POST /api/miniapp/webhook handles /eth command"""
        payload = {
            "message": {
                "chat": {"id": 123456789},
                "text": "/eth"
            }
        }
        response = requests.post(
            f"{BASE_URL}/api/miniapp/webhook",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True

    def test_webhook_sol_command(self):
        """POST /api/miniapp/webhook handles /sol command"""
        payload = {
            "message": {
                "chat": {"id": 123456789},
                "text": "/sol"
            }
        }
        response = requests.post(
            f"{BASE_URL}/api/miniapp/webhook",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True

    def test_webhook_empty_update(self):
        """POST /api/miniapp/webhook handles empty update gracefully"""
        payload = {}
        response = requests.post(
            f"{BASE_URL}/api/miniapp/webhook",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
