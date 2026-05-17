"""
mbrain_integrity.replay
=======================

G2 replay engine — directional integrity audit on REAL side-car decisions.

Constraints (per directive):
- HTTP-only (no direct trading_os mongo reads from FOMO core).
- No commits / no persistence in side-car (`/api/verdict/commit` not used).
- No synthetic ModelOutput injection (we trigger heavy-compute end-to-end
  inside the side-car, which runs real ML models → real Verdict pipeline
  → real Rules → real Meta-Brain → real Calibration → real final action).
- No production fusion influence (results are written ONLY to FOMO
  `mbrain_integrity_runs` collection in `test_database`, never to
  `trading_os`).
- Snapshots persist only on FOMO side, opt-in via the route.

Pipeline per replay sample:
    GET <upstream>/api/market/chart/price-vs-expectation-v4
        ?asset=<symbol>&range=<range>&horizon=<horizon>
        →  body.verdict  (full Verdict v2 envelope incl. raw, adjustments,
                          appliedRules, regime)
    →  normalize_verdict_to_decision(verdict)
    →  decision (v1 shape with stage-by-stage survival reconstruction)

The matrix sweeps the upstream cache to produce a wide directional
distribution — different ranges feed different feature contexts to the
ML models (1D/7D/30D), yielding distinct verdicts per (symbol, range,
horizon) tuple. This is REAL inference, not synthetic.

Output metrics (per `mbrain_integrity` core):
- LONG / SHORT / HOLD shares overall and per stage
- directional_entropy / directional_imbalance / hold_suppression
- per_asset / per_timeframe / per_confidence_bucket / per_regime
- stage survival: raw → after_rules → after_meta_brain → after_calibration → final
- bearish_survival_rate (fraction of raw=SHORT that remain SHORT at final)
- collapse counts per stage (which stage absorbs bearish signal into HOLD)
"""
from __future__ import annotations

import math
import os
import time
from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx

from .normalize import normalize_verdict_to_decision

UPSTREAM = os.environ.get(
    "TRADING_TERMINAL_UPSTREAM",
    "http://localhost:8002",
).rstrip("/")

# Default sweep matrix — wide enough to hit ~180+ real verdicts.
# Choosing assets actually traded on Binance USDT pairs to keep
# heavy-compute happy; ranges trigger different feature window lengths.
DEFAULT_ASSETS = [
    "BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA",
    "AVAX", "LINK", "MATIC", "DOT", "ATOM", "TON", "ARB", "OP",
]
DEFAULT_HORIZONS = ["1D", "7D", "30D"]
DEFAULT_RANGES = ["24h", "7d", "30d", "90d"]


def fetch_verdict_via_chart(
    asset: str, range_: str, horizon: str,
    client: httpx.Client, timeout: float = 60.0,
) -> Optional[Dict[str, Any]]:
    """Pulls one Verdict v2 envelope via the upstream chart endpoint.
    Returns the verdict envelope WITH `_entry_price` injected (the
    last price point from the chart response, captured at the same
    instant the verdict was computed — clean baseline for Module 2B
    realized-PnL attribution).
    Returns None on any 4xx/5xx so the caller can record a failure."""
    url = f"{UPSTREAM}/api/market/chart/price-vs-expectation-v4"
    try:
        r = client.get(url, params={"asset": asset, "range": range_,
                                    "horizon": horizon}, timeout=timeout)
        if r.status_code != 200:
            return None
        body = r.json()
        v = body.get("verdict")
        if not isinstance(v, dict):
            return None
        # Capture entry_price from the upstream price series (clean
        # synchronous baseline — no separate fetch, no timestamp drift).
        pts = body.get("price") or []
        entry_price = None
        if pts:
            try:
                entry_price = float(pts[-1].get("price"))
            except (TypeError, ValueError, AttributeError):
                entry_price = None
        v["_entry_price"] = entry_price
        return v
    except Exception:
        return None


