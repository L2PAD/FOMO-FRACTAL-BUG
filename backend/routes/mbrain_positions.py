"""
mbrain_positions — paper-first Position Runtime for the Expo Trading
Runtime v1.

Goal: surface the three "parallel universes" of how the same set of
verdicts would have performed if executed at different stages of the
decision pipeline:

   RAW    → if we acted on raw model directions
   META   → if we acted after Rules + Meta-Brain (current behavior)
   FINAL  → if we acted on final action (current behavior + ensemble)

This is paper-only. NO orders. NO live execution. NO commit. NO writes
to trading_os. NO production fusion influence. We read the existing
forward-tracking outcome records (`mbrain_integrity_outcomes`) and
compute hypothetical unrealized PnL using a fresh close-price fetched
from the side-car (HTTP-only, read-only).

Endpoint:

  GET /api/mbrain/positions/parallel?include_resolved=true|false

Returns:
  {
    portfolios: {
      raw:   { ...summary, positions: [...] },
      meta:  { ...summary, positions: [...] },
      final: { ...summary, positions: [...] },
    },
    headline: {
      suppressed_alpha_pct,        # PnL diff RAW - FINAL
      hold_decisions_blocked,      # count of HOLDs in FINAL that were SHORT/LONG in RAW
      directional_trades_killed,   # ditto with directional flip
      meta_brain_pnl_delta,        # FINAL - META (often ~0; mostly survives)
    },
    constraints: [...],
  }
"""
from __future__ import annotations

import asyncio
import os
import statistics
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import APIRouter, Query
from pymongo import MongoClient

UPSTREAM = os.environ.get(
    "TRADING_TERMINAL_UPSTREAM", "http://localhost:8002",
).rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

router = APIRouter(prefix="/api/mbrain/positions", tags=["mbrain-positions"])


# ─────────────────────────────────────────────────────────────────────
# Price fetcher — current close from side-car. HTTP-only, async, capped.
# ─────────────────────────────────────────────────────────────────────

async def _fetch_current_price_async(symbol: str,
                                     client: httpx.AsyncClient,
                                     timeout: float = 5.0) -> Optional[float]:
    """Pull the latest spot from the side-car chart endpoint, async, with
    aggressive timeout to avoid blocking the event loop."""
    asset = symbol.replace("USDT", "") if symbol.endswith("USDT") else symbol
    try:
        r = await client.get(
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


async def _fetch_prices_parallel(
    symbols: List[str], timeout: float = 5.0,
) -> Dict[str, Optional[float]]:
    """Fetch every symbol concurrently with a single AsyncClient."""
    out: Dict[str, Optional[float]] = {s: None for s in symbols}
    if not symbols:
        return out
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*[
            _fetch_current_price_async(s, client, timeout) for s in symbols
        ], return_exceptions=True)
    for sym, val in zip(symbols, results):
        if isinstance(val, Exception):
            out[sym] = None
        else:
            out[sym] = val
    return out


def _fetch_current_price(symbol: str, client: httpx.Client,
                         timeout: float = 5.0) -> Optional[float]:
    """Sync version kept for legacy callers (not used by the main route)."""
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


# ─────────────────────────────────────────────────────────────────────
# Per-stage hypothetical PnL math
# ─────────────────────────────────────────────────────────────────────

def _pnl_for_direction(direction: str, entry: float, close: float) -> float:
    """Pretend we hold a $1 unit of position. PnL is in fraction of entry."""
    if not entry or entry <= 0 or close <= 0:
        return 0.0
    move = (close - entry) / entry
    if direction == "LONG":
        return move
    if direction == "SHORT":
        return -move
    return 0.0  # HOLD does nothing


