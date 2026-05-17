"""
S10.8 — Meta-Brain Exchange Hook Tests
======================================

Testing Exchange Intelligence → Meta-Brain integration.
Golden Rule: Exchange can ONLY DOWNGRADE, NEVER upgrade or initiate.

Tests:
1. API endpoint availability (all 7 endpoints)
2. Context retrieval for symbols
3. Simulate verdict processing
4. Process real verdict
5. Impact metrics tracking
6. Downgrade rules and history
7. GOLDEN RULE: No upgrade verification
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestMetaBrainContextAPI:
    """GET /api/v10/meta-brain/context/:symbol"""
    
    def test_context_btcusdt_returns_ok(self):
        """Context API returns ok for BTCUSDT"""
        response = requests.get(f"{BASE_URL}/api/v10/meta-brain/context/BTCUSDT")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        assert data.get('symbol') == 'BTCUSDT'
        print("✓ GET /context/BTCUSDT returns ok:true")
    
    def test_context_has_regime_info(self):
        """Context contains regime information"""
        response = requests.get(f"{BASE_URL}/api/v10/meta-brain/context/BTCUSDT")
        data = response.json()
        context = data.get('context', {})
        
        assert 'regime' in context
        assert 'regimeConfidence' in context
        assert isinstance(context['regimeConfidence'], (int, float))
        print(f"✓ Context has regime: {context['regime']}, confidence: {context['regimeConfidence']}")
    
    def test_context_has_market_stress(self):
        """Context contains marketStress"""
        response = requests.get(f"{BASE_URL}/api/v10/meta-brain/context/BTCUSDT")
        data = response.json()
        context = data.get('context', {})
        
        assert 'marketStress' in context
        assert isinstance(context['marketStress'], (int, float))
        assert 0 <= context['marketStress'] <= 1
        print(f"✓ Context has marketStress: {context['marketStress']}")
    
    def test_context_has_flow_info(self):
        """Context contains flow bias and dominance"""
        response = requests.get(f"{BASE_URL}/api/v10/meta-brain/context/BTCUSDT")
        data = response.json()
        context = data.get('context', {})
        
        assert 'flowBias' in context
        assert context['flowBias'] in ['BUY', 'SELL', 'NEUTRAL']
        assert 'flowDominance' in context
        print(f"✓ Context has flowBias: {context['flowBias']}, flowDominance: {context['flowDominance']}")
    
    def test_context_has_liquidity_state(self):
        """Context contains liquidity state"""
        response = requests.get(f"{BASE_URL}/api/v10/meta-brain/context/BTCUSDT")
        data = response.json()
        context = data.get('context', {})
        
        assert 'liquidityState' in context
        assert context['liquidityState'] in ['THIN', 'NORMAL', 'HEAVY']
        print(f"✓ Context has liquidityState: {context['liquidityState']}")
    
    def test_context_has_pattern_summary(self):
        """Context contains pattern summary"""
        response = requests.get(f"{BASE_URL}/api/v10/meta-brain/context/BTCUSDT")
        data = response.json()
        context = data.get('context', {})
        
        ps = context.get('patternSummary', {})
        assert 'count' in ps
        assert 'bullish' in ps
        assert 'bearish' in ps
        assert 'neutral' in ps
        assert 'hasConflict' in ps
        print(f"✓ Context has patternSummary: count={ps['count']}, bullish={ps['bullish']}, bearish={ps['bearish']}")
    
    def test_context_has_ml_verdict(self):
        """Context contains ML verdict"""
        response = requests.get(f"{BASE_URL}/api/v10/meta-brain/context/BTCUSDT")
        data = response.json()
        context = data.get('context', {})
        
        assert 'mlVerdict' in context
        assert context['mlVerdict'] in ['USE', 'IGNORE', 'WARNING']
        assert 'mlConfidence' in context
        print(f"✓ Context has mlVerdict: {context['mlVerdict']}, mlConfidence: {context['mlConfidence']}")
    
    def test_context_has_timestamp(self):
        """Context contains timestamp"""
        response = requests.get(f"{BASE_URL}/api/v10/meta-brain/context/BTCUSDT")
        data = response.json()
        context = data.get('context', {})
        
        assert 'timestamp' in context
        assert isinstance(context['timestamp'], int)
        print(f"✓ Context has timestamp: {context['timestamp']}")


class TestMetaBrainSimulateAPI:
    """POST /api/v10/meta-brain/simulate"""
    
    def test_simulate_returns_ok(self):
        """Simulate API returns ok"""
        response = requests.post(
            f"{BASE_URL}/api/v10/meta-brain/simulate",
            json={"symbol": "BTCUSDT", "direction": "BULLISH", "confidence": 0.8, "strength": "STRONG"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        print("✓ POST /simulate returns ok:true")
    
    def test_simulate_returns_verdict(self):
        """Simulate returns full verdict structure"""
        response = requests.post(
            f"{BASE_URL}/api/v10/meta-brain/simulate",
            json={"symbol": "BTCUSDT", "direction": "BULLISH", "confidence": 0.8, "strength": "STRONG"}
        )
        data = response.json()
        verdict = data.get('verdict', {})
        
        assert 'direction' in verdict
        assert 'originalConfidence' in verdict
        assert 'originalStrength' in verdict
        assert 'finalConfidence' in verdict
        assert 'finalStrength' in verdict
        assert 'downgraded' in verdict
        assert 'exchangeImpact' in verdict
        print(f"✓ Simulate verdict: {verdict['originalStrength']} → {verdict['finalStrength']}")
    
    def test_simulate_preserves_direction(self):
        """Simulate preserves input direction (BULLISH/BEARISH/NEUTRAL)"""
        for direction in ['BULLISH', 'BEARISH', 'NEUTRAL']:
            response = requests.post(
                f"{BASE_URL}/api/v10/meta-brain/simulate",
                json={"symbol": "BTCUSDT", "direction": direction, "confidence": 0.8, "strength": "STRONG"}
            )
            data = response.json()
            verdict = data.get('verdict', {})
            assert verdict.get('direction') == direction
        print("✓ Simulate preserves all direction types: BULLISH, BEARISH, NEUTRAL")


class TestMetaBrainProcessAPI:
    """POST /api/v10/meta-brain/process"""
    
    def test_process_returns_ok(self):
        """Process API returns ok"""
        response = requests.post(
            f"{BASE_URL}/api/v10/meta-brain/process",
            json={"symbol": "BTCUSDT", "direction": "BULLISH", "confidence": 0.8, "strength": "STRONG"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        print("✓ POST /process returns ok:true")
    
    def test_process_requires_symbol(self):
        """Process requires symbol"""
        response = requests.post(
            f"{BASE_URL}/api/v10/meta-brain/process",
            json={"direction": "BULLISH", "confidence": 0.8, "strength": "STRONG"}
        )
        data = response.json()
        # Should return error if symbol is missing
        assert data.get('ok') == False or 'error' in data
        print("✓ POST /process validates required fields")
    
    def test_process_returns_verdict_with_sources(self):
        """Process returns verdict with sources"""
        response = requests.post(
            f"{BASE_URL}/api/v10/meta-brain/process",
            json={
                "symbol": "BTCUSDT", 
                "direction": "BULLISH", 
                "confidence": 0.8, 
                "strength": "STRONG",
                "sentimentSource": {"confidence": 0.75, "direction": "BULLISH"},
                "onchainSource": {"confidence": 0.7, "validation": "CONFIRMED"}
            }
        )
        data = response.json()
        verdict = data.get('verdict', {})
        sources = verdict.get('sources', {})
        
        assert 'sentiment' in sources
        assert 'onchain' in sources
        assert 'exchange' in sources
        print(f"✓ Process returns verdict with all 3 sources")


class TestMetaBrainImpactMetricsAPI:
    """GET /api/v10/meta-brain/impact/metrics"""
    
    def test_metrics_returns_ok(self):
        """Impact metrics API returns ok"""
        response = requests.get(f"{BASE_URL}/api/v10/meta-brain/impact/metrics")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        print("✓ GET /impact/metrics returns ok:true")
    
    def test_metrics_has_total_decisions(self):
        """Metrics has totalDecisions"""
        response = requests.get(f"{BASE_URL}/api/v10/meta-brain/impact/metrics")
        data = response.json()
        metrics = data.get('metrics', {})
        
        assert 'totalDecisions' in metrics
        assert isinstance(metrics['totalDecisions'], int)
        print(f"✓ Metrics totalDecisions: {metrics['totalDecisions']}")
    
    def test_metrics_has_downgrade_stats(self):
        """Metrics has downgrade statistics"""
        response = requests.get(f"{BASE_URL}/api/v10/meta-brain/impact/metrics")
        data = response.json()
        metrics = data.get('metrics', {})
        
        assert 'downgraded' in metrics
        assert 'downgradedRate' in metrics
        print(f"✓ Metrics downgraded: {metrics['downgraded']}, rate: {metrics['downgradedRate']}")
    
    def test_metrics_has_trigger_breakdown(self):
        """Metrics has breakdown by trigger type"""
        response = requests.get(f"{BASE_URL}/api/v10/meta-brain/impact/metrics")
        data = response.json()
        metrics = data.get('metrics', {})
        by_trigger = metrics.get('byTrigger', {})
        
        assert 'regime' in by_trigger
        assert 'stress' in by_trigger
        assert 'conflict' in by_trigger
        assert 'mlWarning' in by_trigger
        print(f"✓ Metrics byTrigger: regime={by_trigger['regime']}, stress={by_trigger['stress']}, conflict={by_trigger['conflict']}, mlWarning={by_trigger['mlWarning']}")


class TestMetaBrainImpactRulesAPI:
    """GET /api/v10/meta-brain/impact/rules"""
    
    def test_rules_returns_ok(self):
        """Impact rules API returns ok"""
        response = requests.get(f"{BASE_URL}/api/v10/meta-brain/impact/rules")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        print("✓ GET /impact/rules returns ok:true")
    
    def test_rules_has_downgrading_regimes(self):
        """Rules has downgrading regimes list"""
        response = requests.get(f"{BASE_URL}/api/v10/meta-brain/impact/rules")
        data = response.json()
        rules = data.get('rules', {})
        
        assert 'downgradingRegimes' in rules
        regimes = rules['downgradingRegimes']
        assert isinstance(regimes, list)
        assert 'EXHAUSTION' in regimes
        assert 'LONG_SQUEEZE' in regimes
        assert 'SHORT_SQUEEZE' in regimes
        assert 'DISTRIBUTION' in regimes
        print(f"✓ Rules downgradingRegimes: {regimes}")
    
    def test_rules_has_thresholds(self):
        """Rules has all threshold values"""
        response = requests.get(f"{BASE_URL}/api/v10/meta-brain/impact/rules")
        data = response.json()
        rules = data.get('rules', {})
        
        assert 'marketStressThreshold' in rules
        assert 'conflictPatternThreshold' in rules
        assert 'regimeConfidenceThreshold' in rules
        assert 'mlWarningBlocksStrong' in rules
        print(f"✓ Rules thresholds: stress={rules['marketStressThreshold']}, conflict={rules['conflictPatternThreshold']}, regime={rules['regimeConfidenceThreshold']}, mlWarning={rules['mlWarningBlocksStrong']}")


class TestMetaBrainDowngradesAPI:
    """GET /api/v10/meta-brain/impact/downgrades"""
    
    def test_downgrades_returns_ok(self):
        """Downgrades API returns ok"""
        response = requests.get(f"{BASE_URL}/api/v10/meta-brain/impact/downgrades")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        print("✓ GET /impact/downgrades returns ok:true")
    
    def test_downgrades_has_count(self):
        """Downgrades has count field"""
        response = requests.get(f"{BASE_URL}/api/v10/meta-brain/impact/downgrades")
        data = response.json()
        
        assert 'count' in data
        assert 'downgrades' in data
        assert isinstance(data['downgrades'], list)
        print(f"✓ Downgrades count: {data['count']}")
    
    def test_downgrades_respects_limit(self):
        """Downgrades respects limit parameter"""
        response = requests.get(f"{BASE_URL}/api/v10/meta-brain/impact/downgrades?limit=5")
        data = response.json()
        
        assert len(data.get('downgrades', [])) <= 5
        print("✓ Downgrades respects limit parameter")


class TestMetaBrainResetAPI:
    """POST /api/v10/meta-brain/impact/reset"""
    
    def test_reset_returns_ok(self):
        """Reset API returns ok"""
        response = requests.post(f"{BASE_URL}/api/v10/meta-brain/impact/reset")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        assert data.get('message') == 'Impact metrics reset'
        print("✓ POST /impact/reset returns ok:true")
    
    def test_reset_clears_metrics(self):
        """Reset clears all metrics"""
        # First process some verdicts
        requests.post(
            f"{BASE_URL}/api/v10/meta-brain/process",
            json={"symbol": "BTCUSDT", "direction": "BULLISH", "confidence": 0.8, "strength": "STRONG"}
        )
        
        # Reset
        requests.post(f"{BASE_URL}/api/v10/meta-brain/impact/reset")
        
        # Check metrics are reset
        response = requests.get(f"{BASE_URL}/api/v10/meta-brain/impact/metrics")
        data = response.json()
        metrics = data.get('metrics', {})
        
        assert metrics.get('totalDecisions') == 0
        assert metrics.get('downgraded') == 0
        print("✓ Reset clears all metrics to 0")


class TestGoldenRuleNoUpgrade:
    """
    GOLDEN RULE VERIFICATION
    Exchange can ONLY downgrade, NEVER upgrade.
    """
    
    def test_strong_not_upgraded_in_favorable_conditions(self):
        """STRONG verdict is NOT upgraded when conditions are favorable"""
        # Reset metrics first
        requests.post(f"{BASE_URL}/api/v10/meta-brain/impact/reset")
        
        # Process STRONG verdict with neutral/favorable exchange context
        response = requests.post(
            f"{BASE_URL}/api/v10/meta-brain/process",
            json={
                "symbol": "BTCUSDT", 
                "direction": "BULLISH", 
                "confidence": 0.7,  # Lower confidence
                "strength": "STRONG"
            }
        )
        data = response.json()
        verdict = data.get('verdict', {})
        
        # Original values should be preserved (no upgrade)
        assert verdict.get('originalConfidence') == 0.7
        assert verdict.get('originalStrength') == 'STRONG'
        
        # Final values should NOT exceed original (GOLDEN RULE)
        assert verdict.get('finalConfidence') <= verdict.get('originalConfidence')
        # If downgraded, strength should be lower, if not downgraded, should be same
        if not verdict.get('downgraded'):
            assert verdict.get('finalStrength') == verdict.get('originalStrength')
        
        print(f"✓ GOLDEN RULE: STRONG {verdict['originalConfidence']} → {verdict['finalStrength']} {verdict['finalConfidence']:.2f} (no upgrade)")
    
    def test_weak_not_upgraded_to_moderate(self):
        """WEAK verdict is NOT upgraded to MODERATE"""
        response = requests.post(
            f"{BASE_URL}/api/v10/meta-brain/process",
            json={
                "symbol": "BTCUSDT", 
                "direction": "BULLISH", 
                "confidence": 0.5,
                "strength": "WEAK"
            }
        )
        data = response.json()
        verdict = data.get('verdict', {})
        
        # WEAK should stay WEAK or go to NONE, never upgrade
        assert verdict.get('finalStrength') in ['WEAK', 'NONE']
        assert verdict.get('finalConfidence') <= verdict.get('originalConfidence')
        print(f"✓ GOLDEN RULE: WEAK stays WEAK/NONE (no upgrade to MODERATE)")
    
    def test_moderate_not_upgraded_to_strong(self):
        """MODERATE verdict is NOT upgraded to STRONG"""
        response = requests.post(
            f"{BASE_URL}/api/v10/meta-brain/process",
            json={
                "symbol": "BTCUSDT", 
                "direction": "BULLISH", 
                "confidence": 0.6,
                "strength": "MODERATE"
            }
        )
        data = response.json()
        verdict = data.get('verdict', {})
        
        # MODERATE should stay MODERATE/WEAK/NONE, never upgrade to STRONG
        assert verdict.get('finalStrength') in ['MODERATE', 'WEAK', 'NONE']
        assert verdict.get('finalConfidence') <= verdict.get('originalConfidence')
        print(f"✓ GOLDEN RULE: MODERATE never upgrades to STRONG")
    
    def test_confidence_never_increases(self):
        """Confidence never increases (GOLDEN RULE)"""
        test_cases = [
            {"direction": "BULLISH", "confidence": 0.3, "strength": "WEAK"},
            {"direction": "BEARISH", "confidence": 0.5, "strength": "MODERATE"},
            {"direction": "NEUTRAL", "confidence": 0.8, "strength": "STRONG"},
        ]
        
        for tc in test_cases:
            response = requests.post(
                f"{BASE_URL}/api/v10/meta-brain/process",
                json={"symbol": "BTCUSDT", **tc}
            )
            data = response.json()
            verdict = data.get('verdict', {})
            
            # GOLDEN RULE: final confidence <= original confidence
            assert verdict.get('finalConfidence') <= verdict.get('originalConfidence'), \
                f"Confidence increased from {verdict['originalConfidence']} to {verdict['finalConfidence']}!"
        
        print("✓ GOLDEN RULE: Confidence NEVER increases in all test cases")
    
    def test_exchange_cannot_initiate_signals(self):
        """Exchange context is READ-ONLY (in sources, not initiator)"""
        response = requests.post(
            f"{BASE_URL}/api/v10/meta-brain/process",
            json={
                "symbol": "BTCUSDT", 
                "direction": "NEUTRAL", 
                "confidence": 0.4,
                "strength": "WEAK"
            }
        )
        data = response.json()
        verdict = data.get('verdict', {})
        
        # Exchange should be in sources but not change direction
        assert 'exchange' in verdict.get('sources', {})
        # Direction should be preserved (Exchange cannot change it)
        assert verdict.get('direction') == 'NEUTRAL'
        print("✓ GOLDEN RULE: Exchange is READ-ONLY (doesn't change direction)")


class TestExchangeImpactDowngradeScenarios:
    """Test downgrade scenarios based on exchange context"""
    
    def test_process_tracks_decision_count(self):
        """Process increments totalDecisions"""
        # Reset first
        requests.post(f"{BASE_URL}/api/v10/meta-brain/impact/reset")
        
        # Process 3 verdicts
        for _ in range(3):
            requests.post(
                f"{BASE_URL}/api/v10/meta-brain/process",
                json={"symbol": "BTCUSDT", "direction": "BULLISH", "confidence": 0.8, "strength": "STRONG"}
            )
        
        # Check metrics
        response = requests.get(f"{BASE_URL}/api/v10/meta-brain/impact/metrics")
        data = response.json()
        metrics = data.get('metrics', {})
        
        assert metrics.get('totalDecisions') == 3
        print(f"✓ Metrics totalDecisions after 3 calls: {metrics['totalDecisions']}")
    
    def test_exchange_impact_fields_present(self):
        """Verdict has all exchangeImpact fields"""
        response = requests.post(
            f"{BASE_URL}/api/v10/meta-brain/process",
            json={"symbol": "BTCUSDT", "direction": "BULLISH", "confidence": 0.8, "strength": "STRONG"}
        )
        data = response.json()
        impact = data.get('verdict', {}).get('exchangeImpact', {})
        
        assert 'applied' in impact
        assert 'regimeDowngrade' in impact
        assert 'stressGuard' in impact
        assert 'conflictGuard' in impact
        assert 'mlWarningGate' in impact
        print(f"✓ ExchangeImpact structure: applied={impact['applied']}, regime={impact['regimeDowngrade']}, stress={impact['stressGuard']}, conflict={impact['conflictGuard']}, ml={impact['mlWarningGate']}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
