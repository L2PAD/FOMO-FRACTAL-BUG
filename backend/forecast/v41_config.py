"""
Exchange Forecast v4.1 — Configuration & Constants
====================================================
Configurable thresholds, direction classification, suppression caps,
calibration tables. All values live here, not hardcoded in generator.

v4.1 Recovery: Restores directional usefulness by removing
over-suppression and introducing 5-state classification.
"""

import hashlib

# ── Direction Classifier (5-state) ──────────────────────
# Score is continuous [-1, 1]. These thresholds map it to semantic classes.

DEFAULT_MILD_THRESHOLD = 0.20
NEW_MILD_THRESHOLD = 0.12

DIRECTION_THRESHOLDS = {
    "strong_bull": 0.65,
    "mild_bull": DEFAULT_MILD_THRESHOLD,
    "mild_bear": -DEFAULT_MILD_THRESHOLD,
    "strong_bear": -0.65,
}

DIRECTION_CLASSES = ("STRONG_BULL", "MILD_BULL", "NEUTRAL", "MILD_BEAR", "STRONG_BEAR")

# Shadow threshold for A/B comparison (set to None to disable)
SHADOW_MILD_THRESHOLD = NEW_MILD_THRESHOLD

# ── Rollout config for new threshold ──
NEUTRAL_ROLLOUT_PCT = 10          # % of forecasts using new threshold (0-100)
NEUTRAL_ROLLOUT_SALT = "neutral_v2_sprint2"


def _in_rollout(asset: str, horizon: str) -> bool:
    """Deterministic hash-based rollout: returns True for NEUTRAL_ROLLOUT_PCT% of asset+horizon combos."""
    if NEUTRAL_ROLLOUT_PCT <= 0:
        return False
    if NEUTRAL_ROLLOUT_PCT >= 100:
        return True
    h = int(hashlib.sha256(f"{NEUTRAL_ROLLOUT_SALT}:{asset}:{horizon}".encode()).hexdigest()[:8], 16)
    return (h % 100) < NEUTRAL_ROLLOUT_PCT


def get_active_mild_threshold(asset: str = "", horizon: str = "") -> float:
    """Get the effective mild threshold for a given asset+horizon.
    Returns NEW_MILD_THRESHOLD for rollout cohort, DEFAULT otherwise."""
    if _in_rollout(asset, horizon):
        return NEW_MILD_THRESHOLD
    return DEFAULT_MILD_THRESHOLD


def classify_direction(score: float, mild_threshold: float = None) -> str:
    """Map continuous directional score to 5-state class.
    
    Args:
        score: Directional score [-1, 1]
        mild_threshold: Override mild bull/bear threshold (default: config value)
    """
    t_mild = mild_threshold if mild_threshold is not None else DIRECTION_THRESHOLDS["mild_bull"]
    if score >= DIRECTION_THRESHOLDS["strong_bull"]:
        return "STRONG_BULL"
    if score >= t_mild:
        return "MILD_BULL"
    if score <= DIRECTION_THRESHOLDS["strong_bear"]:
        return "STRONG_BEAR"
    if score <= -t_mild:
        return "MILD_BEAR"
    return "NEUTRAL"


def classify_direction_shadow(score: float) -> dict:
    """Classify with BOTH live and shadow thresholds for comparison."""
    live = classify_direction(score)
    shadow = classify_direction(score, SHADOW_MILD_THRESHOLD) if SHADOW_MILD_THRESHOLD else live
    return {
        "live_direction": live,
        "shadow_direction": shadow,
        "live_threshold": DIRECTION_THRESHOLDS["mild_bull"],
        "shadow_threshold": SHADOW_MILD_THRESHOLD,
        "differs": live != shadow,
    }


# ── Regime Shrinkage ────────────────────────────────────
# v4.0: TRANSITION=0.6 (too aggressive). v4.1: 0.82 floor.
REGIME_SHRINKAGE = {
    "TREND": 1.00,
    "RANGE": 0.85,
    "RISK_OFF": 0.80,
    "TRANSITION": 0.82,
}


