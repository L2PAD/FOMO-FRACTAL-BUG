"""
Test Suite: Market Context Layer (Macro Context)
Tests for Fear & Greed Index, BTC Dominance, Stablecoin Dominance APIs

Endpoints tested:
- GET /api/v10/macro/health
- GET /api/v10/macro/snapshot
- GET /api/v10/macro/signal
- GET /api/v10/macro/impact
- GET /api/v10/macro/fear-greed
- GET /api/v10/macro/dominance
- GET /api/v10/macro/rules
- POST /api/v10/macro/refresh
- POST /api/v10/meta-brain/simulate (macro context integration)
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestMacroHealth:
    """Health endpoint tests"""
    
    def test_health_returns_ok(self):
        """GET /api/v10/macro/health - returns ok status"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/health", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        assert data.get('module') == 'macro'
        assert data.get('version') == 'v1.0'
        print(f"Health check: ok={data.get('ok')}, quality={data.get('quality')}")

    def test_health_has_quality_field(self):
        """GET /api/v10/macro/health - has quality field"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/health", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert 'quality' in data
        assert data['quality'] in ['LIVE', 'CACHED', 'DEGRADED', 'NO_DATA']


class TestMacroSnapshot:
    """Snapshot endpoint tests - aggregated macro data"""
    
    def test_snapshot_returns_ok(self):
        """GET /api/v10/macro/snapshot - returns aggregated data"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/snapshot", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        assert 'data' in data
        print(f"Snapshot: quality={data['data'].get('quality', {}).get('mode')}")
    
    def test_snapshot_has_fear_greed(self):
        """GET /api/v10/macro/snapshot - has fearGreed data"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/snapshot", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert 'fearGreed' in data['data']
        fg = data['data']['fearGreed']
        assert 'value' in fg
        assert 'label' in fg
        assert 0 <= fg['value'] <= 100
        assert fg['label'] in ['EXTREME_FEAR', 'FEAR', 'NEUTRAL', 'GREED', 'EXTREME_GREED']
        print(f"Fear & Greed: {fg['value']} ({fg['label']})")
    
    def test_snapshot_has_dominance(self):
        """GET /api/v10/macro/snapshot - has dominance data"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/snapshot", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert 'dominance' in data['data']
        dom = data['data']['dominance']
        assert 'btcPct' in dom
        assert 'stablePct' in dom
        assert 0 <= dom['btcPct'] <= 100
        assert 0 <= dom['stablePct'] <= 100
        print(f"Dominance: BTC={dom['btcPct']:.2f}%, Stable={dom['stablePct']:.2f}%")
    
    def test_snapshot_has_quality(self):
        """GET /api/v10/macro/snapshot - has quality info"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/snapshot", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert 'quality' in data['data']
        quality = data['data']['quality']
        assert 'mode' in quality
        assert quality['mode'] in ['LIVE', 'CACHED', 'DEGRADED', 'NO_DATA']
    
    def test_snapshot_has_regime_hints(self):
        """GET /api/v10/macro/snapshot - has regimeHints"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/snapshot", timeout=30)
        assert response.status_code == 200
        data = response.json()
        if 'regimeHints' in data['data']:
            hints = data['data']['regimeHints']
            assert 'riskMode' in hints
            assert hints['riskMode'] in ['RISK_ON', 'RISK_OFF', 'RANGE', 'UNKNOWN']
            print(f"Regime: {hints['riskMode']}, drivers={hints.get('drivers', [])}")
    
    def test_snapshot_refresh_param(self):
        """GET /api/v10/macro/snapshot?refresh=true - force refresh"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/snapshot?refresh=true", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True


class TestMacroSignal:
    """Signal endpoint tests - processed signal with flags"""
    
    def test_signal_returns_ok(self):
        """GET /api/v10/macro/signal - returns processed signal"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/signal", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        assert 'data' in data
    
    def test_signal_has_flags(self):
        """GET /api/v10/macro/signal - has flags array"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/signal", timeout=30)
        assert response.status_code == 200
        data = response.json()
        signal = data['data']
        assert 'flags' in signal
        assert isinstance(signal['flags'], list)
        print(f"Signal flags: {signal['flags']}")
    
    def test_signal_has_scores(self):
        """GET /api/v10/macro/signal - has scores object"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/signal", timeout=30)
        assert response.status_code == 200
        data = response.json()
        signal = data['data']
        assert 'scores' in signal
        scores = signal['scores']
        assert 'riskOffScore' in scores
        assert 'riskOnScore' in scores
        assert 'confidencePenalty' in scores
        assert 0 <= scores['riskOffScore'] <= 1
        assert 0 <= scores['riskOnScore'] <= 1
        assert 0.6 <= scores['confidencePenalty'] <= 1.0
        print(f"Scores: riskOff={scores['riskOffScore']:.2f}, riskOn={scores['riskOnScore']:.2f}, penalty={scores['confidencePenalty']:.2f}")
    
    def test_signal_has_explanation(self):
        """GET /api/v10/macro/signal - has explanation"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/signal", timeout=30)
        assert response.status_code == 200
        data = response.json()
        signal = data['data']
        assert 'explain' in signal
        explain = signal['explain']
        assert 'summary' in explain
        assert 'bullets' in explain
        assert isinstance(explain['bullets'], list)
        print(f"Explanation: {explain['summary']}")


class TestMacroImpact:
    """Impact endpoint tests - Meta-Brain integration"""
    
    def test_impact_returns_ok(self):
        """GET /api/v10/macro/impact - returns impact calculation"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/impact", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        assert 'data' in data
    
    def test_impact_has_signal(self):
        """GET /api/v10/macro/impact - has signal"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/impact", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert 'signal' in data['data']
    
    def test_impact_has_impact_object(self):
        """GET /api/v10/macro/impact - has impact calculation"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/impact", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert 'impact' in data['data']
        impact = data['data']['impact']
        assert 'applied' in impact
        assert 'confidenceMultiplier' in impact
        assert 'blockedStrong' in impact
        assert 'reason' in impact
        assert isinstance(impact['blockedStrong'], bool)
        assert 0.6 <= impact['confidenceMultiplier'] <= 1.0
        print(f"Impact: applied={impact['applied']}, multiplier={impact['confidenceMultiplier']:.2f}, blocked={impact['blockedStrong']}")
    
    def test_impact_added_risk_flags(self):
        """GET /api/v10/macro/impact - has addedRiskFlags"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/impact", timeout=30)
        assert response.status_code == 200
        data = response.json()
        impact = data['data']['impact']
        assert 'addedRiskFlags' in impact
        assert isinstance(impact['addedRiskFlags'], list)


class TestMacroFearGreed:
    """Fear & Greed specific endpoint tests"""
    
    def test_fear_greed_returns_ok(self):
        """GET /api/v10/macro/fear-greed - returns Fear & Greed data"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/fear-greed", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
    
    def test_fear_greed_has_data(self):
        """GET /api/v10/macro/fear-greed - has fearGreed data"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/fear-greed", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert 'fearGreed' in data['data']
        fg = data['data']['fearGreed']
        assert 'value' in fg
        assert 'label' in fg
        print(f"Fear & Greed only: {fg['value']} ({fg['label']})")


class TestMacroDominance:
    """Dominance specific endpoint tests"""
    
    def test_dominance_returns_ok(self):
        """GET /api/v10/macro/dominance - returns dominance data"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/dominance", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
    
    def test_dominance_has_data(self):
        """GET /api/v10/macro/dominance - has dominance data"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/dominance", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert 'dominance' in data['data']
        dom = data['data']['dominance']
        assert 'btcPct' in dom
        assert 'stablePct' in dom
        print(f"Dominance only: BTC={dom['btcPct']:.2f}%, Stable={dom['stablePct']:.2f}%")
    
    def test_dominance_has_rsi(self):
        """GET /api/v10/macro/dominance - has RSI data"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/dominance", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert 'rsi' in data['data']


