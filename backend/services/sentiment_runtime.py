"""
sentiment_runtime — Stage A-4: Sentiment as truthful crowd-pressure layer.

NOT an LLM summary service.  NOT a tweet-classification engine.

This service aggregates the existing `sentiment_events` collection into an
honest pressure signal that works EVEN when the LLM budget is exhausted.

Pipeline:
    sentiment_events  →  symbol filter + recency window  →
    weighted score / share / fear-euphoria  →  state + direction

Rules (suppression-friendly):
    - default: WAIT / neutral
    - sample < 5 events       → degraded, conf capped at 0.20
    - LLM-down                → ok=true, llm='unavailable_budget_exhausted'
    - LLM-down ≠ sentiment-down   (events-based score remains)
    - never invent bullish from absence of bearish
    - confidence ≤ 0.55 unless sample ≥ 10 AND alignment is clean

Schema of `sentiment_events` (observed in dev DB):
    symbol             'BTC'|'ETH'|'SOL'|'MARKET'
    source             'fear_greed_index'|'coingecko'|'cryptocompare_news'|…
    sourceType         e.g. 'index'
    sourceWeight       0..1 (per-source trust)
    weightedScore      -1..+1 (signed)
    weightedConfidence 0..1
    eventType          e.g. 'market_sentiment'
    createdAt          datetime
    raw                nested per-source payload (fear/greed value etc.)

Time window: last 24h.  In-memory 60s cache per symbol.
"""

from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from pymongo import MongoClient


# ─── Tuning ────────────────────────────────────────────────────────────
WINDOW_HOURS = 24
CACHE_TTL_SEC = 60
MIN_SAMPLE_FOR_CLEAN = 5
SAMPLE_FOR_CONF_FULL = 10

# Direction thresholds.  Score is weighted mean ∈ [-1..+1].
SCORE_NEUTRAL_BAND = 0.10
SCORE_BIAS_BAND = 0.15

# Confidence policy (suppression-friendly).
CONF_SOFT_CAP = 0.55
CONF_LOW_SAMPLE_CAP = 0.20

# Fear/Greed thresholds (from fear_greed_index raw.value 0-100).
FG_EXTREME_FEAR = 25
FG_FEAR = 45
FG_GREED = 55
FG_EXTREME_EUPHORIA = 75

# Cross-symbol weight reduction when reading 'MARKET' events for a
# specific asset (e.g. BTC).  Market context still informs but shouldn't
# dominate per-asset signal.
MARKET_CONTEXT_WEIGHT = 0.5


# ─── Mongo wiring ──────────────────────────────────────────────────────
_lock = threading.RLock()
_cache: Dict[str, dict] = {}              # symbol → (record, ts)
_client: Optional[MongoClient] = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db():
    global _client
    if _client is None:
        _client = MongoClient(os.environ.get("MONGO_URL"))
    return _client[os.environ.get("DB_NAME", "test_database")]


# ─── LLM availability probe (does NOT spend budget) ────────────────────
def _llm_status() -> str:
    """Read the most recent LLM ops log to surface budget state honestly.
    We never call the LLM here — just check the recurring err.log signal."""
    try:
        path = "/var/log/supervisor/backend.err.log"
        with open(path, "rb") as f:
            try:
                f.seek(-8000, 2)
            except OSError:
                f.seek(0)
            tail = f.read().decode(errors="replace")
        if "Budget has been exceeded" in tail or "MaxBudgetExceeded" in tail.lower():
            return "unavailable_budget_exhausted"
        if "LLM analysis error" in tail:
            return "degraded"
        return "not_used"   # this runtime is events-based; LLM isn't invoked
    except Exception:
        return "unknown"


