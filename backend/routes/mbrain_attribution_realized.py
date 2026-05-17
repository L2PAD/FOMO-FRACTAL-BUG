"""
mbrain_attribution.realized
===========================

Realized Attribution Layer — economic effect of Meta-Brain on
RESOLVED forward-tracking outcomes.

Difference vs `mbrain_attribution.attribution`:
  • the original endpoint computes paper-snapshot PnL using *current*
    spot for both PENDING and RESOLVED records — useful for "live"
    explainability but mixes horizons;
  • this endpoint reads ONLY status=RESOLVED rows, where:
      - close_price was captured at horizon-end
      - realized_return / realized_return_raw / attribution_class /
        realized_direction_correct were stored at resolve time
    Therefore the numbers it returns are the **actual** economic
    effect of Meta-Brain over the matured horizons.

Per-stage metrics (RAW / META / FINAL):
  • realized_pnl_total         — sum of per-row realized return
  • realized_pnl_mean          — average across active subset
  • directional_accuracy       — % of rows where direction matches sign(price_move)
  • avg_abs_move               — magnitude quality (mean |price_move|)
  • exposure_efficiency        — pnl / exposure_count
  • sharpe_proxy               — pnl_mean / pnl_stdev (no annualization)

Headline:
  • avoided_loss               — fraction sum on rows where
                                 RAW directional → FINAL HOLD AND raw_pnl<0
  • missed_gain                — same but raw_pnl>0
  • net_alpha                  — avoided_loss − missed_gain
  • verdict                    — META_NET_POSITIVE / META_NET_NEGATIVE / NEUTRAL
  • attribution_breakdown      — counts for each attribution_class

Per-horizon breakdown (1D / 7D / 30D):
  • avoided_loss / missed_gain / net_alpha / verdict per horizon
  • directional_accuracy raw vs final per horizon
  • exposure suppression rate per horizon

NO ORDERS. NO EXECUTION. NO COMMITS. NO trading_os WRITES.
Read-only over `mbrain_integrity_outcomes` (FOMO mongo, status=RESOLVED only).
"""
from __future__ import annotations

import os
import statistics
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
from pymongo import MongoClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

router = APIRouter(prefix="/api/mbrain/attribution",
                   tags=["mbrain-attribution-realized"])


def _pnl_for(direction: str, move: float) -> float:
    if direction == "LONG":
        return move
    if direction == "SHORT":
        return -move
    return 0.0


def _max_drawdown(returns: List[float]) -> Optional[float]:
    """Max peak-to-trough drawdown over a cumulative return path.

    Returns absolute drawdown magnitude (positive number, e.g. 0.18 → -18%
    drawdown). None if the path is empty or has no decline.
    """
    if not returns:
        return None
    cum = 0.0
    peak = 0.0
    max_dd = 0.0
    for r in returns:
        cum += r
        if cum > peak:
            peak = cum
        dd = peak - cum
        if dd > max_dd:
            max_dd = dd
    return round(max_dd, 6)


def _sortino(returns: List[float]) -> Optional[float]:
    """Sortino ratio proxy — mean / downside_stdev. NOT annualized.
    Uses negative-only deviations as the volatility denominator."""
    if not returns or len(returns) < 4:
        return None
    m = sum(returns) / len(returns)
    downside = [r for r in returns if r < 0]
    if not downside:
        return None  # no downside → undefined
    if len(downside) < 2:
        return None
    ds = statistics.pstdev(downside)
    if ds <= 0:
        return None
    return round(m / ds, 4)


def _calmar(returns: List[float]) -> Optional[float]:
    """Calmar ratio proxy — total_return / max_drawdown. NOT annualized.
    Useful as a path-quality sanity check across stages."""
    if not returns:
        return None
    total = sum(returns)
    mdd = _max_drawdown(returns)
    if mdd is None or mdd <= 0:
        return None
    return round(total / mdd, 4)


