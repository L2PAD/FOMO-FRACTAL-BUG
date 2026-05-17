"""
Scenario Probability Calibration — Block 8.3
==============================================
Calibrates scenario probabilities (bullish/base/bearish) against real outcomes.

Pipeline:
  1. Label outcomes → which scenario realized
  2. Build reliability table → predicted vs actual frequency
  3. Calibrate → piecewise/isotonic mapping per scenario
  4. Renormalize → sum(p) = 1.0 always

Supports:
  - Forecasts WITH explicit scenario ranges (30D)
  - Forecasts WITHOUT scenarios → uses horizon-based standard thresholds
"""

import os
from collections import defaultdict
from pymongo import MongoClient, DESCENDING

# Standard scenario thresholds by horizon (when no explicit ranges exist)
# Defines the % move boundaries for bullish/base/bearish
SCENARIO_THRESHOLDS = {
    "24H": {"bull": 1.5, "bear": -1.5},
    "7D": {"bull": 3.0, "bear": -3.0},
    "30D": {"bull": 5.0, "bear": -5.0},
}


def _get_db():
    return MongoClient(os.environ.get("MONGO_URL"))[os.environ.get("DB_NAME")]


def label_scenario_outcome(
    real_move_pct: float,
    scenarios: dict | None = None,
    horizon: str = "30D",
) -> str:
    """Label which scenario was realized.

    Args:
        real_move_pct: Actual price move in %
        scenarios: Explicit scenario data (if available)
        horizon: Forecast horizon for default thresholds

    Returns:
        "bullish", "base", or "bearish"
    """
    # Try explicit scenario ranges first
    if scenarios and isinstance(scenarios, dict):
        scenario_list = scenarios.get("scenarios", [])
        if scenario_list:
            for s in scenario_list:
                r = s.get("range", [])
                if len(r) == 2 and r[0] <= real_move_pct <= r[1]:
                    return s.get("type", "base")
            # Fallback: closest range
            if real_move_pct > scenario_list[0].get("range", [0, 0])[0]:
                return "bullish"
            elif real_move_pct < scenario_list[-1].get("range", [0, 0])[1]:
                return "bearish"
            return "base"

    # Standard threshold-based labeling
    thresholds = SCENARIO_THRESHOLDS.get(horizon, SCENARIO_THRESHOLDS["30D"])
    if real_move_pct >= thresholds["bull"]:
        return "bullish"
    elif real_move_pct <= thresholds["bear"]:
        return "bearish"
    return "base"


def build_scenario_dataset(
    asset: str | None = None,
    horizon: str | None = None,
) -> list[dict]:
    """Build labeled scenario dataset from evaluated forecasts."""
    db = _get_db()
    col = db["exchange_forecasts"]

    query = {"evaluated": True}
    if asset:
        query["asset"] = asset.upper()
    if horizon:
        query["horizon"] = horizon

    projection = {
        "_id": 0,
        "asset": 1,
        "horizon": 1,
        "confidence": 1,
        "direction": 1,
        "entryPrice": 1,
        "scenarios": 1,
        "outcome": 1,
        "audit": 1,
        "createdBucket": 1,
    }

    rows = []
    for doc in col.find(query, projection):
        outcome = doc.get("outcome")
        if not outcome or not isinstance(outcome, dict):
            continue

        # Support both old and new outcome format
        real_move = outcome.get("realMovePct")
        if real_move is None:
            real_move = outcome.get("deviationPct")
        if real_move is None:
            # Compute from entryPrice + realPrice
            entry = doc.get("entryPrice")
            real_price = outcome.get("realPrice") or outcome.get("actualPriceAtEval")
            if entry and real_price and entry > 0:
                real_move = ((real_price - entry) / entry) * 100
        if real_move is None:
            continue

        scenarios = doc.get("scenarios")
        h = doc.get("horizon", "7D")

        # Label which scenario realized
        realized = label_scenario_outcome(real_move, scenarios, h)

        # Extract raw probabilities (if scenarios exist)
        raw_probs = {"bullish": 1 / 3, "base": 1 / 3, "bearish": 1 / 3}
        if scenarios and isinstance(scenarios, dict):
            for s in scenarios.get("scenarios", []):
                stype = s.get("type")
                if stype in raw_probs:
                    raw_probs[stype] = s.get("probability", raw_probs[stype])

        # Quality score from acceleration
        accel = (doc.get("audit") or {}).get("acceleration", {})
        quality = accel.get("qualityScore", 0.5)
        overlap = accel.get("overlapGroup", "")

        rows.append({
            "asset": doc.get("asset", "BTC"),
            "horizon": h,
            "realMovePct": real_move,
            "realized": realized,
            "rawProbs": raw_probs,
            "hasExplicitScenarios": scenarios is not None,
            "qualityScore": quality,
            "overlapGroup": overlap,
            "confidence": doc.get("confidence"),
        })

    return rows


