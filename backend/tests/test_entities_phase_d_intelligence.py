"""
Entities V2 Phase D: Actor Intelligence Extensions
====================================================
Tests for 5 new backend features:
1. D1: Actor Impact Score - GET /api/entities/v2/{slug}/intelligence now includes actor_impact with impact_score, impact_category, components
2. D2: Strategy Drift Tracking - GET /api/entities/v2/{slug}/strategy-history returns adaptive snapshots
3. D3: Pressure by Token - GET /api/entities/v2/{slug}/token-pressure returns per-token pressure analysis
4. D4: Actor Interaction Map - GET /api/entities/v2/global/actor-flows returns cross-entity capital flows
5. D5: Actor vs Actor Pressure Map - GET /api/entities/v2/global/pressure-map returns bullish/bearish/neutral entities

Regression tests for existing endpoints.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test entities: exchanges, protocols
TEST_ENTITIES = ['binance', 'coinbase', 'uniswap', 'okx', 'kraken']


# ═══════════════════════════════════════════════════════════
# D1: ACTOR IMPACT SCORE (inside /intelligence endpoint)
# ═══════════════════════════════════════════════════════════
class TestD1ActorImpactScore:
    """Tests for actor_impact field in intelligence response"""

    def test_intelligence_has_actor_impact(self):
        """Verify intelligence endpoint includes actor_impact"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        assert response.status_code == 200
        data = response.json()
        assert 'actor_impact' in data, "Missing actor_impact in intelligence response"

    def test_actor_impact_has_impact_score(self):
        """Verify actor_impact has impact_score integer 0-100"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        assert response.status_code == 200
        data = response.json()
        
        ai = data['actor_impact']
        assert 'impact_score' in ai
        assert isinstance(ai['impact_score'], int)
        assert 0 <= ai['impact_score'] <= 100, f"impact_score {ai['impact_score']} not in 0-100"

    def test_actor_impact_has_impact_category(self):
        """Verify actor_impact has impact_category LOW/MEDIUM/HIGH/SYSTEMIC"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        assert response.status_code == 200
        data = response.json()
        
        ai = data['actor_impact']
        assert 'impact_category' in ai
        valid_categories = ['LOW', 'MEDIUM', 'HIGH', 'SYSTEMIC']
        assert ai['impact_category'] in valid_categories, f"Invalid category: {ai['impact_category']}"

    def test_actor_impact_has_components(self):
        """Verify actor_impact has components: portfolio, flow, cluster, velocity"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        assert response.status_code == 200
        data = response.json()
        
        ai = data['actor_impact']
        assert 'components' in ai
        components = ai['components']
        
        expected_keys = ['portfolio', 'flow', 'cluster', 'velocity']
        for key in expected_keys:
            assert key in components, f"Missing component: {key}"
            assert isinstance(components[key], int), f"Component {key} should be int"
            assert 0 <= components[key] <= 100, f"Component {key} value {components[key]} not in 0-100"

    def test_actor_impact_categories_match_thresholds(self):
        """Verify impact categories match thresholds: 0-25 LOW, 25-45 MEDIUM, 45-70 HIGH, 70+ SYSTEMIC"""
        for entity in TEST_ENTITIES:
            response = requests.get(f"{BASE_URL}/api/entities/v2/{entity}/intelligence")
            assert response.status_code == 200
            data = response.json()
            
            ai = data['actor_impact']
            score = ai['impact_score']
            category = ai['impact_category']
            
            if score >= 70:
                assert category == 'SYSTEMIC', f"{entity}: score {score} should be SYSTEMIC, got {category}"
            elif score >= 45:
                assert category == 'HIGH', f"{entity}: score {score} should be HIGH, got {category}"
            elif score >= 25:
                assert category == 'MEDIUM', f"{entity}: score {score} should be MEDIUM, got {category}"
            else:
                assert category == 'LOW', f"{entity}: score {score} should be LOW, got {category}"


# ═══════════════════════════════════════════════════════════
# D2: STRATEGY DRIFT TRACKING
# ═══════════════════════════════════════════════════════════
class TestD2StrategyHistory:
    """Tests for GET /api/entities/v2/{slug}/strategy-history"""

    def test_strategy_history_returns_200(self):
        """Verify strategy-history endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/strategy-history")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True

    def test_strategy_history_has_entity_slug(self):
        """Verify response includes entity slug"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/strategy-history")
        assert response.status_code == 200
        data = response.json()
        assert 'entity' in data
        assert data['entity'] == 'binance'

    def test_strategy_history_has_history_array(self):
        """Verify response includes history array"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/strategy-history")
        assert response.status_code == 200
        data = response.json()
        assert 'history' in data
        assert isinstance(data['history'], list)

    def test_strategy_history_has_count(self):
        """Verify response includes count"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/strategy-history")
        assert response.status_code == 200
        data = response.json()
        assert 'count' in data
        assert isinstance(data['count'], int)
        assert data['count'] == len(data['history'])

    def test_strategy_history_entry_structure(self):
        """Verify each history entry has strategy/pressure/regime/conviction"""
        # First call intelligence to ensure a snapshot is created
        intel_response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        assert intel_response.status_code == 200
        
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/strategy-history")
        assert response.status_code == 200
        data = response.json()
        
        if len(data['history']) > 0:
            entry = data['history'][0]
            assert 'strategy' in entry
            assert 'pressure' in entry
            assert 'regime' in entry
            assert 'conviction' in entry
            assert 'timestamp' in entry

    def test_strategy_history_respects_limit(self):
        """Verify limit parameter works"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/strategy-history?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data['history']) <= 5


