"""
ML Dataset Status — Block 5.A.1
================================
Tracks dataset quality and accumulation progress for ML Overlay training.
Only counts v4.2.1+ forecasts with full audit features.

Tasks implemented:
  1. Dataset counter with feature completeness checks
  2. Quality metrics (variance in entropy, uncertainty, regime diversity)
  3. Minimum threshold enforcement (usable_rows >= 100)
  4. Data purity (only v4.2.1+ with full audit)
"""

import os
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient

_client = None

ML_MINIMUM_ROWS = 100
ML_IDEAL_ROWS = 200
ML_MODEL_VERSION_PREFIX = "v4."  # Only v4+ models
ML_REQUIRED_AUDIT_FIELDS = ["regimeV2", "regimeAdjustments"]


def _db():
    global _client
    if _client is None:
        _client = MongoClient(os.environ["MONGO_URL"])
    return _client[os.environ["DB_NAME"]]


def compute_dataset_status(asset: str = "BTC") -> dict:
    """
    Full dataset status for ML training readiness.
    Returns counts, feature coverage, quality metrics, and readiness verdict.
    """
    col = _db()["exchange_forecasts"]

    # Total evaluated v4+ forecasts
    total_evaluated = col.count_documents({"evaluated": True, "asset": asset})

    # v4+ only
    v4_filter = {
        "evaluated": True,
        "asset": asset,
        "modelVersion": {"$regex": "^v4"},
    }
    v4_total = col.count_documents(v4_filter)

    # With full audit (regimeV2 + regimeAdjustments)
    full_audit_filter = {
        **v4_filter,
        "audit.regimeV2": {"$exists": True},
        "audit.regimeAdjustments": {"$exists": True},
    }
    with_full_audit = col.count_documents(full_audit_filter)

    # With outcome (evaluated and resolved)
    with_outcome = col.count_documents({**full_audit_filter, "outcome": {"$exists": True}})

    # Usable for ML: has full audit + outcome + non-bootstrap
    usable_filter = {
        **full_audit_filter,
        "outcome": {"$exists": True},
        "modelVersion": {"$not": {"$regex": "bootstrap"}},
    }
    usable_rows = col.count_documents(usable_filter)

    # Date range coverage
    days_covered = 0
    if usable_rows > 0:
        oldest = col.find_one(usable_filter, {"_id": 0, "createdAt": 1}, sort=[("createdAt", 1)])
        newest = col.find_one(usable_filter, {"_id": 0, "createdAt": 1}, sort=[("createdAt", -1)])
        if oldest and newest:
            oldest_dt = datetime.fromtimestamp(oldest["createdAt"] / 1000, tz=timezone.utc)
            newest_dt = datetime.fromtimestamp(newest["createdAt"] / 1000, tz=timezone.utc)
            days_covered = max(1, (newest_dt - oldest_dt).days)

    # Quality metrics — only from usable rows
    quality = _compute_quality(col, usable_filter, usable_rows)

    # Readiness verdict
    readiness = _compute_readiness(usable_rows, days_covered, quality)

    return {
        "total_evaluated": total_evaluated,
        "v4_total": v4_total,
        "with_full_audit": with_full_audit,
        "with_outcome": with_outcome,
        "usable_for_ml": usable_rows,
        "days_covered": days_covered,
        "minimum_threshold": ML_MINIMUM_ROWS,
        "ideal_threshold": ML_IDEAL_ROWS,
        "progress_pct": round(min(usable_rows / ML_MINIMUM_ROWS, 1.0) * 100, 1),
        "quality": quality,
        "readiness": readiness,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def _compute_quality(col, usable_filter, usable_rows) -> dict:
    """Compute quality metrics for the usable dataset."""
    if usable_rows == 0:
        return {
            "sufficient": False,
            "reason": "no_usable_data",
            "entropy_variance": 0,
            "uncertainty_variance": 0,
            "regime_diversity": 0,
            "direction_diversity": 0,
            "horizon_coverage": [],
        }

    # Fetch usable docs for quality analysis
    proj = {
        "_id": 0,
        "direction": 1,
        "confidence": 1,
        "horizonDays": 1,
        "audit.regimeV2.dominant_regime": 1,
        "audit.regimeV2.regime_entropy": 1,
        "audit.regimeAdjustments.decision_uncertainty": 1,
        "outcome.hit": 1,
        "outcome.errorPct": 1,
    }
    docs = list(col.find(usable_filter, proj).limit(500))

    # Entropy variance
    entropies = [
        (d.get("audit", {}).get("regimeV2", {}).get("regime_entropy", 0))
        for d in docs
    ]
    entropy_var = _variance(entropies)

    # Uncertainty variance
    uncertainties = [
        (d.get("audit", {}).get("regimeAdjustments", {}).get("decision_uncertainty", 0))
        for d in docs
    ]
    uncertainty_var = _variance(uncertainties)

    # Regime diversity (unique regimes)
    regimes = set()
    for d in docs:
        r = d.get("audit", {}).get("regimeV2", {}).get("dominant_regime", "unknown")
        regimes.add(r.lower())
    regime_diversity = len(regimes)

    # Direction diversity
    directions = set(d.get("direction", "NEUTRAL") for d in docs)
    direction_diversity = len(directions)

    # Horizon coverage
    horizons = set(d.get("horizonDays", 0) for d in docs)

    # All-neutral check
    neutral_pct = sum(1 for d in docs if d.get("direction") == "NEUTRAL") / max(len(docs), 1)
    all_neutral = neutral_pct > 0.95

    # Verdict
    issues = []
    if entropy_var < 0.01:
        issues.append("low_entropy_variance")
    if uncertainty_var < 0.01:
        issues.append("low_uncertainty_variance")
    if regime_diversity < 3:
        issues.append("low_regime_diversity")
    if all_neutral:
        issues.append("all_neutral_bias")

    return {
        "sufficient": len(issues) == 0,
        "issues": issues,
        "entropy_variance": round(entropy_var, 4),
        "uncertainty_variance": round(uncertainty_var, 4),
        "regime_diversity": regime_diversity,
        "unique_regimes": sorted(regimes),
        "direction_diversity": direction_diversity,
        "unique_directions": sorted(directions),
        "horizon_coverage": sorted(horizons),
        "neutral_pct": round(neutral_pct, 3),
        "sample_size": len(docs),
    }


def _compute_readiness(usable_rows: int, days_covered: int, quality: dict) -> dict:
    """Determine if dataset is ready for ML training."""
    blockers = []

    if usable_rows < ML_MINIMUM_ROWS:
        blockers.append({
            "gate": "dataset_size",
            "required": ML_MINIMUM_ROWS,
            "current": usable_rows,
            "message": f"Need {ML_MINIMUM_ROWS - usable_rows} more usable forecasts",
        })

    if not quality.get("sufficient"):
        for issue in quality.get("issues", []):
            blockers.append({
                "gate": "quality",
                "issue": issue,
                "message": f"Quality issue: {issue.replace('_', ' ')}",
            })

    if days_covered < 7 and usable_rows > 0:
        blockers.append({
            "gate": "time_coverage",
            "required_days": 7,
            "current_days": days_covered,
            "message": f"Need at least 7 days of data, currently {days_covered}",
        })

    ready = len(blockers) == 0
    status = "READY" if ready else "BLOCKED"

    # Estimate when ready
    eta = None
    if not ready and usable_rows < ML_MINIMUM_ROWS:
        remaining = ML_MINIMUM_ROWS - usable_rows
        # Assume 3 forecasts/day
        eta_days = max(1, remaining // 3)
        eta = f"~{eta_days} days at 3 forecasts/day"

    return {
        "ready": ready,
        "status": status,
        "blockers": blockers,
        "eta": eta,
    }


def _variance(values):
    """Simple variance computation."""
    if len(values) < 2:
        return 0
    mean = sum(values) / len(values)
    return sum((x - mean) ** 2 for x in values) / len(values)
