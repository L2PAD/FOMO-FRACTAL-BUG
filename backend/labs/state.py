"""
Labs state classifier — higher-level regime classification.
Combines individual lab results into an overall market state.
"""

from typing import Dict, List
from .scoring import clamp


STATE_DEFS = {
    "BREAKOUT_ACTIVE": {
        "desc": "Strong flow + structure shift. Momentum confirmed.",
        "action": "Actionable if risk allows",
    },
    "BREAKOUT_BUILDING": {
        "desc": "Compression high + flow building. Watch for confirmation.",
        "action": "Prepare entry on confirmation",
    },
    "DISTRIBUTION": {
        "desc": "Smart money risk high + flow weakening.",
        "action": "Avoid longs / consider short on confirmation",
    },
    "LIQUIDITY_TRAP": {
        "desc": "Thin liquidity + stop-hunt risk elevated.",
        "action": "Avoid or reduce size significantly",
    },
    "RANGE_CHOP": {
        "desc": "No clear edge. Compression low, regime neutral.",
        "action": "Mean-revert only or sit out",
    },
    "DATA_WEAK": {
        "desc": "Insufficient or stale data.",
        "action": "No action (data unreliable)",
    },
}


def _get(labs_map: Dict[str, dict], key: str, field: str, default=0.0) -> float:
    return float(labs_map.get(key, {}).get(field, default))


def classify_overall_state(labs: List[dict]) -> dict:
    """
    Score-based state classifier. No if/else chains.
    Returns {stateKey, stateLabel, confidence, tags[], scores{}}.
    """
    labs_map = {x["lab"]: x for x in labs}

    # Extract key signals
    compression = _get(labs_map, "volatility", "abnormality")
    momentum = _get(labs_map, "momentum", "abnormality")
    flow_abn = _get(labs_map, "flow", "abnormality")
    participation = _get(labs_map, "participation", "abnormality")
    liq_risk = _get(labs_map, "liquidity", "riskContribution")
    manip_risk = _get(labs_map, "manipulation", "riskContribution")
    stress_risk = _get(labs_map, "market_stress", "riskContribution")
    conflict = _get(labs_map, "signal_conflict", "abnormality")
    quality_conf = _get(labs_map, "data_quality", "confidence")

    if quality_conf < 0.35:
        return {"stateKey": "DATA_WEAK", "stateLabel": "Data weak", "confidence": round(quality_conf, 3), "tags": ["LOW_CONFIDENCE"], "scores": {}}

    # Score each state
    score_range = clamp(
        compression * 0.3 +
        (1 - momentum) * 0.3 +
        (1 - flow_abn) * 0.2 +
        (1 - participation) * 0.2
    )

    score_breakout = clamp(
        momentum * 0.35 +
        flow_abn * 0.25 +
        participation * 0.2 +
        compression * 0.2
    )

    score_distribution = clamp(
        manip_risk * 0.35 +
        stress_risk * 0.25 +
        conflict * 0.2 +
        (1 - flow_abn) * 0.2
    )

    score_trap = clamp(
        liq_risk * 0.4 +
        manip_risk * 0.3 +
        stress_risk * 0.3
    )

    scores = {
        "RANGE_CHOP": round(score_range, 3),
        "BREAKOUT_ACTIVE": round(score_breakout, 3),
        "DISTRIBUTION": round(score_distribution, 3),
        "LIQUIDITY_TRAP": round(score_trap, 3),
    }

    state_key = max(scores, key=scores.get)
    state_conf = scores[state_key]

    labels = {
        "RANGE_CHOP": "Range / chop",
        "BREAKOUT_ACTIVE": "Breakout active",
        "DISTRIBUTION": "Distribution risk",
        "LIQUIDITY_TRAP": "Liquidity trap risk",
    }

    tags_map = {
        "RANGE_CHOP": ["NO_EDGE"],
        "BREAKOUT_ACTIVE": ["FLOW_STRONG", "MOMENTUM"],
        "DISTRIBUTION": ["SMART_MONEY_RISK"],
        "LIQUIDITY_TRAP": ["THIN_LIQUIDITY", "STOP_HUNT_RISK"],
    }

    return {
        "stateKey": state_key,
        "stateLabel": labels.get(state_key, state_key),
        "confidence": round(state_conf, 3),
        "tags": tags_map.get(state_key, []),
        "scores": scores,
    }
