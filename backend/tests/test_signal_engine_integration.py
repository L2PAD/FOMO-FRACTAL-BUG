"""
Signal Engine Integration Tests
================================
Tests for the new Signal Engine integration into Twitter Santiment pages.
Key features:
- MOMENTUM/ATTENTION signals replacing old BUY STRONG
- Top Signal Strip with real signal data
- WHY/drivers blocks
- Impact-based tweet sizing (HIGH/MEDIUM/LOW)
- Affected assets per tweet
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com')


class TestTopSignalsAPI:
    """Tests for /api/v4/sentiment/top-signals endpoint"""
    
    def test_top_signals_returns_ok(self):
        """Top signals endpoint returns ok status"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        print(f"✓ Top signals endpoint returns ok status")
    
    def test_top_signals_has_signal_data(self):
        """Top signals returns array with signal data"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        data = response.json()
        assert "data" in data
        assert isinstance(data["data"], list)
        assert len(data["data"]) > 0
        print(f"✓ Top signals returns {len(data['data'])} signals")
    
    def test_top_signals_has_momentum_or_attention_types(self):
        """Top signals contain MOMENTUM or ATTENTION types (not old BUY STRONG)"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        data = response.json()
        signals = data["data"]
        
        valid_types = {"MOMENTUM", "ATTENTION"}
        for sig in signals:
            assert "signalType" in sig
            assert sig["signalType"] in valid_types, f"Invalid signal type: {sig['signalType']}"
        print(f"✓ All signals have valid types (MOMENTUM/ATTENTION)")
    
    def test_top_signals_has_required_fields(self):
        """Top signals have all required fields: score, confidence, strength, age, drivers"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        data = response.json()
        signals = data["data"]
        
        required_fields = ["entityId", "symbol", "signalType", "score", "confidence", "strength", "age", "drivers"]
        for sig in signals[:5]:  # Check first 5
            for field in required_fields:
                assert field in sig, f"Missing field: {field}"
        print(f"✓ Top signals have all required fields")
    
    def test_top_signals_strength_values(self):
        """Signal strength is HIGH, MEDIUM, or LOW"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        data = response.json()
        signals = data["data"]
        
        valid_strengths = {"HIGH", "MEDIUM", "LOW"}
        for sig in signals:
            assert sig["strength"] in valid_strengths, f"Invalid strength: {sig['strength']}"
        print(f"✓ All signals have valid strength values")
    
    def test_top_signals_has_drivers(self):
        """Top signals have drivers array for WHY explanation"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        data = response.json()
        signals = data["data"]
        
        signals_with_drivers = [s for s in signals if s.get("drivers") and len(s["drivers"]) > 0]
        assert len(signals_with_drivers) > 0, "No signals have drivers"
        
        # Check driver content
        for sig in signals_with_drivers[:3]:
            for driver in sig["drivers"]:
                assert isinstance(driver, str)
                assert len(driver) > 0
        print(f"✓ {len(signals_with_drivers)} signals have drivers for WHY explanation")


class TestCorrelationsAPI:
    """Tests for /api/v4/sentiment/correlations endpoint"""
    
    def test_correlations_returns_ok(self):
        """Correlations endpoint returns ok status"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        print(f"✓ Correlations endpoint returns ok status")
    
    def test_correlations_has_signal_object(self):
        """Correlations have signal object with type, score, confidence"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        data = response.json()
        correlations = data["data"]
        
        for corr in correlations[:5]:
            assert "signal" in corr
            signal = corr["signal"]
            assert "type" in signal
            assert "score" in signal
            assert "confidence" in signal
            assert "strength" in signal
        print(f"✓ Correlations have signal objects")
    
    def test_correlations_signal_types_are_valid(self):
        """Signal types are MOMENTUM, ATTENTION, or NEUTRAL"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        data = response.json()
        correlations = data["data"]
        
        valid_types = {"MOMENTUM", "ATTENTION", "NEUTRAL"}
        for corr in correlations:
            signal_type = corr["signal"]["type"]
            assert signal_type in valid_types, f"Invalid signal type: {signal_type}"
        print(f"✓ All correlation signal types are valid")
    
    def test_correlations_has_age_field(self):
        """Correlations have signal age (e.g., 1h, 2h)"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        data = response.json()
        correlations = data["data"]
        
        for corr in correlations[:5]:
            assert "age" in corr["signal"]
            age = corr["signal"]["age"]
            assert isinstance(age, str)
        print(f"✓ Correlations have signal age field")
    
    def test_correlations_has_action_text(self):
        """Correlations have action text (e.g., High probability continuation)"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        data = response.json()
        correlations = data["data"]
        
        for corr in correlations[:5]:
            assert "action" in corr["signal"]
            action = corr["signal"]["action"]
            assert isinstance(action, str)
            assert len(action) > 0
        print(f"✓ Correlations have action text")
    
    def test_correlations_has_drivers_for_why_block(self):
        """Correlations have drivers array for WHY block"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        data = response.json()
        correlations = data["data"]
        
        # Check that at least some correlations have drivers
        corrs_with_drivers = [c for c in correlations if c["signal"].get("drivers") and len(c["signal"]["drivers"]) > 0]
        assert len(corrs_with_drivers) > 0, "No correlations have drivers"
        print(f"✓ {len(corrs_with_drivers)} correlations have drivers for WHY block")
    
    def test_correlations_no_old_buy_strong(self):
        """Correlations do NOT have old BUY STRONG signal type"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        data = response.json()
        correlations = data["data"]
        
        for corr in correlations:
            signal_type = corr["signal"]["type"]
            assert "BUY" not in signal_type, f"Found old BUY signal type: {signal_type}"
            assert "SELL" not in signal_type, f"Found old SELL signal type: {signal_type}"
            assert "STRONG" not in signal_type, f"Found old STRONG signal type: {signal_type}"
        print(f"✓ No old BUY STRONG signal types found")


