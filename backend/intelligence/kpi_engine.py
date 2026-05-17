"""
KPI Engine
============
Block 4 — Task 4.3

Aggregates telemetry events into actionable KPIs.
All metrics computed from resolved events only.

Metrics:
  1. Core: accuracy, pnl_total, pnl_avg
  2. Scenario: coverage, dominant_accuracy
  3. Execution: avg_size_factor, mode_distribution
  4. Uncertainty: accuracy_by_uncertainty, pnl_by_uncertainty
  5. Phase: accuracy_by_phase
  6. Catastrophic: catastrophic_rate
"""

import os
from datetime import datetime, timedelta, timezone

from pymongo import MongoClient


TELEMETRY_COL = "intelligence_telemetry"


def _get_db():
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
    db_name = os.environ.get("DB_NAME", "intelligence_engine")
    return MongoClient(mongo_url)[db_name]


def compute_kpis(
    asset: str = "BTC",
    horizon: str | None = None,
    window_days: int = 30,
) -> dict:
    """
    Compute all KPIs from resolved telemetry events.

    Args:
        asset: Asset to filter
        horizon: Optional horizon filter ("7D", "30D")
        window_days: Number of days to look back
    """
    db = _get_db()

    cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days * 2)).isoformat()

    query = {
        "asset": asset,
        "outcome_resolved": True,
        "timestamp": {"$gte": cutoff},
    }
    if horizon:
        query["horizon"] = horizon

    events = list(db[TELEMETRY_COL].find(query, {"_id": 0}))

    if not events:
        return {"n": 0, "window": f"last_{window_days}d", "error": "no resolved events"}

    n = len(events)

    return {
        "n": n,
        "window": f"last_{window_days}d",
        "asset": asset,
        "horizon": horizon or "all",
        **_core_metrics(events),
        "scenario": _scenario_metrics(events),
        "execution": _execution_metrics(events),
        "uncertainty": _uncertainty_metrics(events),
        "phase": _phase_metrics(events),
        "catastrophic": _catastrophic_metrics(events),
    }


def _core_metrics(events: list) -> dict:
    """Core accuracy and PnL metrics."""
    n = len(events)
    correct = sum(1 for e in events if e.get("direction_correct"))
    pnl_total = sum(e.get("pnl", 0) for e in events)
    pnl_values = [e.get("pnl", 0) for e in events]

    return {
        "accuracy": round(correct / n, 4),
        "pnl_total": round(pnl_total, 2),
        "pnl_avg": round(pnl_total / n, 4),
        "pnl_max": round(max(pnl_values), 2) if pnl_values else 0,
        "pnl_min": round(min(pnl_values), 2) if pnl_values else 0,
    }


def _scenario_metrics(events: list) -> dict:
    """Scenario-specific metrics (30D only typically)."""
    scenario_events = [e for e in events if e.get("scenario_ranges")]
    if not scenario_events:
        return {"n": 0, "coverage": None, "dominant_accuracy": None}

    n = len(scenario_events)
    hits = sum(1 for e in scenario_events if e.get("scenario_hit"))

    # Dominant scenario direction accuracy
    dominant_correct = 0
    for e in scenario_events:
        dom = e.get("dominant_scenario")
        if not dom:
            continue
        realized = e.get("realized_return", 0)
        real_dir = "UP" if realized > 0 else "DOWN"

        # Get dominant scenario expected direction from ranges
        ranges = e.get("scenario_ranges", {})
        dom_range = ranges.get(dom, [0, 0])
        dom_center = (dom_range[0] + dom_range[1]) / 2 if len(dom_range) == 2 else 0
        dom_dir = "UP" if dom_center > 0 else "DOWN"
        if dom_dir == real_dir:
            dominant_correct += 1

    # Per-scenario hit distribution
    hit_dist = {"bullish": 0, "base": 0, "bearish": 0}
    for e in scenario_events:
        if not e.get("scenario_hit"):
            continue
        ranges = e.get("scenario_ranges", {})
        realized = e.get("realized_return", 0)
        for stype, srange in ranges.items():
            if len(srange) == 2 and srange[0] <= realized <= srange[1]:
                hit_dist[stype] = hit_dist.get(stype, 0) + 1

    return {
        "n": n,
        "coverage": round(hits / n, 4),
        "dominant_accuracy": round(dominant_correct / n, 4),
        "hit_distribution": hit_dist,
    }


def _execution_metrics(events: list) -> dict:
    """Execution mode distribution and size factor stats."""
    mode_counts = {}
    size_factors = []

    for e in events:
        mode = e.get("execution_mode", "unknown")
        mode_counts[mode] = mode_counts.get(mode, 0) + 1
        sf = e.get("size_factor")
        if sf is not None:
            size_factors.append(sf)

    n = len(events)
    return {
        "avg_size_factor": round(sum(size_factors) / len(size_factors), 4) if size_factors else None,
        "mode_distribution": {k: round(v / n, 4) for k, v in mode_counts.items()},
    }


def _uncertainty_metrics(events: list) -> dict:
    """Accuracy and PnL broken down by uncertainty level."""
    buckets = {"low": [], "mid": [], "high": []}

    for e in events:
        level = e.get("uncertainty_level", "mid")
        if level not in buckets:
            level = "mid"
        buckets[level].append(e)

    result = {}
    for level, group in buckets.items():
        if not group:
            result[level] = {"n": 0}
            continue
        n = len(group)
        correct = sum(1 for e in group if e.get("direction_correct"))
        pnl = sum(e.get("pnl", 0) for e in group)
        result[level] = {
            "n": n,
            "accuracy": round(correct / n, 4),
            "pnl": round(pnl, 2),
            "pnl_avg": round(pnl / n, 4),
        }

    return result


def _phase_metrics(events: list) -> dict:
    """Accuracy and PnL broken down by market phase."""
    phase_groups = {}

    for e in events:
        phase = e.get("phase") or "unknown"
        if phase not in phase_groups:
            phase_groups[phase] = []
        phase_groups[phase].append(e)

    result = {}
    for phase, group in phase_groups.items():
        n = len(group)
        correct = sum(1 for e in group if e.get("direction_correct"))
        pnl = sum(e.get("pnl", 0) for e in group)
        result[phase] = {
            "n": n,
            "accuracy": round(correct / n, 4),
            "pnl": round(pnl, 2),
        }

    return result


def _catastrophic_metrics(events: list, threshold_pct: float = 5.0) -> dict:
    """Count catastrophic errors: wrong direction on large moves."""
    n = len(events)
    catastrophic = 0

    for e in events:
        realized = abs(e.get("realized_return", 0))
        if realized > threshold_pct and not e.get("direction_correct"):
            catastrophic += 1

    return {
        "threshold_pct": threshold_pct,
        "count": catastrophic,
        "rate": round(catastrophic / n, 4) if n > 0 else 0,
    }
