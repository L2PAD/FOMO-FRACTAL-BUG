"""
ML Overlay Dataset Builder V2 (Modern Only)
=============================================
Block 5.A.3

Builds dataset ONLY from modern forecasts (v4.2.1+).
Separates into Dataset A (core risk features) and Dataset B (full microstructure).
"""

import os
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

MIN_MODEL_VERSION = "v4.2.1"
CATASTROPHIC_THRESHOLD_PCT = 5.0
OBS_WINDOW_MS = 3600 * 1000


def _get_db():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def _version_gte(v: str, target: str) -> bool:
    try:
        def parse(s):
            s = s.lstrip("v").split("-")[0]
            return tuple(int(x) for x in s.split("."))
        return parse(v) >= parse(target)
    except (ValueError, AttributeError):
        return False


def _compute_label_v2(forecast: dict) -> dict | None:
    """
    Label V2: focused on catastrophicRisk from modern stack.
    Not dependent on neutral bias.
    """
    outcome = forecast.get("outcome")
    if not outcome:
        return None

    real_move = outcome.get("realMovePct") or outcome.get("errorPct") or 0
    dir_match = outcome.get("directionMatch", False)
    direction = (forecast.get("direction") or "NEUTRAL").upper()

    # For NEUTRAL: error if large move happened
    if direction in ("NEUTRAL", "FLAT"):
        is_error = abs(real_move) > 2.0
    else:
        is_error = not dir_match

    # Catastrophic: large adverse move regardless of direction classification
    is_catastrophic = abs(real_move) > CATASTROPHIC_THRESHOLD_PCT and is_error

    return {
        "error_risk": int(is_error),
        "catastrophic_risk": int(is_catastrophic),
        "real_move_pct": real_move,
        "abs_move_pct": abs(real_move),
        "direction_match": dir_match,
    }


def _build_core_features(forecast: dict, obs: dict | None, funding: dict | None) -> dict:
    """
    Dataset A — Core risk features.
    Available from forecast audit + basic market state.
    """
    audit = forecast.get("audit") or {}
    regime_v2 = audit.get("regimeV2") or {}
    regime_adj = audit.get("regimeAdjustments") or {}

    features = {}

    # Forecast meta
    features["confidence"] = forecast.get("confidence", 0.5)
    features["confidence_raw"] = forecast.get("confidenceRaw") or forecast.get("confidence", 0.5)
    features["expected_move_pct"] = forecast.get("expectedMovePct", 0.0)
    features["confidence_gap"] = features["confidence"] - features["confidence_raw"]

    direction = (forecast.get("direction") or "NEUTRAL").upper()
    features["direction_encoded"] = {"LONG": 1, "UP": 1}.get(direction, -1 if direction in ("SHORT", "DOWN") else 0)

    # Regime from audit
    probs = regime_v2.get("probabilities") or {}
    features["regime_prob_trend"] = probs.get("trend", 0.0)
    features["regime_prob_range"] = probs.get("range", 0.0)
    features["regime_prob_transition"] = probs.get("transition", 0.0)
    features["regime_confidence"] = regime_v2.get("regime_confidence", 0.5)
    features["regime_entropy"] = regime_v2.get("regime_entropy", 0.5)

    # Regime features
    rf = regime_v2.get("features") or {}
    features["trend_strength"] = rf.get("trend_strength", 0.0)
    features["reversal_risk"] = rf.get("reversal_risk", 0.0)
    features["drawdown_pressure"] = rf.get("drawdown_pressure", 0.0)
    features["exhaustion_proximity"] = rf.get("exhaustion_proximity", 0.0)

    # Regime adjustment flags (binary)
    flags = regime_adj.get("flags") or []
    features["flag_transition_caution"] = 1 if "transition_caution" in flags else 0
    features["flag_high_entropy"] = 1 if "high_entropy" in flags else 0
    features["flag_transition_hard"] = 1 if "transition_hard_dampen" in flags else 0
    features["flag_uncertainty_damp"] = 1 if "uncertainty_damping" in flags else 0

    # Uncertainty from audit
    features["uncertainty"] = regime_adj.get("uncertainty", 0.5)

    # Scenario features (if available)
    scenarios = forecast.get("scenarios") or {}
    features["scenario_spread"] = scenarios.get("spread", 0.0)
    features["scenario_dominant_prob"] = 0.0
    paths = scenarios.get("paths") or []
    if paths:
        features["scenario_dominant_prob"] = max(p.get("probability", 0) for p in paths)

    # Funding (basic)
    fund = funding or {}
    features["funding_score"] = fund.get("fundingScore", 0.0)

    return features


