"""
On-chain Per-Asset Intelligence (PROD-GAP-3)
=============================================
Builds **per-symbol** on-chain-flavoured metrics for the production universe
(11 assets) using already-ingested primary sources:

  • CryptoRank (raw_funding · venue=cryptorank … with price_usd, market_cap, volume_24h)
  • Hyperliquid (raw_funding · venue=hyperliquid … fundingRate / markPrice / indexPrice)
  • CCXT OHLC (market_data.ohlc_provider for 7d / 30d momentum)

Persists to MongoDB `onchain_metrics` keyed by `symbol` (in addition to the
existing chain-level docs).  `trading_runtime._fetch_onchain` reads
symbol-first, chain-fallback.

DIRECTION (honest, deterministic):
  • Δ7d  > +3%  → +1 bull
  • Δ7d  < -3%  → +1 bear
  • Δ30d > +10% → +1 bull
  • Δ30d < -10% → +1 bear
  • fundingRate < 0 (negative funding = shorts pay longs, bullish skew)  → +1 bull
  • fundingRate > +0.0005 (overly positive = crowd-long, mean-revert risk) → +1 bear
  • volume24h / market_cap ratio > 10%        → +1 bull (high engagement)
  • volume24h / market_cap ratio < 2%         → 0    (low engagement)

We never fabricate data: if a metric is missing the signal abstains rather
than coercing a fake vote.
"""
from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pymongo import MongoClient, DESCENDING

# Avoid circular imports — core_universe is plain module.
# PRODUCTION_UNIVERSE is a tuple of dicts → extract symbol strings.
try:
    from core_universe import PRODUCTION_UNIVERSE as _PU_RAW
    _PU = []
    for item in _PU_RAW:
        if isinstance(item, str):
            _PU.append(item.upper())
        elif isinstance(item, dict):
            _PU.append(str(item.get("symbol") or "").upper())
    PRODUCTION_UNIVERSE = [s for s in _PU if s]
    if not PRODUCTION_UNIVERSE:
        raise ValueError("empty universe after extraction")
except Exception:
    PRODUCTION_UNIVERSE = [
        "BTC", "ETH", "SOL", "DOGE", "LINK", "AVAX",
        "ARB", "OP", "ADA", "BNB", "XRP",
    ]

_DEFAULT_INTERVAL_SEC = 10 * 60  # 10 minutes

_mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
_db_name = os.environ.get("DB_NAME", "fomo_mobile")
_client = MongoClient(_mongo_url)
_db = _client[_db_name]


def _interval() -> int:
    try:
        return max(60, int(os.environ.get("ONCHAIN_PER_ASSET_INTERVAL_SEC", _DEFAULT_INTERVAL_SEC)))
    except Exception:
        return _DEFAULT_INTERVAL_SEC


# ─────────────────────────────────────────────────────────────────────────────
# Source pulls
# ─────────────────────────────────────────────────────────────────────────────
def _pull_cryptorank(symbol: str) -> Dict[str, Any]:
    """Latest CryptoRank document for the symbol (price / mcap / volume)."""
    try:
        doc = _db.raw_funding.find_one(
            {"source": "cryptorank", "symbol": symbol.upper()},
            sort=[("fetched_at", DESCENDING), ("_id", DESCENDING)],
        )
        if not doc:
            return {}
        return {
            "price_usd":    doc.get("price_usd"),
            "market_cap":   doc.get("market_cap"),
            "volume_24h":   doc.get("volume_24h"),
            "category":     doc.get("category"),
            "fetched_at":   doc.get("fetched_at"),
        }
    except Exception:
        return {}


def _pull_hyperliquid(symbol: str) -> Dict[str, Any]:
    """Latest Hyperliquid funding/mark for the symbol."""
    try:
        doc = _db.raw_funding.find_one(
            {"venue": "hyperliquid", "symbol": symbol.upper()},
            sort=[("ingestedAt", DESCENDING), ("_id", DESCENDING)],
        )
        if not doc:
            return {}
        return {
            "fundingRate": doc.get("fundingRate"),
            "markPrice":   doc.get("markPrice"),
            "indexPrice":  doc.get("indexPrice"),
            "ingestedAt":  doc.get("ingestedAt"),
        }
    except Exception:
        return {}


