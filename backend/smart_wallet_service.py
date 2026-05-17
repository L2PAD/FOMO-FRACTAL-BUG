"""
Smart Wallet Engine — P2
==========================
Computes unified smart_wallet_score and ranks wallets.

Formula:
  smart_wallet_score =
    0.30 * profitability +
    0.25 * early_entry +
    0.20 * alpha +
    0.15 * capital_size +
    0.10 * influence

Data sources:
  - wallet_scores: dex_activity, early_entry, smart_money_score, interaction_score
  - graph_nodes: capital_influence_score, total_flow_usd, degree
  - wallet_counterparty_flow_buckets: flow analysis for profitability proxy
  - wallet_clusters: cluster mapping
"""

from datetime import datetime, timezone
from collections import defaultdict


async def compute_smart_wallet_rankings(db, limit=100):
    """
    Build a ranked smart wallet leaderboard by combining on-chain metrics.
    Returns sorted list of wallets with composite scores.
    """

    # 1. Load wallet_scores
    ws_cursor = db["wallet_scores"].find({}, {"_id": 0})
    wallet_scores_map = {}
    async for ws in ws_cursor:
        addr = ws.get("wallet", "")
        if addr:
            wallet_scores_map[addr] = ws

    # 2. Load graph_nodes for wallets with influence data
    gn_cursor = db["graph_nodes"].find(
        {"type": {"$in": ["wallet", "smart_money", "fund"]}},
        {"_id": 0, "id": 1, "label": 1, "type": 1, "address": 1,
         "capital_influence_score": 1, "total_flow_usd": 1,
         "smart_money_score": 1, "degree": 1, "cluster_id": 1,
         "alpha_score": 1}
    )
    graph_nodes_map = {}
    async for gn in gn_cursor:
        nid = gn.get("id", "")
        addr = gn.get("address", "")
        if nid:
            graph_nodes_map[nid] = gn
        if addr:
            graph_nodes_map[addr] = gn

    # 3. Get max values for normalization
    max_flow = 1.0
    max_degree = 1
    for gn in graph_nodes_map.values():
        f = gn.get("total_flow_usd") or 0
        d = gn.get("degree") or 0
        if f > max_flow:
            max_flow = f
        if d > max_degree:
            max_degree = d

    # 4. Aggregate flow data from wallet_counterparty_flow_buckets
    flow_pipeline = [
        {"$group": {
            "_id": "$walletAddress",
            "total_in": {"$sum": "$inUsd"},
            "total_out": {"$sum": "$outUsd"},
            "net_flow": {"$sum": "$netUsd"},
            "counterparties": {"$addToSet": "$counterpartyAddress"},
        }},
    ]
    flow_agg = await db["wallet_counterparty_flow_buckets"].aggregate(flow_pipeline).to_list(5000)
    flow_map = {}
    max_net = 1.0
    for fa in flow_agg:
        addr = fa.get("_id", "")
        if addr:
            net = abs(fa.get("net_flow", 0))
            flow_map[addr] = {
                "total_in": fa.get("total_in", 0),
                "total_out": fa.get("total_out", 0),
                "net_flow": fa.get("net_flow", 0),
                "counterparty_count": len(fa.get("counterparties", [])),
            }
            if net > max_net:
                max_net = net

    # 5. Load wallet_clusters for cluster_id mapping
    cluster_map = {}
    cl_cursor = db["wallet_clusters"].find({}, {"_id": 0, "cluster_id": 1, "wallets": 1})
    async for cl in cl_cursor:
        cid = cl.get("cluster_id", "")
        for w in cl.get("wallets", []):
            waddr = w.get("address", "") if isinstance(w, dict) else str(w)
            if waddr:
                cluster_map[waddr] = cid

    # 6. Build unified wallet list and score
    all_wallets = set()
    for addr in wallet_scores_map:
        all_wallets.add(addr)
    for nid, gn in graph_nodes_map.items():
        addr = gn.get("address", "")
        if addr:
            all_wallets.add(addr)

    results = []
    for addr in all_wallets:
        ws = wallet_scores_map.get(addr, {})
        # Find matching graph node
        gn = graph_nodes_map.get(addr) or graph_nodes_map.get(f"wallet:{addr}:ethereum", {})
        fl = flow_map.get(addr, {})

        # Component scores (all 0..1)
        # 1. Profitability (0.30): proxy from net flow + dex activity
        net_flow_norm = min(abs(fl.get("net_flow", 0)) / max_net, 1.0) if max_net > 0 else 0
        dex = ws.get("dex_activity", 0)
        profitability = (net_flow_norm * 0.6 + dex * 0.4)

        # 2. Early Entry (0.25): from wallet_scores
        early_entry = ws.get("early_entry", 0)

        # 3. Alpha (0.20): from graph alpha_score or smart_money_score
        alpha = gn.get("alpha_score", 0) or ws.get("smart_money_score", 0)

        # 4. Capital Size (0.15): from flow volume
        flow_usd = gn.get("total_flow_usd", 0) or (fl.get("total_in", 0) + fl.get("total_out", 0))
        capital_size = min(flow_usd / max_flow, 1.0) if max_flow > 0 else 0

        # 5. Influence (0.10): from capital_influence_score
        influence = gn.get("capital_influence_score", 0)

        # Composite score
        score = (
            profitability * 0.30 +
            early_entry * 0.25 +
            alpha * 0.20 +
            capital_size * 0.15 +
            influence * 0.10
        )

        if score <= 0:
            continue

        label = gn.get("label", "") or addr[:10] + "..."
        results.append({
            "wallet": addr,
            "label": label,
            "cluster_id": cluster_map.get(addr, gn.get("cluster_id", "")),
            "smart_wallet_score": round(score, 4),
            "profitability": round(profitability, 4),
            "early_entry_score": round(early_entry, 4),
            "alpha_score": round(alpha, 4),
            "capital_size": round(capital_size, 4),
            "capital_influence_score": round(influence, 4),
            "total_flow_usd": round(flow_usd, 2),
            "degree": gn.get("degree", 0),
            "counterparty_count": fl.get("counterparty_count", 0),
        })

    # Sort by composite score descending
    results.sort(key=lambda x: x["smart_wallet_score"], reverse=True)
    return results[:limit]