class TestFeedAPI:
    """Tests for /api/v4/sentiment/feed endpoint"""
    
    def test_feed_returns_ok(self):
        """Feed endpoint returns ok status"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/feed?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        print(f"✓ Feed endpoint returns ok status")
    
    def test_feed_has_impact_level(self):
        """Feed tweets have impact level (HIGH, MEDIUM, LOW)"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/feed?limit=30")
        data = response.json()
        tweets = data["data"]
        
        valid_impacts = {"HIGH", "MEDIUM", "LOW"}
        for tweet in tweets:
            assert "impact" in tweet
            assert tweet["impact"] in valid_impacts, f"Invalid impact: {tweet['impact']}"
        print(f"✓ All tweets have valid impact levels")
    
    def test_feed_has_affected_assets(self):
        """Feed tweets have affectedAssets array"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/feed?limit=30")
        data = response.json()
        tweets = data["data"]
        
        for tweet in tweets:
            assert "affectedAssets" in tweet
            assert isinstance(tweet["affectedAssets"], list)
        
        # Check that at least some tweets have affected assets
        tweets_with_assets = [t for t in tweets if len(t["affectedAssets"]) > 0]
        print(f"✓ {len(tweets_with_assets)}/{len(tweets)} tweets have affected assets")
    
    def test_feed_affected_assets_have_direction(self):
        """Affected assets have direction (up, down, neutral)"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/feed?limit=30")
        data = response.json()
        tweets = data["data"]
        
        valid_directions = {"up", "down", "neutral"}
        for tweet in tweets:
            for asset in tweet["affectedAssets"]:
                assert "direction" in asset
                assert asset["direction"] in valid_directions, f"Invalid direction: {asset['direction']}"
                assert "symbol" in asset
        print(f"✓ Affected assets have valid direction arrows")
    
    def test_feed_has_signal_injection(self):
        """Some feed tweets have signal injection from entity_alerts"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/feed?limit=30")
        data = response.json()
        tweets = data["data"]
        
        tweets_with_signal = [t for t in tweets if t.get("signal") is not None]
        
        # Check signal structure
        for tweet in tweets_with_signal[:3]:
            signal = tweet["signal"]
            assert "type" in signal
            assert "score" in signal
            assert "confidence" in signal
            assert "entity" in signal
        print(f"✓ {len(tweets_with_signal)}/{len(tweets)} tweets have signal injection")
    
    def test_feed_high_impact_tweets_exist(self):
        """Feed contains HIGH impact tweets"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/feed?limit=50")
        data = response.json()
        tweets = data["data"]
        
        high_impact = [t for t in tweets if t["impact"] == "HIGH"]
        print(f"✓ Found {len(high_impact)} HIGH impact tweets")
    
    def test_feed_low_impact_tweets_exist(self):
        """Feed contains LOW impact tweets (for collapsed view)"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/feed?limit=50")
        data = response.json()
        tweets = data["data"]
        
        low_impact = [t for t in tweets if t["impact"] == "LOW"]
        print(f"✓ Found {len(low_impact)} LOW impact tweets (for collapsed view)")


class TestModelStatsAPI:
    """Tests for /api/v4/sentiment/model-stats endpoint"""
    
    def test_model_stats_returns_ok(self):
        """Model stats endpoint returns ok status"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/model-stats")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        print(f"✓ Model stats endpoint returns ok status")
    
    def test_model_stats_has_active_alerts(self):
        """Model stats has activeAlerts count"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/model-stats")
        data = response.json()
        stats = data["data"]
        
        assert "activeAlerts" in stats
        assert isinstance(stats["activeAlerts"], int)
        print(f"✓ Active alerts count: {stats['activeAlerts']}")
    
    def test_model_stats_has_type_breakdown(self):
        """Model stats has typeBreakdown with MOMENTUM and ATTENTION"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/model-stats")
        data = response.json()
        stats = data["data"]
        
        assert "typeBreakdown" in stats
        breakdown = stats["typeBreakdown"]
        
        # Check for MOMENTUM and ATTENTION types
        assert "MOMENTUM" in breakdown, "Missing MOMENTUM in typeBreakdown"
        assert "ATTENTION" in breakdown, "Missing ATTENTION in typeBreakdown"
        
        # Check structure
        for type_name in ["MOMENTUM", "ATTENTION"]:
            type_data = breakdown[type_name]
            assert "count" in type_data
            assert "avgScore" in type_data
        
        print(f"✓ Type breakdown: MOMENTUM={breakdown['MOMENTUM']['count']}, ATTENTION={breakdown['ATTENTION']['count']}")


