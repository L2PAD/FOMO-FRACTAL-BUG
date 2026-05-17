"""
MBrain Shadow Routes — Sprint 3 / Phase A observability surface.

These endpoints are READ-ONLY for the legacy mind. They expose:
  * POST /api/mbrain/shadow/evaluate     — run a single shadow eval and store it
  * GET  /api/mbrain/shadow/recent       — last N rows
  * GET  /api/mbrain/shadow/summary      — rolling-window aggregate metrics
  * GET  /api/mbrain/shadow/health       — TA adapter health probe

NB: production fusion is NOT touched by anything in this file. The data
written to `mbrain_shadow_eval` is for offline analysis & admin telemetry.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Body, Query
from fastapi.responses import JSONResponse

from modules.mbrain_adapters.ta_shadow_fusion import (
    evaluate_shadow,
    fetch_recent,
    summary as fusion_summary,
    summary_rolling as fusion_summary_rolling,
    breakdown as fusion_breakdown,
    timeline as fusion_timeline,
    divergences as fusion_divergences,
    influence_pairs as fusion_influence,
    histogram as fusion_histogram,
)
from modules.mbrain_adapters.trading_terminal_adapter import health as ta_health

router = APIRouter(prefix="/api/mbrain/shadow", tags=["mbrain-shadow"])


@router.post("/evaluate")
async def post_evaluate(
    asset: str = Query("BTC"),
    horizon: str = Query("7D"),
    persist: bool = Query(True),
    legacy: dict = Body(default_factory=dict),
):
    """Run a shadow evaluation (off-loaded to a thread — sync httpx inside)."""
    record = await asyncio.to_thread(
        evaluate_shadow,
        asset=asset,
        horizon=horizon,
        legacy_bias=legacy.get("bias"),
        legacy_confidence=legacy.get("confidence"),
        legacy_signal=legacy.get("signal"),
        persist=persist,
    )
    return JSONResponse(content={"ok": True, "record": record})


@router.get("/recent")
async def get_recent(
    asset: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
):
    rows = await asyncio.to_thread(fetch_recent, asset=asset, limit=limit)
    return {"ok": True, "n": len(rows), "rows": rows}


@router.get("/summary")
async def get_summary(window: int = Query(200, ge=10, le=5000)):
    s = await asyncio.to_thread(fusion_summary, window_n=window)
    return s


@router.get("/summary/rolling")
async def get_summary_rolling():
    """KPIs in rolling time windows: 1h, 24h, 7d, all-time. The dashboard
    uses this for the top status strip — short-term spikes vs long-term."""
    s = await asyncio.to_thread(fusion_summary_rolling)
    return s


@router.get("/histogram")
async def get_histogram(
    metric: str = Query("confidence_shift"),
    bins: int = Query(21, ge=5, le=101),
    window: int = Query(2000, ge=10, le=20000),
):
    return await asyncio.to_thread(fusion_histogram, metric, bins, window)


@router.get("/health")
async def get_health():
    h = await asyncio.to_thread(ta_health)
    return {"ok": True, "ta_adapter": h}


@router.get("/breakdown")
async def get_breakdown(
    dim: str = Query("horizon"),
    window: int = Query(500, ge=10, le=10000),
):
    return await asyncio.to_thread(fusion_breakdown, dim, window)


@router.get("/timeline")
async def get_timeline(
    window: int = Query(500, ge=10, le=10000),
    bucket_minutes: int = Query(60, ge=1, le=1440),
):
    return await asyncio.to_thread(fusion_timeline, window, bucket_minutes)


@router.get("/divergences")
async def get_divergences(
    limit: int = Query(50, ge=1, le=500),
    only_active: bool = Query(True),
):
    rows = await asyncio.to_thread(fusion_divergences, limit, only_active)
    return {"ok": True, "n": len(rows), "rows": rows}


@router.get("/influence")
async def get_influence(window: int = Query(500, ge=10, le=10000)):
    return await asyncio.to_thread(fusion_influence, window)


# ── Standalone observability dashboard (HTML) ───────────────────────────
# A single self-contained page (no React build, no bundler). Uses Chart.js
# from CDN for the timeline + scatter charts. Lives at:
#   /api/mbrain/shadow/dashboard
from fastapi.responses import HTMLResponse as _MShadowHTML


@router.get("/dashboard", response_class=_MShadowHTML, include_in_schema=False)
async def dashboard_html():
    from fastapi.responses import HTMLResponse
    import os
    here = os.path.dirname(__file__)
    html_path = os.path.join(here, "_mbrain_shadow_dashboard.html")
    if not os.path.isfile(html_path):
        return HTMLResponse(content="<h1>Dashboard template missing</h1>", status_code=500)
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    return HTMLResponse(content=html, headers={"Cache-Control": "no-cache"})
