"""Macro V2 configuration — weights, thresholds, windows."""

# Rolling z-score window (daily points)
Z_WINDOW = 180
EPSILON = 1e-9

# Softmax temperature for regime probabilities
TEMP_SOFTMAX = 1.0

# CPI weights
CPI_WEIGHTS = {
    "btc_dom_7d": 0.35,
    "stable_dom_7d": 0.25,
    "btc_ret_7d": 0.20,
    "alt_vs_btc_7d": -0.20,
}

# Risk-Off probability weights
RISKOFF_WEIGHTS = {
    "stable_dom": 0.65,
    "fg_inv": 0.55,
    "vol": 0.35,
    "neg_btc_ret": 0.25,
}

# Macro confidence multiplier coefficients
MACRO_MULT_RISKOFF_COEFF = 0.55
MACRO_MULT_GREED_COEFF = 0.25
MACRO_MULT_FLOOR = 0.40
MACRO_MULT_CEILING = 1.05

# Regime score weights
REGIME_WEIGHTS = {
    "FLIGHT_TO_BTC": {
        "z_db7": 1.1, "z_rbtc7": 0.6, "riskoff": 0.8, "z_altvsbtc7": -0.5,
    },
    "ALT_ROTATION": {
        "z_db7": -1.0, "riskoff": -0.6, "z_altvsbtc7": 0.9, "z_ds7": -0.3,
    },
    "CAPITAL_EXIT": {
        "z_ds7": 1.2, "riskoff": 1.0, "z_rbtc7": -0.7,
    },
    "NEUTRAL": {
        "abs_cpi": -0.4,
    },
}

# Gating thresholds
STRONG_BLOCK_RISKOFF = 0.75
STRONG_BLOCK_EXTFEAR = 0.75
ALT_REDUCED_THRESHOLD = 0.65

# Cache TTL for macro data (seconds)
CACHE_TTL = 120

# Horizons (in daily index offsets)
HORIZON_7D = 7
