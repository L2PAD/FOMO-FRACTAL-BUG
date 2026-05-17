"""
Graph Core API — Unified Intelligence Platform
=================================================
Full graph API with projection layer, data integration,
cluster layer, capital routes, and intelligence overlay.
"""

from fastapi import APIRouter, Query
from datetime import datetime, timezone
import time
from corridor_detector import detect_corridors
from edge_tagger import tag_edges
from graph_normalizer import normalize_node_id, normalize_existing_id
from infura_fallback import init_infura_fallback, infura_fallback_for_node
from liquidity_map_service import build_liquidity_map
from route_intelligence_service import build_route_intelligence, build_entity_route_intelligence
from wash_detection import run_detection as run_wash_detection
from exposure_service import compute_exposure
from risk_scoring_service import compute_risk
from cluster_engine import run_clustering
from smart_money_detector import detect_smart_money
from flow_signal_engine import generate_flow_signals
from liquidity_pressure_engine import compute_pressure
from narrative_detector import detect_narratives
from graph_projection_service import project_graph
from graph_data_integrator import run_full_integration
from discovery_service import discover_seeds
from cluster_layer import run_cluster_layer
from capital_routes_service import run_capital_routes, get_routes_ranked
from intelligence_overlay import run_intelligence_overlay
from identity_resolver_service import (
    run_identity_resolver, resolve_wallet, resolve_identity,
    get_cluster_wallets, get_entity_wallets, get_entity_clusters,
)
from graph_context_service import run_context_layer, get_context, get_context_for_node
from smart_wallet_service import compute_smart_wallet_rankings, get_top_clusters, get_top_capital_routes
from graph_playback_service import get_playback_frames, get_playback_events
from edge_lane_service import aggregate_lanes, build_render_edges
import graph_storage as storage

router = APIRouter(prefix="/api/graph-core", tags=["graph-core"])

_db = None

# In-memory cache stats (reset on restart)
_cache_stats = {
    "hits": 0,
    "misses": 0,
    "build_times_ms": [],  # last 100 build times
}

MAX_BUILD_TIMES = 100
CACHE_TTL_SECONDS = 600  # 10 minutes
CACHE_SIZE_GUARD = 500   # skip cache if > 500 nodes


def init_graph_core(database):
    global _db
    _db = database
    storage.init_storage(database)
    init_infura_fallback(database)


async def _ensure_cache_indexes():
    """Create TTL and lookup indexes on graph_neighbors_cache"""
    coll = _db["graph_neighbors_cache"]
    try:
        await coll.create_index("created_at", expireAfterSeconds=CACHE_TTL_SECONDS)
    except Exception:
        pass
    try:
        await coll.create_index("cache_key", unique=True)
    except Exception:
        pass
    try:
        await coll.create_index("node_id")
    except Exception:
        pass


def _build_cache_key(node_id: str, depth: int, limit_nodes: int, limit_edges: int) -> str:
    return f"{node_id}:{depth}:{limit_nodes}:{limit_edges}"


def _record_build_time(ms: float):
    _cache_stats["build_times_ms"].append(ms)
    if len(_cache_stats["build_times_ms"]) > MAX_BUILD_TIMES:
        _cache_stats["build_times_ms"] = _cache_stats["build_times_ms"][-MAX_BUILD_TIMES:]




# ========================================================
# SEARCH / RESOLVE: Find a graph_node by label or address
# ========================================================

@router.get("/search/suggest")
async def search_suggest(
    q: str = Query(..., min_length=2, description="Search prefix"),
    limit: int = Query(default=10, ge=1, le=30),
):
    """Auto-suggest: prefix search on graph_nodes labels and anchor entities."""
    if _db is None:
        return {"results": [], "query": q}

    q_lower = q.strip().lower()
    results = []
    seen = set()

    # 1. Search anchor entities by label prefix (highest priority)
    anchor_cursor = _db["graph_anchor_entities"].find(
        {"label": {"$regex": f"^{q_lower}", "$options": "i"}},
        {"_id": 0}
    ).limit(limit)
    async for a in anchor_cursor:
        addr = a.get("address", "").lower()
        atype = a.get("type", "wallet")
        chain = a.get("chain", "ethereum")
        node_id = normalize_node_id(atype, addr, chain)
        if node_id not in seen:
            seen.add(node_id)
            results.append({
                "node_id": node_id,
                "label": a.get("label", "").replace("_", " "),
                "type": atype,
                "chain": chain,
            })

    # 2. Search graph_nodes by label prefix (lower priority)
    if len(results) < limit:
        remaining = limit - len(results)
        node_cursor = _db["graph_nodes"].find(
            {"label": {"$regex": f"^{q_lower}", "$options": "i"}},
            {"_id": 0, "id": 1, "label": 1, "type": 1, "chain": 1, "degree": 1}
        ).sort("degree", -1).limit(remaining)
        async for n in node_cursor:
            nid = n.get("id", "")
            if nid not in seen:
                seen.add(nid)
                results.append({
                    "node_id": nid,
                    "label": n.get("label", "").replace("_", " "),
                    "type": n.get("type", "wallet"),
                    "chain": n.get("chain", "ethereum"),
                })

    # 3. Search graph_nodes by label contains (if still few results)
    if len(results) < limit:
        remaining = limit - len(results)
        contains_cursor = _db["graph_nodes"].find(
            {"label": {"$regex": q_lower, "$options": "i"}, "id": {"$nin": list(seen)}},
            {"_id": 0, "id": 1, "label": 1, "type": 1, "chain": 1, "degree": 1}
        ).sort("degree", -1).limit(remaining)
        async for n in contains_cursor:
            nid = n.get("id", "")
            if nid not in seen:
                seen.add(nid)
                results.append({
                    "node_id": nid,
                    "label": n.get("label", "").replace("_", " "),
                    "type": n.get("type", "wallet"),
                    "chain": n.get("chain", "ethereum"),
                })

    # 4. Address prefix match
    if len(results) < limit and q_lower.startswith("0x") and len(q_lower) >= 4:
        remaining = limit - len(results)
        addr_cursor = _db["graph_nodes"].find(
            {"address": {"$regex": f"^{q_lower}", "$options": "i"}, "id": {"$nin": list(seen)}},
            {"_id": 0, "id": 1, "label": 1, "type": 1, "chain": 1}
        ).limit(remaining)
        async for n in addr_cursor:
            nid = n.get("id", "")
            if nid not in seen:
                seen.add(nid)
                results.append({
                    "node_id": nid,
                    "label": n.get("label", "").replace("_", " "),
                    "type": n.get("type", "wallet"),
                    "chain": n.get("chain", "ethereum"),
                })

    return {"results": results, "count": len(results), "query": q}


@router.get("/resolve")
async def resolve_node(q: str = Query(..., description="Search query: label, address, or partial match")):
    """Resolve a search query to a graph_node and return its canonical node_id."""
    if _db is None:
        return {"found": False, "query": q}

    q_lower = q.strip().lower()

    # 1. Exact address match
    if q_lower.startswith("0x") and len(q_lower) >= 10:
        node = await _db["graph_nodes"].find_one({"address": q_lower}, {"_id": 0})
        if node:
            return {"found": True, "node_id": node["id"], "label": node.get("label", ""), "type": node.get("type", "wallet")}
        # If no node, create a temporary wallet node_id
        node_id = normalize_node_id("wallet", q_lower, "ethereum")
        return {"found": True, "node_id": node_id, "label": q_lower[:10] + "...", "type": "wallet"}

    # 2. Exact label match in anchor entities
    anchor = await _db["graph_anchor_entities"].find_one(
        {"label": {"$regex": f"^{q_lower}$", "$options": "i"}}, {"_id": 0}
    )
    if anchor:
        addr = anchor.get("address", "").lower()
        atype = anchor.get("type", "wallet")
        chain = anchor.get("chain", "ethereum")
        node_id = normalize_node_id(atype, addr, chain)
        return {"found": True, "node_id": node_id, "label": anchor.get("label", ""), "type": atype}

    # 3. Fuzzy label match in graph_nodes
    node = await _db["graph_nodes"].find_one(
        {"label": {"$regex": q_lower, "$options": "i"}}, {"_id": 0}
    )
    if node:
        return {"found": True, "node_id": node["id"], "label": node.get("label", ""), "type": node.get("type", "wallet")}

    # 4. Not found — try constructing a wallet node_id
    return {"found": False, "query": q}


# ========================================================
# P1: NEIGHBOR CACHE
# ========================================================

@router.get("/neighbors/{node_id:path}")
async def get_neighbors_cached(
    node_id: str,
    depth: int = Query(default=2, ge=1, le=3),
    limit_nodes: int = Query(default=150, ge=1, le=500),
    limit_edges: int = Query(default=400, ge=1, le=1500),
    start_time: int = Query(default=None, description="Temporal filter: start timestamp"),
    end_time: int = Query(default=None, description="Temporal filter: end timestamp"),
):
    """
    Get graph neighbors — 3-tier cascade:
    1. graph_snapshots (pre-built)
    2. graph_neighbors_cache (TTL)
    3. graph_relations → build → tag → detect corridors → save
    
    Supports temporal filtering via start_time/end_time.
    """
    if _db is None:
        return {"nodes": [], "edges": [], "corridors": [], "cached": False, "error": "no_database"}

    await _ensure_cache_indexes()
    await storage.ensure_storage_indexes()

    # Normalize node_id to canonical format
    node_id = normalize_existing_id(node_id)

    cache_key = _build_cache_key(node_id, depth, limit_nodes, limit_edges)
    is_temporal = start_time is not None or end_time is not None

    # 1. Check snapshot (skip if temporal query)
    if not is_temporal:
        snapshot = await storage.get_snapshot(cache_key)
        if snapshot:
            _cache_stats["hits"] += 1
            return {
                "nodes": snapshot.get("nodes", []),
                "edges": snapshot.get("edges", []),
                "corridors": snapshot.get("corridors", []),
                "node_count": snapshot.get("node_count", 0),
                "edge_count": snapshot.get("edge_count", 0),
                "corridor_count": snapshot.get("corridor_count", 0),
                "cached": True,
                "source": "snapshot",
                "cache_key": cache_key,
            }

    # 2. Check neighbor cache (skip if temporal query)
    if not is_temporal:
        cached = await _db["graph_neighbors_cache"].find_one(
            {"cache_key": cache_key}, {"_id": 0}
        )
        if cached:
            _cache_stats["hits"] += 1
            return {
                "nodes": cached.get("nodes", []),
                "edges": cached.get("edges", []),
                "corridors": cached.get("corridors", []),
                "node_count": cached.get("node_count", 0),
                "edge_count": cached.get("edge_count", 0),
                "corridor_count": cached.get("corridor_count", 0),
                "cached": True,
                "source": "cache",
                "cache_key": cache_key,
            }

    # 3. Cache miss — build from relations first, then KG fallback
    _cache_stats["misses"] += 1
    build_start = time.time()

    # Try relations layer first
    nodes, edges = await storage.build_graph_from_relations(
        node_id, depth=depth, limit_nodes=limit_nodes, limit_edges=limit_edges,
        start_time=start_time, end_time=end_time,
    )

    # If relations empty, try Infura RPC fallback (Ethereum mainnet)
    if not nodes and not edges:
        from graph_normalizer import parse_node_id
        ntype, _, nchain = parse_node_id(node_id)
        nodes, edges = await infura_fallback_for_node(node_id, ntype, nchain)

    # If still empty, fall back to knowledge_graph service
    if not nodes and not edges:
        nodes, edges = await _build_neighbor_graph(node_id, depth, limit_nodes, limit_edges)

    # P2: Edge tagging
    node_map = {n.get("id", ""): n for n in nodes}
    edges = tag_edges(edges, node_map)

    # P2: Corridor detection
    corridors = detect_corridors(nodes, edges)

    build_ms = round((time.time() - build_start) * 1000, 1)
    _record_build_time(build_ms)

    # Save to cache (skip temporal queries and empty results)
    if not is_temporal and nodes and len(nodes) <= CACHE_SIZE_GUARD:
        cache_doc = {
            "cache_key": cache_key,
            "node_id": node_id,
            "nodes": nodes,
            "edges": edges,
            "corridors": corridors,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "corridor_count": len(corridors),
            "created_at": datetime.now(timezone.utc),
        }
        try:
            await _db["graph_neighbors_cache"].update_one(
                {"cache_key": cache_key}, {"$set": cache_doc}, upsert=True,
            )
        except Exception:
            pass

    return {
        "nodes": nodes,
        "edges": edges,
        "corridors": corridors,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "corridor_count": len(corridors),
        "cached": False,
        "source": "build",
        "build_time_ms": build_ms,
        "cache_key": cache_key,
    }


async def _build_neighbor_graph(node_id: str, depth: int, limit_nodes: int, limit_edges: int):
    """
    Build neighbor graph from existing knowledge_graph query service.
    Falls back to direct MongoDB query if service not available.
    """
    try:
        from knowledge_graph.query_service import GraphQueryService
        qs = GraphQueryService(_db)

        # Parse node_id: type:identifier:chain → type, identifier
        parts = node_id.split(":")
        entity_type = parts[0] if len(parts) >= 1 else "wallet"
        entity_id = ":".join(parts[1:]) if len(parts) >= 2 else node_id

        network = await qs.get_network(
            center_type=entity_type,
            center_id=entity_id,
            depth=depth,
            limit_nodes=limit_nodes,
            limit_edges=limit_edges,
        )

        # Serialize nodes/edges (strip _id, convert ObjectId)
        nodes = []
        for n in (network.nodes if hasattr(network, 'nodes') else []):
            nd = n if isinstance(n, dict) else n.__dict__
            nd.pop("_id", None)
            # Ensure all values are JSON serializable
            nodes.append({k: str(v) if not isinstance(v, (str, int, float, bool, list, dict, type(None))) else v for k, v in nd.items()})

        edges = []
        for e in (network.edges if hasattr(network, 'edges') else []):
            ed = e if isinstance(e, dict) else e.__dict__
            ed.pop("_id", None)
            edges.append({k: str(v) if not isinstance(v, (str, int, float, bool, list, dict, type(None))) else v for k, v in ed.items()})

        return nodes, edges

    except Exception as e:
        print(f"[GraphCore] Neighbor build error: {e}")
        # Fallback: try direct edge query
        return await _build_neighbor_direct(node_id, limit_nodes, limit_edges)


