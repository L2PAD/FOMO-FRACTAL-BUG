"""
Execution Adapter — Block 10.2
================================
Translates prediction output into terminal-friendly execution language.

NO new market logic — only derived interpretation of existing prediction truth.

Output designed for:
  - Trading terminal
  - Internal orchestration
  - Tactical application layer
"""

from exchange.output.prediction_formatter import build_prediction_output


def _derive_bias(summary: dict) -> str:
    """Derive execution bias from prediction summary."""
    consensus = summary.get("consensus_direction", "neutral")
    agreement = summary.get("horizon_agreement", 0.0)
    avg_conf = summary.get("avg_confidence", 0.0)

    # Weak agreement or low confidence → neutral regardless of consensus
    if agreement < 0.50 or avg_conf < 0.20:
        return "neutral"

    return consensus


def _derive_strength(summary: dict, horizon_30d: dict | None) -> float:
    """
    Derive execution strength (0.0-1.0) from:
      - avg confidence
      - horizon agreement
      - 30D dominant probability
    """
    avg_conf = summary.get("avg_confidence", 0.0)
    agreement = summary.get("horizon_agreement", 0.0)

    # 30D dominant probability (if available)
    dom_prob = 0.33
    if horizon_30d and "probabilities" in horizon_30d:
        probs = horizon_30d["probabilities"]
        dom_prob = max(probs.values()) if probs else 0.33

    # Weighted combination
    strength = avg_conf * 0.40 + agreement * 0.30 + dom_prob * 0.30
    return round(max(0.0, min(1.0, strength)), 4)


def _derive_risk_mode(horizons: dict) -> str:
    """
    Derive risk mode from uncertainty and 30D path/scenario state.

    - normal: low uncertainty + continuation path
    - cautious: medium uncertainty or base-dominant
    - defensive: high uncertainty or breakdown/distribution path
    """
    h30 = horizons.get("30D", {})
    uncertainties = [h.get("uncertainty", "high") for h in horizons.values()]

    # Count uncertainty levels
    high_count = uncertainties.count("high")
    low_count = uncertainties.count("low")

    path = h30.get("path", "range_hold")
    dominant = h30.get("dominant", "base")

    # Defensive: high uncertainty dominates OR breakdown/distribution path
    if high_count >= 2 or path in ("breakdown", "distribution", "flush_then_recover"):
        return "defensive"

    # Normal: low uncertainty dominates AND continuation/grind path
    if low_count >= 2 and path in ("continuation", "grind_up") and dominant != "base":
        return "normal"

    # Default: cautious
    return "cautious"


def _derive_timing_quality(summary: dict, horizons: dict) -> str:
    """
    Timing quality = quality of current setup for terminal use.

    - high: aligned horizons, low uncertainty, clear direction
    - medium: mixed but usable
    - low: conflict, high uncertainty, base-heavy
    """
    agreement = summary.get("horizon_agreement", 0.0)
    avg_conf = summary.get("avg_confidence", 0.0)
    uncertainties = [h.get("uncertainty", "high") for h in horizons.values()]

    h30 = horizons.get("30D", {})
    dominant = h30.get("dominant", "base")

    high_unc = uncertainties.count("high")

    # Low: high uncertainty dominant or very low agreement
    if high_unc >= 2 or agreement < 0.50:
        return "low"

    # High: strong agreement + decent confidence + not base-dominant
    if agreement >= 0.67 and avg_conf >= 0.45 and dominant != "base":
        return "high"

    return "medium"


def _derive_execution_hint(risk_mode: str, timing_quality: str, strength: float) -> str:
    """
    Final execution hint — 3 modes only.

    - allow: normal risk, decent timing, reasonable strength
    - allow_reduced: cautious risk or medium timing
    - wait: defensive risk or low timing quality
    """
    if risk_mode == "defensive" or timing_quality == "low":
        return "wait"
    if risk_mode == "normal" and timing_quality == "high" and strength >= 0.40:
        return "allow"
    return "allow_reduced"


def _build_reasons(summary: dict, horizons: dict, bias: str, risk_mode: str) -> list[str]:
    """Build human-readable reason list for execution decision."""
    reasons = []

    h30 = horizons.get("30D", {})
    h7 = horizons.get("7D", {})
    h1 = horizons.get("24H", {})

    # 30D info
    if h30.get("dominant"):
        reasons.append(f"30D {h30['dominant']}-dominant")
    if h30.get("path"):
        reasons.append(f"30D path: {h30['path']}")

    # 7D direction
    if h7.get("direction"):
        reasons.append(f"7D {h7['direction']}")

    # 1D direction
    if h1.get("direction"):
        reasons.append(f"1D {h1['direction']}")

    # Uncertainty
    unc_30 = h30.get("uncertainty", "high")
    reasons.append(f"uncertainty {unc_30}")

    # Agreement
    agreement = summary.get("horizon_agreement", 0.0)
    reasons.append(f"agreement {agreement:.0%}")

    return reasons


def build_execution_adapter(asset: str) -> dict:
    """
    Build execution adapter output from prediction truth.

    Calls build_prediction_output internally — single source of truth.
    Optionally applies ML catastrophic risk overlay (Block 12.1).
    """
    prediction = build_prediction_output(asset)
    summary = prediction.get("summary", {})
    horizons = prediction.get("horizons", {})

    bias = _derive_bias(summary)
    strength = _derive_strength(summary, horizons.get("30D"))
    risk_mode = _derive_risk_mode(horizons)
    timing_quality = _derive_timing_quality(summary, horizons)
    execution_hint = _derive_execution_hint(risk_mode, timing_quality, strength)
    reasons = _build_reasons(summary, horizons, bias, risk_mode)

    # Block 12.1: Catastrophic risk overlay
    catastrophic_risk_score = 0.0
    catastrophic_risk_level = "unknown"
    try:
        from ml_overlay.catastrophic_risk import predict_from_asset
        # Use 7D as primary horizon for risk assessment
        cr = predict_from_asset(asset, "7D")
        if cr.get("model_status") == "OK":
            catastrophic_risk_score = cr["catastrophic_risk"]
            catastrophic_risk_level = cr["risk_level"]

            # Override execution hint based on catastrophic risk
            if catastrophic_risk_score > 0.6:
                execution_hint = "wait"
                reasons.append(f"catastrophic_risk={catastrophic_risk_score:.0%}")
            elif catastrophic_risk_score > 0.4 and execution_hint == "allow":
                execution_hint = "allow_reduced"
                reasons.append(f"catastrophic_risk={catastrophic_risk_score:.0%}")
    except Exception:
        pass

    return {
        "asset": asset.upper(),
        "bias": bias,
        "strength": strength,
        "risk_mode": risk_mode,
        "timing_quality": timing_quality,
        "execution_hint": execution_hint,
        "catastrophic_risk": catastrophic_risk_score,
        "catastrophic_risk_level": catastrophic_risk_level,
        "reasons": reasons,
    }
