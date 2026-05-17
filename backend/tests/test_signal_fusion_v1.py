"""
Signal Fusion v1 Tests - Decision Intelligence System

Tests for:
- Exchange direction normalization (SHORT→BEARISH, LONG→BULLISH)
- Signal Fusion: 2+ aligned sources produce HIGH_CONVICTION or EXTREME decisionType
- Score boost: +2/-2 for high fusion, +4/-4 for extreme fusion
- Conflicted signals produce penalty
- Decision mapping: score>=4→BUY, score<=-4→SELL, |score|<2→WAIT, else→AVOID
- Existing notification endpoints still work
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestSignalFusionDecisionEndpoint:
    """Test GET /api/notifications/decision/{asset}?horizon= returns correct fusion object"""

    def test_decision_endpoint_returns_fusion_object(self):
        """Verify decision endpoint returns fusion object with alignedSignals, direction, strength"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/BTC?horizon=30D")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Response should have ok=True"
        
        # Check fusion object exists in components
        components = data.get("components", {})
        assert "fusion" in components, "Components should include 'fusion'"
        
        fusion = components["fusion"]
        assert "alignedSignals" in fusion, "Fusion should have 'alignedSignals'"
        assert "direction" in fusion, "Fusion should have 'direction'"
        assert "strength" in fusion, "Fusion should have 'strength'"
        assert "sources" in fusion, "Fusion should have 'sources'"
        
        # Validate types
        assert isinstance(fusion["alignedSignals"], int), "alignedSignals should be int"
        assert fusion["direction"] in ["bullish", "bearish", "neutral", "mixed"], f"Invalid direction: {fusion['direction']}"
        assert fusion["strength"] in ["normal", "high", "extreme", "conflicted"], f"Invalid strength: {fusion['strength']}"
        assert isinstance(fusion["sources"], list), "sources should be a list"
        
        print(f"PASS: Fusion object structure correct - alignedSignals={fusion['alignedSignals']}, direction={fusion['direction']}, strength={fusion['strength']}")

    def test_decision_type_field_exists(self):
        """Verify decisionType field exists and is valid"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/BTC?horizon=30D")
        assert response.status_code == 200
        
        data = response.json()
        assert "decisionType" in data, "Response should have 'decisionType'"
        assert data["decisionType"] in ["NORMAL", "HIGH_CONVICTION", "EXTREME"], f"Invalid decisionType: {data['decisionType']}"
        
        print(f"PASS: decisionType={data['decisionType']}")


class TestExchangeDirectionNormalization:
    """Test Exchange direction normalization: SHORT→BEARISH, LONG→BULLISH"""

    def test_exchange_component_direction_normalized(self):
        """Verify exchange component direction is normalized (not SHORT/LONG)"""
        for asset in ["BTC", "ETH", "SOL"]:
            for horizon in ["24H", "7D", "30D"]:
                response = requests.get(f"{BASE_URL}/api/notifications/decision/{asset}?horizon={horizon}")
                assert response.status_code == 200
                
                data = response.json()
                exchange = data.get("components", {}).get("exchange", {})
                
                if exchange.get("available"):
                    direction = exchange.get("direction", "")
                    # Direction should be normalized to BULLISH/BEARISH/NEUTRAL, not SHORT/LONG
                    assert direction not in ["SHORT", "LONG", "UP", "DOWN"], \
                        f"Exchange direction should be normalized, got '{direction}' for {asset}/{horizon}"
                    assert direction in ["BULLISH", "BEARISH", "NEUTRAL", ""], \
                        f"Invalid normalized direction: '{direction}' for {asset}/{horizon}"
                    
                    print(f"PASS: {asset}/{horizon} exchange direction normalized to '{direction}'")


class TestSignalFusionLogic:
    """Test Signal Fusion logic for aligned sources"""

    def test_fusion_strength_based_on_aligned_signals(self):
        """Verify fusion strength is based on number of aligned signals"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/BTC?horizon=30D")
        assert response.status_code == 200
        
        data = response.json()
        fusion = data.get("components", {}).get("fusion", {})
        aligned = fusion.get("alignedSignals", 0)
        strength = fusion.get("strength", "")
        decision_type = data.get("decisionType", "")
        
        # Verify strength matches aligned signals
        if aligned >= 3:
            assert strength == "extreme", f"3+ aligned should be 'extreme', got '{strength}'"
            assert decision_type == "EXTREME", f"3+ aligned should be EXTREME decisionType, got '{decision_type}'"
        elif aligned >= 2:
            # Could be high or conflicted
            assert strength in ["high", "conflicted"], f"2 aligned should be 'high' or 'conflicted', got '{strength}'"
            if strength == "high":
                assert decision_type == "HIGH_CONVICTION", f"2 aligned high should be HIGH_CONVICTION, got '{decision_type}'"
        else:
            assert strength in ["normal", "conflicted"], f"<2 aligned should be 'normal' or 'conflicted', got '{strength}'"
            if strength == "normal":
                assert decision_type == "NORMAL", f"<2 aligned should be NORMAL decisionType, got '{decision_type}'"
        
        print(f"PASS: Fusion strength logic correct - aligned={aligned}, strength={strength}, decisionType={decision_type}")

    def test_fusion_sources_list_valid(self):
        """Verify fusion sources list contains valid directions"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/ETH?horizon=7D")
        assert response.status_code == 200
        
        data = response.json()
        fusion = data.get("components", {}).get("fusion", {})
        sources = fusion.get("sources", [])
        
        for source in sources:
            assert source in ["bullish", "bearish"], f"Invalid source direction: '{source}'"
        
        print(f"PASS: Fusion sources valid - {sources}")


class TestDecisionMapping:
    """Test decision mapping: score>=4→BUY, score<=-4→SELL, |score|<2→WAIT, else→AVOID"""

    def test_decision_mapping_logic(self):
        """Verify decision mapping based on score"""
        for asset in ["BTC", "ETH", "SOL"]:
            response = requests.get(f"{BASE_URL}/api/notifications/decision/{asset}?horizon=30D")
            assert response.status_code == 200
            
            data = response.json()
            score = data.get("score", 0)
            decision = data.get("decision", "")
            
            # Verify decision mapping
            if score >= 4:
                expected = "BUY"
            elif score <= -4:
                expected = "SELL"
            elif abs(score) < 2:
                expected = "WAIT"
            else:
                expected = "AVOID"
            
            assert decision == expected, f"Score {score} should map to {expected}, got {decision}"
            print(f"PASS: {asset} score={score} → decision={decision} (correct)")


class TestDecisionsOverview:
    """Test GET /api/notifications/decisions/overview returns 9 decisions"""

    def test_overview_returns_9_decisions(self):
        """Verify overview returns 9 decisions (3 assets × 3 horizons)"""
        response = requests.get(f"{BASE_URL}/api/notifications/decisions/overview")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        overview = data.get("overview", [])
        assert len(overview) == 9, f"Expected 9 decisions, got {len(overview)}"
        
        # Verify all combinations present
        expected_combos = set()
        for asset in ["BTC", "ETH", "SOL"]:
            for horizon in ["24H", "7D", "30D"]:
                expected_combos.add((asset, horizon))
        
        actual_combos = set()
        for item in overview:
            actual_combos.add((item["asset"], item["horizon"]))
        
        assert actual_combos == expected_combos, f"Missing combinations: {expected_combos - actual_combos}"
        
        print(f"PASS: Overview returns all 9 asset/horizon combinations")

    def test_overview_items_have_required_fields(self):
        """Verify each overview item has required fields"""
        response = requests.get(f"{BASE_URL}/api/notifications/decisions/overview")
        assert response.status_code == 200
        
        data = response.json()
        overview = data.get("overview", [])
        
        required_fields = ["asset", "horizon", "decision", "confidence", "score", "reasoning"]
        for item in overview:
            for field in required_fields:
                assert field in item, f"Missing field '{field}' in overview item"
        
        print(f"PASS: All overview items have required fields")


class TestTelegramDecisionSend:
    """Test POST /api/notifications/decision/{asset}/send formats HIGH_CONVICTION/EXTREME correctly"""

    def test_decision_send_endpoint_works(self):
        """Verify decision send endpoint returns correct structure"""
        response = requests.post(f"{BASE_URL}/api/notifications/decision/BTC/send?horizon=30D")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "decision" in data
        assert "decisionType" in data
        assert "telegram_sent" in data
        
        print(f"PASS: Decision send endpoint works - decision={data['decision']}, decisionType={data['decisionType']}, telegram_sent={data['telegram_sent']}")

    def test_decision_send_includes_fusion_in_components(self):
        """Verify decision send includes fusion in components"""
        response = requests.post(f"{BASE_URL}/api/notifications/decision/ETH/send?horizon=7D")
        assert response.status_code == 200
        
        data = response.json()
        components = data.get("components", {})
        assert "fusion" in components, "Components should include fusion"
        
        fusion = components["fusion"]
        assert "alignedSignals" in fusion
        assert "direction" in fusion
        assert "strength" in fusion
        
        print(f"PASS: Decision send includes fusion - strength={fusion['strength']}")


class TestExistingNotificationEndpoints:
    """Test existing notification endpoints still work"""

    def test_feed_endpoint(self):
        """GET /api/notifications/feed still works"""
        response = requests.get(f"{BASE_URL}/api/notifications/feed")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "notifications" in data
        assert "unread" in data
        
        print(f"PASS: Feed endpoint works - {len(data['notifications'])} notifications, {data['unread']} unread")

    def test_unread_count_endpoint(self):
        """GET /api/notifications/unread-count still works"""
        response = requests.get(f"{BASE_URL}/api/notifications/unread-count")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "unread" in data
        
        print(f"PASS: Unread count endpoint works - {data['unread']} unread")

    def test_events_endpoint(self):
        """GET /api/notifications/events still works"""
        response = requests.get(f"{BASE_URL}/api/notifications/events")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "events" in data
        
        print(f"PASS: Events endpoint works - {len(data['events'])} events")

    def test_events_publish_endpoint(self):
        """POST /api/notifications/events/publish still works"""
        test_event = {
            "type": "test.signal_fusion.v1",
            "source": "test",
            "asset": "BTC",
            "severity": "low",
            "title": "Signal Fusion Test Event",
            "payload": {"test": True}
        }
        response = requests.post(f"{BASE_URL}/api/notifications/events/publish", json=test_event)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        print(f"PASS: Events publish endpoint works")


class TestWhaleThresholdFilter:
    """Test POST /api/notifications/events/onchain-whale whale threshold $3M filter"""

    def test_whale_below_threshold_skipped(self):
        """Verify whale events below $3M are skipped"""
        test_event = {
            "asset": "BTC",
            "amount": 10,
            "valueUsd": 2_000_000  # Below $3M threshold
        }
        response = requests.post(f"{BASE_URL}/api/notifications/events/onchain-whale", json=test_event)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert data.get("skipped") is True, "Events below $3M should be skipped"
        assert "threshold" in data.get("reason", "").lower(), f"Reason should mention threshold: {data.get('reason')}"
        
        print(f"PASS: Whale event below $3M skipped - reason: {data.get('reason')}")

    def test_whale_above_threshold_processed(self):
        """Verify whale events above $3M are processed"""
        test_event = {
            "asset": "BTC",
            "amount": 100,
            "valueUsd": 5_000_000  # Above $3M threshold
        }
        response = requests.post(f"{BASE_URL}/api/notifications/events/onchain-whale", json=test_event)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        # Should not be skipped (or skipped due to dedupe, not threshold)
        if data.get("skipped"):
            assert "dedupe" in data.get("reason", "").lower(), f"If skipped, should be due to dedupe, not threshold: {data.get('reason')}"
        
        print(f"PASS: Whale event above $3M processed")


class TestSentimentSpikeThresholdFilter:
    """Test POST /api/notifications/events/sentiment-spike delta 0.2 threshold filter"""

    def test_sentiment_below_threshold_skipped(self):
        """Verify sentiment events with |delta| < 0.2 are skipped"""
        test_event = {
            "asset": "BTC",
            "delta": 0.1,  # Below 0.2 threshold
            "window": "4h"
        }
        response = requests.post(f"{BASE_URL}/api/notifications/events/sentiment-spike", json=test_event)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert data.get("skipped") is True, "Events with |delta| < 0.2 should be skipped"
        assert "threshold" in data.get("reason", "").lower(), f"Reason should mention threshold: {data.get('reason')}"
        
        print(f"PASS: Sentiment event below threshold skipped - reason: {data.get('reason')}")

    def test_sentiment_above_threshold_processed(self):
        """Verify sentiment events with |delta| >= 0.2 are processed"""
        test_event = {
            "asset": "ETH",
            "delta": 0.3,  # Above 0.2 threshold
            "window": "4h"
        }
        response = requests.post(f"{BASE_URL}/api/notifications/events/sentiment-spike", json=test_event)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        # Should not be skipped (or skipped due to dedupe, not threshold)
        if data.get("skipped"):
            assert "dedupe" in data.get("reason", "").lower(), f"If skipped, should be due to dedupe, not threshold: {data.get('reason')}"
        
        print(f"PASS: Sentiment event above threshold processed")


class TestFusionReasoningInResponse:
    """Test that fusion reasoning appears in response when strength != normal"""

    def test_fusion_reasoning_in_response(self):
        """Verify fusion reasoning appears when strength is high or extreme"""
        response = requests.get(f"{BASE_URL}/api/notifications/decision/BTC?horizon=30D")
        assert response.status_code == 200
        
        data = response.json()
        fusion = data.get("components", {}).get("fusion", {})
        reasoning = data.get("reasoning", [])
        
        if fusion.get("strength") in ["high", "extreme"]:
            # Should have SIGNAL FUSION in reasoning
            fusion_reasons = [r for r in reasoning if "SIGNAL FUSION" in r.upper() or "FUSION" in r.upper()]
            assert len(fusion_reasons) > 0, f"High/extreme fusion should have SIGNAL FUSION in reasoning: {reasoning}"
            print(f"PASS: Fusion reasoning present for strength={fusion['strength']}: {fusion_reasons[0]}")
        else:
            print(f"INFO: Fusion strength is '{fusion.get('strength')}', no fusion reasoning expected")


class TestAllAssetsAllHorizons:
    """Comprehensive test across all assets and horizons"""

    def test_all_combinations_return_valid_response(self):
        """Test all 9 asset/horizon combinations return valid responses"""
        assets = ["BTC", "ETH", "SOL"]
        horizons = ["24H", "7D", "30D"]
        
        for asset in assets:
            for horizon in horizons:
                response = requests.get(f"{BASE_URL}/api/notifications/decision/{asset}?horizon={horizon}")
                assert response.status_code == 200, f"Failed for {asset}/{horizon}"
                
                data = response.json()
                assert data.get("ok") is True
                assert data.get("asset") == asset
                assert data.get("horizonRaw") == horizon
                assert data.get("decision") in ["BUY", "SELL", "WAIT", "AVOID"]
                assert data.get("decisionType") in ["NORMAL", "HIGH_CONVICTION", "EXTREME"]
                assert "components" in data
                assert "fusion" in data["components"]
                
                print(f"PASS: {asset}/{horizon} - decision={data['decision']}, type={data['decisionType']}, score={data['score']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
