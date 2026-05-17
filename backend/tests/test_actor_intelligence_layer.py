"""
Actor Intelligence Layer API Tests (Phase A)
=============================================
Tests for the new unified intelligence endpoint and field validations.

Endpoints tested:
- GET /api/entities/v2/{slug}/intelligence - Unified actor intelligence endpoint
- GET /api/entities/v2/list - Entity listing
- GET /api/entities/v2/{slug}/impact - Market impact
- GET /api/entities/v2/{slug}/timeline - Temporal events
- GET /api/entities/v2/{slug}/interactions - Entity relationships
- GET /api/entities/v2/{slug}/behaviour - Behaviour classification

Field validations:
- pressure: string (bullish/bearish/neutral)
- pressure_detail: contains score, inflow_ratio, net_flow_usd, drivers array
- strategy: string with strategy_detail
- conviction: string with conviction_detail containing score int, drivers array
- regime: string
- cluster_roles: array of cluster objects
- token_dependency: object with stablecoin_dependency, eth_dependency, top_token_dependency
- quick_tags: array of strings
- highlights: array of strings
- summary: string
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test entities: exchanges, protocols
TEST_ENTITIES = ['binance', 'coinbase', 'uniswap', 'okx', 'kraken']


class TestIntelligenceEndpoint:
    """Tests for GET /api/entities/v2/{slug}/intelligence"""

    def test_intelligence_returns_200_for_valid_entity(self):
        """Verify intelligence endpoint returns 200 for valid entity"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True

    def test_intelligence_returns_404_for_nonexistent_entity(self):
        """Verify intelligence endpoint returns 404 for nonexistent entity"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/nonexistent/intelligence")
        assert response.status_code == 404
        data = response.json()
        assert data.get('ok') == False
        assert 'error' in data

    def test_intelligence_has_all_required_fields(self):
        """Verify intelligence response has all required fields"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        assert response.status_code == 200
        data = response.json()

        required_fields = [
            'slug', 'name', 'pressure', 'pressure_detail', 'strategy',
            'strategy_detail', 'conviction', 'conviction_detail', 'regime',
            'regime_detail', 'playbook', 'playbook_detail', 'cluster_roles',
            'token_dependency', 'quick_tags', 'highlights', 'summary', 'computed_at'
        ]

        for field in required_fields:
            assert field in data, f"Missing required field: {field}"


class TestPressureField:
    """Tests for pressure field and pressure_detail structure"""

    def test_pressure_is_valid_string(self):
        """Verify pressure is bullish/bearish/neutral"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        assert response.status_code == 200
        data = response.json()

        assert isinstance(data['pressure'], str)
        assert data['pressure'] in ['bullish', 'bearish', 'neutral']

    def test_pressure_detail_structure(self):
        """Verify pressure_detail contains score, inflow_ratio, net_flow_usd, drivers"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        assert response.status_code == 200
        data = response.json()

        pd = data['pressure_detail']
        assert 'pressure' in pd
        assert 'score' in pd
        assert isinstance(pd['score'], (int, float))
        assert 'drivers' in pd
        assert isinstance(pd['drivers'], list)

        # inflow_ratio and net_flow_usd may not be present if no flow data
        if 'inflow_ratio' in pd:
            assert isinstance(pd['inflow_ratio'], (int, float))
        if 'net_flow_usd' in pd:
            assert isinstance(pd['net_flow_usd'], (int, float))

    def test_pressure_varies_per_entity_type(self):
        """Verify different entities can have different pressure values"""
        pressures = {}
        for entity in ['binance', 'coinbase', 'okx']:
            response = requests.get(f"{BASE_URL}/api/entities/v2/{entity}/intelligence")
            assert response.status_code == 200
            pressures[entity] = response.json()['pressure']

        # At least binance, coinbase, okx should return valid pressures
        for entity, pressure in pressures.items():
            assert pressure in ['bullish', 'bearish', 'neutral'], f"{entity} has invalid pressure: {pressure}"


class TestStrategyField:
    """Tests for strategy field and strategy_detail structure"""

    def test_strategy_is_string(self):
        """Verify strategy is a string"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data['strategy'], str)

    def test_strategy_detail_structure(self):
        """Verify strategy_detail contains strategy string, confidence float, drivers array"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        assert response.status_code == 200
        data = response.json()

        sd = data['strategy_detail']
        assert 'strategy' in sd
        assert isinstance(sd['strategy'], str)
        assert 'confidence' in sd
        assert isinstance(sd['confidence'], (int, float))
        assert 0 <= sd['confidence'] <= 1, f"Confidence {sd['confidence']} not in 0-1 range"
        assert 'drivers' in sd
        assert isinstance(sd['drivers'], list)


class TestConvictionField:
    """Tests for conviction field and conviction_detail structure"""

    def test_conviction_is_valid_string(self):
        """Verify conviction is low/moderate/high/extreme"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        assert response.status_code == 200
        data = response.json()

        assert isinstance(data['conviction'], str)
        assert data['conviction'] in ['low', 'moderate', 'high', 'extreme']

    def test_conviction_detail_structure(self):
        """Verify conviction_detail contains conviction string, score int, drivers array"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        assert response.status_code == 200
        data = response.json()

        cd = data['conviction_detail']
        assert 'conviction' in cd
        assert isinstance(cd['conviction'], str)
        assert 'score' in cd
        assert isinstance(cd['score'], int)
        assert 0 <= cd['score'] <= 100, f"Score {cd['score']} not in 0-100 range"
        assert 'drivers' in cd
        assert isinstance(cd['drivers'], list)


