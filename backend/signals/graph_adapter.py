"""
Graph Signal Adapter
====================
Builds signal context from Knowledge Graph intelligence layers.
Feeds into core_signal_logic.detect_signal_type().

Data sources:
  - graph_edges: MENTIONED_TOKEN, attention_flow, alpha_source, entity_pressure
  - graph_edge_state: weight_current, weight_total, count
  - graph_nodes: token, project, fund
"""

import logging

logger = logging.getLogger("graph_adapter")


async def build_graph_context(db, token_id: str) -> dict:
    """
    Build unified signal context for a token from graph intelligence edges.

    Returns context dict compatible with core_signal_logic.detect_signal_type():
        mentions, momentum, pressure, alpha, flow, growth_rate, actor_count
    """
    # ── Count actor mentions ──
    mention_edges = await db.graph_edges.find(
        {"to_node_id": token_id, "relation_type": "MENTIONED_TOKEN"},
        {"_id": 0, "from_node_id": 1}
    ).to_list(200)
    mentions = len(mention_edges)
    unique_actors = len(set(e["from_node_id"] for e in mention_edges))

    # ── Entity Pressure ──
    pressure_edge = await db.graph_edges.find_one(
        {"to_node_id": token_id, "relation_type": "entity_pressure"},
        {"_id": 0, "from_node_id": 1}
    )
    pressure_state = None
    if pressure_edge:
        pressure_state = await db.graph_edge_state.find_one(
            {
                "from_node_id": pressure_edge["from_node_id"],
                "to_node_id": token_id,
                "relation_type": "entity_pressure",
            },
            {"_id": 0, "weight_current": 1, "weight_total": 1, "count": 1}
        )

    pressure = 0.0
    if pressure_state:
        # Normalize: weight_current is decayed, use as pressure signal
        w = pressure_state.get("weight_current", 0)
        pressure = min(w / 5.0, 1.0)  # 5+ weight = max pressure

    # ── Alpha Source ──
    alpha_edges = await db.graph_edges.find(
        {"to_node_id": token_id, "relation_type": "alpha_source"},
        {"_id": 0, "from_node_id": 1}
    ).to_list(20)

    alpha = 0.0
    if alpha_edges:
        # More alpha sources = stronger signal
        alpha = min(len(alpha_edges) / 3.0, 1.0)

    # ── Attention Flow (actor→project via token) ──
    # Find project for this token
    project_edge = await db.graph_edges.find_one(
        {"from_node_id": token_id, "relation_type": "token_of"},
        {"_id": 0, "to_node_id": 1}
    )

    flow = 0.0
    if project_edge:
        project_id = project_edge["to_node_id"]
        flow_edges = await db.graph_edges.find(
            {"to_node_id": project_id, "relation_type": "attention_flow"},
            {"_id": 0, "from_node_id": 1}
        ).to_list(50)
        flow = min(len(flow_edges) / 5.0, 1.0)

    # ── Momentum: recent mention growth ──
    # Compare current vs decayed total weight as momentum proxy
    momentum = 0.0
    if pressure_state:
        total = pressure_state.get("weight_total", 0)
        current = pressure_state.get("weight_current", 0)
        if total > 0:
            # Ratio of current/total indicates recency of activity
            momentum = min(current / max(total, 1), 1.0)

    # ── Growth Rate from mention edge states ──
    growth_rate = 0.0
    if mention_edges:
        states = []
        for me in mention_edges[:10]:
            s = await db.graph_edge_state.find_one(
                {
                    "from_node_id": me["from_node_id"],
                    "to_node_id": token_id,
                    "relation_type": "MENTIONED_TOKEN",
                },
                {"_id": 0, "weight_current": 1, "count": 1}
            )
            if s:
                states.append(s)

        if states:
            avg_current = sum(s.get("weight_current", 0) for s in states) / len(states)
            avg_count = sum(s.get("count", 0) for s in states) / len(states)
            growth_rate = min(avg_current * avg_count / 10, 1.0) if avg_count > 1 else 0

    return {
        "mentions": mentions,
        "momentum": momentum,
        "pressure": pressure,
        "alpha": alpha,
        "flow": flow,
        "growth_rate": growth_rate,
        "actor_count": unique_actors,
        "source": "graph",
        "token_id": token_id,
    }


async def build_fund_context(db, fund_id: str) -> dict:
    """
    Build signal context aggregated at fund level.

    Aggregates entity_pressure and attention_flow across all projects
    invested in by the fund.

    Returns context dict for detect_signal_type().
    """
    # ── Find projects invested by this fund ──
    invested_edges = await db.graph_edges.find(
        {"from_node_id": fund_id, "relation_type": "invested_in"},
        {"_id": 0, "to_node_id": 1}
    ).to_list(100)

    project_ids = [e["to_node_id"] for e in invested_edges]
    if not project_ids:
        return {
            "mentions": 0, "momentum": 0, "pressure": 0,
            "alpha": 0, "flow": 0, "growth_rate": 0,
            "actor_count": 0, "source": "graph_fund", "fund_id": fund_id,
        }

    # ── Aggregate across projects ──
    total_pressure = 0.0
    total_flow = 0.0
    total_alpha = 0.0
    total_mentions = 0
    all_actors = set()

    for proj_id in project_ids:
        # Find token for project
        token_edge = await db.graph_edges.find_one(
            {"to_node_id": proj_id, "relation_type": "token_of"},
            {"_id": 0, "from_node_id": 1}
        )

        if token_edge:
            token_id = token_edge["from_node_id"]
            ctx = await build_graph_context(db, token_id)
            total_pressure += ctx["pressure"]
            total_flow += ctx["flow"]
            total_alpha += ctx["alpha"]
            total_mentions += ctx["mentions"]
            # Collect unique actors
            mention_edges = await db.graph_edges.find(
                {"to_node_id": token_id, "relation_type": "MENTIONED_TOKEN"},
                {"_id": 0, "from_node_id": 1}
            ).to_list(100)
            for me in mention_edges:
                all_actors.add(me["from_node_id"])

        # Also check attention_flow directly to project
        flow_edges = await db.graph_edges.find(
            {"to_node_id": proj_id, "relation_type": "attention_flow"},
            {"_id": 0, "from_node_id": 1}
        ).to_list(50)
        total_flow += len(flow_edges) * 0.1

    n = max(len(project_ids), 1)

    return {
        "mentions": total_mentions,
        "momentum": min(total_pressure / n, 1.0),
        "pressure": min(total_pressure / n, 1.0),
        "alpha": min(total_alpha / n, 1.0),
        "flow": min(total_flow / n, 1.0),
        "growth_rate": 0,
        "actor_count": len(all_actors),
        "source": "graph_fund",
        "fund_id": fund_id,
        "project_count": len(project_ids),
    }
