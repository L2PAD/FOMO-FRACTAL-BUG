"""
paper_runtime — Phase C foundation skeleton.

NOT live execution.  NOT paper trading.  NOT broker integration.
NOT order routing.  NOT PnL calculation.  NOT position management.

This is the *architectural contract* for an eventual paper runtime —
laid down NOW so the surface, gates, and collections exist before any
execution semantics ship.  Every endpoint is currently inert by design.

Layers established:
    paper_accounts     — operator account configurations (not auth)
    paper_positions    — would-be paper positions (always empty pre-gate)
    paper_orders       — would-be paper orders (always empty pre-gate)
    paper_events       — audit ledger of gate decisions and simulate intents

Gate logic (paper_runtime_gate):
    OPEN   ⇔   operator.mode == 'paper'
           ∧   shadow_verdicts has ≥1 record within last 24h
           ∧   mbrain_integrity_outcomes has ≥1 resolved classification
           ∧   market_prices for universe symbols all non-degraded

Anything less → gate CLOSED, with explicit `requires` array enumerating
the missing preconditions.  Honest substrate, no premature deployment.
"""
from __future__ import annotations

import os
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

from pymongo import MongoClient


UNIVERSE = ["BTC", "ETH", "SOL"]
RECENT_SHADOW_WINDOW_HOURS = 24

COLL_ACCOUNTS = "paper_accounts"
COLL_POSITIONS = "paper_positions"
COLL_ORDERS = "paper_orders"
COLL_EVENTS = "paper_events"

_lock = threading.RLock()
_client: Optional[MongoClient] = None


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now_utc().isoformat()


def _db():
    global _client
    if _client is None:
        _client = MongoClient(os.environ.get("MONGO_URL"))
    return _client[os.environ.get("DB_NAME", "test_database")]


