"""
mbrain_integrity.asymmetry  —  Module 2: Outcome Asymmetry Audit
=================================================================

Module 1 answered: where do signals die?
Module 2 answers:  is the suppressed alpha economically real?

Two sub-analyses:

  2A) EXPECTED-ASYMMETRY (computable from Module 1 snapshot only)
      Uses the side-car ML model's own `raw.expectedReturn` as the
      forward-looking alpha estimate. We compare how that estimate
      survives across stages, and quantify how much expected alpha
      is destroyed by Meta-Brain's HOLD-conversion. This is NOT
      synthetic — `expectedReturn` is the literal output of the real
      ML pipeline (model_1d / model_7d / model_30d).

  2B) REALIZED-ASYMMETRY (forward-tracking, requires waiting period)
      Persists the (symbol, horizon, ts, entry_price, raw_dir, final_action)
      tuple per decision into `mbrain_integrity_outcomes` (FOMO mongo,
      NOT trading_os). After horizon elapses, we pull the close price
      from the side-car (HTTP-only) and compute realized PnL. Then we
      can compare suppressed_short vs surviving_short realized PnL —
      the definitive answer to "does Meta-Brain destroy alpha or
      protect from drawdown?"

Constraints (per directive, identical to Module 1):
  • read-only
  • HTTP-only — no direct trading_os mongo reads/writes from FOMO core
  • no synthetic data
  • no production fusion influence
  • snapshots only into FOMO `test_database`

This module does NOT change the side-car, does NOT modify rules /
meta-brain / calibration / verdict engine, does NOT enable rollout.
"""
from __future__ import annotations

import os
import statistics
import time
from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx

UPSTREAM = os.environ.get(
    "TRADING_TERMINAL_UPSTREAM", "http://localhost:8002",
).rstrip("/")


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _median(values: List[float]) -> Optional[float]:
    return statistics.median(values) if values else None


def _mean(values: List[float]) -> Optional[float]:
    return (sum(values) / len(values)) if values else None


def _stdev(values: List[float]) -> Optional[float]:
    return statistics.stdev(values) if len(values) > 1 else None


def _summary(values: List[float]) -> Dict[str, Any]:
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "mean": round(_mean(values), 6),
        "median": round(_median(values), 6),
        "stdev": round(_stdev(values), 6) if len(values) > 1 else None,
        "min": round(min(values), 6),
        "max": round(max(values), 6),
        "p25": round(statistics.quantiles(values, n=4)[0], 6) if len(values) >= 4 else None,
        "p75": round(statistics.quantiles(values, n=4)[2], 6) if len(values) >= 4 else None,
    }


def _stage_dir(decision: Dict[str, Any], stage: str) -> str:
    return ((decision.get("stages") or {}).get(stage) or {}).get(
        "direction", "HOLD")


# ─────────────────────────────────────────────────────────────────────
# 2A — EXPECTED ASYMMETRY (no waiting period required)
# ─────────────────────────────────────────────────────────────────────

def classify_outcome(decision: Dict[str, Any]) -> str:
    """
    Map (raw_dir, final_dir) → outcome class. Used for suppression
    economics:

        suppressed_short  =  raw=SHORT, final≠SHORT (Meta-Brain killed bearish)
        surviving_short   =  raw=SHORT, final=SHORT
        flipped_short     =  raw=SHORT, final=LONG (rare)
        suppressed_long   =  raw=LONG,  final≠LONG
        surviving_long    =  raw=LONG,  final=LONG
        flipped_long      =  raw=LONG,  final=SHORT
        consistent_hold   =  raw=HOLD,  final=HOLD (negligible from raw=0)
        new_hold          =  raw=HOLD,  final≠HOLD
    """
    raw = _stage_dir(decision, "raw")
    final_dir = _stage_dir(decision, "final")
    if raw == "SHORT":
        if final_dir == "SHORT":
            return "surviving_short"
        if final_dir == "LONG":
            return "flipped_short"
        return "suppressed_short"
    if raw == "LONG":
        if final_dir == "LONG":
            return "surviving_long"
        if final_dir == "SHORT":
            return "flipped_long"
        return "suppressed_long"
    if final_dir == "HOLD":
        return "consistent_hold"
    return "new_hold"


