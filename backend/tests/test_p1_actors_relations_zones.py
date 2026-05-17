"""
P1.1, P1.2, P1.5 API Tests - Actors V2, Relations V2, Zones
Tests for network-aware actor queries, relations/corridors, and accumulation/distribution zones.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestActorsV2API:
    """P1.1 - Actors V2 API Tests (Network-aware)"""
    
    def test_actors_list_with_network(self):
        """GET /api/v2/actors?network=ethereum - list actors with flow roles"""
        response = requests.get(f"{BASE_URL}/api/v2/actors?network=ethereum&limit=10")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        assert 'actors' in data['data']
        assert 'pagination' in data['data']
        assert 'meta' in data['data']
        
        # Verify actor structure
        if len(data['data']['actors']) > 0:
            actor = data['data']['actors'][0]
            assert 'actorId' in actor
            assert 'network' in actor
            assert 'flowRole' in actor
            assert actor['flowRole'] in ['ACCUMULATOR', 'DISTRIBUTOR', 'ROUTER', 'INACTIVE']
            assert 'inflowCount' in actor
            assert 'outflowCount' in actor
            assert 'netFlow' in actor
            assert 'transactionCount' in actor
            assert 'uniqueCounterparties' in actor
            assert 'flowRoleConfidence' in actor
        
        # Verify pagination
        assert 'total' in data['data']['pagination']
        assert 'limit' in data['data']['pagination']
        assert 'hasMore' in data['data']['pagination']
        
        # Verify meta
        assert data['data']['meta']['network'] == 'ethereum'
    
    def test_actors_list_without_network_returns_400(self):
        """GET /api/v2/actors (without network) returns 400 NETWORK_REQUIRED"""
        response = requests.get(f"{BASE_URL}/api/v2/actors")
        assert response.status_code == 400
        
        data = response.json()
        assert data['ok'] is False
        assert data['error'] == 'NETWORK_REQUIRED'
    
    def test_actors_list_invalid_network_returns_400(self):
        """GET /api/v2/actors?network=invalid returns 400 NETWORK_INVALID"""
        response = requests.get(f"{BASE_URL}/api/v2/actors?network=invalid")
        assert response.status_code == 400
        
        data = response.json()
        assert data['ok'] is False
        assert data['error'] == 'NETWORK_INVALID'
    
    def test_actors_filter_by_flow_role(self):
        """GET /api/v2/actors?network=ethereum&flowRole=ACCUMULATOR - filter by role"""
        response = requests.get(f"{BASE_URL}/api/v2/actors?network=ethereum&flowRole=ACCUMULATOR&limit=5")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        
        # All actors should be accumulators
        for actor in data['data']['actors']:
            assert actor['flowRole'] == 'ACCUMULATOR'
    
    def test_actors_stats_summary(self):
        """GET /api/v2/actors/stats/summary?network=ethereum - actor statistics"""
        response = requests.get(f"{BASE_URL}/api/v2/actors/stats/summary?network=ethereum")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        assert 'network' in data['data']
        assert 'window' in data['data']
        assert 'total' in data['data']
        assert 'byFlowRole' in data['data']
        
        # Verify flow role breakdown
        roles = {r['role'] for r in data['data']['byFlowRole']}
        assert 'ACCUMULATOR' in roles or 'DISTRIBUTOR' in roles or 'ROUTER' in roles
        
        for role_stat in data['data']['byFlowRole']:
            assert 'role' in role_stat
            assert 'count' in role_stat
            assert 'percentage' in role_stat
            assert 'avgNetFlow' in role_stat
            assert 'avgTxCount' in role_stat
    
    def test_actors_stats_summary_without_network_returns_400(self):
        """GET /api/v2/actors/stats/summary (without network) returns 400"""
        response = requests.get(f"{BASE_URL}/api/v2/actors/stats/summary")
        assert response.status_code == 400
        
        data = response.json()
        assert data['ok'] is False
        assert data['error'] == 'NETWORK_REQUIRED'
    
    def test_actor_detail_by_address(self):
        """GET /api/v2/actors/:address?network=ethereum - get actor detail"""
        # First get an actor address from the list
        list_response = requests.get(f"{BASE_URL}/api/v2/actors?network=ethereum&limit=1")
        assert list_response.status_code == 200
        
        actors = list_response.json()['data']['actors']
        if len(actors) == 0:
            pytest.skip("No actors available for testing")
        
        address = actors[0]['actorId']
        
        # Get actor detail
        response = requests.get(f"{BASE_URL}/api/v2/actors/{address}?network=ethereum")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        assert data['data']['address'] == address
        assert data['data']['network'] == 'ethereum'
        assert 'score' in data['data']
        
        if data['data']['score']:
            score = data['data']['score']
            assert 'inflowCount' in score
            assert 'outflowCount' in score
            assert 'netFlow' in score
            assert 'flowRole' in score
            assert 'flowRoleConfidence' in score
    
    def test_actor_detail_without_network_returns_400(self):
        """GET /api/v2/actors/:address (without network) returns 400"""
        response = requests.get(f"{BASE_URL}/api/v2/actors/0x1234567890123456789012345678901234567890")
        assert response.status_code == 400
        
        data = response.json()
        assert data['ok'] is False
        assert data['error'] == 'NETWORK_REQUIRED'


class TestRelationsV2API:
    """P1.2 - Relations V2 API Tests (Network-aware)"""
    
    def test_relations_list_with_network(self):
        """GET /api/v2/relations?network=ethereum - list top relations"""
        response = requests.get(f"{BASE_URL}/api/v2/relations?network=ethereum&limit=10")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        assert 'relations' in data['data']
        assert 'pagination' in data['data']
        assert 'meta' in data['data']
        
        # Verify relation structure
        if len(data['data']['relations']) > 0:
            relation = data['data']['relations'][0]
            assert 'id' in relation
            assert 'from' in relation
            assert 'to' in relation
            assert 'network' in relation
            assert 'interactionCount' in relation
            assert 'densityScore' in relation
            assert 'direction' in relation
        
        # Verify meta
        assert data['data']['meta']['network'] == 'ethereum'
    
    def test_relations_list_without_network_returns_400(self):
        """GET /api/v2/relations (without network) returns 400 NETWORK_REQUIRED"""
        response = requests.get(f"{BASE_URL}/api/v2/relations")
        assert response.status_code == 400
        
        data = response.json()
        assert data['ok'] is False
        assert data['error'] == 'NETWORK_REQUIRED'
    
    def test_relations_list_invalid_network_returns_400(self):
        """GET /api/v2/relations?network=invalid returns 400 NETWORK_INVALID"""
        response = requests.get(f"{BASE_URL}/api/v2/relations?network=invalid")
        assert response.status_code == 400
        
        data = response.json()
        assert data['ok'] is False
        assert data['error'] == 'NETWORK_INVALID'
    
    def test_relations_for_address(self):
        """GET /api/v2/relations/address/:address?network=ethereum - relations for address"""
        # First get an actor address
        actors_response = requests.get(f"{BASE_URL}/api/v2/actors?network=ethereum&limit=1")
        assert actors_response.status_code == 200
        
        actors = actors_response.json()['data']['actors']
        if len(actors) == 0:
            pytest.skip("No actors available for testing")
        
        address = actors[0]['actorId']
        
        # Get relations for address
        response = requests.get(f"{BASE_URL}/api/v2/relations/address/{address}?network=ethereum&limit=10")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        assert data['data']['address'] == address
        assert data['data']['network'] == 'ethereum'
        assert 'summary' in data['data']
        assert 'relations' in data['data']
        
        # Verify summary structure
        summary = data['data']['summary']
        assert 'totalRelations' in summary
        assert 'inboundCount' in summary
        assert 'outboundCount' in summary
        assert 'totalInteractions' in summary
        assert 'avgDensity' in summary
    
    def test_relations_for_address_without_network_returns_400(self):
        """GET /api/v2/relations/address/:address (without network) returns 400"""
        response = requests.get(f"{BASE_URL}/api/v2/relations/address/0x1234567890123456789012345678901234567890")
        assert response.status_code == 400
        
        data = response.json()
        assert data['ok'] is False
        assert data['error'] == 'NETWORK_REQUIRED'
    
    def test_relations_stats(self):
        """GET /api/v2/relations/stats?network=ethereum - relation statistics"""
        response = requests.get(f"{BASE_URL}/api/v2/relations/stats?network=ethereum")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        assert data['data']['network'] == 'ethereum'
        assert 'totalRelations' in data['data']
        assert 'totalInteractions' in data['data']
        assert 'uniqueAddresses' in data['data']
        assert 'avgDensity' in data['data']
        assert 'maxDensity' in data['data']
        assert 'densityDistribution' in data['data']
        
        # Verify density distribution structure
        for bucket in data['data']['densityDistribution']:
            assert 'bucket' in bucket
            assert 'count' in bucket
    
    def test_relations_stats_without_network_returns_400(self):
        """GET /api/v2/relations/stats (without network) returns 400"""
        response = requests.get(f"{BASE_URL}/api/v2/relations/stats")
        assert response.status_code == 400
        
        data = response.json()
        assert data['ok'] is False
        assert data['error'] == 'NETWORK_REQUIRED'


class TestZonesAPI:
    """P1.5 - Accumulation/Distribution Zones API Tests"""
    
    def test_zones_list_with_network(self):
        """GET /api/v2/zones?network=ethereum - list accumulation/distribution zones"""
        response = requests.get(f"{BASE_URL}/api/v2/zones?network=ethereum&limit=10")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        assert 'zones' in data['data']
        assert 'pagination' in data['data']
        assert 'meta' in data['data']
        
        # Verify zone structure
        if len(data['data']['zones']) > 0:
            zone = data['data']['zones'][0]
            assert 'zoneId' in zone
            assert 'type' in zone
            assert zone['type'] in ['ACCUMULATION', 'DISTRIBUTION', 'MIXED']
            assert 'strength' in zone
            assert zone['strength'] in ['STRONG', 'MODERATE', 'WEAK']
            assert 'coreAddresses' in zone
            assert 'netFlow' in zone
            assert 'flowRatio' in zone
            assert 'totalTxCount' in zone
            assert 'confidence' in zone
        
        # Verify meta
        assert data['data']['meta']['network'] == 'ethereum'
    
    def test_zones_list_without_network_returns_400(self):
        """GET /api/v2/zones (without network) returns 400 NETWORK_REQUIRED"""
        response = requests.get(f"{BASE_URL}/api/v2/zones")
        assert response.status_code == 400
        
        data = response.json()
        assert data['ok'] is False
        assert data['error'] == 'NETWORK_REQUIRED'
    
    def test_zones_list_invalid_network_returns_400(self):
        """GET /api/v2/zones?network=invalid returns 400 NETWORK_INVALID"""
        response = requests.get(f"{BASE_URL}/api/v2/zones?network=invalid")
        assert response.status_code == 400
        
        data = response.json()
        assert data['ok'] is False
        assert data['error'] == 'NETWORK_INVALID'
    
    def test_zones_filter_by_type(self):
        """GET /api/v2/zones?network=ethereum&type=ACCUMULATION - filter by zone type"""
        response = requests.get(f"{BASE_URL}/api/v2/zones?network=ethereum&type=ACCUMULATION&limit=5")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        
        # All zones should be accumulation type
        for zone in data['data']['zones']:
            assert zone['type'] == 'ACCUMULATION'
    
    def test_zones_signal(self):
        """GET /api/v2/zones/signal?network=ethereum - get market signal from zones"""
        response = requests.get(f"{BASE_URL}/api/v2/zones/signal?network=ethereum")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        assert data['data']['network'] == 'ethereum'
        assert 'signal' in data['data']
        assert data['data']['signal'] in ['STRONG_ACCUMULATION', 'ACCUMULATION', 'NEUTRAL', 'DISTRIBUTION', 'STRONG_DISTRIBUTION']
        assert 'signalStrength' in data['data']
        assert 'breakdown' in data['data']
        assert 'interpretation' in data['data']
        
        # Verify breakdown structure
        breakdown = data['data']['breakdown']
        assert 'accumulation' in breakdown
        assert 'distribution' in breakdown
        
        for zone_type in ['accumulation', 'distribution']:
            assert 'total' in breakdown[zone_type]
            assert 'strong' in breakdown[zone_type]
            assert 'moderate' in breakdown[zone_type]
            assert 'score' in breakdown[zone_type]
    
    def test_zones_signal_without_network_returns_400(self):
        """GET /api/v2/zones/signal (without network) returns 400"""
        response = requests.get(f"{BASE_URL}/api/v2/zones/signal")
        assert response.status_code == 400
        
        data = response.json()
        assert data['ok'] is False
        assert data['error'] == 'NETWORK_REQUIRED'
    
    def test_zone_check_address_in_zone(self):
        """GET /api/v2/zones/:address?network=ethereum - check if address is in zone"""
        # First get a zone with an address
        zones_response = requests.get(f"{BASE_URL}/api/v2/zones?network=ethereum&limit=1")
        assert zones_response.status_code == 200
        
        zones = zones_response.json()['data']['zones']
        if len(zones) == 0:
            pytest.skip("No zones available for testing")
        
        address = zones[0]['coreAddresses'][0]
        
        # Check if address is in zone
        response = requests.get(f"{BASE_URL}/api/v2/zones/{address}?network=ethereum")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        assert data['data']['address'] == address
        assert data['data']['network'] == 'ethereum'
        assert data['data']['inZone'] is True
        assert 'zone' in data['data']
        
        zone = data['data']['zone']
        assert 'zoneId' in zone
        assert 'type' in zone
        assert 'strength' in zone
        assert 'netFlow' in zone
        assert 'confidence' in zone
    
    def test_zone_check_address_not_in_zone(self):
        """GET /api/v2/zones/:address?network=ethereum - address not in any zone"""
        response = requests.get(f"{BASE_URL}/api/v2/zones/0xnonexistent?network=ethereum")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        assert data['data']['inZone'] is False
        assert data['data']['zone'] is None
    
    def test_zone_check_address_without_network_returns_400(self):
        """GET /api/v2/zones/:address (without network) returns 400"""
        response = requests.get(f"{BASE_URL}/api/v2/zones/0x1234567890123456789012345678901234567890")
        assert response.status_code == 400
        
        data = response.json()
        assert data['ok'] is False
        assert data['error'] == 'NETWORK_REQUIRED'


class TestMultiNetworkSupport:
    """Test that all APIs support multiple networks"""
    
    NETWORKS = ['ethereum', 'arbitrum', 'optimism', 'base', 'polygon']
    
    def test_actors_supports_all_networks(self):
        """Actors V2 API supports all networks"""
        for network in self.NETWORKS:
            response = requests.get(f"{BASE_URL}/api/v2/actors?network={network}&limit=1")
            assert response.status_code == 200, f"Failed for network: {network}"
            assert response.json()['ok'] is True
            assert response.json()['data']['meta']['network'] == network
    
    def test_relations_supports_all_networks(self):
        """Relations V2 API supports all networks"""
        for network in self.NETWORKS:
            response = requests.get(f"{BASE_URL}/api/v2/relations?network={network}&limit=1")
            assert response.status_code == 200, f"Failed for network: {network}"
            assert response.json()['ok'] is True
            assert response.json()['data']['meta']['network'] == network
    
    def test_zones_supports_all_networks(self):
        """Zones API supports all networks"""
        for network in self.NETWORKS:
            response = requests.get(f"{BASE_URL}/api/v2/zones?network={network}&limit=1")
            assert response.status_code == 200, f"Failed for network: {network}"
            assert response.json()['ok'] is True
            assert response.json()['data']['meta']['network'] == network
    
    def test_zones_signal_supports_all_networks(self):
        """Zones signal API supports all networks"""
        for network in self.NETWORKS:
            response = requests.get(f"{BASE_URL}/api/v2/zones/signal?network={network}")
            assert response.status_code == 200, f"Failed for network: {network}"
            assert response.json()['ok'] is True
            assert response.json()['data']['network'] == network


class TestDataIntegrity:
    """Test data integrity and consistency across APIs"""
    
    def test_actor_score_consistency(self):
        """Actor scores are consistent (inflowCount + outflowCount = transactionCount)"""
        response = requests.get(f"{BASE_URL}/api/v2/actors?network=ethereum&limit=10")
        assert response.status_code == 200
        
        for actor in response.json()['data']['actors']:
            expected_tx_count = actor['inflowCount'] + actor['outflowCount']
            assert actor['transactionCount'] == expected_tx_count, \
                f"Transaction count mismatch for {actor['actorId']}"
    
    def test_zone_signal_breakdown_consistency(self):
        """Zone signal breakdown totals match zone counts"""
        response = requests.get(f"{BASE_URL}/api/v2/zones/signal?network=ethereum")
        assert response.status_code == 200
        
        data = response.json()['data']
        breakdown = data['breakdown']
        
        # Verify strong + moderate <= total for each type
        for zone_type in ['accumulation', 'distribution']:
            total = breakdown[zone_type]['total']
            strong = breakdown[zone_type]['strong']
            moderate = breakdown[zone_type]['moderate']
            assert strong + moderate <= total, \
                f"Strong + moderate exceeds total for {zone_type}"
    
    def test_relations_stats_consistency(self):
        """Relations stats are consistent"""
        response = requests.get(f"{BASE_URL}/api/v2/relations/stats?network=ethereum")
        assert response.status_code == 200
        
        data = response.json()['data']
        
        # Total interactions should be >= total relations
        assert data['totalInteractions'] >= data['totalRelations'], \
            "Total interactions should be >= total relations"
        
        # Avg density should be between 0 and max density
        assert 0 <= data['avgDensity'] <= data['maxDensity'], \
            "Avg density should be between 0 and max density"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
