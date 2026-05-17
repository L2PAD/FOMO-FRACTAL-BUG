"""
Cross-Platform Constraints — checks probability constraints between Poly and Kalshi markets.

Only 2 modes:
  SUBSET:     P(stricter) <= P(looser)
  EQUIVALENT: |P(A) - P(B)| <= tolerance
"""
import logging

logger = logging.getLogger("cross_market.kalshi.constraints")

EQUIVALENT_TOLERANCE = 0.03


def check_subset(subset_prob: float, superset_prob: float, relation: dict) -> dict:
    """Check SUBSET constraint: stricter market should be priced <= looser market."""
    gap = subset_prob - superset_prob

    return {
        "violated": gap > 0,
        "gap": round(gap, 4) if gap > 0 else 0,
        "type": "SUBSET",
        "subset_platform": relation.get("subset_platform", ""),
        "superset_platform": relation.get("superset_platform", ""),
        "subset_prob": round(subset_prob, 4),
        "superset_prob": round(superset_prob, 4),
        "poly_market_id": relation.get("poly_market_id", ""),
        "kalshi_market_id": relation.get("kalshi_market_id", ""),
        "relation_confidence": relation.get("confidence", 0),
        "parser_confidence": relation.get("parser_confidence", 0),
        "explanation": relation.get("explanation", ""),
        "entity": relation.get("entity", ""),
        "cluster_id": relation.get("cluster_id", ""),
        "poly_threshold": relation.get("poly_threshold", 0),
        "kalshi_threshold": relation.get("kalshi_threshold", 0),
    }


def check_equivalent(prob_a: float, prob_b: float, relation: dict) -> dict:
    """Check EQUIVALENT constraint: prices should be approximately equal."""
    gap = abs(prob_a - prob_b)

    return {
        "violated": gap > EQUIVALENT_TOLERANCE,
        "gap": round(gap, 4),
        "type": "EQUIVALENT",
        "poly_prob": round(prob_a, 4),
        "kalshi_prob": round(prob_b, 4),
        "poly_market_id": relation.get("poly_market_id", ""),
        "kalshi_market_id": relation.get("kalshi_market_id", ""),
        "relation_confidence": relation.get("confidence", 0),
        "parser_confidence": relation.get("parser_confidence", 0),
        "explanation": relation.get("explanation", ""),
        "entity": relation.get("entity", ""),
        "cluster_id": relation.get("cluster_id", ""),
        "poly_threshold": relation.get("poly_threshold", 0),
        "kalshi_threshold": relation.get("kalshi_threshold", 0),
    }


def check_constraint(relation: dict) -> dict | None:
    """Check constraint for a cross-platform relation.

    Returns constraint result or None if no check possible.
    """
    rel_type = relation.get("relation", "")
    poly_price = relation.get("poly_price")
    kalshi_price = relation.get("kalshi_price")

    if poly_price is None or kalshi_price is None:
        return None

    if rel_type == "SUBSET":
        subset_platform = relation.get("subset_platform", "")
        if subset_platform == "kalshi":
            return check_subset(kalshi_price, poly_price, relation)
        else:
            return check_subset(poly_price, kalshi_price, relation)

    elif rel_type == "EQUIVALENT":
        return check_equivalent(poly_price, kalshi_price, relation)

    return None


def check_all_constraints(relations: list[dict]) -> list[dict]:
    """Check constraints for all relations. Returns only violations."""
    violations = []
    for rel in relations:
        result = check_constraint(rel)
        if result and result["violated"] and result["gap"] > 0:
            violations.append(result)

    logger.info(f"[CrossPlatformConstraints] {len(relations)} relations -> {len(violations)} violations")
    return violations
