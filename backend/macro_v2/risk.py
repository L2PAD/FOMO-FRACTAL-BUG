"""Structural vs Tactical Risk separation."""


def _clamp01(x):
    return max(0.0, min(1.0, x))


def _level(score):
    if score >= 80:
        return "EXTREME"
    if score >= 60:
        return "HIGH"
    if score >= 30:
        return "MEDIUM"
    return "LOW"


def compute_structural_risk(macro_snapshot):
    """Structural Risk (0..100) — macro pressure on the market.
    
    structural = 100 * clamp01(
        0.50 * riskOffProb
      + 0.15 * transitionToExitProb
      + 0.35 * abs(1 - macroMult)
    )
    """
    c = macro_snapshot.get("computed", {})
    riskoff = c.get("riskOffProb", 0.5)
    macro_mult = c.get("macroMult", 1.0)

    # Transition to exit probability (if available)
    transitions = macro_snapshot.get("transitions", {})
    probs = transitions.get("probabilities", {})
    exit_prob = probs.get("CAPITAL_EXIT", 0)

    raw = _clamp01(
        0.50 * riskoff
        + 0.15 * exit_prob
        + 0.35 * abs(1 - macro_mult)
    )
    score = round(100 * raw)

    return {"structural": score, "level": _level(score)}


def compute_tactical_risk(labs_state=None):
    """Tactical Risk (0..100) — exchange microstructure risk.
    
    tactical = 100 * clamp01(
        0.45 * riskPenalty
      + 0.25 * volatilityShock
      + 0.20 * fundingCrowding
      + 0.10 * (1 - setupScore)
    )
    
    If fields missing, zero contribution and renormalize.
    """
    if not labs_state:
        labs_state = {}

    risk_penalty = labs_state.get("riskPenalty", 0)
    vol_shock = labs_state.get("volatilityShock", 0)
    funding = labs_state.get("fundingCrowding", 0)
    setup = labs_state.get("setupScore", 0.5)

    # Count available components for renormalization
    weights = []
    values = []

    if risk_penalty > 0 or "riskPenalty" in labs_state:
        weights.append(0.45)
        values.append(risk_penalty)
    if vol_shock > 0 or "volatilityShock" in labs_state:
        weights.append(0.25)
        values.append(vol_shock)
    if funding > 0 or "fundingCrowding" in labs_state:
        weights.append(0.20)
        values.append(funding)

    weights.append(0.10)
    values.append(1 - setup)

    if not weights:
        return {"tactical": 0, "level": "LOW"}

    # Renormalize weights
    total_w = sum(weights)
    raw = sum(w * v / total_w for w, v in zip(weights, values))
    raw = _clamp01(raw)
    score = round(100 * raw)

    return {"tactical": score, "level": _level(score)}


def compute_risk_split(macro_snapshot, labs_state=None):
    """Combined risk split: structural + tactical + total."""
    s = compute_structural_risk(macro_snapshot)
    t = compute_tactical_risk(labs_state)

    total = round(0.55 * t["tactical"] + 0.45 * s["structural"])

    return {
        "structural": s["structural"],
        "tactical": t["tactical"],
        "total": total,
        "levels": {
            "structural": s["level"],
            "tactical": t["level"],
            "total": _level(total),
        },
    }