def _build_full_features(forecast: dict, obs: dict | None, funding: dict | None) -> dict:
    """
    Dataset B — Full microstructure features.
    Core features + orderflow + liquidations + absorption + tactical.
    """
    features = _build_core_features(forecast, obs, funding)

    of = (obs.get("orderFlow") or {}) if obs else {}
    liq = (obs.get("liquidations") or {}) if obs else {}
    vol = (obs.get("volume") or {}) if obs else {}
    oi = (obs.get("openInterest") or {}) if obs else {}
    market = (obs.get("market") or {}) if obs else {}

    # Orderflow
    features["orderflow_imbalance"] = of.get("imbalance", 0.0)
    features["orderflow_dominance"] = of.get("dominance", 0.5)
    features["aggressor_encoded"] = {"BUY": 1, "SELL": -1}.get(of.get("aggressorBias", ""), 0)

    # Liquidations
    features["cascade_active"] = 1 if liq.get("cascadeActive") else 0
    lv = liq.get("longVolume", 0) or 0
    sv = liq.get("shortVolume", 0) or 0
    features["liq_long_volume"] = lv
    features["liq_short_volume"] = sv
    features["liq_ratio"] = lv / max(lv + sv, 1) if (lv + sv) > 0 else 0.5

    # Absorption
    features["absorption_active"] = 1 if of.get("absorption") else 0
    features["absorption_side"] = {"ASK": 1, "BID": -1}.get(of.get("absorptionSide", ""), 0)

    # Funding full
    fund = funding or {}
    features["funding_trend"] = fund.get("fundingTrend", 0.0)

    # Volume/OI
    features["volume_delta"] = vol.get("delta", 0.0)
    features["oi_delta_pct"] = oi.get("deltaPct", 0.0)
    features["price_volatility"] = market.get("volatility", 0.0)

    # Tactical derived
    if obs:
        from tactical.tactical_signal_builder import build_tactical_signals
        from tactical.tactical_fusion_engine import fuse_tactical_signals

        snap = {
            "imbalance": of.get("imbalance", 0.0),
            "dominance": of.get("dominance", 0.5),
            "aggressor_bias": of.get("aggressorBias", "NEUTRAL"),
            "long_liq_volume": lv,
            "short_liq_volume": sv,
            "cascade_active": liq.get("cascadeActive", False),
            "cascade_direction": liq.get("cascadeDirection", ""),
            "cascade_phase": liq.get("cascadePhase") or "",
            "funding_score": fund.get("fundingScore", 0.0),
            "funding_trend": fund.get("fundingTrend", 0.0),
            "funding_label": fund.get("label", "NEUTRAL"),
            "absorption": of.get("absorption", False),
            "absorption_side": of.get("absorptionSide", ""),
        }
        signals = build_tactical_signals(snap)
        fusion = fuse_tactical_signals(signals)
        features["tactical_score"] = fusion["score"]
        features["tactical_bias"] = {"bullish": 1, "bearish": -1}.get(fusion["bias"], 0)
        features["tactical_strength"] = fusion["signal_strength"]
    else:
        features["tactical_score"] = 0.0
        features["tactical_bias"] = 0
        features["tactical_strength"] = 0.0

    features["has_obs"] = 1 if obs else 0
    features["has_funding"] = 1 if funding else 0

    return features


def build_modern_dataset(
    horizon_days: int = 7,
    asset: str = "BTC",
    dataset_type: str = "A",
) -> dict:
    """
    Build ML dataset from modern forecasts only.

    Args:
        dataset_type: "A" (core risk) or "B" (full microstructure)
    """
    db = _get_db()
    symbol = f"{asset}USDT"

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

    # Filter modern only
    modern = [f for f in forecasts if _version_gte(f.get("modelVersion", ""), MIN_MODEL_VERSION)]
    print(f"[Dataset V2] Total: {len(forecasts)}, Modern (>={MIN_MODEL_VERSION}): {len(modern)}")

    build_fn = _build_core_features if dataset_type == "A" else _build_full_features

    rows = []
    for fc in modern:
        labels = _compute_label_v2(fc)
        if not labels:
            continue

        ts = fc.get("createdAt", 0)
        obs = db["exchange_observations"].find_one(
            {"symbol": symbol, "timestamp": {"$lte": ts, "$gte": ts - OBS_WINDOW_MS}},
            {"_id": 0},
        )
        funding = db["exchange_funding_context"].find_one(
            {"symbol": symbol, "ts": {"$lte": ts}},
            {"_id": 0},
            sort=[("ts", -1)],
        )

        features = build_fn(fc, obs, funding)
        rows.append({
            "forecast_id": fc.get("id", ""),
            "created_at": ts,
            "model_version": fc.get("modelVersion", ""),
            "features": features,
            "labels": labels,
        })

    # Stats
    n = len(rows)
    if n == 0:
        return {"ok": False, "type": dataset_type, "rows": [], "stats": {"n_rows": 0}}

    error_pos = sum(1 for r in rows if r["labels"]["error_risk"] == 1)
    cat_pos = sum(1 for r in rows if r["labels"]["catastrophic_risk"] == 1)

    # Feature coverage
    feature_names = list(rows[0]["features"].keys())
    coverage = {}
    for fname in feature_names:
        nonzero = sum(1 for r in rows if r["features"].get(fname, 0) != 0)
        coverage[fname] = round(nonzero / n, 3)

    stats = {
        "n_rows": n,
        "dataset_type": dataset_type,
        "n_features": len(feature_names),
        "feature_names": feature_names,
        "labels": {
            "error_rate": round(error_pos / n, 3),
            "catastrophic_rate": round(cat_pos / n, 3),
        },
        "feature_coverage": coverage,
        "model_versions": list(set(r["model_version"] for r in rows)),
    }

    return {"ok": True, "type": dataset_type, "rows": rows, "stats": stats}


if __name__ == "__main__":
    for dt in ["A", "B"]:
        print(f"\n{'='*60}")
        print(f"DATASET {dt}")
        print(f"{'='*60}")
        result = build_modern_dataset(dataset_type=dt)
        print(json.dumps(result["stats"], indent=2, default=str))
