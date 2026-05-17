"""
mbrain_integrity.calibration — Module 3: Confidence Calibration Audit
======================================================================

Module 1: where do signals die?       (Meta-Brain)
Module 2A: is suppressed alpha real?  (yes — 4:1 destruction, inverse on long)
Module 3: is confidence mathematically miscalibrated?

Two complementary analyses:

3.1) META-BRAIN ATTENUATION CURVE
     For each decision compute confidence_delta = raw.confidence - final.confidence
     and bucket by |raw.expectedReturn|. The smoking-gun question:

         Does Meta-Brain reduce confidence MORE for stronger expectedReturn?

     If yes — directly confirmed inverse selection at the math level
     (the bigger the model's conviction, the harder it gets penalized).

     This works without realized PnL — it operates on side-car-emitted
     pre/post Meta-Brain values only.

3.2) CONFIDENCE MONOTONICITY (vs realized)
     Required for full Module 3, but only callable AFTER Module 2B
     has resolved enough forward outcomes. We provide the function;
     the route gates execution on `n_resolved ≥ K`.

Pure computation. No I/O. No side-car mutation. No production influence.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any, Dict, List, Optional


def _summary(vals: List[float]) -> Dict[str, Any]:
    if not vals:
        return {"n": 0}
    out = {
        "n": len(vals),
        "mean": round(sum(vals) / len(vals), 6),
        "median": round(statistics.median(vals), 6),
        "min": round(min(vals), 6),
        "max": round(max(vals), 6),
    }
    if len(vals) > 1:
        out["stdev"] = round(statistics.stdev(vals), 6)
    if len(vals) >= 4:
        q = statistics.quantiles(vals, n=4)
        out["p25"] = round(q[0], 6)
        out["p75"] = round(q[2], 6)
    return out


# ─────────────────────────────────────────────────────────────────────
# 3.1 — Meta-Brain attenuation curve
# ─────────────────────────────────────────────────────────────────────

# |expectedReturn| buckets (absolute return magnitude).
ER_BUCKETS = [
    (0.00, 0.01, "0-1%"),
    (0.01, 0.03, "1-3%"),
    (0.03, 0.05, "3-5%"),
    (0.05, 0.08, "5-8%"),
    (0.08, 0.12, "8-12%"),
    (0.12, 1.00, "12%+"),
]


def _bucket_for_er(abs_er: float) -> str:
    for lo, hi, lbl in ER_BUCKETS:
        if lo <= abs_er < hi:
            return lbl
    return "12%+"


def compute_meta_brain_attenuation(
    decisions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    For every decision:
        raw_conf      = decision.decision_raw.confidence
        post_meta_c   = decision.stages.after_meta_brain.confidence
        delta         = raw_conf - post_meta_c       (positive = down-shift)
        |er|          = |decision.decision_raw.expectedReturn|

    We then bucket on |er| and report:
        n
        delta_mean / median / stdev / p75
        confidence_kept_share = mean(post_meta_c / raw_conf)
        p_action_downgraded   = % of bucket that was converted to HOLD by meta

    Reported for LONG side, SHORT side, and combined — because the
    inverse-selection effect was much sharper on LONG.
    """
    if not decisions:
        return {"ok": True, "n": 0, "note": "no decisions"}

    # Lists per (side, bucket) → deltas / kept_ratios
    deltas: Dict[str, Dict[str, List[float]]] = {
        "long": defaultdict(list),
        "short": defaultdict(list),
        "combined": defaultdict(list),
    }
    kept_ratios: Dict[str, Dict[str, List[float]]] = {
        "long": defaultdict(list),
        "short": defaultdict(list),
        "combined": defaultdict(list),
    }
    converted_to_hold: Dict[str, Dict[str, int]] = {
        "long": defaultdict(int),
        "short": defaultdict(int),
        "combined": defaultdict(int),
    }
    bucket_n: Dict[str, Dict[str, int]] = {
        "long": defaultdict(int),
        "short": defaultdict(int),
        "combined": defaultdict(int),
    }

    for d in decisions:
        raw = d.get("decision_raw") or {}
        raw_er = raw.get("expectedReturn")
        raw_conf = raw.get("confidence")
        if raw_er is None or raw_conf is None:
            continue
        try:
            er_f = float(raw_er); conf_f = float(raw_conf)
        except (TypeError, ValueError):
            continue
        abs_er = abs(er_f)
        bucket = _bucket_for_er(abs_er)
        side = "long" if er_f > 0 else "short" if er_f < 0 else None

        post_stage = (d.get("stages") or {}).get("after_meta_brain") or {}
        post_conf = post_stage.get("confidence")
        post_dir = post_stage.get("direction")
        post_conf_f: Optional[float] = None
        if post_conf is not None:
            try:
                post_conf_f = float(post_conf)
            except (TypeError, ValueError):
                post_conf_f = None

        delta = (conf_f - post_conf_f) if post_conf_f is not None else None
        kept = (post_conf_f / conf_f) if (
            post_conf_f is not None and conf_f > 0) else None
        downgraded = 1 if post_dir == "HOLD" else 0

        for grp in ("combined", side) if side else ("combined",):
            if delta is not None:
                deltas[grp][bucket].append(delta)
            if kept is not None:
                kept_ratios[grp][bucket].append(kept)
            converted_to_hold[grp][bucket] += downgraded
            bucket_n[grp][bucket] += 1

    def _emit_group(group: str) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for _, _, lbl in ER_BUCKETS:
            n = bucket_n[group].get(lbl, 0)
            if n == 0:
                continue
            d_list = deltas[group][lbl]
            k_list = kept_ratios[group][lbl]
            out[lbl] = {
                "n": n,
                "delta_summary": _summary(d_list),
                "confidence_kept_ratio_mean": (
                    round(sum(k_list) / len(k_list), 4) if k_list else None
                ),
                "p_action_downgraded_to_hold": round(
                    converted_to_hold[group][lbl] / n, 4),
            }
        return out

    long_curve = _emit_group("long")
    short_curve = _emit_group("short")
    combined_curve = _emit_group("combined")

    # Headline test — monotonicity of confidence-kept-ratio vs |er|.
    # If higher |er| → LOWER kept ratio  →  inverse selection confirmed.
    # If higher |er| → HIGHER p_downgrade → also inverse selection.
    def _trend(curve: Dict[str, Any], key: str = "confidence_kept_ratio_mean",
               higher_means_worse: bool = False
               ) -> Optional[str]:
        """When higher_means_worse=True → an increasing trend across
        |er| buckets means MORE penalty for stronger signals — i.e.
        inverse-selection (BAD). When False → decreasing trend means
        MORE penalty for stronger signals."""
        labels = [lbl for _, _, lbl in ER_BUCKETS if lbl in curve]
        vals = [curve[lbl].get(key) for lbl in labels]
        vals = [v for v in vals if v is not None]
        if len(vals) < 3:
            return None
        decreasing = all(vals[i] >= vals[i + 1] - 1e-6 for i in range(len(vals) - 1))
        increasing = all(vals[i] <= vals[i + 1] + 1e-6 for i in range(len(vals) - 1))
        if higher_means_worse:
            if increasing and not decreasing:
                return "monotonically_increasing_(inverse_selection_confirmed)"
            if decreasing and not increasing:
                return "monotonically_decreasing_(rational_filter)"
        else:
            if decreasing and not increasing:
                return "monotonically_decreasing_(inverse_selection_confirmed)"
            if increasing and not decreasing:
                return "monotonically_increasing_(rational_filter)"
        first = sum(vals[: max(1, len(vals) // 2)]) / max(1, len(vals) // 2)
        last = sum(vals[len(vals) // 2:]) / (len(vals) - len(vals) // 2)
        if higher_means_worse:
            if last > first + 0.05:
                return "broadly_increasing_(inverse_lean)"
            if last < first - 0.05:
                return "broadly_decreasing_(rational_lean)"
        else:
            if last < first - 0.05:
                return "broadly_decreasing_(inverse_lean)"
            if last > first + 0.05:
                return "broadly_increasing_(rational_lean)"
        return "ambiguous_or_flat"

    return {
        "ok": True,
        "n": sum(bucket_n["combined"].values()),
        "by_er_bucket": {
            "combined": combined_curve,
            "long": long_curve,
            "short": short_curve,
        },
        "headline": {
            "combined_trend_kept_ratio_vs_abs_er":
                _trend(combined_curve, "confidence_kept_ratio_mean", False),
            "long_trend_kept_ratio_vs_abs_er":
                _trend(long_curve, "confidence_kept_ratio_mean", False),
            "short_trend_kept_ratio_vs_abs_er":
                _trend(short_curve, "confidence_kept_ratio_mean", False),
            "combined_trend_p_downgrade_vs_abs_er":
                _trend(combined_curve, "p_action_downgraded_to_hold", True),
            "long_trend_p_downgrade_vs_abs_er":
                _trend(long_curve, "p_action_downgraded_to_hold", True),
            "short_trend_p_downgrade_vs_abs_er":
                _trend(short_curve, "p_action_downgraded_to_hold", True),
        },
    }


# ─────────────────────────────────────────────────────────────────────
# 3.2 — Realized confidence calibration (gated by 2B resolution)
# ─────────────────────────────────────────────────────────────────────

# Confidence buckets (post-meta-brain, the "advertised" confidence the
# system would show users).
CONF_BUCKETS = [
    (0.00, 0.50, "<0.50"),
    (0.50, 0.55, "0.50-0.55"),
    (0.55, 0.60, "0.55-0.60"),
    (0.60, 0.65, "0.60-0.65"),
    (0.65, 0.70, "0.65-0.70"),
    (0.70, 0.80, "0.70-0.80"),
    (0.80, 1.001, "0.80+"),
]


def _conf_bucket(c: float) -> str:
    for lo, hi, lbl in CONF_BUCKETS:
        if lo <= c < hi:
            return lbl
    return "<0.50"


def compute_realized_calibration(
    resolved_outcomes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    `resolved_outcomes` rows must contain at least:
        confidence (post-meta), realized_return, abs_move, direction (final)

    Reports realized return per confidence bucket. If higher confidence
    yields HIGHER realized edge — calibration sound. If flat or
    inverted — calibration broken.
    """
    if not resolved_outcomes:
        return {"ok": True, "n": 0, "note": "no resolved outcomes yet"}

    by_bucket_returns: Dict[str, List[float]] = defaultdict(list)
    by_bucket_abs_move: Dict[str, List[float]] = defaultdict(list)

    for r in resolved_outcomes:
        c = r.get("confidence")
        rr = r.get("realized_return")
        am = r.get("abs_move") or r.get("opp_cost_abs")
        if c is None or rr is None:
            continue
        try:
            cf = float(c); rf = float(rr)
        except (TypeError, ValueError):
            continue
        bucket = _conf_bucket(cf)
        by_bucket_returns[bucket].append(rf)
        if am is not None:
            try:
                by_bucket_abs_move[bucket].append(float(am))
            except (TypeError, ValueError):
                pass

    out: Dict[str, Any] = {}
    for _, _, lbl in CONF_BUCKETS:
        if lbl not in by_bucket_returns:
            continue
        out[lbl] = {
            "realized_return_summary": _summary(by_bucket_returns[lbl]),
            "abs_move_summary": _summary(by_bucket_abs_move.get(lbl, [])),
        }

    # Monotonicity: do higher confidence buckets yield higher mean
    # realized return? (Should — if calibration is healthy.)
    ordered = [lbl for _, _, lbl in CONF_BUCKETS if lbl in out]
    means = [out[lbl]["realized_return_summary"].get("mean") for lbl in ordered]
    means = [m for m in means if m is not None]
    interpretation = None
    if len(means) >= 3:
        increasing = all(means[i] <= means[i + 1] + 1e-6 for i in range(len(means) - 1))
        if increasing:
            interpretation = "calibration_monotonic_healthy"
        elif means[-1] < means[0] - 0.01:
            interpretation = "calibration_inverted"
        else:
            interpretation = "calibration_flat_or_noisy"

    return {
        "ok": True,
        "n": sum(len(v) for v in by_bucket_returns.values()),
        "by_confidence_bucket": out,
        "headline": {
            "monotonicity": interpretation,
            "n_resolved": sum(len(v) for v in by_bucket_returns.values()),
        },
    }
