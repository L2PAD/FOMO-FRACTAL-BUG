"""
Cross-Platform Mispricing Score — the money layer.

Pipeline: constraint → mispricing → edge_case → multiplier → actionability → output

Base score:
  score = gap_norm*0.40 + relation_confidence*0.20 + parser_confidence*0.15 + liquidity*0.15 + time*0.10

Actionability:
  actionability = score*0.40 + liquidity*0.30 + execution_feasibility*0.20 + time*0.10

Hard filters:
  - gap < 0.02 → drop
  - relation_confidence < 0.6 → drop
  - parser_confidence < 0.6 → drop
  - liquidity_score < 0.4 → drop (softened — real_edge_filter handles rest)
  - spread > 0.05 → drop
  - actionability_score < 0.55 → drop
"""
import math
import time as _time
import logging

from prediction.cross_market.kalshi.edge_case_classifier import classify_edge_case, get_multiplier

logger = logging.getLogger("cross_market.kalshi.mispricing")

# Base score weights
W_GAP = 0.40
W_REL_CONF = 0.20
W_PARSER_CONF = 0.15
W_LIQUIDITY = 0.15
W_TIME = 0.10

# Actionability weights
AW_SCORE = 0.40
AW_LIQUIDITY = 0.30
AW_EXECUTION = 0.20
AW_TIME = 0.10

# Hard filters
MIN_GAP = 0.02
MIN_REL_CONFIDENCE = 0.6
MIN_PARSER_CONFIDENCE = 0.6
MIN_LIQUIDITY_SCORE = 0.4  # Softened — real_edge_filter provides additional protection
MAX_SPREAD = 0.05
MIN_ACTIONABILITY = 0.55

# Severity thresholds
SEV_STRONG = 0.75
SEV_HIGH = 0.65
SEV_MEDIUM = 0.55


def _normalize_liquidity(volume_a: float, volume_b: float) -> float:
    """Normalize cross-platform liquidity using geometric mean.

    sqrt(a * b) balances between min and max:
    - Penalizes asymmetric liquidity naturally
    - Doesn't kill signals when one side has decent volume
    - Additional penalty if one side is very thin
    """
    a = max(volume_a or 0, 0)
    b = max(volume_b or 0, 0)

    if a == 0 and b == 0:
        return 0.1

    min_vol = min(a, b)

    # Floor zero-volume to 500 for geometric mean (avoids zero product)
    a_floor = max(a, 500)
    b_floor = max(b, 500)
    geo = math.sqrt(a_floor * b_floor)

    # Tier by geometric mean
    if geo >= 50000:
        score = 1.0
    elif geo >= 20000:
        score = 0.85
    elif geo >= 10000:
        score = 0.75
    elif geo >= 5000:
        score = 0.65
    elif geo >= 2000:
        score = 0.55
    else:
        score = 0.4

    # Fallback: penalize if one side very thin
    if min_vol < 1000:
        score *= 0.8

    return round(max(score, 0.1), 2)


def _normalize_time(expiry_ts: float | None) -> float:
    """Normalize time to expiry."""
    if not expiry_ts or expiry_ts <= 0:
        return 0.6
    now_ms = _time.time() * 1000
    hours_left = max((expiry_ts - now_ms) / 3_600_000, 0)
    if hours_left <= 24:
        return 1.0
    elif hours_left <= 72:
        return 0.8
    return 0.6


def _normalize_execution(spread_a: float | None, spread_b: float | None) -> float:
    """Normalize execution feasibility from spreads."""
    spreads = [s for s in [spread_a, spread_b] if s is not None and s > 0]
    if not spreads:
        return 0.7
    max_spread = max(spreads)
    if max_spread <= 0.02:
        return 1.0
    elif max_spread <= 0.05:
        return 0.7
    return 0.4


def _severity_label(actionability: float) -> str:
    if actionability >= SEV_STRONG:
        return "STRONG"
    elif actionability >= SEV_HIGH:
        return "HIGH"
    elif actionability >= SEV_MEDIUM:
        return "MEDIUM"
    return "DROP"


