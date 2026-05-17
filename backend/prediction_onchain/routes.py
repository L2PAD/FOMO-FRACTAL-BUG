"""
Prediction On-chain Market Routes
==================================
GET /api/prediction/onchain-market — full on-chain market prediction state
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/prediction", tags=["prediction-onchain"])


@router.get("/onchain-market")
def onchain_market():
    """Full on-chain market prediction — aggregated from snapshot + flow data."""
    try:
        from .service import get_onchain_market_prediction
        data = get_onchain_market_prediction()
        return JSONResponse(content={"ok": True, **data})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
