"""
Intelligence Layer — Routes
==============================
Cross-cutting intelligence endpoints:
  - OTC Detection
  - Market Maker Detection
  - Live Monitoring KPIs (Block 4)
  - Scenario Performance
  - Phase Intelligence
"""

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/intelligence", tags=["intelligence-layer"])


@router.get("/otc")
def otc_detections(entity: str = None):
    """Detect probable OTC trades across entities or for a specific entity."""
    from .otc_service import detect_otc_trades
    result = detect_otc_trades(entity_slug=entity)
    return JSONResponse(content={"ok": True, **result})


@router.get("/market-makers")
def market_makers():
    """Detect probable hidden market makers among tracked entities."""
    from .market_maker_service import detect_market_makers
    result = detect_market_makers()
    return JSONResponse(content={"ok": True, **result})


# ── Block 4: Live Monitoring Endpoints ──

@router.get("/kpi")
def get_kpis(
    asset: str = Query("BTC"),
    horizon: str = Query(None),
    window: int = Query(30, description="Window in days"),
):
    """Main KPI endpoint: accuracy, PnL, scenario coverage, uncertainty, phase performance."""
    from intelligence.kpi_engine import compute_kpis
    result = compute_kpis(asset=asset, horizon=horizon, window_days=window)
    return {"ok": True, "data": result}


@router.get("/scenarios")
def get_scenario_performance(
    asset: str = Query("BTC"),
    window: int = Query(30),
):
    """Scenario performance: coverage, dominant accuracy, hit distribution."""
    from intelligence.kpi_engine import compute_kpis
    kpis = compute_kpis(asset=asset, window_days=window)
    return {
        "ok": True,
        "data": {
            "n": kpis.get("n", 0),
            "scenario": kpis.get("scenario", {}),
            "catastrophic": kpis.get("catastrophic", {}),
        },
    }


@router.get("/phases")
def get_phase_intelligence(
    asset: str = Query("BTC"),
    window: int = Query(30),
):
    """Phase-level performance: which market phases produce best/worst results."""
    from intelligence.kpi_engine import compute_kpis
    kpis = compute_kpis(asset=asset, window_days=window)
    return {
        "ok": True,
        "data": {
            "n": kpis.get("n", 0),
            "phase": kpis.get("phase", {}),
        },
    }


@router.get("/events")
def get_events(
    limit: int = Query(50, le=200),
    horizon: str = Query(None),
):
    """Get recent telemetry events."""
    from intelligence.telemetry.telemetry_recorder import get_recent_events
    events = get_recent_events(limit=limit, horizon=horizon)
    return {"ok": True, "data": events, "count": len(events)}


@router.post("/resolve")
def trigger_resolve(asset: str = Query("BTC")):
    """Trigger outcome resolution for unresolved events."""
    from intelligence.telemetry.outcome_resolver import resolve_outcomes
    stats = resolve_outcomes(asset=asset)
    return {"ok": True, "data": stats}


@router.post("/backfill-telemetry")
def backfill_telemetry(
    asset: str = Query("BTC"),
    limit: int = Query(100),
):
    """Backfill telemetry from existing exchange_forecasts collection."""
    import os
    from pymongo import MongoClient
    from intelligence.telemetry.telemetry_recorder import record_from_stored_forecast

    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
    db_name = os.environ.get("DB_NAME", "intelligence_engine")
    db = MongoClient(mongo_url)[db_name]

    forecasts = list(db["exchange_forecasts"].find(
        {"asset": asset}, {"_id": 0},
    ).sort("madeAtTs", -1).limit(limit))

    recorded = 0
    skipped = 0

    for doc in forecasts:
        existing = db["intelligence_telemetry"].find_one(
            {"entry_price": doc.get("entryPrice"), "horizon": doc.get("horizonLabel")},
        )
        if existing:
            skipped += 1
            continue
        event_id = record_from_stored_forecast(doc)
        if event_id:
            recorded += 1

    return {
        "ok": True,
        "data": {
            "total_forecasts": len(forecasts),
            "recorded": recorded,
            "skipped": skipped,
        },
    }
