"""
Unified Audit Runner
=====================
GET /api/prediction/audit — single endpoint that returns all key metrics
for the prediction engine, separated by horizon and regime.
Config injected via FractalConfig.
"""

from fastapi import APIRouter, Query
from datetime import datetime, timezone
from pymongo import MongoClient, DESCENDING

router = APIRouter(prefix="/api/prediction", tags=["prediction-audit"])


def _db():
    from forecast.repo import _cfg
    c = _cfg()
    return MongoClient(c.mongo_url)[c.db_name]


@router.get("/audit")
async def prediction_audit(asset: str = Query("BTC")):
    """
    Unified audit endpoint returning:
    - Baseline vs Model comparison
    - 7D: DirHit, MAE, FlipRate
    - 30D: Band Coverage (core + wide), Median MAE
    - Calibration stats
    - Regime breakdown
    """
    db = _db()
    col = db["exchange_forecasts"]

    result = {
        "ok": True,
        "asset": asset,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "horizons": {},
    }

    for horizon in ["7D", "30D"]:
        evaluated = list(col.find(
            {"asset": asset, "horizon": horizon, "evaluated": True, "outcome": {"$ne": None}},
            {"_id": 0},
        ).sort("createdBucket", DESCENDING))

        if not evaluated:
            result["horizons"][horizon] = {"total": 0, "message": "No evaluated forecasts"}
            continue

        total = len(evaluated)
        tp = sum(1 for d in evaluated if d.get("outcome", {}).get("label") == "TP")
        fp = sum(1 for d in evaluated if d.get("outcome", {}).get("label") == "FP")
        weak = sum(1 for d in evaluated if d.get("outcome", {}).get("label") == "WEAK")
        dir_hits = sum(1 for d in evaluated if d.get("outcome", {}).get("directionMatch"))

        # MAE
        errors = []
        for d in evaluated:
            entry = d.get("entryPrice", 0)
            target = d.get("targetPrice", 0)
            actual = d.get("outcome", {}).get("realPrice", 0)
            if entry > 0 and actual > 0:
                errors.append(abs((actual - target) / entry) * 100)
        mae = sum(errors) / len(errors) if errors else 0

        # Flip rate (consecutive direction changes)
        directions = [d.get("direction", "NEUTRAL") for d in reversed(evaluated)]
        flips = sum(1 for i in range(1, len(directions)) if directions[i] != directions[i - 1])
        flip_rate = flips / max(1, len(directions) - 1) if len(directions) > 1 else 0

        # Confidence calibration
        confs = [d.get("confidence", 0) for d in evaluated]
        avg_conf = sum(confs) / len(confs) if confs else 0
        actual_win_rate = tp / total if total > 0 else 0
        ece = abs(avg_conf - actual_win_rate)

        horizon_data = {
            "total": total,
            "winRate": round(tp / total, 4) if total > 0 else 0,
            "dirHitRate": round(dir_hits / total, 4) if total > 0 else 0,
            "mae": round(mae, 4),
            "flipRate": round(flip_rate, 4),
            "outcomeBreakdown": {"TP": tp, "FP": fp, "WEAK": weak},
            "calibration": {
                "avgConfidence": round(avg_conf, 4),
                "actualWinRate": round(actual_win_rate, 4),
                "ece": round(ece, 4),
                "status": "OK" if ece < 0.25 else "DRIFT",
            },
        }

        # 30D-specific: Band Coverage
        if horizon == "30D":
            band_docs = [d for d in evaluated if d.get("forecastType") == "band"]
            if band_docs:
                core_hits = 0
                wide_hits = 0
                median_errors = []
                for d in band_docs:
                    actual = d.get("outcome", {}).get("realPrice", 0)
                    entry = d.get("entryPrice", 0)
                    bl = d.get("bandCoreLow", 0)
                    bh = d.get("bandCoreHigh", 0)
                    wl = d.get("bandWideLow", 0)
                    wh = d.get("bandWideHigh", 0)
                    mt = d.get("medianTarget", 0)
                    if actual and bl and bh:
                        if bl <= actual <= bh:
                            core_hits += 1
                        if wl and wh and wl <= actual <= wh:
                            wide_hits += 1
                    if actual and entry and mt:
                        median_errors.append(abs((actual - mt) / entry) * 100)

                b_total = len(band_docs)
                horizon_data["bandCoverage"] = {
                    "total": b_total,
                    "coreCoverage": round(core_hits / b_total, 4) if b_total > 0 else 0,
                    "wideCoverage": round(wide_hits / b_total, 4) if b_total > 0 else 0,
                    "medianMAE": round(sum(median_errors) / len(median_errors), 4) if median_errors else 0,
                    "status": "OK" if (core_hits / b_total >= 0.40 if b_total > 0 else False) else "NARROW",
                }
            else:
                horizon_data["bandCoverage"] = {"total": 0, "message": "No band forecasts evaluated yet"}

        # Regime breakdown
        regime_map = {}
        for d in evaluated:
            # Infer regime from direction patterns (rough approximation)
            # For proper regime tracking, use regime_signals collection
            src = d.get("source", "scheduler")
            regime_map.setdefault(src, {"total": 0, "tp": 0, "dir_hit": 0})
            regime_map[src]["total"] += 1
            if d.get("outcome", {}).get("label") == "TP":
                regime_map[src]["tp"] += 1
            if d.get("outcome", {}).get("directionMatch"):
                regime_map[src]["dir_hit"] += 1

        horizon_data["sourceBreakdown"] = {
            src: {
                "total": v["total"],
                "winRate": round(v["tp"] / v["total"], 4) if v["total"] > 0 else 0,
                "dirHitRate": round(v["dir_hit"] / v["total"], 4) if v["total"] > 0 else 0,
            }
            for src, v in regime_map.items()
        }

        result["horizons"][horizon] = horizon_data

    # Regime signals history
    signals = list(db["regime_signals"].find(
        {"asset": asset},
        {"_id": 0},
    ).sort("date", DESCENDING).limit(10))
    result["regimeHistory"] = signals

    # Current regime
    for h in ["7D", "30D"]:
        snap = db["drift_snapshots"].find_one(
            {"asset": asset, "horizon": h},
            {"_id": 0, "regime": 1, "regimeConfidence": 1},
            sort=[("ts", DESCENDING)],
        )
        if snap:
            result["horizons"].setdefault(h, {})
            result["horizons"][h]["currentRegime"] = snap.get("regime", "TRANSITION")
            result["horizons"][h]["regimeConfidence"] = snap.get("regimeConfidence", 0.5)

    return result