def run_replay(
    assets: Optional[List[str]] = None,
    horizons: Optional[List[str]] = None,
    ranges: Optional[List[str]] = None,
    max_decisions: int = 500,
    timeout_seconds: float = 60.0,
    retain_decisions: bool = False,
) -> Dict[str, Any]:
    """Sweep (assets × ranges × horizons), pull verdict via heavy-compute,
    normalize, audit. Returns the full report. If `retain_decisions=True`
    the per-row decisions list is included under report['decisions']
    (used by Module 2 asymmetry analysis)."""
    assets = assets or DEFAULT_ASSETS
    horizons = horizons or DEFAULT_HORIZONS
    ranges = ranges or DEFAULT_RANGES

    decisions: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []

    started_at = time.time()
    with httpx.Client() as client:
        for asset in assets:
            for rng in ranges:
                for hz in horizons:
                    if len(decisions) >= max_decisions:
                        break
                    v = fetch_verdict_via_chart(
                        asset, rng, hz, client,
                        timeout=timeout_seconds,
                    )
                    if v is None:
                        failures.append({
                            "asset": asset, "range": rng, "horizon": hz,
                            "reason": "fetch_failed_or_empty_verdict",
                        })
                        continue
                    # Capture clean baseline price BEFORE normalize
                    # strips it. Used by Module 2B realized-PnL math.
                    entry_price = v.get("_entry_price")
                    d = normalize_verdict_to_decision(v)
                    d["_replay_range"] = rng
                    d["_entry_price"] = entry_price
                    decisions.append(d)
    elapsed_ms = int((time.time() - started_at) * 1000)

    report = compute_distribution_report(decisions)
    report["meta"] = {
        "n_decisions": len(decisions),
        "n_failures": len(failures),
        "elapsed_ms": elapsed_ms,
        "matrix": {
            "assets": assets,
            "horizons": horizons,
            "ranges": ranges,
        },
        "upstream": UPSTREAM,
        "constraints": [
            "http_only",
            "no_commit",
            "no_persistence_in_side_car",
            "no_synthetic_model_outputs",
            "no_production_fusion_influence",
        ],
    }
    if failures:
        report["failures_sample"] = failures[:20]
    if retain_decisions:
        report["decisions"] = decisions
    return report


# --- distribution computations ----------------------------------------------

CONF_BUCKETS = [(0.0, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8),
                (0.8, 0.9), (0.9, 1.0001)]


def _bucket_label(c: Optional[float]) -> str:
    if c is None or not isinstance(c, (int, float)) or math.isnan(c):
        return "NA"
    for lo, hi in CONF_BUCKETS:
        if lo <= c < hi:
            return f"{lo:.1f}-{hi:.1f}".replace("1.0001", "1.0")
    return "NA"


def _shannon_entropy(counter: Counter) -> float:
    total = sum(counter.values())
    if total <= 0:
        return 0.0
    h = 0.0
    for v in counter.values():
        if v <= 0:
            continue
        p = v / total
        h -= p * math.log2(p)
    return h


def _share(counter: Counter, key: str) -> float:
    total = sum(counter.values())
    if total <= 0:
        return 0.0
    return counter.get(key, 0) / total


def _imbalance(counter: Counter) -> float:
    return abs(_share(counter, "LONG") - _share(counter, "SHORT"))


def _hold_suppression(stage_counter: Counter) -> float:
    """Fraction of total volume that ends up as HOLD at this stage. High
    HOLD share is the suppression-into-paralysis pattern user warned us
    about."""
    return _share(stage_counter, "HOLD")


