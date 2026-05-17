"""
Fix Graph IDs & Rebuild — One-time Migration
==============================================
1. Normalize all graph_anchor_entities  (lowercase addresses)
2. Normalize all graph_nodes            (canonical IDs, merge dupes)
3. Normalize all graph_relations        (canonical source_id / target_id)
4. Auto-create missing anchor nodes
5. Clear graph_snapshots + graph_neighbors_cache
6. Rebuild snapshots for anchors with data
7. Warm neighbor cache for top nodes

Run:  cd /app/backend && python fix_and_rebuild.py
"""

import asyncio
import os
import time
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

from graph_normalizer import normalize_node_id, normalize_existing_id, extract_address
from graph_storage import init_storage, ensure_storage_indexes, build_graph_from_relations, save_snapshot
from corridor_detector import detect_corridors
from edge_tagger import tag_edges


async def step1_normalize_anchors(db):
    """Normalize anchor entities: lowercase addresses, canonical IDs"""
    coll = db["graph_anchor_entities"]
    anchors = await coll.find({}).to_list(100)
    updated = 0

    for doc in anchors:
        old_addr = doc.get("address", "")
        new_addr = old_addr.lower()
        if old_addr != new_addr:
            await coll.update_one(
                {"_id": doc["_id"]},
                {"$set": {"address": new_addr}},
            )
            updated += 1

    total = await coll.count_documents({})
    print(f"[Step 1] Anchors normalized: {updated} updated, {total} total")
    return total


async def step2_normalize_nodes(db):
    """Normalize graph_nodes: canonical IDs, merge duplicates"""
    coll = db["graph_nodes"]
    cursor = coll.find({})
    rename_map = {}  # old_id -> new_id
    updated = 0
    merged = 0

    docs = await cursor.to_list(length=10000)
    for doc in docs:
        old_id = doc.get("id", "")
        new_id = normalize_existing_id(old_id)

        if old_id != new_id:
            rename_map[old_id] = new_id

            existing = await coll.find_one({"id": new_id})
            if existing:
                # Merge: keep the one with higher degree
                if (doc.get("degree") or 0) > (existing.get("degree") or 0):
                    await coll.delete_one({"_id": existing["_id"]})
                    await coll.update_one(
                        {"_id": doc["_id"]},
                        {"$set": {"id": new_id, "updated_at": datetime.now(timezone.utc).isoformat()}},
                    )
                else:
                    await coll.delete_one({"_id": doc["_id"]})
                merged += 1
            else:
                await coll.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"id": new_id, "updated_at": datetime.now(timezone.utc).isoformat()}},
                )
                updated += 1

    total = await coll.count_documents({})
    print(f"[Step 2] Nodes normalized: {updated} updated, {merged} merged, {total} total")
    return rename_map


async def step3_normalize_relations(db, rename_map):
    """Normalize graph_relations: canonical source_id / target_id"""
    coll = db["graph_relations"]
    cursor = coll.find({})
    updated = 0

    docs = await cursor.to_list(length=20000)
    for doc in docs:
        old_src = doc.get("source_id", "")
        old_tgt = doc.get("target_id", "")

        new_src = rename_map.get(old_src, normalize_existing_id(old_src))
        new_tgt = rename_map.get(old_tgt, normalize_existing_id(old_tgt))

        if old_src != new_src or old_tgt != new_tgt:
            # Check for duplicate relation
            existing = await coll.find_one({
                "source_id": new_src,
                "target_id": new_tgt,
                "relation_type": doc.get("relation_type"),
                "_id": {"$ne": doc["_id"]},
            })
            if existing:
                # Merge: sum tx_count and total_amount_usd, keep latest
                await coll.update_one(
                    {"_id": existing["_id"]},
                    {"$inc": {
                        "tx_count": doc.get("tx_count", 0),
                        "total_amount_usd": doc.get("total_amount_usd", 0),
                    }},
                )
                await coll.delete_one({"_id": doc["_id"]})
            else:
                await coll.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {
                        "source_id": new_src,
                        "target_id": new_tgt,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }},
                )
            updated += 1

    total = await coll.count_documents({})
    print(f"[Step 3] Relations normalized: {updated} updated, {total} total")


