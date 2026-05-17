"""
Prediction Feed Phase 2 Tests — Structure Edge, Fair Prob v2, Event Decision Engine.

Tests Phase 2 integration:
- Structure Edge Engine (analyze_ladder, get_outcome_structure_edge)
- Fair Prob v2 (5-factor model)
- Event Decision Engine (decide_event with ranking, sibling resolution, conviction)
- API overlay fields: why, structure, structure_edge on best_pick
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestFeedPhase2API:
    """Phase 2 API endpoint tests"""

    def test_feed_hot_returns_phase2_overlay(self):
        """GET /api/feed?mode=hot returns Phase 2 overlay with new fields"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert data.get("hot_count", 0) > 0
        
        # Check first event has Phase 2 overlay fields
        events = data.get("events", [])
        assert len(events) > 0
        
        ev = events[0]
        ov = ev.get("overlay", {})
        
        # Phase 2 required fields
        assert "action" in ov, "Missing action field"
        assert "urgency" in ov, "Missing urgency field"
        assert "confidence" in ov, "Missing confidence field"
        assert "why" in ov, "Missing why field"
        assert isinstance(ov.get("why"), list), "why should be a list"
        
        # Action values
        assert ov["action"] in ("BUY_YES", "BUY_NO", "WATCH", "AVOID")
        assert ov["urgency"] in ("now", "soon", "watch")
        assert ov["confidence"] in ("high", "medium", "low")

    def test_feed_actionable_returns_real_edge_values(self):
        """GET /api/feed?mode=actionable returns events with real edge values"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=actionable")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        events = data.get("events", [])
        # Actionable events should have significant edge
        for ev in events[:5]:
            ov = ev.get("overlay", {})
            bp = ov.get("best_pick")
            if bp:
                edge = abs(bp.get("edge", 0))
                assert edge > 0.02, f"Actionable event should have edge > 2%, got {edge}"

    def test_feed_all_returns_all_events(self):
        """GET /api/feed?mode=all returns all events"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=all")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert data.get("total", 0) == data.get("all_count", 0)

    def test_feed_health_returns_status(self):
        """GET /api/feed/health returns health status"""
        response = requests.get(f"{BASE_URL}/api/feed/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "events_count" in data
        assert "markets_count" in data


class TestPhase2OverlayStructure:
    """Tests for Phase 2 overlay structure"""

    def test_overlay_action_values(self):
        """Overlay action should be BUY_YES/BUY_NO/WATCH/AVOID"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        data = response.json()
        
        for ev in data.get("events", [])[:10]:
            ov = ev.get("overlay", {})
            action = ov.get("action")
            assert action in ("BUY_YES", "BUY_NO", "WATCH", "AVOID"), f"Invalid action: {action}"

    def test_overlay_urgency_values(self):
        """Overlay urgency should be now/soon/watch"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        data = response.json()
        
        for ev in data.get("events", [])[:10]:
            ov = ev.get("overlay", {})
            urgency = ov.get("urgency")
            assert urgency in ("now", "soon", "watch"), f"Invalid urgency: {urgency}"

    def test_overlay_confidence_values(self):
        """Overlay confidence should be high/medium/low"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        data = response.json()
        
        for ev in data.get("events", [])[:10]:
            ov = ev.get("overlay", {})
            conf = ov.get("confidence")
            assert conf in ("high", "medium", "low"), f"Invalid confidence: {conf}"

    def test_why_array_present(self):
        """Why array with reasoning should be present in overlay"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        data = response.json()
        
        events_with_why = 0
        for ev in data.get("events", []):
            ov = ev.get("overlay", {})
            why = ov.get("why", [])
            if why and len(why) > 0:
                events_with_why += 1
                # Check why items are strings
                for reason in why:
                    assert isinstance(reason, str), f"Why reason should be string: {reason}"
        
        # At least some events should have why reasons
        assert events_with_why > 0, "No events have why reasons"


class TestStructureAnalysis:
    """Tests for Structure Edge Engine integration"""

    def test_structure_present_for_multi_outcome(self):
        """Structure analysis should be present for multi-outcome events"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        data = response.json()
        
        multi_with_structure = 0
        for ev in data.get("events", []):
            if ev.get("is_multi") and ev.get("markets_count", 0) >= 3:
                ov = ev.get("overlay", {})
                structure = ov.get("structure")
                if structure:
                    multi_with_structure += 1
                    # Check structure fields
                    assert "ladder_quality" in structure
                    assert "monotonic" in structure
                    assert isinstance(structure.get("monotonic"), bool)
        
        # At least some multi-outcome events should have structure
        assert multi_with_structure > 0, "No multi-outcome events have structure analysis"

    def test_structure_ladder_quality(self):
        """Structure ladder_quality should be 0-1"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        data = response.json()
        
        for ev in data.get("events", []):
            ov = ev.get("overlay", {})
            structure = ov.get("structure")
            if structure:
                lq = structure.get("ladder_quality")
                if lq is not None:
                    assert 0 <= lq <= 1, f"ladder_quality should be 0-1, got {lq}"

    def test_structure_dominant_issue(self):
        """Structure dominant_issue should be string or None"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        data = response.json()
        
        for ev in data.get("events", []):
            ov = ev.get("overlay", {})
            structure = ov.get("structure")
            if structure:
                issue = structure.get("dominant_issue")
                if issue is not None:
                    assert isinstance(issue, str), f"dominant_issue should be string: {issue}"


class TestBestPickStructureEdge:
    """Tests for structure_edge on best_pick"""

    def test_best_pick_has_structure_edge(self):
        """Best pick should include structure_edge value"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        data = response.json()
        
        picks_with_struct_edge = 0
        for ev in data.get("events", []):
            ov = ev.get("overlay", {})
            bp = ov.get("best_pick")
            if bp:
                if "structure_edge" in bp:
                    picks_with_struct_edge += 1
                    se = bp.get("structure_edge")
                    assert isinstance(se, (int, float)), f"structure_edge should be numeric: {se}"
        
        assert picks_with_struct_edge > 0, "No best_picks have structure_edge"

    def test_top_outcomes_have_structure_edge(self):
        """Top outcomes should include structure_edge"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        data = response.json()
        
        outcomes_with_struct_edge = 0
        for ev in data.get("events", []):
            ov = ev.get("overlay", {})
            top = ov.get("top_outcomes", [])
            for o in top:
                if "structure_edge" in o:
                    outcomes_with_struct_edge += 1
        
        assert outcomes_with_struct_edge > 0, "No top_outcomes have structure_edge"


class TestAssetFilters:
    """Tests for asset filters"""

    @pytest.mark.parametrize("asset", ["BTC", "ETH", "SOL", "XRP", "ALT"])
    def test_asset_filter(self, asset):
        """Asset filters should work correctly"""
        response = requests.get(f"{BASE_URL}/api/feed?asset={asset}")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        # All returned events should match asset filter
        for ev in data.get("events", []):
            assert ev.get("asset_group") == asset, f"Event asset {ev.get('asset_group')} != {asset}"


class TestTierSelector:
    """Tests for tier selector"""

    def test_tier_hot_count_matches(self):
        """Hot tier should return correct count"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        data = response.json()
        
        assert data.get("ok") is True
        assert data.get("total") == data.get("hot_count")

    def test_tier_actionable_count_matches(self):
        """Actionable tier should return correct count"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=actionable")
        data = response.json()
        
        assert data.get("ok") is True
        assert data.get("total") == data.get("actionable_count")

    def test_tier_all_count_matches(self):
        """All tier should return correct count"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=all")
        data = response.json()
        
        assert data.get("ok") is True
        assert data.get("total") == data.get("all_count")