# ── Suppression Caps ────────────────────────────────────
# Hard limits: no combination of penalties can exceed these reductions.
MAX_SCORE_REDUCTION = 0.25       # Score shrinks by at most 25%
MAX_MOVE_REDUCTION = 0.30        # Expected move shrinks by at most 30%
MAX_CONFIDENCE_REDUCTION = 0.35  # Confidence shrinks by at most 35%


# ── Soft Degradation (replaces forced-neutral throttle) ─
DEGRADATION_CONFIG = {
    # Meta-shrinkage: applied when rolling win rate < 25% over last N
    "meta_threshold": 0.25,
    "meta_min_samples": 3,
    "meta_score_factor": 0.90,     # score *= 0.90
    "meta_move_factor": 0.88,      # move *= 0.88
    "meta_confidence_factor": 0.88, # confidence *= 0.88

    # Heavy degradation: applied when win rate < 15% over last 5+
    "heavy_threshold": 0.15,
    "heavy_min_samples": 5,
    "heavy_score_factor": 0.85,
    "heavy_move_factor": 0.82,
    "heavy_confidence_factor": 0.84,
    # NOTE: direction is NEVER forced to NEUTRAL by degradation
}


# ── Confidence Calibration Bins (per horizon) ───────────
# Built from historical exchange_forecasts data.
# Maps raw confidence range → calibrated probability.
# MUST be monotonic. Updated periodically from audit data.

# Initial calibration — bootstrapped from 354 historical forecasts.
# Will be refined after v4.1 collects more data.
CALIBRATION_BINS = {
    "7D": {
        "direction": [
            # (raw_low, raw_high, calibrated_p_direction_correct)
            (0.00, 0.10, 0.45),
            (0.10, 0.20, 0.52),
            (0.20, 0.30, 0.58),
            (0.30, 0.40, 0.62),
            (0.40, 0.60, 0.65),
            (0.60, 1.00, 0.68),
        ],
        "target": [
            (0.00, 0.10, 0.20),
            (0.10, 0.20, 0.30),
            (0.20, 0.30, 0.37),
            (0.30, 0.40, 0.41),
            (0.40, 0.60, 0.44),
            (0.60, 1.00, 0.48),
        ],
    },
    "30D": {
        "direction": [
            (0.00, 0.10, 0.35),
            (0.10, 0.20, 0.38),
            (0.20, 0.30, 0.42),
            (0.30, 0.40, 0.46),
            (0.40, 0.60, 0.50),
            (0.60, 1.00, 0.55),
        ],
        "target": [
            (0.00, 0.10, 0.22),
            (0.10, 0.20, 0.28),
            (0.20, 0.30, 0.33),
            (0.30, 0.40, 0.36),
            (0.40, 0.60, 0.40),
            (0.60, 1.00, 0.44),
        ],
    },
    "24H": {
        "direction": [
            (0.00, 0.30, 0.40),
            (0.30, 0.60, 0.48),
            (0.60, 1.00, 0.55),
        ],
        "target": [
            (0.00, 0.30, 0.15),
            (0.30, 0.60, 0.25),
            (0.60, 1.00, 0.35),
        ],
    },
}


def calibrate_confidence(raw: float, horizon: str, kind: str = "direction") -> float:
    """
    Look up calibrated confidence from bins.
    kind: 'direction' or 'target'
    """
    bins = CALIBRATION_BINS.get(horizon, {}).get(kind)
    if not bins:
        return max(0.10, min(0.85, raw))
    for low, high, cal in bins:
        if low <= raw < high:
            return cal
    # Above last bin
    return bins[-1][2]


# ── Blended Baseline Config ─────────────────────────────
BASELINE_BLEND = {
    "recent_weight": 0.65,
    "long_weight": 0.35,
    "recent_window_days": 60,
    "fallback_window_days": 90,
    "min_recent_samples": 20,
}
