"""
Phase 13: Engine Integration - Unified Decision Engine Tests
Tests GET /api/engine/context endpoint which aggregates all 4 intelligence modules
(Entities, Smart Money, Token, CEX) into a single market decision.

Composite Score = 0.35 * smart_money + 0.30 * cex + 0.20 * entities + 0.15 * token
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestEngineIntegrationPhase13:
    """Phase 13: Engine Integration - Unified Decision Engine"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - fetch engine context for tests"""
        self.response = requests.get(f"{BASE_URL}/api/engine/context?window=30d")
        if self.response.status_code == 200:
            self.data = self.response.json()
        else:
            self.data = {}
    
    # === Basic Response Tests ===
    
    def test_01_engine_context_returns_200(self):
        """GET /api/engine/context returns 200"""
        assert self.response.status_code == 200, f"Expected 200, got {self.response.status_code}"
        print("PASS: GET /api/engine/context returns 200")
    
    def test_02_response_ok_true(self):
        """Response contains ok=true"""
        assert self.data.get('ok') is True, "Expected ok=true"
        print("PASS: Response contains ok=true")
    
    # === Decision Tests ===
    
    def test_03_decision_field_exists(self):
        """Response contains decision field"""
        assert 'decision' in self.data, "Missing decision field"
        print(f"PASS: Decision field exists: {self.data.get('decision')}")
    
    def test_04_decision_valid_value(self):
        """Decision is BUY, SELL, or NEUTRAL"""
        decision = self.data.get('decision')
        assert decision in ['BUY', 'SELL', 'NEUTRAL'], f"Invalid decision: {decision}"
        print(f"PASS: Decision is valid: {decision}")
    
    # === Confidence Tests ===
    
    def test_05_confidence_object_exists(self):
        """Response contains confidence object"""
        assert 'confidence' in self.data, "Missing confidence field"
        assert isinstance(self.data.get('confidence'), dict), "Confidence must be dict"
        print("PASS: Confidence object exists")
    
    def test_06_confidence_has_level(self):
        """Confidence has level field (HIGH/MODERATE/LOW/INSUFFICIENT)"""
        conf = self.data.get('confidence', {})
        assert 'level' in conf, "Missing confidence.level"
        assert conf['level'] in ['HIGH', 'MODERATE', 'LOW', 'INSUFFICIENT'], f"Invalid level: {conf['level']}"
        print(f"PASS: Confidence level: {conf.get('level')}")
    
    def test_07_confidence_has_score(self):
        """Confidence has score field (0-100)"""
        conf = self.data.get('confidence', {})
        assert 'score' in conf, "Missing confidence.score"
        assert 0 <= conf['score'] <= 100, f"Score out of range: {conf['score']}"
        print(f"PASS: Confidence score: {conf.get('score')}")
    
    # === Setup Tests ===
    
    def test_08_setup_object_exists(self):
        """Response contains setup object"""
        assert 'setup' in self.data, "Missing setup field"
        assert isinstance(self.data.get('setup'), dict), "Setup must be dict"
        print("PASS: Setup object exists")
    
    def test_09_setup_has_type(self):
        """Setup has type field"""
        setup = self.data.get('setup', {})
        assert 'type' in setup, "Missing setup.type"
        print(f"PASS: Setup type: {setup.get('type')}")
    
    def test_10_setup_has_bias(self):
        """Setup has bias field (bullish/bearish/neutral)"""
        setup = self.data.get('setup', {})
        assert 'bias' in setup, "Missing setup.bias"
        assert setup['bias'] in ['bullish', 'bearish', 'neutral'], f"Invalid bias: {setup['bias']}"
        print(f"PASS: Setup bias: {setup.get('bias')}")
    
    # === Window Tests ===
    
    def test_11_window_field_exists(self):
        """Response contains window string"""
        assert 'window' in self.data, "Missing window field"
        assert isinstance(self.data.get('window'), str), "Window must be string"
        print(f"PASS: Window: {self.data.get('window')}")
    
    # === Scores Tests ===
    
    def test_12_scores_object_exists(self):
        """Response contains scores object"""
        assert 'scores' in self.data, "Missing scores field"
        assert isinstance(self.data.get('scores'), dict), "Scores must be dict"
        print("PASS: Scores object exists")
    
    def test_13_scores_has_entities_score(self):
        """Scores has entities_score"""
        scores = self.data.get('scores', {})
        assert 'entities_score' in scores, "Missing entities_score"
        assert 0 <= scores['entities_score'] <= 100, f"Score out of range: {scores['entities_score']}"
        print(f"PASS: entities_score: {scores.get('entities_score')}")
    
    def test_14_scores_has_smart_money_score(self):
        """Scores has smart_money_score"""
        scores = self.data.get('scores', {})
        assert 'smart_money_score' in scores, "Missing smart_money_score"
        assert 0 <= scores['smart_money_score'] <= 100, f"Score out of range: {scores['smart_money_score']}"
        print(f"PASS: smart_money_score: {scores.get('smart_money_score')}")
    
    def test_15_scores_has_token_score(self):
        """Scores has token_score"""
        scores = self.data.get('scores', {})
        assert 'token_score' in scores, "Missing token_score"
        assert 0 <= scores['token_score'] <= 100, f"Score out of range: {scores['token_score']}"
        print(f"PASS: token_score: {scores.get('token_score')}")
    
    def test_16_scores_has_cex_score(self):
        """Scores has cex_score"""
        scores = self.data.get('scores', {})
        assert 'cex_score' in scores, "Missing cex_score"
        assert 0 <= scores['cex_score'] <= 100, f"Score out of range: {scores['cex_score']}"
        print(f"PASS: cex_score: {scores.get('cex_score')}")
    
    def test_17_scores_has_composite(self):
        """Scores has composite"""
        scores = self.data.get('scores', {})
        assert 'composite' in scores, "Missing composite"
        assert 0 <= scores['composite'] <= 100, f"Composite out of range: {scores['composite']}"
        print(f"PASS: composite: {scores.get('composite')}")
    
    # === Weights Verification ===
    
    def test_18_weights_correct(self):
        """Composite follows weights: smart_money 0.35, cex 0.30, entities 0.20, token 0.15"""
        scores = self.data.get('scores', {})
        weights = scores.get('weights', {})
        assert weights.get('smart_money') == 0.35, f"smart_money weight: {weights.get('smart_money')}"
        assert weights.get('cex') == 0.30, f"cex weight: {weights.get('cex')}"
        assert weights.get('entities') == 0.20, f"entities weight: {weights.get('entities')}"
        assert weights.get('token') == 0.15, f"token weight: {weights.get('token')}"
        print("PASS: All weights correct (0.35, 0.30, 0.20, 0.15)")
    
    def test_19_composite_calculation_valid(self):
        """Composite score matches weighted sum of module scores"""
        scores = self.data.get('scores', {})
        sm = scores.get('smart_money_score', 0)
        cex = scores.get('cex_score', 0)
        ent = scores.get('entities_score', 0)
        tok = scores.get('token_score', 0)
        composite = scores.get('composite', 0)
        calculated = round(sm * 0.35 + cex * 0.30 + ent * 0.20 + tok * 0.15)
        # Allow 1 point rounding difference
        assert abs(calculated - composite) <= 1, f"Composite mismatch: calculated={calculated}, api={composite}"
        print(f"PASS: Composite calculation valid ({calculated} ~= {composite})")
    
    # === Market State Tests ===
    
    def test_20_market_state_exists(self):
        """Response contains market_state"""
        assert 'market_state' in self.data, "Missing market_state"
        print(f"PASS: market_state: {self.data.get('market_state')}")
    
    # === Gates Tests ===
    
    def test_21_gates_object_exists(self):
        """Response contains gates object"""
        assert 'gates' in self.data, "Missing gates field"
        assert isinstance(self.data.get('gates'), dict), "Gates must be dict"
        print("PASS: Gates object exists")
    
    def test_22_gates_has_evidence(self):
        """Gates has evidence gate"""
        gates = self.data.get('gates', {})
        assert 'evidence' in gates, "Missing evidence gate"
        print(f"PASS: Evidence gate status: {gates.get('evidence', {}).get('status')}")
    
    def test_23_gates_has_risk(self):
        """Gates has risk gate"""
        gates = self.data.get('gates', {})
        assert 'risk' in gates, "Missing risk gate"
        print(f"PASS: Risk gate status: {gates.get('risk', {}).get('status')}")
    
    def test_24_gates_has_coverage(self):
        """Gates has coverage gate"""
        gates = self.data.get('gates', {})
        assert 'coverage' in gates, "Missing coverage gate"
        print(f"PASS: Coverage gate status: {gates.get('coverage', {}).get('status')}")
    
    def test_25_evidence_has_verdicts_for_4_modules(self):
        """Evidence gate has verdicts for all 4 modules"""
        evidence = self.data.get('gates', {}).get('evidence', {})
        verdicts = evidence.get('verdicts', {})
        assert 'entities' in verdicts, "Missing entities verdict"
        assert 'smart_money' in verdicts, "Missing smart_money verdict"
        assert 'cex' in verdicts, "Missing cex verdict"
        assert 'token' in verdicts, "Missing token verdict"
        print(f"PASS: Evidence verdicts: {verdicts}")
    
    # === Drivers Tests ===
    
    def test_26_drivers_array_exists(self):
        """Response contains drivers array"""
        assert 'drivers' in self.data, "Missing drivers field"
        assert isinstance(self.data.get('drivers'), list), "Drivers must be list"
        print(f"PASS: {len(self.data.get('drivers', []))} drivers found")
    
    def test_27_module_drivers_exists(self):
        """Response contains module_drivers object"""
        assert 'module_drivers' in self.data, "Missing module_drivers field"
        assert isinstance(self.data.get('module_drivers'), dict), "Module drivers must be dict"
        print("PASS: module_drivers object exists")
    
    def test_28_module_drivers_has_4_modules(self):
        """module_drivers has all 4 module keys"""
        md = self.data.get('module_drivers', {})
        assert 'entities' in md, "Missing entities drivers"
        assert 'smart_money' in md, "Missing smart_money drivers"
        assert 'cex' in md, "Missing cex drivers"
        assert 'token' in md, "Missing token drivers"
        print("PASS: module_drivers has all 4 module keys")
    
    # === Risks Tests ===
    
    def test_29_risks_array_exists(self):
        """Response contains risks array"""
        assert 'risks' in self.data, "Missing risks field"
        assert isinstance(self.data.get('risks'), list), "Risks must be list"
        print(f"PASS: {len(self.data.get('risks', []))} risks found")
    
    # === Context Matrix Tests ===
    
    def test_30_context_matrix_exists(self):
        """Response contains context_matrix"""
        assert 'context_matrix' in self.data, "Missing context_matrix"
        assert isinstance(self.data.get('context_matrix'), dict), "Context matrix must be dict"
        print("PASS: context_matrix exists")
    
    def test_31_context_matrix_has_entities(self):
        """Context matrix has entities section"""
        cm = self.data.get('context_matrix', {})
        assert 'entities' in cm, "Missing entities in context_matrix"
        print(f"PASS: entities context: {cm.get('entities', {}).get('entity_count')} entities")
    
    def test_32_context_matrix_has_smart_money(self):
        """Context matrix has smart_money section"""
        cm = self.data.get('context_matrix', {})
        assert 'smart_money' in cm, "Missing smart_money in context_matrix"
        print(f"PASS: smart_money context present")
    
    def test_33_context_matrix_has_cex(self):
        """Context matrix has cex section"""
        cm = self.data.get('context_matrix', {})
        assert 'cex' in cm, "Missing cex in context_matrix"
        print(f"PASS: cex context present")
    
    def test_34_context_matrix_has_token(self):
        """Context matrix has token section"""
        cm = self.data.get('context_matrix', {})
        assert 'token' in cm, "Missing token in context_matrix"
        print(f"PASS: token context present")
    
    # === Signals Tests ===
    
    def test_35_signals_array_exists(self):
        """Response contains signals array"""
        assert 'signals' in self.data, "Missing signals field"
        assert isinstance(self.data.get('signals'), list), "Signals must be list"
        print(f"PASS: {len(self.data.get('signals', []))} signals found")
    
    def test_36_signals_have_lifecycle_phases(self):
        """Signals have lifecycle phases (detected, confirmed, expansion, exhaustion)"""
        signals = self.data.get('signals', [])
        if len(signals) == 0:
            pytest.skip("No signals to test")
        phases = set()
        for s in signals:
            phase = s.get('phase')
            if phase:
                phases.add(phase)
        valid_phases = {'detected', 'confirmed', 'expansion', 'exhaustion'}
        # At least some phases should be present
        assert len(phases) > 0, "No phases found in signals"
        assert phases.issubset(valid_phases), f"Invalid phases: {phases - valid_phases}"
        print(f"PASS: Signal phases found: {phases}")
    
    def test_37_signal_structure(self):
        """Each signal has required fields: type, source, description, confidence, phase, age_h"""
        signals = self.data.get('signals', [])
        if len(signals) == 0:
            pytest.skip("No signals to test")
        required = ['type', 'source', 'description', 'confidence', 'phase', 'age_h']
        for i, s in enumerate(signals[:5]):  # Check first 5
            for field in required:
                assert field in s, f"Signal {i} missing {field}"
        print(f"PASS: Signals have all required fields")
    
    # === Meta Tests ===
    
    def test_38_meta_object_exists(self):
        """Response contains meta object"""
        assert 'meta' in self.data, "Missing meta field"
        assert isinstance(self.data.get('meta'), dict), "Meta must be dict"
        print("PASS: meta object exists")
    
    def test_39_meta_version_13(self):
        """Meta version is 13.0"""
        meta = self.data.get('meta', {})
        version = meta.get('version')
        assert version == '13.0', f"Expected version 13.0, got {version}"
        print(f"PASS: Meta version: {version}")
    
    def test_40_meta_has_modules(self):
        """Meta has modules array with 4 modules"""
        meta = self.data.get('meta', {})
        modules = meta.get('modules', [])
        assert len(modules) == 4, f"Expected 4 modules, got {len(modules)}"
        expected = {'entities', 'smart_money', 'token', 'cex'}
        assert set(modules) == expected, f"Missing modules: {expected - set(modules)}"
        print(f"PASS: Meta modules: {modules}")


class TestEngineWindowParams:
    """Test window query parameter variations"""
    
    def test_41_window_24h(self):
        """GET /api/engine/context?window=24h works"""
        response = requests.get(f"{BASE_URL}/api/engine/context?window=24h")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get('ok') is True, "Expected ok=true"
        assert data.get('meta', {}).get('window') == '24h', "Window should be 24h"
        print("PASS: window=24h works")
    
    def test_42_window_7d(self):
        """GET /api/engine/context?window=7d works"""
        response = requests.get(f"{BASE_URL}/api/engine/context?window=7d")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get('ok') is True, "Expected ok=true"
        assert data.get('meta', {}).get('window') == '7d', "Window should be 7d"
        print("PASS: window=7d works")
    
    def test_43_window_30d_default(self):
        """GET /api/engine/context (default window=30d) works"""
        response = requests.get(f"{BASE_URL}/api/engine/context")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get('ok') is True, "Expected ok=true"
        assert data.get('meta', {}).get('window') == '30d', "Default window should be 30d"
        print("PASS: Default window=30d works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
