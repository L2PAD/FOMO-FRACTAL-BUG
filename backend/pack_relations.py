"""
Pack Relations — Deduplication & Unique Index
==============================================
Ensures the unique index (source_id, target_id, relation_type) on graph_relations.
If duplicates exist, merges them into a single packed document.

Run ONCE before enabling the unique index.

Usage:
  python pack_relations.py
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
DB_NAME = os.environ.get("DB_NAME", "intelligence_engine")


async def pack():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    coll = db["graph_relations"]

    total = await coll.count_documents({})
    print(f"[PackRelations] Total relations before packing: {total}")

    # Step 1: Find duplicates via aggregation
    pipeline = [
        {"$group": {
            "_id": {"source_id": "$source_id", "target_id": "$target_id", "relation_type": "$relation_type"},
            "count": {"$sum": 1},
            "ids": {"$push": "$_id"},
            "total_tx_count": {"$sum": {"$ifNull": ["$total_tx_count", {"$ifNull": ["$tx_count", 1]}]}},
            "total_amount_usd": {"$sum": {"$ifNull": ["$total_amount_usd", 0]}},
            "min_first_seen": {"$min": "$first_seen"},
            "max_last_seen": {"$max": "$last_seen"},
            "chains": {"$addToSet": "$chain"},
            "all_tags": {"$push": "$tags"},
            "max_confidence": {"$max": "$confidence"},
        }},
        {"$match": {"count": {"$gt": 1}}},
    ]

    dup_count = 0
    merged = 0

    async for group in coll.aggregate(pipeline):
        dup_count += group["count"]
        key = group["_id"]

        # Flatten tags
        all_tags = []
        for tag_list in group.get("all_tags", []):
            if isinstance(tag_list, list):
                all_tags.extend(tag_list)
        unique_tags = list(set(all_tags))

        chain = group["chains"][0] if group["chains"] else "ethereum"

        # Delete all duplicates
        await coll.delete_many({"_id": {"$in": group["ids"]}})

        # Insert merged document
        await coll.insert_one({
            "source_id": key["source_id"],
            "target_id": key["target_id"],
            "relation_type": key["relation_type"],
            "chain": chain,
            "total_tx_count": group["total_tx_count"],
            "total_amount_usd": group["total_amount_usd"],
            "first_seen": group["min_first_seen"],
            "last_seen": group["max_last_seen"],
            "confidence": group["max_confidence"],
            "tags": unique_tags,
        })
        merged += 1

    after = await coll.count_documents({})
    print(f"[PackRelations] Found {dup_count} duplicate docs across {merged} groups")
    print(f"[PackRelations] Relations after packing: {after}")

    # Step 2: Create unique index
    print("[PackRelations] Creating unique compound index...")
    try:
        await coll.create_index(
            [("source_id", 1), ("target_id", 1), ("relation_type", 1)],
            unique=True,
            name="packed_relation_unique"
        )
        print("[PackRelations] Unique index created successfully.")
    except Exception as e:
        print(f"[PackRelations] Index creation error: {e}")

    # Step 3: Add single-field indexes for fast expand
    for field in ["source_id", "target_id"]:
        try:
            await coll.create_index(field)
            print(f"[PackRelations] Index on '{field}' created.")
        except Exception:
            pass

    client.close()
    print("[PackRelations] Done.")


if __name__ == "__main__":
    asyncio.run(pack())
