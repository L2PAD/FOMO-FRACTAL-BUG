"""
Capital Routes Layer — Phase A Step 4
=======================================
Detects and stores capital movement routes through the graph.

Route Object:
  source, via, destination, amount_usd, confidence, importance, lead_time, speed

Route Types:
  token_rotation, bridge_migration, exchange_routing,
  cluster_execution, liquidity_provision

Route Ranking:
  largest, smart_money, fastest, newest, highest_alpha
"""

import time
import hashlib
from datetime import datetime, timezone
from collections import defaultdict

from graph_normalizer import normalize_node_id, parse_node_id
import graph_storage as storage


async def build_capital_routes(db):
    """
    Build capital routes from graph relations.
    Finds multi-hop paths that represent capital movement patterns.
    """
    stats = {"routes": 0}
    now_ts = int(datetime.now(timezone.utc).timestamp())

    # 1. Find high-value corridors as route seeds
    corridors = await db["graph_corridors"].find(
        {"total_amount_usd": {"$gt": 0}},
        {"_id": 0}
    ).sort("total_amount_usd", -1).limit(100).to_list(100)

    for corr in corridors:
        source = corr.get("source", "")
        target = corr.get("target", "")
        bridge = corr.get("bridge", "")
        if not source or not target:
            continue

        route_id = _make_route_id(source, bridge, target)
        route_type = _classify_route(source, target, bridge)

        route = {
            "route_id": route_id,
            "source": source,
            "via": bridge or "",
            "destination": target,
            "amount_usd": corr.get("total_amount_usd", 0),
            "confidence": corr.get("confidence", 0.5),
            "importance": _compute_importance(corr),
            "route_type": route_type,
            "corridor_count": corr.get("corridor_count", 0),
            "lead_time": 0,
            "speed": "medium",
            "flow_direction": corr.get("flow_direction", ""),
            "chain": corr.get("chain", "ethereum"),
            "last_seen": corr.get("last_seen", now_ts),
        }
        await storage.upsert_route(route)
        stats["routes"] += 1

    # 2. Find smart money routes (wallets with high smart_money_score)
    sm_wallets = await db["graph_nodes"].find(
        {"smart_money_score": {"$gt": 0.3}, "type": "wallet"},
        {"_id": 0, "id": 1, "smart_money_score": 1}
    ).sort("smart_money_score", -1).limit(50).to_list(50)

    for wallet in sm_wallets:
        wid = wallet["id"]
        # Find outgoing relations from this smart money wallet
        rels = await db["graph_relations"].find(
            {"source_id": wid, "total_amount_usd": {"$gt": 0}},
            {"_id": 0}
        ).sort("total_amount_usd", -1).limit(10).to_list(10)

        for rel in rels:
            target = rel.get("target_id", "")
            if not target:
                continue

            # Check if target has further outgoing (2-hop route)
            next_rels = await db["graph_relations"].find(
                {"source_id": target, "total_amount_usd": {"$gt": 0}},
                {"_id": 0}
            ).sort("total_amount_usd", -1).limit(3).to_list(3)

            if next_rels:
                for nr in next_rels:
                    dest = nr.get("target_id", "")
                    route_id = _make_route_id(wid, target, dest)
                    route = {
                        "route_id": route_id,
                        "source": wid,
                        "via": target,
                        "destination": dest,
                        "amount_usd": min(rel.get("total_amount_usd", 0), nr.get("total_amount_usd", 0)),
                        "confidence": wallet.get("smart_money_score", 0.5),
                        "importance": wallet.get("smart_money_score", 0) * 0.8,
                        "route_type": "cluster_execution",
                        "lead_time": 0,
                        "speed": "fast",
                        "chain": "ethereum",
                        "last_seen": now_ts,
                        "tags": ["smart_money"],
                    }
                    await storage.upsert_route(route)
                    stats["routes"] += 1
            else:
                # Single-hop route
                route_id = _make_route_id(wid, "", target)
                route = {
                    "route_id": route_id,
                    "source": wid,
                    "via": "",
                    "destination": target,
                    "amount_usd": rel.get("total_amount_usd", 0),
                    "confidence": wallet.get("smart_money_score", 0.5),
                    "importance": wallet.get("smart_money_score", 0) * 0.6,
                    "route_type": _classify_route(wid, target, ""),
                    "lead_time": 0,
                    "speed": "medium",
                    "chain": "ethereum",
                    "last_seen": now_ts,
                    "tags": ["smart_money"],
                }
                await storage.upsert_route(route)
                stats["routes"] += 1

    # 3. Exchange routing patterns (deposit → exchange → withdraw)
    exchanges = await db["graph_nodes"].find(
        {"type": {"$in": ["exchange", "cex"]}, "actor_type": {"$in": ["exchange", "cex", "CEX"]}},
        {"_id": 0, "id": 1, "label": 1}
    ).limit(30).to_list(30)

    # Also include entity-based exchange nodes (e.g., exchange:binance:ethereum)
    entity_exchanges = await db["graph_nodes"].find(
        {"type": "exchange", "id": {"$regex": "^exchange:"}},
        {"_id": 0, "id": 1, "label": 1}
    ).limit(30).to_list(30)

    seen_ids = {e["id"] for e in exchanges}
    for ee in entity_exchanges:
        if ee["id"] not in seen_ids:
            exchanges.append(ee)
            seen_ids.add(ee["id"])

    for ex in exchanges:
        eid = ex["id"]
        # Incoming deposits
        deposits = await db["graph_relations"].find(
            {"target_id": eid, "relation_type": {"$in": ["deposit", "transfer"]}, "total_amount_usd": {"$gt": 0}},
            {"_id": 0, "source_id": 1, "total_amount_usd": 1}
        ).sort("total_amount_usd", -1).limit(10).to_list(10)

        # Outgoing withdrawals
        withdrawals = await db["graph_relations"].find(
            {"source_id": eid, "relation_type": {"$in": ["withdraw", "transfer"]}, "total_amount_usd": {"$gt": 0}},
            {"_id": 0, "target_id": 1, "total_amount_usd": 1}
        ).sort("total_amount_usd", -1).limit(10).to_list(10)

        for dep in deposits[:5]:
            for wdr in withdrawals[:5]:
                source = dep.get("source_id", "")
                dest = wdr.get("target_id", "")
                if not source or not dest or source == dest:
                    continue

                amount = min(dep.get("total_amount_usd", 0), wdr.get("total_amount_usd", 0))
                route_id = _make_route_id(source, eid, dest)
                route = {
                    "route_id": route_id,
                    "source": source,
                    "via": eid,
                    "destination": dest,
                    "amount_usd": amount,
                    "confidence": 0.6,
                    "importance": min(amount / 1000000, 1.0),
                    "route_type": "exchange_routing",
                    "lead_time": 0,
                    "speed": "medium",
                    "chain": "ethereum",
                    "last_seen": now_ts,
                    "tags": ["exchange_routing"],
                }
                await storage.upsert_route(route)
                stats["routes"] += 1

    return stats


