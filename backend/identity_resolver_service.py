"""
Identity Resolver Service — P0 Identity Hierarchy Layer
=========================================================
Manages the 3-level identity hierarchy:
  Level 1 — Wallet Graph:  wallet → wallet edges
  Level 2 — Cluster Graph: wallets collapsed → cluster → cluster edges
  Level 3 — Entity Graph:  clusters collapsed → entity → entity edges

Stores mappings in graph_identity_map:
  { wallet_id, cluster_id, entity_id, confidence, source }

Critical rules:
  - Node IDs are IMMUTABLE (wallet:0xabc stays wallet:0xabc)
  - Hierarchy is stored separately via mapping
  - ForceGraphViewer sees the same {nodes, edges} contract
  - Only label/type/metadata change when projecting at higher levels
"""

import time
from datetime import datetime, timezone

from graph_normalizer import normalize_node_id
import graph_storage as storage


# ========================================================
# BUILD IDENTITY MAP
# ========================================================

async def build_identity_map(db):
    """
    Scan graph_nodes and build wallet → cluster → entity mappings.
    Sources: node.cluster_id, node.entity, entity_control edges.
    """
    stats = {"mappings": 0, "wallets": 0, "orphan_wallets": 0}
    now_ts = int(datetime.now(timezone.utc).timestamp())

    # Ensure indexes
    coll = db["graph_identity_map"]
    await coll.create_index("wallet_id", unique=True)
    await coll.create_index("cluster_id")
    await coll.create_index("entity_id")

    # 1. Build cluster → entity mapping from entity_control edges
    cluster_to_entity = {}
    entity_nodes = {}

    # Collect entity nodes
    cursor = db["graph_nodes"].find(
        {"type": {"$in": ["entity", "exchange", "protocol", "dex", "bridge"]}},
        {"_id": 0, "id": 1, "label": 1, "type": 1, "address": 1}
    )
    async for ent in cursor:
        entity_nodes[ent["id"]] = ent
        # Entity slug is the address field
        slug = ent.get("address", "")
        if slug:
            cluster_to_entity[slug] = ent["id"]

    # From entity_control edges: entity → wallet means entity controls wallet
    # So entity controls cluster if wallet belongs to cluster
    ctrl_edges = db["graph_relations"].find(
        {"relation_type": "entity_control"},
        {"_id": 0, "source_id": 1, "target_id": 1}
    )
    entity_wallets = {}  # entity_id → [wallet_ids]
    async for edge in ctrl_edges:
        entity_id = edge["source_id"]
        wallet_id = edge["target_id"]
        entity_wallets.setdefault(entity_id, []).append(wallet_id)

    # 2. Scan all wallet nodes and build identity map
    cursor = db["graph_nodes"].find(
        {"type": "wallet"},
        {"_id": 0, "id": 1, "cluster_id": 1, "entity": 1, "confidence": 1}
    )
    async for wallet in cursor:
        wid = wallet["id"]
        stats["wallets"] += 1

        cluster_id = wallet.get("cluster_id", "")
        entity_name = wallet.get("entity", "")

        # Clean up bad cluster_ids
        if cluster_id in ("None", "null", "", None):
            cluster_id = ""

        # Resolve cluster node ID
        cluster_node_id = ""
        if cluster_id:
            cluster_node_id = normalize_node_id("cluster", cluster_id, "ethereum")

        # Resolve entity node ID
        entity_node_id = ""
        if entity_name:
            # Try to find matching entity node
            entity_slug = entity_name.lower().replace(" ", "-").replace("_", "-")
            for eid, enode in entity_nodes.items():
                if enode.get("address", "") == entity_slug or enode.get("label", "").lower() == entity_name.lower():
                    entity_node_id = eid
                    break
            if not entity_node_id:
                # Check cluster_to_entity mapping
                entity_node_id = cluster_to_entity.get(entity_slug, "")
            if not entity_node_id:
                # Create entity node ID from name
                entity_node_id = normalize_node_id("entity", entity_slug, "ethereum")

        # If wallet has entity but no cluster, use entity as cluster
        if entity_node_id and not cluster_node_id:
            cluster_node_id = entity_node_id

        # If wallet has cluster but no entity, try to find entity for cluster
        if cluster_node_id and not entity_node_id:
            slug = cluster_id.lower().replace(" ", "-").replace("_", "-")
            entity_node_id = cluster_to_entity.get(slug, "")

        # Compute confidence
        confidence = wallet.get("confidence", 0.5)
        if entity_node_id and cluster_node_id:
            confidence = max(confidence, 0.8)
        elif cluster_node_id:
            confidence = max(confidence, 0.6)

        # Determine source
        source = "node_metadata"
        if entity_name:
            source = "entity_label"
        if cluster_id and cluster_id not in ("None", ""):
            source = "cluster_engine"

        mapping = {
            "wallet_id": wid,
            "cluster_id": cluster_node_id,
            "entity_id": entity_node_id,
            "confidence": confidence,
            "source": source,
            "updated_at": now_ts,
        }

        await coll.update_one(
            {"wallet_id": wid},
            {"$set": mapping},
            upsert=True,
        )
        stats["mappings"] += 1

        if not cluster_node_id and not entity_node_id:
            stats["orphan_wallets"] += 1

    return stats


