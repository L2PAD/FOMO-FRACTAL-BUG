"""
Build Graph from Existing Data — P3 Data Pipeline
===================================================
Reads from existing MongoDB collections and populates:
  1. graph_nodes (from wallet_registry, address_labels, cex_entities, entities_v2)
  2. graph_relations (from wallet_counterparty_flow_buckets, onchain_v2_dex_swaps)

Run: python seed_graph_from_db.py
"""

import asyncio
import time
from motor.motor_asyncio import AsyncIOMotorClient
import os
from datetime import datetime, timezone

from graph_storage import init_storage, ensure_storage_indexes
from graph_normalizer import normalize_node_id
from corridor_detector import detect_corridors
from edge_tagger import tag_edges


CHAIN_MAP = {1: "ethereum", 42161: "arbitrum", 137: "polygon", 10: "optimism", 8453: "base"}


def _chain_name(chain_id):
    if isinstance(chain_id, str):
        return chain_id
    return CHAIN_MAP.get(chain_id, "ethereum")


def _node_id(address, chain="ethereum", ntype="wallet"):
    addr = address.lower() if address else ""
    return normalize_node_id(ntype, addr, chain)


async def build_graph_nodes(db):
    """Build graph_nodes from wallet_registry, address_labels, cex_entities, entities_v2"""
    coll = db["graph_nodes"]
    inserted = 0

    # 1. wallet_registry (458 wallets)
    print("[Nodes] Reading wallet_registry...")
    cursor = db["wallet_registry"].find({}, {"_id": 0})
    async for doc in cursor:
        addr = (doc.get("address") or "").lower()
        if not addr:
            continue
        chain = doc.get("chain", "ethereum")
        wtype = doc.get("type", "wallet")
        # Map exchange → cex
        if wtype == "exchange":
            wtype = "cex"
        nid = _node_id(addr, chain, wtype)
        node = {
            "id": nid,
            "type": wtype,
            "chain": chain,
            "address": addr,
            "label": doc.get("label") or doc.get("entity") or addr[:10],
            "entity": doc.get("entity"),
            "confidence": doc.get("confidence", 0),
            "cluster_id": doc.get("entity", "").lower().replace(" ", "_") if doc.get("entity") else None,
            "degree": 0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await coll.update_one({"id": nid}, {"$set": node}, upsert=True)
        inserted += 1

    print(f"  wallet_registry: {inserted} nodes")

    # 2. onchain_v2_address_labels (389 labels)
    print("[Nodes] Reading onchain_v2_address_labels...")
    label_count = 0
    cursor = db["onchain_v2_address_labels"].find({}, {"_id": 0})
    async for doc in cursor:
        addr = (doc.get("address") or "").lower()
        if not addr:
            continue
        chain = _chain_name(doc.get("chainId", 1))
        ltype = (doc.get("type") or "wallet").lower()
        if ltype == "exchange":
            ltype = "cex"
        elif ltype == "dex":
            ltype = "dex"
        nid = _node_id(addr, chain, ltype)
        node = {
            "id": nid,
            "type": ltype,
            "chain": chain,
            "address": addr,
            "label": doc.get("name") or addr[:10],
            "entity": doc.get("entityId"),
            "cluster_id": doc.get("clusterId"),
            "confidence": doc.get("confidence", 0),
            "degree": 0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await coll.update_one({"id": nid}, {"$set": node}, upsert=True)
        label_count += 1

    print(f"  address_labels: {label_count} nodes")

    # 3. cex_entities (26 CEXs)
    print("[Nodes] Reading cex_entities...")
    cex_count = 0
    cursor = db["cex_entities"].find({}, {"_id": 0})
    async for doc in cursor:
        eid = doc.get("entityId", "")
        nid = f"cex:{eid}:ethereum"
        node = {
            "id": nid,
            "type": "cex",
            "chain": "ethereum",
            "label": doc.get("entityName") or eid,
            "entity": eid,
            "address_count": doc.get("addressCount", 0),
            "degree": 0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await coll.update_one({"id": nid}, {"$set": node}, upsert=True)
        cex_count += 1

    print(f"  cex_entities: {cex_count} nodes")

    # 4. entities_v2 (15 entities)
    print("[Nodes] Reading entities_v2...")
    ent_count = 0
    cursor = db["entities_v2"].find({}, {"_id": 0})
    async for doc in cursor:
        slug = doc.get("slug", "")
        cat = (doc.get("category") or "").lower()
        if cat in ("cex", "exchange"):
            ntype = "cex"
        elif cat == "dex":
            ntype = "dex"
        elif cat == "bridge":
            ntype = "bridge"
        else:
            ntype = "contract"
        nid = f"{ntype}:{slug}:ethereum"
        node = {
            "id": nid,
            "type": ntype,
            "chain": "ethereum",
            "label": doc.get("name") or slug,
            "entity": slug,
            "confidence": doc.get("confidence", 0),
            "degree": 0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await coll.update_one({"id": nid}, {"$set": node}, upsert=True)
        ent_count += 1

    print(f"  entities_v2: {ent_count} nodes")

    total = await coll.count_documents({})
    print(f"[Nodes] Total graph_nodes: {total}")
    return total


async def build_graph_relations(db):
    """
    Build aggregated graph_relations from:
    1. wallet_counterparty_flow_buckets (already aggregated!)
    2. onchain_v2_dex_swaps (aggregated by sender→pool)
    """
    coll = db["graph_relations"]
    inserted = 0

    # 1. wallet_counterparty_flow_buckets (8,064 — already aggregated by day)
    print("[Relations] Reading wallet_counterparty_flow_buckets...")

    # Aggregate across all buckets: group by (wallet, counterparty)
    pipeline = [
        {"$group": {
            "_id": {
                "src": "$walletAddress",
                "tgt": "$counterpartyAddress",
            },
            "total_in_usd": {"$sum": "$inUsd"},
            "total_out_usd": {"$sum": "$outUsd"},
            "total_transfers": {"$sum": "$transfers"},
            "first_seen": {"$min": "$bucketDate"},
            "last_seen": {"$max": "$bucketDate"},
            "chain_id": {"$first": "$chainId"},
            "entity_name": {"$first": "$entityName"},
            "entity_type": {"$first": "$entityType"},
        }},
        {"$match": {"total_transfers": {"$gte": 1}}},
    ]

    flow_count = 0
    async for doc in db["wallet_counterparty_flow_buckets"].aggregate(pipeline):
        src_addr = (doc["_id"]["src"] or "").lower()
        tgt_addr = (doc["_id"]["tgt"] or "").lower()
        if not src_addr or not tgt_addr:
            continue

        chain = _chain_name(doc.get("chain_id", 1))

        # Resolve node types from graph_nodes
        src_type = "wallet"
        tgt_type = "wallet"
        src_node = await db["graph_nodes"].find_one({"address": src_addr}, {"type": 1})
        tgt_node = await db["graph_nodes"].find_one({"address": tgt_addr}, {"type": 1})
        if src_node:
            src_type = src_node.get("type", "wallet")
        if tgt_node:
            tgt_type = tgt_node.get("type", "wallet")

        src_id = _node_id(src_addr, chain, src_type)
        tgt_id = _node_id(tgt_addr, chain, tgt_type)

        total_usd = (doc.get("total_in_usd") or 0) + (doc.get("total_out_usd") or 0)

        # Determine relation type
        relation_type = "transfer"
        if tgt_type == "cex" or (doc.get("entity_type") or "").lower() == "cex":
            relation_type = "deposit"
        elif src_type == "cex":
            relation_type = "withdraw"
        elif tgt_type == "dex" or src_type == "dex":
            relation_type = "swap"

        # Compute direction
        direction = "out"
        if (doc.get("total_in_usd") or 0) > (doc.get("total_out_usd") or 0):
            direction = "in"

        # Parse dates to timestamps
        first_seen = _parse_date(doc.get("first_seen"))
        last_seen = _parse_date(doc.get("last_seen"))

        rel = {
            "source_id": src_id,
            "target_id": tgt_id,
            "relation_type": relation_type,
            "direction": direction,
            "chain": chain,
            "tx_count": doc.get("total_transfers", 0),
            "total_amount_usd": round(total_usd, 2),
            "first_seen": first_seen,
            "last_seen": last_seen,
            "confidence": 0.9,
            "tags": [],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        await coll.update_one(
            {"source_id": src_id, "target_id": tgt_id, "relation_type": relation_type},
            {"$set": rel},
            upsert=True,
        )
        flow_count += 1

    print(f"  wallet_counterparty_flow_buckets: {flow_count} relations")

    # 2. onchain_v2_dex_swaps — aggregate by (sender → pool/protocol)
    print("[Relations] Reading onchain_v2_dex_swaps (aggregating)...")

    swap_pipeline = [
        {"$group": {
            "_id": {
                "sender": "$sender",
                "pool": "$pool",
                "protocol": "$protocol",
            },
            "count": {"$sum": 1},
            "chain_id": {"$first": "$chainId"},
            "first_block": {"$min": "$blockNumber"},
            "last_block": {"$max": "$blockNumber"},
        }},
        {"$match": {"count": {"$gte": 1}}},
        {"$limit": 5000},  # cap to avoid overload
    ]

    swap_count = 0
    async for doc in db["onchain_v2_dex_swaps"].aggregate(swap_pipeline):
        sender = (doc["_id"]["sender"] or "").lower()
        pool = (doc["_id"]["pool"] or "").lower()
        protocol = doc["_id"].get("protocol") or "unknown_dex"

        if not sender or not pool:
            continue

        chain = _chain_name(doc.get("chain_id", 1))

        src_id = _node_id(sender, chain, "wallet")
        tgt_id = _node_id(pool, chain, "dex")

        # Ensure nodes exist
        await db["graph_nodes"].update_one(
            {"id": src_id},
            {"$setOnInsert": {"id": src_id, "type": "wallet", "chain": chain, "address": sender, "label": f"0x{sender[2:6]}...{sender[-4:]}", "degree": 0}},
            upsert=True,
        )
        await db["graph_nodes"].update_one(
            {"id": tgt_id},
            {"$setOnInsert": {"id": tgt_id, "type": "dex", "chain": chain, "address": pool, "label": protocol, "degree": 0}},
            upsert=True,
        )

        rel = {
            "source_id": src_id,
            "target_id": tgt_id,
            "relation_type": "swap",
            "direction": "out",
            "chain": chain,
            "tx_count": doc.get("count", 0),
            "total_amount_usd": 0,  # dex_swaps don't have USD amount in this schema
            "first_seen": doc.get("first_block", 0),
            "last_seen": doc.get("last_block", 0),
            "confidence": 0.85,
            "tags": ["dex_swap"],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        await coll.update_one(
            {"source_id": src_id, "target_id": tgt_id, "relation_type": "swap"},
            {"$set": rel},
            upsert=True,
        )
        swap_count += 1

    print(f"  dex_swaps: {swap_count} relations")

    # Update node degrees
    print("[Relations] Computing node degrees...")
    async for doc in coll.aggregate([
        {"$group": {"_id": "$source_id", "degree": {"$sum": 1}}},
    ]):
        await db["graph_nodes"].update_one(
            {"id": doc["_id"]},
            {"$set": {"degree": doc["degree"]}},
        )
    async for doc in coll.aggregate([
        {"$group": {"_id": "$target_id", "degree": {"$sum": 1}}},
    ]):
        await db["graph_nodes"].update_one(
            {"id": doc["_id"]},
            {"$inc": {"degree": doc["degree"]}},
        )

    total = await coll.count_documents({})
    print(f"[Relations] Total graph_relations: {total}")
    return total


def _parse_date(val):
    """Convert date string or value to Unix timestamp"""
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return int(val)
    try:
        dt = datetime.fromisoformat(str(val).replace("Z", "+00:00"))
        return int(dt.timestamp())
    except Exception:
        return 0


async def rebuild_snapshots(db):
    """Rebuild snapshots for anchor entities using new relations"""
    from graph_storage import build_graph_from_relations, save_snapshot

    anchors = []
    cursor = db["graph_anchor_entities"].find({}, {"_id": 0})
    async for doc in cursor:
        anchors.append(doc)

    print(f"[Snapshots] Rebuilding for {len(anchors)} anchors...")

    # Clear old snapshots
    await db["graph_snapshots"].delete_many({})

    built = 0
    for anchor in anchors:
        addr = (anchor.get("address") or "").lower()
        atype = anchor.get("type", "wallet")
        chain = anchor.get("chain", "ethereum")
        label = anchor.get("label", "")

        node_id = normalize_node_id(atype, addr, chain)
        snapshot_key = f"{node_id}:2:150:400"

        nodes, edges = await build_graph_from_relations(node_id, depth=2, limit_nodes=150, limit_edges=400)

        if nodes or edges:
            node_map = {n.get("id", ""): n for n in nodes}
            edges = tag_edges(edges, node_map)
            corridors = detect_corridors(nodes, edges)

            await save_snapshot(snapshot_key, node_id, nodes, edges, corridors)
            built += 1
            print(f"  {label}: {len(nodes)} nodes, {len(edges)} edges, {len(corridors)} corridors")

    print(f"[Snapshots] Built: {built}/{len(anchors)}")
    return built


async def warm_cache(db):
    """Warm neighbor cache for top nodes"""
    from graph_storage import build_graph_from_relations

    # Get top nodes by degree
    top_nodes = []
    cursor = db["graph_nodes"].find({"degree": {"$gt": 0}}, {"_id": 0}).sort("degree", -1).limit(30)
    async for doc in cursor:
        top_nodes.append(doc)

    print(f"[Cache] Warming for {len(top_nodes)} top nodes...")

    warmed = 0
    for node in top_nodes:
        nid = node["id"]
        cache_key = f"{nid}:2:150:400"

        nodes, edges = await build_graph_from_relations(nid, depth=1, limit_nodes=50, limit_edges=150)

        if nodes:
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

    print(f"[Cache] Warmed: {warmed}")
    return warmed


async def main():
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
    client = AsyncIOMotorClient(mongo_url)
    db_name = os.environ.get("DB_NAME", "intelligence_engine")
    db = client[db_name]

    init_storage(db)
    await ensure_storage_indexes()

    start = time.time()

    print("=" * 60)
    print("GRAPH DATA PIPELINE — Building from existing data")
    print("=" * 60)

    # Step 1: Build nodes
    node_count = await build_graph_nodes(db)

    # Step 2: Build relations
    rel_count = await build_graph_relations(db)

    # Step 3: Rebuild snapshots
    snap_count = await rebuild_snapshots(db)

    # Step 4: Warm cache
    cache_count = await warm_cache(db)

    elapsed = round(time.time() - start, 1)

    print("=" * 60)
    print(f"DONE in {elapsed}s")
    print(f"  graph_nodes: {node_count}")
    print(f"  graph_relations: {rel_count}")
    print(f"  graph_snapshots: {snap_count}")
    print(f"  graph_neighbors_cache: {cache_count}")
    print("=" * 60)

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
