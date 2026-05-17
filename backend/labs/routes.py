"""
Labs V2 API routes.
GET /api/exchange/labs?mode=global|universe|asset&asset=BTCUSDT
GET /api/exchange/labs/drilldown?lab=liquidity&asset=BTCUSDT
GET /api/exchange/labs/symbols
"""

from fastapi import APIRouter, Query
from .service import _get_labs_response, compute_drilldown
from .providers import get_all_symbols

router = APIRouter(prefix="/api/exchange/labs", tags=["labs-v2"])


@router.get("")
async def get_labs(
    mode: str = Query("global", description="global|universe|asset"),
    asset: str = Query(None, description="Symbol (for asset mode)"),
):
    return _get_labs_response(mode, asset)


@router.get("/drilldown")
async def get_drilldown(
    lab: str = Query(..., description="Lab key (e.g. liquidity, regime)"),
    asset: str = Query("BTCUSDT", description="Symbol"),
):
    result = compute_drilldown(lab, asset)
    if result is None:
        return {"ok": False, "error": "Lab not found or no data"}
    return {"ok": True, **result}


@router.get("/symbols")
async def get_symbols():
    return {"symbols": get_all_symbols()}