# ========================================================
# RESOLVE IDENTITY
# ========================================================

async def resolve_wallet(db, wallet_id):
    """Resolve a wallet to its cluster and entity."""
    doc = await db["graph_identity_map"].find_one(
        {"wallet_id": wallet_id}, {"_id": 0}
    )
    return doc


async def resolve_cluster(db, wallet_id):
    """Resolve a wallet to its cluster ID."""
    doc = await db["graph_identity_map"].find_one(
        {"wallet_id": wallet_id}, {"_id": 0, "cluster_id": 1}
    )
    return doc.get("cluster_id", "") if doc else ""


async def resolve_entity(db, wallet_id):
    """Resolve a wallet to its entity ID."""
    doc = await db["graph_identity_map"].find_one(
        {"wallet_id": wallet_id}, {"_id": 0, "entity_id": 1}
    )
    return doc.get("entity_id", "") if doc else ""


async def resolve_identity(db, node_id, level="wallet"):
    """
    Resolve a node to the requested identity level.
    level: 'wallet' | 'cluster' | 'entity'
    Returns the node ID at the requested level.
    """
    if level == "wallet":
        return node_id

    node_type = node_id.split(":")[0] if ":" in node_id else "wallet"

    if node_type == "wallet":
        doc = await db["graph_identity_map"].find_one(
            {"wallet_id": node_id}, {"_id": 0}
        )
        if not doc:
            return node_id
        if level == "cluster":
            return doc.get("cluster_id") or node_id
        if level == "entity":
            return doc.get("entity_id") or doc.get("cluster_id") or node_id

    if node_type == "cluster":
        if level == "entity":
            # Find entity for this cluster
            doc = await db["graph_identity_map"].find_one(
                {"cluster_id": node_id, "entity_id": {"$ne": ""}},
                {"_id": 0, "entity_id": 1}
            )
            return doc.get("entity_id", node_id) if doc else node_id
        return node_id

    # entity, exchange, protocol, etc. — already at entity level
    return node_id


# ========================================================
# GET CLUSTER/ENTITY MEMBERS
# ========================================================

async def get_cluster_wallets(db, cluster_id):
    """Get all wallets belonging to a cluster."""
    cursor = db["graph_identity_map"].find(
        {"cluster_id": cluster_id},
        {"_id": 0, "wallet_id": 1}
    )
    docs = await cursor.to_list(1000)
    return [d["wallet_id"] for d in docs]


async def get_entity_wallets(db, entity_id):
    """Get all wallets belonging to an entity."""
    cursor = db["graph_identity_map"].find(
        {"entity_id": entity_id},
        {"_id": 0, "wallet_id": 1}
    )
    docs = await cursor.to_list(1000)
    return [d["wallet_id"] for d in docs]


async def get_entity_clusters(db, entity_id):
    """Get all clusters belonging to an entity."""
    cursor = db["graph_identity_map"].find(
        {"entity_id": entity_id, "cluster_id": {"$ne": ""}},
        {"_id": 0, "cluster_id": 1}
    )
    docs = await cursor.to_list(200)
    return list(set(d["cluster_id"] for d in docs))


# ========================================================
# DEDUPLICATION
# ========================================================

