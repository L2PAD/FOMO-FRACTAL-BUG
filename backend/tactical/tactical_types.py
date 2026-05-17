"""
Tactical Types
================
Block X — Task X.1

Type definitions for the 1D Tactical Decision Layer.
This layer answers "how to act today", not "where price goes".
"""

from typing import Literal, TypedDict


TacticalBias = Literal["bullish", "neutral", "bearish"]
TradeQuality = Literal["high", "medium", "low"]
ExecutionAdvice = Literal["normal", "reduced", "avoid_aggressive", "wait"]
VolatilityExpectation = Literal["low", "moderate", "high", "extreme"]


# ── Raw signal flags ──
# Each signal is a discrete, explainable event — no ML.

SIGNAL_NAMES = [
    "bearish_orderflow",      # imbalance < -0.2, dominance > 0.6
    "bullish_orderflow",      # imbalance > 0.2, dominance > 0.6
    "forced_selling",         # cascade active, direction LONG
    "forced_buying",          # cascade active, direction SHORT (short squeeze)
    "crowded_longs",          # funding extreme bullish
    "crowded_shorts",         # funding extreme bearish
    "seller_exhaustion",      # absorption on ASK side
    "buyer_exhaustion",       # absorption on BID side
    "high_volatility",        # vol spike detected
    "liquidation_imbalance",  # strong long/short liq ratio
]


class TacticalSignals(TypedDict):
    """Raw signals extracted from microstructure data."""
    bearish_orderflow: bool
    bullish_orderflow: bool
    forced_selling: bool
    forced_buying: bool
    crowded_longs: bool
    crowded_shorts: bool
    seller_exhaustion: bool
    buyer_exhaustion: bool
    high_volatility: bool
    liquidation_imbalance_direction: str | None  # "long" or "short" or None


class TacticalFusion(TypedDict):
    """Fused tactical output."""
    score: float              # weighted composite (-5 to +5)
    bias: TacticalBias
    signal_strength: float    # 0-1, how strong the signal stack is
    active_signals: list[str]
    bearish_count: int
    bullish_count: int


class TacticalAdvice(TypedDict):
    """Final tactical decision payload."""
    tacticalBias: TacticalBias
    tradeQuality: TradeQuality
    executionAdvice: ExecutionAdvice
    volatilityExpectation: VolatilityExpectation
    reasonFlags: list[str]
    signalStrength: float
    fusionScore: float
    note: str


class MicrostructureSnapshot(TypedDict):
    """Input from exchange_observations."""
    # Order flow
    imbalance: float          # -1 to 1
    dominance: float          # 0 to 1
    aggressor_bias: str       # "NEUTRAL" / "BULL" / "BEAR"

    # Liquidations
    long_liq_volume: float
    short_liq_volume: float
    cascade_active: bool
    cascade_direction: str    # "LONG" / "SHORT"
    cascade_phase: str        # "START" / "PEAK" / "FADE"

    # Funding
    funding_score: float      # -1 to 1
    funding_trend: float
    funding_label: str        # "NEUTRAL" / "BULLISH_EXTREME" / "BEARISH_EXTREME"

    # Absorption
    absorption: bool
    absorption_side: str      # "ASK" / "BID"

    # Volume
    volume_delta: float
    oi_delta_pct: float

    # Context (from existing layers)
    uncertainty: float        # 0-1 from regime layer
    regime: str
    phase: str | None
