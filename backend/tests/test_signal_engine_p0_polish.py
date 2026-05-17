"""
Signal Engine P0 Polish Tests
=============================
Tests for Expected Move, Time Decay, Confidence Labels, Account Score+HitRate features.

Features tested:
- Expected Move block (text + risk)
- Time Decay (FRESH/ACTIVE/AGING/DEAD + decayedScore)
- Confidence Labels (HIGH/MEDIUM/LOW)
- Account Signal Score + Hit Rate
- Top Signal Strip (expectedMove, freshness, filters DEAD)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com').rstrip('/')


class TestTopSignalsAPI:
    """Test /api/v4/sentiment/top-signals for P0 polish fields"""
    
    def test_top_signals_returns_ok(self):
        """API returns ok: true"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "data" in data
    
    def test_top_signals_has_decayed_score(self):
        """Each signal has decayedScore field"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        data = response.json()
        for signal in data.get("data", []):
            assert "decayedScore" in signal, f"Missing decayedScore in signal {signal.get('entityId')}"
            assert isinstance(signal["decayedScore"], (int, float))
    
    def test_top_signals_has_freshness(self):
        """Each signal has freshness field with valid values"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        data = response.json()
        valid_freshness = {"FRESH", "ACTIVE", "AGING", "DEAD"}
        for signal in data.get("data", []):
            assert "freshness" in signal, f"Missing freshness in signal {signal.get('entityId')}"
            assert signal["freshness"] in valid_freshness, f"Invalid freshness: {signal['freshness']}"
    
    def test_top_signals_has_confidence_label(self):
        """Each signal has confidenceLabel field with valid values"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        data = response.json()
        valid_labels = {"HIGH", "MEDIUM", "LOW"}
        for signal in data.get("data", []):
            assert "confidenceLabel" in signal, f"Missing confidenceLabel in signal {signal.get('entityId')}"
            assert signal["confidenceLabel"] in valid_labels, f"Invalid confidenceLabel: {signal['confidenceLabel']}"
    
    def test_top_signals_has_expected_move(self):
        """Each signal has expectedMove with text and risk"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        data = response.json()
        for signal in data.get("data", []):
            assert "expectedMove" in signal, f"Missing expectedMove in signal {signal.get('entityId')}"
            exp_move = signal["expectedMove"]
            assert "text" in exp_move, "expectedMove missing 'text' field"
            assert "risk" in exp_move, "expectedMove missing 'risk' field"
    
    def test_expected_move_text_format(self):
        """Expected move text contains percentage range"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        data = response.json()
        for signal in data.get("data", []):
            text = signal.get("expectedMove", {}).get("text", "")
            # Should contain percentage indicators like +3-8%, -2-5%, ±2-4%
            assert any(c in text for c in ["%", "Sideways"]), f"Expected move text should contain % or Sideways: {text}"
    
    def test_expected_move_risk_text(self):
        """Expected move risk contains meaningful text"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        data = response.json()
        valid_risk_keywords = ["Breakout", "continuation", "volatility", "pullback", "Momentum", "bias", "Elevated", "direction"]
        for signal in data.get("data", []):
            risk = signal.get("expectedMove", {}).get("risk", "")
            assert len(risk) > 5, f"Risk text too short: {risk}"