def _build_chips_for_position(raw_dir: str, meta_dir: str, final_dir: str,
                              raw_pnl: Optional[float],
                              final_pnl: Optional[float],
                              attribution_class: Optional[str] = None,
                              realized_return: Optional[float] = None,
                              realized_return_raw: Optional[float] = None,
                              ) -> List[Dict[str, str]]:
    """Compute small inline chips that explain what happened to this signal.

    If `attribution_class` (from RESOLVED outcome) is provided, we emit
    realized chips (LOSS_AVOIDED with magnitude, GAIN_MISSED, CORRECT_FLIP,
    WRONG_FLIP, PASSED_CORRECT, PASSED_WRONG) instead of the live ones.

    Tones:
      good  — Meta saved capital / position currently winning
      block — Meta missed money / position currently losing
      warn  — Meta downgraded / collapsed signal
      alert — Direction flip
      info  — neutral state
    """
    chips: List[Dict[str, str]] = []
    raw_directional = raw_dir in ("LONG", "SHORT")
    final_directional = final_dir in ("LONG", "SHORT")

    # ── REALIZED-PRIORITY chips ─────────────────────────────────────
    if attribution_class:
        ac = attribution_class
        if ac == "loss_avoided":
            mag = abs(realized_return_raw or 0.0) * 100
            chips.append({"type": "LOSS_AVOIDED", "tone": "good",
                          "label": f"saved {mag:.1f}%"})
        elif ac == "gain_missed":
            mag = (realized_return_raw or 0.0) * 100
            chips.append({"type": "GAIN_MISSED", "tone": "block",
                          "label": f"missed +{mag:.1f}%"})
        elif ac == "correct_flip":
            mag = (realized_return or 0.0) * 100
            chips.append({"type": "CORRECT_FLIP", "tone": "good",
                          "label": f"flip won +{mag:.1f}%"})
        elif ac == "wrong_flip":
            mag = (realized_return or 0.0) * 100
            chips.append({"type": "WRONG_FLIP", "tone": "block",
                          "label": f"flip lost {mag:.1f}%"})
        elif ac == "passed_correct":
            mag = (realized_return or 0.0) * 100
            chips.append({"type": "PASSED_CORRECT", "tone": "good",
                          "label": f"+{mag:.1f}% realized"})
        elif ac == "passed_wrong":
            mag = (realized_return or 0.0) * 100
            chips.append({"type": "PASSED_WRONG", "tone": "block",
                          "label": f"{mag:.1f}% realized"})
        elif ac == "neutral_suppress":
            chips.append({"type": "SUPPRESSED", "tone": "warn",
                          "label": "SUPPRESSED·flat"})
        return chips

    # ── PAPER-SNAPSHOT chips (unresolved positions) ─────────────────
    # 1. SUPPRESSED / BLOCKED — raw was directional, final is HOLD
    if raw_directional and final_dir == "HOLD":
        chips.append({"type": "SUPPRESSED",
                      "label": "SUPPRESSED",
                      "tone": "warn"})
        # Sub-tag: was that a loss avoided or a gain missed?
        if raw_pnl is not None:
            if raw_pnl < -0.001:
                chips.append({"type": "LOSS_AVOIDED",
                              "label": f"saved {abs(raw_pnl)*100:.1f}%",
                              "tone": "good"})
            elif raw_pnl > 0.001:
                chips.append({"type": "GAIN_MISSED",
                              "label": f"missed {raw_pnl*100:.1f}%",
                              "tone": "block"})

    # 2. FLIPPED — raw and final are both directional but opposite
    elif raw_directional and final_directional and raw_dir != final_dir:
        chips.append({"type": "FLIPPED",
                      "label": f"FLIP {raw_dir[0]}→{final_dir[0]}",
                      "tone": "alert"})

    # 3. DOWNGRADED — raw directional → meta HOLD → final restored direction
    elif raw_directional and meta_dir == "HOLD" and final_dir == raw_dir:
        chips.append({"type": "DOWNGRADED",
                      "label": "META→HOLD·OVERRIDE",
                      "tone": "warn"})

    # 4. PASSED — raw == final == directional, meta did not block
    elif raw_directional and final_dir == raw_dir and meta_dir == raw_dir:
        chips.append({"type": "PASSED",
                      "label": "PASSED",
                      "tone": "info"})

    # 5. WIN / LOSS — outcome on the actual final position
    if final_directional and final_pnl is not None:
        if final_pnl > 0.001:
            chips.append({"type": "WIN",
                          "label": f"+{final_pnl*100:.1f}%",
                          "tone": "good"})
        elif final_pnl < -0.001:
            chips.append({"type": "LOSS",
                          "label": f"{final_pnl*100:.1f}%",
                          "tone": "block"})
    return chips


