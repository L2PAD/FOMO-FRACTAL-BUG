"""
Graph Storage Layer — Unified Schema
======================================
Manages MongoDB collections, indexes, and CRUD for:
  - graph_nodes         (registry — wallet, cluster, entity, token, exchange, etc.)
  - graph_relations      (aggregated — transfer, deposit, swap, accumulation, etc.)
  - graph_snapshots      (pre-built graph views)
  - graph_clusters       (cluster definitions — first-class nodes)
  - graph_capital_routes (capital movement routes)

All graph reads follow the cascade:
  snapshot → neighbor_cache → relations fallback → build → save
"""

from datetime import datetime, timezone

from graph_normalizer import normalize_existing_id, extract_address, VALID_NODE_TYPES, VALID_EDGE_TYPES


_db = None


def init_storage(database):
    global _db
    _db = database


async def ensure_storage_indexes():
    """Create all production indexes for graph storage collections."""
    if _db is None:
        return

    # graph_nodes — unified schema
    nodes = _db["graph_nodes"]
    await _safe_index(nodes, "id", unique=True)
    await _safe_index(nodes, "type")
    await _safe_index(nodes, "chain")
    await _safe_index(nodes, "cluster_id")
    await _safe_index(nodes, [("degree", -1)])
    await _safe_index(nodes, [("total_flow_usd", -1)])
    await _safe_index(nodes, [("last_seen", -1)])
    await _safe_index(nodes, "address")
    await _safe_index(nodes, [("label", 1)])
    await _safe_index(nodes, [("importance_score", -1)])
    await _safe_index(nodes, [("smart_money_score", -1)])
    await _safe_index(nodes, [("risk_score", -1)])
    await _safe_index(nodes, [("alpha_score", -1)])
    await _safe_index(nodes, "actor_type")
    await _safe_index(nodes, "behavior")

    # graph_relations — PACKED: one relation per (source, target, type)
    rels = _db["graph_relations"]
    await _safe_index(rels, [("source_id", 1), ("target_id", 1), ("relation_type", 1)], unique=True)
    await _safe_index(rels, [("source_id", 1), ("last_seen", -1)])
    await _safe_index(rels, [("target_id", 1), ("last_seen", -1)])
    await _safe_index(rels, "source_id")
    await _safe_index(rels, "target_id")
    await _safe_index(rels, "relation_type")
    await _safe_index(rels, "chain")
    await _safe_index(rels, [("last_seen", -1)])
    await _safe_index(rels, [("total_amount_usd", -1)])
    await _safe_index(rels, [("signal_strength", -1)])

    # graph_relation_buckets (temporal optimization)
    buckets = _db["graph_relation_buckets"]
    await _safe_index(buckets, [("source_id", 1), ("bucket_day", -1)])
    await _safe_index(buckets, [("target_id", 1), ("bucket_day", -1)])
    await _safe_index(buckets, [("bucket_day", -1)])
    await _safe_index(buckets, [("relation_type", 1), ("bucket_day", -1)])
    await _safe_index(buckets, [("chain", 1), ("bucket_day", -1)])

    # graph_snapshots
    snaps = _db["graph_snapshots"]
    await _safe_index(snaps, "snapshot_key", unique=True)
    await _safe_index(snaps, "center_node")
    await _safe_index(snaps, [("created_at", -1)])

    # graph_corridors (macro flows)
    corridors = _db["graph_corridors"]
    await _safe_index(corridors, [("source", 1), ("target", 1)])
    await _safe_index(corridors, [("total_amount_usd", -1)])
    await _safe_index(corridors, [("last_seen", -1)])

    # graph_clusters — first-class nodes
    clusters = _db["graph_clusters"]
    await _safe_index(clusters, "cluster_id", unique=True)
    await _safe_index(clusters, "type")
    await _safe_index(clusters, "cluster_type")
    await _safe_index(clusters, [("cluster_score", -1)])

    # graph_capital_routes
    routes = _db["graph_capital_routes"]
    await _safe_index(routes, "route_id", unique=True)
    await _safe_index(routes, "route_type")
    await _safe_index(routes, [("amount_usd", -1)])
    await _safe_index(routes, [("importance", -1)])
    await _safe_index(routes, "source")
    await _safe_index(routes, "destination")

    # graph_intelligence_overlay
    overlay = _db["graph_intelligence_overlay"]
    await _safe_index(overlay, "overlay_type")
    await _safe_index(overlay, "node_id")
    await _safe_index(overlay, [("created_at", -1)])


async def _safe_index(coll, keys, unique=False):
    try:
        if isinstance(keys, str):
            await coll.create_index(keys, unique=unique)
        else:
            await coll.create_index(keys, unique=unique)
    except Exception:
        pass


# ========================================================
# GRAPH NODES (Registry)
# ========================================================

