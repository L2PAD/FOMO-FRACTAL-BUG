"""
fractal_runtime — Stage A-5: Fractal as truthful structural perception layer.

NOT pattern-detection.  NOT chart-drawing.  NOT bullish-by-default.

Reads the existing snapshot memory (now alive after Stage A-3) and emits
an honest structural opinion:

    - phase:       'compression' | 'rangebound' | 'expansion' | 'unavailable'
    - state:       'rangebound' | 'compression' | 'expansion' | 'mixed' | 'unavailable'
    - direction:   'WAIT' | 'LONG_BIAS' | 'SHORT_BIAS'   (very rarely the last two)
    - structure:   trend / breakoutRisk / breakdownRisk / rangeQuality

Sources (in priority order):
    1. intelligence_telemetry   per-asset, per-horizon directional opinion
    2. decision_history         per-asset decision distribution (WAIT/AVOID/LONG)
    3. engine_micro_snapshots   market-wide regime + flow_state
    4. engine_context_snapshots market-wide setup type + market_state

Rules:
    - LONG/SHORT requires multi-horizon agreement AND clean alignment in
      decision_history — never one snapshot.
    - If decision_history dominated by WAIT/AVOID → phase='compression' and
      reasons say so. No "Fractal bullish" without expansion confirmation.
    - Confidence cap by evidence count:
          evidence < 10  → max 0.20
          10 ≤ ev < 50   → max 0.38
          evidence ≥ 50  → max 0.55
    - sample-too-small → ok=false, state='unavailable', reason='insufficient_snapshot_memory'

In-memory 60s cache per symbol.
"""

from __future__ import annotations

import os
import threading
import time
from collections import Counter
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from pymongo import MongoClient


# ─── Tuning ────────────────────────────────────────────────────────────
CACHE_TTL_SEC = 60
WINDOW_HOURS = 72                  # widen vs sentiment (memory accumulates slowly)
MIN_EVIDENCE_CLEAN = 10            # below this → degraded
EVIDENCE_FOR_FULL_CONF = 50
EVIDENCE_FOR_MID_CONF = 10

# Confidence policy.
CONF_CAP_TINY = 0.20
CONF_CAP_MID = 0.38
CONF_CAP_FULL = 0.55

# Decision-history dominance thresholds.
WAIT_DOMINANCE_FOR_COMPRESSION = 0.70   # ≥70% WAIT → compression
EXPANSION_LONG_SHARE = 0.30             # ≥30% LONG decisions → possible expansion

# Bias requirements (conservative).
HORIZONS_REQUIRED_FOR_BIAS = 2          # need ≥2 horizons agreeing
BIAS_DIR_LABELS_BULL = {"MILD_BULL", "STRONG_BULL", "BULL"}
BIAS_DIR_LABELS_BEAR = {"MILD_BEAR", "STRONG_BEAR", "BEAR"}


# ─── Mongo ─────────────────────────────────────────────────────────────
_lock = threading.RLock()
_cache: Dict[str, dict] = {}
_client: Optional[MongoClient] = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db():
    global _client
    if _client is None:
        _client = MongoClient(os.environ.get("MONGO_URL"))
    return _client[os.environ.get("DB_NAME", "test_database")]


def _cutoff_naive():
    """Mongo stores `timestamp` / `createdAt` as ISO strings or naive UTC
    datetimes depending on collection.  Return a naive cutoff for safe
    comparison against both shapes."""
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=WINDOW_HOURS)


