"""
Snapshot Builder Job — P3.3
============================
Builds pre-computed graph snapshots for anchor entities.
Run manually or as a cron job.

Usage:
  python build_graph_snapshots.py

Flow:
  load anchor entities → for each: build graph from relations →
  run corridor detection → run edge tagging → save snapshot
"""

import asyncio
import time
from motor.motor_asyncio import AsyncIOMotorClient
import os

from graph_storage import init_storage, ensure_storage_indexes, build_graph_from_relations, save_snapshot, get_snapshot
from graph_normalizer import normalize_node_id
from corridor_detector import detect_corridors
from edge_tagger import tag_edges


async def build_snapshots():
    """Build snapshots for all anchor entities"""
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
    client = AsyncIOMotorClient(mongo_url)
    db_name = os.environ.get("DB_NAME", "intelligence_engine")
    db = client[db_name]

    init_storage(db)
    await ensure_storage_indexes()

    # Load anchor entities
    anchors = []
    cursor = db["graph_anchor_entities"].find({}, {"_id": 0})
    async for doc in cursor:
        anchors.append(doc)

    print(f"[SnapshotBuilder] Found {len(anchors)} anchor entities")

    built = 0
    skipped = 0

    for anchor in anchors:
        addr = anchor.get("address", "").lower()
        atype = anchor.get("type", "wallet")
        chain = anchor.get("chain", "ethereum")
        label = anchor.get("label", addr[:10])

        node_id = normalize_node_id(atype, addr, chain)
        snapshot_key = f"{node_id}:2:150:400"

        # Check if snapshot already exists and is fresh (< 1 hour)
        existing = await get_snapshot(snapshot_key)
        if existing:
            skipped += 1
            continue

        start = time.time()

        # Build graph from relations
        nodes, edges = await build_graph_from_relations(
            node_id, depth=2, limit_nodes=150, limit_edges=400
        )

        # Tag edges
        node_map = {n.get("id", ""): n for n in nodes}
        edges = tag_edges(edges, node_map)

        # Detect corridors
        corridors = detect_corridors(nodes, edges)

        # Save snapshot
        await save_snapshot(snapshot_key, node_id, nodes, edges, corridors)

        elapsed = round((time.time() - start) * 1000, 1)
        built += 1
        print(f"  [{built}] {label} ({node_id}): {len(nodes)} nodes, {len(edges)} edges, {len(corridors)} corridors [{elapsed}ms]")

    print(f"[SnapshotBuilder] Done: built={built}, skipped={skipped}, total={len(anchors)}")

    client.close()


if __name__ == "__main__":
    asyncio.run(build_snapshots())
