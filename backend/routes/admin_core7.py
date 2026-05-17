"""Admin Core7 Mapping Endpoint (PROD-GAP-1.6)

Python port of the F-TRADE-FINAL TypeScript /api/admin/core7/mapping.

Core7 is the 7-dimensional context surface the Tech-Analysis Operator
Console reads to show how each cognition module — TA / Sentiment /
Fractal / On-chain / Exchange / MetaBrain / Trading Runtime — contributes
to the verdict for a given symbol/timeframe.

Returns a flat mapping object plus a per-symbol drill-down so the Admin UI
(Core7 Context tab) can render the matrix.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
from pymongo import MongoClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/core7", tags=["admin-core7"])


def _db():
    client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    return client[os.environ.get("DB_NAME", "fomo_mobile")]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


UNIVERSE = ["BTC", "ETH", "SOL", "DOGE", "LINK", "AVAX", "ARB", "OP", "ADA", "BNB", "XRP"]
TIMEFRAMES = ["1h", "4h", "1d", "7d"]
CORE7_DIMENSIONS = [
    {"key": "ta",          "label": "Tech Analysis",   "source": "native_ta_v1"},
    {"key": "sentiment",   "label": "Sentiment",       "source": "sentiment_runtime"},
    {"key": "fractal",     "label": "Fractal",         "source": "fractal_native_v1"},
    {"key": "onchain",     "label": "On-chain",        "source": "onchain_lite"},
    {"key": "exchange",    "label": "Exchange",        "source": "exchange_forecasts"},
    {"key": "metabrain",   "label": "MetaBrain",       "source": "meta_brain_service"},
    {"key": "runtime",     "label": "Trading Runtime", "source": "trading_runtime_v1"},
]


def _verdict_for(symbol: str) -> Optional[Dict[str, Any]]:
    try:
        from services.trading_runtime import build_verdict
        return build_verdict(symbol)
    except Exception as e:
        logger.debug(f"[core7] verdict failed for {symbol}: {e}")
        return None


def _summarize_module_for_symbol(symbol: str, verdict: Dict[str, Any]) -> Dict[str, Any]:
    """Extract per-dimension status for a single symbol."""
    alignment = verdict.get("alignment", {}) or {}
    active_modules = set(alignment.get("activeModules") or [])
    degraded_modules = set(alignment.get("degradedModules") or [])
    abstained_modules = set(alignment.get("abstainedModules") or [])

    out: Dict[str, Any] = {}
    for dim in CORE7_DIMENSIONS:
        key = dim["key"]
        if key == "metabrain" or key == "runtime":
            # composite layers — mark from verdict-level data
            status = "active" if verdict.get("confidence", 0) > 0 else "idle"
            module_vote = verdict.get("action", "WAIT")
        else:
            module_vote = alignment.get(key, "UNKNOWN")
            if key in degraded_modules:
                status = "degraded"
            elif key in abstained_modules:
                status = "abstained"
            elif key in active_modules:
                status = "active"
            else:
                status = "idle"

        out[key] = {
            "label":  dim["label"],
            "source": dim["source"],
            "vote":   module_vote,
            "status": status,
        }
    return out


@router.get("/mapping")
def get_core7_mapping(
    symbol:    str = Query(None, description="Single-symbol drill-down"),
    timeframe: str = Query("1d", description="Timeframe key (1h/4h/1d/7d)"),
) -> Dict[str, Any]:
    """Core7 mapping object.

    When `symbol` is omitted, returns a matrix across the entire universe.
    When `symbol` is provided, returns a drill-down for that symbol.
    """
    if timeframe not in TIMEFRAMES:
        timeframe = "1d"

    if symbol:
        sym = symbol.upper().strip()
        v = _verdict_for(sym)
        if not v:
            return {
                "ok":        False,
                "symbol":    sym,
                "timeframe": timeframe,
                "degraded":  True,
                "reason":    "verdict_unavailable",
                "asOf":      _now_iso(),
            }
        return {
            "ok":          True,
            "symbol":      sym,
            "timeframe":   timeframe,
            "action":      v.get("action"),
            "confidence":  v.get("confidence"),
            "modules":     _summarize_module_for_symbol(sym, v),
            "alignment":   v.get("alignment", {}),
            "reasons":     v.get("reasons", [])[:5],
            "blockedBy":   v.get("blockedBy", [])[:5],
            "dimensions":  CORE7_DIMENSIONS,
            "asOf":        _now_iso(),
            "source":      "core7_python_v1",
        }

    # Matrix across the whole universe
    matrix: List[Dict[str, Any]] = []
    for sym in UNIVERSE:
        v = _verdict_for(sym)
        if not v:
            matrix.append({"symbol": sym, "degraded": True, "reason": "verdict_unavailable"})
            continue
        matrix.append({
            "symbol":     sym,
            "action":     v.get("action"),
            "confidence": round(float(v.get("confidence", 0.0)), 4),
            "modules":    _summarize_module_for_symbol(sym, v),
        })

    return {
        "ok":         True,
        "timeframe":  timeframe,
        "universe":   UNIVERSE,
        "dimensions": CORE7_DIMENSIONS,
        "matrix":     matrix,
        "count":      len(matrix),
        "asOf":       _now_iso(),
        "source":     "core7_python_v1",
    }


@router.get("/health")
def core7_health() -> Dict[str, Any]:
    return {
        "ok":         True,
        "dimensions": len(CORE7_DIMENSIONS),
        "universe":   len(UNIVERSE),
        "timeframes": TIMEFRAMES,
        "asOf":       _now_iso(),
    }
