"""
Graph Data Integrator — Phase A Step 2
========================================
Integrates all platform data sources into the unified graph:
  1. Smart Money → Graph (wallet_scores, wallet_clusters)
  2. CEX Flow → Graph (cex_flow_buckets, cex_entities)
  3. Token Intelligence → Graph (token_registry, token_flow_buckets)
  4. Wallet Intelligence → Graph (wallet_registry, wallet_scores)
  5. Entity Intelligence → Graph (entities_v2, entity_addresses_v2)
"""

import time
import hashlib
from datetime import datetime, timezone

from graph_normalizer import normalize_node_id
import graph_storage as storage


# ========================================================
# 1. SMART MONEY → GRAPH
# ========================================================

async def integrate_smart_money(db):
    """
    Source: wallet_scores, wallet_clusters, wallet_registry
    Creates: wallet/cluster/entity nodes + accumulation/distribution/rotation/capital_route edges
    """
    stats = {"nodes": 0, "edges": 0}
    now_ts = int(datetime.now(timezone.utc).timestamp())

    # 1a. Wallet scores → enrich existing wallet nodes
    cursor = db["wallet_scores"].find({}, {"_id": 0})
    async for ws in cursor:
        addr = ws.get("wallet", "").lower()
        if not addr:
            continue
        node_id = normalize_node_id("wallet", addr, "ethereum")

        # Check if wallet has entity info from registry
        reg = await db["wallet_registry"].find_one({"address": addr}, {"_id": 0})
        label = addr[:8] + "..."
        actor_type = "unknown"
        entity_name = ""
        if reg:
            label = reg.get("label", label)
            actor_type = reg.get("type", "unknown")
            entity_name = reg.get("entity", "")

        node = {
            "id": node_id,
            "type": "wallet",
            "label": label,
            "address": addr,
            "chain": "ethereum",
            "smart_money_score": ws.get("smart_money_score", 0),
            "alpha_score": ws.get("smart_money_score", 0),
            "actor_type": actor_type,
            "metadata": {
                "dex_activity": ws.get("dex_activity", 0),
                "early_entry": ws.get("early_entry", 0),
                "holding_time": ws.get("holding_time", 0),
                "interaction_score": ws.get("interaction_score", 0),
            },
            "last_seen": now_ts,
        }
        if entity_name:
            node["entity"] = entity_name

        await storage.upsert_node(node)
        stats["nodes"] += 1

    # 1b. Wallet clusters → create cluster nodes + cluster_member edges
    cursor = db["wallet_clusters"].find({}, {"_id": 0})
    async for wc in cursor:
        cluster_id = wc.get("cluster_id", "")
        if not cluster_id:
            continue

        cluster_node_id = normalize_node_id("cluster", cluster_id, "ethereum")
        cluster_node = {
            "id": cluster_node_id,
            "type": "cluster",
            "label": f"Cluster {cluster_id}",
            "address": cluster_id,
            "chain": "ethereum",
            "cluster_id": cluster_id,
            "metadata": {
                "cluster_type": wc.get("cluster_type", "unknown"),
                "wallet_count": wc.get("wallet_count", 0),
                "cluster_score": wc.get("cluster_score", 0),
                "total_value_eth": wc.get("total_value_eth", 0),
            },
            "behavior": wc.get("cluster_type", "unknown"),
            "last_seen": now_ts,
        }
        await storage.upsert_node(cluster_node)
        stats["nodes"] += 1

        # Create cluster_member edges from cluster → each wallet
        wallets = wc.get("wallets", [])
        for wallet_addr in wallets[:50]:  # limit members per cluster
            wallet_node_id = normalize_node_id("wallet", wallet_addr.lower(), "ethereum")
            edge = {
                "source_id": cluster_node_id,
                "target_id": wallet_node_id,
                "relation_type": "cluster_member",
                "chain": "ethereum",
                "total_amount_usd": 0,
                "tx_count": 1,
                "confidence": wc.get("confidence", 0.5),
                "first_seen": now_ts,
                "last_seen": now_ts,
            }
            await storage.upsert_relation(edge)
            stats["edges"] += 1

    return stats


# ========================================================
# 2. CEX FLOW → GRAPH
# ========================================================