# ─── Evidence collectors ───────────────────────────────────────────────
def _collect_native_forecasts(symbol: str) -> List[dict]:
    """
    P1 · PRIMARY source — native fractal forecasts from per-scope
    collections (`{btc|eth|sol|spx|dxy}_fractal_forecasts`).

    These are produced by `fractal_forecast.native_engine` (recurrence /
    analog / regime-tagged) — NOT by Node :8003 and NOT by reading
    `decision_history`.  Source identity on every row is
    `fractal_native_v1`.

    Returns most recent forecasts (last 48h) across all horizons for
    the asset.  Empty list if none — caller will fall back to
    regime-context only, and trading_runtime classifier marks fractal
    as degraded.
    """
    sym = symbol.upper()
    col_name = f"{sym.lower()}_fractal_forecasts"
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    try:
        if col_name not in _db().list_collection_names():
            return []
        col = _db()[col_name]
        # Native rows always store createdAt as a real datetime.
        rows = list(
            col.find(
                {"createdAt": {"$gte": cutoff}, "source": "fractal_native_v1"},
                {"_id": 0},
            ).sort("createdAt", -1).limit(20)
        )
        return rows
    except Exception as e:
        # Read failure must NOT silently fabricate — return [] so
        # caller falls back honestly.
        return []


def _collect_telemetry(symbol: str) -> List[dict]:
    sym = symbol.upper()
    cutoff = _cutoff_naive()
    cutoff_iso = cutoff.isoformat()
    q = {
        "asset": sym,
        "$or": [
            {"timestamp": {"$gte": cutoff}},
            {"timestamp": {"$gte": cutoff_iso}},
        ],
    }
    try:
        return list(_db().intelligence_telemetry.find(q, {"_id": 0}).sort("timestamp", -1).limit(50))
    except Exception:
        return []


def _collect_decisions(symbol: str) -> List[dict]:
    sym = symbol.upper()
    cutoff = _cutoff_naive()
    cutoff_iso = cutoff.isoformat()
    q = {
        "asset": sym,
        "$or": [
            {"timestamp": {"$gte": cutoff}},
            {"timestamp": {"$gte": cutoff_iso}},
        ],
    }
    try:
        return list(_db().decision_history.find(q, {"_id": 0}).sort("timestamp", -1).limit(200))
    except Exception:
        return []


def _collect_global_micro() -> Optional[dict]:
    """Latest market-wide micro snapshot (regime, flow, setup)."""
    try:
        doc = _db().engine_micro_snapshots.find_one({}, {"_id": 0}, sort=[("timestamp", -1)])
        return doc
    except Exception:
        return None


def _collect_global_context() -> Optional[dict]:
    try:
        return _db().engine_context_snapshots.find_one({}, {"_id": 0}, sort=[("timestamp", -1)])
    except Exception:
        return None


# ─── Aggregation primitives ────────────────────────────────────────────
def _horizon_majority(telemetry: List[dict]) -> Dict[str, str]:
    """Latest direction per horizon for the asset."""
    seen: Dict[str, str] = {}
    for t in telemetry:                      # already sorted desc by timestamp
        h = t.get("horizon")
        if h and h not in seen:
            seen[h] = (t.get("direction") or "NEUTRAL").upper()
    return seen


def _decision_distribution(decisions: List[dict]) -> Dict[str, float]:
    if not decisions:
        return {"WAIT": 0.0, "AVOID": 0.0, "LONG": 0.0, "SHORT": 0.0}
    counts = Counter()
    for d in decisions:
        dv = (d.get("decision") or "").upper().strip()
        if dv in {"LONG", "BUY", "ENTER_LONG"}:
            counts["LONG"] += 1
        elif dv in {"SHORT", "SELL", "ENTER_SHORT"}:
            counts["SHORT"] += 1
        elif dv in {"AVOID", "BLOCK", "SUPPRESS"}:
            counts["AVOID"] += 1
        else:
            counts["WAIT"] += 1
    n = max(1, sum(counts.values()))
    return {k: round(counts.get(k, 0) / n, 3) for k in ["WAIT", "AVOID", "LONG", "SHORT"]}


def _classify_phase(dist: Dict[str, float], micro: Optional[dict]) -> str:
    """Derive phase from decision dominance + market regime."""
    wait_or_avoid = dist["WAIT"] + dist["AVOID"]
    expansion_share = dist["LONG"] + dist["SHORT"]

    regime = (micro or {}).get("regime") or ""
    regime_low = regime.lower()
    regime_status = (micro or {}).get("regime_status") or ""

    if expansion_share >= EXPANSION_LONG_SHARE:
        return "expansion"
    if wait_or_avoid >= WAIT_DOMINANCE_FOR_COMPRESSION:
        return "compression"
    if "chop" in regime_low or regime_status == "weak":
        return "rangebound"
    return "rangebound"


