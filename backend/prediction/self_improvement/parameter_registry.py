"""
Parameter Registry — defines what can be tuned and within what bounds.

All tunable parameters have min/max/step bounds.
Weight parameters must sum to 1.0 (normalized).
Max 2 weight changes per tuning cycle.
"""
import logging

logger = logging.getLogger("self_improvement.param_registry")

# Tunable parameters: key → {min, max, step, type, group}
TUNABLE_PARAMS = {
    # Fair Prob v2 weights (must sum to 1.0)
    "fair_prob.time_decay_weight": {"min": 0.0, "max": 0.30, "step": 0.01, "type": "weight", "group": "fair_prob"},
    "fair_prob.liquidity_weight": {"min": 0.0, "max": 0.25, "step": 0.01, "type": "weight", "group": "fair_prob"},
    "fair_prob.structure_weight": {"min": 0.0, "max": 0.30, "step": 0.01, "type": "weight", "group": "fair_prob"},
    "fair_prob.volatility_weight": {"min": 0.0, "max": 0.20, "step": 0.01, "type": "weight", "group": "fair_prob"},

    # Confidence thresholds
    "confidence.buy_now_threshold": {"min": 0.55, "max": 0.85, "step": 0.01, "type": "threshold", "group": "confidence"},
    "confidence.buy_threshold": {"min": 0.45, "max": 0.75, "step": 0.01, "type": "threshold", "group": "confidence"},

    # Sizing caps
    "sizing.low_liquidity_cap": {"min": 0.20, "max": 0.80, "step": 0.05, "type": "cap", "group": "sizing"},
    "sizing.short_expiry_cap": {"min": 0.20, "max": 1.00, "step": 0.05, "type": "cap", "group": "sizing"},
    "sizing.high_volatility_cap": {"min": 0.30, "max": 0.80, "step": 0.05, "type": "cap", "group": "sizing"},
}

# Max deltas per tuning cycle
MAX_DELTA_WEIGHT = 0.02
MAX_DELTA_THRESHOLD = 0.05
MAX_DELTA_CAP = 0.10
MAX_WEIGHT_CHANGES_PER_CYCLE = 2


def get_param_spec(key: str) -> dict | None:
    return TUNABLE_PARAMS.get(key)


def get_all_params() -> dict:
    return dict(TUNABLE_PARAMS)


def get_max_delta(param_type: str) -> float:
    if param_type == "weight":
        return MAX_DELTA_WEIGHT
    if param_type == "threshold":
        return MAX_DELTA_THRESHOLD
    return MAX_DELTA_CAP


def validate_delta(key: str, delta: float) -> tuple[bool, str]:
    """Validate that a proposed delta is within bounds."""
    spec = TUNABLE_PARAMS.get(key)
    if not spec:
        return False, f"Unknown param: {key}"

    max_d = get_max_delta(spec["type"])
    if abs(delta) > max_d:
        return False, f"Delta {delta} exceeds max {max_d} for {spec['type']}"

    return True, "ok"


def validate_value(key: str, value: float) -> tuple[bool, str]:
    """Validate that a proposed value is within bounds."""
    spec = TUNABLE_PARAMS.get(key)
    if not spec:
        return False, f"Unknown param: {key}"

    if value < spec["min"] or value > spec["max"]:
        return False, f"Value {value} out of bounds [{spec['min']}, {spec['max']}]"

    return True, "ok"


def get_weight_group_keys(group: str) -> list[str]:
    """Get all parameter keys in a weight group."""
    return [k for k, v in TUNABLE_PARAMS.items() if v.get("group") == group and v.get("type") == "weight"]


def normalize_weights(params: dict, group: str) -> dict:
    """Normalize weights in a group to sum to 1.0."""
    keys = get_weight_group_keys(group)
    values = [params.get(k, 0) for k in keys]
    total = sum(values)

    if total == 0 or abs(total - 1.0) < 0.001:
        return params

    result = dict(params)
    for k, v in zip(keys, values):
        result[k] = round(v / total, 4)

    return result
