"""
Build Relation Buckets — Temporal Optimization Layer
=====================================================
Aggregates graph_relations into daily buckets for fast temporal queries.

Schema:
  {
    source_id, target_id, relation_type, chain,
    bucket_day: "2025-03-15",
    tx_count, total_amount_usd, last_seen
  }

Run:  cd /app/backend && python build_relation_buckets.py
"""

import asyncio
import os
import time
from datetime import datetime, timezone

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

from graph_storage import init_storage, ensure_storage_indexes


async def main():
    load_dotenv()
    client = AsyncIOMotorClient(os.environ.get("MONGO_URL"))
    db = client[os.environ.get("DB_NAME", "intelligence_engine")]
    init_storage(db)
    await ensure_storage_indexes()

    start = time.time()
    print("=" * 60)
    print("BUILDING RELATION BUCKETS")
    print("=" * 60)

    rels_coll = db["graph_relations"]
    buckets_coll = db["graph_relation_buckets"]

    # Clear existing buckets
    deleted = await buckets_coll.delete_many({})
    print(f"Cleared {deleted.deleted_count} old buckets")

    total_rels = await rels_coll.count_documents({})
    print(f"Processing {total_rels} relations...")

    cursor = rels_coll.find({}, {"_id": 0})
    processed = 0
    bucket_ops = []

    async for rel in cursor:
        source_id = rel.get("source_id", "")
        target_id = rel.get("target_id", "")
        relation_type = rel.get("relation_type", "transfer")
        chain = rel.get("chain", "ethereum")
        tx_count = rel.get("tx_count", 1)
        total_usd = rel.get("total_amount_usd", 0)
        first_seen = rel.get("first_seen", 0)
        last_seen = rel.get("last_seen", 0)

        # Determine bucket days from first_seen and last_seen
        # If timestamps are valid, create one bucket per relation
        # (with the day of last_seen as the bucket_day)
        if last_seen and last_seen > 1000000000:
            bucket_day = datetime.fromtimestamp(last_seen, tz=timezone.utc).strftime("%Y-%m-%d")
        elif first_seen and first_seen > 1000000000:
            bucket_day = datetime.fromtimestamp(first_seen, tz=timezone.utc).strftime("%Y-%m-%d")
        else:
            bucket_day = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        bucket_doc = {
            "source_id": source_id,
            "target_id": target_id,
            "relation_type": relation_type,
            "chain": chain,
            "bucket_day": bucket_day,
            "tx_count": tx_count,
            "total_amount_usd": total_usd,
            "first_seen": first_seen,
            "last_seen": last_seen,
        }

        bucket_ops.append(bucket_doc)
        processed += 1

        # Batch insert every 500
        if len(bucket_ops) >= 500:
            await buckets_coll.insert_many(bucket_ops)
            bucket_ops = []
            if processed % 2000 == 0:
                print(f"  Processed {processed}/{total_rels}...")

    # Flush remaining
    if bucket_ops:
        await buckets_coll.insert_many(bucket_ops)

    bucket_count = await buckets_coll.count_documents({})
    elapsed = round(time.time() - start, 1)

    # Stats: distinct days
    days = await buckets_coll.distinct("bucket_day")

    print("=" * 60)
    print(f"DONE in {elapsed}s")
    print(f"  Relations processed: {processed}")
    print(f"  Buckets created: {bucket_count}")
    print(f"  Distinct days: {len(days)}")
    if days:
        days_sorted = sorted(days)
        print(f"  Range: {days_sorted[0]} → {days_sorted[-1]}")
    print("=" * 60)

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
