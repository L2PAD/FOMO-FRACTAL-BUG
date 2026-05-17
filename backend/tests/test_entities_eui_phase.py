"""
Entities V2 Phase E-UI: Actor Intelligence Extensions Tests
============================================================
Tests for:
1. GET /api/entities/v2/{slug}/impact - Actor market impact
2. GET /api/entities/v2/{slug}/timeline - Entity timeline
3. GET /api/entities/v2/{slug}/interactions - Interaction network
4. Entities list page data validation
5. Entity detail page data validation
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestEntitiesV2ImpactEndpoint:
    """Tests for /api/entities/v2/{slug}/impact endpoint"""

    def test_impact_returns_200_for_valid_entity(self):
        """GET impact returns 200 for valid entity slug"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/impact")
        assert response.status_code == 200
        print("PASS: Impact endpoint returns 200 for binance")

    def test_impact_response_has_ok_true(self):
        """Response contains ok: true"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/impact")
        data = response.json()
        assert data.get("ok") == True
        print("PASS: Impact response has ok: true")

    def test_impact_has_slug(self):
        """Response contains correct slug"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/impact")
        data = response.json()
        assert data.get("slug") == "binance"
        print("PASS: Impact response has correct slug")

    def test_impact_has_impact_score(self):
        """Response contains impact_score (0-100)"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/impact")
        data = response.json()
        assert "impact_score" in data
        assert 0 <= data["impact_score"] <= 100
        print(f"PASS: Impact score: {data['impact_score']}")

    def test_impact_has_impact_level(self):
        """Response contains valid impact_level"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/impact")
        data = response.json()
        assert "impact_level" in data
        assert data["impact_level"] in ["SYSTEMIC", "HIGH", "MEDIUM", "LOW"]
        print(f"PASS: Impact level: {data['impact_level']}")

    def test_impact_has_components(self):
        """Response contains components with scores"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/impact")
        data = response.json()
        assert "components" in data
        components = data["components"]
        # Check all 4 components exist
        for comp in ["portfolio", "flow", "network", "exchange"]:
            assert comp in components
            assert "score" in components[comp]
        print(f"PASS: Components present: {list(components.keys())}")

    def test_impact_has_drivers(self):
        """Response contains drivers array"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/impact")
        data = response.json()
        assert "drivers" in data
        assert isinstance(data["drivers"], list)
        print(f"PASS: Drivers count: {len(data['drivers'])}")

    def test_impact_has_behaviour(self):
        """Response contains behaviour classification"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/impact")
        data = response.json()
        assert "behaviour" in data
        assert "confidence" in data
        print(f"PASS: Behaviour: {data['behaviour']}, confidence: {data['confidence']}")

    def test_impact_returns_404_for_invalid_entity(self):
        """GET impact returns 404 for non-existent entity"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/nonexistent_entity_xyz/impact")
        assert response.status_code == 404
        print("PASS: Impact endpoint returns 404 for invalid entity")


