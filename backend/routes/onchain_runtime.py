"""
Per-asset On-chain runtime router (PROD-GAP-3)
==============================================
Exposes `/api/onchain/runtime/{asset}` returning a real per-asset doc built
by `services.onchain_per_asset`.  Mounted BEFORE legacy_compat to take
precedence over the catch-all stub.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pymongo import MongoClient, DESCENDING

router = APIRouter(prefix="/api/onchain", tags=["onchain"])

_client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
_db = _client[os.environ.get("DB_NAME", "fomo_mobile")]


def _project(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


@router.get("/runtime/{asset}")
async def onchain_runtime(asset: str):
    """Per-asset on-chain runtime snapshot (PROD-GAP-3)."""
    sym = (asset or "").upper().strip()
    if not sym:
        raise HTTPException(status_code=400, detail="asset required")

    # 1. Try latest stored per-asset doc
    snap = _db.onchain_metrics.find_one(
        {"symbol": sym}, sort=[("createdAt", DESCENDING)]
    )
    if snap:
        return _project(snap)

    # 2. On-demand build (first request before periodic loop ran)
    try:
        from services.onchain_per_asset import build_metric_for
        doc = build_metric_for(sym)
        # Best-effort persist so subsequent reads are cached.
        try:
            doc_to_save = dict(doc)
            doc_to_save["createdAt"] = datetime.now(timezone.utc)
            doc_to_save["chain"] = "per_asset"
            doc_to_save["provider"] = "cryptorank+hyperliquid+ccxt"
            _db.onchain_metrics.insert_one(doc_to_save)
        except Exception:
            pass
        return doc
    except Exception as e:
        return JSONResponse(
            {
                "ok": False,
                "symbol": sym,
                "error": f"per_asset_build_failed: {type(e).__name__}",
                "degraded": True,
                "source": "onchain_per_asset_v1",
                "asOf": datetime.now(timezone.utc).isoformat(),
            },
            status_code=200,
        )


@router.get("/runtime")
async def onchain_runtime_all():
    """Latest per-asset on-chain snapshot for the production universe."""
    try:
        from core_universe import PRODUCTION_UNIVERSE as _PU_RAW
        PRODUCTION_UNIVERSE = []
        for item in _PU_RAW:
            if isinstance(item, str):
                PRODUCTION_UNIVERSE.append(item.upper())
            elif isinstance(item, dict):
                PRODUCTION_UNIVERSE.append(str(item.get("symbol") or "").upper())
        PRODUCTION_UNIVERSE = [s for s in PRODUCTION_UNIVERSE if s]
        if not PRODUCTION_UNIVERSE:
            raise ValueError("empty")
    except Exception:
        PRODUCTION_UNIVERSE = [
            "BTC", "ETH", "SOL", "DOGE", "LINK", "AVAX",
            "ARB", "OP", "ADA", "BNB", "XRP",
        ]
    out = []
    for sym in PRODUCTION_UNIVERSE:
        snap = _db.onchain_metrics.find_one(
            {"symbol": sym}, sort=[("createdAt", DESCENDING)]
        )
        if snap:
            out.append(_project(snap))
        else:
            try:
                from services.onchain_per_asset import build_metric_for
                out.append(build_metric_for(sym))
            except Exception as e:
                out.append({"symbol": sym, "ok": False, "error": str(e)[:120]})
    return {
        "ok": True,
        "count": len(out),
        "assets": out,
        "asOf": datetime.now(timezone.utc).isoformat(),
        "source": "onchain_per_asset_v1",
    }