def _classify_state(horizons: Dict[str, str], dist: Dict[str, float], phase: str) -> str:
    """state ∈ {rangebound, compression, expansion, mixed, unavailable}."""
    if not horizons:
        return "unavailable"

    bull = sum(1 for d in horizons.values() if d in BIAS_DIR_LABELS_BULL)
    bear = sum(1 for d in horizons.values() if d in BIAS_DIR_LABELS_BEAR)
    neut = sum(1 for d in horizons.values() if d in {"NEUTRAL", "FLAT"})
    if bull > 0 and bear > 0:
        return "mixed"
    if phase == "expansion":
        return "expansion"
    if phase == "compression":
        return "compression"
    if neut == len(horizons):
        return "rangebound"
    return "rangebound"


def _classify_direction(horizons: Dict[str, str], dist: Dict[str, float]) -> str:
    """LONG/SHORT requires multi-horizon agreement AND decision evidence."""
    bull = sum(1 for d in horizons.values() if d in BIAS_DIR_LABELS_BULL)
    bear = sum(1 for d in horizons.values() if d in BIAS_DIR_LABELS_BEAR)
    if bull >= HORIZONS_REQUIRED_FOR_BIAS and dist["LONG"] >= 0.10 and bull > bear:
        return "LONG_BIAS"
    if bear >= HORIZONS_REQUIRED_FOR_BIAS and dist["SHORT"] >= 0.10 and bear > bull:
        return "SHORT_BIAS"
    return "WAIT"


def _structure(dist: Dict[str, float], micro: Optional[dict], horizons: Dict[str, str]) -> dict:
    bull_share = dist["LONG"]
    bear_share = dist["SHORT"]
    wait_share = dist["WAIT"] + dist["AVOID"]
    bull = sum(1 for d in horizons.values() if d in BIAS_DIR_LABELS_BULL)
    bear = sum(1 for d in horizons.values() if d in BIAS_DIR_LABELS_BEAR)

    if bull > bear and bull > 0:
        trend = "up_bias"
    elif bear > bull and bear > 0:
        trend = "down_bias"
    elif bull > 0 and bear > 0:
        trend = "mixed"
    else:
        trend = "neutral"

    breakout_risk = "high" if bull_share > 0.15 else ("medium" if bull_share > 0.05 else "low")
    breakdown_risk = "high" if (bear_share > 0.15 or dist["AVOID"] > 0.20) else ("medium" if (bear_share > 0.05 or dist["AVOID"] > 0.10) else "low")

    regime_conf = float((micro or {}).get("regime_confidence") or 0.0)
    if regime_conf >= 0.50:
        range_quality = "strong"
    elif regime_conf >= 0.30:
        range_quality = "normal"
    else:
        range_quality = "weak"

    return {
        "trend": trend,
        "breakoutRisk": breakout_risk,
        "breakdownRisk": breakdown_risk,
        "rangeQuality": range_quality,
    }


def _conf_cap(evidence: int) -> float:
    if evidence < MIN_EVIDENCE_CLEAN:
        return CONF_CAP_TINY
    if evidence < EVIDENCE_FOR_FULL_CONF:
        return CONF_CAP_MID
    return CONF_CAP_FULL


def _raw_confidence(telemetry: List[dict], evidence: int, horizons: Dict[str, str]) -> float:
    """Average telemetry confidence, scaled by evidence and capped per policy."""
    if not telemetry:
        return 0.0
    confs = [float(t.get("confidence") or 0.0) for t in telemetry if t.get("confidence") is not None]
    avg = sum(confs) / len(confs) if confs else 0.0
    scaled = avg * min(1.0, evidence / EVIDENCE_FOR_FULL_CONF)
    return round(min(scaled, _conf_cap(evidence)), 4)


