"""
Cluster Layer — Phase A Step 3
================================
Clusters become first-class graph nodes with:
  - cluster_id, cluster_type, members_count
  - cluster_conviction, cluster_behavior, cluster_strategy, cluster_score
  
Cluster Relations:
  cluster → wallet, cluster → token, cluster → exchange,
  cluster → bridge, cluster → cluster
"""

import time
from datetime import datetime, timezone
from collections import defaultdict

from graph_normalizer import normalize_node_id
import graph_storage as storage


async def build_cluster_nodes(db):
    """
    Build first-class cluster nodes from:
    1. graph_clusters (existing cluster definitions)
    2. wallet_clusters (wallet-based clusters)
    3. graph_nodes with cluster_id (entity-based clusters)
    
    Creates cluster nodes and all cluster relations.
    """
    stats = {"cluster_nodes": 0, "cluster_relations": 0}
    now_ts = int(datetime.now(timezone.utc).timestamp())

    # 1. Existing graph_clusters → upgrade to full nodes
    cursor = db["graph_clusters"].find({}, {"_id": 0})
    async for gc in cursor:
        cid = gc.get("cluster_id", "")
        if not cid:
            continue

        cluster_node_id = normalize_node_id("cluster", cid, "ethereum")

        # Count members
        member_count = await db["graph_nodes"].count_documents({"cluster_id": cid})

        # Compute cluster-level metrics from members
        pipeline = [
            {"$match": {"cluster_id": cid}},
            {"$group": {
                "_id": None,
                "avg_degree": {"$avg": "$degree"},
                "total_flow": {"$sum": "$total_flow_usd"},
                "avg_risk": {"$avg": {"$ifNull": ["$risk_score", 0]}},
                "avg_smart_money": {"$avg": {"$ifNull": ["$smart_money_score", 0]}},
                "types": {"$addToSet": "$type"},
            }},
        ]
        agg_result = await db["graph_nodes"].aggregate(pipeline).to_list(1)
        metrics = agg_result[0] if agg_result else {}

        cluster_node = {
            "id": cluster_node_id,
            "type": "cluster",
            "label": gc.get("label", f"Cluster {cid}"),
            "address": cid,
            "chain": "ethereum",
            "cluster_id": cid,
            "behavior": _infer_cluster_behavior(metrics, gc),
            "conviction": _compute_conviction(metrics),
            "metadata": {
                "cluster_type": gc.get("type", "unknown"),
                "members_count": member_count,
                "cluster_score": gc.get("cluster_score", metrics.get("avg_smart_money", 0) or 0),
                "cluster_strategy": _infer_strategy(metrics, gc),
                "cluster_behavior": _infer_cluster_behavior(metrics, gc),
                "total_flow_usd": metrics.get("total_flow", 0) or 0,
                "avg_degree": round(metrics.get("avg_degree", 0) or 0, 1),
                "avg_risk": round(metrics.get("avg_risk", 0) or 0, 3),
                "member_types": metrics.get("types", []),
            },
            "importance_score": gc.get("confidence", 0) or 0,
            "last_seen": now_ts,
        }
        await storage.upsert_node(cluster_node)
        stats["cluster_nodes"] += 1

    # 2. Build cluster relations based on member interactions
    # Find all distinct cluster_ids in graph_nodes
    cluster_ids = await db["graph_nodes"].distinct("cluster_id")
    cluster_ids = [c for c in cluster_ids if c]

    for cid in cluster_ids:
        cluster_node_id = normalize_node_id("cluster", cid, "ethereum")

        # Get cluster members
        members = await db["graph_nodes"].find(
            {"cluster_id": cid},
            {"_id": 0, "id": 1, "type": 1}
        ).to_list(200)

        member_ids = [m["id"] for m in members]
        if not member_ids:
            continue

        # Find relations FROM cluster members to non-cluster nodes
        # This reveals which tokens, exchanges, bridges the cluster interacts with
        external_targets = defaultdict(lambda: {"amount": 0, "count": 0, "types": set()})

        for mid in member_ids[:20]:  # Sample top 20 members
            rels = await db["graph_relations"].find(
                {"source_id": mid, "target_id": {"$nin": member_ids}},
                {"_id": 0, "target_id": 1, "total_amount_usd": 1, "total_tx_count": 1, "relation_type": 1}
            ).limit(50).to_list(50)

            for rel in rels:
                tid = rel.get("target_id", "")
                external_targets[tid]["amount"] += rel.get("total_amount_usd", 0)
                external_targets[tid]["count"] += rel.get("total_tx_count", rel.get("tx_count", 0))
                external_targets[tid]["types"].add(rel.get("relation_type", "transfer"))

        # Create cluster → external node edges for significant interactions
        for target_id, data in sorted(external_targets.items(), key=lambda x: x[1]["amount"], reverse=True)[:30]:
            target_type = target_id.split(":")[0] if ":" in target_id else "wallet"

            # Determine edge type based on target
            edge_type = "transfer"
            if target_type == "token":
                if data["amount"] > 0:
                    edge_type = "accumulation" if any("deposit" in t or "transfer" in t for t in data["types"]) else "distribution"
            elif target_type in ("exchange", "cex"):
                edge_type = "deposit" if "deposit" in data["types"] else "withdraw"
            elif target_type == "bridge":
                edge_type = "capital_route"
            elif target_type == "cluster":
                edge_type = "capital_route"

            await storage.upsert_relation({
                "source_id": cluster_node_id,
                "target_id": target_id,
                "relation_type": edge_type,
                "chain": "ethereum",
                "total_amount_usd": data["amount"],
                "tx_count": data["count"],
                "confidence": 0.7,
                "first_seen": now_ts,
                "last_seen": now_ts,
            })
            stats["cluster_relations"] += 1

    return stats


def _infer_cluster_behavior(metrics, gc):
    """Infer cluster behavior pattern"""
    avg_sm = metrics.get("avg_smart_money", 0) or 0
    avg_risk = metrics.get("avg_risk", 0) or 0
    cluster_type = gc.get("type", "")

    if cluster_type == "institution":
        return "institutional"
    if avg_sm > 0.5:
        return "smart_money"
    if avg_risk > 0.5:
        return "high_risk"
    return "mixed"


def _compute_conviction(metrics):
    """Compute cluster conviction score"""
    flow = metrics.get("total_flow", 0) or 0
    degree = metrics.get("avg_degree", 0) or 0
    if flow > 1000000 and degree > 10:
        return 0.9
    if flow > 100000:
        return 0.7
    if degree > 5:
        return 0.5
    return 0.3


def _infer_strategy(metrics, gc):
    """Infer cluster strategy fingerprint"""
    types = metrics.get("types", [])
    if "exchange" in types or "cex" in types:
        return "exchange_focused"
    if "dex" in types:
        return "defi_focused"
    if len(types) > 3:
        return "diversified"
    return "concentrated"


async def run_cluster_layer(db):
    """Main entry point for cluster layer build."""
    storage.init_storage(db)

    t0 = time.time()
    print("[ClusterLayer] Building cluster nodes and relations...")
    stats = await build_cluster_nodes(db)
    elapsed = round(time.time() - t0, 1)

    print(f"[ClusterLayer] Done in {elapsed}s: {stats['cluster_nodes']} nodes, {stats['cluster_relations']} relations")
    return {
        "status": "completed",
        "elapsed_seconds": elapsed,
        **stats,
    }
