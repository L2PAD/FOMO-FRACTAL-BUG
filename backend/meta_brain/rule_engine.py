from __future__ import annotations
from dataclasses import asdict
from .contracts import MetaFeatures


def meta_rule_decision(f: MetaFeatures) -> dict:
    # Provider component (30% weight)
    provider_score = (
        0.40 * f.exchange_score
        + 0.20 * f.sentiment_score
        + 0.15 * f.fractal_score
        + 0.15 * f.onchain_score
        + 0.10 * (f.long_votes - f.short_votes) / 4.0
    )

    # Market momentum component (50% weight) — REAL price dynamics
    market_score = (
        0.60 * f.momentum_score
        + 0.40 * _clamp(f.sma20_distance / 0.05, -1, 1)
    )

    # Composite score: market-driven with provider confirmation
    score = 0.30 * provider_score + 0.50 * market_score + 0.20 * _vol_signal(f.volatility)

    # agreement boost (only when directional providers agree)
    if f.agreement_ratio >= 0.75 and f.neutral_votes < 3:
        score *= 1.20

    # regime discipline
    if f.regime == "TREND_DOWN" and score > 0:
        score *= 0.80
    elif f.regime == "TREND_UP" and score < 0:
        score *= 0.80

    # volatility damping for extreme vol
    if f.volatility > 0.10:
        score *= 0.85

    # TUNING 1: anti-fake signal in flat market
    if f.volatility < 0.01:
        score *= 0.7

    # dynamic threshold
    directional_votes = f.long_votes + f.short_votes
    if directional_votes >= 3:
        threshold = 0.08
    elif directional_votes >= 2:
        threshold = 0.12
    elif directional_votes == 1:
        threshold = 0.15
    else:
        threshold = 0.20

    if score >= threshold:
        direction = "LONG"
    elif score <= -threshold:
        direction = "SHORT"
    else:
        direction = "NEUTRAL"

    # TUNING 4: weak signal kill (raised from 0.015)
    if abs(score) < 0.03:
        direction = "NEUTRAL"

    confidence = (
        0.25 * min(1.0, abs(score) * 5)
        + 0.25 * f.avg_confidence
        + 0.20 * f.agreement_ratio
        + 0.15 * min(1.0, abs(f.dominant_score))
        + 0.15 * min(1.0, abs(f.momentum_score))
    )
    confidence = max(0.2, min(0.9, confidence))

    # TUNING 2: momentum confirmation — penalize counter-trend
    if direction == "LONG" and f.momentum_score < 0:
        confidence *= 0.6
    if direction == "SHORT" and f.momentum_score > 0:
        confidence *= 0.6

    # TUNING 3: strong signal boost
    if abs(score) > 0.10 and f.agreement_ratio >= 0.75:
        confidence += 0.05
        confidence = min(0.9, confidence)

    return {
        "direction": direction,
        "score": round(score, 4),
        "confidence": round(confidence, 4),
        "threshold": round(threshold, 4),
        "features": asdict(f),
    }


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _vol_signal(vol: float) -> float:
    """High volatility → slightly bearish bias (risk-off)."""
    if vol > 0.08:
        return -0.1
    if vol < 0.03:
        return 0.05
    return 0.0
