"""
Tests: Forecast Access Guard
==============================
Ensures fractal_forecasts cannot be accessed from decision-making contexts.
"""

import pytest
from fractal_forecast.guard import assert_no_forecast_access, ForecastAccessViolation


class TestForecastGuard:
    """Guard must block forbidden contexts and allow safe ones."""

    def test_api_route_allowed(self):
        assert_no_forecast_access("api_route")

    def test_pipeline_allowed(self):
        assert_no_forecast_access("pipeline")

    def test_evaluator_allowed(self):
        assert_no_forecast_access("evaluator")

    def test_scheduler_allowed(self):
        assert_no_forecast_access("scheduler")

    def test_metabrain_blocked(self):
        with pytest.raises(ForecastAccessViolation):
            assert_no_forecast_access("metabrain")

    def test_meta_brain_blocked(self):
        with pytest.raises(ForecastAccessViolation):
            assert_no_forecast_access("meta_brain_aggregator")

    def test_decision_blocked(self):
        with pytest.raises(ForecastAccessViolation):
            assert_no_forecast_access("final_decision_layer")

    def test_aggregator_blocked(self):
        with pytest.raises(ForecastAccessViolation):
            assert_no_forecast_access("signal_aggregator")

    def test_weight_adjust_blocked(self):
        with pytest.raises(ForecastAccessViolation):
            assert_no_forecast_access("weight_adjust_module")

    def test_confidence_adjust_blocked(self):
        with pytest.raises(ForecastAccessViolation):
            assert_no_forecast_access("confidence_adjust")

    def test_case_insensitive(self):
        with pytest.raises(ForecastAccessViolation):
            assert_no_forecast_access("MetaBrain")

    def test_embedded_context_blocked(self):
        with pytest.raises(ForecastAccessViolation):
            assert_no_forecast_access("some_metabrain_function")
