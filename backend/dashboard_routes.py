"""
Intelligence Dashboard API
============================
Backend endpoints for the Interaction/Meta monitoring dashboard.
All endpoints use the same filter contract: ?horizon=all&period=7d
Queries evaluated exchange_forecasts with interaction audit data.
"""

import os
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Query
from motor.motor_asyncio import AsyncIOMotorClient

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

_client = AsyncIOMotorClient(os.environ["MONGO_URL"])
_db = _client[os.environ.get("DB_NAME", "institutional")]
_col = _db["exchange_forecasts"]

HORIZONS = ("24H", "7D", "30D")
STATE_GROUPS = {
    "aligned_bullish": "aligned", "aligned_bearish": "aligned",
    "fragile_bullish": "fragile", "fragile_bearish": "fragile",
    "transition_conflict": "conflict",
    "range_mixed": "range", "mixed_unclear": "range",
}


def _build_match(horizon: str, period: str) -> dict:
    m: dict = {}
    now = datetime.now(timezone.utc)
    period_map = {"24h": 1, "7d": 7, "30d": 30}
    if period in period_map:
        m["createdAt"] = {"$gte": int((now - timedelta(days=period_map[period])).timestamp() * 1000)}
    if horizon != "all" and horizon in HORIZONS:
        m["horizon"] = horizon
    return m


def _safe_div(a, b, default=0.0):
    return round(a / b, 4) if b else default


@router.get("/overview")
async def dashboard_overview(
    horizon: str = Query("all"),
    period: str = Query("7d"),
):
    match = _build_match(horizon, period)
    total = await _col.count_documents(match)
    eval_match = {**match, "evaluated": True}
    evaluated = await _col.count_documents(eval_match)

    pipeline = [
        {"$match": eval_match},
        {"$group": {
            "_id": None,
            "tp": {"$sum": {"$cond": [{"$eq": ["$outcome", "TP"]}, 1, 0]}},
            "fp": {"$sum": {"$cond": [{"$eq": ["$outcome", "FP"]}, 1, 0]}},
            "fn": {"$sum": {"$cond": [{"$eq": ["$outcome", "FN"]}, 1, 0]}},
            "weak": {"$sum": {"$cond": [{"$eq": ["$outcome", "WEAK"]}, 1, 0]}},
            "avg_err": {"$avg": "$errorPct"},
        }},
    ]
    agg = await _col.aggregate(pipeline).to_list(1)
    r = agg[0] if agg else {}
    directional = r.get("tp", 0) + r.get("fp", 0) + r.get("fn", 0)

    return {
        "total_forecasts": total,
        "evaluated": evaluated,
        "evaluated_pct": _safe_div(evaluated * 100, total),
        "hit_rate": _safe_div(r.get("tp", 0), directional),
        "fp_rate": _safe_div(r.get("fp", 0), directional),
        "avg_error": round(r.get("avg_err", 0) or 0, 2),
        "sample_size": evaluated,
        "active_layers": {
            "interaction": True,
            "stage2_confidence": True,
            "meta_v1": False,
            "meta_v2": False,
        },
    }


