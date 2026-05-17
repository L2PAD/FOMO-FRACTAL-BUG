from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/engine/v3", tags=["engine-v3"])


@router.get("/context")
def engine_v3_context(
    chainId: int = Query(1),
    window: str = Query("30d"),
):
    """
    Engine V3 — Decision Intelligence Layer.
    Wraps /api/onchain/market/context and adds:
      - Decision classification (STRONG_BUY / BUY / WATCH / REDUCE / AVOID)
      - Confidence engine (HIGH / MODERATE / LOW / INSUFFICIENT)
      - Setup classifier (Accumulation / Distribution / Rotation / etc)
      - Decision Gates (Evidence / Risk / Coverage)
      - Risk engine
      - Evidence engine
      - Diagnostics
    """
    try:
        from .service import get_engine_context
        ctx = get_engine_context(chain_id=chainId, window=window)
        return JSONResponse(content={"ok": True, **ctx})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