# ═══════════════════════════════════════════════════════════
# D3: PRESSURE BY TOKEN (intelligence + token-pressure endpoint)
# ═══════════════════════════════════════════════════════════
class TestD3TokenPressure:
    """Tests for token_pressure in intelligence and /token-pressure endpoint"""

    def test_intelligence_has_token_pressure(self):
        """Verify intelligence endpoint includes token_pressure array"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        assert response.status_code == 200
        data = response.json()
        assert 'token_pressure' in data
        assert isinstance(data['token_pressure'], list)

    def test_token_pressure_endpoint_returns_200(self):
        """Verify /token-pressure endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/token-pressure")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True

    def test_token_pressure_endpoint_has_tokens_array(self):
        """Verify /token-pressure returns tokens array"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/token-pressure")
        assert response.status_code == 200
        data = response.json()
        assert 'tokens' in data
        assert isinstance(data['tokens'], list)
        assert 'count' in data

    def test_token_pressure_entry_structure(self):
        """Verify token pressure entry has symbol, pressure, score, role, dominance"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/token-pressure")
        assert response.status_code == 200
        data = response.json()
        
        if len(data['tokens']) > 0:
            token = data['tokens'][0]
            assert 'symbol' in token
            assert 'pressure' in token
            assert token['pressure'] in ['bullish', 'bearish', 'neutral']
            assert 'score' in token
            assert 'role' in token
            assert 'dominance' in token
            assert isinstance(token['dominance'], (int, float))

    def test_token_pressure_returns_404_for_nonexistent(self):
        """Verify /token-pressure returns 404 for nonexistent entity"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/nonexistent/token-pressure")
        assert response.status_code == 404
        data = response.json()
        assert data.get('ok') == False


# ═══════════════════════════════════════════════════════════
# D4: ACTOR INTERACTION MAP (global/actor-flows)
# ═══════════════════════════════════════════════════════════
class TestD4ActorFlows:
    """Tests for GET /api/entities/v2/global/actor-flows"""

    def test_actor_flows_returns_200(self):
        """Verify /global/actor-flows returns 200"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/global/actor-flows")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True

    def test_actor_flows_has_interactions_array(self):
        """Verify response has interactions array"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/global/actor-flows")
        assert response.status_code == 200
        data = response.json()
        assert 'interactions' in data
        assert isinstance(data['interactions'], list)

    def test_actor_flows_has_counts(self):
        """Verify response has entity_count and total_interactions"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/global/actor-flows")
        assert response.status_code == 200
        data = response.json()
        assert 'entity_count' in data
        assert 'total_interactions' in data
        assert isinstance(data['entity_count'], int)
        assert isinstance(data['total_interactions'], int)

    def test_actor_flow_entry_structure(self):
        """Verify each interaction has from/to/volume/type fields"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/global/actor-flows")
        assert response.status_code == 200
        data = response.json()
        
        if len(data['interactions']) > 0:
            flow = data['interactions'][0]
            # Required fields
            assert 'from' in flow
            assert 'from_name' in flow
            assert 'to' in flow
            assert 'to_name' in flow
            assert 'type' in flow


# ═══════════════════════════════════════════════════════════
# D5: ACTOR vs ACTOR PRESSURE MAP
# ═══════════════════════════════════════════════════════════
class TestD5PressureMap:
    """Tests for GET /api/entities/v2/global/pressure-map"""

    def test_pressure_map_returns_200(self):
        """Verify /global/pressure-map returns 200"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/global/pressure-map")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True

    def test_pressure_map_has_entity_arrays(self):
        """Verify response has bullish_entities, bearish_entities, neutral_entities"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/global/pressure-map")
        assert response.status_code == 200
        data = response.json()
        
        assert 'bullish_entities' in data
        assert 'bearish_entities' in data
        assert 'neutral_entities' in data
        
        assert isinstance(data['bullish_entities'], list)
        assert isinstance(data['bearish_entities'], list)
        assert isinstance(data['neutral_entities'], list)

    def test_pressure_map_has_counts(self):
        """Verify response has total, bullish, bearish, neutral counts"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/global/pressure-map")
        assert response.status_code == 200
        data = response.json()
        
        assert 'total_entities' in data
        assert 'bullish_count' in data
        assert 'bearish_count' in data
        assert 'neutral_count' in data
        
        # Counts should match array lengths
        assert data['bullish_count'] == len(data['bullish_entities'])
        assert data['bearish_count'] == len(data['bearish_entities'])
        assert data['neutral_count'] == len(data['neutral_entities'])
        
        # Total should equal sum
        assert data['total_entities'] == data['bullish_count'] + data['bearish_count'] + data['neutral_count']

    def test_pressure_map_entity_structure(self):
        """Verify each entity entry has required fields with impact weight"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/global/pressure-map")
        assert response.status_code == 200
        data = response.json()
        
        # Check first entity from any non-empty list
        all_entities = data['bullish_entities'] + data['bearish_entities'] + data['neutral_entities']
        if len(all_entities) > 0:
            entity = all_entities[0]
            assert 'entity' in entity  # slug
            assert 'name' in entity
            assert 'pressure' in entity
            assert 'impact' in entity  # impact_category
            assert 'impact_score' in entity

    def test_pressure_map_sorted_by_impact(self):
        """Verify entities are sorted by impact_score descending"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/global/pressure-map")
        assert response.status_code == 200
        data = response.json()
        
        for key in ['bullish_entities', 'bearish_entities', 'neutral_entities']:
            entities = data[key]
            if len(entities) > 1:
                for i in range(len(entities) - 1):
                    assert entities[i]['impact_score'] >= entities[i+1]['impact_score'], \
                        f"{key} not sorted: {entities[i]['impact_score']} < {entities[i+1]['impact_score']}"