async def dedupe_edges_for_level(db, edges, level="wallet"):
    """
    Deduplicate edges by collapsing to the requested identity level.
    
    At cluster level:
      walletA → dex + walletB → dex (same cluster) → cluster → dex (aggregated)
    
    At entity level:
      clusterA → dex + clusterB → dex (same entity) → entity → dex (aggregated)
    """
    if level == "wallet" or not edges:
        return edges

    # Build node → higher-level mapping
    all_node_ids = set()
    for e in edges:
        all_node_ids.add(e.get("source", ""))
        all_node_ids.add(e.get("target", ""))

    id_map = {}  # node_id → resolved_id at requested level
    for nid in all_node_ids:
        if not nid:
            continue
        resolved = await resolve_identity(db, nid, level)
        id_map[nid] = resolved

    # Aggregate edges by (resolved_source, resolved_target, type)
    from collections import defaultdict
    agg = defaultdict(lambda: {"amountUsd": 0, "txCount": 0, "tags": set(), "count": 0, "best_edge": None})

    for e in edges:
        src = id_map.get(e.get("source", ""), e.get("source", ""))
        tgt = id_map.get(e.get("target", ""), e.get("target", ""))
        etype = e.get("type", "transfer")

        if src == tgt:
            continue  # Skip self-loops created by collapsing

        key = (src, tgt, etype)
        agg[key]["amountUsd"] += e.get("amountUsd", 0)
        agg[key]["txCount"] += e.get("txCount", 0)
        agg[key]["count"] += 1
        for t in e.get("tags", []):
            agg[key]["tags"].add(t)
        if agg[key]["best_edge"] is None or e.get("amountUsd", 0) > agg[key]["best_edge"].get("amountUsd", 0):
            agg[key]["best_edge"] = e

    # Build deduped edges
    deduped = []
    for (src, tgt, etype), data in agg.items():
        base = dict(data["best_edge"])
        base["source"] = src
        base["target"] = tgt
        base["id"] = f"{src}-{tgt}-{etype}"
        base["amountUsd"] = data["amountUsd"]
        base["txCount"] = data["txCount"]
        base["tags"] = list(data["tags"])[:10]
        deduped.append(base)

    return deduped


async def dedupe_nodes_for_level(db, nodes, level="wallet"):
    """
    Collapse nodes to the requested identity level.
    At cluster level: wallets → their cluster node
    At entity level: clusters → their entity node
    """
    if level == "wallet" or not nodes:
        return nodes

    # Build mapping
    seen = {}
    result = []

    for n in nodes:
        nid = n.get("id", "")
        resolved = await resolve_identity(db, nid, level)

        if resolved in seen:
            # Merge metrics into existing node
            existing = seen[resolved]
            existing["degree"] = (existing.get("degree", 0) or 0) + (n.get("degree", 0) or 0)
            existing["totalFlowUsd"] = (existing.get("totalFlowUsd", 0) or 0) + (n.get("totalFlowUsd", 0) or 0)
            members = existing.get("metadata", {}).get("_collapsed_count", 1)
            existing.setdefault("metadata", {})["_collapsed_count"] = members + 1
        else:
            # First time seeing this resolved ID
            collapsed = dict(n)
            if resolved != nid:
                # This node was collapsed — update to higher level
                collapsed["id"] = resolved
                res_type = resolved.split(":")[0] if ":" in resolved else n.get("type", "wallet")
                collapsed["type"] = res_type

                # Try to get label from the resolved node
                res_node = await db["graph_nodes"].find_one({"id": resolved}, {"_id": 0, "label": 1})
                if res_node:
                    collapsed["label"] = res_node.get("label", collapsed.get("label", ""))

                collapsed.setdefault("metadata", {})["_collapsed_count"] = 1

            seen[resolved] = collapsed
            result.append(collapsed)

    return result


# ========================================================
# MAIN ENTRY POINT
# ========================================================

async def run_identity_resolver(db):
    """Build the full identity map."""
    storage.init_storage(db)

    t0 = time.time()
    print("[IdentityResolver] Building identity map...")
    stats = await build_identity_map(db)
    elapsed = round(time.time() - t0, 1)

    print(f"[IdentityResolver] Done in {elapsed}s: {stats['mappings']} mappings, {stats['orphan_wallets']} orphans")
    return {
        "status": "completed",
        "elapsed_seconds": elapsed,
        **stats,
    }
