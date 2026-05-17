"""
Prediction Lab API Tests — Mega Sprint 1: Truth Engine.

Tests all Prediction Lab endpoints:
- GET /api/prediction-lab/overview
- GET /api/prediction-lab/calibration
- GET /api/prediction-lab/families
- GET /api/prediction-lab/forecasts
- GET /api/prediction-lab/results
- GET /api/prediction-lab/scheduler-status
- POST /api/prediction-lab/resolve
- POST /api/prediction-lab/recalculate
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestPredictionLabOverview:
    """Tests for GET /api/prediction-lab/overview endpoint."""

    def test_overview_returns_200(self):
        """Overview endpoint returns 200 OK."""
        response = requests.get(f"{BASE_URL}/api/prediction-lab/overview")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: Overview returns 200")

    def test_overview_has_forecast_counts(self):
        """Overview has total_forecasts, resolved_forecasts, pending_forecasts, stale_forecasts."""
        response = requests.get(f"{BASE_URL}/api/prediction-lab/overview")
        data = response.json()
        
        assert "total_forecasts" in data, "Missing total_forecasts"
        assert "resolved_forecasts" in data, "Missing resolved_forecasts"
        assert "pending_forecasts" in data, "Missing pending_forecasts"
        assert "stale_forecasts" in data, "Missing stale_forecasts"
        
        assert isinstance(data["total_forecasts"], int), "total_forecasts should be int"
        assert isinstance(data["pending_forecasts"], int), "pending_forecasts should be int"
        print(f"PASS: Forecast counts present - total={data['total_forecasts']}, pending={data['pending_forecasts']}")

    def test_overview_has_accuracy_metrics(self):
        """Overview has accuracy, avg_brier, validated_results fields."""
        response = requests.get(f"{BASE_URL}/api/prediction-lab/overview")
        data = response.json()
        
        assert "accuracy" in data, "Missing accuracy"
        assert "avg_brier" in data, "Missing avg_brier"
        assert "validated_results" in data, "Missing validated_results"
        
        # These can be null if no resolved forecasts
        print(f"PASS: Accuracy metrics present - accuracy={data['accuracy']}, avg_brier={data['avg_brier']}")

    def test_overview_has_opportunity_metrics(self):
        """Overview has opportunity_rate and avg_entry_quality fields."""
        response = requests.get(f"{BASE_URL}/api/prediction-lab/overview")
        data = response.json()
        
        assert "opportunity_rate" in data, "Missing opportunity_rate"
        assert "avg_entry_quality" in data, "Missing avg_entry_quality"
        print(f"PASS: Opportunity metrics present - rate={data['opportunity_rate']}, entry_quality={data['avg_entry_quality']}")

    def test_overview_has_calibration_verdict(self):
        """Overview has calibration_verdict field."""
        response = requests.get(f"{BASE_URL}/api/prediction-lab/overview")
        data = response.json()
        
        assert "calibration_verdict" in data, "Missing calibration_verdict"
        assert isinstance(data["calibration_verdict"], str), "calibration_verdict should be string"
        print(f"PASS: Calibration verdict present - {data['calibration_verdict']}")

    def test_overview_has_families(self):
        """Overview has best_families and worst_families arrays."""
        response = requests.get(f"{BASE_URL}/api/prediction-lab/overview")
        data = response.json()
        
        assert "best_families" in data, "Missing best_families"
        assert "worst_families" in data, "Missing worst_families"
        assert isinstance(data["best_families"], list), "best_families should be list"
        assert isinstance(data["worst_families"], list), "worst_families should be list"
        print(f"PASS: Families present - best={len(data['best_families'])}, worst={len(data['worst_families'])}")

    def test_overview_has_dimensions(self):
        """Overview has dimensions dict."""
        response = requests.get(f"{BASE_URL}/api/prediction-lab/overview")
        data = response.json()
        
        assert "dimensions" in data, "Missing dimensions"
        assert isinstance(data["dimensions"], dict), "dimensions should be dict"
        print(f"PASS: Dimensions present - keys={list(data['dimensions'].keys())}")

    def test_overview_has_calibration_buckets(self):
        """Overview has calibration array."""
        response = requests.get(f"{BASE_URL}/api/prediction-lab/overview")
        data = response.json()
        
        assert "calibration" in data, "Missing calibration"
        assert isinstance(data["calibration"], list), "calibration should be list"
        print(f"PASS: Calibration buckets present - count={len(data['calibration'])}")

    def test_overview_has_recent_results(self):
        """Overview has recent_mistakes and recent_correct arrays."""
        response = requests.get(f"{BASE_URL}/api/prediction-lab/overview")
        data = response.json()
        
        assert "recent_mistakes" in data, "Missing recent_mistakes"
        assert "recent_correct" in data, "Missing recent_correct"
        assert isinstance(data["recent_mistakes"], list), "recent_mistakes should be list"
        assert isinstance(data["recent_correct"], list), "recent_correct should be list"
        print(f"PASS: Recent results present - mistakes={len(data['recent_mistakes'])}, correct={len(data['recent_correct'])}")


class TestPredictionLabCalibration:
    """Tests for GET /api/prediction-lab/calibration endpoint."""

    def test_calibration_returns_200(self):
        """Calibration endpoint returns 200 OK."""
        response = requests.get(f"{BASE_URL}/api/prediction-lab/calibration")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: Calibration returns 200")

    def test_calibration_has_global_and_by_family(self):
        """Calibration has global and by_family structure."""
        response = requests.get(f"{BASE_URL}/api/prediction-lab/calibration")
        data = response.json()
        
        # Either has global/by_family or has message (not calculated yet)
        if "message" in data:
            print(f"PASS: Calibration not calculated yet - {data['message']}")
        else:
            assert "global" in data, "Missing global"
            assert isinstance(data["global"], list), "global should be list"
            print(f"PASS: Calibration structure present - global buckets={len(data.get('global', []))}")


class TestPredictionLabFamilies:
    """Tests for GET /api/prediction-lab/families endpoint."""

    def test_families_returns_200(self):
        """Families endpoint returns 200 OK."""
        response = requests.get(f"{BASE_URL}/api/prediction-lab/families")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: Families returns 200")

    def test_families_has_families_and_dimensions(self):
        """Families has families array and dimensions dict."""
        response = requests.get(f"{BASE_URL}/api/prediction-lab/families")
        data = response.json()
        
        assert "families" in data, "Missing families"
        assert "dimensions" in data, "Missing dimensions"
        assert isinstance(data["families"], list), "families should be list"
        assert isinstance(data["dimensions"], dict), "dimensions should be dict"
        print(f"PASS: Families structure present - families={len(data['families'])}, dimensions={list(data['dimensions'].keys())}")


class TestPredictionLabForecasts:
    """Tests for GET /api/prediction-lab/forecasts endpoint."""

    def test_forecasts_returns_200(self):
        """Forecasts endpoint returns 200 OK."""
        response = requests.get(f"{BASE_URL}/api/prediction-lab/forecasts")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: Forecasts returns 200")

    def test_forecasts_has_total_and_records(self):
        """Forecasts has total and records array."""
        response = requests.get(f"{BASE_URL}/api/prediction-lab/forecasts")
        data = response.json()
        
        assert "total" in data, "Missing total"
        assert "records" in data, "Missing records"
        assert isinstance(data["total"], int), "total should be int"
        assert isinstance(data["records"], list), "records should be list"
        print(f"PASS: Forecasts structure present - total={data['total']}, records_returned={len(data['records'])}")

    def test_forecasts_pagination(self):
        """Forecasts supports limit and offset pagination."""
        response = requests.get(f"{BASE_URL}/api/prediction-lab/forecasts?limit=5&offset=0")
        data = response.json()
        
        assert len(data["records"]) <= 5, "Limit not respected"
        print(f"PASS: Forecasts pagination works - limit=5, returned={len(data['records'])}")

    def test_forecasts_record_structure(self):
        """Forecast records have expected fields (outcomes, price_snapshots)."""
        response = requests.get(f"{BASE_URL}/api/prediction-lab/forecasts?limit=1")
        data = response.json()
        
        if data["records"]:
            record = data["records"][0]
            # Check key fields
            expected_fields = ["forecast_id", "event_id", "action", "created_at"]
            for field in expected_fields:
                assert field in record, f"Missing field: {field}"
            
            # Check for outcomes array (full outcome set logging)
            if "outcomes" in record:
                assert isinstance(record["outcomes"], list), "outcomes should be list"
                print(f"PASS: Forecast record has outcomes array - count={len(record['outcomes'])}")
            else:
                print("INFO: Forecast record does not have outcomes array (may be binary market)")
            
            # Check for price_snapshots (price trajectory tracking)
            if "price_snapshots" in record:
                assert isinstance(record["price_snapshots"], list), "price_snapshots should be list"
                print(f"PASS: Forecast record has price_snapshots - count={len(record['price_snapshots'])}")
            else:
                print("INFO: Forecast record does not have price_snapshots yet")
        else:
            print("INFO: No forecast records to check structure")


class TestPredictionLabResults:
    """Tests for GET /api/prediction-lab/results endpoint."""

    def test_results_returns_200(self):
        """Results endpoint returns 200 OK."""
        response = requests.get(f"{BASE_URL}/api/prediction-lab/results")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: Results returns 200")

    def test_results_has_total_and_results(self):
        """Results has total and results array."""
        response = requests.get(f"{BASE_URL}/api/prediction-lab/results")
        data = response.json()
        
        assert "total" in data, "Missing total"
        assert "results" in data, "Missing results"
        assert isinstance(data["total"], int), "total should be int"
        assert isinstance(data["results"], list), "results should be list"
        print(f"PASS: Results structure present - total={data['total']}, results_returned={len(data['results'])}")

    def test_results_correctness_filter(self):
        """Results supports correctness filter."""
        response = requests.get(f"{BASE_URL}/api/prediction-lab/results?correctness=CORRECT")
        assert response.status_code == 200
        print("PASS: Results correctness filter works")

    def test_results_record_structure(self):
        """Result records have expected fields (brier_score, opportunity_captured, entry_quality, price_path)."""
        response = requests.get(f"{BASE_URL}/api/prediction-lab/results?limit=1")
        data = response.json()
        
        if data["results"]:
            result = data["results"][0]
            # Check key fields
            expected_fields = ["forecast_id", "correctness", "brier_score"]
            for field in expected_fields:
                assert field in result, f"Missing field: {field}"
            
            # Check for opportunity_captured
            if "opportunity_captured" in result:
                print(f"PASS: Result has opportunity_captured - {result['opportunity_captured']}")
            
            # Check for entry_quality
            if "entry_quality" in result:
                print(f"PASS: Result has entry_quality - {result['entry_quality']}")
            
            # Check for price_path
            if "price_path" in result:
                assert isinstance(result["price_path"], dict), "price_path should be dict"
                print(f"PASS: Result has price_path - keys={list(result['price_path'].keys())}")
        else:
            print("INFO: No results to check structure (markets haven't resolved yet)")


class TestPredictionLabScheduler:
    """Tests for GET /api/prediction-lab/scheduler-status endpoint."""

    def test_scheduler_status_returns_200(self):
        """Scheduler status endpoint returns 200 OK."""
        response = requests.get(f"{BASE_URL}/api/prediction-lab/scheduler-status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: Scheduler status returns 200")

    def test_scheduler_status_has_jobs(self):
        """Scheduler status has jobs array with intervals."""
        response = requests.get(f"{BASE_URL}/api/prediction-lab/scheduler-status")
        data = response.json()
        
        assert "ok" in data, "Missing ok"
        assert "jobs" in data, "Missing jobs"
        assert isinstance(data["jobs"], list), "jobs should be list"
        
        # Check job structure
        for job in data["jobs"]:
            assert "name" in job, "Job missing name"
            assert "interval" in job, "Job missing interval"
        
        job_names = [j["name"] for j in data["jobs"]]
        print(f"PASS: Scheduler jobs present - {job_names}")

    def test_scheduler_status_has_forecast_counts(self):
        """Scheduler status has forecast counts."""
        response = requests.get(f"{BASE_URL}/api/prediction-lab/scheduler-status")
        data = response.json()
        
        assert "total_forecasts" in data, "Missing total_forecasts"
        assert "pending_forecasts" in data, "Missing pending_forecasts"
        assert "stale_forecasts" in data, "Missing stale_forecasts"
        print(f"PASS: Scheduler forecast counts - total={data['total_forecasts']}, pending={data['pending_forecasts']}, stale={data['stale_forecasts']}")


class TestPredictionLabActions:
    """Tests for POST /api/prediction-lab/resolve and /recalculate endpoints."""

    def test_resolve_returns_ok(self):
        """POST /resolve returns ok=true."""
        response = requests.post(f"{BASE_URL}/api/prediction-lab/resolve")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert "ok" in data, "Missing ok"
        assert data["ok"] is True, "ok should be True"
        print(f"PASS: Resolve returns ok - stats={data}")

    def test_recalculate_returns_ok(self):
        """POST /recalculate returns ok=true."""
        response = requests.post(f"{BASE_URL}/api/prediction-lab/recalculate")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert "ok" in data, "Missing ok"
        assert data["ok"] is True, "ok should be True"
        print(f"PASS: Recalculate returns ok - stats={data}")


class TestPredictionLabDataIntegrity:
    """Tests for data integrity and consistency."""

    def test_overview_counts_match_forecasts(self):
        """Overview total_forecasts matches forecasts endpoint total."""
        overview_resp = requests.get(f"{BASE_URL}/api/prediction-lab/overview")
        forecasts_resp = requests.get(f"{BASE_URL}/api/prediction-lab/forecasts")
        
        overview = overview_resp.json()
        forecasts = forecasts_resp.json()
        
        assert overview["total_forecasts"] == forecasts["total"], \
            f"Mismatch: overview={overview['total_forecasts']}, forecasts={forecasts['total']}"
        print(f"PASS: Forecast counts match - {overview['total_forecasts']}")

    def test_overview_counts_match_scheduler(self):
        """Overview counts match scheduler-status counts."""
        overview_resp = requests.get(f"{BASE_URL}/api/prediction-lab/overview")
        scheduler_resp = requests.get(f"{BASE_URL}/api/prediction-lab/scheduler-status")
        
        overview = overview_resp.json()
        scheduler = scheduler_resp.json()
        
        assert overview["total_forecasts"] == scheduler["total_forecasts"], \
            f"Mismatch: overview={overview['total_forecasts']}, scheduler={scheduler['total_forecasts']}"
        assert overview["pending_forecasts"] == scheduler["pending_forecasts"], \
            f"Mismatch: overview pending={overview['pending_forecasts']}, scheduler={scheduler['pending_forecasts']}"
        print(f"PASS: Overview and scheduler counts match")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