async def integrate_cex_flow(db):
    """
    Source: cex_entities, cex_flow_buckets, wallet_registry (type=exchange)
    Creates: exchange nodes + deposit/withdraw/liquidity_provision edges
    """
    stats = {"nodes": 0, "edges": 0}
    now_ts = int(datetime.now(timezone.utc).timestamp())

    # 2a. CEX entities → exchange nodes
    cursor = db["cex_entities"].find({}, {"_id": 0})
    async for ce in cursor:
        entity_id = ce.get("entityId", "").lower()
        if not entity_id:
            continue

        node_id = normalize_node_id("exchange", entity_id, "ethereum")
        node = {
            "id": node_id,
            "type": "exchange",
            "label": ce.get("entityName", entity_id),
            "address": entity_id,
            "chain": "ethereum",
            "actor_type": ce.get("entityType", "cex"),
            "metadata": {
                "address_count": ce.get("addressCount", 0),
                "chains": ce.get("chains", []),
                "status": ce.get("status", "active"),
            },
            "last_seen": now_ts,
        }
        await storage.upsert_node(node)
        stats["nodes"] += 1

    # 2b. CEX flow buckets → aggregate into deposit/withdraw edges
    # Group by exchange → token to create meaningful edges
    pipeline = [
        {"$group": {
            "_id": {"exchange": "$exchangeId", "token": "$tokenAddress"},
            "total_inflow": {"$sum": "$inflowUsd"},
            "total_outflow": {"$sum": "$outflowUsd"},
            "total_transfers": {"$sum": "$transferCount"},
            "token_symbol": {"$first": "$tokenSymbol"},
            "last_update": {"$max": "$updatedAt"},
        }},
        {"$match": {"$or": [{"total_inflow": {"$gt": 0}}, {"total_outflow": {"$gt": 0}}]}},
        {"$sort": {"total_inflow": -1}},
        {"$limit": 500},
    ]

    async for agg in db["cex_flow_buckets"].aggregate(pipeline):
        exchange_id = agg["_id"]["exchange"]
        token_addr = agg["_id"]["token"]
        if not exchange_id or not token_addr:
            continue

        exchange_node_id = normalize_node_id("exchange", exchange_id.lower(), "ethereum")
        token_node_id = normalize_node_id("token", token_addr.lower(), "ethereum")

        # Ensure token node exists
        token_label = agg.get("token_symbol") or token_addr[:8] + "..."
        await storage.upsert_node({
            "id": token_node_id,
            "type": "token",
            "label": token_label,
            "address": token_addr.lower(),
            "chain": "ethereum",
            "last_seen": now_ts,
        })

        inflow = agg.get("total_inflow", 0)
        outflow = agg.get("total_outflow", 0)
        transfers = agg.get("total_transfers", 0)

        # Deposit edge (token → exchange) if inflow > 0
        if inflow > 0:
            await storage.upsert_relation({
                "source_id": token_node_id,
                "target_id": exchange_node_id,
                "relation_type": "deposit",
                "chain": "ethereum",
                "total_amount_usd": inflow,
                "tx_count": transfers,
                "flow_direction": "in",
                "first_seen": now_ts,
                "last_seen": now_ts,
            })
            stats["edges"] += 1

        # Withdraw edge (exchange → token) if outflow > 0
        if outflow > 0:
            await storage.upsert_relation({
                "source_id": exchange_node_id,
                "target_id": token_node_id,
                "relation_type": "withdraw",
                "chain": "ethereum",
                "total_amount_usd": outflow,
                "tx_count": transfers,
                "flow_direction": "out",
                "first_seen": now_ts,
                "last_seen": now_ts,
            })
            stats["edges"] += 1

        stats["nodes"] += 1  # token node

    return stats


# ========================================================
# 3. TOKEN INTELLIGENCE → GRAPH
# ========================================================

