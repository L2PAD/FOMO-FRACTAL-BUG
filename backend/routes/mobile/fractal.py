"""Fractal routes — multi-scope fractal analysis for mobile app."""
from fastapi import APIRouter, Query
from typing import Optional
from services.fractal_generator import get_fractal_summary, generate_fractal_forecasts

router = APIRouter()


@router.get("/fractal")
async def get_fractal_data(asset: str = Query(default="BTC")):
    """Get fractal analysis summary for mobile app."""
    return get_fractal_summary(asset.upper().strip())


@router.get("/fractal/all")
async def get_all_fractal_data():
    """Get fractal summaries for all scopes."""
    scopes = ["BTC", "ETH", "SOL", "SPX", "DXY"]
    results = {}
    for scope in scopes:
        results[scope] = get_fractal_summary(scope)
    return {"ok": True, "scopes": results}


@router.post("/fractal/generate")
async def trigger_fractal_generation(asset: str = Query(default="BTC")):
    """Manually trigger fractal forecast generation."""
    forecasts = generate_fractal_forecasts(asset.upper().strip())
    return {
        "ok": True,
        "generated": len(forecasts),
        "asset": asset.upper(),
    }
