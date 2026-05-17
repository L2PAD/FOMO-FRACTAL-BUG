"""
Mispricing Score Engine — calculates weighted mispricing scores for constraint violations.

Phase 2 Score formula:
  score = gap * 0.50 + confidence * 0.20 + liquidity_score * 0.15 + time_factor * 0.15

Phase 2.5 Actionability formula:
  actionability_score = score * 0.40 + liquidity_score * 0.30 + execution_feasibility * 0.20 + time_factor * 0.10

Severity (by actionability_score):
  >= 0.75 → STRONG
  >= 0.65 → HIGH
  >= 0.55 → MEDIUM
  <  0.55 → HIDDEN (filtered out)

Hard filters:
  - gap >= 0.01 (1%)
  - volume >= 10000
  - relation_confidence >= 0.6
"""
import time
import logging
from typing import Optional

logger = logging.getLogger("cross_market.mispricing")

# Mispricing Score Weights
W_GAP = 0.50
W_CONFIDENCE = 0.20
W_LIQUIDITY = 0.15
W_TIME = 0.15

# Actionability Weights
AW_SCORE = 0.40
AW_LIQUIDITY = 0.30
AW_EXECUTION = 0.20
AW_TIME = 0.10

# Hard filters
MIN_GAP = 0.01
MIN_VOLUME = 10000
MIN_RELATION_CONFIDENCE = 0.6

# Actionability thresholds
ACTIONABILITY_STRONG = 0.75
ACTIONABILITY_HIGH = 0.65
ACTIONABILITY_MEDIUM = 0.55


def _normalize_liquidity(volume_a: float, volume_b: float) -> float:
    """Normalize liquidity into 0-1 score."""
    min_vol = min(volume_a, volume_b)
    if min_vol >= 100000:
        return 1.0
    elif min_vol >= 25000:
        return 0.8
    elif min_vol >= 10000:
        return 0.6
    else:
        return 0.3


def _normalize_time(expiry_ts: Optional[float]) -> float:
    """Normalize time-to-expiry into 0-1 factor."""
    if expiry_ts is None or expiry_ts <= 0:
        return 0.6

    now_ms = time.time() * 1000
    time_to_expiry_ms = expiry_ts - now_ms

    if time_to_expiry_ms <= 0:
        return 0.3
    elif time_to_expiry_ms < 24 * 60 * 60 * 1000:
        return 1.0
    elif time_to_expiry_ms < 3 * 24 * 60 * 60 * 1000:
        return 0.8
    elif time_to_expiry_ms < 7 * 24 * 60 * 60 * 1000:
        return 0.6
    else:
        return 0.4


def _normalize_execution(spread_a: Optional[float], spread_b: Optional[float]) -> float:
    """Normalize execution feasibility based on spread.

    Lower spread = better execution.
    """
    spreads = [s for s in [spread_a, spread_b] if s is not None and s > 0]
    if not spreads:
        return 0.7  # Unknown spread — default mid

    max_spread = max(spreads)
    if max_spread <= 0.02:
        return 1.0
    elif max_spread <= 0.05:
        return 0.7
    else:
        return 0.4


def _compute_actionability_severity(actionability: float) -> str:
    """Map actionability_score to severity label."""
    if actionability >= ACTIONABILITY_STRONG:
        return "STRONG"
    elif actionability >= ACTIONABILITY_HIGH:
        return "HIGH"
    elif actionability >= ACTIONABILITY_MEDIUM:
        return "MEDIUM"
    return "HIDDEN"


def score_mispricing(
    constraint_violation: dict,
    expiry_ts: Optional[float] = None,
) -> Optional[dict]:
    """Calculate mispricing score + actionability score.

    Returns scored violation dict or None if filtered out.
    """
    gap = constraint_violation.get("gap", 0)
    relation_confidence = constraint_violation.get("relation_confidence", 0)
    volume_a = constraint_violation.get("volume_a", 0) or 0
    volume_b = constraint_violation.get("volume_b", 0) or 0
    spread_a = constraint_violation.get("spread_a")
    spread_b = constraint_violation.get("spread_b")

    # Hard filter: relation confidence
    if relation_confidence < MIN_RELATION_CONFIDENCE:
        return None

    # Hard filter: gap
    if gap < MIN_GAP:
        return None

    # Hard filter: volume
    if min(volume_a, volume_b) < MIN_VOLUME:
        return None

    # Normalizations
    liquidity_score = _normalize_liquidity(volume_a, volume_b)
    time_factor = _normalize_time(expiry_ts)
    execution_feasibility = _normalize_execution(spread_a, spread_b)

    # Composite mispricing score
    score = round(min(
        gap * W_GAP
        + relation_confidence * W_CONFIDENCE
        + liquidity_score * W_LIQUIDITY
        + time_factor * W_TIME,
        1.0
    ), 4)

    # Actionability score (Phase 2.5)
    actionability_score = round(min(
        score * AW_SCORE
        + liquidity_score * AW_LIQUIDITY
        + execution_feasibility * AW_EXECUTION
        + time_factor * AW_TIME,
        1.0
    ), 4)

    # Severity based on actionability
    severity = _compute_actionability_severity(actionability_score)

    # Hard filter: don't show HIDDEN signals
    if severity == "HIDDEN":
        return None

    return {
        **constraint_violation,
        "mispricing_score": score,
        "actionability_score": actionability_score,
        "actionability_severity": severity,
        "components": {
            "gap": round(gap, 4),
            "gap_weight": W_GAP,
            "confidence": round(relation_confidence, 4),
            "confidence_weight": W_CONFIDENCE,
            "liquidity_score": round(liquidity_score, 4),
            "liquidity_weight": W_LIQUIDITY,
            "time_factor": round(time_factor, 4),
            "time_weight": W_TIME,
            "execution_feasibility": round(execution_feasibility, 4),
            "execution_weight": AW_EXECUTION,
        },
        "actionability_breakdown": {
            "score_component": round(score * AW_SCORE, 4),
            "liquidity_component": round(liquidity_score * AW_LIQUIDITY, 4),
            "execution_component": round(execution_feasibility * AW_EXECUTION, 4),
            "time_component": round(time_factor * AW_TIME, 4),
        },
        "volume_a": volume_a,
        "volume_b": volume_b,
    }


def score_all_mispricings(
    constraint_violations: list[dict],
    expiry_map: Optional[dict] = None,
) -> list[dict]:
    """Score all constraint violations, filter by actionability.

    Returns list sorted by actionability_score desc.
    """
    expiry_map = expiry_map or {}
    scored = []

    for cv in constraint_violations:
        market_a = cv.get("market_a", "")
        market_b = cv.get("market_b", "")
        expiry_ts = expiry_map.get(market_a) or expiry_map.get(market_b)

        result = score_mispricing(cv, expiry_ts)
        if result is not None:
            scored.append(result)

    scored.sort(key=lambda x: x["actionability_score"], reverse=True)

    logger.info(
        f"[Mispricing] {len(constraint_violations)} violations → "
        f"{len(scored)} actionable mispricings"
    )
    return scored
