"""
Graph Context Layer — P1
==========================
Computes structural intelligence on top of the graph:
  1. capital_influence_score — per-node onchain influence based on capital volume,
     network centrality, smart wallet score, capital flow control, temporal activity
  2. capital_center detection — dominant clusters, tokens, exchanges
  3. dominant_routes — most important capital paths

Stores results in graph_context collection.
Projection Layer uses context to highlight structural nodes.
"""

import time
from datetime import datetime, timezone, timedelta
from collections import defaultdict

from graph_normalizer import normalize_node_id
import graph_storage as storage


async def compute_capital_influence_scores(db):
    """
    Compute capital_influence_score for every node.
    Formula:
      0.30 * capital_volume +
      0.25 * network_centrality +
      0.20 * smart_wallet_score +
      0.15 * capital_flow_control +
      0.10 * temporal_activity
    """
    stats = {"scored": 0}

    # Get global max values for normalization
    pipeline = [
        {"$group": {
            "_id": None,
            "max_degree": {"$max": {"$ifNull": ["$degree", 0]}},
            "max_flow": {"$max": {"$ifNull": ["$total_flow_usd", 0]}},
        }}
    ]
    agg = await db["graph_nodes"].aggregate(pipeline).to_list(1)
    maxes = agg[0] if agg else {}
    max_degree = max(maxes.get("max_degree", 1) or 1, 1)
    max_flow = max(maxes.get("max_flow", 1) or 1, 1)

    # Compute temporal activity from graph_relation_buckets
    # Count transactions per node in last 24h, 7d, 30d
    now = datetime.now(timezone.utc)
    day_30_ago = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    day_7_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    day_1_ago = (now - timedelta(days=1)).strftime("%Y-%m-%d")

    temporal_map = defaultdict(lambda: {"tx_30d": 0, "tx_7d": 0, "tx_1d": 0})
    bucket_cursor = db["graph_relation_buckets"].find(
        {"bucket_day": {"$gte": day_30_ago}},
        {"_id": 0, "source_id": 1, "target_id": 1, "tx_count": 1, "bucket_day": 1}
    )
    async for b in bucket_cursor:
        tx = b.get("tx_count", 0)
        bday = b.get("bucket_day", "")
        for nid in [b.get("source_id"), b.get("target_id")]:
            if not nid:
                continue
            temporal_map[nid]["tx_30d"] += tx
            if bday >= day_7_ago:
                temporal_map[nid]["tx_7d"] += tx
            if bday >= day_1_ago:
                temporal_map[nid]["tx_1d"] += tx

    # Max temporal for normalization
    max_tx_30d = max((v["tx_30d"] for v in temporal_map.values()), default=1) or 1

    # Compute betweenness-like flow control:
    # Count how many unique source→target pairs pass through each node
    flow_control_map = defaultdict(int)
    route_cursor = db["graph_capital_routes"].find(
        {}, {"_id": 0, "path": 1}
    )
    async for route in route_cursor:
        path = route.get("path", [])
        for node_id in path:
            flow_control_map[node_id] += 1
    max_flow_control = max(flow_control_map.values(), default=1) or 1

    # Score all nodes with degree > 0 OR cluster/exchange types
    cursor = db["graph_nodes"].find(
        {"$or": [
            {"degree": {"$gt": 0}},
            {"type": {"$in": ["cluster", "exchange", "cex", "entity", "protocol"]}},
        ]},
        {"_id": 0, "id": 1, "degree": 1, "total_flow_usd": 1,
         "smart_money_score": 1, "type": 1}
    )
    async for node in cursor:
        nid = node.get("id", "")
        degree = (node.get("degree") or 0)
        flow = (node.get("total_flow_usd") or 0)
        sm = (node.get("smart_money_score") or 0)

        # 1. Capital Volume (0.30)
        capital_volume = min(flow / max_flow, 1.0) if max_flow > 0 else 0

        # 2. Network Centrality (0.25) — degree centrality
        network_centrality = min(degree / max_degree, 1.0)

        # 3. Smart Wallet Score (0.20) — already 0..1
        smart_wallet = min(sm, 1.0)

        # 4. Capital Flow Control (0.15) — betweenness-like
        flow_control = min(flow_control_map.get(nid, 0) / max_flow_control, 1.0)

        # 5. Temporal Activity (0.10)
        t = temporal_map.get(nid, {})
        temporal = min(t.get("tx_30d", 0) / max_tx_30d, 1.0)

        influence = (
            capital_volume * 0.30 +
            network_centrality * 0.25 +
            smart_wallet * 0.20 +
            flow_control * 0.15 +
            temporal * 0.10
        )

        # Boost for structural node types
        ntype = node.get("type", "wallet")
        if ntype in ("exchange", "cex"):
            influence = min(influence * 1.3, 1.0)
        elif ntype == "cluster":
            influence = min(influence * 1.2, 1.0)
        elif ntype in ("entity", "protocol"):
            influence = min(influence * 1.15, 1.0)

        await db["graph_nodes"].update_one(
            {"id": nid},
            {"$set": {"capital_influence_score": round(influence, 4)}}
        )
        stats["scored"] += 1

    return stats