def compute_distribution_report(decisions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Pure computation. Does not write anywhere. Returns the audit
    report with stage-by-stage survival, stratifications, and the
    survival funnel for bearish signals."""

    if not decisions:
        return {"ok": True, "n": 0, "note": "no decisions to audit"}

    stages = ["raw", "after_rules", "after_meta_brain",
              "after_calibration", "final"]

    # Per-stage direction counters.
    per_stage: Dict[str, Counter] = {s: Counter() for s in stages}
    for d in decisions:
        stages_obj = d.get("stages") or {}
        for s in stages:
            stage_blob = stages_obj.get(s) or {}
            per_stage[s][stage_blob.get("direction", "HOLD")] += 1

    # Stage-level metrics.
    stage_metrics: Dict[str, Dict[str, Any]] = {}
    for s in stages:
        c = per_stage[s]
        stage_metrics[s] = {
            "counts": dict(c),
            "share_long": round(_share(c, "LONG"), 4),
            "share_short": round(_share(c, "SHORT"), 4),
            "share_hold": round(_share(c, "HOLD"), 4),
            "directional_entropy": round(_shannon_entropy(c), 4),
            "directional_imbalance": round(_imbalance(c), 4),
            "hold_suppression": round(_hold_suppression(c), 4),
        }

    # Bearish survival funnel.
    raw_short = [d for d in decisions
                 if (d.get("stages") or {}).get("raw", {}).get("direction") == "SHORT"]
    n_raw_short = len(raw_short)
    funnel = {"n_raw_short": n_raw_short}
    for s in stages[1:]:
        survived = [d for d in raw_short
                    if (d.get("stages") or {}).get(s, {}).get("direction") == "SHORT"]
        funnel[f"survived_to_{s}"] = len(survived)
        funnel[f"survived_share_{s}"] = (
            round(len(survived) / n_raw_short, 4) if n_raw_short else None
        )
    # Where did bearish die per stage (count of SHORT→HOLD/LONG transitions)?
    transitions = Counter()
    for d in raw_short:
        st = d.get("stages") or {}
        prev = "SHORT"
        for s in stages[1:]:
            cur = (st.get(s) or {}).get("direction", "HOLD")
            if prev == "SHORT" and cur != "SHORT":
                transitions[f"died_at_{s}"] += 1
                break
            prev = cur
    funnel["bearish_died_at"] = dict(transitions)

    # Stratifications (on raw + final stage).
    by_asset: Dict[str, Dict[str, Counter]] = {}
    by_timeframe: Dict[str, Dict[str, Counter]] = {}
    by_regime: Dict[str, Dict[str, Counter]] = {}
    by_confidence: Dict[str, Dict[str, Counter]] = {}

    def _ensure(d: dict, key: str) -> Dict[str, Counter]:
        if key not in d:
            d[key] = {"raw": Counter(), "final": Counter()}
        return d[key]

    for dec in decisions:
        sym = dec.get("symbol") or "?"
        tf = dec.get("timeframe") or "?"
        regime = dec.get("regime") or "?"
        bucket = _bucket_label(dec.get("confidence_final"))
        st = dec.get("stages") or {}
        raw_dir = (st.get("raw") or {}).get("direction", "HOLD")
        final_dir = (st.get("final") or {}).get("direction", "HOLD")
        _ensure(by_asset, sym)["raw"][raw_dir] += 1
        _ensure(by_asset, sym)["final"][final_dir] += 1
        _ensure(by_timeframe, tf)["raw"][raw_dir] += 1
        _ensure(by_timeframe, tf)["final"][final_dir] += 1
        _ensure(by_regime, regime)["raw"][raw_dir] += 1
        _ensure(by_regime, regime)["final"][final_dir] += 1
        _ensure(by_confidence, bucket)["raw"][raw_dir] += 1
        _ensure(by_confidence, bucket)["final"][final_dir] += 1

    def _stratum_to_dict(strat: Dict[str, Dict[str, Counter]]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for k, c in strat.items():
            out[k] = {
                "raw": dict(c["raw"]),
                "final": dict(c["final"]),
                "imbalance_raw": round(_imbalance(c["raw"]), 4),
                "imbalance_final": round(_imbalance(c["final"]), 4),
                "entropy_raw": round(_shannon_entropy(c["raw"]), 4),
                "entropy_final": round(_shannon_entropy(c["final"]), 4),
            }
        return out

    # Block / collapse aggregates.
    blocked_total = sum(1 for d in decisions if d.get("blocked"))
    block_reasons = Counter()
    for d in decisions:
        for r in d.get("block_reason") or []:
            block_reasons[str(r)] += 1
    collapse_keys = Counter()
    for d in decisions:
        for r in d.get("reason_chain") or []:
            collapse_keys[r] += 1

    return {
        "ok": True,
        "n": len(decisions),
        "stage_metrics": stage_metrics,
        "bearish_funnel": funnel,
        "stratifications": {
            "by_asset": _stratum_to_dict(by_asset),
            "by_timeframe": _stratum_to_dict(by_timeframe),
            "by_regime": _stratum_to_dict(by_regime),
            "by_confidence_bucket": _stratum_to_dict(by_confidence),
        },
        "blocking": {
            "blocked_total": blocked_total,
            "blocked_share": round(blocked_total / len(decisions), 4),
            "block_reasons_top": block_reasons.most_common(10),
        },
        "collapse_keys_top": collapse_keys.most_common(15),
    }
