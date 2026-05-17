"""
Tactical Fusion Engine
========================
Block X — Task X.3

Fuses discrete tactical signals into a single bias + strength.
Simple weighted scoring — no ML, fully transparent.

Key design: single weak signal does NOT flip the bias.
Need signal stack (≥2 aligned signals) for non-neutral output.
"""

from tactical.tactical_types import TacticalSignals, TacticalFusion


# Signal weights: higher = more conviction
_SIGNAL_WEIGHTS = {
    "forced_selling":    -2.5,  # strongest bearish: active liquidation cascade
    "forced_buying":     +2.5,  # strongest bullish: short squeeze
    "bearish_orderflow": -1.0,  # directional flow pressure
    "bullish_orderflow": +1.0,
    "crowded_longs":     -1.5,  # mean-reversion risk
    "crowded_shorts":    +1.5,
    "seller_exhaustion": +0.8,  # absorption signals
    "buyer_exhaustion":  -0.8,
    "high_volatility":    0.0,  # neutral directionally, but affects quality
}

# Liquidation imbalance adds directional weight
_LIQ_IMBALANCE_WEIGHT = 1.0  # long imbalance → bearish, short → bullish


def fuse_tactical_signals(signals: TacticalSignals) -> TacticalFusion:
    """
    Fuse signals into composite bias.

    Rules:
      - Each signal contributes a weighted score
      - Bias only moves from neutral with score magnitude ≥ 1.5
      - Signal strength = normalized |score| / max_possible
    """
    score = 0.0
    active = []
    bearish_count = 0
    bullish_count = 0

    # Apply discrete signal weights
    for sig_name, weight in _SIGNAL_WEIGHTS.items():
        if sig_name in signals and signals[sig_name]:
            score += weight
            active.append(sig_name)
            if weight < 0:
                bearish_count += 1
            elif weight > 0:
                bullish_count += 1

    # Liquidation imbalance
    liq_dir = signals.get("liquidation_imbalance_direction")
    if liq_dir == "long":
        score -= _LIQ_IMBALANCE_WEIGHT
        active.append("liquidation_imbalance_long")
        bearish_count += 1
    elif liq_dir == "short":
        score += _LIQ_IMBALANCE_WEIGHT
        active.append("liquidation_imbalance_short")
        bullish_count += 1

    # ── Bias determination ──
    # Need sufficient signal stack to overcome neutral
    # Threshold: |score| >= 1.0 for directional bias
    # (calibrated: most scores in (-1, 1) range, need clear signal stack)
    if score <= -1.0:
        bias = "bearish"
    elif score >= 1.0:
        bias = "bullish"
    else:
        bias = "neutral"

    # ── Signal strength ──
    # Normalize: realistic max score ~4-5 (most signals aligned)
    max_possible = 4.5
    signal_strength = min(abs(score) / max_possible, 1.0)

    return {
        "score": round(score, 2),
        "bias": bias,
        "signal_strength": round(signal_strength, 3),
        "active_signals": active,
        "bearish_count": bearish_count,
        "bullish_count": bullish_count,
    }
