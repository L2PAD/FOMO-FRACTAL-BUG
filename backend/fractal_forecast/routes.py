"""
Fractal Forecast API Routes (Multi-scope)
============================================
Three independent endpoints:
  GET /api/fractal/btc/forecasts
  GET /api/fractal/spx/forecasts
  GET /api/fractal/dxy/forecasts

Plus manual triggers:
  POST /api/fractal/btc/forecasts/run
  POST /api/fractal/spx/forecasts/run
  POST /api/fractal/dxy/forecasts/run
  POST /api/fractal/forecasts/run-all
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Query

from fractal_forecast.repository import query_forecasts

router = APIRouter(tags=["fractal-forecasts"])


def _build_response(scope: str, horizon: str | None, limit: int):
    query = {}
    if horizon:
        query["horizon"] = horizon

    docs = query_forecasts(
        scope=scope,
        context="api_route",
        query=query,
        sort=[("createdAt", -1)],
        limit=limit,
    )

    rows = []
    for doc in docs:
        row = {
            "scope": doc.get("scope", scope),
            "createdAt": doc["createdAt"].isoformat() if isinstance(doc.get("createdAt"), datetime) else str(doc.get("createdAt", "")),
            "evaluateAt": doc["evaluateAt"].isoformat() if isinstance(doc.get("evaluateAt"), datetime) else str(doc.get("evaluateAt", "")),
            "horizon": doc.get("horizon"),
            "entryPrice": doc.get("entryPrice"),
            "targetPrice": doc.get("targetPrice"),
            "expectedReturn": doc.get("expectedReturn"),
            "direction": doc.get("direction"),
            "confidence": doc.get("confidence"),
            "modelVersion": doc.get("modelVersion"),
            "source": doc.get("source"),
            "signalId": doc.get("signalId"),
            "entryPriceSource": doc.get("entryPriceSource"),
            "actualPrice": doc.get("actualPrice"),
            "errorPct": doc.get("errorPct"),
            "hit": doc.get("hit"),
            "directionCorrect": doc.get("directionCorrect"),
            "status": doc.get("status"),
            "fractal_eval": doc.get("fractal_eval"),
        }
        rows.append(row)

    # Summary stats
    resolved = [r for r in rows if r["status"] == "resolved"]
    hits = [r for r in resolved if r["hit"] is True]
    pending_rows = [r for r in rows if r["status"] == "pending"]
    dir_correct = [r for r in resolved if r.get("directionCorrect") is True]

    # F4 multi-metric summary
    tolerance_hits = [r for r in resolved if (r.get("fractal_eval") or {}).get("tolerance_hit") is True]
    range_hits = [r for r in resolved if (r.get("fractal_eval") or {}).get("range_hit") is True]
    direction_hits = [r for r in resolved if (r.get("fractal_eval") or {}).get("direction_hit") is True]
    composite_scores = [
        (r.get("fractal_eval") or {}).get("composite_score", 0)
        for r in resolved if r.get("fractal_eval")
    ]

    now = datetime.now(timezone.utc)
    overdue = 0
    for r in rows:
        if r["status"] == "pending":
            try:
                eval_at = datetime.fromisoformat(r.get("evaluateAt", "").replace("Z", "+00:00"))
                if eval_at.tzinfo is None:
                    eval_at = eval_at.replace(tzinfo=timezone.utc)
                if eval_at <= now:
                    overdue += 1
            except Exception:
                continue

    total_resolved = len(resolved)
    win_rate = len(hits) / total_resolved if total_resolved > 0 else 0
    dir_accuracy = len(dir_correct) / total_resolved if total_resolved > 0 else 0

    avg_error = 0
    if resolved:
        errors = [r["errorPct"] for r in resolved if r["errorPct"] is not None]
        avg_error = sum(errors) / len(errors) if errors else 0

    avg_return = 0
    if resolved:
        returns = []
        for r in resolved:
            if r["actualPrice"] and r["entryPrice"] and r["entryPrice"] > 0:
                if r["direction"] == "UP":
                    ret = (r["actualPrice"] - r["entryPrice"]) / r["entryPrice"]
                elif r["direction"] == "DOWN":
                    ret = (r["entryPrice"] - r["actualPrice"]) / r["entryPrice"]
                else:
                    ret = 0
                returns.append(ret)
        avg_return = sum(returns) / len(returns) if returns else 0

    return {
        "ok": True,
        "scope": scope,
        "rows": rows,
        "summary": {
            "total": len(rows),
            "evaluated": total_resolved,
            "wins": len(hits),
            "losses": len(resolved) - len(hits),
            "pending": len(pending_rows),
            "overdue": overdue,
            "winRate": round(win_rate, 4),
            "dirAccuracy": round(dir_accuracy, 4),
            "avgReturn": round(avg_return, 6),
            "avgError": round(avg_error, 6),
            "multiMetric": {
                "toleranceHits": len(tolerance_hits),
                "rangeHits": len(range_hits),
                "directionHits": len(direction_hits),
                "toleranceRate": round(len(tolerance_hits) / total_resolved, 4) if total_resolved else 0,
                "rangeRate": round(len(range_hits) / total_resolved, 4) if total_resolved else 0,
                "directionRate": round(len(direction_hits) / total_resolved, 4) if total_resolved else 0,
                "avgCompositeScore": round(sum(composite_scores) / len(composite_scores), 4) if composite_scores else 0,
            },
        },
    }


# ── BTC ──────────────────────────────────────────────────
@router.get("/api/fractal/btc/forecasts")
async def get_btc_forecasts(
    horizon: str = Query(None),
    limit: int = Query(40, ge=1, le=200),
):
    return _build_response("BTC", horizon, limit)


@router.post("/api/fractal/btc/forecasts/run")
async def trigger_btc_pipeline():
    from fractal_forecast.pipeline import run_pipeline_for_scope
    return {"ok": True, **run_pipeline_for_scope("BTC")}


# ── SPX ──────────────────────────────────────────────────
@router.get("/api/fractal/spx/forecasts")
async def get_spx_forecasts(
    horizon: str = Query(None),
    limit: int = Query(40, ge=1, le=200),
):
    return _build_response("SPX", horizon, limit)


@router.post("/api/fractal/spx/forecasts/run")
async def trigger_spx_pipeline():
    from fractal_forecast.pipeline import run_pipeline_for_scope
    return {"ok": True, **run_pipeline_for_scope("SPX")}


# ── DXY ──────────────────────────────────────────────────
@router.get("/api/fractal/dxy/forecasts")
async def get_dxy_forecasts(
    horizon: str = Query(None),
    limit: int = Query(40, ge=1, le=200),
):
    return _build_response("DXY", horizon, limit)


@router.post("/api/fractal/dxy/forecasts/run")
async def trigger_dxy_pipeline():
    from fractal_forecast.pipeline import run_pipeline_for_scope
    return {"ok": True, **run_pipeline_for_scope("DXY")}


# ── Run All ──────────────────────────────────────────────
@router.post("/api/fractal/forecasts/run-all")
async def trigger_all_pipelines():
    from fractal_forecast.pipeline import run_all_pipelines
    results = run_all_pipelines()
    return {"ok": True, "results": results}


# ── Legacy endpoint (backward compat) ───────────────────
@router.get("/api/fractal/forecasts")
async def get_fractal_forecasts_legacy(
    scope: str = Query("BTC"),
    horizon: str = Query(None),
    limit: int = Query(40, ge=1, le=200),
):
    return _build_response(scope, horizon, limit)
