"""
Phase 5 Pre-Signal Engine Tests
================================
Tests for early signal detection, velocity anomalies, triple confluence,
symbol resolution, and non-crypto entity filtering.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestEarlySignalsEndpoint:
    """Tests for GET /api/v4/sentiment/early-signals"""

    def test_early_signals_returns_ok(self):
        """Early signals endpoint returns ok=true"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/early-signals")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print("PASS: early-signals returns ok=true")

    def test_early_signals_has_required_structure(self):
        """Early signals response has earlySignals, confluences, totalDetected"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/early-signals")
        data = response.json()["data"]
        
        assert "earlySignals" in data, "Missing earlySignals array"
        assert "confluences" in data, "Missing confluences array"
        assert "totalDetected" in data, "Missing totalDetected count"
        assert "tripleConfluenceCount" in data, "Missing tripleConfluenceCount"
        assert "scanTime" in data, "Missing scanTime"
        print(f"PASS: Structure verified - {data['totalDetected']} signals, {data['tripleConfluenceCount']} confluences")

    def test_early_signal_has_required_fields(self):
        """Each early signal has anomalyLevel, strength, reliability, velocityDisplay, exchangeMentions, escalated"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/early-signals")
        signals = response.json()["data"]["earlySignals"]
        
        if not signals:
            pytest.skip("No early signals available for testing")
        
        required_fields = [
            "id", "entityId", "symbol", "name", "signalType",
            "anomalyLevel", "strength", "reliability", "velocityDisplay",
            "exchangeMentions", "escalated"
        ]
        
        for sig in signals[:5]:  # Check first 5
            for field in required_fields:
                assert field in sig, f"Missing field '{field}' in signal {sig.get('symbol', 'unknown')}"
        
        print(f"PASS: All {len(required_fields)} required fields present in early signals")

    def test_anomaly_levels_are_valid(self):
        """Anomaly levels are LOW, MED, or HIGH"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/early-signals")
        signals = response.json()["data"]["earlySignals"]
        
        valid_levels = {"LOW", "MED", "HIGH"}
        for sig in signals:
            level = sig.get("anomalyLevel")
            assert level in valid_levels, f"Invalid anomaly level: {level}"
        
        print(f"PASS: All {len(signals)} signals have valid anomaly levels")

    def test_anomaly_level_thresholds(self):
        """Verify anomaly level thresholds: LOW=x2, MED=x3, HIGH=x5+"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/early-signals")
        signals = response.json()["data"]["earlySignals"]
        
        for sig in signals:
            ratio = sig.get("velocityRatio", 0)
            level = sig.get("anomalyLevel")
            
            if level == "HIGH":
                assert ratio >= 5, f"HIGH anomaly should have ratio >= 5, got {ratio}"
            elif level == "MED":
                assert 3 <= ratio < 5, f"MED anomaly should have 3 <= ratio < 5, got {ratio}"
            elif level == "LOW":
                assert 2 <= ratio < 3, f"LOW anomaly should have 2 <= ratio < 3, got {ratio}"
        
        print(f"PASS: Anomaly level thresholds verified for {len(signals)} signals")


class TestSymbolResolution:
    """Tests for proper symbol resolution (BTC not bitcoin, ETH not ethereum)"""

    def test_symbols_are_uppercase_tickers(self):
        """Symbols should be uppercase tickers (BTC, ETH, SOL) not entity names"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/early-signals")
        signals = response.json()["data"]["earlySignals"]
        
        # Entity names that should NOT be used as symbols (should be mapped to tickers)
        entity_names_not_symbols = {"bitcoin", "ethereum", "solana", "arbitrum", "polygon", "chainlink", "optimism"}
        
        for sig in signals:
            symbol = sig.get("symbol", "")
            entity_id = sig.get("entityId", "")
            
            # Symbol should be uppercase
            assert symbol == symbol.upper(), f"Symbol should be uppercase: {symbol}"
            # Common entity names should be mapped to tickers (bitcoin→BTC, not BITCOIN)
            if entity_id.lower() in entity_names_not_symbols:
                assert symbol.lower() != entity_id.lower(), f"Entity '{entity_id}' should map to ticker, not '{symbol}'"
            # Symbol should be short (2-10 chars)
            assert 2 <= len(symbol) <= 10, f"Symbol length should be 2-10: {symbol}"
        
        print(f"PASS: Symbol resolution verified for {len(signals)} signals")

    def test_common_symbols_resolved_correctly(self):
        """Common entities resolve to correct symbols"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/early-signals")
        signals = response.json()["data"]["earlySignals"]
        
        expected_mappings = {
            "bitcoin": "BTC",
            "ethereum": "ETH",
            "solana": "SOL",
            "arbitrum": "ARB",
            "polygon": "MATIC",
            "chainlink": "LINK",
            "optimism": "OP",
        }
        
        for sig in signals:
            entity_id = sig.get("entityId", "").lower()
            symbol = sig.get("symbol", "")
            
            if entity_id in expected_mappings:
                expected = expected_mappings[entity_id]
                assert symbol == expected, f"Entity '{entity_id}' should map to '{expected}', got '{symbol}'"
        
        print("PASS: Common symbol mappings verified")


