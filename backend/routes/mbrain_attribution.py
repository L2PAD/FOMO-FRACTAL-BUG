"""
mbrain_positions.attribution
============================

Realized Attribution Layer — paper-snapshot of Meta-Brain's net economic
effect on hypothetical PnL.

Returns answers to three questions per stage (RAW / META / FINAL):

  1. avoided_loss      — how much PnL would have been LOST if we had
                         executed RAW directions on positions where
                         FINAL converted them to HOLD?
                         (positive = Meta-Brain saved you that much)

  2. missed_gain       — how much PnL would have been EARNED if we had
                         executed RAW directions on positions where
                         FINAL converted them to HOLD?
                         (positive = Meta-Brain cost you that much)

  3. net_alpha         — avoided_loss − missed_gain
                         positive = Meta-Brain net-positive
                         negative = Meta-Brain net-negative

Plus per-stage:
  • direction_accuracy = % of active positions where direction == sign(price_move)
  • magnitude_accuracy = mean |raw_expectedReturn − abs(price_move)|
  • sharpe_proxy

Input source: same `mbrain_integrity_outcomes` collection.
For PENDING records: uses CURRENT spot vs entry_price (paper-snapshot).
For RESOLVED records: uses captured close_price + realized_return.

NO ORDERS. NO EXECUTION. NO COMMITS. NO trading_os WRITES.
Read-only HTTP-only proxy to side-car for current price fetches.
"""
from __future__ import annotations

import os
import statistics
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Query
from pymongo import MongoClient

UPSTREAM = os.environ.get(
    "TRADING_TERMINAL_UPSTREAM", "http://localhost:8002",
).rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

router = APIRouter(prefix="/api/mbrain/positions",
                   tags=["mbrain-positions-attribution"])


def _fetch_current_price(symbol: str, client: httpx.Client,
                         timeout: float = 15.0) -> Optional[float]:
    asset = symbol.replace("USDT", "") if symbol.endswith("USDT") else symbol
    try:
        r = client.get(
            f"{UPSTREAM}/api/market/chart/price-vs-expectation-v4",
            params={"asset": asset, "range": "24h", "horizon": "1D"},
            timeout=timeout,
        )
        if r.status_code != 200:
            return None
        body = r.json()
        pts = body.get("price") or []
        if not pts:
            return None
        return float(pts[-1].get("price"))
    except Exception:
        return None


def _pnl(direction: str, entry: float, close: float) -> float:
    if not entry or entry <= 0:
        return 0.0
    move = (close - entry) / entry
    if direction == "LONG":
        return move
    if direction == "SHORT":
        return -move
    return 0.0


def _direction_accuracy(positions: List[Dict[str, Any]]) -> Optional[float]:
    """Of active (non-HOLD) positions, what fraction had direction
    matching the actual price move sign?"""
    actives = [p for p in positions if p.get("direction") in ("LONG", "SHORT")
               and p.get("price_move_pct") is not None]
    if not actives:
        return None
    correct = 0
    for p in actives:
        move = p["price_move_pct"]
        if (p["direction"] == "LONG" and move > 0) or (
                p["direction"] == "SHORT" and move < 0):
            correct += 1
    return correct / len(actives)


def _sharpe(active_pnls: List[float]) -> Optional[float]:
    if len(active_pnls) < 4:
        return None
    m = sum(active_pnls) / len(active_pnls)
    s = statistics.pstdev(active_pnls)
    if s <= 0:
        return None
    return m / s


