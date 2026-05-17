"""
ML Overlay Readiness Engine
==============================
Block 5.A.2

Computes dataset readiness metrics to determine when ML training is viable.
Exposes GET /api/ml/readiness endpoint.
"""

import os
import math
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

from ml_overlay.overlay_feature_builder import build_features_from_forecast_and_obs

# ── Ready thresholds ──
READINESS_TARGETS = {
    "obs_coverage": 0.5,
    "funding_coverage": 0.6,
    "tactical_coverage": 0.4,
    "non_neutral_share": 0.25,
    "confidence_std": 0.05,
    "usable_rows": 100,
}

# Minimum model version for modern dataset
MIN_MODEL_VERSION = "v4.2.1"

OBS_WINDOW_MS = 3600 * 1000  # 1h


def _get_db():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def _version_gte(v: str, target: str) -> bool:
    """Check if version v >= target (simple numeric comparison)."""
    try:
        def parse(s):
            # Strip prefix 'v' and suffix like '-bootstrap'
            s = s.lstrip("v").split("-")[0]
            return tuple(int(x) for x in s.split("."))
        return parse(v) >= parse(target)
    except (ValueError, AttributeError):
        return False


def compute_readiness(horizon_days: int = 7, asset: str = "BTC") -> dict:
    """
    Compute ML dataset readiness metrics.

    Returns dict with metrics, pass/fail for each threshold, and overall verdict.
    """
    db = _get_db()
    symbol = f"{asset}USDT"

    # ── Fetch evaluated forecasts ──
    forecasts = list(
        db["exchange_forecasts"]
        .find(
            {
                "evaluated": True,
                "horizonDays": horizon_days,
                "outcome": {"$exists": True, "$ne": None},
                "asset": asset,
            },
            {"_id": 0},
        )
        .sort("createdAt", 1)
    )

    total = len(forecasts)
    if total == 0:
        return {"ok": False, "error": "No evaluated forecasts found", "verdict": "NO_DATA"}

    # ── Modern forecasts only ──
    modern = [f for f in forecasts if _version_gte(f.get("modelVersion", ""), MIN_MODEL_VERSION)]

    # ── Direction distribution ──
    directions = [f.get("direction", "NEUTRAL") for f in forecasts]
    neutral_count = sum(1 for d in directions if d in ("NEUTRAL", "FLAT", None))
    non_neutral_share = 1 - (neutral_count / total)

    # ── Confidence stats ──
    confidences = [f.get("confidence", 0) for f in forecasts]
    conf_mean = sum(confidences) / total
    conf_std = math.sqrt(sum((c - conf_mean) ** 2 for c in confidences) / total)

    # ── Regime variance ──
    # Use regimeV2 from audit if available, else from obs
    regime_values = []
    for f in forecasts:
        rv2 = (f.get("audit") or {}).get("regimeV2", {})
        if rv2.get("dominant_regime"):
            regime_values.append(rv2["dominant_regime"])
    regime_unique = len(set(regime_values))
    regime_variance = regime_unique / max(len(regime_values), 1)

    # ── Coverage: obs, funding, tactical ──
    obs_count = 0
    funding_count = 0
    tactical_count = 0
    usable_rows = 0

    for f in forecasts:
        ts = f.get("createdAt", 0)
        has_obs = False
        has_funding = False

        # Check obs
        obs = db["exchange_observations"].find_one(
            {"symbol": symbol, "timestamp": {"$lte": ts, "$gte": ts - OBS_WINDOW_MS}},
            {"_id": 0, "timestamp": 1, "orderFlow": 1},
        )
        if obs:
            has_obs = True
            obs_count += 1
            of = obs.get("orderFlow") or {}
            if of.get("imbalance") is not None:
                tactical_count += 1

        # Check funding
        funding = db["exchange_funding_context"].find_one(
            {"symbol": symbol, "ts": {"$lte": ts}},
            {"_id": 0, "ts": 1},
        )
        if funding and (ts - funding["ts"]) < 24 * 3600 * 1000:
            has_funding = True
            funding_count += 1

        # Usable = has obs + funding
        if has_obs and has_funding:
            usable_rows += 1

    obs_coverage = obs_count / total
    funding_coverage = funding_count / total
    tactical_coverage = tactical_count / total

    # ── Labels ──
    error_count = 0
    catastrophic_count = 0
    for f in forecasts:
        outcome = f.get("outcome") or {}
        dir_match = outcome.get("directionMatch", False)
        real_move = outcome.get("realMovePct") or outcome.get("errorPct") or 0
        direction = (f.get("direction") or "NEUTRAL").upper()

        if direction in ("NEUTRAL", "FLAT"):
            is_error = abs(real_move) > 2.0
        else:
            is_error = not dir_match

        if is_error:
            error_count += 1
        if abs(real_move) > 5.0 and is_error:
            catastrophic_count += 1

    error_rate = error_count / total
    catastrophic_rate = catastrophic_count / total

    # ── Check thresholds ──
    checks = {
        "obs_coverage": obs_coverage >= READINESS_TARGETS["obs_coverage"],
        "funding_coverage": funding_coverage >= READINESS_TARGETS["funding_coverage"],
        "tactical_coverage": tactical_coverage >= READINESS_TARGETS["tactical_coverage"],
        "non_neutral_share": non_neutral_share >= READINESS_TARGETS["non_neutral_share"],
        "confidence_std": conf_std >= READINESS_TARGETS["confidence_std"],
        "usable_rows": usable_rows >= READINESS_TARGETS["usable_rows"],
    }

    passed = sum(1 for v in checks.values() if v)
    verdict = "READY" if passed >= 5 else "HOLD"

    return {
        "ok": True,
        "verdict": verdict,
        "passed": f"{passed}/6",
        "horizon": f"{horizon_days}D",
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "metrics": {
            "total_rows": total,
            "modern_rows": len(modern),
            "usable_rows": usable_rows,
            "coverage": {
                "observations": round(obs_coverage, 3),
                "funding": round(funding_coverage, 3),
                "tactical": round(tactical_coverage, 3),
            },
            "distribution": {
                "neutral_share": round(1 - non_neutral_share, 3),
                "non_neutral_share": round(non_neutral_share, 3),
                "confidence_std": round(conf_std, 4),
                "regime_variance": round(regime_variance, 3),
            },
            "labels": {
                "error_rate": round(error_rate, 3),
                "catastrophic_rate": round(catastrophic_rate, 3),
            },
        },
        "thresholds": READINESS_TARGETS,
        "checks": checks,
    }


if __name__ == "__main__":
    import json
    result = compute_readiness()
    print(json.dumps(result, indent=2, default=str))
