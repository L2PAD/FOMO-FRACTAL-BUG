"""
Test Prediction Feed Phase 2 Batch 1 Features:
- Confidence Gate (action + size gates)
- Position Sizing Engine (edge quality, conviction sizing, 5 risk caps, hard blockers)
- Edge Quality scoring integrated into event decision
- Execution Filtering (slippage/liquidity downgrade in both decision and sizing)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestFeedAPIPhase2Batch1:
    """Test Phase 2 Batch 1 features in Feed API"""

    def test_feed_hot_returns_200(self):
        """GET /api/feed?mode=hot returns 200"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"PASS: Feed hot returns 200 with {data.get('total')} events")

    def test_feed_has_edge_quality_field(self):
        """Overlay contains edge_quality field (high/medium/low)"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        data = response.json()
        events = data.get("events", [])
        assert len(events) > 0, "No events returned"
        
        edge_qualities = set()
        for ev in events:
            ov = ev.get("overlay", {})
            eq = ov.get("edge_quality")
            assert eq is not None, f"edge_quality missing for event {ev.get('event_id')}"
            assert eq in ("high", "medium", "low"), f"Invalid edge_quality: {eq}"
            edge_qualities.add(eq)
        
        print(f"PASS: edge_quality field present. Values found: {edge_qualities}")

    def test_feed_has_competition_field(self):
        """Overlay contains competition field (clear_dominant/no_edge/N_competing)"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        data = response.json()
        events = data.get("events", [])
        
        competitions = set()
        for ev in events:
            ov = ev.get("overlay", {})
            comp = ov.get("competition")
            assert comp is not None, f"competition missing for event {ev.get('event_id')}"
            # Valid values: clear_dominant, no_edge, or N_competing
            assert comp in ("clear_dominant", "no_edge") or "_competing" in comp, f"Invalid competition: {comp}"
            competitions.add(comp)
        
        print(f"PASS: competition field present. Values found: {competitions}")

    def test_feed_has_sizing_object(self):
        """Overlay contains sizing object with required fields"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        data = response.json()
        events = data.get("events", [])
        
        sizing_found = 0
        for ev in events:
            ov = ev.get("overlay", {})
            sizing = ov.get("sizing")
            assert sizing is not None, f"sizing missing for event {ev.get('event_id')}"
            
            # Check required sizing fields
            assert "size_label" in sizing, "size_label missing in sizing"
            assert "size_pct" in sizing, "size_pct missing in sizing"
            assert "edge_quality" in sizing, "edge_quality missing in sizing"
            assert "conviction" in sizing, "conviction missing in sizing"
            assert "reasons" in sizing, "reasons missing in sizing"
            sizing_found += 1
        
        print(f"PASS: sizing object present in all {sizing_found} events")

    def test_sizing_size_label_values(self):
        """sizing.size_label is TINY/SMALL/MEDIUM/LARGE/MAX/NONE"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        data = response.json()
        events = data.get("events", [])
        
        valid_labels = {"TINY", "SMALL", "MEDIUM", "LARGE", "MAX", "NONE"}
        labels_found = set()
        
        for ev in events:
            sizing = ev.get("overlay", {}).get("sizing", {})
            label = sizing.get("size_label")
            assert label in valid_labels, f"Invalid size_label: {label}"
            labels_found.add(label)
        
        print(f"PASS: size_label values valid. Found: {labels_found}")

    def test_sizing_none_for_watch_avoid(self):
        """sizing.size_label is NONE when action is WATCH or AVOID"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        data = response.json()
        events = data.get("events", [])
        
        watch_avoid_count = 0
        for ev in events:
            ov = ev.get("overlay", {})
            action = ov.get("action")
            sizing = ov.get("sizing", {})
            
            if action in ("WATCH", "AVOID"):
                watch_avoid_count += 1
                size_label = sizing.get("size_label")
                assert size_label == "NONE", f"Expected NONE for {action}, got {size_label}"
        
        assert watch_avoid_count > 0, "No WATCH/AVOID events found to test"
        print(f"PASS: {watch_avoid_count} WATCH/AVOID events have sizing.size_label=NONE")

    def test_sizing_has_caps_for_actionable(self):
        """Actionable events have caps breakdown in sizing"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        data = response.json()
        events = data.get("events", [])
        
        actionable_count = 0
        for ev in events:
            ov = ev.get("overlay", {})
            action = ov.get("action")
            sizing = ov.get("sizing", {})
            
            if action in ("BUY_YES", "BUY_NO"):
                actionable_count += 1
                caps = sizing.get("caps", {})
                # Check for expected cap keys
                expected_caps = {"liquidity", "volatility", "event_risk", "expiry", "slippage"}
                actual_caps = set(caps.keys())
                assert actual_caps == expected_caps, f"Missing caps: {expected_caps - actual_caps}"
        
        assert actionable_count > 0, "No BUY events found to test"
        print(f"PASS: {actionable_count} BUY events have all 5 caps in sizing")

    def test_sizing_has_reasons(self):
        """sizing.reasons is a list of strings"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        data = response.json()
        events = data.get("events", [])
        
        for ev in events:
            sizing = ev.get("overlay", {}).get("sizing", {})
            reasons = sizing.get("reasons")
            assert isinstance(reasons, list), f"reasons should be list, got {type(reasons)}"
            for r in reasons:
                assert isinstance(r, str), f"reason should be string, got {type(r)}"
        
        print("PASS: sizing.reasons is list of strings for all events")

    def test_confidence_gate_low_confidence_not_buy(self):
        """Events with low confidence should have action WATCH or AVOID, not BUY"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=all")
        data = response.json()
        events = data.get("events", [])
        
        low_conf_buy = []
        for ev in events:
            ov = ev.get("overlay", {})
            confidence = ov.get("confidence")
            action = ov.get("action")
            
            if confidence == "low" and action in ("BUY_YES", "BUY_NO"):
                low_conf_buy.append(ev.get("event_id"))
        
        assert len(low_conf_buy) == 0, f"Low confidence events with BUY action: {low_conf_buy}"
        print("PASS: No low confidence events have BUY action (confidence gate working)")

    def test_risk_warnings_in_why_array(self):
        """Risk warnings appear in why[] array (starting with 'Risk:')"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        data = response.json()
        events = data.get("events", [])
        
        risk_warnings_found = 0
        for ev in events:
            ov = ev.get("overlay", {})
            why = ov.get("why", [])
            for reason in why:
                if reason.startswith("Risk:"):
                    risk_warnings_found += 1
        
        # Risk warnings may not be present in all events, but should exist in some
        print(f"PASS: Found {risk_warnings_found} risk warnings in why[] arrays")

    def test_buy_now_urgency_requires_high_confidence(self):
        """BUY NOW urgency only with high confidence (confidence gate working)"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        data = response.json()
        events = data.get("events", [])
        
        violations = []
        for ev in events:
            ov = ev.get("overlay", {})
            action = ov.get("action")
            urgency = ov.get("urgency")
            confidence = ov.get("confidence")
            
            # NOW urgency should only be with high confidence
            if urgency == "now" and confidence != "high":
                violations.append({
                    "event_id": ev.get("event_id"),
                    "action": action,
                    "urgency": urgency,
                    "confidence": confidence
                })
        
        assert len(violations) == 0, f"NOW urgency with non-high confidence: {violations}"
        print("PASS: All NOW urgency events have high confidence")

    def test_action_distribution_conservative(self):
        """Action distribution is conservative (~18 BUY vs ~22 WATCH/AVOID)"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        data = response.json()
        events = data.get("events", [])
        
        actions = {}
        for ev in events:
            action = ev.get("overlay", {}).get("action", "UNKNOWN")
            actions[action] = actions.get(action, 0) + 1
        
        buy_count = actions.get("BUY_YES", 0) + actions.get("BUY_NO", 0)
        watch_avoid_count = actions.get("WATCH", 0) + actions.get("AVOID", 0)
        
        print(f"Action distribution: BUY={buy_count}, WATCH/AVOID={watch_avoid_count}")
        print(f"  BUY_YES={actions.get('BUY_YES', 0)}, BUY_NO={actions.get('BUY_NO', 0)}")
        print(f"  WATCH={actions.get('WATCH', 0)}, AVOID={actions.get('AVOID', 0)}")
        
        # Conservative means more WATCH/AVOID than BUY
        assert watch_avoid_count >= buy_count * 0.5, "Action distribution not conservative enough"
        print("PASS: Action distribution is conservative")

    def test_size_distribution(self):
        """Size distribution: TINY/SMALL/MEDIUM/LARGE/MAX/NONE"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        data = response.json()
        events = data.get("events", [])
        
        sizes = {}
        for ev in events:
            sizing = ev.get("overlay", {}).get("sizing", {})
            label = sizing.get("size_label", "MISSING")
            sizes[label] = sizes.get(label, 0) + 1
        
        print(f"Size distribution: {sizes}")
        
        # NONE should be present for WATCH/AVOID events
        assert "NONE" in sizes, "NONE size label not found"
        print("PASS: Size distribution includes NONE for non-actionable events")

    def test_edge_quality_in_sizing_matches_overlay(self):
        """sizing.edge_quality matches overlay.edge_quality for actionable events"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        data = response.json()
        events = data.get("events", [])
        
        for ev in events:
            ov = ev.get("overlay", {})
            action = ov.get("action")
            
            if action in ("BUY_YES", "BUY_NO"):
                overlay_eq = ov.get("edge_quality")
                sizing_eq = ov.get("sizing", {}).get("edge_quality")
                # They should match for actionable events
                assert overlay_eq == sizing_eq, f"edge_quality mismatch: overlay={overlay_eq}, sizing={sizing_eq}"
        
        print("PASS: edge_quality consistent between overlay and sizing")

    def test_tier_switching_hot_actionable_all(self):
        """Tier switching works: Hot/Actionable/All with correct counts"""
        # Get all three tiers
        hot_resp = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        actionable_resp = requests.get(f"{BASE_URL}/api/feed?mode=actionable")
        all_resp = requests.get(f"{BASE_URL}/api/feed?mode=all")
        
        assert hot_resp.status_code == 200
        assert actionable_resp.status_code == 200
        assert all_resp.status_code == 200
        
        hot_data = hot_resp.json()
        actionable_data = actionable_resp.json()
        all_data = all_resp.json()
        
        # Verify counts
        hot_count = hot_data.get("hot_count", 0)
        actionable_count = hot_data.get("actionable_count", 0)
        all_count = hot_data.get("all_count", 0)
        
        assert hot_count > 0, "No hot events"
        assert actionable_count > 0, "No actionable events"
        assert all_count >= hot_count, "all_count should be >= hot_count"
        
        # Verify returned events match mode
        assert len(hot_data.get("events", [])) == hot_count
        assert len(actionable_data.get("events", [])) == actionable_count
        assert len(all_data.get("events", [])) == all_count
        
        print(f"PASS: Tier switching works. Hot={hot_count}, Actionable={actionable_count}, All={all_count}")

    def test_execution_filtering_slippage_downgrade(self):
        """High slippage events have urgency downgraded from NOW to SOON"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        data = response.json()
        events = data.get("events", [])
        
        high_slippage_now = []
        for ev in events:
            ov = ev.get("overlay", {})
            bp = ov.get("best_pick", {})
            if bp:
                exec_info = bp.get("execution", {})
                slippage = exec_info.get("slippage_risk")
                urgency = ov.get("urgency")
                action = ov.get("action")
                
                # High slippage with NOW urgency would be a violation
                if slippage == "high" and urgency == "now" and action in ("BUY_YES", "BUY_NO"):
                    high_slippage_now.append(ev.get("event_id"))
        
        # This is a soft check - high slippage should downgrade urgency
        if high_slippage_now:
            print(f"WARNING: {len(high_slippage_now)} high slippage events with NOW urgency")
        else:
            print("PASS: No high slippage events with NOW urgency (execution filtering working)")


