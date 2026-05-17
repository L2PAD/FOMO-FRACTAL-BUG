"""
operator_observatory — Operator Cognition Observatory aggregator.

NOT an admin dashboard.  NOT Grafana.  NOT telemetry wall.  NOT KPI center.

Reflective interpretive surface for operators.  Composes already-live
substrate (shadow runtime + outcome memory + sentiment + fractal + TA)
into 5 quiet topological sections:

    1. deploymentClimate     — current restraint field
    2. alignmentDrift        — per-symbol cross-module coherence (text)
    3. cognitiveMemory       — outcomes accumulation (not performance)
    4. shadowStructures      — blocked/wait/considered/unresolved topology
    5. regimeContinuity      — fractal phase persistence per symbol

Forbidden vocabulary (enforced at field-name level):
    accuracy · winRate · success · ROI · PnL · profit · alpha

Allowed vocabulary:
    restraint · integrity · coherence · continuity · accumulation ·
    persistence · field · drift · climate · topology

Behavior:
    - Strictly manual.  No scheduling.  No background recomputation.
    - Returns ok=false, reason='insufficient_decision_context' when
      decision_history is empty (do NOT pretend the layer is alive).
    - All text fields are interpretive phrases — never numerical labels.
"""
from __future__ import annotations

import os
import threading
from collections import Counter
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from pymongo import MongoClient


# ─── Configuration ──────────────────────────────────────────────────────
UNIVERSE = ["BTC", "ETH", "SOL"]   # canonical cognitive runtime universe

# Coherence labels (cross-module agreement state, not signal direction)
COHERENCE_ALIGNED = "aligned"      # ≥2 layers agree on direction
COHERENCE_PARTIAL = "partial"      # only one layer takes a directional view
COHERENCE_DIVERGENT = "divergent"  # layers point in opposite directions
COHERENCE_SILENT = "silent"        # all layers neutral / unavailable

DIR_LONG = "LONG_BIAS"
DIR_SHORT = "SHORT_BIAS"
DIR_NEUTRAL = "NEUTRAL"


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


# ─── Layer direction normalizer ────────────────────────────────────────
def _layer_direction(layer: Optional[dict]) -> str:
    if not isinstance(layer, dict):
        return DIR_NEUTRAL
    d = (layer.get("direction") or "").upper().strip()
    if d == DIR_LONG:
        return DIR_LONG
    if d == DIR_SHORT:
        return DIR_SHORT
    return DIR_NEUTRAL


# ─── Section 1 · Deployment Climate ────────────────────────────────────
def _deployment_climate() -> dict:
    """Restraint field across the cognitive runtime universe."""
    try:
        from services.shadow_verdict_runtime import summary as _shadow_summary  # type: ignore
    except Exception:
        return {
            "ok": False,
            "reason": "shadow_runtime_unavailable",
            "phrase": "deployment climate unobserved",
        }

    s = _safe(_shadow_summary, UNIVERSE) or {}
    if not s.get("ok") or (s.get("totalVerdicts") or 0) == 0:
        return {
            "ok": False,
            "reason": "no_shadow_verdicts_swept",
            "phrase": "deployment climate not yet observed · run shadow sweep first",
            "totalVerdicts": s.get("totalVerdicts", 0),
        }

    dist = s.get("distribution") or {}
    total = sum(dist.values()) or 1
    blocked_pct = (dist.get("blocked", 0) / total)
    wait_pct = (dist.get("wait", 0) / total)
    considered_pct = (dist.get("considered", 0) / total)
    unresolved_pct = (dist.get("unresolved", 0) / total)

    # Dominant climate phrase — interpretive, not numerical
    if blocked_pct >= 0.75:
        phrase = "restraint dominant · canonical veto suppressing partial cognitive bias"
        integrity = "high restraint integrity"
    elif blocked_pct >= 0.4 and wait_pct >= 0.2:
        phrase = "restraint held intermittently · mixed neutrality with vetoed signals"
        integrity = "stable restraint integrity"
    elif wait_pct >= 0.7:
        phrase = "system mostly silent · cognition layers neutral across universe"
        integrity = "neutral cognitive field"
    elif considered_pct >= 0.3:
        phrase = "structural consideration emerging · cross-module alignment partially forming"
        integrity = "alignment emerging"
    elif unresolved_pct >= 0.3:
        phrase = "directional pressure unresolved · canonical and cognitive layers disagree"
        integrity = "alignment drift detected"
    else:
        phrase = "mixed deployment climate · no dominant posture"
        integrity = "mixed restraint field"

    # Top vetoing layer attribution
    top_blocked_by = s.get("topBlockedBy") or []
    primary_veto = None
    if top_blocked_by:
        primary_veto = top_blocked_by[0][0]  # most_common first
    veto_label_map = {
        "metaDecision": "canonical MetaBrain veto",
        "fractal": "fractal compression",
        "technical_alignment": "thin technical alignment",
        "sentiment_confidence": "low sentiment confidence",
        "price_unavailable": "missing price substrate",
    }
    veto_phrase = veto_label_map.get(primary_veto, primary_veto) if primary_veto else None

    return {
        "ok": True,
        "phrase": phrase,
        "restraintIntegrity": integrity,
        "primaryVetoLayer": primary_veto,
        "primaryVetoPhrase": veto_phrase,
        "totalVerdicts": s.get("totalVerdicts"),
    }


