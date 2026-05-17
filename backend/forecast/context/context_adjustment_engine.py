"""
Context Adjustment Engine
===========================
Applies context-aware adjustments to score, confidence, and band width.
Modifies intensity — NOT direction. The adjustments are mild and capped.
"""


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


# Caps for adjustment multipliers
# Score caps are safety limits (score_mult is always 1.0 in confidence-only mode)
_MAX_SCORE_BOOST = 1.08
_MAX_SCORE_SHRINK = 0.90
# Confidence caps — wider range since context only affects confidence now
_MAX_CONF_BOOST = 1.10
_MAX_CONF_SHRINK = 0.80
# Band caps — wider to allow context meaningful influence
_MAX_BAND_EXPAND = 1.25
_MAX_BAND_SHRINK = 0.90


def apply_context(
    score: float,
    conf_dir: float,
    conf_tgt: float,
    band_width: float,
    ctx: dict,
    phase: dict,
) -> dict:
    """
    Apply market-context adjustments.
    Returns adjusted values + audit metadata.
    """
    market_phase = phase["market_phase"]
    ctx_conf = phase["context_confidence"]

    score_mult = 1.0
    conf_dir_mult = 1.0
    conf_tgt_mult = 1.0
    band_mult = 1.0
    flags = []

    if market_phase == "continuation":
        # Strong trend: boost confidence, tighten bands
        conf_dir_mult = 1.08
        conf_tgt_mult = 1.05
        band_mult = 0.93
        flags.append("continuation_boost")

    elif market_phase == "late_trend":
        # Trend exhausting: reduce confidence, widen bands
        conf_dir_mult = 0.90
        conf_tgt_mult = 0.88
        band_mult = 1.12
        flags.append("late_trend_caution")

    elif market_phase == "pullback":
        # Pullback in trend: slight confidence reduction, slightly wider bands
        conf_dir_mult = 0.97
        band_mult = 1.03
        flags.append("pullback_steady")

    elif market_phase == "unstable_transition":
        # Unreliable environment: drop confidence hard, widen bands
        conf_dir_mult = 0.82
        conf_tgt_mult = 0.82
        band_mult = 1.20
        flags.append("transition_low_trust")

    elif market_phase == "breakdown":
        # Bearish stress: reduce bull confidence, keep bear confidence
        if score < 0:
            conf_dir_mult = 1.04
            flags.append("breakdown_bear_affirm")
        else:
            conf_dir_mult = 0.85
            flags.append("breakdown_bull_distrust")
        band_mult = 1.10

    elif market_phase == "recovery_attempt":
        # Post-damage recovery: cautious confidence
        conf_dir_mult = 0.93
        conf_tgt_mult = 0.92
        band_mult = 1.08
        flags.append("recovery_caution")

    elif market_phase == "mixed_range":
        # No clear signal: reduce confidence, widen bands
        conf_dir_mult = 0.91
        conf_tgt_mult = 0.90
        band_mult = 1.12
        flags.append("range_caution")

    # Clamp multipliers within safety caps
    score_mult = _clamp(score_mult, _MAX_SCORE_SHRINK, _MAX_SCORE_BOOST)
    conf_dir_mult = _clamp(conf_dir_mult, _MAX_CONF_SHRINK, _MAX_CONF_BOOST)
    conf_tgt_mult = _clamp(conf_tgt_mult, _MAX_CONF_SHRINK, _MAX_CONF_BOOST)
    band_mult = _clamp(band_mult, _MAX_BAND_SHRINK, _MAX_BAND_EXPAND)

    # Apply
    adj_score = _clamp(score * score_mult, -1.0, 1.0)
    adj_conf_dir = _clamp(conf_dir * conf_dir_mult, 0.0, 1.0)
    adj_conf_tgt = _clamp(conf_tgt * conf_tgt_mult, 0.0, 1.0)
    adj_band = band_width * band_mult

    return {
        "score": round(adj_score, 6),
        "conf_dir": round(adj_conf_dir, 4),
        "conf_tgt": round(adj_conf_tgt, 4),
        "band_width": round(adj_band, 6),
        "adjustments": {
            "score_mult": round(score_mult, 4),
            "conf_dir_mult": round(conf_dir_mult, 4),
            "conf_tgt_mult": round(conf_tgt_mult, 4),
            "band_mult": round(band_mult, 4),
            "flags": flags,
        },
    }
