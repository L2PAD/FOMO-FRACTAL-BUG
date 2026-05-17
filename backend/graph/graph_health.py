"""
Graph Health Engine — observability & stability control.

Computes health metrics after each cron cycle:
  - Growth: new_nodes, new_edges
  - Quality: duplicates_pct, unresolved_nodes_pct, unresolved_edges_pct
  - Concentration: actor_gini, token_gini
  - Signal decay: avg_decay, avg_edge_weight
  - Parser health: per-source success_rate + html_fallback_used
  - Edge saturation: soft weight penalty on over-represented entities

Stores snapshots in graph_health_log with cycle_id.

Red flags (thresholds):
  - duplicates_pct > 5% → WARNING, > 10% → CRITICAL
  - unresolved_nodes_pct > 10% → WARNING
  - unresolved_edges_pct > 10% → WARNING
  - actor_gini > 0.6 → WARNING
  - token_gini > 0.6 → WARNING
  - new_edges consecutive < threshold (2 cycles) → WARNING
  - parser_success_rate < 0.8 → WARNING

Rule: Health Engine OBSERVES, does not auto-fix (except soft saturation penalty).
"""

import logging
import math
import uuid
from datetime import datetime, timezone, timedelta
from collections import Counter

logger = logging.getLogger(__name__)

# ── Thresholds ──
THRESHOLDS = {
    "duplicates_pct_warn": 5.0,
    "duplicates_pct_crit": 10.0,
    "unresolved_nodes_pct_warn": 10.0,
    "unresolved_edges_pct_warn": 10.0,
    "actor_gini_warn": 0.6,
    "token_gini_warn": 0.6,
    "parser_success_rate_warn": 0.8,
    "min_new_edges_6h": 5,
    "saturation_limit": 150,
}


def _gini(values: list) -> float:
    """Compute Gini coefficient. 0=perfect equality, 1=perfect inequality."""
    if not values or len(values) < 2:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    total = sum(sorted_vals)
    if total == 0:
        return 0.0
    cum = 0.0
    for i, v in enumerate(sorted_vals):
        cum += (2 * (i + 1) - n - 1) * v
    return round(cum / (n * total), 4)


