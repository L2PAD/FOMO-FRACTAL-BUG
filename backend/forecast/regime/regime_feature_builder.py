"""
Regime Feature Builder
=======================
Builds regime features from base, structure, context, and multiscale data.
All outputs are deterministic and in [0, 1].

Features:
  1. trend_strength     — directional intensity
  2. trend_persistence  — continuity vs chop
  3. exhaustion         — trend decay signals
  4. reversal_risk      — probability of bias breaking
  5. drawdown_pressure  — bearish stress / damage
  6. structure_alignment— major/minor agreement (NEW)
  7. volatility_expansion — vol state as continuous (NEW)
"""


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def build_regime_features(
    base: dict,
    structure: dict,
    context: dict,
    multiscale: dict,
) -> dict:
    """
    Build regime features.  Reuses context signals where possible,
    adds structure_alignment and volatility_expansion.
    """
    # Reuse context signals directly (already calibrated [0,1])
    trend_strength = context.get("trend_strength", 0.3)
    trend_persistence = context.get("trend_persistence", 0.5)
    exhaustion = context.get("trend_exhaustion", 0.1)
    reversal_risk = context.get("reversal_risk", 0.1)
    drawdown_pressure = context.get("drawdown_pressure", 0.1)

    # NEW: Structure Alignment
    # How much do major and minor agree on direction?
    major = multiscale.get("major", {})
    minor = multiscale.get("minor", {})
    major_bias = major.get("structure_bias_score", 0.0)
    minor_bias = minor.get("structure_bias_score", 0.0)

    # Soft alignment: 1.0 = perfect agreement, 0.0 = opposite
    if abs(major_bias) < 0.01 and abs(minor_bias) < 0.01:
        structure_alignment = 0.5  # both neutral
    else:
        # Sign agreement + magnitude similarity
        sign_agree = 1.0 if (major_bias * minor_bias) > 0 else 0.0
        mag_diff = abs(abs(major_bias) - abs(minor_bias))
        structure_alignment = _clamp(
            0.6 * sign_agree + 0.4 * (1.0 - mag_diff)
        )

    # NEW: Volatility Expansion (continuous version of vol_state)
    vol_state = context.get("volatility_state", "normal")
    if vol_state == "compressed":
        volatility_expansion = 0.2
    elif vol_state == "expanded":
        volatility_expansion = 0.8
    else:
        # Use actual volatility for finer granularity
        vol = base.get("volatility", 0.04)
        volatility_expansion = _clamp((vol - 0.02) / 0.04)  # 0.02→0, 0.06→1

    return {
        "trend_strength": round(trend_strength, 4),
        "trend_persistence": round(trend_persistence, 4),
        "exhaustion": round(exhaustion, 4),
        "reversal_risk": round(reversal_risk, 4),
        "drawdown_pressure": round(drawdown_pressure, 4),
        "structure_alignment": round(structure_alignment, 4),
        "volatility_expansion": round(volatility_expansion, 4),
    }
