"""
Graph Intelligence — signal reasoning inside the graph.

Executed AFTER graph_builder populates nodes+edges.
Adds dynamic intelligence edges on top of structural graph.

Build order (each step is independent and testable):
  1. entity_pressure  — token→project pressure from actor convergence
  2. alpha_source     — actor→token edge for high-conviction early actors
  3. temporal_decay   — weight_current with exp decay, weight_total preserved
  4. attention_flow   — 1-hop collapse: actor→project via token bridge

Rules:
  - Every new edge type is STRICT (high threshold)
  - Never mass-create — quality over quantity
  - Never destroy historical weight — decay only current, preserve total
  - Layer = SIGNAL for all intelligence edges
"""

import logging
import math
from datetime import datetime, timezone, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


# ============================================================
# 1. ENTITY PRESSURE
# ============================================================

async def build_entity_pressure(db, window_hours: int = 24, min_actors: int = 3):
    """
    If >= min_actors mention a token in a time window → create
    token → project (entity_pressure) edge.

    Weight = coordination_score * avg_actor_strength
      coordination = unique_actors / total_actors_in_window (how focused)
      actor_strength = avg hit_rate of mentioning actors

    Only creates edge if token→project bridge exists (token_of).
    """
    now = datetime.now(timezone.utc)

    # Get all signal events
    events = await db.actor_signal_events.find(
        {}, {"_id": 0, "actor_handle": 1, "token": 1, "signal_type": 1,
             "timestamp": 1, "created_at": 1}
    ).to_list(15000)

    # Group by token
    token_data = defaultdict(lambda: {"actors": set(), "early_count": 0, "total": 0})
    for e in events:
        token = e.get("token", "")
        actor = e.get("actor_handle", "")
        sig_type = e.get("signal_type", "mention")
        if not token or not actor:
            continue
        td = token_data[token]
        td["actors"].add(actor)
        td["total"] += 1
        if sig_type in ("conviction", "warning"):
            td["early_count"] += 1

    # Get actor intelligence for strength calc
    actor_intel = {}
    async for doc in db.actor_intelligence.find(
        {}, {"_id": 0, "actor_handle": 1, "hit_rate_24h": 1, "early_ratio": 1}
    ):
        actor_intel[doc["actor_handle"]] = doc

    # Get token→project bridges
    bridges = {}
    async for edge in db.graph_edges.find(
        {"relation_type": "token_of", "layer": "KNOWLEDGE"},
        {"_id": 0, "from_node_id": 1, "to_node_id": 1}
    ):
        token_id = edge["from_node_id"]  # e.g. token:ETH
        project_id = edge["to_node_id"]  # e.g. project:ethereum
        sym = token_id.replace("token:", "")
        bridges[sym] = project_id

    edges_created = 0
    pressure_data = []

    for token, td in token_data.items():
        unique_actors = len(td["actors"])
        if unique_actors < min_actors:
            continue

        project_id = bridges.get(token)
        if not project_id:
            continue

        # Coordination: how many unique actors vs total pool
        total_actors_in_graph = max(len(actor_intel), 1)
        coordination = min(unique_actors / total_actors_in_graph, 1.0)

        # Actor strength: average hit_rate of actors mentioning this token
        hit_rates = []
        for actor in td["actors"]:
            intel = actor_intel.get(actor)
            if intel and intel.get("hit_rate_24h", 0) > 0:
                hit_rates.append(intel["hit_rate_24h"])
        avg_strength = sum(hit_rates) / len(hit_rates) if hit_rates else 0.3

        # Early signal ratio
        early_ratio = td["early_count"] / max(td["total"], 1)

        # Weight = coordination * strength * (1 + early_bonus)
        weight = round(
            coordination * avg_strength * (1.0 + early_ratio * 0.5),
            4
        )
        weight = min(weight, 1.0)

        token_id = f"token:{token}"

        await db.graph_edges.update_one(
            {
                "from_node_id": token_id,
                "to_node_id": project_id,
                "relation_type": "entity_pressure",
                "layer": "SIGNAL",
            },
            {
                "$set": {
                    "weight": weight,
                    "updated_at": now,
                    "metadata": {
                        "unique_actors": unique_actors,
                        "coordination": round(coordination, 4),
                        "avg_actor_strength": round(avg_strength, 4),
                        "early_ratio": round(early_ratio, 4),
                        "total_mentions": td["total"],
                    },
                },
                "$setOnInsert": {
                    "from_node_id": token_id,
                    "to_node_id": project_id,
                    "relation_type": "entity_pressure",
                    "layer": "SIGNAL",
                    "created_at": now,
                },
            },
            upsert=True,
        )
        edges_created += 1
        pressure_data.append({
            "token": token, "project": project_id,
            "actors": unique_actors, "weight": weight,
        })

    # Sort by weight for reporting
    pressure_data.sort(key=lambda x: x["weight"], reverse=True)

    logger.info(f"[GraphIntel] entity_pressure: {edges_created} edges")
    return {
        "edges": edges_created,
        "top_pressure": pressure_data[:10],
    }