async def integrate_token_intelligence(db):
    """
    Source: token_registry, token_flow_buckets, onchain_v2_token_flows
    Creates: token nodes + rotation/accumulation/distribution edges
    """
    stats = {"nodes": 0, "edges": 0}
    now_ts = int(datetime.now(timezone.utc).timestamp())

    # 3a. Token registry → token nodes
    cursor = db["token_registry"].find({}, {"_id": 0})
    async for tr in cursor:
        addr = tr.get("address", "").lower()
        if not addr:
            continue

        node_id = normalize_node_id("token", addr, tr.get("chain", "ethereum"))
        node = {
            "id": node_id,
            "type": "token",
            "label": tr.get("symbol", tr.get("name", addr[:8])),
            "address": addr,
            "chain": tr.get("chain", "ethereum"),
            "metadata": {
                "name": tr.get("name", ""),
                "symbol": tr.get("symbol", ""),
                "decimals": tr.get("decimals", 18),
                "verified": tr.get("verified", False),
                "coingecko_id": tr.get("coingecko_id", ""),
            },
            "last_seen": now_ts,
        }
        await storage.upsert_node(node)
        stats["nodes"] += 1

    # 3b. Token flow buckets → rotation/distribution edges
    pipeline = [
        {"$group": {
            "_id": {"from": "$from_entity", "to": "$to_entity", "token": "$token_address"},
            "total_amount": {"$sum": "$amount_usd"},
            "tx_count": {"$sum": "$tx_count"},
            "last_seen": {"$max": "$bucket_end"},
        }},
        {"$match": {"total_amount": {"$gt": 0}}},
        {"$sort": {"total_amount": -1}},
        {"$limit": 300},
    ]

    try:
        async for agg in db["token_flow_buckets"].aggregate(pipeline):
            from_id = agg["_id"].get("from", "")
            to_id = agg["_id"].get("to", "")
            token = agg["_id"].get("token", "")
            if not from_id or not to_id:
                continue

            source_nid = normalize_node_id("wallet", from_id.lower(), "ethereum")
            target_nid = normalize_node_id("wallet", to_id.lower(), "ethereum")

            await storage.upsert_relation({
                "source_id": source_nid,
                "target_id": target_nid,
                "relation_type": "rotation",
                "chain": "ethereum",
                "total_amount_usd": agg.get("total_amount", 0),
                "tx_count": agg.get("tx_count", 0),
                "tags": [f"token:{token}"] if token else [],
                "first_seen": now_ts,
                "last_seen": now_ts,
            })
            stats["edges"] += 1
    except Exception:
        pass  # Collection may not have expected fields

    # 3c. onchain_v2_token_flows for richer flow data
    pipeline2 = [
        {"$group": {
            "_id": {"from": "$from_address", "to": "$to_address"},
            "total_usd": {"$sum": "$value_usd"},
            "count": {"$sum": 1},
            "tokens": {"$addToSet": "$token_symbol"},
        }},
        {"$match": {"total_usd": {"$gt": 100}}},
        {"$sort": {"total_usd": -1}},
        {"$limit": 500},
    ]

    try:
        async for agg in db["onchain_v2_token_flows"].aggregate(pipeline2):
            from_addr = agg["_id"].get("from", "").lower()
            to_addr = agg["_id"].get("to", "").lower()
            if not from_addr or not to_addr:
                continue

            source_nid = normalize_node_id("wallet", from_addr, "ethereum")
            target_nid = normalize_node_id("wallet", to_addr, "ethereum")

            tokens = agg.get("tokens", [])
            rel_type = "transfer"
            if len(tokens) > 1:
                rel_type = "rotation"

            await storage.upsert_relation({
                "source_id": source_nid,
                "target_id": target_nid,
                "relation_type": rel_type,
                "chain": "ethereum",
                "total_amount_usd": agg.get("total_usd", 0),
                "tx_count": agg.get("count", 0),
                "tags": tokens[:5],
                "first_seen": now_ts,
                "last_seen": now_ts,
            })
            stats["edges"] += 1
    except Exception:
        pass

    return stats


# ========================================================
# 4. WALLET INTELLIGENCE → GRAPH
# ========================================================

async def integrate_wallet_intelligence(db):
    """
    Source: wallet_registry, wallet_scores, wallet_snapshots
    Enriches: wallet nodes with metadata (alpha_score, execution_style, risk_profile, etc.)
    """
    stats = {"nodes": 0, "enriched": 0}
    now_ts = int(datetime.now(timezone.utc).timestamp())

    # Wallet registry → create/enrich wallet nodes
    cursor = db["wallet_registry"].find({}, {"_id": 0})
    async for wr in cursor:
        addr = wr.get("address", "").lower()
        if not addr:
            continue

        chain = wr.get("chain", "ethereum")
        wtype = wr.get("type", "wallet")

        # Map wallet_registry types to graph types
        type_map = {"exchange": "exchange", "cex": "exchange", "dex": "dex", "bridge": "bridge"}
        graph_type = type_map.get(wtype, "wallet")

        node_id = normalize_node_id(graph_type, addr, chain)

        # Get score data if available
        score = await db["wallet_scores"].find_one({"wallet": addr}, {"_id": 0})

        node = {
            "id": node_id,
            "type": graph_type,
            "label": wr.get("label", addr[:8] + "..."),
            "address": addr,
            "chain": chain,
            "confidence": wr.get("confidence", 0),
            "actor_type": wtype,
            "last_seen": now_ts,
        }

        if wr.get("entity"):
            node["entity"] = wr["entity"]
            node["cluster_id"] = wr["entity"].lower().replace(" ", "_")

        if score:
            node["smart_money_score"] = score.get("smart_money_score", 0)
            node["alpha_score"] = score.get("smart_money_score", 0)
            node["metadata"] = {
                "dex_activity": score.get("dex_activity", 0),
                "early_entry": score.get("early_entry", 0),
                "holding_time": score.get("holding_time", 0),
                "interaction_score": score.get("interaction_score", 0),
                "execution_style": _infer_execution_style(score),
                "risk_profile": _infer_risk_profile(score),
            }
            stats["enriched"] += 1

        await storage.upsert_node(node)
        stats["nodes"] += 1

    return stats