async def compute_health_snapshot(db) -> dict:
    """Compute full health snapshot. Does NOT write to DB."""
    now = datetime.now(timezone.utc)
    cutoff_6h = now - timedelta(hours=6)

    # ── 1. Graph size ──
    total_nodes = await db.graph_nodes.count_documents({})
    total_edges = await db.graph_edges.count_documents({})
    signal_edges = await db.graph_edges.count_documents({"layer": "SIGNAL"})
    knowledge_edges = await db.graph_edges.count_documents({"layer": "KNOWLEDGE"})

    # New in last 6h (use created_at if available)
    new_nodes_6h = await db.graph_nodes.count_documents(
        {"created_at": {"$gte": cutoff_6h}}
    )
    new_edges_6h = await db.graph_edges.count_documents(
        {"created_at": {"$gte": cutoff_6h}}
    )

    # ── 2. Duplicates ──
    dup_pipeline = [
        {"$group": {
            "_id": {"f": "$from_node_id", "t": "$to_node_id",
                    "r": "$relation_type", "l": "$layer"},
            "count": {"$sum": 1}
        }},
        {"$match": {"count": {"$gt": 1}}},
        {"$count": "dups"}
    ]
    dup_result = await db.graph_edges.aggregate(dup_pipeline).to_list(1)
    dup_count = dup_result[0]["dups"] if dup_result else 0
    unique_edges = total_edges - dup_count
    duplicates_pct = round(dup_count / max(total_edges, 1) * 100, 2)

    # ── 3. Unresolved ──
    # Unresolved nodes: nodes with no edges at all
    # Split into meaningful (project, token, etc.) vs infra (wallet, exchange, etc.)
    from graph.graph_resolution import INFRA_TYPES, MEANINGFUL_TYPES

    all_node_ids = set()
    node_types = {}
    async for n in db.graph_nodes.find({}, {"_id": 0, "id": 1, "type": 1}):
        all_node_ids.add(n["id"])
        node_types[n["id"]] = n.get("type", "")

    connected_ids = set()
    async for e in db.graph_edges.find({}, {"_id": 0, "from_node_id": 1, "to_node_id": 1}):
        connected_ids.add(e["from_node_id"])
        connected_ids.add(e["to_node_id"])

    orphan_nodes = all_node_ids - connected_ids
    meaningful_orphans = sum(1 for oid in orphan_nodes if node_types.get(oid, "") in MEANINGFUL_TYPES)
    infra_orphans = sum(1 for oid in orphan_nodes if node_types.get(oid, "") in INFRA_TYPES)
    total_meaningful = sum(1 for t in node_types.values() if t in MEANINGFUL_TYPES)

    unresolved_nodes_pct = round(len(orphan_nodes) / max(total_nodes, 1) * 100, 2)
    meaningful_unresolved_pct = round(meaningful_orphans / max(total_meaningful, 1) * 100, 2)

    # Unresolved edges: edges where from_node_id or to_node_id not in graph_nodes
    edges_with_missing = 0
    edge_sample = await db.graph_edges.find(
        {}, {"_id": 0, "from_node_id": 1, "to_node_id": 1}
    ).to_list(15000)
    for e in edge_sample:
        if e["from_node_id"] not in all_node_ids or e["to_node_id"] not in all_node_ids:
            edges_with_missing += 1
    unresolved_edges_pct = round(edges_with_missing / max(len(edge_sample), 1) * 100, 2)

    # ── 4. Concentration (Gini) ──
    # Actor Gini: distribution of MENTIONED_TOKEN edges per actor
    actor_edge_counts = Counter()
    async for e in db.graph_edges.find(
        {"relation_type": "MENTIONED_TOKEN", "layer": "SIGNAL"},
        {"_id": 0, "from_node_id": 1}
    ):
        actor_edge_counts[e["from_node_id"]] += 1
    actor_gini = _gini(list(actor_edge_counts.values()))

    # Token Gini: distribution of mentions per token
    token_edge_counts = Counter()
    async for e in db.graph_edges.find(
        {"relation_type": "MENTIONED_TOKEN", "layer": "SIGNAL"},
        {"_id": 0, "to_node_id": 1}
    ):
        token_edge_counts[e["to_node_id"]] += 1
    token_gini = _gini(list(token_edge_counts.values()))

    # ── 5. Edge weights & decay ──
    avg_edge_weight = 0.0
    weight_pipeline = [
        {"$match": {"weight": {"$exists": True, "$gt": 0}}},
        {"$group": {"_id": None, "avg": {"$avg": "$weight"}}}
    ]
    wres = await db.graph_edges.aggregate(weight_pipeline).to_list(1)
    if wres:
        avg_edge_weight = round(wres[0]["avg"], 4)

    avg_decay = 0.0
    decay_pipeline = [
        {"$group": {"_id": None,
                     "avg_decay": {"$avg": "$decay_factor"},
                     "avg_current": {"$avg": "$weight_current"},
                     "avg_total": {"$avg": "$weight_total"}}}
    ]
    dres = await db.graph_edge_state.aggregate(decay_pipeline).to_list(1)
    decay_stats = {}
    if dres:
        avg_decay = round(dres[0].get("avg_decay", 0), 4)
        decay_stats = {
            "avg_decay": avg_decay,
            "avg_current": round(dres[0].get("avg_current", 0), 4),
            "avg_total": round(dres[0].get("avg_total", 0), 4),
        }

    # ── 6. Parser health (per-source) ──
    parser_health = {}
    total_success = 0
    total_parsers = 0
    async for p in db.parser_registry.find({}, {"_id": 0}):
        name = p.get("name", "")
        status = p.get("status", "UNKNOWN")
        cf = p.get("consecutive_failures", 0)
        fb = p.get("html_fallback_active", False)
        ok = status == "ACTIVE" and cf < 2

        parser_health[name] = {
            "status": status,
            "consecutive_failures": cf,
            "html_fallback_active": fb,
            "ok": ok,
        }
        total_parsers += 1
        if ok:
            total_success += 1

    parser_success_rate = round(total_success / max(total_parsers, 1), 4)
    html_fallback_used = sum(1 for v in parser_health.values() if v.get("html_fallback_active"))

    # ── 7. Edge saturation (top entities by degree) ──
    entity_degree = Counter()
    for e in edge_sample:
        entity_degree[e["from_node_id"]] += 1
        entity_degree[e["to_node_id"]] += 1

    top_saturated = entity_degree.most_common(10)
    saturated_entities = [
        {"entity": eid, "edges": cnt,
         "over_limit": cnt > THRESHOLDS["saturation_limit"]}
        for eid, cnt in top_saturated
    ]

    # ── 8. Intelligence edge counts ──
    intel_counts = {}
    for rel in ("entity_pressure", "alpha_source", "attention_flow"):
        intel_counts[rel] = await db.graph_edges.count_documents({"relation_type": rel})
    edge_states = await db.graph_edge_state.count_documents({})

    # ── 9. Alerts ──
    alerts = []
    if duplicates_pct > THRESHOLDS["duplicates_pct_crit"]:
        alerts.append({"level": "CRITICAL", "metric": "duplicates_pct", "value": duplicates_pct, "threshold": THRESHOLDS["duplicates_pct_crit"]})
    elif duplicates_pct > THRESHOLDS["duplicates_pct_warn"]:
        alerts.append({"level": "WARNING", "metric": "duplicates_pct", "value": duplicates_pct, "threshold": THRESHOLDS["duplicates_pct_warn"]})

    if unresolved_nodes_pct > THRESHOLDS["unresolved_nodes_pct_warn"]:
        # Only alert on meaningful nodes, not infra (wallet/exchange/cex are expected orphans)
        if meaningful_unresolved_pct > THRESHOLDS["unresolved_nodes_pct_warn"]:
            alerts.append({"level": "WARNING", "metric": "meaningful_unresolved_pct", "value": meaningful_unresolved_pct, "threshold": THRESHOLDS["unresolved_nodes_pct_warn"]})

    if unresolved_edges_pct > THRESHOLDS["unresolved_edges_pct_warn"]:
        alerts.append({"level": "WARNING", "metric": "unresolved_edges_pct", "value": unresolved_edges_pct, "threshold": THRESHOLDS["unresolved_edges_pct_warn"]})

    if actor_gini > THRESHOLDS["actor_gini_warn"]:
        alerts.append({"level": "WARNING", "metric": "actor_gini", "value": actor_gini, "threshold": THRESHOLDS["actor_gini_warn"]})

    if token_gini > THRESHOLDS["token_gini_warn"]:
        alerts.append({"level": "WARNING", "metric": "token_gini", "value": token_gini, "threshold": THRESHOLDS["token_gini_warn"]})

    if parser_success_rate < THRESHOLDS["parser_success_rate_warn"]:
        alerts.append({"level": "WARNING", "metric": "parser_success_rate", "value": parser_success_rate, "threshold": THRESHOLDS["parser_success_rate_warn"]})

    # Check consecutive low growth (compare with last health log)
    last_log = await db.graph_health_log.find_one(
        {}, {"_id": 0, "new_edges_6h": 1}, sort=[("timestamp", -1)]
    )
    if last_log and last_log.get("new_edges_6h", 999) < THRESHOLDS["min_new_edges_6h"]:
        if new_edges_6h < THRESHOLDS["min_new_edges_6h"]:
            alerts.append({"level": "WARNING", "metric": "growth_stall", "value": new_edges_6h,
                           "message": "2 consecutive cycles with low edge growth"})

    health_status = "HEALTHY"
    if any(a["level"] == "CRITICAL" for a in alerts):
        health_status = "CRITICAL"
    elif alerts:
        health_status = "WARNING"

    return {
        "timestamp": now.isoformat(),
        "status": health_status,

        "nodes": total_nodes,
        "edges": total_edges,
        "signal_edges": signal_edges,
        "knowledge_edges": knowledge_edges,

        "new_nodes_6h": new_nodes_6h,
        "new_edges_6h": new_edges_6h,

        "duplicates_pct": duplicates_pct,
        "unresolved_nodes_pct": unresolved_nodes_pct,
        "meaningful_unresolved_pct": meaningful_unresolved_pct,
        "meaningful_orphans": meaningful_orphans,
        "infra_orphans": infra_orphans,
        "unresolved_edges_pct": unresolved_edges_pct,

        "actor_gini": actor_gini,
        "token_gini": token_gini,

        "avg_edge_weight": avg_edge_weight,
        "decay_stats": decay_stats,

        "parser_success_rate": parser_success_rate,
        "parser_health": parser_health,
        "html_fallback_used": html_fallback_used,

        "intelligence": intel_counts,
        "edge_states": edge_states,

        "saturation": saturated_entities,

        "alerts": alerts,
        "alert_count": len(alerts),
        "thresholds": THRESHOLDS,
    }


