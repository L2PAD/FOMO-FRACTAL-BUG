"""
ML Overlay Types
==================
Block 5 — Task 5.1

Type definitions for the ML risk overlay.
ML Overlay does NOT replace core intelligence —
it predicts forecast error risk and applies soft adjustments.
"""

from typing import Literal, TypedDict


# ── Prediction Output ──

class OverlayPrediction(TypedDict):
    """ML risk estimation output."""
    error_risk: float           # 0..1 — probability forecast direction is wrong
    catastrophic_risk: float    # 0..1 — probability of large adverse move
    flags: list[str]            # human-readable risk flags


# ── Feature Vector ──

class OverlayFeatures(TypedDict):
    """Feature set for ML model. All features must be available at forecast time."""

    # ── Forecast meta ──
    horizon_days: int             # 1, 7, 30
    confidence: float             # model confidence 0..1
    confidence_raw: float         # raw confidence before adjustments
    expected_move_pct: float      # predicted move %
    direction_encoded: int        # LONG=1, NEUTRAL=0, SHORT=-1

    # ── Market snapshot (from exchange_observations) ──
    orderflow_imbalance: float    # -1..1
    orderflow_dominance: float    # 0..1
    aggressor_encoded: int        # BUY=1, NEUTRAL=0, SELL=-1
    cascade_active: int           # 0/1
    liq_long_volume: float
    liq_short_volume: float
    liq_ratio: float              # long/(long+short), 0.5 if no liq
    absorption_active: int        # 0/1
    absorption_side_encoded: int  # ASK=1, NONE=0, BID=-1

    # ── Funding context ──
    funding_score: float          # -1..1
    funding_trend: float

    # ── Volatility / OI ──
    volume_delta: float
    oi_delta_pct: float
    price_volatility: float       # from market.volatility

    # ── Regime (from obs) ──
    regime_encoded: int           # TREND=2, NEUTRAL=1, RANGE=0
    regime_confidence: float

    # ── Tactical signals (derived) ──
    tactical_score: float         # fusion score
    tactical_bias_encoded: int    # bullish=1, neutral=0, bearish=-1


# ── Adjustment Output ──

AdjustmentAction = Literal["none", "soft_penalty", "strong_penalty", "flag_only"]


class OverlayAdjustments(TypedDict):
    """Soft adjustments applied by ML overlay."""
    confidence_mult: float       # 0.7..1.0 multiplier on confidence
    size_factor_mult: float      # 0.7..1.0 multiplier on sizeFactor
    action: AdjustmentAction
    flags: list[str]             # warning flags for UI/logging


# ── Dataset Row ──

class DatasetRow(TypedDict):
    """Single training example."""
    forecast_id: str
    created_at: float             # timestamp ms
    horizon_days: int
    features: OverlayFeatures
    labels: dict                  # {error_risk: 0/1, catastrophic_risk: 0/1}