def _stage_summary(rows: List[Dict[str, Any]],
                    direction_field: str,
                    label: str) -> Dict[str, Any]:
    if not rows:
        return {"label": label, "n": 0, "n_active": 0,
                "realized_pnl_total": 0.0,
                "realized_pnl_mean": None,
                "directional_accuracy": None,
                "avg_abs_move": None,
                "exposure_efficiency": None,
                "sharpe_proxy": None,
                "sortino_proxy": None,
                "calmar_proxy": None,
                "max_drawdown_pct": None,
                "exposure_adjusted_utility": None,
                "exposure": {"long": 0, "short": 0, "hold": 0}}

    active_pnls: List[float] = []
    correct = 0
    n_dir = 0
    abs_moves: List[float] = []
    long_n = short_n = hold_n = 0
    for r in rows:
        dirn = r.get(direction_field) or "HOLD"
        move = r.get("price_move")
        if move is None:
            continue
        abs_moves.append(abs(move))
        if dirn == "LONG":
            long_n += 1
        elif dirn == "SHORT":
            short_n += 1
        else:
            hold_n += 1
        if dirn in ("LONG", "SHORT"):
            n_dir += 1
            if (dirn == "LONG" and move > 0) or (dirn == "SHORT" and move < 0):
                correct += 1
            active_pnls.append(_pnl_for(dirn, move))

    pnl_total = round(sum(active_pnls), 6) if active_pnls else 0.0
    pnl_mean = round(pnl_total / len(active_pnls), 6) if active_pnls else None
    sharpe = None
    if len(active_pnls) >= 4:
        s = statistics.pstdev(active_pnls)
        m = sum(active_pnls) / len(active_pnls)
        if s > 0:
            sharpe = round(m / s, 4)
    sortino = _sortino(active_pnls)
    calmar = _calmar(active_pnls)
    mdd = _max_drawdown(active_pnls)
    # Exposure-adjusted utility: net pnl per *unit of exposure taken*.
    # If a stage took 30 directional bets and earned 0.5 total, utility = 0.5/30.
    n_exposed = long_n + short_n
    util = (
        round(pnl_total / n_exposed, 6) if n_exposed > 0 else None
    )
    return {
        "label": label,
        "n": len(rows),
        "n_active": len(active_pnls),
        "realized_pnl_total": pnl_total,
        "realized_pnl_mean": pnl_mean,
        "directional_accuracy": round(correct / n_dir, 4) if n_dir else None,
        "avg_abs_move": round(sum(abs_moves) / len(abs_moves), 6) if abs_moves else None,
        "exposure_efficiency": (
            round(pnl_total / len(active_pnls), 6) if active_pnls else None
        ),
        "sharpe_proxy": sharpe,
        "sortino_proxy": sortino,
        "calmar_proxy": calmar,
        "max_drawdown_pct": (
            round(mdd * 100, 4) if mdd is not None else None
        ),
        "exposure_adjusted_utility": util,
        "exposure": {"long": long_n, "short": short_n, "hold": hold_n},
    }


def _verdict(net_alpha: float) -> str:
    if net_alpha > 0.001:
        return "META_NET_POSITIVE"
    if net_alpha < -0.001:
        return "META_NET_NEGATIVE"
    return "NEUTRAL"


