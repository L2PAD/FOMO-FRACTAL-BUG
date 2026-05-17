"""
Context Audit Builder
======================
Formats context data for the forecast audit payload.
"""


def build_context_audit(ctx_features: dict, phase: dict, adjustments: dict) -> dict:
    """Build the market_context section for the forecast audit."""
    return {
        "market_context": ctx_features,
        "context_phase": {
            "market_phase": phase["market_phase"],
            "context_confidence": phase["context_confidence"],
            "flags": phase["flags"],
        },
        "context_adjustments": adjustments.get("adjustments", {}),
    }
