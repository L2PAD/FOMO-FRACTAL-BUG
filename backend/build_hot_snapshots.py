"""
Build Hot Snapshots — P2.5
============================
Builds pre-computed graph snapshots for:
  - All anchor entities
  - Top degree nodes
  - Top flow nodes
  - Cluster representative nodes

Run periodically (1-2 times/day) to minimize snapshot misses.

Usage:
  python build_hot_snapshots.py
"""

import asyncio
import os
import time
from datetime import datetime, timezone

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

from graph_storage import init_storage, ensure_storage_indexes, build_graph_from_relations, save_snapshot
from graph_normalizer import normalize_node_id
from corridor_detector import detect_corridors
from edge_tagger import tag_edges
from infura_fallback import init_infura_fallback, infura_fallback_for_node
from graph_normalizer import parse_node_id

DEPTH = 2
LIMIT_NODES = 150
LIMIT_EDGES = 400


async def build_snapshot_for(db, node_id, label=""):
    """Build and save snapshot for a single node."""
    snapshot_key = f"{node_id}:{DEPTH}:{LIMIT_NODES}:{LIMIT_EDGES}"

    nodes, edges = await build_graph_from_relations(
        node_id, depth=DEPTH, limit_nodes=LIMIT_NODES, limit_edges=LIMIT_EDGES
    )

    if not nodes and not edges:
        ntype, _, nchain = parse_node_id(node_id)
        nodes, edges = await infura_fallback_for_node(node_id, ntype, nchain)

    if not nodes:
        return False

    node_map = {n.get("id", ""): n for n in nodes}
    edges = tag_edges(edges, node_map)
    corridors = detect_corridors(nodes, edges)

    await save_snapshot(snapshot_key, node_id, nodes, edges, corridors)
    print(f"  {label or node_id[:40]:30s} | {len(nodes):4d} nodes | {len(edges):4d} edges | {len(corridors)} corridors")
    return True


async def main():
    load_dotenv()
    client = AsyncIOMotorClient(os.environ.get("MONGO_URL"))
    db = client[os.environ.get("DB_NAME", "intelligence_engine")]
    init_storage(db)
    init_infura_fallback(db)
    await ensure_storage_indexes()

    start = time.time()
    built = 0
    built_ids = set()

    print("=" * 60)
    print("HOT SNAPSHOT BUILDER")
    print("=" * 60)

    # Phase 1: Anchor entities
    print("\n--- Anchors ---")
    anchors = await db["graph_anchor_entities"].find({}, {"_id": 0}).to_list(50)
    for a in anchors:
        addr = a.get("address", "").lower()
        atype = a.get("type", "wallet")
        chain = a.get("chain", "ethereum")
        node_id = normalize_node_id(atype, addr, chain)
        if await build_snapshot_for(db, node_id, a.get("label", "")):
            built += 1
            built_ids.add(node_id)
        await asyncio.sleep(0.05)

    # Phase 2: Top degree nodes
    print("\n--- Top Degree ---")
    top_degree = await db["graph_nodes"].find(
        {"degree": {"$gt": 3}, "id": {"$nin": list(built_ids)}},
        {"_id": 0}
    ).sort("degree", -1).limit(50).to_list(50)

    for node in top_degree:
        nid = node["id"]
        if await build_snapshot_for(db, nid, node.get("label", nid[:20])):
            built += 1
            built_ids.add(nid)
        await asyncio.sleep(0.05)

    # Phase 3: Top flow nodes
    print("\n--- Top Flow ---")
    top_flow = await db["graph_nodes"].find(
        {"total_flow_usd": {"$gt": 1000}, "id": {"$nin": list(built_ids)}},
        {"_id": 0}
    ).sort("total_flow_usd", -1).limit(30).to_list(30)

    for node in top_flow:
        nid = node["id"]
        if await build_snapshot_for(db, nid, node.get("label", nid[:20])):
            built += 1
            built_ids.add(nid)

    # Phase 4: Cluster nodes
    print("\n--- Clusters ---")
    cluster_nodes = await db["graph_nodes"].find(
        {"cluster_id": {"$exists": True, "$ne": None}, "id": {"$nin": list(built_ids)}},
        {"_id": 0}
    ).limit(20).to_list(20)

    for node in cluster_nodes:
        nid = node["id"]
        if await build_snapshot_for(db, nid, node.get("label", nid[:20])):
            built += 1
            built_ids.add(nid)

    # Stats
    snap_count = await db["graph_snapshots"].count_documents({})
    elapsed = round(time.time() - start, 1)

    print("\n" + "=" * 60)
    print(f"DONE in {elapsed}s")
    print(f"Built: {built} snapshots")
    print(f"Total snapshots: {snap_count}")
    print("=" * 60)

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
