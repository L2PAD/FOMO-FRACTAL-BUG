"""
State Transition Engine — detects significant changes between old and new state.

Produces transition events that trigger alerts.
"""

# Priority transitions (from → to)
HIGH_PRIORITY_TRANSITIONS = {
    # Action upgrades
    ("WATCH", "YES_NOW"), ("WATCH", "NO_NOW"),
    ("WAIT", "YES_NOW"), ("WAIT", "NO_NOW"),
    ("YES_SMALL", "YES_NOW"), ("NO_SMALL", "NO_NOW"),
    # Repricing starts
    ("fresh_mispricing", "early_repricing"),
    ("stalled", "early_repricing"),
    ("stalled", "fresh_mispricing"),
    # Entry window
    ("wait_confirmation", "enter_now"),
    ("wait_retrace", "enter_now"),
}

MEDIUM_PRIORITY_TRANSITIONS = {
    ("YES_NOW", "YES_SMALL"), ("NO_NOW", "NO_SMALL"),
    ("YES_NOW", "WAIT"), ("NO_NOW", "WAIT"),
    ("early_repricing", "active_repricing"),
    ("enter_now", "enter_limit"),
}

DEGRADATION_TRANSITIONS = {
    ("YES_NOW", "AVOID"), ("NO_NOW", "AVOID"),
    ("YES_SMALL", "AVOID"), ("NO_SMALL", "AVOID"),
    ("enter_now", "too_late"),
    ("enter_limit", "too_late"),
    ("early_repricing", "overheated"),
    ("active_repricing", "overheated"),
    ("triggered", "exhausted"),
    ("triggered", "invalidated"),
}


def detect_transitions(old_state: dict | None, new_case: dict) -> list[dict]:
    """
    Compare old persisted state vs new case. Return list of transitions.

    Each transition: {field, from, to, priority, type}
    """
    if not old_state:
        return [{"field": "lifecycle", "from": None, "to": "new",
                 "priority": "low", "type": "new_market"}]

    transitions = []

    # Recommendation action change
    old_action = old_state.get("last_recommendation")
    new_action = new_case.get("recommendation", {}).get("action")
    if old_action and new_action and old_action != new_action:
        pair = (old_action, new_action)
        if pair in HIGH_PRIORITY_TRANSITIONS:
            prio = "high"
        elif pair in MEDIUM_PRIORITY_TRANSITIONS:
            prio = "medium"
        elif pair in DEGRADATION_TRANSITIONS:
            prio = "high"
        else:
            prio = "low"
        transitions.append({
            "field": "recommendation",
            "from": old_action, "to": new_action,
            "priority": prio,
            "type": "upgrade" if prio == "high" else "change",
        })

    # Repricing state change
    old_repr = old_state.get("last_repricing_state")
    new_repr = new_case.get("repricing", {}).get("repricing_state")
    if old_repr and new_repr and old_repr != new_repr:
        pair = (old_repr, new_repr)
        if pair in HIGH_PRIORITY_TRANSITIONS:
            prio = "high"
        elif pair in MEDIUM_PRIORITY_TRANSITIONS:
            prio = "medium"
        elif pair in DEGRADATION_TRANSITIONS:
            prio = "high"
        else:
            prio = "low"
        transitions.append({
            "field": "repricing_state",
            "from": old_repr, "to": new_repr,
            "priority": prio,
            "type": "repricing_change",
        })

    # Entry action change
    old_entry = old_state.get("last_entry_action")
    new_entry = new_case.get("entry_timing", {}).get("entry_action")
    if old_entry and new_entry and old_entry != new_entry:
        pair = (old_entry, new_entry)
        if pair in HIGH_PRIORITY_TRANSITIONS:
            prio = "high"
        elif pair in DEGRADATION_TRANSITIONS:
            prio = "high"
        else:
            prio = "medium"
        transitions.append({
            "field": "entry_action",
            "from": old_entry, "to": new_entry,
            "priority": prio,
            "type": "entry_change",
        })

    # Size upgrade/downgrade
    old_size = old_state.get("last_size")
    new_size = new_case.get("sizing", {}).get("size")
    SIZE_ORDER = {"NONE": 0, "TINY": 1, "SMALL": 2, "MEDIUM": 3, "FULL": 4}
    if old_size and new_size and old_size != new_size:
        old_rank = SIZE_ORDER.get(old_size, 0)
        new_rank = SIZE_ORDER.get(new_size, 0)
        if new_rank > old_rank:
            transitions.append({
                "field": "size", "from": old_size, "to": new_size,
                "priority": "medium", "type": "size_upgrade",
            })
        elif new_rank < old_rank:
            transitions.append({
                "field": "size", "from": old_size, "to": new_size,
                "priority": "medium", "type": "size_downgrade",
            })

    # Stage change
    old_stage = old_state.get("last_stage")
    new_stage = new_case.get("market_stage")
    if old_stage and new_stage and old_stage != new_stage:
        pair = (old_stage, new_stage)
        if pair in DEGRADATION_TRANSITIONS:
            prio = "high"
        elif new_stage == "triggered":
            prio = "high"
        else:
            prio = "low"
        transitions.append({
            "field": "stage", "from": old_stage, "to": new_stage,
            "priority": prio, "type": "stage_change",
        })

    return transitions
