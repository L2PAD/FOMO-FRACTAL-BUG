"""
Adaptive Major Extractor
==========================
Tries strict major profile first. If major is "silent" (insufficient swings
or zero directional bias), falls back to a relaxed major profile.

This ensures major almost always provides a directional signal,
enabling aligned mode in the pullback detector and unlocking alpha.
"""

from forecast.structure.extractor import StructureFeatureExtractor, EMPTY_FEATURES
from forecast.structure.structure_profiles import STRICT_MAJOR_PROFILE, RELAXED_MAJOR_PROFILE

_extractor = StructureFeatureExtractor()

# Validity thresholds: major must show SOME signal
_MIN_BIAS = 0.15
_MIN_TREND = 0.30


def extract_adaptive_major(prices_dict: dict) -> dict:
    """
    Extract major structure features with adaptive profile fallback.

    1. Try strict major (lookback=8, min_move_pct=1.6)
    2. If result is too weak (low bias AND low trend), fall back to relaxed
    3. Return features + metadata about which profile was used
    """
    if not prices_dict:
        return {
            "features": dict(EMPTY_FEATURES),
            "profile_used": "strict",
            "fallback_used": False,
        }

    # Step 1: Try strict major
    strict_features = _extractor.extract_from_prices(prices_dict, profile=STRICT_MAJOR_PROFILE)

    if _is_valid_major(strict_features):
        return {
            "features": strict_features,
            "profile_used": "strict",
            "fallback_used": False,
        }

    # Step 2: Strict was silent → try relaxed
    relaxed_features = _extractor.extract_from_prices(prices_dict, profile=RELAXED_MAJOR_PROFILE)

    return {
        "features": relaxed_features,
        "profile_used": "relaxed",
        "fallback_used": True,
    }


def _is_valid_major(features: dict) -> bool:
    """
    Major is valid if it has directional signal.
    Requires bias >= 0.15 OR trend >= 0.30.
    If the extractor couldn't find enough swings, all features are 0 → invalid.
    """
    bias = abs(features.get("structure_bias_score", 0.0))
    trend = features.get("structure_trend_score", 0.0)
    return bias >= _MIN_BIAS or trend >= _MIN_TREND
