"""Trading Cases Active Endpoint (PROD-GAP-1.4)

Replaces `legacy_compat_stub_empty` for /api/trading/cases/active.

An "active case" is a trading-relevant alignment that the runtime currently
tracks. We compose them from:
  1. Open paper-trading positions (paper_positions collection)
  2. Highest-confidence verdicts across the production universe
     where alignment.score ≠ 0 (i.e. directional bias is forming)

This gives the Decisions tab a non-empty, real, production-grade feed.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Query
from pymongo import MongoClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/trading", tags=["trading-cases"])


def _db():
    client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    return client[os.environ.get("DB_NAME", "fomo_mobile")]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


UNIVERSE = ["BTC", "ETH", "SOL", "DOGE", "LINK", "AVAX", "ARB", "OP", "ADA", "BNB", "XRP"]


def _open_positions_as_cases() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    try:
        cur = _db()["paper_positions"].find({"closed": {"$ne": True}}).limit(50)
        for p in cur:
            out.append({
                "id":          str(p.get("_id")),
                "caseType":    "open_position",
                "symbol":      p.get("symbol"),
                "side":        p.get("side", "long").upper(),
                "entry":       p.get("entry"),
                "size":        p.get("size"),
                "openedAt":    (p.get("openedAt").isoformat() if hasattr(p.get("openedAt"), "isoformat") else p.get("openedAt")),
                "status":      "open",
                "unrealizedPnl": p.get("unrealizedPnl"),
                "confidence":  p.get("confidence"),
                "source":      "paper_positions",
            })
    except Exception as e:
        logger.debug(f"[trading_cases] paper_positions miss: {e}")
    return out


def _verdicts_as_cases(min_confidence: float, limit: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    try:
        from services.trading_runtime import build_verdict
    except Exception as e:
        logger.warning(f"[trading_cases] build_verdict import failed: {e}")
        return []

    for sym in UNIVERSE:
        try:
            v = build_verdict(sym)
            conf = float(v.get("confidence", 0.0))
            if conf < min_confidence:
                continue
            alignment = v.get("alignment", {}) or {}
            score = float(alignment.get("score", 0.0) or 0.0)
            if abs(score) < 1e-6 and v.get("action", "WAIT") == "WAIT":
                continue  # genuinely neutral, no directional bias forming
            out.append({
                "id":         f"verdict:{sym}",
                "caseType":   "alignment_forming",
                "symbol":     sym,
                "action":     v.get("action", "WAIT"),
                "confidence": round(conf, 4),
                "alignment":  {
                    "score":         score,
                    "longVotes":     alignment.get("longVotes"),
                    "shortVotes":    alignment.get("shortVotes"),
                    "waitVotes":     alignment.get("waitVotes"),
                    "activeModules": alignment.get("activeModules"),
                },
                "reasons":    v.get("reasons", [])[:3],
                "blockedBy":  v.get("blockedBy", [])[:3],
                "entry":      v.get("entry"),
                "stop":       v.get("stop"),
                "target":     v.get("target"),
                "rr":         v.get("rr"),
                "source":     "trading_runtime_v1",
                "status":     "pending",
            })
            if len(out) >= limit:
                break
        except Exception as e:
            logger.debug(f"[trading_cases] verdict {sym} miss: {e}")
            continue
    return out


@router.get("/cases/active")
def list_active_cases(
    min_confidence: float = Query(0.15, ge=0.0, le=1.0, description="Min verdict confidence to include"),
    limit:          int   = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    """Real active trading cases (replaces legacy_compat_stub_empty).

    Combines open paper positions with currently-forming alignments
    from the runtime. Returns at most `limit` cases, sorted descending
    by confidence so the Decisions tab surfaces the most actionable.
    """
    open_cases = _open_positions_as_cases()
    alignment_cases = _verdicts_as_cases(min_confidence, limit)

    cases = open_cases + alignment_cases
    cases.sort(key=lambda c: -float(c.get("confidence") or 0.0))
    cases = cases[:limit]

    return {
        "ok":     True,
        "path":   "/api/trading/cases/active",
        "data":   cases,
        "items":  cases,  # legacy compat shape
        "count":  len(cases),
        "total":  len(cases),
        "breakdown": {
            "open_positions":    len(open_cases),
            "alignment_forming": len(alignment_cases),
        },
        "asOf":   _now_iso(),
        "source": "trading_runtime_v1+paper_runtime",
    }
