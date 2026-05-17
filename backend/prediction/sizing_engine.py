"""
Position Sizing Engine — converts recommendations to position sizes.

Inputs: edge, confidence, alignment, resolution_risk, structural_risk,
        pricing_state, liquidity, spread, action, time_to_expiry.

Output: allowed, size (NONE/TINY/SMALL/MEDIUM/FULL), size_fraction (0-1),
        execution_mode (MARKET/LIMIT/WAIT), max_slippage_bps,
        risk_flags, why_now, why_not.
"""


def compute(analysis: dict, recommendation: dict, resolution: dict,
            pricing: dict, market: dict) -> dict:
    """
    Compute position sizing from full case analysis.

    Returns:
        dict with allowed, size, size_fraction, execution_mode,
              max_slippage_bps, risk_flags, why_now, why_not
    """
    action = recommendation.get("action", "AVOID")
    edge = analysis.get("net_edge", 0)
    confidence = analysis.get("model_confidence", 0)
    alignment = analysis.get("alignment_score", 0.5)
    structural = analysis.get("structural_risk", {}).get("combined_risk", 0)
    res_risk = resolution.get("resolution_risk_score", 0)
    pricing_state = pricing.get("market_state", "fairly_priced")
    liquidity = market.get("liquidity", 0)
    spread = market.get("spread", 0)
    urgency = pricing.get("urgency", "unknown")
    days_to_expiry = pricing.get("days_to_expiry")

    why_now = []
    why_not = []
    risk_flags = []

    # --- Hard blocks ---
    if action == "AVOID":
        return _blocked("AVOID recommendation", ["avoid_action"])

    if res_risk >= 0.55:
        return _blocked("Resolution risk too high", ["resolution_risk_high"])

    if liquidity < 1500 and pricing_state != "stale_price":
        return _blocked("Liquidity too low", ["low_liquidity"])

    # --- Base score (8 components) ---
    score = 0.0

    # 1. Edge
    score += _edge_component(edge)

    # 2. Confidence
    score += confidence * 0.22

    # 3. Alignment
    score += alignment * 0.15

    # 4. Penalties
    score -= res_risk * 0.22
    score -= structural * 0.16
    score -= _pricing_penalty(pricing_state)
    score -= _microstructure_penalty(spread, liquidity)

    # 5. Action modifier
    score += _action_modifier(action)

    # 6. Time urgency modifier
    score += _time_modifier(days_to_expiry, urgency)

    # Clamp
    score = max(0.0, min(1.0, score))

    # --- Score → Size ---
    size, size_fraction = _score_to_size(score, action)

    # --- Execution mode ---
    execution_mode = _execution_mode(pricing_state, spread, action)
    max_slippage_bps = _max_slippage(liquidity, spread)

    # --- Explainability ---
    if edge >= 0.12:
        why_now.append("Edge is materially positive")
    if confidence >= 0.68:
        why_now.append("Model confidence is high")
    if alignment >= 0.55:
        why_now.append("Modules are aligned")
    if pricing_state in ("underpriced", "early_repricing"):
        why_now.append("Market is not fully priced yet")

    if res_risk >= 0.3:
        why_not.append("Resolution risk is still meaningful")
        risk_flags.append("resolution_risk_medium")
    if structural >= 0.35:
        why_not.append("Structural risk is elevated")
        risk_flags.append("structural_risk_elevated")
    if pricing_state in ("overheated", "late_repricing", "priced_in"):
        why_not.append("Price may already reflect the thesis")
        risk_flags.append("pricing_not_ideal")
    if spread >= 0.06:
        why_not.append("Spread is wide for clean execution")
        risk_flags.append("wide_spread")

    return {
        "allowed": size != "NONE",
        "size": size,
        "size_fraction": round(size_fraction, 2),
        "raw_score": round(score, 4),
        "execution_mode": execution_mode,
        "max_slippage_bps": max_slippage_bps,
        "risk_flags": risk_flags,
        "why_now": why_now,
        "why_not": why_not,
    }


def _blocked(reason: str, flags: list) -> dict:
    return {
        "allowed": False,
        "size": "NONE",
        "size_fraction": 0,
        "raw_score": 0,
        "execution_mode": "WAIT",
        "max_slippage_bps": 0,
        "risk_flags": flags,
        "why_now": [],
        "why_not": [reason],
    }


def _edge_component(edge: float) -> float:
    abs_edge = abs(edge)
    if abs_edge >= 0.20:
        return 0.30
    if abs_edge >= 0.15:
        return 0.24
    if abs_edge >= 0.10:
        return 0.18
    if abs_edge >= 0.06:
        return 0.10
    if abs_edge >= 0.03:
        return 0.05
    return 0.0


def _pricing_penalty(state: str) -> float:
    return {
        "underpriced": 0.0,
        "early_repricing": 0.03,
        "fairly_priced": 0.06,
        "priced_in": 0.12,
        "late_repricing": 0.14,
        "overheated": 0.18,
        "panic_move": 0.20,
        "stale_price": 0.04,
    }.get(state, 0.06)


def _microstructure_penalty(spread: float, liquidity: float) -> float:
    p = 0.0
    if spread >= 0.08:
        p += 0.14
    elif spread >= 0.05:
        p += 0.08
    elif spread >= 0.03:
        p += 0.04

    if liquidity < 5000:
        p += 0.08
    elif liquidity < 15000:
        p += 0.04
    return p


def _action_modifier(action: str) -> float:
    return {
        "YES_NOW": 0.10,
        "NO_NOW": 0.10,
        "YES_SMALL": -0.02,
        "NO_SMALL": -0.02,
        "GOOD_IDEA_BAD_PRICE": -0.12,
        "WATCH": -0.16,
        "WAIT": -0.16,
    }.get(action, -0.20)


def _time_modifier(days, urgency) -> float:
    if days is not None:
        if days <= 0.25:  # 6h
            return -0.10
        if days <= 1:
            return -0.06
        if days <= 3:
            return -0.03
    return 0.0


def _score_to_size(score: float, action: str) -> tuple[str, float]:
    # WATCH/WAIT/GIBP: max TINY
    if action in ("WATCH", "WAIT", "GOOD_IDEA_BAD_PRICE"):
        if score >= 0.45:
            return ("TINY", 0.10)
        return ("NONE", 0.0)

    if score >= 0.78:
        return ("FULL", 1.0)
    if score >= 0.62:
        return ("MEDIUM", 0.50)
    if score >= 0.45:
        return ("SMALL", 0.25)
    if score >= 0.32:
        return ("TINY", 0.10)
    return ("NONE", 0.0)


def _execution_mode(pricing_state: str, spread: float, action: str) -> str:
    if pricing_state in ("overheated", "late_repricing") or spread >= 0.05:
        return "LIMIT"
    if action in ("WAIT", "WATCH"):
        return "WAIT"
    return "MARKET"


def _max_slippage(liquidity: float, spread: float) -> int:
    if liquidity >= 50000 and spread < 0.03:
        return 35
    if liquidity >= 15000 and spread < 0.05:
        return 60
    return 100
