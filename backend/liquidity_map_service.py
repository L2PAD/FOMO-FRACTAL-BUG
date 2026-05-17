"""
Liquidity Map Service
======================
Builds a liquidity flow map from graph_relations and graph_corridors.

Outputs:
  - DEX → CEX flows
  - CEX → DEX flows
  - Bridge flows
  - Cross-chain routes
  - Dominant capital routes ranked by volume

Data sources:
  - graph_relations (packed)
  - graph_corridors
  - graph_nodes (type info)
"""

import asyncio
import os
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from collections import defaultdict

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
DB_NAME = os.environ.get("DB_NAME", "intelligence_engine")

# Flow categories
FLOW_CATEGORIES = {
    "cex_to_dex": {"source_types": ["cex"], "target_types": ["dex"]},
    "dex_to_cex": {"source_types": ["dex"], "target_types": ["cex"]},
    "cex_to_cex": {"source_types": ["cex"], "target_types": ["cex"]},
    "bridge_out": {"source_types": ["cex", "dex", "wallet"], "target_types": ["bridge"]},
    "bridge_in": {"source_types": ["bridge"], "target_types": ["cex", "dex", "wallet"]},
    "wallet_to_cex": {"source_types": ["wallet"], "target_types": ["cex"]},
    "cex_to_wallet": {"source_types": ["cex"], "target_types": ["wallet"]},
    "wallet_to_dex": {"source_types": ["wallet"], "target_types": ["dex"]},
    "dex_to_wallet": {"source_types": ["dex"], "target_types": ["wallet"]},
}


def classify_flow(src_type, tgt_type):
    """Classify a relation into a flow category."""
    for cat, spec in FLOW_CATEGORIES.items():
        if src_type in spec["source_types"] and tgt_type in spec["target_types"]:
            return cat
    return "other"