def _build_narrative(raw_dir: str, final_dir: str,
                     price_move: Optional[float],
                     raw_pnl: Optional[float],
                     final_pnl: Optional[float],
                     attribution_class: Optional[str] = None,
                     realized_return: Optional[float] = None,
                     realized_return_raw: Optional[float] = None,
                     ) -> Optional[Dict[str, Any]]:
    """Lightweight narrative for the Timeline Replay Card. NOT a full
    replay engine — just the story line the UI is going to render.

    If `attribution_class` is provided we use realized data for the
    ending step ("Suppressed trade would have yielded +11.4%" /
    "Meta-Brain avoided loss") instead of paper-snapshot pnl.
    """
    if price_move is None or raw_pnl is None or final_pnl is None:
        return None
    move_pct = price_move * 100
    raw_directional = raw_dir in ("LONG", "SHORT")
    final_directional = final_dir in ("LONG", "SHORT")
    raw_label = f"RAW {raw_dir}"
    final_label = f"META {final_dir}" if final_dir == "HOLD" else f"FINAL {final_dir}"

    end_label = ""
    end_tone = "info"
    realized = bool(attribution_class)

    if realized:
        # REALIZED narrative endings
        ac = attribution_class
        if ac == "loss_avoided":
            mag = abs(realized_return_raw or 0.0) * 100
            end_label = f"Meta avoided -{mag:.1f}% loss"
            end_tone = "good"
        elif ac == "gain_missed":
            mag = (realized_return_raw or 0.0) * 100
            end_label = f"Suppressed: +{mag:.1f}% missed"
            end_tone = "block"
        elif ac == "correct_flip":
            mag = (realized_return or 0.0) * 100
            end_label = f"Flip won: +{mag:.1f}%"
            end_tone = "good"
        elif ac == "wrong_flip":
            mag = (realized_return or 0.0) * 100
            end_label = f"Flip lost: {mag:.1f}%"
            end_tone = "block"
        elif ac == "passed_correct":
            mag = (realized_return or 0.0) * 100
            end_label = f"Conviction realized: +{mag:.1f}%"
            end_tone = "good"
        elif ac == "passed_wrong":
            mag = (realized_return or 0.0) * 100
            end_label = f"Conviction wrong: {mag:.1f}%"
            end_tone = "block"
        elif ac == "neutral_suppress":
            end_label = "Suppressed (flat outcome)"
            end_tone = "info"
        else:
            return None
    else:
        # PAPER-SNAPSHOT narrative endings
        if raw_directional and final_dir == "HOLD":
            if raw_pnl < -0.001:
                end_label = "Capital preserved"
                end_tone = "good"
            elif raw_pnl > 0.001:
                end_label = "Opportunity missed"
                end_tone = "block"
            else:
                end_label = "Held flat"
                end_tone = "info"
        elif raw_directional and final_directional and raw_dir != final_dir:
            end_label = "Direction flipped" + (
                " · won" if final_pnl > 0 else " · lost" if final_pnl < 0 else "")
            end_tone = "good" if final_pnl > 0 else "block" if final_pnl < 0 else "alert"
        elif raw_directional and raw_dir == final_dir:
            if final_pnl > 0.001:
                end_label = "Conviction paid"
                end_tone = "good"
            elif final_pnl < -0.001:
                end_label = "Direction wrong"
                end_tone = "block"
            else:
                end_label = "No move yet"
                end_tone = "info"
        else:
            return None

    return {
        "raw": raw_label,
        "final": final_label,
        "move_pct": round(move_pct, 2),
        "end_label": end_label,
        "end_tone": end_tone,
        "raw_pnl_pct": round(raw_pnl * 100, 2),
        "final_pnl_pct": round(final_pnl * 100, 2),
        "realized": realized,
    }