def score_cross_platform_mispricing(
    constraint: dict,
    poly_market: dict | None = None,
    kalshi_market: dict | None = None,
    poly_parsed: dict | None = None,
    kalshi_parsed: dict | None = None,
) -> dict | None:
    """Score a single cross-platform constraint violation.

    Flow: constraint → score → edge_case → multiplier → actionability → filter

    Returns scored mispricing dict or None if filtered out.
    """
    gap = constraint.get("gap", 0)
    rel_confidence = constraint.get("relation_confidence", 0)
    parser_confidence = constraint.get("parser_confidence", 0)

    # Hard filters
    if gap < MIN_GAP:
        return None
    if rel_confidence < MIN_REL_CONFIDENCE:
        return None
    if parser_confidence < MIN_PARSER_CONFIDENCE:
        return None

    # Market data
    poly_market = poly_market or {}
    kalshi_market = kalshi_market or {}

    poly_volume = poly_market.get("volume", 0) or 0
    kalshi_volume = kalshi_market.get("volume", 0) or 0
    poly_spread = poly_market.get("spread")
    kalshi_spread = kalshi_market.get("spread")
    expiry_ts = kalshi_market.get("expiry_ts") or poly_market.get("expiry_ts")

    # Hard filter: spread
    spreads = [s for s in [poly_spread, kalshi_spread] if s is not None and s > 0]
    if spreads and max(spreads) > MAX_SPREAD:
        return None

    # Normalizations
    liquidity_score = _normalize_liquidity(poly_volume, kalshi_volume)
    time_factor = _normalize_time(expiry_ts)
    execution_feasibility = _normalize_execution(poly_spread, kalshi_spread)

    # Hard filter: liquidity
    if liquidity_score < MIN_LIQUIDITY_SCORE:
        return None

    # Normalize gap to [0, 1] — raw probability diffs (0.02-0.10) become meaningful scores
    # 2% → 0.4, 4% → 0.8, 5%+ → 1.0
    gap_score = min(gap / 0.05, 1.0)

    # Base score
    base_score = (
        gap_score * W_GAP
        + rel_confidence * W_REL_CONF
        + parser_confidence * W_PARSER_CONF
        + liquidity_score * W_LIQUIDITY
        + time_factor * W_TIME
    )
    base_score = round(min(base_score, 1.0), 4)

    # Edge case classification (inside pipeline)
    edge_case_type = classify_edge_case(constraint, poly_parsed, kalshi_parsed)
    multiplier = get_multiplier(edge_case_type)

    # Apply multiplier
    score = round(min(base_score * multiplier, 1.0), 4)

    # Actionability
    actionability_score = round(min(
        score * AW_SCORE
        + liquidity_score * AW_LIQUIDITY
        + execution_feasibility * AW_EXECUTION
        + time_factor * AW_TIME,
        1.0
    ), 4)

    # Hard filter: actionability
    if actionability_score < MIN_ACTIONABILITY:
        return None

    severity = _severity_label(actionability_score)
    if severity == "DROP":
        return None

    actionable = actionability_score >= SEV_HIGH

    return {
        "cluster_id": constraint.get("cluster_id", ""),
        "entity": constraint.get("entity", ""),
        "constraint_type": constraint.get("type", ""),
        "poly_market_id": constraint.get("poly_market_id", ""),
        "kalshi_market_id": constraint.get("kalshi_market_id", ""),
        "poly_threshold": constraint.get("poly_threshold", 0),
        "kalshi_threshold": constraint.get("kalshi_threshold", 0),
        "gap": gap,
        "gap_pct": round(gap * 100, 2),
        "score": score,
        "base_score": base_score,
        "actionability_score": actionability_score,
        "severity": severity,
        "actionable": actionable,
        "edge_case_type": edge_case_type,
        "edge_multiplier": multiplier,
        "components": {
            "gap": round(gap, 4),
            "relation_confidence": round(rel_confidence, 4),
            "parser_confidence": round(parser_confidence, 4),
            "liquidity_score": round(liquidity_score, 4),
            "time_factor": round(time_factor, 4),
            "execution_feasibility": round(execution_feasibility, 4),
        },
        "poly_price": constraint.get("poly_prob") or constraint.get("superset_prob") or (poly_market.get("yes_price")),
        "kalshi_price": constraint.get("kalshi_prob") or constraint.get("subset_prob") or (kalshi_market.get("yes_price")),
        "explanation": constraint.get("explanation", ""),
    }


def score_all_mispricings(
    constraints: list[dict],
    poly_markets_map: dict | None = None,
    kalshi_markets_map: dict | None = None,
    poly_parsed_map: dict | None = None,
    kalshi_parsed_map: dict | None = None,
) -> list[dict]:
    """Score all constraint violations and filter.

    Returns sorted by actionability_score desc.
    """
    poly_markets_map = poly_markets_map or {}
    kalshi_markets_map = kalshi_markets_map or {}
    poly_parsed_map = poly_parsed_map or {}
    kalshi_parsed_map = kalshi_parsed_map or {}

    scored = []
    for c in constraints:
        poly_id = c.get("poly_market_id", "")
        kalshi_id = c.get("kalshi_market_id", "")

        result = score_cross_platform_mispricing(
            constraint=c,
            poly_market=poly_markets_map.get(poly_id),
            kalshi_market=kalshi_markets_map.get(kalshi_id),
            poly_parsed=poly_parsed_map.get(poly_id),
            kalshi_parsed=kalshi_parsed_map.get(kalshi_id),
        )
        if result is not None:
            scored.append(result)

    scored.sort(key=lambda x: x["actionability_score"], reverse=True)

    logger.info(
        f"[CrossPlatformMispricing] {len(constraints)} constraints → "
        f"{len(scored)} scored mispricings"
    )
    return scored
