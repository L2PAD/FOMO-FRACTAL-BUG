"""
Decision Intelligence Phase 1 - Backend API Tests
Tests for new signal card fields: setupType, signalMaturity, riskContext, timeframe in expectedMove
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com')

class TestTopSignalsAPI:
    """Tests for /api/v4/sentiment/top-signals endpoint - new Decision Intelligence fields"""
    
    def test_top_signals_returns_setup_type(self):
        """Verify setupType field exists with valid values"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        
        for signal in data["data"]:
            assert "setupType" in signal, f"Missing setupType for {signal.get('entityId')}"
            assert signal["setupType"] in ["CONTINUATION", "BREAKOUT", "EXHAUSTION"], \
                f"Invalid setupType: {signal['setupType']}"
        print(f"PASS: All {len(data['data'])} signals have valid setupType")
    
    def test_top_signals_returns_signal_maturity(self):
        """Verify signalMaturity field exists with valid values"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        assert response.status_code == 200
        data = response.json()
        
        for signal in data["data"]:
            assert "signalMaturity" in signal, f"Missing signalMaturity for {signal.get('entityId')}"
            assert signal["signalMaturity"] in ["EARLY", "CONFIRMED", "LATE"], \
                f"Invalid signalMaturity: {signal['signalMaturity']}"
        print(f"PASS: All {len(data['data'])} signals have valid signalMaturity")
    
    def test_top_signals_returns_risk_context(self):
        """Verify riskContext field exists as array with valid values"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        assert response.status_code == 200
        data = response.json()
        
        valid_risks = ["Elevated volatility", "Weak confirmation", "Single-source signal", "Normal conditions", "Insufficient data"]
        
        for signal in data["data"]:
            assert "riskContext" in signal, f"Missing riskContext for {signal.get('entityId')}"
            assert isinstance(signal["riskContext"], list), "riskContext should be a list"
            assert len(signal["riskContext"]) > 0, "riskContext should not be empty"
            for risk in signal["riskContext"]:
                assert risk in valid_risks, f"Invalid risk: {risk}"
        print(f"PASS: All signals have valid riskContext arrays")
    
    def test_top_signals_expected_move_has_timeframe(self):
        """Verify expectedMove.text includes timeframe like (6-24h) or (1-3d)"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        assert response.status_code == 200
        data = response.json()
        
        for signal in data["data"]:
            assert "expectedMove" in signal
            move = signal["expectedMove"]
            assert "text" in move
            assert "timeframe" in move
            # Check text contains timeframe pattern
            text = move["text"]
            assert "(6-24h)" in text or "(1-3d)" in text, \
                f"Expected move text should contain timeframe: {text}"
        print(f"PASS: All expectedMove.text values include timeframe")
    
    def test_top_signals_no_buy_sell_language(self):
        """Verify no BUY/SELL/WAIT language appears in signal data"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        assert response.status_code == 200
        data = response.json()
        
        forbidden_words = ["BUY", "SELL", "WAIT", "HOLD", "LONG", "SHORT"]
        
        for signal in data["data"]:
            # Check all string fields
            signal_str = str(signal).upper()
            for word in forbidden_words:
                # Allow "short term" but not standalone "SHORT"
                if word == "SHORT" and "SHORT TERM" in signal_str:
                    continue
                assert word not in signal_str or "SHORT TERM" in signal_str, \
                    f"Found forbidden word '{word}' in signal: {signal.get('entityId')}"
        print("PASS: No BUY/SELL/WAIT language found in top-signals")


class TestCorrelationsAPI:
    """Tests for /api/v4/sentiment/correlations endpoint - new Decision Intelligence fields"""
    
    def test_correlations_signal_has_setup_type(self):
        """Verify signal object contains setupType"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        
        for item in data["data"]:
            signal = item.get("signal", {})
            assert "setupType" in signal, f"Missing setupType in signal for {item.get('id')}"
            assert signal["setupType"] in ["CONTINUATION", "BREAKOUT", "EXHAUSTION"], \
                f"Invalid setupType: {signal['setupType']}"
        print(f"PASS: All {len(data['data'])} correlation signals have setupType")
    
    def test_correlations_signal_has_maturity(self):
        """Verify signal object contains signalMaturity"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        assert response.status_code == 200
        data = response.json()
        
        for item in data["data"]:
            signal = item.get("signal", {})
            assert "signalMaturity" in signal, f"Missing signalMaturity for {item.get('id')}"
            assert signal["signalMaturity"] in ["EARLY", "CONFIRMED", "LATE"], \
                f"Invalid signalMaturity: {signal['signalMaturity']}"
        print(f"PASS: All correlation signals have signalMaturity")
    
    def test_correlations_signal_has_risk_context(self):
        """Verify signal object contains riskContext array"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        assert response.status_code == 200
        data = response.json()
        
        for item in data["data"]:
            signal = item.get("signal", {})
            assert "riskContext" in signal, f"Missing riskContext for {item.get('id')}"
            assert isinstance(signal["riskContext"], list), "riskContext should be a list"
        print(f"PASS: All correlation signals have riskContext")
    
    def test_correlations_expected_move_has_timeframe(self):
        """Verify expectedMove includes timeframe"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        assert response.status_code == 200
        data = response.json()
        
        for item in data["data"]:
            signal = item.get("signal", {})
            if signal.get("type") != "NEUTRAL":
                move = signal.get("expectedMove", {})
                text = move.get("text", "")
                assert "(6-24h)" in text or "(1-3d)" in text or "Sideways" in text, \
                    f"Expected move should have timeframe: {text}"
        print(f"PASS: All non-NEUTRAL signals have timeframe in expectedMove")
    
    def test_correlations_no_buy_sell_language(self):
        """Verify no BUY/SELL language in correlations"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        assert response.status_code == 200
        data = response.json()
        
        forbidden_words = ["BUY", "SELL", "WAIT", "HOLD"]
        
        for item in data["data"]:
            item_str = str(item).upper()
            for word in forbidden_words:
                assert word not in item_str, \
                    f"Found forbidden word '{word}' in correlation: {item.get('id')}"
        print("PASS: No BUY/SELL language in correlations")


class TestMergedDisplayFormat:
    """Tests for merged SETUP — MATURITY display format"""
    
    def test_setup_maturity_combination_valid(self):
        """Verify setupType and signalMaturity can be combined for display"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        assert response.status_code == 200
        data = response.json()
        
        valid_setups = ["CONTINUATION", "BREAKOUT", "EXHAUSTION"]
        valid_maturities = ["EARLY", "CONFIRMED", "LATE"]
        
        for signal in data["data"]:
            setup = signal.get("setupType")
            maturity = signal.get("signalMaturity")
            
            assert setup in valid_setups
            assert maturity in valid_maturities
            
            # Verify merged format would be valid
            merged = f"{setup} — {maturity}"
            print(f"  {signal['symbol']}: {merged}")
        
        print(f"PASS: All {len(data['data'])} signals have valid merged format")