async def _build_neighbor_direct(node_id: str, limit_nodes: int, limit_edges: int):
    """Direct MongoDB fallback for building neighbors"""
    try:
        edges_coll = _db["graph_edges"]
        nodes_coll = _db["graph_nodes"]

        edge_cursor = edges_coll.find(
            {"$or": [{"from_node_id": {"$regex": node_id, "$options": "i"}},
                     {"to_node_id": {"$regex": node_id, "$options": "i"}}]},
            {"_id": 0}
        ).limit(limit_edges)
        edges = await edge_cursor.to_list(length=limit_edges)

        # Collect neighbor IDs
        neighbor_ids = set()
        for e in edges:
            neighbor_ids.add(e.get("from_node_id", ""))
            neighbor_ids.add(e.get("to_node_id", ""))
        neighbor_ids.discard("")

        if neighbor_ids:
            node_cursor = nodes_coll.find(
                {"id": {"$in": list(neighbor_ids)}},
                {"_id": 0}
            ).limit(limit_nodes)
            nodes = await node_cursor.to_list(length=limit_nodes)
        else:
            nodes = []

        return nodes, edges
    except Exception as e:
        print(f"[GraphCore] Direct neighbor build error: {e}")
        return [], []


@router.post("/cache/invalidate/{node_id:path}")
async def invalidate_cache(node_id: str):
    """Invalidate all cache entries for a specific node_id"""
    if _db is None:
        return {"invalidated": 0, "error": "no_database"}

    result = await _db["graph_neighbors_cache"].delete_many({"node_id": node_id})
    return {"invalidated": result.deleted_count, "node_id": node_id}


@router.post("/cache/invalidate-all")
async def invalidate_all_cache():
    """Flush the entire neighbor cache"""
    if _db is None:
        return {"invalidated": 0, "error": "no_database"}

    result = await _db["graph_neighbors_cache"].delete_many({})
    _cache_stats["hits"] = 0
    _cache_stats["misses"] = 0
    _cache_stats["build_times_ms"] = []
    return {"invalidated": result.deleted_count}


# ========================================================
# HEALTH (enhanced with cache stats)
# ========================================================