# ─── Event fetcher ─────────────────────────────────────────────────────
def _fetch_events(symbol: str) -> List[dict]:
    """Pull events for SYMBOL in the last WINDOW_HOURS, plus MARKET events
    as global context (weight-reduced downstream)."""
    sym = (symbol or "").upper().strip()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=WINDOW_HOURS)
    # `createdAt` is stored as naive UTC string in current dev DB — strip tz for compare
    cutoff_naive = cutoff.replace(tzinfo=None)
    q = {
        "$and": [
            {"$or": [{"symbol": sym}, {"symbol": "MARKET"}]},
            {"createdAt": {"$gte": cutoff_naive}},
        ]
    }
    rows = list(_db().sentiment_events.find(q, {"_id": 0}))
    # Mark whether each row is asset-specific or MARKET so we can weight downstream.
    for r in rows:
        r["_is_market_ctx"] = (r.get("symbol") == "MARKET" and sym != "MARKET")
    return rows


# ─── Aggregation primitives ────────────────────────────────────────────
def _bucket_label(score: float) -> str:
    if score > SCORE_NEUTRAL_BAND:
        return "bullish"
    if score < -SCORE_NEUTRAL_BAND:
        return "bearish"
    return "neutral"


def _pressure_label(bullish_share: float, bearish_share: float) -> str:
    diff = bullish_share - bearish_share
    if diff > 0.20:
        return "rising"
    if diff < -0.20:
        return "falling"
    return "balanced"


def _fear_euphoria_from_events(events: List[dict]) -> str:
    """Extract latest fear_greed_index reading and classify."""
    fg = [e for e in events if e.get("source") == "fear_greed_index"]
    if not fg:
        return "unknown"
    # use latest (events are not guaranteed sorted, take by createdAt desc)
    fg.sort(key=lambda e: e.get("createdAt") or "", reverse=True)
    raw = (fg[0].get("raw") or {})
    val = raw.get("value")
    if val is None:
        cls = (raw.get("classification") or "").lower()
        if "extreme fear" in cls: return "extreme_fear"
        if "fear" in cls: return "fear"
        if "extreme greed" in cls: return "extreme_euphoria"
        if "greed" in cls: return "greed"
        return "neutral"
    try:
        v = float(val)
    except Exception:
        return "neutral"
    if v < FG_EXTREME_FEAR:    return "extreme_fear"
    if v < FG_FEAR:            return "fear"
    if v < FG_GREED:           return "neutral"
    if v < FG_EXTREME_EUPHORIA:return "greed"
    return "extreme_euphoria"


def _aggregate(events: List[dict]) -> dict:
    """Reduce events to {score, conf, shares, sample, bullish/bearish/neutral counts}."""
    if not events:
        return {
            "sample": 0,
            "score": 0.0,
            "conf": 0.0,
            "bullishShare": 0.0,
            "bearishShare": 0.0,
            "neutralShare": 0.0,
            "bullish": 0, "bearish": 0, "neutral": 0,
        }

    total_w = 0.0
    weighted_score_sum = 0.0
    conf_sum = 0.0
    bull = bear = neut = 0

    for e in events:
        s = e.get("weightedScore")
        c = e.get("weightedConfidence")
        w_src = e.get("sourceWeight") or 0.5
        if s is None or c is None:
            continue
        try:
            s = float(s); c = float(c); w_src = float(w_src)
        except Exception:
            continue
        # Clamp score to [-1, 1] in case some sources emit 0..1.
        if s > 1.0: s = 1.0
        if s < -1.0: s = -1.0
        w = w_src * c
        if e.get("_is_market_ctx"):
            w *= MARKET_CONTEXT_WEIGHT
        if w <= 0:
            continue
        total_w += w
        weighted_score_sum += s * w
        conf_sum += c
        label = _bucket_label(s)
        if label == "bullish": bull += 1
        elif label == "bearish": bear += 1
        else: neut += 1

    sample = bull + bear + neut
    score = (weighted_score_sum / total_w) if total_w > 0 else 0.0
    conf_avg = (conf_sum / sample) if sample > 0 else 0.0

    return {
        "sample": sample,
        "score": round(score, 4),
        "conf": round(conf_avg, 4),
        "bullishShare": round(bull / sample, 3) if sample else 0.0,
        "bearishShare": round(bear / sample, 3) if sample else 0.0,
        "neutralShare": round(neut / sample, 3) if sample else 0.0,
        "bullish": bull, "bearish": bear, "neutral": neut,
    }