def compute_scenario_reliability(
    dataset: list[dict],
    n_bins: int = 5,
) -> dict:
    """Compute per-scenario reliability (predicted probability vs actual frequency).

    Returns bucket analysis for each scenario type.
    """
    if not dataset:
        return {"status": "INSUFFICIENT_DATA"}

    results = {}

    for scenario in ["bullish", "base", "bearish"]:
        # For each forecast, get the predicted probability for this scenario
        # and whether this scenario actually realized
        entries = []
        for row in dataset:
            pred_prob = row["rawProbs"].get(scenario, 1 / 3)
            actual = 1.0 if row["realized"] == scenario else 0.0
            entries.append({"pred": pred_prob, "actual": actual})

        if not entries:
            results[scenario] = {"status": "NO_DATA"}
            continue

        # Bucket analysis
        bin_edges = [i / n_bins for i in range(n_bins + 1)]
        buckets = []

        for i in range(n_bins):
            low, high = bin_edges[i], bin_edges[i + 1]
            in_bucket = [e for e in entries if low <= e["pred"] < high]
            if i == n_bins - 1:
                in_bucket = [e for e in entries if low <= e["pred"] <= high]

            if not in_bucket:
                buckets.append({"range": [round(low, 2), round(high, 2)], "count": 0})
                continue

            avg_pred = sum(e["pred"] for e in in_bucket) / len(in_bucket)
            avg_actual = sum(e["actual"] for e in in_bucket) / len(in_bucket)

            buckets.append({
                "range": [round(low, 2), round(high, 2)],
                "avgPred": round(avg_pred, 4),
                "actualFreq": round(avg_actual, 4),
                "gap": round(avg_pred - avg_actual, 4),
                "count": len(in_bucket),
            })

        # Overall stats
        total_pred = sum(e["pred"] for e in entries) / len(entries)
        total_actual = sum(e["actual"] for e in entries) / len(entries)

        results[scenario] = {
            "avgPredicted": round(total_pred, 4),
            "actualFrequency": round(total_actual, 4),
            "gap": round(total_pred - total_actual, 4),
            "sampleSize": len(entries),
            "buckets": buckets,
        }

    # Multiclass Brier Score
    brier = 0.0
    for row in dataset:
        for scenario in ["bullish", "base", "bearish"]:
            pred = row["rawProbs"].get(scenario, 1 / 3)
            actual = 1.0 if row["realized"] == scenario else 0.0
            brier += (pred - actual) ** 2
    brier /= len(dataset)
    brier = round(brier, 6)

    # Outcome distribution
    outcome_counts = defaultdict(int)
    for row in dataset:
        outcome_counts[row["realized"]] += 1
    total = len(dataset)
    distribution = {k: round(v / total, 4) for k, v in sorted(outcome_counts.items())}

    return {
        "sampleSize": total,
        "brierScore": brier,
        "outcomeDistribution": distribution,
        "perScenario": results,
    }


