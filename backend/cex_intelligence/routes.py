from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/onchain/cex", tags=["cex-intelligence"])


@router.get("/context")
async def cex_context(
    chainId: int = Query(1),
    window: str = Query("7d"),
):
    """CEX Intelligence — single aggregated endpoint for Exchange Market Intelligence."""
    try:
        from .service import get_cex_context
        ctx = get_cex_context(chain_id=chainId, window=window)
        return JSONResponse(content={"ok": True, **ctx, "meta": {"chainId": chainId, "window": window}})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
