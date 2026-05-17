"""
Kalshi Cross-Platform API Routes.

Batch 1 Endpoints:
  GET  /api/cross-market/kalshi/markets    — Fetched + normalized Kalshi markets
  GET  /api/cross-market/kalshi/clusters   — Cross-platform clusters (Poly ↔ Kalshi)
  GET  /api/cross-market/kalshi/relations  — Inferred relations
  POST /api/cross-market/kalshi/rebuild    — Force rebuild
  GET  /api/cross-market/debug/clusters    — Debug view with scoring details
"""
import logging
from fastapi import APIRouter

from prediction.cross_market.kalshi.kalshi_source import fetch_kalshi_markets
from prediction.cross_market.kalshi.kalshi_normalizer import normalize_all
from prediction.cross_market.kalshi.kalshi_market_filter import filter_markets
from prediction.cross_market.kalshi.platform_market_linker import link_platforms
from prediction.cross_market.kalshi.resolution_parser_v2 import parse_resolution_v2
from prediction.cross_market.kalshi.cross_platform_relation_engine import infer_all_relations
from prediction.cross_market.kalshi.cross_platform_orchestrator import run_cross_platform_pipeline
from prediction.cross_market.kalshi.cross_platform_analytics import (
    get_analytics_by_edge_type,
    get_analytics_by_platform_pair_and_type,
    get_recent_signals,
    get_signal_count,
)
from prediction.cross_market.kalshi.manual_validation import (
    get_validation_queue,
    get_validation_metrics,
    submit_verdict,
    MANUAL_VERDICTS,
)
from prediction.cross_market.kalshi.auto_rebuild import (
    get_health as get_rebuild_health,
    start_auto_rebuild,
    stop_auto_rebuild,
)

logger = logging.getLogger("cross_market.kalshi.routes")

router = APIRouter(prefix="/api/cross-market/kalshi", tags=["cross-market-kalshi"])

# Cache
_kalshi_cache = {
    "kalshi_markets": [],
    "poly_markets": [],
    "clusters": [],
    "relations": [],
    "poly_parsed": {},
    "kalshi_parsed": {},
    "pipeline_result": None,
    "poly_markets_map": {},
    "kalshi_markets_map": {},
}


async def _get_poly_markets() -> list[dict]:
    """Get current Polymarket markets from our feed for matching."""
    try:
        from prediction.feed.event_ingestion import ingest_feed
        feed = await ingest_feed()
        events = feed.get("all", [])
        markets = []
        for ev in events:
            for mkt in ev.get("markets", []):
                question = mkt.get("question", "")
                # Extract threshold from question
                import re
                threshold = 0
                q_lower = question.lower()

                # "above $60,000" or "above $64,000" pattern
                above_match = re.search(r'above\s+\$?([\d,]+)', q_lower)
                if above_match:
                    threshold = float(above_match.group(1).replace(",", ""))

                # "reach $75,000" or "hit $80,000" pattern
                if threshold == 0:
                    reach_match = re.search(r'(?:reach|hit|exceed)\s+\$?([\d,]+)', q_lower)
                    if reach_match:
                        threshold = float(reach_match.group(1).replace(",", ""))

                # "$60k" shorthand
                if threshold == 0:
                    k_match = re.search(r'\$(\d+)k\b', q_lower)
                    if k_match:
                        threshold = float(k_match.group(1)) * 1000

                # "between $74,000 and $76,000" pattern
                if threshold == 0:
                    between_match = re.search(r'between\s+\$?([\d,]+)', q_lower)
                    if between_match:
                        threshold = float(between_match.group(1).replace(",", ""))

                direction = "ABOVE"
                if "below" in q_lower or "less than" in q_lower:
                    direction = "BELOW"
                elif "between" in q_lower:
                    direction = "BETWEEN"

                markets.append({
                    "market_id": mkt.get("market_id", "") or mkt.get("id", ""),
                    "question": question,
                    "title": ev.get("title", ""),
                    "yes_price": mkt.get("yes_price"),
                    "volume": mkt.get("volume", 0),
                    "spread": mkt.get("spread"),
                    "asset_group": ev.get("asset_group", ""),
                    "threshold": threshold,
                    "direction": direction,
                    "end_date_iso": ev.get("end_date_iso", ""),
                    "platform": "polymarket",
                })
        return markets
    except Exception as e:
        logger.error(f"Failed to get Polymarket markets: {e}")
        return []