def _direction_and_state(agg: dict) -> tuple[str, str, List[str]]:
    sample = agg["sample"]
    score = agg["score"]
    bs = agg["bullishShare"]
    br = agg["bearishShare"]
    reasons: List[str] = []

    if sample == 0:
        return "WAIT", "unavailable", ["no sentiment events in window"]
    if sample < MIN_SAMPLE_FOR_CLEAN:
        reasons.append(f"small sample ({sample} events) — no clean signal")
        return "WAIT", "neutral", reasons

    # Sample is enough.  Direction requires both score and share to agree.
    if score > SCORE_BIAS_BAND and bs > br:
        reasons.append("weighted sentiment skewed positive")
        if bs - br > 0.2:
            reasons.append("crowd share clearly bullish")
        return "LONG_BIAS", "bullish", reasons
    if score < -SCORE_BIAS_BAND and br > bs:
        reasons.append("weighted sentiment skewed negative")
        if br - bs > 0.2:
            reasons.append("crowd share clearly bearish")
        return "SHORT_BIAS", "bearish", reasons

    reasons.append("mixed sentiment — score and crowd share disagree" if (score * (bs - br) < 0) else "balanced sentiment")
    return "WAIT", "neutral", reasons


def _final_confidence(agg: dict) -> float:
    sample = agg["sample"]
    if sample == 0:
        return 0.0
    if sample < MIN_SAMPLE_FOR_CLEAN:
        return min(CONF_LOW_SAMPLE_CAP, agg["conf"])
    raw = agg["conf"] * min(1.0, sample / SAMPLE_FOR_CONF_FULL)
    return round(min(raw, CONF_SOFT_CAP), 4)


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


def runtime(symbol: str) -> dict:
    sym = (symbol or "").upper().strip()
    if not sym:
        return _degraded("", "empty_symbol")

    cached = _read_cached(sym)
    if cached is not None:
        return cached

    llm_st = _llm_status()
    try:
        events = _fetch_events(sym)
    except Exception as e:
        rec = _degraded(sym, f"db_error:{type(e).__name__}", llm=llm_st)
        _write_cached(sym, rec)
        return rec

    agg = _aggregate(events)

    if agg["sample"] == 0:
        rec = {
            "symbol": sym, "ok": False, "degraded": True,
            "state": "unavailable", "direction": "WAIT",
            "score": 0.0, "confidence": 0.0, "pressure": "balanced",
            "crowd": {"bullishShare": 0.0, "bearishShare": 0.0, "neutralShare": 0.0},
            "fearEuphoria": "unknown",
            "sample": 0,
            "reason": ["no sentiment events in 24h window"],
            "llm": llm_st,
            "source": "sentiment_events",
            "asOf": _now_iso(),
        }
        _write_cached(sym, rec)
        return rec

    direction, state, reasons = _direction_and_state(agg)
    fe = _fear_euphoria_from_events(events)
    if fe in ("fear", "extreme_fear"):
        reasons.append(f"market fear/greed: {fe}")
    elif fe in ("greed", "extreme_euphoria"):
        reasons.append(f"market fear/greed: {fe}")

    rec = {
        "symbol": sym, "ok": True,
        "state": state, "direction": direction,
        "score": agg["score"], "confidence": _final_confidence(agg),
        "pressure": _pressure_label(agg["bullishShare"], agg["bearishShare"]),
        "crowd": {
            "bullishShare": agg["bullishShare"],
            "bearishShare": agg["bearishShare"],
            "neutralShare": agg["neutralShare"],
        },
        "fearEuphoria": fe,
        "sample": agg["sample"],
        "reason": reasons,
        "llm": llm_st,
        "degraded": agg["sample"] < MIN_SAMPLE_FOR_CLEAN,
        "source": "sentiment_events",
        "asOf": _now_iso(),
    }
    _write_cached(sym, rec)
    return rec