def _attribution_block(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute attribution headline numbers from already-resolved rows."""
    avoided_loss = 0.0
    missed_gain = 0.0
    n_killed = 0
    n_loss_avoided = 0
    n_gain_missed = 0

    suppressed_shorts: List[float] = []
    suppressed_longs: List[float] = []

    for r in rows:
        raw = r.get("raw_direction") or "HOLD"
        fin = r.get("final_direction") or "HOLD"
        rr_raw = r.get("realized_return_raw")
        if rr_raw is None and r.get("price_move") is not None:
            rr_raw = _pnl_for(raw, r["price_move"])
        if raw in ("LONG", "SHORT") and fin == "HOLD":
            n_killed += 1
            if rr_raw is not None and rr_raw < -0.0005:
                avoided_loss += abs(rr_raw)
                n_loss_avoided += 1
            elif rr_raw is not None and rr_raw > 0.0005:
                missed_gain += rr_raw
                n_gain_missed += 1
            if raw == "SHORT":
                suppressed_shorts.append(rr_raw or 0.0)
            elif raw == "LONG":
                suppressed_longs.append(rr_raw or 0.0)

    net_alpha = avoided_loss - missed_gain
    return {
        "avoided_loss_pct": round(avoided_loss * 100, 4),
        "missed_gain_pct": round(missed_gain * 100, 4),
        "net_alpha_pct": round(net_alpha * 100, 4),
        "n_killed_to_hold": n_killed,
        "n_killed_loss_avoided": n_loss_avoided,
        "n_killed_gain_missed": n_gain_missed,
        "suppressed_shorts": {
            "n": len(suppressed_shorts),
            "would_have_total": round(sum(suppressed_shorts), 6) if suppressed_shorts else 0.0,
            "would_have_mean": (
                round(sum(suppressed_shorts) / len(suppressed_shorts), 6)
                if suppressed_shorts else None
            ),
            "win_rate_if_executed": (
                round(sum(1 for v in suppressed_shorts if v > 0) /
                      len(suppressed_shorts), 4)
                if suppressed_shorts else None
            ),
        },
        "suppressed_longs": {
            "n": len(suppressed_longs),
            "would_have_total": round(sum(suppressed_longs), 6) if suppressed_longs else 0.0,
            "would_have_mean": (
                round(sum(suppressed_longs) / len(suppressed_longs), 6)
                if suppressed_longs else None
            ),
            "win_rate_if_executed": (
                round(sum(1 for v in suppressed_longs if v > 0) /
                      len(suppressed_longs), 4)
                if suppressed_longs else None
            ),
        },
        "verdict": _verdict(net_alpha),
    }


@router.get("/realized")
async def attribution_realized(
    horizon: Optional[str] = Query(None, description="1D|7D|30D"),
    limit: int = Query(2000, ge=1, le=10000),
):
    """Realized economic attribution of Meta-Brain decisions over the
    set of RESOLVED forward-tracking outcomes.

    READ-ONLY. NO EXECUTION. NO ORDERS. NO COMMITS.
    """
    cli = MongoClient(MONGO_URL)
    db = cli[DB_NAME]
    q: Dict[str, Any] = {"status": "RESOLVED"}
    if horizon:
        q["horizon"] = horizon
    rows = list(db.mbrain_integrity_outcomes.find(q, {"_id": 0}).limit(limit))
    if not rows:
        return {
            "ok": True,
            "n": 0,
            "note": ("no resolved outcomes — call POST "
                     "/api/mbrain/integrity/asymmetry/resolve first"),
            "headline": _attribution_block([]),
        }

    raw_summary = _stage_summary(rows, "raw_direction", "RAW")
    final_summary = _stage_summary(rows, "final_direction", "FINAL")
    meta_summary = _stage_summary(rows, "after_meta_direction", "META")

    headline = _attribution_block(rows)

    # Attribution-class distribution
    cls_counter: Counter = Counter()
    for r in rows:
        cls_counter[r.get("attribution_class") or "unknown"] += 1
    attr_breakdown = dict(cls_counter)

    # Per-horizon breakdown (1D / 7D / 30D), each with its own headline
    horizons: Dict[str, Any] = {}
    by_h: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_h[r.get("horizon") or "?"].append(r)
    for h, hrows in by_h.items():
        h_head = _attribution_block(hrows)
        h_raw = _stage_summary(hrows, "raw_direction", "RAW")
        h_final = _stage_summary(hrows, "final_direction", "FINAL")
        suppress_rate = None
        n_raw_dir = sum(1 for r in hrows
                        if (r.get("raw_direction") or "HOLD") in ("LONG", "SHORT"))
        n_final_hold = sum(1 for r in hrows
                           if (r.get("raw_direction") or "HOLD") in ("LONG", "SHORT")
                           and (r.get("final_direction") or "HOLD") == "HOLD")
        if n_raw_dir:
            suppress_rate = round(n_final_hold / n_raw_dir, 4)
        horizons[h] = {
            "n": len(hrows),
            "headline": h_head,
            "raw": {
                "directional_accuracy": h_raw["directional_accuracy"],
                "realized_pnl_total": h_raw["realized_pnl_total"],
            },
            "final": {
                "directional_accuracy": h_final["directional_accuracy"],
                "realized_pnl_total": h_final["realized_pnl_total"],
            },
            "exposure_suppression_rate": suppress_rate,
        }

    # Asset-level summary
    by_a: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_a[r.get("symbol") or "?"].append(r)
    by_asset: Dict[str, Any] = {}
    for a, arows in by_a.items():
        a_head = _attribution_block(arows)
        a_final = _stage_summary(arows, "final_direction", "FINAL")
        by_asset[a] = {
            "n": len(arows),
            "net_alpha_pct": a_head["net_alpha_pct"],
            "verdict": a_head["verdict"],
            "final_pnl_total": a_final["realized_pnl_total"],
        }

    return {
        "ok": True,
        "n": len(rows),
        "filter": {"horizon": horizon},
        "stage_summary": {
            "raw": raw_summary,
            "meta": meta_summary,
            "final": final_summary,
        },
        "headline": headline,
        "attribution_breakdown": attr_breakdown,
        "by_horizon": horizons,
        "by_asset": by_asset,
        "constraints": [
            "paper_only", "read_only", "no_orders", "no_execution",
            "no_commits", "no_trading_os_writes",
            "no_production_fusion_influence",
        ],
    }