class TestNonCryptoFiltering:
    """Tests for non-crypto entity filtering (a16z, marc-andreessen, etc.)"""

    def test_no_vc_entities_in_signals(self):
        """VC entities (a16z, paradigm, sequoia) should be filtered out"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/early-signals")
        signals = response.json()["data"]["earlySignals"]
        
        skip_entities = {"a16z", "marc-andreessen", "paradigm", "sequoia", "multicoin"}
        
        for sig in signals:
            entity_id = sig.get("entityId", "").lower()
            assert entity_id not in skip_entities, f"VC entity should be filtered: {entity_id}"
        
        print(f"PASS: No VC entities in {len(signals)} signals")

    def test_no_exchange_entities_in_signals(self):
        """Exchange entities (binance, coinbase) should be filtered out"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/early-signals")
        signals = response.json()["data"]["earlySignals"]
        
        skip_entities = {"coinbase", "binance", "binance-labs", "binance-cex", "cz_binance", "brian_armstrong"}
        
        for sig in signals:
            entity_id = sig.get("entityId", "").lower()
            assert entity_id not in skip_entities, f"Exchange entity should be filtered: {entity_id}"
        
        print(f"PASS: No exchange entities in {len(signals)} signals")


class TestTripleConfluence:
    """Tests for Triple Confluence (listing + anomaly + sentiment)"""

    def test_confluences_array_exists(self):
        """Confluences array exists in response"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/early-signals")
        data = response.json()["data"]
        
        assert "confluences" in data
        assert isinstance(data["confluences"], list)
        print(f"PASS: Confluences array exists with {len(data['confluences'])} items")

    def test_confluence_has_required_fields(self):
        """Each confluence has listing, anomaly, sentiment details"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/early-signals")
        confluences = response.json()["data"]["confluences"]
        
        if not confluences:
            pytest.skip("No confluences available for testing")
        
        for conf in confluences:
            assert "token" in conf, "Missing token"
            assert "listing" in conf, "Missing listing details"
            assert "anomaly" in conf, "Missing anomaly details"
            assert "sentiment" in conf, "Missing sentiment details"
            assert "rarity" in conf, "Missing rarity label"
            
            # Check nested fields
            assert "exchange" in conf["listing"], "Missing listing.exchange"
            assert "level" in conf["anomaly"], "Missing anomaly.level"
            assert "value" in conf["sentiment"], "Missing sentiment.value"
        
        print(f"PASS: Confluence structure verified for {len(confluences)} items")

    def test_confluence_rarity_label(self):
        """Confluence has 'Top 0.1% signal' rarity label"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/early-signals")
        confluences = response.json()["data"]["confluences"]
        
        if not confluences:
            pytest.skip("No confluences available for testing")
        
        for conf in confluences:
            rarity = conf.get("rarity", "")
            assert "Top 0.1%" in rarity, f"Expected 'Top 0.1%' in rarity, got: {rarity}"
        
        print("PASS: Confluence rarity labels verified")


class TestEscalationTracking:
    """Tests for escalation tracking (early → listing)"""

    def test_escalated_field_exists(self):
        """Each signal has escalated boolean field"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/early-signals")
        signals = response.json()["data"]["earlySignals"]
        
        for sig in signals:
            assert "escalated" in sig, f"Missing escalated field in {sig.get('symbol')}"
            assert isinstance(sig["escalated"], bool), "escalated should be boolean"
        
        print(f"PASS: Escalated field present in all {len(signals)} signals")

    def test_escalated_signals_have_listing(self):
        """Escalated signals should have corresponding listing"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/early-signals")
        signals = response.json()["data"]["earlySignals"]
        
        # Get listings for cross-reference
        listings_resp = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        listings_data = listings_resp.json()["data"]
        listing_tokens = set()
        for l in listings_data.get("confirmed", []) + listings_data.get("potential", []):
            listing_tokens.add(l.get("token"))
        
        for sig in signals:
            if sig.get("escalated"):
                token = sig.get("symbol")
                assert token in listing_tokens, f"Escalated signal {token} should have listing"
        
        print("PASS: Escalated signals verified against listings")


class TestExchangeMentionDetection:
    """Tests for exchange mention detection with weighted scoring"""

    def test_exchange_mentions_is_array(self):
        """exchangeMentions is an array"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/early-signals")
        signals = response.json()["data"]["earlySignals"]
        
        for sig in signals:
            mentions = sig.get("exchangeMentions")
            assert isinstance(mentions, list), f"exchangeMentions should be array, got {type(mentions)}"
        
        print(f"PASS: exchangeMentions is array in all {len(signals)} signals")

    def test_exchange_mentions_are_valid_names(self):
        """Exchange mentions are valid exchange names"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/early-signals")
        signals = response.json()["data"]["earlySignals"]
        
        valid_exchanges = {"Binance", "Coinbase", "Bybit", "OKX", "KuCoin", "Gate.io", "Upbit", "Kraken", "Bitget", "MEXC", "HTX"}
        
        for sig in signals:
            for mention in sig.get("exchangeMentions", []):
                assert mention in valid_exchanges, f"Invalid exchange mention: {mention}"
        
        print("PASS: All exchange mentions are valid")


class TestStrengthAndReliability:
    """Tests for Strength and Reliability separate fields"""

    def test_strength_field_exists(self):
        """Each signal has strength field (HIGH/MED/LOW)"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/early-signals")
        signals = response.json()["data"]["earlySignals"]
        
        valid_values = {"HIGH", "MED", "LOW"}
        for sig in signals:
            strength = sig.get("strength")
            assert strength in valid_values, f"Invalid strength: {strength}"
        
        print(f"PASS: Strength field verified in all {len(signals)} signals")

    def test_reliability_field_exists(self):
        """Each signal has reliability field (HIGH/MED/LOW)"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/early-signals")
        signals = response.json()["data"]["earlySignals"]
        
        valid_values = {"HIGH", "MED", "LOW"}
        for sig in signals:
            reliability = sig.get("reliability")
            assert reliability in valid_values, f"Invalid reliability: {reliability}"
        
        print(f"PASS: Reliability field verified in all {len(signals)} signals")


class TestVelocityDisplay:
    """Tests for velocity display format"""

    def test_velocity_display_format(self):
        """velocityDisplay is in '+N% vs baseline' format"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/early-signals")
        signals = response.json()["data"]["earlySignals"]
        
        for sig in signals:
            vel = sig.get("velocityDisplay", "")
            assert "% vs baseline" in vel, f"Invalid velocity display format: {vel}"
            assert vel.startswith("+"), f"Velocity display should start with +: {vel}"
        
        print(f"PASS: Velocity display format verified in all {len(signals)} signals")


class TestPhase1To4Regression:
    """Regression tests for Phase 1-4 features"""

    def test_listings_endpoint_still_works(self):
        """Listings endpoint returns data"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/listings")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print("PASS: Listings endpoint still works")

    def test_top_signals_endpoint_still_works(self):
        """Top signals endpoint returns data"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print("PASS: Top signals endpoint still works")

    def test_correlations_endpoint_still_works(self):
        """Correlations endpoint returns data"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print("PASS: Correlations endpoint still works")

    def test_no_buy_sell_wait_in_early_signals(self):
        """No BUY/SELL/WAIT in early signals response"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/early-signals")
        text = response.text.upper()
        
        assert '"BUY"' not in text, "Found BUY in response"
        assert '"SELL"' not in text, "Found SELL in response"
        assert '"WAIT"' not in text, "Found WAIT in response"
        print("PASS: No BUY/SELL/WAIT in early signals")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
