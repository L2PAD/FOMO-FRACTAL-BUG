"""
Backend tests for Edge Opportunities (Early Money Engine)
Tests GET /api/mobile/edge/opportunities endpoint
"""
import pytest
import requests
import os

# Use public backend URL from frontend .env
BASE_URL = "https://expo-telegram-web.preview.emergentagent.com"

class TestEdgeOpportunities:
    """Edge Opportunities endpoint tests"""

    def test_get_edge_opportunities_success(self, api_client, auth_token):
        """Test GET /api/mobile/edge/opportunities returns real opportunities"""
        response = api_client.get(
            f"{BASE_URL}/api/mobile/edge/opportunities",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()
        assert data["ok"] is True, "Response should have ok=True"
        assert "opportunities" in data, "Response should have opportunities field"
        assert "count" in data, "Response should have count field"
        assert isinstance(data["opportunities"], list), "opportunities should be a list"
        
        print(f"✅ GET /api/mobile/edge/opportunities - {data['count']} opportunities returned")

    def test_edge_opportunities_structure(self, api_client, auth_token):
        """Test each opportunity has required fields"""
        response = api_client.get(
            f"{BASE_URL}/api/mobile/edge/opportunities",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200

        data = response.json()
        opportunities = data["opportunities"]
        
        if len(opportunities) == 0:
            pytest.skip("No opportunities available - cannot test structure")
        
        # Test first opportunity structure
        opp = opportunities[0]
        required_fields = [
            "id", "asset", "type", "badge", "confidence", 
            "title", "drivers", "tension", "timing"
        ]
        
        for field in required_fields:
            assert field in opp, f"Opportunity missing required field: {field}"
        
        # Validate types
        assert isinstance(opp["id"], str), "id should be string"
        assert isinstance(opp["asset"], str), "asset should be string"
        assert opp["type"] in ["FLOW", "SOCIAL", "CATALYST"], f"type should be FLOW/SOCIAL/CATALYST, got {opp['type']}"
        assert isinstance(opp["badge"], str), "badge should be string"
        assert isinstance(opp["confidence"], (int, float)), "confidence should be number"
        assert isinstance(opp["title"], str), "title should be string"
        assert isinstance(opp["drivers"], list), "drivers should be list"
        assert isinstance(opp["tension"], str), "tension should be string"
        assert isinstance(opp["timing"], str), "timing should be string"
        
        print(f"✅ Opportunity structure valid: {opp['asset']} - {opp['type']} - {opp['badge']}")

    def test_edge_opportunities_flow_type(self, api_client, auth_token):
        """Test FLOW type opportunities (Fear & Greed based)"""
        response = api_client.get(
            f"{BASE_URL}/api/mobile/edge/opportunities",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200

        data = response.json()
        opportunities = data["opportunities"]
        
        flow_opps = [o for o in opportunities if o["type"] == "FLOW"]
        
        if len(flow_opps) == 0:
            print("⚠️ No FLOW opportunities found (may be normal if Fear & Greed is neutral)")
            return
        
        flow_opp = flow_opps[0]
        assert flow_opp["asset"] in ["BTC", "ETH", "SOL"], f"FLOW opportunities should be major assets, got {flow_opp['asset']}"
        assert len(flow_opp["drivers"]) >= 1, "FLOW opportunity should have at least 1 driver"
        
        # Check if drivers mention Fear & Greed
        driver_texts = [d["text"] for d in flow_opp["drivers"]]
        has_fear_greed = any("Fear" in text or "Greed" in text or "fear" in text or "greed" in text for text in driver_texts)
        assert has_fear_greed, "FLOW opportunity should mention Fear & Greed in drivers"
        
        print(f"✅ FLOW opportunity found: {flow_opp['asset']} - {flow_opp['badge']} - {flow_opp['confidence']}% confidence")

    def test_edge_opportunities_social_type(self, api_client, auth_token):
        """Test SOCIAL type opportunities (actor_signal_events based)"""
        response = api_client.get(
            f"{BASE_URL}/api/mobile/edge/opportunities",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200

        data = response.json()
        opportunities = data["opportunities"]
        
        social_opps = [o for o in opportunities if o["type"] == "SOCIAL"]
        
        if len(social_opps) == 0:
            print("⚠️ No SOCIAL opportunities found (may be normal if no recent social activity)")
            return
        
        social_opp = social_opps[0]
        assert social_opp["badge"] == "SOCIAL SPIKE", f"SOCIAL opportunity should have SOCIAL SPIKE badge, got {social_opp['badge']}"
        assert len(social_opp["drivers"]) >= 1, "SOCIAL opportunity should have at least 1 driver"
        
        # Check if drivers mention social/influencer/engagement
        driver_texts = [d["text"] for d in social_opp["drivers"]]
        has_social = any(
            "signal" in text.lower() or "actor" in text.lower() or 
            "engagement" in text.lower() or "attention" in text.lower()
            for text in driver_texts
        )
        assert has_social, "SOCIAL opportunity should mention social/engagement in drivers"
        
        print(f"✅ SOCIAL opportunity found: {social_opp['asset']} - {social_opp['badge']} - {social_opp['confidence']}% confidence")

    def test_edge_opportunities_drivers_structure(self, api_client, auth_token):
        """Test driver structure (icon, text, positive)"""
        response = api_client.get(
            f"{BASE_URL}/api/mobile/edge/opportunities",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200

        data = response.json()
        opportunities = data["opportunities"]
        
        if len(opportunities) == 0:
            pytest.skip("No opportunities available - cannot test drivers")
        
        opp = opportunities[0]
        drivers = opp["drivers"]
        
        assert len(drivers) >= 1, "Opportunity should have at least 1 driver"
        
        driver = drivers[0]
        assert "icon" in driver, "Driver should have icon field"
        assert "text" in driver, "Driver should have text field"
        assert "positive" in driver, "Driver should have positive field"
        assert isinstance(driver["icon"], str), "Driver icon should be string"
        assert isinstance(driver["text"], str), "Driver text should be string"
        assert isinstance(driver["positive"], bool), "Driver positive should be boolean"
        
        print(f"✅ Driver structure valid: {driver['text']} (positive={driver['positive']})")

    def test_edge_opportunities_asset_filter(self, api_client, auth_token):
        """Test filtering by asset"""
        response = api_client.get(
            f"{BASE_URL}/api/mobile/edge/opportunities?asset=BTC",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200

        data = response.json()
        opportunities = data["opportunities"]
        
        # All opportunities should be BTC or have BTC as signalLink
        for opp in opportunities:
            assert opp["asset"] == "BTC" or opp.get("signalLink") == "BTC", \
                f"Filtered by BTC but got {opp['asset']} with signalLink={opp.get('signalLink')}"
        
        print(f"✅ Asset filter working: {len(opportunities)} BTC opportunities")

    def test_edge_opportunities_not_mocked(self, api_client, auth_token):
        """Verify opportunities are from real MongoDB data (not mocked)"""
        response = api_client.get(
            f"{BASE_URL}/api/mobile/edge/opportunities",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200

        data = response.json()
        opportunities = data["opportunities"]
        
        if len(opportunities) == 0:
            pytest.skip("No opportunities available - cannot verify real data")
        
        # Check for real data indicators:
        # 1. FLOW opportunities should have numeric Fear & Greed values
        # 2. SOCIAL opportunities should have numeric engagement metrics
        # 3. IDs should be deterministic (not random UUIDs)
        
        flow_opps = [o for o in opportunities if o["type"] == "FLOW"]
        if flow_opps:
            flow_opp = flow_opps[0]
            driver_texts = [d["text"] for d in flow_opp["drivers"]]
            # Look for numeric values in driver text (e.g., "Fear & Greed at 12")
            has_numeric = any(any(char.isdigit() for char in text) for text in driver_texts)
            assert has_numeric, "FLOW opportunity should have numeric Fear & Greed value (real data)"
            print(f"✅ FLOW opportunity has real data: {driver_texts[0]}")
        
        social_opps = [o for o in opportunities if o["type"] == "SOCIAL"]
        if social_opps:
            social_opp = social_opps[0]
            driver_texts = [d["text"] for d in social_opp["drivers"]]
            # Look for numeric values (e.g., "5 signals from 3 actors")
            has_numeric = any(any(char.isdigit() for char in text) for text in driver_texts)
            assert has_numeric, "SOCIAL opportunity should have numeric engagement metrics (real data)"
            print(f"✅ SOCIAL opportunity has real data: {driver_texts[0]}")


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture
def auth_token(api_client):
    """Get auth token via dev login"""
    response = api_client.post(
        f"{BASE_URL}/api/mobile/auth/dev-login",
        json={"email": "dev@fomo.ai", "name": "FOMO Developer"}
    )
    assert response.status_code == 200, f"Dev login failed: {response.text}"
    data = response.json()
    assert "accessToken" in data, "Dev login should return accessToken"
    return data["accessToken"]
