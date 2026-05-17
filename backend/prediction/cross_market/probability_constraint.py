"""
Probability Constraint Engine — enforces logical probability constraints between related markets.

Constraint modes:
  SUBSET:     P(A) <= P(B) — harder condition must have lower probability
  MONOTONIC:  P(A_n+1) <= P(A_n) — prices decrease as thresholds increase
  EQUIVALENT: P(A) ≈ P(B) — equivalent markets should have similar probabilities
"""
import logging
from typing import Optional

logger = logging.getLogger("cross_market.probability_constraint")


def check_constraint(relation: dict) -> Optional[dict]:
    """Check if a relation satisfies its probability constraint.

    Returns violation dict if broken, None if satisfied.
    """
    price_a = relation.get("price_a")
    price_b = relation.get("price_b")
    rel_confidence = relation.get("confidence", 0)

    if price_a is None or price_b is None:
        return None

    # Guard: skip weak relations
    if rel_confidence < 0.6:
        return None

    mode = relation.get("relation", "SUBSET")

    if mode == "SUBSET":
        return _check_subset(relation, price_a, price_b)
    elif mode == "MONOTONIC":
        return _check_monotonic(relation, price_a, price_b)
    elif mode == "EQUIVALENT":
        return _check_equivalent(relation, price_a, price_b)

    return None


def _check_subset(rel: dict, price_a: float, price_b: float) -> Optional[dict]:
    """SUBSET: P(higher_threshold) <= P(lower_threshold).
    market_a = higher threshold (subset), market_b = lower threshold (superset).
    """
    if price_a <= price_b + 0.005:
        return None

    gap = round(price_a - price_b, 4)
    if gap < 0.01:  # Hard filter: gap >= 1%
        return None

    return {
        "mode": "SUBSET",
        "market_a": rel["market_a"],
        "market_b": rel["market_b"],
        "question_a": rel.get("question_a", ""),
        "question_b": rel.get("question_b", ""),
        "price_a": price_a,
        "price_b": price_b,
        "threshold_a": rel.get("threshold_a", 0),
        "threshold_b": rel.get("threshold_b", 0),
        "gap": gap,
        "gap_pct": round(gap * 100, 2),
        "expected": f"P(${rel.get('threshold_a', 0):,.0f}) <= P(${rel.get('threshold_b', 0):,.0f})",
        "actual": f"{price_a:.1%} > {price_b:.1%}",
        "severity": "HIGH" if gap > 0.03 else "MEDIUM",
        "relation_confidence": rel.get("confidence", 0),
        "volume_a": rel.get("volume_a", 0),
        "volume_b": rel.get("volume_b", 0),
        "spread_a": rel.get("spread_a"),
        "spread_b": rel.get("spread_b"),
    }


def _check_monotonic(rel: dict, price_a: float, price_b: float) -> Optional[dict]:
    """MONOTONIC: adjacent prices should decrease as thresholds increase.
    market_a = higher threshold, market_b = lower threshold.
    """
    if price_a <= price_b + 0.005:
        return None

    gap = round(price_a - price_b, 4)
    if gap < 0.01:
        return None

    return {
        "mode": "MONOTONIC",
        "market_a": rel["market_a"],
        "market_b": rel["market_b"],
        "question_a": rel.get("question_a", ""),
        "question_b": rel.get("question_b", ""),
        "price_a": price_a,
        "price_b": price_b,
        "threshold_a": rel.get("threshold_a", 0),
        "threshold_b": rel.get("threshold_b", 0),
        "gap": gap,
        "gap_pct": round(gap * 100, 2),
        "expected": f"P(${rel.get('threshold_a', 0):,.0f}) <= P(${rel.get('threshold_b', 0):,.0f})",
        "actual": f"{price_a:.1%} > {price_b:.1%}",
        "severity": "MEDIUM",
        "relation_confidence": rel.get("confidence", 0),
        "volume_a": rel.get("volume_a", 0),
        "volume_b": rel.get("volume_b", 0),
        "spread_a": rel.get("spread_a"),
        "spread_b": rel.get("spread_b"),
    }


def _check_equivalent(rel: dict, price_a: float, price_b: float) -> Optional[dict]:
    """EQUIVALENT: prices should be approximately equal."""
    diff = abs(price_a - price_b)
    if diff <= 0.02:
        return None

    if diff < 0.01:
        return None

    return {
        "mode": "EQUIVALENT",
        "market_a": rel["market_a"],
        "market_b": rel["market_b"],
        "question_a": rel.get("question_a", ""),
        "question_b": rel.get("question_b", ""),
        "price_a": price_a,
        "price_b": price_b,
        "threshold_a": rel.get("threshold_a", 0),
        "threshold_b": rel.get("threshold_b", 0),
        "gap": round(diff, 4),
        "gap_pct": round(diff * 100, 2),
        "expected": "P(A) ≈ P(B)",
        "actual": f"{price_a:.1%} vs {price_b:.1%}",
        "severity": "HIGH" if diff > 0.05 else "MEDIUM",
        "relation_confidence": rel.get("confidence", 0),
        "volume_a": rel.get("volume_a", 0),
        "volume_b": rel.get("volume_b", 0),
        "spread_a": rel.get("spread_a"),
        "spread_b": rel.get("spread_b"),
    }


def check_all_constraints(relations: list[dict]) -> list[dict]:
    """Check probability constraints for all relations.

    Returns list of constraint violations, filtered by hard thresholds.
    """
    violations = []

    for rel in relations:
        v = check_constraint(rel)
        if v is not None:
            violations.append(v)

    logger.info(f"[ProbConstraint] {len(relations)} relations → {len(violations)} constraint violations")
    return violations
