"""
Cross-Platform Orchestrator — runs the full Phase 3B pipeline.

Pipeline:
  cluster → relation → constraint → mispricing → edge_case → multiplier
  → actionability → REAL_EDGE_FILTER → strategy → dedup → analytics → output
"""
import time
import logging

from prediction.cross_market.kalshi.cross_platform_constraints import check_all_constraints
from prediction.cross_market.kalshi.cross_platform_mispricing import score_all_mispricings
from prediction.cross_market.kalshi.real_edge_filter import apply_real_edge_filter
from prediction.cross_market.kalshi.cross_platform_strategy import build_all_strategies
from prediction.cross_market.kalshi.cross_platform_analytics import store_batch

logger = logging.getLogger("cross_market.kalshi.orchestrator")

# Dedup: same cluster signal not repeated within this window
DEDUP_WINDOW_SEC = 1800  # 30 minutes

# Dedup cache: {key: timestamp}
_dedup_cache: dict[str, float] = {}


def _dedup_key(mispricing: dict) -> str:
    """Create dedup key from mispricing."""
    return (
        f"{mispricing.get('cluster_id', '')}:"
        f"{mispricing.get('constraint_type', '')}:"
        f"{mispricing.get('poly_market_id', '')}:"
        f"{mispricing.get('kalshi_market_id', '')}"
    )


def _deduplicate(mispricings: list[dict]) -> list[dict]:
    """Remove duplicate signals within dedup window."""
    now = time.time()
    deduped = []

    # Clean old entries
    expired_keys = [k for k, ts in _dedup_cache.items() if now - ts > DEDUP_WINDOW_SEC]
    for k in expired_keys:
        del _dedup_cache[k]

    for m in mispricings:
        key = _dedup_key(m)
        if key in _dedup_cache:
            continue  # Skip duplicate
        _dedup_cache[key] = now
        deduped.append(m)

    if len(mispricings) != len(deduped):
        logger.info(f"[Dedup] {len(mispricings)} → {len(deduped)} (removed {len(mispricings) - len(deduped)} dupes)")

    return deduped


def run_cross_platform_pipeline(
    relations: list[dict],
    poly_markets_map: dict | None = None,
    kalshi_markets_map: dict | None = None,
    poly_parsed_map: dict | None = None,
    kalshi_parsed_map: dict | None = None,
) -> dict:
    """Run the full cross-platform pipeline.

    Args:
        relations: from cross_platform_relation_engine
        poly_markets_map: {market_id: market_dict}
        kalshi_markets_map: {market_id: market_dict}
        poly_parsed_map: {market_id: parsed_resolution}
        kalshi_parsed_map: {market_id: parsed_resolution}

    Returns:
        Full pipeline result dict
    """
    # Step 1: Check constraints
    constraint_violations = check_all_constraints(relations)

    # Step 2: Score mispricings (includes edge_case classification + actionability)
    scored_mispricings = score_all_mispricings(
        constraint_violations,
        poly_markets_map=poly_markets_map,
        kalshi_markets_map=kalshi_markets_map,
        poly_parsed_map=poly_parsed_map,
        kalshi_parsed_map=kalshi_parsed_map,
    )

    # Step 3: Real Edge Filter (trap detection, verification)
    real_edge_filtered = apply_real_edge_filter(
        scored_mispricings,
        poly_markets_map=poly_markets_map or {},
        kalshi_markets_map=kalshi_markets_map or {},
    )

    # Step 4: Dedup
    deduped = _deduplicate(real_edge_filtered)

    # Step 5: Build strategies
    strategies = build_all_strategies(deduped)

    # Step 6: Store signals in analytics (non-blocking)
    try:
        strategies_map = {}
        for s in strategies.get("actionable", []):
            cid = s.get("cluster_id", "")
            if cid:
                strategies_map[cid] = s
        store_batch(deduped, strategies_map)
    except Exception as e:
        logger.warning(f"[Analytics] Failed to store batch: {e}")

    result = {
        "relations_count": len(relations),
        "violations_count": len(constraint_violations),
        "mispricings_scored": len(scored_mispricings),
        "mispricings_after_real_edge": len(real_edge_filtered),
        "mispricings_count": len(deduped),
        "strategies_actionable": strategies["total_actionable"],
        "strategies_no_trade": strategies["total_no_trade"],
        "constraint_violations": constraint_violations,
        "mispricings": deduped,
        "strategies": strategies,
    }

    logger.info(
        f"[CrossPlatformPipeline] {len(relations)} relations → "
        f"{len(constraint_violations)} violations → "
        f"{len(deduped)} mispricings → "
        f"{strategies['total_actionable']} actionable strategies"
    )

    return result