async def build_liquidity_map(db, time_range=None):
    """Build the liquidity map from relations and node types."""

    # Load node type index
    node_types = {}
    cursor = db["graph_nodes"].find({}, {"_id": 0, "id": 1, "type": 1, "label": 1})
    async for n in cursor:
        node_types[n["id"]] = {"type": n.get("type", "wallet"), "label": n.get("label", "")}

    # Aggregate flows by category
    flow_agg = defaultdict(lambda: {
        "total_amount_usd": 0, "total_tx_count": 0, "routes": defaultdict(lambda: {"amount": 0, "tx_count": 0, "last_seen": 0})
    })

    # Counterparty aggregation
    counterparty_volume = defaultdict(lambda: {"amount": 0, "tx_count": 0, "label": ""})
    total_tx_in = 0
    total_tx_out = 0

    query = {}
    if time_range and "min_last_seen" in time_range:
        query["last_seen"] = {"$gte": time_range["min_last_seen"]}

    rel_cursor = db["graph_relations"].find(query, {"_id": 0})
    async for rel in rel_cursor:
        src = rel.get("source_id", "")
        tgt = rel.get("target_id", "")
        src_info = node_types.get(src, {"type": "wallet", "label": ""})
        tgt_info = node_types.get(tgt, {"type": "wallet", "label": ""})

        category = classify_flow(src_info["type"], tgt_info["type"])
        amount = rel.get("total_amount_usd", 0) or 0
        tx_count = rel.get("total_tx_count", rel.get("tx_count", 0)) or 0
        last_seen = rel.get("last_seen", 0) or 0

        flow_agg[category]["total_amount_usd"] += amount
        flow_agg[category]["total_tx_count"] += tx_count

        # TX in/out: inflow categories vs outflow categories
        if category in ("cex_to_wallet", "dex_to_wallet", "bridge_in"):
            total_tx_in += tx_count
        elif category in ("wallet_to_cex", "wallet_to_dex", "bridge_out"):
            total_tx_out += tx_count

        # Track top routes within each category
        src_label = src_info.get("label") or (src[:10] + "..." + src[-6:] if len(src) > 20 else src)
        tgt_label = tgt_info.get("label") or (tgt[:10] + "..." + tgt[-6:] if len(tgt) > 20 else tgt)
        route_key = f"{src_label} → {tgt_label}"
        flow_agg[category]["routes"][route_key]["amount"] += amount
        flow_agg[category]["routes"][route_key]["tx_count"] += tx_count
        flow_agg[category]["routes"][route_key]["last_seen"] = max(
            flow_agg[category]["routes"][route_key]["last_seen"], last_seen
        )

        # Counterparty aggregation: track both src and tgt as counterparties
        counterparty_volume[src]["amount"] += amount
        counterparty_volume[src]["tx_count"] += tx_count
        counterparty_volume[src]["label"] = src_label
        counterparty_volume[tgt]["amount"] += amount
        counterparty_volume[tgt]["tx_count"] += tx_count
        counterparty_volume[tgt]["label"] = tgt_label

    # Build result
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "categories": {},
        "top_routes": [],
        "summary": {},
    }

    all_routes = []
    for cat, data in flow_agg.items():
        # Sort routes by amount
        sorted_routes = sorted(data["routes"].items(), key=lambda x: x[1]["amount"], reverse=True)[:10]
        top_routes = [
            {"route": k, "amount_usd": round(v["amount"], 2), "tx_count": v["tx_count"], "last_seen": v["last_seen"]}
            for k, v in sorted_routes
        ]

        result["categories"][cat] = {
            "total_amount_usd": round(data["total_amount_usd"], 2),
            "total_tx_count": data["total_tx_count"],
            "top_routes": top_routes,
        }
        all_routes.extend([(r["route"], r["amount_usd"], cat) for r in top_routes])

    # Global top routes
    all_routes.sort(key=lambda x: x[1], reverse=True)
    result["top_routes"] = [
        {"route": r[0], "amount_usd": r[1], "category": r[2]}
        for r in all_routes[:20]
    ]

    # Summary
    total_cex_in = sum(flow_agg[c]["total_amount_usd"] for c in ["wallet_to_cex", "dex_to_cex"])
    total_cex_out = sum(flow_agg[c]["total_amount_usd"] for c in ["cex_to_wallet", "cex_to_dex"])
    total_dex_in = sum(flow_agg[c]["total_amount_usd"] for c in ["wallet_to_dex", "cex_to_dex"])
    total_dex_out = sum(flow_agg[c]["total_amount_usd"] for c in ["dex_to_wallet", "dex_to_cex"])
    total_bridge = sum(flow_agg[c]["total_amount_usd"] for c in ["bridge_out", "bridge_in"])
    total_volume = sum(d["total_amount_usd"] for d in flow_agg.values())

    # Global inflow/outflow
    total_inflow = sum(flow_agg[c]["total_amount_usd"] for c in [
        "cex_to_wallet", "dex_to_wallet", "bridge_in"
    ] if c in flow_agg)
    total_outflow = sum(flow_agg[c]["total_amount_usd"] for c in [
        "wallet_to_cex", "wallet_to_dex", "bridge_out"
    ] if c in flow_agg)
    net_flow = total_inflow - total_outflow

    # Flow state: ACCUMULATION, DISTRIBUTION, or ROUTING
    if total_inflow > 0 and total_outflow > 0:
        ratio = min(total_inflow, total_outflow) / max(total_inflow, total_outflow)
        if ratio > 0.85:
            flow_state = "ROUTING"
        elif net_flow >= 0:
            flow_state = "ACCUMULATION"
        else:
            flow_state = "DISTRIBUTION"
    elif net_flow >= 0:
        flow_state = "ACCUMULATION"
    else:
        flow_state = "DISTRIBUTION"

    # Flow driver: determine what drives the flow
    from_sources = {
        "CEX": sum(flow_agg[c]["total_amount_usd"] for c in ["cex_to_wallet", "cex_to_dex"] if c in flow_agg),
        "DEX": sum(flow_agg[c]["total_amount_usd"] for c in ["dex_to_wallet", "dex_to_cex"] if c in flow_agg),
        "Wallets": sum(flow_agg[c]["total_amount_usd"] for c in ["wallet_to_cex", "wallet_to_dex"] if c in flow_agg),
        "Bridge": flow_agg.get("bridge_in", {}).get("total_amount_usd", 0),
    }
    dominant_source = max(from_sources, key=from_sources.get) if any(v > 0 for v in from_sources.values()) else None
    if dominant_source:
        flow_driver = f"{dominant_source}-driven" if flow_state == "ACCUMULATION" else f"{dominant_source} exit"
    else:
        flow_driver = None

    # FROM aggregates with percentages
    from_agg_raw = {
        "CEX": sum(flow_agg[c]["total_amount_usd"] for c in ["cex_to_wallet", "cex_to_dex"] if c in flow_agg),
        "Wallets": sum(flow_agg[c]["total_amount_usd"] for c in ["wallet_to_cex", "wallet_to_dex"] if c in flow_agg),
        "DEX": sum(flow_agg[c]["total_amount_usd"] for c in ["dex_to_wallet", "dex_to_cex"] if c in flow_agg),
        "Bridge": flow_agg.get("bridge_in", {}).get("total_amount_usd", 0),
    }
    from_total = sum(from_agg_raw.values())
    from_agg = {
        k: {"amount": round(v, 2), "pct": round(v / from_total * 100, 1) if from_total > 0 else 0}
        for k, v in from_agg_raw.items()
    }

    # TO aggregates with percentages
    to_agg_raw = {
        "CEX": sum(flow_agg[c]["total_amount_usd"] for c in ["wallet_to_cex", "dex_to_cex"] if c in flow_agg),
        "Wallets": sum(flow_agg[c]["total_amount_usd"] for c in ["cex_to_wallet", "dex_to_wallet"] if c in flow_agg),
        "DEX": sum(flow_agg[c]["total_amount_usd"] for c in ["cex_to_dex", "wallet_to_dex"] if c in flow_agg),
        "Bridge": flow_agg.get("bridge_out", {}).get("total_amount_usd", 0),
    }
    to_total = sum(to_agg_raw.values())
    to_agg = {
        k: {"amount": round(v, 2), "pct": round(v / to_total * 100, 1) if to_total > 0 else 0}
        for k, v in to_agg_raw.items()
    }

    # Total edges and TX counts
    edges_total = await db["graph_relations"].count_documents(query or {})
    total_tx_count = sum(d["total_tx_count"] for d in flow_agg.values())

    # Top counterparties by volume — entities only (exclude tokens)
    ENTITY_TYPES = {"wallet", "cex", "exchange", "dex", "bridge", "contract", "entity", "protocol", "cluster"}
    sorted_counterparties = sorted(counterparty_volume.items(), key=lambda x: x[1]["amount"], reverse=True)
    top_counterparties = []
    for cp_id, cp in sorted_counterparties:
        cp_type = node_types.get(cp_id, {}).get("type", "wallet")
        if cp_type not in ENTITY_TYPES:
            continue
        top_counterparties.append({
            "id": cp_id, "label": cp["label"], "amount": round(cp["amount"], 2),
            "tx_count": cp["tx_count"], "type": cp_type,
        })
        if len(top_counterparties) >= 10:
            break

    result["summary"] = {
        "inflow": round(total_inflow, 2),
        "outflow": round(total_outflow, 2),
        "net": round(net_flow, 2),
        "volume": round(total_volume, 2),
        "flow_state": flow_state,
        "flow_driver": flow_driver,
        "edges_total": edges_total,
        "tx_count": total_tx_count,
        "tx_in": total_tx_in,
        "tx_out": total_tx_out,
        "cex_net_flow": round(total_cex_in - total_cex_out, 2),
        "cex_inflow": round(total_cex_in, 2),
        "cex_outflow": round(total_cex_out, 2),
        "dex_net_flow": round(total_dex_in - total_dex_out, 2),
        "dex_inflow": round(total_dex_in, 2),
        "dex_outflow": round(total_dex_out, 2),
        "bridge_volume": round(total_bridge, 2),
        "total_volume": round(total_volume, 2),
    }
    result["from_aggregates"] = from_agg
    result["to_aggregates"] = to_agg
    result["top_counterparties"] = top_counterparties

    return result