def _reasons(dist: Dict[str, float], horizons: Dict[str, str], phase: str, evidence: int, micro: Optional[dict]) -> List[str]:
    out: List[str] = []
    wait_share = dist["WAIT"] + dist["AVOID"]
    if wait_share >= WAIT_DOMINANCE_FOR_COMPRESSION:
        out.append(f"recent decision history dominated by WAIT/AVOID ({int(wait_share*100)}%)")
    if phase == "compression":
        out.append("no confirmed expansion phase")
    bull = sum(1 for d in horizons.values() if d in BIAS_DIR_LABELS_BULL)
    bear = sum(1 for d in horizons.values() if d in BIAS_DIR_LABELS_BEAR)
    if bull > 0 and bear > 0:
        out.append(f"horizons disagree ({bull} bullish, {bear} bearish)")
    elif bull == 0 and bear == 0:
        out.append("no horizon shows directional conviction")
    if evidence < MIN_EVIDENCE_CLEAN:
        out.append(f"low evidence ({evidence}) — confidence capped")
    regime = (micro or {}).get("regime")
    if regime:
        out.append(f"market regime: {regime}")
    if not out:
        out.append("structural state pending more evidence")
    return out


# ─── Public API ────────────────────────────────────────────────────────
def _read_cached(symbol: str) -> Optional[dict]:
    with _lock:
        c = _cache.get(symbol)
        if c and time.time() - c[1] < CACHE_TTL_SEC:
            return c[0]
    return None


def _write_cached(symbol: str, rec: dict) -> None:
    with _lock:
        _cache[symbol] = (rec, time.time())


def _degraded(symbol: str, reason: str, evidence: int = 0) -> dict:
    return {
        "symbol": symbol.upper(),
        "ok": False,
        "state": "unavailable",
        "direction": "WAIT",
        "confidence": 0.0,
        "degraded": True,
        "phase": "unavailable",
        "structure": {
            "trend": "neutral", "breakoutRisk": "low",
            "breakdownRisk": "low", "rangeQuality": "weak",
        },
        "evidence": {"snapshots": 0, "microSnapshots": 0, "decisionHistory": 0, "telemetry": 0},
        "reasons": [reason],
        "source": "snapshot_memory",
        "asOf": _now_iso(),
    }


