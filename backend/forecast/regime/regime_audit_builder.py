"""
Regime Audit Builder
=====================
Formats regime engine output for the forecast audit payload.
"""


def build_regime_audit(features: dict, regime: dict, adjustments: dict) -> dict:
    """Build audit payload for the regime engine."""
    return {
        "regime_v2": {
            "features": features,
            "probabilities": regime.get("probabilities", {}),
            "dominant_regime": regime.get("dominant_regime"),
            "regime_confidence": regime.get("regime_confidence"),
            "regime_entropy": regime.get("regime_entropy"),
            "flags": regime.get("flags", []),
        },
        "regime_adjustments": adjustments.get("adjustments", {}),
    }