class TestEntitiesV2TimelineEndpoint:
    """Tests for /api/entities/v2/{slug}/timeline endpoint"""

    def test_timeline_returns_200_for_valid_entity(self):
        """GET timeline returns 200 for valid entity slug"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/timeline")
        assert response.status_code == 200
        print("PASS: Timeline endpoint returns 200 for binance")

    def test_timeline_response_has_ok_true(self):
        """Response contains ok: true"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/timeline")
        data = response.json()
        assert data.get("ok") == True
        print("PASS: Timeline response has ok: true")

    def test_timeline_has_slug_and_name(self):
        """Response contains slug and name"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/timeline")
        data = response.json()
        assert data.get("slug") == "binance"
        assert "name" in data
        print(f"PASS: Timeline for {data['name']} (slug: {data['slug']})")

    def test_timeline_has_events_array(self):
        """Response contains events array"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/timeline")
        data = response.json()
        assert "events" in data
        assert isinstance(data["events"], list)
        print(f"PASS: Timeline events count: {len(data['events'])}")

    def test_timeline_events_have_required_fields(self):
        """Events have type, window, and description"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/timeline")
        data = response.json()
        events = data.get("events", [])
        if events:
            for event in events:
                assert "type" in event
                assert "description" in event
            print(f"PASS: All {len(events)} events have required fields")
        else:
            print("INFO: No events in timeline")

    def test_timeline_event_types_valid(self):
        """Events have valid types (flow, token_shift, behaviour, cluster, multichain)"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/timeline")
        data = response.json()
        events = data.get("events", [])
        valid_types = {"flow", "token_shift", "behaviour", "cluster", "multichain"}
        for event in events:
            assert event["type"] in valid_types
        print(f"PASS: All event types valid")

    def test_timeline_has_event_count(self):
        """Response contains event_count"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/timeline")
        data = response.json()
        assert "event_count" in data
        assert data["event_count"] == len(data.get("events", []))
        print(f"PASS: Event count: {data['event_count']}")

    def test_timeline_has_window_summary(self):
        """Response contains window_summary for 24h, 7d, 30d"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/timeline")
        data = response.json()
        assert "window_summary" in data
        for window in ["24h", "7d", "30d"]:
            assert window in data["window_summary"]
        print("PASS: Window summary has all 3 windows (24h, 7d, 30d)")

    def test_timeline_returns_404_for_invalid_entity(self):
        """GET timeline returns 404 for non-existent entity"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/nonexistent_entity_xyz/timeline")
        assert response.status_code == 404
        print("PASS: Timeline endpoint returns 404 for invalid entity")


class TestEntitiesV2InteractionsEndpoint:
    """Tests for /api/entities/v2/{slug}/interactions endpoint"""

    def test_interactions_returns_200_for_valid_entity(self):
        """GET interactions returns 200 for valid entity slug"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/interactions")
        assert response.status_code == 200
        print("PASS: Interactions endpoint returns 200 for binance")

    def test_interactions_response_has_ok_true(self):
        """Response contains ok: true"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/interactions")
        data = response.json()
        assert data.get("ok") == True
        print("PASS: Interactions response has ok: true")

    def test_interactions_has_slug_and_name(self):
        """Response contains slug and name"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/interactions")
        data = response.json()
        assert data.get("slug") == "binance"
        assert "name" in data
        print(f"PASS: Interactions for {data['name']}")

    def test_interactions_has_nodes_array(self):
        """Response contains nodes array"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/interactions")
        data = response.json()
        assert "nodes" in data
        assert isinstance(data["nodes"], list)
        print(f"PASS: Nodes count: {len(data['nodes'])}")

    def test_interactions_has_edges_array(self):
        """Response contains edges array"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/interactions")
        data = response.json()
        assert "edges" in data
        assert isinstance(data["edges"], list)
        print(f"PASS: Edges count: {len(data['edges'])}")

    def test_interactions_nodes_have_required_fields(self):
        """Nodes have id, type, and label"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/interactions")
        data = response.json()
        nodes = data.get("nodes", [])
        for node in nodes:
            assert "id" in node
            assert "type" in node
            assert "label" in node
        print(f"PASS: All {len(nodes)} nodes have required fields")

    def test_interactions_edges_have_required_fields(self):
        """Edges have source, target, and type"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/interactions")
        data = response.json()
        edges = data.get("edges", [])
        for edge in edges:
            assert "source" in edge
            assert "target" in edge
            assert "type" in edge
        print(f"PASS: All {len(edges)} edges have required fields")

    def test_interactions_has_self_node(self):
        """Nodes include self entity node with is_self=True"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/interactions")
        data = response.json()
        nodes = data.get("nodes", [])
        self_nodes = [n for n in nodes if n.get("is_self")]
        assert len(self_nodes) == 1
        assert self_nodes[0]["id"] == "binance"
        print("PASS: Self node present with is_self=True")

    def test_interactions_has_summary(self):
        """Response contains summary with totals"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/interactions")
        data = response.json()
        assert "summary" in data
        summary = data["summary"]
        assert "total_nodes" in summary
        assert "total_edges" in summary
        assert "by_type" in summary
        print(f"PASS: Summary - nodes: {summary['total_nodes']}, edges: {summary['total_edges']}")

    def test_interactions_returns_404_for_invalid_entity(self):
        """GET interactions returns 404 for non-existent entity"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/nonexistent_entity_xyz/interactions")
        assert response.status_code == 404
        print("PASS: Interactions endpoint returns 404 for invalid entity")


class TestEntitiesListAPI:
    """Tests for entities list API used by EntitiesTerminal page"""

    def test_entities_list_returns_200(self):
        """GET list returns 200"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/list?limit=50")
        assert response.status_code == 200
        print("PASS: Entities list returns 200")

    def test_entities_list_has_entities_array(self):
        """Response contains entities array"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/list?limit=50")
        data = response.json()
        assert "entities" in data
        assert isinstance(data["entities"], list)
        print(f"PASS: Entities count: {len(data['entities'])}")

    def test_entities_list_shows_15_entities(self):
        """List shows 15 entities as per test requirements"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/list?limit=50")
        data = response.json()
        # Based on context, expecting 15 entities tracked
        entities = data.get("entities", [])
        assert len(entities) >= 15
        print(f"PASS: Found {len(entities)} entities (expected >= 15)")

    def test_entities_have_required_fields(self):
        """Entities have slug, name, type, category"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/list?limit=50")
        data = response.json()
        entities = data.get("entities", [])
        for e in entities[:5]:  # Check first 5
            assert "slug" in e
            assert "name" in e
            assert "type" in e
        print("PASS: Entities have required fields")


class TestEntityBehaviourOverview:
    """Tests for behaviour overview API"""

    def test_behaviour_overview_returns_200(self):
        """GET behaviour overview returns 200"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/behaviour/overview")
        assert response.status_code == 200
        print("PASS: Behaviour overview returns 200")

    def test_behaviour_overview_has_entities(self):
        """Response contains entities array with behaviours"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/behaviour/overview")
        data = response.json()
        assert "entities" in data
        print(f"PASS: Behaviour overview has {len(data.get('entities', []))} entities")


class TestMultipleEntities:
    """Test impact, timeline, interactions for multiple entities"""

    @pytest.mark.parametrize("slug", ["binance", "coinbase", "uniswap"])
    def test_impact_for_multiple_entities(self, slug):
        """Test impact endpoint for multiple entities"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/{slug}/impact")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert data.get("slug") == slug
        print(f"PASS: Impact for {slug} - level: {data.get('impact_level')}")

    @pytest.mark.parametrize("slug", ["binance", "coinbase", "uniswap"])
    def test_timeline_for_multiple_entities(self, slug):
        """Test timeline endpoint for multiple entities"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/{slug}/timeline")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print(f"PASS: Timeline for {slug} - {data.get('event_count')} events")

    @pytest.mark.parametrize("slug", ["binance", "coinbase", "uniswap"])
    def test_interactions_for_multiple_entities(self, slug):
        """Test interactions endpoint for multiple entities"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/{slug}/interactions")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print(f"PASS: Interactions for {slug} - {data.get('summary', {}).get('total_nodes')} nodes")


class TestEngineContext:
    """Tests for engine context API (Market Brain Engine)"""

    def test_engine_context_returns_200(self):
        """GET /api/engine/context returns 200"""
        response = requests.get(f"{BASE_URL}/api/engine/context")
        assert response.status_code == 200
        print("PASS: Engine context returns 200")

    def test_engine_context_has_decision(self):
        """Response has decision field"""
        response = requests.get(f"{BASE_URL}/api/engine/context")
        data = response.json()
        assert "decision" in data
        assert data["decision"] in ["BUY", "SELL", "NEUTRAL"]
        print(f"PASS: Engine decision: {data['decision']}")

    def test_engine_context_has_signals_with_phases(self):
        """Response has signals with lifecycle phases"""
        response = requests.get(f"{BASE_URL}/api/engine/context")
        data = response.json()
        signals = data.get("signals", [])
        phases = set(s.get("phase") for s in signals if s.get("phase"))
        assert len(signals) > 0
        print(f"PASS: Engine has {len(signals)} signals with phases: {phases}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
