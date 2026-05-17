"""
Forecast Access Guard
======================
SECURITY: Prevents fractal_forecasts from being used in
MetaBrain, decision, signal aggregation, or any prediction logic.

fractal_forecasts = observability layer ONLY.
It must NEVER influence model decisions.

If this guard throws — someone tried to cross the boundary.
"""

import traceback

FORBIDDEN_CONTEXTS = frozenset([
    "metabrain",
    "meta_brain",
    "decision",
    "aggregator",
    "signal_aggregat",
    "final_decision",
    "weight_adjust",
    "confidence_adjust",
])


class ForecastAccessViolation(Exception):
    """Raised when forecast data is accessed from a forbidden context."""
    pass


def assert_no_forecast_access(context: str):
    """
    Guard: blocks access to fractal_forecasts from decision-making code.

    Usage:
        assert_no_forecast_access("api_route")  # OK
        assert_no_forecast_access("metabrain")   # RAISES

    Args:
        context: caller identifier (module/function name)

    Raises:
        ForecastAccessViolation if context is in the forbidden list
    """
    lower = context.lower()

    for forbidden in FORBIDDEN_CONTEXTS:
        if forbidden in lower:
            stack = traceback.format_stack()
            print(f"[FORECAST BREACH] Illegal access from '{context}'")
            print(f"[FORECAST BREACH] Stack:\n{''.join(stack[-5:])}")
            raise ForecastAccessViolation(
                f"Illegal access to fractal_forecasts from '{context}'. "
                f"Forecasts are an observability layer and MUST NOT be used in prediction logic."
            )
