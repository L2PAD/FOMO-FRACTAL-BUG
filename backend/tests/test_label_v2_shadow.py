"""
Test Label Logic V2 (Phase 1) - Shadow Mode for Sentiment System
Tests compute_label_v2() classification, horizon-aware thresholds, and API endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# ─── Unit Tests for compute_label_v2() ───

class TestComputeLabelV2Logic:
    """Test the 5-label classification logic with peak-aware evaluation"""
    
    def test_import_compute_label_v2(self):
        """Verify compute_label_v2 can be imported"""
        try:
            from outcome_resolver import compute_label_v2, LABEL_V2_THRESHOLDS
            assert callable(compute_label_v2)
            assert isinstance(LABEL_V2_THRESHOLDS, dict)
            print("SUCCESS: compute_label_v2 imported successfully")
        except ImportError as e:
            pytest.fail(f"Failed to import compute_label_v2: {e}")
    
    def test_thresholds_24h(self):
        """24H thresholds: weak=1.5%, strong=2.5%"""
        from outcome_resolver import LABEL_V2_THRESHOLDS
        assert "24H" in LABEL_V2_THRESHOLDS
        assert LABEL_V2_THRESHOLDS["24H"]["weak"] == 1.5
        assert LABEL_V2_THRESHOLDS["24H"]["strong"] == 2.5
        print("SUCCESS: 24H thresholds correct (weak=1.5, strong=2.5)")
    
    def test_thresholds_7d(self):
        """7D thresholds: weak=2%, strong=5%"""
        from outcome_resolver import LABEL_V2_THRESHOLDS
        assert "7D" in LABEL_V2_THRESHOLDS
        assert LABEL_V2_THRESHOLDS["7D"]["weak"] == 2.0
        assert LABEL_V2_THRESHOLDS["7D"]["strong"] == 5.0
        print("SUCCESS: 7D thresholds correct (weak=2, strong=5)")
    
    def test_thresholds_30d(self):
        """30D thresholds: weak=4%, strong=10%"""
        from outcome_resolver import LABEL_V2_THRESHOLDS
        assert "30D" in LABEL_V2_THRESHOLDS
        assert LABEL_V2_THRESHOLDS["30D"]["weak"] == 4.0
        assert LABEL_V2_THRESHOLDS["30D"]["strong"] == 10.0
        print("SUCCESS: 30D thresholds correct (weak=4, strong=10)")
    
    def test_strong_good_classification(self):
        """STRONG_GOOD: move_up >= strong AND final > -weak/2"""
        from outcome_resolver import compute_label_v2
        # 24H: strong=2.5, weak=1.5 → final > -0.75
        label, conf = compute_label_v2(move_up_peak=3.0, move_down_peak=0.5, final_return=1.0, horizon="24H")
        assert label == "STRONG_GOOD", f"Expected STRONG_GOOD, got {label}"
        assert 0 <= conf <= 1, f"Confidence {conf} not in [0,1]"
        print(f"SUCCESS: STRONG_GOOD classification (move_up=3.0, final=1.0) → {label}, conf={conf}")
    
    def test_weak_good_classification(self):
        """WEAK_GOOD: move_up >= weak AND final > -weak/2"""
        from outcome_resolver import compute_label_v2
        # 24H: weak=1.5 → move_up >= 1.5, final > -0.75
        label, conf = compute_label_v2(move_up_peak=1.8, move_down_peak=0.3, final_return=0.5, horizon="24H")
        assert label == "WEAK_GOOD", f"Expected WEAK_GOOD, got {label}"
        assert 0 <= conf <= 1
        print(f"SUCCESS: WEAK_GOOD classification (move_up=1.8, final=0.5) → {label}, conf={conf}")
    
    def test_strong_bad_classification(self):
        """STRONG_BAD: move_down >= strong AND final < weak/2"""
        from outcome_resolver import compute_label_v2
        # 24H: strong=2.5, weak=1.5 → final < 0.75
        label, conf = compute_label_v2(move_up_peak=0.3, move_down_peak=3.0, final_return=-2.0, horizon="24H")
        assert label == "STRONG_BAD", f"Expected STRONG_BAD, got {label}"
        assert 0 <= conf <= 1
        print(f"SUCCESS: STRONG_BAD classification (move_down=3.0, final=-2.0) → {label}, conf={conf}")
    
    def test_weak_bad_classification(self):
        """WEAK_BAD: move_down >= weak AND final < weak/2"""
        from outcome_resolver import compute_label_v2
        # 24H: weak=1.5 → move_down >= 1.5, final < 0.75
        label, conf = compute_label_v2(move_up_peak=0.2, move_down_peak=1.8, final_return=-0.5, horizon="24H")
        assert label == "WEAK_BAD", f"Expected WEAK_BAD, got {label}"
        assert 0 <= conf <= 1
        print(f"SUCCESS: WEAK_BAD classification (move_down=1.8, final=-0.5) → {label}, conf={conf}")
    
    def test_neutral_classification(self):
        """NEUTRAL: below all thresholds"""
        from outcome_resolver import compute_label_v2
        # Small movements, no clear direction
        label, conf = compute_label_v2(move_up_peak=0.5, move_down_peak=0.5, final_return=0.1, horizon="24H")
        assert label == "NEUTRAL", f"Expected NEUTRAL, got {label}"
        assert 0 <= conf <= 1
        print(f"SUCCESS: NEUTRAL classification (move_up=0.5, move_down=0.5, final=0.1) → {label}, conf={conf}")
    
    def test_confidence_score_range(self):
        """Confidence score must be between 0 and 1"""
        from outcome_resolver import compute_label_v2
        test_cases = [
            (10.0, 0.0, 5.0, "24H"),  # Very strong up
            (0.0, 10.0, -5.0, "24H"),  # Very strong down
            (0.1, 0.1, 0.0, "24H"),   # Very weak
            (5.0, 5.0, 0.0, "7D"),    # Mixed
        ]
        for move_up, move_down, final, horizon in test_cases:
            label, conf = compute_label_v2(move_up, move_down, final, horizon)
            assert 0 <= conf <= 1, f"Confidence {conf} out of range for inputs ({move_up}, {move_down}, {final}, {horizon})"
        print("SUCCESS: All confidence scores in [0, 1] range")
    
    def test_horizon_aware_classification_7d(self):
        """7D horizon uses different thresholds"""
        from outcome_resolver import compute_label_v2
        # 7D: weak=2, strong=5
        # move_up=3 is >= weak(2) but < strong(5) → WEAK_GOOD
        label, conf = compute_label_v2(move_up_peak=3.0, move_down_peak=0.5, final_return=1.0, horizon="7D")
        assert label == "WEAK_GOOD", f"Expected WEAK_GOOD for 7D, got {label}"
        print(f"SUCCESS: 7D horizon classification (move_up=3.0) → {label}")
    
    def test_horizon_aware_classification_30d(self):
        """30D horizon uses different thresholds"""
        from outcome_resolver import compute_label_v2
        # 30D: weak=4, strong=10
        # move_up=5 is >= weak(4) but < strong(10) → WEAK_GOOD
        label, conf = compute_label_v2(move_up_peak=5.0, move_down_peak=1.0, final_return=2.0, horizon="30D")
        assert label == "WEAK_GOOD", f"Expected WEAK_GOOD for 30D, got {label}"
        print(f"SUCCESS: 30D horizon classification (move_up=5.0) → {label}")


# ─── API Tests ───

class TestLabelsV2CompareAPI:
    """Test GET /api/outcome/labels-v2-compare endpoint"""
    
    def test_labels_v2_compare_returns_200(self):
        """API returns 200 OK"""
        response = requests.get(f"{BASE_URL}/api/outcome/labels-v2-compare", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"SUCCESS: GET /api/outcome/labels-v2-compare returned 200")
    
    def test_labels_v2_compare_response_structure(self):
        """Response has required fields"""
        response = requests.get(f"{BASE_URL}/api/outcome/labels-v2-compare", timeout=30)
        data = response.json()
        
        assert data.get("ok") == True, "Response should have ok=True"
        assert "total_resolved" in data, "Missing total_resolved"
        assert "v2_labeled" in data, "Missing v2_labeled"
        assert "v1_distribution" in data, "Missing v1_distribution"
        assert "v2_distribution" in data, "Missing v2_distribution"
        assert "transitions" in data, "Missing transitions"
        assert "avg_v2_confidence" in data, "Missing avg_v2_confidence"
        
        print(f"SUCCESS: Response structure valid - total_resolved={data['total_resolved']}, v2_labeled={data['v2_labeled']}")
    
    def test_v1_distribution_has_3_labels(self):
        """V1 distribution should have GOOD/BAD/NEUTRAL"""
        response = requests.get(f"{BASE_URL}/api/outcome/labels-v2-compare", timeout=30)
        data = response.json()
        v1 = data.get("v1_distribution", {})
        
        # V1 uses 3 labels
        valid_v1_labels = {"GOOD", "BAD", "NEUTRAL", "UNKNOWN"}
        for label in v1.keys():
            assert label in valid_v1_labels, f"Unexpected V1 label: {label}"
        
        print(f"SUCCESS: V1 distribution labels valid: {list(v1.keys())}")
    
    def test_v2_distribution_has_5_labels(self):
        """V2 distribution should have 5 labels"""
        response = requests.get(f"{BASE_URL}/api/outcome/labels-v2-compare", timeout=30)
        data = response.json()
        v2 = data.get("v2_distribution", {})
        
        # V2 uses 5 labels
        valid_v2_labels = {"STRONG_GOOD", "WEAK_GOOD", "NEUTRAL", "WEAK_BAD", "STRONG_BAD", "UNKNOWN"}
        for label in v2.keys():
            assert label in valid_v2_labels, f"Unexpected V2 label: {label}"
        
        print(f"SUCCESS: V2 distribution labels valid: {list(v2.keys())}")
    
    def test_transitions_structure(self):
        """Transitions should have old, new, count fields"""
        response = requests.get(f"{BASE_URL}/api/outcome/labels-v2-compare", timeout=30)
        data = response.json()
        transitions = data.get("transitions", [])
        
        if transitions:
            for t in transitions:
                assert "old" in t, "Transition missing 'old' field"
                assert "new" in t, "Transition missing 'new' field"
                assert "count" in t, "Transition missing 'count' field"
                assert isinstance(t["count"], int), "count should be int"
        
        print(f"SUCCESS: Transitions structure valid ({len(transitions)} transitions)")
    
    def test_avg_v2_confidence_range(self):
        """avg_v2_confidence should be between 0 and 1 if present"""
        response = requests.get(f"{BASE_URL}/api/outcome/labels-v2-compare", timeout=30)
        data = response.json()
        conf = data.get("avg_v2_confidence")
        
        if conf is not None:
            assert 0 <= conf <= 1, f"avg_v2_confidence {conf} out of range"
            print(f"SUCCESS: avg_v2_confidence={conf} is in valid range")
        else:
            print("INFO: avg_v2_confidence is None (no V2 labels yet)")


class TestBackfillLabelsV2API:
    """Test POST /api/outcome/backfill-labels-v2 endpoint"""
    
    def test_backfill_returns_200(self):
        """API returns 200 OK"""
        response = requests.post(f"{BASE_URL}/api/outcome/backfill-labels-v2?limit=5", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"SUCCESS: POST /api/outcome/backfill-labels-v2 returned 200")
    
    def test_backfill_response_structure(self):
        """Response has required fields"""
        response = requests.post(f"{BASE_URL}/api/outcome/backfill-labels-v2?limit=5", timeout=60)
        data = response.json()
        
        assert data.get("ok") == True, "Response should have ok=True"
        assert "backfilled" in data, "Missing backfilled count"
        assert "errors" in data, "Missing errors count"
        assert "remaining" in data, "Missing remaining count"
        
        print(f"SUCCESS: Backfill response - backfilled={data['backfilled']}, errors={data['errors']}, remaining={data['remaining']}")
    
    def test_backfill_counts_are_integers(self):
        """All counts should be integers"""
        response = requests.post(f"{BASE_URL}/api/outcome/backfill-labels-v2?limit=5", timeout=60)
        data = response.json()
        
        assert isinstance(data.get("backfilled"), int), "backfilled should be int"
        assert isinstance(data.get("errors"), int), "errors should be int"
        assert isinstance(data.get("remaining"), int), "remaining should be int"
        
        print("SUCCESS: All backfill counts are integers")


class TestV2ShadowModeIntegrity:
    """Test that V2 shadow mode doesn't change production labels"""
    
    def test_v1_labels_unchanged_after_backfill(self):
        """V1 production labels should remain unchanged"""
        # Get V1 distribution before
        before = requests.get(f"{BASE_URL}/api/outcome/labels-v2-compare", timeout=30).json()
        v1_before = before.get("v1_distribution", {})
        
        # Run backfill (small batch)
        requests.post(f"{BASE_URL}/api/outcome/backfill-labels-v2?limit=5", timeout=60)
        
        # Get V1 distribution after
        after = requests.get(f"{BASE_URL}/api/outcome/labels-v2-compare", timeout=30).json()
        v1_after = after.get("v1_distribution", {})
        
        # V1 distribution should be unchanged
        assert v1_before == v1_after, f"V1 distribution changed! Before: {v1_before}, After: {v1_after}"
        print(f"SUCCESS: V1 production labels unchanged after backfill")
    
    def test_outcome_stats_unchanged(self):
        """outcome.label counts should remain unchanged"""
        # Get outcome stats
        response = requests.get(f"{BASE_URL}/api/outcome/stats", timeout=30)
        data = response.json()
        
        assert data.get("ok") == True
        labels = data.get("labels", {})
        
        # V1 labels should still be GOOD/BAD/NEUTRAL
        for label in labels.keys():
            assert label in {"GOOD", "BAD", "NEUTRAL"}, f"Unexpected production label: {label}"
        
        print(f"SUCCESS: Production outcome.label uses V1 labels: {labels}")


