"""
Cross-Platform Relation Engine — infers logical relations between Poly and Kalshi markets.

Only uses:
  - SUBSET: one market's condition is stricter
  - EQUIVALENT: same condition on different platforms
"""
import logging

logger = logging.getLogger("cross_market.kalshi.relation_engine")


def infer_cross_platform_relation(
    poly_parsed: dict,
    kalshi_parsed: dict,
    match_result: dict,
) -> dict | None:
    """Infer logical relation between a matched Poly-Kalshi pair.

    Returns relation dict or None if no clear relation.
    """
    poly_primitives = set(poly_parsed.get("primitives", []))
    kalshi_primitives = set(kalshi_parsed.get("primitives", []))

    poly_threshold = poly_parsed.get("threshold", 0) or 0
    kalshi_threshold = kalshi_parsed.get("threshold", 0) or 0
    poly_direction = poly_parsed.get("direction", "")
    kalshi_direction = kalshi_parsed.get("direction", "")

    poly_strictness = poly_parsed.get("strictness_score", 0)
    kalshi_strictness = kalshi_parsed.get("strictness_score", 0)

    parser_confidence = min(
        poly_parsed.get("parser_confidence", 0),
        kalshi_parsed.get("parser_confidence", 0),
    )

    # Guard: skip if parser confidence is weak
    if parser_confidence < 0.6:
        return None

    # PRICE_THRESHOLD markets: use threshold comparison
    if "PRICE_THRESHOLD" in poly_primitives and "PRICE_THRESHOLD" in kalshi_primitives:
        return _infer_price_relation(
            poly_parsed, kalshi_parsed, match_result, parser_confidence
        )

    # Non-price markets: use strictness comparison
    if poly_primitives and kalshi_primitives:
        return _infer_strictness_relation(
            poly_parsed, kalshi_parsed, match_result, parser_confidence
        )

    return None


def _infer_price_relation(
    poly: dict, kalshi: dict, match: dict, parser_confidence: float
) -> dict | None:
    """Infer relation for price threshold markets."""
    poly_t = poly.get("threshold", 0)
    kalshi_t = kalshi.get("threshold", 0)
    poly_dir = poly.get("direction", "ABOVE")
    kalshi_dir = kalshi.get("direction", "ABOVE")

    # Must be same direction
    if poly_dir != kalshi_dir:
        return None

    # Same threshold = EQUIVALENT
    if poly_t > 0 and kalshi_t > 0:
        diff_pct = abs(poly_t - kalshi_t) / max(poly_t, kalshi_t)

        if diff_pct < 0.005:
            return {
                "relation": "EQUIVALENT",
                "confidence": round(min(parser_confidence, match.get("match_score", 0)) * 0.95, 4),
                "poly_market_id": match.get("poly_market_id", ""),
                "kalshi_market_id": match.get("kalshi_market_id", ""),
                "poly_threshold": poly_t,
                "kalshi_threshold": kalshi_t,
                "poly_price": match.get("poly_price"),
                "kalshi_price": match.get("kalshi_price"),
                "poly_strictness": poly.get("strictness_score", 0),
                "kalshi_strictness": kalshi.get("strictness_score", 0),
                "parser_confidence": parser_confidence,
                "explanation": (
                    f"Same threshold ~${poly_t:,.0f} on both platforms: "
                    f"P(Poly)={match.get('poly_price', 0):.1%} vs P(Kalshi)={match.get('kalshi_price', 0):.1%}"
                ),
            }

        # ABOVE direction: higher threshold = stricter (SUBSET of lower)
        if poly_dir == "ABOVE":
            if kalshi_t > poly_t:
                # Kalshi is stricter → Kalshi ⊂ Poly
                return _build_subset_relation(
                    subset_platform="kalshi", superset_platform="polymarket",
                    subset_parsed=kalshi, superset_parsed=poly,
                    match=match, parser_confidence=parser_confidence,
                )
            elif poly_t > kalshi_t:
                # Poly is stricter → Poly ⊂ Kalshi
                return _build_subset_relation(
                    subset_platform="polymarket", superset_platform="kalshi",
                    subset_parsed=poly, superset_parsed=kalshi,
                    match=match, parser_confidence=parser_confidence,
                )

    return None


