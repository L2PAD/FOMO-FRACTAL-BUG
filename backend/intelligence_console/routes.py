"""
Intelligence Console — API Routes
====================================
6 section endpoints + 1 aggregator.
All support ?range=7d|30d|90d|all and ?asset=BTC
"""

from fastapi import APIRouter, Query
from intelligence_console.engine import (
    compute_overview,
    compute_phases,
    compute_regimes,
    compute_scenarios,
    compute_drift,
    compute_tactical,
    compute_full_console,
)

router = APIRouter(prefix="/api/admin/intelligence", tags=["Intelligence Console"])


@router.get("/overview")
async def get_overview(
    range: str = Query("30d", regex="^(7d|30d|90d|all)$"),
    asset: str = Query("BTC"),
):
    return {"ok": True, "data": compute_overview(range, asset)}


@router.get("/phases")
async def get_phases(
    range: str = Query("30d", regex="^(7d|30d|90d|all)$"),
    asset: str = Query("BTC"),
):
    return {"ok": True, "data": compute_phases(range, asset)}


@router.get("/regimes")
async def get_regimes(
    range: str = Query("30d", regex="^(7d|30d|90d|all)$"),
    asset: str = Query("BTC"),
):
    return {"ok": True, "data": compute_regimes(range, asset)}


@router.get("/scenarios")
async def get_scenarios(
    range: str = Query("30d", regex="^(7d|30d|90d|all)$"),
    asset: str = Query("BTC"),
):
    return {"ok": True, "data": compute_scenarios(range, asset)}


@router.get("/drift")
async def get_drift(
    range: str = Query("30d", regex="^(7d|30d|90d|all)$"),
    asset: str = Query("BTC"),
):
    return {"ok": True, "data": compute_drift(range, asset)}


@router.get("/tactical")
async def get_tactical(
    range: str = Query("30d", regex="^(7d|30d|90d|all)$"),
    asset: str = Query("BTC"),
):
    return {"ok": True, "data": compute_tactical(range, asset)}


@router.get("/console")
async def get_console(
    range: str = Query("30d", regex="^(7d|30d|90d|all)$"),
    asset: str = Query("BTC"),
):
    """Aggregator — returns all 6 sections in one response."""
    return {"ok": True, "data": compute_full_console(range, asset)}