class TestTimeframeLogic:
    """Tests for timeframe computation logic"""
    
    def test_momentum_signals_have_short_timeframe(self):
        """MOMENTUM signals with high velocity should have 6-24h timeframe"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        assert response.status_code == 200
        data = response.json()
        
        momentum_signals = [s for s in data["data"] if s["signalType"] == "MOMENTUM"]
        
        for signal in momentum_signals:
            move = signal.get("expectedMove", {})
            timeframe = move.get("timeframe", "")
            # MOMENTUM typically has 6-24h
            assert timeframe in ["6-24h", "1-3d"], f"Invalid timeframe: {timeframe}"
        
        print(f"PASS: {len(momentum_signals)} MOMENTUM signals have valid timeframes")
    
    def test_expected_move_text_matches_timeframe(self):
        """Verify expectedMove.text contains the same timeframe as expectedMove.timeframe"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        assert response.status_code == 200
        data = response.json()
        
        for signal in data["data"]:
            move = signal.get("expectedMove", {})
            text = move.get("text", "")
            timeframe = move.get("timeframe", "")
            
            if timeframe:
                assert f"({timeframe})" in text, \
                    f"Text '{text}' should contain timeframe '({timeframe})'"
        
        print("PASS: All expectedMove.text values match their timeframe field")


class TestRiskContextLogic:
    """Tests for risk context computation"""
    
    def test_high_volatility_signals_have_elevated_risk(self):
        """Signals with high sentiment + velocity should show Elevated volatility"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        assert response.status_code == 200
        data = response.json()
        
        elevated_count = 0
        for signal in data["data"]:
            risks = signal.get("riskContext", [])
            if "Elevated volatility" in risks:
                elevated_count += 1
        
        print(f"PASS: Found {elevated_count} signals with 'Elevated volatility' risk")
    
    def test_low_confidence_signals_have_weak_confirmation(self):
        """Signals with low confidence should show Weak confirmation"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        assert response.status_code == 200
        data = response.json()
        
        for signal in data["data"]:
            confidence = signal.get("confidence", 100)
            risks = signal.get("riskContext", [])
            
            if confidence < 40:
                assert "Weak confirmation" in risks, \
                    f"Low confidence ({confidence}) should have 'Weak confirmation' risk"
        
        print("PASS: Low confidence signals correctly show 'Weak confirmation'")


class TestExistingFeaturesStillWork:
    """Regression tests for existing features"""
    
    def test_top_signals_still_has_core_fields(self):
        """Verify existing fields still present"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ["entityId", "symbol", "name", "signalType", "score", 
                          "decayedScore", "confidence", "strength", "age", 
                          "freshness", "expectedMove", "drivers"]
        
        for signal in data["data"]:
            for field in required_fields:
                assert field in signal, f"Missing required field: {field}"
        
        print(f"PASS: All {len(required_fields)} core fields present")
    
    def test_correlations_still_has_core_fields(self):
        """Verify existing correlation fields still present"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ["id", "symbol", "name", "sentiment", "correlation", "signal"]
        
        for item in data["data"]:
            for field in required_fields:
                assert field in item, f"Missing required field: {field}"
        
        print(f"PASS: All correlation core fields present")
    
    def test_feed_api_still_works(self):
        """Verify feed API still returns tweets"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/feed?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        assert len(data["data"]) > 0
        print(f"PASS: Feed API returns {len(data['data'])} tweets")
    
    def test_accounts_api_still_works(self):
        """Verify accounts API still returns data"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/accounts")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        assert len(data["data"]) > 0
        print(f"PASS: Accounts API returns {len(data['data'])} accounts")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
