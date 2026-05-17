"""
shadow_verdict_runtime — Stage A-7: Shadow Verdict Runtime.

NOT paper execution.  NOT broker.  NOT live orders.  NOT trade signals.
NOT setups.  NOT entry triggers.  NOT recommendations.

This is the *shadow forward structure*: given current cognition layers
(ta + sentiment + fractal) and the canonical MetaBrain finalAction
(from decision_history), what *could* the system have considered, and
why didn't it deploy?

A-6 was accountability memory (what happened after a decision).
A-7 is shadow forward structure (what could be considered right now).

Core principle:  system restraint is the moat.
  - `blocked` is a healthy state, not a failure
  - `wait` is a valid result
  - `considered` is rare (only when raw cognition aligns with canonical final)

Contract:
{
    "symbol": "BTC",
    "mode": "shadow",
    "status": "blocked" | "wait" | "considered" | "unresolved",
    "rawAction": "LONG_BIAS" | "SHORT_BIAS" | "NEUTRAL",
    "finalAction": "WAIT" | "AVOID" | "LONG" | "SHORT" | null,
    "shadowAction": "NO_DEPLOYMENT" | "HYPOTHETICAL_LONG" | "HYPOTHETICAL_SHORT",
    "reason": [ ... human-readable strings, sorted, top-N ... ],
    "deploymentBlockedBy": [ "metaDecision" | "fractal" | "technical_alignment" | "sentiment_confidence" | ... ],
    "hypothetical": {
        "entry": float,
        "stop": float,
        "target": float,
        "riskReward": float,
        "sizeModel": "disabled_shadow",          # ALWAYS — we do NOT compute size
        "source": "atr_v1" | "pct_fallback",
    } | null,
    "cognitionSnapshot": { ta, sentiment, fractal, market_price },
    "createdAt": ISO,
}

Rules:
  - finalAction is READ from decision_history (latest per symbol).
    Shadow runtime NEVER mutates decision_history.
  - shadowAction respects MetaBrain veto:
      finalAction ∈ {WAIT, AVOID, None} → shadowAction = NO_DEPLOYMENT
      (even if rawAction would have permitted LONG_BIAS/SHORT_BIAS)
  - shadowAction = HYPOTHETICAL_* only when rawAction AND finalAction agree
    (cross-validation between raw cognition and canonical MetaBrain).
  - hypothetical structure is a *counterfactual* — never an execution intent.
  - deploymentBlockedBy is structural attribution: which layer(s) vetoed.
  - SEMANTIC dedup window: 15 minutes. If a shadow within 15m has the
    same (symbol, finalAction, rawAction, top-3 reasons), suppress duplicate.
  - Observational only: no mutation of ta / sentiment / fractal / decision_history.
"""
from __future__ import annotations

import os
import threading
from collections import Counter
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

from pymongo import ASCENDING, DESCENDING, MongoClient


# ─── Tuning / Constants ────────────────────────────────────────────────
DEDUP_WINDOW_MIN = 15
DEFAULT_SYMBOLS = ["BTC", "ETH", "SOL"]
COLLECTION = "shadow_verdicts"

# Hypothetical structure — fallback pct-based (used until ATR is wired up)
LONG_STOP_PCT = 0.06        # -6%
LONG_TARGET_PCT = 0.10      # +10% → RR ≈ 1.67
SHORT_STOP_PCT = 0.06       # +6% (above entry)
SHORT_TARGET_PCT = 0.10     # -10% → RR ≈ 1.67

# Direction labels (must match sentiment_runtime / fractal_runtime / ta)
DIR_LONG = "LONG_BIAS"
DIR_SHORT = "SHORT_BIAS"
DIR_NEUTRAL = "NEUTRAL"

WAIT_SET = {"WAIT", "AVOID", "SUPPRESS", "BLOCK", "HOLD", ""}
LONG_FINAL_SET = {"LONG", "BUY", "ENTER_LONG"}
SHORT_FINAL_SET = {"SHORT", "SELL", "ENTER_SHORT"}