def _infer_execution_style(score):
    """Infer execution style from wallet scores"""
    dex = score.get("dex_activity", 0)
    early = score.get("early_entry", 0)
    if dex > 0.7:
        return "dex_heavy"
    if early > 0.5:
        return "early_mover"
    return "balanced"


def _infer_risk_profile(score):
    """Infer risk profile from wallet scores"""
    sm = score.get("smart_money_score", 0)
    if sm > 0.7:
        return "aggressive"
    if sm > 0.3:
        return "moderate"
    return "conservative"


# ========================================================
# 5. ENTITY INTELLIGENCE → GRAPH
# ========================================================

async def integrate_entity_intelligence(db):
    """
    Source: entities_v2, entity_addresses_v2, entity_holdings_v2
    Creates: entity/protocol/exchange nodes + entity_control/accumulation/distribution edges
    """
    stats = {"nodes": 0, "edges": 0}
    now_ts = int(datetime.now(timezone.utc).timestamp())

    # 5a. entities_v2 → entity nodes
    cursor = db["entities_v2"].find({}, {"_id": 0})
    async for ent in cursor:
        slug = ent.get("slug", "")
        if not slug:
            continue

        # Map entity type to graph type
        ent_type = ent.get("type", "entity").lower()
        type_map = {
            "exchange": "exchange",
            "cex": "exchange",
            "dex": "dex",
            "bridge": "bridge",
            "protocol": "protocol",
            "fund": "entity",
            "market_maker": "entity",
        }
        graph_type = type_map.get(ent_type, "entity")

        node_id = normalize_node_id(graph_type, slug, "ethereum")
        node = {
            "id": node_id,
            "type": graph_type,
            "label": ent.get("name", slug),
            "address": slug,
            "chain": "ethereum",
            "actor_type": ent_type,
            "confidence": ent.get("confidence", 0) / 100.0 if ent.get("confidence", 0) > 1 else ent.get("confidence", 0),
            "metadata": {
                "category": ent.get("category", ""),
                "description": ent.get("description", ""),
                "tags": ent.get("tags", []),
                "status": ent.get("status", "active"),
                "addresses_count": ent.get("addresses_count", 0),
            },
            "last_seen": now_ts,
        }
        await storage.upsert_node(node)
        stats["nodes"] += 1

        # 5b. Entity addresses → entity_control edges
        addr_cursor = db["entity_addresses_v2"].find(
            {"entity_slug": slug}, {"_id": 0}
        )
        async for ea in addr_cursor:
            wallet_addr = ea.get("address", "").lower()
            if not wallet_addr:
                continue

            wallet_node_id = normalize_node_id("wallet", wallet_addr, "ethereum")

            # Ensure wallet node exists
            await storage.upsert_node({
                "id": wallet_node_id,
                "type": "wallet",
                "label": ea.get("label", wallet_addr[:8] + "..."),
                "address": wallet_addr,
                "chain": "ethereum",
                "entity": ent.get("name", slug),
                "cluster_id": slug,
                "last_seen": now_ts,
            })

            # entity_control edge
            await storage.upsert_relation({
                "source_id": node_id,
                "target_id": wallet_node_id,
                "relation_type": "entity_control",
                "chain": "ethereum",
                "total_amount_usd": 0,
                "tx_count": 1,
                "confidence": ea.get("confidence", 0.8),
                "first_seen": now_ts,
                "last_seen": now_ts,
            })
            stats["edges"] += 1
            stats["nodes"] += 1

    return stats


# ========================================================
# MASTER INTEGRATION PIPELINE
# ========================================================

async def run_full_integration(db):
    """Run all data integration steps in order."""
    storage.init_storage(db)
    await storage.ensure_storage_indexes()

    results = {}
    t0 = time.time()

    print("[Integrator] Step 1/5: Smart Money...")
    results["smart_money"] = await integrate_smart_money(db)

    print("[Integrator] Step 2/5: CEX Flow...")
    results["cex_flow"] = await integrate_cex_flow(db)

    print("[Integrator] Step 3/5: Token Intelligence...")
    results["token_intelligence"] = await integrate_token_intelligence(db)

    print("[Integrator] Step 4/5: Wallet Intelligence...")
    results["wallet_intelligence"] = await integrate_wallet_intelligence(db)

    print("[Integrator] Step 5/5: Entity Intelligence...")
    results["entity_intelligence"] = await integrate_entity_intelligence(db)

    elapsed = round(time.time() - t0, 1)
    total_nodes = sum(r.get("nodes", 0) for r in results.values())
    total_edges = sum(r.get("edges", 0) for r in results.values())

    print(f"[Integrator] Done in {elapsed}s: {total_nodes} nodes, {total_edges} edges")
    return {
        "status": "completed",
        "elapsed_seconds": elapsed,
        "total_nodes_upserted": total_nodes,
        "total_edges_upserted": total_edges,
        "details": results,
    }
