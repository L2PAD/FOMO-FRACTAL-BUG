"""
outcome_memory — Stage A-6: Cognitive Accountability Layer.

NOT reinforcement learning.  NOT pnl-optimization.  NOT broker semantics.
NOT execution.  NOT trade simulation.

Purpose: convert past decisions (canonical substrate = decision_history)
into honest, classifiable memory of "decision → later market reality →
classification".  WAIT/AVOID are first-class outcomes too — capital
preservation and missed asymmetry are remembered alongside execution
verdicts.

Contracts:
    sweep_outcomes(limit)   → creates PENDING records, no classification yet
    resolve_outcomes(limit) → closes mature PENDING records (resolves_at ≤ now)
    service_health()        → honest counters + classification distribution

Rules / truthful-degradation policy:
    - 1 decision → 1 canonical outcome (NO multi-horizon now).
    - horizon = decision.horizon if present, else 3600s.
    - If decision_history empty → ok=False, reason='insufficient_decision_context'
      (do NOT pretend the layer is alive).
    - Significance threshold for WAIT/AVOID classification: ±1.5%.
        |Δ| < 1.5% → neutral_wait (a remembered non-event)
        Δ ≥ +1.5% & verdict ∈ {WAIT,AVOID} → missed_gain
        Δ ≤ −1.5% & verdict ∈ {WAIT,AVOID} → avoided_loss
    - LONG/SHORT verdicts: realized_gain / realized_loss based on Δ sign.
    - If market reality at resolves_at not available → status='expired',
      reason='missing_market_reality'.  No live-fallback for old maturity.
    - Cognition snapshot is an IMMUTABLE COPY (not a reference).  Marked
      decision_time_approximation=true only when sweep ran within 5 minutes
      of the original decision.

NO multi-horizon.  NO background scheduler.  NO pnl.  NO "wouldHaveWon".
"""
from __future__ import annotations

import os
import threading
from collections import Counter
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional

import requests
from pymongo import ASCENDING, MongoClient


# ─── Tuning ────────────────────────────────────────────────────────────
DEFAULT_HORIZON_SEC = 3600
SIGNIFICANT_MOVE_PCT = 0.015          # ±1.5%
DECISION_TIME_APPROX_WINDOW_SEC = 300  # cognition_snapshot ≈ decision-time if swept ≤ 5min
HISTORICAL_LIVE_FALLBACK_SEC = 120     # use live price if maturity within ±2min of now

HORIZON_MAP = {
    "1H": 3600,
    "4H": 14400,
    "12H": 43200,
    "24H": 86400,
    "1D": 86400,
    "3D": 259200,
    "7D": 604800,
    "14D": 1209600,
    "30D": 2592000,
}

COINGECKO_RANGE_URL = "https://api.coingecko.com/api/v3/coins/{cg_id}/market_chart/range"
HTTP_TIMEOUT = 8.0

OUTCOMES_COLL = "mbrain_integrity_outcomes"


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
        coll = _db()[OUTCOMES_COLL]
        coll.create_index([("decision_id", ASCENDING)], unique=True, name="ux_decision_id")
        coll.create_index([("status", ASCENDING), ("resolves_at", ASCENDING)], name="ix_status_resolves")
        coll.create_index([("symbol", ASCENDING), ("created_at", ASCENDING)], name="ix_symbol_created")
        _indexes_ensured = True
    except Exception:
        # non-fatal — indexes are an optimization
        _indexes_ensured = False


