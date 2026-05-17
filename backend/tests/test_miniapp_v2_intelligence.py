"""
MiniApp v2 Intelligence Layer Tests
====================================
Tests for the major intelligence upgrade:
- Home screen: decision (mode/strength/riskLevel), actionPlan, marketStory, structure, pressure.net, why, timeline, alertsPreview
- Feed v2: time grouping (Now/Today/Earlier), impact labels, interpretation, direction badges
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestMiniAppHomeV2:
    """Tests for /api/miniapp/home endpoint with v2 intelligence layer"""
    
    def test_home_returns_ok(self):
        """Test home endpoint returns 200 OK"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=BTC", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") == True, "Response should have ok=true"
        print("✓ Home endpoint returns 200 OK")
    
    def test_decision_has_mode(self):
        """Test decision has mode (DEFENSIVE/STANDARD/AGGRESSIVE)"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=BTC", timeout=30)
        data = response.json()
        decision = data.get("decision", {})
        assert "mode" in decision, "Decision should have 'mode' field"
        assert decision["mode"] in ["DEFENSIVE", "STANDARD", "AGGRESSIVE"], f"Mode should be DEFENSIVE/STANDARD/AGGRESSIVE, got {decision['mode']}"
        print(f"✓ Decision mode: {decision['mode']}")
    
    def test_decision_has_strength(self):
        """Test decision has strength (LOW_EDGE/MODERATE/HIGH)"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=BTC", timeout=30)
        data = response.json()
        decision = data.get("decision", {})
        assert "strength" in decision, "Decision should have 'strength' field"
        assert decision["strength"] in ["LOW_EDGE", "MODERATE", "HIGH"], f"Strength should be LOW_EDGE/MODERATE/HIGH, got {decision['strength']}"
        print(f"✓ Decision strength: {decision['strength']}")
    
    def test_decision_has_risk_level(self):
        """Test decision has riskLevel (LOW/MEDIUM/HIGH)"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=BTC", timeout=30)
        data = response.json()
        decision = data.get("decision", {})
        assert "riskLevel" in decision, "Decision should have 'riskLevel' field"
        assert decision["riskLevel"] in ["LOW", "MEDIUM", "HIGH"], f"RiskLevel should be LOW/MEDIUM/HIGH, got {decision['riskLevel']}"
        print(f"✓ Decision riskLevel: {decision['riskLevel']}")
    
    def test_action_plan_has_summary(self):
        """Test actionPlan has summary"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=BTC", timeout=30)
        data = response.json()
        action_plan = data.get("actionPlan", {})
        assert "summary" in action_plan, "ActionPlan should have 'summary' field"
        assert isinstance(action_plan["summary"], str), "Summary should be a string"
        assert len(action_plan["summary"]) > 0, "Summary should not be empty"
        print(f"✓ ActionPlan summary: {action_plan['summary']}")
    
    def test_action_plan_has_next_trigger(self):
        """Test actionPlan has nextTrigger"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=BTC", timeout=30)
        data = response.json()
        action_plan = data.get("actionPlan", {})
        assert "nextTrigger" in action_plan, "ActionPlan should have 'nextTrigger' field"
        assert isinstance(action_plan["nextTrigger"], str), "NextTrigger should be a string"
        print(f"✓ ActionPlan nextTrigger: {action_plan['nextTrigger']}")
    
    def test_action_plan_has_comment(self):
        """Test actionPlan has comment"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=BTC", timeout=30)
        data = response.json()
        action_plan = data.get("actionPlan", {})
        assert "comment" in action_plan, "ActionPlan should have 'comment' field"
        print(f"✓ ActionPlan comment: {action_plan['comment']}")
    
    def test_pressure_net_has_direction(self):
        """Test pressure.net has direction"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=BTC", timeout=30)
        data = response.json()
        pressure = data.get("pressure", {})
        net = pressure.get("net", {})
        assert "direction" in net, "Pressure.net should have 'direction' field"
        assert net["direction"] in ["BULLISH", "BEARISH", "MIXED"], f"Direction should be BULLISH/BEARISH/MIXED, got {net['direction']}"
        print(f"✓ Pressure.net direction: {net['direction']}")
    
    def test_pressure_net_has_confidence(self):
        """Test pressure.net has confidence"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=BTC", timeout=30)
        data = response.json()
        pressure = data.get("pressure", {})
        net = pressure.get("net", {})
        assert "confidence" in net, "Pressure.net should have 'confidence' field"
        assert net["confidence"] in ["LOW", "MED", "HIGH"], f"Confidence should be LOW/MED/HIGH, got {net['confidence']}"
        print(f"✓ Pressure.net confidence: {net['confidence']}")
    
    def test_pressure_net_has_summary(self):
        """Test pressure.net has summary"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=BTC", timeout=30)
        data = response.json()
        pressure = data.get("pressure", {})
        net = pressure.get("net", {})
        assert "summary" in net, "Pressure.net should have 'summary' field"
        assert isinstance(net["summary"], str), "Summary should be a string"
        assert len(net["summary"]) > 0, "Summary should not be empty"
        print(f"✓ Pressure.net summary: {net['summary']}")
    
    def test_market_story_has_text(self):
        """Test marketStory has text"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=BTC", timeout=30)
        data = response.json()
        market_story = data.get("marketStory", {})
        assert "text" in market_story, "MarketStory should have 'text' field"
        assert isinstance(market_story["text"], str), "Text should be a string"
        assert len(market_story["text"]) > 0, "Text should not be empty"
        print(f"✓ MarketStory text: {market_story['text']}")
    
    def test_market_story_has_regime(self):
        """Test marketStory has regime"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=BTC", timeout=30)
        data = response.json()
        market_story = data.get("marketStory", {})
        assert "regime" in market_story, "MarketStory should have 'regime' field"
        assert market_story["regime"] in ["TRENDING", "UNCERTAIN", "TRANSITIONING"], f"Regime should be TRENDING/UNCERTAIN/TRANSITIONING, got {market_story['regime']}"
        print(f"✓ MarketStory regime: {market_story['regime']}")
    
    def test_why_array_has_at_least_2_reasons(self):
        """Test why array has at least 2 reasons"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=BTC", timeout=30)
        data = response.json()
        why = data.get("why", [])
        assert isinstance(why, list), "Why should be a list"
        assert len(why) >= 2, f"Why should have at least 2 reasons, got {len(why)}"
        for reason in why:
            assert isinstance(reason, str), "Each reason should be a string"
        print(f"✓ Why array has {len(why)} reasons: {why[:2]}...")
    
    def test_timeline_array_exists(self):
        """Test timeline array exists"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=BTC", timeout=30)
        data = response.json()
        timeline = data.get("timeline", [])
        assert isinstance(timeline, list), "Timeline should be a list"
        print(f"✓ Timeline array exists with {len(timeline)} items")
        if len(timeline) > 0:
            for item in timeline:
                assert "time" in item, "Timeline item should have 'time'"
                assert "decision" in item, "Timeline item should have 'decision'"
            print(f"✓ Timeline items have time and decision fields")
    
    def test_structure_has_insight(self):
        """Test structure has insight text"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=BTC", timeout=30)
        data = response.json()
        structure = data.get("structure", {})
        assert "insight" in structure, "Structure should have 'insight' field"
        assert isinstance(structure["insight"], str), "Insight should be a string"
        assert len(structure["insight"]) > 0, "Insight should not be empty"
        print(f"✓ Structure insight: {structure['insight']}")
    
    def test_alerts_preview_has_impact(self):
        """Test alertsPreview items have impact (HIGH/MED/LOW)"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=BTC", timeout=30)
        data = response.json()
        alerts = data.get("alertsPreview", [])
        assert isinstance(alerts, list), "AlertsPreview should be a list"
        if len(alerts) > 0:
            for alert in alerts:
                assert "impact" in alert, "Alert should have 'impact' field"
                assert alert["impact"] in ["HIGH", "MED", "LOW"], f"Impact should be HIGH/MED/LOW, got {alert['impact']}"
            print(f"✓ AlertsPreview has {len(alerts)} items with impact levels")
        else:
            print("✓ AlertsPreview is empty (no recent alerts)")


class TestMiniAppFeedV2:
    """Tests for /api/miniapp/feed endpoint with v2 time grouping"""
    
    def test_feed_returns_ok(self):
        """Test feed endpoint returns 200 OK"""
        response = requests.get(f"{BASE_URL}/api/miniapp/feed", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") == True, "Response should have ok=true"
        print("✓ Feed endpoint returns 200 OK")
    
    def test_feed_has_sections_array(self):
        """Test feed has sections array"""
        response = requests.get(f"{BASE_URL}/api/miniapp/feed", timeout=30)
        data = response.json()
        assert "sections" in data, "Feed should have 'sections' field"
        assert isinstance(data["sections"], list), "Sections should be a list"
        print(f"✓ Feed has sections array with {len(data['sections'])} sections")
    
    def test_feed_sections_have_now_today_earlier(self):
        """Test feed sections have Now/Today/Earlier groups"""
        response = requests.get(f"{BASE_URL}/api/miniapp/feed", timeout=30)
        data = response.json()
        sections = data.get("sections", [])
        labels = [s.get("label") for s in sections]
        assert "Now" in labels, "Sections should include 'Now'"
        assert "Today" in labels, "Sections should include 'Today'"
        assert "Earlier" in labels, "Sections should include 'Earlier'"
        print(f"✓ Feed sections have Now/Today/Earlier groups: {labels}")
    
    def test_feed_has_counts(self):
        """Test feed has counts object"""
        response = requests.get(f"{BASE_URL}/api/miniapp/feed", timeout=30)
        data = response.json()
        assert "counts" in data, "Feed should have 'counts' field"
        counts = data["counts"]
        assert "all" in counts, "Counts should have 'all'"
        assert "high" in counts, "Counts should have 'high'"
        print(f"✓ Feed counts: all={counts['all']}, high={counts['high']}")
    
    def test_feed_items_have_interpretation(self):
        """Test feed items have interpretation field"""
        response = requests.get(f"{BASE_URL}/api/miniapp/feed", timeout=30)
        data = response.json()
        sections = data.get("sections", [])
        found_item = False
        for section in sections:
            items = section.get("items", [])
            for item in items:
                found_item = True
                assert "interpretation" in item, "Feed item should have 'interpretation' field"
                assert isinstance(item["interpretation"], str), "Interpretation should be a string"
        if found_item:
            print("✓ Feed items have interpretation field")
        else:
            print("✓ No feed items to check (empty feed)")
    
    def test_feed_items_have_direction(self):
        """Test feed items have direction field"""
        response = requests.get(f"{BASE_URL}/api/miniapp/feed", timeout=30)
        data = response.json()
        sections = data.get("sections", [])
        found_item = False
        for section in sections:
            items = section.get("items", [])
            for item in items:
                found_item = True
                assert "direction" in item, "Feed item should have 'direction' field"
                assert item["direction"] in ["BULLISH", "BEARISH", "NEUTRAL"], f"Direction should be BULLISH/BEARISH/NEUTRAL, got {item['direction']}"
        if found_item:
            print("✓ Feed items have direction field")
        else:
            print("✓ No feed items to check (empty feed)")
    
    def test_feed_items_have_impact(self):
        """Test feed items have impact field"""
        response = requests.get(f"{BASE_URL}/api/miniapp/feed", timeout=30)
        data = response.json()
        sections = data.get("sections", [])
        found_item = False
        for section in sections:
            items = section.get("items", [])
            for item in items:
                found_item = True
                assert "impact" in item, "Feed item should have 'impact' field"
                assert item["impact"] in ["HIGH", "MED", "LOW"], f"Impact should be HIGH/MED/LOW, got {item['impact']}"
        if found_item:
            print("✓ Feed items have impact field")
        else:
            print("✓ No feed items to check (empty feed)")
    
    def test_feed_items_have_title(self):
        """Test feed items have title field"""
        response = requests.get(f"{BASE_URL}/api/miniapp/feed", timeout=30)
        data = response.json()
        sections = data.get("sections", [])
        found_item = False
        for section in sections:
            items = section.get("items", [])
            for item in items:
                found_item = True
                assert "title" in item, "Feed item should have 'title' field"
                assert isinstance(item["title"], str), "Title should be a string"
        if found_item:
            print("✓ Feed items have title field")
        else:
            print("✓ No feed items to check (empty feed)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
