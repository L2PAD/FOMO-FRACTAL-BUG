"""
Structure Profiles
===================
Two depth profiles for multi-scale structure analysis.

Major: captures large structural moves (global trend context)
Minor: captures local swings (tactical impulse)

Key difference: min_move_pct filters out small swings in major,
keeping only significant structural pivots.
"""

STRUCTURE_PROFILES = {
    "major": {
        "lookback": 8,
        "min_move_pct": 1.6,
        "min_candles": 30,
        "label": "major",
    },
    "minor": {
        "lookback": 3,
        "min_move_pct": 0.7,
        "min_candles": 14,
        "label": "minor",
    },
}

# v4.1.3: Adaptive Major profiles
STRICT_MAJOR_PROFILE = {
    "lookback": 8,
    "min_move_pct": 1.6,
    "min_candles": 30,
    "label": "strict_major",
}

RELAXED_MAJOR_PROFILE = {
    "lookback": 6,
    "min_move_pct": 1.0,
    "min_candles": 24,
    "label": "relaxed_major",
}