def _safe(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception:
        return None


# ─── Gate ──────────────────────────────────────────────────────────────
def _check_operator_mode() -> Tuple[bool, str]:
    """Operator mode must be explicitly 'paper'.  No silent paper enablement."""
    try:
        db = _db()
        # operator_access stores per-user capability docs; in this phase we
        # look for ANY operator account whose mode field equals 'paper'.
        # Absence ⇒ closed.  This will be replaced by per-request gating
        # once auth wiring lands.
        doc = db.operator_access.find_one({"mode": "paper"})
        if doc:
            return True, "operator_mode_paper"
    except Exception:
        pass
    return False, "operator_mode_paper"


def _check_shadow_recent() -> Tuple[bool, str]:
    try:
        cutoff = (_now_utc() - timedelta(hours=RECENT_SHADOW_WINDOW_HOURS)).isoformat()
        count = _db().shadow_verdicts.count_documents({"createdAt": {"$gte": cutoff}})
        return count > 0, "validated_shadow_runtime"
    except Exception:
        return False, "validated_shadow_runtime"


def _check_outcome_resolved() -> Tuple[bool, str]:
    try:
        count = _db().mbrain_integrity_outcomes.count_documents({"status": "resolved"})
        return count > 0, "mature_outcomes"
    except Exception:
        return False, "mature_outcomes"


def _check_market_prices_healthy() -> Tuple[bool, str]:
    """All universe symbols must have non-degraded live prices."""
    try:
        from services.market_prices import get_price  # type: ignore
    except Exception:
        return False, "market_prices_healthy"
    for sym in UNIVERSE:
        p = _safe(get_price, sym)
        if not (isinstance(p, dict) and p.get("ok") and p.get("price") and not p.get("degraded")):
            return False, "market_prices_healthy"
    return True, "market_prices_healthy"


def paper_runtime_gate() -> dict:
    """Compose all gate preconditions.  Returns gate state + missing requirements."""
    checks = [
        _check_outcome_resolved(),       # mature_outcomes
        _check_shadow_recent(),          # validated_shadow_runtime
        _check_operator_mode(),          # operator_mode_paper
        _check_market_prices_healthy(),  # market_prices_healthy
    ]
    passing = [name for ok, name in checks if ok]
    missing = [name for ok, name in checks if not ok]
    open_gate = len(missing) == 0
    result = {
        "open": open_gate,
        "passing": passing,
        "requires": missing,
        "evaluatedAt": _now_iso(),
    }

    # Phase D Pass 1 · forward-only continuity trace — emit only on state
    # transition (open↔closed), not on every gate call.  Best-effort.
    try:
        last = _db()["paper_gate_state"].find_one({"_id": "current"})
        prev_open = bool(last.get("open")) if last else None
        if prev_open is None or prev_open != open_gate:
            from services.runtime_events import emit as _emit
            _emit("PAPER_GATE_STATE_CHANGED", {
                "open": open_gate,
                "requires": missing,
                "passing": passing,
            })
            _db()["paper_gate_state"].update_one(
                {"_id": "current"},
                {"$set": {"open": open_gate, "at": _now_iso()}},
                upsert=True,
            )
    except Exception:
        pass

    return result


# ─── Audit ─────────────────────────────────────────────────────────────
def _record_event(event_type: str, payload: dict) -> None:
    """Append-only ledger of gate decisions / simulate intents.

    Lightweight; never blocks.  Allows post-hoc audit even though no
    execution has occurred.  Capped via TTL-style trimming in future."""
    try:
        _db()[COLL_EVENTS].insert_one({
            "type": event_type,
            "payload": payload,
            "createdAt": _now_iso(),
        })
    except Exception:
        pass


# ─── Public API ────────────────────────────────────────────────────────
def service_health() -> dict:
    with _lock:
        db = _db()
        try:
            accounts = db[COLL_ACCOUNTS].count_documents({})
            positions = db[COLL_POSITIONS].count_documents({})
            orders = db[COLL_ORDERS].count_documents({})
            events = db[COLL_EVENTS].count_documents({})
        except Exception as e:
            return {"ok": False, "reason": f"db_error: {e!r}"}

        gate = paper_runtime_gate()
        return {
            "ok": True,
            "gate": gate,
            "collections": {
                "accounts": accounts,
                "positions": positions,
                "orders": orders,
                "events": events,
            },
            "universe": list(UNIVERSE),
            "phase": "C · foundation skeleton",
            "active": False,
            "note": (
                "paper runtime is not active. shadow memory is still forming. "
                "no execution surface exposed."
            ),
            "asOf": _now_iso(),
        }


def list_accounts() -> dict:
    try:
        rows = list(
            _db()[COLL_ACCOUNTS].find({}, {"_id": 0}).sort("createdAt", -1).limit(50)
        )
        return {"ok": True, "count": len(rows), "items": rows, "asOf": _now_iso()}
    except Exception as e:
        return {"ok": False, "reason": f"db_error: {e!r}", "count": 0, "items": []}


def list_positions() -> dict:
    try:
        rows = list(
            _db()[COLL_POSITIONS].find({}, {"_id": 0}).sort("createdAt", -1).limit(100)
        )
        return {"ok": True, "count": len(rows), "items": rows, "asOf": _now_iso()}
    except Exception as e:
        return {"ok": False, "reason": f"db_error: {e!r}", "count": 0, "items": []}


def list_events(limit: int = 50) -> dict:
    try:
        rows = list(
            _db()[COLL_EVENTS]
            .find({}, {"_id": 0})
            .sort("createdAt", -1)
            .limit(max(1, min(int(limit), 200)))
        )
        return {"ok": True, "count": len(rows), "items": rows, "asOf": _now_iso()}
    except Exception as e:
        return {"ok": False, "reason": f"db_error: {e!r}", "count": 0, "items": []}


def list_orders(limit: int = 50) -> dict:
    try:
        rows = list(
            _db()[COLL_ORDERS]
            .find({}, {"_id": 0})
            .sort("createdAt", -1)
            .limit(max(1, min(int(limit), 200)))
        )
        return {"ok": True, "count": len(rows), "items": rows, "asOf": _now_iso()}
    except Exception as e:
        return {"ok": False, "reason": f"db_error: {e!r}", "count": 0, "items": []}


def simulate_order(payload: Optional[dict] = None) -> dict:
    """Gated simulate intent.

    When gate is closed (current state by design): returns the explicit
    structured refusal with required preconditions.  NO write to
    paper_orders / paper_positions.  The intent itself is appended to
    paper_events for audit transparency.
    """
    gate = paper_runtime_gate()
    _record_event("simulate_intent", {
        "intent": payload or {},
        "gateOpen": gate["open"],
        "requires": gate["requires"],
    })

    if not gate["open"]:
        return {
            "ok": False,
            "reason": "paper_runtime_not_enabled",
            "requires": gate["requires"],
            "passing": gate["passing"],
            "phase": "C · foundation skeleton",
            "asOf": _now_iso(),
        }

    # Future paper execution path (deliberately not implemented in Phase C).
    return {
        "ok": False,
        "reason": "paper_runtime_simulation_not_implemented",
        "phase": "C · foundation skeleton",
        "asOf": _now_iso(),
    }



# ═══════════════════════════════════════════════════════════════════════
# Phase D Pass 2B — Canonical adapter (derived cognition: paper_runtime)
# ═══════════════════════════════════════════════════════════════════════
# DISCIPLINE: while `gate.open == False` (Phase C), the canonical state is
# ALWAYS 'suppressed'. This is correct — paper runtime explicitly refuses
# to take a directional posture until the gate opens. No fake 'active
# paper cognition' (A9 — never amplify certainty).


def canonical(payload):
    """
    Adapt a raw `paper_runtime.service_health()` result to a CognitionSnapshot.

    Pure: no DB, no network, no recomputation.

    State derivation:
      ok=False                                 → 'degraded'
      gate.open == True AND active == True     → 'active'   (future Phase D+)
      gate.open == False                       → 'suppressed'  (current Phase C)
      gate.open == True AND active == False    → 'wait'     (gate just opened
                                                              but runtime not yet
                                                              taking positions)

    Direction: ALWAYS None (paper runtime is a gated execution layer; it
              does not produce a directional reading itself — that comes
              from the upstream cognition modules).
    Confidence: ALWAYS None.

    Reasons: derived from `gate.requires` and `gate.passing` arrays, which
             are already snake-case tokens.
    """
    from services.runtime_contract import (
        CognitionSnapshot, make_insufficient,
    )

    if not isinstance(payload, dict) or not payload:
        return make_insufficient(
            module="paper",
            source="paper_runtime_gate",
            reasons=("missing_paper_payload",),
        )

    source = "paper_runtime_gate"
    updated_at = payload.get("asOf")

    if not payload.get("ok"):
        reason = str(payload.get("reason") or "paper_unavailable").lower()
        return CognitionSnapshot.build(
            module="paper",
            source=source,
            state="degraded",
            reasons=(reason.replace(" ", "_").replace(":", "_")[:64],),
            degraded=True,
            updatedAt=updated_at,
        )

    gate = payload.get("gate") or {}
    gate_open = bool(gate.get("open"))
    active = bool(payload.get("active"))

    if gate_open and active:
        state = "active"
    elif not gate_open:
        state = "suppressed"
    else:
        # gate open but not yet active
        state = "wait"

    # Reason tokens — preserve substrate honestly.
    reasons = []
    for r in (gate.get("requires") or []):
        if not r: continue
        tok = f"requires_{str(r).strip().lower().replace(' ', '_')}"
        if tok not in reasons:
            reasons.append(tok)
    for p in (gate.get("passing") or []):
        if not p: continue
        tok = f"passing_{str(p).strip().lower().replace(' ', '_')}"
        if tok not in reasons:
            reasons.append(tok)

    if state == "suppressed" and not reasons:
        reasons.append("gate_closed")

    return CognitionSnapshot.build(
        module="paper",
        source=source,
        state=state,
        direction=None,
        confidence=None,
        reasons=reasons or ("paper_state_pending",),
        degraded=False,
        updatedAt=updated_at,
    )