def _make_route_id(source, via, dest):
    """Generate deterministic route ID"""
    raw = f"{source}|{via}|{dest}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def _classify_route(source, target, bridge):
    """Classify route type based on node types"""
    s_type = source.split(":")[0] if ":" in source else ""
    t_type = target.split(":")[0] if ":" in target else ""
    b_type = bridge.split(":")[0] if bridge and ":" in bridge else ""

    if b_type == "bridge":
        return "bridge_migration"
    if s_type == "token" or t_type == "token":
        return "token_rotation"
    if s_type in ("exchange", "cex") or t_type in ("exchange", "cex"):
        return "exchange_routing"
    if s_type == "cluster" or t_type == "cluster":
        return "cluster_execution"
    return "capital_route"


def _compute_importance(corridor):
    """Compute route importance from corridor data"""
    amount = corridor.get("total_amount_usd", 0)
    count = corridor.get("corridor_count", 0)
    conf = corridor.get("confidence", 0.5)
    return min((amount / 1000000) * conf * min(count, 10) / 10, 1.0)


async def get_routes_ranked(db, ranking="largest", limit=20):
    """Get routes sorted by different ranking criteria."""
    sort_map = {
        "largest": ("amount_usd", -1),
        "smart_money": ("confidence", -1),
        "fastest": ("speed", 1),
        "newest": ("last_seen", -1),
        "highest_alpha": ("importance", -1),
    }
    sort_field, sort_dir = sort_map.get(ranking, ("amount_usd", -1))

    query = {}
    if ranking == "smart_money":
        query["tags"] = "smart_money"

    cursor = db["graph_capital_routes"].find(
        query, {"_id": 0}
    ).sort(sort_field, sort_dir).limit(limit)

    return await cursor.to_list(limit)


async def run_capital_routes(db):
    """Main entry point for capital routes build."""
    storage.init_storage(db)

    t0 = time.time()
    print("[CapitalRoutes] Building routes...")
    stats = await build_capital_routes(db)
    elapsed = round(time.time() - t0, 1)

    print(f"[CapitalRoutes] Done in {elapsed}s: {stats['routes']} routes")
    return {
        "status": "completed",
        "elapsed_seconds": elapsed,
        **stats,
    }
