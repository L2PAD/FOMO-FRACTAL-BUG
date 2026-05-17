"""
Recompute Node Metrics — P0.2
==============================
Reads graph_relations (packed) and updates graph_nodes with:
  - degree: total number of unique relations (in + out)
  - total_flow_usd: sum of total_amount_usd across all relations
  - last_seen: max(last_seen) across all relations

Run after relation packing or periodically to refresh metrics.

Usage:
  python recompute_node_metrics.py
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from collections import defaultdict

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
DB_NAME = os.environ.get("DB_NAME", "intelligence_engine")


async def recompute():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    rels_coll = db["graph_relations"]
    nodes_coll = db["graph_nodes"]

    metrics = defaultdict(lambda: {"degree": 0, "total_flow_usd": 0.0, "last_seen": 0})

    total_rels = await rels_coll.count_documents({})
    print(f"[NodeMetrics] Processing {total_rels} relations...")

    cursor = rels_coll.find({}, {"_id": 0, "source_id": 1, "target_id": 1, "total_amount_usd": 1, "last_seen": 1})
    count = 0
    async for rel in cursor:
        src = rel.get("source_id", "")
        tgt = rel.get("target_id", "")
        amount = rel.get("total_amount_usd", 0) or 0
        last_seen = rel.get("last_seen", 0) or 0

        if src:
            metrics[src]["degree"] += 1
            metrics[src]["total_flow_usd"] += amount
            metrics[src]["last_seen"] = max(metrics[src]["last_seen"], last_seen)

        if tgt:
            metrics[tgt]["degree"] += 1
            metrics[tgt]["total_flow_usd"] += amount
            metrics[tgt]["last_seen"] = max(metrics[tgt]["last_seen"], last_seen)

        count += 1
        if count % 2000 == 0:
            print(f"  ... processed {count}/{total_rels} relations, {len(metrics)} nodes")

    print(f"[NodeMetrics] Computed metrics for {len(metrics)} nodes. Updating DB...")

    updated = 0
    for node_id, m in metrics.items():
        result = await nodes_coll.update_one(
            {"id": node_id},
            {"$set": {
                "degree": m["degree"],
                "total_flow_usd": round(m["total_flow_usd"], 2),
                "last_seen": m["last_seen"],
            }},
        )
        if result.modified_count > 0:
            updated += 1

    print(f"[NodeMetrics] Updated {updated} nodes out of {len(metrics)} total.")

    # Print top 10 by degree
    top_degree = sorted(metrics.items(), key=lambda x: x[1]["degree"], reverse=True)[:10]
    print("\n--- TOP 10 by Degree ---")
    for nid, m in top_degree:
        print(f"  {nid}: degree={m['degree']}, flow=${m['total_flow_usd']:,.0f}")

    # Print top 10 by flow
    top_flow = sorted(metrics.items(), key=lambda x: x[1]["total_flow_usd"], reverse=True)[:10]
    print("\n--- TOP 10 by Flow ---")
    for nid, m in top_flow:
        print(f"  {nid}: flow=${m['total_flow_usd']:,.0f}, degree={m['degree']}")

    client.close()
    print(f"\n[NodeMetrics] Done.")


if __name__ == "__main__":
    asyncio.run(recompute())