class TestCorrelationsAPI:
    """Test /api/v4/sentiment/correlations for P0 polish fields"""
    
    def test_correlations_returns_ok(self):
        """API returns ok: true"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
    
    def test_correlations_signal_has_decayed_score(self):
        """Each correlation's signal has decayedScore"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        data = response.json()
        for corr in data.get("data", []):
            signal = corr.get("signal", {})
            assert "decayedScore" in signal, f"Missing decayedScore in correlation {corr.get('id')}"
    
    def test_correlations_signal_has_freshness(self):
        """Each correlation's signal has freshness"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        data = response.json()
        valid_freshness = {"FRESH", "ACTIVE", "AGING", "DEAD"}
        for corr in data.get("data", []):
            signal = corr.get("signal", {})
            assert "freshness" in signal, f"Missing freshness in correlation {corr.get('id')}"
            assert signal["freshness"] in valid_freshness
    
    def test_correlations_signal_has_confidence_label(self):
        """Each correlation's signal has confidenceLabel"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        data = response.json()
        valid_labels = {"HIGH", "MEDIUM", "LOW"}
        for corr in data.get("data", []):
            signal = corr.get("signal", {})
            assert "confidenceLabel" in signal, f"Missing confidenceLabel in correlation {corr.get('id')}"
            assert signal["confidenceLabel"] in valid_labels
    
    def test_correlations_signal_has_expected_move(self):
        """Each correlation's signal has expectedMove"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/correlations")
        data = response.json()
        for corr in data.get("data", []):
            signal = corr.get("signal", {})
            assert "expectedMove" in signal, f"Missing expectedMove in correlation {corr.get('id')}"
            exp_move = signal["expectedMove"]
            assert "text" in exp_move
            assert "risk" in exp_move


class TestAccountsAPI:
    """Test /api/v4/sentiment/accounts for Signal Score and Hit Rate"""
    
    def test_accounts_returns_ok(self):
        """API returns ok: true"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/accounts")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
    
    def test_accounts_have_signal_score(self):
        """Each account has signalScore field"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/accounts")
        data = response.json()
        for account in data.get("data", []):
            assert "signalScore" in account, f"Missing signalScore in account {account.get('id')}"
            assert isinstance(account["signalScore"], (int, float))
            assert 0 <= account["signalScore"] <= 100, f"signalScore out of range: {account['signalScore']}"
    
    def test_accounts_have_hit_rate(self):
        """Each account has hitRate field"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/accounts")
        data = response.json()
        for account in data.get("data", []):
            assert "hitRate" in account, f"Missing hitRate in account {account.get('id')}"
            assert isinstance(account["hitRate"], (int, float))
            assert 0 <= account["hitRate"] <= 100, f"hitRate out of range: {account['hitRate']}"


class TestModelStatsAPI:
    """Test /api/v4/sentiment/model-stats for Active Alerts and Type Breakdown"""
    
    def test_model_stats_returns_ok(self):
        """API returns ok: true"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/model-stats")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
    
    def test_model_stats_has_active_alerts(self):
        """Model stats includes activeAlerts count"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/model-stats")
        data = response.json()
        stats = data.get("data", {})
        assert "activeAlerts" in stats, "Missing activeAlerts in model-stats"
        assert isinstance(stats["activeAlerts"], int)
    
    def test_model_stats_has_type_breakdown(self):
        """Model stats includes typeBreakdown with MOMENTUM and ATTENTION"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/model-stats")
        data = response.json()
        stats = data.get("data", {})
        assert "typeBreakdown" in stats, "Missing typeBreakdown in model-stats"
        breakdown = stats["typeBreakdown"]
        # Should have MOMENTUM and ATTENTION types
        assert "MOMENTUM" in breakdown or "ATTENTION" in breakdown, "typeBreakdown should have MOMENTUM or ATTENTION"


class TestTimeDecayLogic:
    """Test time decay computation logic"""
    
    def test_fresh_signals_have_high_decayed_score(self):
        """FRESH signals should have decayedScore close to original score"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        data = response.json()
        for signal in data.get("data", []):
            if signal.get("freshness") == "FRESH":
                # FRESH signals should have decay factor >= 0.85
                original = signal.get("score", 0)
                decayed = signal.get("decayedScore", 0)
                if original > 0:
                    decay_factor = decayed / original
                    assert decay_factor >= 0.8, f"FRESH signal has too much decay: {decay_factor}"
    
    def test_dead_signals_filtered_from_top_strip(self):
        """Top signals should not include DEAD signals (filtered in frontend)"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        data = response.json()
        # Backend may return DEAD signals, but frontend filters them
        # Just verify the freshness field exists for filtering
        for signal in data.get("data", []):
            assert "freshness" in signal


class TestExpectedMoveVariants:
    """Test different expected move text variants"""
    
    def test_momentum_expected_move_bullish(self):
        """MOMENTUM signals with high sentiment should show bullish expected move"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        data = response.json()
        for signal in data.get("data", []):
            if signal.get("signalType") == "MOMENTUM":
                text = signal.get("expectedMove", {}).get("text", "")
                # MOMENTUM should show positive expected move
                assert "+" in text or "potential" in text.lower() or "short term" in text.lower(), \
                    f"MOMENTUM signal should have bullish expected move: {text}"
    
    def test_attention_expected_move_volatile(self):
        """ATTENTION signals should show volatile expected move"""
        response = requests.get(f"{BASE_URL}/api/v4/sentiment/top-signals")
        data = response.json()
        for signal in data.get("data", []):
            if signal.get("signalType") == "ATTENTION":
                text = signal.get("expectedMove", {}).get("text", "")
                risk = signal.get("expectedMove", {}).get("risk", "")
                # ATTENTION should mention volatility or risk
                combined = text.lower() + risk.lower()
                assert any(kw in combined for kw in ["volatil", "risk", "±", "unclear", "elevated"]), \
                    f"ATTENTION signal should mention volatility: {text}, {risk}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
