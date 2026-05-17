"""
Tests for Historical Shadow Validation (Backfill) System
==========================================================
Tests the backfill/replay framework for validating structure intelligence impact.
Point-in-time replay, dual pipeline execution, outcome evaluation, KPI aggregation, verdict engine.
"""

import pytest
import requests
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Use the public API URL
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://expo-telegram-web.preview.emergentagent.com")


# ═══════════════════════════════════════════════════════
# API ENDPOINT TESTS
# ═══════════════════════════════════════════════════════

class TestBackfillLatestEndpoint:
    """Test GET /api/forecast/backfill/latest"""
    
    def test_latest_endpoint_returns_ok(self):
        """Verify latest backfill endpoint returns success response"""
        response = requests.get(f"{BASE_URL}/api/forecast/backfill/latest?asset=BTC&horizon=7D")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        
    def test_latest_has_run_metadata(self):
        """Verify latest endpoint includes run metadata"""
        response = requests.get(f"{BASE_URL}/api/forecast/backfill/latest?asset=BTC&horizon=7D")
        data = response.json()
        assert "run" in data
        run = data["run"]
        assert "runId" in run
        assert "asset" in run
        assert "horizon" in run
        assert "status" in run
        assert run["status"] == "completed"
        
    def test_latest_has_kpis(self):
        """Verify latest endpoint includes KPI metrics"""
        response = requests.get(f"{BASE_URL}/api/forecast/backfill/latest?asset=BTC&horizon=7D")
        data = response.json()
        assert "kpis" in data
        kpis = data["kpis"]
        assert "n" in kpis
        assert kpis["n"] >= 90  # Should have 90+ cases
        assert "base" in kpis
        assert "structure" in kpis
        assert "comparison" in kpis
        
    def test_latest_has_verdict(self):
        """Verify latest endpoint includes automatic verdict"""
        response = requests.get(f"{BASE_URL}/api/forecast/backfill/latest?asset=BTC&horizon=7D")
        data = response.json()
        assert "verdict" in data
        verdict = data["verdict"]
        assert "verdict" in verdict  # PROMOTE/HOLD/ROLLBACK
        assert "confidence" in verdict
        assert "reasons" in verdict
        assert "recommendation" in verdict