def build_calibration_map(dataset: list[dict]) -> dict:
    """Build piecewise calibration anchors from scenario reliability data.

    For each scenario: maps raw probability → calibrated probability
    based on observed frequency in buckets.
    """
    if len(dataset) < 20:
        return {"status": "INSUFFICIENT_DATA", "minRequired": 20, "current": len(dataset)}

    calibration = {}

    for scenario in ["bullish", "base", "bearish"]:
        entries = []
        for row in dataset:
            pred = row["rawProbs"].get(scenario, 1 / 3)
            actual = 1.0 if row["realized"] == scenario else 0.0
            entries.append((pred, actual))

        # Sort by predicted probability
        entries.sort(key=lambda x: x[0])

        # Build anchors from quintiles
        n = len(entries)
        anchors = [(0.0, 0.0)]

        chunk_size = max(1, n // 5)
        for i in range(0, n, chunk_size):
            chunk = entries[i:i + chunk_size]
            if chunk:
                avg_pred = sum(e[0] for e in chunk) / len(chunk)
                avg_actual = sum(e[1] for e in chunk) / len(chunk)
                anchors.append((round(avg_pred, 4), round(avg_actual, 4)))

        anchors.append((1.0, 1.0))

        # Ensure monotonicity
        for i in range(1, len(anchors)):
            if anchors[i][1] < anchors[i - 1][1]:
                anchors[i] = (anchors[i][0], anchors[i - 1][1])

        calibration[scenario] = anchors

    return {"status": "OK", "anchors": calibration}


def calibrate_scenario_probs(
    raw_probs: dict[str, float],
    calibration_map: dict,
) -> dict[str, float]:
    """Apply calibration to scenario probabilities and renormalize."""
    if not calibration_map or calibration_map.get("status") != "OK":
        return raw_probs

    anchors_map = calibration_map.get("anchors", {})
    calibrated = {}

    for scenario in ["bullish", "base", "bearish"]:
        raw = raw_probs.get(scenario, 1 / 3)
        anchors = anchors_map.get(scenario, [(0.0, 0.0), (1.0, 1.0)])
        calibrated[scenario] = _interpolate(raw, anchors)

    # Renormalize: sum must equal 1.0
    total = sum(calibrated.values()) + 1e-8
    calibrated = {k: round(v / total, 4) for k, v in calibrated.items()}

    return calibrated


def _interpolate(value: float, anchors: list[tuple]) -> float:
    """Piecewise linear interpolation."""
    value = max(0.0, min(1.0, value))
    for i in range(len(anchors) - 1):
        x0, y0 = anchors[i]
        x1, y1 = anchors[i + 1]
        if x0 <= value <= x1:
            if x1 == x0:
                return y0
            t = (value - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return value


def compute_scenario_metrics(
    asset: str | None = None,
    horizon: str | None = None,
) -> dict:
    """Full scenario calibration analysis."""
    dataset = build_scenario_dataset(asset, horizon)
    reliability = compute_scenario_reliability(dataset)
    cal_map = build_calibration_map(dataset)

    # Simulate calibrated Brier
    if cal_map.get("status") == "OK" and dataset:
        brier_cal = 0.0
        for row in dataset:
            cal_probs = calibrate_scenario_probs(row["rawProbs"], cal_map)
            for scenario in ["bullish", "base", "bearish"]:
                pred = cal_probs.get(scenario, 1 / 3)
                actual = 1.0 if row["realized"] == scenario else 0.0
                brier_cal += (pred - actual) ** 2
        brier_cal = round(brier_cal / len(dataset), 6)
    else:
        brier_cal = None

    return {
        "asset": asset or "ALL",
        "horizon": horizon or "ALL",
        "reliability": reliability,
        "calibrationMap": cal_map,
        "simulatedBrierAfterCal": brier_cal,
        "improvement": {
            "brierDelta": round(reliability.get("brierScore", 0) - brier_cal, 6) if brier_cal else None,
        } if brier_cal else None,
    }
