"""
Test Engine V4 — Actor Intelligence Layer Integration
======================================================
Tests:
  1. Engine V4 API structure (scores, signals, context, drivers)
  2. Entities score integration (not wallet_score)
  3. Actor Intelligence signals in feed
  4. Pressure balance in context matrix
  5. Regression on Entities endpoints
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

class TestEngineV4Core:
    """Engine V4 Core API Tests"""

    def test_engine_context_returns_200(self):
        """Engine context endpoint returns 200"""
        r = requests.get(f"{BASE_URL}/api/engine/context", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True
        print("PASS: Engine context returns 200")

    def test_engine_v4_version(self):
        """Engine version is 4.0"""
        r = requests.get(f"{BASE_URL}/api/engine/context", timeout=15)
        data = r.json()
        meta = data.get("meta", {})
        assert meta.get("version") == "4.0", f"Expected version 4.0, got {meta.get('version')}"
        print("PASS: Engine version is 4.0")

    def test_engine_has_valid_decision(self):
        """Engine returns valid decision"""
        r = requests.get(f"{BASE_URL}/api/engine/context", timeout=15)
        data = r.json()
        assert data.get("decision") in ["BUY", "SELL", "NEUTRAL", "STRONG_BUY", "WATCH", "REDUCE", "AVOID"]
        print(f"PASS: Decision is {data.get('decision')}")

    def test_engine_has_confidence(self):
        """Engine returns confidence with level and score"""
        r = requests.get(f"{BASE_URL}/api/engine/context", timeout=15)
        data = r.json()
        confidence = data.get("confidence", {})
        assert "level" in confidence
        assert "score" in confidence
        assert confidence["level"] in ["HIGH", "MODERATE", "LOW", "INSUFFICIENT"]
        assert isinstance(confidence["score"], (int, float))
        print(f"PASS: Confidence level={confidence['level']}, score={confidence['score']}")

    def test_engine_has_setup(self):
        """Engine returns setup with type, bias, description"""
        r = requests.get(f"{BASE_URL}/api/engine/context", timeout=15)
        data = r.json()
        setup = data.get("setup", {})
        assert "type" in setup
        assert "bias" in setup
        assert "description" in setup
        print(f"PASS: Setup type={setup['type']}, bias={setup['bias']}")


class TestEngineV4Scores:
    """Engine V4 Scores Tests — entities_score instead of wallet_score"""

    def test_engine_has_entities_score(self):
        """Scores include entities_score (V4)"""
        r = requests.get(f"{BASE_URL}/api/engine/context", timeout=15)
        data = r.json()
        scores = data.get("scores", {})
        assert "entities_score" in scores, "Missing entities_score in scores"
        assert isinstance(scores["entities_score"], (int, float))
        print(f"PASS: entities_score = {scores['entities_score']}")

    def test_engine_no_wallet_score(self):
        """Scores do NOT include wallet_score (replaced by entities)"""
        r = requests.get(f"{BASE_URL}/api/engine/context", timeout=15)
        data = r.json()
        scores = data.get("scores", {})
        # wallet_score should not exist in V4
        assert "wallet_score" not in scores, "wallet_score should not exist in V4"
        print("PASS: wallet_score is not present (replaced by entities)")

    def test_engine_has_all_module_scores(self):
        """Scores include all V4 modules: composite, smart_money, cex, entities, token"""
        r = requests.get(f"{BASE_URL}/api/engine/context", timeout=15)
        data = r.json()
        scores = data.get("scores", {})
        required = ["composite", "smart_money_score", "cex_score", "entities_score", "token_score"]
        for key in required:
            assert key in scores, f"Missing {key} in scores"
        print(f"PASS: All module scores present: composite={scores['composite']}, sm={scores['smart_money_score']}, cex={scores['cex_score']}, entities={scores['entities_score']}, token={scores['token_score']}")

    def test_engine_v4_weights(self):
        """Scores include correct V4 weights"""
        r = requests.get(f"{BASE_URL}/api/engine/context", timeout=15)
        data = r.json()
        weights = data.get("scores", {}).get("weights", {})
        assert weights.get("entities") == 0.2, f"entities weight should be 0.2, got {weights.get('entities')}"
        assert weights.get("smart_money") == 0.35
        assert weights.get("cex") == 0.3
        assert weights.get("token") == 0.15
        print(f"PASS: V4 weights correct: {weights}")

    def test_engine_entities_components(self):
        """Entities score has V4 components including actor_pressure"""
        r = requests.get(f"{BASE_URL}/api/engine/context", timeout=15)
        data = r.json()
        components = data.get("scores", {}).get("components", {}).get("entities", {})
        expected = ["behaviour_coherence", "capital_activity", "cluster_coverage", "discovery_quality", "holdings_depth", "actor_pressure"]
        for key in expected:
            assert key in components, f"Missing {key} in entities components"
        print(f"PASS: Entities components include actor_pressure: {components.get('actor_pressure')}")


class TestEngineV4Signals:
    """Engine V4 Signals Tests — array of objects with source/description/confidence/phase"""

    def test_engine_signals_is_array(self):
        """Signals is an array of objects"""
        r = requests.get(f"{BASE_URL}/api/engine/context", timeout=15)
        data = r.json()
        signals = data.get("signals", [])
        assert isinstance(signals, list), "Signals should be an array"
        print(f"PASS: Signals is array with {len(signals)} items")

    def test_engine_signals_have_required_fields(self):
        """Each signal has type, source, description, confidence, phase"""
        r = requests.get(f"{BASE_URL}/api/engine/context", timeout=15)
        data = r.json()
        signals = data.get("signals", [])
        assert len(signals) > 0, "No signals returned"
        for s in signals[:5]:
            assert "type" in s, f"Signal missing type: {s}"
            assert "source" in s, f"Signal missing source: {s}"
            assert "description" in s, f"Signal missing description: {s}"
            assert "confidence" in s, f"Signal missing confidence: {s}"
            assert "phase" in s, f"Signal missing phase: {s}"
        print(f"PASS: Signals have required fields (type, source, description, confidence, phase)")

    def test_engine_has_entities_signals(self):
        """Signals include entities-sourced signals"""
        r = requests.get(f"{BASE_URL}/api/engine/context", timeout=15)
        data = r.json()
        signals = data.get("signals", [])
        entities_signals = [s for s in signals if s.get("source") == "entities"]
        assert len(entities_signals) > 0, "No entities signals found"
        print(f"PASS: {len(entities_signals)} entities signals found")

    def test_engine_signals_sources(self):
        """Signals have sources from V4 modules: entities, smart_money, cex, token"""
        r = requests.get(f"{BASE_URL}/api/engine/context", timeout=15)
        data = r.json()
        signals = data.get("signals", [])
        sources = set(s.get("source") for s in signals)
        assert "entities" in sources, "No entities signals"
        print(f"PASS: Signal sources: {sources}")


class TestEngineV4ContextMatrix:
    """Engine V4 Context Matrix — entities module with pressure_balance"""

    def test_engine_context_matrix_has_entities(self):
        """Context matrix includes entities module"""
        r = requests.get(f"{BASE_URL}/api/engine/context", timeout=15)
        data = r.json()
        matrix = data.get("context_matrix", {})
        assert "entities" in matrix, "Context matrix missing entities"
        print("PASS: Context matrix has entities")

    def test_engine_entities_has_pressure_balance(self):
        """Entities context has pressure_balance field"""
        r = requests.get(f"{BASE_URL}/api/engine/context", timeout=15)
        data = r.json()
        entities = data.get("context_matrix", {}).get("entities", {})
        assert "pressure_balance" in entities, "Missing pressure_balance in entities context"
        assert entities["pressure_balance"] in ["bullish", "bearish", "neutral"]
        print(f"PASS: Entities pressure_balance = {entities['pressure_balance']}")

    def test_engine_entities_has_actor_counts(self):
        """Entities context has bullish_actors and bearish_actors counts"""
        r = requests.get(f"{BASE_URL}/api/engine/context", timeout=15)
        data = r.json()
        entities = data.get("context_matrix", {}).get("entities", {})
        assert "bullish_actors" in entities, "Missing bullish_actors"
        assert "bearish_actors" in entities, "Missing bearish_actors"
        assert isinstance(entities["bullish_actors"], int)
        assert isinstance(entities["bearish_actors"], int)
        print(f"PASS: bullish_actors={entities['bullish_actors']}, bearish_actors={entities['bearish_actors']}")

    def test_engine_entities_has_top_actors(self):
        """Entities context has top_bullish and top_bearish arrays"""
        r = requests.get(f"{BASE_URL}/api/engine/context", timeout=15)
        data = r.json()
        entities = data.get("context_matrix", {}).get("entities", {})
        assert "top_bullish" in entities
        assert "top_bearish" in entities
        assert isinstance(entities["top_bullish"], list)
        assert isinstance(entities["top_bearish"], list)
        print(f"PASS: top_bullish has {len(entities['top_bullish'])} actors, top_bearish has {len(entities['top_bearish'])} actors")


class TestEngineV4Drivers:
    """Engine V4 Drivers — objects with {source, text}"""

    def test_engine_drivers_is_array(self):
        """Drivers is an array"""
        r = requests.get(f"{BASE_URL}/api/engine/context", timeout=15)
        data = r.json()
        drivers = data.get("drivers", [])
        assert isinstance(drivers, list)
        print(f"PASS: Drivers is array with {len(drivers)} items")

    def test_engine_drivers_have_source_and_text(self):
        """Each driver is object with source and text"""
        r = requests.get(f"{BASE_URL}/api/engine/context", timeout=15)
        data = r.json()
        drivers = data.get("drivers", [])
        assert len(drivers) > 0, "No drivers"
        for d in drivers[:5]:
            assert isinstance(d, dict), f"Driver should be dict: {d}"
            assert "source" in d, f"Driver missing source: {d}"
            assert "text" in d, f"Driver missing text: {d}"
        print("PASS: Drivers are objects with {source, text}")

    def test_engine_has_entities_drivers(self):
        """Drivers include entities-sourced drivers"""
        r = requests.get(f"{BASE_URL}/api/engine/context", timeout=15)
        data = r.json()
        drivers = data.get("drivers", [])
        entities_drivers = [d for d in drivers if d.get("source") == "entities"]
        assert len(entities_drivers) > 0, "No entities drivers"
        print(f"PASS: {len(entities_drivers)} entities drivers: {[d['text'][:50] for d in entities_drivers[:3]]}")


class TestEngineV4Gates:
    """Engine V4 Decision Gates"""

    def test_engine_has_gates(self):
        """Engine returns decision gates"""
        r = requests.get(f"{BASE_URL}/api/engine/context", timeout=15)
        data = r.json()
        gates = data.get("gates", {})
        assert "evidence" in gates
        assert "risk" in gates
        assert "coverage" in gates
        print("PASS: Gates present (evidence, risk, coverage)")

    def test_engine_evidence_gate_structure(self):
        """Evidence gate has status, modules_agreeing, verdicts"""
        r = requests.get(f"{BASE_URL}/api/engine/context", timeout=15)
        data = r.json()
        evidence = data.get("gates", {}).get("evidence", {})
        assert "status" in evidence
        assert "modules_agreeing" in evidence
        assert "verdicts" in evidence
        verdicts = evidence.get("verdicts", {})
        # V4: verdicts should have entities not wallet
        assert "entities" in verdicts, "verdicts should have entities (V4)"
        print(f"PASS: Evidence gate: status={evidence['status']}, modules_agreeing={evidence['modules_agreeing']}, entities verdict={verdicts.get('entities')}")


class TestEntitiesRegressionEndpoints:
    """Regression tests for Entities endpoints"""

    def test_entities_intelligence_endpoint(self):
        """GET /api/entities/v2/{slug}/intelligence returns 200"""
        r = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True
        assert "actor_impact" in data, "Missing actor_impact in intelligence"
        print("PASS: Entities intelligence endpoint returns 200 with actor_impact")

    def test_entities_strategy_history_endpoint(self):
        """GET /api/entities/v2/{slug}/strategy-history returns 200"""
        r = requests.get(f"{BASE_URL}/api/entities/v2/binance/strategy-history", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True
        assert "history" in data
        print(f"PASS: Strategy history returns {data.get('count', 0)} entries")

    def test_entities_token_pressure_endpoint(self):
        """GET /api/entities/v2/{slug}/token-pressure returns 200"""
        r = requests.get(f"{BASE_URL}/api/entities/v2/binance/token-pressure", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True
        assert "tokens" in data
        print(f"PASS: Token pressure returns {len(data.get('tokens', []))} tokens")

    def test_entities_global_pressure_map_endpoint(self):
        """GET /api/entities/v2/global/pressure-map returns 200"""
        r = requests.get(f"{BASE_URL}/api/entities/v2/global/pressure-map", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True
        assert "bullish_entities" in data
        assert "bearish_entities" in data
        assert "neutral_entities" in data
        print(f"PASS: Pressure map: bullish={len(data.get('bullish_entities', []))}, bearish={len(data.get('bearish_entities', []))}, neutral={len(data.get('neutral_entities', []))}")

    def test_entities_global_actor_flows_endpoint(self):
        """GET /api/entities/v2/global/actor-flows returns 200"""
        r = requests.get(f"{BASE_URL}/api/entities/v2/global/actor-flows", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True
        assert "interactions" in data
        assert "entity_count" in data
        print(f"PASS: Actor flows: {data.get('total_interactions', 0)} interactions, {data.get('entity_count', 0)} entities")

    def test_entities_list_endpoint(self):
        """GET /api/entities/v2/list returns list"""
        r = requests.get(f"{BASE_URL}/api/entities/v2/list", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True
        assert "entities" in data
        print(f"PASS: Entities list returns {len(data.get('entities', []))} entities")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
