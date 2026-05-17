"""
mbrain_integrity.normalize
==========================

Compatibility adapter: side-car Verdict v2 → v1 mbrain_integrity decision shape.

* Read-only — no side-effects, no persistence, no synthetic data.
* Pure function — same input always produces the same output.
* No mongo writes anywhere.
* No imports from side-car internals (only HTTP-fetched JSON).

Verdict v2 (side-car authoritative shape, see
`/app/legacy/backend-src/modules/verdict/contracts/verdict.types.ts`
— this is a docstring reference to the QUARANTINED legacy tree, kept for
historical context; the contract itself is re-implemented natively in
this normalize() function below):

    {
      verdictId, symbol, ts, horizon,
      action: "BUY" | "SELL" | "HOLD",
      expectedReturn, confidence, risk, positionSizePct,
      raw: { expectedReturn, confidence, horizon, modelId },
      adjustments: [
        { stage: "RULES" | "META_BRAIN" | "CALIBRATION",
          key, deltaConfidence?, deltaReturn?, notes? }
      ],
      appliedRules: [
        { id, severity: "INFO" | "WARN" | "BLOCK", message, overrideAction? }
      ],
      modelId, regime, status?
    }

v1 mbrain_integrity decision shape (consumed by `compute_distribution`):

    {
      symbol, timeframe, ts,
      decision_raw:      { direction, confidence, reasons[] },
      decision_enforced: { direction },                    # post-rules + meta-brain
      final_action: "LONG" | "SHORT" | "HOLD" | "BUY" | "SELL",
      blocked: bool, block_reason: [str],
      reason_chain: [str],
      regime, modelId,
      stages: { raw, after_rules, after_meta_brain, after_calibration, final }
    }

Stage-by-stage survival reconstruction
--------------------------------------
The Verdict pipeline applies adjustments in a fixed order:
    raw  →  RULES  →  META_BRAIN  →  CALIBRATION  →  final

Each `adjustments[i].stage` tells us at which stage the engine modified
confidence/return. We accumulate deltas to reconstruct the snapshot at
each stage. Direction at a stage is computed as:
    sign(expectedReturn_at_stage)  if abs() > eps else "HOLD"

`appliedRules` with severity BLOCK or `overrideAction` are layered over
the RULES stage — if a BLOCK fires, direction collapses to HOLD at that
stage. `adjustments` with key `ACTION_DOWNGRADED_TO_AVOID` on the
META_BRAIN stage signals a collapse to HOLD at that exact stage.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


_EPS = 1e-6  # below this expectedReturn is considered HOLD


def _action_to_dir(action: Optional[str]) -> str:
    """side-car Action {BUY, SELL, HOLD, AVOID} → integrity direction."""
    if not action:
        return "HOLD"
    a = str(action).upper()
    if a == "BUY":
        return "LONG"
    if a == "SELL":
        return "SHORT"
    # HOLD, AVOID, WAIT, NONE → HOLD
    return "HOLD"


def _dir_from_return(expected_return: Optional[float]) -> str:
    """expectedReturn sign → LONG / SHORT / HOLD."""
    if expected_return is None:
        return "HOLD"
    try:
        er = float(expected_return)
    except (TypeError, ValueError):
        return "HOLD"
    if er > _EPS:
        return "LONG"
    if er < -_EPS:
        return "SHORT"
    return "HOLD"


def _is_block_severity(rule: Dict[str, Any]) -> bool:
    return str(rule.get("severity", "")).upper() == "BLOCK"


def _stage_collapse_to_hold(adj: Dict[str, Any]) -> bool:
    """
    Detect whether an adjustment forces direction collapse to HOLD/AVOID
    at its stage. We look at the side-car-emitted `key` and `notes`.
    Examples observed:
      - "ACTION_DOWNGRADED_TO_AVOID"
      - "ACTION_DOWNGRADED_TO_HOLD"
      - "BLOCKED_BY_GUARDRAIL"
    """
    key = str(adj.get("key", "")).upper()
    if not key:
        return False
    return (
        "DOWNGRADE" in key
        or "AVOID" in key
        or "HOLD" in key
        or "BLOCK" in key
        or "SUPPRESS" in key
    )


def reconstruct_survival(verdict: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Reconstruct {raw, after_rules, after_meta_brain, after_calibration, final}
    snapshots from a Verdict v2 envelope. No synthetic generation — the
    deltas are exactly those reported by the side-car engine.
    """
    raw = verdict.get("raw") or {}
    raw_er = raw.get("expectedReturn")
    raw_conf = raw.get("confidence")

    cur_er = float(raw_er) if raw_er is not None else 0.0
    cur_conf = float(raw_conf) if raw_conf is not None else 0.0
    cur_dir = _dir_from_return(cur_er)

    stages: Dict[str, Dict[str, Any]] = {
        "raw": {
            "direction": cur_dir,
            "expectedReturn": cur_er,
            "confidence": cur_conf,
            "collapsed_to_hold": False,
        }
    }

    # Apply rules layer (rules adjustments + appliedRules with severity BLOCK)
    rule_adjs = [a for a in (verdict.get("adjustments") or [])
                 if str(a.get("stage", "")).upper() == "RULES"]
    rules_collapsed = any(_stage_collapse_to_hold(a) for a in rule_adjs)
    block_fired = any(_is_block_severity(r)
                      for r in (verdict.get("appliedRules") or []))
    for a in rule_adjs:
        cur_er += float(a.get("deltaReturn") or 0.0)
        cur_conf += float(a.get("deltaConfidence") or 0.0)
    rules_dir = "HOLD" if (rules_collapsed or block_fired) else _dir_from_return(cur_er)
    stages["after_rules"] = {
        "direction": rules_dir,
        "expectedReturn": cur_er,
        "confidence": cur_conf,
        "collapsed_to_hold": rules_collapsed or block_fired,
    }
    if rules_collapsed or block_fired:
        cur_dir = "HOLD"
    else:
        cur_dir = rules_dir

    # Meta-brain layer
    meta_adjs = [a for a in (verdict.get("adjustments") or [])
                 if str(a.get("stage", "")).upper() == "META_BRAIN"]
    meta_collapsed = any(_stage_collapse_to_hold(a) for a in meta_adjs)
    for a in meta_adjs:
        cur_er += float(a.get("deltaReturn") or 0.0)
        cur_conf += float(a.get("deltaConfidence") or 0.0)
    if cur_dir == "HOLD":
        meta_dir = "HOLD"
    else:
        meta_dir = "HOLD" if meta_collapsed else _dir_from_return(cur_er)
    stages["after_meta_brain"] = {
        "direction": meta_dir,
        "expectedReturn": cur_er,
        "confidence": cur_conf,
        "collapsed_to_hold": meta_collapsed,
    }
    cur_dir = meta_dir

    # Calibration layer
    cal_adjs = [a for a in (verdict.get("adjustments") or [])
                if str(a.get("stage", "")).upper() == "CALIBRATION"]
    cal_collapsed = any(_stage_collapse_to_hold(a) for a in cal_adjs)
    for a in cal_adjs:
        cur_er += float(a.get("deltaReturn") or 0.0)
        cur_conf += float(a.get("deltaConfidence") or 0.0)
    if cur_dir == "HOLD":
        cal_dir = "HOLD"
    else:
        cal_dir = "HOLD" if cal_collapsed else _dir_from_return(cur_er)
    stages["after_calibration"] = {
        "direction": cal_dir,
        "expectedReturn": cur_er,
        "confidence": cur_conf,
        "collapsed_to_hold": cal_collapsed,
    }

    # Final = engine-reported final action
    final_dir = _action_to_dir(verdict.get("action"))
    stages["final"] = {
        "direction": final_dir,
        "expectedReturn": float(verdict.get("expectedReturn") or 0.0),
        "confidence": (float(verdict.get("confidence"))
                       if verdict.get("confidence") is not None else None),
        "collapsed_to_hold": (final_dir == "HOLD" and cal_dir != "HOLD"),
    }
    return stages