def _degraded(symbol: str, reason: str, llm: str = "unknown") -> dict:
    return {
        "symbol": symbol.upper(),
        "ok": False, "degraded": True,
        "state": "unavailable", "direction": "WAIT",
        "score": 0.0, "confidence": 0.0, "pressure": "balanced",
        "crowd": {"bullishShare": 0.0, "bearishShare": 0.0, "neutralShare": 0.0},
        "fearEuphoria": "unknown",
        "sample": 0,
        "reason": [reason],
        "llm": llm,
        "source": "sentiment_events",
        "asOf": _now_iso(),
    }


def runtime_many(symbols: List[str]) -> Dict[str, dict]:
    return {s.upper(): runtime(s) for s in symbols}


def service_health() -> dict:
    db = _db()
    try:
        n_total = db.sentiment_events.count_documents({})
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=WINDOW_HOURS)
        n_recent = db.sentiment_events.count_documents({"createdAt": {"$gte": cutoff}})
        symbols = sorted(db.sentiment_events.distinct("symbol"))
        sources = sorted(db.sentiment_events.distinct("source"))
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    return {
        "ok": n_total > 0,
        "eventsTotal": n_total,
        "eventsInWindow": n_recent,
        "windowHours": WINDOW_HOURS,
        "symbols": symbols,
        "sources": sources,
        "cacheTtlSec": CACHE_TTL_SEC,
        "minSampleForClean": MIN_SAMPLE_FOR_CLEAN,
        "llm": _llm_status(),
        "source": "sentiment_events",
        "asOf": _now_iso(),
    }


def as_miniapp_module(srt: dict) -> dict:
    """Adapt a sentiment runtime record to the shape that
    /api/miniapp/home's `structure.modules` array consumes
    (`{module, direction, confidence, insight}`)."""
    if not srt.get("ok"):
        return {
            "module": "Sentiment",
            "direction": "Neutral",
            "confidence": 0.0,
            "insight": "Sentiment unavailable — " + (srt.get("reason") or ["no data"])[0],
        }
    dir_map = {"LONG_BIAS": "Bullish", "SHORT_BIAS": "Bearish", "WAIT": "Neutral"}
    insight_bits = []
    bs = srt["crowd"]["bullishShare"]
    br = srt["crowd"]["bearishShare"]
    insight_bits.append(f"Crowd: {int(bs*100)}% bullish / {int(br*100)}% bearish")
    fe = srt.get("fearEuphoria")
    if fe and fe not in ("unknown", "neutral"):
        insight_bits.append(f"Fear/Greed: {fe}")
    insight_bits.append(f"Pressure {srt['pressure']}")
    return {
        "module": "Sentiment",
        "direction": dir_map.get(srt["direction"], "Neutral"),
        "confidence": float(srt["confidence"]),
        "insight": " · ".join(insight_bits),
    }



# ═══════════════════════════════════════════════════════════════════════
# Phase D Pass 2A — Canonical adapter (Unified Runtime Contract)
# ═══════════════════════════════════════════════════════════════════════
# PURE: never calls runtime(), never touches DB/network, never recomputes.
# Only normalizes a pre-computed sentiment record into a CognitionSnapshot.

# Maps the small set of stable free-text reasons emitted by runtime() to
# snake_case tokens. Anything outside the map (rare) is dropped.
_SENTIMENT_REASON_TOKEN_MAP = {
    "no sentiment events in window": "no_events_in_window",
    "no sentiment events in 24h window": "no_events_24h",
    "weighted sentiment skewed positive": "weighted_positive",
    "crowd share clearly bullish": "crowd_bullish",
    "weighted sentiment skewed negative": "weighted_negative",
    "crowd share clearly bearish": "crowd_bearish",
    "mixed sentiment — score and crowd share disagree": "mixed_signal",
    "balanced sentiment": "balanced",
    "market fear/greed: fear": "regime_fear",
    "market fear/greed: extreme_fear": "regime_extreme_fear",
    "market fear/greed: greed": "regime_greed",
    "market fear/greed: extreme_euphoria": "regime_extreme_euphoria",
    "empty_symbol": "empty_symbol",
}