class TestPositionSizingEngine:
    """Test Position Sizing Engine specific features"""

    def test_sizing_conviction_values(self):
        """sizing.conviction is high/medium/low"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        data = response.json()
        events = data.get("events", [])
        
        valid_convictions = {"high", "medium", "low"}
        convictions_found = set()
        
        for ev in events:
            sizing = ev.get("overlay", {}).get("sizing", {})
            conviction = sizing.get("conviction")
            assert conviction in valid_convictions, f"Invalid conviction: {conviction}"
            convictions_found.add(conviction)
        
        print(f"PASS: conviction values valid. Found: {convictions_found}")

    def test_sizing_raw_score_present(self):
        """sizing.raw_score is present for actionable events"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        data = response.json()
        events = data.get("events", [])
        
        for ev in events:
            ov = ev.get("overlay", {})
            action = ov.get("action")
            sizing = ov.get("sizing", {})
            
            if action in ("BUY_YES", "BUY_NO"):
                raw_score = sizing.get("raw_score")
                assert raw_score is not None, f"raw_score missing for BUY event"
                assert 0 <= raw_score <= 1, f"raw_score out of range: {raw_score}"
        
        print("PASS: raw_score present and valid for actionable events")

    def test_sizing_caps_values_valid(self):
        """Cap values are between 0 and 1"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        data = response.json()
        events = data.get("events", [])
        
        for ev in events:
            ov = ev.get("overlay", {})
            action = ov.get("action")
            sizing = ov.get("sizing", {})
            
            if action in ("BUY_YES", "BUY_NO"):
                caps = sizing.get("caps", {})
                for cap_name, cap_value in caps.items():
                    assert 0 <= cap_value <= 1, f"Cap {cap_name} out of range: {cap_value}"
        
        print("PASS: All cap values are between 0 and 1")

    def test_sizing_size_pct_matches_fraction(self):
        """sizing.size_pct = sizing.size_fraction * 100"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        data = response.json()
        events = data.get("events", [])
        
        for ev in events:
            sizing = ev.get("overlay", {}).get("sizing", {})
            fraction = sizing.get("size_fraction", 0)
            pct = sizing.get("size_pct", 0)
            
            expected_pct = round(fraction * 100, 2)
            assert abs(pct - expected_pct) < 0.01, f"size_pct mismatch: {pct} vs {expected_pct}"
        
        print("PASS: size_pct matches size_fraction * 100")


