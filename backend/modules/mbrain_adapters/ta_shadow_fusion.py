"""
TA Shadow Fusion — Sprint 3 / Phase A
======================================

Computes a *parallel* MBrain decision in which the new TA-Terminal adapter
participates, but DOES NOT modify the production pipeline. Only telemetry
is written to `mbrain_shadow_eval` so we can later quantify whether
adding the 5-th intelligence ring would help, hurt, or merely be noisy.

Hard rules:
  * No mutation of legacy `forecasts`, `*_forecasts`, `predictions`, etc.
  * No call into `forecast/system/aggregator_v1` — we accept the legacy
    decision as input (`legacy_bias`, `legacy_confidence`) and only ADD
    the TA component on top.
  * Write-once, read-only collection — the legacy mind never reads it.
  * Failure-tolerant: if either side is missing the eval is still saved
    with `ok=False` so we can monitor adapter availability over time.

Output envelope (one row per evaluation, stored in `mbrain_shadow_eval`):

    {
        "ts":             ISO-8601,
        "asset":          "BTC",
        "horizon":        "7D",

        "legacy": {
            "bias":       "bullish",
            "signal":     0.42,
            "confidence": 0.68,
            "source":     "legacy_mbrain"
        },
        "ta": {
            "bias":       "bearish",
            "signal":     -0.31,
            "confidence": 0.55,
            "weight":     0.18,
            "source":     "ta_terminal"
        },

        "shadow_fusion": {
            "bias":       "neutral",
            "signal":     0.34,
            "confidence": 0.62
        },

        "metrics": {
            "agreement_score":     0.0..1.0,
            "directional_delta":  -1.0..+1.0,
            "confidence_shift":   -1.0..+1.0,
            "divergence":          bool,
            "ta_override":         bool,    # shadow.bias != legacy.bias
            "ta_active":           bool     # TA adapter returned ok
        },

        "ok":  true,
        "err": null
    }
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

from pymongo import MongoClient, DESCENDING

from .trading_terminal_adapter import get_signal as ta_get_signal

logger = logging.getLogger("mbrain_adapters.ta_shadow_fusion")

SHADOW_COLLECTION = "mbrain_shadow_eval"
DEFAULT_DB = os.environ.get("DB_NAME", "intelligence_engine")

# Legacy bias → numeric signal (-1..+1). Mirrors trading_terminal_adapter.
_BIAS_NUM = {"bullish": +1.0, "bearish": -1.0, "neutral": 0.0,
             "long": +1.0, "short": -1.0, "buy": +1.0, "sell": -1.0,
             "up": +1.0, "down": -1.0}


# ──────────────────────────────────────────────────────────────────────────
# Storage
# ──────────────────────────────────────────────────────────────────────────

def _db():
    """Returns the FOMO DB handle (NOT trading_os — air-gap)."""
    return MongoClient(os.environ["MONGO_URL"])[DEFAULT_DB]


def _ensure_indexes() -> None:
    try:
        col = _db()[SHADOW_COLLECTION]
        col.create_index([("ts", DESCENDING)])
        col.create_index([("asset", 1), ("horizon", 1), ("ts", DESCENDING)])
    except Exception as exc:  # pragma: no cover
        logger.debug("ta_shadow_fusion: index ensure failed: %s", exc)


def save_shadow_eval(record: dict) -> Optional[str]:
    """Persist one shadow evaluation row. Returns inserted _id or None."""
    try:
        col = _db()[SHADOW_COLLECTION]
        res = col.insert_one(dict(record))
        return str(res.inserted_id)
    except Exception as exc:
        logger.warning("ta_shadow_fusion: save failed: %s", exc)
        return None


# ──────────────────────────────────────────────────────────────────────────
# Math helpers
# ──────────────────────────────────────────────────────────────────────────

def _norm_bias(b: Optional[str]) -> str:
    if not b:
        return "neutral"
    s = str(b).lower().strip()
    if s in {"long", "buy", "bullish", "up", "+1", "1"}:
        return "bullish"
    if s in {"short", "sell", "bearish", "down", "-1"}:
        return "bearish"
    return "neutral"


def _bias_to_signal(b: Optional[str]) -> float:
    if not b:
        return 0.0
    return _BIAS_NUM.get(str(b).lower().strip(), 0.0)


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return lo
    if v != v:
        return lo
    return max(lo, min(hi, v))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ──────────────────────────────────────────────────────────────────────────
# Fusion math (shadow only — never affects production)
# ──────────────────────────────────────────────────────────────────────────

def _shadow_fuse(
    legacy_signal: float,
    legacy_conf: float,
    ta_signal: float,
    ta_conf: float,
    ta_weight: float,
) -> dict:
    """
    Simple convex combination:
        legacy_share  = 1 - ta_weight
        fused_signal  = legacy_share * legacy_signal + ta_weight * ta_signal
        fused_conf    = legacy_share * legacy_conf   + ta_weight * ta_conf

    Where weights satisfy: legacy_share + ta_weight = 1.00 (ИНВ-5 honored).
    """
    ta_w = _clamp(ta_weight, 0.0, 1.0)
    legacy_share = 1.0 - ta_w

    fused_signal = legacy_share * legacy_signal + ta_w * ta_signal
    fused_conf = legacy_share * legacy_conf + ta_w * ta_conf
    fused_signal = max(-1.0, min(1.0, fused_signal))
    fused_conf = _clamp(fused_conf)

    bias = ("bullish" if fused_signal > 0.10 else
            "bearish" if fused_signal < -0.10 else "neutral")

    return {
        "bias":       bias,
        "signal":     round(fused_signal, 4),
        "confidence": round(fused_conf, 4),
    }


def _agreement(legacy_bias: str, ta_bias: str, legacy_sig: float, ta_sig: float) -> float:
    """
    Agreement score in [0, 1]:
        - same direction (both bullish or both bearish) → 1.0
        - one neutral, other directional               → 0.5
        - opposite directions                          → 0.0 (or proportional
          to magnitude product so weak disagreements aren't max-distance)
    """
    if legacy_bias == ta_bias:
        return 1.0
    if "neutral" in (legacy_bias, ta_bias):
        return 0.5
    # Opposite directions — distance proportional to magnitude.
    return max(0.0, 1.0 - min(1.0, abs(legacy_sig - ta_sig) / 2.0))


# ──────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────

def evaluate_shadow(
    asset: str,
    horizon: str = "7D",
    *,
    legacy_bias: Optional[str] = None,
    legacy_confidence: Optional[float] = None,
    legacy_signal: Optional[float] = None,
    persist: bool = True,
) -> dict:
    """
    Build a shadow evaluation row for `(asset, horizon)`.

    Caller is expected to pass the production legacy decision via
    `legacy_bias`/`legacy_confidence`/`legacy_signal`. If `legacy_signal`
    is omitted it is inferred from `legacy_bias × legacy_confidence`.
    If both bias and signal are missing we fall back to neutral / 0.0.
    """
    asset_u = (asset or "BTC").upper()
    horizon_u = horizon or "7D"

    # ── Legacy (input) ────────────────────────────────────────────────
    leg_bias = _norm_bias(legacy_bias) if legacy_bias else "neutral"
    leg_conf = _clamp(legacy_confidence) if legacy_confidence is not None else 0.0
    if legacy_signal is not None:
        leg_sig = max(-1.0, min(1.0, float(legacy_signal)))
    else:
        leg_sig = _bias_to_signal(leg_bias) * leg_conf

    # ── TA component (live HTTP via gateway) ──────────────────────────
    try:
        ta_env = ta_get_signal(asset_u, horizon_u)
    except Exception as exc:  # pragma: no cover
        logger.exception("ta_shadow_fusion: ta_get_signal raised")
        ta_env = {
            "ok": False, "error": str(exc), "bias": "neutral",
            "signal": 0.0, "confidence": 0.0, "weight": 0.0,
        }

    ta_active = bool(ta_env.get("ok"))
    ta_bias = _norm_bias(ta_env.get("bias"))
    ta_sig = float(ta_env.get("signal") or 0.0)
    ta_conf = _clamp(ta_env.get("confidence", 0.0))
    ta_weight = _clamp(ta_env.get("weight", 0.0))

    # ── Shadow fusion (would-be MBrain v2 output) ─────────────────────
    if ta_active:
        shadow = _shadow_fuse(leg_sig, leg_conf, ta_sig, ta_conf, ta_weight)
    else:
        # If TA is down, shadow degrades to legacy unchanged — we still
        # record the row so we can later see how often TA was unavailable.
        shadow = {"bias": leg_bias, "signal": round(leg_sig, 4), "confidence": round(leg_conf, 4)}

    # ── Telemetry metrics ─────────────────────────────────────────────
    metrics = {
        "agreement_score":  round(_agreement(leg_bias, ta_bias, leg_sig, ta_sig), 4),
        "directional_delta": round(shadow["signal"] - leg_sig, 4),
        "confidence_shift":  round(shadow["confidence"] - leg_conf, 4),
        "divergence":        leg_bias != ta_bias and "neutral" not in (leg_bias, ta_bias),
        "ta_override":       shadow["bias"] != leg_bias,
        "ta_active":         ta_active,
    }

    record = {
        "ts":      _utc_now(),
        "asset":   asset_u,
        "horizon": horizon_u,

        "legacy": {
            "bias":       leg_bias,
            "signal":     round(leg_sig, 4),
            "confidence": round(leg_conf, 4),
            "source":     "legacy_mbrain",
        },
        "ta": {
            "bias":       ta_bias,
            "signal":     round(ta_sig, 4),
            "confidence": round(ta_conf, 4),
            "weight":     round(ta_weight, 4),
            "source":     "ta_terminal",
            "ok":         ta_active,
            "error":      ta_env.get("error"),
            # Regime is what hypothesis component reports — pulled to top
            # level so observability queries can group by it cheaply.
            "regime":     ((ta_env.get("components") or {}).get("hypothesis") or {}).get("regime"),
        },

        "shadow_fusion": shadow,
        "metrics":       metrics,

        "ok":  True,
        "err": None,
    }

    if persist:
        rid = save_shadow_eval(record)
        if rid:
            record["_id"] = rid

    return record


def fetch_recent(asset: Optional[str] = None, limit: int = 50) -> list[dict]:
    try:
        q: dict = {}
        if asset:
            q["asset"] = asset.upper()
        col = _db()[SHADOW_COLLECTION]
        rows = list(col.find(q, {"_id": 0}).sort("ts", DESCENDING).limit(int(limit)))
        return rows
    except Exception as exc:
        logger.warning("ta_shadow_fusion: fetch_recent failed: %s", exc)
        return []


def summary(window_n: int = 200) -> dict:
    """Aggregate basic stats over the most recent `window_n` evaluations."""
    try:
        col = _db()[SHADOW_COLLECTION]
        rows = list(col.find({}, {"_id": 0}).sort("ts", DESCENDING).limit(int(window_n)))
    except Exception as exc:
        return {"ok": False, "error": str(exc), "n": 0}

    if not rows:
        return {"ok": True, "n": 0, "window": window_n}

    n = len(rows)

    def avg(key_path: str) -> float:
        vals = []
        for r in rows:
            cur = r
            for k in key_path.split("."):
                cur = (cur or {}).get(k) if isinstance(cur, dict) else None
                if cur is None:
                    break
            if isinstance(cur, (int, float)):
                vals.append(float(cur))
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    def share(predicate) -> float:
        c = sum(1 for r in rows if predicate(r))
        return round(c / n, 4) if n else 0.0

    overrides = share(lambda r: r.get("metrics", {}).get("ta_override") is True)
    divergence = share(lambda r: r.get("metrics", {}).get("divergence") is True)
    ta_uptime = share(lambda r: r.get("metrics", {}).get("ta_active") is True)

    return {
        "ok": True,
        "n": n,
        "window": window_n,
        "first_ts": rows[-1].get("ts"),
        "last_ts":  rows[0].get("ts"),
        "ta_uptime_share":      ta_uptime,
        "ta_override_share":    overrides,
        "divergence_share":     divergence,
        "avg_agreement":        avg("metrics.agreement_score"),
        "avg_directional_delta":avg("metrics.directional_delta"),
        "avg_confidence_shift": avg("metrics.confidence_shift"),
        "avg_legacy_confidence":avg("legacy.confidence"),
        "avg_ta_confidence":    avg("ta.confidence"),
        "avg_shadow_confidence":avg("shadow_fusion.confidence"),
    }


# ──────────────────────────────────────────────────────────────────────────
# Phase B — Observability layer (breakdowns, timelines, divergence feed)
# ──────────────────────────────────────────────────────────────────────────

def _bucket_kpis(rows: list[dict]) -> dict:
    """Compute KPI block for a single bucket of rows."""
    n = len(rows)
    if n == 0:
        return {"n": 0}

    def avg(path: str, default: float = 0.0) -> float:
        vals = []
        for r in rows:
            cur: object = r
            for k in path.split("."):
                cur = cur.get(k) if isinstance(cur, dict) else None
                if cur is None:
                    break
            if isinstance(cur, (int, float)):
                vals.append(float(cur))
        return round(sum(vals) / len(vals), 4) if vals else default

    def share(pred) -> float:
        c = sum(1 for r in rows if pred(r))
        return round(c / n, 4)

    return {
        "n": n,
        "ta_uptime_share":       share(lambda r: (r.get("metrics") or {}).get("ta_active") is True),
        "ta_override_share":     share(lambda r: (r.get("metrics") or {}).get("ta_override") is True),
        "divergence_share":      share(lambda r: (r.get("metrics") or {}).get("divergence") is True),
        "avg_agreement":         avg("metrics.agreement_score"),
        "avg_directional_delta": avg("metrics.directional_delta"),
        "avg_confidence_shift":  avg("metrics.confidence_shift"),
        "avg_legacy_confidence": avg("legacy.confidence"),
        "avg_ta_confidence":     avg("ta.confidence"),
        "avg_shadow_confidence": avg("shadow_fusion.confidence"),
    }


def breakdown(dim: str, window_n: int = 500) -> dict:
    """
    Group recent shadow evals by `dim` and emit per-group KPI block.
    Supported dims: "horizon", "asset", "regime", "ta_bias".
    """
    if dim not in {"horizon", "asset", "regime", "ta_bias"}:
        return {"ok": False, "error": f"unsupported dim '{dim}'"}
    try:
        col = _db()[SHADOW_COLLECTION]
        rows = list(col.find({}, {"_id": 0}).sort("ts", DESCENDING).limit(int(window_n)))
    except Exception as exc:
        return {"ok": False, "error": str(exc), "groups": {}}

    groups: dict[str, list] = {}
    for r in rows:
        if dim == "horizon":
            key = r.get("horizon") or "unknown"
        elif dim == "asset":
            key = r.get("asset") or "unknown"
        elif dim == "regime":
            key = ((r.get("ta") or {}).get("regime")) or "unknown"
        else:  # ta_bias
            key = ((r.get("ta") or {}).get("bias")) or "unknown"
        groups.setdefault(str(key), []).append(r)

    return {
        "ok":    True,
        "dim":   dim,
        "n":     len(rows),
        "window": window_n,
        "groups": {k: _bucket_kpis(v) for k, v in groups.items()},
    }


def timeline(window_n: int = 500, bucket_minutes: int = 60) -> dict:
    """
    Time-series of agreement / divergence / override aggregated into
    `bucket_minutes`-wide buckets. Useful for the dashboard chart.
    """
    try:
        col = _db()[SHADOW_COLLECTION]
        rows = list(col.find({}, {"_id": 0}).sort("ts", DESCENDING).limit(int(window_n)))
    except Exception as exc:
        return {"ok": False, "error": str(exc), "buckets": []}

    if not rows:
        return {"ok": True, "buckets": [], "n": 0}

    bucket_seconds = max(60, int(bucket_minutes) * 60)
    by_bucket: dict[int, list] = {}
    for r in rows:
        ts = r.get("ts")
        if not ts:
            continue
        try:
            t = datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()
        except Exception:
            continue
        b = int(t // bucket_seconds) * bucket_seconds
        by_bucket.setdefault(b, []).append(r)

    out = []
    for b in sorted(by_bucket):
        kpi = _bucket_kpis(by_bucket[b])
        out.append({
            "ts":  datetime.fromtimestamp(b, tz=timezone.utc).isoformat(),
            **kpi,
        })

    return {"ok": True, "n": len(rows), "buckets": out, "bucket_minutes": bucket_minutes}


def divergences(limit: int = 50, only_active: bool = True) -> list[dict]:
    """Recent rows where legacy and TA disagree (divergence=True)."""
    try:
        col = _db()[SHADOW_COLLECTION]
        q: dict = {"metrics.divergence": True}
        if only_active:
            q["metrics.ta_active"] = True
        rows = list(col.find(q, {"_id": 0}).sort("ts", DESCENDING).limit(int(limit)))
        return rows
    except Exception as exc:
        logger.warning("ta_shadow_fusion: divergences failed: %s", exc)
        return []


# ──────────────────────────────────────────────────────────────────────────
# Rolling time windows + histograms (Phase B operational metrics)
# ──────────────────────────────────────────────────────────────────────────

def _rows_since(minutes: int, hard_cap: int = 20000) -> list[dict]:
    """Fetch all rows newer than `minutes` ago (capped at hard_cap)."""
    try:
        col = _db()[SHADOW_COLLECTION]
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        cutoff_iso = cutoff.isoformat()
        rows = list(
            col.find({"ts": {"$gte": cutoff_iso}}, {"_id": 0})
               .sort("ts", DESCENDING)
               .limit(int(hard_cap))
        )
        return rows
    except Exception as exc:
        logger.warning("ta_shadow_fusion: _rows_since failed: %s", exc)
        return []


def summary_rolling() -> dict:
    """
    Return KPIs in 4 rolling windows: 1h / 24h / 7d / all-time.
    All-time is capped at 20k rows for safety.
    """
    out = {"ok": True, "windows": {}}

    # All-time (last 20k rows by ts desc)
    try:
        col = _db()[SHADOW_COLLECTION]
        all_rows = list(col.find({}, {"_id": 0}).sort("ts", DESCENDING).limit(20000))
    except Exception as exc:
        return {"ok": False, "error": str(exc), "windows": {}}

    out["windows"]["all"] = _bucket_kpis(all_rows)
    out["windows"]["1h"] = _bucket_kpis(_rows_since(60))
    out["windows"]["24h"] = _bucket_kpis(_rows_since(60 * 24))
    out["windows"]["7d"] = _bucket_kpis(_rows_since(60 * 24 * 7))

    # Earliest/latest stamps for the dashboard chrome.
    if all_rows:
        out["first_ts"] = all_rows[-1].get("ts")
        out["last_ts"] = all_rows[0].get("ts")

    return out


def histogram(metric: str = "confidence_shift", bins: int = 21, window_n: int = 2000) -> dict:
    """
    Compute a histogram for a numeric metric across recent rows.
    Supported metrics:
        confidence_shift   ∈ [-1, +1]
        directional_delta  ∈ [-1, +1]
        agreement_score    ∈ [ 0,  1]
        ta_confidence      ∈ [ 0,  1]   (alias for ta.confidence)
        legacy_confidence  ∈ [ 0,  1]
        shadow_confidence  ∈ [ 0,  1]
    """
    paths = {
        "confidence_shift":  ("metrics.confidence_shift",  -1.0, +1.0),
        "directional_delta": ("metrics.directional_delta", -1.0, +1.0),
        "agreement_score":   ("metrics.agreement_score",    0.0,  1.0),
        "ta_confidence":     ("ta.confidence",              0.0,  1.0),
        "legacy_confidence": ("legacy.confidence",          0.0,  1.0),
        "shadow_confidence": ("shadow_fusion.confidence",   0.0,  1.0),
    }
    if metric not in paths:
        return {"ok": False, "error": f"unsupported metric '{metric}'"}
    path, lo, hi = paths[metric]

    try:
        col = _db()[SHADOW_COLLECTION]
        rows = list(col.find({}, {"_id": 0}).sort("ts", DESCENDING).limit(int(window_n)))
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    bins_n = max(5, min(int(bins), 101))
    edges = [lo + (hi - lo) * i / bins_n for i in range(bins_n + 1)]
    counts = [0] * bins_n
    n_used = 0
    n_nan = 0
    sum_v = 0.0

    for r in rows:
        cur = r
        for k in path.split("."):
            cur = cur.get(k) if isinstance(cur, dict) else None
            if cur is None:
                break
        if not isinstance(cur, (int, float)):
            n_nan += 1
            continue
        v = float(cur)
        if v != v:  # NaN
            n_nan += 1
            continue
        n_used += 1
        sum_v += v
        # Find bin (clamp to last bin on right edge)
        idx = int((v - lo) / (hi - lo) * bins_n) if hi > lo else 0
        if idx < 0:
            idx = 0
        if idx >= bins_n:
            idx = bins_n - 1
        counts[idx] += 1

    return {
        "ok": True,
        "metric": metric,
        "lo": lo,
        "hi": hi,
        "bins": bins_n,
        "edges": [round(e, 4) for e in edges],
        "counts": counts,
        "n": n_used,
        "n_nan": n_nan,
        "mean": round(sum_v / n_used, 4) if n_used else 0.0,
    }


def influence_pairs(window_n: int = 500) -> dict:
    """
    Returns (legacy_conf, shadow_conf, ta_active, ts) pairs so the dashboard
    can render a scatter and detect TA confidence inflation.
    """
    try:
        col = _db()[SHADOW_COLLECTION]
        rows = list(col.find({}, {"_id": 0}).sort("ts", DESCENDING).limit(int(window_n)))
    except Exception as exc:
        return {"ok": False, "error": str(exc), "pairs": []}

    pairs = []
    for r in rows:
        leg = (r.get("legacy") or {}).get("confidence") or 0.0
        sh = (r.get("shadow_fusion") or {}).get("confidence") or 0.0
        pairs.append({
            "ts": r.get("ts"),
            "asset": r.get("asset"),
            "horizon": r.get("horizon"),
            "legacy_confidence": float(leg),
            "shadow_confidence": float(sh),
            "ta_active": bool((r.get("metrics") or {}).get("ta_active")),
        })
    return {"ok": True, "n": len(pairs), "pairs": pairs}


# Initial index ensure on first import (best-effort).
_ensure_indexes()
