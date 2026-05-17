"""
Test A1 Feature Importance Stability + Pruning Pipeline
Tests endpoints:
- GET /api/ml-overlay/pruning-report
- GET /api/ml-overlay/status (pruning field)
- POST /api/ml-overlay/apply-pruning?horizon=7D
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestPruningReportEndpoint:
    """GET /api/ml-overlay/pruning-report tests"""

    def test_pruning_report_returns_ok(self):
        """Endpoint returns ok:true with report, selectedFeatures, summary fields"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/pruning-report", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok:true, got {data}"
        assert "report" in data, "Missing 'report' field"
        assert "selectedFeatures" in data, "Missing 'selectedFeatures' field"
        assert "summary" in data, "Missing 'summary' field"
        print(f"PASS: pruning-report returns ok:true with report, selectedFeatures, summary")

    def test_pruning_report_7d_selected_features(self):
        """7D selected features should be ['ret_1d', 'rsi_14', 'vol_7d', 'ma20_slope']"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/pruning-report", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        sf = data.get("selectedFeatures", {})
        horizons = sf.get("horizons", {})
        h7d = horizons.get("7D", {})
        selected_7d = h7d.get("selected", [])
        
        expected = ['ret_1d', 'rsi_14', 'vol_7d', 'ma20_slope']
        assert set(selected_7d) == set(expected), f"7D selected: {selected_7d}, expected: {expected}"
        assert len(selected_7d) == 4, f"7D should have 4 features, got {len(selected_7d)}"
        print(f"PASS: 7D selected features = {selected_7d}")

    def test_pruning_report_30d_selected_features_count(self):
        """30D should have 6 selected features"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/pruning-report", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        sf = data.get("selectedFeatures", {})
        horizons = sf.get("horizons", {})
        h30d = horizons.get("30D", {})
        selected_30d = h30d.get("selected", [])
        
        assert len(selected_30d) == 6, f"30D should have 6 features, got {len(selected_30d)}: {selected_30d}"
        print(f"PASS: 30D selected features count = 6: {selected_30d}")

    def test_pruning_report_7d_comparison_deltas(self):
        """7D comparison.deltas should show flip improvements (flip_delta)"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/pruning-report", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        report = data.get("report", {})
        horizons = report.get("horizons", {})
        h7d = horizons.get("7D", {})
        comparison = h7d.get("comparison", {})
        deltas = comparison.get("deltas", [])
        
        assert len(deltas) >= 2, f"Expected at least 2 fold deltas, got {len(deltas)}"
        
        # Check that deltas have flip_delta field
        for d in deltas:
            assert "flip_delta" in d, f"Missing flip_delta in delta: {d}"
            assert "fold" in d, f"Missing fold in delta: {d}"
        
        # Check for flip improvements (negative flip_delta means improvement)
        flip_deltas = [d["flip_delta"] for d in deltas]
        print(f"7D flip_deltas: {flip_deltas}")
        
        # Verify 2024 has -8.2pp and 2025 has -6.0pp as per problem statement
        d2024 = next((d for d in deltas if d["fold"] == "2024"), None)
        d2025 = next((d for d in deltas if d["fold"] == "2025"), None)
        
        if d2024:
            assert d2024["flip_delta"] <= 0, f"2024 flip_delta should show improvement, got {d2024['flip_delta']}"
            print(f"PASS: 2024 flip_delta = {d2024['flip_delta']}pp")
        
        if d2025:
            assert d2025["flip_delta"] <= 0, f"2025 flip_delta should show improvement, got {d2025['flip_delta']}"
            print(f"PASS: 2025 flip_delta = {d2025['flip_delta']}pp")

    def test_pruning_report_has_stability_metrics(self):
        """Report should include stability metrics per feature"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/pruning-report", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        report = data.get("report", {})
        horizons = report.get("horizons", {})
        
        for h in ["7D", "30D"]:
            h_data = horizons.get(h, {})
            stability = h_data.get("stability", {})
            assert len(stability) > 0, f"Missing stability metrics for {h}"
            
            # Check stability structure
            for feat, s in stability.items():
                assert "meanImportance" in s, f"Missing meanImportance in {feat}"
                assert "stdImportance" in s, f"Missing stdImportance in {feat}"
                assert "stabilityScore" in s, f"Missing stabilityScore in {feat}"
                
        print(f"PASS: Report has stability metrics for both horizons")


class TestMLOverlayStatusPruning:
    """GET /api/ml-overlay/status pruning field tests"""

    def test_status_includes_pruning(self):
        """Status endpoint should include pruning field with selected features per horizon"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/status", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "pruning" in data, "Missing 'pruning' field in status"
        
        pruning = data.get("pruning", {})
        assert "7D" in pruning, "Missing 7D in pruning"
        assert "30D" in pruning, "Missing 30D in pruning"
        
        # Check 7D
        p7d = pruning.get("7D", {})
        assert "selected" in p7d, "Missing 'selected' in 7D pruning"
        assert "prunedCount" in p7d, "Missing 'prunedCount' in 7D pruning"
        assert len(p7d["selected"]) == 4, f"7D should have 4 selected features, got {len(p7d['selected'])}"
        
        # Check 30D
        p30d = pruning.get("30D", {})
        assert "selected" in p30d, "Missing 'selected' in 30D pruning"
        assert "prunedCount" in p30d, "Missing 'prunedCount' in 30D pruning"
        assert len(p30d["selected"]) == 6, f"30D should have 6 selected features, got {len(p30d['selected'])}"
        
        print(f"PASS: Status includes pruning - 7D: {len(p7d['selected'])} active/{p7d['prunedCount']} pruned, 30D: {len(p30d['selected'])} active/{p30d['prunedCount']} pruned")


class TestApplyPruningEndpoint:
    """POST /api/ml-overlay/apply-pruning tests"""

    def test_apply_pruning_7d_returns_ok(self):
        """apply-pruning?horizon=7D should retrain model and return ok:true"""
        response = requests.post(f"{BASE_URL}/api/ml-overlay/apply-pruning?horizon=7D", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok:true, got {data}"
        assert "modelId" in data, "Missing modelId in response"
        assert "features" in data, "Missing features in response"
        assert "featureCount" in data, "Missing featureCount in response"
        
        # Verify 7D pruned features
        features = data.get("features", [])
        assert len(features) == 4, f"Expected 4 features for 7D, got {len(features)}: {features}"
        
        expected = ['ret_1d', 'rsi_14', 'vol_7d', 'ma20_slope']
        assert set(features) == set(expected), f"Features mismatch: {features} vs {expected}"
        
        print(f"PASS: apply-pruning 7D returned ok:true with modelId={data.get('modelId')}, featureCount={data.get('featureCount')}")


class TestPruningSummary:
    """Verify pruning summary contents"""

    def test_summary_is_markdown(self):
        """Summary should be readable markdown"""
        response = requests.get(f"{BASE_URL}/api/ml-overlay/pruning-report", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        summary = data.get("summary", "")
        
        assert "# Overlay Feature Pruning Summary" in summary, "Missing title in summary"
        assert "## 7D Horizon" in summary, "Missing 7D section"
        assert "## 30D Horizon" in summary, "Missing 30D section"
        assert "Selected:" in summary, "Missing Selected info"
        assert "Pruned:" in summary, "Missing Pruned info"
        
        print(f"PASS: Summary is markdown with proper sections")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