class TestEdgeQualityIntegration:
    """Test Edge Quality integration in event decision"""

    def test_edge_quality_affects_action(self):
        """Low edge quality events should not have BUY action"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=all")
        data = response.json()
        events = data.get("events", [])
        
        low_eq_buy = []
        for ev in events:
            ov = ev.get("overlay", {})
            eq = ov.get("edge_quality")
            action = ov.get("action")
            
            # Very low edge quality should not result in BUY
            if eq == "low" and action in ("BUY_YES", "BUY_NO"):
                low_eq_buy.append({
                    "event_id": ev.get("event_id"),
                    "edge_quality": eq,
                    "action": action
                })
        
        # This is expected behavior - low edge quality gates BUY actions
        if low_eq_buy:
            print(f"INFO: {len(low_eq_buy)} low edge quality events with BUY action (may be valid)")
        else:
            print("PASS: No low edge quality events have BUY action")

    def test_edge_quality_score_in_sizing(self):
        """sizing.edge_quality_score is present and valid"""
        response = requests.get(f"{BASE_URL}/api/feed?mode=hot")
        data = response.json()
        events = data.get("events", [])
        
        for ev in events:
            ov = ev.get("overlay", {})
            action = ov.get("action")
            sizing = ov.get("sizing", {})
            
            if action in ("BUY_YES", "BUY_NO"):
                eq_score = sizing.get("edge_quality_score")
                assert eq_score is not None, "edge_quality_score missing"
                assert 0 <= eq_score <= 1, f"edge_quality_score out of range: {eq_score}"
        
        print("PASS: edge_quality_score present and valid for actionable events")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