def _pull_momentum(symbol: str) -> Dict[str, Optional[float]]:
    """
    Derive 7d / 30d % change using stored ta_snapshots history OR CCXT OHLC fallback.
    Returns nulls if neither path is available — we never fabricate.
    """
    out = {"change7d": None, "change30d": None, "close_now": None}
    try:
        # Try CCXT OHLC daily provider (already cached server-side).
        from market_data.ohlc_provider import get_daily_ohlc
        ohlc = get_daily_ohlc(symbol.upper(), days=35)
        if ohlc and len(ohlc) >= 8:
            closes = [c.get("close") for c in ohlc if c.get("close")]
            if len(closes) >= 8:
                now_c = float(closes[-1])
                c7    = float(closes[-8])
                out["change7d"] = round(((now_c - c7) / c7) * 100, 3)
                out["close_now"] = now_c
            if len(closes) >= 31:
                c30 = float(closes[-31])
                out["change30d"] = round(((now_c - c30) / c30) * 100, 3)
        return out
    except Exception:
        return out


# ─────────────────────────────────────────────────────────────────────────────
# Classification
# ─────────────────────────────────────────────────────────────────────────────
def _classify_per_asset(metrics: Dict[str, Any]) -> Dict[str, Any]:
    change7d  = metrics.get("change7d")
    change30d = metrics.get("change30d")
    funding   = metrics.get("fundingRate")
    mcap      = metrics.get("market_cap") or 0.0
    vol       = metrics.get("volume_24h") or 0.0

    bull = 0
    bear = 0
    notes: List[str] = []

    if change7d is not None:
        if change7d > 3:
            bull += 1; notes.append(f"7d +{change7d:.1f}% → bullish momentum")
        elif change7d < -3:
            bear += 1; notes.append(f"7d {change7d:.1f}% → bearish momentum")
        else:
            notes.append(f"7d {change7d:+.1f}% → range")

    if change30d is not None:
        if change30d > 10:
            bull += 1; notes.append(f"30d +{change30d:.1f}% → macro uptrend")
        elif change30d < -10:
            bear += 1; notes.append(f"30d {change30d:.1f}% → macro downtrend")
        else:
            notes.append(f"30d {change30d:+.1f}% → consolidating")

    if funding is not None:
        try:
            fnum = float(funding)
            if fnum < 0:
                bull += 1; notes.append(f"funding {fnum:.5f} → shorts paying (bullish skew)")
            elif fnum > 0.0005:
                bear += 1; notes.append(f"funding {fnum:.5f} → crowd long (mean-revert)")
            else:
                notes.append(f"funding {fnum:.5f} → balanced")
        except Exception:
            pass

    if mcap and vol:
        ratio = float(vol) / float(mcap)
        if ratio > 0.10:
            bull += 1; notes.append(f"vol/mcap {ratio*100:.1f}% → high engagement")
        elif ratio < 0.02:
            notes.append(f"vol/mcap {ratio*100:.1f}% → low engagement")
        else:
            notes.append(f"vol/mcap {ratio*100:.1f}% → normal engagement")

    total = bull + bear
    if total == 0:
        direction = "NEUTRAL"
        confidence = 0.10
    elif bull >= 2 and bull > bear:
        direction = "LONG"
        confidence = min(0.80, (bull / max(total, 1)) * 0.65)
    elif bear >= 2 and bear > bull:
        direction = "SHORT"
        confidence = min(0.80, (bear / max(total, 1)) * 0.65)
    else:
        direction = "NEUTRAL"
        confidence = 0.20

    return {
        "direction":   direction,
        "confidence":  round(confidence, 3),
        "bullSignals": bull,
        "bearSignals": bear,
        "signals":     notes,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────
def build_metric_for(symbol: str) -> Dict[str, Any]:
    """Build a single per-asset metric document (read-only, no DB write)."""
    sym = symbol.upper()
    cr = _pull_cryptorank(sym)
    hl = _pull_hyperliquid(sym)
    mo = _pull_momentum(sym)

    metrics: Dict[str, Any] = {
        "symbol":      sym,
        "price_usd":   cr.get("price_usd") or mo.get("close_now"),
        "market_cap":  cr.get("market_cap"),
        "volume_24h":  cr.get("volume_24h"),
        "fundingRate": hl.get("fundingRate"),
        "markPrice":   hl.get("markPrice"),
        "indexPrice":  hl.get("indexPrice"),
        "change7d":    mo.get("change7d"),
        "change30d":   mo.get("change30d"),
    }

    classification = _classify_per_asset(metrics)

    sources_used: List[str] = []
    if cr: sources_used.append("cryptorank")
    if hl: sources_used.append("hyperliquid")
    if mo.get("change7d") is not None: sources_used.append("ccxt_ohlc")

    return {
        **metrics,
        **classification,
        "sources":   sources_used,
        "degraded":  len(sources_used) < 2,
        "source":    "onchain_per_asset_v1",
        "asOf":      datetime.now(timezone.utc).isoformat(),
    }


async def run_once() -> Dict[str, Any]:
    """Snapshot all 11 universe assets and persist."""
    now = datetime.now(timezone.utc)
    started = time.time()
    inserted = 0
    errors: List[str] = []
    for sym in PRODUCTION_UNIVERSE:
        try:
            doc = build_metric_for(sym)
            doc.update({
                "createdAt":     now,
                "createdBucket": now.strftime("%Y-%m-%dT%H"),
                "chain":         "per_asset",
                "provider":      "cryptorank+hyperliquid+ccxt",
            })
            _db.onchain_metrics.insert_one(doc)
            _db.onchain_events.insert_one({
                "symbol":     sym,
                "createdAt":  now,
                "type":       "metric_snapshot_per_asset",
                "direction":  doc.get("direction"),
                "confidence": doc.get("confidence"),
                "source":     "onchain_per_asset_v1",
            })
            inserted += 1
        except Exception as exc:
            errors.append(f"{sym}: {exc!r}")
    elapsed = round(time.time() - started, 2)
    print(f"[OnchainPerAsset] {now.isoformat()} inserted={inserted}/{len(PRODUCTION_UNIVERSE)} errors={len(errors)} elapsed={elapsed}s")
    return {"ok": not errors, "inserted": inserted, "errors": errors, "ts": now.isoformat()}


async def _loop():
    interval = _interval()
    print(f"[OnchainPerAsset] starting loop interval={interval}s assets={PRODUCTION_UNIVERSE}")
    await asyncio.sleep(20)  # give backend time to stabilise
    while True:
        try:
            await run_once()
        except Exception as exc:
            print(f"[OnchainPerAsset] loop error: {exc!r}")
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            print("[OnchainPerAsset] loop cancelled")
            raise


def start_loop_if_enabled() -> Dict[str, Any]:
    flag = os.environ.get("ONCHAIN_PER_ASSET_ENABLED", "true").strip().lower()
    if flag in ("0", "false", "no", "off"):
        print("[OnchainPerAsset] disabled by flag")
        return {"started": False, "reason": "disabled_by_flag"}
    asyncio.create_task(_loop())
    return {"started": True, "interval_sec": _interval()}


# ─────────────────────────────────────────────────────────────────────────────
# Best-effort indexes
# ─────────────────────────────────────────────────────────────────────────────
try:
    _db.onchain_metrics.create_index([("symbol", 1), ("createdAt", DESCENDING)])
    _db.onchain_events.create_index([("symbol", 1), ("createdAt", DESCENDING)])
except Exception:
    pass