def _summarize_portfolio(positions: List[Dict[str, Any]],
                         label: str) -> Dict[str, Any]:
    """Aggregate hypothetical per-asset positions into one portfolio."""
    if not positions:
        return {
            "label": label, "n": 0, "n_active": 0,
            "exposure": {"long": 0, "short": 0, "hold": 0},
            "unrealized_pnl_total": 0.0, "unrealized_pnl_mean": 0.0,
            "win_rate": None, "directional_winrate": None,
            "active_pnl_summary": None,
            "hold_count": 0,
            "positions": [],
        }
    long_n = sum(1 for p in positions if p.get("direction") == "LONG")
    short_n = sum(1 for p in positions if p.get("direction") == "SHORT")
    hold_n = sum(1 for p in positions if p.get("direction") == "HOLD")
    active = [p for p in positions if p.get("direction") in ("LONG", "SHORT")]
    total_pnl = sum(p.get("pnl") or 0.0 for p in positions)
    active_pnl = [p["pnl"] for p in active
                  if p.get("pnl") is not None]
    wins = sum(1 for x in active_pnl if x > 0)
    win_rate = (wins / len(active_pnl)) if active_pnl else None

    # Sharpe proxy on the active subset (no annualization — paper PnL
    # snapshot, just signal quality).
    sharpe_proxy = None
    if len(active_pnl) >= 4:
        m = sum(active_pnl) / len(active_pnl)
        s = statistics.pstdev(active_pnl)
        sharpe_proxy = (m / s) if s > 0 else None

    return {
        "label": label,
        "n": len(positions),
        "n_active": len(active),
        "exposure": {"long": long_n, "short": short_n, "hold": hold_n},
        "unrealized_pnl_total": round(total_pnl, 6),
        "unrealized_pnl_mean": round(total_pnl / len(positions), 6),
        "active_pnl_total": round(sum(active_pnl), 6) if active_pnl else 0.0,
        "active_pnl_mean": (
            round(sum(active_pnl) / len(active_pnl), 6)
            if active_pnl else None
        ),
        "win_rate": round(win_rate, 4) if win_rate is not None else None,
        "sharpe_proxy": round(sharpe_proxy, 4) if sharpe_proxy is not None else None,
        "hold_count": hold_n,
        "positions": positions,
    }


