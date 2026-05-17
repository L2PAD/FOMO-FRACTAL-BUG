"""
Engine Playbook Service — Playbook Layer
==========================================
Generates operational trading playbook from engine data.
Rule-based, no LLM. Short and actionable.

Sections: bias, confirmation, invalidation, targets, risk_note
"""


def _build_bias(engine_data: dict) -> str:
    """Determine directional bias from decision + regime."""
    decision = engine_data.get("decision", "NEUTRAL")
    regime = engine_data.get("regime_engine", {}).get("primary", {})
    regime_type = regime.get("type", "neutral_chop")

    if decision == "BUY":
        return "bullish"
    elif decision == "SELL":
        return "bearish"

    # Neutral decision — derive from regime
    if regime_type in ("bull_trend", "accumulation"):
        return "cautiously bullish"
    elif regime_type in ("bear_trend", "distribution"):
        return "cautiously bearish"
    return "neutral"


def _build_confirmation(engine_data: dict) -> list:
    """Build confirmation conditions from setup supports + flow."""
    rules = []
    setup = engine_data.get("setup_engine", {}).get("primary", {})
    flow = engine_data.get("flow_engine", {})
    prob = engine_data.get("probability_layer", {})

    supports = setup.get("supports", [])
    if supports:
        rules.append(supports[0])

    flow_state = flow.get("state", "neutral")
    decision = engine_data.get("decision", "NEUTRAL")

    if decision == "BUY" and flow_state == "bullish_acceleration":
        rules.append("Maintain bullish flow acceleration")
    elif decision == "BUY":
        rules.append("Flow must confirm bullish direction")

    if decision == "SELL" and flow_state == "bearish_acceleration":
        rules.append("Bearish flow acceleration continues")
    elif decision == "SELL":
        rules.append("Flow must confirm bearish direction")

    cont = prob.get("continuation", 0)
    if cont > 0.6:
        rules.append(f"Continuation probability holds above 60% (currently {round(cont * 100)}%)")

    return rules[:3]


def _build_invalidation(engine_data: dict) -> list:
    """Build invalidation conditions from setup invalidation + risk drivers."""
    rules = []
    setup = engine_data.get("setup_engine", {}).get("primary", {})
    risk = engine_data.get("risk_engine", {})

    inv = setup.get("invalidation", [])
    rules.extend(inv[:2])

    drivers = risk.get("drivers", [])
    for d in drivers[:2]:
        if d not in rules:
            rules.append(d)

    return rules[:4]


def _build_targets(engine_data: dict) -> list:
    """Build target list from liquidity map."""
    targets = []
    liq = engine_data.get("liquidity_map", {})
    target_zones = liq.get("target_zones", [])
    magnet_zones = liq.get("magnet_zones", [])

    for t in target_zones[:2]:
        targets.append({
            "type": "primary" if len(targets) == 0 else "intermediate",
            "reason": t.get("reason", "liquidity target"),
            "direction": t.get("direction", "neutral"),
            "confidence": t.get("confidence", 0),
        })

    for m in magnet_zones[:1]:
        targets.append({
            "type": "magnet",
            "reason": m.get("reason", "magnet zone"),
            "direction": m.get("direction", "neutral"),
            "confidence": m.get("confidence", 0),
        })

    return targets


def _build_risk_note(engine_data: dict) -> str:
    """Build risk note summary."""
    risk = engine_data.get("risk_engine", {})
    level = risk.get("risk_level", "MODERATE")
    score = risk.get("risk_score", 50)
    drivers = risk.get("drivers", [])

    if level in ("HIGH", "ELEVATED"):
        note = f"Risk is {level.lower()} ({score}/100)"
        if drivers:
            note += f" — {drivers[0].lower()}"
        return note
    elif level == "MODERATE":
        if drivers:
            return f"Moderate risk — {drivers[0].lower()}"
        return "Moderate risk — monitor for changes"
    else:
        return "Low risk environment — favorable for position sizing"


def build_playbook(engine_data: dict) -> dict:
    """
    Main entry point — build complete playbook.
    Returns structured playbook with all 5 sections.
    """
    bias = _build_bias(engine_data)
    confirmation = _build_confirmation(engine_data)
    invalidation = _build_invalidation(engine_data)
    targets = _build_targets(engine_data)
    risk_note = _build_risk_note(engine_data)

    return {
        "bias": bias,
        "confirmation": confirmation,
        "invalidation": invalidation,
        "targets": targets,
        "risk_note": risk_note,
    }
