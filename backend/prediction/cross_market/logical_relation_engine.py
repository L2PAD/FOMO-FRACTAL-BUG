"""
Logical Relation Engine — infers logical relations between markets in a cluster.

Relation modes:
  SUBSET        — A ⊂ B: if A resolves YES, B must also resolve YES
                  e.g., BTC>70k ⊂ BTC>60k (if 70k hit, 60k is certainly hit)
  MONOTONIC     — prices should decrease monotonically as thresholds increase
  EQUIVALENT    — two markets are logically equivalent (same resolution condition)
"""
import logging

logger = logging.getLogger("cross_market.logical_relation_engine")

# Threshold for considering two thresholds equivalent
EQUIVALENT_TOLERANCE = 0.001  # 0.1%


def infer_relations(parsed_topic: dict) -> list[dict]:
    """Infer logical relations between markets in a parsed topic cluster."""
    markets = parsed_topic.get("parsed_markets", [])
    if not parsed_topic.get("is_ladder") or len(markets) < 2:
        return []

    relations = []
    threshold_markets = [
        m for m in markets
        if m["primitive"] in ("PRICE_THRESHOLD", "FDV_THRESHOLD")
        and m["threshold"] > 0
        and m["direction"] == "ABOVE"
    ]

    threshold_markets.sort(key=lambda m: m["threshold"])

    for i in range(len(threshold_markets)):
        for j in range(i + 1, len(threshold_markets)):
            lower = threshold_markets[i]
            higher = threshold_markets[j]

            # Check EQUIVALENT first
            if lower["threshold"] > 0 and abs(higher["threshold"] - lower["threshold"]) / lower["threshold"] < EQUIVALENT_TOLERANCE:
                relations.append({
                    "market_a": higher["market_id"],
                    "question_a": higher["question"],
                    "threshold_a": higher["threshold"],
                    "market_b": lower["market_id"],
                    "question_b": lower["question"],
                    "threshold_b": lower["threshold"],
                    "relation": "EQUIVALENT",
                    "explanation": (
                        f"{parsed_topic['entity']} ${higher['threshold']:,.0f} ≡ "
                        f"${lower['threshold']:,.0f} — logically equivalent"
                    ),
                    "confidence": 0.95,
                    "price_a": higher.get("yes_price"),
                    "price_b": lower.get("yes_price"),
                    "volume_a": higher.get("volume", 0),
                    "volume_b": lower.get("volume", 0),
                    "spread_a": higher.get("spread"),
                    "spread_b": lower.get("spread"),
                })
                continue

            # SUBSET: higher ⊂ lower
            relations.append({
                "market_a": higher["market_id"],
                "question_a": higher["question"],
                "threshold_a": higher["threshold"],
                "market_b": lower["market_id"],
                "question_b": lower["question"],
                "threshold_b": lower["threshold"],
                "relation": "SUBSET",
                "explanation": (
                    f"If {parsed_topic['entity']} > ${higher['threshold']:,.0f}, "
                    f"then {parsed_topic['entity']} > ${lower['threshold']:,.0f} is guaranteed"
                ),
                "confidence": 0.99 if abs(higher["threshold"] - lower["threshold"]) > 0 else 0.5,
                "price_a": higher.get("yes_price"),
                "price_b": lower.get("yes_price"),
                "volume_a": higher.get("volume", 0),
                "volume_b": lower.get("volume", 0),
                "spread_a": higher.get("spread"),
                "spread_b": lower.get("spread"),
            })

    # MONOTONIC relations: check adjacent pairs
    for i in range(len(threshold_markets) - 1):
        curr = threshold_markets[i]
        next_m = threshold_markets[i + 1]
        relations.append({
            "market_a": next_m["market_id"],
            "question_a": next_m["question"],
            "threshold_a": next_m["threshold"],
            "market_b": curr["market_id"],
            "question_b": curr["question"],
            "threshold_b": curr["threshold"],
            "relation": "MONOTONIC",
            "explanation": (
                f"Price at ${next_m['threshold']:,.0f} should be ≤ price at "
                f"${curr['threshold']:,.0f} (monotonic ladder)"
            ),
            "confidence": 0.95,
            "price_a": next_m.get("yes_price"),
            "price_b": curr.get("yes_price"),
            "volume_a": next_m.get("volume", 0),
            "volume_b": curr.get("volume", 0),
            "spread_a": next_m.get("spread"),
            "spread_b": curr.get("spread"),
        })

    logger.info(f"[RelationEngine] {parsed_topic['topic_key']}: {len(relations)} relations")
    return relations