async def _rebuild_kalshi():
    """Rebuild all Kalshi cross-platform data."""
    # Step 1: Fetch Kalshi
    raw_markets = fetch_kalshi_markets()
    normalized = normalize_all(raw_markets)
    filtered = filter_markets(normalized)

    # Step 2: Get Polymarket markets
    poly_markets = await _get_poly_markets()

    # Step 3: Link platforms
    clusters = link_platforms(poly_markets, filtered)

    # Step 4: Parse resolutions
    poly_parsed = {}
    kalshi_parsed = {}
    for pm in poly_markets:
        mid = pm.get("market_id", "")
        if mid:
            poly_parsed[mid] = parse_resolution_v2(pm)

    for km in filtered:
        mid = km.get("id", "")
        if mid:
            kalshi_parsed[mid] = parse_resolution_v2(km)

    # Step 5: Infer relations
    relations = infer_all_relations(clusters, poly_parsed, kalshi_parsed)

    # Step 6: Build market maps for Phase 3B pipeline
    poly_markets_map = {pm.get("market_id", ""): pm for pm in poly_markets if pm.get("market_id")}
    kalshi_markets_map = {km.get("id", ""): km for km in filtered if km.get("id")}

    # Step 7: Run Phase 3B pipeline (constraints → mispricing → strategy)
    pipeline_result = run_cross_platform_pipeline(
        relations=relations,
        poly_markets_map=poly_markets_map,
        kalshi_markets_map=kalshi_markets_map,
        poly_parsed_map=poly_parsed,
        kalshi_parsed_map=kalshi_parsed,
    )

    # Update cache
    _kalshi_cache["kalshi_markets"] = filtered
    _kalshi_cache["poly_markets"] = poly_markets
    _kalshi_cache["clusters"] = clusters
    _kalshi_cache["relations"] = relations
    _kalshi_cache["poly_parsed"] = poly_parsed
    _kalshi_cache["kalshi_parsed"] = kalshi_parsed
    _kalshi_cache["pipeline_result"] = pipeline_result
    _kalshi_cache["poly_markets_map"] = poly_markets_map
    _kalshi_cache["kalshi_markets_map"] = kalshi_markets_map

    return {
        "kalshi_raw": len(raw_markets),
        "kalshi_normalized": len(normalized),
        "kalshi_filtered": len(filtered),
        "poly_markets": len(poly_markets),
        "clusters": len(clusters),
        "relations": len(relations),
        "violations": pipeline_result["violations_count"],
        "mispricings": pipeline_result["mispricings_count"],
        "strategies_actionable": pipeline_result["strategies_actionable"],
    }


@router.get("/markets")
async def kalshi_markets():
    """Fetched + normalized + filtered Kalshi crypto markets."""
    if not _kalshi_cache["kalshi_markets"]:
        await _rebuild_kalshi()

    markets = _kalshi_cache["kalshi_markets"]
    return {
        "ok": True,
        "count": len(markets),
        "markets": [
            {
                "id": m["id"],
                "ticker": m["ticker"],
                "entity": m["entity"],
                "question": m["question"],
                "yes_price": m["yes_price"],
                "yes_bid": m.get("yes_bid"),
                "yes_ask": m.get("yes_ask"),
                "spread": m.get("spread"),
                "volume": m["volume"],
                "threshold": m["threshold"],
                "direction": m["direction"],
                "close_time": m["close_time"],
            }
            for m in markets[:100]
        ],
    }


@router.get("/clusters")
async def kalshi_clusters():
    """Cross-platform clusters (matched Poly ↔ Kalshi markets)."""
    if not _kalshi_cache["clusters"]:
        await _rebuild_kalshi()

    clusters = _kalshi_cache["clusters"]
    return {
        "ok": True,
        "count": len(clusters),
        "clusters": [
            {
                "cluster_id": c["cluster_id"],
                "entity": c["entity"],
                "topic": c["topic"],
                "market_count": len(c["markets"]),
                "match_count": len(c["matches"]),
                "markets": c["markets"],
            }
            for c in clusters
        ],
    }


