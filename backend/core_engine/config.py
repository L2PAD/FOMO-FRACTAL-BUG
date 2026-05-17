"""
Core Engine V2 — Configuration.
Weights, thresholds, transition matrix, temperature.
"""

# Softmax temperature for regime probabilities
# Lower = more decisive, higher = more uniform
REGIME_TEMPERATURE = 0.8

# ── Regime candidate score weights ──
REGIME_WEIGHTS = {
    "range": {
        "compression": 0.30,
        "momentum_low": 0.25,
        "flow_low": 0.25,
        "participation_low": 0.20,
    },
    "trend": {
        "momentum_strong": 0.35,
        "flow_strong": 0.30,
        "participation_expanding": 0.20,
        "conflict_low": 0.15,
    },
    "breakout": {
        "compression": 0.25,
        "liquidity_thin": 0.20,
        "divergence": 0.20,
        "momentum_building": 0.20,
        "manipulation_low": 0.15,
    },
    "distribution": {
        "manipulation_high": 0.30,
        "sellers_dominant": 0.25,
        "liquidation_rising": 0.25,
        "conflict_partial": 0.20,
    },
}

# ── Risk surface weights ──
RISK_WEIGHTS = {
    "liquidity": 0.25,
    "stress": 0.20,
    "manipulation": 0.20,
    "structure": 0.20,
    "conflict": 0.15,
}

# Risk thresholds
RISK_LOW = 35
RISK_HIGH = 70

# ── Factor decomposition weights ──
# These define how factors are computed from lab data
FACTOR_WEIGHTS = {
    "structure": {
        "regime_abn": 0.30,
        "compression": 0.25,
        "momentum_abn": 0.25,
        "participation_abn": 0.20,
    },
    "flow": {
        "flow_abn": 0.35,
        "flow_conv_abs": 0.35,
        "volume_abn": 0.30,
    },
    "liquidity": {
        "liquidity_risk_inv": 0.50,
        "liquidity_abn_inv": 0.30,
        "stress_risk_inv": 0.20,
    },
    "smartMoney": {
        "whale_abn": 0.45,
        "whale_conv_abs": 0.30,
        "liquidation_risk_inv": 0.25,
    },
    "stability": {
        "stress_abn_inv": 0.35,
        "conflict_abn_inv": 0.35,
        "data_quality": 0.30,
    },
}

# ── Pressure weights ──
PRESSURE_UP_WEIGHTS = {
    "flow_positive": 0.40,
    "momentum_positive": 0.30,
    "whale_accumulation": 0.20,
    "liquidity_health": 0.10,
}

PRESSURE_DOWN_WEIGHTS = {
    "flow_negative": 0.40,
    "momentum_negative": 0.30,
    "liquidation_risk": 0.20,
    "stress": 0.10,
}

# Bias thresholds
BIAS_STRONG = 0.15
BIAS_SLIGHT = 0.05

# ── Transition engine weights ──
# ── Transition engine weights ──
# NEW: instability = entropy, shift = instability + risk + trigger
SHIFT_FORMULA = {
    "instability_weight": 0.45,
    "risk_weight": 0.35,
    "trigger_weight": 0.20,
}

# Transition trigger components
TRIGGER_WEIGHTS = {
    "vol_expansion": 0.30,
    "compression": 0.25,
    "divergence": 0.25,
    "liquidity_thin": 0.20,
}

