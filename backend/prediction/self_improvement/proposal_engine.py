"""
Proposal Engine — generates tuning proposals from patterns + drift.

Rules:
  - 24h cooldown per scope (no repeat proposals for same param within 24h)
  - Max 2 weight changes per cycle
  - Governance: reject proposals for scopes with status=UNSTABLE or severity=HIGH drift
  - Each proposal gets status SUGGESTED (needs manual approval)
"""
import logging
import uuid
from datetime import datetime, timezone, timedelta

from prediction.self_improvement.parameter_registry import (
    get_param_spec,
    get_max_delta,
    validate_value,
    get_weight_group_keys,
    normalize_weights,
    MAX_WEIGHT_CHANGES_PER_CYCLE,
)

logger = logging.getLogger("self_improvement.proposal_engine")

COOLDOWN_HOURS = 24
MAX_PROPOSALS_PER_CYCLE = 5


def generate_proposals(db) -> list[dict]:
    """Generate tuning proposals based on detected patterns and drift."""
    patterns = list(db.pattern_findings.find({"active": True}, {"_id": 0}))
    drift_states = list(db.drift_states.find({}, {"_id": 0}))

    if not patterns and not drift_states:
        return []

    now = datetime.now(timezone.utc)
    cooldown_cutoff = (now - timedelta(hours=COOLDOWN_HOURS)).isoformat()

    # Check recent proposals for cooldown
    recent_proposals = list(db.tuning_proposals.find(
        {"created_at": {"$gte": cooldown_cutoff}},
        {"_id": 0, "param_key": 1, "created_at": 1}
    ))
    cooled_params = {p["param_key"] for p in recent_proposals}

    # Get active params
    active_params = _get_active_params(db)

    proposals = []
    weight_changes = 0

    # Generate proposals from patterns
    for pattern in patterns:
        if len(proposals) >= MAX_PROPOSALS_PER_CYCLE:
            break

        new_proposals = _proposals_from_pattern(pattern, active_params, cooled_params, drift_states)
        for p in new_proposals:
            spec = get_param_spec(p["param_key"])
            if spec and spec["type"] == "weight":
                if weight_changes >= MAX_WEIGHT_CHANGES_PER_CYCLE:
                    continue
                weight_changes += 1
            proposals.append(p)
            if len(proposals) >= MAX_PROPOSALS_PER_CYCLE:
                break

    # Run governance checks
    governed = []
    for p in proposals:
        gov = _governance_check(p, drift_states)
        p["governance_check"] = gov
        if gov["approved"]:
            p["status"] = "SUGGESTED"
            governed.append(p)
        else:
            p["status"] = "REJECTED_BY_GOVERNANCE"
            governed.append(p)

    # Persist proposals
    now_iso = now.isoformat()
    for p in governed:
        p["proposal_id"] = f"prop_{uuid.uuid4().hex[:12]}"
        p["created_at"] = now_iso
        p["cooldown_until"] = (now + timedelta(hours=COOLDOWN_HOURS)).isoformat()

    if governed:
        db.tuning_proposals.insert_many([dict(p) for p in governed])

    return governed


def _get_active_params(db) -> dict:
    """Get current active parameter values."""
    params = {}
    for doc in db.active_model_params.find({}, {"_id": 0}):
        params[doc["param_key"]] = doc["value"]
    return params


def _proposals_from_pattern(pattern: dict, active_params: dict,
                            cooled_params: set, drift_states: list) -> list[dict]:
    """Map a pattern to concrete param change proposals."""
    proposals = []
    issue = pattern.get("issue_type", "")
    effect = pattern.get("effect_size", 0)

    if issue == "OVERCONFIDENCE":
        # Suggest raising confidence thresholds
        key = "confidence.buy_now_threshold"
        if key not in cooled_params:
            current = active_params.get(key, 0.65)
            delta = min(0.02, effect * 0.3)
            proposed = round(current + delta, 4)
            ok, _ = validate_value(key, proposed)
            if ok:
                proposals.append(_make_proposal(key, current, proposed, delta, pattern))

    elif issue == "UNDERCONFIDENCE":
        key = "confidence.buy_threshold"
        if key not in cooled_params:
            current = active_params.get(key, 0.55)
            delta = min(0.02, effect * 0.3)
            proposed = round(current - delta, 4)
            ok, _ = validate_value(key, proposed)
            if ok:
                proposals.append(_make_proposal(key, current, proposed, -delta, pattern))

    elif issue == "LATE_SIGNAL":
        key = "fair_prob.time_decay_weight"
        if key not in cooled_params:
            current = active_params.get(key, 0.15)
            delta = min(0.02, effect * 0.2)
            proposed = round(current + delta, 4)
            ok, _ = validate_value(key, proposed)
            if ok:
                proposals.append(_make_proposal(key, current, proposed, delta, pattern))

    elif issue == "SHORT_EXPIRY_NOISE":
        key = "sizing.short_expiry_cap"
        if key not in cooled_params:
            current = active_params.get(key, 0.60)
            delta = min(0.05, effect * 0.5)
            proposed = round(current - delta, 4)
            ok, _ = validate_value(key, proposed)
            if ok:
                proposals.append(_make_proposal(key, current, proposed, -delta, pattern))

    elif issue in ("WEAK_STRUCTURE", "STRONG_STRUCTURE"):
        key = "fair_prob.structure_weight"
        if key not in cooled_params:
            current = active_params.get(key, 0.15)
            direction = 1 if issue == "STRONG_STRUCTURE" else -1
            delta = min(0.02, effect * 0.3) * direction
            proposed = round(current + delta, 4)
            ok, _ = validate_value(key, proposed)
            if ok:
                proposals.append(_make_proposal(key, current, proposed, delta, pattern))

    return proposals


def _make_proposal(param_key: str, current: float, proposed: float,
                   delta: float, pattern: dict) -> dict:
    """Create a proposal dict."""
    return {
        "param_key": param_key,
        "current_value": round(current, 4),
        "proposed_value": round(proposed, 4),
        "delta": round(delta, 4),
        "reason": f"Pattern {pattern['issue_type']}: {pattern.get('summary', '')}",
        "based_on_patterns": [pattern.get("pattern_key", "")],
        "based_on_drift": [],
    }


def _governance_check(proposal: dict, drift_states: list) -> dict:
    """Check if proposal passes governance gates."""
    param_key = proposal["param_key"]
    spec = get_param_spec(param_key)
    if not spec:
        return {"approved": False, "reason": f"Unknown param: {param_key}"}

    max_delta = get_max_delta(spec["type"])
    if abs(proposal["delta"]) > max_delta:
        return {"approved": False, "reason": f"Delta {proposal['delta']} exceeds max {max_delta}"}

    # Check if the scope is unstable in drift
    unstable_scopes = {
        d["scope_value"]
        for d in drift_states
        if d.get("status") == "DEGRADING" and d.get("severity") == "HIGH"
    }

    group = spec.get("group", "")
    if group in unstable_scopes or "all" in unstable_scopes:
        return {"approved": False, "reason": f"Scope '{group}' is currently DEGRADING with HIGH severity"}

    return {"approved": True, "reason": "Passed all governance checks"}


def get_proposals(db, status: str = None, limit: int = 50) -> list[dict]:
    """Get proposals from DB."""
    query = {}
    if status:
        query["status"] = status
    return list(db.tuning_proposals.find(
        query, {"_id": 0}
    ).sort("created_at", -1).limit(limit))
