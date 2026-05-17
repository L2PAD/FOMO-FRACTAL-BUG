"""
Cross-Market Orchestrator — runs the full Phase 1 + Phase 2 pipeline.

Pipeline:
  Phase 1: Feed events → Link → Cluster → Parse → Relations → Signals
  Phase 2: Relations → Probability Constraints → Mispricing Scores → Strategies
"""
import logging
from prediction.cross_market.market_linker import link_markets
from prediction.cross_market.topic_clusterer import cluster_topics
from prediction.cross_market.resolution_parser import parse_cluster_resolutions
from prediction.cross_market.logical_relation_engine import infer_relations, detect_violations
from prediction.cross_market.cross_market_signal import generate_signals
from prediction.cross_market.probability_constraint import check_all_constraints
from prediction.cross_market.mispricing import score_all_mispricings
from prediction.cross_market.strategy import build_all_strategies

logger = logging.getLogger("cross_market.orchestrator")


def run_cross_market_analysis(events: list[dict]) -> dict:
    """Run the full cross-market analysis pipeline (Phase 1 + Phase 2)."""
    # ═══ Phase 1 ═══
    # Step 1: Link markets
    clusters = link_markets(events)

    # Step 2: Build topic clusters
    topics = cluster_topics(clusters)

    # Step 3-5: Parse → Relations → Signals for each topic
    all_parsed = []
    all_relations = []
    all_violations = []
    all_signals = []

    # Build expiry map from events
    expiry_map = _build_expiry_map(events)

    for topic in topics:
        parsed = parse_cluster_resolutions(topic)
        all_parsed.append(parsed)

        if parsed["is_ladder"]:
            relations = infer_relations(parsed)
            all_relations.extend(relations)

            violations = detect_violations(relations)
            all_violations.extend(violations)

            signals = generate_signals(parsed, relations, violations)
            all_signals.extend(signals)

    # Sort signals by severity
    severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    all_signals.sort(key=lambda s: severity_order.get(s.get("severity", "LOW"), 3))

    # ═══ Phase 2 ═══
    # Step 6: Probability Constraints
    constraint_violations = check_all_constraints(all_relations)

    # Step 7: Mispricing Scores
    scored_mispricings = score_all_mispricings(constraint_violations, expiry_map)

    # Step 8: Strategy Builder
    strategies = build_all_strategies(scored_mispricings)

    result = {
        # Phase 1 summary
        "clusters_count": len(clusters),
        "topics_count": len(topics),
        "ladders_count": sum(1 for p in all_parsed if p["is_ladder"]),
        "relations_count": len(all_relations),
        "violations_count": len(all_violations),
        "signals_count": len(all_signals),
        # Phase 2 summary
        "constraint_violations_count": len(constraint_violations),
        "mispricings_count": len(scored_mispricings),
        "strategies_actionable": strategies["total_actionable"],
        "strategies_no_trade": strategies["total_no_trade"],
        # Phase 1 data
        "topics": topics,
        "parsed_topics": all_parsed,
        "relations": all_relations[:50],
        "violations": all_violations,
        "signals": all_signals,
        # Phase 2 data
        "constraint_violations": constraint_violations[:30],
        "mispricings": scored_mispricings[:20],
        "strategies": strategies,
    }

    logger.info(
        f"[CrossMarket] {len(events)} events → "
        f"{len(clusters)} clusters → {len(topics)} topics → "
        f"{len(all_signals)} signals ({len(all_violations)} violations) | "
        f"Phase 2: {len(scored_mispricings)} mispricings → "
        f"{strategies['total_actionable']} strategies"
    )

    return result


def _build_expiry_map(events: list[dict]) -> dict:
    """Build a map of market_id → expiry_timestamp_ms from events."""
    expiry_map = {}
    for event in events:
        for mkt in event.get("markets", []):
            market_id = mkt.get("id", "")
            end_date = mkt.get("end_date_iso", "") or event.get("end_date_iso", "")
            if market_id and end_date:
                try:
                    from datetime import datetime, timezone
                    dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                    expiry_map[market_id] = dt.timestamp() * 1000
                except (ValueError, TypeError):
                    pass
    return expiry_map