# ═══════════════════════════════════════════════════════════
# REGRESSION TESTS - Existing Endpoints
# ═══════════════════════════════════════════════════════════
class TestRegressionExistingEndpoints:
    """Verify all existing endpoints still work"""

    def test_list_endpoint(self):
        """GET /api/entities/v2/list still works"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/list")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        assert 'entities' in data

    def test_entity_detail_endpoint(self):
        """GET /api/entities/v2/{slug} still works"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        assert 'entity' in data

    def test_impact_endpoint(self):
        """GET /api/entities/v2/{slug}/impact still works"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/impact")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        assert 'impact_score' in data

    def test_timeline_endpoint(self):
        """GET /api/entities/v2/{slug}/timeline still works"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/timeline")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        assert 'events' in data

    def test_interactions_endpoint(self):
        """GET /api/entities/v2/{slug}/interactions still works"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/interactions")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        assert 'nodes' in data

    def test_intelligence_endpoint(self):
        """GET /api/entities/v2/{slug}/intelligence still works"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/intelligence")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        assert 'pressure' in data
        assert 'strategy' in data

    def test_behaviour_endpoint(self):
        """GET /api/entities/v2/{slug}/behaviour still works"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/behaviour")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True

    def test_holdings_endpoint(self):
        """GET /api/entities/v2/{slug}/holdings still works"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/holdings")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True

    def test_flows_endpoint(self):
        """GET /api/entities/v2/{slug}/flows still works"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/flows")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True

    def test_clusters_endpoint(self):
        """GET /api/entities/v2/{slug}/clusters still works"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/clusters")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True

    def test_similar_endpoint(self):
        """GET /api/entities/v2/{slug}/similar still works"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/similar")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True

    def test_chains_endpoint(self):
        """GET /api/entities/v2/{slug}/chains still works"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/binance/chains")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True

    def test_discovery_endpoint(self):
        """GET /api/entities/v2/discovery still works"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/discovery")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True


# ═══════════════════════════════════════════════════════════
# 404 ERROR HANDLING TESTS
# ═══════════════════════════════════════════════════════════
class Test404ErrorHandling:
    """Verify 404 handling for nonexistent entities"""

    def test_intelligence_404(self):
        """GET /api/entities/v2/nonexistent/intelligence returns 404"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/nonexistent/intelligence")
        assert response.status_code == 404
        data = response.json()
        assert data.get('ok') == False

    def test_strategy_history_returns_empty_for_nonexistent(self):
        """GET /api/entities/v2/nonexistent/strategy-history returns 200 with empty history"""
        # Note: strategy-history may return 200 with empty array rather than 404
        response = requests.get(f"{BASE_URL}/api/entities/v2/nonexistent/strategy-history")
        # Either 404 or 200 with empty history is acceptable
        if response.status_code == 200:
            data = response.json()
            assert data.get('ok') == True
            assert data.get('count', 0) == 0 or len(data.get('history', [])) == 0
        else:
            assert response.status_code == 404

    def test_token_pressure_404(self):
        """GET /api/entities/v2/nonexistent/token-pressure returns 404"""
        response = requests.get(f"{BASE_URL}/api/entities/v2/nonexistent/token-pressure")
        assert response.status_code == 404


