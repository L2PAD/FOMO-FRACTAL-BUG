"""
Edge Case Classifier — categorizes cross-platform mispricings by type.

Called INSIDE mispricing pipeline (not separately).

Types:
  SOFT_HARD_TRIGGER, THRESHOLD_EQUIVALENT, APPROVAL_CHAIN,
  LISTING_STAGE, TIME_WINDOW_MISMATCH, LADDER_SHAPE_MISMATCH,
  NARRATIVE_DIVERGENCE, UNKNOWN
"""
import logging

logger = logging.getLogger("cross_market.kalshi.edge_classifier")

EDGE_CASE_TYPES = [
    "SOFT_HARD_TRIGGER",
    "THRESHOLD_EQUIVALENT",
    "APPROVAL_CHAIN",
    "LISTING_STAGE",
    "TIME_WINDOW_MISMATCH",
    "LADDER_SHAPE_MISMATCH",
    "NARRATIVE_DIVERGENCE",
    "UNKNOWN",
]

# Score multipliers per edge case type
EDGE_MULTIPLIER = {
    "SOFT_HARD_TRIGGER": 1.20,
    "THRESHOLD_EQUIVALENT": 1.15,
    "APPROVAL_CHAIN": 1.10,
    "LISTING_STAGE": 1.05,
    "TIME_WINDOW_MISMATCH": 1.00,
    "LADDER_SHAPE_MISMATCH": 1.00,
    "NARRATIVE_DIVERGENCE": 0.90,
    "UNKNOWN": 0.80,
}

# Strictness ordering for trigger detection
STRICTNESS_ORDER = [
    "INTENT_ANNOUNCED",
    "FORMAL_PROCESS",
    "APPROVAL",
    "SIGNED_DEAL",
    "BUYER_NAMED",
    "CONTROL_TRANSFER",
]


def classify_edge_case(
    constraint: dict,
    poly_parsed: dict | None = None,
    kalshi_parsed: dict | None = None,
) -> str:
    """Classify the edge case type for a constraint violation."""
    poly_prims = set((poly_parsed or {}).get("primitives", []))
    kalshi_prims = set((kalshi_parsed or {}).get("primitives", []))
    constraint_type = constraint.get("type", "")

    # 1. SOFT_HARD_TRIGGER: one side has softer trigger than the other
    soft_triggers = {"INTENT_ANNOUNCED", "FORMAL_PROCESS"}
    hard_triggers = {"SIGNED_DEAL", "BUYER_NAMED", "CONTROL_TRANSFER", "APPROVAL"}

    poly_has_soft = bool(poly_prims & soft_triggers)
    poly_has_hard = bool(poly_prims & hard_triggers)
    kalshi_has_soft = bool(kalshi_prims & soft_triggers)
    kalshi_has_hard = bool(kalshi_prims & hard_triggers)

    if (poly_has_soft and kalshi_has_hard) or (kalshi_has_soft and poly_has_hard):
        return "SOFT_HARD_TRIGGER"

    # 2. THRESHOLD_EQUIVALENT: same/very close price threshold on both platforms
    both_price = "PRICE_THRESHOLD" in poly_prims and "PRICE_THRESHOLD" in kalshi_prims
    if both_price:
        poly_t = constraint.get("poly_threshold", 0)
        kalshi_t = constraint.get("kalshi_threshold", 0)
        if poly_t > 0 and kalshi_t > 0:
            tolerance = 0.03 * max(poly_t, kalshi_t)
            if abs(poly_t - kalshi_t) < tolerance:
                return "THRESHOLD_EQUIVALENT"

    # 3. APPROVAL_CHAIN: approval stages differ
    approval_prims = {"APPROVAL", "FORMAL_PROCESS"}
    if (poly_prims & approval_prims) or (kalshi_prims & approval_prims):
        if poly_prims != kalshi_prims:
            return "APPROVAL_CHAIN"

    # 4. LISTING_STAGE: listing/trading stages
    listing_prims = {"LISTING"}
    if (poly_prims & listing_prims) or (kalshi_prims & listing_prims):
        return "LISTING_STAGE"

    # 5. LADDER_SHAPE_MISMATCH: threshold-based with different thresholds (before TIME check)
    if both_price:
        return "LADDER_SHAPE_MISMATCH"

    # 6. TIME_WINDOW_MISMATCH: different time buckets
    poly_time = (poly_parsed or {}).get("time_bucket")
    kalshi_time = (kalshi_parsed or {}).get("time_bucket")
    if poly_time and kalshi_time and poly_time != kalshi_time:
        return "TIME_WINDOW_MISMATCH"

    # 7. NARRATIVE_DIVERGENCE: large gap with no structural reason
    gap = constraint.get("gap", 0)
    if gap > 0.05 and constraint_type == "EQUIVALENT":
        return "NARRATIVE_DIVERGENCE"

    return "UNKNOWN"


def get_multiplier(edge_case_type: str) -> float:
    """Get score multiplier for edge case type."""
    return EDGE_MULTIPLIER.get(edge_case_type, 0.8)