@router.get("/calibration")
async def dashboard_calibration(
    horizon: str = Query("all"),
    period: str = Query("7d"),
):
    match = {**_build_match(horizon, period), "evaluated": True}
    docs = await _col.find(
        match,
        {"_id": 0, "confidence": 1, "outcome": 1, "direction": 1},
    ).to_list(5000)

    if not docs:
        return {"ece": None, "brier": None, "sharpness": None, "sample_size": 0, "buckets": []}

    buckets_map = {}
    brier_sum = 0.0
    n = 0
    for d in docs:
        conf = d.get("confidence")
        outcome = d.get("outcome", "")
        if conf is None:
            continue
        hit = 1.0 if outcome == "TP" else 0.0
        brier_sum += (conf - hit) ** 2
        n += 1
        b = round(min(conf, 0.99), 1)
        if b not in buckets_map:
            buckets_map[b] = {"sum_conf": 0.0, "sum_hit": 0.0, "count": 0}
        buckets_map[b]["sum_conf"] += conf
        buckets_map[b]["sum_hit"] += hit
        buckets_map[b]["count"] += 1

    brier = round(brier_sum / n, 4) if n else None

    buckets = []
    ece = 0.0
    for b_val in sorted(buckets_map.keys()):
        bk = buckets_map[b_val]
        avg_conf = bk["sum_conf"] / bk["count"]
        actual = bk["sum_hit"] / bk["count"]
        ece += abs(avg_conf - actual) * bk["count"]
        buckets.append({
            "conf": round(avg_conf, 2),
            "actual": round(actual, 2),
            "count": bk["count"],
        })
    ece = round(ece / n, 4) if n else None

    confs = [d["confidence"] for d in docs if d.get("confidence") is not None]
    sharpness = round((sum((c - sum(confs) / len(confs)) ** 2 for c in confs) / len(confs)) ** 0.5, 4) if confs else None

    return {
        "ece": ece,
        "brier": brier,
        "sharpness": sharpness,
        "sample_size": n,
        "buckets": buckets,
    }


@router.get("/interaction")
async def dashboard_interaction(
    horizon: str = Query("all"),
    period: str = Query("7d"),
):
    match = {**_build_match(horizon, period), "evaluated": True, "audit.interaction": {"$exists": True}}
    docs = await _col.find(
        match,
        {"_id": 0, "audit.interaction": 1, "outcome": 1, "direction": 1},
    ).to_list(5000)

    if not docs:
        return {
            "sample_size": 0,
            "state_distribution": {},
            "performance_by_state": [],
            "confidence_delta": {},
            "confidence_flow": {"avg_before": None, "avg_after": None, "avg_delta": None},
        }

    group_counts = {}
    group_correct = {}
    group_fp = {}
    group_deltas = {}
    all_before = []
    all_after = []

    for d in docs:
        ia = d.get("audit", {}).get("interaction", {})
        sg = ia.get("state_group") or STATE_GROUPS.get(ia.get("state", ""), "range")
        outcome = d.get("outcome", "")

        group_counts[sg] = group_counts.get(sg, 0) + 1
        if outcome == "TP":
            group_correct[sg] = group_correct.get(sg, 0) + 1
        if outcome == "FP":
            group_fp[sg] = group_fp.get(sg, 0) + 1

        delta = ia.get("confidence_delta")
        if delta is not None:
            group_deltas.setdefault(sg, []).append(delta)
        before = ia.get("confidence_before_interaction")
        after = ia.get("confidence_after_interaction")
        if before is not None:
            all_before.append(before)
        if after is not None:
            all_after.append(after)

    total = sum(group_counts.values())
    state_dist = {g: round(c / total, 2) for g, c in group_counts.items()} if total else {}

    perf = []
    for g in ("aligned", "fragile", "conflict", "range"):
        cnt = group_counts.get(g, 0)
        if cnt == 0:
            continue
        directional = group_correct.get(g, 0) + group_fp.get(g, 0)
        perf.append({
            "state": g,
            "accuracy": _safe_div(group_correct.get(g, 0), directional),
            "fp_rate": _safe_div(group_fp.get(g, 0), directional) if directional else _safe_div(group_fp.get(g, 0), cnt),
            "count": cnt,
        })

    conf_delta = {}
    for g, deltas in group_deltas.items():
        conf_delta[g] = round(sum(deltas) / len(deltas), 4) if deltas else 0.0

    avg_b = round(sum(all_before) / len(all_before), 4) if all_before else None
    avg_a = round(sum(all_after) / len(all_after), 4) if all_after else None

    return {
        "sample_size": total,
        "state_distribution": state_dist,
        "performance_by_state": perf,
        "confidence_delta": conf_delta,
        "confidence_flow": {
            "avg_before": avg_b,
            "avg_after": avg_a,
            "avg_delta": round(avg_a - avg_b, 4) if avg_b is not None and avg_a is not None else None,
        },
    }


