"""
Context Feature Builder
========================
Builds market context signals from existing base features, fused structure,
and multiscale payload. All values are deterministic and in [0, 1].
"""


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def build_context_features(
    base: dict,
    fused_structure: dict,
    multiscale: dict,
) -> dict:
    """
    Build context features from already-computed pipeline data.
    All outputs are in [0, 1] except volatility_state (categorical).
    """
    # Extract inputs
    momentum = base.get("momentum", 0.0)
    volatility = base.get("volatility", 0.05)

    fused_bias = fused_structure.get("structure_bias_score", 0.0)
    fused_trend = fused_structure.get("structure_trend_score", 0.0)
    fused_momentum = fused_structure.get("structure_momentum_score", 0.0)
    fused_reversal = fused_structure.get("structure_reversal_risk", 0.0)
    fused_exhaustion = fused_structure.get("structure_exhaustion_score", 0.0)
    fused_stability = fused_structure.get("structure_stability_score", 0.0)

    major = multiscale.get("major", {})
    minor = multiscale.get("minor", {})
    mode = multiscale.get("mode", "mixed_range")

    major_bias = major.get("structure_bias_score", 0.0)
    minor_bias = minor.get("structure_bias_score", 0.0)
    major_reversal = major.get("structure_reversal_risk", 0.0)
    minor_reversal = minor.get("structure_reversal_risk", 0.0)
    major_exhaustion = major.get("structure_exhaustion_score", 0.0)

    # ── Trend Strength ──
    # How directional is the market overall
    momentum_norm = _clamp(abs(momentum) * 10, 0, 1)
    trend_strength = _clamp(
        0.5 * abs(fused_bias)
        + 0.3 * fused_trend
        + 0.2 * momentum_norm
    )

    # ── Trend Persistence ──
    # Is the trend continuous or choppy
    # High stability + low reversal disagreement = high persistence
    choch_density_norm = _clamp(
        abs(major_reversal - minor_reversal) * 2, 0, 1
    )
    trend_continuity = 1.0 if mode == "aligned" else (0.6 if mode == "pullback" else 0.3)
    trend_persistence = _clamp(
        0.5 * fused_stability
        + 0.3 * (1.0 - choch_density_norm)
        + 0.2 * trend_continuity
    )

    # ── Trend Exhaustion ──
    # Is the trend dying
    late_move_compression = _clamp(
        max(0, fused_trend - abs(fused_bias)) * 2, 0, 1
    )
    trend_exhaustion = _clamp(
        0.6 * fused_exhaustion
        + 0.2 * (1.0 - trend_persistence)
        + 0.2 * late_move_compression
    )

    # ── Reversal Risk ──
    # How likely the current bias breaks
    disagreement = 0.0 if mode == "aligned" else (
        _clamp(abs(abs(major_bias) - abs(minor_bias)) * 2, 0, 1)
        if mode != "mixed_range" else 0.5
    )
    reversal_risk = _clamp(
        0.5 * fused_reversal
        + 0.3 * disagreement
        + 0.2 * choch_density_norm
    )

    # ── Drawdown Pressure ──
    # Bearish stress / damage
    # Use negative momentum as proxy for downside pressure
    downside_momentum = _clamp(max(0, -momentum) * 15, 0, 1)
    failed_bounce = _clamp(
        max(0, minor_reversal - major_reversal) * 3, 0, 1
    ) if mode == "pullback" and major_bias < 0 else 0.0
    downside_cluster = _clamp(abs(min(0, fused_bias)) * 1.5, 0, 1)
    drawdown_pressure = _clamp(
        0.6 * downside_momentum
        + 0.2 * failed_bounce
        + 0.2 * downside_cluster
    )

    # ── Volatility State ──
    # Categorical: compressed / normal / expanded
    # Use simple percentile thresholds on volatility
    if volatility < 0.02:
        volatility_state = "compressed"
    elif volatility > 0.06:
        volatility_state = "expanded"
    else:
        volatility_state = "normal"

    return {
        "trend_strength": round(trend_strength, 4),
        "trend_persistence": round(trend_persistence, 4),
        "trend_exhaustion": round(trend_exhaustion, 4),
        "reversal_risk": round(reversal_risk, 4),
        "drawdown_pressure": round(drawdown_pressure, 4),
        "volatility_state": volatility_state,
    }