# ═══════════════════════════════════════════════════════════
# ALL ENTITIES VALIDATION
# ═══════════════════════════════════════════════════════════
class TestAllEntitiesPhaseD:
    """Verify Phase D features work for all test entities"""

    def test_all_entities_intelligence_with_actor_impact(self):
        """Verify all entities have actor_impact in intelligence"""
        for entity in TEST_ENTITIES:
            response = requests.get(f"{BASE_URL}/api/entities/v2/{entity}/intelligence")
            assert response.status_code == 200, f"{entity} intelligence failed"
            data = response.json()
            assert 'actor_impact' in data, f"{entity} missing actor_impact"
            assert 'impact_score' in data['actor_impact']
            assert 'impact_category' in data['actor_impact']

    def test_all_entities_token_pressure(self):
        """Verify all entities return token_pressure"""
        for entity in TEST_ENTITIES:
            response = requests.get(f"{BASE_URL}/api/entities/v2/{entity}/token-pressure")
            assert response.status_code == 200, f"{entity} token-pressure failed"
            data = response.json()
            assert 'tokens' in data

    def test_all_entities_strategy_history(self):
        """Verify all entities return strategy-history"""
        for entity in TEST_ENTITIES:
            response = requests.get(f"{BASE_URL}/api/entities/v2/{entity}/strategy-history")
            assert response.status_code == 200, f"{entity} strategy-history failed"
            data = response.json()
            assert 'history' in data


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