# ============================================================
# 2. ALPHA SOURCE
# ============================================================

async def build_alpha_source(db, min_hit_rate: float = 0.65, min_early: float = 0.5,
                              min_signals: int = 10):
    """
    If actor has hit_rate > threshold AND early_ratio > threshold → create
    actor → token (alpha_source) edge for their top mentioned tokens.

    Strict: only top-performing actors, only their strongest signals.
    """
    now = datetime.now(timezone.utc)

    # Get qualifying actors
    actors = await db.actor_intelligence.find(
        {
            "hit_rate_24h": {"$gte": min_hit_rate},
            "early_ratio": {"$gte": min_early},
            "total_signals": {"$gte": min_signals},
        },
        {"_id": 0, "actor_handle": 1, "hit_rate_24h": 1, "early_ratio": 1,
         "total_signals": 1, "role": 1}
    ).to_list(100)

    if not actors:
        return {"edges": 0, "qualifying_actors": 0}

    actor_handles = {a["actor_handle"] for a in actors}
    actor_map = {a["actor_handle"]: a for a in actors}

    # Get their signal events grouped by token
    pipeline = [
        {"$match": {"actor_handle": {"$in": list(actor_handles)}}},
        {"$group": {
            "_id": {"actor": "$actor_handle", "token": "$token"},
            "count": {"$sum": 1},
            "conviction_count": {
                "$sum": {"$cond": [{"$eq": ["$signal_type", "conviction"]}, 1, 0]}
            },
            "last_seen": {"$max": "$created_at"},
        }},
    ]

    pairs = []
    async for doc in db.actor_signal_events.aggregate(pipeline):
        pairs.append(doc)

    edges_created = 0
    alpha_data = []

    for p in pairs:
        actor = p["_id"]["actor"]
        token = p["_id"]["token"]
        count = p["count"]
        conviction = p["conviction_count"]

        intel = actor_map.get(actor, {})
        hit_rate = intel.get("hit_rate_24h", 0)
        early = intel.get("early_ratio", 0)

        # Alpha weight = hit_rate * early_ratio * signal_strength
        signal_strength = min(math.log(1 + count) / 4.0, 1.0)
        conviction_bonus = min(conviction / max(count, 1), 0.3)

        weight = round(
            hit_rate * 0.4 + early * 0.3 + signal_strength * 0.2 + conviction_bonus * 0.1,
            4
        )

        from_id = f"twitter:{actor.lower()}"
        to_id = f"token:{token.upper()}"

        await db.graph_edges.update_one(
            {
                "from_node_id": from_id,
                "to_node_id": to_id,
                "relation_type": "alpha_source",
                "layer": "SIGNAL",
            },
            {
                "$set": {
                    "weight": weight,
                    "updated_at": now,
                    "metadata": {
                        "hit_rate": round(hit_rate, 4),
                        "early_ratio": round(early, 4),
                        "mention_count": count,
                        "conviction_count": conviction,
                        "actor_role": intel.get("role", "UNKNOWN"),
                    },
                },
                "$setOnInsert": {
                    "from_node_id": from_id,
                    "to_node_id": to_id,
                    "relation_type": "alpha_source",
                    "layer": "SIGNAL",
                    "created_at": now,
                },
            },
            upsert=True,
        )
        edges_created += 1
        alpha_data.append({
            "actor": actor, "token": token,
            "weight": weight, "hit_rate": hit_rate,
        })

    alpha_data.sort(key=lambda x: x["weight"], reverse=True)

    logger.info(f"[GraphIntel] alpha_source: {edges_created} edges from {len(actors)} actors")
    return {
        "edges": edges_created,
        "qualifying_actors": len(actors),
        "top_alpha": alpha_data[:10],
    }


# ============================================================
# 3. TEMPORAL DECAY
# ============================================================

