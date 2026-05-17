"""
Confidence Calibrator — Block 8.1
===================================
Maps raw model confidence to calibrated confidence based on historical accuracy.
Per-horizon calibration using piecewise linear interpolation.

Data source: 316 evaluated forecasts (exchange_forecasts collection).

Key findings:
  - 24H (n=17): slightly overconfident (conf 0.19, real 0.12)
  - 7D  (n=162): underconfident (conf 0.43, real 0.59)
  - 30D (n=137): heavily underconfident (conf 0.10, real 0.36)

Guarantees:
  - Monotonic: higher raw -> higher calibrated
  - Bounded: output in [0.0, 1.0]
  - Smooth: linear interpolation between anchors
  - Raw confidence always preserved alongside calibrated
  - Per-horizon: different correction curves per forecast horizon
"""


# Per-horizon empirical calibration anchors: (raw_confidence, calibrated_accuracy)
# Derived from bucket analysis of 316 evaluated forecasts.
CALIBRATION_ANCHORS_BY_HORIZON = {
    "7D": [
        # n=162, most reliable dataset
        # Bucket 0.0-0.2: avg_conf=0.10, real_acc=0.33 (global)
        # Bucket 0.4-0.6: avg_conf=0.43, real_acc=0.59 (per-horizon)
        (0.00, 0.00),
        (0.10, 0.33),   # strong underconfidence
        (0.43, 0.59),   # from per-horizon data
        (0.65, 0.72),   # extrapolated conservatively
        (0.85, 0.82),   # extrapolated
        (1.00, 1.00),
    ],
    "30D": [
        # n=137, raw confidence diversified (Block 8.2.1)
        # Historical accuracy = 0.36, new raw distribution ~0.40-0.50
        # Calibration REDUCES confidence (model now slightly overconfident for 30D)
        (0.00, 0.00),
        (0.20, 0.18),   # low raw → low expected accuracy
        (0.35, 0.30),   # below average
        (0.50, 0.38),   # typical new raw → aligned with historical 0.36
        (0.65, 0.48),   # above average → moderate boost
        (0.80, 0.58),   # high confidence
        (1.00, 1.00),
    ],
    "24H": [
        # n=17, sparse data — model slightly overconfident
        # avg_conf=0.19, real_acc=0.12
        (0.00, 0.00),
        (0.19, 0.12),   # overconfident: reduce
        (0.40, 0.30),   # extrapolated with correction trend
        (0.60, 0.50),   # conservative
        (0.80, 0.68),   # conservative
        (1.00, 0.85),   # ceiling lower due to sparse data
    ],
}

# Fallback anchors for unknown horizons
CALIBRATION_ANCHORS_DEFAULT = [
    (0.00, 0.00),
    (0.10, 0.33),
    (0.45, 0.62),
    (0.70, 0.78),
    (1.00, 1.00),
]


def _interpolate(raw_conf: float, anchors: list[tuple[float, float]]) -> float:
    """Piecewise linear interpolation between anchor points."""
    raw_conf = max(0.0, min(1.0, raw_conf))
    for i in range(len(anchors) - 1):
        x0, y0 = anchors[i]
        x1, y1 = anchors[i + 1]
        if x0 <= raw_conf <= x1:
            if x1 == x0:
                return y0
            t = (raw_conf - x0) / (x1 - x0)
            return round(y0 + t * (y1 - y0), 4)
    return round(raw_conf, 4)


def calibrate_confidence(raw_conf: float, horizon: str = "7D") -> float:
    """Map raw model confidence to calibrated value.

    Args:
        raw_conf: Model's raw confidence value [0, 1]
        horizon: Forecast horizon key ("24H", "7D", "30D")

    Returns:
        Calibrated confidence reflecting true expected accuracy.
    """
    anchors = CALIBRATION_ANCHORS_BY_HORIZON.get(
        horizon, CALIBRATION_ANCHORS_DEFAULT
    )
    return _interpolate(raw_conf, anchors)


def calibrate_confidence_target(raw_conf: float, horizon: str = "7D") -> float:
    """Calibrate confidence for target price hitting.

    Target hitting is harder than direction, so we apply a discount
    to the direction-calibrated value.
    """
    direction_cal = calibrate_confidence(raw_conf, horizon)
    # Target accuracy is ~65-70% of direction accuracy historically
    TARGET_DISCOUNT = {
        "24H": 0.70,
        "7D": 0.68,
        "30D": 0.65,
    }
    discount = TARGET_DISCOUNT.get(horizon, 0.68)
    return round(max(0.05, direction_cal * discount), 4)


def get_calibration_info(horizon: str = "7D") -> dict:
    """Return calibration metadata for audit/debugging."""
    anchors = CALIBRATION_ANCHORS_BY_HORIZON.get(
        horizon, CALIBRATION_ANCHORS_DEFAULT
    )
    return {
        "horizon": horizon,
        "anchors": [{"raw": x, "calibrated": y} for x, y in anchors],
        "method": "piecewise_linear_per_horizon",
        "dataPoints": 316,
        "status": "active",
        "version": "8.1",
    }