async def step4_create_missing_anchor_nodes(db):
    """Create graph_nodes for anchor entities that don't exist yet"""
    anchors = await db["graph_anchor_entities"].find({}, {"_id": 0}).to_list(100)
    created = 0

    for a in anchors:
        addr = a.get("address", "").lower()
        atype = a.get("type", "wallet")
        chain = a.get("chain", "ethereum")
        label = a.get("label", addr[:10])

        node_id = normalize_node_id(atype, addr, chain)

        existing = await db["graph_nodes"].find_one({"id": node_id})
        if not existing:
            node = {
                "id": node_id,
                "type": atype,
                "chain": chain,
                "address": addr,
                "label": label,
                "entity": label.lower().replace(" ", "_"),
                "confidence": 1.0,
                "degree": 0,
                "is_anchor": True,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            await db["graph_nodes"].update_one({"id": node_id}, {"$set": node}, upsert=True)
            created += 1

    total = await db["graph_nodes"].count_documents({})
    print(f"[Step 4] Anchor nodes created: {created}, total nodes: {total}")


async def step5_clear_cache(db):
    """Clear snapshots and neighbor cache"""
    snap_del = await db["graph_snapshots"].delete_many({})
    cache_del = await db["graph_neighbors_cache"].delete_many({})
    print(f"[Step 5] Cleared: {snap_del.deleted_count} snapshots, {cache_del.deleted_count} cache entries")


async def step6_rebuild_snapshots(db):
    """Rebuild snapshots for all anchor entities"""
    anchors = await db["graph_anchor_entities"].find({}, {"_id": 0}).to_list(100)
    built = 0
    empty = 0

    for anchor in anchors:
        addr = anchor.get("address", "").lower()
        atype = anchor.get("type", "wallet")
        chain = anchor.get("chain", "ethereum")
        label = anchor.get("label", addr[:10])

        node_id = normalize_node_id(atype, addr, chain)
        snapshot_key = f"{node_id}:2:150:400"

        nodes, edges = await build_graph_from_relations(
            node_id, depth=2, limit_nodes=150, limit_edges=400
        )

        if nodes or edges:
            node_map = {n.get("id", ""): n for n in nodes}
            edges = tag_edges(edges, node_map)
            corridors = detect_corridors(nodes, edges)

            await save_snapshot(snapshot_key, node_id, nodes, edges, corridors)
            built += 1
            print(f"  {label}: {len(nodes)} nodes, {len(edges)} edges, {len(corridors)} corridors")
        else:
            empty += 1

    print(f"[Step 6] Snapshots: {built} built, {empty} empty (need Infura), {len(anchors)} total")
    return built


async def step7_warm_cache(db):
    """Warm neighbor cache for top-degree nodes"""
    top_nodes = await db["graph_nodes"].find(
        {"degree": {"$gt": 0}}, {"_id": 0}
    ).sort("degree", -1).limit(30).to_list(30)

    warmed = 0
    for node in top_nodes:
        nid = node["id"]
        cache_key = f"{nid}:1:50:150"

        nodes, edges = await build_graph_from_relations(nid, depth=1, limit_nodes=50, limit_edges=150)
        if not nodes:
            continue

        node_map = {n.get("id", ""): n for n in nodes}
        edges = tag_edges(edges, node_map)
        corridors = detect_corridors(nodes, edges)

        cache_doc = {
            "cache_key": cache_key,
            "node_id": nid,
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
        warmed += 1

    print(f"[Step 7] Cache warmed: {warmed}/{len(top_nodes)}")


async def main():
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME", "intelligence_engine")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    init_storage(db)
    await ensure_storage_indexes()

    start = time.time()

    print("=" * 60)
    print("GRAPH ID NORMALIZATION & REBUILD")
    print("=" * 60)

    await step1_normalize_anchors(db)
    rename_map = await step2_normalize_nodes(db)
    await step3_normalize_relations(db, rename_map)
    await step4_create_missing_anchor_nodes(db)
    await step5_clear_cache(db)
    await step6_rebuild_snapshots(db)
    await step7_warm_cache(db)

    # Final stats
    stats = {
        "graph_nodes": await db["graph_nodes"].count_documents({}),
        "graph_relations": await db["graph_relations"].count_documents({}),
        "graph_snapshots": await db["graph_snapshots"].count_documents({}),
        "graph_neighbors_cache": await db["graph_neighbors_cache"].count_documents({}),
        "graph_anchor_entities": await db["graph_anchor_entities"].count_documents({}),
    }

    elapsed = round(time.time() - start, 1)

    print("=" * 60)
    print(f"DONE in {elapsed}s")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print("=" * 60)

    # Check for duplicates
    pipeline = [
        {"$group": {"_id": "$id", "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 1}}},
    ]
    dupes = await db["graph_nodes"].aggregate(pipeline).to_list(100)
    if dupes:
        print(f"WARNING: {len(dupes)} duplicate node IDs found!")
    else:
        print("No duplicate node IDs found.")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
