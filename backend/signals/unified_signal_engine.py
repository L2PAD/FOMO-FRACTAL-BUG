"""
Unified Signal Engine
=====================
Single entry point for signal detection.
Both Overview and Graph feed contexts here.

Usage:
    from signals.signal_engine import detect_signal, run_graph_signals, run_fund_signals

    # From graph:
    context = await build_graph_context(db, "token:SOL")
    signal = detect_signal(context)

    # From overview:
    context = build_overview_context(data)
    signal = detect_signal(context)
"""

import logging
from datetime import datetime, timezone

from .core_signal_logic import detect_signal_type, context_modifier, severity

logger = logging.getLogger("signal_engine")


def detect_signal(context: dict, market_context: dict = None) -> dict:
    """
    Unified signal detection.

    Args:
        context: Signal context from any adapter (graph, overview, fund)
        market_context: Optional market context for score adjustment
            {regime, pressure, ranking, risk}

    Returns:
        {is_signal, type, strength, confidence, direction, severity, source}
    """
    result = detect_signal_type(context)

    # Apply context modifier if market context available
    if market_context and result["is_signal"]:
        modifier = context_modifier(result["direction"], market_context)
        adjusted = max(0, min(result["strength"] + modifier, 100))
        result["strength"] = adjusted
        result["severity"] = severity(adjusted)

    # Pass through source info
    result["source"] = context.get("source", "unknown")

    return result


async def run_graph_signals(db, limit: int = 50) -> dict:
    """
    Run signal detection across active graph tokens.
    Writes detected signals as graph edges + signal_log.

    Returns summary of signals found.
    """
    from .graph_adapter import build_graph_context
    from graph.graph_builder import upsert_edge

    # Find active tokens (those with recent MENTIONED_TOKEN edges)
    pipeline = [
        {"$match": {"relation_type": "MENTIONED_TOKEN"}},
        {"$group": {"_id": "$to_node_id", "count": {"$sum": 1}}},
        {"$match": {"count": {"$gte": 2}}},
        {"$sort": {"count": -1}},
        {"$limit": limit},
    ]
    active_tokens = await db.graph_edges.aggregate(pipeline).to_list(limit)

    signals_found = []
    now = datetime.now(timezone.utc)

    for token_doc in active_tokens:
        token_id = token_doc["_id"]
        mention_count = token_doc["count"]

        ctx = await build_graph_context(db, token_id)
        signal = detect_signal(ctx)

        if not signal["is_signal"]:
            continue

        # Find project for token (for edge creation)
        project_edge = await db.graph_edges.find_one(
            {"from_node_id": token_id, "relation_type": "token_of"},
            {"_id": 0, "to_node_id": 1}
        )

        # Write signal edge: token → project
        if project_edge:
            project_id = project_edge["to_node_id"]
            await upsert_edge(
                db, token_id, project_id,
                "signal_detected", "SIGNAL",
                metadata={
                    "signal_type": signal["type"],
                    "strength": signal["strength"],
                    "confidence": signal["confidence"],
                    "direction": signal["direction"],
                    "severity": signal["severity"],
                    "source": "graph_signal_engine",
                    "detected_at": now.isoformat(),
                }
            )

        # Write to signal_log (future ML dataset)
        await db.signal_log.insert_one({
            "entity": token_id,
            "entity_type": "token",
            "type": signal["type"],
            "strength": signal["strength"],
            "confidence": signal["confidence"],
            "direction": signal["direction"],
            "severity": signal["severity"],
            "context": {
                "mentions": ctx["mentions"],
                "pressure": ctx["pressure"],
                "alpha": ctx["alpha"],
                "flow": ctx["flow"],
                "actor_count": ctx["actor_count"],
            },
            "source": "graph",
            "timestamp": now.isoformat(),
        })

        signals_found.append({
            "token": token_id,
            "project": project_edge["to_node_id"] if project_edge else None,
            "type": signal["type"],
            "strength": signal["strength"],
            "direction": signal["direction"],
            "severity": signal["severity"],
        })

    logger.info(f"[SignalEngine] Graph signals: {len(signals_found)} detected from {len(active_tokens)} active tokens")

    return {
        "signals_detected": len(signals_found),
        "tokens_scanned": len(active_tokens),
        "signals": signals_found,
    }


async def run_fund_signals(db, limit: int = 20) -> dict:
    """
    Run signal detection at fund level.
    Aggregates project signals per fund → fund_pressure.

    Returns summary of fund-level signals.
    """
    from .graph_adapter import build_fund_context
    from graph.graph_builder import upsert_edge

    # Find all fund nodes
    funds = await db.graph_nodes.find(
        {"type": "fund"},
        {"_id": 0, "id": 1, "label": 1}
    ).to_list(limit)

    signals_found = []
    now = datetime.now(timezone.utc)

    for fund in funds:
        fund_id = fund["id"]

        ctx = await build_fund_context(db, fund_id)

        # Skip funds with no portfolio data
        if ctx.get("project_count", 0) == 0:
            continue

        signal = detect_signal(ctx)

        if not signal["is_signal"]:
            continue

        # Write signal_log for fund
        await db.signal_log.insert_one({
            "entity": fund_id,
            "entity_type": "fund",
            "type": "FUND_PRESSURE",
            "strength": signal["strength"],
            "confidence": signal["confidence"],
            "direction": signal["direction"],
            "severity": signal["severity"],
            "context": {
                "mentions": ctx["mentions"],
                "pressure": ctx["pressure"],
                "alpha": ctx["alpha"],
                "flow": ctx["flow"],
                "actor_count": ctx["actor_count"],
                "project_count": ctx.get("project_count", 0),
            },
            "source": "graph_fund",
            "timestamp": now.isoformat(),
        })

        # Mark fund as active in graph
        await db.graph_nodes.update_one(
            {"id": fund_id},
            {"$set": {
                "signal_active": True,
                "signal_strength": signal["strength"],
                "signal_direction": signal["direction"],
                "signal_updated": now.isoformat(),
            }}
        )

        signals_found.append({
            "fund": fund_id,
            "label": fund.get("label", ""),
            "type": "FUND_PRESSURE",
            "strength": signal["strength"],
            "direction": signal["direction"],
            "severity": signal["severity"],
            "project_count": ctx.get("project_count", 0),
            "actor_count": ctx["actor_count"],
        })

    logger.info(f"[SignalEngine] Fund signals: {len(signals_found)} detected from {len(funds)} funds")

    return {
        "signals_detected": len(signals_found),
        "funds_scanned": len(funds),
        "signals": signals_found,
    }


async def get_signal_log(db, entity: str = None, limit: int = 50) -> list:
    """Get recent signal log entries."""
    query = {}
    if entity:
        query["entity"] = entity

    cursor = db.signal_log.find(
        query, {"_id": 0}
    ).sort("timestamp", -1).limit(limit)

    return await cursor.to_list(limit)
