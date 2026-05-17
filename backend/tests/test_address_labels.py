"""
Address Labels & Exchange Entities API Tests (P0.2.2)

Tests for:
- GET /api/labels - search address labels
- GET /api/labels/:chain/:address - get specific label
- POST /api/labels/upsert - create/update label
- GET /api/labels/stats - labels statistics
- POST /api/labels/seed - seed known labels
- GET /api/exchanges - search exchange entities
- GET /api/exchanges/:identifier - get exchange by ID
- POST /api/exchanges/upsert - create/update exchange
- GET /api/exchanges/stats - exchange statistics
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAddressLabelsAPI:
    """Address Labels endpoint tests"""
    
    # ============================================
    # GET /api/labels - Search Labels
    # ============================================
    
    def test_search_labels_returns_list(self):
        """GET /api/labels returns list of labels"""
        response = requests.get(f"{BASE_URL}/api/labels")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert 'data' in data
        assert 'labels' in data['data']
        assert 'count' in data['data']
        assert isinstance(data['data']['labels'], list)
        print(f"✓ Found {data['data']['count']} labels")
    
    def test_search_labels_with_chain_filter(self):
        """GET /api/labels?chain=ETH filters by chain"""
        response = requests.get(f"{BASE_URL}/api/labels", params={'chain': 'ETH'})
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        labels = data['data']['labels']
        
        # All returned labels should be ETH chain
        for label in labels:
            assert label['chain'] == 'ETH', f"Expected ETH, got {label['chain']}"
        print(f"✓ Chain filter works - {len(labels)} ETH labels")
    
    def test_search_labels_with_category_filter(self):
        """GET /api/labels?category=CEX filters by category"""
        response = requests.get(f"{BASE_URL}/api/labels", params={'category': 'CEX'})
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        labels = data['data']['labels']
        
        # All returned labels should be CEX category
        for label in labels:
            assert label['category'] == 'CEX', f"Expected CEX, got {label['category']}"
        print(f"✓ Category filter works - {len(labels)} CEX labels")
    
    def test_search_labels_with_query(self):
        """GET /api/labels?q=binance searches by name"""
        response = requests.get(f"{BASE_URL}/api/labels", params={'q': 'binance'})
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        labels = data['data']['labels']
        
        # Should find Binance labels
        assert len(labels) > 0, "Should find Binance labels"
        for label in labels:
            assert 'binance' in label['name'].lower() or 'bnb' in str(label.get('tags', [])).lower()
        print(f"✓ Search query works - found {len(labels)} Binance labels")
    
    def test_search_labels_with_limit(self):
        """GET /api/labels?limit=5 respects limit"""
        response = requests.get(f"{BASE_URL}/api/labels", params={'limit': 5})
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        labels = data['data']['labels']
        
        assert len(labels) <= 5, f"Expected max 5 labels, got {len(labels)}"
        print(f"✓ Limit parameter works - returned {len(labels)} labels")
    
    # ============================================
    # GET /api/labels/:chain/:address - Get Specific Label
    # ============================================
    
    def test_get_specific_label_success(self):
        """GET /api/labels/:chain/:address returns label with entity"""
        # Use known Binance address
        chain = 'ETH'
        address = '0x28c6c06298d514db089934071355e5743bf21d60'
        
        response = requests.get(f"{BASE_URL}/api/labels/{chain}/{address}")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert 'data' in data
        assert 'label' in data['data']
        assert 'entity' in data['data']
        assert 'isExchange' in data['data']
        assert 'isKnown' in data['data']
        
        label = data['data']['label']
        assert label['chain'] == chain.upper()
        assert label['address'] == address.lower()
        assert label['category'] == 'CEX'
        assert 'Binance' in label['name']
        
        # Should have linked entity
        entity = data['data']['entity']
        assert entity is not None
        assert entity['name'] == 'Binance'
        
        print(f"✓ Got label: {label['name']} with entity: {entity['name']}")
    
    def test_get_specific_label_not_found(self):
        """GET /api/labels/:chain/:address returns 404 for unknown address"""
        response = requests.get(f"{BASE_URL}/api/labels/ETH/0x0000000000000000000000000000000000000000")
        assert response.status_code == 404
        
        data = response.json()
        assert data['ok'] == False
        assert data['error'] == 'LABEL_NOT_FOUND'
        print("✓ Returns 404 for unknown address")
    
    # ============================================
    # POST /api/labels/upsert - Create/Update Label
    # ============================================
    
    def test_upsert_label_create(self):
        """POST /api/labels/upsert creates new label"""
        test_label = {
            'chain': 'ETH',
            'address': '0xTEST_' + str(int(time.time())) + '000000000000000000000000',
            'name': 'TEST Label',
            'category': 'WHALE',
            'subcategory': 'test',
            'confidence': 'LOW',
            'tags': ['test', 'automated']
        }
        
        response = requests.post(f"{BASE_URL}/api/labels/upsert", json=test_label)
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert 'data' in data
        
        created = data['data']
        assert created['chain'] == test_label['chain']
        assert created['address'] == test_label['address'].lower()
        assert created['name'] == test_label['name']
        assert created['category'] == test_label['category']
        assert created['confidence'] == test_label['confidence']
        assert 'labelId' in created
        
        print(f"✓ Created label: {created['labelId']}")
        
        # Cleanup - delete the test label
        requests.delete(f"{BASE_URL}/api/labels/{test_label['chain']}/{test_label['address']}")
    
    def test_upsert_label_update(self):
        """POST /api/labels/upsert updates existing label"""
        # Create a label first
        test_address = '0xTEST_UPDATE_' + str(int(time.time()))
        test_label = {
            'chain': 'ARB',
            'address': test_address,
            'name': 'Original Name',
            'category': 'OTHER'
        }
        
        response = requests.post(f"{BASE_URL}/api/labels/upsert", json=test_label)
        assert response.status_code == 200
        
        # Update the label
        updated_label = {
            'chain': 'ARB',
            'address': test_address,
            'name': 'Updated Name',
            'category': 'WHALE',
            'confidence': 'HIGH'
        }
        
        response = requests.post(f"{BASE_URL}/api/labels/upsert", json=updated_label)
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert data['data']['name'] == 'Updated Name'
        assert data['data']['category'] == 'WHALE'
        assert data['data']['confidence'] == 'HIGH'
        
        print("✓ Updated label successfully")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/labels/ARB/{test_address}")
    
    def test_upsert_label_validation(self):
        """POST /api/labels/upsert validates required fields"""
        # Missing required fields
        response = requests.post(f"{BASE_URL}/api/labels/upsert", json={
            'chain': 'ETH'
            # Missing address, name, category
        })
        assert response.status_code == 400
        
        data = response.json()
        assert data['ok'] == False
        assert data['error'] == 'INVALID_INPUT'
        print("✓ Validation works for missing fields")
    
    # ============================================
    # GET /api/labels/stats - Labels Statistics
    # ============================================
    
    def test_get_labels_stats(self):
        """GET /api/labels/stats returns statistics"""
        response = requests.get(f"{BASE_URL}/api/labels/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert 'data' in data
        
        stats = data['data']
        assert 'totalLabels' in stats
        assert 'byCategory' in stats
        assert 'byChain' in stats
        assert 'byConfidence' in stats
        assert 'verified' in stats
        assert 'recentlyAdded' in stats
        
        assert isinstance(stats['totalLabels'], int)
        assert isinstance(stats['byCategory'], dict)
        assert isinstance(stats['byChain'], dict)
        
        print(f"✓ Stats: {stats['totalLabels']} total labels, categories: {list(stats['byCategory'].keys())}")
    
    # ============================================
    # POST /api/labels/seed - Seed Known Labels
    # ============================================
    
    def test_seed_known_labels(self):
        """POST /api/labels/seed seeds known exchanges and bridges"""
        response = requests.post(f"{BASE_URL}/api/labels/seed")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert 'data' in data
        
        result = data['data']
        assert 'entities' in result
        assert 'labels' in result
        assert isinstance(result['entities'], int)
        assert isinstance(result['labels'], int)
        
        print(f"✓ Seeded {result['entities']} entities and {result['labels']} labels")


class TestExchangeEntitiesAPI:
    """Exchange Entities endpoint tests"""
    
    # ============================================
    # GET /api/exchanges - Search Exchanges
    # ============================================
    
    def test_search_exchanges_returns_list(self):
        """GET /api/exchanges returns list of entities"""
        response = requests.get(f"{BASE_URL}/api/exchanges")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert 'data' in data
        assert 'entities' in data['data']
        assert 'count' in data['data']
        assert isinstance(data['data']['entities'], list)
        
        print(f"✓ Found {data['data']['count']} exchange entities")
    
    def test_search_exchanges_with_type_filter(self):
        """GET /api/exchanges?type=CEX filters by type"""
        response = requests.get(f"{BASE_URL}/api/exchanges", params={'type': 'CEX'})
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        entities = data['data']['entities']
        
        # All returned entities should be CEX type
        for entity in entities:
            assert entity['type'] == 'CEX', f"Expected CEX, got {entity['type']}"
        print(f"✓ Type filter works - {len(entities)} CEX entities")
    
    def test_search_exchanges_with_tier_filter(self):
        """GET /api/exchanges?tier=1 filters by tier"""
        response = requests.get(f"{BASE_URL}/api/exchanges", params={'tier': 1})
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        entities = data['data']['entities']
        
        # All returned entities should be tier 1
        for entity in entities:
            assert entity['tier'] == 1, f"Expected tier 1, got {entity['tier']}"
        print(f"✓ Tier filter works - {len(entities)} tier 1 entities")
    
    def test_search_exchanges_with_query(self):
        """GET /api/exchanges?q=binance searches by name"""
        response = requests.get(f"{BASE_URL}/api/exchanges", params={'q': 'binance'})
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        entities = data['data']['entities']
        
        assert len(entities) > 0, "Should find Binance"
        assert any('binance' in e['name'].lower() for e in entities)
        print(f"✓ Search query works - found Binance")
    
    # ============================================
    # GET /api/exchanges/:identifier - Get Exchange by ID
    # ============================================
    
    def test_get_exchange_by_entity_id(self):
        """GET /api/exchanges/:identifier returns exchange by entityId"""
        response = requests.get(f"{BASE_URL}/api/exchanges/ENTITY:binance")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert 'data' in data
        
        entity = data['data']
        assert entity['entityId'] == 'ENTITY:binance'
        assert entity['name'] == 'Binance'
        assert entity['type'] == 'CEX'
        assert 'wallets' in entity
        assert isinstance(entity['wallets'], list)
        assert len(entity['wallets']) > 0
        
        print(f"✓ Got exchange: {entity['name']} with {len(entity['wallets'])} wallets")
    
    def test_get_exchange_by_name(self):
        """GET /api/exchanges/:identifier returns exchange by name"""
        response = requests.get(f"{BASE_URL}/api/exchanges/Coinbase")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert data['data']['name'] == 'Coinbase'
        print("✓ Got exchange by name")
    
    def test_get_exchange_not_found(self):
        """GET /api/exchanges/:identifier returns 404 for unknown exchange"""
        response = requests.get(f"{BASE_URL}/api/exchanges/ENTITY:nonexistent")
        assert response.status_code == 404
        
        data = response.json()
        assert data['ok'] == False
        assert data['error'] == 'EXCHANGE_NOT_FOUND'
        print("✓ Returns 404 for unknown exchange")
    
    # ============================================
    # POST /api/exchanges/upsert - Create/Update Exchange
    # ============================================
    
    def test_upsert_exchange_create(self):
        """POST /api/exchanges/upsert creates new exchange"""
        test_exchange = {
            'name': 'TEST Exchange ' + str(int(time.time())),
            'shortName': 'TEST',
            'type': 'DEX',
            'tier': 3,
            'isRegulated': False,
            'website': 'https://test.exchange'
        }
        
        response = requests.post(f"{BASE_URL}/api/exchanges/upsert", json=test_exchange)
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert 'data' in data
        
        created = data['data']
        assert created['name'] == test_exchange['name']
        assert created['shortName'] == test_exchange['shortName']
        assert created['type'] == test_exchange['type']
        assert created['tier'] == test_exchange['tier']
        assert 'entityId' in created
        
        print(f"✓ Created exchange: {created['entityId']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/exchanges/{created['entityId']}")
    
    def test_upsert_exchange_validation(self):
        """POST /api/exchanges/upsert validates required fields"""
        response = requests.post(f"{BASE_URL}/api/exchanges/upsert", json={
            'name': 'Test'
            # Missing shortName and type
        })
        assert response.status_code == 400
        
        data = response.json()
        assert data['ok'] == False
        assert data['error'] == 'INVALID_INPUT'
        print("✓ Validation works for missing fields")
    
    # ============================================
    # GET /api/exchanges/stats - Exchange Statistics
    # ============================================
    
    def test_get_exchange_stats(self):
        """GET /api/exchanges/stats returns statistics"""
        response = requests.get(f"{BASE_URL}/api/exchanges/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert data['ok'] == True
        assert 'data' in data
        
        stats = data['data']
        assert 'totalEntities' in stats
        assert 'byType' in stats
        assert 'byTier' in stats
        assert 'regulated' in stats
        assert 'totalWallets' in stats
        
        assert isinstance(stats['totalEntities'], int)
        assert isinstance(stats['byType'], dict)
        assert isinstance(stats['byTier'], dict)
        
        print(f"✓ Stats: {stats['totalEntities']} entities, {stats['totalWallets']} wallets")


class TestLabelDataIntegrity:
    """Data integrity and structure validation tests"""
    
    def test_label_structure(self):
        """Verify label document structure"""
        response = requests.get(f"{BASE_URL}/api/labels", params={'limit': 1})
        assert response.status_code == 200
        
        data = response.json()
        if data['data']['count'] > 0:
            label = data['data']['labels'][0]
            
            # Required fields
            assert 'labelId' in label
            assert 'chain' in label
            assert 'address' in label
            assert 'name' in label
            assert 'category' in label
            assert 'confidence' in label
            assert 'sources' in label
            assert 'tags' in label
            assert 'createdAt' in label
            assert 'updatedAt' in label
            
            # Type validation
            assert isinstance(label['sources'], list)
            assert isinstance(label['tags'], list)
            
            print(f"✓ Label structure valid: {label['labelId']}")
    
    def test_exchange_structure(self):
        """Verify exchange entity document structure"""
        response = requests.get(f"{BASE_URL}/api/exchanges", params={'limit': 1})
        assert response.status_code == 200
        
        data = response.json()
        if data['data']['count'] > 0:
            entity = data['data']['entities'][0]
            
            # Required fields
            assert 'entityId' in entity
            assert 'name' in entity
            assert 'shortName' in entity
            assert 'type' in entity
            assert 'tier' in entity
            assert 'isRegulated' in entity
            assert 'wallets' in entity
            assert 'totalWallets' in entity
            assert 'chainsPresent' in entity
            assert 'createdAt' in entity
            assert 'updatedAt' in entity
            
            # Type validation
            assert isinstance(entity['wallets'], list)
            assert isinstance(entity['chainsPresent'], list)
            assert isinstance(entity['tier'], int)
            
            # Wallet structure
            if len(entity['wallets']) > 0:
                wallet = entity['wallets'][0]
                assert 'chain' in wallet
                assert 'address' in wallet
                assert 'type' in wallet
            
            print(f"✓ Exchange structure valid: {entity['entityId']}")
    
    def test_label_category_values(self):
        """Verify label categories are valid"""
        valid_categories = ['CEX', 'DEX', 'BRIDGE', 'LENDING', 'FUND', 'WHALE', 
                          'PROTOCOL', 'CONTRACT', 'MIXER', 'SCAM', 'CUSTODIAN', 'OTHER']
        
        response = requests.get(f"{BASE_URL}/api/labels")
        assert response.status_code == 200
        
        data = response.json()
        for label in data['data']['labels']:
            assert label['category'] in valid_categories, f"Invalid category: {label['category']}"
        
        print(f"✓ All {len(data['data']['labels'])} labels have valid categories")
    
    def test_exchange_type_values(self):
        """Verify exchange types are valid"""
        valid_types = ['CEX', 'DEX', 'BRIDGE', 'PROTOCOL']
        
        response = requests.get(f"{BASE_URL}/api/exchanges")
        assert response.status_code == 200
        
        data = response.json()
        for entity in data['data']['entities']:
            assert entity['type'] in valid_types, f"Invalid type: {entity['type']}"
        
        print(f"✓ All {len(data['data']['entities'])} entities have valid types")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
