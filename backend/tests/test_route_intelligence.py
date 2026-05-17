"""
Route Intelligence API Tests (P0.3)

Tests for Bridge & Route Intelligence v2 module:
- Route listing with filtering
- Route retrieval by ID with segments
- Routes by wallet address
- EXIT routes (potential dumps)
- High-risk routes detection
- Route statistics
- Wallet dump pattern analysis
- Route segments retrieval
- Seed test data
- Build routes from events
- Recompute route metrics
- Delete routes
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test wallets from seeded data
TEST_WALLETS = [
    '0x742d35cc6634c0532925a3b844bc454e4438f44e',
    '0x8ba1f109551bd432803012645ac136ddd64dba72',
    '0xd8da6bf26964af9d7eed9e03e53415d37aa96045'
]

# Test route IDs
TEST_ROUTE_IDS = [
    'ROUTE:TEST:EXIT:001',
    'ROUTE:TEST:EXIT:002',
    'ROUTE:TEST:MIGRATION:001'
]


@pytest.fixture(scope='module')
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({'Content-Type': 'application/json'})
    return session


@pytest.fixture(scope='module', autouse=True)
def seed_test_data(api_client):
    """Seed test data before running tests"""
    response = api_client.post(f'{BASE_URL}/api/routes/seed', json={})
    assert response.status_code == 200, f"Seed failed: {response.text}"
    data = response.json()
    assert data['ok'] is True
    assert data['data']['routes'] == 3
    assert data['data']['segments'] == 8
    print(f"Seeded {data['data']['routes']} routes and {data['data']['segments']} segments")
    yield
    # Cleanup is handled by seed which deletes existing test data


class TestRouteListEndpoint:
    """GET /api/routes - List routes with filtering"""
    
    def test_list_routes_default(self, api_client):
        """Test listing routes with default parameters"""
        response = api_client.get(f'{BASE_URL}/api/routes')
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        assert 'routes' in data['data']
        assert 'count' in data['data']
        assert 'offset' in data['data']
        assert 'limit' in data['data']
        assert data['data']['offset'] == 0
        assert data['data']['limit'] == 100
        
    def test_list_routes_filter_by_type(self, api_client):
        """Test filtering routes by type"""
        response = api_client.get(f'{BASE_URL}/api/routes?type=EXIT')
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        routes = data['data']['routes']
        # All returned routes should be EXIT type
        for route in routes:
            assert route['routeType'] == 'EXIT'
            
    def test_list_routes_filter_by_status(self, api_client):
        """Test filtering routes by status"""
        response = api_client.get(f'{BASE_URL}/api/routes?status=COMPLETE')
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        routes = data['data']['routes']
        for route in routes:
            assert route['status'] == 'COMPLETE'
            
    def test_list_routes_filter_by_min_confidence(self, api_client):
        """Test filtering routes by minimum confidence"""
        response = api_client.get(f'{BASE_URL}/api/routes?minConfidence=0.9')
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        routes = data['data']['routes']
        for route in routes:
            assert route['confidenceScore'] >= 0.9
            
    def test_list_routes_with_pagination(self, api_client):
        """Test pagination parameters"""
        response = api_client.get(f'{BASE_URL}/api/routes?limit=2&offset=0')
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        assert data['data']['limit'] == 2
        assert data['data']['offset'] == 0
        assert len(data['data']['routes']) <= 2
        
    def test_list_routes_filter_by_chain(self, api_client):
        """Test filtering routes by chain"""
        response = api_client.get(f'{BASE_URL}/api/routes?chain=ETH')
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        routes = data['data']['routes']
        for route in routes:
            assert 'ETH' in route['chainsInvolved']


class TestRouteByIdEndpoint:
    """GET /api/routes/:routeId - Get route by ID with segments"""
    
    def test_get_route_by_id_success(self, api_client):
        """Test getting route by valid ID"""
        response = api_client.get(f'{BASE_URL}/api/routes/ROUTE:TEST:EXIT:001')
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        assert 'route' in data['data']
        assert 'segments' in data['data']
        
        route = data['data']['route']
        assert route['routeId'] == 'ROUTE:TEST:EXIT:001'
        assert route['routeType'] == 'EXIT'
        assert route['endLabel'] == 'Binance'
        
        segments = data['data']['segments']
        assert len(segments) == 2
        assert segments[0]['index'] == 0
        assert segments[1]['index'] == 1
        
    def test_get_route_by_id_not_found(self, api_client):
        """Test getting non-existent route"""
        response = api_client.get(f'{BASE_URL}/api/routes/NONEXISTENT_ROUTE')
        assert response.status_code == 404
        
        data = response.json()
        assert data['ok'] is False
        assert data['error'] == 'ROUTE_NOT_FOUND'
        
    def test_get_route_with_segments_ordered(self, api_client):
        """Test that segments are returned in correct order"""
        response = api_client.get(f'{BASE_URL}/api/routes/ROUTE:TEST:EXIT:002')
        assert response.status_code == 200
        
        data = response.json()
        segments = data['data']['segments']
        assert len(segments) == 4
        
        # Verify segments are ordered by index
        for i, segment in enumerate(segments):
            assert segment['index'] == i


class TestRoutesByWalletEndpoint:
    """GET /api/routes/wallet/:address - Get routes by wallet address"""
    
    def test_get_routes_by_wallet_success(self, api_client):
        """Test getting routes for a wallet"""
        wallet = TEST_WALLETS[0]
        response = api_client.get(f'{BASE_URL}/api/routes/wallet/{wallet}')
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        assert data['data']['wallet'] == wallet.lower()
        assert 'routes' in data['data']
        assert 'count' in data['data']
        
    def test_get_routes_by_wallet_with_segments(self, api_client):
        """Test getting routes with segments included"""
        wallet = TEST_WALLETS[0]
        response = api_client.get(f'{BASE_URL}/api/routes/wallet/{wallet}?includeSegments=true')
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        routes = data['data']['routes']
        if len(routes) > 0:
            # When includeSegments=true, each item should have route and segments
            assert 'route' in routes[0] or 'routeId' in routes[0]
            
    def test_get_routes_by_wallet_with_limit(self, api_client):
        """Test limiting routes returned"""
        wallet = TEST_WALLETS[0]
        response = api_client.get(f'{BASE_URL}/api/routes/wallet/{wallet}?limit=1')
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        assert len(data['data']['routes']) <= 1
        
    def test_get_routes_by_wallet_empty(self, api_client):
        """Test getting routes for wallet with no routes"""
        # Use a random wallet that definitely has no routes
        response = api_client.get(f'{BASE_URL}/api/routes/wallet/0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef')
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        # May have 0 or more routes depending on system state
        assert 'count' in data['data']


class TestExitRoutesEndpoint:
    """GET /api/routes/exits - Get EXIT routes (potential dumps)"""
    
    def test_get_exit_routes_default(self, api_client):
        """Test getting exit routes with defaults"""
        response = api_client.get(f'{BASE_URL}/api/routes/exits')
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        assert 'exits' in data['data']
        assert 'count' in data['data']
        
        # All returned routes should be EXIT type
        for route in data['data']['exits']:
            assert route['routeType'] == 'EXIT'
            
    def test_get_exit_routes_filter_by_exchange(self, api_client):
        """Test filtering exit routes by exchange"""
        response = api_client.get(f'{BASE_URL}/api/routes/exits?exchange=Binance')
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        for route in data['data']['exits']:
            assert 'Binance' in route.get('endLabel', '')
            
    def test_get_exit_routes_filter_by_min_amount(self, api_client):
        """Test filtering exit routes by minimum amount"""
        response = api_client.get(f'{BASE_URL}/api/routes/exits?minAmountUsd=100000')
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        for route in data['data']['exits']:
            if route.get('totalAmountUsd'):
                assert route['totalAmountUsd'] >= 100000


class TestHighRiskRoutesEndpoint:
    """GET /api/routes/high-risk - Get high-risk routes"""
    
    def test_get_high_risk_routes_default(self, api_client):
        """Test getting high-risk routes with defaults"""
        response = api_client.get(f'{BASE_URL}/api/routes/high-risk')
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        assert 'highRiskRoutes' in data['data']
        assert 'count' in data['data']
        
    def test_high_risk_routes_have_dump_analysis(self, api_client):
        """Test that high-risk routes include dump analysis"""
        response = api_client.get(f'{BASE_URL}/api/routes/high-risk')
        assert response.status_code == 200
        
        data = response.json()
        for item in data['data']['highRiskRoutes']:
            assert 'route' in item
            assert 'segments' in item
            assert 'dump' in item
            assert 'severity' in item
            
            # Dump analysis structure
            dump = item['dump']
            assert 'isDump' in dump
            assert 'confidence' in dump
            assert 'signals' in dump
            
    def test_high_risk_routes_filter_by_confidence(self, api_client):
        """Test filtering high-risk routes by confidence"""
        response = api_client.get(f'{BASE_URL}/api/routes/high-risk?minConfidence=0.8')
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True


class TestRouteStatsEndpoint:
    """GET /api/routes/stats - Get route statistics"""
    
    def test_get_route_stats(self, api_client):
        """Test getting route statistics"""
        response = api_client.get(f'{BASE_URL}/api/routes/stats')
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        
        stats = data['data']
        assert 'totalRoutes' in stats
        assert 'activeRoutes' in stats
        assert 'completedRoutes' in stats
        assert 'staleRoutes' in stats
        assert 'byType' in stats
        assert 'avgConfidence' in stats
        assert 'avgSegments' in stats
        assert 'totalVolumeUsd' in stats
        assert 'exitRoutesToday' in stats
        assert 'topExitDestinations' in stats
        
    def test_route_stats_type_breakdown(self, api_client):
        """Test that stats include type breakdown"""
        response = api_client.get(f'{BASE_URL}/api/routes/stats')
        assert response.status_code == 200
        
        data = response.json()
        by_type = data['data']['byType']
        # Should have EXIT and MIGRATION from seeded data
        assert isinstance(by_type, dict)
        
    def test_route_stats_top_destinations(self, api_client):
        """Test that stats include top exit destinations"""
        response = api_client.get(f'{BASE_URL}/api/routes/stats')
        assert response.status_code == 200
        
        data = response.json()
        destinations = data['data']['topExitDestinations']
        assert isinstance(destinations, list)
        
        for dest in destinations:
            assert 'label' in dest
            assert 'count' in dest
            assert 'volumeUsd' in dest


class TestWalletAnalysisEndpoint:
    """GET /api/routes/analyze/:address - Analyze wallet for dump patterns"""
    
    def test_analyze_wallet_with_exit_routes(self, api_client):
        """Test analyzing wallet that has exit routes"""
        wallet = TEST_WALLETS[2]  # Has EXIT route to Coinbase
        response = api_client.get(f'{BASE_URL}/api/routes/analyze/{wallet}')
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        assert data['data']['wallet'] == wallet.lower()
        assert 'hasDumpPattern' in data['data']
        assert 'exitRoutes' in data['data']
        assert 'totalExitVolume' in data['data']
        assert 'topDestinations' in data['data']
        
    def test_analyze_wallet_dump_detection(self, api_client):
        """Test dump pattern detection in analysis"""
        wallet = TEST_WALLETS[2]
        response = api_client.get(f'{BASE_URL}/api/routes/analyze/{wallet}')
        assert response.status_code == 200
        
        data = response.json()
        exit_routes = data['data']['exitRoutes']
        
        for exit_route in exit_routes:
            assert 'route' in exit_route
            assert 'dump' in exit_route
            assert 'severity' in exit_route
            
    def test_analyze_wallet_no_routes(self, api_client):
        """Test analyzing wallet with no routes"""
        response = api_client.get(f'{BASE_URL}/api/routes/analyze/0x0000000000000000000000000000000000000000')
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        assert data['data']['hasDumpPattern'] is False
        assert data['data']['totalExitVolume'] == 0


class TestRouteSegmentsEndpoint:
    """GET /api/routes/:routeId/segments - Get segments for a route"""
    
    def test_get_segments_success(self, api_client):
        """Test getting segments for a route"""
        response = api_client.get(f'{BASE_URL}/api/routes/ROUTE:TEST:EXIT:001/segments')
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        assert data['data']['routeId'] == 'ROUTE:TEST:EXIT:001'
        assert 'segments' in data['data']
        assert 'count' in data['data']
        assert data['data']['count'] == 2
        
    def test_get_segments_ordered_by_index(self, api_client):
        """Test that segments are ordered by index"""
        response = api_client.get(f'{BASE_URL}/api/routes/ROUTE:TEST:EXIT:002/segments')
        assert response.status_code == 200
        
        data = response.json()
        segments = data['data']['segments']
        
        for i, segment in enumerate(segments):
            assert segment['index'] == i
            
    def test_get_segments_structure(self, api_client):
        """Test segment data structure"""
        response = api_client.get(f'{BASE_URL}/api/routes/ROUTE:TEST:EXIT:001/segments')
        assert response.status_code == 200
        
        data = response.json()
        segment = data['data']['segments'][0]
        
        # Required fields
        assert 'routeId' in segment
        assert 'index' in segment
        assert 'type' in segment
        assert 'chainFrom' in segment
        assert 'txHash' in segment
        assert 'blockNumber' in segment
        assert 'timestamp' in segment
        assert 'walletFrom' in segment
        assert 'walletTo' in segment
        assert 'tokenAddress' in segment
        assert 'amount' in segment
        assert 'confidence' in segment
        
    def test_get_segments_empty_route(self, api_client):
        """Test getting segments for non-existent route returns empty"""
        response = api_client.get(f'{BASE_URL}/api/routes/NONEXISTENT/segments')
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        assert data['data']['count'] == 0


class TestSeedEndpoint:
    """POST /api/routes/seed - Seed test data"""
    
    def test_seed_test_routes(self, api_client):
        """Test seeding test routes"""
        response = api_client.post(f'{BASE_URL}/api/routes/seed', json={})
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        assert data['data']['routes'] == 3
        assert data['data']['segments'] == 8
        assert 'Seeded' in data['message']
        
    def test_seed_is_idempotent(self, api_client):
        """Test that seeding is idempotent (cleans existing test data)"""
        # Seed twice
        response1 = api_client.post(f'{BASE_URL}/api/routes/seed', json={})
        response2 = api_client.post(f'{BASE_URL}/api/routes/seed', json={})
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # Both should return same counts
        assert response1.json()['data']['routes'] == response2.json()['data']['routes']


class TestRecomputeEndpoint:
    """POST /api/routes/recompute - Recompute route metrics"""
    
    def test_recompute_all_routes(self, api_client):
        """Test recomputing all route metrics"""
        response = api_client.post(f'{BASE_URL}/api/routes/recompute', json={})
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        assert 'updated' in data['data']
        assert data['data']['updated'] >= 0
        
    def test_recompute_specific_routes(self, api_client):
        """Test recomputing specific routes"""
        response = api_client.post(f'{BASE_URL}/api/routes/recompute', json={
            'routeIds': ['ROUTE:TEST:EXIT:001']
        })
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True


class TestDeleteRouteEndpoint:
    """DELETE /api/routes/:routeId - Delete a route"""
    
    def test_delete_route_not_found(self, api_client):
        """Test deleting non-existent route"""
        response = api_client.delete(f'{BASE_URL}/api/routes/NONEXISTENT_ROUTE')
        assert response.status_code == 404
        
        data = response.json()
        assert data['ok'] is False
        assert data['error'] == 'ROUTE_NOT_FOUND'
        
    def test_delete_route_success(self, api_client):
        """Test deleting a route successfully"""
        # First seed to ensure route exists
        api_client.post(f'{BASE_URL}/api/routes/seed', json={})
        
        # Delete the route
        response = api_client.delete(f'{BASE_URL}/api/routes/ROUTE:TEST:EXIT:001')
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        assert 'Deleted' in data['message']
        
        # Verify route is gone
        get_response = api_client.get(f'{BASE_URL}/api/routes/ROUTE:TEST:EXIT:001')
        assert get_response.status_code == 404
        
        # Re-seed for other tests
        api_client.post(f'{BASE_URL}/api/routes/seed', json={})


class TestRouteClassification:
    """Test route classification and confidence scoring"""
    
    def test_exit_route_classification(self, api_client):
        """Test EXIT route has correct classification"""
        response = api_client.get(f'{BASE_URL}/api/routes/ROUTE:TEST:EXIT:001')
        assert response.status_code == 200
        
        route = response.json()['data']['route']
        assert route['routeType'] == 'EXIT'
        assert route['endLabel'] == 'Binance'
        assert route['confidenceFactors']['cexMatch'] == 1.0
        
    def test_migration_route_classification(self, api_client):
        """Test MIGRATION route has correct classification"""
        response = api_client.get(f'{BASE_URL}/api/routes/ROUTE:TEST:MIGRATION:001')
        assert response.status_code == 200
        
        route = response.json()['data']['route']
        assert route['routeType'] == 'MIGRATION'
        assert len(route['chainsInvolved']) >= 2
        assert route['startChain'] != route['endChain']
        
    def test_confidence_factors_structure(self, api_client):
        """Test confidence factors have correct structure"""
        response = api_client.get(f'{BASE_URL}/api/routes/ROUTE:TEST:EXIT:002')
        assert response.status_code == 200
        
        route = response.json()['data']['route']
        factors = route['confidenceFactors']
        
        assert 'amountSimilarity' in factors
        assert 'timeProximity' in factors
        assert 'bridgeMatch' in factors
        assert 'protocolKnown' in factors
        assert 'cexMatch' in factors
        
        # All factors should be between 0 and 1
        for key, value in factors.items():
            assert 0 <= value <= 1, f"{key} should be between 0 and 1"


class TestSegmentTypes:
    """Test different segment types"""
    
    def test_transfer_segment(self, api_client):
        """Test TRANSFER segment type"""
        response = api_client.get(f'{BASE_URL}/api/routes/ROUTE:TEST:EXIT:001/segments')
        assert response.status_code == 200
        
        segments = response.json()['data']['segments']
        transfer_segment = next((s for s in segments if s['type'] == 'TRANSFER'), None)
        assert transfer_segment is not None
        
    def test_cex_deposit_segment(self, api_client):
        """Test CEX_DEPOSIT segment type"""
        response = api_client.get(f'{BASE_URL}/api/routes/ROUTE:TEST:EXIT:001/segments')
        assert response.status_code == 200
        
        segments = response.json()['data']['segments']
        cex_segment = next((s for s in segments if s['type'] == 'CEX_DEPOSIT'), None)
        assert cex_segment is not None
        assert cex_segment['toLabel'] is not None
        
    def test_bridge_segment(self, api_client):
        """Test BRIDGE segment type"""
        response = api_client.get(f'{BASE_URL}/api/routes/ROUTE:TEST:EXIT:002/segments')
        assert response.status_code == 200
        
        segments = response.json()['data']['segments']
        bridge_segment = next((s for s in segments if s['type'] == 'BRIDGE'), None)
        assert bridge_segment is not None
        assert bridge_segment['chainTo'] is not None
        assert bridge_segment['protocol'] is not None
        
    def test_swap_segment(self, api_client):
        """Test SWAP segment type"""
        response = api_client.get(f'{BASE_URL}/api/routes/ROUTE:TEST:EXIT:002/segments')
        assert response.status_code == 200
        
        segments = response.json()['data']['segments']
        swap_segment = next((s for s in segments if s['type'] == 'SWAP'), None)
        assert swap_segment is not None
        assert swap_segment['protocol'] is not None


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_invalid_route_type_filter(self, api_client):
        """Test filtering with invalid route type"""
        response = api_client.get(f'{BASE_URL}/api/routes?type=INVALID_TYPE')
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        assert data['data']['count'] == 0
        
    def test_case_insensitive_wallet_lookup(self, api_client):
        """Test wallet lookup is case insensitive"""
        wallet_upper = TEST_WALLETS[0].upper()
        wallet_lower = TEST_WALLETS[0].lower()
        
        response_upper = api_client.get(f'{BASE_URL}/api/routes/wallet/{wallet_upper}')
        response_lower = api_client.get(f'{BASE_URL}/api/routes/wallet/{wallet_lower}')
        
        assert response_upper.status_code == 200
        assert response_lower.status_code == 200
        
        # Both should return same wallet (normalized to lowercase)
        assert response_upper.json()['data']['wallet'] == response_lower.json()['data']['wallet']
        
    def test_large_offset_returns_empty(self, api_client):
        """Test large offset returns empty results"""
        response = api_client.get(f'{BASE_URL}/api/routes?offset=999999')
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] is True
        assert data['data']['count'] == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
