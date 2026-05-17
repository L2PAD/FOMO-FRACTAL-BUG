from dataclasses import dataclass


@dataclass
class ProviderSignal:
    score: float          # -1..1
    confidence: float     # 0..1
    health: str           # OK / WARN / FAIL
    direction: str        # LONG / SHORT / NEUTRAL


@dataclass
class MetaFeatures:
    exchange_score: float
    exchange_conf: float

    sentiment_score: float
    sentiment_conf: float

    fractal_score: float
    fractal_conf: float

    onchain_score: float
    onchain_conf: float

    long_votes: int
    short_votes: int
    neutral_votes: int

    avg_confidence: float
    score_dispersion: float
    dominant_score: float
    agreement_ratio: float

    regime: str
    volatility: float

    # Real market features (dynamic)
    price_change_1d: float    # % change over 1 day
    price_change_7d: float    # % change over 7 days
    price_change_30d: float   # % change over 30 days
    sma20_distance: float     # (price - SMA20) / SMA20
    momentum_score: float     # composite momentum -1..1

