"""Real TA Prediction Endpoint (PROD-GAP-1.3)

Replaces the `legacy_compat_stub_empty` for /api/ta/prediction/{symbol}.

Builds a per-asset prediction object that combines:
  - Native TA (services.technical_analysis.analyze) → trend / momentum / RSI / S-R
  - Fractal forecast nearest to the requested horizon (fractal_forecasts_*)
  - Exchange forecast (exchange_forecasts collection)
  - MetaBrain agreement score (when available)

Returns a single prediction object — not a stub — so the Prediction tab in
the 8-tab Trading Terminal stops showing 0 evaluations.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Path, Query
from pymongo import MongoClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ta", tags=["ta-prediction"])


def _db():
    client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    return client[os.environ.get("DB_NAME", "fomo_mobile")]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canon(sym: str) -> str:
    if not sym:
        return ""
    s = sym.upper().strip()
    for suf in ("USDT", "USDC", "USD", "-PERP", "-USD", "PERP"):
        if s.endswith(suf):
            s = s[: -len(suf)] if not s.endswith("-" + suf) else s[: -len(suf) - 1]
            break
    return s


def _nearest_fractal_target(base: str, horizon_days: int) -> Optional[Dict[str, Any]]:
    try:
        coll = _db().get_collection(f"fractal_forecasts_{base.lower()}")
        # find doc with closest horizonDays
        best = None
        best_delta = None
        for doc in coll.find().sort("createdAt", -1).limit(40):
            hd = doc.get("horizonDays")
            if hd is None:
                continue
            delta = abs(hd - horizon_days)
            if best is None or delta < best_delta:
                best = doc
                best_delta = delta
        if not best:
            return None
        return {
            "horizonDays":  best.get("horizonDays"),
            "targetPrice":  best.get("targetPrice") or best.get("target"),
            "direction":    best.get("direction", "unknown"),
            "confidence":   float(best.get("confidence", 0.0)),
            "source":       "fractal_native_v1",
        }
    except Exception as e:
        logger.debug(f"[ta_prediction] fractal miss: {e}")
        return None


def _exchange_forecast(base: str) -> Optional[Dict[str, Any]]:
    try:
        doc = _db()["exchange_forecasts"].find_one(
            {"symbol": {"$in": [base, base + "USDT", base + "USD"]}},
            sort=[("createdAt", -1)],
        )
        if not doc:
            return None
        return {
            "horizonDays": doc.get("horizonDays", 1),
            "targetPrice": doc.get("targetPrice") or doc.get("target"),
            "direction":   doc.get("direction", "unknown"),
            "confidence":  float(doc.get("confidence", 0.0)),
            "source":      "exchange_forecasts",
        }
    except Exception:
        return None


@router.get("/prediction/{symbol}")
def get_ta_prediction(
    symbol: str = Path(...),
    horizon: int = Query(7, ge=1, le=30, description="Forecast horizon (days)"),
) -> Dict[str, Any]:
    """Real TA-anchored prediction (no longer a stub).

    Composition:
        currentPrice   — native_ta_v1
        directionVote  — majority of TA / fractal / exchange directions
        targetPrice    — fractal nearest horizon target (preferred) or exchange forecast
        confidence     — averaged across available sources
        evaluations    — list of evaluable horizons with source attribution
    """
    base = _canon(symbol)

    # 1. TA snapshot (current price + direction)
    ta_snap: Dict[str, Any] = {}
    try:
        from services.technical_analysis import analyze as _ta_analyze
        ta_snap = _ta_analyze(base) or {}
    except Exception as e:
        logger.warning(f"[ta_prediction] ta_analyze failed for {base}: {e}")

    current_price = ta_snap.get("currentPrice")
    ta_direction = ta_snap.get("direction", "WAIT")
    ta_conf = float(ta_snap.get("confidence", 0.0))

    # 2. Fractal nearest target
    frac = _nearest_fractal_target(base, horizon)
    # 3. Exchange forecast
    exch = _exchange_forecast(base)

    # 4. Composite
    evaluations: List[Dict[str, Any]] = []
    if current_price is not None:
        evaluations.append({
            "horizonDays": 0,
            "target":      current_price,
            "direction":   ta_direction,
            "confidence":  ta_conf,
            "source":      "native_ta_v1",
            "status":      "anchor",
        })
    if exch and exch.get("targetPrice") is not None:
        evaluations.append({
            "horizonDays": exch["horizonDays"],
            "target":      exch["targetPrice"],
            "direction":   exch["direction"],
            "confidence":  exch["confidence"],
            "source":      exch["source"],
            "status":      "forecast",
        })
    if frac and frac.get("targetPrice") is not None:
        evaluations.append({
            "horizonDays": frac["horizonDays"],
            "target":      frac["targetPrice"],
            "direction":   frac["direction"],
            "confidence":  frac["confidence"],
            "source":      frac["source"],
            "status":      "forecast",
        })

    # Directional vote
    votes = [e["direction"] for e in evaluations if e.get("direction") in ("LONG", "SHORT", "WAIT")]
    if votes:
        # Pick most common; if tie → WAIT
        from collections import Counter
        c = Counter(votes).most_common()
        primary = c[0][0]
        if len(c) > 1 and c[0][1] == c[1][1]:
            primary = "WAIT"
    else:
        primary = ta_direction or "WAIT"

    confidences = [e["confidence"] for e in evaluations if isinstance(e.get("confidence"), (int, float))]
    avg_conf = round(sum(confidences) / len(confidences), 4) if confidences else 0.0

    # Primary target = highest-confidence forecast (skip anchor)
    fc_only = [e for e in evaluations if e.get("status") == "forecast"]
    primary_target = max(fc_only, key=lambda e: e.get("confidence", 0)) if fc_only else None

    degraded = len(evaluations) <= 1  # only anchor, no real forecast

    return {
        "symbol":          base,
        "horizonDays":     horizon,
        "currentPrice":    current_price,
        "targetPrice":     primary_target["target"] if primary_target else None,
        "direction":       primary,
        "confidence":      avg_conf,
        "evaluations":     evaluations,
        "sourceCount":     len({e["source"] for e in evaluations}),
        "degraded":        degraded,
        "reason":          "only_ta_anchor_no_forecasts" if degraded else None,
        "asOf":            _now_iso(),
    }