@router.get("/parallel")
async def parallel_universes(
    include_resolved: bool = Query(False),
    limit: int = Query(200, ge=1, le=500),
):
    """Compute hypothetical paper portfolios for the three pipeline
    stages (RAW / META / FINAL) using current spot prices vs the
    captured entry_price at decision time.

    NO EXECUTION. NO ORDERS. NO STATE WRITES OUTSIDE FOMO MONGO.
    """
    cli = MongoClient(MONGO_URL)
    db = cli[DB_NAME]
    q: Dict[str, Any] = {}
    if not include_resolved:
        q["status"] = "PENDING"
    rows = list(db.mbrain_integrity_outcomes.find(q, {"_id": 0}).limit(limit))
    if not rows:
        return {
            "ok": True,
            "n": 0,
            "note": "no outcome records — run /api/mbrain/integrity/replay/run first",
            "portfolios": {"raw": _summarize_portfolio([], "RAW"),
                            "meta": _summarize_portfolio([], "META"),
                            "final": _summarize_portfolio([], "FINAL")},
        }

    # Pull current prices once per unique symbol (parallel, async).
    symbols = sorted({r.get("symbol") for r in rows if r.get("symbol")})
    price_cache: Dict[str, Optional[float]] = await _fetch_prices_parallel(
        symbols, timeout=15.0)

    raw_positions: List[Dict[str, Any]] = []
    meta_positions: List[Dict[str, Any]] = []
    final_positions: List[Dict[str, Any]] = []
    unified: List[Dict[str, Any]] = []  # one row per outcome with all dirs/pnls

    for r in rows:
        sym = r.get("symbol")
        entry = r.get("entry_price")
        close = price_cache.get(sym)
        raw_dir = r.get("raw_direction") or "HOLD"
        meta_dir = r.get("after_meta_direction") or "HOLD"
        final_dir = r.get("final_direction") or "HOLD"

        if entry is None or close is None:
            base = {
                "symbol": sym, "horizon": r.get("horizon"),
                "ts": r.get("ts_iso"), "entry": entry, "close": close,
                "regime": r.get("regime"), "modelId": r.get("modelId"),
                "raw_expected_return": r.get("raw_expected_return"),
                "outcome_class": r.get("outcome_class"),
                "raw_dir": raw_dir, "meta_dir": meta_dir, "final_dir": final_dir,
                "raw_pnl": None, "meta_pnl": None, "final_pnl": None,
                "pnl": None, "missing_price": True, "chips": [],
            }
            raw_positions.append({**base, "direction": raw_dir})
            meta_positions.append({**base, "direction": meta_dir})
            final_positions.append({**base, "direction": final_dir})
            continue

        move_pct = (close - entry) / entry
        raw_pnl = _pnl_for_direction(raw_dir, entry, close)
        meta_pnl = _pnl_for_direction(meta_dir, entry, close)
        final_pnl = _pnl_for_direction(final_dir, entry, close)
        # If row is RESOLVED, use realized fields (close at horizon-end);
        # else _build_chips_for_position falls back to paper-snapshot logic.
        attr_cls = r.get("attribution_class") if r.get("status") == "RESOLVED" else None
        realized_ret = r.get("realized_return") if r.get("status") == "RESOLVED" else None
        realized_ret_raw = r.get("realized_return_raw") if r.get("status") == "RESOLVED" else None
        chips = _build_chips_for_position(
            raw_dir, meta_dir, final_dir, raw_pnl, final_pnl,
            attribution_class=attr_cls,
            realized_return=realized_ret,
            realized_return_raw=realized_ret_raw,
        )
        narrative = _build_narrative(
            raw_dir, final_dir, move_pct, raw_pnl, final_pnl,
            attribution_class=attr_cls,
            realized_return=realized_ret,
            realized_return_raw=realized_ret_raw,
        )

        base = {
            "symbol": sym, "horizon": r.get("horizon"),
            "ts": r.get("ts_iso"), "entry": entry, "close": close,
            "price_move_pct": round(move_pct, 6),
            "regime": r.get("regime"), "modelId": r.get("modelId"),
            "raw_expected_return": r.get("raw_expected_return"),
            "outcome_class": r.get("outcome_class"),
            "raw_dir": raw_dir, "meta_dir": meta_dir, "final_dir": final_dir,
            "raw_pnl": round(raw_pnl, 6),
            "meta_pnl": round(meta_pnl, 6),
            "final_pnl": round(final_pnl, 6),
            "chips": chips,
        }
        if narrative:
            base["narrative"] = narrative
        raw_positions.append({**base, "direction": raw_dir,
                              "pnl": round(raw_pnl, 6)})
        meta_positions.append({**base, "direction": meta_dir,
                               "pnl": round(meta_pnl, 6)})
        final_positions.append({**base, "direction": final_dir,
                                "pnl": round(final_pnl, 6)})
        unified.append(base)

    raw_summary = _summarize_portfolio(raw_positions, "RAW")
    meta_summary = _summarize_portfolio(meta_positions, "META")
    final_summary = _summarize_portfolio(final_positions, "FINAL")

    # Headline diffs (the "parallel universe" comparison).
    suppressed_alpha = (
        raw_summary["unrealized_pnl_total"] - final_summary["unrealized_pnl_total"]
    )
    meta_brain_delta = (
        final_summary["unrealized_pnl_total"] - meta_summary["unrealized_pnl_total"]
    )
    holds_blocked = sum(
        1 for r, f in zip(raw_positions, final_positions)
        if (r.get("direction") in ("LONG", "SHORT")
            and f.get("direction") == "HOLD")
    )
    flipped = sum(
        1 for r, f in zip(raw_positions, final_positions)
        if (r.get("direction") in ("LONG", "SHORT")
            and f.get("direction") in ("LONG", "SHORT")
            and r.get("direction") != f.get("direction"))
    )

    # Per-symbol PnL breakdown (for UI table rendering)
    by_symbol: Dict[str, Dict[str, Any]] = {}
    for s in symbols:
        rs = [p for p in raw_positions if p["symbol"] == s and p.get("pnl") is not None]
        fs = [p for p in final_positions if p["symbol"] == s and p.get("pnl") is not None]
        ms = [p for p in meta_positions if p["symbol"] == s and p.get("pnl") is not None]
        by_symbol[s] = {
            "n": len(rs),
            "raw_pnl": round(sum(p["pnl"] for p in rs), 6),
            "meta_pnl": round(sum(p["pnl"] for p in ms), 6),
            "final_pnl": round(sum(p["pnl"] for p in fs), 6),
            "current_price": price_cache.get(s),
        }

    # Build the Timeline-Replay narratives — realized stories first.
    narratives_all: List[Dict[str, Any]] = [
        {**u, "ts": u.get("ts"), "abs_raw": abs(u.get("raw_pnl") or 0.0)}
        for u in unified
        if u.get("narrative")
    ]
    realized_only = [x for x in narratives_all if x["narrative"].get("realized")]
    paper_only = [x for x in narratives_all if not x["narrative"].get("realized")]
    realized_only.sort(key=lambda x: x["abs_raw"], reverse=True)
    paper_only.sort(key=lambda x: x["abs_raw"], reverse=True)

    def _pack(item: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "symbol": item["symbol"],
            "horizon": item["horizon"],
            "ts": item["ts"],
            **item["narrative"],
        }

    # Priority: realized first (top 6), then paper-snapshot fillers.
    narratives_dedup: List[Dict[str, Any]] = []
    seen = set()
    for x in realized_only[:8] + paper_only[:6]:
        k = (x["symbol"], x["horizon"], x["ts"])
        if k in seen:
            continue
        seen.add(k)
        narratives_dedup.append(_pack(x))
        if len(narratives_dedup) >= 10:
            break

    return {
        "ok": True,
        "n": len(rows),
        "portfolios": {
            "raw": raw_summary,
            "meta": meta_summary,
            "final": final_summary,
        },
        "headline": {
            "suppressed_alpha_pct": round(suppressed_alpha * 100, 4),
            "meta_brain_pnl_delta_pct": round(meta_brain_delta * 100, 4),
            "directional_trades_killed_to_hold": holds_blocked,
            "directional_trades_flipped": flipped,
            "n_total": len(rows),
            "n_priced": sum(1 for p in raw_positions if p.get("pnl") is not None),
            "n_realized": sum(1 for r in rows if r.get("status") == "RESOLVED"),
        },
        "narratives": narratives_dedup,
        "by_symbol": by_symbol,
        "constraints": [
            "paper_only", "read_only", "http_only_to_sidecar",
            "no_commit", "no_orders", "no_execution",
            "no_trading_os_writes", "no_production_fusion_influence",
        ],
    }
