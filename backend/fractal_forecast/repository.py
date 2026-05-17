"""
Forecast Repository — Single Point of Access
==============================================
ALL reads from fractal forecast collections MUST go through this module.
Direct collection access is forbidden.

This repository enforces the access guard on every query.
"""

from fractal_forecast.common import get_forecast_col
from fractal_forecast.guard import assert_no_forecast_access


def query_forecasts(scope: str, context: str, query: dict, projection: dict = None, sort=None, limit: int = 40):
    """
    Guarded read access to forecast collections.

    Args:
        scope: BTC, SPX, or DXY
        context: caller identifier (e.g. "api_route", "pipeline")
        query: MongoDB query dict
        projection: fields to include/exclude
        sort: sort specification
        limit: max documents

    Raises:
        ForecastAccessViolation if context is forbidden
    """
    assert_no_forecast_access(context)

    col = get_forecast_col(scope)
    proj = projection or {"_id": 0}

    cursor = col.find(query, proj)
    if sort:
        cursor = cursor.sort(sort)
    if limit:
        cursor = cursor.limit(limit)

    return list(cursor)


def count_forecasts(scope: str, context: str, query: dict) -> int:
    """Guarded count."""
    assert_no_forecast_access(context)
    col = get_forecast_col(scope)
    return col.count_documents(query)
