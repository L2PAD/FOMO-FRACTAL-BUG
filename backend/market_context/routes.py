from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/onchain/market", tags=["market-context"])


@router.get("/context")
def market_context(
    chainId: int = Query(1),
    window: str = Query("30d"),
):
    """
    Unified Market Context — Market Brain Data Layer.
    Aggregates CEX + Smart Money + Token + Wallet into 4-layer structure:
      scores   → normalized 0-100
      context  → compressed key data per module
      signals  → structured per module
      drivers  → human-readable reasons
    """
    try:
        from .service import get_market_context
        ctx = get_market_context(chain_id=chainId, window=window)
        return JSONResponse(content={"ok": True, **ctx, "meta": {"chainId": chainId, "window": window}})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