def runtime(symbol: str) -> dict:
    sym = (symbol or "").upper().strip()
    if not sym:
        return _degraded("", "empty_symbol")

    cached = _read_cached(sym)
    if cached is not None:
        return cached

    # ── P1 · PRIMARY source: native fractal forecasts ─────────────
    native_rows = _collect_native_forecasts(sym)
    micro = _collect_global_micro()
    ctx = _collect_global_context()

    if native_rows:
        # We have a fresh native forecast (≤ 48h).  Build the runtime
        # output FROM THAT.  decision_history / intelligence_telemetry
        # are read ONLY as historical comparison context — never as the
        # source of direction or confidence.
        # Pick the dominant horizon: prefer 30D as the headline view,
        # fall back to the freshest row.
        by_horizon = {r.get("horizon"): r for r in native_rows}
        headline = by_horizon.get("30D") or by_horizon.get("7D") or native_rows[0]
        native_dir = (headline.get("direction") or "NEUTRAL").upper()
        # Map native UP/DOWN/NEUTRAL → bias tokens
        bias = "WAIT"
        if native_dir == "UP":
            bias = "LONG_BIAS"
        elif native_dir == "DOWN":
            bias = "SHORT_BIAS"
        confidence = float(headline.get("confidence") or 0.0)
        regime = (headline.get("nativeMeta") or {}).get("regime") or {}

        # Multi-horizon consensus: how many horizons agree with headline
        agreeing = 0
        opposing = 0
        for r in native_rows:
            d = (r.get("direction") or "NEUTRAL").upper()
            if d == native_dir and d != "NEUTRAL":
                agreeing += 1
            elif d != "NEUTRAL" and d != native_dir:
                opposing += 1
        # If multi-horizon consensus is split (more opposing than
        # agreeing), demote bias to WAIT — fractal speaks honestly only
        # when horizons echo each other.
        if opposing > agreeing and native_dir != "NEUTRAL":
            bias = "WAIT"
            native_dir = "MIXED"

        reasons = []
        analog_count = int((headline.get("nativeMeta") or {}).get("analogCount") or 0)
        avg_sim = float((headline.get("nativeMeta") or {}).get("avgSimilarity") or 0.0)
        agree_share = float((headline.get("nativeMeta") or {}).get("agreeShare") or 0.0)
        reasons.append(
            f"native fractal v1: {native_dir} from {analog_count} historical analogs "
            f"(avg sim {avg_sim:.2f}, agreement {int(agree_share*100)}%)"
        )
        reasons.append(
            f"macro regime: {regime.get('spxBucket','unknown')} · DXY trend {regime.get('dxyTrend',0)}"
        )
        if regime.get("matchUsed"):
            reasons.append("regime-filtered analogs (current macro regime matched)")
        else:
            reasons.append("regime-unfiltered analogs (insufficient regime matches)")
        if opposing and not (opposing > agreeing):
            reasons.append(f"horizons mostly aligned ({agreeing} agree / {opposing} opposing)")
        if native_dir == "MIXED":
            reasons.append("horizons disagree — fractal abstains until they align")

        # Structure block (semantic, not TA): regime-based interpretation only.
        structure = {
            "trend":         "up_bias" if native_dir == "UP" else ("down_bias" if native_dir == "DOWN" else "neutral"),
            "breakoutRisk":  "high" if (native_dir == "UP" and confidence > 0.4) else "low",
            "breakdownRisk": "high" if (native_dir == "DOWN" and confidence > 0.4) else "low",
            "rangeQuality":  "strong" if regime.get("matchUsed") else "normal",
        }

        # Phase from horizon consensus
        if agreeing >= 3 and opposing == 0:
            phase = "expansion"
        elif agreeing == opposing and agreeing > 0:
            phase = "mixed"
        elif agreeing == 0 and opposing == 0:
            phase = "compression"
        else:
            phase = "rangebound"

        # decision_history is consulted ONLY for historical comparison
        # context — never to drive direction or confidence.
        try:
            n_dec = _db().decision_history.count_documents({"asset": sym})
        except Exception:
            n_dec = 0
        try:
            n_tel = _db().intelligence_telemetry.count_documents({"asset": sym})
        except Exception:
            n_tel = 0

        rec = {
            "symbol":      sym,
            "ok":          True,
            "state":       "active" if native_dir != "MIXED" else "mixed",
            "direction":   bias,
            "confidence":  round(confidence, 4),
            "phase":       phase,
            "structure":   structure,
            "evidence": {
                "nativeForecasts":  len(native_rows),
                "horizonsAgreeing": agreeing,
                "horizonsOpposing": opposing,
                "decisionHistory":  n_dec,   # context only — NOT a driver
                "telemetry":        n_tel,   # context only — NOT a driver
            },
            "horizons": {
                r.get("horizon"): {
                    "direction":      r.get("direction"),
                    "confidence":     r.get("confidence"),
                    "expectedReturn": r.get("expectedReturn"),
                    "analogCount":    (r.get("nativeMeta") or {}).get("analogCount"),
                    "agreeShare":     (r.get("nativeMeta") or {}).get("agreeShare"),
                }
                for r in native_rows if r.get("horizon")
            },
            "decisionDistribution": {},   # P1: not used as fractal source
            "reasons":              reasons,
            "marketContext": {
                "regime":       regime.get("spxBucket"),
                "regimeStatus": "matched" if regime.get("matchUsed") else "unmatched",
                "dxyTrend":     regime.get("dxyTrend"),
            },
            "degraded":     False,
            "source":       "fractal_native_v1",
            "asOf":         _now_iso(),
            "modelVersion": headline.get("modelVersion", "fractal_native_v1"),
        }
        _write_cached(sym, rec)
        return rec

    # ── No native forecast: fall back to HONEST degraded state ───
    # We deliberately do NOT use decision_history as a direction
    # source (that's the circularity trap the user explicitly closed).
    # We surface a regime-only context if available, but the module
    # remains degraded so trading_runtime marks it as abstaining.
    try:
        n_dec = _db().decision_history.count_documents({"asset": sym})
    except Exception:
        n_dec = 0
    try:
        n_tel = _db().intelligence_telemetry.count_documents({"asset": sym})
    except Exception:
        n_tel = 0

    rec = _degraded(sym, "no_native_fractal_forecast_in_48h", evidence=0)
    rec["evidence"] = {
        "nativeForecasts":  0,
        "horizonsAgreeing": 0,
        "horizonsOpposing": 0,
        "decisionHistory":  n_dec,   # context, not source
        "telemetry":        n_tel,   # context, not source
    }
    rec["marketContext"] = {
        "regime":       (micro or {}).get("regime"),
        "regimeStatus": (micro or {}).get("regime_status"),
        "marketState":  (ctx or {}).get("market_state"),
    }
    rec["source"] = "fractal_unavailable_no_native_v1"
    _write_cached(sym, rec)
    return rec