async def get_top_clusters(db, limit=20):
    """Get top clusters ranked by cluster_score from wallet_clusters."""
    cursor = db["wallet_clusters"].find(
        {}, {"_id": 0}
    ).sort("cluster_score", -1).limit(limit)

    results = []
    async for cl in cursor:
        results.append({
            "cluster_id": cl.get("cluster_id", ""),
            "label": cl.get("cluster_type", cl.get("cluster_id", "")),
            "cluster_score": cl.get("cluster_score", 0),
            "total_value_eth": cl.get("total_value_eth", 0),
            "wallet_count": cl.get("wallet_count", 0),
            "total_tx_count": cl.get("total_tx_count", 0),
            "confidence": cl.get("confidence", 0),
            "cluster_type": cl.get("cluster_type", ""),
        })
    return results


async def get_top_capital_routes(db, limit=20):
    """Get top capital routes ranked by importance."""
    cursor = db["graph_context"].find(
        {"context_type": "dominant_route"},
        {"_id": 0}
    ).sort("importance", -1).limit(limit)

    routes = []
    async for doc in cursor:
        data = doc.get("data", {})
        routes.append({
            "route_id": doc.get("context_id", ""),
            "path": data.get("path", []),
            "total_flow_usd": data.get("total_flow_usd", 0),
            "avg_confidence": data.get("avg_confidence", 0),
            "importance": doc.get("importance", 0),
            "label": doc.get("label", ""),
        })
    return routes
