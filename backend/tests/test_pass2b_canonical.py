"""
Acceptance tests for Phase D Pass 2B canonical adapters
(shadow, outcome_memory, paper, observatory).

A1..A8 same as Pass 2A, plus:
  A9 — Canonical adapters preserve restraint: never amplify certainty.
       If raw payload is WAIT/blocked/insufficient/degraded, canonical
       state can never become 'active'.

Run from /app/backend:
    /root/.venv/bin/python3 -m pytest tests/test_pass2b_canonical.py -q
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/app/backend")

from services.runtime_contract import (
    CognitionSnapshot,
    DIRECTION_ENUM,
    FORBIDDEN_REASON_TOKENS,
    STATE_ENUM,
)

import services.shadow_verdict_runtime as shadow_mod
import services.outcome_memory as outcome_mod
import services.paper_runtime as paper_mod
import services.operator_observatory as obs_mod


ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _assert_invariants(snap, expected_module):
    """A2/A3/A4/A8 invariants — common to every canonical snapshot."""
    assert isinstance(snap, CognitionSnapshot)
    d = snap.to_dict()
    assert d["module"] == expected_module
    assert d["state"] in STATE_ENUM
    if d["state"] != "active":
        assert d["direction"] is None
        assert d["confidence"] is None
    if d["confidence"] is not None:
        assert 0.0 <= d["confidence"] <= 1.0
    assert ISO_RE.match(d["updatedAt"]), d["updatedAt"]
    for r in d["reasons"]:
        for forbidden in FORBIDDEN_REASON_TOKENS:
            assert forbidden not in r, f"forbidden vocab '{forbidden}' in '{r}'"


# ─────────────────────────────────────────────────────────────────────
# SHADOW
# ─────────────────────────────────────────────────────────────────────

_SHADOW_BLOCKED = {
    "symbol": "BTC", "mode": "shadow", "status": "blocked",
    "rawAction": "NEUTRAL", "finalAction": "WAIT",
    "shadowAction": "NO_DEPLOYMENT",
    "reason": [
        "MetaBrain canonical decision: WAIT",
        "fractal compression — no expansion phase",
        "sentiment bullish but not cross-confirmed",
        "insufficient cross-module alignment",
    ],
    "deploymentBlockedBy": ["metaDecision", "fractal", "technical_alignment", "price_unavailable"],
    "hypothetical": None,
    "createdAt": "2026-05-11T20:30:00Z",
}

_SHADOW_WAIT = {**_SHADOW_BLOCKED, "status": "wait"}
_SHADOW_CONSIDERED = {**_SHADOW_BLOCKED, "status": "considered", "shadowAction": "PROCEED"}
_SHADOW_UNRESOLVED = {**_SHADOW_BLOCKED, "status": "unresolved"}


def test_shadow_blocked_maps_to_suppressed():
    s = shadow_mod.canonical(_SHADOW_BLOCKED)
    _assert_invariants(s, "shadow")
    assert s.state == "suppressed"
    assert s.direction is None
    assert s.confidence is None
    # Reasons include both the free-text mappings AND deploymentBlockedBy
    assert "meta_canonical_wait" in s.reasons
    assert "fractal_compression" in s.reasons
    assert any(r.startswith("blocked_by_") for r in s.reasons)


def test_shadow_wait_maps_to_wait():
    s = shadow_mod.canonical(_SHADOW_WAIT)
    _assert_invariants(s, "shadow")
    assert s.state == "wait"


def test_shadow_considered_maps_to_active():
    s = shadow_mod.canonical(_SHADOW_CONSIDERED)
    _assert_invariants(s, "shadow")
    assert s.state == "active"
    # Discipline: even 'considered' carries no direction/confidence in canonical.
    assert s.direction is None
    assert s.confidence is None


def test_shadow_unresolved_maps_to_degraded():
    s = shadow_mod.canonical(_SHADOW_UNRESOLVED)
    _assert_invariants(s, "shadow")
    assert s.state == "degraded"
    assert s.degraded is True


def test_shadow_unknown_status_degrades():
    s = shadow_mod.canonical({**_SHADOW_BLOCKED, "status": "nonsense_value"})
    _assert_invariants(s, "shadow")
    assert s.state == "degraded"


def test_shadow_missing_payload():
    s = shadow_mod.canonical(None)
    _assert_invariants(s, "shadow")
    assert s.state == "insufficient"


# ─────────────────────────────────────────────────────────────────────
# OUTCOME MEMORY
# ─────────────────────────────────────────────────────────────────────

_OUTCOME_EMPTY = {
    "ok": False, "reason": "insufficient_decision_context",
    "totalDecisions": 0, "asOf": "2026-05-11T20:30:00Z",
}

_OUTCOME_MATURING = {
    "ok": True, "pending": 108, "resolved": 0, "expired": 0,
    "totalOutcomes": 108, "totalDecisions": 216,
    "coveragePct": 0.5, "maturePending": 0,
    "classifications": {}, "asOf": "2026-05-11T20:30:00Z",
}

_OUTCOME_ESTABLISHED = {
    "ok": True, "pending": 60, "resolved": 40, "expired": 8,
    "totalOutcomes": 108, "totalDecisions": 120,
    "coveragePct": 0.9, "maturePending": 2,
    "classifications": {"realized_gain": 10, "avoided_loss": 20, "neutral_wait": 10},
    "asOf": "2026-05-11T20:30:00Z",
}

_OUTCOME_DEGRADED = {
    "ok": False, "reason": "db_error: PyMongoError",
    "asOf": "2026-05-11T20:30:00Z",
}


def test_outcome_empty_is_insufficient():
    s = outcome_mod.canonical(_OUTCOME_EMPTY)
    _assert_invariants(s, "outcome_memory")
    assert s.state == "insufficient"
    assert s.direction is None
    assert s.confidence is None


def test_outcome_maturing_is_wait():
    s = outcome_mod.canonical(_OUTCOME_MATURING)
    _assert_invariants(s, "outcome_memory")
    assert s.state == "wait"
    assert "memory_maturing" in s.reasons
    assert s.direction is None
    assert s.confidence is None


def test_outcome_established_is_active():
    s = outcome_mod.canonical(_OUTCOME_ESTABLISHED)
    _assert_invariants(s, "outcome_memory")
    assert s.state == "active"
    # CRITICAL: outcome memory is accountability — even when active,
    # direction and confidence remain None.
    assert s.direction is None
    assert s.confidence is None
    assert "memory_established" in s.reasons


def test_outcome_degraded():
    s = outcome_mod.canonical(_OUTCOME_DEGRADED)
    _assert_invariants(s, "outcome_memory")
    assert s.state == "degraded"


def test_outcome_missing_payload():
    s = outcome_mod.canonical(None)
    assert s.state == "insufficient"


# ─────────────────────────────────────────────────────────────────────
# PAPER RUNTIME
# ─────────────────────────────────────────────────────────────────────

_PAPER_GATE_CLOSED = {
    "ok": True,
    "gate": {
        "open": False,
        "passing": ["validated_shadow_runtime", "market_prices_healthy"],
        "requires": ["mature_outcomes", "operator_mode_paper"],
        "evaluatedAt": "2026-05-11T20:30:00Z",
    },
    "collections": {"accounts": 0, "positions": 0, "orders": 0, "events": 3},
    "universe": ["BTC", "ETH", "SOL"],
    "phase": "C · foundation skeleton", "active": False,
    "note": "paper runtime is not active.",
    "asOf": "2026-05-11T20:30:00Z",
}

_PAPER_GATE_OPEN_INACTIVE = {
    **_PAPER_GATE_CLOSED,
    "gate": {**_PAPER_GATE_CLOSED["gate"], "open": True, "requires": [], "passing": ["validated_shadow_runtime", "market_prices_healthy", "mature_outcomes", "operator_mode_paper"]},
    "active": False,
}

_PAPER_GATE_OPEN_ACTIVE = {
    **_PAPER_GATE_OPEN_INACTIVE,
    "active": True,
}

_PAPER_DEGRADED = {
    "ok": False, "reason": "db_error: timeout",
    "asOf": "2026-05-11T20:30:00Z",
}


def test_paper_gate_closed_is_suppressed():
    s = paper_mod.canonical(_PAPER_GATE_CLOSED)
    _assert_invariants(s, "paper")
    # Discipline: gate closed → suppressed (NOT 'wait', NOT 'insufficient')
    assert s.state == "suppressed"
    assert s.direction is None
    assert s.confidence is None
    assert any("requires_mature_outcomes" in r for r in s.reasons)
    assert any("passing_validated_shadow_runtime" in r for r in s.reasons)


def test_paper_gate_open_inactive_is_wait():
    s = paper_mod.canonical(_PAPER_GATE_OPEN_INACTIVE)
    _assert_invariants(s, "paper")
    assert s.state == "wait"


def test_paper_gate_open_active_is_active():
    s = paper_mod.canonical(_PAPER_GATE_OPEN_ACTIVE)
    _assert_invariants(s, "paper")
    assert s.state == "active"
    # Even when active, paper carries no direction/confidence in canonical layer.
    assert s.direction is None
    assert s.confidence is None


def test_paper_degraded():
    s = paper_mod.canonical(_PAPER_DEGRADED)
    _assert_invariants(s, "paper")
    assert s.state == "degraded"


def test_paper_missing_payload():
    s = paper_mod.canonical(None)
    assert s.state == "insufficient"


# ─────────────────────────────────────────────────────────────────────
# OBSERVATORY
# ─────────────────────────────────────────────────────────────────────

_OBS_FULL = {
    "ok": True, "asOf": "2026-05-11T20:30:00Z",
    "universe": ["BTC", "ETH", "SOL"],
    "deploymentClimate": {"ok": True, "phrase": "..."},
    "alignmentDrift": {"ok": True, "phrase": "..."},
    "cognitiveMemory": {"ok": True, "phrase": "..."},
    "shadowStructures": {"ok": True, "phrase": "..."},
    "regimeContinuity": {"ok": True, "phrase": "..."},
}

_OBS_PARTIAL = {
    **_OBS_FULL,
    "cognitiveMemory": {"ok": False, "phrase": "insufficient"},
    "shadowStructures": {"ok": False, "phrase": "insufficient"},
}

_OBS_ALL_DOWN = {
    **_OBS_FULL,
    "deploymentClimate": {"ok": False},
    "alignmentDrift": {"ok": False},
    "cognitiveMemory": {"ok": False},
    "shadowStructures": {"ok": False},
    "regimeContinuity": {"ok": False},
}

_OBS_INSUFFICIENT = {
    "ok": False, "reason": "insufficient_decision_context",
    "phrase": "Insufficient continuity for interpretive surface.",
    "asOf": "2026-05-11T20:30:00Z",
}


def test_observatory_full_is_active():
    s = obs_mod.canonical(_OBS_FULL)
    _assert_invariants(s, "observatory")
    assert s.state == "active"
    # Observatory is interpretive — direction/confidence ALWAYS None even when active.
    assert s.direction is None
    assert s.confidence is None


def test_observatory_partial_is_wait():
    s = obs_mod.canonical(_OBS_PARTIAL)
    _assert_invariants(s, "observatory")
    assert s.state == "wait"
    assert any("section_unavailable_" in r for r in s.reasons)


def test_observatory_all_down_is_degraded():
    s = obs_mod.canonical(_OBS_ALL_DOWN)
    _assert_invariants(s, "observatory")
    assert s.state == "degraded"


def test_observatory_insufficient():
    s = obs_mod.canonical(_OBS_INSUFFICIENT)
    _assert_invariants(s, "observatory")
    assert s.state == "insufficient"


# ─────────────────────────────────────────────────────────────────────
# A9 — Canonical adapters NEVER amplify certainty
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,adapter,module",
    [
        # Shadow: any non-considered status MUST NOT become 'active'
        (_SHADOW_BLOCKED, shadow_mod.canonical, "shadow"),
        (_SHADOW_WAIT, shadow_mod.canonical, "shadow"),
        (_SHADOW_UNRESOLVED, shadow_mod.canonical, "shadow"),
        # Outcome: empty/maturing/degraded MUST NOT become 'active'
        (_OUTCOME_EMPTY, outcome_mod.canonical, "outcome_memory"),
        (_OUTCOME_MATURING, outcome_mod.canonical, "outcome_memory"),
        (_OUTCOME_DEGRADED, outcome_mod.canonical, "outcome_memory"),
        # Paper: gate-closed MUST NEVER become 'active'
        (_PAPER_GATE_CLOSED, paper_mod.canonical, "paper"),
        (_PAPER_GATE_OPEN_INACTIVE, paper_mod.canonical, "paper"),
        (_PAPER_DEGRADED, paper_mod.canonical, "paper"),
        # Observatory: partial/all-down/insufficient MUST NEVER become 'active'
        (_OBS_PARTIAL, obs_mod.canonical, "observatory"),
        (_OBS_ALL_DOWN, obs_mod.canonical, "observatory"),
        (_OBS_INSUFFICIENT, obs_mod.canonical, "observatory"),
    ],
)
def test_A9_no_certainty_amplification(raw, adapter, module):
    """A9 — Canonical layer only preserves or reduces certainty, never amplifies.
    If raw payload is in a non-deployment / restraint state, the canonical
    state must NOT be 'active'."""
    snap = adapter(raw)
    assert snap.module == module
    assert snap.state != "active", (
        f"A9 VIOLATION ({module}): non-deployment raw payload "
        f"was amplified to 'active' state"
    )


# ─────────────────────────────────────────────────────────────────────
# A7 — purity (no I/O during canonical())
# ─────────────────────────────────────────────────────────────────────


def _io_tripwire():
    import socket
    import urllib.request

    class Tripwire:
        def __init__(self, name):
            self.name = name
        def __call__(self, *a, **kw):
            raise AssertionError(f"adapter performed I/O: {self.name}")

    orig = {
        "socket.create_connection": socket.create_connection,
        "urllib.request.urlopen": urllib.request.urlopen,
    }
    socket.create_connection = Tripwire("socket.create_connection")
    urllib.request.urlopen = Tripwire("urlopen")

    def restore():
        socket.create_connection = orig["socket.create_connection"]
        urllib.request.urlopen = orig["urllib.request.urlopen"]
    return restore


def test_shadow_adapter_pure_no_io():
    restore = _io_tripwire()
    try:
        shadow_mod.canonical(_SHADOW_BLOCKED)
        shadow_mod.canonical(_SHADOW_CONSIDERED)
        shadow_mod.canonical(None)
    finally:
        restore()


def test_outcome_adapter_pure_no_io():
    restore = _io_tripwire()
    try:
        outcome_mod.canonical(_OUTCOME_EMPTY)
        outcome_mod.canonical(_OUTCOME_ESTABLISHED)
        outcome_mod.canonical(None)
    finally:
        restore()


def test_paper_adapter_pure_no_io():
    restore = _io_tripwire()
    try:
        paper_mod.canonical(_PAPER_GATE_CLOSED)
        paper_mod.canonical(_PAPER_GATE_OPEN_ACTIVE)
        paper_mod.canonical(None)
    finally:
        restore()


def test_observatory_adapter_pure_no_io():
    restore = _io_tripwire()
    try:
        obs_mod.canonical(_OBS_FULL)
        obs_mod.canonical(_OBS_INSUFFICIENT)
        obs_mod.canonical(None)
    finally:
        restore()


# ─────────────────────────────────────────────────────────────────────
# Discipline check — runtime_contract.py contains no score-fusion words
# ─────────────────────────────────────────────────────────────────────


def test_runtime_contract_no_fusion_concepts():
    """Pass 2B explicit constraint — the canonical contract layer must NOT
    introduce score fusion / aggregate confidence / meta_score concepts."""
    import services.runtime_contract as rc
    src = open(rc.__file__).read().lower()
    forbidden_concepts = [
        "aggregate_confidence",
        "weighted_mean",
        "weighted_average",
        "meta_score",
        "alignment_index",
        "fusion",
        "ensemble_score",
    ]
    for bad in forbidden_concepts:
        assert bad not in src, (
            f"runtime_contract.py contains forbidden concept '{bad}' — "
            f"Pass 2B explicitly bans score fusion in canonical layer."
        )


# ─────────────────────────────────────────────────────────────────────
# A1 — Public APIs unchanged structurally for Pass 2B endpoints
# ─────────────────────────────────────────────────────────────────────

GOLDEN_DIR = Path("/app/memory/golden")


@pytest.mark.parametrize(
    "name,url",
    [
        ("shadow_runtime_summary", "http://localhost:8001/api/mbrain/shadow-runtime/summary?symbols=BTC,ETH,SOL"),
        ("outcomes_health", "http://localhost:8001/api/mbrain/outcomes/health"),
        ("paper_runtime_health", "http://localhost:8001/api/paper/runtime/health"),
        ("observatory_state", "http://localhost:8001/api/mbrain/observatory/state"),
    ],
)
def test_pass2b_endpoints_structurally_unchanged(name, url):
    import urllib.request
    raw_baseline = GOLDEN_DIR / f"{name}.raw.json"
    if not raw_baseline.exists():
        pytest.skip(f"golden baseline missing for {name}")
    expected_dict = json.loads(raw_baseline.read_text())

    with urllib.request.urlopen(url, timeout=10) as resp:
        body = resp.read()
    try:
        actual_dict = json.loads(body)
    except json.JSONDecodeError:
        pytest.skip(f"endpoint {url} not JSON")

    def shape(o, prefix=""):
        out = set()
        if isinstance(o, dict):
            for k, v in o.items():
                out.add(f"{prefix}.{k}")
                out |= shape(v, f"{prefix}.{k}")
        elif isinstance(o, list):
            if o:
                for x in o[:3]:
                    out |= shape(x, f"{prefix}[]")
            else:
                out.add(f"{prefix}[]:empty")
        else:
            out.add(f"{prefix}:{type(o).__name__ if o is not None else 'null'}")
        return out

    def normalize_numeric(s):
        for tag in (":int", ":float"):
            if s.endswith(tag):
                return s[: -len(tag)] + ":<num>"
        return s

    es = {normalize_numeric(x) for x in shape(expected_dict)}
    ac = {normalize_numeric(x) for x in shape(actual_dict)}
    added = sorted(ac - es)
    removed = sorted(es - ac)
    if added or removed:
        pytest.fail(
            f"\n{name}: STRUCTURAL DRIFT (A1 violation)\n"
            f"  added:   {added[:30]}\n"
            f"  removed: {removed[:30]}"
        )