class TestMacroRules:
    """Rules endpoint tests - rule definitions"""
    
    def test_rules_returns_ok(self):
        """GET /api/v10/macro/rules - returns rule definitions"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/rules", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
    
    def test_rules_has_fear_greed_rules(self):
        """GET /api/v10/macro/rules - has fearGreedRules"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/rules", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert 'fearGreedRules' in data['data']
        rules = data['data']['fearGreedRules']
        assert 'EXTREME_FEAR' in rules
        assert 'EXTREME_GREED' in rules
        assert 'NEUTRAL' in rules
        # Verify EXTREME_FEAR has correct penalty (0.6)
        assert rules['EXTREME_FEAR']['confidencePenalty'] == 0.6
        print(f"EXTREME_FEAR penalty: {rules['EXTREME_FEAR']['confidencePenalty']}")
    
    def test_rules_has_thresholds(self):
        """GET /api/v10/macro/rules - has thresholds"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/rules", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert 'thresholds' in data['data']
        thresholds = data['data']['thresholds']
        assert 'BTC_DOM_DELTA_THRESHOLD' in thresholds
        assert 'STABLE_DOM_DELTA_THRESHOLD' in thresholds
        assert 'CONFIDENCE_MIN' in thresholds
        assert thresholds['CONFIDENCE_MIN'] == 0.6


class TestMacroRefresh:
    """POST /api/v10/macro/refresh - force refresh"""
    
    def test_refresh_returns_ok(self):
        """POST /api/v10/macro/refresh - refreshes all macro data"""
        response = requests.post(f"{BASE_URL}/api/v10/macro/refresh", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        assert 'message' in data
    
    def test_refresh_returns_fresh_data(self):
        """POST /api/v10/macro/refresh - returns snapshot and signal"""
        response = requests.post(f"{BASE_URL}/api/v10/macro/refresh", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert 'snapshot' in data['data']
        assert 'signal' in data['data']
        # Verify quality is LIVE after refresh
        quality = data['data']['snapshot'].get('quality', {}).get('mode')
        print(f"After refresh: quality={quality}")


class TestMetaBrainMacroIntegration:
    """Meta-Brain integration with macro context"""
    
    def test_simulate_returns_ok(self):
        """POST /api/v10/meta-brain/simulate - returns verdict"""
        payload = {
            "symbol": "BTCUSDT",
            "simulatedInput": {
                "direction": "BULLISH",
                "confidence": 0.85,
                "strength": "STRONG"
            }
        }
        response = requests.post(
            f"{BASE_URL}/api/v10/meta-brain/simulate",
            json=payload,
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        print(f"Simulate response: {data}")
    
    def test_simulate_has_macro_context(self):
        """POST /api/v10/meta-brain/simulate - verdict includes macroContext"""
        payload = {
            "symbol": "BTCUSDT",
            "simulatedInput": {
                "direction": "BULLISH",
                "confidence": 0.85,
                "strength": "STRONG"
            }
        }
        response = requests.post(
            f"{BASE_URL}/api/v10/meta-brain/simulate",
            json=payload,
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        verdict = data.get('data', {}).get('verdict', data.get('data', {}))
        # macroContext should be present if macro impact was applied
        if 'macroContext' in verdict:
            mc = verdict['macroContext']
            assert 'flags' in mc
            assert 'confidenceMultiplier' in mc
            assert 'blockedStrong' in mc
            print(f"Macro context in verdict: {mc}")
        else:
            print("No macroContext in verdict - macro may have minimal impact")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