async def detect_capital_centers(db):
    """
    Find dominant structures in the graph:
      - Top clusters by aggregate flow
      - Top tokens by connection count
      - Top exchanges by throughput
    """
    stats = {"centers": 0}
    now_ts = int(datetime.now(timezone.utc).timestamp())
    coll = db["graph_context"]

    # 1. Dominant clusters
    pipeline = [
        {"$match": {"type": "cluster", "capital_influence_score": {"$gt": 0}}},
        {"$sort": {"capital_influence_score": -1}},
        {"$limit": 20},
        {"$project": {"_id": 0, "id": 1, "label": 1, "capital_influence_score": 1,
                       "total_flow_usd": 1, "degree": 1, "metadata": 1}},
    ]
    top_clusters = await db["graph_nodes"].aggregate(pipeline).to_list(20)
    for cl in top_clusters:
        await coll.update_one(
            {"context_id": f"capital_center:cluster:{cl['id']}"},
            {"$set": {
                "context_id": f"capital_center:cluster:{cl['id']}",
                "context_type": "capital_center",
                "sub_type": "dominant_cluster",
                "node_id": cl["id"],
                "label": cl.get("label", ""),
                "importance": cl.get("capital_influence_score", 0),
                "data": {
                    "total_flow_usd": cl.get("total_flow_usd", 0),
                    "degree": cl.get("degree", 0),
                    "members_count": (cl.get("metadata") or {}).get("members_count", 0),
                },
                "updated_at": now_ts,
            }},
            upsert=True,
        )
        stats["centers"] += 1

    # 2. Dominant exchanges
    pipeline = [
        {"$match": {"type": {"$in": ["exchange", "cex"]}, "capital_influence_score": {"$gt": 0}}},
        {"$sort": {"capital_influence_score": -1}},
        {"$limit": 10},
        {"$project": {"_id": 0, "id": 1, "label": 1, "capital_influence_score": 1,
                       "total_flow_usd": 1, "degree": 1}},
    ]
    top_exchanges = await db["graph_nodes"].aggregate(pipeline).to_list(10)
    for ex in top_exchanges:
        await coll.update_one(
            {"context_id": f"capital_center:exchange:{ex['id']}"},
            {"$set": {
                "context_id": f"capital_center:exchange:{ex['id']}",
                "context_type": "capital_center",
                "sub_type": "exchange_pressure",
                "node_id": ex["id"],
                "label": ex.get("label", ""),
                "importance": ex.get("capital_influence_score", 0),
                "data": {
                    "total_flow_usd": ex.get("total_flow_usd", 0),
                    "degree": ex.get("degree", 0),
                },
                "updated_at": now_ts,
            }},
            upsert=True,
        )
        stats["centers"] += 1

    # 3. Dominant tokens
    pipeline = [
        {"$match": {"type": "token"}},
        {"$sort": {"degree": -1}},
        {"$limit": 15},
        {"$project": {"_id": 0, "id": 1, "label": 1, "degree": 1, "total_flow_usd": 1}},
    ]
    top_tokens = await db["graph_nodes"].aggregate(pipeline).to_list(15)
    for tk in top_tokens:
        await coll.update_one(
            {"context_id": f"capital_center:token:{tk['id']}"},
            {"$set": {
                "context_id": f"capital_center:token:{tk['id']}",
                "context_type": "capital_center",
                "sub_type": "token_control",
                "node_id": tk["id"],
                "label": tk.get("label", ""),
                "importance": min((tk.get("degree", 0) or 0) / 50, 1.0),
                "data": {
                    "degree": tk.get("degree", 0),
                    "total_flow_usd": tk.get("total_flow_usd", 0),
                },
                "updated_at": now_ts,
            }},
            upsert=True,
        )
        stats["centers"] += 1

    return stats


