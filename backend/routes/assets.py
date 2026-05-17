"""
Asset Logos Router.

Endpoints:
    GET /api/assets/logo/{symbol}?size=thumb|small|large
        → 302 redirect to the image URL (works everywhere)

    GET /api/assets/logos?symbols=BTC,ETH,SOL
        → {"ok": true, "logos": {"BTC": {url, thumb, small, large, name, coingecko_id}, ...}}

    POST /api/assets/logos/backfill (admin)
        → Force-refresh from CoinGecko (top 500 coins).

    GET /api/assets/logos/stats (admin)
        → {"total": N, "updated_at_median": ...}
"""
from __future__ import annotations

import logging
import os
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse

from services.assets import asset_logos
from services.assets.logos import resolve_source_logo, SOURCE_LOGOS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/assets", tags=["assets"])

DEFAULT_FALLBACK = (
    "https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/"
    "svg/color/generic.svg"
)


def _is_admin(request: Request) -> bool:
    auth = request.headers.get("authorization", "") or request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return False
    token = auth.split(" ", 1)[1].strip()
    if not token:
        return False
    try:
        import jwt
        secret = os.environ.get("ADMIN_JWT_SECRET", "") or os.environ.get("JWT_ACCESS_SECRET", "")
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload.get("role") in ("superadmin", "admin")
    except Exception:
        return False


# ── Public ───────────────────────────────────────────────────────────
@router.get("/source/{slug}")
async def source_logo(slug: str):
    """Resolve a news source / platform / exchange logo → redirect.

    Examples:
        /api/assets/source/coindesk
        /api/assets/source/twitter
        /api/assets/source/binance
        /api/assets/source/https://www.coindesk.com/…   (accepts full URL too)
    """
    meta = resolve_source_logo(slug)
    return RedirectResponse(meta["url"], status_code=302)


@router.get("/sources")
async def source_logos_bulk(slugs: str = ""):
    """Bulk: /api/assets/sources?slugs=coindesk,twitter,binance."""
    items = [s.strip() for s in slugs.split(",") if s.strip()]
    if not items:
        return {"ok": True, "sources": {s: {"name": v["name"], "url": v["url"]} for s, v in SOURCE_LOGOS.items()}}
    return {"ok": True, "sources": {s: resolve_source_logo(s) for s in items}}


@router.get("/logo/{symbol}")
async def asset_logo(symbol: str, size: str = "small"):
    """Redirect to the logo image URL. Use in <img src=.../> directly."""
    logo = await asset_logos.get_one(symbol)
    if not logo:
        return RedirectResponse(DEFAULT_FALLBACK, status_code=302)
    key = {"thumb": "thumb", "small": "small", "large": "large"}.get(size, "small")
    url = logo.get(key) or logo.get("url") or DEFAULT_FALLBACK
    return RedirectResponse(url, status_code=302)


@router.get("/logos")
async def asset_logos_bulk(symbols: str = ""):
    """Bulk lookup. Example: /api/assets/logos?symbols=BTC,ETH,SOL."""
    syms = [s.strip() for s in symbols.split(",") if s.strip()]
    if not syms:
        return {"ok": True, "logos": {}}
    logos = await asset_logos.get_many(syms)
    return {"ok": True, "logos": logos}


# ── Admin ────────────────────────────────────────────────────────────
@router.post("/logos/backfill")
async def asset_logos_backfill(request: Request, pages: int = 2, per_page: int = 250):
    if not _is_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})
    if pages < 1 or pages > 5:
        return JSONResponse(status_code=400, content={"ok": False, "error": "pages must be 1..5"})
    result = await asset_logos.backfill_from_coingecko(pages=pages, per_page=per_page)
    return result


@router.get("/logos/stats")
async def asset_logos_stats(request: Request):
    if not _is_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})
    db = asset_logos._db()
    total = await db["asset_logos"].count_documents({})
    sample = await db["asset_logos"].find_one({}, {"_id": 0, "symbol": 1, "updated_at": 1}, sort=[("updated_at", -1)])
    return {"ok": True, "total": total, "latest": sample}