async def apply_temporal_decay(db, tau_hours: float = 48.0):
    """
    For all SIGNAL edges with timestamps:
      weight_current = base_weight * exp(-hours_elapsed / tau)
      weight_total += base_weight  (only grows, never decays)

    Uses graph_edge_state collection (separate from graph_edges).
    Structure stays stable. Only state changes.

    tau_hours = half-life-ish parameter. 48h = signal loses ~63% after 48h.
    """
    now = datetime.now(timezone.utc)

    signal_edges = await db.graph_edges.find(
        {
            "layer": "SIGNAL",
            "metadata.last_seen": {"$exists": True},
        },
        {"_id": 0, "from_node_id": 1, "to_node_id": 1, "relation_type": 1,
         "weight": 1, "metadata.last_seen": 1, "metadata.count": 1}
    ).to_list(10000)

    updated = 0
    for edge in signal_edges:
        last_seen_raw = edge.get("metadata", {}).get("last_seen")
        base_weight = edge.get("weight", 0)
        if not last_seen_raw or not base_weight:
            continue

        # Parse last_seen
        try:
            if isinstance(last_seen_raw, str):
                ls = datetime.fromisoformat(last_seen_raw.replace("Z", "+00:00"))
            elif isinstance(last_seen_raw, datetime):
                ls = last_seen_raw if last_seen_raw.tzinfo else last_seen_raw.replace(tzinfo=timezone.utc)
            else:
                continue
        except (ValueError, TypeError):
            continue

        hours_elapsed = max((now - ls).total_seconds() / 3600, 0)
        decay_factor = math.exp(-hours_elapsed / tau_hours)
        weight_current = round(base_weight * decay_factor, 4)

        edge_key = {
            "from_node_id": edge["from_node_id"],
            "to_node_id": edge["to_node_id"],
            "relation_type": edge["relation_type"],
        }

        await db.graph_edge_state.update_one(
            edge_key,
            {
                "$set": {
                    "weight_current": weight_current,
                    "decay_factor": round(decay_factor, 4),
                    "hours_elapsed": round(hours_elapsed, 1),
                    "updated_at": now,
                },
                "$inc": {
                    "weight_total": base_weight,
                },
                "$setOnInsert": {
                    **edge_key,
                    "created_at": now,
                },
            },
            upsert=True,
        )
        updated += 1

    # Stats
    avg_decay = 0
    if updated:
        pipeline = [
            {"$group": {"_id": None, "avg_decay": {"$avg": "$decay_factor"},
                         "avg_current": {"$avg": "$weight_current"},
                         "avg_total": {"$avg": "$weight_total"}}}
        ]
        stats = await db.graph_edge_state.aggregate(pipeline).to_list(1)
        if stats:
            avg_decay = round(stats[0].get("avg_decay", 0), 4)

    logger.info(f"[GraphIntel] temporal_decay: {updated} edges, avg_decay={avg_decay}")
    return {
        "edges_updated": updated,
        "avg_decay_factor": avg_decay,
        "tau_hours": tau_hours,
    }


# ============================================================
# 4. ATTENTION FLOW (1-hop collapse)
# ============================================================

async def build_attention_flow(db, min_mentions: int = 2):
    """
    1-hop collapse: if actor→token AND token→project (token_of)
    → create actor→project (attention_flow).

    Only for actors with meaningful signal (>=min_mentions of that token).
    Weight = mention_weight * bridge_confidence.
    """
    now = datetime.now(timezone.utc)

    # Get token→project bridges
    bridges = {}
    async for edge in db.graph_edges.find(
        {"relation_type": "token_of", "layer": "KNOWLEDGE"},
        {"_id": 0, "from_node_id": 1, "to_node_id": 1}
    ):
        token_id = edge["from_node_id"]
        project_id = edge["to_node_id"]
        bridges[token_id] = project_id

    if not bridges:
        return {"edges": 0, "reason": "no token_of bridges"}

    # Get MENTIONED_TOKEN edges with metadata
    mention_edges = await db.graph_edges.find(
        {
            "relation_type": "MENTIONED_TOKEN",
            "layer": "SIGNAL",
            "metadata.count": {"$gte": min_mentions},
        },
        {"_id": 0, "from_node_id": 1, "to_node_id": 1, "weight": 1,
         "metadata.count": 1, "metadata.recency": 1}
    ).to_list(10000)

    # Group by actor→project (collapse through token)
    actor_project = defaultdict(lambda: {"weight_sum": 0, "tokens": [], "count": 0})

    for me in mention_edges:
        actor_id = me["from_node_id"]  # twitter:handle
        token_id = me["to_node_id"]     # token:ETH
        project_id = bridges.get(token_id)
        if not project_id:
            continue

        weight = me.get("weight", 0)
        count = me.get("metadata", {}).get("count", 0)
        recency = me.get("metadata", {}).get("recency", 0)

        key = (actor_id, project_id)
        ap = actor_project[key]
        ap["weight_sum"] += weight
        ap["tokens"].append(token_id.replace("token:", ""))
        ap["count"] += count

    edges_created = 0
    flow_data = []

    for (actor_id, project_id), ap in actor_project.items():
        if not ap["tokens"]:
            continue

        # Normalized weight
        weight = round(min(ap["weight_sum"] / max(len(ap["tokens"]), 1), 1.0), 4)

        await db.graph_edges.update_one(
            {
                "from_node_id": actor_id,
                "to_node_id": project_id,
                "relation_type": "attention_flow",
                "layer": "SIGNAL",
            },
            {
                "$set": {
                    "weight": weight,
                    "updated_at": now,
                    "metadata": {
                        "via_tokens": ap["tokens"][:5],
                        "total_mentions": ap["count"],
                        "token_count": len(ap["tokens"]),
                    },
                },
                "$setOnInsert": {
                    "from_node_id": actor_id,
                    "to_node_id": project_id,
                    "relation_type": "attention_flow",
                    "layer": "SIGNAL",
                    "created_at": now,
                },
            },
            upsert=True,
        )
        edges_created += 1
        flow_data.append({
            "actor": actor_id, "project": project_id,
            "tokens": ap["tokens"][:3], "weight": weight,
        })

    flow_data.sort(key=lambda x: x["weight"], reverse=True)

    logger.info(f"[GraphIntel] attention_flow: {edges_created} edges (1-hop collapse)")
    return {
        "edges": edges_created,
        "top_flows": flow_data[:10],
    }