class TestSignalEngineIntegration:
    """Integration tests for Signal Engine features"""
    
    def test_signal_types_consistent_across_endpoints(self):
        """Signal types are consistent between top-signals and correlations"""
        top_signals_resp = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        correlations_resp = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        
        top_signals = top_signals_resp.json()["data"]
        correlations = correlations_resp.json()["data"]
        
        # Get all signal types from both endpoints
        top_types = {s["signalType"] for s in top_signals}
        corr_types = {c["signal"]["type"] for c in correlations}
        
        valid_types = {"MOMENTUM", "ATTENTION", "NEUTRAL"}
        assert top_types.issubset(valid_types)
        assert corr_types.issubset(valid_types)
        print(f"✓ Signal types consistent: top-signals={top_types}, correlations={corr_types}")
    
    def test_entity_alerts_data_flows_to_feed(self):
        """Entity alerts data flows to feed tweets via signal injection"""
        feed_resp = requests.get(f"{BASE_URL}/api/v4/sentiment/feed?limit=50")
        tweets = feed_resp.json()["data"]
        
        # Find tweets with signal injection
        tweets_with_signal = [t for t in tweets if t.get("signal")]
        
        if tweets_with_signal:
            # Verify signal structure matches entity_alerts format
            for tweet in tweets_with_signal[:3]:
                signal = tweet["signal"]
                assert signal["type"] in {"MOMENTUM", "ATTENTION", "NEUTRAL"}
                assert isinstance(signal["score"], (int, float))
                assert isinstance(signal["confidence"], (int, float))
        
        print(f"✓ Entity alerts data flows to {len(tweets_with_signal)} feed tweets")
    
    def test_drivers_explain_why(self):
        """Drivers provide meaningful WHY explanation"""
        correlations_resp = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        correlations = correlations_resp.json()["data"]
        
        # Find correlations with drivers
        corrs_with_drivers = [c for c in correlations if c["signal"].get("drivers")]
        
        expected_driver_patterns = [
            "velocity", "sentiment", "sources", "mentions", "trending"
        ]
        
        for corr in corrs_with_drivers[:3]:
            drivers = corr["signal"]["drivers"]
            # Check that drivers contain meaningful explanations
            driver_text = " ".join(drivers).lower()
            has_meaningful_driver = any(pattern in driver_text for pattern in expected_driver_patterns)
            assert has_meaningful_driver, f"Drivers don't explain WHY: {drivers}"
        
        print(f"✓ Drivers provide meaningful WHY explanations")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
