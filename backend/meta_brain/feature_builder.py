from __future__ import annotations
from .contracts import ProviderSignal, MetaFeatures


def sign_to_vote(direction: str) -> tuple:
    if direction == "LONG":
        return 1, 0, 0
    if direction == "SHORT":
        return 0, 1, 0
    return 0, 0, 1


def build_meta_features(
    exchange: ProviderSignal,
    sentiment: ProviderSignal,
    fractal: ProviderSignal,
    onchain: ProviderSignal,
    regime: str,
    volatility: float,
    price_change_1d: float = 0.0,
    price_change_7d: float = 0.0,
    price_change_30d: float = 0.0,
    sma20_distance: float = 0.0,
) -> MetaFeatures:
    providers = [exchange, sentiment, fractal, onchain]
    scores = [p.score for p in providers]
    confs = [p.confidence for p in providers]

    long_votes = short_votes = neutral_votes = 0
    for p in providers:
        lv, sv, nv = sign_to_vote(p.direction)
        long_votes += lv
        short_votes += sv
        neutral_votes += nv

    avg_conf = sum(confs) / len(confs)
    dominant_score = max(scores, key=lambda x: abs(x))
    dispersion = max(scores) - min(scores)

    agreement_ratio = max(long_votes, short_votes, neutral_votes) / 4.0

    # Composite momentum from price changes (-1 to 1)
    momentum_score = (
        0.50 * _clamp(price_change_1d / 3.0, -1, 1)
        + 0.30 * _clamp(price_change_7d / 8.0, -1, 1)
        + 0.20 * _clamp(price_change_30d / 15.0, -1, 1)
    )

    return MetaFeatures(
        exchange_score=exchange.score,
        exchange_conf=exchange.confidence,
        sentiment_score=sentiment.score,
        sentiment_conf=sentiment.confidence,
        fractal_score=fractal.score,
        fractal_conf=fractal.confidence,
        onchain_score=onchain.score,
        onchain_conf=onchain.confidence,
        long_votes=long_votes,
        short_votes=short_votes,
        neutral_votes=neutral_votes,
        avg_confidence=avg_conf,
        score_dispersion=dispersion,
        dominant_score=dominant_score,
        agreement_ratio=agreement_ratio,
        regime=regime,
        volatility=volatility,
        price_change_1d=price_change_1d,
        price_change_7d=price_change_7d,
        price_change_30d=price_change_30d,
        sma20_distance=sma20_distance,
        momentum_score=momentum_score,
    )


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))
