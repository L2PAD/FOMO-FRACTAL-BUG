"""
Narrative Tokens API Tests
Tests for GET /api/connections/narratives/tokens endpoint with filters and sorting
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com').rstrip('/')


class TestNarrativeTokensAPI:
    """Tests for Narrative Tokens endpoint"""

    def test_basic_endpoint_returns_ok(self):
        """GET /api/connections/narratives/tokens returns data with ok=true"""
        response = requests.get(f"{BASE_URL}/api/connections/narratives/tokens")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        assert 'data' in data
        assert isinstance(data['data'], list)
    
    def test_required_fields_present(self):
        """Response includes all required fields"""
        response = requests.get(f"{BASE_URL}/api/connections/narratives/tokens")
        data = response.json()
        assert data['ok'] == True
        assert len(data['data']) > 0
        
        required_fields = [
            'token', 'score', 'socialSignalScore', 'velocity', 'deltaMentions',
            'influencers', 'coordination', 'narrativeShare', 'sector', 'sentiment',
            'narrativeFit', 'rank'
        ]
        first_token = data['data'][0]
        for field in required_fields:
            assert field in first_token, f"Missing required field: {field}"
    
    def test_sort_by_mentions(self):
        """Sort filter works: ?sort=mentions returns tokens sorted descending by mentions"""
        response = requests.get(f"{BASE_URL}/api/connections/narratives/tokens?sort=mentions")
        data = response.json()
        assert data['ok'] == True
        
        tokens = data['data']
        if len(tokens) >= 2:
            # Verify descending order
            mentions = [t['mentions'] for t in tokens]
            for i in range(len(mentions) - 1):
                assert mentions[i] >= mentions[i+1], f"Not sorted by mentions: {mentions[i]} < {mentions[i+1]}"
    
    def test_sort_by_velocity(self):
        """Sort filter works: ?sort=velocity returns tokens sorted descending by velocity"""
        response = requests.get(f"{BASE_URL}/api/connections/narratives/tokens?sort=velocity")
        data = response.json()
        assert data['ok'] == True
        
        tokens = data['data']
        if len(tokens) >= 2:
            # Verify descending order
            velocities = [t['velocity'] for t in tokens]
            for i in range(len(velocities) - 1):
                assert velocities[i] >= velocities[i+1], f"Not sorted by velocity: {velocities[i]} < {velocities[i+1]}"
    
    def test_sector_filter(self):
        """Sector filter works: ?sector=DeFi returns only DeFi tokens"""
        response = requests.get(f"{BASE_URL}/api/connections/narratives/tokens?sector=DeFi")
        data = response.json()
        assert data['ok'] == True
        
        tokens = data['data']
        if tokens:
            sectors = set(t.get('sector') for t in tokens)
            assert sectors == {'DeFi'}, f"Expected only DeFi sector, got: {sectors}"
    
    def test_sentiment_filter(self):
        """Sentiment filter works: ?sentiment=positive returns only positive sentiment tokens"""
        response = requests.get(f"{BASE_URL}/api/connections/narratives/tokens?sentiment=positive")
        data = response.json()
        assert data['ok'] == True
        
        tokens = data['data']
        if tokens:
            sentiments = set(t.get('sentiment') for t in tokens)
            assert sentiments == {'positive'}, f"Expected only positive sentiment, got: {sentiments}"
    
    def test_min_score_filter(self):
        """minScore filter works: ?minScore=55 returns only tokens with score >= 55"""
        response = requests.get(f"{BASE_URL}/api/connections/narratives/tokens?minScore=55")
        data = response.json()
        assert data['ok'] == True
        
        tokens = data['data']
        if tokens:
            scores = [t.get('score', 0) for t in tokens]
            assert all(s >= 55 for s in scores), f"Found scores below 55: {[s for s in scores if s < 55]}"
    
    def test_coordination_filter(self):
        """Coordination filter works: ?coordination=true returns only coordinated tokens"""
        response = requests.get(f"{BASE_URL}/api/connections/narratives/tokens?coordination=true")
        data = response.json()
        assert data['ok'] == True
        
        tokens = data['data']
        if tokens:
            coords = [t.get('coordination') for t in tokens]
            assert all(c == True for c in coords), f"Found non-coordinated tokens: {[c for c in coords if c != True]}"
    
    def test_delta_mentions_not_all_zero(self):
        """deltaMentions values are not all zero - should have varied positive/negative values"""
        response = requests.get(f"{BASE_URL}/api/connections/narratives/tokens")
        data = response.json()
        assert data['ok'] == True
        
        tokens = data['data']
        if tokens:
            deltas = [t.get('deltaMentions', 0) for t in tokens]
            non_zero = [d for d in deltas if d != 0]
            assert len(non_zero) > 0, "All deltaMentions are zero"
            
            # Check for variety - both positive and negative values expected
            positive = [d for d in deltas if d > 0]
            negative = [d for d in deltas if d < 0]
            print(f"deltaMentions: {len(positive)} positive, {len(negative)} negative, {len(deltas) - len(non_zero)} zero")
    
    def test_velocity_not_all_zero(self):
        """Velocity values are not all zero"""
        response = requests.get(f"{BASE_URL}/api/connections/narratives/tokens")
        data = response.json()
        assert data['ok'] == True
        
        tokens = data['data']
        if tokens:
            velocities = [t.get('velocity', 0) for t in tokens]
            non_zero = [v for v in velocities if v != 0]
            assert len(non_zero) > 0, "All velocities are zero"
    
    def test_narratives_and_sectors_lists_returned(self):
        """Response includes narratives and sectors lists for filters"""
        response = requests.get(f"{BASE_URL}/api/connections/narratives/tokens")
        data = response.json()
        assert data['ok'] == True
        
        assert 'narratives' in data, "Missing narratives list"
        assert 'sectors' in data, "Missing sectors list"
        assert isinstance(data['narratives'], list)
        assert isinstance(data['sectors'], list)