async def save_liquidity_snapshot(db, liq_map):
    """Save the liquidity map as a snapshot for fast retrieval."""
    await db["graph_liquidity_maps"].update_one(
        {"snapshot_type": "latest"},
        {"$set": {
            "snapshot_type": "latest",
            "data": liq_map,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )


async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    print("=" * 60)
    print("LIQUIDITY MAP BUILDER")
    print("=" * 60)

    liq_map = await build_liquidity_map(db)

    # Print summary
    s = liq_map["summary"]
    print(f"\n--- Summary ---")
    print(f"  Total Volume:  ${s['total_volume']:,.0f}")
    print(f"  CEX Inflow:    ${s['cex_inflow']:,.0f}")
    print(f"  CEX Outflow:   ${s['cex_outflow']:,.0f}")
    print(f"  CEX Net:       ${s['cex_net_flow']:,.0f}")
    print(f"  DEX Inflow:    ${s['dex_inflow']:,.0f}")
    print(f"  DEX Outflow:   ${s['dex_outflow']:,.0f}")
    print(f"  Bridge Volume: ${s['bridge_volume']:,.0f}")

    print(f"\n--- Categories ---")
    for cat, data in sorted(liq_map["categories"].items(), key=lambda x: x[1]["total_amount_usd"], reverse=True):
        print(f"  {cat:20s}  ${data['total_amount_usd']:>12,.0f}  ({data['total_tx_count']} tx)")

    print(f"\n--- Top 10 Routes ---")
    for r in liq_map["top_routes"][:10]:
        print(f"  {r['route']:50s}  ${r['amount_usd']:>12,.0f}  [{r['category']}]")

    # Save snapshot
    await save_liquidity_snapshot(db, liq_map)
    print(f"\n[LiquidityMap] Snapshot saved to graph_liquidity_maps.")

    client.close()
    print("[LiquidityMap] Done.")


if __name__ == "__main__":
    asyncio.run(main())