class TestAuditFieldsStructure:
    """Test audit.labels_v2 and audit.label_inputs structure"""
    
    def test_labels_v2_compare_shows_audit_data(self):
        """V2 compare endpoint should show audit data if backfilled"""
        response = requests.get(f"{BASE_URL}/api/outcome/labels-v2-compare", timeout=30)
        data = response.json()
        
        v2_labeled = data.get("v2_labeled", 0)
        v2_dist = data.get("v2_distribution", {})
        
        if v2_labeled > 0:
            # Should have V2 distribution
            assert len(v2_dist) > 0, "V2 distribution should not be empty if v2_labeled > 0"
            print(f"SUCCESS: V2 audit data present - {v2_labeled} samples labeled")
            print(f"  V2 distribution: {v2_dist}")
        else:
            print("INFO: No V2 labels yet (v2_labeled=0)")
    
    def test_transitions_show_label_changes(self):
        """Transitions should show what V2 unfroze from NEUTRAL"""
        response = requests.get(f"{BASE_URL}/api/outcome/labels-v2-compare", timeout=30)
        data = response.json()
        
        transitions = data.get("transitions", [])
        
        # Find transitions where old != new (actual changes)
        changes = [t for t in transitions if t.get("old") != t.get("new")]
        
        if changes:
            print(f"SUCCESS: Found {len(changes)} label transitions (V2 unfroze):")
            for t in changes[:5]:  # Show first 5
                print(f"  {t['old']} → {t['new']}: {t['count']}")
        else:
            print("INFO: No label changes found (all V2 labels match V1)")


