"""
Labs explain generator — human-readable text for each lab result.
"""

from typing import Dict, List


def _top_drivers(labs: List[dict], k=3):
    ranked = sorted(labs, key=lambda x: x.get("abnormality", 0) * x.get("confidence", 0), reverse=True)
    return ranked[:k]


def _risk_flags(labs: List[dict]) -> List[str]:
    flags = []
    for x in labs:
        if x["lab"] in ("liquidity", "manipulation", "liquidation") and x["riskContribution"] >= 0.65:
            flags.append(f"HIGH {x['lab'].replace('_', ' ').upper()} RISK")
        elif x["lab"] in ("liquidity", "manipulation") and x["riskContribution"] >= 0.50:
            flags.append(f"ELEVATED {x['lab'].replace('_', ' ').upper()}")
    return flags[:4]


def _invalidation(state_key: str) -> str:
    if state_key in ("BREAKOUT_ACTIVE", "BREAKOUT_BUILDING"):
        return "Invalidated if flow drops or liquidity/manipulation risk spikes."
    if state_key in ("DISTRIBUTION", "LIQUIDITY_TRAP"):
        return "Invalidated if risk normalizes and flow stabilizes."
    return "No clear invalidation trigger."


def generate_explain(state: dict, labs: List[dict]) -> dict:
    """
    Generate short human-readable explanation with state probability + risk breakdown.
    """
    drivers = _top_drivers(labs, k=3)
    risks = _risk_flags(labs)
    confidence = state.get("confidence", 0)

    bullets = []
    for d in drivers:
        lab_name = d.get("displayName", d["lab"].replace("_", " ").title())
        st = d.get("state", "")
        bullets.append(f"{lab_name}: {st}")
    if risks:
        bullets.append("Risks: " + ", ".join(risks))

    # Risk breakdown from labs
    labs_map = {x["lab"]: x for x in labs}
    risk_breakdown = {
        "liquidity": round(labs_map.get("liquidity", {}).get("riskContribution", 0) * 100),
        "stress": round(labs_map.get("market_stress", {}).get("riskContribution", 0) * 100),
        "manipulation": round(labs_map.get("manipulation", {}).get("riskContribution", 0) * 100),
        "structure": round(labs_map.get("regime", {}).get("riskContribution", 0) * 100),
        "conflict": round(labs_map.get("signal_conflict", {}).get("riskContribution", 0) * 100),
    }

    return {
        "oneLiner": f"{state['stateLabel']} — confidence {int(confidence * 100)}%",
        "stateConfidence": round(confidence * 100),
        "scores": state.get("scores", {}),
        "bullets": bullets[:5],
        "risks": risks,
        "riskBreakdown": risk_breakdown,
        "invalidation": _invalidation(state["stateKey"]),
    }