def _sentiment_reason_token(raw):
    if raw is None:
        return None
    key = str(raw).strip().lower()
    if key in _SENTIMENT_REASON_TOKEN_MAP:
        return _SENTIMENT_REASON_TOKEN_MAP[key]
    if key.startswith("small sample"):
        return "small_sample"
    if key.startswith("db_error"):
        return "db_error"
    if key in (
        "no_events_24h",
        "no_events_in_window",
        "small_sample",
        "weighted_positive",
        "weighted_negative",
    ):
        return key
    return None


def _sentiment_reasons_to_tokens(raw_reasons):
    """`reason` field in sentiment runtime is sometimes a list, sometimes a string."""
    if raw_reasons is None:
        return []
    if isinstance(raw_reasons, str):
        raw_reasons = [raw_reasons]
    out = []
    for r in raw_reasons:
        tok = _sentiment_reason_token(r)
        if tok and tok not in out:
            out.append(tok)
    return out


def _sentiment_canonical_direction(direction_raw):
    m = {"LONG_BIAS": "long", "SHORT_BIAS": "short", "WAIT": "neutral"}
    return m.get(str(direction_raw or "").upper(), "neutral")


def _sentiment_canonical_state(payload):
    """
      ok=False, state='unavailable'   → 'degraded' (provider unhealthy)
                                         or 'insufficient' (sample=0)
      ok=True, direction='WAIT'       → 'wait'
      ok=True, direction in (LONG_BIAS, SHORT_BIAS) → 'active'
    """
    if not payload.get("ok"):
        if payload.get("sample", 0) == 0 and not payload.get("reason", []):
            return "insufficient"
        # Distinguish empty-substrate from real degradation
        reasons = payload.get("reason") or []
        if isinstance(reasons, list) and reasons:
            first = str(reasons[0]).lower()
            if "no sentiment events" in first or first == "empty_symbol":
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
    Adapt a raw sentiment `runtime(symbol)` result to a CognitionSnapshot.

    Pure: no DB, no network, no recomputation. The caller is responsible
    for obtaining `payload` via the established read path.
    """
    from services.runtime_contract import (
        CognitionSnapshot, make_insufficient,
    )

    if not isinstance(payload, dict) or not payload:
        return make_insufficient(
            module="sentiment",
            source="sentiment_events",
            reasons=("missing_sentiment_payload",),
        )

    source = str(payload.get("source") or "sentiment_events").strip().lower()
    updated_at = payload.get("asOf")

    state = _sentiment_canonical_state(payload)

    if state in ("insufficient", "degraded"):
        reason_tokens = _sentiment_reasons_to_tokens(payload.get("reason"))
        if not reason_tokens:
            reason_tokens = ["sentiment_unavailable"]
        return CognitionSnapshot.build(
            module="sentiment",
            source=source,
            state=state,
            reasons=reason_tokens,
            degraded=bool(payload.get("degraded")) or state == "degraded",
            updatedAt=updated_at,
        )

    direction = _sentiment_canonical_direction(payload.get("direction"))
    confidence = payload.get("confidence")
    reasons = _sentiment_reasons_to_tokens(payload.get("reason"))
    if not reasons:
        reasons = ["sentiment_reasons_unmapped"]

    return CognitionSnapshot.build(
        module="sentiment",
        source=source,
        state=state,
        direction=direction,
        confidence=confidence,
        reasons=reasons,
        degraded=bool(payload.get("degraded")),
        updatedAt=updated_at,
    )