def compute_expected_asymmetry(decisions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Pure computation. No I/O.

    For each decision the side-car ML pipeline emitted a raw
    `expectedReturn` (the model's forecast). We segment decisions by
    outcome class and report the distribution of that expected return.

    If Meta-Brain is rationally suppressing low-conviction signals,
    we expect suppressed_short.expected_return to be statistically
    SMALLER in magnitude than surviving_short.expected_return.

    If Meta-Brain is destroying alpha, we expect them to be of similar
    magnitude — meaning the suppressed signals were NOT lower-quality
    forecasts, just signals the policy layer chose not to act on.

    expected_alpha_destroyed = sum(|raw.expectedReturn|) over
    {suppressed_short ∪ suppressed_long}, divided by N.
    """
    if not decisions:
        return {"ok": True, "n": 0, "note": "no decisions"}

    bucket_returns: Dict[str, List[float]] = defaultdict(list)
    bucket_conf: Dict[str, List[float]] = defaultdict(list)
    bucket_count: Counter = Counter()

    suppressed_alpha_total = 0.0
    surviving_alpha_total = 0.0
    suppressed_n = 0
    surviving_n = 0

    # Per-horizon aggregation for the long-horizon paralysis check.
    by_horizon: Dict[str, Dict[str, List[float]]] = defaultdict(
        lambda: defaultdict(list))

    for d in decisions:
        cls = classify_outcome(d)
        bucket_count[cls] += 1
        raw = d.get("decision_raw") or {}
        er = raw.get("expectedReturn")
        conf = raw.get("confidence")
        if er is None:
            continue
        try:
            er_f = float(er)
        except (TypeError, ValueError):
            continue
        bucket_returns[cls].append(er_f)
        if conf is not None:
            try:
                bucket_conf[cls].append(float(conf))
            except (TypeError, ValueError):
                pass
        # By horizon
        hz = d.get("timeframe") or "?"
        by_horizon[hz]["all"].append(er_f)
        by_horizon[hz][cls].append(er_f)

        # Suppression economics
        if cls in ("suppressed_short", "suppressed_long"):
            suppressed_alpha_total += abs(er_f)
            suppressed_n += 1
        elif cls in ("surviving_short", "surviving_long"):
            surviving_alpha_total += abs(er_f)
            surviving_n += 1

    # Build segment summaries.
    segments: Dict[str, Any] = {}
    for cls, vals in bucket_returns.items():
        segments[cls] = {
            "expected_return": _summary(vals),
            "expected_return_abs": _summary([abs(v) for v in vals]),
            "raw_confidence": _summary(bucket_conf.get(cls, [])),
        }

    # The headline asymmetry test:
    # If suppressed.|er| ≈ surviving.|er| → Meta-Brain destroying alpha
    # If suppressed.|er| < surviving.|er| → Meta-Brain rational filter
    suppressed_short = bucket_returns.get("suppressed_short", [])
    surviving_short = bucket_returns.get("surviving_short", [])
    suppressed_long = bucket_returns.get("suppressed_long", [])
    surviving_long = bucket_returns.get("surviving_long", [])

    short_asym = None
    if suppressed_short and surviving_short:
        sup_med = _median([abs(v) for v in suppressed_short])
        sur_med = _median([abs(v) for v in surviving_short])
        short_asym = {
            "suppressed_abs_median": round(sup_med, 6),
            "surviving_abs_median": round(sur_med, 6),
            "ratio_suppressed_over_surviving": (
                round(sup_med / sur_med, 4) if sur_med else None
            ),
            "interpretation": (
                "alpha_destruction" if (sup_med >= 0.8 * sur_med)
                else "rational_filter"
            ),
        }

    long_asym = None
    if suppressed_long and surviving_long:
        sup_med = _median([abs(v) for v in suppressed_long])
        sur_med = _median([abs(v) for v in surviving_long])
        long_asym = {
            "suppressed_abs_median": round(sup_med, 6),
            "surviving_abs_median": round(sur_med, 6),
            "ratio_suppressed_over_surviving": (
                round(sup_med / sur_med, 4) if sur_med else None
            ),
            "interpretation": (
                "alpha_destruction" if (sup_med >= 0.8 * sur_med)
                else "rational_filter"
            ),
        }

    # HOLD opportunity-cost: |expectedReturn| of the model on decisions
    # that were converted to HOLD. If high → high theoretical opp cost.
    hold_decisions_er = (
        bucket_returns.get("suppressed_short", [])
        + bucket_returns.get("suppressed_long", [])
        + bucket_returns.get("consistent_hold", [])
    )
    hold_opportunity_cost = _summary([abs(v) for v in hold_decisions_er])

    # Per-horizon expected destruction
    horizon_breakdown: Dict[str, Any] = {}
    for hz, blocks in by_horizon.items():
        sup = blocks.get("suppressed_short", []) + blocks.get("suppressed_long", [])
        sur = blocks.get("surviving_short", []) + blocks.get("surviving_long", [])
        all_ = blocks.get("all", [])
        horizon_breakdown[hz] = {
            "n": len(all_),
            "expected_return_abs_overall": _summary([abs(v) for v in all_]),
            "expected_return_abs_suppressed": _summary([abs(v) for v in sup]),
            "expected_return_abs_surviving": _summary([abs(v) for v in sur]),
            "suppression_count": len(sup),
            "survival_count": len(sur),
        }

    return {
        "ok": True,
        "n": len(decisions),
        "outcome_class_counts": dict(bucket_count),
        "segments": segments,
        "headline": {
            "short_alpha_asymmetry": short_asym,
            "long_alpha_asymmetry": long_asym,
            "expected_alpha_destroyed_total": round(suppressed_alpha_total, 6),
            "expected_alpha_destroyed_per_decision": (
                round(suppressed_alpha_total / suppressed_n, 6)
                if suppressed_n else None
            ),
            "expected_alpha_realized_total": round(surviving_alpha_total, 6),
            "expected_alpha_realized_per_decision": (
                round(surviving_alpha_total / surviving_n, 6)
                if surviving_n else None
            ),
            "destruction_to_realization_ratio": (
                round(suppressed_alpha_total / surviving_alpha_total, 4)
                if surviving_alpha_total > 0 else None
            ),
            "n_suppressed": suppressed_n,
            "n_surviving": surviving_n,
        },
        "hold_opportunity_cost_abs": hold_opportunity_cost,
        "by_horizon": horizon_breakdown,
    }


# ─────────────────────────────────────────────────────────────────────
# 2B — REALIZED-ASYMMETRY  (forward-tracking infrastructure)
# ─────────────────────────────────────────────────────────────────────

# Resolve horizons in seconds — for forward outcome scheduling.
HORIZON_SECONDS = {
    "1D": 24 * 3600,
    "7D": 7 * 24 * 3600,
    "30D": 30 * 24 * 3600,
}


def fetch_close_price(symbol: str, ts_iso: Optional[str] = None,
                      timeout: float = 6.0) -> Optional[float]:
    """
    Pull current spot price for a symbol via the side-car. HTTP-only.
    If `ts_iso` is None → use current price (for forward-resolved
    outcomes). For historical points we'd need a side-car endpoint
    that accepts a `ts` param — not used in 2A.
    """
    url = f"{UPSTREAM}/api/market/chart/price-vs-expectation-v4"
    try:
        with httpx.Client() as c:
            r = c.get(url, params={"asset": symbol, "range": "24h",
                                   "horizon": "1D"},
                      timeout=timeout)
            if r.status_code != 200:
                return None
            body = r.json()
            pts = body.get("price") or []
            if not pts:
                return None
            return float(pts[-1].get("price"))
    except Exception:
        return None


def build_forward_outcome_records(
    decisions: List[Dict[str, Any]],
    entry_prices: Optional[Dict[str, float]] = None,
) -> List[Dict[str, Any]]:
    """
    Convert raw decisions into per-row outcome-tracking records
    suitable for persistence in `mbrain_integrity_outcomes`. Caller
    is responsible for actual insert (see routes/mbrain_integrity.py).
    """
    out: List[Dict[str, Any]] = []
    entry_prices = entry_prices or {}
    now = time.time()
    for d in decisions:
        sym = d.get("symbol")
        hz = d.get("timeframe")
        if not sym or hz not in HORIZON_SECONDS:
            continue
        rec = {
            "symbol": sym,
            "horizon": hz,
            "ts_iso": d.get("ts"),
            "entry_price": entry_prices.get(sym),
            "raw_direction": _stage_dir(d, "raw"),
            "after_meta_direction": _stage_dir(d, "after_meta_brain"),
            "final_direction": _stage_dir(d, "final"),
            "raw_expected_return": (
                (d.get("decision_raw") or {}).get("expectedReturn")),
            "raw_confidence": (
                (d.get("decision_raw") or {}).get("confidence")),
            "regime": d.get("regime"),
            "modelId": d.get("modelId"),
            "outcome_class": classify_outcome(d),
            "resolveAtEpoch": now + HORIZON_SECONDS[hz],
            "status": "PENDING",
            "_verdictId": d.get("_verdictId"),
        }
        out.append(rec)
    return out


def resolve_pending_outcomes(records: List[Dict[str, Any]],
                             now_epoch: Optional[float] = None,
                             price_cache: Optional[Dict[str, float]] = None,
                             ) -> Dict[str, Any]:
    """
    For each pending record whose `resolveAtEpoch` has passed, fetch
    the current close price via the side-car and compute realized
    return. Returns the mutation list (caller persists the updates).

    realized_return for LONG-direction =  (close - entry) / entry
    realized_return for SHORT-direction = -(close - entry) / entry
    For HOLD final we report the absolute price move (opportunity cost).

    If `price_cache` (symbol -> price) is provided we skip the HTTP
    fetch — the caller already pulled prices async-parallel.
    """
    now_epoch = now_epoch if now_epoch is not None else time.time()
    updates: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []

    cache: Dict[str, float] = dict(price_cache or {})
    for rec in records:
        if rec.get("status") != "PENDING":
            continue
        if rec.get("resolveAtEpoch") and rec["resolveAtEpoch"] > now_epoch:
            continue
        sym = rec.get("symbol")
        if sym not in cache:
            p = fetch_close_price(
                sym + "USDT" if not sym.endswith("USDT") else sym)
            if p is None:
                failures.append({"symbol": sym, "reason": "fetch_close_failed"})
                continue
            cache[sym] = p
        close = cache[sym]
        entry = rec.get("entry_price")
        if not entry or entry <= 0:
            failures.append({"symbol": sym, "reason": "no_entry_price"})
            continue
        move = (close - entry) / entry
        final_dir = rec.get("final_direction")
        raw_dir = rec.get("raw_direction") or "HOLD"
        if final_dir == "LONG":
            realized = move
        elif final_dir == "SHORT":
            realized = -move
        else:
            realized = 0.0  # HOLD has no realized PnL; opp_cost = abs(move)

        # Realized direction-correctness (vs price move sign).
        # Considers what we would have HAD if we executed RAW vs FINAL.
        def _correct(direction: str) -> Optional[bool]:
            if direction == "LONG":
                return move > 0
            if direction == "SHORT":
                return move < 0
            return None  # HOLD has no direction
        # What "RAW would have realized" if we had executed it
        if raw_dir == "LONG":
            realized_raw = move
        elif raw_dir == "SHORT":
            realized_raw = -move
        else:
            realized_raw = 0.0
        # Outcome attribution: classify each row's economic effect.
        attribution_class = "neutral"
        # If RAW was directional and FINAL converted to HOLD:
        if raw_dir in ("LONG", "SHORT") and final_dir == "HOLD":
            if realized_raw < -0.0005:
                attribution_class = "loss_avoided"   # Meta saved capital
            elif realized_raw > 0.0005:
                attribution_class = "gain_missed"    # Meta destroyed alpha
            else:
                attribution_class = "neutral_suppress"
        # If RAW differs from FINAL (and both directional) → flip
        elif raw_dir in ("LONG", "SHORT") and final_dir in ("LONG", "SHORT") and raw_dir != final_dir:
            if realized > 0.0005:
                attribution_class = "correct_flip"   # flip improved outcome
            elif realized < -0.0005:
                attribution_class = "wrong_flip"     # flip destroyed outcome
            else:
                attribution_class = "neutral_flip"
        elif final_dir in ("LONG", "SHORT") and raw_dir == final_dir:
            attribution_class = (
                "passed_correct" if realized > 0.0005
                else "passed_wrong" if realized < -0.0005
                else "passed_flat"
            )
        else:
            attribution_class = "consistent_hold"

        updates.append({
            "symbol": sym,
            "horizon": rec.get("horizon"),
            "ts_iso": rec.get("ts_iso"),
            "entry_price": entry,
            "close_price": close,
            "price_move": move,
            "realized_return": realized,
            "realized_return_raw": realized_raw,
            "opp_cost_abs": abs(move),
            "realized_direction_correct": _correct(final_dir),
            "raw_direction_correct": _correct(raw_dir),
            "attribution_class": attribution_class,
            "status": "RESOLVED",
            "resolved_at_epoch": now_epoch,
        })
    return {"updates": updates, "failures": failures, "n": len(updates)}


def compute_realized_asymmetry(resolved: List[Dict[str, Any]],
                               outcome_classes: Dict[Tuple[str, str], str],
                               ) -> Dict[str, Any]:
    """
    Aggregate realized PnL by outcome class. `outcome_classes` is the
    map (symbol, ts_iso) → outcome class produced at decision time.
    """
    by_class: Dict[str, List[float]] = defaultdict(list)
    by_horizon: Dict[str, List[float]] = defaultdict(list)
    abs_moves: Dict[str, List[float]] = defaultdict(list)
    for r in resolved:
        key = (r.get("symbol"), r.get("ts_iso"))
        cls = outcome_classes.get(key, "?")
        rr = r.get("realized_return")
        if rr is None:
            continue
        by_class[cls].append(float(rr))
        by_horizon[str(r.get("horizon"))].append(float(rr))
        abs_moves[cls].append(abs(float(r.get("price_move") or 0.0)))
    out = {
        "ok": True,
        "n": len(resolved),
        "realized_by_class": {k: _summary(v) for k, v in by_class.items()},
        "realized_by_horizon": {k: _summary(v) for k, v in by_horizon.items()},
        "abs_move_by_class": {k: _summary(v) for k, v in abs_moves.items()},
    }
    # Headline test:
    # opp_cost(suppressed_short) ≈ abs(realized) of "what would have been"
    if abs_moves.get("suppressed_short"):
        out["headline_suppressed_short_abs_move_median"] = round(
            _median(abs_moves["suppressed_short"]), 6)
    if abs_moves.get("surviving_short"):
        out["headline_surviving_short_abs_move_median"] = round(
            _median(abs_moves["surviving_short"]), 6)
    return out
