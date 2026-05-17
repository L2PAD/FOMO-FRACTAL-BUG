"""
Neighbor Cache Warming Script
==============================
Precomputes neighbor graphs for anchor entities and top-degree nodes.
Stores results in graph_neighbors_cache with TTL.

Run:  cd /app/backend && python warm_neighbor_cache.py
"""

import asyncio
import os
import time
from datetime import datetime, timezone

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

from graph_storage import init_storage, ensure_storage_indexes, build_graph_from_relations
from graph_normalizer import normalize_node_id
from corridor_detector import detect_corridors
from edge_tagger import tag_edges
from infura_fallback import init_infura_fallback, infura_fallback_for_node


# Cache configs matching graph_core_routes defaults
DEPTH = 2
LIMIT_NODES = 150
LIMIT_EDGES = 400


async def warm_single(db, node_id, label=""):
    """Warm cache for a single node. Returns True if data was cached."""
    cache_key = f"{node_id}:{DEPTH}:{LIMIT_NODES}:{LIMIT_EDGES}"

    nodes, edges = await build_graph_from_relations(
        node_id, depth=DEPTH, limit_nodes=LIMIT_NODES, limit_edges=LIMIT_EDGES
    )

    # If no data from relations, try Infura
    if not nodes and not edges:
        from graph_normalizer import parse_node_id
        ntype, _, nchain = parse_node_id(node_id)
        nodes, edges = await infura_fallback_for_node(node_id, ntype, nchain)

    if not nodes:
        return False

    node_map = {n.get("id", ""): n for n in nodes}
    edges = tag_edges(edges, node_map)
    corridors = detect_corridors(nodes, edges)

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
    await db["graph_neighbors_cache"].update_one(
        {"cache_key": cache_key}, {"$set": cache_doc}, upsert=True,
    )
    print(f"  {label or node_id[:40]:30s} | {len(nodes):4d} nodes | {len(edges):4d} edges")
    return True


async def main():
    load_dotenv()
    client = AsyncIOMotorClient(os.environ.get("MONGO_URL"))
    db = client[os.environ.get("DB_NAME", "intelligence_engine")]
    init_storage(db)
    init_infura_fallback(db)
    await ensure_storage_indexes()

    start = time.time()
    print("=" * 60)
    print("NEIGHBOR CACHE WARMING")
    print("=" * 60)

    # Phase 1: All anchor entities
    print("\n--- Anchor Entities ---")
    anchors = await db["graph_anchor_entities"].find({}, {"_id": 0}).to_list(50)
    warmed = 0
    for a in anchors:
        addr = a.get("address", "").lower()
        atype = a.get("type", "wallet")
        chain = a.get("chain", "ethereum")
        label = a.get("label", "")
        node_id = normalize_node_id(atype, addr, chain)
        if await warm_single(db, node_id, label):
            warmed += 1
        await asyncio.sleep(0.1)  # Rate limit for Infura

    print(f"\nAnchors warmed: {warmed}/{len(anchors)}")

    # Phase 2: Top-degree nodes (non-anchor)
    print("\n--- Top Degree Nodes ---")
    anchor_ids = set()
    for a in anchors:
        addr = a.get("address", "").lower()
        atype = a.get("type", "wallet")
        chain = a.get("chain", "ethereum")
        anchor_ids.add(normalize_node_id(atype, addr, chain))

    warmed_ids = set(anchor_ids)

    top_degree = await db["graph_nodes"].find(
        {"degree": {"$gt": 1}, "id": {"$nin": list(warmed_ids)}},
        {"_id": 0}
    ).sort("degree", -1).limit(80).to_list(80)

    top_warmed = 0
    for node in top_degree:
        nid = node["id"]
        label = node.get("label", nid[:20])
        if await warm_single(db, nid, label):
            top_warmed += 1
            warmed_ids.add(nid)

    print(f"\nTop degree warmed: {top_warmed}/{len(top_degree)}")

    # Phase 3: Top-flow nodes (non-already-warmed)
    print("\n--- Top Flow Nodes ---")
    top_flow = await db["graph_nodes"].find(
        {"total_flow_usd": {"$gt": 0}, "id": {"$nin": list(warmed_ids)}},
        {"_id": 0}
    ).sort("total_flow_usd", -1).limit(60).to_list(60)

    flow_warmed = 0
    for node in top_flow:
        nid = node["id"]
        label = node.get("label", nid[:20])
        if await warm_single(db, nid, label):
            flow_warmed += 1
            warmed_ids.add(nid)

    print(f"\nTop flow warmed: {flow_warmed}/{len(top_flow)}")

    # Phase 4: Cluster member nodes
    print("\n--- Cluster Nodes ---")
    cluster_nodes = await db["graph_nodes"].find(
        {"cluster_id": {"$exists": True, "$ne": None}, "id": {"$nin": list(warmed_ids)}},
        {"_id": 0}
    ).limit(30).to_list(30)

    cluster_warmed = 0
    for node in cluster_nodes:
        nid = node["id"]
        label = node.get("label", nid[:20])
        if await warm_single(db, nid, label):
            cluster_warmed += 1
            warmed_ids.add(nid)

    print(f"\nCluster nodes warmed: {cluster_warmed}/{len(cluster_nodes)}")

    # Phase 5: Importance-ranked nodes (fill to target ~150)
    print("\n--- Importance-Ranked Nodes ---")
    importance_nodes = await db["graph_nodes"].find(
        {"importance_score": {"$gt": 0}, "id": {"$nin": list(warmed_ids)}},
        {"_id": 0}
    ).sort("importance_score", -1).limit(60).to_list(60)

    imp_warmed = 0
    for node in importance_nodes:
        nid = node["id"]
        label = node.get("label", nid[:20])
        if await warm_single(db, nid, label):
            imp_warmed += 1
            warmed_ids.add(nid)

    print(f"\nImportance nodes warmed: {imp_warmed}/{len(importance_nodes)}")

    # Stats
    cache_count = await db["graph_neighbors_cache"].count_documents({})
    elapsed = round(time.time() - start, 1)

    print("=" * 60)
    print(f"DONE in {elapsed}s")
    print(f"Total cache entries: {cache_count}")
    print("=" * 60)

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
