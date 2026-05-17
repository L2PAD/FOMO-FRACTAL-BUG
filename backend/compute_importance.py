"""
Compute Node Importance Ranking
================================
Adds importance_score to graph_nodes.

Formula:
  importance_score = normalized_flow * 0.5 + normalized_degree * 0.3 + normalized_recency * 0.2

Normalization: min-max across all nodes with non-zero metrics.

Usage:
  python compute_importance.py
"""

import asyncio
import os
import time
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
DB_NAME = os.environ.get("DB_NAME", "intelligence_engine")


async def compute():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    nodes_coll = db["graph_nodes"]

    start = time.time()

    # Collect all nodes with metrics
    cursor = nodes_coll.find(
        {"degree": {"$gt": 0}},
        {"_id": 0, "id": 1, "degree": 1, "total_flow_usd": 1, "last_seen": 1}
    )
    nodes = await cursor.to_list(None)
    print(f"[Importance] Loaded {len(nodes)} nodes with degree > 0")

    if not nodes:
        print("[Importance] No nodes to rank.")
        client.close()
        return

    # Find min/max for normalization
    max_flow = max(n.get("total_flow_usd", 0) for n in nodes) or 1
    max_degree = max(n.get("degree", 0) for n in nodes) or 1
    all_last_seen = [n.get("last_seen", 0) for n in nodes if n.get("last_seen", 0) > 0]
    min_last_seen = min(all_last_seen) if all_last_seen else 0
    max_last_seen = max(all_last_seen) if all_last_seen else 1
    range_last_seen = (max_last_seen - min_last_seen) or 1

    print(f"  max_flow=${max_flow:,.0f}, max_degree={max_degree}, last_seen range={range_last_seen}")

    # Compute scores
    updated = 0
    for n in nodes:
        flow_norm = (n.get("total_flow_usd", 0) / max_flow)
        degree_norm = (n.get("degree", 0) / max_degree)
        recency_norm = ((n.get("last_seen", 0) - min_last_seen) / range_last_seen) if n.get("last_seen", 0) > 0 else 0

        score = round(flow_norm * 0.5 + degree_norm * 0.3 + recency_norm * 0.2, 6)

        result = await nodes_coll.update_one(
            {"id": n["id"]},
            {"$set": {"importance_score": score}}
        )
        if result.modified_count > 0:
            updated += 1

    # Top 15
    top = await nodes_coll.find(
        {"importance_score": {"$gt": 0}},
        {"_id": 0, "id": 1, "label": 1, "importance_score": 1, "degree": 1, "total_flow_usd": 1}
    ).sort("importance_score", -1).limit(15).to_list(15)

    print(f"\n[Importance] Updated {updated} nodes")
    print("\n--- TOP 15 by Importance ---")
    for i, n in enumerate(top, 1):
        label = n.get("label", n["id"][:30])
        print(f"  {i:2d}. {label:30s} score={n['importance_score']:.4f}  degree={n.get('degree',0):4d}  flow=${n.get('total_flow_usd',0):,.0f}")

    elapsed = round(time.time() - start, 1)
    print(f"\n[Importance] Done in {elapsed}s")
    client.close()


if __name__ == "__main__":
    asyncio.run(compute())