def detect_violations(relations: list[dict]) -> list[dict]:
    """Detect logical violations across all relation modes."""
    violations = []

    for rel in relations:
        price_a = rel.get("price_a")
        price_b = rel.get("price_b")

        if price_a is None or price_b is None:
            continue

        if rel["relation"] == "SUBSET":
            # Subset (higher threshold) should be priced BELOW superset (lower threshold)
            if price_a > price_b + 0.005:
                gap = round(price_a - price_b, 4)
                violations.append({
                    "market_a": rel["market_a"],
                    "question_a": rel["question_a"],
                    "price_a": price_a,
                    "threshold_a": rel["threshold_a"],
                    "market_b": rel["market_b"],
                    "question_b": rel["question_b"],
                    "price_b": price_b,
                    "threshold_b": rel["threshold_b"],
                    "violation_type": "SUBSET_OVERPRICED",
                    "relation_mode": "SUBSET",
                    "gap": gap,
                    "gap_pct": round(gap * 100, 2),
                    "explanation": (
                        f"${rel['threshold_a']:,.0f} priced at {price_a:.1%} but "
                        f"${rel['threshold_b']:,.0f} (easier condition) at {price_b:.1%} — "
                        f"gap {gap:.1%}"
                    ),
                    "confidence": rel["confidence"],
                    "volume_a": rel.get("volume_a", 0),
                    "volume_b": rel.get("volume_b", 0),
                })

        elif rel["relation"] == "MONOTONIC":
            # Higher threshold should have lower or equal price
            if price_a > price_b + 0.005:
                gap = round(price_a - price_b, 4)
                violations.append({
                    "market_a": rel["market_a"],
                    "question_a": rel["question_a"],
                    "price_a": price_a,
                    "threshold_a": rel["threshold_a"],
                    "market_b": rel["market_b"],
                    "question_b": rel["question_b"],
                    "price_b": price_b,
                    "threshold_b": rel["threshold_b"],
                    "violation_type": "MONOTONIC_BREAK",
                    "relation_mode": "MONOTONIC",
                    "gap": gap,
                    "gap_pct": round(gap * 100, 2),
                    "explanation": (
                        f"Non-monotonic: ${rel['threshold_a']:,.0f} at {price_a:.1%} > "
                        f"${rel['threshold_b']:,.0f} at {price_b:.1%}"
                    ),
                    "confidence": rel["confidence"],
                    "volume_a": rel.get("volume_a", 0),
                    "volume_b": rel.get("volume_b", 0),
                })

        elif rel["relation"] == "EQUIVALENT":
            # Equivalent markets should have similar prices
            diff = abs(price_a - price_b)
            if diff > 0.02:  # >2% difference for equivalent markets
                violations.append({
                    "market_a": rel["market_a"],
                    "question_a": rel["question_a"],
                    "price_a": price_a,
                    "threshold_a": rel["threshold_a"],
                    "market_b": rel["market_b"],
                    "question_b": rel["question_b"],
                    "price_b": price_b,
                    "threshold_b": rel["threshold_b"],
                    "violation_type": "EQUIVALENT_DIVERGENCE",
                    "relation_mode": "EQUIVALENT",
                    "gap": round(diff, 4),
                    "gap_pct": round(diff * 100, 2),
                    "explanation": (
                        f"Equivalent markets diverge: {price_a:.1%} vs {price_b:.1%} — "
                        f"gap {diff:.1%}"
                    ),
                    "confidence": rel["confidence"],
                    "volume_a": rel.get("volume_a", 0),
                    "volume_b": rel.get("volume_b", 0),
                })

    if violations:
        logger.info(f"[RelationEngine] Found {len(violations)} violations")

    return violations
