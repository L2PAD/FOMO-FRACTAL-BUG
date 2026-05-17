"""
Radar V11 API Tests - Server-side pagination, filtering, sorting
================================================================
Tests for: GET /api/v11/exchange/radar/spot, futures, universe
Validates: pagination meta, venue param, filters (search, verdict, minConv), sort options
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestRadarV11Universe:
    """Universe endpoint tests"""
    
    def test_universe_spot_mode(self):
        """Test universe endpoint returns spot counts"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/universe?mode=spot")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert data.get('ok') == True
        assert data.get('mode') == 'spot'
        assert 'spotMainCount' in data
        assert 'spotAlphaCount' in data
        assert 'spotMainSymbols' in data
        print(f"✓ Universe spot: Main={data['spotMainCount']}, Alpha={data['spotAlphaCount']}")
    
    def test_universe_futures_mode(self):
        """Test universe endpoint returns futures counts"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/universe?mode=futures")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert data.get('ok') == True
        assert data.get('mode') == 'futures'
        assert 'futuresCount' in data
        assert 'futuresSymbols' in data
        print(f"✓ Universe futures: Count={data['futuresCount']}")


class TestRadarV11SpotAPI:
    """Spot radar endpoint tests with pagination & filters"""
    
    def test_spot_main_venue_default_pagination(self):
        """Test spot endpoint with main venue, default pagination"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') == True
        assert data.get('mode') == 'spot'
        assert data.get('venue') == 'main'
        
        # Verify meta structure
        meta = data.get('meta', {})
        assert 'total' in meta
        assert 'page' in meta
        assert 'pages' in meta
        assert 'limit' in meta
        assert 'universe' in meta
        assert meta['page'] == 1
        assert meta['limit'] == 20  # default
        
        # Verify rows array exists
        assert 'rows' in data
        assert isinstance(data['rows'], list)
        print(f"✓ Spot main: {len(data['rows'])} rows, total={meta['total']}, pages={meta['pages']}")
    
    def test_spot_alpha_venue(self):
        """Test spot endpoint with alpha venue"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=alpha")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('venue') == 'alpha'
        meta = data.get('meta', {})
        assert meta.get('universe') == 'alpha'
        print(f"✓ Spot alpha: {len(data['rows'])} rows, total={meta['total']}")
    
    def test_spot_pagination_custom_page_limit(self):
        """Test spot endpoint with custom page and limit"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&page=1&limit=5")
        assert response.status_code == 200
        data = response.json()
        
        meta = data.get('meta', {})
        assert meta.get('limit') == 5
        assert len(data.get('rows', [])) <= 5
        print(f"✓ Spot pagination: page={meta['page']}, limit={meta['limit']}, rows={len(data['rows'])}")
    
    def test_spot_search_filter(self):
        """Test spot endpoint with search filter"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&search=sol")
        assert response.status_code == 200
        data = response.json()
        
        # If results found, verify they contain 'sol' in symbol
        for row in data.get('rows', []):
            assert 'sol' in row['symbol'].lower(), f"Search filter failed: {row['symbol']}"
        print(f"✓ Spot search 'sol': {len(data['rows'])} rows found")
    
    def test_spot_verdict_filter(self):
        """Test spot endpoint with verdict filter"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&verdict=buy")
        assert response.status_code == 200
        data = response.json()
        
        # Verify all results have 'buy' verdict
        for row in data.get('rows', []):
            assert row['verdict'] == 'buy', f"Verdict filter failed: {row['verdict']}"
        print(f"✓ Spot verdict=buy: {len(data['rows'])} rows found")
    
    def test_spot_minconv_filter(self):
        """Test spot endpoint with minimum conviction filter"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&minConv=50")
        assert response.status_code == 200
        data = response.json()
        
        # Verify all results have conviction >= 50
        for row in data.get('rows', []):
            assert row['conviction'] >= 50, f"MinConv filter failed: {row['conviction']}"
        print(f"✓ Spot minConv>=50: {len(data['rows'])} rows found")
    
    def test_spot_sort_by_conviction(self):
        """Test spot endpoint sorted by conviction (default)"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&sort=conviction")
        assert response.status_code == 200
        data = response.json()
        
        rows = data.get('rows', [])
        if len(rows) > 1:
            # Verify descending order
            for i in range(len(rows) - 1):
                assert rows[i]['conviction'] >= rows[i+1]['conviction'], "Sort by conviction failed"
        print(f"✓ Spot sort=conviction: {len(rows)} rows in descending order")
    
    def test_spot_sort_by_risk(self):
        """Test spot endpoint sorted by risk"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&sort=risk")
        assert response.status_code == 200
        data = response.json()
        
        rows = data.get('rows', [])
        # Verify risk order: high -> medium -> low
        risk_order = {'high': 0, 'medium': 1, 'low': 2}
        if len(rows) > 1:
            for i in range(len(rows) - 1):
                curr_order = risk_order.get(rows[i]['risk'], 1)
                next_order = risk_order.get(rows[i+1]['risk'], 1)
                assert curr_order <= next_order, f"Sort by risk failed: {rows[i]['risk']} after {rows[i+1]['risk']}"
        print(f"✓ Spot sort=risk: {len(rows)} rows sorted by risk level")
    
    def test_spot_sort_by_symbol(self):
        """Test spot endpoint sorted by symbol (alphabetical)"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&sort=symbol")
        assert response.status_code == 200
        data = response.json()
        
        rows = data.get('rows', [])
        if len(rows) > 1:
            for i in range(len(rows) - 1):
                assert rows[i]['symbol'] <= rows[i+1]['symbol'], f"Sort by symbol failed: {rows[i]['symbol']} > {rows[i+1]['symbol']}"
        print(f"✓ Spot sort=symbol: {len(rows)} rows in alphabetical order")
    
    def test_spot_row_structure(self):
        """Test spot row has all required fields"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&limit=1")
        assert response.status_code == 200
        data = response.json()
        
        if data.get('rows'):
            row = data['rows'][0]
            required_fields = ['symbol', 'venue', 'direction', 'verdict', 'conviction', 
                              'breakoutProb', 'structure', 'momentumBuild', 'risk', 
                              'features', 'reasons', 'explain', 'updatedAt']
            for field in required_fields:
                assert field in row, f"Missing field: {field}"
            
            # Verify features structure
            features = row.get('features', {})
            feature_fields = ['compression', 'volumeBuild', 'trendAlignment', 'liquidity', 'risk']
            for ff in feature_fields:
                assert ff in features, f"Missing feature: {ff}"
            print(f"✓ Spot row structure valid: {row['symbol']}")


class TestRadarV11FuturesAPI:
    """Futures radar endpoint tests with pagination & filters"""
    
    def test_futures_default_pagination(self):
        """Test futures endpoint with default pagination"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/futures")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') == True
        assert data.get('mode') == 'futures'
        
        # Verify meta structure
        meta = data.get('meta', {})
        assert 'total' in meta
        assert 'page' in meta
        assert 'pages' in meta
        assert 'limit' in meta
        assert meta['page'] == 1
        assert meta['limit'] == 20  # default
        
        print(f"✓ Futures default: {len(data['rows'])} rows, total={meta['total']}, pages={meta['pages']}")
    
    def test_futures_pagination_page_2(self):
        """Test futures endpoint page 2"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/futures?page=2&limit=20")
        assert response.status_code == 200
        data = response.json()
        
        meta = data.get('meta', {})
        assert meta.get('page') == 2
        print(f"✓ Futures page 2: {len(data['rows'])} rows")
    
    def test_futures_pagination_last_page(self):
        """Test futures endpoint navigating to last page"""
        # First get total pages
        response1 = requests.get(f"{BASE_URL}/api/v11/exchange/radar/futures?limit=20")
        data1 = response1.json()
        total_pages = data1.get('meta', {}).get('pages', 1)
        
        # Navigate to last page
        response2 = requests.get(f"{BASE_URL}/api/v11/exchange/radar/futures?page={total_pages}&limit=20")
        assert response2.status_code == 200
        data2 = response2.json()
        
        meta = data2.get('meta', {})
        assert meta.get('page') == total_pages
        print(f"✓ Futures last page ({total_pages}): {len(data2['rows'])} rows")
    
    def test_futures_search_filter(self):
        """Test futures endpoint with search filter"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/futures?search=btc")
        assert response.status_code == 200
        data = response.json()
        
        for row in data.get('rows', []):
            assert 'btc' in row['symbol'].lower()
        print(f"✓ Futures search 'btc': {len(data['rows'])} rows found")
    
    def test_futures_verdict_filter(self):
        """Test futures endpoint with verdict filter"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/futures?verdict=sell")
        assert response.status_code == 200
        data = response.json()
        
        for row in data.get('rows', []):
            assert row['verdict'] == 'sell'
        print(f"✓ Futures verdict=sell: {len(data['rows'])} rows found")
    
    def test_futures_minconv_filter(self):
        """Test futures endpoint with minimum conviction filter"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/futures?minConv=60")
        assert response.status_code == 200
        data = response.json()
        
        for row in data.get('rows', []):
            assert row['conviction'] >= 60
        print(f"✓ Futures minConv>=60: {len(data['rows'])} rows found")
    
    def test_futures_sort_options(self):
        """Test futures endpoint with all sort options"""
        for sort_option in ['conviction', 'risk', 'symbol']:
            response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/futures?sort={sort_option}&limit=10")
            assert response.status_code == 200, f"Sort {sort_option} failed"
        print(f"✓ Futures all sort options working")
    
    def test_futures_combined_filters(self):
        """Test futures endpoint with combined filters"""
        response = requests.get(
            f"{BASE_URL}/api/v11/exchange/radar/futures?page=1&limit=10&sort=conviction&minConv=40"
        )
        assert response.status_code == 200
        data = response.json()
        
        meta = data.get('meta', {})
        assert meta.get('limit') == 10
        
        for row in data.get('rows', []):
            assert row['conviction'] >= 40
        print(f"✓ Futures combined filters: {len(data['rows'])} rows")
    
    def test_futures_row_structure(self):
        """Test futures row has all required fields"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/futures?limit=1")
        assert response.status_code == 200
        data = response.json()
        
        if data.get('rows'):
            row = data['rows'][0]
            required_fields = ['symbol', 'direction', 'bias', 'verdict', 'conviction', 
                              'breakoutProb', 'squeezeRisk', 'squeezeRiskScore', 'oiShift', 
                              'fundingState', 'risk', 'features', 'reasons', 'explain', 'updatedAt']
            for field in required_fields:
                assert field in row, f"Missing field: {field}"
            
            # Verify features structure
            features = row.get('features', {})
            feature_fields = ['oiShift', 'fundingSkew', 'liquidationDensity', 'volatilityRegime', 'risk']
            for ff in feature_fields:
                assert ff in features, f"Missing feature: {ff}"
            print(f"✓ Futures row structure valid: {row['symbol']}")


class TestRadarV11MetaObject:
    """Test meta object is consistent across endpoints"""
    
    def test_meta_object_spot(self):
        """Verify meta object structure in spot response"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main")
        data = response.json()
        meta = data.get('meta', {})
        
        assert 'universe' in meta, "meta.universe missing"
        assert 'total' in meta, "meta.total missing"
        assert 'page' in meta, "meta.page missing"
        assert 'pages' in meta, "meta.pages missing"
        assert 'limit' in meta, "meta.limit missing"
        
        assert meta['universe'] == 'main'
        print(f"✓ Spot meta object valid: universe={meta['universe']}")
    
    def test_meta_object_futures(self):
        """Verify meta object structure in futures response"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/futures")
        data = response.json()
        meta = data.get('meta', {})
        
        assert 'universe' in meta
        assert 'total' in meta
        assert 'page' in meta
        assert 'pages' in meta
        assert 'limit' in meta
        
        assert meta['universe'] == 'futures'
        print(f"✓ Futures meta object valid: universe={meta['universe']}")
    
    def test_pagination_math_correct(self):
        """Verify pagination calculations are correct"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/futures?limit=20")
        data = response.json()
        meta = data.get('meta', {})
        
        total = meta.get('total', 0)
        limit = meta.get('limit', 20)
        pages = meta.get('pages', 1)
        
        # pages should be ceiling of total/limit
        expected_pages = max(1, (total + limit - 1) // limit)
        assert pages == expected_pages, f"Pagination math wrong: {pages} != {expected_pages}"
        print(f"✓ Pagination math correct: {total} items / {limit} per page = {pages} pages")


class TestHighConvictionSOL:
    """Test SOL with conviction=60 for High Conviction badge"""
    
    def test_sol_conviction_value(self):
        """Verify SOL has conviction >= 60 for High Conviction badge"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/radar/spot?venue=main&search=sol")
        assert response.status_code == 200
        data = response.json()
        
        sol_rows = [r for r in data.get('rows', []) if 'SOL' in r['symbol'].upper()]
        if sol_rows:
            sol = sol_rows[0]
            print(f"✓ SOL found: conviction={sol['conviction']}, verdict={sol['verdict']}")
            assert sol['conviction'] >= 60, f"SOL conviction should be >= 60 for High Conviction badge, got {sol['conviction']}"
        else:
            print("⚠ SOL not found in spot main - may be in different venue")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
