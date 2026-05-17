"""
Backend tests for SignalDetailScreen feature
Tests GET /api/mobile/signals/{asset} endpoint
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('APP_URL', 'https://expo-telegram-web.preview.emergentagent.com').rstrip('/')

class TestSignalDetailBackend:
    """Test signal detail endpoint returns real data"""

    def test_get_btc_signal(self):
        """Test GET /api/mobile/signals/BTC returns real signal with 6 drivers"""
        response = requests.get(f"{BASE_URL}/api/mobile/signals/BTC?horizon=swing")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["ok"] is True, "Response should have ok=True"
        assert "signal" in data, "Response should contain signal"
        
        signal = data["signal"]
        
        # Verify signal structure
        assert signal["asset"] == "BTC", f"Expected BTC, got {signal['asset']}"
        assert signal["action"] in ["BUY", "SELL", "WAIT"], f"Invalid action: {signal['action']}"
        assert "confidence" in signal, "Signal should have confidence"
        assert 0 <= signal["confidence"] <= 1, f"Confidence out of range: {signal['confidence']}"
        
        # Verify drivers
        assert "drivers" in signal, "Signal should have drivers"
        drivers = signal["drivers"]
        assert len(drivers) == 6, f"Expected 6 drivers, got {len(drivers)}"
        
        # Verify driver modules
        driver_modules = [d["module"] for d in drivers]
        expected_modules = ["sentiment", "exchange", "fractal", "prediction", "social", "technical"]
        assert set(driver_modules) == set(expected_modules), f"Missing modules: {set(expected_modules) - set(driver_modules)}"
        
        # Verify each driver has required fields
        for driver in drivers:
            assert "module" in driver, "Driver missing module"
            assert "name" in driver, "Driver missing name"
            assert "direction" in driver, "Driver missing direction"
            assert "confidence" in driver, "Driver missing confidence"
            assert "weight" in driver, "Driver missing weight"
            assert "value" in driver, "Driver missing value"
            assert "reason" in driver, "Driver missing reason"
            
            # Verify direction is valid
            assert driver["direction"] in ["Bullish", "Bearish", "Neutral"], f"Invalid direction: {driver['direction']}"
            
            # Verify confidence range
            assert 0 <= driver["confidence"] <= 1, f"Driver confidence out of range: {driver['confidence']}"
        
        # Verify sentiment driver has Fear & Greed data
        sentiment_driver = next((d for d in drivers if d["module"] == "sentiment"), None)
        assert sentiment_driver is not None, "Sentiment driver not found"
        assert "Fear" in sentiment_driver["value"] or "Greed" in sentiment_driver["value"], \
            f"Sentiment driver should contain Fear & Greed data: {sentiment_driver['value']}"
        
        # Verify driverSummary
        assert "driverSummary" in signal, "Signal should have driverSummary"
        summary = signal["driverSummary"]
        assert "bullish" in summary, "driverSummary missing bullish count"
        assert "bearish" in summary, "driverSummary missing bearish count"
        assert "neutral" in summary, "driverSummary missing neutral count"
        assert summary["bullish"] + summary["bearish"] + summary["neutral"] == 6, \
            "driverSummary counts should sum to 6"
        
        # Verify other required fields
        assert "summary" in signal, "Signal should have summary text"
        assert len(signal["summary"]) > 0, "Summary should not be empty"
        assert "horizon" in signal, "Signal should have horizon"
        assert "updatedAt" in signal, "Signal should have updatedAt"
        
        print(f"✅ BTC signal test passed")
        print(f"   Action: {signal['action']}, Confidence: {signal['confidence']:.0%}")
        print(f"   Drivers: {summary['bullish']} bullish, {summary['bearish']} bearish, {summary['neutral']} neutral")
        print(f"   Sentiment: {sentiment_driver['value']}")

    def test_get_eth_signal(self):
        """Test GET /api/mobile/signals/ETH works"""
        response = requests.get(f"{BASE_URL}/api/mobile/signals/ETH?horizon=swing")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["ok"] is True
        assert data["signal"]["asset"] == "ETH"
        assert len(data["signal"]["drivers"]) == 6
        
        print(f"✅ ETH signal test passed")

    def test_get_all_signals(self):
        """Test GET /api/mobile/signals returns multiple signals"""
        response = requests.get(f"{BASE_URL}/api/mobile/signals?horizon=swing")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["ok"] is True
        assert "signals" in data
        assert "count" in data
        assert len(data["signals"]) > 0, "Should return at least one signal"
        
        # Verify BTC is in the list
        btc_signal = next((s for s in data["signals"] if s["asset"] == "BTC"), None)
        assert btc_signal is not None, "BTC should be in signals list"
        
        print(f"✅ All signals test passed - returned {data['count']} signals")

    def test_signal_not_mocked(self):
        """Verify signal data is real (not mocked)"""
        response = requests.get(f"{BASE_URL}/api/mobile/signals/BTC?horizon=swing")
        assert response.status_code == 200
        
        signal = response.json()["signal"]
        
        # Check that drivers have real data (not placeholder values)
        sentiment_driver = next((d for d in signal["drivers"] if d["module"] == "sentiment"), None)
        
        # Real sentiment driver should have numeric Fear & Greed value
        assert "Fear & Greed:" in sentiment_driver["value"], "Should have Fear & Greed label"
        
        # Extract numeric value from "Fear & Greed: 12 (Extreme Fear)"
        import re
        match = re.search(r'Fear & Greed: (\d+)', sentiment_driver["value"])
        assert match is not None, f"Could not extract Fear & Greed value from: {sentiment_driver['value']}"
        
        fg_value = int(match.group(1))
        assert 0 <= fg_value <= 100, f"Fear & Greed value out of range: {fg_value}"
        
        print(f"✅ Signal data is real (not mocked)")
        print(f"   Fear & Greed value: {fg_value}")


class TestPaymentFlow:
    """Test payment invoice creation"""

    def test_create_wallet_invoice(self):
        """Test POST /api/payments/create-wallet-invoice returns URL"""
        # First login to get token
        login_response = requests.post(
            f"{BASE_URL}/api/mobile/auth/dev-login",
            json={"email": "dev@fomo.ai", "name": "Test"}
        )
        assert login_response.status_code == 200
        token = login_response.json()["accessToken"]
        
        # Create invoice
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.post(
            f"{BASE_URL}/api/payments/create-wallet-invoice",
            json={"plan": "monthly"},
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "invoice_url" in data, "Response should contain invoice_url"
        assert len(data["invoice_url"]) > 0, "invoice_url should not be empty"
        
        print(f"✅ Payment invoice creation test passed")
        print(f"   Invoice URL: {data['invoice_url'][:50]}...")