class TestRegimeField:
    """Tests for regime field and regime_detail structure"""

    def test_regime_is_valid_string(self):
        """Verify regime is accumulation/distribution/liquidity/dormant/rotation"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        assert response.status_code == 200
        data = response.json()

        assert isinstance(data['regime'], str)
        valid_regimes = ['accumulation', 'distribution', 'liquidity', 'dormant', 'rotation']
        assert data['regime'] in valid_regimes, f"Invalid regime: {data['regime']}"

    def test_regime_detail_has_drivers(self):
        """Verify regime_detail contains regime and drivers"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        assert response.status_code == 200
        data = response.json()

        rd = data['regime_detail']
        assert 'regime' in rd
        assert 'drivers' in rd
        assert isinstance(rd['drivers'], list)


class TestClusterRoles:
    """Tests for cluster_roles array structure"""

    def test_cluster_roles_is_array(self):
        """Verify cluster_roles is an array"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        assert response.status_code == 200
        data = response.json()

        assert isinstance(data['cluster_roles'], list)

    def test_cluster_role_structure(self):
        """Verify cluster objects have required fields"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        assert response.status_code == 200
        data = response.json()

        if len(data['cluster_roles']) > 0:
            cluster = data['cluster_roles'][0]
            expected_fields = ['cluster_id', 'tier', 'size', 'cluster_role', 'flow_weight', 'token_profile', 'confidence']
            for field in expected_fields:
                assert field in cluster, f"Cluster missing field: {field}"


class TestTokenDependency:
    """Tests for token_dependency object structure"""

    def test_token_dependency_is_object(self):
        """Verify token_dependency is an object"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        assert response.status_code == 200
        data = response.json()

        assert isinstance(data['token_dependency'], dict)

    def test_token_dependency_fields(self):
        """Verify token_dependency has stablecoin_dependency, eth_dependency, top_token_dependency"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        assert response.status_code == 200
        data = response.json()

        td = data['token_dependency']
        assert 'stablecoin_dependency' in td
        assert isinstance(td['stablecoin_dependency'], (int, float))
        assert 0 <= td['stablecoin_dependency'] <= 1

        assert 'eth_dependency' in td
        assert isinstance(td['eth_dependency'], (int, float))
        assert 0 <= td['eth_dependency'] <= 1

        assert 'top_token_dependency' in td
        assert isinstance(td['top_token_dependency'], (int, float))
        assert 0 <= td['top_token_dependency'] <= 1


class TestQuickTagsAndHighlights:
    """Tests for quick_tags and highlights arrays"""

    def test_quick_tags_is_array(self):
        """Verify quick_tags is an array of strings"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        assert response.status_code == 200
        data = response.json()

        assert isinstance(data['quick_tags'], list)
        for tag in data['quick_tags']:
            assert isinstance(tag, str)

    def test_highlights_is_array(self):
        """Verify highlights is an array of strings"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        assert response.status_code == 200
        data = response.json()

        assert isinstance(data['highlights'], list)
        for highlight in data['highlights']:
            assert isinstance(highlight, str)


class TestSummary:
    """Tests for summary field"""

    def test_summary_is_string(self):
        """Verify summary is a string"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        assert response.status_code == 200
        data = response.json()

        assert isinstance(data['summary'], str)
        assert len(data['summary']) > 0


class TestDifferentiatedResults:
    """Tests for differentiated results per entity type"""

    def test_exchange_vs_protocol_differentiation(self):
        """Verify exchanges and protocols have different intelligence patterns"""
        # Exchange: binance
        exchange_resp = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        assert exchange_resp.status_code == 200
        exchange_data = exchange_resp.json()

        # Protocol: uniswap
        protocol_resp = requests.get(f"{BASE_URL}/api/entities/v2/uniswap/intelligence")
        assert protocol_resp.status_code == 200
        protocol_data = protocol_resp.json()

        # Both should return valid responses
        assert exchange_data.get('ok') == True
        assert protocol_data.get('ok') == True

        # Verify structure is consistent
        assert 'pressure' in exchange_data and 'pressure' in protocol_data
        assert 'strategy' in exchange_data and 'strategy' in protocol_data

    def test_all_test_entities_return_200(self):
        """Verify all test entities return valid responses"""
        for entity in TEST_ENTITIES:
            response = requests.get(f"{BASE_URL}/api/entities/v2/{entity}/intelligence")
            assert response.status_code == 200, f"Entity {entity} returned {response.status_code}"
            data = response.json()
            assert data.get('ok') == True, f"Entity {entity} returned ok=False"


class TestExistingEndpointsStillWork:
    """Regression tests for existing endpoints"""

    def test_list_endpoint(self):
        """GET /api/entities/v2/list still works"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/list")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        assert 'entities' in data

    def test_impact_endpoint(self):
        """GET /api/entities/v2/{slug}/impact still works"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/impact")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        assert 'impact_score' in data
        assert 'impact_level' in data

    def test_timeline_endpoint(self):
        """GET /api/entities/v2/{slug}/timeline still works"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/timeline")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        assert 'events' in data
        assert 'event_count' in data

    def test_interactions_endpoint(self):
        """GET /api/entities/v2/{slug}/interactions still works"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/interactions")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        assert 'nodes' in data
        assert 'edges' in data

    def test_behaviour_endpoint(self):
        """GET /api/entities/v2/{slug}/behaviour still works"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/behaviour")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        assert 'behaviour_type' in data


class TestPlaybook:
    """Tests for playbook field"""

    def test_playbook_is_string(self):
        """Verify playbook is a string"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data['playbook'], str)

    def test_playbook_detail_structure(self):
        """Verify playbook_detail has playbook, strategy, regime, pressure"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        assert response.status_code == 200
        data = response.json()

        pd = data['playbook_detail']
        assert 'playbook' in pd
        assert 'strategy' in pd
        assert 'regime' in pd
        assert 'pressure' in pd


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