async def upsert_node(node_data):
    """Upsert a node in the registry"""
    if _db is None:
        return
    node_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await _db["graph_nodes"].update_one(
        {"id": node_data["id"]},
        {"$set": node_data},
        upsert=True,
    )


async def get_node(node_id):
    """Get a single node by ID"""
    if _db is None:
        return None
    return await _db["graph_nodes"].find_one({"id": node_id}, {"_id": 0})


async def get_nodes_by_type(node_type, limit=100):
    """Get nodes by type"""
    if _db is None:
        return []
    cursor = _db["graph_nodes"].find({"type": node_type}, {"_id": 0}).limit(limit)
    return await cursor.to_list(length=limit)


# ========================================================
# GRAPH RELATIONS (Aggregated — source of truth)
# ========================================================

async def upsert_relation(rel_data):
    """Upsert an aggregated relation using packing logic.
    Uses $inc/$min/$max to merge into a single document per (source, target, type)."""
    if _db is None:
        return
    source_id = rel_data["source_id"]
    target_id = rel_data["target_id"]
    relation_type = rel_data.get("relation_type", "transfer")

    update_ops = {
        "$inc": {
            "total_tx_count": rel_data.get("tx_count", rel_data.get("total_tx_count", 1)),
            "total_amount_usd": rel_data.get("total_amount_usd", 0),
        },
        "$min": {},
        "$max": {},
        "$set": {
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        "$setOnInsert": {
            "source_id": source_id,
            "target_id": target_id,
            "relation_type": relation_type,
            "chain": rel_data.get("chain", "ethereum"),
        },
    }

    first_seen = rel_data.get("first_seen")
    if first_seen is not None:
        update_ops["$min"]["first_seen"] = first_seen
    last_seen = rel_data.get("last_seen")
    if last_seen is not None:
        update_ops["$max"]["last_seen"] = last_seen

    # Clean empty operators
    if not update_ops["$min"]:
        del update_ops["$min"]
    if not update_ops["$max"]:
        del update_ops["$max"]

    # Merge extra fields into $set (tags, confidence, direction, flow_direction, etc.)
    for key in ("tags", "confidence", "direction", "flow_direction", "route_role", "signal_strength", "lead_time"):
        if key in rel_data and rel_data[key]:
            update_ops["$set"][key] = rel_data[key]

    await _db["graph_relations"].update_one(
        {"source_id": source_id, "target_id": target_id, "relation_type": relation_type},
        update_ops,
        upsert=True,
    )


async def upsert_relation_bulk(rel_data):
    """Legacy upsert — full $set replacement for seed/migration scripts."""
    if _db is None:
        return
    rel_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await _db["graph_relations"].update_one(
        {
            "source_id": rel_data["source_id"],
            "target_id": rel_data["target_id"],
            "relation_type": rel_data["relation_type"],
        },
        {"$set": rel_data},
        upsert=True,
    )


async def get_relations_for_node(node_id, limit=400, start_time=None, end_time=None):
    """Get all relations involving a node (as source or target), with optional time filter.
    Uses relation_buckets for temporal queries, falls back to relations layer."""
    if _db is None:
        return []

    canonical_id = normalize_existing_id(node_id)
    is_temporal = start_time or end_time

    # For temporal queries, try relation_buckets first (faster)
    if is_temporal:
        results = await _get_from_buckets(canonical_id, limit, start_time, end_time)
        if results:
            return results

    # Standard: query aggregated relations
    query = {"$or": [{"source_id": canonical_id}, {"target_id": canonical_id}]}
    if is_temporal:
        time_filter = {}
        if start_time:
            time_filter["$gte"] = start_time
        if end_time:
            time_filter["$lte"] = end_time
        query["last_seen"] = time_filter

    cursor = _db["graph_relations"].find(query, {"_id": 0}).limit(limit)
    results = await cursor.to_list(length=limit)

    # Fallback: address-based search if exact match returns nothing
    if not results:
        address = extract_address(canonical_id)
        if address and len(address) > 10:
            addr_query = {"$or": [
                {"source_id": {"$regex": f":{address}:", "$options": "i"}},
                {"target_id": {"$regex": f":{address}:", "$options": "i"}},
            ]}
            if is_temporal:
                addr_query["last_seen"] = time_filter
            cursor2 = _db["graph_relations"].find(addr_query, {"_id": 0}).limit(limit)
            results = await cursor2.to_list(length=limit)

    return results


async def _get_from_buckets(node_id, limit, start_time, end_time):
    """Query relation_buckets for temporal data. Returns relations in standard format."""
    if _db is None:
        return []

    query = {"$or": [{"source_id": node_id}, {"target_id": node_id}]}

    # Convert timestamps to bucket_day range
    if start_time:
        start_day = datetime.fromtimestamp(start_time, tz=timezone.utc).strftime("%Y-%m-%d")
        query.setdefault("bucket_day", {})["$gte"] = start_day
    if end_time:
        end_day = datetime.fromtimestamp(end_time, tz=timezone.utc).strftime("%Y-%m-%d")
        query.setdefault("bucket_day", {})["$lte"] = end_day

    cursor = _db["graph_relation_buckets"].find(query, {"_id": 0}).limit(limit)
    return await cursor.to_list(length=limit)


async def build_graph_from_relations(center_node_id, depth=2, limit_nodes=150, limit_edges=400, start_time=None, end_time=None, chains=None):
    """
    Build a graph by traversing relations from a center node.
    Returns (nodes, edges) in unified format.

    Args:
        chains: Optional list of chain keys (e.g., ['ethereum', 'arbitrum']). If provided,
                only include relations within those chains. Edges NEVER cross chains.
    """
    if _db is None:
        return [], []

    visited_nodes = set()
    all_edges = []
    frontier = {center_node_id}

    for _ in range(depth):
        if not frontier:
            break
        new_frontier = set()
        for nid in frontier:
            if nid in visited_nodes:
                continue
            visited_nodes.add(nid)

            rels = await get_relations_for_node(nid, limit=limit_edges, start_time=start_time, end_time=end_time)
            for rel in rels:
                # Chain isolation: skip relations from other chains
                rel_chain = rel.get("chain", "ethereum")
                if chains and rel_chain not in chains:
                    continue
                # Cross-chain edge guard: source and target must be on same chain
                src_chain = rel.get("source_id", "").rsplit(":", 1)[-1] if ":" in rel.get("source_id", "") else rel_chain
                tgt_chain = rel.get("target_id", "").rsplit(":", 1)[-1] if ":" in rel.get("target_id", "") else rel_chain
                if src_chain != tgt_chain:
                    continue
                all_edges.append(rel)
                other = rel["target_id"] if rel["source_id"] == nid else rel["source_id"]
                if other not in visited_nodes:
                    new_frontier.add(other)

            if len(visited_nodes) >= limit_nodes:
                break
        frontier = new_frontier
        if len(visited_nodes) >= limit_nodes:
            break

    # Deduplicate edges
    seen_edges = set()
    unique_edges = []
    for e in all_edges:
        edge_key = f"{e['source_id']}:{e['target_id']}:{e.get('relation_type', '')}"
        if edge_key not in seen_edges:
            seen_edges.add(edge_key)
            unique_edges.append(e)
        if len(unique_edges) >= limit_edges:
            break

    # Build node list
    node_ids = set()
    for e in unique_edges:
        node_ids.add(e["source_id"])
        node_ids.add(e["target_id"])

    nodes = []
    for nid in node_ids:
        node_doc = await get_node(nid)
        if node_doc:
            nodes.append(node_doc)
        else:
            # Create minimal node from ID: type:address:chain
            parts = nid.split(":")
            nodes.append({
                "id": nid,
                "type": parts[0] if parts else "wallet",
                "label": nid,
                "chain": parts[2] if len(parts) > 2 else "ethereum",
            })

    # Convert relations to edges
    edges = []
    for rel in unique_edges:
        edge = {
            "id": f"{rel['source_id']}-{rel['target_id']}-{rel.get('relation_type', 'transfer')}",
            "source": rel["source_id"],
            "target": rel["target_id"],
            "direction": rel.get("direction", "out"),
            "type": rel.get("relation_type", "transfer"),
            "amountUsd": rel.get("total_amount_usd", 0),
            "txCount": rel.get("total_tx_count", rel.get("tx_count", 0)),
            "timestamp": rel.get("last_seen"),
            "chain": rel.get("chain", "ethereum"),
            "tags": rel.get("tags", []),
            "confidence": rel.get("confidence", 0),
            "flowDirection": rel.get("flow_direction", ""),
            "routeRole": rel.get("route_role", ""),
            "signalStrength": rel.get("signal_strength", 0),
            "leadTime": rel.get("lead_time", 0),
        }
        edges.append(edge)

    return nodes, edges


# ========================================================
# GRAPH SNAPSHOTS (Pre-built graph views)
# ========================================================

async def get_snapshot(snapshot_key):
    """Get a pre-built snapshot"""
    if _db is None:
        return None
    return await _db["graph_snapshots"].find_one({"snapshot_key": snapshot_key}, {"_id": 0})


async def save_snapshot(snapshot_key, center_node, nodes, edges, corridors=None):
    """Save a pre-built graph snapshot"""
    if _db is None:
        return
    doc = {
        "snapshot_key": snapshot_key,
        "center_node": center_node,
        "nodes": nodes,
        "edges": edges,
        "corridors": corridors or [],
        "node_count": len(nodes),
        "edge_count": len(edges),
        "corridor_count": len(corridors or []),
        "created_at": datetime.now(timezone.utc),
    }
    await _db["graph_snapshots"].update_one(
        {"snapshot_key": snapshot_key},
        {"$set": doc},
        upsert=True,
    )


async def invalidate_snapshot(center_node):
    """Invalidate all snapshots for a center node"""
    if _db is None:
        return 0
    result = await _db["graph_snapshots"].delete_many({"center_node": center_node})
    return result.deleted_count


# ========================================================
# GRAPH CLUSTERS (Structure only — no engine)
# ========================================================

async def upsert_cluster(cluster_data):
    """Upsert a cluster definition"""
    if _db is None:
        return
    cluster_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await _db["graph_clusters"].update_one(
        {"cluster_id": cluster_data["cluster_id"]},
        {"$set": cluster_data},
        upsert=True,
    )


async def get_clusters(limit=100):
    """Get all cluster definitions"""
    if _db is None:
        return []
    cursor = _db["graph_clusters"].find({}, {"_id": 0}).limit(limit)
    return await cursor.to_list(length=limit)


# ========================================================
# STORAGE STATS
# ========================================================

async def get_storage_stats():
    """Get counts of all graph storage collections"""
    if _db is None:
        return {}
    return {
        "graph_nodes": await _db["graph_nodes"].count_documents({}),
        "graph_relations": await _db["graph_relations"].count_documents({}),
        "graph_snapshots": await _db["graph_snapshots"].count_documents({}),
        "graph_clusters": await _db["graph_clusters"].count_documents({}),
        "graph_neighbors_cache": await _db["graph_neighbors_cache"].count_documents({}),
        "graph_anchor_entities": await _db["graph_anchor_entities"].count_documents({}),
        "graph_capital_routes": await _db["graph_capital_routes"].count_documents({}),
        "graph_intelligence_overlay": await _db["graph_intelligence_overlay"].count_documents({}),
    }


# ========================================================
# CAPITAL ROUTES
# ========================================================

async def upsert_route(route_data):
    """Upsert a capital route"""
    if _db is None:
        return
    route_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await _db["graph_capital_routes"].update_one(
        {"route_id": route_data["route_id"]},
        {"$set": route_data},
        upsert=True,
    )


async def get_routes(route_type=None, sort_by="amount_usd", limit=50):
    """Get capital routes, optionally filtered by type"""
    if _db is None:
        return []
    query = {}
    if route_type:
        query["route_type"] = route_type
    cursor = _db["graph_capital_routes"].find(
        query, {"_id": 0}
    ).sort(sort_by, -1).limit(limit)
    return await cursor.to_list(length=limit)


async def get_routes_for_node(node_id, limit=20):
    """Get all routes involving a node"""
    if _db is None:
        return []
    cursor = _db["graph_capital_routes"].find(
        {"$or": [{"source": node_id}, {"destination": node_id}, {"via": node_id}]},
        {"_id": 0}
    ).sort("amount_usd", -1).limit(limit)
    return await cursor.to_list(length=limit)


# ========================================================
# INTELLIGENCE OVERLAY
# ========================================================

async def upsert_overlay(overlay_data):
    """Upsert an intelligence overlay entry"""
    if _db is None:
        return
    overlay_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    key = overlay_data.get("overlay_id", f"{overlay_data.get('overlay_type','')}:{overlay_data.get('node_id','')}")
    await _db["graph_intelligence_overlay"].update_one(
        {"overlay_id": key},
        {"$set": {**overlay_data, "overlay_id": key}},
        upsert=True,
    )


async def get_overlays(overlay_type=None, node_id=None, limit=50):
    """Get intelligence overlay entries"""
    if _db is None:
        return []
    query = {}
    if overlay_type:
        query["overlay_type"] = overlay_type
    if node_id:
        query["node_id"] = node_id
    cursor = _db["graph_intelligence_overlay"].find(
        query, {"_id": 0}
    ).sort("updated_at", -1).limit(limit)
    return await cursor.to_list(length=limit)


# ========================================================
# BULK NODE ENRICHMENT
# ========================================================

async def enrich_node(node_id, fields):
    """Enrich an existing node with additional fields (preserves existing data)"""
    if _db is None:
        return
    fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    await _db["graph_nodes"].update_one(
        {"id": node_id},
        {"$set": fields},
    )


async def get_nodes_by_ids(node_ids, projection=None):
    """Get multiple nodes by their IDs"""
    if _db is None:
        return []
    proj = projection or {"_id": 0}
    cursor = _db["graph_nodes"].find({"id": {"$in": node_ids}}, proj)
    return await cursor.to_list(length=len(node_ids))
