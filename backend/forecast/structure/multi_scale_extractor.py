"""
Multi-Scale Structure Extractor
================================
Runs structure feature extraction at two scales:
  - Major: Adaptive (strict → relaxed fallback) for global trend context
  - Minor: Fixed profile for local tactical impulse

Returns both feature sets + metadata about major profile selection.
"""

from forecast.structure.extractor import StructureFeatureExtractor, EMPTY_FEATURES
from forecast.structure.structure_profiles import STRUCTURE_PROFILES
from forecast.structure.adaptive_major_extractor import extract_adaptive_major

_extractor = StructureFeatureExtractor()

EMPTY_MULTISCALE = {
    "major": dict(EMPTY_FEATURES),
    "minor": dict(EMPTY_FEATURES),
    "major_profile_used": "strict",
    "major_fallback_used": False,
}


def extract_multiscale(prices_dict: dict) -> dict:
    """
    Extract structure features at two scales using adaptive major.

    Returns dict with:
      - major: features from adaptive major (strict or relaxed)
      - minor: features from fixed minor profile
      - major_profile_used: "strict" or "relaxed"
      - major_fallback_used: bool
    """
    if not prices_dict:
        return dict(EMPTY_MULTISCALE)

    try:
        # Major: adaptive extraction (strict → relaxed fallback)
        major_result = extract_adaptive_major(prices_dict)
        major_features = major_result["features"]

        # Minor: fixed profile
        minor_profile = STRUCTURE_PROFILES["minor"]
        minor_features = _extractor.extract_from_prices(prices_dict, profile=minor_profile)

        return {
            "major": major_features,
            "minor": minor_features,
            "major_profile_used": major_result["profile_used"],
            "major_fallback_used": major_result["fallback_used"],
        }
    except Exception:
        return dict(EMPTY_MULTISCALE)
