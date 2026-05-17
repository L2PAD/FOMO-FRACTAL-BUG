"""Cross-System Sync: Core Regime ↔ Macro Regime alignment."""


def _clamp01(x):
    return max(0.0, min(1.0, x))


def _core_dir(bias):
    """Map core bias to direction: BULL=+1, BEAR=-1, NEUTRAL=0."""
    b = str(bias).upper()
    if b in ("BULL", "BULLISH", "UP"):
        return 1.0
    if b in ("BEAR", "BEARISH", "DOWN"):
        return -1.0
    return 0.0


def _macro_dir(macro_snapshot):
    """Map macro state to direction: RISK_ON=+1, RISK_OFF=-1, NEUTRAL=0."""
    c = macro_snapshot.get("computed", {})
    regime = c.get("regime", "NEUTRAL")
    riskoff = c.get("riskOffProb", 0.5)

    if regime == "ALT_ROTATION":
        return 1.0
    if regime in ("CAPITAL_EXIT", "FLIGHT_TO_BTC") and riskoff > 0.6:
        return -1.0
    if riskoff > 0.65:
        return -1.0
    if riskoff < 0.35:
        return 1.0
    return 0.0


def compute_alignment(core_snapshot, macro_snapshot):
    """Compute alignment/conflict between Core Engine and Macro V2.
    
    ConflictScore = 100 * weightedConflict
    AlignmentScore = 100 - ConflictScore
    """
    # Core direction and strength
    pressure = core_snapshot.get("pressure", {})
    core_bias = "BULL" if pressure.get("upward", 50) > 60 else ("BEAR" if pressure.get("downward", 50) > 60 else "NEUTRAL")
    core_dir = _core_dir(core_bias)

    regime = core_snapshot.get("regime", {})
    core_confidence = regime.get("confidence", 0.5)
    core_regime = regime.get("dominant", "range")

    # Macro direction and strength
    macro_dir = _macro_dir(macro_snapshot)
    c = macro_snapshot.get("computed", {})
    riskoff = c.get("riskOffProb", 0.5)
    macro_mult = c.get("macroMult", 1.0)
    macro_regime = c.get("regime", "NEUTRAL")

    macro_strength = _clamp01(0.6 * riskoff + 0.4 * abs(1 - macro_mult))
    core_strength = _clamp01(core_confidence)

    # Conflict calculation
    conflict = 0.5 * (1 - core_dir * macro_dir)
    weighted = conflict * (0.6 * macro_strength + 0.4 * core_strength)

    conflict_score = round(100 * weighted)
    alignment_score = 100 - conflict_score

    # State
    if conflict_score >= 70:
        state = "CONFLICT"
    elif conflict_score >= 30:
        state = "MIXED"
    else:
        state = "ALIGNED"

    # Explain bullets
    explain = []
    if state == "ALIGNED":
        explain.append("Core and Macro aligned — signals reinforce each other")
    elif state == "CONFLICT":
        explain.append("Core bias conflicts with macro regime — reduce aggression")
    else:
        explain.append("Mixed signals between Core and Macro — use caution")

    if macro_strength > 0.6:
        explain.append("Macro signal strong — respect macro context")
    elif macro_strength < 0.3:
        explain.append("Macro signal weak — Core has more authority")

    if conflict_score < 20:
        explain.append("OK to increase aggression slightly")
    elif conflict_score > 60:
        explain.append("Prefer WATCH mode, short horizon only")

    return {
        "alignmentScore": alignment_score,
        "conflictScore": conflict_score,
        "state": state,
        "core": {
            "bias": core_bias,
            "confidence": round(core_confidence, 3),
            "regime": core_regime,
        },
        "macro": {
            "bias": "RISK_OFF" if macro_dir < 0 else ("RISK_ON" if macro_dir > 0 else "NEUTRAL"),
            "riskOffProb": round(riskoff, 3),
            "macroMult": round(macro_mult, 3),
            "regime": macro_regime,
        },
        "explain": explain,
    }