@router.get("/health")
async def graph_health():
    """Graph health endpoint — key metrics including cache, storage, and performance"""
    if _db is None:
        return {"status": "no_database", "node_count": 0, "edge_count": 0}

    start = time.time()

    # Storage stats
    storage_stats = await storage.get_storage_stats()

    latency_ms = round((time.time() - start) * 1000, 1)

    total_requests = _cache_stats["hits"] + _cache_stats["misses"]
    hit_rate = round(_cache_stats["hits"] / total_requests, 2) if total_requests > 0 else 0.0
    build_times = _cache_stats["build_times_ms"]
    avg_build_ms = round(sum(build_times) / len(build_times), 1) if build_times else 0.0

    return {
        "status": "ok",
        "storage": storage_stats,
        "cache_entries": storage_stats.get("graph_neighbors_cache", 0),
        "cache_hit_rate": hit_rate,
        "cache_hits": _cache_stats["hits"],
        "cache_misses": _cache_stats["misses"],
        "avg_graph_build_time_ms": avg_build_ms,
        "query_latency_ms": latency_ms,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/snapshots/build")
async def trigger_snapshot_build():
    """Trigger snapshot build for all anchor entities"""
    if _db is None:
        return {"error": "no_database"}

    anchors = []
    cursor = _db["graph_anchor_entities"].find({}, {"_id": 0})
    async for doc in cursor:
        anchors.append(doc)

    built = 0
    for anchor in anchors:
        addr = anchor.get("address", "").lower()
        atype = anchor.get("type", "wallet")
        chain = anchor.get("chain", "ethereum")

        node_id = normalize_node_id(atype, addr, chain)
        snapshot_key = f"{node_id}:2:150:400"

        existing = await storage.get_snapshot(snapshot_key)
        if existing:
            continue

        nodes, edges = await storage.build_graph_from_relations(
            node_id, depth=2, limit_nodes=150, limit_edges=400
        )
        if not nodes and not edges:
            nodes, edges = await infura_fallback_for_node(node_id, atype, chain)
        if not nodes and not edges:
            nodes, edges = await _build_neighbor_graph(node_id, 2, 150, 400)

        node_map = {n.get("id", ""): n for n in nodes}
        edges = tag_edges(edges, node_map)
        corridors = detect_corridors(nodes, edges)

        await storage.save_snapshot(snapshot_key, node_id, nodes, edges, corridors)
        built += 1

    return {"built": built, "total_anchors": len(anchors)}


# ========================================================
# P3.4: CLUSTER STRUCTURE (reference model, no engine)
# ========================================================

@router.get("/clusters")
async def get_clusters():
    """List all cluster definitions"""
    if _db is None:
        return {"clusters": [], "count": 0}
    clusters = []
    cursor = _db["graph_clusters"].find({}, {"_id": 0}).limit(200)
    async for doc in cursor:
        # Count members via graph_nodes.cluster_id
        member_count = await _db["graph_nodes"].count_documents({"cluster_id": doc.get("cluster_id")})
        doc["member_count"] = member_count
        clusters.append(doc)
    return {"clusters": clusters, "count": len(clusters)}


@router.post("/clusters")
async def upsert_cluster(data: dict):
    """Create or update a cluster definition (reference model — members stored in graph_nodes.cluster_id)"""
    if _db is None:
        return {"error": "no_database"}

    cluster_id = data.get("cluster_id")
    if not cluster_id:
        return {"error": "cluster_id is required"}

    doc = {
        "cluster_id": cluster_id,
        "type": data.get("type", "institution"),
        "label": data.get("label", cluster_id),
        "confidence": data.get("confidence", 0.0),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await _db["graph_clusters"].update_one(
        {"cluster_id": cluster_id}, {"$set": doc}, upsert=True,
    )

    # If member_ids provided, update those nodes' cluster_id
    member_ids = data.get("member_ids", [])
    if member_ids:
        await _db["graph_nodes"].update_many(
            {"id": {"$in": member_ids}},
            {"$set": {"cluster_id": cluster_id}},
        )

    return {"cluster_id": cluster_id, "members_updated": len(member_ids)}


@router.get("/clusters/{cluster_id}/members")
async def get_cluster_members(cluster_id: str):
    """Get all nodes belonging to a cluster"""
    if _db is None:
        return {"members": [], "count": 0}
    cursor = _db["graph_nodes"].find({"cluster_id": cluster_id}, {"_id": 0}).limit(500)
    members = await cursor.to_list(length=500)
    return {"cluster_id": cluster_id, "members": members, "count": len(members)}


# ========================================================
# P3.5: CORRIDOR AGGREGATION + ACTIVE CORRIDORS
# ========================================================

@router.get("/corridors/active")
async def get_active_corridors(
    limit: int = Query(default=20, ge=1, le=100),
    min_value: float = Query(default=0, ge=0),
):
    """
    Get aggregated active corridors — macro flows.
    Primary: reads from pre-computed graph_corridors collection.
    Fallback: aggregates from snapshot/cache corridor data.
    """
    if _db is None:
        return {"corridors": [], "count": 0}

    # Primary: read from graph_corridors (pre-computed by build_corridors.py)
    cursor = _db["graph_corridors"].find(
        {"total_amount_usd": {"$gte": min_value}} if min_value > 0 else {},
        {"_id": 0}
    ).sort("total_amount_usd", -1).limit(limit)
    precomputed = await cursor.to_list(length=limit)

    if precomputed:
        result = []
        for c in precomputed:
            result.append({
                "source": c.get("source", ""),
                "target": c.get("target", ""),
                "source_label": c.get("source_label", ""),
                "target_label": c.get("target_label", ""),
                "bridge_label": c.get("bridge") or "",
                "source_type": c.get("source_type", ""),
                "target_type": c.get("target_type", ""),
                "corridor_count": c.get("corridor_count", 0),
                "total_amount_usd": c.get("total_amount_usd", 0),
                "last_seen": c.get("last_seen", 0),
                "chains": [c.get("chain", "ethereum")] if c.get("chain") else ["ethereum"],
            })
        return {"corridors": result, "count": len(result)}

    # Fallback: aggregate from snapshots + cache (legacy behavior)
    raw_corridors = []
    snap_cursor = _db["graph_snapshots"].find(
        {"corridor_count": {"$gt": 0}},
        {"_id": 0, "corridors": 1}
    )
    async for snap in snap_cursor:
        for c in snap.get("corridors", []):
            if (c.get("amountUsd") or 0) >= min_value:
                raw_corridors.append(c)

    cache_cursor = _db["graph_neighbors_cache"].find(
        {"corridor_count": {"$gt": 0}},
        {"_id": 0, "corridors": 1}
    )
    async for cached in cache_cursor:
        for c in cached.get("corridors", []):
            if (c.get("amountUsd") or 0) >= min_value:
                raw_corridors.append(c)

    # Aggregate by source→target
    agg_map = {}
    for c in raw_corridors:
        key = f"{c.get('source', '')}→{c.get('target', '')}"
        if key not in agg_map:
            agg_map[key] = {
                "source": c.get("source", ""),
                "target": c.get("target", ""),
                "pattern": c.get("pattern", ""),
                "corridor_count": 0,
                "total_amount_usd": 0,
                "chains": set(),
            }
        entry = agg_map[key]
        entry["corridor_count"] += 1
        entry["total_amount_usd"] += c.get("amountUsd", 0)
        for ch in c.get("chains", []):
            entry["chains"].add(ch)

    # Resolve labels
    anchor_labels = {}
    a_cursor = _db["graph_anchor_entities"].find({}, {"_id": 0, "address": 1, "label": 1, "type": 1})
    async for a in a_cursor:
        addr = a.get("address", "").lower()
        anchor_labels[addr] = a.get("label", "")
        anchor_labels[f"{a.get('type', '')}:{addr}"] = a.get("label", "")

    def _resolve_label(node_id):
        if node_id in anchor_labels:
            return anchor_labels[node_id]
        parts = node_id.split(":")
        if len(parts) >= 2:
            if parts[1].lower() in anchor_labels:
                return anchor_labels[parts[1].lower()]
        if len(parts) >= 2 and parts[1].startswith("0x"):
            return f"{parts[0].upper()} {parts[1][:6]}...{parts[1][-4:]}"
        return node_id

    result = []
    for entry in sorted(agg_map.values(), key=lambda x: x["total_amount_usd"], reverse=True)[:limit]:
        result.append({
            "source": entry["source"],
            "target": entry["target"],
            "source_label": _resolve_label(entry["source"]),
            "target_label": _resolve_label(entry["target"]),
            "bridge_label": "",
            "pattern": entry["pattern"],
            "corridor_count": entry["corridor_count"],
            "total_amount_usd": entry["total_amount_usd"],
            "chains": list(entry["chains"]),
        })

    return {"corridors": result, "count": len(result)}


# ========================================================
# P0: ANCHOR ENTITIES
# ========================================================

@router.get("/anchor-entities")
async def get_anchor_entities():
    """Return all seeded anchor entities"""
    if _db is None:
        return {"entities": [], "count": 0}

    entities = []
    cursor = _db["graph_anchor_entities"].find({}, {"_id": 0})
    async for doc in cursor:
        entities.append(doc)

    return {"entities": entities, "count": len(entities)}


@router.post("/seed-anchors")
async def seed_anchor_entities():
    """Seed anchor entities from the predefined list"""
    if _db is None:
        return {"error": "no database", "seeded": 0}

    anchors = [
        {"type": "dex", "label": "Uniswap", "chain": "ethereum", "address": "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984"},
        {"type": "dex", "label": "Curve", "chain": "ethereum", "address": "0xD533a949740bb3306d119CC777fa900bA034cd52"},
        {"type": "dex", "label": "Balancer", "chain": "ethereum", "address": "0xba100000625a3754423978a60c9317c58a424e3D"},
        {"type": "dex", "label": "Sushi", "chain": "ethereum", "address": "0x6B3595068778DD592e39A122f4f5a5cF09C90fE2"},
        {"type": "cex", "label": "Binance", "chain": "ethereum", "address": "0x28C6c06298d514Db089934071355E5743bf21d60"},
        {"type": "cex", "label": "Binance 2", "chain": "ethereum", "address": "0x21a31Ee1afC51d94C2eFcCAa2092aD1028285549"},
        {"type": "cex", "label": "Coinbase", "chain": "ethereum", "address": "0x71660c4005BA85c37ccec55d0C4493E66Fe775d3"},
        {"type": "cex", "label": "Coinbase 2", "chain": "ethereum", "address": "0xA9D1e08C7793af67e9d92fe308d5697FB81d3E43"},
        {"type": "cex", "label": "Kraken", "chain": "ethereum", "address": "0x2910543Af39abA0Cd09dBb2D50200b3E800A63D2"},
        {"type": "cex", "label": "OKX", "chain": "ethereum", "address": "0x6cC5F688a315f3dC28A7781717a9A798a59fDA7b"},
        {"type": "token", "label": "ETH", "chain": "ethereum", "address": "0x0000000000000000000000000000000000000000"},
        {"type": "token", "label": "WETH", "chain": "ethereum", "address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"},
        {"type": "token", "label": "USDC", "chain": "ethereum", "address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"},
        {"type": "token", "label": "USDT", "chain": "ethereum", "address": "0xdAC17F958D2ee523a2206206994597C13D831ec7"},
        {"type": "token", "label": "WBTC", "chain": "ethereum", "address": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"},
        {"type": "token", "label": "DAI", "chain": "ethereum", "address": "0x6B175474E89094C44Da98b954EedeAC495271d0F"},
        {"type": "token", "label": "LINK", "chain": "ethereum", "address": "0x514910771AF9Ca656af840dff83E8264EcF986CA"},
        {"type": "token", "label": "UNI", "chain": "ethereum", "address": "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984"},
        {"type": "token", "label": "AAVE", "chain": "ethereum", "address": "0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9"},
        {"type": "bridge", "label": "Wormhole", "chain": "ethereum", "address": "0x98f3c9e6E3fAce36bAAd05FE09d375Ef1464288B"},
        {"type": "bridge", "label": "LayerZero", "chain": "ethereum", "address": "0x66A71Dcef29A0fFBDBE3c6a460a3B5BC225Cd675"},
        {"type": "bridge", "label": "Arbitrum Bridge", "chain": "arbitrum", "address": "0x8315177aB297bA92A06054cE80a67Ed4DBd7ed3a"},
        {"type": "bridge", "label": "Hop", "chain": "ethereum", "address": "0xb8901acB165ed027E32754E0FFe830802919727f"},
        {"type": "bridge", "label": "Stargate", "chain": "ethereum", "address": "0x8731d54E9D02c286767d56ac03e8037C07e01e98"},
        {"type": "wallet", "label": "Vitalik", "chain": "ethereum", "address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"},
        {"type": "wallet", "label": "Jump Trading", "chain": "ethereum", "address": "0xF584F8728B874a6a5c7A8d4d387C9aae9172D621"},
        {"type": "wallet", "label": "Wintermute", "chain": "ethereum", "address": "0x0000006daea1723962647b7e189d311d757Fb793"},
        {"type": "wallet", "label": "a16z", "chain": "ethereum", "address": "0x05E793cE0C6027323Ac150F6d45C2344d28B6019"},
        {"type": "contract", "label": "Aave V3", "chain": "ethereum", "address": "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2"},
        {"type": "contract", "label": "Lido stETH", "chain": "ethereum", "address": "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84"},
    ]

    coll = _db["graph_anchor_entities"]

    # First, remove old entries with mixed-case addresses to avoid duplicates
    await coll.delete_many({})

    seeded = 0
    for anchor in anchors:
        # Canonical: lowercase address
        anchor["address"] = anchor["address"].lower()
        anchor["updated_at"] = datetime.now(timezone.utc).isoformat()
        result = await coll.update_one(
            {"address": anchor["address"]},
            {"$set": anchor},
            upsert=True,
        )
        if result.upserted_id or result.modified_count:
            seeded += 1

    await coll.create_index("address", unique=True)
    await coll.create_index("type")

    total = await coll.count_documents({})
    return {"seeded": seeded, "total": total, "status": "ok"}


# ========================================================
# LIQUIDITY MAP LAYER
# ========================================================

@router.get("/liquidity-map")
async def get_liquidity_map(entity: str = Query(default=None, description="Entity ID for entity-specific analysis")):
    """Return the liquidity map. If entity is provided, compute entity-specific routes."""
    if _db is None:
        return {"error": "no database"}

    # Entity-specific mode: compute routes for this entity's subgraph
    if entity:
        entity = normalize_existing_id(entity)
        liq_map = await build_liquidity_map(_db)
        try:
            route_intel = await build_entity_route_intelligence(_db, entity)
            liq_map["top_routes"] = route_intel.get("top_routes", [])
            liq_map["route_meta"] = {
                "route_count": route_intel.get("route_count", 0),
                "wash_volume_usd": route_intel.get("wash_volume_usd", 0),
                "wash_route_count": route_intel.get("wash_route_count", 0),
                "fan_out_count": route_intel.get("fan_out_count", 0),
                "fan_in_count": route_intel.get("fan_in_count", 0),
                "edges_in_subgraph": route_intel.get("edges_in_subgraph", 0),
                "nodes_in_subgraph": route_intel.get("nodes_in_subgraph", 0),
            }
            if liq_map.get("summary"):
                liq_map["summary"]["flow_state"] = route_intel.get("flow_state")
                liq_map["summary"]["flow_driver"] = route_intel.get("flow_driver")
        except Exception as e:
            import traceback
            traceback.print_exc()
        return {"source": "entity", "entity": entity, **liq_map}

    # Global mode: try cache first
    cached = await _db["graph_liquidity_maps"].find_one(
        {"snapshot_type": "latest"}, {"_id": 0}
    )
    if cached and cached.get("data"):
        return {"source": "cache", **cached["data"]}

    # Build on-the-fly
    liq_map = await build_liquidity_map(_db)
    try:
        route_intel = await build_route_intelligence(_db)
        liq_map["top_routes"] = route_intel.get("top_routes", [])
        liq_map["route_flow_state"] = route_intel.get("flow_state", liq_map.get("summary", {}).get("flow_state"))
        liq_map["route_flow_driver"] = route_intel.get("flow_driver", liq_map.get("summary", {}).get("flow_driver"))
        liq_map["route_meta"] = {
            "route_count": route_intel.get("route_count", 0),
            "wash_volume_usd": route_intel.get("wash_volume_usd", 0),
            "wash_route_count": route_intel.get("wash_route_count", 0),
            "fan_out_count": route_intel.get("fan_out_count", 0),
            "fan_in_count": route_intel.get("fan_in_count", 0),
        }
        if liq_map.get("summary"):
            liq_map["summary"]["flow_state"] = route_intel.get("flow_state", liq_map["summary"].get("flow_state"))
            liq_map["summary"]["flow_driver"] = route_intel.get("flow_driver", liq_map["summary"].get("flow_driver"))
    except Exception as e:
        import traceback
        traceback.print_exc()
        liq_map["top_routes"] = liq_map.get("top_routes", [])

    return {"source": "live", **liq_map}


@router.post("/liquidity-map/refresh")
async def refresh_liquidity_map():
    """Rebuild and cache the liquidity map with route intelligence."""
    if _db is None:
        return {"error": "no database"}

    liq_map = await build_liquidity_map(_db)

    # Add route intelligence
    try:
        route_intel = await build_route_intelligence(_db)
        liq_map["top_routes"] = route_intel.get("top_routes", [])
        liq_map["route_flow_state"] = route_intel.get("flow_state")
        liq_map["route_flow_driver"] = route_intel.get("flow_driver")
        liq_map["route_meta"] = {
            "route_count": route_intel.get("route_count", 0),
            "wash_volume_usd": route_intel.get("wash_volume_usd", 0),
            "wash_route_count": route_intel.get("wash_route_count", 0),
            "fan_out_count": route_intel.get("fan_out_count", 0),
            "fan_in_count": route_intel.get("fan_in_count", 0),
        }
        if liq_map.get("summary"):
            liq_map["summary"]["flow_state"] = route_intel.get("flow_state", liq_map["summary"].get("flow_state"))
            liq_map["summary"]["flow_driver"] = route_intel.get("flow_driver", liq_map["summary"].get("flow_driver"))
    except Exception as e:
        import traceback
        traceback.print_exc()

    await _db["graph_liquidity_maps"].update_one(
        {"snapshot_type": "latest"},
        {"$set": {
            "snapshot_type": "latest",
            "data": liq_map,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    return {"status": "refreshed", "summary": liq_map.get("summary", {}), "route_count": len(liq_map.get("top_routes", []))}


# ========================================================
# NODE RANKING
# ========================================================

@router.get("/nodes/top")
async def get_top_nodes(
    sort_by: str = Query(default="importance_score", description="Sort field"),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Return top-ranked nodes by importance, degree, or flow."""
    if _db is None:
        return {"nodes": []}

    valid_sorts = {"importance_score", "degree", "total_flow_usd", "last_seen"}
    if sort_by not in valid_sorts:
        sort_by = "importance_score"

    cursor = _db["graph_nodes"].find(
        {sort_by: {"$gt": 0}},
        {"_id": 0, "id": 1, "label": 1, "type": 1, "chain": 1,
         "degree": 1, "total_flow_usd": 1, "importance_score": 1, "last_seen": 1}
    ).sort(sort_by, -1).limit(limit)

    nodes = await cursor.to_list(limit)
    return {"nodes": nodes, "count": len(nodes), "sort_by": sort_by}



# ========================================================
# WASH / MANIPULATION DETECTION
# ========================================================

@router.get("/wash/alerts")
async def get_wash_alerts(
    pattern_type: str = Query(default=None, description="Фильтр по типу паттерна"),
    min_confidence: float = Query(default=0, ge=0, le=1),
    limit: int = Query(default=50, ge=1, le=200),
):
    """Вернуть wash/manipulation алерты."""
    if _db is None:
        return {"alerts": []}

    query = {}
    if pattern_type:
        query["pattern_type"] = pattern_type
    if min_confidence > 0:
        query["confidence"] = {"$gte": min_confidence}

    cursor = _db["graph_wash_alerts"].find(
        query, {"_id": 0}
    ).sort("confidence", -1).limit(limit)

    alerts = await cursor.to_list(limit)
    total = await _db["graph_wash_alerts"].count_documents(query)

    # Статистика по типам
    pipeline = [
        {"$group": {"_id": "$pattern_type", "count": {"$sum": 1}, "avg_confidence": {"$avg": "$confidence"}}},
        {"$sort": {"count": -1}},
    ]
    stats = await _db["graph_wash_alerts"].aggregate(pipeline).to_list(10)

    return {
        "alerts": alerts,
        "total": total,
        "returned": len(alerts),
        "stats": {s["_id"]: {"count": s["count"], "avg_confidence": round(s["avg_confidence"], 3)} for s in stats},
    }


@router.post("/wash/scan")
async def run_wash_scan():
    """Запустить сканирование wash-паттернов."""
    if _db is None:
        return {"error": "no database"}

    alerts = await run_wash_detection(_db)
    return {
        "status": "completed",
        "alerts_found": len(alerts),
        "by_type": {pt: sum(1 for a in alerts if a["pattern_type"] == pt) for pt in set(a["pattern_type"] for a in alerts)},
    }


# ========================================================
# COMPLIANCE / EXPOSURE
# ========================================================

@router.get("/nodes/{node_id:path}/exposure")
async def get_node_exposure(node_id: str):
    """Вернуть exposure-данные для ноды."""
    if _db is None:
        return {"error": "no database"}

    node = await _db["graph_nodes"].find_one(
        {"id": node_id},
        {"_id": 0, "id": 1, "label": 1, "type": 1,
         "exposure_score": 1, "exposure_flags": 1}
    )

    if not node:
        return {"error": "node not found", "node_id": node_id}

    # Wash-алерты для этой ноды
    wash_cursor = _db["graph_wash_alerts"].find(
        {"nodes": node_id},
        {"_id": 0, "alert_id": 1, "pattern_type": 1, "confidence": 1, "amount_usd": 1}
    ).limit(10)
    wash_alerts = await wash_cursor.to_list(10)

    return {
        "node_id": node_id,
        "label": node.get("label", ""),
        "type": node.get("type", ""),
        "exposure_score": node.get("exposure_score", 0),
        "exposure_flags": node.get("exposure_flags", []),
        "wash_alerts": wash_alerts,
    }


@router.post("/exposure/compute")
async def compute_exposure_scores():
    """Пересчитать exposure для всех нод."""
    if _db is None:
        return {"error": "no database"}

    scores = await compute_exposure(_db)
    flagged = sum(1 for s in scores.values() if s > 0)
    return {"status": "completed", "nodes_scored": len(scores), "flagged": flagged}


# ========================================================
# RISK SCORING
# ========================================================

@router.get("/nodes/{node_id:path}/risk")
async def get_node_risk(node_id: str):
    """Вернуть risk-данные для ноды."""
    if _db is None:
        return {"error": "no database"}

    node = await _db["graph_nodes"].find_one(
        {"id": node_id},
        {"_id": 0, "id": 1, "label": 1, "type": 1,
         "risk_score": 1, "risk_level": 1, "risk_components": 1,
         "exposure_score": 1, "exposure_flags": 1}
    )

    if not node:
        return {"error": "node not found", "node_id": node_id}

    return {
        "node_id": node_id,
        "label": node.get("label", ""),
        "type": node.get("type", ""),
        "risk_score": node.get("risk_score", 0),
        "risk_level": node.get("risk_level", "clean"),
        "risk_components": node.get("risk_components", {}),
        "exposure_score": node.get("exposure_score", 0),
        "exposure_flags": node.get("exposure_flags", []),
    }


@router.post("/risk/compute")
async def compute_risk_scores():
    """Пересчитать risk для всех нод (wash → exposure → risk)."""
    if _db is None:
        return {"error": "no database"}

    # Каскадный пересчёт
    alerts = await run_wash_detection(_db)
    exposure = await compute_exposure(_db)
    levels = await compute_risk(_db)

    return {
        "status": "completed",
        "wash_alerts": len(alerts),
        "exposure_flagged": sum(1 for s in exposure.values() if s > 0),
        "risk_levels": dict(levels),
    }


# ========================================================
# CLUSTER ENGINE
# ========================================================

# Stabilization Sprint C2 — shadowed by `/clusters` defined earlier in this file (line ~541).
# Kept as `_get_clusters_v2` for future migration; not registered.
async def _get_clusters_v2(
    limit: int = Query(default=50, ge=1, le=200),
):
    """Вернуть все кластеры."""
    if _db is None:
        return {"clusters": []}

    cursor = _db["graph_clusters"].find(
        {}, {"_id": 0}
    ).sort("member_count", -1).limit(limit)

    clusters = await cursor.to_list(limit)
    total = await _db["graph_clusters"].count_documents({})

    return {"clusters": clusters, "total": total, "returned": len(clusters)}


# Stabilization Sprint C2 — shadowed by `/clusters/{cluster_id}/members` earlier in this file (line ~588).
async def _get_cluster_members_v2(
    cluster_id: str,
    limit: int = Query(default=50, ge=1, le=200),
):
    """Вернуть членов кластера."""
    if _db is None:
        return {"members": []}

    # Найти кластер
    cluster = await _db["graph_clusters"].find_one(
        {"cluster_id": cluster_id}, {"_id": 0}
    )

    if not cluster:
        return {"error": "cluster not found", "cluster_id": cluster_id}

    # Найти ноды с этим cluster_id
    cursor = _db["graph_nodes"].find(
        {"cluster_id": cluster_id},
        {"_id": 0, "id": 1, "label": 1, "type": 1, "degree": 1,
         "total_flow_usd": 1, "risk_score": 1, "importance_score": 1}
    ).sort("degree", -1).limit(limit)

    members = await cursor.to_list(limit)

    return {
        "cluster": {
            "cluster_id": cluster.get("cluster_id"),
            "type": cluster.get("type"),
            "label": cluster.get("label"),
            "confidence": cluster.get("confidence"),
            "member_count": cluster.get("member_count", len(members)),
        },
        "members": members,
        "returned": len(members),
    }


@router.post("/clusters/rebuild")
async def rebuild_clusters():
    """Перестроить кластеры (запустить кластеризацию)."""
    if _db is None:
        return {"error": "no database"}

    new_clusters = await run_clustering(_db)
    return {
        "status": "completed",
        "new_clusters": len(new_clusters),
        "total": await _db["graph_clusters"].count_documents({}),
    }


# ========================================================
# ALPHA ENGINE
# ========================================================

@router.get("/alpha/signals")
async def get_alpha_signals(
    signal_type: str = Query(default=None, description="Фильтр по типу сигнала"),
    limit: int = Query(default=30, ge=1, le=100),
):
    """Вернуть alpha-сигналы."""
    if _db is None:
        return {"signals": []}

    query = {}
    if signal_type:
        query["signal_type"] = signal_type

    cursor = _db["graph_alpha_signals"].find(
        query, {"_id": 0}
    ).sort("generated_at", -1).limit(limit)

    signals = await cursor.to_list(limit)
    total = await _db["graph_alpha_signals"].count_documents(query)

    # Типы сигналов
    pipeline = [
        {"$group": {"_id": "$signal_type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    types = await _db["graph_alpha_signals"].aggregate(pipeline).to_list(20)

    return {
        "signals": signals,
        "total": total,
        "returned": len(signals),
        "signal_types": {t["_id"]: t["count"] for t in types},
    }


@router.get("/alpha/pressure")
async def get_liquidity_pressure():
    """Вернуть текущее давление ликвидности."""
    if _db is None:
        return {"error": "no database"}

    cached = await _db["graph_liquidity_pressure"].find_one(
        {"snapshot_type": "latest"}, {"_id": 0}
    )
    if cached:
        return cached

    # Вычислить на лету
    result = await compute_pressure(_db)
    return result


@router.get("/alpha/smart-money")
async def get_smart_money(
    limit: int = Query(default=20, ge=1, le=100),
):
    """Вернуть топ smart money кошельков."""
    if _db is None:
        return {"wallets": []}

    cursor = _db["graph_nodes"].find(
        {"smart_money_score": {"$gt": 0}, "type": "wallet"},
        {"_id": 0, "id": 1, "label": 1, "type": 1,
         "smart_money_score": 1, "degree": 1, "total_flow_usd": 1,
         "risk_score": 1, "cluster_id": 1}
    ).sort("smart_money_score", -1).limit(limit)

    wallets = await cursor.to_list(limit)
    return {"wallets": wallets, "count": len(wallets)}


@router.post("/alpha/generate")
async def generate_alpha():
    """Запустить полный pipeline генерации alpha-сигналов."""
    if _db is None:
        return {"error": "no database"}

    # 1. Smart money detection
    sm_scores = await detect_smart_money(_db)

    # 2. Flow signals
    flow_signals = await generate_flow_signals(_db)

    # 3. Liquidity pressure
    pressure = await compute_pressure(_db)

    # 4. Narratives
    narratives = await detect_narratives(_db)

    return {
        "status": "completed",
        "smart_money_scored": len(sm_scores),
        "flow_signals": len(flow_signals),
        "pressure": pressure.get("trend", "unknown"),
        "narratives": len(narratives),
        "total_signals": len(flow_signals) + len(narratives),
    }


# ========================================================
# GRAPH PROJECTION LAYER — UNIFIED ENDPOINT
# ========================================================

@router.get("/project/{node_id:path}")
async def get_projected_graph(
    node_id: str,
    depth: int = Query(default=2, ge=1, le=3),
    max_nodes: int = Query(default=150, ge=1, le=500),
    max_edges: int = Query(default=400, ge=1, le=1500),
    mode: str = Query(default=None, description="Graph mode: smart_money, cex_flow, token_rotation, entity, risk"),
    level: str = Query(default=None, description="Identity level: wallet, cluster, entity"),
    start_time: int = Query(default=None, description="Temporal filter: start timestamp"),
    end_time: int = Query(default=None, description="Temporal filter: end timestamp"),
):
    """
    Graph Projection Layer — unified endpoint with identity hierarchy.
    Supports 3 identity levels: wallet (raw), cluster (behavior), entity (institutional).
    """
    if _db is None:
        return {"nodes": [], "edges": [], "meta": {"error": "no_database"}}

    node_id = normalize_existing_id(node_id)

    result = await project_graph(
        _db,
        center_node_id=node_id,
        depth=depth,
        max_nodes=max_nodes,
        max_edges=max_edges,
        mode=mode,
        start_time=start_time,
        end_time=end_time,
        level=level,
    )

    # ── Unified Intelligence Layer ──
    if result and result.get("nodes"):
        token_flow_data = []
        if _db is not None:
            token_flow_data = await _fetch_token_flows_for_nodes(result.get("nodes", []))
        intelligence = _compute_graph_intelligence(
            result.get("nodes", []), result.get("edges", []), token_flow_data
        )
        
        # Market context from FULL intelligence
        result["market_context"] = _compute_market_context(intelligence)
        
        # STRICT: Filter intelligence by mode category (no cross-category leaking)
        if mode:
            MODE_CATEGORY_MAP = {
                "smart_money": "smart_money",
                "entity": "entity",
                "risk": "risk",
                "token_rotation": "token_flow",
                "cex_flow": "route",
            }
            filter_cat = MODE_CATEGORY_MAP.get(mode)
            if filter_cat:
                intelligence = [sig for sig in intelligence if sig.get("category") == filter_cat]
        
        result["intelligence"] = intelligence

    return result


# ========================================================
# DATA INTEGRATION PIPELINE
# ========================================================

@router.post("/integrate/run")
async def run_integration():
    """Run full data integration pipeline (all 5 sources → graph)."""
    if _db is None:
        return {"error": "no database"}
    result = await run_full_integration(_db)
    return result


@router.post("/integrate/smart-money")
async def integrate_sm():
    """Integrate only Smart Money data into graph."""
    if _db is None:
        return {"error": "no database"}
    from graph_data_integrator import integrate_smart_money
    storage.init_storage(_db)
    return await integrate_smart_money(_db)


@router.post("/integrate/cex-flow")
async def integrate_cex():
    """Integrate only CEX Flow data into graph."""
    if _db is None:
        return {"error": "no database"}
    from graph_data_integrator import integrate_cex_flow
    storage.init_storage(_db)
    return await integrate_cex_flow(_db)


@router.post("/integrate/tokens")
async def integrate_tokens():
    """Integrate only Token Intelligence data into graph."""
    if _db is None:
        return {"error": "no database"}
    from graph_data_integrator import integrate_token_intelligence
    storage.init_storage(_db)
    return await integrate_token_intelligence(_db)


@router.post("/integrate/wallets")
async def integrate_wallets():
    """Integrate only Wallet Intelligence data into graph."""
    if _db is None:
        return {"error": "no database"}
    from graph_data_integrator import integrate_wallet_intelligence
    storage.init_storage(_db)
    return await integrate_wallet_intelligence(_db)


@router.post("/integrate/entities")
async def integrate_entities():
    """Integrate only Entity Intelligence data into graph."""
    if _db is None:
        return {"error": "no database"}
    from graph_data_integrator import integrate_entity_intelligence
    storage.init_storage(_db)
    return await integrate_entity_intelligence(_db)


# ========================================================
# CLUSTER LAYER
# ========================================================

@router.post("/clusters/build-layer")
async def build_cluster_layer():
    """Build cluster layer — clusters as first-class nodes with relations."""
    if _db is None:
        return {"error": "no database"}
    return await run_cluster_layer(_db)


# ========================================================
# CAPITAL ROUTES
# ========================================================

@router.get("/routes")
async def get_capital_routes(
    route_type: str = Query(default=None, description="Filter by route type"),
    ranking: str = Query(default="largest", description="Ranking: largest, smart_money, fastest, newest, highest_alpha"),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Get capital routes with ranking."""
    if _db is None:
        return {"routes": []}

    if route_type:
        routes = await storage.get_routes(route_type=route_type, limit=limit)
    else:
        routes = await get_routes_ranked(_db, ranking=ranking, limit=limit)

    return {"routes": routes, "count": len(routes), "ranking": ranking}


@router.get("/routes/node/{node_id:path}")
async def get_node_routes(
    node_id: str,
    limit: int = Query(default=20, ge=1, le=100),
):
    """Get all capital routes involving a specific node."""
    if _db is None:
        return {"routes": []}

    node_id = normalize_existing_id(node_id)
    routes = await storage.get_routes_for_node(node_id, limit=limit)
    return {"routes": routes, "count": len(routes), "node_id": node_id}


@router.post("/routes/build")
async def build_routes():
    """Build capital routes from graph data."""
    if _db is None:
        return {"error": "no database"}
    return await run_capital_routes(_db)


# ========================================================
# INTELLIGENCE OVERLAY
# ========================================================

@router.get("/overlay")
async def get_overlays(
    overlay_type: str = Query(default=None, description="Filter: risk, signal, narrative, alert"),
    node_id: str = Query(default=None, description="Filter by node ID"),
    limit: int = Query(default=50, ge=1, le=200),
):
    """Get intelligence overlay entries."""
    if _db is None:
        return {"overlays": []}

    overlays = await storage.get_overlays(overlay_type=overlay_type, node_id=node_id, limit=limit)
    return {"overlays": overlays, "count": len(overlays)}


@router.post("/overlay/build")
async def build_overlay():
    """Build all intelligence overlays."""
    if _db is None:
        return {"error": "no database"}
    return await run_intelligence_overlay(_db)


# ========================================================
# NODE DETAIL (unified node summary)
# ========================================================

@router.get("/node/{node_id:path}")
async def get_node_detail(node_id: str):
    """Get full node detail including overlays and routes."""
    if _db is None:
        return {"error": "no database"}

    node_id = normalize_existing_id(node_id)
    node = await storage.get_node(node_id)
    if not node:
        return {"error": "node not found", "node_id": node_id}

    # Get overlays for this node
    overlays = await storage.get_overlays(node_id=node_id, limit=20)

    # Get routes for this node
    routes = await storage.get_routes_for_node(node_id, limit=10)

    return {
        "node": node,
        "overlays": overlays,
        "routes": routes,
    }


# ========================================================
# NODE EDGES (relations for a specific node)
# ========================================================

@router.get("/edges/{node_id:path}")
async def get_node_edges(
    node_id: str,
    limit: int = Query(default=100, ge=1, le=500),
):
    """Get all edges/relations for a specific node from graph data."""
    if _db is None:
        return {"edges": [], "total": 0}

    node_id = normalize_existing_id(node_id)
    raw_edges = []

    # 1. Try graph_relations (primary graph store)
    # Fields: source_id, target_id, relation_type, total_amount_usd, direction, confidence, tags
    cursor = _db["graph_relations"].find(
        {"$or": [{"source_id": node_id}, {"target_id": node_id}]},
        {"_id": 0}
    ).limit(limit)
    for doc in await cursor.to_list(limit):
        raw_edges.append({
            "source": doc.get("source_id", ""),
            "target": doc.get("target_id", ""),
            "type": doc.get("relation_type", "transfer"),
            "relation_id": f"{doc.get('source_id','')}-{doc.get('target_id','')}",
            "amount_usd": doc.get("total_amount_usd", 0),
            "direction": doc.get("direction", "out"),
            "confidence": doc.get("confidence", 0),
            "tags": doc.get("tags", []),
            "tx_count": doc.get("tx_count", 0),
        })

    # 2. Fallback: graph_edges (knowledge_graph store)
    if not raw_edges:
        cursor2 = _db["graph_edges"].find(
            {"$or": [
                {"from_node_id": {"$regex": node_id.replace(":", ".*"), "$options": "i"}},
                {"to_node_id": {"$regex": node_id.replace(":", ".*"), "$options": "i"}},
            ]},
            {"_id": 0}
        ).limit(limit)
        kg_edges = await cursor2.to_list(limit)
        for e in kg_edges:
            raw_edges.append({
                "source": e.get("from_node_id", ""),
                "target": e.get("to_node_id", ""),
                "type": e.get("relation_type", e.get("type", "transfer")),
                "relation_id": e.get("id", ""),
                "amount_usd": e.get("amount_usd", e.get("weight", 0)),
                "direction": e.get("direction", "out"),
                "confidence": e.get("confidence", 0),
                "tags": e.get("tags", []),
            })

    # Resolve labels
    node_ids = set()
    for e in raw_edges:
        node_ids.add(e.get("source", ""))
        node_ids.add(e.get("target", ""))
    node_ids.discard("")

    label_map = {}
    if node_ids:
        # Check graph_nodes first
        label_cursor = _db["graph_nodes"].find(
            {"id": {"$in": list(node_ids)}},
            {"_id": 0, "id": 1, "label": 1}
        )
        async for n in label_cursor:
            label_map[n["id"]] = n.get("label", "")

        # Also check anchor entities for better labels
        for nid in node_ids:
            if nid not in label_map or not label_map[nid]:
                parts = nid.split(":")
                if len(parts) >= 2:
                    addr = parts[1].lower()
                    anchor = await _db["graph_anchor_entities"].find_one(
                        {"address": addr}, {"_id": 0, "label": 1}
                    )
                    if anchor and anchor.get("label"):
                        label_map[nid] = anchor["label"]

    edges = []
    for e in raw_edges:
        src = e.get("source", "")
        tgt = e.get("target", "")
        edges.append({
            "id": e.get("relation_id", f"{src}-{tgt}"),
            "source": src,
            "target": tgt,
            "source_label": label_map.get(src, ""),
            "target_label": label_map.get(tgt, ""),
            "relation": e.get("type", "transfer"),
            "type": e.get("type", "transfer"),
            "direction": e.get("direction", "out"),
            "amount_usd": e.get("amount_usd", 0),
            "confidence": e.get("confidence", 0),
            "tags": e.get("tags", []),
        })

    return {"edges": edges, "total": len(edges), "node_id": node_id}


# ========================================================
# FULL PIPELINE (run everything in order)
# ========================================================

@router.post("/pipeline/run")
async def run_full_pipeline():
    """
    Run the complete Phase A pipeline in order:
    1. Data Integration (Smart Money → CEX → Token → Wallet → Entity)
    2. Cluster Layer
    3. Capital Routes
    4. Intelligence Overlay
    """
    if _db is None:
        return {"error": "no database"}

    results = {}
    t0 = time.time()

    # 1. Data Integration
    results["integration"] = await run_full_integration(_db)

    # 2. Cluster Layer
    results["cluster_layer"] = await run_cluster_layer(_db)

    # 3. Capital Routes
    results["capital_routes"] = await run_capital_routes(_db)

    # 4. Intelligence Overlay
    results["intelligence_overlay"] = await run_intelligence_overlay(_db)

    # 5. Identity Hierarchy
    results["identity_hierarchy"] = await run_identity_resolver(_db)

    # 6. Graph Context Layer
    results["context_layer"] = await run_context_layer(_db)

    elapsed = round(time.time() - t0, 1)

    return {
        "status": "completed",
        "elapsed_seconds": elapsed,
        "steps": results,
    }


# ========================================================
# IDENTITY HIERARCHY
# ========================================================

@router.post("/identity/build")
async def build_identity_map():
    """Build wallet → cluster → entity identity map."""
    if _db is None:
        return {"error": "no database"}
    return await run_identity_resolver(_db)


@router.get("/identity/resolve/{node_id:path}")
async def resolve_node_identity(
    node_id: str,
    level: str = Query(default="entity", description="Target level: wallet, cluster, entity"),
):
    """Resolve a node to the requested identity level."""
    if _db is None:
        return {"error": "no database"}
    node_id = normalize_existing_id(node_id)
    resolved = await resolve_identity(_db, node_id, level)
    mapping = await resolve_wallet(_db, node_id)
    return {
        "input": node_id,
        "level": level,
        "resolved": resolved,
        "mapping": mapping,
    }


@router.get("/identity/cluster/{cluster_id:path}/wallets")
async def get_cluster_wallet_list(cluster_id: str):
    """Get all wallets in a cluster."""
    if _db is None:
        return {"wallets": []}
    wallets = await get_cluster_wallets(_db, cluster_id)
    return {"cluster_id": cluster_id, "wallets": wallets, "count": len(wallets)}


@router.get("/identity/entity/{entity_id:path}/wallets")
async def get_entity_wallet_list(entity_id: str):
    """Get all wallets belonging to an entity."""
    if _db is None:
        return {"wallets": []}
    wallets = await get_entity_wallets(_db, entity_id)
    return {"entity_id": entity_id, "wallets": wallets, "count": len(wallets)}


@router.get("/identity/entity/{entity_id:path}/clusters")
async def get_entity_cluster_list(entity_id: str):
    """Get all clusters belonging to an entity."""
    if _db is None:
        return {"clusters": []}
    clusters = await get_entity_clusters(_db, entity_id)
    return {"entity_id": entity_id, "clusters": clusters, "count": len(clusters)}


# ========================================================
# GRAPH CONTEXT LAYER
# ========================================================

@router.post("/context/build")
async def build_context():
    """Build Graph Context Layer: influence scores, capital centers, dominant routes."""
    if _db is None:
        return {"error": "no database"}
    return await run_context_layer(_db)


@router.get("/context")
async def get_graph_context(
    context_type: str = Query(default=None, description="Filter: capital_center, dominant_route"),
    limit: int = Query(default=30, ge=1, le=100),
):
    """Get graph context entries (capital centers, dominant routes, etc.)."""
    if _db is None:
        return {"context": []}
    entries = await get_context(_db, context_type=context_type, limit=limit)
    return {"context": entries, "count": len(entries)}


@router.get("/context/node/{node_id:path}")
async def get_node_context(node_id: str):
    """Get context entries for a specific node."""
    if _db is None:
        return {"context": []}
    node_id = normalize_existing_id(node_id)
    entries = await get_context_for_node(_db, node_id)
    return {"context": entries, "count": len(entries), "node_id": node_id}



# ========================================================
# SMART WALLET ENGINE (P2)
# ========================================================

@router.get("/smart-wallets")
async def smart_wallets_leaderboard(
    limit: int = Query(default=50, ge=1, le=200),
):
    """Get ranked smart wallet leaderboard."""
    if _db is None:
        return {"wallets": [], "total": 0}
    wallets = await compute_smart_wallet_rankings(_db, limit=limit)
    return {"wallets": wallets, "total": len(wallets)}


@router.get("/top-clusters")
async def top_clusters_ranking(
    limit: int = Query(default=20, ge=1, le=100),
):
    """Get top clusters ranked by capital influence."""
    if _db is None:
        return {"clusters": [], "total": 0}
    clusters = await get_top_clusters(_db, limit=limit)
    return {"clusters": clusters, "total": len(clusters)}


@router.get("/top-routes")
async def top_routes_ranking(
    limit: int = Query(default=20, ge=1, le=100),
):
    """Get top capital routes ranked by importance."""
    if _db is None:
        return {"routes": [], "total": 0}
    routes = await get_top_capital_routes(_db, limit=limit)
    return {"routes": routes, "total": len(routes)}



# ========================================================
# DISCOVERY ENGINE — Global Mode Intelligence
# ========================================================

@router.get("/discovery")
async def graph_discovery(
    mode: str = Query(default="all", description="Discovery mode: all, smart_money, cex_flow, token_rotation, entity, risk"),
    chain: str = Query(default=None, description="Chain filter (e.g., ethereum)"),
    timeframe: str = Query(default=None, description="Time window (e.g., 7d, 30d)"),
    limit: int = Query(default=20, ge=1, le=100),
):
    """
    Discovery endpoint: finds seed nodes for global mode without a starting address.
    Pipeline: MODE → QUERY → SEED_NODES
    """
    if _db is None:
        return {"seed_nodes": [], "mode": mode, "reason": "no_database", "count": 0}

    result = await discover_seeds(_db, mode=mode, chain=chain, timeframe=timeframe, limit=limit)
    return result


# ========================================================
# SEED GRAPH RENDER — Multi-seed graph building
# ========================================================

@router.get("/render-seeds")
async def render_seeds_graph(
    seeds: str = Query(description="Comma-separated seed node IDs"),
    depth: int = Query(default=1, ge=1, le=2),
    limit: int = Query(default=100, ge=1, le=300),
    mode: str = Query(default=None, description="Graph mode filter"),
    max_edges_per_node: int = Query(default=30, ge=5, le=100),
    chains: str = Query(default=None, description="Comma-separated chain keys, e.g. ethereum,arbitrum"),
):
    """
    Render graph around multiple seed nodes.
    Pipeline: SEEDS → multi-center projection → lane aggregation → render edges
    """
    if _db is None:
        return {"nodes": [], "edges": [], "meta": {"error": "no_database"}}

    seed_list = [s.strip() for s in seeds.split(",") if s.strip()]
    if not seed_list:
        return {"nodes": [], "edges": [], "meta": {"error": "no_seeds"}}

    chain_list = [c.strip() for c in chains.split(",") if c.strip()] if chains else None

    # Collect nodes + edges from all seeds
    all_nodes = {}
    all_edges = []
    seen_edge_keys = set()

    for seed_id in seed_list[:20]:  # Max 20 seeds
        result = await project_graph(
            _db,
            center_node_id=seed_id,
            depth=depth,
            max_nodes=limit // len(seed_list) + 10,
            max_edges=(limit * 2) // len(seed_list) + 20,
            mode=mode,
            chains=chain_list,
        )
        for n in result.get("nodes", []):
            if n.get("id") not in all_nodes:
                all_nodes[n["id"]] = n
        for e in result.get("edges", []):
            ekey = f"{e.get('source','')}-{e.get('target','')}-{e.get('type','')}"
            if ekey not in seen_edge_keys:
                seen_edge_keys.add(ekey)
                all_edges.append(e)

    # P0.2: Edge ranking — limit edges per node by importance
    all_edges = _rank_and_limit_edges(all_edges, max_edges_per_node)

    nodes_list = list(all_nodes.values())[:limit]
    node_ids = {n["id"] for n in nodes_list}
    filtered_edges = [e for e in all_edges if e.get("source") in node_ids and e.get("target") in node_ids]

    # Lane aggregation + render edge projection
    from edge_lane_service import aggregate_lanes, build_render_edges
    lanes = aggregate_lanes(filtered_edges)
    render_edges = build_render_edges(lanes, center_node_id=seed_list[0] if seed_list else "")

    render_edges = [e for e in render_edges if e["source"] in node_ids and e["target"] in node_ids]

    # CEX Flow — find CEX-to-CEX routes (no filtering)
    cex_routes = []
    if mode == "cex_flow":
        cex_routes = _find_cex_routes(nodes_list, render_edges, seed_list[0] if seed_list else "")
        # Cross-reference with DB wash alerts
        cex_routes = await _enrich_routes_with_db_wash_alerts(cex_routes)

    # Compute ring colors for seed graph too
    nodes_list = _compute_node_ring_colors(nodes_list, render_edges)

    # ── Unified Intelligence Layer ──
    # Fetch token flows from DB for rotation detection
    token_flow_data = []
    if _db is not None:
        token_flow_data = await _fetch_token_flows_for_nodes(nodes_list)
    intelligence = _compute_graph_intelligence(nodes_list, render_edges, token_flow_data)

    # Compute market context from FULL intelligence (before mode filtering)
    market_context = _compute_market_context(intelligence)

    # STRICT: Filter intelligence by mode category (no cross-category leaking)
    if mode:
        MODE_CATEGORY_MAP = {
            "smart_money": "smart_money",
            "entity": "entity",
            "risk": "risk",
            "token_rotation": "token_flow",
            "cex_flow": "route",
        }
        filter_cat = MODE_CATEGORY_MAP.get(mode)
        if filter_cat:
            intelligence = [sig for sig in intelligence if sig.get("category") == filter_cat]

    result = {
        "nodes": nodes_list,
        "edges": render_edges,
        "intelligence": intelligence,
        "market_context": market_context,
        "meta": {
            "source": "discovery_render",
            "seed_count": len(seed_list),
            "node_count": len(nodes_list),
            "render_edge_count": len(render_edges),
            "mode": mode,
        },
    }
    if cex_routes:
        result["cex_routes"] = cex_routes
    return result


async def _fetch_token_flows_for_nodes(nodes):
    """Fetch token flow data from onchain_v2_token_flows for DEX pools in the graph."""
    if _db is None:
        return []
    try:
        # Extract pool addresses from DEX node IDs (dex:0xAbcd...:ethereum → 0xAbcd...)
        pool_addrs = []
        pool_to_node = {}
        for n in nodes:
            nid = n.get("id", "")
            parts = nid.split(":")
            if len(parts) >= 2 and parts[0] == "dex":
                addr = parts[1].lower()
                pool_addrs.append(addr)
                pool_to_node[addr] = nid
        if not pool_addrs:
            return []

        ie_db = _db.client["intelligence_engine"]
        cursor = ie_db.onchain_v2_token_flows.aggregate([
            {"$match": {"poolAddress": {"$in": pool_addrs}}},
            {"$group": {
                "_id": {"pool": "$poolAddress", "token": "$tokenSymbol", "side": "$side"},
                "volume": {"$sum": "$usdVolume"},
                "count": {"$sum": 1},
            }},
            {"$sort": {"volume": -1}},
            {"$limit": 200},
        ])
        results = await cursor.to_list(200)
        return [{"pool": r["_id"]["pool"], "node_id": pool_to_node.get(r["_id"]["pool"], ""),
                 "token": r["_id"]["token"], "side": r["_id"]["side"],
                 "volume": r["volume"], "count": r["count"]}
                for r in results]
    except Exception as e:
        print(f"[token_flows] Error: {e}")
        return []



def _compute_graph_intelligence(nodes, edges, token_flow_data=None):
    """
    Unified Intelligence Layer — formula-based confidence with breakdown.
    STRICT category ownership: each signal type belongs to ONE category.

    Categories:
      smart_money → accumulation, distribution, whale_activity
      entity      → entity_cluster
      risk        → loop_routing, high_risk_nodes
      token_flow  → rotation
      route       → cex_flow_summary
    """
    from collections import defaultdict
    import math
    signals = []

    node_map = {n.get("id", ""): n for n in nodes}

    # ── Pre-compute edge aggregation ──
    node_in_vol = defaultdict(float)
    node_out_vol = defaultdict(float)
    node_in_cnt = defaultdict(int)
    node_out_cnt = defaultdict(int)
    node_peers = defaultdict(set)
    token_edges = []
    max_vol = 0.0

    for e in edges:
        src, tgt = e.get("source", ""), e.get("target", "")
        vol = e.get("amountUsd") or e.get("volume_usd") or e.get("amount_usd") or 0
        node_out_vol[src] += vol
        node_in_vol[tgt] += vol
        node_out_cnt[src] += 1
        node_in_cnt[tgt] += 1
        node_peers[src].add(tgt)
        node_peers[tgt].add(src)
        if vol > max_vol:
            max_vol = vol
        tg = e.get("tokenGroup") or e.get("token_group") or ""
        if tg:
            token_edges.append({"source": src, "target": tgt, "volume": vol, "token": tg})

    log_max_vol = math.log10(max_vol + 1) if max_vol > 0 else 1

    # ═══════════════════════════════════════════
    # ENTITY (entity_cluster) — STRICT: only entity
    # ═══════════════════════════════════════════
    clusters = defaultdict(list)
    for n in nodes:
        cid = n.get("clusterId") or n.get("cluster_id") or ""
        if cid:
            clusters[cid].append(n)

    for cid, members in clusters.items():
        if len(members) < 2:
            continue
        member_ids = {m["id"] for m in members}

        internal_vol = 0.0
        external_vol = 0.0
        internal_edges = 0
        for e in edges:
            src, tgt = e.get("source", ""), e.get("target", "")
            vol = e.get("amountUsd") or e.get("volume_usd") or 0
            if src in member_ids and tgt in member_ids:
                internal_vol += vol
                internal_edges += 1
            elif src in member_ids or tgt in member_ids:
                external_vol += vol

        behaviors = [m.get("behavior", "") for m in members if m.get("behavior")]
        entity_type = "unknown"
        for tag in ["exchange", "fund", "whale", "protocol", "dex", "bridge"]:
            if any(tag in b for b in behaviors):
                entity_type = tag
                break

        # Formula: baseline(0.15) + internal_flow_ratio(0.3) + interaction_density(0.2) + shared_behavior(0.15) + size(0.2)
        total_flow = internal_vol + external_vol
        internal_ratio = internal_vol / total_flow if total_flow > 0 else 0
        max_possible_edges = len(members) * (len(members) - 1) / 2
        density = internal_edges / max_possible_edges if max_possible_edges > 0 else 0
        behavior_set = set(behaviors)
        shared_beh = 1.0 if len(behavior_set) <= 1 and behaviors else (1.0 / len(behavior_set) if behavior_set else 0)
        size_score = min(1.0, len(members) / 15)

        # Baseline: having a shared clusterId is already evidence
        conf = 0.15 + 0.3 * internal_ratio + 0.2 * min(density, 1.0) + 0.15 * shared_beh + 0.2 * size_score
        conf = round(min(0.95, max(0.15, conf)), 2)

        breakdown = []
        if internal_ratio > 0:
            breakdown.append(f"Internal flow ratio: {internal_ratio:.0%}")
        if density > 0:
            breakdown.append(f"Interaction density: {density:.0%}")
        if shared_beh > 0.5:
            breakdown.append(f"Shared behavior: {entity_type}")
        breakdown.append(f"Cluster size: {len(members)}")

        label = members[0].get("label", cid)
        if ":" in label:
            parts = label.split(":")
            label = parts[1] if len(parts) > 1 else parts[0]

        signals.append({
            "type": "entity_cluster",
            "category": "entity",
            "confidence": conf,
            "confidence_breakdown": breakdown,
            "summary": f"{entity_type.title()} cluster — {len(members)} addresses",
            "entities": [m["id"] for m in members[:10]],
            "details": {
                "cluster_id": cid,
                "cluster_size": len(members),
                "entity_type": entity_type,
                "label": label,
                "internal_flow_usd": round(internal_vol, 2),
                "external_flow_usd": round(external_vol, 2),
                "coherence": round(internal_ratio, 2),
                "behaviors": list(set(behaviors))[:5],
            },
        })

    # ═══════════════════════════════════════════
    # SMART MONEY — STRICT: only accumulation, distribution, whale
    # ═══════════════════════════════════════════
    sm_nodes = [n for n in nodes if (n.get("smartMoneyScore") or 0) > 0 or (n.get("alphaScore") or 0) > 0]

    accum, distrib = [], []
    for n in sm_nodes:
        nid = n["id"]
        inv, outv = node_in_vol.get(nid, 0), node_out_vol.get(nid, 0)
        total = inv + outv
        if total == 0:
            continue
        in_ratio = inv / total
        if in_ratio >= 0.65:
            accum.append(n)
        elif in_ratio <= 0.35:
            distrib.append(n)

    # Also check non-SM wallets with strong accumulation pattern
    for n in nodes:
        if n in sm_nodes or n.get("type") not in ("wallet",):
            continue
        nid = n["id"]
        inv, outv = node_in_vol.get(nid, 0), node_out_vol.get(nid, 0)
        total = inv + outv
        if total < 100:
            continue
        in_ratio = inv / total
        in_cnt = node_in_cnt.get(nid, 0)
        if in_ratio >= 0.8 and in_cnt >= 3:
            accum.append(n)
        elif in_ratio <= 0.2 and node_out_cnt.get(nid, 0) >= 3:
            distrib.append(n)

    if accum:
        total_accum_vol = sum(node_in_vol.get(n["id"], 0) for n in accum)
        sm_scores = [n.get("smartMoneyScore", 0) for n in accum]
        avg_sm = sum(sm_scores) / len(sm_scores) if sm_scores else 0
        # Formula: consistency(0.3) + accumulation_pattern(0.3) + wallet_coordination(0.2) + volume(0.2)
        avg_in_ratio = sum(node_in_vol.get(n["id"], 0) / max(node_in_vol.get(n["id"], 0) + node_out_vol.get(n["id"], 0), 1) for n in accum) / len(accum)
        consistency = min(1.0, avg_in_ratio)
        pattern = min(1.0, avg_sm * 2) if avg_sm > 0 else (0.4 if avg_in_ratio > 0.8 else 0.2)
        coordination = min(1.0, len(accum) / 10)
        vol_score = min(1.0, math.log10(total_accum_vol + 1) / log_max_vol) if log_max_vol > 0 else 0

        conf = round(min(0.95, max(0.15, 0.3 * consistency + 0.3 * pattern + 0.2 * coordination + 0.2 * vol_score)), 2)
        breakdown = []
        breakdown.append(f"Avg buy ratio: {avg_in_ratio:.0%}")
        if avg_sm > 0:
            breakdown.append(f"SM score: {avg_sm:.2f}")
        breakdown.append(f"Coordinated wallets: {len(accum)}")
        breakdown.append(f"Total inflow: {_fmt_usd(total_accum_vol)}")

        signals.append({
            "type": "accumulation",
            "category": "smart_money",
            "confidence": conf,
            "confidence_breakdown": breakdown,
            "summary": f"Accumulation detected — {len(accum)} wallet{'s' if len(accum) > 1 else ''}",
            "entities": [n["id"] for n in accum[:10]],
            "details": {
                "wallet_count": len(accum),
                "total_volume_usd": round(total_accum_vol, 2),
                "avg_smart_money_score": round(avg_sm, 2),
                "pattern": "gradual_accumulation",
                "wallets": [{
                    "id": n["id"],
                    "label": (n.get("label") or n["id"].split(":")[-1])[:20],
                    "inflow": round(node_in_vol.get(n["id"], 0), 2),
                    "sm_score": n.get("smartMoneyScore", 0),
                } for n in accum[:20]],
            },
        })

    if distrib:
        total_distrib_vol = sum(node_out_vol.get(n["id"], 0) for n in distrib)
        sm_scores = [n.get("smartMoneyScore", 0) for n in distrib]
        avg_sm = sum(sm_scores) / len(sm_scores) if sm_scores else 0
        avg_out_ratio = sum(node_out_vol.get(n["id"], 0) / max(node_in_vol.get(n["id"], 0) + node_out_vol.get(n["id"], 0), 1) for n in distrib) / len(distrib)
        sell_pressure = min(1.0, avg_out_ratio)
        dispersion = min(1.0, len(distrib) / 10)
        vol_score = min(1.0, math.log10(total_distrib_vol + 1) / log_max_vol) if log_max_vol > 0 else 0

        conf = round(min(0.95, max(0.15, 0.4 * sell_pressure + 0.3 * dispersion + 0.2 * vol_score + 0.1 * min(1.0, avg_sm * 2))), 2)
        breakdown = [f"Avg sell ratio: {avg_out_ratio:.0%}", f"Distributing wallets: {len(distrib)}", f"Total outflow: {_fmt_usd(total_distrib_vol)}"]

        signals.append({
            "type": "distribution",
            "category": "smart_money",
            "confidence": conf,
            "confidence_breakdown": breakdown,
            "summary": f"Distribution detected — {len(distrib)} wallet{'s' if len(distrib) > 1 else ''}",
            "entities": [n["id"] for n in distrib[:10]],
            "details": {
                "wallet_count": len(distrib),
                "total_volume_usd": round(total_distrib_vol, 2),
                "avg_smart_money_score": round(avg_sm, 2),
                "pattern": "distribution",
                "wallets": [{
                    "id": n["id"],
                    "label": (n.get("label") or n["id"].split(":")[-1])[:20],
                    "outflow": round(node_out_vol.get(n["id"], 0), 2),
                    "sm_score": n.get("smartMoneyScore", 0),
                } for n in distrib[:20]],
            },
        })

    whale_nodes = [n for n in nodes if (n.get("capitalInfluenceScore") or 0) > 0.3 or (n.get("totalFlowUsd") or 0) > 1_000_000]
    if whale_nodes:
        total_whale_flow = sum(node_in_vol.get(n["id"], 0) + node_out_vol.get(n["id"], 0) for n in whale_nodes)
        avg_influence = sum(n.get("capitalInfluenceScore", 0) for n in whale_nodes) / len(whale_nodes)
        vol_score = min(1.0, math.log10(total_whale_flow + 1) / log_max_vol) if log_max_vol > 0 else 0
        conf = round(min(0.95, max(0.2, 0.4 * min(1.0, avg_influence * 2) + 0.3 * vol_score + 0.3 * min(1.0, len(whale_nodes) / 5))), 2)
        breakdown = [f"Large players: {len(whale_nodes)}", f"Total flow: {_fmt_usd(total_whale_flow)}", f"Avg influence: {avg_influence:.2f}"]

        signals.append({
            "type": "whale_activity",
            "category": "smart_money",
            "confidence": conf,
            "confidence_breakdown": breakdown,
            "summary": f"Whale activity — {len(whale_nodes)} large player{'s' if len(whale_nodes) > 1 else ''}",
            "entities": [n["id"] for n in whale_nodes[:10]],
            "details": {
                "whale_count": len(whale_nodes),
                "total_flow_usd": round(total_whale_flow, 2),
                "whales": [{
                    "id": n["id"],
                    "label": (n.get("label") or n["id"].split(":")[-1])[:20],
                    "flow_usd": round(node_in_vol.get(n["id"], 0) + node_out_vol.get(n["id"], 0), 2),
                    "influence": n.get("capitalInfluenceScore", 0),
                } for n in whale_nodes[:20]],
            },
        })

    # ═══════════════════════════════════════════
    # RISK — STRICT: only loop_routing, high_risk_nodes
    # ═══════════════════════════════════════════
    risky_nodes = [n for n in nodes if (n.get("riskScore") or n.get("risk_score") or 0) > 0.3]
    if risky_nodes:
        avg_risk = sum(n.get("riskScore", n.get("risk_score", 0)) for n in risky_nodes) / len(risky_nodes)
        severity = "high" if avg_risk >= 0.7 else "medium" if avg_risk >= 0.5 else "low"
        conf = round(min(0.95, avg_risk), 2)
        breakdown = [f"Flagged nodes: {len(risky_nodes)}", f"Avg risk score: {avg_risk:.2f}", f"Severity: {severity}"]

        signals.append({
            "type": "high_risk_nodes",
            "category": "risk",
            "confidence": conf,
            "confidence_breakdown": breakdown,
            "summary": f"{severity.title()} risk — {len(risky_nodes)} flagged node{'s' if len(risky_nodes) > 1 else ''}",
            "entities": [n["id"] for n in risky_nodes[:10]],
            "details": {
                "node_count": len(risky_nodes),
                "avg_risk_score": round(avg_risk, 2),
                "severity": severity,
                "nodes": [{
                    "id": n["id"],
                    "label": (n.get("label") or n["id"].split(":")[-1])[:20],
                    "risk_score": n.get("riskScore", n.get("risk_score", 0)),
                    "type": n.get("type", "wallet"),
                } for n in risky_nodes[:5]],
            },
        })

    # Loop detection (A↔B)
    edge_pairs = defaultdict(int)
    for e in edges:
        src, tgt = e.get("source", ""), e.get("target", "")
        edge_pairs[(src, tgt)] += 1
    loops = []
    seen_loops = set()
    for (s, t), cnt in edge_pairs.items():
        if (t, s) in edge_pairs and (t, s) not in seen_loops:
            seen_loops.add((s, t))
            seen_loops.add((t, s))
            vol_fwd = sum(e.get("amountUsd") or e.get("volume_usd") or 0 for e in edges if e.get("source") == s and e.get("target") == t)
            vol_rev = sum(e.get("amountUsd") or e.get("volume_usd") or 0 for e in edges if e.get("source") == t and e.get("target") == s)
            loops.append({"a": s, "b": t, "fwd_vol": vol_fwd, "rev_vol": vol_rev, "tx": cnt + edge_pairs[(t, s)]})

    if loops:
        total_loop_vol = sum(lp["fwd_vol"] + lp["rev_vol"] for lp in loops)
        # Formula: loop_count(0.35) + volume(0.25) + symmetry(0.25) + time_density(0.15)
        loop_count_score = min(1.0, len(loops) / 10)
        vol_score = min(1.0, math.log10(total_loop_vol + 1) / log_max_vol) if log_max_vol > 0 else 0
        symmetries = []
        for lp in loops:
            total_lp = lp["fwd_vol"] + lp["rev_vol"]
            if total_lp > 0:
                symmetries.append(min(lp["fwd_vol"], lp["rev_vol"]) / max(lp["fwd_vol"], lp["rev_vol"], 1))
        avg_symmetry = sum(symmetries) / len(symmetries) if symmetries else 0
        # No timestamp data → time_density = 0.5 default
        time_density = 0.5

        conf = round(min(0.95, max(0.15, 0.35 * loop_count_score + 0.25 * vol_score + 0.25 * avg_symmetry + 0.15 * time_density)), 2)
        breakdown = [f"Loops detected: {len(loops)}", f"Volume symmetry: {avg_symmetry:.0%}", f"Total volume: {_fmt_usd(total_loop_vol)}"]

        signals.append({
            "type": "loop_routing",
            "category": "risk",
            "confidence": conf,
            "confidence_breakdown": breakdown,
            "summary": f"Loop routing — {len(loops)} bidirectional pair{'s' if len(loops) > 1 else ''}",
            "entities": list({lp["a"] for lp in loops[:5]} | {lp["b"] for lp in loops[:5]}),
            "details": {
                "loop_count": len(loops),
                "total_volume_usd": round(total_loop_vol, 2),
                "avg_symmetry": round(avg_symmetry, 2),
                "loops": [{
                    "node_a": (node_map.get(lp["a"], {}).get("label") or lp["a"].split(":")[-1])[:20],
                    "node_b": (node_map.get(lp["b"], {}).get("label") or lp["b"].split(":")[-1])[:20],
                    "volume_usd": round(lp["fwd_vol"] + lp["rev_vol"], 2),
                    "tx_count": lp["tx"],
                } for lp in sorted(loops, key=lambda x: x["fwd_vol"] + x["rev_vol"], reverse=True)[:5]],
            },
        })

    # ═══════════════════════════════════════════
    # TOKEN FLOW — STRICT: only rotation
    # Uses DB token_flow_data when edge-level tokenGroup is all "OTHER"
    # ═══════════════════════════════════════════
    token_volumes = defaultdict(float)
    token_sources = defaultdict(set)
    token_targets = defaultdict(set)
    for te in token_edges:
        tk = te["token"]
        if tk and tk != "OTHER":
            token_volumes[tk] += te["volume"]
            token_sources[tk].add(te["source"])
            token_targets[tk].add(te["target"])

    # If no real token diversity from edges, use DB token_flow_data
    if len(token_volumes) < 2 and token_flow_data:
        # Build per-token aggregation from DB flows via DEX pools
        # Pool-level: which tokens flow through which pools
        pool_token_sell = defaultdict(lambda: defaultdict(float))  # pool → token → sell_volume
        pool_token_buy = defaultdict(lambda: defaultdict(float))   # pool → token → buy_volume
        pool_node_map = {}  # pool_addr → node_id
        for tf in token_flow_data:
            pool = tf["pool"]
            tk = tf["token"]
            pool_node_map[pool] = tf.get("node_id", "")
            if tf["side"] == "SELL":
                pool_token_sell[pool][tk] += tf["volume"]
            else:
                pool_token_buy[pool][tk] += tf["volume"]

        # Find wallets connected to pools with different tokens
        # wallet → { token: total_volume } via graph edges
        wallet_token_exposure = defaultdict(lambda: defaultdict(float))
        for e in edges:
            src, tgt = e.get("source", ""), e.get("target", "")
            vol = e.get("amountUsd") or e.get("volume_usd") or 0
            # If source is a pool → wallet is target
            src_parts = src.split(":")
            tgt_parts = tgt.split(":")
            if len(src_parts) >= 2 and src_parts[0] == "dex":
                pool_addr = src_parts[1].lower()
                for tk, tv in {**pool_token_sell.get(pool_addr, {}), **pool_token_buy.get(pool_addr, {})}.items():
                    wallet_token_exposure[tgt][tk] += vol
            if len(tgt_parts) >= 2 and tgt_parts[0] == "dex":
                pool_addr = tgt_parts[1].lower()
                for tk, tv in {**pool_token_sell.get(pool_addr, {}), **pool_token_buy.get(pool_addr, {})}.items():
                    wallet_token_exposure[src][tk] += vol

        # Aggregate token-level sells and buys across all pools
        token_sell_vol = defaultdict(float)
        token_buy_vol = defaultdict(float)
        for pool, tokens in pool_token_sell.items():
            for tk, vol in tokens.items():
                token_sell_vol[tk] += vol
        for pool, tokens in pool_token_buy.items():
            for tk, vol in tokens.items():
                token_buy_vol[tk] += vol

        # Find token pairs where one is being sold and another bought
        sell_sorted = sorted(token_sell_vol.items(), key=lambda x: -x[1])
        buy_sorted = sorted(token_buy_vol.items(), key=lambda x: -x[1])

        for sell_tk, sell_vol in sell_sorted[:5]:
            for buy_tk, buy_vol in buy_sorted[:5]:
                if sell_tk == buy_tk:
                    continue
                # Find wallets exposed to both tokens
                shared_wallets = set()
                for w, tokens in wallet_token_exposure.items():
                    if sell_tk in tokens and buy_tk in tokens:
                        shared_wallets.add(w)

                if not shared_wallets:
                    # Fallback: just having both tokens flow through connected pools
                    sell_pools = {p for p, tks in pool_token_sell.items() if sell_tk in tks}
                    buy_pools = {p for p, tks in pool_token_buy.items() if buy_tk in tks}
                    if sell_pools and buy_pools:
                        shared_wallets = {"pool_indirect"}

                if shared_wallets:
                    max_vol = max(sell_vol, buy_vol, 1)
                    vol_score = min(1.0, math.log10(min(sell_vol, buy_vol) + 1) / math.log10(max_vol + 1)) if max_vol > 1 else 0
                    shared_score = min(1.0, len(shared_wallets) / 5)
                    direction = min(sell_vol, buy_vol) / max_vol

                    conf = round(min(0.90, max(0.2, 0.35 * 0.8 + 0.2 * vol_score + 0.25 * shared_score + 0.2 * direction)), 2)
                    breakdown = [
                        f"Exit: {sell_tk} (${sell_vol:,.0f})",
                        f"Entry: {buy_tk} (${buy_vol:,.0f})",
                        f"Connected wallets: {len(shared_wallets)}",
                        f"Volume ratio: {direction:.0%}",
                    ]
                    entity_ids = [w for w in list(shared_wallets)[:20] if w != "pool_indirect"]

                    # Build wallet details for UI
                    wallet_details = []
                    for wid in entity_ids:
                        n = node_map.get(wid, {})
                        # Per-wallet exposure to sell/buy tokens
                        sell_exp = wallet_token_exposure.get(wid, {}).get(sell_tk, 0)
                        buy_exp = wallet_token_exposure.get(wid, {}).get(buy_tk, 0)
                        wallet_details.append({
                            "id": wid,
                            "label": (n.get("label") or wid.split(":")[-1])[:20],
                            "sell_exposure": round(sell_exp, 2),
                            "buy_exposure": round(buy_exp, 2),
                        })

                    signals.append({
                        "type": "rotation",
                        "category": "token_flow",
                        "confidence": conf,
                        "confidence_breakdown": breakdown,
                        "summary": f"Rotation: {sell_tk} → {buy_tk}",
                        "entities": entity_ids,
                        "details": {
                            "token_from": sell_tk, "token_to": buy_tk,
                            "token_from_label": sell_tk, "token_to_label": buy_tk,
                            "volume_from_usd": round(sell_vol, 2), "volume_to_usd": round(buy_vol, 2),
                            "shared_wallets": len(shared_wallets), "flow_type": "capital_rotation",
                            "wallets": wallet_details,
                        },
                    })
                    break
            if signals and signals[-1].get("type") == "rotation":
                break
    else:
        # Original edge-based detection (when edges have real tokenGroup)
        tokens_sorted = sorted(token_volumes.items(), key=lambda x: -x[1])
        if len(tokens_sorted) >= 2:
            for i in range(min(len(tokens_sorted), 3)):
                for j in range(i + 1, min(len(tokens_sorted), 4)):
                    tk_a, vol_a = tokens_sorted[i]
                    tk_b, vol_b = tokens_sorted[j]
                    shared = token_targets[tk_a] & token_sources[tk_b]
                    if not shared:
                        shared = token_sources[tk_a] & token_targets[tk_b]
                        if shared:
                            tk_a, tk_b = tk_b, tk_a
                            vol_a, vol_b = vol_b, vol_a
                    if shared:
                        transition = 0.8
                        vol_score = min(1.0, math.log10(min(vol_a, vol_b) + 1) / log_max_vol) if log_max_vol > 0 else 0
                        shared_score = min(1.0, len(shared) / 5)
                        direction = min(vol_a, vol_b) / max(vol_a, vol_b, 1)

                        conf = round(min(0.90, max(0.2, 0.35 * transition + 0.2 * vol_score + 0.25 * shared_score + 0.2 * direction)), 2)
                        tk_a_label = tk_a.split(":")[-1][:12] if ":" in tk_a else tk_a[:12]
                        tk_b_label = tk_b.split(":")[-1][:12] if ":" in tk_b else tk_b[:12]
                        breakdown = [f"Token pair: {tk_a_label} → {tk_b_label}", f"Shared wallets: {len(shared)}", f"Volume ratio: {direction:.0%}"]

                        signals.append({
                            "type": "rotation",
                            "category": "token_flow",
                            "confidence": conf,
                            "confidence_breakdown": breakdown,
                            "summary": f"Rotation: {tk_a_label} → {tk_b_label}",
                            "entities": list(shared)[:10],
                            "details": {
                                "token_from": tk_a, "token_to": tk_b,
                                "token_from_label": tk_a_label, "token_to_label": tk_b_label,
                                "volume_from_usd": round(vol_a, 2), "volume_to_usd": round(vol_b, 2),
                                "shared_wallets": len(shared), "flow_type": "capital_rotation",
                            },
                        })
                        break
                if signals and signals[-1].get("type") == "rotation":
                    break

    # ═══════════════════════════════════════════
    # ROUTE — cex_flow_summary (always computed)
    # ═══════════════════════════════════════════
    cex_nodes = [n for n in nodes if (n.get("type") or "").lower() in ("cex", "exchange") or n.get("id", "").startswith("cex:") or n.get("id", "").startswith("exchange:")]
    if cex_nodes:
        total_cex_in = sum(node_in_vol.get(n["id"], 0) for n in cex_nodes)
        total_cex_out = sum(node_out_vol.get(n["id"], 0) for n in cex_nodes)
        net = total_cex_in - total_cex_out
        flow_state = "inflow" if net > 0 else "outflow" if net < 0 else "neutral"
        total = total_cex_in + total_cex_out
        conf = round(min(0.95, max(0.2, 0.5 + abs(net) / max(total, 1) * 0.4)), 2)
        breakdown = [f"CEX inflow: {_fmt_usd(total_cex_in)}", f"CEX outflow: {_fmt_usd(total_cex_out)}", f"Net: {_fmt_usd(net)}"]

        signals.append({
            "type": "cex_flow_summary",
            "category": "route",
            "confidence": conf,
            "confidence_breakdown": breakdown,
            "summary": f"CEX net {flow_state}: {'+' if net >= 0 else ''}{_fmt_usd(net)}",
            "entities": [n["id"] for n in cex_nodes[:10]],
            "details": {
                "cex_count": len(cex_nodes),
                "total_inflow_usd": round(total_cex_in, 2),
                "total_outflow_usd": round(total_cex_out, 2),
                "net_flow_usd": round(net, 2),
                "flow_state": flow_state,
            },
        })

    signals.sort(key=lambda s: -s["confidence"])
    return signals


def _compute_market_context(signals):
    """
    Market Context Engine — combines signals into a single macro interpretation.
    Returns None if confidence < 0.4 (not enough evidence).
    """
    if not signals:
        return None

    # Signal classification: bullish vs bearish
    BULLISH_TYPES = {
        "accumulation": 1.0,
        "whale_activity": 0.8,
        "entity_cluster": 0.8,  # strong clusters = institutional presence
        "rotation": 0.6,
    }
    BEARISH_TYPES = {
        "distribution": 1.0,
        "high_risk_nodes": 1.5,
        "loop_routing": 1.5,
    }
    # CEX flow: outflow = bullish (capital leaving exchanges), inflow = bearish
    CEX_WEIGHT = 1.2

    bullish_score = 0.0
    bearish_score = 0.0
    drivers = []
    risks = []

    for sig in signals:
        st = sig["type"]
        conf = sig["confidence"]

        if st in BULLISH_TYPES:
            w = BULLISH_TYPES[st]
            bullish_score += conf * w
            drivers.append({"type": st, "confidence": conf, "weight": w, "contribution": round(conf * w, 2)})

        elif st in BEARISH_TYPES:
            w = BEARISH_TYPES[st]
            bearish_score += conf * w
            risks.append({"type": st, "confidence": conf, "weight": w, "contribution": round(conf * w, 2)})

        elif st == "cex_flow_summary":
            det = sig.get("details", {})
            net = det.get("net_flow_usd", 0)
            if net < 0:  # outflow = bullish
                bullish_score += conf * CEX_WEIGHT
                drivers.append({"type": "cex_outflow", "confidence": conf, "weight": CEX_WEIGHT, "contribution": round(conf * CEX_WEIGHT, 2)})
            elif net > 0:  # inflow = bearish
                bearish_score += conf * CEX_WEIGHT
                risks.append({"type": "cex_inflow", "confidence": conf, "weight": CEX_WEIGHT, "contribution": round(conf * CEX_WEIGHT, 2)})

    total = bullish_score + bearish_score
    if total == 0:
        return None

    # Determine context type
    if bullish_score > bearish_score * 1.2:
        ctx_type = "bullish"
    elif bearish_score > bullish_score * 1.2:
        ctx_type = "bearish"
    elif total < 0.5:
        ctx_type = "uncertain"
    else:
        ctx_type = "neutral"

    # Confidence = how clearly one side dominates
    confidence = round(abs(bullish_score - bearish_score) / total, 2) if total > 0 else 0

    if confidence < 0.15:
        ctx_type = "neutral"

    # Don't show if too uncertain
    if confidence < 0.1 and ctx_type in ("neutral", "uncertain"):
        return None

    SUMMARIES = {
        "bullish": "Bullish setup forming",
        "bearish": "Bearish pressure detected",
        "neutral": "Mixed signals — no clear direction",
        "uncertain": "Insufficient data for market read",
    }

    return {
        "type": ctx_type,
        "confidence": confidence,
        "summary": SUMMARIES[ctx_type],
        "bullish_score": round(bullish_score, 2),
        "bearish_score": round(bearish_score, 2),
        "drivers": sorted(drivers, key=lambda x: -x["contribution"]),
        "risks": sorted(risks, key=lambda x: -x["contribution"]),
    }



def _fmt_usd(v):
    """Format USD value for intelligence summaries."""
    if not v and v != 0:
        return "$0"
    av = abs(v)
    if av >= 1e9:
        return f"${v / 1e9:.1f}B"
    if av >= 1e6:
        return f"${v / 1e6:.1f}M"
    if av >= 1e3:
        return f"${v / 1e3:.1f}K"
    return f"${v:.0f}"



async def _enrich_routes_with_db_wash_alerts(routes):
    """Cross-reference CEX routes with stored wash alerts from DB."""
    if _db is None or not routes:
        return routes

    try:
        # Collect all node IDs from all routes
        all_node_ids = set()
        for r in routes:
            for nid in r.get("path", []):
                all_node_ids.add(nid)

        if not all_node_ids:
            return routes

        # Fetch wash alerts that involve any of these nodes
        cursor = _db["graph_wash_alerts"].find(
            {"nodes": {"$in": list(all_node_ids)}},
            {"_id": 0, "alert_id": 1, "pattern_type": 1, "nodes": 1,
             "confidence": 1, "amount_usd": 1}
        ).limit(50)
        db_alerts = await cursor.to_list(50)

        if not db_alerts:
            return routes

        # Build node → alerts map
        node_alerts = {}
        for alert in db_alerts:
            for nid in alert.get("nodes", []):
                if nid not in node_alerts:
                    node_alerts[nid] = []
                node_alerts[nid].append(alert)

        # Enrich each route with matching DB alerts
        for route in routes:
            path = route.get("path", [])
            matching = []
            seen_alert_ids = set()
            for nid in path:
                for alert in node_alerts.get(nid, []):
                    aid = alert["alert_id"]
                    if aid not in seen_alert_ids:
                        seen_alert_ids.add(aid)
                        matching.append({
                            "alert_id": aid,
                            "pattern_type": alert["pattern_type"],
                            "confidence": alert.get("confidence", 0),
                            "amount_usd": alert.get("amount_usd", 0),
                        })
            route["db_wash_alerts"] = matching
            # Boost wash_score if DB alerts found
            if matching and route.get("wash_score", 0) < 0.3:
                route["wash_score"] = round(min(route.get("wash_score", 0) + 0.15 * len(matching), 1.0), 2)

    except Exception as e:
        print(f"[Wash enrichment] Error: {e}")

    return routes




def _find_cex_routes(nodes, render_edges, center_node_id):
    """
    Find CEX-to-CEX paths through the graph.
    Returns a list of routes, each with a path (list of node IDs)
    and direction (deposit=towards CEX, withdraw=from CEX).
    Uses BFS from each CEX node to find paths to other CEX nodes.
    """
    from collections import deque

    CEX_TYPES = {"cex", "exchange"}

    # Build node type lookup
    node_types = {}
    for n in nodes:
        nid = n.get("id", "")
        ntype = (n.get("type") or "wallet").lower()
        node_types[nid] = ntype

    # Identify CEX node IDs
    cex_ids = set()
    for nid, ntype in node_types.items():
        if ntype in CEX_TYPES or nid.startswith("cex:") or nid.startswith("exchange:"):
            cex_ids.add(nid)

    if len(cex_ids) < 2:
        return []

    # Build adjacency list from edges (undirected for pathfinding)
    adj = {}
    for e in render_edges:
        src = e.get("source", "")
        tgt = e.get("target", "")
        if src not in adj:
            adj[src] = set()
        if tgt not in adj:
            adj[tgt] = set()
        adj[src].add(tgt)
        adj[tgt].add(src)

    MAX_HOPS = 15
    routes = []
    seen_pairs = set()

    for start_cex in cex_ids:
        # BFS from this CEX to find other CEX nodes
        queue = deque([(start_cex, [start_cex])])
        visited = {start_cex}

        while queue:
            current, path = queue.popleft()
            if len(path) > MAX_HOPS:
                continue

            for neighbor in adj.get(current, []):
                if neighbor in visited:
                    continue
                new_path = path + [neighbor]
                visited.add(neighbor)

                if neighbor in cex_ids and neighbor != start_cex:
                    # Found a path from CEX to CEX
                    pair_key = tuple(sorted([start_cex, neighbor]))
                    if pair_key not in seen_pairs:
                        seen_pairs.add(pair_key)
                        routes.append({
                            "from_cex": start_cex,
                            "to_cex": neighbor,
                            "path": new_path,
                            "hops": len(new_path) - 2,  # intermediate nodes
                        })
                else:
                    # Continue BFS through non-CEX nodes
                    queue.append((neighbor, new_path))

    # Sort by shortest path first
    routes.sort(key=lambda r: r["hops"])
    routes = routes[:20]  # Limit to top 20 routes

    # Wash / fake routing analysis on found routes
    routes = _analyze_wash_patterns(routes, nodes, render_edges, adj, cex_ids, node_types)

    return routes


def _analyze_wash_patterns(routes, nodes, edges, adj, cex_ids, node_types):
    """
    Analyze found CEX-to-CEX routes for wash / fake routing patterns.
    Adds wash_flags[] and wash_score to each route.

    Detected patterns:
    1. bidirectional  — A→…→B AND B→…→A exist (mirror route)
    2. pass_through   — intermediates have very low degree (≤3), likely shell wallets
    3. shared_intermediates — multiple routes share the same intermediates (layering)
    4. circular       — a node appears >1 time in a path (loop)
    5. volume_symmetric — bidirectional routes with similar volumes (suggesting wash)
    """
    from collections import defaultdict

    # Pre-compute node degrees from edges
    node_degree = defaultdict(int)
    for e in edges:
        node_degree[e.get("source", "")] += 1
        node_degree[e.get("target", "")] += 1

    # Pre-compute edge volumes per pair
    edge_volumes = defaultdict(float)
    for e in edges:
        src = e.get("source", "")
        tgt = e.get("target", "")
        vol = e.get("amountUsd") or e.get("volumeUsd") or e.get("volume_usd") or e.get("amount_usd") or 0
        edge_volumes[(src, tgt)] += vol
        edge_volumes[(tgt, src)] += vol

    # Build pair → route map for bidirectional detection
    pair_routes = defaultdict(list)
    for i, r in enumerate(routes):
        pair_key = tuple(sorted([r["from_cex"], r["to_cex"]]))
        pair_routes[pair_key].append(i)

    # Intermediate frequency map (for shared_intermediates detection)
    intermediate_usage = defaultdict(int)
    for r in routes:
        path = r.get("path", [])
        for nid in path[1:-1]:  # skip source and target CEX
            intermediate_usage[nid] += 1

    for ri, route in enumerate(routes):
        flags = []
        path = route.get("path", [])
        from_cex = route["from_cex"]
        to_cex = route["to_cex"]
        intermediates = path[1:-1]

        # 1. Bidirectional: check if reverse route exists
        has_reverse = False
        for rj, other in enumerate(routes):
            if rj == ri:
                continue
            if other["from_cex"] == to_cex and other["to_cex"] == from_cex:
                has_reverse = True
                break
            if other["from_cex"] == from_cex and other["to_cex"] == to_cex and rj != ri:
                has_reverse = True
                break
        if has_reverse:
            flags.append({
                "type": "bidirectional",
                "label": "Mirror Route",
                "description": "Reverse path between same CEX pair exists",
                "severity": "high",
            })

        # 2. Pass-through: intermediates with degree ≤ 3
        pass_through_count = 0
        for nid in intermediates:
            deg = node_degree.get(nid, 0)
            if deg <= 3:
                pass_through_count += 1
        if pass_through_count > 0 and len(intermediates) > 0:
            ratio = pass_through_count / len(intermediates)
            sev = "high" if ratio >= 0.8 else "medium" if ratio >= 0.5 else "low"
            flags.append({
                "type": "pass_through",
                "label": "Shell Wallets",
                "description": f"{pass_through_count}/{len(intermediates)} intermediates have ≤3 connections",
                "severity": sev,
                "count": pass_through_count,
            })

        # 3. Shared intermediates: same wallet in multiple routes
        shared = [nid for nid in intermediates if intermediate_usage[nid] >= 2]
        if shared:
            flags.append({
                "type": "shared_intermediates",
                "label": "Layering",
                "description": f"{len(shared)} intermediate{'s' if len(shared) > 1 else ''} used in multiple routes",
                "severity": "medium" if len(shared) >= 2 else "low",
                "count": len(shared),
            })

        # 4. Circular: a node repeats in the path
        if len(set(path)) < len(path):
            flags.append({
                "type": "circular",
                "label": "Loop Detected",
                "description": "Path contains a circular reference",
                "severity": "high",
            })

        # 5. Volume symmetry: route volume ≈ reverse route volume
        if has_reverse:
            fwd_vol = sum(edge_volumes.get((path[i], path[i + 1]), 0) for i in range(len(path) - 1))
            for other in routes:
                if other["from_cex"] == to_cex and other["to_cex"] == from_cex:
                    rev_path = other.get("path", [])
                    rev_vol = sum(edge_volumes.get((rev_path[i], rev_path[i + 1]), 0) for i in range(len(rev_path) - 1))
                    if fwd_vol > 0 and rev_vol > 0:
                        ratio = min(fwd_vol, rev_vol) / max(fwd_vol, rev_vol)
                        if ratio >= 0.7:
                            sev = "high" if ratio >= 0.9 else "medium"
                            flags.append({
                                "type": "volume_symmetric",
                                "label": "Volume Match",
                                "description": f"Bidirectional volume ratio {ratio:.0%}",
                                "severity": sev,
                                "ratio": round(ratio, 2),
                            })
                    break

        # Calculate composite wash_score
        severity_weights = {"high": 0.35, "medium": 0.20, "low": 0.10}
        raw_score = sum(severity_weights.get(f["severity"], 0.1) for f in flags)
        wash_score = round(min(raw_score, 1.0), 2)

        route["wash_flags"] = flags
        route["wash_score"] = wash_score

    return routes


def _compute_node_ring_colors(nodes, edges):
    """
    Compute accumulation/distribution ring for each node.
    Green ring = ACCUMULATION (net inflow > threshold)
    Red ring   = DISTRIBUTION (net outflow > threshold)
    Intensity via opacity = |net| / volume, clamped [0.35, 1.0]
    Threshold = volume * 0.05
    """
    from collections import defaultdict

    node_inflow = defaultdict(float)
    node_outflow = defaultdict(float)

    for edge in edges:
        src = edge.get("source", "")
        tgt = edge.get("target", "")
        weight = edge.get("weight", 0) or edge.get("amountUsd", 0) or 1
        node_outflow[src] += weight
        node_inflow[tgt] += weight

    for n in nodes:
        nid = n.get("id", "")
        inflow = node_inflow.get(nid, 0)
        outflow = node_outflow.get(nid, 0)
        volume = inflow + outflow
        net = inflow - outflow
        threshold = volume * 0.05

        if volume == 0:
            n["ring_color"] = None
            n["ring_opacity"] = 0
            n["flow_state"] = "ROUTING"
        elif abs(net) < threshold:
            # Balanced in/out → pass-through / routing behavior
            n["ring_color"] = "#EAB308"
            n["ring_opacity"] = 0.5
            n["flow_state"] = "ROUTING"
        elif net > 0:
            strength = abs(net) / volume
            n["ring_color"] = "#22c55e"
            n["ring_opacity"] = round(max(0.35, min(1.0, strength)), 2)
            n["flow_state"] = "ACCUMULATION"
        else:
            strength = abs(net) / volume
            n["ring_color"] = "#EF4444"
            n["ring_opacity"] = round(max(0.35, min(1.0, strength)), 2)
            n["flow_state"] = "DISTRIBUTION"

        n["flow_category"] = (n["flow_state"]).lower()

    return nodes


def _rank_and_limit_edges(edges, max_per_node=30):
    """P0.2: Limit edges per node, keeping highest-value ones."""
    from collections import defaultdict

    # Group edges by source node
    by_source = defaultdict(list)
    for e in edges:
        by_source[e.get("source", "")].append(e)

    # For each node, keep top edges by amount
    result = []
    seen = set()
    for node_id, node_edges in by_source.items():
        ranked = sorted(node_edges, key=lambda x: x.get("amountUsd", 0) or x.get("total_amount_usd", 0) or 0, reverse=True)
        for e in ranked[:max_per_node]:
            ekey = id(e)
            if ekey not in seen:
                seen.add(ekey)
                result.append(e)

    return result



# ========================================================
# ARKHAM-STYLE RENDER ENDPOINT (Multi-Lane Edges)
# ========================================================

@router.get("/render/{node_id:path}")
async def render_graph(
    node_id: str,
    depth: int = Query(default=2, ge=1, le=3),
    limit: int = Query(default=150, ge=1, le=500),
    identity_level: str = Query(default=None, description="Identity level: wallet, cluster, entity"),
    time_start: int = Query(default=None, description="Start timestamp"),
    time_end: int = Query(default=None, description="End timestamp"),
    mode: str = Query(default=None, description="Graph mode filter"),
    chains: str = Query(default=None, description="Comma-separated chain keys, e.g. ethereum,arbitrum"),
):
    """
    Arkham-style render endpoint.
    Returns nodes + pre-computed multi-lane render edges with curvature/width/opacity/color.
    Pipeline: relations → lane_aggregation (runtime) → projection → render_edges
    Multi-chain: edges NEVER cross chains, nodes unique per chain+address.
    """
    if _db is None:
        return {"nodes": [], "edges": [], "meta": {"error": "no_database"}}

    node_id = normalize_existing_id(node_id)
    chain_list = [c.strip() for c in chains.split(",") if c.strip()] if chains else None

    # Step 1: Get raw graph via existing projection (handles identity levels, mode, compression)
    result = await project_graph(
        _db,
        center_node_id=node_id,
        depth=depth,
        max_nodes=limit,
        max_edges=limit * 4,
        mode=mode,
        start_time=time_start,
        end_time=time_end,
        level=identity_level,
        chains=chain_list,
    )

    raw_nodes = result.get("nodes", [])
    raw_edges = result.get("edges", [])

    if not raw_nodes:
        return {"nodes": [], "edges": [], "meta": {"source": "render_empty"}}

    # Step 1.5: Edge ranking — limit edges per hub node
    raw_edges = _rank_and_limit_edges(raw_edges, max_per_node=50)

    # Step 2: Lane aggregation (runtime — no persistence)
    lanes = aggregate_lanes(raw_edges)

    # Step 3: Corridor stacking + render edge projection
    render_edges = build_render_edges(lanes, center_node_id=node_id)

    # Step 4: Filter edges to only include nodes that exist
    node_ids = {n.get("id", "") for n in raw_nodes}
    render_edges = [e for e in render_edges if e["source"] in node_ids and e["target"] in node_ids]

    # Step 4.5: CEX Flow — find CEX-to-CEX routes (no filtering, just pathfinding)
    cex_routes = []
    if mode == "cex_flow":
        cex_routes = _find_cex_routes(raw_nodes, render_edges, node_id)

    # Step 5: Compute ring colors for each node based on flow categories
    raw_nodes = _compute_node_ring_colors(raw_nodes, render_edges)

    # ── Unified Intelligence Layer ──
    token_flow_data = []
    if _db is not None:
        token_flow_data = await _fetch_token_flows_for_nodes(raw_nodes)
    intelligence = _compute_graph_intelligence(raw_nodes, render_edges, token_flow_data)

    # Market context from FULL intelligence
    market_context = _compute_market_context(intelligence)

    # STRICT: Filter intelligence by mode category (no cross-category leaking)
    if mode:
        MODE_CATEGORY_MAP = {
            "smart_money": "smart_money",
            "entity": "entity",
            "risk": "risk",
            "token_rotation": "token_flow",
            "cex_flow": "route",
        }
        filter_cat = MODE_CATEGORY_MAP.get(mode)
        if filter_cat:
            intelligence = [sig for sig in intelligence if sig.get("category") == filter_cat]

    result = {
        "nodes": raw_nodes,
        "edges": render_edges,
        "intelligence": intelligence,
        "market_context": market_context,
        "meta": {
            "source": "render",
            "center_node": node_id,
            "raw_edge_count": len(raw_edges),
            "lane_count": len(lanes),
            "render_edge_count": len(render_edges),
            "mode": mode,
            "level": identity_level,
        },
    }
    if cex_routes:
        result["cex_routes"] = cex_routes
    return result


# ========================================================
# GRAPH PLAYBACK (P3)
# ========================================================

@router.get("/playback")
async def graph_playback(
    node_id: str = Query(default="", description="Center node ID"),
    resolution: str = Query(default="24h", regex="^(1h|24h|7d|30d|90d)$"),
    level: str = Query(default="", regex="^(|wallet|cluster|entity)$"),
):
    """Get temporal playback frames from graph_relation_buckets."""
    if _db is None:
        return {"frames": [], "total_frames": 0}
    result = await get_playback_frames(
        _db,
        node_id=node_id,
        resolution=resolution,
        level=level or None,
    )
    return result



@router.get("/playback/events")
async def graph_playback_events(
    node_id: str = Query(default="", description="Center node ID"),
    seeds: str = Query(default="", description="Comma-separated seed node IDs"),
    resolution: str = Query(default="24h", description="Time bucket resolution"),
    max_events: int = Query(default=500, ge=1, le=1000),
):
    """Flow events for edge-by-edge animation (no graph reload)."""
    if _db is None:
        return {"events": [], "total_events": 0, "time_range": {"start": 0, "end": 0}}
    return await get_playback_events(
        _db,
        node_id=node_id or None,
        seeds=seeds or None,
        resolution=resolution,
        max_events=max_events,
    )



# ═══════════════════════════════════════════════════════════════
# MOMENTUM ENDPOINT — Entity history for EntityTrendChart
# ═══════════════════════════════════════════════════════════════

momentum_router = APIRouter(prefix="/api/momentum", tags=["momentum"])


@momentum_router.get("/entity/{entity_type}/{entity_id:path}/history")
async def entity_momentum_history(
    entity_type: str,
    entity_id: str,
    days: int = Query(default=30, ge=1, le=365),
):
    """
    Return daily momentum history for an entity.
    Aggregates graph_relation_buckets by day to compute flow-based momentum.
    Handles partial node IDs (e.g. wallet:0x123 matches wallet:0x123:ethereum).
    """
    if _db is None:
        return {"history": [], "entity": f"{entity_type}:{entity_id}", "days": days}

    import re
    node_prefix = f"{entity_type}:{entity_id}"
    # Use regex prefix match to handle partial IDs (missing chain suffix)
    prefix_re = re.compile(f"^{re.escape(node_prefix)}")

    query = {"$or": [
        {"source_id": {"$regex": f"^{re.escape(node_prefix)}"}},
        {"target_id": {"$regex": f"^{re.escape(node_prefix)}"}},
    ]}
    buckets = await _db["graph_relation_buckets"].find(query, {"_id": 0}).to_list(length=10000)

    if not buckets:
        buckets = await _db["graph_relations"].find(query, {"_id": 0}).to_list(length=5000)

    # Aggregate by day
    from collections import defaultdict
    daily = defaultdict(lambda: {"volume_usd": 0, "tx_count": 0, "inflow": 0, "outflow": 0})

    for b in buckets:
        day = b.get("bucket_day") or ""
        if not day:
            ts = b.get("first_seen") or b.get("last_seen") or ""
            if isinstance(ts, str) and len(ts) >= 10:
                day = ts[:10]
            else:
                continue

        vol = b.get("total_amount_usd", 0) or 0
        txc = b.get("tx_count", 1) or 1
        daily[day]["volume_usd"] += vol
        daily[day]["tx_count"] += txc

        src = b.get("source_id", "")
        if prefix_re.match(src):
            daily[day]["outflow"] += vol
        else:
            daily[day]["inflow"] += vol

    if not daily:
        return {"history": [], "entity": node_prefix, "days": days}

    sorted_days = sorted(daily.keys())[-days:]

    volumes = [daily[d]["volume_usd"] for d in sorted_days]
    max_vol = max(volumes) if volumes else 1
    if max_vol == 0:
        max_vol = 1

    history = []
    for d in sorted_days:
        data = daily[d]
        vol_norm = (data["volume_usd"] / max_vol) * 70
        tx_factor = min(data["tx_count"] / 10, 1) * 30
        momentum = round(min(vol_norm + tx_factor, 100), 1)

        history.append({
            "date": d,
            "momentum_score": momentum,
            "volume_usd": round(data["volume_usd"], 2),
            "tx_count": data["tx_count"],
            "inflow_usd": round(data["inflow"], 2),
            "outflow_usd": round(data["outflow"], 2),
            "net_flow_usd": round(data["inflow"] - data["outflow"], 2),
        })

    return {"history": history, "entity": node_prefix, "days": days}