# ─── Section 2 · Alignment Drift ───────────────────────────────────────
def _alignment_drift() -> dict:
    """Per-symbol cross-module coherence — textual topology, no grids."""
    # Isolated lazy imports so any single layer failure doesn't sink the section.
    _ta = _sent = _frac = None
    try:
        from services.technical_analysis import analyze as _ta  # type: ignore
    except Exception:
        pass
    try:
        from services.sentiment_runtime import runtime as _sent  # type: ignore
    except Exception:
        pass
    try:
        from services.fractal_runtime import runtime as _frac  # type: ignore
    except Exception:
        pass

    if not (_sent or _frac or _ta):
        return {
            "ok": False,
            "reason": "cognition_runtimes_unavailable",
            "perSymbol": {},
        }

    per_symbol: Dict[str, dict] = {}
    aligned = 0
    divergent = 0
    silent = 0
    partial = 0

    for sym in UNIVERSE:
        ta = _safe(_ta, sym) if _ta else None
        sent = _safe(_sent, sym) if _sent else None
        frac = _safe(_frac, sym) if _frac else None
        ta_d = _layer_direction(ta)
        sent_d = _layer_direction(sent)
        frac_d = _layer_direction(frac)

        longs = sum(1 for d in (ta_d, sent_d, frac_d) if d == DIR_LONG)
        shorts = sum(1 for d in (ta_d, sent_d, frac_d) if d == DIR_SHORT)

        if longs >= 2 and shorts == 0:
            coherence = COHERENCE_ALIGNED
            phrase = "layers align toward long-side cognitive bias"
            aligned += 1
        elif shorts >= 2 and longs == 0:
            coherence = COHERENCE_ALIGNED
            phrase = "layers align toward short-side cognitive bias"
            aligned += 1
        elif longs >= 1 and shorts >= 1:
            coherence = COHERENCE_DIVERGENT
            phrase = "cognition layers disagree on direction"
            divergent += 1
        elif longs == 1 or shorts == 1:
            coherence = COHERENCE_PARTIAL
            phrase = "only one layer takes a directional view"
            partial += 1
        else:
            coherence = COHERENCE_SILENT
            phrase = "all layers structurally neutral"
            silent += 1

        per_symbol[sym] = {
            "coherence": coherence,
            "phrase": phrase,
            "layers": {
                "technical": ta_d.lower().replace("_bias", ""),
                "sentiment": sent_d.lower().replace("_bias", ""),
                "fractal": frac_d.lower().replace("_bias", ""),
            },
        }

    # Universe-wide drift narrative
    if aligned >= 2:
        drift = "cross-module coherence forming across multiple assets"
    elif divergent >= 2:
        drift = "structural disagreement persists across assets"
    elif silent >= 2:
        drift = "cognitive field largely silent across the universe"
    else:
        drift = "mixed coherence · individual asset readings divergent"

    return {
        "ok": True,
        "driftPhrase": drift,
        "perSymbol": per_symbol,
    }


