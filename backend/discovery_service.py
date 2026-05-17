"""
Discovery Service — Global Mode Intelligence
=============================================
Finds seed nodes for each analysis mode without requiring a starting address.
Pipeline: MODE → DISCOVERY → SEED_NODES → (caller renders graph)
"""

from collections import defaultdict


async def discover_seeds(db, mode="all", chain=None, timeframe=None, limit=20):
    strategy = DISCOVERY_STRATEGIES.get(mode, _discover_all)
    seeds = await strategy(db, chain=chain, timeframe=timeframe, limit=limit)
    return {
        "seed_nodes": seeds[:limit],
        "mode": mode,
        "reason": DISCOVERY_REASONS.get(mode, "Top nodes by importance"),
        "count": len(seeds[:limit]),
    }


async def _discover_all(db, chain=None, timeframe=None, limit=20):
    query = {}
    if chain:
        query["chain"] = chain
    nodes = await db.graph_nodes.find(query, {"_id": 0, "id": 1, "label": 1, "type": 1,
                                               "importance_score": 1, "degree": 1, "total_flow_usd": 1}) \
        .sort([("importance_score", -1), ("degree", -1)]) \
        .to_list(length=limit * 3)
    return _diversify_seeds(nodes, limit)


async def _discover_smart_money(db, chain=None, timeframe=None, limit=20):
    query = {"smart_money_score": {"$gt": 0}}
    if chain:
        query["chain"] = chain
    nodes = await db.graph_nodes.find(query, {"_id": 0, "id": 1, "label": 1, "type": 1,
                                               "smart_money_score": 1, "total_flow_usd": 1,
                                               "importance_score": 1, "degree": 1}) \
        .sort("smart_money_score", -1) \
        .to_list(length=limit * 2)
    return [_seed_node(n, score=n.get("smart_money_score", 0)) for n in nodes[:limit]]


async def _discover_cex_flow(db, chain=None, timeframe=None, limit=20):
    query = {"type": {"$in": ["exchange", "cex"]}}
    if chain:
        query["chain"] = chain
    exchanges = await db.graph_nodes.find(query, {"_id": 0, "id": 1, "label": 1, "type": 1,
                                                   "total_flow_usd": 1, "degree": 1, "importance_score": 1}) \
        .sort([("importance_score", -1), ("total_flow_usd", -1)]) \
        .to_list(length=limit)

    if not exchanges:
        pipeline = [
            {"$match": {"relation_type": {"$in": ["deposit", "withdraw"]}}},
            {"$group": {"_id": "$source_id", "total_flow": {"$sum": "$total_amount_usd"}}},
            {"$sort": {"total_flow": -1}},
            {"$limit": limit},
        ]
        agg = await db.graph_relations.aggregate(pipeline).to_list(length=limit)
        node_ids = [r["_id"] for r in agg]
        exchanges = await db.graph_nodes.find({"id": {"$in": node_ids}}, {"_id": 0, "id": 1, "label": 1, "type": 1, "total_flow_usd": 1}).to_list(length=limit)

    return [_seed_node(n, score=n.get("importance_score", 0)) for n in exchanges[:limit]]


async def _discover_token_rotation(db, chain=None, timeframe=None, limit=20):
    query = {"type": {"$in": ["token", "dex"]}}
    if chain:
        query["chain"] = chain
    tokens = await db.graph_nodes.find(query, {"_id": 0, "id": 1, "label": 1, "type": 1,
                                                "total_flow_usd": 1, "importance_score": 1, "degree": 1}) \
        .sort([("importance_score", -1), ("total_flow_usd", -1)]) \
        .to_list(length=limit * 2)

    if not tokens:
        pipeline = [
            {"$match": {"relation_type": {"$in": ["swap", "rotation"]}}},
            {"$group": {"_id": "$source_id", "total_flow": {"$sum": "$total_amount_usd"}}},
            {"$sort": {"total_flow": -1}},
            {"$limit": limit},
        ]
        agg = await db.graph_relations.aggregate(pipeline).to_list(length=limit)
        node_ids = [r["_id"] for r in agg]
        tokens = await db.graph_nodes.find({"id": {"$in": node_ids}}, {"_id": 0, "id": 1, "label": 1, "type": 1, "total_flow_usd": 1}).to_list(length=limit)

    return [_seed_node(n, score=n.get("importance_score", 0)) for n in tokens[:limit]]


async def _discover_entity(db, chain=None, timeframe=None, limit=20):
    query = {"type": {"$in": ["entity", "cluster", "protocol"]}}
    if chain:
        query["chain"] = chain
    entities = await db.graph_nodes.find(query, {"_id": 0, "id": 1, "label": 1, "type": 1,
                                                  "importance_score": 1, "degree": 1, "capital_influence_score": 1}) \
        .sort([("importance_score", -1), ("degree", -1)]) \
        .to_list(length=limit)
    return [_seed_node(n, score=n.get("importance_score", 0)) for n in entities[:limit]]


async def _discover_risk(db, chain=None, timeframe=None, limit=20):
    query = {"risk_score": {"$gt": 0}}
    if chain:
        query["chain"] = chain
    nodes = await db.graph_nodes.find(query, {"_id": 0, "id": 1, "label": 1, "type": 1,
                                               "risk_score": 1, "total_flow_usd": 1, "degree": 1}) \
        .sort("risk_score", -1) \
        .to_list(length=limit * 2)

    if not nodes:
        pipeline = [
            {"$match": {"relation_type": {"$in": ["signal_link"]}}},
            {"$group": {"_id": "$source_id", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": limit},
        ]
        agg = await db.graph_relations.aggregate(pipeline).to_list(length=limit)
        node_ids = [r["_id"] for r in agg]
        nodes = await db.graph_nodes.find({"id": {"$in": node_ids}}, {"_id": 0, "id": 1, "label": 1, "type": 1, "risk_score": 1}).to_list(length=limit)

    return [_seed_node(n, score=n.get("risk_score", 0)) for n in nodes[:limit]]


def _seed_node(node, score=0):
    return {
        "id": node.get("id", ""),
        "label": node.get("label", ""),
        "type": node.get("type", "wallet"),
        "score": round(score, 4),
    }


def _diversify_seeds(nodes, limit):
    by_type = defaultdict(list)
    for n in nodes:
        by_type[n.get("type", "wallet")].append(n)

    result = []
    type_keys = list(by_type.keys())
    idx = 0
    while len(result) < limit and type_keys:
        t = type_keys[idx % len(type_keys)]
        if by_type[t]:
            node = by_type[t].pop(0)
            result.append(_seed_node(node, score=node.get("importance_score", 0)))
        else:
            type_keys.remove(t)
            if not type_keys:
                break
            continue
        idx += 1
    return result


DISCOVERY_STRATEGIES = {
    "all": _discover_all,
    "smart_money": _discover_smart_money,
    "cex_flow": _discover_cex_flow,
    "token_rotation": _discover_token_rotation,
    "entity": _discover_entity,
    "risk": _discover_risk,
}

DISCOVERY_REASONS = {
    "all": "Top nodes by importance and connectivity",
    "smart_money": "Top smart wallets by score",
    "cex_flow": "Exchanges with largest capital flows",
    "token_rotation": "Tokens with highest rotation activity",
    "entity": "Entities with highest connectivity",
    "risk": "Nodes with highest risk indicators",
}
