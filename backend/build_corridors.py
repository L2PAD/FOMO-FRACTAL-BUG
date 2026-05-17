"""
Build Graph Corridors — Macro Flow Aggregation
================================================
Aggregates micro-corridors (detected in snapshots/cache) and
relation_buckets into macro corridor flows.

Example:
  Uniswap → Binance: $4.2M via Wormhole (12 corridors)

Schema:
  {
    source, target, bridge,
    corridor_count, total_amount_usd, last_seen
  }

Run:  cd /app/backend && python build_corridors.py
"""

import asyncio
import os
import time
from datetime import datetime, timezone
from collections import defaultdict

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

from graph_storage import init_storage, ensure_storage_indexes
from graph_normalizer import parse_node_id


# Known entity types for corridor detection
ANCHOR_TYPES = {"cex", "dex", "bridge"}


async def main():
    load_dotenv()
    client = AsyncIOMotorClient(os.environ.get("MONGO_URL"))
    db = client[os.environ.get("DB_NAME", "intelligence_engine")]
    init_storage(db)
    await ensure_storage_indexes()

    start = time.time()
    print("=" * 60)
    print("BUILDING GRAPH CORRIDORS")
    print("=" * 60)

    corridors_coll = db["graph_corridors"]
    rels_coll = db["graph_relations"]
    nodes_coll = db["graph_nodes"]

    # Clear old corridors
    deleted = await corridors_coll.delete_many({})
    print(f"Cleared {deleted.deleted_count} old corridors")

    # Build node type lookup for anchor types
    anchor_nodes = await nodes_coll.find(
        {"type": {"$in": list(ANCHOR_TYPES)}}, {"_id": 0, "id": 1, "type": 1, "label": 1}
    ).to_list(1000)
    node_type_map = {n["id"]: n for n in anchor_nodes}
    print(f"Loaded {len(anchor_nodes)} anchor-type nodes (cex/dex/bridge)")

    # Strategy: Find 2-hop paths through bridges
    # path: (cex/dex) → wallet → bridge → wallet → (cex/dex)
    # Simplified: look for relations where source/target are anchor types

    # Collect all relations involving anchor nodes
    macro_flows = defaultdict(lambda: {
        "corridor_count": 0,
        "total_amount_usd": 0,
        "last_seen": 0,
        "bridges": set(),
    })

    # Strategy 1: Direct anchor-to-anchor flows
    print("\n--- Direct Anchor-to-Anchor Flows ---")
    direct_count = 0
    for anchor in anchor_nodes:
        aid = anchor["id"]
        rels = await rels_coll.find(
            {"source_id": aid}, {"_id": 0}
        ).limit(500).to_list(500)

        for rel in rels:
            target = rel.get("target_id", "")
            if target in node_type_map:
                target_info = node_type_map[target]
                src_type = anchor.get("type", "")
                tgt_type = target_info.get("type", "")
                if src_type != tgt_type:
                    flow_key = (aid, target)
                    flow = macro_flows[flow_key]
                    flow["corridor_count"] += 1
                    flow["total_amount_usd"] += rel.get("total_amount_usd", 0)
                    flow["last_seen"] = max(flow["last_seen"], rel.get("last_seen", 0))
                    direct_count += 1

    print(f"  Found {direct_count} direct flows")

    # Strategy 2: 2-hop flows through wallets (anchor → wallet → anchor)
    print("--- 2-hop Flows (anchor → wallet → anchor) ---")
    twohop_count = 0

    for anchor in anchor_nodes:
        aid = anchor["id"]
        atype = anchor.get("type", "")

        # Get wallets this anchor transacts with
        out_rels = await rels_coll.find(
            {"source_id": aid}, {"_id": 0, "target_id": 1, "total_amount_usd": 1, "last_seen": 1}
        ).sort("total_amount_usd", -1).limit(50).to_list(50)

        in_rels = await rels_coll.find(
            {"target_id": aid}, {"_id": 0, "source_id": 1, "total_amount_usd": 1, "last_seen": 1}
        ).sort("total_amount_usd", -1).limit(50).to_list(50)

        # Collect intermediary wallet IDs
        wallet_ids = set()
        wallet_flow = {}  # wallet_id → {usd, last_seen}
        for r in out_rels:
            tid = r["target_id"]
            if tid not in node_type_map:
                wallet_ids.add(tid)
                wallet_flow[tid] = {"usd": r.get("total_amount_usd", 0), "ls": r.get("last_seen", 0)}
        for r in in_rels:
            sid = r["source_id"]
            if sid not in node_type_map:
                wallet_ids.add(sid)
                wallet_flow[sid] = {"usd": r.get("total_amount_usd", 0), "ls": r.get("last_seen", 0)}

        if not wallet_ids:
            continue

        # For each wallet, check if it also transacts with another anchor
        for wid in list(wallet_ids)[:30]:
            w_rels = await rels_coll.find(
                {"$or": [{"source_id": wid}, {"target_id": wid}]},
                {"_id": 0, "source_id": 1, "target_id": 1, "total_amount_usd": 1, "last_seen": 1}
            ).limit(100).to_list(100)

            for wr in w_rels:
                other = wr["target_id"] if wr["source_id"] == wid else wr["source_id"]
                if other != aid and other in node_type_map:
                    other_info = node_type_map[other]
                    if other_info.get("type", "") != atype:
                        flow_key = (aid, other)
                        flow = macro_flows[flow_key]
                        flow["corridor_count"] += 1
                        min_usd = min(
                            wallet_flow.get(wid, {}).get("usd", 0),
                            wr.get("total_amount_usd", 0)
                        )
                        flow["total_amount_usd"] += min_usd
                        flow["last_seen"] = max(
                            flow["last_seen"],
                            wallet_flow.get(wid, {}).get("ls", 0),
                            wr.get("last_seen", 0)
                        )
                        twohop_count += 1

    print(f"  Found {twohop_count} 2-hop flows")

    # Save corridors
    saved = 0
    now_iso = datetime.now(timezone.utc).isoformat()

    for (source_id, target_id), flow in macro_flows.items():
        if flow["corridor_count"] < 1:
            continue

        src_info = node_type_map.get(source_id, {})
        tgt_info = node_type_map.get(target_id, {})

        corridor_doc = {
            "source": source_id,
            "target": target_id,
            "source_label": src_info.get("label", source_id[:20]),
            "target_label": tgt_info.get("label", target_id[:20]),
            "source_type": src_info.get("type", ""),
            "target_type": tgt_info.get("type", ""),
            "bridge": ", ".join(sorted(flow["bridges"])) if flow["bridges"] else None,
            "corridor_count": flow["corridor_count"],
            "total_amount_usd": round(flow["total_amount_usd"], 2),
            "last_seen": flow["last_seen"],
            "flow_direction": f"{src_info.get('type', '?')}→{tgt_info.get('type', '?')}",
            "confidence": min(0.99, 0.5 + flow["corridor_count"] * 0.05),
            "updated_at": now_iso,
        }

        await corridors_coll.update_one(
            {"source": source_id, "target": target_id},
            {"$set": corridor_doc},
            upsert=True,
        )
        saved += 1

    elapsed = round(time.time() - start, 1)

    print("=" * 60)
    print(f"DONE in {elapsed}s")
    print(f"  Macro corridors saved: {saved}")

    # Show top corridors
    top = await corridors_coll.find(
        {}, {"_id": 0}
    ).sort("total_amount_usd", -1).limit(10).to_list(10)

    if top:
        print("\n  Top corridors by volume:")
        for c in top:
            bridge_str = f" via {c['bridge']}" if c.get("bridge") else ""
            print(f"    {c.get('source_label', '?')} → {c.get('target_label', '?')}: "
                  f"${c['total_amount_usd']:,.0f}{bridge_str} ({c['corridor_count']} flows)")

    print("=" * 60)
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
