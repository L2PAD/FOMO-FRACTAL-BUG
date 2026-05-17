"""
Smart Money Radar + Brain API Tests
====================================
Sprint 1.2+ and 1.3 tests:
- Radar: signal_class, impact_score, signal_severity fields
- Radar: sort=impact parameter
- Brain: alpha_score, signal, drivers, components fields
- Brain: limit parameter
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestSmartMoneyRadarEnhancements:
    """Tests for Sprint 1.2+ Radar enhancements"""

    def test_radar_returns_signal_class_field(self):
        """Radar events should have signal_class (wallet/market/cluster)"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/radar?chainId=1&window=24h&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        events = data.get("events", [])
        assert len(events) > 0, "Expected at least one radar event"
        
        for event in events:
            assert "signal_class" in event, f"Event missing signal_class: {event}"
            assert event["signal_class"] in ["wallet", "market", "cluster"], \
                f"Invalid signal_class: {event['signal_class']}"

    def test_radar_returns_impact_score_field(self):
        """Radar events should have impact_score (0-100)"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/radar?chainId=1&window=24h&limit=10")
        assert response.status_code == 200
        data = response.json()
        
        events = data.get("events", [])
        for event in events:
            assert "impact_score" in event, f"Event missing impact_score: {event}"
            assert 0 <= event["impact_score"] <= 100, \
                f"impact_score out of range: {event['impact_score']}"

    def test_radar_returns_signal_severity_field(self):
        """Radar events should have signal_severity (LOW/MEDIUM/HIGH/CRITICAL)"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/radar?chainId=1&window=24h&limit=10")
        assert response.status_code == 200
        data = response.json()
        
        events = data.get("events", [])
        for event in events:
            assert "signal_severity" in event, f"Event missing signal_severity: {event}"
            assert event["signal_severity"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"], \
                f"Invalid signal_severity: {event['signal_severity']}"

    def test_radar_sort_by_impact_works(self):
        """Radar sort=impact should sort events by impact_score descending"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/radar?chainId=1&window=24h&sort=impact&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("meta", {}).get("sort") == "impact"
        
        events = data.get("events", [])
        if len(events) > 1:
            impact_scores = [e["impact_score"] for e in events]
            assert impact_scores == sorted(impact_scores, reverse=True), \
                f"Events not sorted by impact descending: {impact_scores}"

    def test_radar_signal_class_market_for_large_cluster(self):
        """Cluster with >= 20 wallets should have signal_class='market'"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/radar?chainId=1&window=24h&limit=20")
        assert response.status_code == 200
        data = response.json()
        
        events = data.get("events", [])
        market_events = [e for e in events if e.get("signal_class") == "market"]
        cluster_events = [e for e in events if e.get("signal_class") == "cluster"]
        
        # Verify market class events have >= 20 wallets
        for event in market_events:
            if event.get("event_type") == "cluster_activity":
                assert event.get("cluster_wallets", 0) >= 20, \
                    f"Market signal_class should have >= 20 wallets: {event}"
        
        # Verify cluster class events have < 20 wallets
        for event in cluster_events:
            if event.get("event_type") == "cluster_activity":
                assert event.get("cluster_wallets", 0) < 20, \
                    f"Cluster signal_class should have < 20 wallets: {event}"