class TestMarketOverlay:
    """Tests for market-level overlay"""

    def test_market_overlay_has_structure_edge(self):
        """Market overlay should include structure_edge"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        data = response.json()
        
        markets_with_struct_edge = 0
        for ev in data.get("events", []):
            for m in ev.get("markets", []):
                ov = m.get("overlay")
                if ov and "structure_edge" in ov:
                    markets_with_struct_edge += 1
        
        assert markets_with_struct_edge > 0, "No market overlays have structure_edge"

    def test_market_overlay_has_fair_prob(self):
        """Market overlay should include fair_prob"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        data = response.json()
        
        for ev in data.get("events", []):
            for m in ev.get("markets", []):
                ov = m.get("overlay")
                if ov:
                    assert "fair_prob" in ov, "Market overlay missing fair_prob"
                    assert "edge" in ov, "Market overlay missing edge"
                    assert "edge_pct" in ov, "Market overlay missing edge_pct"


class TestEventDecisionEngine:
    """Tests for Event Decision Engine output"""

    def test_decision_summary_present(self):
        """Event overlay should have summary"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        data = response.json()
        
        for ev in data.get("events", []):
            ov = ev.get("overlay", {})
            summary = ov.get("summary")
            assert summary is not None, "Missing summary in overlay"
            assert isinstance(summary, str), "Summary should be string"

    def test_decision_outcomes_analyzed(self):
        """Event overlay should have outcomes_analyzed count"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        data = response.json()
        
        for ev in data.get("events", []):
            ov = ev.get("overlay", {})
            analyzed = ov.get("outcomes_analyzed")
            assert analyzed is not None, "Missing outcomes_analyzed"
            assert isinstance(analyzed, int), "outcomes_analyzed should be int"

    def test_decision_outcomes_with_edge(self):
        """Event overlay should have outcomes_with_edge count"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        data = response.json()
        
        for ev in data.get("events", []):
            ov = ev.get("overlay", {})
            with_edge = ov.get("outcomes_with_edge")
            assert with_edge is not None, "Missing outcomes_with_edge"
            assert isinstance(with_edge, int), "outcomes_with_edge should be int"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