# ── Transition matrix (from → to conditions) ──
TRANSITION_MATRIX = {
    "range_to_breakout": {"compression": 0.35, "liquidity_thin": 0.30, "divergence": 0.35},
    "range_to_trend": {"participation": 0.40, "momentum_strong": 0.35, "flow_strong": 0.25},
    "range_to_distribution": {"manipulation": 0.40, "stress": 0.30, "conflict": 0.30},
    "breakout_to_range": {"momentum_fade": 0.40, "volume_drop": 0.30, "flow_fade": 0.30},
    "breakout_to_distribution": {"manipulation": 0.45, "liquidation": 0.30, "conflict": 0.25},
    "breakout_to_trend": {"momentum_strong": 0.40, "flow_strong": 0.35, "participation": 0.25},
    "trend_to_range": {"momentum_fade": 0.35, "flow_fade": 0.35, "compression": 0.30},
    "trend_to_distribution": {"liquidation": 0.35, "sellers": 0.35, "conflict": 0.30},
    "distribution_to_range": {"stress_low": 0.40, "conflict_low": 0.30, "manipulation_low": 0.30},
    "distribution_to_breakout": {"compression": 0.40, "divergence": 0.30, "liquidity_thin": 0.30},
}

# ── Execution controls ──
EXECUTION_CONFIG = {
    "aggression_risk_sensitivity": 1.0,
    "leverage_liquidity_weight": 0.7,
    "leverage_vol_weight": 0.3,
    "signal_amp_stability_weight": 0.5,
    "signal_amp_risk_weight": 0.6,
    "signal_amp_base": 0.5,
}

# ── Integrity penalty config ──
INTEGRITY_CONFIG = {
    "freshness_thresholds": [
        (60, 1.0),
        (180, 0.8),
        (600, 0.6),
    ],
    "freshness_fallback": 0.4,
    "coverage_required": 8,
    "data_quality_map": {
        "healthy": 1.0,
        "partial": 0.7,
        "degraded": 0.5,
        "critical": 0.3,
    },
    "venue_consistency_map": {
        "ok": 1.0,
        "conflict": 0.6,
        "extreme": 0.4,
    },
}

# ── Macro multiplier config ──
MACRO_CONFIG = {
    "fear_greed_extreme_fear": 20,
    "fear_greed_extreme_greed": 80,
    "confidence_floor": 0.5,
    "confidence_ceiling": 1.2,
}

# ── Cache ──
CACHE_TTL = 45

# ── Timeframes ──
VALID_TIMEFRAMES = ["30m", "1h", "4h", "1d", "1w"]
DEFAULT_TIMEFRAME = "1h"

# ── TF-dependent scaling profiles ──
# Each TF adjusts how Core Engine interprets the same raw data
# temperature: softmax sharpness (lower = more decisive regime)
# risk_damping: multiplier on risk (higher TF = smoother)
# shift_scale: multiplier on shift probability (lower TF = more volatile)
# noise_floor: minimum instability added (lower TF = noisier)
# bias_damping: bias signal dampening (higher TF = smoother)
TF_PROFILES = {
    "30m": {
        "temperature": 1.2,
        "risk_damping": 1.15,
        "shift_scale": 1.3,
        "noise_floor": 0.08,
        "bias_damping": 0.85,
        "label": "Fast, higher noise",
    },
    "1h": {
        "temperature": 0.8,
        "risk_damping": 1.0,
        "shift_scale": 1.0,
        "noise_floor": 0.0,
        "bias_damping": 1.0,
        "label": "Baseline",
    },
    "4h": {
        "temperature": 0.55,
        "risk_damping": 0.85,
        "shift_scale": 0.75,
        "noise_floor": 0.0,
        "bias_damping": 1.1,
        "label": "Swing",
    },
    "1d": {
        "temperature": 0.4,
        "risk_damping": 0.7,
        "shift_scale": 0.55,
        "noise_floor": 0.0,
        "bias_damping": 1.2,
        "label": "Structural",
    },
    "1w": {
        "temperature": 0.3,
        "risk_damping": 0.55,
        "shift_scale": 0.4,
        "noise_floor": 0.0,
        "bias_damping": 1.3,
        "label": "Macro context",
    },
}

# ── Regime confidence labels ──
CONFIDENCE_HIGH = 0.35
CONFIDENCE_MODERATE = 0.28

# ── Blocked gates thresholds ──
GATE_DQ_MIN = 0.4
GATE_LIQUIDITY_MAX = 70
GATE_MANIPULATION_MAX = 75