# ─── Mongo wiring ──────────────────────────────────────────────────────
_lock = threading.RLock()
_client: Optional[MongoClient] = None
_indexes_ensured = False


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now_utc().isoformat()


def _db():
    global _client
    if _client is None:
        _client = MongoClient(os.environ.get("MONGO_URL"))
    return _client[os.environ.get("DB_NAME", "test_database")]


def _ensure_indexes():
    global _indexes_ensured
    if _indexes_ensured:
        return
    try:
        coll = _db()[COLLECTION]
        coll.create_index(
            [("symbol", ASCENDING), ("createdAt", DESCENDING)],
            name="ix_symbol_created_desc",
        )
        coll.create_index(
            [("status", ASCENDING), ("createdAt", DESCENDING)],
            name="ix_status_created_desc",
        )
        _indexes_ensured = True
    except Exception:
        _indexes_ensured = False


# ─── Safe cognition adapters ───────────────────────────────────────────
def _safe(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception:
        return None


def _gather_cognition(symbol: str) -> dict:
    snap = {"ta": None, "sentiment": None, "fractal": None, "market_price": None}
    try:
        from services.technical_analysis import basic as _ta_basic  # type: ignore
        snap["ta"] = _safe(_ta_basic, symbol)
    except Exception:
        pass
    try:
        from services.sentiment_runtime import runtime as _sent  # type: ignore
        snap["sentiment"] = _safe(_sent, symbol)
    except Exception:
        pass
    try:
        from services.fractal_runtime import runtime as _frac  # type: ignore
        snap["fractal"] = _safe(_frac, symbol)
    except Exception:
        pass
    try:
        from services.market_prices import get_price as _gp  # type: ignore
        snap["market_price"] = _safe(_gp, symbol)
    except Exception:
        pass
    return snap


# ─── Canonical final action from decision_history ──────────────────────
def _read_canonical_final(symbol: str) -> Tuple[Optional[str], Optional[dict]]:
    """Return (finalAction, latest_decision_doc).  We read canonical MetaBrain
    output — never recompute it.  None if no history for the symbol."""
    try:
        latest = _db().decision_history.find_one(
            {"asset": symbol.upper()},
            {"_id": 0},
            sort=[("timestamp", -1)],
        )
        if not latest:
            return None, None
        action = (latest.get("decision") or "").upper().strip() or None
        return action, latest
    except Exception:
        return None, None


# ─── Raw action computation ────────────────────────────────────────────
def _layer_direction(layer: Optional[dict]) -> str:
    if not isinstance(layer, dict):
        return DIR_NEUTRAL
    d = (layer.get("direction") or "").upper().strip()
    if d == DIR_LONG:
        return DIR_LONG
    if d == DIR_SHORT:
        return DIR_SHORT
    return DIR_NEUTRAL


def _compute_raw_action(cognition: dict) -> str:
    """Aggregate ta+sentiment+fractal directional opinion.

    Requires AT LEAST 2 agreeing layers for LONG_BIAS/SHORT_BIAS.
    Otherwise NEUTRAL.  No 'majority of 1'."""
    dirs = [
        _layer_direction(cognition.get("ta")),
        _layer_direction(cognition.get("sentiment")),
        _layer_direction(cognition.get("fractal")),
    ]
    longs = sum(1 for d in dirs if d == DIR_LONG)
    shorts = sum(1 for d in dirs if d == DIR_SHORT)
    if longs >= 2 and shorts == 0:
        return DIR_LONG
    if shorts >= 2 and longs == 0:
        return DIR_SHORT
    return DIR_NEUTRAL


# ─── Shadow action / status / blocked-by attribution ───────────────────
def _final_normalized(final_action: Optional[str]) -> str:
    if not final_action:
        return "WAIT"
    fa = final_action.upper().strip()
    if fa in LONG_FINAL_SET:
        return "LONG"
    if fa in SHORT_FINAL_SET:
        return "SHORT"
    if fa in WAIT_SET:
        return "WAIT"
    return "WAIT"


def _any_layer_bias(cognition: dict) -> bool:
    """True if ANY single cognition layer shows LONG_BIAS or SHORT_BIAS.
    Used for `blocked` status — canonical MetaBrain veto over even partial
    cognitive bias is a healthy restraint signal."""
    for k in ("ta", "sentiment", "fractal"):
        if _layer_direction(cognition.get(k)) in {DIR_LONG, DIR_SHORT}:
            return True
    return False


def _compute_shadow_action(
    raw: str, final_norm: str, cognition: dict
) -> Tuple[str, str]:
    """Return (shadowAction, status).

    MetaBrain veto wins: if final is WAIT/AVOID, shadow is NO_DEPLOYMENT
    regardless of raw cognition.

    `blocked` requires ≥1 layer bias (restraint over partial signal).
    `considered` requires strict raw (≥2 layers) AND aligned canonical final.
    """
    if final_norm == "WAIT":
        if _any_layer_bias(cognition):
            return ("NO_DEPLOYMENT", "blocked")
        return ("NO_DEPLOYMENT", "wait")

    if final_norm == "LONG":
        if raw == DIR_LONG:
            return ("HYPOTHETICAL_LONG", "considered")
        return ("NO_DEPLOYMENT", "unresolved")  # final says yes, raw doesn't agree

    if final_norm == "SHORT":
        if raw == DIR_SHORT:
            return ("HYPOTHETICAL_SHORT", "considered")
        return ("NO_DEPLOYMENT", "unresolved")

    return ("NO_DEPLOYMENT", "wait")


def _deployment_blocked_by(
    cognition: dict, final_norm: str, raw: str, shadow_action: str
) -> List[str]:
    """Structural attribution of which cognitive layer(s) vetoed deployment.
    Future-proof: stays consistent as a vector even when system grows."""
    blocked: List[str] = []
    if shadow_action == "NO_DEPLOYMENT":
        # MetaBrain veto?
        if final_norm == "WAIT":
            blocked.append("metaDecision")

        # Fractal veto?
        fr = cognition.get("fractal") or {}
        phase = (fr.get("phase") or "").lower()
        if phase in {"compression", "rangebound", "unavailable"}:
            blocked.append("fractal")

        # TA alignment?
        ta = cognition.get("ta") or {}
        if isinstance(ta, dict):
            aligned = ta.get("alignedIndicators")
            if aligned is None or (isinstance(aligned, (int, float)) and aligned < 3):
                blocked.append("technical_alignment")

        # Sentiment confidence?
        se = cognition.get("sentiment") or {}
        if isinstance(se, dict):
            conf = se.get("confidence")
            if conf is None or (isinstance(conf, (int, float)) and conf < 0.30):
                blocked.append("sentiment_confidence")

        # Price unavailable?
        mp = cognition.get("market_price") or {}
        if not (isinstance(mp, dict) and mp.get("ok") and mp.get("price")):
            blocked.append("price_unavailable")

    # dedup, preserve order
    seen = set()
    out: List[str] = []
    for b in blocked:
        if b not in seen:
            seen.add(b)
            out.append(b)
    return out


def _compose_reasons(
    cognition: dict, final_norm: str, raw: str
) -> List[str]:
    """Human-readable reason strings — observational, no agency language."""
    reasons: List[str] = []
    ta = cognition.get("ta") or {}
    se = cognition.get("sentiment") or {}
    fr = cognition.get("fractal") or {}

    # MetaBrain
    if final_norm == "WAIT":
        reasons.append("MetaBrain canonical decision: WAIT")

    # Fractal
    if isinstance(fr, dict):
        phase = (fr.get("phase") or "").lower()
        if phase == "compression":
            reasons.append("fractal compression — no expansion phase")
        elif phase == "rangebound":
            reasons.append("fractal rangebound — no directional structure")
        elif phase == "unavailable":
            reasons.append("fractal evidence insufficient")

    # TA
    if isinstance(ta, dict):
        aligned = ta.get("alignedIndicators")
        if isinstance(aligned, (int, float)) and aligned < 3:
            reasons.append(f"TA insufficient alignment ({int(aligned)}/3+)")
        if ta.get("ok") is False or ta.get("degraded") is True:
            reasons.append("TA degraded or no history")

    # Sentiment
    if isinstance(se, dict):
        if se.get("ok") and se.get("direction") in {DIR_LONG, DIR_SHORT}:
            label = "bullish" if se["direction"] == DIR_LONG else "bearish"
            reasons.append(f"sentiment {label} but not cross-confirmed")
        conf = se.get("confidence")
        if isinstance(conf, (int, float)) and conf < 0.30:
            reasons.append("sentiment confidence below 0.30 threshold")

    # Cross-module alignment (when only one layer agrees with the move)
    dirs = [
        _layer_direction(ta), _layer_direction(se), _layer_direction(fr),
    ]
    longs = sum(1 for d in dirs if d == DIR_LONG)
    shorts = sum(1 for d in dirs if d == DIR_SHORT)
    if longs == 1 or shorts == 1:
        reasons.append("insufficient cross-module alignment")

    # Healthy considered case — keep reasons positive but observational
    if final_norm in {"LONG", "SHORT"} and raw != DIR_NEUTRAL:
        if final_norm == "LONG" and raw == DIR_LONG:
            reasons.append("raw cognition aligned with canonical LONG")
        elif final_norm == "SHORT" and raw == DIR_SHORT:
            reasons.append("raw cognition aligned with canonical SHORT")

    # dedup, cap at 5
    seen = set()
    out: List[str] = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            out.append(r)
        if len(out) >= 5:
            break
    return out


# ─── Hypothetical counterfactual structure ─────────────────────────────
def _compute_hypothetical(
    raw: str, market_price: Optional[dict]
) -> Optional[dict]:
    """Hypothetical entry/stop/target — pct-based fallback.

    This is a *counterfactual structure*, NOT a recommended trade.
    sizeModel is ALWAYS 'disabled_shadow' — shadow never sizes.
    """
    if raw == DIR_NEUTRAL:
        return None
    if not isinstance(market_price, dict) or not market_price.get("ok"):
        return None
    price = market_price.get("price")
    if not isinstance(price, (int, float)) or price <= 0:
        return None

    entry = float(price)
    if raw == DIR_LONG:
        stop = round(entry * (1.0 - LONG_STOP_PCT), 4)
        target = round(entry * (1.0 + LONG_TARGET_PCT), 4)
        rr = round((target - entry) / max(1e-9, (entry - stop)), 3)
    else:  # SHORT
        stop = round(entry * (1.0 + SHORT_STOP_PCT), 4)
        target = round(entry * (1.0 - SHORT_TARGET_PCT), 4)
        rr = round((entry - target) / max(1e-9, (stop - entry)), 3)

    return {
        "entry": round(entry, 4),
        "stop": stop,
        "target": target,
        "riskReward": rr,
        "sizeModel": "disabled_shadow",
        "source": "pct_fallback",
    }


# ─── Semantic dedup ────────────────────────────────────────────────────
def _semantic_key(
    final_norm: str, raw: str, reasons: List[str]
) -> Tuple[str, str, Tuple[str, ...]]:
    top = tuple(sorted(set(reasons[:3])))
    return (final_norm, raw, top)


def _is_semantically_duplicate(
    symbol: str, key: Tuple[str, str, Tuple[str, ...]]
) -> bool:
    cutoff = (_now_utc() - timedelta(minutes=DEDUP_WINDOW_MIN)).isoformat()
    try:
        latest = _db()[COLLECTION].find_one(
            {"symbol": symbol, "createdAt": {"$gte": cutoff}},
            {"_id": 0, "finalAction": 1, "rawAction": 1, "reason": 1, "createdAt": 1},
            sort=[("createdAt", -1)],
        )
        if not latest:
            return False
        prev_key = _semantic_key(
            _final_normalized(latest.get("finalAction")),
            (latest.get("rawAction") or DIR_NEUTRAL),
            latest.get("reason") or [],
        )
        return prev_key == key
    except Exception:
        return False


# ─── Build single shadow verdict for a symbol ──────────────────────────
def shadow_for_symbol(symbol: str) -> dict:
    sym = symbol.upper().strip()
    cognition = _gather_cognition(sym)
    final_raw, _latest_dec = _read_canonical_final(sym)
    final_norm = _final_normalized(final_raw)
    raw = _compute_raw_action(cognition)
    shadow_action, status = _compute_shadow_action(raw, final_norm, cognition)
    reasons = _compose_reasons(cognition, final_norm, raw)
    blocked_by = _deployment_blocked_by(cognition, final_norm, raw, shadow_action)
    hypothetical = _compute_hypothetical(raw, cognition.get("market_price"))

    return {
        "symbol": sym,
        "mode": "shadow",
        "status": status,
        "rawAction": raw,
        "finalAction": final_norm if final_raw else None,
        "shadowAction": shadow_action,
        "reason": reasons,
        "deploymentBlockedBy": blocked_by,
        "hypothetical": hypothetical,
        "cognitionSnapshot": cognition,
        "createdAt": _now_iso(),
    }


# ─── Public: sweep ─────────────────────────────────────────────────────
def sweep(symbols: Optional[List[str]] = None) -> dict:
    """Sweep shadow verdicts for given symbols (default BTC/ETH/SOL).

    Semantic dedup: same (symbol, finalAction, rawAction, top-3 reasons)
    within 15 minutes is suppressed (returns dedup_suppressed count, no DB write).
    """
    with _lock:
        _ensure_indexes()
        db = _db()
        syms = [s.upper().strip() for s in (symbols or DEFAULT_SYMBOLS) if s.strip()]
        if not syms:
            return {
                "ok": False,
                "reason": "no_symbols_specified",
                "created": 0,
                "dedupSuppressed": 0,
                "errors": 0,
                "asOf": _now_iso(),
            }

        # Sanity: insufficient_decision_context if decision_history is empty
        try:
            total_dec = db.decision_history.count_documents({})
        except Exception:
            total_dec = 0
        if total_dec == 0:
            return {
                "ok": False,
                "reason": "insufficient_decision_context",
                "created": 0,
                "dedupSuppressed": 0,
                "errors": 0,
                "asOf": _now_iso(),
            }

        created = 0
        dedup_suppressed = 0
        errors = 0
        records: List[dict] = []

        for sym in syms:
            try:
                verdict = shadow_for_symbol(sym)
                key = _semantic_key(
                    verdict.get("finalAction") or "WAIT",
                    verdict["rawAction"],
                    verdict["reason"],
                )
                if _is_semantically_duplicate(sym, key):
                    dedup_suppressed += 1
                    continue
                db[COLLECTION].insert_one({**verdict})
                created += 1
                records.append({
                    "symbol": sym,
                    "status": verdict["status"],
                    "shadowAction": verdict["shadowAction"],
                })
                # Phase D Pass 1 · forward-only continuity trace.
                if verdict.get("status") == "blocked":
                    try:
                        from services.runtime_events import emit as _emit
                        _emit("SHADOW_BLOCKED", {
                            "symbol": sym,
                            "rawAction": verdict.get("rawAction"),
                            "finalAction": verdict.get("finalAction"),
                            "blockedBy": (verdict.get("deploymentBlockedBy") or [])[:5],
                        })
                    except Exception:
                        pass
            except Exception:
                errors += 1
                continue

        return {
            "ok": True,
            "symbolsRequested": len(syms),
            "created": created,
            "dedupSuppressed": dedup_suppressed,
            "errors": errors,
            "records": records,
            "asOf": _now_iso(),
        }


# ─── Public: health ────────────────────────────────────────────────────
def service_health() -> dict:
    with _lock:
        _ensure_indexes()
        db = _db()
        try:
            total = db[COLLECTION].count_documents({})
        except Exception as e:
            return {"ok": False, "reason": f"db_error: {e!r}"}

        try:
            cls_counter: Counter = Counter()
            for doc in db[COLLECTION].find({}, {"status": 1, "_id": 0}):
                cls_counter[doc.get("status") or "unknown"] += 1
            distinct_syms = db[COLLECTION].distinct("symbol")
            last = db[COLLECTION].find_one(
                {}, {"_id": 0, "createdAt": 1}, sort=[("createdAt", -1)]
            )
            last_iso = (last or {}).get("createdAt")
        except Exception as e:
            return {"ok": False, "reason": f"db_error: {e!r}"}

        if total == 0:
            return {
                "ok": True,
                "symbols": 0,
                "totalVerdicts": 0,
                "blocked": 0,
                "wait": 0,
                "considered": 0,
                "unresolved": 0,
                "lastSweepAt": None,
                "dedupWindowMin": DEDUP_WINDOW_MIN,
                "note": "no shadow verdicts swept yet — run POST /sweep",
                "asOf": _now_iso(),
            }

        return {
            "ok": True,
            "symbols": len(distinct_syms),
            "totalVerdicts": total,
            "blocked": int(cls_counter.get("blocked", 0)),
            "wait": int(cls_counter.get("wait", 0)),
            "considered": int(cls_counter.get("considered", 0)),
            "unresolved": int(cls_counter.get("unresolved", 0)),
            "lastSweepAt": last_iso,
            "dedupWindowMin": DEDUP_WINDOW_MIN,
            "asOf": _now_iso(),
        }


# ─── Public: recent (no cognitionSnapshot for privacy/size) ────────────
def recent(limit: int = 25, symbol: Optional[str] = None) -> dict:
    with _lock:
        _ensure_indexes()
        db = _db()
        try:
            q: dict = {}
            if symbol:
                q["symbol"] = symbol.upper().strip()
            rows = list(
                db[COLLECTION]
                .find(q, {"_id": 0, "cognitionSnapshot": 0})
                .sort("createdAt", -1)
                .limit(int(limit))
            )
            return {
                "ok": True,
                "count": len(rows),
                "items": rows,
                "asOf": _now_iso(),
            }
        except Exception as e:
            return {"ok": False, "reason": f"db_error: {e!r}"}


# ─── Public: summary (latest per symbol + distribution + top reasons) ──
def summary(symbols: Optional[List[str]] = None) -> dict:
    with _lock:
        _ensure_indexes()
        db = _db()
        target = [s.upper().strip() for s in (symbols or DEFAULT_SYMBOLS) if s.strip()]
        try:
            total = db[COLLECTION].count_documents({})
        except Exception as e:
            return {"ok": False, "reason": f"db_error: {e!r}"}

        if total == 0:
            return {
                "ok": True,
                "totalVerdicts": 0,
                "perSymbol": {},
                "distribution": {},
                "topReasons": [],
                "topBlockedBy": [],
                "note": "no shadow verdicts swept yet",
                "asOf": _now_iso(),
            }

        per_symbol: Dict[str, dict] = {}
        for sym in target:
            doc = db[COLLECTION].find_one(
                {"symbol": sym},
                {"_id": 0, "cognitionSnapshot": 0},
                sort=[("createdAt", -1)],
            )
            if doc:
                per_symbol[sym] = doc

        dist: Counter = Counter()
        reasons_c: Counter = Counter()
        blocked_c: Counter = Counter()
        try:
            for doc in db[COLLECTION].find(
                {},
                {"_id": 0, "status": 1, "reason": 1, "deploymentBlockedBy": 1},
            ):
                dist[doc.get("status") or "unknown"] += 1
                for r in (doc.get("reason") or [])[:3]:
                    reasons_c[r] += 1
                for b in (doc.get("deploymentBlockedBy") or []):
                    blocked_c[b] += 1
        except Exception:
            pass

        return {
            "ok": True,
            "totalVerdicts": total,
            "perSymbol": per_symbol,
            "distribution": dict(dist),
            "topReasons": reasons_c.most_common(8),
            "topBlockedBy": blocked_c.most_common(8),
            "dedupWindowMin": DEDUP_WINDOW_MIN,
            "asOf": _now_iso(),
        }


# ═══════════════════════════════════════════════════════════════════════
# Phase D Pass 2B — Canonical adapter (derived cognition: shadow)
# ═══════════════════════════════════════════════════════════════════════
# DISCIPLINE: shadow is *interpretive*, not generative. Adapter only
# normalizes posture — never raises certainty (A9), never invents direction,
# never aggregates confidence. Original shadow semantics (status,
# rawAction, finalAction, shadowAction) MUST remain in the public payload
# untouched — this adapter exposes a *parallel* canonical view.


# Status → canonical state mapping per user directive.
_SHADOW_STATUS_TO_STATE = {
    "blocked": "suppressed",
    "wait": "wait",
    "considered": "active",
    "unresolved": "degraded",
}


def _shadow_reason_to_token(raw):
    """
    Stable mapping for the small set of `_compose_reasons()` outputs.
    Anything unmapped is dropped (with a sentinel if reasons becomes empty).
    """
    if raw is None:
        return None
    s = str(raw).strip().lower()
    # Prefix-based — _compose_reasons emits parameterized phrases.
    if "metabrain canonical decision" in s:
        # Extract WAIT/LONG/SHORT tail.
        if "wait" in s: return "meta_canonical_wait"
        if "long" in s: return "meta_canonical_long"
        if "short" in s: return "meta_canonical_short"
        return "meta_canonical_decision"
    if "fractal compression" in s or "no expansion phase" in s:
        return "fractal_compression"
    if "sentiment bullish but not cross-confirmed" in s:
        return "sentiment_uncrossed_bullish"
    if "sentiment bearish but not cross-confirmed" in s:
        return "sentiment_uncrossed_bearish"
    if "insufficient cross-module alignment" in s:
        return "insufficient_alignment"
    if "no market price" in s or "price unavailable" in s:
        return "price_unavailable"
    if "horizons disagree" in s:
        return "horizons_disagree"
    if "technical alignment absent" in s or "no technical alignment" in s:
        return "technical_alignment_absent"
    if "regime not supportive" in s:
        return "regime_unsupportive"
    # Pass-through if already snake-cased and short
    if " " not in s and len(s) <= 64:
        return s
    return None


def _shadow_reasons_to_tokens(raw_reasons):
    if not raw_reasons:
        return []
    out = []
    for r in raw_reasons:
        tok = _shadow_reason_to_token(r)
        if tok and tok not in out:
            out.append(tok)
    return out


def canonical(payload):
    """
    Adapt a raw `shadow_for_symbol(symbol)` result to a CognitionSnapshot.

    Pure: no DB, no network, no recomputation. Caller supplies the payload.

    Discipline:
      - state mapping: blocked→suppressed, wait→wait, considered→active,
        unresolved→degraded.
      - direction: ALWAYS None for shadow. Shadow is a restraint surface;
        it never asserts long/short directionally. (Even when status is
        'considered', the directional opinion still lives in the source
        cognition modules — shadow only says 'consideration is permitted'.)
      - confidence: ALWAYS None. Shadow does not produce a numeric
        confidence; that is core cognition's job.
      - A9: this adapter never amplifies — non-considered statuses can
        never become 'active', and considered status never carries a
        confidence number we did not have upstream.
    """
    from services.runtime_contract import (
        CognitionSnapshot, make_insufficient,
    )

    if not isinstance(payload, dict) or not payload:
        return make_insufficient(
            module="shadow",
            source="shadow_verdicts",
            reasons=("missing_shadow_payload",),
        )

    status = str(payload.get("status") or "").strip().lower()
    state = _SHADOW_STATUS_TO_STATE.get(status)
    if state is None:
        # Unknown status → degrade honestly rather than guessing.
        state = "degraded"

    reasons = _shadow_reasons_to_tokens(payload.get("reason") or [])

    # `deploymentBlockedBy` is already a snake-case-ish list of layer names —
    # surface it as supplementary reason tokens (prefixed for clarity).
    for layer in payload.get("deploymentBlockedBy") or []:
        if not layer:
            continue
        tok = f"blocked_by_{str(layer).strip().lower().replace(' ', '_')}"
        if tok not in reasons:
            reasons.append(tok)

    if not reasons:
        reasons = ["shadow_no_reasons"]

    return CognitionSnapshot.build(
        module="shadow",
        source="shadow_verdicts",
        state=state,
        direction=None,
        confidence=None,
        reasons=reasons,
        degraded=state == "degraded",
        updatedAt=payload.get("createdAt"),
    )

