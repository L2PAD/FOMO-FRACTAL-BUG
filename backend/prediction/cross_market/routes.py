"""
Cross-Market Intelligence API Routes.

Phase 1:
  GET  /api/cross-market/analysis   — Full analysis (clusters + relations + signals)
  GET  /api/cross-market/clusters   — Topic clusters only
  GET  /api/cross-market/relations  — Logical relations only
  GET  /api/cross-market/signals    — Cross-market signals only
  POST /api/cross-market/rebuild    — Force rebuild analysis from current feed

Phase 2:
  GET  /api/cross-market/mispricing  — Scored mispricings
  GET  /api/cross-market/strategies  — Generated strategies
"""
import logging
from fastapi import APIRouter

from prediction.cross_market.orchestrator import run_cross_market_analysis

logger = logging.getLogger("cross_market.routes")

router = APIRouter(prefix="/api/cross-market", tags=["cross-market"])

# Cache last analysis result
_cache = {"result": None}


async def _get_feed_events() -> list[dict]:
    """Fetch current feed events for analysis."""
    try:
        from prediction.feed.event_ingestion import ingest_feed
        feed = await ingest_feed()
        return feed.get("all", [])
    except Exception as e:
        logger.error(f"Failed to get feed events: {e}")
        return []


async def _ensure_analysis() -> dict:
    """Ensure analysis is available, run if not cached."""
    if _cache["result"] is None:
        events = await _get_feed_events()
        if events:
            _cache["result"] = run_cross_market_analysis(events)
        else:
            _cache["result"] = _empty_result()
    return _cache["result"]


def _empty_result() -> dict:
    return {
        "clusters_count": 0, "topics_count": 0,
        "ladders_count": 0, "relations_count": 0,
        "violations_count": 0, "signals_count": 0,
        "constraint_violations_count": 0, "mispricings_count": 0,
        "strategies_actionable": 0, "strategies_no_trade": 0,
        "topics": [], "parsed_topics": [], "relations": [],
        "violations": [], "signals": [],
        "constraint_violations": [], "mispricings": [],
        "strategies": {"actionable": [], "no_trade": [], "total_actionable": 0, "total_no_trade": 0},
    }


# ═══ Phase 1 Endpoints ═══

@router.get("/analysis")
async def cm_analysis():
    """Full cross-market analysis (Phase 1 + Phase 2 summary)."""
    result = await _ensure_analysis()
    return {
        "ok": True,
        "summary": {
            "clusters": result["clusters_count"],
            "topics": result["topics_count"],
            "ladders": result["ladders_count"],
            "relations": result["relations_count"],
            "violations": result["violations_count"],
            "signals": result["signals_count"],
            "mispricings": result["mispricings_count"],
            "strategies_actionable": result["strategies_actionable"],
        },
        "signals": result["signals"],
        "violations": result["violations"],
        "topics": [
            {
                "topic_key": t["topic_key"],
                "entity": t["entity"],
                "time_frame": t["time_frame"],
                "topic_type": t["topic_type"],
                "market_count": t["market_count"],
            }
            for t in result.get("topics", [])
        ],
    }


@router.get("/clusters")
async def cm_clusters():
    """Topic clusters with market details."""
    result = await _ensure_analysis()
    return {
        "ok": True,
        "count": result["topics_count"],
        "topics": result.get("topics", []),
    }


@router.get("/relations")
async def cm_relations():
    """Logical relations between markets."""
    result = await _ensure_analysis()
    return {
        "ok": True,
        "count": result["relations_count"],
        "relations": result.get("relations", []),
    }


@router.get("/signals")
async def cm_signals():
    """Cross-market signals (violations, gaps, structure issues)."""
    result = await _ensure_analysis()
    return {
        "ok": True,
        "count": result["signals_count"],
        "signals": result.get("signals", []),
        "violations": result.get("violations", []),
    }


# ═══ Phase 2 Endpoints ═══

@router.get("/mispricing")
async def cm_mispricing():
    """Scored mispricings with actionability scores and components."""
    result = await _ensure_analysis()
    return {
        "ok": True,
        "count": result["mispricings_count"],
        "mispricings": result.get("mispricings", []),
        "filters": {
            "min_gap": 0.01,
            "min_volume": 10000,
            "min_relation_confidence": 0.6,
            "actionability_strong": 0.75,
            "actionability_high": 0.65,
            "actionability_medium": 0.55,
        },
    }


@router.get("/strategies")
async def cm_strategies():
    """Generated trading strategies from mispricings."""
    result = await _ensure_analysis()
    strategies = result.get("strategies", {})
    return {
        "ok": True,
        "total_actionable": strategies.get("total_actionable", 0),
        "total_no_trade": strategies.get("total_no_trade", 0),
        "actionable": strategies.get("actionable", []),
        "no_trade": strategies.get("no_trade", []),
    }


@router.post("/rebuild")
async def cm_rebuild():
    """Force rebuild analysis from current feed."""
    events = await _get_feed_events()
    if not events:
        return {"ok": False, "error": "No feed events available"}

    result = run_cross_market_analysis(events)
    _cache["result"] = result

    return {
        "ok": True,
        "summary": {
            "events_analyzed": len(events),
            "clusters": result["clusters_count"],
            "topics": result["topics_count"],
            "ladders": result["ladders_count"],
            "relations": result["relations_count"],
            "violations": result["violations_count"],
            "signals": result["signals_count"],
            "mispricings": result["mispricings_count"],
            "strategies_actionable": result["strategies_actionable"],
            "strategies_no_trade": result["strategies_no_trade"],
        },
    }