@router.get("/relations")
async def kalshi_relations():
    """Inferred cross-platform relations (SUBSET/EQUIVALENT)."""
    if not _kalshi_cache["relations"]:
        await _rebuild_kalshi()

    relations = _kalshi_cache["relations"]
    return {
        "ok": True,
        "count": len(relations),
        "relations": relations,
    }


@router.post("/rebuild")
async def kalshi_rebuild():
    """Force rebuild all Kalshi cross-platform analysis."""
    summary = await _rebuild_kalshi()
    return {
        "ok": True,
        "summary": summary,
    }


# ═══ Phase 3B Endpoints ═══

@router.get("/mispricings")
async def kalshi_mispricings():
    """Cross-platform scored mispricings with edge case classification."""
    if not _kalshi_cache["pipeline_result"]:
        await _rebuild_kalshi()

    result = _kalshi_cache.get("pipeline_result") or {}
    mispricings = result.get("mispricings", [])
    return {
        "ok": True,
        "count": len(mispricings),
        "mispricings": mispricings,
    }


@router.get("/strategies")
async def kalshi_strategies():
    """Cross-platform trading strategies (LOGICAL_ARBITRAGE / RELATIVE_VALUE / NO_TRADE)."""
    if not _kalshi_cache["pipeline_result"]:
        await _rebuild_kalshi()

    result = _kalshi_cache.get("pipeline_result") or {}
    strategies = result.get("strategies", {})
    return {
        "ok": True,
        "total_actionable": strategies.get("total_actionable", 0),
        "total_no_trade": strategies.get("total_no_trade", 0),
        "actionable": strategies.get("actionable", []),
        "no_trade": strategies.get("no_trade", []),
    }


@router.get("/signals")
async def kalshi_signals():
    """Cross-platform signals — combined view of mispricings + strategies."""
    if not _kalshi_cache["pipeline_result"]:
        await _rebuild_kalshi()

    result = _kalshi_cache.get("pipeline_result") or {}
    mispricings = result.get("mispricings", [])
    strategies = result.get("strategies", {})

    signals = []
    actionable_strats = strategies.get("actionable", [])

    for m in mispricings:
        # Find matching strategy
        matching_strat = next(
            (s for s in actionable_strats if s.get("cluster_id") == m.get("cluster_id")),
            None
        )
        signals.append({
            "cluster_id": m.get("cluster_id", ""),
            "entity": m.get("entity", ""),
            "constraint_type": m.get("constraint_type", ""),
            "edge_case_type": m.get("edge_case_type", "UNKNOWN"),
            "gap": m.get("gap", 0),
            "gap_pct": m.get("gap_pct", 0),
            "score": m.get("score", 0),
            "actionability_score": m.get("actionability_score", 0),
            "real_edge_score": m.get("real_edge_score"),
            "severity": m.get("severity", "MEDIUM"),
            "actionable": m.get("actionable", False),
            "edge_badge": m.get("edge_badge", ""),
            "trap_flags": m.get("trap_flags", []),
            "real_edge_components": m.get("real_edge_components"),
            "poly_price": m.get("poly_price"),
            "kalshi_price": m.get("kalshi_price"),
            "explanation": m.get("explanation", ""),
            "strategy": matching_strat,
        })

    return {
        "ok": True,
        "count": len(signals),
        "signals": signals,
    }


