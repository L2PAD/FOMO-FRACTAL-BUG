"""
Engine Risk Service — Market Risk Engine
==========================================
Calculates market risk score from engine data.
Reads from engine snapshots. Never runs heavy calculations.

Risk formula:
  risk_score = exchange_risk * 0.30
             + actor_conflict * 0.20
             + liquidity_void * 0.20
             + setup_failure_prob * 0.15
             + flow_instability * 0.15

4 risk levels: LOW (0-25), MODERATE (26-50), ELEVATED (51-75), HIGH (76-100)
"""


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _exchange_risk(engine_data: dict) -> tuple:
    """CEX deposit/flow risk. Returns (risk_value 0-1, driver_text)."""
    cex = engine_data.get("context_matrix", {}).get("cex", {})
    cex_score = cex.get("score", 50)
    drivers = []

    # Low CEX score = bearish (deposits rising)
    risk = _clamp((100 - cex_score) / 100)
    if cex_score < 40:
        drivers.append("Exchange deposit pressure rising")
    elif cex_score > 70:
        drivers.append("Exchange reserves draining (bullish)")
        risk = max(0, risk - 0.2)

    return risk, drivers


def _actor_conflict_risk(engine_data: dict) -> tuple:
    """Actor conflict and disagreement risk."""
    setup = engine_data.get("setup_engine", {}).get("primary", {})
    otc = engine_data.get("otc_mm_influence", {})
    drivers = []

    risk = 0.0

    # Actor conflict setup
    if setup.get("type") == "actor_conflict":
        risk = 0.7
        drivers.append("Actor conflict detected — key entities disagree")

    # MM presence
    if otc.get("mm_presence"):
        risk = max(risk, 0.5)
        drivers.append("Market maker activity — increased false signal risk")

    # OTC bearish bias
    otc_bias = otc.get("otc_bias", "neutral")
    if otc_bias == "bearish":
        risk = max(risk, 0.4)
        drivers.append("OTC flow bias bearish")

    # Contradictions from context
    contradictions = engine_data.get("decision_explanation", {}).get("bearish_or_contradictions", [])
    if len(contradictions) >= 2:
        risk = max(risk, 0.35)
        if not drivers:
            drivers.append(f"Multiple contradictions ({len(contradictions)})")

    return _clamp(risk), drivers


def _liquidity_void_risk(engine_data: dict) -> tuple:
    """Risk from liquidity voids and adverse targets."""
    liq = engine_data.get("liquidity_map", {})
    voids = liq.get("void_zones", [])
    targets = liq.get("target_zones", [])
    decision = engine_data.get("decision", "NEUTRAL")
    drivers = []
    risk = 0.0

    # Voids are risky
    if voids:
        risk = 0.4 + (0.1 * min(len(voids), 3))
        drivers.append(f"Liquidity void detected ({len(voids)} zones)")

    # Target in opposing direction
    for t in targets:
        direction = t.get("direction", "neutral")
        if decision == "BUY" and direction in ("below", "bearish"):
            risk = max(risk, 0.5)
            drivers.append(f"Liquidity target below current price")
            break
        elif decision == "SELL" and direction in ("above", "bullish"):
            risk = max(risk, 0.5)
            drivers.append(f"Liquidity target above current price")
            break

    return _clamp(risk), drivers


def _setup_failure_risk(engine_data: dict) -> tuple:
    """Risk from probability of setup failure."""
    prob = engine_data.get("probability_layer", {})
    failure = prob.get("failure", 0)
    upgrade = prob.get("upgrade", 0)
    drivers = []

    risk = _clamp(failure)

    if failure > 0.4:
        drivers.append(f"Setup failure probability elevated ({round(failure * 100)}%)")
    elif failure > 0.25:
        drivers.append(f"Setup failure risk moderate ({round(failure * 100)}%)")

    # Upgrade potential reduces risk
    if upgrade > 0.2:
        risk = max(0, risk - 0.1)

    return _clamp(risk), drivers


def _flow_instability_risk(engine_data: dict) -> tuple:
    """Risk from flow momentum issues."""
    flow = engine_data.get("flow_engine", {})
    flow_state = flow.get("state", "neutral")
    strength = flow.get("strength", 0)
    decision = engine_data.get("decision", "NEUTRAL")
    drivers = []
    risk = 0.0

    if flow_state == "flow_exhaustion":
        risk = 0.6
        drivers.append("Flow momentum exhausting — velocity declining")

    # Counter-directional flow
    if decision == "BUY" and flow_state == "bearish_acceleration":
        risk = 0.7
        drivers.append("Bearish flow acceleration contradicts bullish decision")
    elif decision == "SELL" and flow_state == "bullish_acceleration":
        risk = 0.7
        drivers.append("Bullish flow acceleration contradicts bearish decision")

    # Neutral flow with active decision
    if flow_state == "neutral" and decision != "NEUTRAL" and strength < 0.3:
        risk = max(risk, 0.3)
        drivers.append("Weak flow support for current decision")

    return _clamp(risk), drivers


def calculate_market_risk(engine_data: dict) -> dict:
    """
    Main entry point — calculate market risk from engine data.
    Returns risk_score (0-100), risk_level, drivers, invalidation.
    """
    # Run all risk detectors
    exch_risk, exch_drivers = _exchange_risk(engine_data)
    actor_risk, actor_drivers = _actor_conflict_risk(engine_data)
    liq_risk, liq_drivers = _liquidity_void_risk(engine_data)
    fail_risk, fail_drivers = _setup_failure_risk(engine_data)
    flow_risk, flow_drivers = _flow_instability_risk(engine_data)

    # Weighted formula
    raw_score = (
        exch_risk * 0.30 +
        actor_risk * 0.20 +
        liq_risk * 0.20 +
        fail_risk * 0.15 +
        flow_risk * 0.15
    )

    risk_score = round(raw_score * 100)

    # Determine level
    if risk_score <= 25:
        risk_level = "LOW"
    elif risk_score <= 50:
        risk_level = "MODERATE"
    elif risk_score <= 75:
        risk_level = "ELEVATED"
    else:
        risk_level = "HIGH"

    # Collect all drivers
    all_drivers = exch_drivers + actor_drivers + liq_drivers + fail_drivers + flow_drivers

    # Determine invalidation from setup
    setup = engine_data.get("setup_engine", {}).get("primary", {})
    invalidation = setup.get("invalidation", [])

    # Component breakdown
    components = {
        "exchange": round(exch_risk * 100),
        "actor_conflict": round(actor_risk * 100),
        "liquidity": round(liq_risk * 100),
        "setup_failure": round(fail_risk * 100),
        "flow_instability": round(flow_risk * 100),
    }

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "drivers": all_drivers,
        "invalidation": invalidation[:3],
        "components": components,
    }