def runtime_many(symbols: List[str]) -> Dict[str, dict]:
    return {s.upper(): runtime(s) for s in symbols}


def service_health() -> dict:
    db = _db()
    try:
        n_ctx = db.engine_context_snapshots.count_documents({})
        n_micro = db.engine_micro_snapshots.count_documents({})
        n_tel = db.intelligence_telemetry.count_documents({})
        n_dec = db.decision_history.count_documents({})
        symbols = sorted(set(db.intelligence_telemetry.distinct("asset") + db.decision_history.distinct("asset")))
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    return {
        "ok": (n_ctx + n_micro + n_tel + n_dec) > 0,
        "windowHours": WINDOW_HOURS,
        "evidenceCounts": {
            "contextSnapshots": n_ctx,
            "microSnapshots": n_micro,
            "telemetry": n_tel,
            "decisionHistory": n_dec,
        },
        "symbolsWithMemory": symbols,
        "minEvidenceForClean": MIN_EVIDENCE_CLEAN,
        "cacheTtlSec": CACHE_TTL_SEC,
        "source": "snapshot_memory",
        "asOf": _now_iso(),
    }


def as_miniapp_module(fr: dict) -> dict:
    """Adapt fractal runtime → structure.modules item shape."""
    if not fr.get("ok"):
        reason = (fr.get("reasons") or ["no data"])[0] if fr.get("reasons") else "no data"
        return {
            "module": "Fractal",
            "direction": "Neutral",
            "confidence": 0.0,
            "insight": f"Fractal unavailable — {reason}",
        }
    dir_map = {"LONG_BIAS": "Bullish", "SHORT_BIAS": "Bearish", "WAIT": "Neutral"}
    bits = []
    bits.append(f"Phase: {fr['phase']}")
    s = fr.get("structure") or {}
    if s.get("rangeQuality"):
        bits.append(f"Range quality: {s['rangeQuality']}")
    if s.get("trend") and s["trend"] != "neutral":
        bits.append(f"Trend: {s['trend']}")
    return {
        "module": "Fractal",
        "direction": dir_map.get(fr["direction"], "Neutral"),
        "confidence": float(fr["confidence"]),
        "insight": " · ".join(bits),
    }



# ═══════════════════════════════════════════════════════════════════════
# Phase D Pass 2A — Canonical adapter (Unified Runtime Contract)
# ═══════════════════════════════════════════════════════════════════════
# PURE: never calls runtime(), never touches DB/network, never recomputes.
# Only normalizes a pre-computed fractal record into a CognitionSnapshot.