@router.get("/debug/clusters")
async def kalshi_debug_clusters():
    """Debug view — full scoring details for each cluster match."""
    if not _kalshi_cache["clusters"]:
        await _rebuild_kalshi()

    clusters = _kalshi_cache["clusters"]
    relations = _kalshi_cache["relations"]
    kalshi_parsed = _kalshi_cache["kalshi_parsed"]
    poly_parsed = _kalshi_cache["poly_parsed"]

    debug_data = []
    for c in clusters:
        cluster_rels = [r for r in relations if r.get("cluster_id") == c["cluster_id"]]

        # Get parsed resolutions for markets in cluster
        parsed_info = []
        for m in c["markets"]:
            mid = m["id"]
            p = kalshi_parsed.get(mid) or poly_parsed.get(mid) or {}
            parsed_info.append({
                "platform": m["platform"],
                "id": mid,
                "primitives": p.get("primitives", []),
                "strictness": p.get("strictness_score", 0),
                "parser_confidence": p.get("parser_confidence", 0),
            })

        debug_data.append({
            "cluster_id": c["cluster_id"],
            "entity": c["entity"],
            "topic": c["topic"],
            "markets": c["markets"],
            "matches": [
                {
                    "poly": m.get("poly_question", "")[:100],
                    "kalshi": m.get("kalshi_question", "")[:100],
                    "score": m.get("match_score"),
                    "entity_score": m.get("entity_score"),
                    "topic_score": m.get("topic_score"),
                    "time_score": m.get("time_score"),
                    "resolution_score": m.get("resolution_score"),
                }
                for m in c.get("matches", [])
            ],
            "parsed_resolutions": parsed_info,
            "relations": [
                {
                    "relation": r.get("relation"),
                    "confidence": r.get("confidence"),
                    "explanation": r.get("explanation"),
                    "poly_price": r.get("poly_price"),
                    "kalshi_price": r.get("kalshi_price"),
                }
                for r in cluster_rels
            ],
        })

    return {
        "ok": True,
        "total_clusters": len(clusters),
        "total_relations": len(relations),
        "clusters": debug_data,
    }



# ─── Analytics Endpoints ──────────────────────────────────────────

@router.get("/analytics")
async def get_cross_platform_analytics():
    """Get cross-platform signal analytics grouped by edge_case_type."""
    by_type = get_analytics_by_edge_type()
    by_pair = get_analytics_by_platform_pair_and_type()
    total = get_signal_count()

    return {
        "ok": True,
        "total_signals_tracked": total,
        "by_edge_type": by_type,
        "by_platform_pair": by_pair,
    }


@router.get("/analytics/signals")
async def get_analytics_signal_history(limit: int = 50):
    """Get recent signal history for manual review."""
    signals = get_recent_signals(limit=limit)
    return {
        "ok": True,
        "count": len(signals),
        "signals": signals,
    }



# ─── Validation Endpoints ──────────────────────────────────────────

@router.get("/validation-queue")
async def get_cross_platform_validation_queue(status: str = "PENDING", limit: int = 50):
    """Get validation entries for manual review."""
    entries = get_validation_queue(status=status, limit=limit)
    return {
        "ok": True,
        "count": len(entries),
        "entries": entries,
    }


@router.post("/validate/{validation_id}")
async def submit_validation_verdict(validation_id: str, body: dict):
    """Submit a manual verdict for a signal."""
    verdict = body.get("manual_verdict", "")
    if verdict not in MANUAL_VERDICTS:
        return {"ok": False, "error": f"Invalid verdict. Must be one of: {MANUAL_VERDICTS}"}

    success = submit_verdict(
        validation_id=validation_id,
        verdict=verdict,
        execution_possible=body.get("execution_possible"),
        verdict_reason=body.get("verdict_reason", ""),
        execution_notes=body.get("execution_notes", ""),
    )
    return {"ok": success}


@router.get("/validation-metrics")
async def get_cross_platform_validation_metrics():
    """Get validation performance metrics."""
    metrics = get_validation_metrics()
    return {"ok": True, **metrics}


# ─── Health & Auto-Rebuild Endpoints ──────────────────────────────

@router.get("/health")
async def get_cross_platform_health():
    """Get rebuild health and scheduler status."""
    return {"ok": True, **get_rebuild_health()}


@router.post("/auto-rebuild/start")
async def start_auto_rebuild_endpoint():
    """Start the auto-rebuild background scheduler."""
    import asyncio
    health = get_rebuild_health()
    if health["running"]:
        return {"ok": True, "message": "Already running"}
    asyncio.create_task(start_auto_rebuild())
    return {"ok": True, "message": "Auto-rebuild started"}


@router.post("/auto-rebuild/stop")
async def stop_auto_rebuild_endpoint():
    """Stop the auto-rebuild background scheduler."""
    stop_auto_rebuild()
    return {"ok": True, "message": "Auto-rebuild stop requested"}