async def detect_dominant_routes(db):
    """
    Find the most important capital routes in the graph.
    """
    stats = {"routes": 0}
    now_ts = int(datetime.now(timezone.utc).timestamp())
    coll = db["graph_context"]

    # Top routes by amount
    routes = await db["graph_capital_routes"].find(
        {}, {"_id": 0}
    ).sort("amount_usd", -1).limit(20).to_list(20)

    for rt in routes:
        ctx_id = f"dominant_route:{rt.get('route_id', '')}"
        await coll.update_one(
            {"context_id": ctx_id},
            {"$set": {
                "context_id": ctx_id,
                "context_type": "dominant_route",
                "sub_type": rt.get("route_type", "capital_route"),
                "node_id": rt.get("source", ""),
                "label": f"{_short(rt.get('source',''))} → {_short(rt.get('destination',''))}",
                "importance": rt.get("importance", 0),
                "data": {
                    "source": rt.get("source", ""),
                    "via": rt.get("via", ""),
                    "destination": rt.get("destination", ""),
                    "amount_usd": rt.get("amount_usd", 0),
                    "route_type": rt.get("route_type", ""),
                    "confidence": rt.get("confidence", 0),
                },
                "updated_at": now_ts,
            }},
            upsert=True,
        )
        stats["routes"] += 1

    return stats


def _short(node_id):
    """Shorten node ID for display"""
    if not node_id:
        return ""
    parts = node_id.split(":")
    if len(parts) >= 2:
        addr = parts[1]
        if addr.startswith("0x") and len(addr) > 10:
            return f"{parts[0]}:{addr[:6]}..{addr[-4:]}"
        return f"{parts[0]}:{addr[:12]}"
    return node_id[:20]


# ========================================================
# QUERY CONTEXT
# ========================================================

async def get_context(db, context_type=None, limit=30):
    """Get graph context entries."""
    query = {}
    if context_type:
        query["context_type"] = context_type
    cursor = db["graph_context"].find(query, {"_id": 0}).sort("importance", -1).limit(limit)
    return await cursor.to_list(limit)


async def get_context_for_node(db, node_id):
    """Get all context entries related to a node."""
    cursor = db["graph_context"].find(
        {"node_id": node_id}, {"_id": 0}
    ).sort("importance", -1).limit(20)
    return await cursor.to_list(20)


# ========================================================
# MAIN ENTRY POINT
# ========================================================

async def run_context_layer(db):
    """Run the full Graph Context Layer pipeline."""
    storage.init_storage(db)

    t0 = time.time()
    results = {}

    # Ensure indexes
    await db["graph_context"].create_index("context_id", unique=True)
    await db["graph_context"].create_index("context_type")
    await db["graph_context"].create_index("node_id")
    await db["graph_context"].create_index([("importance", -1)])

    print("[ContextLayer] Computing capital influence scores...")
    results["capital_influence"] = await compute_capital_influence_scores(db)

    print("[ContextLayer] Detecting capital centers...")
    results["capital_centers"] = await detect_capital_centers(db)

    print("[ContextLayer] Detecting dominant routes...")
    results["dominant_routes"] = await detect_dominant_routes(db)

    elapsed = round(time.time() - t0, 1)
    total = (results["capital_influence"].get("scored", 0) +
             results["capital_centers"].get("centers", 0) +
             results["dominant_routes"].get("routes", 0))

    print(f"[ContextLayer] Done in {elapsed}s: {total} context entries")
    return {
        "status": "completed",
        "elapsed_seconds": elapsed,
        "details": results,
    }