class TestBackfillResultsEndpoint:
    """Test GET /api/forecast/backfill/results/{run_id}"""
    
    @pytest.fixture
    def run_id(self):
        """Get the latest run_id for testing"""
        response = requests.get(f"{BASE_URL}/api/forecast/backfill/latest?asset=BTC&horizon=7D")
        return response.json()["run"]["runId"]
    
    def test_results_endpoint_returns_ok(self, run_id):
        """Verify results endpoint returns success response"""
        response = requests.get(f"{BASE_URL}/api/forecast/backfill/results/{run_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        
    def test_results_has_all_sections(self, run_id):
        """Verify results includes run, kpis, verdict, cases_count"""
        response = requests.get(f"{BASE_URL}/api/forecast/backfill/results/{run_id}")
        data = response.json()
        assert "run" in data
        assert "kpis" in data
        assert "verdict" in data
        assert "cases_count" in data
        assert data["cases_count"] >= 90
        
    def test_invalid_run_id_returns_error(self):
        """Verify invalid run_id returns appropriate error"""
        response = requests.get(f"{BASE_URL}/api/forecast/backfill/results/invalid_run_id_123")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is False
        assert "error" in data


class TestBackfillCasesEndpoint:
    """Test GET /api/forecast/backfill/cases/{run_id}"""
    
    @pytest.fixture
    def run_id(self):
        """Get the latest run_id for testing"""
        response = requests.get(f"{BASE_URL}/api/forecast/backfill/latest?asset=BTC&horizon=7D")
        return response.json()["run"]["runId"]
    
    def test_cases_endpoint_returns_ok(self, run_id):
        """Verify cases endpoint returns success response"""
        response = requests.get(f"{BASE_URL}/api/forecast/backfill/cases/{run_id}?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "count" in data
        assert "cases" in data
        
    def test_cases_structure_is_valid(self, run_id):
        """Verify individual case structure"""
        response = requests.get(f"{BASE_URL}/api/forecast/backfill/cases/{run_id}?limit=1")
        data = response.json()
        assert data["count"] >= 1
        case = data["cases"][0]
        
        # Core fields
        assert "asset" in case
        assert "horizon" in case
        assert "as_of" in case
        assert "outcome_date" in case
        assert "entry_price" in case
        
        # Replay results
        assert "replay" in case
        replay = case["replay"]
        assert "base" in replay
        assert "structure" in replay
        assert "structure_features" in replay
        assert "structure_delta" in replay
        
        # Outcome
        assert "outcome" in case
        outcome = case["outcome"]
        assert "actual_price" in outcome
        assert "real_move_pct" in outcome
        assert "real_direction" in outcome
        
        # Comparison
        assert "comparison" in case
        comparison = case["comparison"]
        assert "case_type" in comparison
        assert "base_correct" in comparison
        assert "structure_correct" in comparison
        
        # Pattern tags
        assert "pattern_tags" in case
        
    def test_cases_case_type_filter(self, run_id):
        """Verify case_type filter works correctly"""
        response = requests.get(f"{BASE_URL}/api/forecast/backfill/cases/{run_id}?case_type=structure_hurt&limit=10")
        data = response.json()
        assert data["ok"] is True
        
        # All returned cases should be structure_hurt
        for case in data["cases"]:
            assert case["comparison"]["case_type"] == "structure_hurt"
            
    def test_cases_pattern_filter(self, run_id):
        """Verify pattern filter works correctly"""
        response = requests.get(f"{BASE_URL}/api/forecast/backfill/cases/{run_id}?pattern=pullback_misread&limit=10")
        data = response.json()
        assert data["ok"] is True
        
        # All returned cases should have pullback_misread tag
        for case in data["cases"]:
            assert "pullback_misread" in case["pattern_tags"]
            
    def test_cases_limit_parameter(self, run_id):
        """Verify limit parameter works correctly"""
        response = requests.get(f"{BASE_URL}/api/forecast/backfill/cases/{run_id}?limit=3")
        data = response.json()
        assert data["count"] == 3
        assert len(data["cases"]) == 3


# ═══════════════════════════════════════════════════════
# KPI AGGREGATION TESTS
# ═══════════════════════════════════════════════════════

class TestKPIMetrics:
    """Test KPI computation and structure"""
    
    @pytest.fixture
    def kpis(self):
        """Get KPIs from latest backfill"""
        response = requests.get(f"{BASE_URL}/api/forecast/backfill/latest?asset=BTC&horizon=7D")
        return response.json()["kpis"]
    
    def test_accuracy_lift_computed(self, kpis):
        """Verify accuracy_lift_pp is computed"""
        comparison = kpis["comparison"]
        assert "accuracy_lift_pp" in comparison
        # Value should be between -100 and +100 (percentage points)
        assert -100 <= comparison["accuracy_lift_pp"] <= 100
        
    def test_hurt_rate_computed(self, kpis):
        """Verify hurt_rate is computed"""
        comparison = kpis["comparison"]
        assert "hurt_rate" in comparison
        assert 0 <= comparison["hurt_rate"] <= 1
        
    def test_case_types_distribution(self, kpis):
        """Verify case types are distributed"""
        case_types = kpis["comparison"]["case_types"]
        assert "both_correct" in case_types or "both_wrong" in case_types
        
    def test_delta_stats_computed(self, kpis):
        """Verify delta statistics are computed"""
        delta_stats = kpis["delta_stats"]
        assert "avg_delta" in delta_stats
        assert "avg_abs_delta" in delta_stats
        assert "max_abs_delta" in delta_stats
        assert "p90_abs_delta" in delta_stats
        
    def test_direction_distribution(self, kpis):
        """Verify direction distribution is computed for both pipelines"""
        for pipeline in ["base", "structure"]:
            dist = kpis[pipeline]["distribution"]
            assert "neutral_ratio" in dist
            assert "mild_ratio" in dist
            assert "strong_ratio" in dist
            assert "counts" in dist


# ═══════════════════════════════════════════════════════
# VERDICT ENGINE TESTS
# ═══════════════════════════════════════════════════════

class TestVerdictEngine:
    """Test automatic verdict generation"""
    
    @pytest.fixture
    def verdict(self):
        """Get verdict from latest backfill"""
        response = requests.get(f"{BASE_URL}/api/forecast/backfill/latest?asset=BTC&horizon=7D")
        return response.json()["verdict"]
    
    def test_verdict_is_valid(self, verdict):
        """Verify verdict is one of valid options"""
        valid_verdicts = ["PROMOTE", "HOLD", "ROLLBACK", "INSUFFICIENT_DATA"]
        assert verdict["verdict"] in valid_verdicts
        
    def test_verdict_has_confidence(self, verdict):
        """Verify verdict includes confidence level"""
        assert verdict["confidence"] in ["low", "medium", "high"]
        
    def test_verdict_has_reasons(self, verdict):
        """Verify verdict includes reasoning"""
        assert isinstance(verdict["reasons"], list)
        assert len(verdict["reasons"]) > 0
        
    def test_verdict_has_recommendation(self, verdict):
        """Verify verdict includes actionable recommendation"""
        assert "recommendation" in verdict
        assert len(verdict["recommendation"]) > 0


# ═══════════════════════════════════════════════════════
# PATTERN TAGGING TESTS
# ═══════════════════════════════════════════════════════

class TestPatternTagging:
    """Test pattern classification"""
    
    @pytest.fixture
    def kpis(self):
        """Get KPIs from latest backfill"""
        response = requests.get(f"{BASE_URL}/api/forecast/backfill/latest?asset=BTC&horizon=7D")
        return response.json()["kpis"]
    
    def test_pattern_distribution_exists(self, kpis):
        """Verify pattern distribution is computed"""
        assert "pattern_distribution" in kpis
        
    def test_known_patterns_tagged(self, kpis):
        """Verify known patterns are being tagged"""
        patterns = kpis["pattern_distribution"]
        # At least some patterns should be present
        assert len(patterns) > 0
        
    def test_pattern_counts_are_positive(self, kpis):
        """Verify pattern counts are positive integers"""
        patterns = kpis["pattern_distribution"]
        for pattern, count in patterns.items():
            assert isinstance(count, int)
            assert count >= 0


# ═══════════════════════════════════════════════════════
# POINT-IN-TIME INTEGRITY TESTS
# ═══════════════════════════════════════════════════════

class TestPointInTimeIntegrity:
    """Test that snapshots respect point-in-time constraints"""
    
    @pytest.fixture
    def cases(self):
        """Get cases from latest backfill"""
        response = requests.get(f"{BASE_URL}/api/forecast/backfill/latest?asset=BTC&horizon=7D")
        run_id = response.json()["run"]["runId"]
        cases_response = requests.get(f"{BASE_URL}/api/forecast/backfill/cases/{run_id}?limit=10")
        return cases_response.json()["cases"]
    
    def test_as_of_before_outcome_date(self, cases):
        """Verify as_of date is always before outcome date"""
        for case in cases:
            as_of = case["as_of"]
            outcome_date = case["outcome_date"]
            assert as_of < outcome_date, f"as_of {as_of} should be before outcome_date {outcome_date}"
            
    def test_entry_price_positive(self, cases):
        """Verify entry prices are positive"""
        for case in cases:
            assert case["entry_price"] > 0
            
    def test_structure_features_present(self, cases):
        """Verify structure features are computed for each case"""
        for case in cases:
            sf = case["replay"]["structure_features"]
            required_features = [
                "structure_bias_score",
                "structure_trend_score",
                "structure_momentum_score",
                "structure_reversal_risk",
                "structure_stability_score",
                "structure_exhaustion_score",
                "structure_compression_score",
            ]
            for feature in required_features:
                assert feature in sf, f"Missing feature: {feature}"


# ═══════════════════════════════════════════════════════
# UNIT TESTS: backfill modules
# ═══════════════════════════════════════════════════════

class TestReplayUniverseBuilder:
    """Test replay universe construction"""
    
    def test_import_module(self):
        """Verify module imports correctly"""
        from forecast.backfill.replay_universe_builder import build_replay_jobs
        assert callable(build_replay_jobs)
        
    def test_build_jobs_with_prices(self):
        """Test job building with sample prices"""
        from forecast.backfill.replay_universe_builder import build_replay_jobs
        
        # Create sample prices
        prices = {f"2026-01-{i:02d}": 80000 + i * 100 for i in range(1, 32)}
        prices.update({f"2026-02-{i:02d}": 83000 + i * 50 for i in range(1, 29)})
        
        jobs = build_replay_jobs("BTC", "7D", "2026-01-15", "2026-02-10", prices)
        
        assert isinstance(jobs, list)
        assert len(jobs) > 0
        
        # Check job structure
        job = jobs[0]
        assert job["asset"] == "BTC"
        assert job["horizon"] == "7D"
        assert "as_of" in job
        assert "outcome_date" in job


class TestHistoricalSnapshotBuilder:
    """Test point-in-time snapshot construction"""
    
    def test_import_module(self):
        """Verify module imports correctly"""
        from forecast.backfill.historical_snapshot_builder import build_snapshot
        assert callable(build_snapshot)


class TestReplayRunner:
    """Test dual pipeline execution"""
    
    def test_import_module(self):
        """Verify module imports correctly"""
        from forecast.backfill.replay_runner import run_dual_replay
        assert callable(run_dual_replay)


class TestHistoricalOutcomeEvaluator:
    """Test outcome evaluation"""
    
    def test_import_module(self):
        """Verify module imports correctly"""
        from forecast.backfill.historical_outcome_evaluator import evaluate_outcome
        assert callable(evaluate_outcome)
        
    def test_evaluate_bull_outcome(self):
        """Test bull outcome classification"""
        from forecast.backfill.historical_outcome_evaluator import evaluate_outcome
        
        prices = {"2026-01-15": 85000}
        result = evaluate_outcome(prices, entry_price=80000, outcome_date="2026-01-15")
        
        assert result is not None
        assert result["real_direction"] == "BULL"
        assert result["real_move_pct"] > 0


class TestShadowCaseComparator:
    """Test A/B comparison logic"""
    
    def test_import_module(self):
        """Verify module imports correctly"""
        from forecast.backfill.shadow_case_comparator import compare_case
        assert callable(compare_case)
        
    def test_structure_improved_classification(self):
        """Test structure_improved case detection"""
        from forecast.backfill.shadow_case_comparator import compare_case
        
        base = {"direction": "MILD_BEAR", "score": -0.3}
        structure = {"direction": "MILD_BULL", "score": 0.3}
        outcome = {"real_direction": "BULL", "real_move_pct": 5.0}
        
        result = compare_case(base, structure, outcome)
        assert result["case_type"] == "structure_improved"
        
    def test_structure_hurt_classification(self):
        """Test structure_hurt case detection"""
        from forecast.backfill.shadow_case_comparator import compare_case
        
        base = {"direction": "MILD_BULL", "score": 0.3}
        structure = {"direction": "NEUTRAL", "score": 0.1}
        outcome = {"real_direction": "BULL", "real_move_pct": 5.0}
        
        result = compare_case(base, structure, outcome)
        assert result["case_type"] == "structure_hurt"


class TestPatternTagger:
    """Test pattern classification"""
    
    def test_import_module(self):
        """Verify module imports correctly"""
        from forecast.backfill.pattern_tagger import tag_patterns
        assert callable(tag_patterns)


class TestShadowKPIAggregator:
    """Test KPI aggregation"""
    
    def test_import_module(self):
        """Verify module imports correctly"""
        from forecast.backfill.shadow_kpi_aggregator import aggregate_kpis
        assert callable(aggregate_kpis)
        
    def test_empty_cases_returns_n_zero(self):
        """Test empty input handling"""
        from forecast.backfill.shadow_kpi_aggregator import aggregate_kpis
        
        result = aggregate_kpis([])
        assert result["n"] == 0


class TestShadowVerdictEngine:
    """Test automatic verdict generation"""
    
    def test_import_module(self):
        """Verify module imports correctly"""
        from forecast.backfill.shadow_verdict_engine import build_verdict
        assert callable(build_verdict)
        
    def test_insufficient_data_verdict(self):
        """Test insufficient data verdict"""
        from forecast.backfill.shadow_verdict_engine import build_verdict
        
        kpis = {"n": 5}
        result = build_verdict(kpis)
        assert result["verdict"] == "INSUFFICIENT_DATA"
