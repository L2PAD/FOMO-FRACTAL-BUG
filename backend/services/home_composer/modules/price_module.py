"""`price` field — top-level numeric."""
from __future__ import annotations

from ..contracts import HomeContext


def assemble(ctx: HomeContext) -> float:
    """
    Resolve the current price for the asset.

    Mirrors the server.py logic exactly:
      1. start from sig.price
      2. if <= 0, use ctx.live_price (CG fallback fetched by composer)
      3. if still <= 0, returns 0 (degenerate honestly)
    """
    sig = ctx.sig or {}
    px = sig.get("price", 0) or 0
    try:
        px = float(px)
    except (TypeError, ValueError):
        px = 0
    if not px or px <= 0:
        if ctx.live_price and ctx.live_price > 0:
            px = float(ctx.live_price)
    return px
