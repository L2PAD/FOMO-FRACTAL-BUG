"""
Catalyst Engine — probability engine for non-price-threshold markets.

Handles: ETF approval, listing, launch, governance, unlock events.
Uses 7-axis probability model instead of scenario-based quant model.

prob = base_prior + Σ(positive_axes) - Σ(negative_axes)
confidence = f(source_quality, signal_density, readiness, official_signals)
"""
from prediction.intelligence import catalyst_feature_builder


# Base priors per event type
BASE_PRIORS = {
    "etf_catalyst": 0.35,
    "listing_catalyst": 0.45,
    "launch_catalyst": 0.40,
    "governance_catalyst": 0.30,
    "unlock_catalyst": 0.50,
}


def run(decoded: dict, related_events: list[dict]) -> dict:
    """
    Run catalyst probability engine.

    Args:
        decoded: decoded market with event_type, entities, deadline, etc.
        related_events: list of {title, text, source, source_type, source_quality, relevance_score}

    Returns:
        dict with fair_yes_prob, confidence, drivers, risks, components
    """
    features = catalyst_feature_builder.build(decoded, related_events)
    etype = decoded.get("event_type", "unknown")

    base_prob = BASE_PRIORS.get(etype, 0.30)

    # Positive contributions
    positive = (
        features["official_signal_score"] * 0.30
        + features["source_credibility_score"] * 0.18
        + features["narrative_pressure_score"] * 0.16
        + features["timeline_pressure_score"] * 0.10
        + features["readiness_score"] * 0.16
        + features["precedent_score"] * 0.10
    )

    # Negative contributions
    negative = (
        features["blocker_penalty"] * 0.24
        + features["contradiction_score"] * 0.12
    )

    fair_yes_prob = base_prob + positive - negative

    # Official signal boost
    if features["official_signal_count"] >= 1:
        fair_yes_prob += 0.06

    fair_yes_prob = max(0.01, min(0.99, fair_yes_prob))

    # Confidence
    confidence = _compute_confidence(features, related_events)

    # Bias for alignment
    bias = "bullish" if fair_yes_prob >= 0.55 else ("bearish" if fair_yes_prob <= 0.45 else "neutral")

    # Drivers / risks
    drivers = _build_drivers(decoded, features)
    risks = _build_risks(decoded, features)

    return {
        "fair_yes_prob": round(fair_yes_prob, 4),
        "fair_no_prob": round(1.0 - fair_yes_prob, 4),
        "model_confidence": round(confidence, 4),
        "uncertainty": round(1.0 - confidence, 4),
        "bias": bias,
        "regime": "CATALYST",
        "structural_risk": {
            "reversal_risk": round(features["contradiction_score"] * 0.7, 4),
            "breakdown_risk": round(features["blocker_penalty"] * 0.5, 4),
            "drawdown_pressure": 0.0,
            "combined_risk": round((features["contradiction_score"] * 0.7 + features["blocker_penalty"] * 0.3) * 0.5, 4),
        },
        "drivers": drivers,
        "risks": risks,
        "components": {
            "base_prob": round(base_prob, 4),
            "official_signal": round(features["official_signal_score"], 4),
            "source_credibility": round(features["source_credibility_score"], 4),
            "narrative_pressure": round(features["narrative_pressure_score"], 4),
            "timeline_pressure": round(features["timeline_pressure_score"], 4),
            "readiness_score": round(features["readiness_score"], 4),
            "precedent_score": round(features["precedent_score"], 4),
            "blocker_penalty": round(-features["blocker_penalty"], 4),
            "contradiction_penalty": round(-features["contradiction_score"], 4),
        },
        "features": features,
    }


def _compute_confidence(features: dict, related_events: list) -> float:
    conf = 0.35
    conf += min(0.18, features["source_credibility_score"] * 0.20)
    conf += min(0.14, features["signal_density"] * 0.14)
    conf += min(0.14, features["readiness_score"] * 0.16)

    if features["official_signal_count"] >= 1:
        conf += 0.12

    if features["blocker_count"] >= 2:
        conf -= 0.08

    if len(related_events) <= 1:
        conf -= 0.06

    return max(0.15, min(0.95, conf))


def _build_drivers(decoded: dict, features: dict) -> list[str]:
    drivers = []
    if features["official_signal_count"] > 0:
        drivers.append("Official or near-official signals detected")
    if features["high_quality_signal_count"] >= 2:
        drivers.append("Multiple high-quality relevant sources support the thesis")
    if features["readiness_score"] >= 0.45:
        drivers.append("Execution readiness signals are present")
    if features["timeline_pressure_score"] >= 0.70:
        drivers.append("Timeline proximity increases probability of resolution")

    etype = decoded.get("event_type", "")
    if etype == "etf_catalyst":
        drivers.append("ETF market — filing/review style signals tracked")
    elif etype == "listing_catalyst":
        drivers.append("Listing market — exchange preparation signals tracked")
    elif etype == "launch_catalyst":
        drivers.append("Launch market — deployment readiness indicators tracked")

    return drivers


def _build_risks(decoded: dict, features: dict) -> list[str]:
    risks = []
    if features["blocker_count"] > 0:
        risks.append("Blocking or contradictory signals present")
    if features["official_signal_count"] == 0:
        risks.append("No explicit official confirmation detected")
    if features["source_credibility_score"] < 0.45:
        risks.append("Source quality insufficient for high conviction")
    if features["readiness_score"] < 0.20:
        risks.append("Execution readiness weak or unconfirmed")
    if features["contradiction_score"] >= 0.25:
        risks.append("Narrative conflict elevated")
    return risks