# ============================================================
# ORCHESTRATOR
# ============================================================

async def run_graph_intelligence(db):
    """
    Run all intelligence layers in order:
    1. entity_pressure
    2. alpha_source
    3. temporal_decay
    4. attention_flow
    """
    import time
    start = time.time()
    results = {}

    logger.info("[GraphIntel] === INTELLIGENCE RUN START ===")

    results["entity_pressure"] = await build_entity_pressure(db)
    results["alpha_source"] = await build_alpha_source(db)
    results["temporal_decay"] = await apply_temporal_decay(db)
    results["attention_flow"] = await build_attention_flow(db)

    # Summary stats
    pressure_count = await db.graph_edges.count_documents({"relation_type": "entity_pressure"})
    alpha_count = await db.graph_edges.count_documents({"relation_type": "alpha_source"})
    flow_count = await db.graph_edges.count_documents({"relation_type": "attention_flow"})
    state_count = await db.graph_edge_state.count_documents({})

    elapsed = round(time.time() - start, 1)

    results["summary"] = {
        "entity_pressure_edges": pressure_count,
        "alpha_source_edges": alpha_count,
        "attention_flow_edges": flow_count,
        "edge_states": state_count,
        "duration_sec": elapsed,
    }

    logger.info(f"[GraphIntel] === DONE === {elapsed}s | pressure={pressure_count}, alpha={alpha_count}, flow={flow_count}")
    return {"ok": True, **results}


async def get_intelligence_stats(db):
    """Stats for intelligence edges."""
    pressure = await db.graph_edges.count_documents({"relation_type": "entity_pressure"})
    alpha = await db.graph_edges.count_documents({"relation_type": "alpha_source"})
    flow = await db.graph_edges.count_documents({"relation_type": "attention_flow"})
    states = await db.graph_edge_state.count_documents({})

    # Top entities by pressure
    top_pressure = await db.graph_edges.find(
        {"relation_type": "entity_pressure"},
        {"_id": 0, "from_node_id": 1, "to_node_id": 1, "weight": 1,
         "metadata.unique_actors": 1}
    ).sort("weight", -1).limit(10).to_list(10)

    # Top alpha sources
    top_alpha = await db.graph_edges.find(
        {"relation_type": "alpha_source"},
        {"_id": 0, "from_node_id": 1, "to_node_id": 1, "weight": 1,
         "metadata.hit_rate": 1}
    ).sort("weight", -1).limit(10).to_list(10)

    # Decay stats
    decay_stats = {}
    pipeline = [
        {"$group": {"_id": None,
                     "avg_decay": {"$avg": "$decay_factor"},
                     "avg_current": {"$avg": "$weight_current"},
                     "avg_total": {"$avg": "$weight_total"},
                     "min_decay": {"$min": "$decay_factor"},
                     "max_decay": {"$max": "$decay_factor"}}}
    ]
    agg = await db.graph_edge_state.aggregate(pipeline).to_list(1)
    if agg:
        decay_stats = {k: round(v, 4) if isinstance(v, float) else v
                       for k, v in agg[0].items() if k != "_id"}

    # Serialize datetimes
    for item in top_pressure + top_alpha:
        for k, v in list(item.items()):
            if isinstance(v, datetime):
                item[k] = v.isoformat()

    return {
        "ok": True,
        "entity_pressure_edges": pressure,
        "alpha_source_edges": alpha,
        "attention_flow_edges": flow,
        "edge_states": states,
        "decay_stats": decay_stats,
        "top_pressure": [
            {"token": p["from_node_id"], "project": p["to_node_id"],
             "weight": p["weight"], "actors": p.get("metadata", {}).get("unique_actors", 0)}
            for p in top_pressure
        ],
        "top_alpha": [
            {"actor": a["from_node_id"], "token": a["to_node_id"],
             "weight": a["weight"], "hit_rate": a.get("metadata", {}).get("hit_rate", 0)}
            for a in top_alpha
        ],
    }