class TestSmartMoneyBrainEndpoint:
    """Tests for Sprint 1.3 Brain endpoint"""

    def test_brain_endpoint_returns_ok(self):
        """Brain endpoint should return ok=true"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/brain?chainId=1&window=24h&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "signals" in data
        assert "meta" in data

    def test_brain_returns_alpha_score_field(self):
        """Brain signals should have alpha_score (0-100)"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/brain?chainId=1&window=24h&limit=10")
        assert response.status_code == 200
        data = response.json()
        
        signals = data.get("signals", [])
        assert len(signals) > 0, "Expected at least one brain signal"
        
        for signal in signals:
            assert "alpha_score" in signal, f"Signal missing alpha_score: {signal}"
            assert 0 <= signal["alpha_score"] <= 100, \
                f"alpha_score out of range: {signal['alpha_score']}"

    def test_brain_returns_signal_field(self):
        """Brain signals should have signal (strong_bullish/bullish/neutral/bearish/strong_bearish)"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/brain?chainId=1&window=24h&limit=10")
        assert response.status_code == 200
        data = response.json()
        
        signals = data.get("signals", [])
        valid_signals = ["strong_bullish", "bullish", "neutral", "bearish", "strong_bearish"]
        
        for signal in signals:
            assert "signal" in signal, f"Signal missing signal field: {signal}"
            assert signal["signal"] in valid_signals, \
                f"Invalid signal value: {signal['signal']}"

    def test_brain_returns_drivers_field(self):
        """Brain signals should have drivers array"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/brain?chainId=1&window=24h&limit=10")
        assert response.status_code == 200
        data = response.json()
        
        signals = data.get("signals", [])
        for signal in signals:
            assert "drivers" in signal, f"Signal missing drivers: {signal}"
            assert isinstance(signal["drivers"], list), "drivers should be a list"

    def test_brain_returns_components_field(self):
        """Brain signals should have components object with breakdown"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/brain?chainId=1&window=24h&limit=10")
        assert response.status_code == 200
        data = response.json()
        
        signals = data.get("signals", [])
        expected_components = ["wallet", "timing", "flow", "cluster", "pattern"]
        
        for signal in signals:
            assert "components" in signal, f"Signal missing components: {signal}"
            components = signal["components"]
            for comp in expected_components:
                assert comp in components, f"components missing {comp}: {components}"

    def test_brain_limit_parameter_works(self):
        """Brain limit parameter should restrict results"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/brain?chainId=1&window=24h&limit=3")
        assert response.status_code == 200
        data = response.json()
        
        signals = data.get("signals", [])
        assert len(signals) <= 3, f"Expected <= 3 signals, got {len(signals)}"

    def test_brain_signal_thresholds_correct(self):
        """Verify alpha_score to signal mapping is correct"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/brain?chainId=1&window=24h&limit=10")
        assert response.status_code == 200
        data = response.json()
        
        signals = data.get("signals", [])
        for s in signals:
            alpha = s["alpha_score"]
            signal = s["signal"]
            
            if alpha >= 75:
                assert signal == "strong_bullish", f"alpha {alpha} should be strong_bullish, got {signal}"
            elif alpha >= 60:
                assert signal == "bullish", f"alpha {alpha} should be bullish, got {signal}"
            elif alpha >= 40:
                assert signal == "neutral", f"alpha {alpha} should be neutral, got {signal}"
            elif alpha >= 25:
                assert signal == "bearish", f"alpha {alpha} should be bearish, got {signal}"
            else:
                assert signal == "strong_bearish", f"alpha {alpha} should be strong_bearish, got {signal}"

    def test_brain_returns_net_flow_and_wallet_count(self):
        """Brain signals should have net_flow_usd and wallet_count"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/brain?chainId=1&window=24h&limit=10")
        assert response.status_code == 200
        data = response.json()
        
        signals = data.get("signals", [])
        for signal in signals:
            assert "net_flow_usd" in signal, f"Signal missing net_flow_usd: {signal}"
            assert "wallet_count" in signal, f"Signal missing wallet_count: {signal}"
            assert "avg_timing" in signal, f"Signal missing avg_timing: {signal}"


class TestRadarExistingFunctionality:
    """Verify existing radar functionality still works"""

    def test_radar_sort_by_confidence(self):
        """Radar sort=confidence still works"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/radar?chainId=1&window=24h&sort=confidence&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("meta", {}).get("sort") == "confidence"

    def test_radar_sort_by_net_flow(self):
        """Radar sort=net_flow still works"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/radar?chainId=1&window=24h&sort=net_flow&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("meta", {}).get("sort") == "net_flow"

    def test_radar_sort_by_recency(self):
        """Radar sort=recency still works"""
        response = requests.get(f"{BASE_URL}/api/onchain/smart-money/radar?chainId=1&window=24h&sort=recency&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("meta", {}).get("sort") == "recency"

    def test_radar_different_windows(self):
        """Radar works with different time windows"""
        for window in ["24h", "7d", "30d"]:
            response = requests.get(f"{BASE_URL}/api/onchain/smart-money/radar?chainId=1&window={window}&limit=5")
            assert response.status_code == 200, f"Failed for window {window}"
            data = response.json()
            assert data.get("ok") is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