def _fractal_reason_to_token(raw):
    """
    Fractal `reasons` are dynamically-templated (e.g. "low evidence (12) —
    confidence capped"). Map the stable prefixes to snake_case tokens.
    """
    if raw is None:
        return None
    s = str(raw).strip().lower()
    # Order matters: most-specific prefix first.
    if "low evidence" in s and "confidence capped" in s:
        return "evidence_capped"
    if "no confirmed expansion phase" in s:
        return "no_expansion_phase"
    if "horizons disagree" in s:
        return "horizons_disagree"
    if "no horizon shows directional conviction" in s:
        return "no_horizon_conviction"
    if "structural state pending more evidence" in s:
        return "awaiting_evidence"
    if "recent decision history dominated by wait/avoid" in s:
        return "decisions_dominated_by_wait"
    if "market regime:" in s:
        # Extract the regime tag, e.g. 'market regime: expansion' → 'regime_expansion'
        tail = s.split("market regime:", 1)[1].strip()
        tail = tail.split()[0] if tail else ""
        tail = "".join(c if c.isalnum() else "_" for c in tail).strip("_")
        return f"regime_{tail}" if tail else "regime_unknown"
    # Known degraded `reason` keys
    if s in (
        "empty_symbol",
        "insufficient_snapshot_memory",
        "unsupported_symbol",
    ):
        return s
    return None


def _fractal_reasons_to_tokens(raw_reasons):
    if not raw_reasons:
        return []
    out = []
    for r in raw_reasons:
        tok = _fractal_reason_to_token(r)
        if tok and tok not in out:
            out.append(tok)
    return out


def _fractal_canonical_direction(direction_raw):
    m = {"LONG_BIAS": "long", "SHORT_BIAS": "short", "WAIT": "neutral"}
    return m.get(str(direction_raw or "").upper(), "neutral")


def _fractal_canonical_state(payload):
    """
      ok=False                          → 'insufficient' (snapshot memory empty)
                                          or 'degraded' (unknown error)
      ok=True, direction='WAIT'         → 'wait'
      ok=True, direction in LONG/SHORT  → 'active'
    """
    if not payload.get("ok"):
        reasons = payload.get("reasons") or []
        first = str(reasons[0]).lower() if reasons else ""
        if first in ("insufficient_snapshot_memory", "empty_symbol", "unsupported_symbol"):
            return "insufficient"
        return "degraded"
    direction = str(payload.get("direction") or "").upper()
    if direction == "WAIT":
        return "wait"
    if direction in ("LONG_BIAS", "SHORT_BIAS"):
        return "active"
    return "wait"


def canonical(payload):
    """
    Adapt a raw fractal `runtime(symbol)` result to a CognitionSnapshot.

    Pure: no DB, no network, no recomputation. The caller is responsible
    for obtaining `payload` via the established read path.
    """
    from services.runtime_contract import (
        CognitionSnapshot, make_insufficient,
    )

    if not isinstance(payload, dict) or not payload:
        return make_insufficient(
            module="fractal",
            source="snapshot_memory",
            reasons=("missing_fractal_payload",),
        )

    source = str(payload.get("source") or "snapshot_memory").strip().lower()
    updated_at = payload.get("asOf")

    state = _fractal_canonical_state(payload)

    if state in ("insufficient", "degraded"):
        reasons = payload.get("reasons") or []
        reason_tokens = _fractal_reasons_to_tokens(reasons)
        if not reason_tokens:
            reason_tokens = ["fractal_unavailable"]
        return CognitionSnapshot.build(
            module="fractal",
            source=source,
            state=state,
            reasons=reason_tokens,
            degraded=bool(payload.get("degraded")) or state == "degraded",
            updatedAt=updated_at,
        )

    direction = _fractal_canonical_direction(payload.get("direction"))
    confidence = payload.get("confidence")
    reasons = _fractal_reasons_to_tokens(payload.get("reasons") or [])
    if not reasons:
        reasons = ["fractal_reasons_unmapped"]

    return CognitionSnapshot.build(
        module="fractal",
        source=source,
        state=state,
        direction=direction,
        confidence=confidence,
        reasons=reasons,
        degraded=bool(payload.get("degraded")),
        updatedAt=updated_at,
    )