@router.get("/attribution")
async def attribution(include_resolved: bool = Query(True),
                      limit: int = Query(500, ge=1, le=2000)):
    cli = MongoClient(MONGO_URL)
    db = cli[DB_NAME]
    q: Dict[str, Any] = {} if include_resolved else {"status": "PENDING"}
    rows = list(db.mbrain_integrity_outcomes.find(q, {"_id": 0}).limit(limit))
    if not rows:
        return {"ok": True, "n": 0, "note": "no outcome records",
                "meta": {"include_resolved": include_resolved}}

    symbols = sorted({r.get("symbol") for r in rows if r.get("symbol")})
    # Reuse the parallel fetcher from mbrain_positions.
    from .mbrain_positions import _fetch_prices_parallel  # noqa: WPS433
    price_cache: Dict[str, Optional[float]] = await _fetch_prices_parallel(
        symbols, timeout=5.0)

    raw_pos: List[Dict[str, Any]] = []
    final_pos: List[Dict[str, Any]] = []

    for r in rows:
        sym = r.get("symbol")
        entry = r.get("entry_price")
        # Prefer the stored close_price (RESOLVED records) over current spot
        close = r.get("close_price") if r.get("status") == "RESOLVED" else price_cache.get(sym)
        raw_dir = r.get("raw_direction") or "HOLD"
        final_dir = r.get("final_direction") or "HOLD"
        if entry is None or close is None:
            continue
        move = (close - entry) / entry
        raw_pos.append({
            "symbol": sym, "horizon": r.get("horizon"), "ts": r.get("ts_iso"),
            "direction": raw_dir, "entry": entry, "close": close,
            "price_move_pct": move,
            "pnl": _pnl(raw_dir, entry, close),
            "outcome_class": r.get("outcome_class"),
            "raw_expected_return": r.get("raw_expected_return"),
            "status": r.get("status"),
        })
        final_pos.append({
            "symbol": sym, "horizon": r.get("horizon"), "ts": r.get("ts_iso"),
            "direction": final_dir, "entry": entry, "close": close,
            "price_move_pct": move,
            "pnl": _pnl(final_dir, entry, close),
            "outcome_class": r.get("outcome_class"),
            "raw_expected_return": r.get("raw_expected_return"),
            "status": r.get("status"),
        })

    # Avoided loss / missed gain — only over rows where FINAL = HOLD and RAW != HOLD
    avoided_loss = 0.0   # positive number = Meta saved you that much
    missed_gain = 0.0    # positive number = Meta cost you that much
    n_killed = 0
    n_killed_loss_avoided = 0
    n_killed_gain_missed = 0
    for raw, fin in zip(raw_pos, final_pos):
        if raw["direction"] in ("LONG", "SHORT") and fin["direction"] == "HOLD":
            n_killed += 1
            if raw["pnl"] < 0:
                avoided_loss += abs(raw["pnl"])
                n_killed_loss_avoided += 1
            elif raw["pnl"] > 0:
                missed_gain += raw["pnl"]
                n_killed_gain_missed += 1

    net_alpha = avoided_loss - missed_gain

    # Per-side breakdown — what happened to suppressed SHORTs vs LONGs
    suppressed_shorts = [r for r, f in zip(raw_pos, final_pos)
                         if r["direction"] == "SHORT" and f["direction"] == "HOLD"]
    suppressed_longs = [r for r, f in zip(raw_pos, final_pos)
                        if r["direction"] == "LONG" and f["direction"] == "HOLD"]

    def _side_summary(rows: List[Dict[str, Any]], label: str) -> Dict[str, Any]:
        if not rows:
            return {"label": label, "n": 0,
                    "would_have_pnl_total": 0.0,
                    "would_have_pnl_mean": None,
                    "win_rate_if_executed": None}
        pnls = [r["pnl"] for r in rows]
        wins = sum(1 for p in pnls if p > 0)
        return {
            "label": label,
            "n": len(rows),
            "would_have_pnl_total": round(sum(pnls), 6),
            "would_have_pnl_mean": round(sum(pnls) / len(pnls), 6),
            "win_rate_if_executed": round(wins / len(pnls), 4),
        }

    raw_active_pnls = [p["pnl"] for p in raw_pos
                       if p["direction"] in ("LONG", "SHORT")]
    final_active_pnls = [p["pnl"] for p in final_pos
                         if p["direction"] in ("LONG", "SHORT")]

    return {
        "ok": True,
        "n": len(rows),
        "n_priced": len(raw_pos),
        "n_resolved": sum(1 for r in rows if r.get("status") == "RESOLVED"),
        "n_pending": sum(1 for r in rows if r.get("status") == "PENDING"),
        "headline": {
            "avoided_loss_pct": round(avoided_loss * 100, 4),
            "missed_gain_pct": round(missed_gain * 100, 4),
            "net_alpha_pct": round(net_alpha * 100, 4),
            "n_killed_to_hold": n_killed,
            "n_killed_loss_avoided": n_killed_loss_avoided,
            "n_killed_gain_missed": n_killed_gain_missed,
            "verdict": (
                "META_NET_POSITIVE" if net_alpha > 0
                else "META_NET_NEGATIVE" if net_alpha < 0
                else "NEUTRAL"
            ),
        },
        "suppressed_shorts": _side_summary(suppressed_shorts,
                                            "Suppressed SHORTs"),
        "suppressed_longs": _side_summary(suppressed_longs,
                                           "Suppressed LONGs"),
        "stage_attribution": {
            "raw": {
                "active_pnl_total": round(sum(raw_active_pnls), 6) if raw_active_pnls else 0,
                "direction_accuracy": _direction_accuracy(raw_pos),
                "sharpe_proxy": _sharpe(raw_active_pnls),
                "n_active": len(raw_active_pnls),
            },
            "final": {
                "active_pnl_total": round(sum(final_active_pnls), 6) if final_active_pnls else 0,
                "direction_accuracy": _direction_accuracy(final_pos),
                "sharpe_proxy": _sharpe(final_active_pnls),
                "n_active": len(final_active_pnls),
            },
        },
        "constraints": [
            "paper_only", "read_only", "http_only_to_sidecar",
            "no_orders", "no_execution", "no_commits",
            "no_trading_os_writes", "no_production_fusion_influence",
        ],
        "meta": {
            "include_resolved": include_resolved,
            "data_window": ("realized" if any(r.get("status") == "RESOLVED" for r in rows)
                            else "paper_24h"),
        },
    }