# ─── Section 3 · Cognitive Memory ──────────────────────────────────────
def _cognitive_memory() -> dict:
    """Outcomes as continuity / accumulation — NEVER performance."""
    try:
        from services.outcome_memory import service_health as _outcomes_health  # type: ignore
    except Exception:
        return {"ok": False, "reason": "outcome_memory_unavailable"}

    h = _safe(_outcomes_health) or {}
    if not h.get("ok"):
        return {
            "ok": False,
            "reason": h.get("reason", "outcome_memory_unavailable"),
        }

    pending = h.get("pending", 0)
    resolved = h.get("resolved", 0)
    expired = h.get("expired", 0)
    total_outcomes = h.get("totalOutcomes", 0)
    total_decisions = h.get("totalDecisions", 0)
    mature = h.get("maturePending", 0)
    cls = h.get("classifications") or {}

    # Continuity phrase — accumulation language
    if total_decisions == 0:
        phrase = "memory substrate empty"
    elif total_outcomes == 0:
        phrase = "memory unwritten · sweep has not run"
    elif resolved == 0 and mature == 0:
        phrase = "memory accumulating · no decisions matured yet"
    elif resolved == 0 and mature > 0:
        phrase = "memory accumulating · mature decisions awaiting resolution"
    elif resolved > 0 and resolved < 5:
        phrase = "memory beginning to crystallize · first resolved outcomes"
    elif resolved >= 5:
        phrase = "memory continuity stable · interpretation gaining substrate"
    else:
        phrase = "memory accumulating"

    # Classification topology — quiet labels, no proportions
    cls_topology: List[dict] = []
    for k in ("avoided_loss", "missed_gain", "neutral_wait",
              "realized_gain", "realized_loss", "neutral_realized"):
        c = cls.get(k, 0)
        if c > 0:
            cls_topology.append({"classification": k.replace("_", " "), "count": c})

    return {
        "ok": True,
        "phrase": phrase,
        "pending": pending,
        "resolved": resolved,
        "expired": expired,
        "maturePending": mature,
        "totalOutcomes": total_outcomes,
        "totalDecisions": total_decisions,
        "coverage": h.get("coveragePct", 0.0),
        "classifications": cls_topology,
    }


# ─── Section 4 · Shadow Structures ─────────────────────────────────────
def _shadow_structures() -> dict:
    """Distribution of shadow verdicts as cognitive topology, not scoreboard."""
    try:
        from services.shadow_verdict_runtime import summary as _shadow_summary  # type: ignore
    except Exception:
        return {"ok": False, "reason": "shadow_runtime_unavailable"}

    s = _safe(_shadow_summary, UNIVERSE) or {}
    if not s.get("ok") or (s.get("totalVerdicts") or 0) == 0:
        return {
            "ok": False,
            "reason": "no_shadow_verdicts_swept",
            "phrase": "shadow topology not yet observed · run shadow sweep first",
        }

    dist = s.get("distribution") or {}
    total = sum(dist.values()) or 1

    # Topology phrase
    blocked = dist.get("blocked", 0)
    wait = dist.get("wait", 0)
    considered = dist.get("considered", 0)
    unresolved = dist.get("unresolved", 0)

    over_suppress = (blocked / total) >= 0.85 and considered == 0
    if over_suppress:
        topology = "shadow field heavily suppressed · cognitive layers carry bias but canonical veto absolute"
    elif considered > 0:
        topology = "structural consideration present alongside restrained verdicts"
    elif unresolved >= 1:
        topology = "unresolved structural disagreement registered"
    elif wait >= blocked:
        topology = "shadow field mostly silent · cognition not yet pressing on canonical layer"
    else:
        topology = "shadow field in restraint posture"

    top_reasons = s.get("topReasons") or []
    top_blocked_by = s.get("topBlockedBy") or []

    return {
        "ok": True,
        "phrase": topology,
        "totalVerdicts": s.get("totalVerdicts"),
        "distribution": {
            "blocked": blocked,
            "wait": wait,
            "considered": considered,
            "unresolved": unresolved,
        },
        "topReasons": [{"reason": r, "count": c} for r, c in top_reasons[:5]],
        "topBlockedBy": [{"layer": l, "count": c} for l, c in top_blocked_by[:5]],
    }


# ─── Section 5 · Regime Continuity ─────────────────────────────────────
def _regime_continuity() -> dict:
    """Per-symbol fractal phase persistence — structural memory."""
    try:
        from services.fractal_runtime import runtime as _frac_runtime  # type: ignore
    except Exception:
        return {"ok": False, "reason": "fractal_runtime_unavailable", "perSymbol": {}}

    per_symbol: Dict[str, dict] = {}
    phase_counter: Counter = Counter()

    for sym in UNIVERSE:
        fr = _safe(_frac_runtime, sym) or {}
        phase = (fr.get("phase") or "unavailable").lower()
        evidence = fr.get("evidence") or fr.get("evidenceCount") or 0
        phase_counter[phase] += 1
        if phase == "compression":
            label = "compression sustained"
        elif phase == "expansion":
            label = "expansion phase"
        elif phase == "rangebound":
            label = "rangebound continuity"
        elif phase == "unavailable":
            label = "structural reading insufficient"
        else:
            label = f"phase · {phase}"
        per_symbol[sym] = {
            "phase": phase,
            "label": label,
            "evidence": evidence,
        }

    # Universe-wide regime phrase
    dom_phase, dom_count = (phase_counter.most_common(1) or [(None, 0)])[0]
    if dom_phase == "compression" and dom_count >= 2:
        regime = "compression regime persists across universe"
    elif dom_phase == "expansion" and dom_count >= 2:
        regime = "expansion regime active"
    elif dom_phase == "rangebound" and dom_count >= 2:
        regime = "rangebound continuity dominant"
    elif dom_phase == "unavailable" and dom_count >= 2:
        regime = "structural substrate insufficient for regime reading"
    else:
        regime = "mixed regime topology"

    return {
        "ok": True,
        "phrase": regime,
        "perSymbol": per_symbol,
    }


