"""
Structure Intelligence V2 — Configuration
==========================================
All weights, caps, and horizon multipliers in one place.
Level 2 (Balanced) weights — recommended starting point.
"""

# ── Structure Feature Weights (Level 2 — Balanced) ──────
STRUCTURE_WEIGHTS = {
    "bias": 0.12,
    "trend": 0.08,
    "momentum": 0.10,
    "reversal_risk": 0.12,
    "exhaustion": 0.08,
    "stability": 0.05,
    "compression": 0.04,
}

# ── Structure Influence Limits ───────────────────────────
STRUCTURE_CONFIG = {
    "max_delta": 0.18,
    "horizon_multiplier": {
        "24H": 0.40,
        "7D": 1.00,
        "30D": 0.60,
    },
    "sign_flip_base_threshold": 0.25,
    "sign_flip_reversal_threshold": 0.70,
    "sign_flip_momentum_threshold": 0.45,
    "weak_base_threshold": 0.08,
    "weak_base_fallback_factor": 0.25,
}

# ── Swing Detection Parameters ───────────────────────────
SWING_CONFIG = {
    "lookback": 5,
    "min_candles": 14,
}
