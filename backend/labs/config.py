"""
Labs config — indicator weights, thresholds, lab definitions.
Maps directly to exchange_observations (38 indicators + top-level fields).
"""

SOURCE_CONFIDENCE = {"obs": 1.0, "mixed": 0.9, "snapshot": 0.75}
FRESHNESS_THRESHOLDS = {"fresh": 120, "warm": 600, "stale": 900}
MAX_CONVICTION_IMPACT = 0.5

# Each indicator maps to a key in the extracted feature_map (see providers.py).
# weight: contribution to lab score. riskW/convW: risk/conviction contributions.

LABS_CONFIG = {
    # ─── Group A: Market Structure ───
    "regime": {
        "group": "Market Structure",
        "displayName": "Regime",
        "description": "Market phase — trending, ranging or transitioning.",
        "indicators": {
            "trend_slope":        {"weight": 0.30, "riskW": 0.05, "convW": 0.40},
            "range_compression":  {"weight": 0.25, "riskW": 0.10, "convW": 0.25},
            "dir_momentum":       {"weight": 0.25, "riskW": 0.15, "convW": 0.35},
            "ema_alignment":      {"weight": 0.20, "riskW": 0.05, "convW": 0.30},
        },
        "horizonW": {"short": 0.2, "mid": 0.4, "swing": 0.4},
        "stateRules": [
            {"state": "TRENDING", "condition": "trend_slope > 0.65"},
            {"state": "RANGING", "condition": "range_compression > 0.60"},
            {"state": "TRANSITION", "condition": "dir_momentum > 0.60"},
        ],
        "defaultState": "NEUTRAL",
    },

    "volatility": {
        "group": "Market Structure",
        "displayName": "Volatility",
        "description": "Amplitude of price movements.",
        "indicators": {
            "atr_normalized":     {"weight": 0.35, "riskW": 0.20, "convW": 0.10},
            "range_compression":  {"weight": 0.35, "riskW": 0.10, "convW": 0.30},
            "vwap_deviation":     {"weight": 0.30, "riskW": 0.15, "convW": 0.20},
        },
        "horizonW": {"short": 0.5, "mid": 0.3, "swing": 0.2},
        "stateRules": [
            {"state": "COMPRESSION", "condition": "range_compression > 0.65"},
            {"state": "HIGH", "condition": "atr_normalized > 0.70"},
        ],
        "defaultState": "NORMAL",
    },

    "liquidity": {
        "group": "Market Structure",
        "displayName": "Liquidity",
        "description": "Order book depth and execution quality.",
        "indicators": {
            "spread_pressure":    {"weight": 0.30, "riskW": 0.35, "convW": -0.20},
            "depth_density":      {"weight": 0.25, "riskW": 0.30, "convW": -0.15, "inverse": True},
            "liquidity_vacuum":   {"weight": 0.25, "riskW": 0.35, "convW": -0.10},
            "liquidity_walls":    {"weight": 0.20, "riskW": 0.20, "convW": -0.05},
        },
        "horizonW": {"short": 0.6, "mid": 0.3, "swing": 0.1},
        "stateRules": [
            {"state": "THIN", "condition": "_abnormality > 0.60"},
            {"state": "DEEP", "condition": "_abnormality < 0.25"},
        ],
        "defaultState": "NORMAL",
    },

    "market_stress": {
        "group": "Market Structure",
        "displayName": "Market Stress",
        "description": "Overall market pressure and stability.",
        "indicators": {
            "liq_pressure":       {"weight": 0.35, "riskW": 0.40, "convW": -0.20},
            "atr_normalized":     {"weight": 0.25, "riskW": 0.30, "convW": -0.15},
            "funding_pressure":   {"weight": 0.20, "riskW": 0.25, "convW": -0.10},
            "oi_delta":           {"weight": 0.20, "riskW": 0.25, "convW": -0.10},
        },
        "horizonW": {"short": 0.6, "mid": 0.3, "swing": 0.1},
        "stateRules": [
            {"state": "PANIC", "condition": "_abnormality > 0.80"},
            {"state": "STRESSED", "condition": "_abnormality > 0.55"},
        ],
        "defaultState": "STABLE",
    },

    # ─── Group B: Flow & Participation ───
    "flow": {
        "group": "Flow & Participation",
        "displayName": "Order Flow",
        "description": "Who is driving the market — buyers or sellers.",
        "indicators": {
            "of_imbalance":       {"weight": 0.40, "riskW": 0.10, "convW": 0.45},
            "aggressor_bias":     {"weight": 0.30, "riskW": 0.05, "convW": 0.35},
            "volume_delta":       {"weight": 0.30, "riskW": 0.05, "convW": 0.30},
        },
        "horizonW": {"short": 0.6, "mid": 0.3, "swing": 0.1},
        "stateRules": [
            {"state": "BUYERS", "condition": "of_imbalance > 0.60"},
            {"state": "SELLERS", "condition": "of_imbalance < 0.35"},
        ],
        "defaultState": "BALANCED",
    },

    "volume": {
        "group": "Flow & Participation",
        "displayName": "Volume",
        "description": "Trading activity level and volume confirmation.",
        "indicators": {
            "relative_volume":         {"weight": 0.40, "riskW": 0.10, "convW": 0.35},
            "volume_index":            {"weight": 0.35, "riskW": 0.05, "convW": 0.30},
            "volume_price_response":   {"weight": 0.25, "riskW": 0.05, "convW": 0.40},
        },
        "horizonW": {"short": 0.5, "mid": 0.3, "swing": 0.2},
        "stateRules": [
            {"state": "SPIKE", "condition": "relative_volume > 0.70"},
            {"state": "LOW", "condition": "volume_index < 0.30"},
        ],
        "defaultState": "NORMAL",
    },

    "momentum": {
        "group": "Flow & Participation",
        "displayName": "Momentum",
        "description": "Strength and direction of the current move.",
        "indicators": {
            "rsi_normalized":     {"weight": 0.35, "riskW": 0.10, "convW": 0.30},
            "dir_momentum":       {"weight": 0.35, "riskW": 0.05, "convW": 0.35},
            "macd_delta":         {"weight": 0.30, "riskW": 0.05, "convW": 0.30},
        },
        "horizonW": {"short": 0.4, "mid": 0.4, "swing": 0.2},
        "stateRules": [
            {"state": "STRONG_UP", "condition": "dir_momentum > 0.70"},
            {"state": "STRONG_DOWN", "condition": "dir_momentum < 0.25"},
        ],
        "defaultState": "NEUTRAL",
    },

    "participation": {
        "group": "Flow & Participation",
        "displayName": "Participation",
        "description": "How many participants support the move.",
        "indicators": {
            "participation_intensity": {"weight": 0.40, "riskW": 0.10, "convW": 0.25},
            "oi_delta":                {"weight": 0.30, "riskW": 0.10, "convW": 0.30},
            "oi_level":                {"weight": 0.30, "riskW": 0.05, "convW": 0.20},
        },
        "horizonW": {"short": 0.3, "mid": 0.4, "swing": 0.3},
        "stateRules": [
            {"state": "EXPANDING", "condition": "participation_intensity > 0.65"},
            {"state": "NARROWING", "condition": "participation_intensity < 0.30"},
        ],
        "defaultState": "MODERATE",
    },

    # ─── Group C: Smart Money & Risk ───
    "whale": {
        "group": "Smart Money & Risk",
        "displayName": "Whale Activity",
        "description": "Large player activity and positioning.",
        "indicators": {
            "large_position_presence": {"weight": 0.35, "riskW": 0.10, "convW": 0.30},
            "absorption_strength":     {"weight": 0.35, "riskW": 0.05, "convW": 0.35},
            "whale_side_bias":         {"weight": 0.30, "riskW": 0.10, "convW": 0.30},
        },
        "horizonW": {"short": 0.4, "mid": 0.4, "swing": 0.2},
        "stateRules": [
            {"state": "ACTIVE_LONG", "condition": "whale_side_bias > 0.65"},
            {"state": "ACTIVE_SHORT", "condition": "whale_side_bias < 0.30"},
        ],
        "defaultState": "QUIET",
    },

    "manipulation": {
        "group": "Smart Money & Risk",
        "displayName": "Manipulation Risk",
        "description": "Signs of manipulation — spoofing, stop hunts, walls.",
        "indicators": {
            "stop_hunt_probability":      {"weight": 0.40, "riskW": 0.45, "convW": -0.20},
            "liquidity_walls":            {"weight": 0.30, "riskW": 0.30, "convW": -0.15},
            "contrarian_pressure_index":  {"weight": 0.30, "riskW": 0.35, "convW": -0.15},
        },
        "horizonW": {"short": 0.6, "mid": 0.3, "swing": 0.1},
        "stateRules": [
            {"state": "HIGH_RISK", "condition": "_abnormality > 0.65"},
        ],
        "defaultState": "CLEAN",
    },

    "liquidation": {
        "group": "Smart Money & Risk",
        "displayName": "Liquidation Risk",
        "description": "Risk of cascading liquidations causing sharp moves.",
        "indicators": {
            "liq_pressure":        {"weight": 0.50, "riskW": 0.40, "convW": -0.25},
            "position_crowding":   {"weight": 0.30, "riskW": 0.30, "convW": -0.15},
            "long_short_ratio":    {"weight": 0.20, "riskW": 0.15, "convW": -0.10},
        },
        "horizonW": {"short": 0.6, "mid": 0.3, "swing": 0.1},
        "stateRules": [
            {"state": "CASCADE_RISK", "condition": "liq_pressure > 0.70"},
            {"state": "ELEVATED", "condition": "_abnormality > 0.50"},
        ],
        "defaultState": "NORMAL",
    },

    # ─── Group E: Meta / Quality ───
    "data_quality": {
        "group": "Meta / Quality",
        "displayName": "Data Quality",
        "description": "Is the input data reliable and fresh.",
        "indicators": {
            "coverage_ratio":     {"weight": 0.50, "riskW": 0.50, "convW": -0.30, "inverse": True},
            "freshness_inv":      {"weight": 0.50, "riskW": 0.50, "convW": -0.30, "inverse": True},
        },
        "horizonW": {"short": 0.4, "mid": 0.4, "swing": 0.2},
        "stateRules": [
            {"state": "DEGRADED", "condition": "coverage_ratio < 0.50"},
        ],
        "defaultState": "HEALTHY",
    },

    "signal_conflict": {
        "group": "Meta / Quality",
        "displayName": "Signal Conflict",
        "description": "Do indicators agree or contradict each other.",
        "indicators": {
            "signal_alignment":   {"weight": 1.0, "riskW": 0.20, "convW": 0.40, "inverse": True},
        },
        "horizonW": {"short": 0.3, "mid": 0.4, "swing": 0.3},
        "stateRules": [
            {"state": "CONFLICTED", "condition": "signal_alignment < 0.35"},
        ],
        "defaultState": "ALIGNED",
    },
}

# Ordered group display
GROUP_ORDER = [
    "Market Structure",
    "Flow & Participation",
    "Smart Money & Risk",
    "Meta / Quality",
]