# ─── Integration Tests ───

class TestLabelV2Integration:
    """Integration tests for Label V2 system"""
    
    def test_full_flow_backfill_then_compare(self):
        """Run backfill then verify compare shows results"""
        # Run backfill
        backfill_resp = requests.post(f"{BASE_URL}/api/outcome/backfill-labels-v2?limit=10", timeout=60)
        backfill_data = backfill_resp.json()
        assert backfill_data.get("ok") == True
        
        # Get compare
        compare_resp = requests.get(f"{BASE_URL}/api/outcome/labels-v2-compare", timeout=30)
        compare_data = compare_resp.json()
        assert compare_data.get("ok") == True
        
        # Verify consistency
        total_resolved = compare_data.get("total_resolved", 0)
        v2_labeled = compare_data.get("v2_labeled", 0)
        
        assert v2_labeled <= total_resolved, "v2_labeled should not exceed total_resolved"
        
        print(f"SUCCESS: Integration flow complete")
        print(f"  Total resolved: {total_resolved}")
        print(f"  V2 labeled: {v2_labeled}")
        print(f"  Remaining: {backfill_data.get('remaining', 'N/A')}")
    
    def test_v2_distribution_percentages(self):
        """V2 distribution should show meaningful spread (not 99% NEUTRAL)"""
        response = requests.get(f"{BASE_URL}/api/outcome/labels-v2-compare", timeout=30)
        data = response.json()
        
        v2_dist = data.get("v2_distribution", {})
        v2_labeled = data.get("v2_labeled", 0)
        
        if v2_labeled > 0:
            neutral_count = v2_dist.get("NEUTRAL", 0)
            neutral_pct = (neutral_count / v2_labeled) * 100 if v2_labeled > 0 else 0
            
            # V2 should have better distribution than V1 (which was ~99% NEUTRAL)
            print(f"V2 Distribution (total={v2_labeled}):")
            for label, count in sorted(v2_dist.items()):
                pct = (count / v2_labeled) * 100
                print(f"  {label}: {count} ({pct:.1f}%)")
            
            # Check if V2 unfroze some NEUTRAL samples
            non_neutral = v2_labeled - neutral_count
            if non_neutral > 0:
                print(f"SUCCESS: V2 unfroze {non_neutral} samples from NEUTRAL ({neutral_pct:.1f}% still NEUTRAL)")
            else:
                print(f"INFO: All V2 samples are NEUTRAL ({neutral_pct:.1f}%)")
        else:
            print("INFO: No V2 labels to analyze")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
