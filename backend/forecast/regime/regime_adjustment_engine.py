"""
Regime Adjustment Engine v4.3.1
================================
Applies calibrated regime-aware adjustments to confidence and band width.

v4.3.1 CHANGES:
  - decision_uncertainty based on REGIME ACCURACY prior (empirically calibrated)
  - Feature-based entropy shown to be anti-correlated with accuracy
  - Transition hard rule (persistent low accuracy zone)
  - Top1/Top2 gap-based ambiguity scaling
  - Phase × regime synergy (2 rules)

CRITICAL RULE: Regime NEVER changes score sign. Only modulates
confidence and band width.

Caps:
  conf_dir_mult  [0.70, 1.10]  — widened for v4.3.1 calibration
  conf_tgt_mult  [0.70, 1.08]
  band_mult      [0.93, 1.15]
"""

_MAX_CONF_DIR_BOOST = 1.10
_MIN_CONF_DIR_SHRINK = 0.70
_MAX_CONF_TGT_BOOST = 1.08
_MIN_CONF_TGT_SHRINK = 0.70
_MAX_BAND_EXPAND = 1.15
_MIN_BAND_SHRINK = 0.93

# Empirically calibrated regime uncertainty prior
# Derived from v4.3.0 backfill per-regime accuracy:
#   pullback=78.6% → low uncertainty
#   breakdown=66.7% → low-moderate
#   range=50.0% → moderate
#   trend=42.9% → moderate-high
#   transition=8.3% → very high
_REGIME_UNCERTAINTY_PRIOR = {
    "pullback":   0.15,
    "breakdown":  0.25,
    "range":      0.45,
    "trend":      0.55,
    "transition": 0.90,
}


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _compute_decision_uncertainty(
    dominant_regime: str,
    regime_entropy: float,
) -> float:
    """
    Decision-aware uncertainty metric.
    Base: empirical regime accuracy prior (what actually predicts errors).
    Modulation: regime_entropy adds ±15% spread.
    Output in [0, 1].
    """
    base = _REGIME_UNCERTAINTY_PRIOR.get(dominant_regime, 0.50)
    # Entropy modulates: high entropy pushes up, low pulls down
    # Scale: 0.7 (low entropy) to 1.3 (high entropy)
    entropy_mod = 0.7 + 0.6 * regime_entropy
    return _clamp(base * entropy_mod, 0.0, 1.0)


def apply_regime_adjustments(
    score: float,
    conf_dir: float,
    conf_tgt: float,
    band_mult: float,
    regime: dict,
    regime_features: dict | None = None,
    context_phase: str | None = None,
) -> dict:
    """
    Apply calibrated regime-aware soft adjustments (v4.3.1).
    score is read-only — never modified by regime.
    """
    dominant = regime["dominant_regime"]
    confidence = regime["regime_confidence"]
    entropy = regime["regime_entropy"]
    probs = regime.get("probabilities", {})

    conf_dir_mult = 1.0
    conf_tgt_mult = 1.0
    band_m = 1.0
    adj_flags = []

    # ── Task 2.1: Decision-aware uncertainty (regime-driven) ──
    decision_uncertainty = _compute_decision_uncertainty(dominant, entropy)

    # ── Per-regime base rules ──
    if dominant == "trend":
        if confidence > 0.30:
            conf_dir_mult = 1.04
            band_m = 0.96
            adj_flags.append("trend_boost")

    elif dominant == "range":
        conf_dir_mult = 0.94
        conf_tgt_mult = 0.92
        band_m = 1.08
        adj_flags.append("range_dampen")

    elif dominant == "pullback":
        conf_dir_mult = 1.03
        band_m = 0.97
        adj_flags.append("pullback_boost")

    elif dominant == "transition":
        conf_dir_mult = 0.90
        conf_tgt_mult = 0.88
        band_m = 1.10
        adj_flags.append("transition_caution")

    elif dominant == "breakdown":
        if score < 0:
            conf_dir_mult = 1.03
            adj_flags.append("breakdown_bear_affirm")
        else:
            conf_dir_mult = 0.92
            adj_flags.append("breakdown_bull_caution")
        band_m = 1.05

    # ── Task 2.2: Decision uncertainty → confidence mapping ──
    # Piecewise: mild damping for moderate, strong for high uncertainty
    if decision_uncertainty < 0.30:
        uncertainty_mult = 1.0  # confident zone — no damping
    elif decision_uncertainty < 0.55:
        uncertainty_mult = 0.93  # moderate — mild damping
    else:
        uncertainty_mult = 0.80  # high — strong damping
    conf_dir_mult *= uncertainty_mult
    conf_tgt_mult *= uncertainty_mult
    if uncertainty_mult < 1.0:
        adj_flags.append("uncertainty_damping")

    # ── Task 2.3: Transition hard rule ──
    # Transition accuracy = 8.3% → aggressive confidence reduction
    if dominant == "transition":
        conf_dir_mult *= 0.75
        conf_tgt_mult *= 0.75
        band_m *= 1.10
        adj_flags.append("transition_hard_dampen")

    # ── Task 2.4: Top1/Top2 gap ambiguity ──
    if probs:
        sorted_p = sorted(probs.values(), reverse=True)
        if len(sorted_p) >= 2:
            gap = sorted_p[0] - sorted_p[1]
            if gap < 0.08:
                conf_dir_mult *= 0.85
                conf_tgt_mult *= 0.85
                adj_flags.append("ambiguity_gap_dampen")

    # ── Task 2.5: Phase × regime synergy (2 rules) ──
    if context_phase:
        if context_phase == "pullback" and dominant == "trend":
            conf_dir_mult *= 1.05
            adj_flags.append("synergy_pullback_trend")
        elif context_phase == "unstable_transition" and dominant in ("transition", "range"):
            conf_dir_mult *= 0.85
            conf_tgt_mult *= 0.85
            adj_flags.append("synergy_transition_weak")

    # ── Apply caps ──
    conf_dir_mult = _clamp(conf_dir_mult, _MIN_CONF_DIR_SHRINK, _MAX_CONF_DIR_BOOST)
    conf_tgt_mult = _clamp(conf_tgt_mult, _MIN_CONF_TGT_SHRINK, _MAX_CONF_TGT_BOOST)
    band_m = _clamp(band_m, _MIN_BAND_SHRINK, _MAX_BAND_EXPAND)

    return {
        "conf_dir": round(conf_dir * conf_dir_mult, 6),
        "conf_tgt": round(conf_tgt * conf_tgt_mult, 6),
        "band_mult": round(band_mult * band_m, 6),
        "adjustments": {
            "conf_dir_mult": round(conf_dir_mult, 4),
            "conf_tgt_mult": round(conf_tgt_mult, 4),
            "band_mult": round(band_m, 4),
            "decision_uncertainty": round(decision_uncertainty, 4),
            "flags": adj_flags,
        },
    }