# ─── Public: full observatory state ────────────────────────────────────
def observatory_state() -> dict:
    """Compose all 5 sections.  Strictly manual recompute — caller is the
    explicit refresh action (button or pull-to-refresh)."""
    with _lock:
        db = _db()
        try:
            total_decisions = db.decision_history.count_documents({})
        except Exception:
            total_decisions = 0

        if total_decisions == 0:
            return {
                "ok": False,
                "reason": "insufficient_decision_context",
                "phrase": "Insufficient continuity for interpretive surface.",
                "asOf": _now_iso(),
            }

        return {
            "ok": True,
            "asOf": _now_iso(),
            "universe": list(UNIVERSE),
            "deploymentClimate": _deployment_climate(),
            "alignmentDrift": _alignment_drift(),
            "cognitiveMemory": _cognitive_memory(),
            "shadowStructures": _shadow_structures(),
            "regimeContinuity": _regime_continuity(),
        }



# ═══════════════════════════════════════════════════════════════════════
# Phase D Pass 2B — Canonical adapter (derived cognition: observatory)
# ═══════════════════════════════════════════════════════════════════════
# DISCIPLINE: observatory is an *interpretive* layer. The canonical adapter
# must NOT:
#   - recompute cognition,
#   - override the truth of upstream modules,
#   - aggregate confidence mathematically (no weighted_mean, no meta_score).
# It only describes the posture of the interpretive surface itself:
# "is the observatory currently producing a usable interpretive surface?"


def canonical(payload):
    """
    Adapt a raw `observatory_state()` result to a CognitionSnapshot.

    Pure: no DB, no network, no recomputation. Caller supplies the payload.

    State derivation (interpretive-only — no score fusion):
      ok=False                          → 'insufficient' (substrate empty)
                                          or 'degraded' (other reason)
      ok=True, all 5 sections have ok   → 'active'
      ok=True, some sections degraded   → 'wait'
      ok=True, all 5 sections degraded  → 'degraded'

    Direction:   ALWAYS None (observatory is interpretive, not directional).
    Confidence:  ALWAYS None (no mathematical aggregation in canonical layer).

    Reasons: which sections are alive, which are not — interpretive only.
    """
    from services.runtime_contract import (
        CognitionSnapshot, make_insufficient,
    )

    if not isinstance(payload, dict) or not payload:
        return make_insufficient(
            module="observatory",
            source="operator_observatory",
            reasons=("missing_observatory_payload",),
        )

    source = "operator_observatory"
    updated_at = payload.get("asOf")

    if not payload.get("ok"):
        reason = str(payload.get("reason") or "observatory_unavailable").lower()
        if "insufficient_decision_context" in reason:
            return make_insufficient(
                module="observatory",
                source=source,
                reasons=("insufficient_decision_context",),
            )
        return CognitionSnapshot.build(
            module="observatory",
            source=source,
            state="degraded",
            reasons=(reason.replace(" ", "_").replace(":", "_")[:64],),
            degraded=True,
            updatedAt=updated_at,
        )

    section_keys = (
        "deploymentClimate",
        "alignmentDrift",
        "cognitiveMemory",
        "shadowStructures",
        "regimeContinuity",
    )
    alive = []
    degraded = []
    for k in section_keys:
        sec = payload.get(k) or {}
        if not isinstance(sec, dict):
            continue
        if sec.get("ok"):
            alive.append(k)
        else:
            degraded.append(k)

    reasons = []
    for k in alive:
        # snake_case the camelCase section name
        snake = "".join(
            "_" + c.lower() if c.isupper() else c for c in k
        ).lstrip("_")
        reasons.append(f"section_alive_{snake}")
    for k in degraded:
        snake = "".join(
            "_" + c.lower() if c.isupper() else c for c in k
        ).lstrip("_")
        reasons.append(f"section_unavailable_{snake}")

    n_alive = len(alive)
    n_total = len(section_keys)
    if n_alive == n_total:
        state = "active"
    elif n_alive == 0:
        state = "degraded"
    else:
        state = "wait"

    if not reasons:
        reasons = ["observatory_empty"]

    return CognitionSnapshot.build(
        module="observatory",
        source=source,
        state=state,
        direction=None,
        confidence=None,
        reasons=reasons,
        degraded=state == "degraded",
        updatedAt=updated_at,
    )