def normalize_verdict_to_decision(verdict: Dict[str, Any]) -> Dict[str, Any]:
    """
    side-car Verdict v2 → v1 mbrain_integrity decision envelope.
    Pure function. No I/O.
    """
    if not isinstance(verdict, dict):
        return {}

    final_action = verdict.get("action")
    final_dir = _action_to_dir(final_action)

    raw = verdict.get("raw") or {}
    raw_dir = _dir_from_return(raw.get("expectedReturn"))

    blocks = [r for r in (verdict.get("appliedRules") or [])
              if _is_block_severity(r)]
    reason_chain = [str(a.get("key") or a.get("notes") or "")
                    for a in (verdict.get("adjustments") or [])
                    if a.get("key") or a.get("notes")]

    stages = reconstruct_survival(verdict)

    return {
        "symbol": verdict.get("symbol"),
        "timeframe": verdict.get("horizon"),
        "ts": verdict.get("ts"),
        "decision_raw": {
            "direction": raw_dir,
            "confidence": (float(raw.get("confidence"))
                           if raw.get("confidence") is not None else None),
            "expectedReturn": (float(raw.get("expectedReturn"))
                               if raw.get("expectedReturn") is not None else None),
            "modelId": raw.get("modelId"),
            "reasons": [],
        },
        "decision_enforced": {
            "direction": stages["after_meta_brain"]["direction"],
        },
        "final_action": final_dir,
        "blocked": len(blocks) > 0,
        "block_reason": [str(b.get("id") or b.get("message") or "") for b in blocks],
        "reason_chain": reason_chain,
        "regime": verdict.get("regime"),
        "modelId": verdict.get("modelId"),
        "confidence_final": (float(verdict.get("confidence"))
                             if verdict.get("confidence") is not None else None),
        "risk": verdict.get("risk"),
        "stages": stages,
        "_source": "verdict_v2",
        "_verdictId": verdict.get("verdictId"),
    }
