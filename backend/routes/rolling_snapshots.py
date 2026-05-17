"""
ROLLING PREDICTION SNAPSHOTS
============================
Serves /api/prediction/snapshots from the `fractal_rolling_snapshots`
Mongo collection backfilled by `scripts/backfill_rolling_forecasts.py`.

Each snapshot contains:
  • asOf          — date when the model was "as of"
  • asOfPrice     — actual price on that day
  • series        — [{t, v}, ...] forecast points going forward `horizonDays`
  • metadata.{stance, confidence, analogCount, source}

The frontend (LivePredictionChart) renders multiple historical snapshots
trimmed at the next snapshot's asOf — producing a continuous black line
that visualises the model's *past* belief over time, so the user can see
where it diverged from reality (real candles).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query
from pymongo import MongoClient, DESCENDING

router = APIRouter(prefix="/api/prediction", tags=["prediction_snapshots"])

_MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
_DB_NAME   = os.environ.get("DB_NAME", "fomo_mobile")
_client    = MongoClient(_MONGO_URL)
_coll      = _client[_DB_NAME].fractal_rolling_snapshots


@router.get("/snapshots")
def get_snapshots(
    asset: str = Query("BTC"),
    view: str = Query("hybrid"),
    horizon: int = Query(180),
    limit: int = Query(60),
):
    """Return historical rolling-forecast snapshots for the chart.

    Frontend `LivePredictionChart.fetchSnapshots` expects:
      { ok: true, snapshots: [ { asOf, asOfPrice, series, metadata, … }, … ] }

    The chart will sort by asOf ascending, use the LAST snapshot as the
    active forecast, and draw earlier snapshots as dashed lines trimmed
    at the next snapshot's asOf (forming a continuous past-belief trail).
    """
    asset = (asset or "BTC").upper()
    view = (view or "hybrid").lower()
    h_int = int(horizon or 180)

    # Strategy: rolling backfill stored 30d snapshots.  For any requested
    # horizon, we return all rolling snapshots (asset filter) regardless
    # of stored horizonDays — the chart only cares about the forecast
    # SHAPE relative to each asOf anchor.  This avoids gaps when the
    # frontend asks for 90d / 180d / 365d.
    query = {"asset": asset, "metadata.source": "rolling_v1"}
    cursor = _coll.find(query, {"_id": 0}).sort("asOf", DESCENDING).limit(int(limit))
    snaps = list(cursor)

    return {
        "ok":         True,
        "asset":      asset,
        "view":       view,
        "horizonDays": h_int,
        "count":      len(snaps),
        "snapshots":  snaps,
    }


@router.get("/snapshots/latest")
def get_latest_snapshot(
    asset: str = Query("BTC"),
    view: str = Query("hybrid"),
):
    asset = (asset or "BTC").upper()
    view = (view or "hybrid").lower()
    snap = _coll.find_one(
        {"asset": asset, "metadata.source": "rolling_v1"},
        {"_id": 0},
        sort=[("asOf", DESCENDING)],
    )
    if not snap:
        return {"ok": False, "reason": "no_snapshots_available"}
    return {"ok": True, "asset": asset, "view": view, "snapshot": snap}