def _infer_strictness_relation(
    poly: dict, kalshi: dict, match: dict, parser_confidence: float
) -> dict | None:
    """Infer relation for non-price markets using strictness."""
    poly_s = poly.get("strictness_score", 0)
    kalshi_s = kalshi.get("strictness_score", 0)

    if abs(poly_s - kalshi_s) < 0.1:
        return {
            "relation": "EQUIVALENT",
            "confidence": round(min(parser_confidence, 0.7), 4),
            "poly_market_id": match.get("poly_market_id", ""),
            "kalshi_market_id": match.get("kalshi_market_id", ""),
            "poly_threshold": poly.get("threshold", 0),
            "kalshi_threshold": kalshi.get("threshold", 0),
            "poly_price": match.get("poly_price"),
            "kalshi_price": match.get("kalshi_price"),
            "poly_strictness": poly_s,
            "kalshi_strictness": kalshi_s,
            "parser_confidence": parser_confidence,
            "explanation": (
                f"Similar strictness ({poly_s:.2f} vs {kalshi_s:.2f}): "
                f"approximately equivalent conditions"
            ),
        }

    if kalshi_s > poly_s + 0.1:
        return _build_subset_relation(
            subset_platform="kalshi", superset_platform="polymarket",
            subset_parsed=kalshi, superset_parsed=poly,
            match=match, parser_confidence=parser_confidence,
        )

    if poly_s > kalshi_s + 0.1:
        return _build_subset_relation(
            subset_platform="polymarket", superset_platform="kalshi",
            subset_parsed=poly, superset_parsed=kalshi,
            match=match, parser_confidence=parser_confidence,
        )

    return None


def _build_subset_relation(
    subset_platform: str, superset_platform: str,
    subset_parsed: dict, superset_parsed: dict,
    match: dict, parser_confidence: float,
) -> dict:
    """Build a SUBSET relation dict."""
    subset_t = subset_parsed.get("threshold", 0)
    superset_t = superset_parsed.get("threshold", 0)

    return {
        "relation": "SUBSET",
        "confidence": round(min(parser_confidence, match.get("match_score", 0)), 4),
        "subset_platform": subset_platform,
        "superset_platform": superset_platform,
        "poly_market_id": match.get("poly_market_id", ""),
        "kalshi_market_id": match.get("kalshi_market_id", ""),
        "poly_threshold": match.get("poly_threshold", 0),
        "kalshi_threshold": match.get("kalshi_threshold", 0),
        "poly_price": match.get("poly_price"),
        "kalshi_price": match.get("kalshi_price"),
        "poly_strictness": subset_parsed.get("strictness_score", 0) if subset_platform == "polymarket" else superset_parsed.get("strictness_score", 0),
        "kalshi_strictness": subset_parsed.get("strictness_score", 0) if subset_platform == "kalshi" else superset_parsed.get("strictness_score", 0),
        "parser_confidence": parser_confidence,
        "explanation": (
            f"{subset_platform.capitalize()} (${subset_t:,.0f}) is stricter subset of "
            f"{superset_platform.capitalize()} (${superset_t:,.0f})"
        ),
    }


def infer_all_relations(
    clusters: list[dict],
    poly_parsed_map: dict[str, dict],
    kalshi_parsed_map: dict[str, dict],
) -> list[dict]:
    """Infer relations for all clusters.

    Args:
        clusters: CrossPlatformCluster list from linker
        poly_parsed_map: {market_id: parsed_resolution}
        kalshi_parsed_map: {market_id: parsed_resolution}

    Returns:
        List of relation dicts
    """
    relations = []

    for cluster in clusters:
        for match in cluster.get("matches", []):
            poly_id = match.get("poly_market_id", "")
            kalshi_id = match.get("kalshi_market_id", "")

            poly_parsed = poly_parsed_map.get(poly_id)
            kalshi_parsed = kalshi_parsed_map.get(kalshi_id)

            if not poly_parsed or not kalshi_parsed:
                continue

            rel = infer_cross_platform_relation(poly_parsed, kalshi_parsed, match)
            if rel:
                rel["cluster_id"] = cluster.get("cluster_id", "")
                rel["entity"] = cluster.get("entity", "")
                relations.append(rel)

    logger.info(f"[CrossPlatformRelation] {len(clusters)} clusters → {len(relations)} relations")
    return relations