async def log_health(db, cycle_id: str = None, snapshot: dict = None):
    """
    Compute health snapshot and save to graph_health_log.
    Called after each cron cycle.
    """
    if snapshot is None:
        snapshot = await compute_health_snapshot(db)

    if cycle_id is None:
        cycle_id = f"health_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    record = {
        "cycle_id": cycle_id,
        **snapshot,
    }

    await db.graph_health_log.insert_one({**record})

    logger.info(
        f"[HealthEngine] {snapshot['status']} | "
        f"nodes={snapshot['nodes']} edges={snapshot['edges']} "
        f"new_6h=+{snapshot['new_edges_6h']} "
        f"dups={snapshot['duplicates_pct']}% "
        f"gini(actor={snapshot['actor_gini']},token={snapshot['token_gini']}) "
        f"alerts={snapshot['alert_count']}"
    )

    return record


async def apply_saturation_penalty(db, saturation_limit: int = None):
    """
    Soft weight penalty on entities with too many edges.
    Only affects graph_edge_state.weight_current (not structure).

    penalty = min(0.3, edges / limit * 0.1)
    weight_current *= (1 - penalty)
    """
    if saturation_limit is None:
        saturation_limit = THRESHOLDS["saturation_limit"]

    now = datetime.now(timezone.utc)

    # Count edges per entity
    entity_degree = Counter()
    async for e in db.graph_edges.find(
        {"layer": "SIGNAL"},
        {"_id": 0, "from_node_id": 1, "to_node_id": 1}
    ):
        entity_degree[e["from_node_id"]] += 1
        entity_degree[e["to_node_id"]] += 1

    saturated = {eid: cnt for eid, cnt in entity_degree.items()
                 if cnt > saturation_limit}

    if not saturated:
        return {"penalized": 0, "saturation_limit": saturation_limit}

    penalized = 0
    for eid, cnt in saturated.items():
        penalty = min(0.3, cnt / saturation_limit * 0.1)

        # Apply penalty to all edge states involving this entity
        result = await db.graph_edge_state.update_many(
            {"$or": [
                {"from_node_id": eid},
                {"to_node_id": eid},
            ]},
            {"$mul": {"weight_current": round(1 - penalty, 4)}},
        )
        penalized += result.modified_count

    logger.info(f"[HealthEngine] Saturation penalty: {len(saturated)} entities, {penalized} states modified")
    return {
        "penalized_states": penalized,
        "saturated_entities": len(saturated),
        "saturation_limit": saturation_limit,
        "entities": [{"id": eid, "edges": cnt, "penalty": round(min(0.3, cnt / saturation_limit * 0.1), 4)}
                     for eid, cnt in sorted(saturated.items(), key=lambda x: -x[1])[:10]],
    }


async def get_health_history(db, limit: int = 20):
    """Get last N health snapshots."""
    logs = await db.graph_health_log.find(
        {}, {"_id": 0}
    ).sort("timestamp", -1).limit(limit).to_list(limit)

    # Convert any remaining datetimes
    for log in logs:
        for k, v in list(log.items()):
            if isinstance(v, datetime):
                log[k] = v.isoformat()

    return {
        "ok": True,
        "count": len(logs),
        "history": logs,
    }