@router.get("/decision")
async def dashboard_decision(
    horizon: str = Query("all"),
    period: str = Query("7d"),
):
    match = {**_build_match(horizon, period), "evaluated": True}
    pipeline = [
        {"$match": match},
        {"$group": {
            "_id": {"direction": "$direction", "horizon": "$horizon"},
            "count": {"$sum": 1},
        }},
    ]
    agg = await _col.aggregate(pipeline).to_list(100)

    total = sum(r["count"] for r in agg)
    dir_counts = {}
    by_horizon = {}
    for r in agg:
        d = r["_id"]["direction"]
        h = r["_id"]["horizon"]
        dir_counts[d] = dir_counts.get(d, 0) + r["count"]
        if h not in by_horizon:
            by_horizon[h] = {"LONG": 0, "SHORT": 0, "NEUTRAL": 0}
        by_horizon[h][d] = by_horizon[h].get(d, 0) + r["count"]

    dir_dist = {d: _safe_div(c, total) for d, c in dir_counts.items()} if total else {}

    by_h_list = []
    for h in HORIZONS:
        if h in by_horizon:
            ht = sum(by_horizon[h].values())
            by_h_list.append({
                "horizon": h,
                "long": _safe_div(by_horizon[h].get("LONG", 0), ht),
                "short": _safe_div(by_horizon[h].get("SHORT", 0), ht),
                "neutral": _safe_div(by_horizon[h].get("NEUTRAL", 0), ht),
            })

    return {
        "sample_size": total,
        "direction_distribution": dir_dist,
        "by_horizon": by_h_list,
    }


@router.get("/distribution")
async def dashboard_distribution(
    horizon: str = Query("all"),
    period: str = Query("7d"),
):
    match = {**_build_match(horizon, period), "evaluated": True, "confidence": {"$exists": True}}
    docs = await _col.find(match, {"_id": 0, "confidence": 1}).to_list(5000)

    bins = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)]
    histogram = []
    for lo, hi in bins:
        cnt = sum(1 for d in docs if lo <= (d.get("confidence") or 0) < hi)
        histogram.append({"bucket": f"{lo:.1f}-{hi:.1f}".replace("1.0", "1.0"), "count": cnt})

    return {"confidence_histogram": histogram}


@router.get("/alerts")
async def dashboard_alerts(
    horizon: str = Query("all"),
    period: str = Query("7d"),
):
    alerts = []

    cal = await dashboard_calibration(horizon, period)
    if cal["ece"] is not None and cal["ece"] > 0.08:
        alerts.append({"type": "CRITICAL", "message": f"ECE деградировала: {cal['ece']:.3f} > 0.08", "severity": "high"})
    if cal["brier"] is not None and cal["brier"] > 0.28:
        alerts.append({"type": "WARNING", "message": f"Brier score высокий: {cal['brier']:.3f}", "severity": "medium"})

    inter = await dashboard_interaction(horizon, period)
    if inter["sample_size"] < 50:
        alerts.append({"type": "WARNING", "message": f"Мало данных: N={inter['sample_size']}", "severity": "medium"})
    for p in inter.get("performance_by_state", []):
        if p["state"] == "conflict" and p["fp_rate"] > 0.55:
            alerts.append({"type": "WARNING", "message": f"FP в conflict: {p['fp_rate']:.0%}", "severity": "medium"})

    flow = inter.get("confidence_flow", {})
    if flow.get("avg_delta") is not None and abs(flow["avg_delta"]) > 0.10:
        alerts.append({"type": "WARNING", "message": f"Confidence delta слишком сильный: {flow['avg_delta']:+.3f}", "severity": "medium"})

    if not alerts:
        alerts.append({"type": "OK", "message": "Система стабильна", "severity": "low"})

    return {"alerts": alerts}
