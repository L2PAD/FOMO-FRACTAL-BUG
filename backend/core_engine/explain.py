"""
Core Engine V2.1 — Explain.
Contribution breakdown + human-readable text.
"""


def build_explain(regime: dict, risk: dict, pressure: dict, transition: dict,
                  execution: dict, integrity: dict, macro: dict) -> dict:
    """Generate human-readable explanation with contribution breakdown."""
    reasons = []
    bullets = []

    dom = regime["dominant"]
    conf = regime["confidence"]
    conf_level = regime.get("confidenceLevel", "low")
    risk_level = risk["level"]
    risk_idx = risk["totalIndex"]
    bias = pressure["biasLabel"]
    shift = transition["shiftProbability"]
    instability = transition["instability"]

    # One-liner
    bias_text = bias.replace("_", " ").replace("slight ", "slightly ")
    one_liner = f"{dom.capitalize()} regime ({conf*100:.0f}% {conf_level}), risk {risk_level} ({risk_idx}), {bias_text} bias"

    if shift > 0.4:
        one_liner += f", elevated transition risk ({shift*100:.0f}%)"
    if execution.get("strongActionsBlocked"):
        one_liner += ", strong actions blocked"

    # Regime bullets
    bullets.append(f"Market in {dom} regime with {conf*100:.0f}% confidence ({conf_level})")
    if conf_level == "low":
        bullets.append("Low regime confidence — mixed signals, no clear structure")
        reasons.append("LOW_REGIME_CONFIDENCE")

    # Dominance gap
    gap = regime.get("dominanceGap", 0)
    if gap < 0.05:
        bullets.append(f"Very tight regime competition (gap {gap*100:.0f}%) — high ambiguity")
        reasons.append("TIGHT_REGIME_COMPETITION")

    # Risk bullets
    if risk_idx > 60:
        bullets.append(f"High risk environment ({risk_idx}/100) — defensive posture recommended")
        reasons.append("HIGH_RISK")
    elif risk_idx < 30:
        bullets.append(f"Low risk ({risk_idx}/100) — favorable conditions")

    # Breakdown: which risk axes are elevated
    breakdown = risk.get("breakdown", {})
    elevated = [(k, v) for k, v in breakdown.items() if v > 50]
    for axis, val in sorted(elevated, key=lambda x: -x[1]):
        bullets.append(f"Elevated {axis} risk ({val}/100)")
        reasons.append(f"HIGH_{axis.upper()}_RISK")

    # Pressure
    if bias in ("bullish", "slight_bullish"):
        bullets.append(f"Upward pressure dominant — {bias_text}")
    elif bias in ("bearish", "slight_bearish"):
        bullets.append(f"Downward pressure dominant — {bias_text}")
    else:
        bullets.append("Balanced pressure — no directional bias")

    # Transition
    if shift > 0.4:
        bullets.append(f"Regime shift probability {shift*100:.0f}% — instability {instability*100:.0f}%")
        reasons.append("ELEVATED_SHIFT_PROBABILITY")
        top_trans = transition.get("transitions", [])
        if top_trans:
            t = top_trans[0]
            bullets.append(f"Most likely transition: {t['from']} → {t['to']} ({t['probability']*100:.0f}%)")

    # Integrity
    warnings = integrity.get("warnings", [])
    if "STALE_DATA" in warnings:
        bullets.append("Data freshness degraded — confidence reduced")
        reasons.append("STALE_DATA")
    if "VENUE_CONFLICT" in warnings:
        bullets.append("Venue divergence detected — increased instability")
        reasons.append("VENUE_CONFLICT")

    # Macro
    if macro.get("strongActionsBlocked"):
        regime_label = macro.get("regimeLabel", "Unknown")
        riskoff = macro.get("riskOffProb", 0)
        bullets.append(f"Macro: {regime_label} — Risk-Off {riskoff*100:.0f}% — strong actions blocked")
        reasons.append("MACRO_RISK_OFF")
    elif macro.get("available"):
        regime_label = macro.get("regimeLabel", "Neutral")
        bullets.append(f"Macro context: {regime_label} (confidence x{macro.get('multiplier', 1.0):.2f})")

    # Execution
    if execution.get("integrityGated"):
        bullets.append("Signal amplification reduced due to data quality")
        reasons.append("INTEGRITY_GATED")

    return {
        "oneLiner": one_liner,
        "bullets": bullets,
        "reasons": reasons,
        "contributions": {
            "regime": {"dominant": dom, "confidence": conf, "level": conf_level, "gap": gap},
            "risk": {"total": risk_idx, "level": risk_level},
            "bias": {"label": bias, "net": pressure["netBias"]},
            "transition": {"shift": shift, "instability": instability},
            "macro": {
                "regime": macro.get("regime", "NEUTRAL"),
                "regimeLabel": macro.get("regimeLabel", "Neutral"),
                "riskOffProb": macro.get("riskOffProb", 0.5),
                "multiplier": macro.get("multiplier", 1.0),
                "available": macro.get("available", False),
            },
            "integrity": {"penalty": integrity.get("penalty", 1.0), "warnings": warnings},
        },
    }