# ─── Time / horizon parsing ────────────────────────────────────────────
def _parse_dt(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    return None


def _parse_horizon(h) -> int:
    if h is None:
        return DEFAULT_HORIZON_SEC
    s = str(h).upper().strip()
    if not s:
        return DEFAULT_HORIZON_SEC
    if s in HORIZON_MAP:
        return HORIZON_MAP[s]
    # generic suffix parsing  e.g. "2H" / "5D" / "30M"
    try:
        if s.endswith("H"):
            return max(60, int(s[:-1]) * 3600)
        if s.endswith("D"):
            return max(60, int(s[:-1]) * 86400)
        if s.endswith("M"):
            return max(60, int(s[:-1]) * 60)
        if s.endswith("W"):
            return max(60, int(s[:-1]) * 604800)
    except Exception:
        pass
    return DEFAULT_HORIZON_SEC


# ─── Cognition snapshot capture ────────────────────────────────────────
def _safe_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception:
        return None


def _cognition_snapshot(symbol: str, decision_time: Optional[datetime]) -> dict:
    """Capture an IMMUTABLE copy of the current cognition layers.

    These layers (ta / sentiment / fractal / price) are computed NOW —
    we mark whether this captures decision-time view (sweep ran ≤ 5 min
    after decision) or sweep-time drift context (older decisions)."""
    snap: Dict[str, object] = {
        "ta": None,
        "sentiment": None,
        "fractal": None,
        "market_price": None,
        "captured_at": _now_iso(),
        "decision_time_approximation": False,
    }

    # mark decision-time approximation
    if decision_time is not None:
        delta = abs((_now_utc() - decision_time).total_seconds())
        snap["decision_time_approximation"] = delta <= DECISION_TIME_APPROX_WINDOW_SEC

    # lazy import — these modules might fail individually; we accept honest None
    try:
        from services.technical_analysis import basic as _ta_basic  # type: ignore
        snap["ta"] = _safe_call(_ta_basic, symbol)
    except Exception:
        pass
    try:
        from services.sentiment_runtime import runtime as _sent_runtime  # type: ignore
        snap["sentiment"] = _safe_call(_sent_runtime, symbol)
    except Exception:
        pass
    try:
        from services.fractal_runtime import runtime as _frac_runtime  # type: ignore
        snap["fractal"] = _safe_call(_frac_runtime, symbol)
    except Exception:
        pass
    try:
        from services.market_prices import get_price as _get_price  # type: ignore
        snap["market_price"] = _safe_call(_get_price, symbol)
    except Exception:
        pass

    return snap


def _meta_decision_copy(dec: dict) -> dict:
    """Capture canonical decision-time substrate (what AI thought THEN)."""
    return {
        "horizon_label": dec.get("horizon"),
        "decision_type": dec.get("decisionType"),
        "score": dec.get("score"),
        "confidence": dec.get("confidence"),
        "fusion": dec.get("fusion"),
        "reasoning": dec.get("reasoning"),
        "status_at_decision": dec.get("status"),
    }


# ─── Historical market reality ─────────────────────────────────────────
def _fetch_market_reality(symbol: str, target_dt: datetime) -> Optional[dict]:
    """Closest CoinGecko price to target_dt.  None ⇒ unavailable."""
    try:
        from services.market_prices import SYMBOL_TO_CG_ID, get_price  # type: ignore
    except Exception:
        return None

    cg_id = SYMBOL_TO_CG_ID.get(symbol.upper())
    if not cg_id:
        return None

    now = _now_utc()
    if target_dt > now:
        return None  # not mature

    # Live-price fallback only for very-recent maturity (≤2min from now)
    if (now - target_dt).total_seconds() <= HISTORICAL_LIVE_FALLBACK_SEC:
        live = _safe_call(get_price, symbol)
        if live and live.get("ok") and live.get("price"):
            return {
                "price": float(live["price"]),
                "source": "coingecko-live-near-maturity",
                "as_of": _now_iso(),
                "target_iso": target_dt.isoformat(),
            }

    # Historical: market_chart/range, ±1h window
    from_ts = int((target_dt - timedelta(hours=1)).timestamp())
    to_ts = int((target_dt + timedelta(hours=1)).timestamp())
    url = COINGECKO_RANGE_URL.format(cg_id=cg_id)
    try:
        r = requests.get(
            url,
            params={"vs_currency": "usd", "from": from_ts, "to": to_ts},
            timeout=HTTP_TIMEOUT,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        prices = data.get("prices") or []
        if not prices:
            return None
        target_ms = int(target_dt.timestamp() * 1000)
        closest = min(prices, key=lambda p: abs(p[0] - target_ms))
        return {
            "price": float(closest[1]),
            "source": "coingecko-historical",
            "as_of": datetime.fromtimestamp(closest[0] / 1000, tz=timezone.utc).isoformat(),
            "target_iso": target_dt.isoformat(),
        }
    except Exception:
        return None


# ─── Classification policy ─────────────────────────────────────────────
def _classify(verdict: str, pct: float) -> str:
    v = (verdict or "").upper().strip()
    significant = abs(pct) >= SIGNIFICANT_MOVE_PCT

    if v in {"WAIT", "AVOID", "SUPPRESS", "BLOCK", "HOLD"}:
        if not significant:
            return "neutral_wait"
        return "missed_gain" if pct > 0 else "avoided_loss"

    if v in {"LONG", "BUY", "ENTER_LONG"}:
        if not significant:
            return "neutral_realized"
        return "realized_gain" if pct > 0 else "realized_loss"

    if v in {"SHORT", "SELL", "ENTER_SHORT"}:
        if not significant:
            return "neutral_realized"
        return "realized_gain" if pct < 0 else "realized_loss"

    # unknown verdict → neutral, never invent semantics
    return "neutral_wait"


# ─── Public: sweep ─────────────────────────────────────────────────────
def sweep_outcomes(limit: int = 500) -> dict:
    """
    Idempotent.  For each decision_history record without a corresponding
    outcome, create a PENDING outcome with an immutable cognition snapshot.

    Returns honest counts.  If decision_history is empty:
      { ok: False, reason: 'insufficient_decision_context' }
    """
    with _lock:
        _ensure_indexes()
        db = _db()

        total_decisions = db.decision_history.count_documents({})
        if total_decisions == 0:
            return {
                "ok": False,
                "reason": "insufficient_decision_context",
                "created": 0,
                "skipped": 0,
                "errors": 0,
                "totalDecisions": 0,
                "asOf": _now_iso(),
            }

        existing_ids = set(db[OUTCOMES_COLL].distinct("decision_id"))

        created = 0
        skipped = 0
        errors = 0

        cursor = (
            db.decision_history.find({}, {"_id": 0})
            .sort("timestamp", -1)
            .limit(int(limit))
        )

        for dec in cursor:
            dec_id = dec.get("id")
            if not dec_id:
                errors += 1
                continue
            if dec_id in existing_ids:
                skipped += 1
                continue

            try:
                sym = (dec.get("asset") or "").upper()
                verdict = (dec.get("decision") or "WAIT").upper()
                created_at = _parse_dt(dec.get("timestamp"))
                if created_at is None:
                    errors += 1
                    continue

                horizon_sec = _parse_horizon(dec.get("horizon"))

                # Prefer decision.evaluateAfter if present (canonical maturity)
                ea = _parse_dt(dec.get("evaluateAfter"))
                if ea is not None and ea > created_at:
                    resolves_at = ea
                    horizon_sec_effective = int((ea - created_at).total_seconds())
                else:
                    resolves_at = created_at + timedelta(seconds=horizon_sec)
                    horizon_sec_effective = horizon_sec

                cog_snap = _cognition_snapshot(sym, created_at)

                doc = {
                    "decision_id": dec_id,
                    "symbol": sym,
                    "verdict": verdict,
                    "horizon_seconds": horizon_sec_effective,
                    "created_at": created_at.isoformat(),
                    "resolves_at": resolves_at.isoformat(),
                    "status": "pending",
                    "classification": None,
                    "entry_price": dec.get("entryPrice"),
                    "cognition_snapshot": cog_snap,
                    "meta_decision": _meta_decision_copy(dec),
                    "market_reality": None,
                    "resolved_at": None,
                    "expiry_reason": None,
                    "sweep_at": _now_iso(),
                }
                db[OUTCOMES_COLL].insert_one(doc)
                existing_ids.add(dec_id)
                created += 1
            except Exception:
                errors += 1
                continue

        return {
            "ok": True,
            "created": created,
            "skipped": skipped,
            "errors": errors,
            "totalDecisions": total_decisions,
            "asOf": _now_iso(),
        }


# ─── Public: resolve ───────────────────────────────────────────────────
def resolve_outcomes(limit: int = 200) -> dict:
    """Close mature pending outcomes.  Mature = resolves_at ≤ now."""
    with _lock:
        _ensure_indexes()
        db = _db()
        now = _now_utc()
        now_iso = now.isoformat()

        cursor = (
            db[OUTCOMES_COLL]
            .find({"status": "pending", "resolves_at": {"$lte": now_iso}})
            .limit(int(limit))
        )

        resolved = 0
        expired = 0
        errors = 0
        cls_counter: Counter = Counter()

        for outcome in cursor:
            try:
                resolves_at = _parse_dt(outcome.get("resolves_at"))
                if resolves_at is None or resolves_at > now:
                    continue

                sym = outcome.get("symbol", "")
                entry = outcome.get("entry_price")
                if entry is None or float(entry) <= 0:
                    db[OUTCOMES_COLL].update_one(
                        {"_id": outcome["_id"]},
                        {"$set": {
                            "status": "expired",
                            "resolved_at": now_iso,
                            "expiry_reason": "missing_entry_price",
                        }},
                    )
                    expired += 1
                    continue

                reality = _fetch_market_reality(sym, resolves_at)
                if reality is None:
                    db[OUTCOMES_COLL].update_one(
                        {"_id": outcome["_id"]},
                        {"$set": {
                            "status": "expired",
                            "resolved_at": now_iso,
                            "expiry_reason": "missing_market_reality",
                        }},
                    )
                    expired += 1
                    continue

                exit_price = float(reality["price"])
                entry_f = float(entry)
                pct = (exit_price - entry_f) / entry_f
                classification = _classify(outcome.get("verdict", ""), pct)
                cls_counter[classification] += 1

                db[OUTCOMES_COLL].update_one(
                    {"_id": outcome["_id"]},
                    {"$set": {
                        "status": "resolved",
                        "classification": classification,
                        "market_reality": {
                            "entry_price": entry_f,
                            "exit_price": exit_price,
                            "pct_change": round(pct, 5),
                            "source": reality.get("source"),
                            "captured_as_of": reality.get("as_of"),
                            "target_iso": reality.get("target_iso"),
                        },
                        "resolved_at": now_iso,
                    }},
                )
                resolved += 1
                # Phase D Pass 1 · forward-only continuity trace.
                try:
                    from services.runtime_events import emit as _emit
                    _emit("OUTCOME_RESOLVED", {
                        "symbol": sym,
                        "verdict": outcome.get("verdict"),
                        "classification": classification,
                        "pctChange": round(pct, 5),
                    })
                except Exception:
                    pass
            except Exception:
                errors += 1
                continue

        return {
            "ok": True,
            "resolved": resolved,
            "expired": expired,
            "errors": errors,
            "newClassifications": dict(cls_counter),
            "asOf": _now_iso(),
        }


# ─── Public: health ────────────────────────────────────────────────────
def service_health() -> dict:
    with _lock:
        _ensure_indexes()
        db = _db()
        try:
            total_decisions = db.decision_history.count_documents({})
        except Exception as e:
            return {"ok": False, "reason": f"db_error: {e!r}"}

        if total_decisions == 0:
            return {
                "ok": False,
                "reason": "insufficient_decision_context",
                "totalDecisions": 0,
                "asOf": _now_iso(),
            }

        try:
            pending = db[OUTCOMES_COLL].count_documents({"status": "pending"})
            resolved = db[OUTCOMES_COLL].count_documents({"status": "resolved"})
            expired = db[OUTCOMES_COLL].count_documents({"status": "expired"})
            total_outcomes = pending + resolved + expired

            now_iso = _now_iso()
            mature_pending = db[OUTCOMES_COLL].count_documents({
                "status": "pending",
                "resolves_at": {"$lte": now_iso},
            })

            cls_counter: Counter = Counter()
            for doc in db[OUTCOMES_COLL].find(
                {"status": "resolved"},
                {"classification": 1, "_id": 0},
            ):
                cls_counter[doc.get("classification") or "unknown"] += 1

            coverage = round(total_outcomes / total_decisions, 3) if total_decisions else 0.0

            return {
                "ok": True,
                "pending": pending,
                "resolved": resolved,
                "expired": expired,
                "totalOutcomes": total_outcomes,
                "totalDecisions": total_decisions,
                "coveragePct": coverage,
                "maturePending": mature_pending,
                "classifications": dict(cls_counter),
                "asOf": _now_iso(),
            }
        except Exception as e:
            return {"ok": False, "reason": f"db_error: {e!r}"}


# ─── Public: recent (optional read for UI / debugging) ─────────────────
def recent_resolved(limit: int = 25) -> dict:
    with _lock:
        _ensure_indexes()
        db = _db()
        try:
            rows = list(
                db[OUTCOMES_COLL]
                .find(
                    {"status": "resolved"},
                    {"_id": 0, "cognition_snapshot": 0},
                )
                .sort("resolved_at", -1)
                .limit(int(limit))
            )
            return {"ok": True, "count": len(rows), "items": rows, "asOf": _now_iso()}
        except Exception as e:
            return {"ok": False, "reason": f"db_error: {e!r}"}



# ═══════════════════════════════════════════════════════════════════════
# Phase D Pass 2B — Canonical adapter (derived cognition: outcome_memory)
# ═══════════════════════════════════════════════════════════════════════
# DISCIPLINE: outcome memory is a *substrate*, not a directional signal.
# Adapter never invents a `direction` — accountability substrate is
# directionless by definition. Confidence is also None: this is not a
# probabilistic forecast, it is a coverage / maturity surface.


def canonical(payload):
    """
    Adapt a raw `outcome_memory.service_health()` result to a CognitionSnapshot.

    Pure: no DB, no network, no recomputation.

    State derivation (purely from substrate counts the caller already produced):
      ok=False                            → 'degraded'     (DB error, etc.)
      totalDecisions == 0                 → 'insufficient' (no substrate)
      totalOutcomes == 0                  → 'insufficient' (memory empty)
      resolved == 0 and pending > 0       → 'wait'         (still maturing)
      resolved > 0                        → 'active'       (memory established)

    Direction: ALWAYS None.   (per user — accountability is not directional)
    Confidence: ALWAYS None.  (per user — no score fusion in canonical layer)
    """
    from services.runtime_contract import (
        CognitionSnapshot, make_insufficient,
    )

    if not isinstance(payload, dict) or not payload:
        return make_insufficient(
            module="outcome_memory",
            source="mbrain_integrity_outcomes",
            reasons=("missing_outcome_payload",),
        )

    source = "mbrain_integrity_outcomes"
    updated_at = payload.get("asOf")

    if not payload.get("ok"):
        reason = str(payload.get("reason") or "outcome_unavailable")
        # 'insufficient_decision_context' is the documented empty-substrate code
        if "insufficient_decision_context" in reason:
            return make_insufficient(
                module="outcome_memory",
                source=source,
                reasons=("insufficient_decision_context",),
            )
        return CognitionSnapshot.build(
            module="outcome_memory",
            source=source,
            state="degraded",
            reasons=(reason.lower().replace(" ", "_").replace(":", "_")[:64],),
            degraded=True,
            updatedAt=updated_at,
        )

    total_outcomes = int(payload.get("totalOutcomes") or 0)
    resolved = int(payload.get("resolved") or 0)
    pending = int(payload.get("pending") or 0)
    expired = int(payload.get("expired") or 0)
    coverage = payload.get("coveragePct") or 0
    mature_pending = int(payload.get("maturePending") or 0)

    reasons = []
    if total_outcomes == 0:
        state = "insufficient"
        reasons.append("memory_empty")
    elif resolved == 0 and pending > 0:
        state = "wait"
        reasons.append("memory_maturing")
        if mature_pending > 0:
            reasons.append("mature_pending_present")
    elif resolved > 0:
        state = "active"
        reasons.append("memory_established")
        if expired > 0:
            reasons.append("contains_expired")
    else:
        # Defensive — no resolved, no pending, no expired but totalOutcomes>0.
        # Should not happen but if it does, treat as degraded.
        state = "degraded"
        reasons.append("inconsistent_counts")

    # Coverage tag — interpretive, not directional.
    if isinstance(coverage, (int, float)):
        if coverage < 0.25:
            reasons.append("coverage_low")
        elif coverage < 0.75:
            reasons.append("coverage_partial")
        else:
            reasons.append("coverage_high")

    return CognitionSnapshot.build(
        module="outcome_memory",
        source=source,
        state=state,
        direction=None,        # discipline: accountability is directionless
        confidence=None,       # discipline: no score fusion
        reasons=reasons,
        degraded=state == "degraded",
        updatedAt=updated_at,
    )
